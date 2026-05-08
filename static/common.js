// Shared helpers for both the home dashboard and the device detail page.

// ----- theme toggle -----
function applyThemeUI(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  const icon = document.getElementById('theme-icon');
  const label = document.getElementById('theme-label');
  if (icon) icon.textContent = theme === 'light' ? '☀' : '🌙';
  if (label) label.textContent = theme;
}
window.addEventListener('DOMContentLoaded', () => {
  applyThemeUI(document.documentElement.getAttribute('data-theme') || 'dark');
  const btn = document.getElementById('theme-toggle');
  if (btn) {
    btn.addEventListener('click', () => {
      const cur = document.documentElement.getAttribute('data-theme') || 'dark';
      const next = cur === 'dark' ? 'light' : 'dark';
      try { localStorage.setItem('theme', next); } catch (e) {}
      applyThemeUI(next);
    });
  }
});

// ----- toast notifications -----
function toast(msg, type = 'info', timeout = 4000) {
  const host = document.getElementById('toasts');
  if (!host) return;
  const t = document.createElement('div');
  t.className = `toast ${type}`;
  t.textContent = msg;
  host.appendChild(t);
  setTimeout(() => {
    t.style.transition = 'opacity 0.3s';
    t.style.opacity = '0';
    setTimeout(() => t.remove(), 300);
  }, timeout);
}

// ----- API helper -----
async function api(path, method = 'GET', body = null) {
  const opts = { method, headers: { 'Content-Type': 'application/json' } };
  if (body) opts.body = JSON.stringify(body);
  const res = await fetch(path, opts);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `${res.status} ${res.statusText}`);
  return data;
}

// ----- formatters -----
function fmtUptime(secs) {
  const d = Math.floor(secs / 86400);
  const h = Math.floor((secs % 86400) / 3600);
  const m = Math.floor((secs % 3600) / 60);
  if (d > 0) return `${d}d ${h}h ${m}m`;
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
}
function fmtTime(ts) { return new Date(ts * 1000).toLocaleTimeString(); }

function escapeHtml(s) {
  return String(s ?? '').replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[c]);
}

// Bitaxe firmware returns difficulties either as raw numbers (4096, 9271000302)
// or pre-formatted strings. Normalize numeric values to K/M/G/T/P.
function formatDiff(v) {
  if (v == null || v === '') return '—';
  if (typeof v === 'string' && /[a-zA-Z]/.test(v)) return v;
  const n = Number(v);
  if (!isFinite(n) || n === 0) return '0';
  const units = ['', 'K', 'M', 'G', 'T', 'P'];
  let i = 0, x = n;
  while (Math.abs(x) >= 1000 && i < units.length - 1) { x /= 1000; i++; }
  return (i === 0 ? x.toString() : x.toFixed(x >= 100 ? 0 : x >= 10 ? 1 : 2)) + units[i];
}

function formatNum(n) {
  if (n == null) return '0';
  return Number(n).toLocaleString();
}

function tempClass(t, asic = true) {
  if (asic) {
    if (t < 60) return 'good';
    if (t < 65) return 'warn';
    return 'crit';
  } else {
    if (t < 55) return 'good';
    if (t < 65) return 'warn';
    return 'crit';
  }
}
function effClass(j) {
  if (j < 16) return 'good';
  if (j < 19) return '';
  if (j < 22) return 'warn';
  return 'crit';
}
function hwErrClass(p) {
  if (p < 0.1) return 'ok';
  if (p < 0.5) return 'warn';
  return 'bad';
}

