'use strict';

const state = { dashboard: null, accounts: [], allAccounts: [], activePage: 'overview', alertItems: [], transactionItems: [], reportData: null };
const $ = (id) => document.getElementById(id);
const INR = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 });
const INR2 = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 2 });
const NUMBER = new Intl.NumberFormat('en-IN');

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
}
function formatMoney(value, decimals = false) { return (decimals ? INR2 : INR).format(Number(value || 0)); }
function formatNumber(value) { return NUMBER.format(Number(value || 0)); }
function shortDate(value) {
  if (!value) return '—';
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return String(value).replace('T',' ').replace('Z','');
  return d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: '2-digit' });
}
function shortTime(value) {
  if (!value) return '';
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? '' : d.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: false });
}
function timeAgo(value) {
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return 'timestamp unavailable';
  const secs = Math.max(0, Math.floor((Date.now() - d.getTime()) / 1000));
  if (secs < 60) return `${secs}s ago`;
  if (secs < 3600) return `${Math.floor(secs / 60)}m ago`;
  if (secs < 86400) return `${Math.floor(secs / 3600)}h ago`;
  if (secs < 604800) return `${Math.floor(secs / 86400)}d ago`;
  return shortDate(value);
}
function statusClass(status) { return 'status-' + String(status || '').toLowerCase(); }
function severityClass(severity) { return 'sev-' + String(severity || 'low').toLowerCase(); }
function riskClass(score) { return Number(score) >= 70 ? 'risk-high' : Number(score) >= 40 ? 'risk-medium' : 'risk-low'; }
function initials(name) { return String(name || 'NA').split(/\s+/).slice(0, 2).map(p => p[0] || '').join('').toUpperCase(); }
function merchantClass(severity) { return severity === 'CRITICAL' || severity === 'HIGH' ? 'red' : severity === 'MEDIUM' ? 'amber' : 'green'; }

async function api(url, options = {}) {
  const res = await fetch(url, { headers: { 'Content-Type': 'application/json', ...(options.headers || {}) }, ...options });
  const contentType = res.headers.get('content-type') || '';
  const payload = contentType.includes('application/json') ? await res.json() : await res.text();
  if (!res.ok) throw new Error(payload && payload.error ? payload.error : `Request failed (${res.status})`);
  return payload;
}
function toast(title, message, kind = 'success') {
  const node = document.createElement('div');
  node.className = `toast ${kind}`;
  node.innerHTML = `<span class="toast-icon">${kind === 'error' ? '!' : '✓'}</span><div><strong>${escapeHtml(title)}</strong><p>${escapeHtml(message)}</p></div>`;
  $('toastRegion').appendChild(node);
  setTimeout(() => { node.style.opacity = '0'; node.style.transform = 'translateY(6px)'; setTimeout(() => node.remove(), 220); }, 4300);
}
function loadingRows(span, message = 'Loading records…') { return `<tr><td colspan="${span}" class="loading-cell">${escapeHtml(message)}</td></tr>`; }
function setBusy(button, busy, busyLabel = 'Working…') {
  if (!button) return;
  if (busy) { button.dataset.oldLabel = button.innerHTML; button.innerHTML = `<span class="btn-symbol">↻</span> ${busyLabel}`; button.disabled = true; }
  else { button.innerHTML = button.dataset.oldLabel || button.innerHTML; button.disabled = false; delete button.dataset.oldLabel; }
}

