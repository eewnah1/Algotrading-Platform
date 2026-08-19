const API = window.location.origin;
const toast = document.getElementById('toast');
const sections = ['live','backtest','strategies','lab','reporting','data','operations','system'];
let equityChart, allocChart, btEquityChart, pnlChart;
let strategyOffset = 0;
let strategyLimit = 25;
let sseConnection = null;
let currentDepthSymbol = 'SPY';

function showToast(msg) { toast.innerText = msg; toast.style.display = 'block'; setTimeout(()=>toast.style.display='none',4000); }

function switchTab(tab) {
  document.querySelectorAll('.nav-links a').forEach(a => a.classList.toggle('active', a.dataset.tab===tab));
  document.querySelectorAll('.section').forEach(s => s.classList.toggle('active', s.id===tab));
  if (tab==='live') loadLive();
  if (tab==='backtest') ;
  if (tab==='strategies') loadStrategiesMeta();
  if (tab==='lab') loadExperiments();
  if (tab==='reporting') loadReporting();
  if (tab==='data') loadDataHealth();
  if (tab==='operations') loadJobs();
  if (tab==='system') loadSystem();
}

document.querySelectorAll('.nav-links a').forEach(a => a.addEventListener('click', e => { e.preventDefault(); switchTab(a.dataset.tab); }));

function fmt(n) { return (n===undefined || n===null || isNaN(n)) ? '-' : Number(n).toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2}); }
function fmtInt(n) { return (n===undefined || n===null || isNaN(n)) ? '-' : Number(n).toLocaleString(undefined,{maximumFractionDigits:0}); }
function pct(n) { return (n===undefined || n===null || isNaN(n)) ? '-' : Number(n).toFixed(2)+'%'; }
function badge(status) {
  const s = (status||'').toLowerCase();
  const cls = s==='ok'||s==='completed'||s==='filled' ? 'ok' : s==='running'||s==='pending' ? 'warn' : 'fail';
  return `<span class="badge ${cls}">${status}</span>`;
}

async function fetchJSON(path, opts) {
  try {
    const r = await fetch(API+path, opts);
    if (!r.ok) throw new Error(await r.text());
    return await r.json();
  } catch(e) { showToast('API error: '+e.message); throw e; }
}

function kpiCard(title, value, cls='') { return `<div class="card"><h3>${title}</h3><div class="value ${cls}">${value}</div></div>`; }

function renderEquity(data, canvasId, label, color='#00d4aa') {
  const labels = data.map(d => d.timestamp ? new Date(d.timestamp).toLocaleString() : '');
  const vals = data.map(d => d.equity || 0);
  const ctx = document.getElementById(canvasId).getContext('2d');
  if (equityChart && canvasId==='equityChart') { equityChart.destroy(); }
  if (btEquityChart && canvasId==='btEquityChart') { btEquityChart.destroy(); }
  const cfg = {
    type:'line',
    data:{labels, datasets:[{label, data:vals, borderColor:color, backgroundColor:color.replace(')',',0.1)').replace('rgb','rgba').replace('#','') || 'rgba(0,212,170,0.1)', fill:true, tension:0.3, pointRadius:0}]},
    options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{x:{ticks:{maxTicksLimit:6,color:'#94a3b8'},grid:{color:'rgba(148,163,184,0.05)'}},y:{ticks:{color:'#94a3b8'},grid:{color:'rgba(148,163,184,0.05)'}}}}
  };
  if (canvasId==='equityChart') equityChart = new Chart(ctx,cfg);
  else if (canvasId==='btEquityChart') btEquityChart = new Chart(ctx,cfg);
}

function renderAllocation(positions) {
  const ctx = document.getElementById('allocChart').getContext('2d');
  if (allocChart) allocChart.destroy();
  const filtered = positions.filter(p => p.weight>0);
  const data = filtered.map(p => p.weight);
  const labels = filtered.map(p => p.symbol);
  const colors = ['#00d4aa','#3b82f6','#f59e0b','#ec4899','#8b5cf6','#10b981','#6366f1','#f43f5e','#06b6d4','#a855f7'];
  allocChart = new Chart(ctx, { type:'doughnut', data:{labels, datasets:[{data, backgroundColor:colors}]}, options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{labels:{color:'#e5e7eb'}}}}});
}

