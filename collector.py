"""
Grass Valley Camera Connect — IP SFP Fibre Level Collector
XML v2.0 protocol over TCP.

Connection sequence:
  1. <application-authentication-request>   (required first message)
  2. <device-information-request subscribe> (discover cameras + watch for changes)
  3. <function-information-request>         (load status Mode option mappings)
  4. <function-value-request subscribe>     (get current values + live updates)

The collector connects and authenticates immediately on start, even if no
cameras are available. Cameras that connect later are detected automatically
via device-information-indication and subscribed on arrival.
"""

import logging
import queue
import socket
import threading
import time
import xml.etree.ElementTree as ET

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


# ── Configuration ──────────────────────────────────────────────────────────────
GATEWAY_IP     = "192.168.61.10"   # Camera Connect Gateway IP address
GATEWAY_PORT   = 8080              # Default XML port
APP_NAME       = "FibreMonitor"    # Visible in gateway web interface / logs
CAMERA_NUMBERS = []                # Specific camera numbers to monitor; [] = auto-discover


# ── SFP NS_IDs ─────────────────────────────────────────────────────────────────
# Cable: higher value = better. ok_limit = min "good" level, err_limit = failure level.
# Signal: lower value = better (0 = perfect). err_limit = max acceptable loss.
SFP_IDS = {
    9105: "sfp1_cable_level",
    9107: "sfp1_cable_status",
    9104: "sfp1_cable_error_limit",
    9106: "sfp1_cable_ok_limit",
    9109: "sfp2_cable_level",
    9111: "sfp2_cable_status",
    9108: "sfp2_cable_error_limit",
    9110: "sfp2_cable_ok_limit",
    9113: "sfp1_signal_level",
    9115: "sfp1_signal_status",
    9112: "sfp1_signal_error_limit",
    9114: "sfp1_signal_ok_limit",
    9117: "sfp2_signal_level",
    9119: "sfp2_signal_status",
    9116: "sfp2_signal_error_limit",
    9118: "sfp2_signal_ok_limit",
}
STATUS_IDS = {9107, 9111, 9115, 9119}

# Default option map (gateway value 0=ok, 1=critical, 2=error).
# Overwritten at startup via function-information-request.
DEFAULT_OPTION_MAP = {ns_id: {0: "ok", 1: "critical", 2: "error"} for ns_id in STATUS_IDS}


# ── XML builders ───────────────────────────────────────────────────────────────

def _msg(xml: str) -> bytes:
    return (xml.strip() + "\n").encode()


def _auth() -> bytes:
    return _msg(
        f'<application-authentication-request xml-protocol="2.0" response-level="Never">'
        f"<name>{APP_NAME}</name>"
        f"</application-authentication-request>"
    )


def _device_request() -> bytes:
    return _msg('<device-information-request subscribe="true"/>')


def _option_map_request(sessionids: list[str]) -> bytes:
    devices = "".join(
        f"<device><sessionid>{sid}</sessionid>"
        + "".join(f'<function id="{fid}"/>' for fid in STATUS_IDS)
        + "</device>"
        for sid in sessionids
    )
    return _msg(
        f'<function-information-request response-level="Never">'
        f"{devices}"
        f"</function-information-request>"
    )


def _subscribe(cam_states: list[dict]) -> bytes:
    devices = "".join(
        f"<device><sessionid>{s['sessionid']}</sessionid>"
        + "".join(f'<function id="{fid}"/>' for fid in SFP_IDS)
        + "</device>"
        for s in cam_states
        if s.get("sessionid")
    )
    if not devices:
        return b""
    return _msg(
        f'<function-value-request subscribe="true" response-level="Always">'
        f"{devices}"
        f"</function-value-request>"
    )


# ── XML parsers ────────────────────────────────────────────────────────────────

def _t(el) -> str:
    return el.text.strip() if el is not None and el.text else ""


def _parse(xml_str: str):
    try:
        return ET.fromstring(f"<root>{xml_str}</root>")
    except ET.ParseError:
        return None


