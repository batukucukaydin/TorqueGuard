const $ = id => document.getElementById(id);
let presets = {}, activeScenario = {}, replay = null, report = null;
const format = (v, digits=1) => Number(v).toFixed(digits);

async function api(path, payload) {
  const response = await fetch(path, payload === undefined ? {} : {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)});
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'Request failed');
  return data;
}
function error(err) { $('error').textContent = err.message; $('error').hidden = false; }
function setValues(s) {
  activeScenario = {...s};
  $('speed').value = s.initial_speed_kph; $('throttle').value = s.throttle*100;
  $('soc').value = s.soc*100; $('grip').value = s.grip*100;
  $('power').value = s.deployment_limit_kw; $('wet').checked = s.wet;
  $('restricted').checked = s.restricted_sector; $('brake').checked = s.brake_overlap;
  $('clutch').checked = s.clutch_engaged; $('engine').checked = s.engine_available; updateOutputs();
  renderEvents(s.events || []);
}
function updateOutputs() {
  $('speed-value').textContent = `${$('speed').value} km/h`;
  $('throttle-value').textContent = `${$('throttle').value}%`;
  $('soc-value').textContent = `${$('soc').value}%`;
  $('grip-value').textContent = format($('grip').value/100, 2);
}
function collect() {
  return {...activeScenario, initial_speed_kph:Number($('speed').value), throttle:$('throttle').value/100,
    soc:$('soc').value/100, grip:$('grip').value/100, deployment_limit_kw:Number($('power').value),
    wet:$('wet').checked, restricted_sector:$('restricted').checked, brake_overlap:$('brake').checked,
    clutch_engaged:$('clutch').checked, engine_available:$('engine').checked, events:collectEvents()};
}

