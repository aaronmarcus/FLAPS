"""Mobile dashboard — served at /mobile. Single column, at-a-glance."""

MOBILE_HTML = """<!DOCTYPE html>
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
.cam-sub   { display: block; font-size: 12px; font-weight: 400; color: var(--dim); margin-top: 1px; letter-spacing: 0; }

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
function cablePct(level) {
  return level != null ? Math.min(100, Math.max(0, (level + 2) / 10 * 100)) : 0;
}
function signalPct(level, errLimit) {
  if (level == null) return 0;
  const max = errLimit != null && errLimit > 0 ? errLimit : 7;
  return Math.min(100, Math.max(0, (1 - level / max) * 100));
}

// ── Channel builders ──────────────────────────────────────────────
function cableCh(chId, label, level, okLimit, errLimit) {
  const cls = cableCls(level, okLimit, errLimit);
  const w   = cablePct(level);
  const val = level != null ? level.toFixed(1) + '\u00a0dBm' : '\u2014';
  return `<div class="ch" data-ch="${chId}">
    <div class="ch-lbl">${label}</div>
    <div class="bar-track"><div class="bar-fill bar-${cls}" style="width:${w}%"></div></div>
    <div class="ch-val ${cls}">${val}</div>
  </div>`;
}
function signalCh(chId, label, level, okLimit, errLimit) {
  const cls = signalCls(level, okLimit, errLimit);
  const w   = signalPct(level, errLimit);
  const val = level != null ? w.toFixed(1) + '\u00a0%' : '\u2014';
  return `<div class="ch" data-ch="${chId}">
    <div class="ch-lbl">${label}</div>
    <div class="bar-track"><div class="bar-fill bar-${cls}" style="width:${w}%"></div></div>
    <div class="ch-val ${cls}">${val}</div>
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
    <div class="channels">
      ${cableCh('sfp1_cable',  'SFP 1 Cable',  cam.sfp1_cable_level,  cam.sfp1_cable_ok_limit,  cam.sfp1_cable_error_limit)}
      ${signalCh('sfp1_signal','SFP 1 Signal', cam.sfp1_signal_level, cam.sfp1_signal_ok_limit, cam.sfp1_signal_error_limit)}
      ${cableCh('sfp2_cable',  'SFP 2 Cable',  cam.sfp2_cable_level,  cam.sfp2_cable_ok_limit,  cam.sfp2_cable_error_limit)}
      ${signalCh('sfp2_signal','SFP 2 Signal', cam.sfp2_signal_level, cam.sfp2_signal_ok_limit, cam.sfp2_signal_error_limit)}
    </div>
  </div>`;
}

// ── In-place patch ────────────────────────────────────────────────
function patchCh(card, chId, cls, w, val) {
  const ch = card.querySelector(`[data-ch="${chId}"]`);
  if (!ch) return;
  const fill = ch.querySelector('.bar-fill');
  if (fill) { fill.style.width = w + '%'; fill.className = `bar-fill bar-${cls}`; }
  const v = ch.querySelector('.ch-val');
  v.textContent = val;
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
      .find(el => (el.dataset.sortKey || el.id.replace('cam-','')) > String(cam.sort_key ?? cam.cam));
    after ? list.insertBefore(card, after) : list.appendChild(card);
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
    patchCh(card, `sfp${n}_cable`,  cableCls(cLvl, cOk, cErr),  cablePct(cLvl),
            cLvl != null ? cLvl.toFixed(1) + '\u00a0dBm' : '\u2014');
    const sLvl = cam[`sfp${n}_signal_level`], sOk = cam[`sfp${n}_signal_ok_limit`], sErr = cam[`sfp${n}_signal_error_limit`];
    const sW = signalPct(sLvl, sErr);
    patchCh(card, `sfp${n}_signal`, signalCls(sLvl, sOk, sErr), sW,
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
  const list = document.getElementById('list');
  if (!cameras.length) {
    list.innerHTML = '<div class="empty">No cameras connected</div>';
    return;
  }
  const sorted = [...cameras].sort((a, b) => (a.sort_key ?? a.cam) - (b.sort_key ?? b.cam));
  list.innerHTML = sorted.map(cardHTML).join('');
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
setInterval(() => { if (!gwConnected) window.location.reload(); }, 30000);

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

poll();
connect();
</script>
</body>
</html>
"""