function renderMarketWatch(quotes) {
  const tbody = document.querySelector('#marketTable tbody');
  const prev = {};
  if (tbody.dataset.last) try { prev = JSON.parse(tbody.dataset.last); } catch(e){}
  tbody.innerHTML = (quotes||[]).map(q => {
    const last = q.last || 0, prevLast = prev[q.symbol] || last;
    const chg = prevLast ? (last-prevLast)/prevLast*100 : 0;
    const cls = chg>0 ? 'pos' : chg<0 ? 'neg' : '';
    return `<tr><td class="mono">${q.symbol}</td><td class="mono">${fmt(last)}</td><td class="mono">${fmt(q.bid)}</td><td class="mono">${fmt(q.ask)}</td><td class="mono ${cls}">${chg.toFixed(2)}%</td><td class="mono">${fmtInt(q.volume)}</td></tr>`;
  }).join('');
  tbody.dataset.last = JSON.stringify(Object.fromEntries((quotes||[]).map(q=>[q.symbol,q.last])));
}

function renderOrderBook(depth) {
  const bids = (depth.bids||[]).map(b => `<div class="lob-row bid"><span>${fmt(b.price)}</span><span class="mono">${fmtInt(b.size)}</span></div>`).join('');
  const asks = (depth.asks||[]).map(a => `<div class="lob-row ask"><span>${fmt(a.price)}</span><span class="mono">${fmtInt(a.size)}</span></div>`).join('');
  document.getElementById('orderBook').innerHTML = `<div class="lob-header"><span class="muted">Price</span><span class="muted">Size</span></div>${asks}<div class="lob-mid">MID ${fmt(depth.mid)}</div>${bids}`;
  document.getElementById('depthSymbol').innerText = depth.symbol;
}

async function loadDepth(symbol) {
  currentDepthSymbol = symbol;
  const depth = await fetchJSON('/api/v1/market/depth?symbol='+symbol+'&levels=10');
  renderOrderBook(depth);
}

async function loadLive() {
  const [pf, perf, quotes] = await Promise.all([
    fetchJSON('/api/v1/portfolio'),
    fetchJSON('/api/v1/performance'),
    fetchJSON('/api/v1/market/snapshot')
  ]);
  const m = perf.metrics || {};
  const kpi = document.getElementById('kpis');
  kpi.innerHTML = `
    ${kpiCard('Total Equity', '$'+fmt(pf.equity))}
    ${kpiCard('Cash', '$'+fmt(pf.cash))}
    ${kpiCard('Total PnL', pct(pf.total_pnl_pct), pf.total_pnl_pct>=0?'pos':'neg')}
    ${kpiCard('Sharpe', fmt(m.sharpe))}
    ${kpiCard('Max Drawdown', fmt(m.max_drawdown)+'%', m.max_drawdown<0?'neg':'')}
  `;
  const posBody = document.querySelector('#positionsTable tbody');
  posBody.innerHTML = (pf.positions||[]).map(p => `<tr><td class="mono">${p.symbol}</td><td>${p.qty}</td><td>${fmt(p.avg_cost)}</td><td>${fmt(p.market_price)}</td><td>$${fmt(p.market_value)}</td><td class="${p.unrealized_pnl_pct>=0?'pos':'neg'}">${pct(p.unrealized_pnl_pct)}</td><td>${pct(p.weight)}</td></tr>`).join('');
  const ordBody = document.querySelector('#ordersTable tbody');
  const orders = await fetchJSON('/api/v1/orders?limit=20');
  ordBody.innerHTML = (orders||[]).slice().reverse().map(o => `<tr><td>${new Date(o.timestamp).toLocaleTimeString()}</td><td class="mono">${o.symbol}</td><td>${badge(o.side)}</td><td>${o.qty}</td><td>${fmt(o.avg_price)}</td><td>${fmt(o.commission)}</td><td>${o.algo}</td><td>${badge(o.status)}</td></tr>`).join('');
  renderMarketWatch(quotes);
  loadDepth(currentDepthSymbol);
  renderEquity(perf.equity||[], 'equityChart', 'Equity');
  renderAllocation(pf.positions||[]);
  const risk = await fetchJSON('/api/v1/risk');
  document.getElementById('riskKpis').innerHTML = `
    ${kpiCard('Gross Exposure', pct(risk.gross_exposure_pct))}
    ${kpiCard('Net Exposure', pct(risk.net_exposure_pct))}
    ${kpiCard('Long %', pct(risk.long_pct))}
    ${kpiCard('Cash %', pct(risk.cash_pct))}
    ${kpiCard('Top 1 Conc.', pct(risk.concentration_top1_pct))}
  `;
  populateOrderSymbols(quotes);
}

