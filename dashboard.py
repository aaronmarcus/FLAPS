"""Desktop dashboard — served at /desktop"""

DESKTOP_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Fibre Monitor</title>
<style>
:root {
  --bg:       #0e0e0e;
  --surface:  #161616;
  --border:   #282828;
  --text:     #e0e0e0;
  --dim:      #505050;
  --ok:       #22c55e;
  --ok-bg:    #052210;
  --ok-bd:    #0f3a1e;
  --warn:     #f97316;
  --warn-bg:  #1e0e00;
  --warn-bd:  #3a1d00;
  --err:      #ef4444;
  --err-bg:   #1e0505;
  --err-bd:   #5a0a0a;
  --unk:      #383838;
}

* { box-sizing: border-box; margin: 0; padding: 0; }

body {
  background: var(--bg);
  color: var(--text);
  font-family: system-ui, sans-serif;
  font-size: 14px;
  min-height: 100vh;
}

/* ── header ── */
header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 20px;
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  position: sticky; top: 0; z-index: 10;
}
header h1 { font-size: 15px; font-weight: 600; letter-spacing: 0.02em; }

.gw-status { display: flex; align-items: center; gap: 8px; font-size: 13px; color: var(--dim); }
.dot { width: 8px; height: 8px; border-radius: 50%; background: var(--unk); transition: background .3s; }
.dot.ok  { background: var(--ok); box-shadow: 0 0 5px var(--ok); }
.dot.err { background: var(--err); }

/* ── nav ── */
nav { display: flex; border-bottom: 1px solid var(--border); }
nav a {
  flex: 1; text-align: center; padding: 8px;
  font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: .1em;
  color: var(--dim); text-decoration: none; border-bottom: 2px solid transparent;
}
nav a.active { color: var(--ok); border-bottom-color: var(--ok); }

/* ── grid ── */
main {
  padding: 12px;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(210px, 1fr));
  gap: 10px;
}

/* ── camera card ── */
.cam {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  overflow: hidden;
  transition: border-color .3s;
}
.cam.ok       { border-color: var(--ok-bd); }
.cam.warn     { border-color: var(--warn-bd); }
.cam.error,
.cam.critical { border-color: var(--err-bd); }

/* ── card header ── */
.cam-head {
  display: flex; align-items: center; justify-content: space-between;
  padding: 8px 12px;
  border-bottom: 1px solid var(--border);
}
.cam-title { font-size: 16px; font-weight: 800; letter-spacing: -.02em; }
.cam-sub   { display: block; font-size: 10px; font-weight: 400; color: var(--dim); margin-top: 1px; letter-spacing: 0; }
.cam-sub   { display: block; font-size: 10px; font-weight: 400; color: var(--dim); margin-top: 1px; letter-spacing: 0; }

