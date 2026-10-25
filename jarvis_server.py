"""
jarvis_server.py - High-Performance Local Backend Server for Jarvis Futuristic HUD UI
Serves the HUD dashboard, streams real-time telemetry, handles command input,
voice waveform sync, and safe task confirmation dialogs.
"""

import http.server
import socketserver
import threading
import json
import time
import os
import sys
import psutil
import datetime
import urllib.request
import jarvis_brain
import jarvis_market

PORT = int(os.environ.get("PORT", 8765))
HOST = "0.0.0.0"  # Render requires binding to 0.0.0.0

# Shared Thread-Safe State
_lock = threading.Lock()
_state = {
    "state": "listening",  # "listening", "recognizing", "thinking", "speaking", "standby"
    "mode": "active",
    "sleeping": False,
    "voice_enabled": True,
    "note": "SYSTEM OPERATIONAL",
    "last_you": "",
    "last_jarvis": "",
    "model": "Groq / GPT-OSS + Hybrid Failover",
    "tool_active": False,
    "last_tool": "Command Processor",
    "tools": 0,
    "t_rec": 0.4,
    "t_think": 0.3,
    "facts": 12,
    "mail_age": 15,
    "chat": [
        {
            "i": 1,
            "k": "sys",
            "x": "Jarvis Mark VII System Online. Voice visualizer & neural pipeline armed.",
            "t": datetime.datetime.now().strftime("%H:%M:%S"),
        }
    ],
    "pending_confirmation": None,
    "sys": {"cpu": 12, "ram": 42, "disk": 58, "free": 120, "up": 7200},
    "stocks": [],
    "cards": [],
    "mic": {"n": 0, "a": [0.1, 0.2, 0.15, 0.05]},
}

_chat_counter = 1
_mic_counter = 0


def add_chat(role, text):
    """Adds a message to the shared telemetry chat log."""
    global _chat_counter
    with _lock:
        _chat_counter += 1
        msg = {
            "i": _chat_counter,
            "k": role,  # "you", "jarvis", "sys"
            "x": text,
            "t": datetime.datetime.now().strftime("%H:%M:%S"),
        }
        _state["chat"].append(msg)
        if len(_state["chat"]) > 100:
            _state["chat"] = _state["chat"][-100:]
        if role == "you":
            _state["last_you"] = text
        elif role == "jarvis":
            _state["last_jarvis"] = text
        return msg


def set_hud_state(st, note=None):
    """Updates the primary HUD state indicator."""
    with _lock:
        _state["state"] = st
        if note:
            _state["note"] = note
        _state["sleeping"] = jarvis_brain.is_sleeping()
        _state["mode"] = jarvis_brain.get_mode()
        _state["pending_confirmation"] = jarvis_brain.get_pending_confirmation()


def set_voice_enabled(enabled):
    """Updates the voice enabled state in server telemetry."""
    with _lock:
        _state["voice_enabled"] = bool(enabled)


def is_voice_enabled():
    """Checks whether voice speech is enabled."""
    with _lock:
        return _state.get("voice_enabled", True)


def speak_response(text):
    """Speaks output aloud if voice output is enabled."""
    if not text or not is_voice_enabled():
        return
    try:
        import jarvis_voice
        jarvis_voice.speak(text, block=False)
    except Exception as e:
        print(f"[Voice speech notice: {e}]")


def push_mic_level(level):
    """Pushes an audio energy sample for oscilloscope visualizer."""
    global _mic_counter
    with _lock:
        _mic_counter += 1
        _state["mic"]["n"] = _mic_counter
        _state["mic"]["a"].append(round(level, 3))
        if len(_state["mic"]["a"]) > 40:
            _state["mic"]["a"] = _state["mic"]["a"][-40:]


