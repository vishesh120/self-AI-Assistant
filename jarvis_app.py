"""
jarvis_app.py - Main Jarvis Executive Assistant Desktop Launcher
Launches the Futuristic HUD Desktop UI, starts the backend API,
and runs the voice recognition and automation engine.
"""

import os
import sys
import time
import webbrowser
import threading
import jarvis_server
import jarvis_voice


def main():
    print("\n" + "=" * 65)
    print("   JARVIS EXECUTIVE AI ASSISTANT - DESKTOP EDITION")
    print("=" * 65)
    print("  [+] Initializing Hybrid Cloud + Local Failover Brain...")
    print("  [+] Starting Futuristic Holographic HUD Web Server...")

    # 1. Start Background Server
    server = jarvis_server.start_server(host=jarvis_server.HOST, port=jarvis_server.PORT, background=True)
    server_url = f"http://{jarvis_server.HOST}:{jarvis_server.PORT}"

    # 2. Launch Desktop UI in Browser
    def _open_ui():
        time.sleep(0.8)
        print(f"  [+] Opening Holographic HUD Dashboard at: {server_url}")
        webbrowser.open(server_url)

    threading.Thread(target=_open_ui, daemon=True).start()

    print("\n" + "-" * 65)
    print("  ⚡ VOICE COMMANDS:")
    print("    - Wake up:        Say 'Open Jarvis'")
    print("    - Standby:        Say 'Sleep, Jarvis'")
    print("    - Open Apps:      'Open Chrome', 'Open VS Code', 'Open Calculator', 'Open Notepad'")
    print("    - Switch Windows: 'Switch to Chrome', 'Switch to VS Code', 'Switch window'")
    print("    - Safe Action:    'Delete file test.txt' (Requires confirmation)")
    print("    - Live Market:    'Stock market report', 'Analyze Nifty', 'Analyze Reliance'")
    # 3. Startup Voice Greeting
    jarvis_voice.speak("Good day, sir. Jarvis Mark VII online. Your personal assistant is armed and at your service.", block=False)

    print("    - Voice Controls: 'Enable voice', 'Disable voice', 'Mute voice'")
    print("-" * 65 + "\n")

    # 4. Enter Voice & Automation Loop
    jarvis_voice.listen_loop()


if __name__ == "__main__":
    main()
