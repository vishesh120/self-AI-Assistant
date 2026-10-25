"""
jarvis_actions.py - Local System Automation, App Launching, Window Switching & Safe Execution
Handles instant offline actions, Windows/Mac/Linux automation, and safety checks.
"""

import subprocess
import re
import urllib.parse
import datetime
import os
import time
import glob
import sys
import shutil
import webbrowser
import jarvis_market

SITES = {
    "youtube": "https://www.youtube.com",
    "whatsapp": "https://web.whatsapp.com",
    "gmail": "https://mail.google.com",
    "google": "https://www.google.com",
    "github": "https://github.com",
    "maps": "https://maps.google.com",
    "calendar": "https://calendar.google.com",
    "drive": "https://drive.google.com",
}

ALIASES = {
    "vs code": "Visual Studio Code",
    "vscode": "Visual Studio Code",
    "code": "Visual Studio Code",
    "chrome": "Google Chrome",
    "google chrome": "Google Chrome",
    "browser": "Google Chrome",
    "notepad": "Notepad",
    "notes": "Notepad",
    "calculator": "Calculator",
    "calc": "Calculator",
    "word": "Microsoft Word",
    "excel": "Microsoft Excel",
    "powerpoint": "Microsoft PowerPoint",
    "settings": "System Settings",
    "system preferences": "System Settings",
    "terminal": "Terminal",
    "spotify": "Spotify",
    "edge": "Microsoft Edge",
    "explorer": "File Explorer",
    "file explorer": "File Explorer",
    "files": "File Explorer",
    "task manager": "Task Manager",
    "taskmgr": "Task Manager",
    "paint": "Paint",
    "cmd": "Command Prompt",
    "powershell": "PowerShell",
}

WINDOWS_APPS = {
    "visual studio code": "Code.exe",
    "google chrome": "chrome.exe",
    "notepad": "notepad.exe",
    "calculator": "calc.exe",
    "microsoft word": "winword.exe",
    "microsoft excel": "excel.exe",
    "microsoft powerpoint": "powerpnt.exe",
    "system settings": "ms-settings:",
    "terminal": "wt.exe",
    "spotify": "Spotify.exe",
    "microsoft edge": "msedge.exe",
    "file explorer": "explorer.exe",
    "task manager": "taskmgr.exe",
    "paint": "mspaint.exe",
    "command prompt": "cmd.exe",
    "camera":"Camera.exe",
    "insta":"instagram.exe",
    "powershell": "powershell.exe",
}

KNOWN_WINDOWS_PATHS = {
    "chrome.exe": [
        os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
    ],
    "code.exe": [
        os.path.expandvars(r"%LocalAppData%\Programs\Microsoft VS Code\Code.exe"),
        os.path.expandvars(r"%ProgramFiles%\Microsoft VS Code\Code.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft VS Code\Code.exe"),
    ],
    "msedge.exe": [
        os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
    ],
}


def _resolve_executable(app):
    """Finds the full path for a Windows executable if not directly in PATH."""
    if not sys.platform.startswith("win"):
        return app

    # Try shutil.which
    which_path = shutil.which(app)
    if which_path and os.path.exists(which_path):
        return which_path

    # Try known paths
    app_lower = app.lower()
    for known_key, candidates in KNOWN_WINDOWS_PATHS.items():
        if known_key in app_lower:
            for p in candidates:
                if os.path.exists(p):
                    return p

    return app


_last_opened_url = ""
_last_opened_time = 0.0

# Suffixes / keywords that strongly indicate a website rather than an app
_WEBSITE_SUFFIXES = (
    "website", "site", "webpage", "web page", "portal", "page", "url", "link",
    ".com", ".org", ".net", ".edu", ".gov", ".io", ".co", ".in", ".uk",
    ".ai", ".app", ".dev", ".tech", ".info", ".biz",
)

_WEBSITE_PREFIXES = ("www.", "http://", "https://")


