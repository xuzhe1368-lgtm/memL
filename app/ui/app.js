const $ = (id) => document.getElementById(id);
let cfg = { apiUrl: localStorage.getItem('meml_api') || 'http://127.0.0.1:8000', token: sessionStorage.getItem('meml_token') || '' };
$('apiUrl').value = cfg.apiUrl; $('token').value = cfg.token;

function headers(){ return { 'Authorization': `Bearer ${cfg.token}`, 'Content-Type':'application/json' }; }
async function req(path, opts={}){ const r = await fetch(cfg.apiUrl + path, { ...opts, headers: { ...headers(), ...(opts.headers||{}) } }); const j = await r.json(); if(!r.ok || j.ok===false) throw new Error(j?.error?.message || j?.detail || r.statusText); return j; }

function drawBars(items){
  const cvs = $('bar'); const ctx = cvs.getContext('2d'); ctx.clearRect(0,0,cvs.width,cvs.height);
  const day = new Map();
  items.forEach(x=>{ const d=(x.updated||'').slice(0,10); day.set(d,(day.get(d)||0)+1); });
  const keys=[...day.keys()].sort().slice(-7); const vals=keys.map(k=>day.get(k)); const max=Math.max(1,...vals);
  const w=48, gap=10; keys.forEach((k,i)=>{ const h=Math.round((vals[i]/max)*90); const x=20+i*(w+gap), y=110-h; ctx.fillStyle='#5b8def'; ctx.fillRect(x,y,w,h); ctx.fillStyle='#6b7583'; ctx.font='10px sans-serif'; ctx.fillText(k.slice(5),x,128); });
}

function drawDonut(items){
  const cvs=$('donut'); const ctx=cvs.getContext('2d'); ctx.clearRect(0,0,cvs.width,cvs.height);
  const cnt=new Map(); items.forEach(x=>(x.tags||[]).forEach(t=>cnt.set(t,(cnt.get(t)||0)+1)));
  const top=[...cnt.entries()].sort((a,b)=>b[1]-a[1]).slice(0,5); const total=top.reduce((s,[_k,v])=>s+v,0)||1;
  let start=-Math.PI/2; const colors=['#5b8def','#f59e0b','#10b981','#ef4444','#8b5cf6'];
  top.forEach(([k,v],i)=>{ const ang=(v/total)*Math.PI*2; ctx.beginPath(); ctx.moveTo(110,70); ctx.arc(110,70,55,start,start+ang); ctx.closePath(); ctx.fillStyle=colors[i%colors.length]; ctx.fill(); start+=ang; });
  ctx.globalCompositeOperation='destination-out'; ctx.beginPath(); ctx.arc(110,70,28,0,Math.PI*2); ctx.fill(); ctx.globalCompositeOperation='source-over';
  ctx.fillStyle='#1b2430'; ctx.font='bold 12px sans-serif'; ctx.fillText(String(total),104,74);
}

function aggregate(items){
  const tagCount = new Map(); items.forEach(x => (x.tags||[]).forEach(t=>tagCount.set(t,(tagCount.get(t)||0)+1)));
  const topTags = [...tagCount.entries()].sort((a,b)=>b[1]-a[1]).slice(0,12);
  $('tags').innerHTML = topTags.map(([t,n])=>`<span class='tag'>#${t} (${n})</span>`).join('') || '暂无';
  const cats = [
    ['偏好 preference', [...tagCount.entries()].filter(([k])=>/pref|偏好/.test(k)).reduce((s,[_k,v])=>s+v,0)],
    ['身份 identity', [...tagCount.entries()].filter(([k])=>/identity|身份/.test(k)).reduce((s,[_k,v])=>s+v,0)],
    ['项目 project', [...tagCount.entries()].filter(([k])=>/project|roadmap|meml/.test(k)).reduce((s,[_k,v])=>s+v,0)],
  ];
  $('cats').innerHTML = cats.map(([k,v])=>`<div class='cat'><span>${k}</span><b>${v}</b></div>`).join('');
  drawBars(items); drawDonut(items);
}

function bindList(items){
  $('list').innerHTML = items.map((x,i)=>`<div class="item" data-i="${i}"><div>${x.text}</div><div class="meta">${x.id} · ${x.updated} · score:${x.score??'-'}</div><div>${(x.tags||[]).map(t=>`<span class='tag'>#${t}</span>`).join('')}</div></div>`).join('') || '<div class="item">暂无数据</div>';
  [...document.querySelectorAll('.item[data-i]')].forEach(el=>el.onclick=()=>{ const x=items[Number(el.dataset.i)]; $('drawerBody').textContent=JSON.stringify(x,null,2); $('drawer').classList.remove('hidden'); });
}

async function refreshStats(){
  const stats = await req('/stats'); $('total').textContent = stats.data.total_memories;
  try{ const m = await (await fetch(cfg.apiUrl + '/metrics')).json(); $('writes').textContent = m?.data?.memory_writes_total ?? '-'; $('searches').textContent = m?.data?.memory_search_total ?? '-'; }
  catch{ $('writes').textContent='-'; $('searches').textContent='-'; }
}

async function loadAll(){ const r = await req('/memory?limit=80'); bindList(r.data.results); aggregate(r.data.results); await refreshStats(); }

$('connectBtn').onclick = async ()=>{
  cfg.apiUrl=$('apiUrl').value.trim();
  cfg.token=$('token').value.trim();
  localStorage.setItem('meml_api',cfg.apiUrl);
  sessionStorage.setItem('meml_token', cfg.token);
  await loadAll();
};

$('disconnectBtn').onclick = ()=>{
  cfg.token='';
  sessionStorage.removeItem('meml_token');
  $('token').value='';
  $('list').innerHTML = '<div class="item">已断开，请重新连接</div>';
};
$('searchBtn').onclick = async ()=>{ const q=$('q').value.trim(); const r=await req('/memory?limit=80&q='+encodeURIComponent(q)); bindList(r.data.results); aggregate(r.data.results); await refreshStats(); };
$('saveBtn').onclick = async ()=>{ const text=$('newText').value.trim(); if(!text) return; await req('/memory',{method:'POST',body:JSON.stringify({text,tags:['ui']})}); $('newText').value=''; await loadAll(); };
$('closeDrawer').onclick = ()=> $('drawer').classList.add('hidden');

