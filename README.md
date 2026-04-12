# GV Fibre Monitor

Live fibre optic signal monitoring dashboard for Grass Valley Camera Connect camera systems.

Connects to the Camera Connect Gateway via XML v2.0 protocol over TCP, subscribes to
fibre level updates, and serves a live dashboard publicly via Cloudflare Tunnel.

---

## Setup

### 1. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure the collector

Edit the `CONFIG` section at the top of `collector.py`:

```python
GATEWAY_IP     = "192.168.1.100"   # ← IP of your Camera Connect Gateway server
GATEWAY_PORT   = 8080              # Default port (check gateway's web interface)
APP_NAME       = "FibreMonitor"    # Shows up in gateway's web interface / logs
CAMERA_NUMBERS = []                # Leave [] to auto-discover, or list e.g. [50, 51, 52]
```

### 3. Run the server

```bash
python app.py
```

You should see:
```
[INFO] Connecting to 192.168.1.100:8080…
[INFO] TCP connected. Authenticating…
[INFO] Found cameras: [50, 51, 52]
[INFO] Loaded option mappings for 4 functions.
[INFO] Subscribed to fibre value changes.
 * Running on http://0.0.0.0:5000
```

Open `http://localhost:5000` to see the dashboard on your local machine.

## How it works (XML v2.0 Protocol)

The collector follows the correct Camera Connect XML v2.0 protocol sequence:

```
1. TCP Connect to Gateway
2. → <application-authentication-request>   (REQUIRED first message)
3. ← <application-authentication-indication>
4. → <device-information-request subscribe="true">
5. ← <device-information-indication>        (list of all cameras/basestations/OCPs)
6. → <function-information-request>         (learn Mode option int→label mappings)
7. ← <function-information-indication>
8. → <function-value-request subscribe="true">  (get current values + subscribe)
9. ← <function-value-indication>            (current values, then pushed on every change)
```

The gateway **pushes** changes as they happen — no polling needed.

---

## API

The Flask server exposes `/api/cameras`:

```json
{
  "connected": true,
  "timestamp": 1712345678.0,
  "cameras": [
    {
      "cam": 50,
      "alias": "MidField",
      "rx_cable_status": "ok",
      "rx_cable_level": 72.5,
      "tx_cable_status": "ok",
      "tx_cable_level": 68.2,
      "rx_signal_status": "ok",
      "rx_signal_level": 75.0,
      "tx_signal_status": "ok",
      "tx_signal_level": 66.7,
      "overall_status": "ok",
      "last_updated": 1712345678.0
    }
  ]
}
```