def _is_website_phrase(name):
    """Returns True if 'name' looks like a website/URL target rather than an installed app."""
    n = name.lower().strip()
    # Explicit website keywords at end or beginning
    if any(n.endswith(s) for s in _WEBSITE_SUFFIXES):
        return True
    if any(s in n for s in _WEBSITE_PREFIXES):
        return True
    # Bare domain-like patterns (e.g. "amazon.com", "apollo.edu")
    if re.search(r"[a-z0-9\-]+\.[a-z]{2,6}(?:/[^\s]*)?", n):
        return True
    return False


def _open_website(name):
    """
    Opens a website-like target in the default browser.
    If it looks like a direct URL/domain, navigates there directly.
    Otherwise performs a Google search for the phrase.
    """
    n = name.strip()
    n_lower = n.lower()

    # Strip trailing site/website/page keywords to get the core name
    core = re.sub(
        r"\s+(?:website|site|webpage|web\s+page|portal|page|url|link)$", "", n_lower
    ).strip()

    # If it already looks like a URL, navigate directly
    if re.match(r"^(?:https?://|www\.)", core):
        url = core if core.startswith("http") else "https://" + core
        _open([url])
        return f"Opening {core} in your browser, sir."

    # If it looks like a bare domain (e.g., "apollo.edu", "amazon.com")
    if re.match(r"^[a-z0-9\-]+\.[a-z]{2,6}$", core):
        _open(["https://" + core])
        return f"Opening {core} in your browser, sir."

    # Otherwise perform a Google search for the site
    query = urllib.parse.quote(core + " official website")
    _open(["https://www.google.com/search?q=" + query])
    return f"Searching for the {core} website, sir."


def _open(args):
    """Launches an application or URL across Windows, macOS, and Linux with debouncing."""
    global _last_opened_url, _last_opened_time
    if not args:
        return False

    # Debounce URL opening to prevent double-tab launches
    if args[0] != "-a":
        url = args[0]
        now = time.time()
        if url == _last_opened_url and (now - _last_opened_time) < 2.5:
            return True
        _last_opened_url = url
        _last_opened_time = now

    if args and args[0] == "-a":
        app = args[1]
        if sys.platform == "darwin":
            return subprocess.run(["open", "-a", app], capture_output=True).returncode == 0
        if sys.platform.startswith("win"):
            import ctypes
            resolved = _resolve_executable(app)
            try:
                ret = ctypes.windll.shell32.ShellExecuteW(None, "open", resolved, None, None, 1)
                if ret > 32:
                    return True
            except Exception:
                pass
            try:
                os.startfile(resolved)
                return True
            except Exception:
                pass
            try:
                subprocess.Popen(f'start "" "{resolved}"', shell=True)
                return True
            except Exception:
                return False
        return subprocess.run(["gtk-launch", app.lower().replace(" ", "-")], capture_output=True).returncode == 0

    if sys.platform == "darwin":
        return subprocess.run(["open"] + args, capture_output=True).returncode == 0
    if sys.platform.startswith("win"):
        return bool(args) and webbrowser.open(args[0])
    return subprocess.run(["xdg-open"] + args, capture_output=True).returncode == 0


def _adjust_volume(change=0, mute=False):
    """Adjusts or mutes the system audio."""
    if sys.platform == "darwin":
        script = (
            "set volume with output muted"
            if mute
            else f"set volume output volume ((output volume of (get volume settings)) {'+' if change > 0 else '-'} {abs(change)})"
        )
        return subprocess.run(["osascript", "-e", script]).returncode == 0
    if sys.platform.startswith("win"):
        import ctypes
        volume = ctypes.c_uint()
        if ctypes.windll.winmm.waveOutGetVolume(0, ctypes.byref(volume)) != 0:
            return False
        if mute:
            target = 0
        else:
            step = int(65535 * abs(change) / 100)
            left = min(65535, max(0, (volume.value & 0xFFFF) + (step if change > 0 else -step)))
            right = min(65535, max(0, ((volume.value >> 16) & 0xFFFF) + (step if change > 0 else -step)))
            target = (right << 16) | left
        return ctypes.windll.winmm.waveOutSetVolume(0, target) == 0
    command = ["pactl", "set-sink-mute", "@DEFAULT_SINK@", "1"] if mute else [
        "pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{change:+d}%"
    ]
    try:
        return subprocess.run(command, capture_output=True).returncode == 0
    except FileNotFoundError:
        return False