function populateOrderSymbols(quotes) {
  const sel = document.getElementById('orderSymbol');
  if (sel.options.length && sel.dataset.loaded) return;
  sel.innerHTML = (quotes||[]).map(q => `<option value="${q.symbol}">${q.symbol}</option>`).join('');
  sel.value = currentDepthSymbol;
  sel.dataset.loaded = 'true';
  sel.onchange = () => loadDepth(sel.value);
}

document.getElementById('orderType').addEventListener('change', e => {
  document.getElementById('orderPrice').disabled = e.target.value !== 'LIMIT';
});

async function placeOrder() {
  const payload = {
    symbol: document.getElementById('orderSymbol').value,
    side: document.getElementById('orderSide').value,
    qty: parseInt(document.getElementById('orderQty').value),
    order_type: document.getElementById('orderType').value,
    price: document.getElementById('orderPrice').value,
    algo: document.getElementById('orderAlgo').value,
  };
  await fetchJSON('/api/v1/orders', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)});
  showToast('Order placed');
  loadLive();
}

async function loadStrategiesMeta() {
  const meta = await fetchJSON('/api/v1/strategies/categories');
  const cat = document.getElementById('strategyCategory');
  const ast = document.getElementById('strategyAsset');
  if (!cat.dataset.loaded) {
    cat.innerHTML = '<option value="">All Categories</option>' + (meta.categories||[]).map(c => `<option value="${c}">${c}</option>`).join('');
    ast.innerHTML = '<option value="">All Asset Classes</option>' + (meta.asset_classes||[]).map(a => `<option value="${a}">${a}</option>`).join('');
    cat.dataset.loaded = 'true';
  }
  loadStrategies();
}

async function loadStrategies() {
  const q = document.getElementById('strategySearch').value;
  const category = document.getElementById('strategyCategory').value;
  const asset = document.getElementById('strategyAsset').value;
  const params = new URLSearchParams({limit: strategyLimit, offset: strategyOffset});
  if (q) params.set('q', q);
  if (category) params.set('category', category);
  if (asset) params.set('asset_class', asset);
  const res = await fetchJSON('/api/v1/strategies?'+params.toString());
  const tbody = document.querySelector('#strategiesTable tbody');
  tbody.innerHTML = (res.items||[]).map(s => `<tr>
    <td class="mono small">${s.id}</td>
    <td>${s.name}</td>
    <td><span class="badge">${s.category}</span></td>
    <td>${s.asset_class}</td>
    <td>${s.family}</td>
    <td>${s.engine}</td>
    <td>${(s.tags||[]).slice(0,3).map(t=>`<span class="tag">${t}</span>`).join(' ')}</td>
    <td><button class="btn small" onclick="runStrategyBacktest('${s.id}')">Run</button></td>
  </tr>`).join('');
  const pages = Math.ceil((res.total||0)/strategyLimit);
  const current = Math.floor(strategyOffset/strategyLimit)+1;
  document.getElementById('strategiesPager').innerHTML = `
    <button class="btn secondary" ${strategyOffset<=0?'disabled':''} onclick="changePage(-1)">Prev</button>
    <span>Page ${current} / ${pages||1} (${res.total||0} strategies)</span>
    <button class="btn secondary" ${strategyOffset+strategyLimit>=(res.total||0)?'disabled':''} onclick="changePage(1)">Next</button>
  `;
}

