const API = window.location.origin;
const toast = document.getElementById('toast');

let equityChart, allocChart, btEquityChart, pnlChart;
let strategyPage = 0;
const strategyPageSize = 25;

function showToast(msg) { toast.innerText = msg; toast.style.display = 'block'; setTimeout(()=>toast.style.display='none',4000); }

function fmt(n, d=2) { return (n==null||isNaN(n)) ? '-' : Number(n).toLocaleString(undefined,{maximumFractionDigits:d}); }
function fmtInt(n) { return (n==null||isNaN(n)) ? '-' : Number(n).toLocaleString(); }
function pct(n) { return (n==null||isNaN(n)) ? '-' : (Number(n)*100).toFixed(2)+'%'; }
function badge(s) { const c = (s||'').toLowerCase(); let cls='neutral'; if(['buy','filled','ok','completed','running'].includes(c)) cls='pos'; if(['sell','failed','error','rejected'].includes(c)) cls='neg'; return `<span class="badge ${cls}">${s||'-'}</span>`; }

async function fetchJSON(path, opts) {
  try {
    const r = await fetch(API+path, opts);
    if (!r.ok) {
      let msg = await r.text();
      try {
        const j = JSON.parse(msg);
        msg = j.detail || j.message || msg;
        if (Array.isArray(msg)) msg = msg.map(x => x.msg || JSON.stringify(x)).join('; ');
      } catch(_) {}
      throw new Error(msg || r.statusText);
    }
    return await r.json();
  } catch(e) { showToast('API error: '+(e.message||e)); throw e; }
}

function kpiCard(title, value, cls='') { return `<div class="card"><h3>${title}</h3><div class="value ${cls}">${value}</div></div>`; }

function hexToRgba(hex, alpha) {
  if (!hex) return 'rgba(0,212,170,'+alpha+')';
  if (hex.startsWith('rgb')) return hex.replace(')',','+alpha+')').replace('rgb','rgba');
  const h = hex.replace('#','');
  const full = h.length===3 ? h.split('').map(c=>c+c).join('') : h;
  const n = parseInt(full, 16);
  return 'rgba('+(n>>16&255)+','+(n>>8&255)+','+(n&255)+','+alpha+')';
}

function renderEquity(data, canvasId, label, color='#00d4aa') {
  const labels = (data||[]).map(d => d.timestamp ? new Date(d.timestamp).toLocaleDateString() : '');
  const vals = (data||[]).map(d => d.equity || 0);
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  if (equityChart && canvasId==='equityChart') { equityChart.destroy(); }
  if (btEquityChart && canvasId==='btEquityChart') { btEquityChart.destroy(); }
  const cfg = {
    type:'line',
    data:{labels, datasets:[{label, data:vals, borderColor:color, backgroundColor:hexToRgba(color,0.12), fill:true, tension:0.3, pointRadius:0}]},
    options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{x:{ticks:{maxTicksLimit:8,color:'#94a3b8'},grid:{color:'rgba(148,163,184,0.05)'}},y:{ticks:{color:'#94a3b8'},grid:{color:'rgba(148,163,184,0.05)'}}}}
  };
  if (canvasId==='equityChart') equityChart = new Chart(ctx,cfg);
  else if (canvasId==='btEquityChart') btEquityChart = new Chart(ctx,cfg);
}

function renderAllocation(positions) {
  const ctx = document.getElementById('allocChart').getContext('2d');
  if (allocChart) allocChart.destroy();
  const filtered = (positions||[]).filter(p => p.weight>0);
  const data = filtered.map(p => p.weight);
  const labels = filtered.map(p => p.symbol);
  const colors = ['#00d4aa','#3b82f6','#f59e0b','#ec4899','#8b5cf6','#10b981','#6366f1','#f43f5e','#06b6d4','#a855f7'];
  allocChart = new Chart(ctx, { type:'doughnut', data:{labels, datasets:[{data, backgroundColor:colors}]}, options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{labels:{color:'#e5e7eb'}}}}});
}