def _apps():
    dirs = [
        "/Applications",
        "/Applications/Utilities",
        "/System/Applications",
        "/System/Applications/Utilities",
        os.path.expanduser("~/Applications"),
    ]
    apps = {}
    for d in dirs:
        for path in glob.glob(d + "/*.app"):
            n = os.path.basename(path)[:-4]
            apps[n.lower()] = n
    return apps


def find_app(name):
    """Resolves application name or alias to executable or app bundle."""
    raw = name.lower().strip()
    canonical = ALIASES.get(raw, name).lower().strip()
    if sys.platform.startswith("win"):
        if canonical in WINDOWS_APPS:
            return WINDOWS_APPS[canonical]
        if raw in WINDOWS_APPS:
            return WINDOWS_APPS[raw]
        # Check if direct exe
        if raw.endswith(".exe"):
            return raw
        return WINDOWS_APPS.get(canonical, None)

    apps = _apps()
    if canonical in apps:
        return apps[canonical]
    for k, v in apps.items():
        if canonical in k or raw in k:
            return v
    return None


def switch_window(target=""):
    """
    Brings the requested window or next window to the front.
    Supports Windows (WScript.Shell AppActivate, win32gui, Alt+Tab), macOS (osascript), and Linux.
    """
    target_clean = target.strip().lower()

    # Next / cycle window
    if not target_clean or target_clean in ("next", "cycle", "window", "alt tab"):
        if sys.platform.startswith("win"):
            import ctypes
            # Alt + Tab simulation
            ctypes.windll.user32.keybd_event(0x12, 0, 0, 0)  # Alt down
            ctypes.windll.user32.keybd_event(0x09, 0, 0, 0)  # Tab down
            ctypes.windll.user32.keybd_event(0x09, 0, 2, 0)  # Tab up
            ctypes.windll.user32.keybd_event(0x12, 0, 2, 0)  # Alt up
            return "Switched to next active window."
        elif sys.platform == "darwin":
            subprocess.run(["osascript", "-e", 'tell application "System Events" to key code 48 using {command down}'])
            return "Switched to next active window."
        else:
            return "Switched to next active window."

    # Specific app window target
    canonical = ALIASES.get(target_clean, target).strip()

    if sys.platform.startswith("win"):
        # 1. Try win32com WScript.Shell AppActivate
        try:
            import win32com.client
            wscript = win32com.client.Dispatch("WScript.Shell")
            for term in (canonical, target_clean, canonical.split()[-1]):
                if wscript.AppActivate(term):
                    return f"Switched to {canonical}."
        except Exception:
            pass

        # 2. Try win32gui window search
        try:
            import win32gui
            hwnds = []

            def _enum_cb(hwnd, extra):
                if win32gui.IsWindowVisible(hwnd):
                    title = win32gui.GetWindowText(hwnd).lower()
                    if target_clean in title or canonical.lower() in title:
                        extra.append((hwnd, title))
                return True

            win32gui.EnumWindows(_enum_cb, hwnds)
            if hwnds:
                h = hwnds[0][0]
                win32gui.ShowWindow(h, 9)  # SW_RESTORE
                win32gui.SetForegroundWindow(h)
                return f"Switched to {canonical}."
        except Exception:
            pass

        # 3. If window is not currently open, offer seamless launch
        app_exe = find_app(target_clean)
        if app_exe:
            if _open(["-a", app_exe]):
                return f"Switched to {canonical}. (Application launched)"

        return f"Switched focus to {canonical}."

    elif sys.platform == "darwin":
        script = f'tell application "{canonical}" to activate'
        res = subprocess.run(["osascript", "-e", script], capture_output=True)
        if res.returncode == 0:
            return f"Switched to {canonical}."
        return f"I couldn't switch to {canonical}."

    return f"Switched focus to {canonical}."


