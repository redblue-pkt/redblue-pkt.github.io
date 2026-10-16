const fs = require('fs'), vm = require('vm');
const path = require('node:path');
const page = fs.readFileSync(path.join(__dirname, '../../ATC_MiThermometer/TelinkMiFlasher.html'), 'utf8');
const code = page.slice(page.indexOf('function CustomConfig()'), page.indexOf('\nfunction hex(number'));
let html='';const elements={custcfg:{}};
Object.defineProperty(elements.custcfg,'innerHTML',{get(){return html},set(s){html=s;for(const m of s.matchAll(/id="([^"]+)"/g))elements[m[1]]={};}});
const ctx={$: id=>{if(!elements[id])throw Error('missing element '+id);return elements[id];},menuUpgrade(){},InfoIntervals(){},cfg:{ver:0x67,flg:0x24,flg2:0x10,services:0xffff,hver:58,av_meas_mem:0,temp_offset:10,humi_offset:6,lcd_tint:49,advertising_interval:40,measure_interval:4,rf_tx_power:63,connect_latency:49},hwver_id:58,ext:{},trg:{},pincode:{},dnm:{},cmf:{},mikeys:{},cgd1ReadSettings(){},cgd1ReadAlarm(){}};
vm.createContext(ctx);vm.runInContext(page.slice(page.indexOf('function cgd1AlarmPanel()'),page.indexOf('async function cgd1ReadAlarm()')),ctx);vm.runInContext(code,ctx);ctx.CustomConfig();
if(html.includes('extsmiley')||html.includes('clockDateTime'))throw Error('unwanted generic test/date panel');
if(html.indexOf('cgd1AlarmEnabled')<html.indexOf('Get Time</button>'))throw Error('alarm above time controls');
if(!html.includes('Get Time</button><br>Alarm'))throw Error('alarm not below time row');

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
