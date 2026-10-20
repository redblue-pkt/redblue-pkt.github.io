const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const page = fs.readFileSync(path.join(__dirname, '../../ATC_MiThermometer/TelinkMiFlasher.html'), 'utf8');

test('brightness slider persists, verifies and then previews; duration is independent', async () => {
	const commands = [];
	const errors = [];
	const saved = [5, 3, 1, 0, 0, 1];
	let seconds = 8;
	const elements = {
		cgd1Brightness: {value: '2'},
		cgd1Volume: {value: '3'},
		cfg_flg_am_pm: {checked: true},
		cgd1LightSeconds: {value: '8'}
	};
	const ctx = {
		Uint8Array, DataView, Promise, Set, Number, Error,
		$: id => elements[id],
		addLog: value => errors.push(value),
		async cgd1Call(sub, data) {
			commands.push([sub, ...data]);
			const r = new DataView(new ArrayBuffer(24));
			if (sub === 1) {
				r.setUint8(4, saved[0]);
				r.setUint8(5, saved[1]);
				r.setUint8(6, saved[2]);
				r.setUint8(10, saved[5]);
			} else if (sub === 2) {
				saved.splice(0, saved.length, ...data);
			} else if (sub === 0x1c) {
				if (data.length) seconds = data[0];
				r.setUint8(3, seconds);
			}
			return r;
		}
	};
	vm.createContext(ctx);
	vm.runInContext(page.slice(page.indexOf('let cgd1SettingsQueue ='), page.indexOf('function cgd1Crc32(')), ctx);
	vm.runInContext(page.slice(page.indexOf('let cgd1SliderPending ='), page.indexOf('async function cgd1DeleteAlarm(')), ctx);
	vm.runInContext("cgd1SliderPending.add('light')", ctx);
	await ctx.cgd1FlushSliders();
	assert.deepEqual(commands, [[1], [2, 2, 3, 1, 0, 0, 1], [1], [0x1a]]);
	assert.equal(seconds, 8);
	assert.deepEqual(errors, []);
	commands.length = 0;
	elements.cgd1LightSeconds.value = '12';
	await ctx.cgd1SetLightSeconds();
	assert.deepEqual(commands, [[0x1c, 12]]);
	assert.equal(seconds, 12);
	assert.equal(saved[0], 2);
	assert.deepEqual(errors, []);
});

test('v91 download references resolve to a valid sized firmware file', () => {
	assert.equal((page.match(/CGD1_v91\.bin/g) || []).length, 2);
	assert.ok(!page.includes('CGD1_v90.bin'));
	const bin = fs.readFileSync(path.join(__dirname, '../../ATC_MiThermometer/CGD1/CGD1_v91.bin'));
	assert.equal(bin.length, 114036);
	assert.ok(bin.length <= 0x20000);
});
