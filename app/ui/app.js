const $ = (id) => document.getElementById(id);

let cfg = { apiUrl: localStorage.getItem('meml_api') || 'http://127.0.0.1:8000', token: localStorage.getItem('meml_token') || '' };
$('apiUrl').value = cfg.apiUrl;
$('token').value = cfg.token;

function headers(){ return { 'Authorization': `Bearer ${cfg.token}`, 'Content-Type':'application/json' }; }

async function req(path, opts={}){
  const r = await fetch(cfg.apiUrl + path, { ...opts, headers: { ...headers(), ...(opts.headers||{}) } });
  const j = await r.json();
  if(!r.ok || j.ok===false) throw new Error(j?.error?.message || j?.detail || r.statusText);
  return j;
}

function renderList(items){
  $('list').innerHTML = items.map(x=>`<div class="item"><div>${x.text}</div><div class="meta">${x.id} · ${x.updated} · score:${x.score??'-'}</div><div>${(x.tags||[]).map(t=>`<span class='tag'>#${t}</span>`).join('')}</div></div>`).join('') || '<div class="item">暂无数据</div>';
}

function aggregate(items){
  const tagCount = new Map();
  items.forEach(x => (x.tags||[]).forEach(t=>tagCount.set(t,(tagCount.get(t)||0)+1)));
  const topTags = [...tagCount.entries()].sort((a,b)=>b[1]-a[1]).slice(0,12);
  $('tags').innerHTML = topTags.map(([t,n])=>`<span class='tag'>#${t} (${n})</span>`).join('') || '暂无';

  const cats = [
    ['偏好 preference', [...tagCount.entries()].filter(([k])=>/pref|偏好/.test(k)).reduce((s,[_k,v])=>s+v,0)],
    ['身份 identity', [...tagCount.entries()].filter(([k])=>/identity|身份/.test(k)).reduce((s,[_k,v])=>s+v,0)],
    ['项目 project', [...tagCount.entries()].filter(([k])=>/project|roadmap|meml/.test(k)).reduce((s,[_k,v])=>s+v,0)],
  ];
  $('cats').innerHTML = cats.map(([k,v])=>`<div class='cat'><span>${k}</span><b>${v}</b></div>`).join('');
}

async function refreshStats(){
  const stats = await req('/stats');
  $('total').textContent = stats.data.total_memories;
  try{
    const m = await (await fetch(cfg.apiUrl + '/metrics')).json();
    $('writes').textContent = m?.data?.memory_writes_total ?? '-';
    $('searches').textContent = m?.data?.memory_search_total ?? '-';
  }catch{ $('writes').textContent='-'; $('searches').textContent='-'; }
}

async function loadAll(){
  const r = await req('/memory?limit=50');
  renderList(r.data.results);
  aggregate(r.data.results);
  await refreshStats();
}

$('connectBtn').onclick = async ()=>{
  cfg.apiUrl = $('apiUrl').value.trim(); cfg.token = $('token').value.trim();
  localStorage.setItem('meml_api', cfg.apiUrl); localStorage.setItem('meml_token', cfg.token);
  await loadAll();
};

$('searchBtn').onclick = async ()=>{
  const q = $('q').value.trim();
  const r = await req('/memory?limit=50&q=' + encodeURIComponent(q));
  renderList(r.data.results); aggregate(r.data.results); await refreshStats();
};

$('saveBtn').onclick = async ()=>{
  const text = $('newText').value.trim(); if(!text) return;
  await req('/memory', { method:'POST', body: JSON.stringify({ text, tags:['ui'] }) });
  $('newText').value='';
  await loadAll();
};