.badge {
  font-size: 9px; font-weight: 700; text-transform: uppercase; letter-spacing: .08em;
  padding: 2px 8px; border-radius: 3px;
}
.badge.ok       { background: #0d3320; color: var(--ok); }
.badge.warn     { background: #2e1800; color: var(--warn); }
.badge.error,
.badge.critical { background: #3a0808; color: var(--err); animation: blink 1s steps(1) infinite; }
.badge.unknown  { background: var(--unk); color: #888; }
@keyframes blink { 50% { opacity: .35; } }

/* ── SFP section ── */
.sfp-section { padding: 7px 12px 6px; }
.sfp-title {
  font-size: 9px; font-weight: 700; text-transform: uppercase; letter-spacing: .12em;
  color: var(--dim); margin-bottom: 4px;
}

/* ── signal row ── */
.sfp-row {
  display: flex; align-items: center; gap: 10px;
  padding: 2px 0;
}
.sfp-row + .sfp-row { margin-top: 3px; }

.row-lbl { font-size: 11px; color: var(--dim); width: 38px; flex-shrink: 0; }

.bar-track { flex: 1; height: 5px; background: #202020; border-radius: 3px; overflow: hidden; }
.bar-fill  { height: 100%; border-radius: 3px; transition: width .4s ease, background .3s; }
.bar-ok       { background: var(--ok); }
.bar-warn     { background: var(--warn); }
.bar-error,
.bar-critical { background: var(--err); }
.bar-unknown  { background: var(--unk); }

.row-val {
  font-size: 12px; font-variant-numeric: tabular-nums;
  width: 54px; text-align: right; flex-shrink: 0; transition: color .3s;
}
.row-val.ok       { color: var(--ok); }
.row-val.warn     { color: var(--warn); }
.row-val.error,
.row-val.critical { color: var(--err); }
.row-val.unknown  { color: var(--dim); }

.sfp-divider { height: 1px; background: var(--border); margin: 0 12px; }

/* ── empty state ── */
.empty {
  grid-column: 1 / -1; text-align: center;
  padding: 80px 0; color: var(--dim); font-size: 14px;
}
</style>
</head>
<body>

<header>
  <h1>Fibre Monitor</h1>
  <div class="gw-status">
    <div class="dot" id="dot"></div>
    <span id="gw-lbl">Connecting\u2026</span>
  </div>
</header>

<nav>
  <a href="/desktop" class="active">Desktop</a>
  <a href="/mobile">Mobile</a>
</nav>

<main id="grid">
  <div class="empty">Waiting for gateway\u2026</div>
</main>

<script>
// ── Colour helpers ────────────────────────────────────────────────
function cableCls(level, okLimit, errLimit) {
  if (level == null) return 'unknown';
  if (okLimit  != null && level >= okLimit)  return 'ok';
  if (errLimit != null && level <= errLimit) return 'error';
  if (okLimit  != null || errLimit != null)  return 'warn';
  return 'ok';
}
function signalCls(level, okLimit, errLimit) {
  if (level == null) return 'unknown';
  if (okLimit  != null && level <= okLimit)  return 'ok';
  if (errLimit != null && level >= errLimit) return 'error';
  if (okLimit  != null || errLimit != null)  return 'warn';
  return 'ok';
}
// Cable: fixed scale -2 to 8 dBm
function cablePct(level) {
  return level != null ? Math.min(100, Math.max(0, (level + 2) / 10 * 100)) : 0;
}
// Signal: fixed scale 0-100% (0 raw = 100%, errLimit raw = 0%)
function signalPct(level, errLimit) {
  if (level == null) return 0;
  const max = errLimit != null && errLimit > 0 ? errLimit : 7;
  return Math.min(100, Math.max(0, (1 - level / max) * 100));
}

// ── Row builders ──────────────────────────────────────────────────
function cableRow(chId, level, okLimit, errLimit) {
  const cls = cableCls(level, okLimit, errLimit);
  const w   = cablePct(level);
  const val = level != null ? level.toFixed(1) + '\u00a0dBm' : '\u2014';
  return `<div class="sfp-row" data-ch="${chId}">
    <span class="row-lbl">Cable</span>
    <div class="bar-track"><div class="bar-fill bar-${cls}" style="width:${w}%"></div></div>
    <span class="row-val ${cls}">${val}</span>
  </div>`;
}
function signalRow(chId, level, okLimit, errLimit) {
  const cls = signalCls(level, okLimit, errLimit);
  const w   = signalPct(level, errLimit);
  const val = level != null ? w.toFixed(1) + '\u00a0%' : '\u2014';
  return `<div class="sfp-row" data-ch="${chId}">
    <span class="row-lbl">Signal</span>
    <div class="bar-track"><div class="bar-fill bar-${cls}" style="width:${w}%"></div></div>
    <span class="row-val ${cls}">${val}</span>
  </div>`;
}
function sfpBlock(n, cam) {
  return `<div class="sfp-section">
    <div class="sfp-title">SFP ${n}</div>
    ${cableRow(`sfp${n}_cable`,  cam[`sfp${n}_cable_level`],  cam[`sfp${n}_cable_ok_limit`],  cam[`sfp${n}_cable_error_limit`])}
    ${signalRow(`sfp${n}_signal`, cam[`sfp${n}_signal_level`], cam[`sfp${n}_signal_ok_limit`], cam[`sfp${n}_signal_error_limit`])}
  </div>`;
}

// ── Card HTML ─────────────────────────────────────────────────────
function cardHTML(cam) {
  const overall = cam.overall_status || 'unknown';
  const badge   = overall === 'unknown' ? 'NO\u00a0DATA' : overall.toUpperCase();
  return `<div class="cam ${overall}" id="cam-${cam.cam}">
    <div class="cam-head">
      <span class="cam-title">${cam.label || 'CAM\u00a0' + cam.cam}<span class="cam-sub">${cam.deviceid || ''}</span></span>
      <span class="badge ${overall}">${badge}</span>
    </div>
    ${sfpBlock(1, cam)}
    <div class="sfp-divider"></div>
    ${sfpBlock(2, cam)}
  </div>`;
}

// ── In-place patch ────────────────────────────────────────────────
function patchRow(card, chId, cls, w, val, isVal) {
  const row = card.querySelector(`[data-ch="${chId}"]`);
  if (!row) return;
  const fill = row.querySelector('.bar-fill');
  if (fill) { fill.style.width = w + '%'; fill.className = `bar-fill bar-${cls}`; }
  const v = row.querySelector('.row-val');
  v.textContent = val;
  v.className   = `row-val ${cls}`;
}

function patchCard(cam) {
  const overall = cam.overall_status || 'unknown';
  let card = document.getElementById('cam-' + cam.cam);
  if (!card) {
    const grid  = document.getElementById('grid');
    const empty = grid.querySelector('.empty');
    if (empty) empty.remove();
    const tmp = document.createElement('div');
    tmp.innerHTML = cardHTML(cam);
    card = tmp.firstChild;
    const after = [...grid.querySelectorAll('.cam')]
      .find(el => (el.dataset.sortKey || el.id.replace('cam-','')) > String(cam.sort_key ?? cam.cam));
    after ? grid.insertBefore(card, after) : grid.appendChild(card);
    card.dataset.sortKey = cam.sort_key ?? cam.cam;
    return;
  }
  card.className = 'cam ' + overall;
  card.dataset.sortKey = cam.sort_key ?? cam.cam;
  const badge = card.querySelector('.badge');
  badge.className   = 'badge ' + overall;
  badge.textContent = overall === 'unknown' ? 'NO\u00a0DATA' : overall.toUpperCase();
  const title = card.querySelector('.cam-title');
  if (title && cam.label) {
    title.innerHTML = cam.label
      + (cam.deviceid ? `<span class="cam-sub">${cam.deviceid}</span>` : '');
  }

  for (const n of ['1','2']) {
    const cLvl = cam[`sfp${n}_cable_level`], cOk = cam[`sfp${n}_cable_ok_limit`], cErr = cam[`sfp${n}_cable_error_limit`];
    patchRow(card, `sfp${n}_cable`,  cableCls(cLvl, cOk, cErr),  cablePct(cLvl),
             cLvl != null ? cLvl.toFixed(1) + '\u00a0dBm' : '\u2014');
    const sLvl = cam[`sfp${n}_signal_level`], sOk = cam[`sfp${n}_signal_ok_limit`], sErr = cam[`sfp${n}_signal_error_limit`];
    const sW = signalPct(sLvl, sErr);
    patchRow(card, `sfp${n}_signal`, signalCls(sLvl, sOk, sErr), sW,
             sLvl != null ? sW.toFixed(1) + '\u00a0%' : '\u2014');
  }
}

// ── Status + render ───────────────────────────────────────────────
let gwConnected = false;

function setGwStatus(connected) {
  gwConnected = connected;
  document.getElementById('dot').className     = 'dot ' + (connected ? 'ok' : 'err');
  document.getElementById('gw-lbl').textContent = connected ? 'Connected' : 'Disconnected';
}

function renderAll(cameras) {
  const grid = document.getElementById('grid');
  if (!cameras.length) {
    grid.innerHTML = '<div class="empty">No cameras connected</div>';
    return;
  }
  const sorted = [...cameras].sort((a, b) => (a.sort_key ?? a.cam) - (b.sort_key ?? b.cam));
  grid.innerHTML = sorted.map(cardHTML).join('');
  sorted.forEach(c => {
    const card = document.getElementById('cam-' + c.cam);
    if (card) card.dataset.sortKey = c.sort_key ?? c.cam;
  });
}

// ── HTTP polling (every 30s, immediate on load) ───────────────────
async function poll() {
  try {
    const data = await fetch('/api/cameras').then(r => r.json());
    setGwStatus(data.connected);
    renderAll(data.cameras || []);
  } catch { setGwStatus(false); }
}

// ── Auto-reload when disconnected ─────────────────────────────────
setInterval(() => {
  if (!gwConnected) {
    window.location.reload();
  }
}, 30000);

// ── Periodic refresh every 30s regardless ─────────────────────────
setInterval(poll, 30000);

// ── SSE for instant live updates ─────────────────────────────────
function connect() {
  const es = new EventSource('/stream');

  es.addEventListener('snapshot', e => {
    const data = JSON.parse(e.data);
    setGwStatus(data.connected);
    if (!document.querySelector('.cam')) renderAll(data.cameras || []);
  });

  es.addEventListener('camera', e => patchCard(JSON.parse(e.data)));

  es.addEventListener('remove', e => {
    const card = document.getElementById('cam-' + JSON.parse(e.data).cam);
    if (!card) return;
    card.style.transition = 'opacity .4s, transform .4s';
    card.style.opacity    = '0';
    card.style.transform  = 'scale(.95)';
    setTimeout(() => {
      card.remove();
      if (!document.querySelector('.cam'))
        document.getElementById('grid').innerHTML = '<div class="empty">No cameras connected</div>';
    }, 400);
  });

  es.onerror = () => {
    setGwStatus(false);
    es.close();
    setTimeout(connect, 3000);
  };
}

poll();
connect();
</script>
</body>
</html>
"""