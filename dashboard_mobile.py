"""Mobile dashboard — served at /mobile. Single column, at-a-glance."""

MOBILE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>F.L.A.P.S.</title>
<style>
:root {
  --bg:       #0e0e0e;
  --surface:  #161616;
  --border:   #282828;
  --text:     #e0e0e0;
  --dim:      #505050;
  --ok:       #22c55e;
  --ok-bd:    #0f3a1e;
  --warn:     #f97316;
  --warn-bd:  #3a1d00;
  --err:      #ef4444;
  --err-bd:   #5a0a0a;
  --unk:      #383838;
}

* { box-sizing: border-box; margin: 0; padding: 0; }

body {
  background: var(--bg);
  color: var(--text);
  font-family: system-ui, sans-serif;
  font-size: 14px;
}

/* ── header ── */
header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 10px 14px;
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  position: sticky; top: 0; z-index: 10;
}
header h1 { font-size: 14px; font-weight: 600; }

.gw-status { display: flex; align-items: center; gap: 7px; font-size: 12px; color: var(--dim); }
.dot { width: 7px; height: 7px; border-radius: 50%; background: var(--unk); transition: background .3s; }
.dot.ok  { background: var(--ok); box-shadow: 0 0 4px var(--ok); }
.dot.err { background: var(--err); }

/* ── nav ── */
nav { display: flex; border-bottom: 1px solid var(--border); }
nav a {
  flex: 1; text-align: center; padding: 7px;
  font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: .1em;
  color: var(--dim); text-decoration: none; border-bottom: 2px solid transparent;
}
nav a.active { color: var(--ok); border-bottom-color: var(--ok); }

/* ── list ── */
main { padding: 8px; display: flex; flex-direction: column; gap: 8px; }

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
  padding: 9px 12px;
  border-bottom: 1px solid var(--border);
}
.cam-title { font-size: 19px; font-weight: 800; letter-spacing: -.03em; }