function renderMarketWatch(quotes) {
  const tbody = document.querySelector('#marketTable tbody');
  let prev = {};
  if (tbody.dataset.last) try { prev = JSON.parse(tbody.dataset.last); } catch(e){}
  tbody.innerHTML = (quotes||[]).map(q => {
    const last = q.last || 0, prevLast = prev[q.symbol] || last;
    const chg = prevLast ? (last-prevLast)/prevLast*100 : 0;
    const cls = chg>0 ? 'pos' : chg<0 ? 'neg' : '';
    return `<tr><td class="mono">${q.symbol}</td><td class="mono">${fmt(last)}</td><td class="mono">${fmt(q.bid)}</td><td class="mono">${fmt(q.ask)}</td><td class="mono ${cls}">${chg.toFixed(2)}%</td><td class="mono">${fmtInt(q.volume)}</td></tr>`;
  }).join('');
  const next = {};
  (quotes||[]).forEach(q => next[q.symbol]=q.last);
  tbody.dataset.last = JSON.stringify(next);
}

function renderOrderBook(book) {
  const el = document.getElementById('orderBook');
  if (!book) { el.innerHTML = '<div class="muted">No depth</div>'; return; }
  const asks = (book.asks||[]).slice().reverse();
  const bids = book.bids||[];
  el.innerHTML = `
    <div class="lob-side asks">${asks.map(a=>`<div class="lob-row ask"><span>${fmt(a[0],4)}</span><span>${fmtInt(a[1])}</span></div>`).join('')}</div>
    <div class="lob-mid mono">${fmt(book.mid||0,4)}</div>
    <div class="lob-side bids">${bids.map(b=>`<div class="lob-row bid"><span>${fmt(b[0],4)}</span><span>${fmtInt(b[1])}</span></div>`).join('')}</div>`;
}

function renderPositions(positions) {
  const tbody = document.querySelector('#positionsTable tbody');
  tbody.innerHTML = (positions||[]).map(p => `<tr><td class="mono">${p.symbol}</td><td>${p.qty}</td><td>${fmt(p.avg_cost)}</td><td>${fmt(p.market_price)}</td><td>${fmt(p.market_value)}</td><td class="${p.unrealized_pnl_pct>=0?'pos':'neg'}">${fmt(p.unrealized_pnl_pct)}%</td><td>${fmt(p.weight*100)}%</td></tr>`).join('');
}

function renderOrders(orders) {
  const ordBody = document.querySelector('#ordersTable tbody');
  ordBody.innerHTML = (orders||[]).slice().reverse().map(o => `<tr><td>${new Date(o.timestamp).toLocaleTimeString()}</td><td class="mono">${o.symbol}</td><td>${badge(o.side)}</td><td>${o.qty}</td><td>${fmt(o.avg_price)}</td><td>${fmt(o.commission)}</td><td>${o.algo}</td><td>${badge(o.status)}</td></tr>`).join('');
}

function renderRisk(risk) {
  if (!risk) return;
  document.getElementById('riskKpis').innerHTML = `
    ${kpiCard('Gross Exp', fmt(risk.gross_exposure))}
    ${kpiCard('Net Exp', fmt(risk.net_exposure))}
    ${kpiCard('Leverage', fmt(risk.leverage))}
    ${kpiCard('Var 95', fmt(risk.var_95))}
    ${kpiCard('Positions', risk.positions_count||0)}
  `;
}

function renderKPIs(summary) {
  if (!summary) return;
  document.getElementById('kpis').innerHTML = `
    ${kpiCard('Equity', fmt(summary.equity))}
    ${kpiCard('Cash', fmt(summary.cash))}
    ${kpiCard('Buying Power', fmt(summary.buying_power))}
    ${kpiCard('Unrealized PnL', fmt(summary.unrealized_pnl), summary.unrealized_pnl>=0?'pos':'neg')}
    ${kpiCard('Realized PnL', fmt(summary.realized_pnl), summary.realized_pnl>=0?'pos':'neg')}
  `;
}

async function refreshLive() {
  try {
    const [summary, positions, orders, risk, quotes] = await Promise.all([
      fetchJSON('/api/v1/portfolio/summary'),
      fetchJSON('/api/v1/portfolio/positions'),
      fetchJSON('/api/v1/orders'),
      fetchJSON('/api/v1/risk'),
      fetchJSON('/api/v1/market/quotes'),
    ]);
    renderKPIs(summary);
    renderPositions(positions);
    renderOrders(orders);
    renderRisk(risk);
    renderMarketWatch(quotes);
    renderAllocation(positions);
    renderEquity(summary.equity_curve||[], 'equityChart', 'Equity');
    const depthSym = document.getElementById('depthSymbol').innerText || 'SPY';
    const book = await fetchJSON('/api/v1/market/depth/'+depthSym);
    renderOrderBook(book);
  } catch(e) {}
}