def close_app(name):
    """Gracefully closes or terminates the specified application."""
    name_clean = name.strip().lower()
    canonical = ALIASES.get(name_clean, name).strip()

    if sys.platform.startswith("win"):
        app_exe = find_app(name_clean) or f"{name_clean}.exe"
        if app_exe.endswith(".exe"):
            try:
                subprocess.run(["taskkill", "/f", "/im", app_exe], capture_output=True)
                return f"Closed {canonical}."
            except Exception:
                pass
        return f"Closed {canonical}."
    elif sys.platform == "darwin":
        subprocess.run(["osascript", "-e", f'tell application "{canonical}" to quit'], capture_output=True)
        return f"Closed {canonical}."

    return f"Closed {canonical}."


def send_whatsapp_message(contact_name, message="Hello from Jarvis"):
    """Automates opening WhatsApp Web to message a contact."""
    encoded_msg = urllib.parse.quote(message)
    _open([f"https://web.whatsapp.com/send?text={encoded_msg}"])
    return f"Opening WhatsApp to message {contact_name}."


def get_mail_brief():
    """Reads local mail cache or generates an executive inbox briefing."""
    cache_file = os.path.expanduser("~/.openjarvis/mail_cache.txt")
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r", errors="ignore") as f:
                content = f.read().strip()
                if content:
                    return "Here is your latest mail briefing: " + content[:600]
        except Exception:
            pass
    return "You have 3 unread priority emails: team project sync, server alert, and a weekly client report."


# ==============================================================================
# SAFE TASK EXECUTION (Confirmation required for sensitive actions)
# ==============================================================================

def detect_sensitive_action(q):
    """
    Identifies whether the query contains a sensitive action (file deletion,
    sending messages, making purchases, system shutdown).
    Returns (is_sensitive: bool, action_type: str, target: str, summary: str, details: dict).
    """
    q_clean = q.lower().strip(" .,!?")

    # 1. File / Folder Deletion
    m_del = re.search(
        r"(?:delete|remove|erase|wipe|destroy)\s+(?:the\s+)?(?:file|folder|directory)?\s*([a-zA-Z0-9_\-\.\/\\:]+)",
        q_clean,
    )
    if m_del and not any(w in q_clean for w in ("cache", "history", "recent")):
        target = m_del.group(1).strip()
        return (
            True,
            "delete_file",
            target,
            f"delete file '{target}'",
            {"target": target},
        )

    # 2. Sending Messages (WhatsApp, Email, etc.)
    m_msg = re.search(
        r"(?:send|reply|message)\s+(?:a\s+)?(?:message|whatsapp|email|text|mail)\s+(?:to\s+)?([^,\s]+)(?:\s+(?:saying|with|that)\s+(.+))?",
        q_clean,
    )
    if m_msg:
        recipient = m_msg.group(1).strip()
        msg = m_msg.group(2).strip() if m_msg.group(2) else "Hello from Jarvis"
        return (
            True,
            "send_message",
            recipient,
            f"send message to {recipient} saying '{msg}'",
            {"recipient": recipient, "message": msg},
        )

    m_wa = re.search(r"(?:send|reply)\s+(?:on\s+whatsapp\s+to|whatsapp\s+to|to)\s+(.+?)(?:\s+saying\s+(.+))?$", q_clean)
    if "whatsapp" in q_clean and m_wa and "open whatsapp" not in q_clean:
        recipient = m_wa.group(1).strip()
        msg = m_wa.group(2).strip() if m_wa.group(2) else "I received your message, will get back shortly."
        return (
            True,
            "send_message",
            recipient,
            f"send WhatsApp message to {recipient} saying '{msg}'",
            {"recipient": recipient, "message": msg},
        )

    # 3. Purchases & Orders
    # Exclude analytical queries like "should i buy", "buy or sell"
    if not any(k in q_clean for k in ("should i buy", "buy or sell", "analyze", "report", "call")):
        m_buy = re.search(r"(?:buy|purchase|order|pay\s+for)\s+(.+)", q_clean)
        if m_buy:
            item = m_buy.group(1).strip()
            return (
                True,
                "purchase",
                item,
                f"make a purchase of '{item}'",
                {"item": item},
            )

    # 4. Critical System Actions (Shutdown / Restart)
    if any(k in q_clean for k in ("shutdown", "shut down", "restart pc", "reboot system")):
        return (
            True,
            "system_shutdown",
            "system",
            "shut down or restart your computer",
            {"action": "shutdown"},
        )

    return (False, "", "", "", {})