function changePage(dir) { strategyOffset = Math.max(0, strategyOffset + dir*strategyLimit); loadStrategies(); }

async function runStrategyBacktest(sid) {
  document.getElementById('btStrategy').value = sid;
  switchTab('backtest');
  await runBacktest();
}

function renderBacktestResult(res) {
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
  tbody.innerHTML = (res.trades||[]).map(t => `<tr><td>${new Date(t.timestamp).toLocaleDateString()}</td><td class="mono">${t.symbol}</td><td>${badge(t.signal>0?'BUY':t.signal<0?'SELL':'HOLD')}</td><td>${fmt(t.price)}</td><td>${t.qty}</td></tr>`).join('');
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

async function generateExperiment() {
  const prompt = document.getElementById('labPrompt').value;
  const exp = await fetchJSON('/api/v1/lab/generate', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({prompt})});
  showToast('Experiment '+exp.id+' generated ('+exp.strategy_family+')');
  await loadExperiments();
  await runLabBacktest(exp.id);
}

async function loadExperiments() {
  const exps = await fetchJSON('/api/v1/lab/experiments');
  const div = document.getElementById('labResults');
  div.innerHTML = (exps.slice(0,8)||[]).map(e => {
    const params = e.strategy_params ? JSON.stringify(e.strategy_params) : '{}';
    const btLink = e.backtest_id ? `<a href="#" onclick="loadBacktest('${e.backtest_id}');return false;">Backtest: ${e.backtest_id}</a>` : '';
    return `<div class="card">
      <h3>${e.id} <span class="badge">${e.strategy_family||'ai-lab'}</span></h3>
      <p>${e.hypothesis}</p>
      <pre class="code">${params}</pre>
      <div class="form-row" style="margin-top:10px">
        <button class="btn small" onclick="runLabBacktest('${e.id}')">Run Backtest</button>
        <span class="muted">${btLink}</span>
        <span class="badge ${e.status==='passed'?'ok':e.status==='failed'?'fail':'warn'}">${e.status}</span>
      </div>
    </div>`;
  }).join('');
}

async function loadReporting() {
  const rep = await fetchJSON('/api/v1/reporting/pnl');
  const daily = rep.daily || [];
  const labels = daily.map(d => d.date);
  const pnl = daily.map(d => d.daily_pnl);
  const ctx = document.getElementById('pnlChart').getContext('2d');
  if (pnlChart) pnlChart.destroy();
  pnlChart = new Chart(ctx, { type:'bar', data:{labels, datasets:[{label:'Daily PnL', data:pnl, backgroundColor: pnl.map(v => v>=0 ? '#34d399' : '#f87171')}]}, options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{x:{ticks:{maxTicksLimit:8,color:'#94a3b8'},grid:{color:'rgba(148,163,184,0.05)'}},y:{ticks:{color:'#94a3b8'},grid:{color:'rgba(148,163,184,0.05)'}}}}});
  const c = rep.costs || {};
  document.getElementById('costReport').innerHTML = `<p>Total commission: $${fmt(c.total_commission)}</p><p>Total slippage: $${fmt(c.total_slippage)}</p><p>Total cost: $${fmt(c.total_cost)}</p><p>Cost bps: ${fmt(c.cost_bps)}</p>`;
  const att = await fetchJSON('/api/v1/reporting/attribution');
  document.querySelector('#attributionTable tbody').innerHTML = (att.attribution||[]).map(a => `<tr><td class="mono">${a.symbol}</td><td class="${a.unrealized_pnl>=0?'pos':'neg'}">${fmt(a.unrealized_pnl)}</td><td>${pct(a.weight_pct)}</td><td>${pct(a.contribution_pct)}</td></tr>`).join('');
}

