"""
Grass Valley Camera Connect — IP SFP Fibre Level Collector
XML v2.0 protocol over TCP.

Connection sequence:
  1. <application-authentication-request>   (required first message)
  2. <device-information-request>           (discover cameras, subscribe to connect/disconnect)
  3. <function-information-request>         (load status Mode option mappings)
  4. <function-value-request subscribe>     (get current values + live updates)

The gateway pushes <function-value-indication> on every change — no polling needed.
Device connect/disconnect arrives as <device-information-indication>.
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
# IP Transmission SFP functions. Signal convention: 0.0 raw = 100% (full signal).
# All 16 IP Transmission SFP NS_IDs — levels, statuses and thresholds.
# Thresholds are static but are returned alongside live values in subscribe="true".
# Cable scale: higher = better. ok_limit = lower bound of "good" range.
# Signal scale: lower = better (0 = full signal). error_limit = max acceptable loss.
SFP_IDS = {
    9105: "sfp1_cable_level",         # SFP 1 Cable actual
    9107: "sfp1_cable_status",        # SFP 1 Cable status (Mode)
    9104: "sfp1_cable_error_limit",   # SFP 1 Cable error threshold
    9106: "sfp1_cable_ok_limit",      # SFP 1 Cable ok threshold
    9109: "sfp2_cable_level",         # SFP 2 Cable actual
    9111: "sfp2_cable_status",        # SFP 2 Cable status (Mode)
    9108: "sfp2_cable_error_limit",   # SFP 2 Cable error threshold
    9110: "sfp2_cable_ok_limit",      # SFP 2 Cable ok threshold
    9113: "sfp1_signal_level",        # SFP 1 Signal actual (0 = full)
    9115: "sfp1_signal_status",       # SFP 1 Signal status (Mode)
    9112: "sfp1_signal_error_limit",  # SFP 1 Signal error threshold (max loss)
    9114: "sfp1_signal_ok_limit",     # SFP 1 Signal ok threshold (min loss for ok)
    9117: "sfp2_signal_level",        # SFP 2 Signal actual
    9119: "sfp2_signal_status",       # SFP 2 Signal status (Mode)
    9116: "sfp2_signal_error_limit",  # SFP 2 Signal error threshold
    9118: "sfp2_signal_ok_limit",     # SFP 2 Signal ok threshold
}
STATUS_IDS = {9107, 9111, 9115, 9119}

# Default option map — gateway uses "OK", "Critic"/"Critical", "Error".
# Overwritten at startup by function-information-request if the gateway responds.
DEFAULT_OPTION_MAP = {ns_id: {0: "ok", 1: "critical", 2: "error"} for ns_id in STATUS_IDS}


# ── XML message builders ───────────────────────────────────────────────────────

def _msg(xml: str) -> bytes:
    return (xml.strip() + "\n").encode()


def auth_request() -> bytes:
    return _msg(
        f'<application-authentication-request xml-protocol="2.0" response-level="Never">'
        f"<name>{APP_NAME}</name>"
        f"</application-authentication-request>"
    )


def device_info_request() -> bytes:
    return _msg('<device-information-request subscribe="true"/>')


def option_map_request(sessionids: list[str]) -> bytes:
    """Request Mode option definitions for status fields."""
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


def subscribe_request(cam_states: list[dict]) -> bytes:
    """Subscribe to all SFP values for the given cameras (addressed by sessionid)."""
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

def _parse_devices(root) -> list[dict]:
    result = []
    for ind in root.findall("device-information-indication"):
        for dev in ind.findall("device"):
            name_el = dev.find("name")
            type_el = dev.find("type")
            if name_el is None or type_el is None:
                continue
            def text(el):
                return el.text.strip() if el is not None and el.text else ""
            result.append({
                "cam":              int(name_el.text.strip()),
                "type":             text(type_el),
                "state":            dev.get("connection-state", "connected"),
                "sessionid":        text(dev.find("sessionid")),
                "deviceid":         text(dev.find("deviceid")),
                "alias":            text(dev.find("alias")),
            })
    return result


def _parse_option_map(root) -> dict:
    """Return {ns_id: {int_val: status_str}} from function-information-indication."""
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
                    elif "critic" in name:     # matches "Critic", "Critical"
                        opts[val] = "critical"
                    elif "error" in name or "err" in name:
                        opts[val] = "error"
                if opts:
                    mappings[fid] = opts
    return mappings


def _parse_values(root, option_map: dict) -> list[dict]:
    """Return [{cam, field, level, status}] from function-value-indication."""
    updates = []
    # Spec note: some gateways use function-information-indication for value responses
    inds = root.findall("function-value-indication") + root.findall("function-information-indication")
    for ind in inds:
        for dev in ind.findall("device"):
            name_el = dev.find("name")
            if name_el is None:
                continue
            try:
                cam = int(name_el.text.strip())
            except (TypeError, ValueError):
                continue
            for func in dev.findall("function"):
                fid = int(func.get("id", 0))
                if fid not in SFP_IDS:
                    continue
                val_el = func.find("value")
                if val_el is None or val_el.text is None:
                    continue
                raw    = val_el.text.strip()
                field  = SFP_IDS[fid]
                level  = status = None
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


# ── Message stream splitter ────────────────────────────────────────────────────

_ROOT_TAGS = [
    "application-authentication-indication",
    "device-information-indication",
    "function-information-indication",
    "function-value-indication",
    "request-response",
]


def _split_messages(buf: str) -> tuple[list[str], str]:
    """Extract complete XML messages from buffer. Returns (messages, remainder)."""
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


def _parse(xml_str: str):
    """Wrap in root element and parse. Returns None on error."""
    try:
        return ET.fromstring(f"<root>{xml_str}</root>")
    except ET.ParseError:
        return None


def _derive_overall(state: dict) -> str:
    """Return worst-case status across all four SFP status fields."""
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
    Manages the TCP connection to the Camera Connect Gateway.
    Maintains live camera state and notifies SSE listeners on every change.
    """

    def __init__(self):
        self._lock       = threading.Lock()
        self._cameras:   dict[int, dict] = {}
        self._option_map = dict(DEFAULT_OPTION_MAP)
        self._connected  = False
        self._sock       = None
        self._listeners: list[queue.Queue] = []

    def start(self):
        threading.Thread(target=self._run, daemon=True).start()

    # ── Public API ─────────────────────────────────────────────────────────────

    def is_connected(self) -> bool:
        return self._connected

    def get_cameras(self) -> list[dict]:
        with self._lock:
            return list(self._cameras.values())

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

            # Step 1: authenticate (must be first message)
            sock.sendall(auth_request())
            time.sleep(0.3)

            # Step 2: discover devices
            sock.sendall(device_info_request())
            devices = _parse_devices(_parse(self._recv_burst(sock)) or ET.Element("root"))

            cam_numbers = list(CAMERA_NUMBERS) or sorted({
                d["cam"] for d in devices
                if d["type"] in ("Camera", "Basestation") and d["state"] == "connected"
            })

            if not cam_numbers:
                log.warning("No cameras found — check GATEWAY_IP and CAMERA_NUMBERS config.")
                time.sleep(10)
                return

            log.info(f"Found {len(cam_numbers)} camera(s): {cam_numbers}")

            with self._lock:
                for d in devices:
                    if d["cam"] not in cam_numbers or d["type"] != "Camera":
                        continue
                    cam = d["cam"]
                    if cam not in self._cameras:
                        self._cameras[cam] = {"cam": cam, "overall_status": "unknown"}
                    self._cameras[cam]["label"]     = d["deviceid"] or d["alias"] or f"CAM {cam}"
                    self._cameras[cam]["sessionid"] = d["sessionid"]

            # Step 3: load Mode option mappings (ok/error/critical integer values vary by model)
            sessionids = [s["sessionid"] for s in self._cameras.values() if s.get("sessionid")]
            if sessionids:
                sock.sendall(option_map_request(sessionids))
                loaded = _parse_option_map(_parse(self._recv_burst(sock)) or ET.Element("root"))
                if loaded:
                    with self._lock:
                        self._option_map = loaded
                    log.info(f"Loaded option mappings for {len(loaded)} status functions.")
                else:
                    log.info("Using default option mappings (ok=0, critical=1, error=2).")

            # Step 4: subscribe to live SFP values
            self._sock = sock
            req = subscribe_request(list(self._cameras.values()))
            if req:
                sock.sendall(req)
                log.info("Subscribed to SFP values.")
            self._connected = True

            # Step 5: process incoming messages indefinitely
            sock.settimeout(30)
            buf = ""
            while True:
                try:
                    chunk = sock.recv(8192).decode("utf-8", errors="replace")
                    if not chunk:
                        raise ConnectionError("Gateway closed the connection.")
                    buf += chunk
                    messages, buf = _split_messages(buf)
                    for xml_str in messages:
                        self._handle(xml_str)
                except socket.timeout:
                    log.debug("No data from gateway for 30s (subscription active).")

    def _recv_burst(self, sock: socket.socket, timeout: float = 3.0) -> str:
        """Read until no data arrives for `timeout` seconds."""
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

    # ── Message handler ────────────────────────────────────────────────────────

    def _handle(self, xml_str: str):
        if not xml_str:
            return
        root = _parse(xml_str)
        if root is None:
            return

        # Device connect / disconnect events
        for d in _parse_devices(root):
            if d["type"] not in ("Camera", "Basestation"):
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

            elif d["state"] == "connected" and d["type"] == "Camera":
                with self._lock:
                    known = cam in self._cameras
                if not known:
                    label = d["deviceid"] or d["alias"] or f"CAM {cam}"
                    log.info(f"Camera {cam} ({label}) connected.")
                    state = {"cam": cam, "label": label, "sessionid": d["sessionid"], "overall_status": "unknown"}
                    with self._lock:
                        self._cameras[cam] = state
                    self._notify({"event": "camera", "data": dict(state)})
                    if self._sock:
                        try:
                            self._sock.sendall(subscribe_request([state]))
                        except OSError as e:
                            log.warning(f"Could not subscribe to CAM {cam}: {e}")

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
                state = self._cameras.setdefault(cam, {"cam": cam, "label": f"CAM {cam}", "overall_status": "unknown"})
                if u["level"] is not None:
                    state[u["field"]] = u["level"]
                elif u["status"] is not None:
                    state[u["field"]] = u["status"]
                state["overall_status"] = _derive_overall(state)
                state["last_updated"]   = time.time()
                snapshot = dict(state)

        if snapshot:
            self._notify({"event": "camera", "data": snapshot})

    def _notify(self, event: dict):
        """Push event to all SSE listeners, pruning disconnected ones."""
        dead = []
        for q in list(self._listeners):
            try:
                q.put_nowait(event)
            except queue.Full:
                dead.append(q)
        if dead:
            with self._lock:
                self._listeners = [l for l in self._listeners if l not in dead]