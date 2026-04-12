"""
Grass Valley Fibre Monitor — Flask Server

GET /            → redirect to /desktop
GET /desktop     → desktop dashboard (grid layout, full detail)
GET /mobile      → mobile dashboard (single column, at-a-glance)
GET /api/cameras → JSON snapshot of all camera states
GET /stream      → Server-Sent Events (snapshot / camera / remove events)
"""

import json
import time

from flask import Flask, jsonify, redirect, render_template_string, Response, stream_with_context

from collector import GrassValleyCollector
from dashboard import DESKTOP_HTML
from dashboard_mobile import MOBILE_HTML

app       = Flask(__name__)
collector = GrassValleyCollector()


@app.route("/")
def index():
    return redirect("/desktop")


@app.route("/desktop")
def desktop():
    return render_template_string(DESKTOP_HTML)


@app.route("/mobile")
def mobile():
    return render_template_string(MOBILE_HTML)


@app.route("/api/cameras")
def api_cameras():
    return jsonify({
        "connected": collector.is_connected(),
        "timestamp": time.time(),
        "cameras":   collector.get_cameras(),
    })


@app.route("/stream")
def stream():
    """
    SSE endpoint shared by both dashboards.

    Events:
      snapshot  {"connected": bool, "cameras": [...]}   — sent once on connect
      camera    {cam state dict}                         — pushed on every change
      remove    {"cam": int}                             — camera disconnected
    """
    q = collector.subscribe()

    @stream_with_context
    def generate():
        try:
            # Send current state immediately so the page renders without waiting
            yield (
                "event: snapshot\n"
                f"data: {json.dumps({'connected': collector.is_connected(), 'cameras': collector.get_cameras()})}\n\n"
            )
            while True:
                try:
                    ev = q.get(timeout=10)
                    yield f"event: {ev['event']}\ndata: {json.dumps(ev['data'])}\n\n"
                except Exception:
                    yield ": keepalive\n\n"   # prevent proxy timeout
        finally:
            collector.unsubscribe(q)

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control":       "no-cache, no-store",
            "X-Accel-Buffering":   "no",      # disable Nginx buffering
            "Connection":          "keep-alive",
        },
    )


if __name__ == "__main__":
    collector.start()
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)