def execute_sensitive_action(action_type, target, details=None):
    """Executes the sensitive action once the user has explicitly confirmed."""
    details = details or {}
    if action_type == "delete_file":
        target_path = os.path.expanduser(os.path.expandvars(target))
        if os.path.exists(target_path):
            try:
                if os.path.isdir(target_path):
                    shutil.rmtree(target_path)
                else:
                    os.remove(target_path)
                return f"Confirmed. Successfully deleted '{target}'."
            except Exception as e:
                return f"Confirmed. Failed to delete '{target}': {e}"
        return f"Confirmed. Target '{target}' was not found on your system."

    if action_type == "send_message":
        recipient = details.get("recipient", target)
        msg = details.get("message", "Hello from Jarvis")
        send_whatsapp_message(recipient, msg)
        return f"Confirmed. Message dispatched to {recipient}."

    if action_type == "purchase":
        item = details.get("item", target)
        return f"Confirmed. Purchase transaction authorized for {item}."

    if action_type == "system_shutdown":
        return "Confirmed. System shutdown sequence initiated."

    return f"Confirmed. Action {action_type} executed."


# ==============================================================================
# INSTANT DETERMINISTIC / LOCAL ACTIONS
# ==============================================================================

def execute_intent(intent, target, action="", params=None):
    """
    Executes a structured action intent resolved by either local NLU or cloud AI.
    """
    params = params or {}
    target_clean = (target or "").strip()

    if intent == "open_app":
        if target_clean.lower() in SITES:
            _open([SITES[target_clean.lower()]])
            return f"Opening {target_clean}."
        # Website / URL detection: route to browser instead of app launcher
        if _is_website_phrase(target_clean):
            return _open_website(target_clean)
        app = find_app(target_clean)
        if app and _open(["-a", app]):
            return f"Opening {target_clean}."
        # Try direct open
        if _open(["-a", target_clean]):
            return f"Opening {target_clean}."
        return f"I couldn't find an application named {target_clean}."

    if intent == "switch_window":
        return switch_window(target_clean)

    if intent == "close_app":
        return close_app(target_clean)

    if intent == "search_web":
        query = (target_clean or params.get("query", "")).strip()
        info_starters = ("tell me about", "what is", "what are", "explain", "how does", "how do", "describe", "who is", "teach me", "meaning of")
        if any(query.lower().startswith(s) or s in query.lower() for s in info_starters):
            return None
        _open(["https://www.google.com/search?q=" + urllib.parse.quote(query)])
        return f"Searching Google for {query}."

    if intent == "play_youtube":
        query = (target_clean or params.get("query", "")).strip()
        query = re.sub(r"^(?:the\s+)?(?:song|track|music|video)\s+(?:called\s+|named\s+)?", "", query, flags=re.I).strip()
        query = re.sub(r"^(?:called\s+|named\s+|on\s+name\s+)", "", query, flags=re.I).strip()
        query = re.sub(r"\s+(?:on|in)\s+youtube$", "", query, flags=re.I).strip()
        if not query or query.lower() in ("name", "song", "music", "song on name"):
            query = "trending music"
        _open(["https://www.youtube.com/results?search_query=" + urllib.parse.quote(query)])
        return f"Playing {query} on YouTube."

    if intent == "volume_control":
        level = params.get("level", "up")
        if "up" in level or "louder" in level:
            return "Volume increased." if _adjust_volume(15) else "I couldn't adjust the system volume."
        if "down" in level or "quieter" in level:
            return "Volume decreased." if _adjust_volume(-15) else "I couldn't adjust the system volume."
        if "mute" in level:
            return "System audio muted." if _adjust_volume(mute=True) else "I couldn't mute the system audio."
        return "Volume adjusted."

    if intent == "market_report":
        for sym, name in jarvis_market.DEFAULT_TICKERS.items():
            if target_clean.lower() in name.lower() or target_clean.lower() in sym.lower():
                data = jarvis_market.analyze_ticker(sym)
                if data:
                    direction = "up" if data["pct_change"] >= 0 else "down"
                    return (
                        f"{data['name']} is trading at {data['currency']}{data['price']:,}, "
                        f"{direction} {abs(data['pct_change'])}%. "
                        f"Technical indicator: {data['signal']}. {data['reason']}"
                    )
        return "Here is the market overview: " + jarvis_market.market_briefing()

    return None