.badge {
  font-size: 8px; font-weight: 700; text-transform: uppercase; letter-spacing: .08em;
  padding: 2px 7px; border-radius: 3px;
}
.badge.ok       { background: #0d3320; color: var(--ok); }
.badge.warn     { background: #2e1800; color: var(--warn); }
.badge.error,
.badge.critical { background: #3a0808; color: var(--err); animation: blink 1s steps(1) infinite; }
.badge.unknown  { background: var(--unk); color: #888; }
@keyframes blink { 50% { opacity: .35; } }

/* ── 2×2 channel grid ── */
.channels {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1px;
  background: var(--border);
}

.ch {
  background: var(--surface);
  padding: 7px 10px 8px;
}

.ch-lbl {
  font-size: 8px; font-weight: 600; text-transform: uppercase; letter-spacing: .1em;
  color: var(--dim); margin-bottom: 5px;
}

.bar-track { height: 7px; background: #1e1e1e; border-radius: 3px; overflow: hidden; margin-bottom: 5px; }
.bar-fill  { height: 100%; border-radius: 3px; transition: width .4s ease, background .3s; }
.bar-ok       { background: var(--ok); }
.bar-warn     { background: var(--warn); }
.bar-error,
.bar-critical { background: var(--err); }
.bar-unknown  { background: var(--unk); }

.ch-val {
  font-size: 11px; font-variant-numeric: tabular-nums; font-weight: 600;
  transition: color .3s;
}
.ch-val.ok       { color: var(--ok); }
.ch-val.warn     { color: var(--warn); }
.ch-val.error,
.ch-val.critical { color: var(--err); }
.ch-val.unknown  { color: var(--dim); }

/* ── empty state ── */
.empty { text-align: center; padding: 60px 0; color: var(--dim); font-size: 13px; }
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
  <a href="/desktop">Desktop</a>
  <a href="/mobile" class="active">Mobile</a>
</nav>

<main id="list">
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

function signalPct(level, errLimit) {
  if (level == null) return null;
  if (errLimit == null || errLimit === 0) return Math.min(100, Math.max(0, 100 - level));
  return Math.min(100, Math.max(0, (1 - level / errLimit) * 100));
}

// Cable bar: fixed scale -2 to 8 dBm. Single colour based on threshold zone.
function cablePct(level) {
  if (level == null) return 0;
  return Math.min(100, Math.max(0, (level + 2) / 10 * 100));
}

// Signal bar: fixed scale 0-100%. Single colour based on threshold zone.
// level=0 → 100% bar (full signal), level=errLimit → 0% bar (no signal).
function signalPct(level, errLimit) {
  if (level == null) return 0;
  const max = errLimit != null && errLimit > 0 ? errLimit : 7;
  return Math.min(100, Math.max(0, (1 - level / max) * 100));
}

// ── Channel cell builders ─────────────────────────────────────────
function cableCh(chId, label, level, status, okLimit, errLimit) {
  const cls = cableCls(level, okLimit, errLimit);
  const w   = cablePct(level);
  const val = level != null ? level.toFixed(1) + '\u00a0dBm' : '\u2014';
  return `<div class="ch" data-ch="${chId}">
    <div class="ch-lbl">${label}</div>
    <div class="bar-track"><div class="bar-fill bar-${cls}" style="width:${w}%"></div></div>
    <div class="ch-val ${cls}">${val}</div>
  </div>`;
}

function signalCh(chId, label, level, status, okLimit, errLimit) {
  const cls = signalCls(level, okLimit, errLimit);
  const w   = signalPct(level, errLimit);
  const val = w > 0 || level === 0 ? w.toFixed(1) + '\u00a0%' : '\u2014';
  return `<div class="ch" data-ch="${chId}">
    <div class="ch-lbl">${label}</div>
    <div class="bar-track"><div class="bar-fill bar-${cls}" style="width:${w}%"></div></div>
    <div class="ch-val ${cls}">${val}</div>
  </div>`;
}

// ── Card render ───────────────────────────────────────────────────
function cardHTML(cam) {
  const overall = cam.overall_status || 'unknown';
  const badge   = overall === 'unknown' ? 'NO\u00a0DATA' : overall.toUpperCase();
  return `<div class="cam ${overall}" id="cam-${cam.cam}">
    <div class="cam-head">
      <span class="cam-title">${cam.label || 'CAM\u00a0' + cam.cam}</span>
      <span class="badge ${overall}">${badge}</span>
    </div>
    <div class="channels">
      ${cableCh('sfp1_cable',  'SFP 1 Cable',  cam.sfp1_cable_level,  cam.sfp1_cable_status,  cam.sfp1_cable_ok_limit,  cam.sfp1_cable_error_limit)}
      ${signalCh('sfp1_signal','SFP 1 Signal', cam.sfp1_signal_level, cam.sfp1_signal_status, cam.sfp1_signal_ok_limit, cam.sfp1_signal_error_limit)}
      ${cableCh('sfp2_cable',  'SFP 2 Cable',  cam.sfp2_cable_level,  cam.sfp2_cable_status,  cam.sfp2_cable_ok_limit,  cam.sfp2_cable_error_limit)}
      ${signalCh('sfp2_signal','SFP 2 Signal', cam.sfp2_signal_level, cam.sfp2_signal_status, cam.sfp2_signal_ok_limit, cam.sfp2_signal_error_limit)}
    </div>
  </div>`;
}

// ── In-place patching ─────────────────────────────────────────────
function patchCableCh(card, chId, level, okLimit, errLimit) {
  const ch = card.querySelector(`[data-ch="${chId}"]`);
  if (!ch) return;
  const cls  = cableCls(level, okLimit, errLimit);
  const fill = ch.querySelector('.bar-fill');
  if (fill) {
    fill.style.width = cablePct(level) + '%';
    fill.className   = `bar-fill bar-${cls}`;
  }
  const v = ch.querySelector('.ch-val');
  v.textContent = level != null ? level.toFixed(1) + '\u00a0dBm' : '\u2014';
  v.className   = `ch-val ${cls}`;
}

function patchSignalCh(card, chId, level, okLimit, errLimit) {
  const ch = card.querySelector(`[data-ch="${chId}"]`);
  if (!ch) return;
  const cls  = signalCls(level, okLimit, errLimit);
  const w    = signalPct(level, errLimit);
  const fill = ch.querySelector('.bar-fill');
  if (fill) { fill.style.width = w + '%'; fill.className = `bar-fill bar-${cls}`; }
  const v = ch.querySelector('.ch-val');
  v.textContent = w > 0 || level === 0 ? w.toFixed(1) + '\u00a0%' : '\u2014';
  v.className   = `ch-val ${cls}`;
}

function patchCard(cam) {
  const overall = cam.overall_status || 'unknown';
  let card = document.getElementById('cam-' + cam.cam);

  if (!card) {
    const list  = document.getElementById('list');
    const empty = list.querySelector('.empty');
    if (empty) empty.remove();
    const tmp = document.createElement('div');
    tmp.innerHTML = cardHTML(cam);
    card = tmp.firstChild;
    const after = [...list.querySelectorAll('.cam')]
      .find(el => parseInt(el.id.replace('cam-','')) > cam.cam);
    after ? list.insertBefore(card, after) : list.appendChild(card);
    return;
  }

  card.className = 'cam ' + overall;
  const badge = card.querySelector('.badge');
  badge.className   = 'badge ' + overall;
  badge.textContent = overall === 'unknown' ? 'NO\u00a0DATA' : overall.toUpperCase();
  const title = card.querySelector('.cam-title');
  if (title && cam.label) title.textContent = cam.label;

  for (const n of ['1', '2']) {
    patchCableCh(card, `sfp${n}_cable`,
      cam[`sfp${n}_cable_level`], cam[`sfp${n}_cable_ok_limit`], cam[`sfp${n}_cable_error_limit`]);
    patchSignalCh(card, `sfp${n}_signal`,
      cam[`sfp${n}_signal_level`], cam[`sfp${n}_signal_ok_limit`], cam[`sfp${n}_signal_error_limit`]);
  }
}

// ── Gateway status ────────────────────────────────────────────────
function setGwStatus(connected) {
  document.getElementById('dot').className    = 'dot ' + (connected ? 'ok' : 'err');
  document.getElementById('gw-lbl').textContent = connected ? 'Connected' : 'Disconnected';
}

function renderAll(cameras) {
  const list = document.getElementById('list');
  if (!cameras.length) {
    list.innerHTML = '<div class="empty">No cameras detected</div>';
    return;
  }
  list.innerHTML = [...cameras].sort((a,b) => a.cam - b.cam).map(cardHTML).join('');
}

async function loadSnapshot() {
  try {
    const data = await fetch('/api/cameras').then(r => r.json());
    setGwStatus(data.connected);
    renderAll(data.cameras || []);
  } catch { setGwStatus(false); }
}

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
    card.style.transition = 'opacity .4s';
    card.style.opacity    = '0';
    setTimeout(() => {
      card.remove();
      if (!document.querySelector('.cam'))
        document.getElementById('list').innerHTML = '<div class="empty">No cameras connected</div>';
    }, 400);
  });

  es.onerror = () => {
    setGwStatus(false);
    es.close();
    setTimeout(connect, 3000);
  };
}

loadSnapshot();
connect();
</script>
</body>
</html>
"""