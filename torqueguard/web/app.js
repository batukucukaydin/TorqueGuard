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
    clutch_engaged:$('clutch').checked, engine_available:$('engine').checked};
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
  svg.append(svgElement('rect',{x:x(replay.scenario.hold_s), y:pad.top, width:x(last)-x(replay.scenario.hold_s), height:h-pad.top-pad.bottom, fill:'#1e2920'}));
  for(let i=0;i<5;i++) {
    const v=min+(max-min)*i/4;
    svg.append(svgElement('line',{x1:pad.left,x2:w-pad.right,y1:y(v),y2:y(v),class:'chart-grid'}));
    svg.append(svgElement('text',{x:pad.left-9,y:y(v)+3,'text-anchor':'end',class:'chart-text'},Math.round(v).toLocaleString()));
  }
  for(let t=0;t<=last;t++) svg.append(svgElement('text',{x:x(t),y:h-9,'text-anchor':'middle',class:'chart-text'},`${t}s`));
  svg.append(svgElement('text',{x:x(replay.scenario.hold_s)+8,y:13,class:'chart-annotation'},'RESTART DEMAND'));
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
  for(const [id,scale] of [['torque-chart',torqueX],['speed-chart',speedX]]) {
    const node=$(id).querySelector('[data-cursor]'); node.setAttribute('x1',scale(a.time_s)); node.setAttribute('x2',scale(a.time_s));
  }
}
function renderReplay() {
  const a=replay.runs.faulty, b=replay.runs.corrected;
  $('horizon').textContent = `${format(replay.scenario.duration_s,2)} s`;
  $('scenario-schedule').textContent = `Brake, then restart at t = ${format(replay.scenario.hold_s,1)} s. ${format(replay.scenario.duration_s,1)} s horizon · fixed sector configuration.`;
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
  for(const item of a.transitions.slice(0,4)) {
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
$('scenario-form').addEventListener('submit',e=>{e.preventDefault();runReplay(collect());});
$('preset').addEventListener('change',()=>{setValues(presets[$('preset').value]);runReplay(collect());});
for(const id of ['speed','throttle','soc','grip']) $(id).addEventListener('input',updateOutputs);
$('timeline').addEventListener('input',cursor);
$('export-button').addEventListener('click',()=>{if(replay)download(replay,'torqueguard-replay.json');});
$('campaign-export').addEventListener('click',()=>{if(report)download(report,`torqueguard-campaign-${report.seed}.json`);});
$('campaign-form').addEventListener('submit',async e=>{
  e.preventDefault();$('campaign-button').disabled=true;$('error').hidden=true;
  $('campaign-result').textContent='Running paired trajectories…';$('witness-button').hidden=true;$('campaign-export').hidden=true;
  try {
    report=await api('/api/campaign',{seed:Number($('seed').value),cases:Number($('cases').value)});
    const result=$('campaign-result');result.replaceChildren();
    for(const [label,val,cls] of [['TRAJECTORIES',report.cases,''],['BASELINE FAILURES',report.failures.faulty,'bad'],['CORRECTED FAILURES',report.failures.corrected,report.failures.corrected?'bad':''],['RESCUED CASES',report.rescued_cases,'']]) {
      const line=document.createElement('div'),value=document.createElement('b');value.className=cls;value.textContent=val.toLocaleString();line.append(`${label}  `,value);result.append(line);
    }
    const note=document.createElement('div');note.textContent=`${report.condition_combinations_observed}/32 boolean condition combinations observed · seed ${report.seed}. Sampled coverage only.`;result.append(note);
    $('witness-button').hidden=!report.first_counterexample;$('campaign-export').hidden=false;
  } catch(err) { error(err);$('campaign-result').textContent='Campaign failed. Adjust the input and retry.'; }
  finally { $('campaign-button').disabled=false; }
});
$('witness-button').addEventListener('click',()=>{if(report?.first_counterexample){$('preset').value='counterexample';setValues(report.first_counterexample.scenario);runReplay(activeScenario);$('lab').scrollIntoView();}});
(async()=>{try{presets=await api('/api/presets');setValues(presets.wet_concertina);await runReplay(collect());}catch(err){error(err);}})();