const SIGNALS = {
  throttle:{label:'Throttle / %',scale:100,max:100,step:1},
  brake:{label:'Brake / %',scale:100,max:100,step:1},
  wet:{label:'Wet-weather mode',boolean:true},
  restricted_sector:{label:'Sector restriction',boolean:true},
  sector:{label:'Sector ID',scale:1,max:99,step:1},
  deployment_limit_kw:{label:'Deployment cap / kW',scale:1,max:350,step:1},
  grip:{label:'Grip coefficient',scale:1,max:1,step:.01},
  clutch_engaged:{label:'Clutch engaged',boolean:true},
  engine_available:{label:'ICE available',boolean:true}
};
function eventRow(time, label, field, value) {
  const row=document.createElement('tr');
  const timeInput=document.createElement('input');timeInput.type='number';timeInput.min=0;
  timeInput.max=activeScenario.duration_s-.02;timeInput.step=.02;timeInput.value=time;timeInput.required=true;
  timeInput.className='event-time';timeInput.setAttribute('aria-label','Event time in seconds');
  const labelInput=document.createElement('input');labelInput.value=label;labelInput.maxLength=80;labelInput.required=true;
  labelInput.className='event-label';labelInput.setAttribute('aria-label','Event label');
  const fieldInput=document.createElement('select');fieldInput.className='event-field';fieldInput.setAttribute('aria-label','Event signal');
  for(const [key,meta] of Object.entries(SIGNALS)) {
    const option=document.createElement('option');option.value=key;option.textContent=meta.label;fieldInput.append(option);
  }
  fieldInput.value=field;
  const valueCell=document.createElement('td');
  function valueControl(initial) {
    const meta=SIGNALS[fieldInput.value];let input;
    if(meta.boolean) {
      input=document.createElement('select');
      for(const [val,text] of [['true','On'],['false','Off']]) {
        const option=document.createElement('option');option.value=val;option.textContent=text;input.append(option);
      }
      input.value=String(initial);
    } else {
      input=document.createElement('input');input.type='number';input.min=0;input.max=meta.max;input.step=meta.step;
      input.value=Number(initial)*meta.scale;input.required=true;
    }
    input.className='event-value';input.setAttribute('aria-label',meta.label+' value');valueCell.replaceChildren(input);
  }
  valueControl(value);
  fieldInput.addEventListener('change',()=>valueControl(SIGNALS[fieldInput.value].boolean?true:fieldInput.value==='throttle'?.85:0));
  for(const control of [timeInput,labelInput,fieldInput]) {
    const cell=document.createElement('td');cell.append(control);row.append(cell);
  }
  row.append(valueCell);
  const removeCell=document.createElement('td'),remove=document.createElement('button');
  remove.type='button';remove.className='remove-event';remove.textContent='×';remove.setAttribute('aria-label','Remove input change');
  remove.addEventListener('click',()=>{row.remove();$('event-empty').hidden=$('event-rows').children.length>0;});
  removeCell.append(remove);row.append(removeCell);$('event-rows').append(row);
  $('event-empty').hidden=true;
}
function renderEvents(events) {
  $('event-rows').replaceChildren();$('event-empty').hidden=false;
  for(const event of events) {
    for(const [field,value] of Object.entries(event)) {
      if(field in SIGNALS && value !== null) eventRow(event.time_s,event.label,field,value);
    }
  }
}
function collectEvents() {
  const groups=new Map();
  for(const row of $('event-rows').children) {
    for(const input of row.querySelectorAll('input')) {
      if(!input.checkValidity()) throw new Error('Complete all event fields with valid values on the 20 ms grid.');
    }
    const time=Number(row.querySelector('.event-time').value),field=row.querySelector('.event-field').value;
    const group=groups.get(time)||{time_s:time,label:row.querySelector('.event-label').value};
    if(field in group) throw new Error(`The ${field} signal appears twice at ${time} s.`);
    const raw=row.querySelector('.event-value').value;
    group[field]=SIGNALS[field].boolean?raw==='true':Number(raw)/SIGNALS[field].scale;
    groups.set(time,group);
  }
  return [...groups.values()].sort((a,b)=>a.time_s-b.time_s);
}
function svgElement(name, attrs={}, value) {
  const node = document.createElementNS('http://www.w3.org/2000/svg', name);
  Object.entries(attrs).forEach(([k,v]) => node.setAttribute(k,v));
  if (value !== undefined) node.textContent = value;
  return node;
}
function chart(id, field, h) {
  const a = replay.runs.faulty.trace, b = replay.runs.corrected.trace;
  const w=700, pad={left:53,right:18,top:22,bottom:30}, last=a.at(-1).time_s;
  const max=Math.max(10, ...a.map(s=>s[field]), ...b.map(s=>s[field])) * 1.15;
  const min=Math.min(0, ...a.map(s=>s[field]), ...b.map(s=>s[field])) * 1.1;
  const x=t=>pad.left + t/last*(w-pad.left-pad.right);
  const y=v=>pad.top+(max-v)/(max-min)*(h-pad.top-pad.bottom);
  const svg=svgElement('svg',{viewBox:`0 0 ${w} ${h}`, 'aria-hidden':'true'});
  let demandStart=null;
  a.forEach((sample,index)=>{
    const demanding=sample.throttle>=.7 && sample.brake<.05 && sample.clutch_engaged;
    if(demanding && demandStart===null) demandStart=sample.time_s;
    if(demandStart!==null && (!demanding || index===a.length-1)) {
      svg.append(svgElement('rect',{x:x(demandStart),y:pad.top,width:Math.max(0,x(sample.time_s)-x(demandStart)),height:h-pad.top-pad.bottom,fill:'#1e2920'}));
      demandStart=null;
    }
  });
  for(let i=0;i<5;i++) {
    const v=min+(max-min)*i/4;
    svg.append(svgElement('line',{x1:pad.left,x2:w-pad.right,y1:y(v),y2:y(v),class:'chart-grid'}));
    svg.append(svgElement('text',{x:pad.left-9,y:y(v)+3,'text-anchor':'end',class:'chart-text'},Math.round(v).toLocaleString()));
  }
  for(let t=0;t<=last;t++) svg.append(svgElement('text',{x:x(t),y:h-9,'text-anchor':'middle',class:'chart-text'},`${t}s`));
  const firstDemand=a.find(sample=>sample.throttle>=.7 && sample.brake<.05 && sample.clutch_engaged);
  if(firstDemand) svg.append(svgElement('text',{x:Math.min(x(firstDemand.time_s)+8,w-120),y:13,class:'chart-annotation'},'DRIVER DEMAND'));
  for(const event of replay.input_events || []) {
    const line=svgElement('line',{x1:x(event.time_s),x2:x(event.time_s),y1:pad.top,y2:h-pad.bottom,class:'chart-event'});
    line.append(svgElement('title',{},`${format(event.time_s,2)} s: ${event.label}`));svg.append(line);
  }
  for(const [data, cls] of [[b,'chart-fixed'],[a,'chart-faulty']]) {
    svg.append(svgElement('path',{d:data.map((s,i)=>`${i?'L':'M'}${x(s.time_s).toFixed(2)},${y(s[field]).toFixed(2)}`).join(' '),class:`chart-line ${cls}`}));
  }
  const cursor=svgElement('line',{x1:0,x2:0,y1:pad.top,y2:h-pad.bottom,class:'chart-cursor','data-cursor':'true'});
  svg.append(cursor); $(id).replaceChildren(svg); return x;
}
let torqueX, speedX;
function cursor() {
  if(!replay) return;
  const i=Number($('timeline').value), a=replay.runs.faulty.trace[i], b=replay.runs.corrected.trace[i];
  $('time-value').textContent = `${format(a.time_s,2)} s`;
  $('signal-throttle').textContent = `${format(a.throttle*100,0)}%`;
  $('signal-state').textContent = a.state;
  $('signal-power').textContent = `${format(a.mgu_power_kw)} kW`;
  $('signal-soc').textContent = `${format(b.soc*100,2)}%`;
  $('signal-sector').textContent = `${a.sector} / ${a.restricted_sector?'Restricted':'Open'}`;
  $('signal-weather').textContent = `${a.wet?'Wet':'Dry'} / ${format(a.deployment_limit_kw,0)} kW`;
  $('signal-brake').textContent = `${format(a.brake*100,0)}% / ${a.clutch_engaged?'Engaged':'Open'}`;
  const latest=(replay.input_events || []).filter(event=>event.time_s<=a.time_s).at(-1);
  $('signal-event').textContent=latest?latest.label:'Base schedule';
  $('signal-event').title=$('signal-event').textContent;
  for(const [id,scale] of [['torque-chart',torqueX],['speed-chart',speedX]]) {
    const node=$(id).querySelector('[data-cursor]'); node.setAttribute('x1',scale(a.time_s)); node.setAttribute('x2',scale(a.time_s));
  }
}
function renderReplay() {
  const a=replay.runs.faulty, b=replay.runs.corrected;
  $('horizon').textContent = `${format(replay.scenario.duration_s,2)} s`;
  const events=replay.input_events || [];
  $('scenario-schedule').textContent = `Base restart at ${format(replay.scenario.hold_s,1)} s · ${format(replay.scenario.duration_s,1)} s horizon · ${events.length} scheduled events.`;
  for(const [id,run] of [['baseline-status',a],['corrected-status',b]]) {
    $(id).textContent=run.passed?'PASS':'FAIL'; $(id).className=run.passed?'good':'bad';
  }
  $('baseline-detail').textContent=a.passed?'No monitored invariant violation':a.findings.map(x=>x.code).join(', ');
  $('corrected-detail').textContent=b.passed?'All modeled response checks pass':b.findings.map(x=>x.code).join(', ');
  $('starvation').replaceChildren(document.createTextNode(format(a.max_starvation_s,2)+' '));
  const sec=document.createElement('em');sec.textContent='s';$('starvation').append(sec);
  $('restart-speed').replaceChildren(document.createTextNode(format(b.final_speed_kph)+' '));
  const unit=document.createElement('em');unit.textContent='km/h';$('restart-speed').append(unit);
  torqueX=chart('torque-chart','wheel_torque_nm',235);speedX=chart('speed-chart','speed_kph',180);
  $('timeline').max=a.trace.length-1; $('timeline').value=Math.min(a.trace.length-1,Math.round((replay.scenario.hold_s+.5)/replay.dt_s));
  $('transitions').replaceChildren();
  for(const item of a.transitions) {
    const row=document.createElement('div');row.className='state-row';
    const time=document.createElement('time');time.textContent=`${format(item.time_s,2)}s`;
    const text=document.createElement('span');text.textContent=`${item.from} → `;
    const state=document.createElement('b');state.textContent=item.to;
    row.append(time,text,state);$('transitions').append(row);
  }
  const finding=a.findings[0];$('finding').className=`finding${a.passed?' good':''}`;
  $('finding').textContent=finding?`${finding.code} at ${format(finding.time_s,2)}s\n${finding.reason}`:'No violation observed. Legitimate torque inhibitions are excluded from the liveness check.';
  cursor();
}
async function runReplay(s) {
  $('replay-button').disabled=true;$('error').hidden=true;
  try { replay=await api('/api/replay',s);renderReplay(); }
  catch(err) { error(err); }
  finally { $('replay-button').disabled=false; }
}
function download(data, name) {
  const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));
  const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
