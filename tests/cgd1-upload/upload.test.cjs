const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {spawn} = require('node:child_process');
const readline = require('node:readline');
const page = fs.readFileSync(path.join(__dirname, '../../ATC_MiThermometer/TelinkMiFlasher.html'), 'utf8');
const code = page.slice(page.indexOf('function cgd1Le32('), page.indexOf('\nfunction setDevTime()'));

function transport(corrupt) {
	const child = spawn(process.env.CGD1_HOST, [], {env: {...process.env, ...(corrupt ? {CORRUPT: '1'} : {})}});
	let pending;
	const lines = readline.createInterface({input: child.stdout});
	lines.on('line', line => { const resolve = pending; pending = null; resolve(line); });
	child.stderr.pipe(process.stderr);
	return {
		async send(bytes) {
			const line = await new Promise(resolve => {
				assert.ok(!pending);
				pending = resolve;
				child.stdin.write(typeof bytes === 'string' ? bytes + '\n' : Buffer.from(bytes).toString('hex') + '\n');
			});
			if(typeof bytes === 'string') return line;
			const result = Uint8Array.from(line === '-' ? [] : Buffer.from(line, 'hex'));
			return new DataView(result.buffer);
		},
		close() { child.stdin.end(); lines.close(); child.kill(); }
	};
}
function context(device, pcm, droppedPacket = -1) {
	let packet = 0;
	const history = [];
	const elements = Object.fromEntries(['cgd1Status', 'cgd1PcmFile', 'cgd1UploadButton', 'cgd1UploadProgress'].map(id => [id, {}]));
	Object.defineProperty(elements.cgd1Status, 'textContent', {
		get() { return history.at(-1); }, set(value) { history.push(value); }
	});
	elements.cgd1PcmFile.files = [{name: 'test.pcm', arrayBuffer: async () => Uint8Array.from(pcm).buffer}];
	const sandbox = {
		Uint8Array, DataView, Date, Math, Number, String, Promise,
		window: {}, $: id => elements[id], addLog() {},
		setTimeout: cb => { cb(); },
		cgd1Call: async (sub, data) => {
			const response = await device.send(Uint8Array.from([sub, ...data]));
			if(response.getUint8(2)) throw new Error('device status ' + response.getUint8(2));
			return response;
		},
		settingsCharacteristics: {writeValueWithoutResponse: async bytes => {
			if(packet++ === droppedPacket) return;
			await device.send(bytes.slice(1));
		}}
	};
	vm.createContext(sandbox);
	vm.runInContext(code, sandbox);
	return {sandbox, elements, history};
}

test('actual browser upload against compiled firmware: 512 KiB, page writes, CRC, visible completion', async () => {
	const device = transport(false);
	try {
		const pcm = Uint8Array.from({length: 0x80000}, (_, i) => (i * 71 + 11) & 255);
		const {sandbox, elements, history} = context(device, pcm);
		await sandbox.cgd1UploadPcm();
		assert.match(elements.cgd1Status.textContent, /100%.*CRC verified, active/);
		assert.equal(elements.cgd1UploadProgress.value, 100);
		assert.equal(elements.cgd1UploadButton.disabled, false);
		assert.ok(history.some(x => /Sending: 50%/.test(x)));
		assert.equal(await device.send('stats'), '2048 128 524288');
	} finally { device.close(); }
});

test('CRC mismatch is reported as failure; no false saved confirmation', async () => {
	const device = transport(true);
	try {
		const {sandbox, elements} = context(device, new Uint8Array(513).fill(128));
		await sandbox.cgd1UploadPcm();
		assert.match(elements.cgd1Status.textContent, /^Transfer FAILED:.*CRC/);
		assert.equal(await device.send('stats'), '3 1 0');
	} finally { device.close(); }
});

test('dropped data packet is caught by firmware offset checks and byte-count verification', async () => {
	const device = transport(false);
	try {
		const {sandbox, elements} = context(device, new Uint8Array(513).fill(128), 2);
		await sandbox.cgd1UploadPcm();
		assert.match(elements.cgd1Status.textContent, /^Transfer FAILED:/);
		assert.equal(elements.cgd1UploadButton.disabled, false);
	} finally { device.close(); }
});

test('audio conversion requests mono 8000 Hz and emits unsigned PCM8', async () => {
	const {sandbox} = context(null, new Uint8Array(1));
	let requested;
	sandbox.window.AudioContext = class {
		async decodeAudioData() { return {duration: 1, sampleRate: 4000}; }
		async close() {}
	};
	sandbox.window.OfflineAudioContext = class {
		constructor(channels, length, rate) { requested = [channels, length, rate]; }
		createBufferSource() { return {connect() {}, start() {}}; }
		async startRendering() { return {getChannelData() { return Float32Array.from([0, 1, -1]); }}; }
	};
	const pcm = await sandbox.cgd1DecodeAudio({name: 'test.wav', arrayBuffer: async () => new ArrayBuffer(4)});
	assert.deepEqual(requested, [1, 8000, 8000]);
	assert.deepEqual([...pcm], [128, 255, 1]);
});
