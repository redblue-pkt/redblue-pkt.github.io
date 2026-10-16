const assert = require('node:assert/strict');
const clock = require('../../ATC_MiThermometer/pvvx-clock.js');
for(const civil of ['2000-01-01T00:00:00','2024-02-29T12:34:56','2026-10-25T02:30:00','2099-12-31T23:59:59']) {
 const t=clock.parse(civil), packet=clock.packet(t);
 assert.equal(clock.format(t),civil);
 assert.equal(packet[0],0x23);
 assert.equal(new DataView(packet.buffer).getUint32(1,true),t);
}
for(const civil of ['2025-02-29T12:00','2026-04-31T12:00','2026-01-01T24:00','1999-12-31T23:59','2100-01-01T00:00',''])
 assert.throws(()=>clock.parse(civil));
for(const offset of [-345,-120,0,300]) {
 const date={getTime:()=>1770000000123,getTimezoneOffset:()=>offset};
 assert.equal(clock.now(date),1770000000-offset*60);
}
console.log('PVVX clock: calendar boundaries, LE32, offsets and invalid dates passed');