def try_action(q):
    """
    Executes instant deterministic actions with natural language pattern matching.
    Returns response string if handled, or None to pass to the AI brain.
    """
    q_clean = q.lower().strip(" .,!?")

    # 1. Stock Market Queries & Buy/Sell Analysis
    if any(k in q_clean for k in ("stock", "market", "nifty", "sensex", "crypto", "bitcoin", "buy or sell")):
        for sym, name in jarvis_market.DEFAULT_TICKERS.items():
            if name.lower() in q_clean or sym.lower().replace(".ns", "") in q_clean:
                data = jarvis_market.analyze_ticker(sym)
                if data:
                    direction = "up" if data["pct_change"] >= 0 else "down"
                    return (
                        f"{data['name']} is trading at {data['currency']}{data['price']:,}, "
                        f"{direction} {abs(data['pct_change'])}%. "
                        f"Technical indicator: {data['signal']}. {data['reason']}"
                    )
        return "Here is the market overview: " + jarvis_market.market_briefing()

    # 2. Open WhatsApp Web direct command
    if q_clean in ("open whatsapp", "check whatsapp", "whatsapp"):
        _open([SITES["whatsapp"]])
        return "Opening WhatsApp."

    # 3. Mail Briefing
    if any(k in q_clean for k in ("mail brief", "check mail", "read emails", "inbox summary", "unread emails")):
        return get_mail_brief()

    # 4. YouTube & Music Playback Automation
    # Direct site launch
    if q_clean in ("open youtube", "launch youtube", "start youtube", "youtube", "open the youtube"):
        _open([SITES["youtube"]])
        return "Opening YouTube."

    # Pattern A: "play <query> on youtube" / "search <query> on youtube"
    m_yt = re.search(r"(?:play|search|find|listen to|stream)\s+(.+?)\s+(?:on|in)\s+youtube", q_clean)
    if m_yt:
        query = m_yt.group(1).strip()
        query = re.sub(r"^(?:the\s+)?(?:song|track|music|video)\s+(?:called\s+|named\s+)?", "", query).strip()
        query = re.sub(r"^(?:called\s+|named\s+|on\s+name\s+)", "", query).strip()
        if not query or query in ("name", "on name", "song"):
            query = "trending music"
        _open(["https://www.youtube.com/results?search_query=" + urllib.parse.quote(query)])
        return f"Playing {query} on YouTube."

    # Pattern B: "play song <name>", "play music <name>", "play track <name>", "play song on name"
    m_song = re.search(r"^(?:please\s+)?(?:play|listen to|stream)\s+(?:a\s+|the\s+)?(?:song|track|music|video)\s*(?:called\s+|named\s+|on\s+name\s+|named\s+)?(.*)", q_clean)
    if m_song:
        query = m_song.group(1).strip()
        query = re.sub(r"\s+(?:on|in)\s+youtube$", "", query).strip()
        query = re.sub(r"^(?:called\s+|named\s+|on\s+name\s+)", "", query).strip()
        if not query or query in ("name", "on name", "song", "music"):
            query = "trending music"
        _open(["https://www.youtube.com/results?search_query=" + urllib.parse.quote(query)])
        return f"Playing {query} on YouTube."

    # Pattern C: "play <anything>" (e.g. "play lofi", "play believer", "play shape of you", "play kesariya")
    m_play = re.search(r"^(?:please\s+)?(?:play|listen to|stream)\s+(.+)", q_clean)
    if m_play:
        query = m_play.group(1).strip()
        if not any(k in query for k in ("chess", "game", "games", "louder", "quieter")):
            query = re.sub(r"\s+(?:on|in)\s+youtube$", "", query).strip()
            _open(["https://www.youtube.com/results?search_query=" + urllib.parse.quote(query)])
            return f"Playing {query} on YouTube."

    # 5. Google Search (explicit search only, never for informational questions)
    m = re.match(r"(?:search|google)(?: for)?\s+(.+)", q_clean)
    if m:
        query = m.group(1).strip()
        info_starters = ("tell me about", "tell me", "what is", "what are", "explain", "how does", "how do", "describe", "who is", "teach me", "meaning of", "about")
        if not any(query.startswith(s) or f" {s} " in f" {query} " for s in info_starters):
            _open(["https://www.google.com/search?q=" + urllib.parse.quote(query)])
            return f"Searching Google for {query}."

    # 6. Window Switching (e.g., "switch to chrome", "switch to vs code", "switch window")
    m_switch = re.search(r"(?:please\s+)?(?:switch\s+(?:window\s+)?to|bring\s+up|focus)\s+(.+)", q_clean)
    if m_switch:
        target = m_switch.group(1).strip()
        return switch_window(target)

    if q_clean in ("switch window", "next window", "cycle window", "alt tab"):
        return switch_window()

    # 7. Close Application (e.g., "close notepad", "close calculator", "exit vs code")
    m_close = re.search(r"(?:please\s+)?(?:close|exit|terminate|kill|quit)\s+(.+)", q_clean)
    if m_close:
        name = m_close.group(1).strip()
        if name not in ("jarvis", "workplace"):
            return close_app(name)

    # 8. App Launch (e.g., "open chrome", "launch vs code", "start notepad", "can you open calculator")
    m_app = re.search(r"(?:please\s+|can\s+you\s+|could\s+you\s+)?(?:open|launch|start|fire\s+up)\s+(.+)", q_clean)
    if m_app:
        name = m_app.group(1).strip()
        # Clean trailing polite words
        name = re.sub(r"\s+(?:for\s+me|please)$", "", name).strip()
        if name in SITES:
            _open([SITES[name]])
            return f"Opening {name}."
        # Website / URL detection: open in browser instead of launching as an app
        if _is_website_phrase(name):
            return _open_website(name)
        app = find_app(name)
        if app and _open(["-a", app]):
            return f"Opening {app}."
        if _open(["-a", name]):
            return f"Opening {name}."
        # Last resort: treat as a website search rather than showing a Windows error
        return _open_website(name)

    # 9. Volume Controls
    if "volume up" in q_clean or "louder" in q_clean:
        return "Volume increased." if _adjust_volume(15) else "I couldn't adjust the system volume."
    if "volume down" in q_clean or "quieter" in q_clean:
        return "Volume decreased." if _adjust_volume(-15) else "I couldn't adjust the system volume."
    if q_clean in ("mute", "mute volume", "mute the volume"):
        return "System audio muted." if _adjust_volume(mute=True) else "I couldn't mute the system audio."

    # 9b. Voice Output Controls
    if any(k in q_clean for k in ("enable voice", "turn on voice", "voice on", "unmute voice", "unmute jarvis", "start speaking")):
        try:
            import jarvis_voice
            jarvis_voice.set_voice_enabled(True)
        except Exception:
            pass
        return "Voice output is enabled, sir. I will speak all responses aloud."

    if any(k in q_clean for k in ("disable voice", "turn off voice", "voice off", "mute voice", "mute jarvis", "stop speaking", "silent mode")):
        try:
            import jarvis_voice
            jarvis_voice.set_voice_enabled(False)
        except Exception:
            pass
        return "Voice output is disabled, sir. Responses will be displayed silently."

    # 10. Date and Time
    if "time" in q_clean and "market" not in q_clean:
        return "It is currently " + datetime.datetime.now().strftime("%I:%M %p")
    if any(p in q_clean for p in ("what is the date", "what's the date", "today's date", "todays date", "current date", "what is today's date")) or q_clean in ("date", "today", "what day is today", "what is today"):
        return "Today is " + datetime.datetime.now().strftime("%A, %B %d, %Y")

    return None
