const fs = require('fs'), vm = require('vm');
const path = require('node:path');
const page = fs.readFileSync(path.join(__dirname, '../../ATC_MiThermometer/TelinkMiFlasher.html'), 'utf8');
const code = page.slice(page.indexOf('function CustomConfig()'), page.indexOf('\nfunction hex(number'));
let html='';const elements={custcfg:{}};
Object.defineProperty(elements.custcfg,'innerHTML',{get(){return html},set(s){html=s;for(const m of s.matchAll(/id="([^"]+)"/g))elements[m[1]]={};}});
const ctx={$: id=>{if(!elements[id])throw Error('missing element '+id);return elements[id];},menuUpgrade(){},InfoIntervals(){},cfg:{ver:0x67,flg:0x24,flg2:0x10,services:0xffff,hver:58,av_meas_mem:0,temp_offset:10,humi_offset:6,lcd_tint:49,advertising_interval:40,measure_interval:4,rf_tx_power:63,connect_latency:49},hwver_id:58,ext:{},trg:{},pincode:{},dnm:{},cmf:{},mikeys:{},cgd1Refresh(){},cgd1ReadSettings(){},cgd1ReadAlarm(){}};
vm.createContext(ctx);vm.runInContext(page.slice(page.indexOf('function cgd1AlarmPanel()'),page.indexOf('async function cgd1ReadAlarm()')),ctx);vm.runInContext(code,ctx);ctx.CustomConfig();
if(html.includes('extsmiley')||html.includes('clockDateTime'))throw Error('unwanted generic test/date panel');
if(html.indexOf('cgd1AlarmEnabled')<html.indexOf('Get Time</button>'))throw Error('alarm above time controls');
if(!html.includes('Get Time</button><br>Alarm'))throw Error('alarm not below time row');

for(const [before, after] of [['cgd1AlarmSlot','cgd1Volume'],['cgd1Volume','cgd1PcmFile'],['cgd1PcmFile','cgd1UploadProgress'],['cgd1UploadProgress','cgd1UploadButton']]) {
 if(html.indexOf(before) >= html.indexOf(after)) throw Error('Wrong row order '+before);
}
if(/class="cgd1AlarmDay"/.test(html)) throw Error('Weekday checkboxes');
if(!html.includes('Mon–Fri') || !html.includes('Sat–Sun')) throw Error('Missing repeat presets');
console.log('CGD1 generated UI: all referenced controls exist; alarm below legacy time row; no smiley/test/date panel');

ctx.cgd1StoreAudioSettings = async () => {};
ctx.addAlog = () => {};
ctx.sendCustomSetting = () => {};
vm.runInContext(page.slice(page.indexOf('function hex(number'), page.indexOf('</script>', page.indexOf('async function SendCustomConfig()'))),ctx);
ctx.SendCustomConfig().then(() => {
 if(ctx.cfg.flg2 !== 0x10) throw Error('PVVX config flags were added twice');
 if(!(ctx.cfg.flg & 32)) throw Error('Show battery flag lost');
 console.log('CGD1 Send Config: flags retained without double addition');
});

const controls = {
 cgd1AlarmSlot:{value:'5'}, cgd1AlarmDays:{value:'31'}, cgd1AlarmEnabled:{value:'1'},
 cgd1AlarmMaster:{value:'1'}, cgd1AlarmSnooze:{value:'1'}, cgd1AlarmTime:{value:'08:15'}, cgd1Status:{}
};
let stored;
const alarmContext = {Uint8Array, Number, Error, $:id=>controls[id], addLog(){},
 async cgd1Call(sub, bytes) {
  const r = new DataView(new ArrayBuffer(16));
  if(sub===4) { stored=Array.from(bytes); }
  if(sub===3) stored.forEach((v,i)=>r.setUint8(3+i,v));
  if(sub===7) r.setUint8(3,1);
  if(sub===0x17) r.setUint8(3,1);
  return r;
 }
};
vm.createContext(alarmContext);
vm.runInContext(page.slice(page.indexOf('async function cgd1WriteAlarm()'),page.indexOf('async function cgd1SetAlarmMaster()')),alarmContext);
alarmContext.cgd1WriteAlarm().then(()=>{
 if(JSON.stringify(stored)!==JSON.stringify([5,1,8,15,31,1])) throw Error('Selected slot/repeat/snooze not sent');
 if(controls.cgd1Status.textContent!=='Alarm saved') throw Error('Wrong confirmation');
 console.log('Alarm: selected slot, weekday preset, snooze and concise verified confirmation OK');
});