async function placeOrder() {
  const payload = {
    symbol: document.getElementById('orderSymbol').value,
    side: document.getElementById('orderSide').value,
    qty: Number(document.getElementById('orderQty').value),
    order_type: document.getElementById('orderType').value,
    limit_price: document.getElementById('orderPrice').value ? Number(document.getElementById('orderPrice').value) : null,
    algo: document.getElementById('orderAlgo').value || 'manual',
  };
  await fetchJSON('/api/v1/orders', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)});
  showToast('Order placed');
  refreshLive();
}

async function loadLiveTradeJobs() {
  try {
    const jobs = await fetchJSON('/api/v1/live-trades');
    const tbody = document.querySelector('#liveTradeJobsTable tbody');
    tbody.innerHTML = (jobs||[]).map(j => `<tr>
      <td>${j.timestamp?new Date(j.timestamp).toLocaleTimeString():'-'}</td>
      <td class="mono">${j.job_id||'-'}</td>
      <td class="mono">${j.strategy_id||'-'}</td>
      <td>${j.signals_count||0}</td>
      <td>${(j.placed||[]).map(o => o.side+' '+o.qty+' '+o.symbol).join('<br>')||'-'}</td>
      <td class="muted">${(j.skipped||[]).join('; ')||'-'}</td>
    </tr>`).join('');
  } catch(e) {}
}

async function runLiveTradeFromPanel() {
  const sid = document.getElementById('liveStrategy').value;
  const symbols = document.getElementById('liveSymbols').value.split(',').map(s=>s.trim()).filter(Boolean);
  const qty = Number(document.getElementById('liveQty').value)||10;
  showToast('Running live trade for '+sid+'...');
  const res = await fetchJSON('/api/v1/live-trades/run', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({strategy_id:sid, symbols, qty})});
  showToast('Live trade job '+(res.job_id||'')+': '+((res.placed||[]).length)+' orders placed');
  loadLiveTradeJobs();
  refreshLive();
}

async function runStrategyBacktest(sid) {
  document.getElementById('btStrategy').value = sid;
  switchTab('backtest');
  await runBacktest();
}

function renderBacktestResult(res) {
  if (res.status === 'failed') {
    const logs = (res.logs||[]).join(' | ') || 'Backtest failed';
    showToast(logs);
    document.getElementById('btMetrics').innerHTML = kpiCard('Status', 'FAILED', 'neg');
    renderEquity([], 'btEquityChart', 'Backtest Equity', '#3b82f6');
    document.querySelector('#btTradesTable tbody').innerHTML = '';
    return;
  }
  const m = res.metrics || {};
  document.getElementById('btMetrics').innerHTML = `
    ${kpiCard('Total Return', pct(m.total_return))}
    ${kpiCard('CAGR', pct(m.cagr))}
    ${kpiCard('Sharpe', fmt(m.sharpe))}
    ${kpiCard('Sortino', fmt(m.sortino))}
    ${kpiCard('Max DD', fmt(m.max_drawdown)+'%', m.max_drawdown<0?'neg':'')}
  `;
  renderEquity(res.equity_curve||[], 'btEquityChart', 'Backtest Equity', '#3b82f6');
  const tbody = document.querySelector('#btTradesTable tbody');
  tbody.innerHTML = (res.trades||[]).map(t => {
    const side = (t.side||'').toUpperCase() || (t.signal>0?'BUY':t.signal<0?'SELL':'HOLD');
    const px = t.avg_price!=null ? t.avg_price : t.price;
    return `<tr><td>${t.timestamp?new Date(t.timestamp).toLocaleDateString():''}</td><td class="mono">${t.symbol||''}</td><td>${badge(side)}</td><td>${fmt(px)}</td><td>${t.qty||0}</td></tr>`;
  }).join('');
  showToast('Backtest complete: '+res.id);
}

async function runBacktest() {
  const payload = {
    strategy_id: document.getElementById('btStrategy').value,
    symbols: document.getElementById('btSymbols').value.split(',').map(s=>s.trim()).filter(Boolean),
    initial_cash: Number(document.getElementById('btCash').value),
    start: document.getElementById('btStart').value || undefined,
    end: document.getElementById('btEnd').value || undefined,
  };
  showToast('Running backtest...');
  const res = await fetchJSON('/api/v1/backtests/run', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)});
  renderBacktestResult(res);
}