def _parse_devices(root) -> list[dict]:
    result = []
    for ind in root.findall("device-information-indication"):
        for dev in ind.findall("device"):
            name_el = dev.find("name")
            type_el = dev.find("type")
            if name_el is None or type_el is None:
                continue
            result.append({
                "cam":       int(name_el.text.strip()),
                "type":      _t(type_el),
                "state":     dev.get("connection-state", "connected"),
                "sessionid": _t(dev.find("sessionid")),
                "alias":     _t(dev.find("alias")),
                "deviceid":  _t(dev.find("deviceid")),
            })
    return result


def _parse_option_map(root) -> dict:
    mappings = {}
    for ind in root.findall("function-information-indication"):
        for dev in ind.findall("device"):
            for func in dev.findall("function"):
                fid = int(func.get("id", 0))
                if fid not in STATUS_IDS:
                    continue
                opts = {}
                for opt in func.findall("option"):
                    name = opt.get("name", "").lower()
                    try:
                        val = int(opt.text.strip())
                    except (TypeError, ValueError):
                        continue
                    if "ok" in name:
                        opts[val] = "ok"
                    elif "critic" in name:
                        opts[val] = "critical"
                    elif "error" in name or "err" in name:
                        opts[val] = "error"
                if opts:
                    mappings[fid] = opts
    return mappings


def _parse_values(root, option_map: dict) -> list[dict]:
    updates = []
    for tag in ("function-value-indication", "function-information-indication"):
        for ind in root.findall(tag):
            for dev in ind.findall("device"):
                name_el = dev.find("name")
                if name_el is None:
                    continue
                try:
                    cam = int(name_el.text.strip())
                except (TypeError, ValueError):
                    continue
                for func in dev.findall("function"):
                    fid    = int(func.get("id", 0))
                    val_el = func.find("value")
                    if fid not in SFP_IDS or val_el is None or not val_el.text:
                        continue
                    raw    = val_el.text.strip()
                    field  = SFP_IDS[fid]
                    level = status = None
                    if fid in STATUS_IDS:
                        try:
                            status = option_map.get(fid, {}).get(int(raw), raw.lower())
                        except ValueError:
                            status = raw.lower()
                    else:
                        try:
                            level = round(float(raw), 2)
                        except ValueError:
                            pass
                    updates.append({"cam": cam, "field": field, "level": level, "status": status})
    return updates


# ── Stream splitter ────────────────────────────────────────────────────────────

_ROOT_TAGS = [
    "application-authentication-indication",
    "device-information-indication",
    "function-information-indication",
    "function-value-indication",
    "request-response",
]


def _split(buf: str) -> tuple[list[str], str]:
    messages = []
    while True:
        best = -1
        for tag in _ROOT_TAGS:
            idx = buf.find(f"</{tag}>")
            if idx != -1:
                end = idx + len(f"</{tag}>")
                if best == -1 or end < best:
                    best = end
        if best == -1:
            break
        messages.append(buf[:best].strip())
        buf = buf[best:].lstrip()
    return messages, buf


# ── Overall status ─────────────────────────────────────────────────────────────

def _overall(state: dict) -> str:
    statuses = [state.get(f) for f in (
        "sfp1_cable_status", "sfp2_cable_status",
        "sfp1_signal_status", "sfp2_signal_status"
    )]
    present = [s for s in statuses if s]
    if not present:
        return "unknown"
    if "critical" in present:
        return "critical"
    if "error" in present:
        return "error"
    if all(s == "ok" for s in present):
        return "ok"
    return "unknown"


# ── Collector ──────────────────────────────────────────────────────────────────