async function cleanSymbol() {
  const symbol = document.getElementById('cleanSymbol').value;
  showToast('Cleaning '+symbol);
  const res = await fetchJSON('/api/v1/data/clean?symbol='+symbol, {method:'POST'});
  document.getElementById('cleanResult').innerText = `${res.symbol}: ${res.rows} rows, ${res.anomalies||0} anomalies repaired`;
  loadDataHealth();
}

async function loadDataHealth() {
  const data = await fetchJSON('/api/v1/data/status');
  const tbody = document.querySelector('#dataHealthTable tbody');
  tbody.innerHTML = (data||[]).map(d => `<tr><td>${d.source}</td><td>${badge(d.status)}</td><td>${d.last_update ? new Date(d.last_update).toLocaleString() : '-'}</td><td>${fmt(d.latency_ms)} ms</td><td>${d.error||'-'}</td></tr>`).join('');
}

async function loadJobs() {
  const jobs = await fetchJSON('/api/v1/operations/jobs');
  const tbody = document.querySelector('#jobsTable tbody');
  tbody.innerHTML = (jobs||[]).map(j => `<tr><td class="mono small">${j.id}</td><td>${j.name}</td><td>${j.schedule}</td><td>${badge(j.status)}</td><td>${j.started?new Date(j.started).toLocaleTimeString():'-'}</td><td>${j.finished?new Date(j.finished).toLocaleTimeString():'-'}</td><td>${(j.log_tail||[]).slice(-1)[0]||'-'}</td></tr>`).join('');
}

async function loadSystem() {
  const [sys, health] = await Promise.all([fetchJSON('/api/v1/system'), fetchJSON('/health')]);
  document.getElementById('systemKpis').innerHTML = `
    ${kpiCard('CPU', fmt(sys.cpu_percent)+'%')}
    ${kpiCard('Memory', fmt(sys.memory.percent)+'%')}
    ${kpiCard('Disk', fmt(sys.disk.percent)+'%')}
    ${kpiCard('Uptime', (sys.uptime_seconds/3600).toFixed(1)+' h')}
  `;
  document.getElementById('healthBox').innerText = JSON.stringify(health, null, 2);
}

function connectSSE() {
  try {
    const es = new EventSource(API + '/api/v1/live/feed');
    es.onmessage = (ev) => {
      const msg = JSON.parse(ev.data);
      document.getElementById('connStatus').className = 'status-dot ok';
      if (msg.portfolio) updateLiveKpis(msg.portfolio);
      if (msg.quotes) renderMarketWatch(msg.quotes);
    };
    es.onerror = () => { document.getElementById('connStatus').className = 'status-dot warn'; };
    sseConnection = es;
  } catch(e) { document.getElementById('connStatus').className = 'status-dot fail'; }
}

function updateLiveKpis(pf) {
  const m = pf.metrics || {};
  const kpi = document.getElementById('kpis');
  if (!kpi) return;
  kpi.innerHTML = `
    ${kpiCard('Total Equity', '$'+fmt(pf.equity))}
    ${kpiCard('Cash', '$'+fmt(pf.cash))}
    ${kpiCard('Total PnL', pct(pf.total_pnl_pct), pf.total_pnl_pct>=0?'pos':'neg')}
    ${kpiCard('Sharpe', fmt(m.sharpe))}
    ${kpiCard('Max Drawdown', fmt(m.max_drawdown)+'%', m.max_drawdown<0?'neg':'')}
  `;
}

setInterval(() => {
  const active = document.querySelector('.section.active');
  if (!active) return;
  if (active.id === 'live') loadLive();
  if (active.id === 'reporting') loadReporting();
  if (active.id === 'data') loadDataHealth();
  if (active.id === 'operations') loadJobs();
  if (active.id === 'system') loadSystem();
}, 5000);

switchTab('live');
connectSSE();
