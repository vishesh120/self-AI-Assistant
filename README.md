# ⚡ Jarvis AI Personal Assistant - Complete Setup

> **A real voice-controlled AI executive assistant for your computer.**
> Features voice activation, holographic Iron Man HUD with live oscilloscope & command input, Windows application automation & window switching, natural language AI command understanding, and safe task execution with confirmation dialogs.

---

## 🚀 Quick Start (In 60 Seconds)

### On Windows:
Double-click `run.bat` or run:
```cmd
run.bat
```
*(Runs installer on first launch, starts the HUD server, opens the dashboard, and boots the assistant).*

### On macOS / Linux:
```bash
chmod +x install.sh
./install.sh
source .venv/bin/activate && python jarvis_app.py
```

---

## 🎙️ Core Capabilities

### 1. 🎤 Voice Activation & Standby
- **Say "Open Jarvis"**: Activates Jarvis from standby. Jarvis greets you and starts listening.
- **Say "Sleep, Jarvis"**: Returns Jarvis to standby mode where it pauses listening for general commands until "Open Jarvis" is heard.
- **UI Toggle**: Click the glowing `ACTIVE` / `STANDBY` button in the header at any time.

### 2. 🖥️ Jarvis Desktop UI (Holographic HUD)
- **Live Voice Visualizer**: Multi-tier frequency oscilloscope that responds to microphone energy and voice.
- **Dynamic Status Indicator**: Displays `STANDBY`, `LISTENING`, `HEARING YOU`, `PROCESSING QUERY`, or `JARVIS RESPONDING` with animated HUD lighting.
- **Chat & Telemetry History**: Real-time logging of user commands, Jarvis responses, and system alerts.
- **Futuristic Command Input**: Transmit text commands directly via keyboard or click quick-action pills (`Chrome`, `VS Code`, `Notepad`, `Calc`, `Switch Chrome`, `Stocks`, `Sleep`, `Wake`).

### 3. ⚙️ Application Automation & Window Switching
- **Open Apps**: Launches Chrome, VS Code, Notepad, Calculator, Microsoft Edge, Spotify, Word, Excel, PowerPoint, File Explorer, Task Manager, Paint, and System Settings.
- **Switch Windows**: Say *"Switch to Chrome"*, *"Switch to VS Code"*, *"Switch to Notepad"*, or *"Switch window"* to cycle through active windows.
- **Close Apps**: Say *"Close Notepad"*, *"Close Calculator"*, etc.
- **System Controls**: Hands-free volume adjustment (*"Volume up"*, *"Mute"*), date and time queries.

### 4. 🧠 AI Command Understanding
- Uses your existing **Groq AI API** (`openai/gpt-oss-20b`, `qwen/qwen3.8-27b`) to understand complex natural language requests instead of relying only on rigid regex phrases.
- Seamlessly extracts user intents, targets, and parameters.
- **Hybrid Failover**: Automatically switches to the local deterministic engine if the API is cooling down or offline.

### 5. 🛡️ Safe Task Execution (Confirmation Dialogs)
- **Sensitive Action Interception**: Automatically detects sensitive tasks:
  - Deleting files or folders (*"delete file notes.txt"*)
  - Sending messages or emails (*"send WhatsApp to Alex saying..."*)
  - Making purchases or financial transactions (*"buy 5 shares of Tesla"*)
  - System shutdowns (*"shut down computer"*)
- **Dual Confirmation**:
  - **By Voice**: Prompts *"Security confirmation required: Do you wish to proceed? Say 'yes' or 'no'"*.
  - **By UI**: Holographic security authorization modal lights up with glowing **Confirm** and **Cancel** buttons.
  - Action only executes upon verified confirmation!

---

## 🎙️ Voice Commands Cheat-Sheet

| What You Say | What Jarvis Does | Safety Check |
| :--- | :--- | :--- |
| `"Open Jarvis"` | Wakes assistant from standby | None |
| `"Sleep, Jarvis"` | Enters standby sleep mode | None |
| `"Open Chrome"` | Launches Google Chrome | None |
| `"Open VS Code"` | Launches Visual Studio Code | None |
| `"Open Notepad"` | Launches Notepad editor | None |
| `"Open Calculator"` | Launches Calculator | None |
| `"Switch to Chrome"` | Brings Chrome window to the front | None |
| `"Switch window"` | Cycles to next active window (Alt+Tab) | None |
| `"Delete file old_logs.txt"` | Halts and asks for confirmation | ⚠️ **Requires Confirmation** |
| `"Send WhatsApp to Sarah saying I'm on my way"` | Prompts before dispatching | ⚠️ **Requires Confirmation** |
| `"Buy 10 shares of Apple"` | Requests confirmation before placing order | ⚠️ **Requires Confirmation** |
| `"Play lofi on YouTube"` | Opens YouTube music | None |
| `"Stock market report"` | Live Nifty, Sensex, Reliance, Nvidia & crypto analysis | None |
| `"Enable voice" / "Voice on"` | Enables spoken voice responses aloud | None |
| `"Disable voice" / "Mute voice"` | Mutes spoken responses (silent screen only) | None |
| `"Volume up" / "Mute"` | Adjusts system volume | None |
| `"What time is it?"` | Tells current local time and date | None |

---

## 🧪 Testing

To run the full unit test suite covering all features:
```cmd
python test_jarvis.py
```
*(Runs 26 automated tests validating actions, voice activation, speech synthesis engine, server endpoints, and safe confirmation flows).*