class GrassValleyCollector:
    """
    Maintains a persistent TCP connection to the Camera Connect Gateway.
    Authenticates immediately on boot — cameras are optional and can join
    or leave at any time. Alias is used as the primary camera identifier.
    """

    def __init__(self):
        self._lock       = threading.Lock()
        self._cameras:   dict[int, dict] = {}   # keyed by camera number
        self._option_map = dict(DEFAULT_OPTION_MAP)
        self._connected  = False   # True once authenticated, regardless of cameras
        self._sock       = None
        self._listeners: list[queue.Queue] = []

    def start(self):
        threading.Thread(target=self._run, daemon=True).start()

    # ── Public API ─────────────────────────────────────────────────────────────

    def is_connected(self) -> bool:
        return self._connected

    def get_cameras(self) -> list[dict]:
        with self._lock:
            return sorted(self._cameras.values(), key=lambda c: c.get("sort_key", c["cam"]))

    def subscribe(self) -> queue.Queue:
        q: queue.Queue = queue.Queue(maxsize=128)
        with self._lock:
            self._listeners.append(q)
        return q

    def unsubscribe(self, q: queue.Queue) -> None:
        with self._lock:
            self._listeners = [l for l in self._listeners if l is not q]

    # ── Connection loop ────────────────────────────────────────────────────────

    def _run(self):
        while True:
            try:
                self._connect_and_run()
            except Exception as e:
                log.error(f"Collector error: {e}", exc_info=True)
            self._connected = False
            self._sock      = None
            log.info("Reconnecting in 5 seconds…")
            time.sleep(5)

    def _connect_and_run(self):
        log.info(f"Connecting to {GATEWAY_IP}:{GATEWAY_PORT}…")
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(15)
            sock.connect((GATEWAY_IP, GATEWAY_PORT))
            log.info("Connected. Authenticating…")

            # Step 1: authenticate (must be first message; no response expected)
            sock.sendall(_auth())
            time.sleep(0.5)

            # Step 2: discover devices and subscribe to connection changes
            sock.sendall(_device_request())
            raw     = self._recv_burst(sock)
            devices = _parse_devices(_parse(raw) or ET.Element("root"))

            # Mark as connected immediately after auth — cameras are optional
            self._connected = True
            log.info(f"Authenticated. Found {len([d for d in devices if d['type'] == 'Camera'])} camera(s).")

            # Seed initial cameras
            cam_numbers = list(CAMERA_NUMBERS) or sorted({
                d["cam"] for d in devices
                if d["type"] == "Camera" and d["state"] == "connected"
            })

            with self._lock:
                for d in devices:
                    if d["type"] != "Camera" or d["state"] != "connected":
                        continue
                    if CAMERA_NUMBERS and d["cam"] not in CAMERA_NUMBERS:
                        continue
                    self._cameras[d["cam"]] = self._make_state(d)

            # Step 3: load Mode option mappings
            sessionids = [s["sessionid"] for s in self._cameras.values() if s.get("sessionid")]
            if sessionids:
                sock.sendall(_option_map_request(sessionids))
                loaded = _parse_option_map(_parse(self._recv_burst(sock)) or ET.Element("root"))
                if loaded:
                    with self._lock:
                        self._option_map = loaded
                    log.info(f"Loaded option mappings for {len(loaded)} status functions.")

            # Step 4: subscribe to SFP values for all known cameras
            self._sock = sock
            with self._lock:
                cam_states = list(self._cameras.values())
            req = _subscribe(cam_states)
            if req:
                sock.sendall(req)
                log.info(f"Subscribed to SFP values for {len(cam_states)} camera(s).")
            else:
                log.info("No cameras to subscribe to yet — waiting for connections.")

            # Step 5: process incoming messages indefinitely
            sock.settimeout(30)
            buf = ""
            while True:
                try:
                    chunk = sock.recv(8192).decode("utf-8", errors="replace")
                    if not chunk:
                        raise ConnectionError("Gateway closed the connection.")
                    buf += chunk
                    messages, buf = _split(buf)
                    for xml_str in messages:
                        self._handle(xml_str)
                except socket.timeout:
                    log.debug("No data from gateway for 30s (subscription active).")

    def _recv_burst(self, sock: socket.socket, timeout: float = 3.0) -> str:
        sock.settimeout(timeout)
        data = ""
        while True:
            try:
                chunk = sock.recv(8192)
                if not chunk:
                    break
                data += chunk.decode("utf-8", errors="replace")
            except socket.timeout:
                break
        return data

    def _make_state(self, d: dict) -> dict:
        """Build initial camera state dict from a device discovery record."""
        alias = d.get("alias", "").strip()
        # Parse numeric part of alias for sort ordering (e.g. "Cam 2" → 2)
        sort_key = d["cam"]
        if alias:
            import re
            m = re.search(r'\d+', alias)
            if m:
                sort_key = int(m.group())
        return {
            "cam":            d["cam"],
            "label":          alias or d.get("deviceid") or f"CAM {d['cam']}",
            "alias":          alias,
            "deviceid":       d.get("deviceid", ""),
            "sessionid":      d.get("sessionid", ""),
            "overall_status": "unknown",
            "sort_key":       sort_key,
        }

    # ── Message handler ────────────────────────────────────────────────────────

    def _handle(self, xml_str: str):
        if not xml_str:
            return
        root = _parse(xml_str)
        if root is None:
            return

        # Device connect / disconnect
        for d in _parse_devices(root):
            if d["type"] != "Camera":
                continue
            cam = d["cam"]

            if d["state"] == "disconnected":
                with self._lock:
                    removed = cam in self._cameras
                    if removed:
                        del self._cameras[cam]
                if removed:
                    log.info(f"Camera {cam} disconnected.")
                    self._notify({"event": "remove", "data": {"cam": cam}})

            elif d["state"] == "connected":
                with self._lock:
                    known = cam in self._cameras

                if not known:
                    # New camera — subscribe and notify
                    if CAMERA_NUMBERS and cam not in CAMERA_NUMBERS:
                        continue
                    state = self._make_state(d)
                    log.info(f"Camera {cam} ({state['label']}) connected.")
                    with self._lock:
                        self._cameras[cam] = state
                    self._notify({"event": "camera", "data": dict(state)})
                    if self._sock:
                        try:
                            self._sock.sendall(_subscribe([state]))
                        except OSError as e:
                            log.warning(f"Could not subscribe to CAM {cam}: {e}")
                else:
                    # Already known — check if alias/label changed and update if so
                    new_alias = d.get("alias", "").strip()
                    new_deviceid = d.get("deviceid", "").strip()
                    with self._lock:
                        state = self._cameras[cam]
                        changed = (
                            state.get("alias")    != new_alias or
                            state.get("deviceid") != new_deviceid
                        )
                        if changed:
                            import re
                            sort_key = cam
                            if new_alias:
                                m = re.search(r'\d+', new_alias)
                                if m:
                                    sort_key = int(m.group())
                            state["alias"]    = new_alias
                            state["deviceid"] = new_deviceid
                            state["label"]    = new_alias or new_deviceid or f"CAM {cam}"
                            state["sort_key"] = sort_key
                            snapshot = dict(state)
                    if changed:
                        log.info(f"Camera {cam} alias updated: {new_alias or new_deviceid}")
                        self._notify({"event": "camera", "data": snapshot})

        # SFP value updates
        with self._lock:
            option_map = dict(self._option_map)

        updates = _parse_values(root, option_map)
        if not updates:
            return

        snapshot = None
        with self._lock:
            for u in updates:
                cam   = u["cam"]
                state = self._cameras.get(cam)
                if state is None:
                    continue
                if u["level"] is not None:
                    state[u["field"]] = u["level"]
                elif u["status"] is not None:
                    state[u["field"]] = u["status"]
                state["overall_status"] = _overall(state)
                state["last_updated"]   = time.time()
                snapshot = dict(state)

        if snapshot:
            self._notify({"event": "camera", "data": snapshot})

    def _notify(self, event: dict):
        dead = []
        for q in list(self._listeners):
            try:
                q.put_nowait(event)
            except queue.Full:
                dead.append(q)
        if dead:
            with self._lock:
                self._listeners = [l for l in self._listeners if l not in dead]