async function runLabBacktest(expId) {
  showToast('Running backtest for '+expId+'...');
  const res = await fetchJSON('/api/v1/lab/'+expId+'/backtest', {method:'POST'});
  renderBacktestResult(res);
  switchTab('backtest');
}

async function loadBacktest(btId) {
  const res = await fetchJSON('/api/v1/backtests/'+btId);
  renderBacktestResult(res);
  switchTab('backtest');
}

async function loadStrategies(page=0) {
  strategyPage = page;
  const q = document.getElementById('strategySearch').value;
  const cat = document.getElementById('strategyCategory').value;
  const asset = document.getElementById('strategyAsset').value;
  const params = new URLSearchParams({limit: strategyPageSize, offset: page*strategyPageSize});
  if (q) params.set('q', q);
  if (cat) params.set('category', cat);
  if (asset) params.set('asset_class', asset);
  const res = await fetchJSON('/api/v1/strategies?'+params.toString());
  const tbody = document.querySelector('#strategiesTable tbody');
  tbody.innerHTML = (res.items||[]).map(s => `<tr>
    <td class="mono">${s.id}</td>
    <td>${s.name}</td>
    <td>${s.category}</td>
    <td>${s.asset_class}</td>
    <td>${s.family}</td>
    <td>${s.engine}</td>
    <td>${(s.tags||[]).slice(0,3).join(', ')}</td>
    <td><button class="btn small" onclick="runStrategyBacktest('${s.id}')">Backtest</button>
        <button class="btn secondary small" onclick="showCode('${s.id}')">Code</button></td>
  </tr>`).join('');
  const totalPages = Math.max(1, Math.ceil((res.total||0)/strategyPageSize));
  document.getElementById('strategiesPager').innerHTML = `
    <button class="btn secondary small" ${page<=0?'disabled':''} onclick="loadStrategies(${page-1})">Prev</button>
    <span class="muted">Page ${page+1} / ${totalPages} (${res.total||0} strategies)</span>
    <button class="btn secondary small" ${page+1>=totalPages?'disabled':''} onclick="loadStrategies(${page+1})">Next</button>`;
  // fill filters once
  const catSel = document.getElementById('strategyCategory');
  if (catSel.options.length<=1) {
    (res.categories||[]).forEach(c => { const o=document.createElement('option'); o.value=c; o.textContent=c; catSel.appendChild(o); });
  }
  const assetSel = document.getElementById('strategyAsset');
  if (assetSel.options.length<=1) {
    (res.asset_classes||[]).forEach(c => { const o=document.createElement('option'); o.value=c; o.textContent=c; assetSel.appendChild(o); });
  }
}

async function showCode(sid) {
  const res = await fetchJSON('/api/v1/strategies/'+sid+'/code');
  document.getElementById('codeBox').textContent = res.code || res.python || JSON.stringify(res,null,2);
  document.getElementById('codeModal').classList.add('open');
}
function closeCodeModal() { document.getElementById('codeModal').classList.remove('open'); }

async function generateExperiment() {
  const prompt = document.getElementById('labPrompt').value;
  const exp = await fetchJSON('/api/v1/lab/experiments', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({prompt})});
  showToast('Experiment '+exp.id+' generated ('+exp.strategy_family+')');
  loadLab();
}

async function loadLab() {
  const items = await fetchJSON('/api/v1/lab/experiments');
  const el = document.getElementById('labResults');
  el.innerHTML = (items||[]).map(e => `<div class="card">
    <h3>${e.title||e.id}</h3>
    <p class="muted">${e.hypothesis||e.prompt||''}</p>
    <div class="form-row">
      <button class="btn small" onclick="runLabBacktest('${e.id}')">Backtest</button>
      <button class="btn secondary small" onclick="showCode('${e.strategy_id||e.id}')">Code</button>
    </div>
  </div>`).join('') || '<div class="muted">No experiments yet</div>';
}