$('scenario-form').addEventListener('submit',e=>{e.preventDefault();try{runReplay(collect());}catch(err){error(err);}});
$('event-form').addEventListener('submit',e=>{
  e.preventDefault();try{$('preset').value='custom_timeline';runReplay(collect());}catch(err){error(err);}
});
$('add-event').addEventListener('click',()=>{
  const times=[...$('event-rows').children].map(row=>Number(row.querySelector('.event-time').value));
  const next=times.length?Math.max(...times)+.2:1;
  if(next>=activeScenario.duration_s) {error(new Error('No room for another event before the horizon.'));return;}
  eventRow(Number(next.toFixed(2)),'Driver input','throttle',.85);
});
$('preset').addEventListener('change',()=>{setValues(presets[$('preset').value]);runReplay(collect());});
for(const id of ['speed','throttle','soc','grip']) $(id).addEventListener('input',updateOutputs);
$('timeline').addEventListener('input',cursor);
$('export-button').addEventListener('click',()=>{if(replay)download(replay,'torqueguard-replay.json');});
$('campaign-export').addEventListener('click',()=>{if(report)download(report,`torqueguard-campaign-${report.seed}.json`);});
$('campaign-form').addEventListener('submit',async e=>{
  e.preventDefault();$('campaign-button').disabled=true;$('error').hidden=true;
  $('campaign-result').textContent='Running paired trajectories…';$('witness-button').hidden=true;$('campaign-export').hidden=true;
  try {
    report=await api('/api/campaign',{seed:Number($('seed').value),cases:Number($('cases').value),profile:$('profile').value});
    const result=$('campaign-result');result.replaceChildren();
    for(const [label,val,cls] of [['TRAJECTORIES',report.cases,''],['BASELINE FAILURES',report.failures.faulty,'bad'],['CORRECTED FAILURES',report.failures.corrected,report.failures.corrected?'bad':''],['RESCUED CASES',report.rescued_cases,'']]) {
      const line=document.createElement('div'),value=document.createElement('b');value.className=cls;value.textContent=val.toLocaleString();line.append(`${label}  `,value);result.append(line);
    }
    const note=document.createElement('div');note.textContent=`${report.profile} profile · ${report.scheduled_events} scheduled events · ${report.condition_combinations_observed}/32 condition combinations observed · seed ${report.seed}. Sampled coverage only.`;result.append(note);
    $('witness-button').hidden=!report.first_counterexample;$('campaign-export').hidden=false;
  } catch(err) { error(err);$('campaign-result').textContent='Campaign failed. Adjust the input and retry.'; }
  finally { $('campaign-button').disabled=false; }
});
$('witness-button').addEventListener('click',()=>{if(report?.first_counterexample){$('preset').value='counterexample';setValues(report.first_counterexample.scenario);runReplay(activeScenario);$('lab').scrollIntoView();}});
(async()=>{try{presets=await api('/api/presets');setValues(presets.wet_concertina);await runReplay(collect());}catch(err){error(err);}})();