// ----- chart drawing -----
function drawChart(canvas, history, key, color) {
  if (!history || history.length < 2) return;
  const ctx = canvas.getContext('2d');
  const dpr = window.devicePixelRatio || 1;
  const w = canvas.clientWidth, h = canvas.clientHeight;
  canvas.width = w * dpr; canvas.height = h * dpr; ctx.scale(dpr, dpr);
  ctx.clearRect(0, 0, w, h);

  ctx.strokeStyle = 'rgba(120,140,135,0.18)';
  for (let i = 1; i < 4; i++) {
    const y = (h / 4) * i;
    ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke();
  }

  const vals = history.map(p => p[key]);
  const lo = Math.min(...vals) * 0.95;
  const hi = Math.max(...vals) * 1.05;
  const range = hi - lo || 1;

  ctx.strokeStyle = color;
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  history.forEach((p, i) => {
    const x = (i / (history.length - 1)) * w;
    const y = h - ((p[key] - lo) / range) * h;
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.stroke();

  ctx.lineTo(w, h); ctx.lineTo(0, h); ctx.closePath();
  const grad = ctx.createLinearGradient(0, 0, 0, h);
  grad.addColorStop(0, color + '33');
  grad.addColorStop(1, color + '00');
  ctx.fillStyle = grad;
  ctx.fill();
}

// ----- tooltip primitive -----
// Use [data-tip="text"] on any element. Optional [data-tip-pos="top|bottom|left|right"]
// (defaults to top). Works on dynamically rendered nodes too — handlers use event delegation.
(function setupTooltips() {
  let tooltipEl = null;
  let activeTrigger = null;
  let showTimer = null;

  function ensureEl() {
    if (tooltipEl) return tooltipEl;
    tooltipEl = document.createElement('div');
    tooltipEl.className = 'app-tooltip';
    tooltipEl.setAttribute('role', 'tooltip');
    document.body.appendChild(tooltipEl);
    return tooltipEl;
  }

  function position(trigger, el) {
    const rect = trigger.getBoundingClientRect();
    const pos = trigger.getAttribute('data-tip-pos') || 'top';
    el.style.left = '0px';
    el.style.top = '0px';
    const elRect = el.getBoundingClientRect();
    const margin = 8;
    let x, y;
    if (pos === 'bottom')      { x = rect.left + rect.width / 2 - elRect.width / 2; y = rect.bottom + margin; }
    else if (pos === 'left')   { x = rect.left - elRect.width - margin; y = rect.top + rect.height / 2 - elRect.height / 2; }
    else if (pos === 'right')  { x = rect.right + margin; y = rect.top + rect.height / 2 - elRect.height / 2; }
    else                       { x = rect.left + rect.width / 2 - elRect.width / 2; y = rect.top - elRect.height - margin; }
    x = Math.max(8, Math.min(window.innerWidth - elRect.width - 8, x));
    y = Math.max(8, Math.min(window.innerHeight - elRect.height - 8, y));
    el.style.left = x + 'px';
    el.style.top = y + 'px';
  }

  function show(trigger) {
    const text = trigger.getAttribute('data-tip');
    if (!text) return;
    const el = ensureEl();
    el.textContent = text;
    activeTrigger = trigger;
    requestAnimationFrame(() => {
      position(trigger, el);
      el.classList.add('visible');
    });
  }

  function hide() {
    clearTimeout(showTimer);
    activeTrigger = null;
    if (tooltipEl) tooltipEl.classList.remove('visible');
  }

  document.addEventListener('mouseover', e => {
    const trigger = e.target && e.target.closest && e.target.closest('[data-tip]');
    if (!trigger || trigger === activeTrigger) return;
    clearTimeout(showTimer);
    showTimer = setTimeout(() => show(trigger), 220);
  });
  document.addEventListener('mouseout', e => {
    const trigger = e.target && e.target.closest && e.target.closest('[data-tip]');
    if (!trigger) return;
    hide();
  });
  document.addEventListener('focusin', e => {
    const trigger = e.target && e.target.closest && e.target.closest('[data-tip]');
    if (trigger) show(trigger);
  });
  document.addEventListener('focusout', e => {
    const trigger = e.target && e.target.closest && e.target.closest('[data-tip]');
    if (trigger) hide();
  });
  // ESC dismisses.
  document.addEventListener('keydown', e => { if (e.key === 'Escape') hide(); });
  // Hide while scrolling so position doesn't get stale.
  window.addEventListener('scroll', hide, true);
})();


function drawTempChart(canvas, history) {
  const ctx = canvas.getContext('2d');
  const dpr = window.devicePixelRatio || 1;
  const w = canvas.clientWidth, h = canvas.clientHeight;
  canvas.width = w * dpr; canvas.height = h * dpr; ctx.scale(dpr, dpr);
  ctx.clearRect(0, 0, w, h);

  ctx.strokeStyle = 'rgba(120,140,135,0.18)';
  for (let i = 1; i < 4; i++) {
    const y = (h / 4) * i;
    ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke();
  }

  const allTemps = [...history.map(p => p.asic), ...history.map(p => p.vr)];
  const lo = Math.min(...allTemps) * 0.95;
  const hi = Math.max(...allTemps) * 1.05;
  const range = hi - lo || 1;

  ['asic', 'vr'].forEach((key, idx) => {
    const color = idx === 0 ? '#4cc9f0' : '#ffb000';
    ctx.strokeStyle = color;
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    history.forEach((p, i) => {
      const x = (i / (history.length - 1)) * w;
      const y = h - ((p[key] - lo) / range) * h;
      if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    });
    ctx.stroke();
  });
}