def _refresh_system_vitals():
    """Polls real CPU, RAM, Disk, Battery, and Network metrics via psutil."""
    try:
        cpu = psutil.cpu_percent(interval=None)
        ram = psutil.virtual_memory()
        disk = psutil.disk_usage("/" if sys.platform != "win32" else "C:\\")
        boot = psutil.boot_time()
        uptime = int(time.time() - boot)

        vitals = {
            "cpu": round(cpu, 1),
            "ram": round(ram.percent, 1),
            "ram_used": round(ram.used / (1024**3), 1),
            "ram_total": round(ram.total / (1024**3), 1),
            "disk": round(disk.percent, 1),
            "free": round(disk.free / (1024**3), 1),
            "disk_total": round(disk.total / (1024**3), 1),
            "up": uptime,
        }

        # Battery
        try:
            bat = psutil.sensors_battery()
            if bat:
                vitals["bat"] = round(bat.percent, 0)
                vitals["plug"] = bat.power_plugged
        except Exception:
            pass

        # Network I/O rates (compare with previous sample)
        try:
            net = psutil.net_io_counters()
            prev = _state.get("_net_prev")
            prev_t = _state.get("_net_prev_t", time.time())
            now_t = time.time()
            if prev and (now_t - prev_t) > 0:
                dt = now_t - prev_t
                vitals["net_up"] = round((net.bytes_sent - prev.bytes_sent) / dt / 1024, 1)   # KB/s
                vitals["net_dn"] = round((net.bytes_recv - prev.bytes_recv) / dt / 1024, 1)   # KB/s
            with _lock:
                _state["_net_prev"] = net
                _state["_net_prev_t"] = now_t
        except Exception:
            pass

        # Per-core CPU (up to 4 cores shown)
        try:
            per_core = psutil.cpu_percent(percpu=True)
            vitals["cores"] = [round(c, 0) for c in per_core[:4]]
        except Exception:
            pass

        with _lock:
            _state["sys"] = vitals
    except Exception:
        pass


def _fetch_weather():
    """Fetches current weather from wttr.in (no API key needed)."""
    try:
        url = "https://wttr.in/?format=%C+%t+%h+Humidity&m"
        req = urllib.request.Request(url, headers={"User-Agent": "Jarvis/1.0"})
        with urllib.request.urlopen(req, timeout=4) as r:
            return r.read().decode("utf-8").strip()
    except Exception:
        return None


def _fetch_top_news():
    """Fetches top story from HackerNews (no API key needed)."""
    try:
        with urllib.request.urlopen("https://hacker-news.firebaseio.com/v0/topstories.json", timeout=4) as r:
            ids = json.loads(r.read().decode())[:1]
        if ids:
            with urllib.request.urlopen(f"https://hacker-news.firebaseio.com/v0/item/{ids[0]}.json", timeout=4) as r:
                item = json.loads(r.read().decode())
                return item.get("title", "")
    except Exception:
        return None


def _refresh_stocks_and_briefings():
    """Fetches real market quotes and live briefing cards for the HUD."""
    try:
        # --- Live Market Data ---
        quotes = []
        for sym, name in list(jarvis_market.DEFAULT_TICKERS.items())[:6]:
            q = jarvis_market.analyze_ticker(sym)
            if q:
                # Derive momentum and trend from available fields
                pct = q["pct_change"]
                sig = q.get("signal", "HOLD")
                above = pct >= 0 and "BUY" in sig
                mom5 = round(pct * 1.4, 2)  # approximate 5-day momentum from daily pct
                quotes.append(
                    {
                        "sym": sym.replace(".NS", "").replace("^", ""),
                        "name": name,
                        "price": q["price"],
                        "pct": pct,
                        "mom": mom5,
                        "above": above,
                        "spark": [round(q["price"] * (1 + (i - 3) * 0.004), 2) for i in range(7)],
                        "stale": False,
                    }
                )
        if quotes:
            with _lock:
                _state["stocks"] = quotes
    except Exception as e:
        print(f"[Market refresh error: {e}]")

    # --- Live Briefing Cards (always generate, independent of market) ---
    try:
        _generate_briefing_cards()
    except Exception as e:
        print(f"[Briefings error: {e}]")