function activatePage(page) {
  if (!document.getElementById(`page-${page}`)) return;
  state.activePage = page;
  document.querySelectorAll('.page-section').forEach(el => el.classList.toggle('active', el.id === `page-${page}`));
  document.querySelectorAll('.nav-item').forEach(el => el.classList.toggle('active', el.dataset.page === page));
  const label = ({overview:'Overview',transactions:'Transactions',alerts:'Fraud alerts',accounts:'Accounts',reports:'SQL insights',audit:'Audit trail'})[page] || 'Overview';
  $('breadcrumbPage').textContent = label;
  if (page === 'transactions') loadTransactions();
  if (page === 'alerts') loadAlerts();
  if (page === 'accounts') loadAccounts();
  if (page === 'reports') loadReports();
  if (page === 'audit') loadAudit();
  if (page === 'overview') loadDashboard();
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

async function loadDashboard() {
  try {
    const data = await api('/api/dashboard'); state.dashboard = data;
    const m = data.metrics;
    $('metricVolume').textContent = formatMoney(m.total_volume);
    $('metricExposure').textContent = formatMoney(m.flagged_exposure);
    $('metricAlerts').textContent = formatNumber(m.active_alerts);
    $('metricHighAlerts').textContent = `${formatNumber(m.high_alerts)} high severity`;
    $('metricAccounts').textContent = formatNumber(m.monitored_accounts);
    $('chartVolume').textContent = formatMoney(m.total_volume);
    $('chartCount').textContent = `${formatNumber(m.total_transactions)} transactions`;
    $('navTxCount').textContent = formatNumber(m.total_transactions);
    $('navAlertCount').textContent = formatNumber(m.active_alerts);
    $('lastUpdated').textContent = `UPDATED ${new Date().toLocaleTimeString('en-IN',{hour:'2-digit',minute:'2-digit',hour12:false})}`;
    renderActivityChart(data.trend || []);
    renderRiskDistribution(data.risk_distribution || []);
    renderOverviewAlerts(data.latest_alerts || []);
    renderActivity(data.activity || []);
    $('alertFooterCount').textContent = `${formatNumber(m.active_alerts)} active alerts in queue`;
  } catch (e) { toast('Dashboard unavailable', e.message, 'error'); }
}

function renderActivityChart(items) {
  const svg = $('activityChart'); const width = 760, height = 230, left = 38, right = 16, top = 18, bottom = 19;
  const usableW = width - left - right, usableH = height - top - bottom;
  const values = items.map(x => Number(x.volume || 0));
  const max = Math.max(1, ...values) * 1.12;
  const points = values.map((v, i) => ({x: left + (items.length < 2 ? usableW/2 : i * usableW/(items.length-1)), y: top + usableH - (v/max)*usableH, v}));
  const grid = [0, .25, .5, .75, 1].map(f => {
    const y = top + usableH - f*usableH;
    const label = formatMoney(max*f).replace('₹','₹');
    return `<line x1="${left}" y1="${y}" x2="${width-right}" y2="${y}" stroke="#242d3c" stroke-width="1" stroke-dasharray="3 5"/><text x="0" y="${y+3}" fill="#68758b" font-size="10">${escapeHtml(compactMoney(max*f))}</text>`;
  }).join('');
  const line = points.map((p,i)=>`${i===0?'M':'L'} ${p.x} ${p.y}`).join(' ');
  const area = `${line} L ${points[points.length-1]?.x || left} ${top+usableH} L ${points[0]?.x || left} ${top+usableH} Z`;
  const markers = points.map((p,i)=>`<circle cx="${p.x}" cy="${p.y}" r="3.5" fill="#101722" stroke="#7897ff" stroke-width="2"><title>${escapeHtml(items[i]?.month || '')}: ${escapeHtml(formatMoney(p.v))}</title></circle>`).join('');
  svg.innerHTML = `<defs><linearGradient id="chartFill" x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stop-color="#688aff" stop-opacity=".29"/><stop offset="100%" stop-color="#688aff" stop-opacity="0"/></linearGradient><linearGradient id="chartLine" x1="0" x2="1"><stop offset="0%" stop-color="#6e8cff"/><stop offset="100%" stop-color="#55dfc0"/></linearGradient></defs>${grid}<path d="${area}" fill="url(#chartFill)"/><path d="${line}" fill="none" stroke="url(#chartLine)" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>${markers}`;
  $('chartLabels').innerHTML = items.map(x=>`<span>${escapeHtml(x.month)}</span>`).join('');
}
function compactMoney(value) {
  const n = Number(value || 0);
  if (n >= 10000000) return `₹${(n/10000000).toFixed(1)}Cr`;
  if (n >= 100000) return `₹${(n/100000).toFixed(1)}L`;
  if (n >= 1000) return `₹${(n/1000).toFixed(0)}k`;
  return `₹${Math.round(n)}`;
}
function renderRiskDistribution(items) {
  const colorMap = {'High risk':'#ff687e','Medium risk':'#f2b96a','Low risk':'#688aff'};
  const order = ['Low risk','Medium risk','High risk'];
  const map = Object.fromEntries(items.map(x=>[x.label, Number(x.count)]));
  const total = order.reduce((sum,k)=>sum+(map[k]||0),0);
  $('riskTotal').textContent = formatNumber(total);
  let acc = 0;
  const segments = order.map(k=>{const count=map[k]||0;const start=total?acc/total*100:0;acc+=count;const end=total?acc/total*100:0;return `${colorMap[k]} ${start}% ${end}%`;});
  $('riskDonut').style.background = total ? `conic-gradient(${segments.join(',')})` : '#273143';
  $('riskLegend').innerHTML = order.map(k=>`<div class="risk-legend-row"><i style="background:${colorMap[k]}"></i><span>${k}</span><b>${formatNumber(map[k]||0)}</b></div>`).join('');
}
function renderOverviewAlerts(items) {
  const body = $('overviewAlerts');
  if (!items.length) { body.innerHTML = `<tr><td colspan="5" class="empty-state">No active alerts. Run a threat scan to evaluate transactions.</td></tr>`; return; }
  body.innerHTML = items.slice(0,6).map(a=>`<tr><td><div class="alert-merchant"><div class="merchant-mark ${merchantClass(a.severity)}">${escapeHtml((a.merchant||'?').slice(0,1).toUpperCase())}</div><div class="merchant-meta"><strong>${escapeHtml(a.merchant)}</strong><span>${escapeHtml(a.external_ref)} · ${escapeHtml(a.account_id)}</span></div></div></td><td><span class="severity-badge ${severityClass(a.severity)}">${escapeHtml(a.severity)}</span></td><td class="amount-cell">${formatMoney(a.amount)}</td><td><span class="status-badge ${statusClass(a.status)}">${escapeHtml(a.status.replace('_',' '))}</span></td><td><button class="table-action" data-page="alerts">Review</button></td></tr>`).join('');
}
function renderActivity(items) {
  const body = $('activityList');
  if (!items.length) { body.innerHTML = '<div class="loading-cell">No activity recorded yet.</div>'; return; }
  body.innerHTML = items.map(a=>{
    const action=String(a.action||'EVENT'); const type=action.includes('ALERT')?'alert':action.includes('TRANSFER')||action.includes('RESOLVED')?'success':'';
    const symbol=action.includes('ALERT')?'!':action.includes('TRANSFER')?'↗':action.includes('SCAN')?'⌁':action.includes('TRANSACTION')?'↔':'◇';
    return `<div class="activity-item"><div class="activity-icon ${type}">${symbol}</div><div class="activity-content"><strong>${escapeHtml(action.replaceAll('_',' ').toLowerCase().replace(/\b\w/g,c=>c.toUpperCase()))}</strong><p>${escapeHtml(a.details || `${a.entity_type} ${a.entity_id}`)}</p></div><span class="activity-time">${escapeHtml(timeAgo(a.created_at))}</span></div>`;
  }).join('');
}

async function loadTransactions() {
  $('transactionsTable').innerHTML = loadingRows(7);
  try {
    const params = new URLSearchParams();
    const q = $('transactionSearch').value.trim(); const risk = $('riskFilter').value; const status = $('txStatusFilter').value;
    if(q) params.set('q',q); if(risk) params.set('risk',risk); if(status) params.set('status',status);
    const data = await api(`/api/transactions?${params}`); state.transactionItems = data.items || [];
    $('transactionResults').textContent = `${formatNumber(state.transactionItems.length)} records`;
    $('transactionsTable').innerHTML = state.transactionItems.length ? state.transactionItems.map(t=>`<tr><td><div class="ref-cell"><strong>${escapeHtml(t.external_ref)}</strong><span>#TX-${String(t.id).padStart(5,'0')}</span></div></td><td><div class="customer-cell"><strong>${escapeHtml(t.merchant)}</strong><span>${escapeHtml(t.customer_name)} · ${escapeHtml(t.account_id)}</span></div></td><td><div class="date-cell">${escapeHtml(shortDate(t.created_at))}<span>${escapeHtml(shortTime(t.created_at))} · ${escapeHtml(t.location)}</span></div></td><td class="amount-cell">${formatMoney(t.amount, true)}</td><td>${escapeHtml(t.channel)}</td><td><div class="score-cell"><span class="risk-badge ${riskClass(t.risk_score)}">${Number(t.risk_score)}/100</span><span class="score-track"><i class="${riskClass(t.risk_score).replace('risk-','')}" style="width:${Number(t.risk_score)}%"></i></span></div></td><td><span class="status-badge ${statusClass(t.status)}">${escapeHtml(t.status)}</span></td></tr>`).join('') : `<tr><td colspan="7" class="empty-state">No transactions match these filters.</td></tr>`;
    const all = await api('/api/transactions'); const items = all.items || [];
    $('txTotalSmall').textContent = formatNumber(items.length);
    $('txHighSmall').textContent = formatNumber(items.filter(t=>Number(t.risk_score)>=70).length);
    $('txReviewSmall').textContent = formatNumber(items.filter(t=>t.status==='REVIEW'||Number(t.risk_score)>=70).length);
    $('txAverageSmall').textContent = formatMoney(items.length ? items.reduce((s,t)=>s+Number(t.amount),0)/items.length : 0);
  } catch(e) { $('transactionsTable').innerHTML=loadingRows(7,'Could not load transactions.');toast('Transactions unavailable',e.message,'error'); }
}

async function loadAlerts() {
  $('alertsTable').innerHTML = loadingRows(7);
  try {
    const params = new URLSearchParams();
    const status=$('alertStatusFilter').value;const severity=$('severityFilter').value;const q=$('alertSearch').value.trim();
    if(status)params.set('status',status);if(severity)params.set('severity',severity);if(q)params.set('q',q);
    const data=await api(`/api/alerts?${params}`);state.alertItems=data.items||[];
    $('alertResults').textContent=`${formatNumber(state.alertItems.length)} alerts`;
    $('alertsTable').innerHTML=state.alertItems.length?state.alertItems.map(a=>{
      const actions = a.status==='OPEN' ? `<button class="table-action" data-alert-action="INVESTIGATING" data-alert-id="${a.id}">Investigate</button> <button class="table-action" data-alert-action="RESOLVED" data-alert-id="${a.id}">Resolve</button>` : a.status==='INVESTIGATING' ? `<button class="table-action" data-alert-action="RESOLVED" data-alert-id="${a.id}">Resolve</button>` : `<button class="table-action" data-alert-action="OPEN" data-alert-id="${a.id}">Reopen</button>`;
      const fp = ['OPEN','INVESTIGATING'].includes(a.status) ? ` <button class="table-action" data-alert-action="FALSE_POSITIVE" data-alert-id="${a.id}">False positive</button>` : '';
      return `<tr><td><div class="ref-cell"><strong>ALT-${String(a.id).padStart(5,'0')}</strong><span>${escapeHtml(a.external_ref)}</span></div></td><td><div class="customer-cell"><strong>${escapeHtml(a.customer_name)}</strong><span>${escapeHtml(a.account_id)} · ${escapeHtml(a.customer_email)}</span></div></td><td><div class="customer-cell"><strong>${escapeHtml(a.rule_name)}</strong><span title="${escapeHtml(a.reason)}">${escapeHtml(a.reason)}</span></div></td><td class="amount-cell">${formatMoney(a.amount)}</td><td><span class="severity-badge ${severityClass(a.severity)}">${escapeHtml(a.severity)} · ${a.score}</span></td><td><span class="status-badge ${statusClass(a.status)}">${escapeHtml(a.status.replace('_',' '))}</span></td><td><div class="action-stack">${actions}${fp}</div></td></tr>`;
    }).join('') : `<tr><td colspan="7" class="empty-state">No alerts match this filter.</td></tr>`;
    const all = await api('/api/alerts?status=all'); const counts={OPEN:0,INVESTIGATING:0,RESOLVED:0,FALSE_POSITIVE:0};
    (all.items||[]).forEach(a=>counts[a.status]=(counts[a.status]||0)+1);
    $('openAlertsCount').textContent=formatNumber(counts.OPEN||0);$('investigatingCount').textContent=formatNumber(counts.INVESTIGATING||0);$('resolvedCount').textContent=formatNumber(counts.RESOLVED||0);$('falsePositiveCount').textContent=formatNumber(counts.FALSE_POSITIVE||0);
  } catch(e) { $('alertsTable').innerHTML=loadingRows(7,'Could not load alerts.');toast('Alert queue unavailable',e.message,'error'); }
}

async function loadAccounts() {
  $('accountsGrid').innerHTML='<div class="panel loading-cell">Loading accounts…</div>';
  try {
    const q=$('accountSearch').value.trim(); const data=await api(`/api/accounts?q=${encodeURIComponent(q)}`);state.accounts=data.items||[]; if(!state.allAccounts.length){const all=await api('/api/accounts');state.allAccounts=all.items||[];}
    const flagged=state.accounts.filter(a=>Number(a.active_alert_count)>0).length;
    $('accountTotal').textContent=formatNumber(state.accounts.length);$('accountFlagged').textContent=formatNumber(flagged);
    $('accountsGrid').innerHTML=state.accounts.length?state.accounts.map(a=>`<article class="account-card"><div class="account-card-top"><div class="account-card-avatar">${escapeHtml(initials(a.customer_name))}</div><div class="account-card-name"><strong>${escapeHtml(a.customer_name)}</strong><span>${escapeHtml(a.account_id)} · ${escapeHtml(a.customer_email)}</span></div><span class="account-type">${escapeHtml(a.account_type)}</span></div><span class="account-balance-label">AVAILABLE BALANCE</span><div class="account-balance">${formatMoney(a.balance)}</div><div class="account-info-row"><span>Transactions</span><b>${formatNumber(a.transaction_count)}</b></div><div class="account-info-row"><span>Active alerts</span><b class="${Number(a.active_alert_count)>0?'attention':''}">${formatNumber(a.active_alert_count)}</b></div><div class="account-card-bottom"><span class="risk-tier ${String(a.risk_tier).toLowerCase()}">${escapeHtml(a.risk_tier)} RISK TIER</span><span class="account-status ${a.account_status==='ACTIVE'?'':'frozen'}">${escapeHtml(a.account_status)}</span></div></article>`).join(''):`<div class="panel empty-state">No accounts match this search.</div>`;
    populateTransferAccounts();
  } catch(e) { $('accountsGrid').innerHTML='<div class="panel empty-state">Could not load accounts.</div>';toast('Accounts unavailable',e.message,'error'); }
}

async function loadReports() {
  try {
    const [d,r]=await Promise.all([api('/api/dashboard'),api('/api/reports')]);state.reportData=r;
    const m=d.metrics;
    $('reportKpis').innerHTML=`<article class="report-kpi"><span>TRANSACTION VOLUME</span><strong>${formatMoney(m.total_volume)}</strong><small>${formatNumber(m.total_transactions)} total records</small></article><article class="report-kpi"><span>FLAGGED EXPOSURE</span><strong>${formatMoney(m.flagged_exposure)}</strong><small>Open or investigating alerts</small></article><article class="report-kpi"><span>ACTIVE ALERTS</span><strong>${formatNumber(m.active_alerts)}</strong><small>${formatNumber(m.high_alerts)} high / critical</small></article><article class="report-kpi"><span>RESOLVED ALERTS</span><strong>${formatNumber(m.resolved_alerts)}</strong><small>${formatNumber(m.false_positives)} marked false positive</small></article>`;
    const max=Math.max(1,...r.category_spend.map(x=>Number(x.volume)));
    $('categoryReport').innerHTML=r.category_spend.length?r.category_spend.map(x=>`<div class="report-row"><span class="report-row-label">${escapeHtml(x.category)}</span><div class="report-bar-wrap"><div class="report-bar" style="width:${Number(x.volume)/max*100}%"></div></div><span class="report-row-value">${escapeHtml(compactMoney(x.volume))}</span></div>`).join(''):'<div class="empty-state">No category data available.</div>';
    const colors={OPEN:'#ff687e',INVESTIGATING:'#f2b96a',RESOLVED:'#55dfc0',FALSE_POSITIVE:'#a78bfa'};
    $('dispositionReport').innerHTML=r.alert_disposition.length?r.alert_disposition.map(x=>`<div class="report-disposition"><span class="report-disposition-left"><i style="background:${colors[x.status]||'#8b94a6'}"></i>${escapeHtml(x.status.replace('_',' '))}</span><b>${formatNumber(x.count)}</b></div>`).join(''):'<div class="empty-state">No alerts recorded.</div>';
    $('queryBook').innerHTML=r.query_examples.map((q,i)=>`<div class="query-item"><div class="query-item-head"><div><strong>${escapeHtml(q.title)}</strong><span style="display:block;margin-top:4px">${escapeHtml(q.description)}</span></div><button class="copy-query" data-copy-query="${i}">Copy SQL</button></div><pre><code>${escapeHtml(q.sql)}</code></pre></div>`).join('');
  } catch(e) { toast('SQL insights unavailable',e.message,'error'); }
}

async function loadAudit() {
  $('auditTable').innerHTML=loadingRows(5);
  try {
    const data=await api('/api/audit?limit=150');const items=data.items||[];
    $('auditTable').innerHTML=items.length?items.map(a=>`<tr><td><div class="ref-cell"><strong>${escapeHtml(a.action.replaceAll('_',' '))}</strong><span>EVT-${String(a.id).padStart(6,'0')}</span></div></td><td>${escapeHtml(a.actor)}</td><td>${escapeHtml(a.entity_type)} · ${escapeHtml(a.entity_id)}</td><td style="white-space:normal;min-width:250px;max-width:470px;color:#8794a8">${escapeHtml(a.details)}</td><td><div class="date-cell">${escapeHtml(shortDate(a.created_at))}<span>${escapeHtml(shortTime(a.created_at))} UTC</span></div></td></tr>`).join(''):`<tr><td colspan="5" class="empty-state">No audit events recorded.</td></tr>`;
  } catch(e) { $('auditTable').innerHTML=loadingRows(5,'Could not load audit trail.');toast('Audit trail unavailable',e.message,'error'); }
}

async function runScan(button) {
  setBusy(button,true,'Scanning…');
  try {
    const result=await api('/api/scan',{method:'POST',body:JSON.stringify({})});
    toast('Threat scan complete',`${formatNumber(result.scanned)} transactions scanned · ${formatNumber(result.created_alerts)} new alerts · ${formatNumber(result.updated_scores)} risk scores updated.`);
    await loadDashboard();
    if(state.activePage==='alerts') await loadAlerts();
    if(state.activePage==='transactions') await loadTransactions();
  } catch(e) { toast('Threat scan failed',e.message,'error'); }
  finally { setBusy(button,false); }
}
async function decideAlert(id,status,button) {
  if(!confirm(`${status==='RESOLVED'?'Resolve':status==='FALSE_POSITIVE'?'Mark as false positive':status==='INVESTIGATING'?'Move to investigating':'Reopen'} alert ALT-${String(id).padStart(5,'0')}? An audit event will be created.`)) return;
  if(button){button.disabled=true;button.textContent='Saving…';}
  try { await api(`/api/alerts/${id}/decision`,{method:'POST',body:JSON.stringify({status,actor:'Fraud Operations',note:'Updated through PHANTOM dashboard'})});toast('Alert updated',`Alert ALT-${String(id).padStart(5,'0')} moved to ${status.replace('_',' ')}.`);await Promise.all([loadAlerts(),loadDashboard()]); }
  catch(e){toast('Could not update alert',e.message,'error');if(button){button.disabled=false;button.textContent='Retry';}}
}

function openTransferModal() {
  populateTransferAccounts();$('transferModal').classList.add('open');$('transferModal').setAttribute('aria-hidden','false');document.body.style.overflow='hidden';setTimeout(()=>$('fromAccount').focus(),80);
}
function closeTransferModal() {$('transferModal').classList.remove('open');$('transferModal').setAttribute('aria-hidden','true');document.body.style.overflow='';}
function populateTransferAccounts() {
  const sourceList=state.allAccounts.length?state.allAccounts:state.accounts; if(!sourceList.length)return;
  const options=sourceList.filter(a=>a.account_status==='ACTIVE').map(a=>`<option value="${escapeHtml(a.account_id)}">${escapeHtml(a.account_id)} · ${escapeHtml(a.customer_name)} · ${escapeHtml(formatMoney(a.balance))}</option>`).join('');
  if($('fromAccount').options.length!==sourceList.filter(a=>a.account_status==='ACTIVE').length){$('fromAccount').innerHTML=options;$('toAccount').innerHTML=options;}
  if($('toAccount').options.length>1 && $('toAccount').value===$('fromAccount').value){$('toAccount').selectedIndex=1;}
}
function openModal(id) {
  const modal = $(id);
  modal.classList.add('open'); modal.setAttribute('aria-hidden', 'false');
  document.body.style.overflow = 'hidden';
}
function closeModal(id) {
  const modal = $(id);
  modal.classList.remove('open'); modal.setAttribute('aria-hidden', 'true');
  if (!document.querySelector('.modal-backdrop.open')) document.body.style.overflow = '';
}
async function openTransactionModal() {
  try {
    if (!state.allAccounts.length) {
      const all = await api('/api/accounts'); state.allAccounts = all.items || [];
    }
    const selectable = state.allAccounts.filter(a => a.account_status !== 'CLOSED');
    if (!selectable.length) { toast('No accounts available', 'Create a customer and account before adding a transaction.', 'error'); return; }
    $('newTxAccount').innerHTML = selectable.map(a => `<option value="${escapeHtml(a.account_id)}">${escapeHtml(a.account_id)} · ${escapeHtml(a.customer_name)} · ${escapeHtml(formatMoney(a.balance))}</option>`).join('');
    openModal('transactionModal'); setTimeout(() => $('newTxMerchant').focus(), 80);
  } catch (e) { toast('Could not load accounts', e.message, 'error'); }
}
function openCustomerModal() { openModal('customerModal'); setTimeout(() => $('newCustomerName').focus(), 80); }

async function refreshAfterDataChange({accountsChanged = false, transactionChanged = false} = {}) {
  if (accountsChanged) { state.allAccounts = []; $('accountSearch').value = ''; }
  if (transactionChanged) { $('transactionSearch').value = ''; $('riskFilter').value = ''; $('txStatusFilter').value = ''; }
  const jobs = [loadDashboard()];
  if (state.activePage === 'transactions' || transactionChanged) jobs.push(loadTransactions());
  if (state.activePage === 'accounts' || accountsChanged) jobs.push(loadAccounts());
  if (state.activePage === 'alerts') jobs.push(loadAlerts());
  if (state.activePage === 'reports') jobs.push(loadReports());
  if (state.activePage === 'audit') jobs.push(loadAudit());
  await Promise.all(jobs);
  // Always reload the full account cache so both creation forms and transfer lists stay current.
  if (accountsChanged || transactionChanged) {
    const all = await api('/api/accounts'); state.allAccounts = all.items || [];
    populateTransferAccounts();
  }
}

async function submitNewCustomer(event) {
  event.preventDefault(); const btn = $('submitCustomer'); setBusy(btn, true, 'Creating…');
  const payload = {
    full_name: $('newCustomerName').value.trim(), email: $('newCustomerEmail').value.trim(),
    phone: $('newCustomerPhone').value.trim(), risk_tier: $('newCustomerRisk').value,
    account_type: $('newAccountType').value, opening_balance: Number($('newOpeningBalance').value),
    country: $('newCustomerCountry').value.trim().toUpperCase()
  };
  try {
    const result = await api('/api/customers', {method: 'POST', body: JSON.stringify(payload)});
    closeModal('customerModal'); $('customerForm').reset(); $('newOpeningBalance').value = '25000'; $('newCustomerCountry').value = 'IN';
    toast('Customer & account created', `${result.full_name} · ${result.account_id} · ${formatMoney(result.opening_balance)} opening balance`);
    await refreshAfterDataChange({accountsChanged: true});
  } catch (e) { toast('Could not create customer', e.message, 'error'); }
  finally { setBusy(btn, false); }
}

async function submitNewTransaction(event) {
  event.preventDefault(); const btn = $('submitTransaction'); setBusy(btn, true, 'Saving…');
  const payload = {
    account_id: $('newTxAccount').value, merchant: $('newTxMerchant').value.trim(),
    category: $('newTxCategory').value, amount: Number($('newTxAmount').value),
    transaction_type: $('newTxType').value, status: $('newTxStatus').value,
    channel: $('newTxChannel').value, location: $('newTxLocation').value.trim(),
    ip_address: $('newTxIP').value.trim(), device_id: $('newTxDevice').value.trim(),
    is_international: $('newTxInternational').checked
  };
  try {
    const result = await api('/api/transactions', {method: 'POST', body: JSON.stringify(payload)});
    closeModal('transactionModal'); $('transactionForm').reset(); $('newTxLocation').value = 'Coimbatore, IN'; $('newTxIP').value = '192.0.2.10'; $('newTxDevice').value = 'PHANTOM-MANUAL';
    toast('Transaction saved to SQLite', `${result.reference} · ${formatMoney(result.amount)}. Run the threat scan to evaluate its risk.`);
    await refreshAfterDataChange({transactionChanged: true});
  } catch (e) { toast('Could not save transaction', e.message, 'error'); }
  finally { setBusy(btn, false); }
}

async function submitTransfer(event) {
  event.preventDefault();const btn=$('submitTransfer');setBusy(btn,true,'Executing…');
  const payload={from_account:$('fromAccount').value,to_account:$('toAccount').value,amount:Number($('transferAmount').value),note:$('transferNote').value};
  try {const result=await api('/api/transfer',{method:'POST',body:JSON.stringify(payload)});closeTransferModal();$('transferForm').reset();toast('Transfer committed',`${result.reference} · ${formatMoney(result.amount)} moved atomically from ${result.from_account} to ${result.to_account}.`);state.allAccounts=[];await Promise.all([loadDashboard(),loadTransactions(),loadAccounts()]);}
  catch(e){toast('Transfer rejected',e.message,'error');}
  finally{setBusy(btn,false);}
}

function debounce(fn, wait=240){let t;return (...args)=>{clearTimeout(t);t=setTimeout(()=>fn(...args),wait);};}

document.addEventListener('click', event => {
  const nav=event.target.closest('[data-page]'); if(nav){activatePage(nav.dataset.page);return;}
  const alertAction=event.target.closest('[data-alert-action]');if(alertAction){decideAlert(Number(alertAction.dataset.alertId),alertAction.dataset.alertAction,alertAction);return;}
  const copy=event.target.closest('[data-copy-query]');if(copy){const q=state.reportData?.query_examples?.[Number(copy.dataset.copyQuery)]?.sql;if(q){navigator.clipboard?.writeText(q).then(()=>toast('SQL copied','Paste the query into a SQLite client.')).catch(()=>toast('Copy unavailable','Select the query text manually.','error'));}return;}
});
$('refreshBtn').addEventListener('click',()=>loadDashboard());
$('runScanBtn').addEventListener('click',e=>runScan(e.currentTarget));
$('alertsScanBtn').addEventListener('click',e=>runScan(e.currentTarget));
$('alertsRefreshBtn').addEventListener('click',()=>loadAlerts());
$('reportsRefreshBtn').addEventListener('click',()=>loadReports());
$('auditRefreshBtn').addEventListener('click',()=>loadAudit());
$('exportBtn').addEventListener('click',()=>{const p=new URLSearchParams();if($('transactionSearch').value.trim())p.set('q',$('transactionSearch').value.trim());if($('riskFilter').value)p.set('risk',$('riskFilter').value);if($('txStatusFilter').value)p.set('status',$('txStatusFilter').value);window.location.href='/api/export/transactions?'+p.toString();toast('Export started','A CSV file is being generated from the database.');});
$('newTransferBtn').addEventListener('click',async()=>{if(!state.accounts.length)await loadAccounts();openTransferModal();});
$('closeTransferModal').addEventListener('click',closeTransferModal);$('cancelTransfer').addEventListener('click',closeTransferModal);
$('transferModal').addEventListener('click',e=>{if(e.target===$('transferModal'))closeTransferModal();});
$('transferForm').addEventListener('submit',submitTransfer);
$('newTransactionBtn').addEventListener('click', openTransactionModal);
$('newCustomerBtn').addEventListener('click', openCustomerModal);
$('closeTransactionModal').addEventListener('click',()=>closeModal('transactionModal'));
$('cancelTransaction').addEventListener('click',()=>closeModal('transactionModal'));
$('transactionModal').addEventListener('click',e=>{if(e.target===$('transactionModal'))closeModal('transactionModal');});
$('transactionForm').addEventListener('submit',submitNewTransaction);
$('closeCustomerModal').addEventListener('click',()=>closeModal('customerModal'));
$('cancelCustomer').addEventListener('click',()=>closeModal('customerModal'));
$('customerModal').addEventListener('click',e=>{if(e.target===$('customerModal'))closeModal('customerModal');});
$('customerForm').addEventListener('submit',submitNewCustomer);
$('topSearchBtn').addEventListener('click',()=>{activatePage('transactions');setTimeout(()=>$('transactionSearch').focus(),50);});
$('transactionSearch').addEventListener('input',debounce(loadTransactions));$('riskFilter').addEventListener('change',loadTransactions);$('txStatusFilter').addEventListener('change',loadTransactions);
$('alertSearch').addEventListener('input',debounce(loadAlerts));$('alertStatusFilter').addEventListener('change',loadAlerts);$('severityFilter').addEventListener('change',loadAlerts);
$('accountSearch').addEventListener('input',debounce(loadAccounts));
document.addEventListener('keydown',e=>{if(e.key==='Escape'){if($('transferModal').classList.contains('open'))closeTransferModal();if($('transactionModal').classList.contains('open'))closeModal('transactionModal');if($('customerModal').classList.contains('open'))closeModal('customerModal');}});

async function boot() {
  try {const health=await api('/api/health'); if(health.ok){await loadDashboard();} } catch(e){toast('Unable to connect to local server','Start PHANTOM using run_phantom.bat, then refresh this page.','error');}
}
boot();