async function loadReporting() {
  try {
    const [pnl, costs, attr] = await Promise.all([
      fetchJSON('/api/v1/reporting/pnl'),
      fetchJSON('/api/v1/reporting/costs'),
      fetchJSON('/api/v1/reporting/attribution'),
    ]);
    const ctx = document.getElementById('pnlChart').getContext('2d');
    if (pnlChart) pnlChart.destroy();
    pnlChart = new Chart(ctx, {type:'bar', data:{labels:(pnl.dates||[]), datasets:[{label:'PnL', data:pnl.values||[], backgroundColor:'#00d4aa'}]}, options:{responsive:true,maintainAspectRatio:false}});
    document.getElementById('costReport').innerHTML = `<pre class="code">${JSON.stringify(costs,null,2)}</pre>`;
    document.querySelector('#attributionTable tbody').innerHTML = (attr.items||attr||[]).map(a => `<tr><td>${a.symbol}</td><td>${fmt(a.unrealized_pnl)}</td><td>${fmt(a.weight)}</td><td>${fmt(a.contribution)}</td></tr>`).join('');
  } catch(e) {}
}

async function cleanSymbol() {
  const symbol = document.getElementById('cleanSymbol').value;
  showToast('Cleaning '+symbol);
  const res = await fetchJSON('/api/v1/data/clean', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({symbol})});
  document.getElementById('cleanResult').textContent = JSON.stringify(res);
  loadDataHealth();
}

async function loadDataHealth() {
  const rows = await fetchJSON('/api/v1/data/health');
  document.querySelector('#dataHealthTable tbody').innerHTML = (rows||[]).map(r => `<tr><td>${r.source}</td><td>${badge(r.status)}</td><td>${r.last_update||'-'}</td><td>${r.latency_ms||'-'}</td><td class="muted">${r.error||''}</td></tr>`).join('');
}

async function loadJobs() {
  const jobs = await fetchJSON('/api/v1/ops/jobs');
  document.querySelector('#jobsTable tbody').innerHTML = (jobs||[]).map(j => `<tr><td class="mono">${j.id}</td><td>${j.name}</td><td>${j.schedule||'-'}</td><td>${badge(j.status)}</td><td>${j.started_at||'-'}</td><td>${j.finished_at||'-'}</td><td class="muted">${(j.log||'').slice(0,80)}</td></tr>`).join('');
}

async function loadSystem() {
  try {
    const [sys, health] = await Promise.all([
      fetchJSON('/api/v1/system'),
      fetchJSON('/health'),
    ]);
    document.getElementById('systemKpis').innerHTML = `
      ${kpiCard('CPU %', fmt(sys.cpu_percent))}
      ${kpiCard('Memory %', fmt((sys.memory||{}).percent))}
      ${kpiCard('Disk %', fmt((sys.disk||{}).percent))}
      ${kpiCard('Uptime s', fmtInt(sys.uptime_seconds))}
    `;
    document.getElementById('healthBox').textContent = JSON.stringify(health, null, 2);
  } catch(e) {}
}

function switchTab(tab) {
  document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
  document.querySelectorAll('.nav-links a').forEach(a => a.classList.remove('active'));
  const sec = document.getElementById(tab);
  if (sec) sec.classList.add('active');
  const link = document.querySelector(`.nav-links a[data-tab="${tab}"]`);
  if (link) link.classList.add('active');
  if (tab==='strategies') loadStrategies(0);
  if (tab==='lab') loadLab();
  if (tab==='reporting') loadReporting();
  if (tab==='data') loadDataHealth();
  if (tab==='operations') loadJobs();
  if (tab==='system') loadSystem();
  if (tab==='live') { refreshLive(); loadLiveTradeJobs(); }
}

document.getElementById('navLinks').addEventListener('click', e => {
  const a = e.target.closest('a[data-tab]');
  if (!a) return;
  e.preventDefault();
  switchTab(a.dataset.tab);
});

document.getElementById('orderType').addEventListener('change', e => {
  document.getElementById('orderPrice').disabled = e.target.value !== 'LIMIT';
});

async function loadSymbols() {
  try {
    const quotes = await fetchJSON('/api/v1/market/quotes');
    const sel = document.getElementById('orderSymbol');
    sel.innerHTML = (quotes||[]).map(q => `<option value="${q.symbol}">${q.symbol}</option>`).join('');
  } catch(e) {}
}

function connectSSE() {
  try {
    const es = new EventSource(API+'/api/v1/stream');
    es.onmessage = () => { document.getElementById('connStatus').style.background = '#00d4aa'; };
    es.onerror = () => { document.getElementById('connStatus').style.background = '#f43f5e'; };
  } catch(e) {}
}

loadSymbols();
refreshLive();
setInterval(() => {
  const active = document.querySelector('.section.active');
  if (active && active.id === 'live') refreshLive();
  if (active && active.id === 'system') loadSystem();
}, 5000);

switchTab('live');
connectSSE();