def _generate_briefing_cards():
    """Builds live executive briefing cards from local system + external APIs."""
    cards = []
    now_str = datetime.datetime.now().strftime("%H:%M")
    cnt = getattr(_generate_briefing_cards, "_cnt", 0) + 1
    _generate_briefing_cards._cnt = cnt

    # Card 1: System Status (always available)
    with _lock:
        sys_v = _state.get("sys", {})
        tools_run = _state.get("tools", 0)
        last_cmd = _state.get("last_tool", "None")

    cpu_v = sys_v.get("cpu", 0)
    ram_v = sys_v.get("ram", 0)
    disk_free = sys_v.get("free", "?")
    status_lbl = "[OK]" if cpu_v < 70 and ram_v < 80 else "[WARN]" if cpu_v < 90 else "[HIGH]"
    cards.append({
        "i": cnt * 10 + 1,
        "title": status_lbl + " SYSTEM STATUS",
        "t": now_str,
        "body": (
            f"CPU {cpu_v}%  |  RAM {ram_v}%  |  Disk free {disk_free} GB  |  "
            f"{tools_run} commands run.  Last: {last_cmd}"
        ),
    })

    # Card 2: Battery / Power status (if battery sensor available)
    bat_v = sys_v.get("bat")
    plug_v = sys_v.get("plug", True)
    if bat_v is not None:
        if bat_v < 20 and not plug_v:
            cards.append({
                "i": cnt * 10 + 2,
                "title": "[!!] BATTERY ALERT",
                "t": now_str,
                "body": f"Battery critically low at {int(bat_v)}%. Please connect charger immediately, sir.",
            })
        else:
            plug_icon = "[CHARGING]" if plug_v else "[ON BATTERY]"
            cards.append({
                "i": cnt * 10 + 2,
                "title": "POWER STATUS",
                "t": now_str,
                "body": f"{plug_icon}  {int(bat_v)}% remaining.",
            })

    # Card 3: Network I/O
    net_up = sys_v.get("net_up")
    net_dn = sys_v.get("net_dn")
    if net_up is not None:
        cards.append({
            "i": cnt * 10 + 3,
            "title": "NETWORK I/O",
            "t": now_str,
            "body": f"Upload {net_up} KB/s  |  Download {net_dn} KB/s",
        })

    # Card 4: Live Weather
    weather = _fetch_weather()
    if weather:
        cards.append({
            "i": cnt * 10 + 4,
            "title": "WEATHER REPORT",
            "t": now_str,
            "body": weather,
        })

    # Card 5: Top Tech News from HackerNews
    news = _fetch_top_news()
    if news:
        # Strip non-ASCII to be safe on all platforms
        news_safe = news.encode("ascii", "replace").decode("ascii")
        cards.append({
            "i": cnt * 10 + 5,
            "title": "TOP TECH NEWS",
            "t": now_str,
            "body": news_safe,
        })

    # Card 6: Market Mood Summary (only when stock data available)
    with _lock:
        stocks_snap = _state.get("stocks", [])
    if stocks_snap:
        bulls = sum(1 for s in stocks_snap if s.get("pct", 0) >= 0)
        bears = len(stocks_snap) - bulls
        mood = "BULLISH" if bulls > bears else "BEARISH" if bears > bulls else "NEUTRAL"
        best = max(stocks_snap, key=lambda s: s.get("pct", 0))
        worst = min(stocks_snap, key=lambda s: s.get("pct", 0))
        cards.append({
            "i": cnt * 10 + 6,
            "title": f"MARKET MOOD: {mood}",
            "t": now_str,
            "body": (
                f"Best: {best['name']} +{best['pct']:.2f}%  |  "
                f"Worst: {worst['name']} {worst['pct']:.2f}%"
            ),
        })

    with _lock:
        _state["cards"] = cards


class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = (sys.platform != "win32")


class JarvisAPIHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        # Silence routine request logging
        return

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        parsed_path = self.path.split("?")[0]

        # 1. State Endpoint
        if parsed_path == "/api/state":
            _refresh_system_vitals()
            with _lock:
                _state["sleeping"] = jarvis_brain.is_sleeping()
                _state["mode"] = jarvis_brain.get_mode()
                _state["pending_confirmation"] = jarvis_brain.get_pending_confirmation()
                data = json.dumps(_state)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data.encode("utf-8"))
            return

        # 2. Serve HUD HTML page
        if parsed_path in ("/", "/index.html", "/jarvis_workplace.html"):
            html_file = os.path.join(os.path.dirname(__file__), "jarvis_workplace.html")
            if os.path.exists(html_file):
                with open(html_file, "rb") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
                return

        return super().do_GET()

    def do_POST(self):
        parsed_path = self.path.split("?")[0]
        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len).decode("utf-8") if content_len > 0 else "{}"
        try:
            req_data = json.loads(body)
        except Exception:
            req_data = {}

        # 1. Command Input Endpoint (Text/Voice from HUD)
        if parsed_path == "/api/command":
            query = req_data.get("query", "").strip()
            if not query:
                self._send_json({"error": "Empty query"}, 400)
                return

            add_chat("you", query)
            set_hud_state("thinking", f"PROCESSING: {query[:30]}")

            t0 = time.time()
            response = jarvis_brain.think(query)
            t_think = time.time() - t0

            with _lock:
                _state["t_think"] = round(t_think, 2)
                _state["tools"] += 1
                _state["last_tool"] = query[:25]

            if response:
                add_chat("jarvis", response)
                set_hud_state("speaking", "JARVIS RESPONDING")
                speak_response(response)
            else:
                set_hud_state("listening", "SYSTEM READY")

            pending = jarvis_brain.get_pending_confirmation()
            self._send_json(
                {
                    "response": response or "",
                    "mode": jarvis_brain.get_mode(),
                    "sleeping": jarvis_brain.is_sleeping(),
                    "pending_confirmation": pending,
                    "voice_enabled": is_voice_enabled(),
                }
            )
            return

        # 2. Confirmation Action Endpoint
        if parsed_path == "/api/confirm":
            approved = bool(req_data.get("approved", False))
            add_chat("you", "Confirmed" if approved else "Cancelled")
            set_hud_state("thinking", "EXECUTING AUTHORIZED TASK" if approved else "ABORTING TASK")

            response = jarvis_brain.resolve_confirmation(approved)
            add_chat("jarvis", response)
            set_hud_state("speaking", "JARVIS RESPONDING")
            speak_response(response)

            self._send_json({"response": response, "approved": approved, "voice_enabled": is_voice_enabled()})
            return

        # 3. Toggle Standby / Wake Mode Endpoint
        if parsed_path == "/api/toggle_sleep":
            sleeping, msg = jarvis_brain.toggle_sleep()
            add_chat("sys", msg)
            set_hud_state("standby" if sleeping else "listening", msg)
            speak_response(msg)
            self._send_json(
                {
                    "sleeping": sleeping,
                    "mode": jarvis_brain.get_mode(),
                    "response": msg,
                    "voice_enabled": is_voice_enabled(),
                }
            )
            return

        # 4. Toggle Voice Output Endpoint
        if parsed_path == "/api/toggle_voice":
            try:
                import jarvis_voice
                new_state = jarvis_voice.toggle_voice()
            except Exception:
                new_state = not is_voice_enabled()
                set_voice_enabled(new_state)

            msg = "Voice output enabled, sir." if new_state else "Voice output muted."
            add_chat("sys", msg)
            if new_state:
                speak_response(msg)
            self._send_json(
                {
                    "voice_enabled": new_state,
                    "message": msg,
                    "response": msg,
                }
            )
            return

        self._send_json({"error": "Not Found"}, 404)

    def _send_json(self, data, code=200):
        content = json.dumps(data).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)


_server_instance = None
_server_thread = None


# Background refresh intervals
_VITALS_INTERVAL = 5       # seconds – hardware vitals
_STOCKS_INTERVAL = 45      # seconds – market data
_BRIEFINGS_INTERVAL = 90   # seconds – briefing cards


def _background_refresh_loop():
    """Continuously refreshes vitals, stocks, and briefings in the background."""
    last_stocks = 0
    last_briefings = 0
    while True:
        try:
            _refresh_system_vitals()
            now = time.time()
            # Refresh briefing cards every 30s (system status, battery, network)
            if now - last_briefings >= 30:
                last_briefings = now
                _generate_briefing_cards()
            # Refresh market data every 45s (network calls)
            if now - last_stocks >= _STOCKS_INTERVAL:
                last_stocks = now
                threading.Thread(target=_refresh_stocks_and_briefings, daemon=True).start()
        except Exception:
            pass
        time.sleep(_VITALS_INTERVAL)


def start_server(host=HOST, port=PORT, background=True):
    """Starts the HUD API and Web server."""
    global _server_instance, _server_thread
    if _server_instance is not None:
        return _server_instance

    # Initial data load — run vitals and briefings synchronously so panels
    # are populated the moment the first browser request arrives
    _refresh_system_vitals()
    _generate_briefing_cards()
    # Market data fetch runs in background (network call, may take a few seconds)
    threading.Thread(target=_refresh_stocks_and_briefings, daemon=True).start()

    # Find free port if 8765 is taken
    active_port = port
    for p in range(port, port + 10):
        try:
            _server_instance = ThreadedHTTPServer((host, p), JarvisAPIHandler)
            active_port = p
            break
        except OSError:
            continue

    if _server_instance is None:
        raise RuntimeError(f"Could not bind server to {host}:{port}")

    print(f"\n[HUD Web Server Online]: http://{host}:{active_port}")

    # Start continuous background refresh daemon
    _bg_thread = threading.Thread(target=_background_refresh_loop, daemon=True, name="JarvisRefresh")
    _bg_thread.start()

    if background:
        _server_thread = threading.Thread(target=_server_instance.serve_forever, daemon=True)
        _server_thread.start()
        return _server_instance
    else:
        _server_instance.serve_forever()


if __name__ == "__main__":
    start_server(background=False)
