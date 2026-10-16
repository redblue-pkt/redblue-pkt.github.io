/* PVVX 0x23: local calendar time represented as LE32 seconds since 1970.
 * Shared by CGD1 (58) and LYWSD02MMC (49). No extra timezone command. */
(function(root) {
	'use strict';
	const api = {
		now(date) {
			return Math.floor(date.getTime() / 1000 - date.getTimezoneOffset() * 60);
		},
		parse(text) {
			const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2}))?$/.exec(text);
			if(!match) throw new Error('Select a valid date and time');
			const p = match.slice(1).map(v => Number(v || 0));
			const date = new Date(Date.UTC(p[0], p[1]-1, p[2], p[3], p[4], p[5]));
			if(date.getUTCFullYear() !== p[0] || date.getUTCMonth()+1 !== p[1] ||
				date.getUTCDate() !== p[2] || date.getUTCHours() !== p[3] ||
				date.getUTCMinutes() !== p[4] || date.getUTCSeconds() !== p[5])
				throw new Error('Invalid calendar date/time');
			const time = date.getTime()/1000;
			api.packet(time);
			return time;
		},
		packet(time) {
			if(!Number.isInteger(time) || time < 946684800 || time > 4102444799)
				throw new Error('RTC date must be between 2000 and 2099');
			const data = new Uint8Array(5);
			data[0] = 0x23;
			new DataView(data.buffer).setUint32(1, time, true);
			return data;
		},
		format(time) { return new Date(time*1000).toISOString().slice(0,19); }
	};
	if(typeof module !== 'undefined') module.exports = api;
	root.PVVXClock = api;
})(typeof window !== 'undefined' ? window : globalThis);
