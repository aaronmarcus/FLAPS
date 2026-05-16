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

---

## Making it publicly accessible (free, no signup needed)

### Option A — Cloudflare Tunnel (recommended)

1. Download `cloudflared` from https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/
2. Run alongside your server:
   ```bash
   cloudflared tunnel --url http://localhost:5000
   ```
3. Cloudflare prints a public URL like `https://something.trycloudflare.com`
4. Share that URL — it works immediately, no account needed

> ⚠️  The anonymous Cloudflare Tunnel URL changes every time you restart.
> For a permanent URL, create a free Cloudflare account and use a named tunnel.

### Option B — ngrok

```bash
ngrok http 5000
```

---

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

Level values are 0–100% (raw 0–255 u8bit scaled to percentage).

---

## NS_IDs monitored

| NS_ID | Name                        | Type  | Field            |
|-------|-----------------------------|-------|------------------|
| 8204  | Cam2Base Fiber Status       | Mode  | rx_cable_status  |
| 8205  | Cam2Base Optical Margin     | Value | rx_cable_level   |
| 8206  | Bs2Cam Fiber Status         | Mode  | tx_cable_status  |
| 8207  | Bs2Cam Optical Margin       | Value | tx_cable_level   |
| 8242  | Cam2Bs Fiber Signal Quality | Value | rx_signal_level  |
| 8244  | Cam2Base Fiber Signal Status| Mode  | rx_signal_status |
| 8246  | Bs2Cam Fiber Signal Quality | Value | tx_signal_level  |
| 8248  | Bs2Cam Fiber Signal Status  | Mode  | tx_signal_status |

---

## Troubleshooting

**"No cameras found"**
- Ping the gateway IP to confirm network connectivity
- Check the gateway's web interface to confirm the XML port (default 8080)
- Try setting `CAMERA_NUMBERS` manually (e.g. `[50, 51, 52]`) if auto-discovery fails

**Status shows as "unknown" even when connected**
- The Mode option mappings may not have loaded. Check the log for "Loaded option mappings"
- Some camera models may report fibre status on Basestation devices rather than Camera
  devices — the collector subscribes to both

**Dashboard shows — for level values**
- That camera may not support those particular NS_IDs (varies by camera model/software version)
- Check the gateway's own web interface to see which functions are available

---

## Files

```
gv_fibre_monitor/
├── app.py          — Flask server (run this)
├── collector.py    — TCP connection + XML v2.0 protocol logic
├── dashboard.py    — HTML dashboard (dark broadcast-style UI)
├── requirements.txt
└── README.md
```
