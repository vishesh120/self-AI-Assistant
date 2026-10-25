"""
jarvis_voice.py - Live Speech Recognition, Voice Activation & Audio Response Loop
Listens continuously through your microphone, processes commands, syncs with HUD,
supports "Open Jarvis" wake activation and "Sleep, Jarvis" standby.
"""

import sys
import os
import subprocess
import time
import queue
import threading
import re
import speech_recognition as sr
import jarvis_brain
import jarvis_server

_speech_queue = queue.Queue()
_speech_worker_thread = None
_speech_lock = threading.Lock()
_voice_enabled = True
_is_speaking = False


def _preferred_microphone_index(names):
    configured_index = os.environ.get("JARVIS_MIC_DEVICE_INDEX")
    if configured_index is not None:
        try:
            return int(configured_index)
        except ValueError as e:
            raise ValueError("JARVIS_MIC_DEVICE_INDEX must be an integer.") from e

    return next(
        (index for index, name in enumerate(names)
         if "realtek" in name.lower() and "microphone" in name.lower()),
        None,
    )


def _denoise_audio(audio):
    try:
        import noisereduce
        import numpy as np
    except ImportError:
        return audio

    try:
        sample_rate = 16000
        raw_audio = audio.get_raw_data(convert_rate=sample_rate, convert_width=2)
        samples = np.frombuffer(raw_audio, dtype=np.int16)
        if not samples.size:
            return audio
        cleaned = noisereduce.reduce_noise(
            y=samples,
            sr=sample_rate,
            stationary=False,
            prop_decrease=0.75,
        )
        cleaned = np.clip(cleaned, -32768, 32767).astype(np.int16)
        return sr.AudioData(cleaned.tobytes(), sample_rate, 2)
    except Exception as e:
        print(f"[Noise reduction unavailable: {e}]")
        return audio


def clean_for_speech(text):
    """Strips markdown, URLs, and noisy syntax for natural voice synthesis."""
    if not text:
        return ""
    # Normalize unicode punctuation
    text = text.replace("\u2011", "-").replace("\u2013", "-").replace("\u2014", "-")
    text = text.replace("\u2018", "'").replace("\u2019", "'").replace("\u201c", '"').replace("\u201d", '"')
    # Strip markdown code blocks
    text = re.sub(r"```.*?```", "code snippet omitted", text, flags=re.DOTALL)
    # Strip inline code ticks
    text = re.sub(r"`([^`]+)`", r"\1", text)
    # Strip markdown links [title](url) -> title
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    # Simplify raw URLs
    text = re.sub(r"https?://\S+", "link", text)
    # Strip bullet stars, hashtags, formatting markers
    text = re.sub(r"[*_~#>|]", "", text)
    # Collapse multiple whitespaces
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _speech_worker():
    """Background worker processing speech tasks sequentially and thread-safely."""
    global _is_speaking
    sapi_speaker = None
    pyttsx_engine = None

    if sys.platform.startswith("win"):
        try:
            import pythoncom
            import win32com.client
            pythoncom.CoInitialize()
            sapi_speaker = win32com.client.Dispatch("SAPI.SpVoice")
            sapi_speaker.Rate = 1  # 175-180 wpm natural PA cadence
            sapi_speaker.Volume = 100
            preferred_name = os.environ.get("JARVIS_VOICE_NAME", "").lower()
            voices = sapi_speaker.GetVoices()
            for v in voices:
                desc = v.GetDescription().lower()
                if preferred_name and preferred_name in desc:
                    sapi_speaker.Voice = v
                    break
                if not preferred_name and "david" in desc:
                    sapi_speaker.Voice = v
                    break
                elif not preferred_name and "hazel" in desc:
                    sapi_speaker.Voice = v
        except Exception as e:
            print(f"[Windows SAPI init notice: {e}]")

    if sapi_speaker is None and sys.platform != "darwin":
        try:
            import pyttsx3
            pyttsx_engine = pyttsx3.init()
            pyttsx_engine.setProperty("rate", 175)
            pyttsx_engine.setProperty("volume", 1.0)
        except Exception as e:
            print(f"[pyttsx3 init notice: {e}]")

    while True:
        item = _speech_queue.get()
        if item is None:
            break
        text, done_event = item

        if not _voice_enabled or not text:
            if done_event:
                done_event.set()
            _speech_queue.task_done()
            continue

        _is_speaking = True
        try:
            jarvis_server.set_hud_state("speaking", "JARVIS RESPONDING")
            clean_text = clean_for_speech(text)
            spoken = False

            # 1. Windows Native SAPI (SpVoice) - Instant & Reliable
            if sapi_speaker is not None:
                try:
                    sapi_speaker.Speak(clean_text)
                    spoken = True
                except Exception as e:
                    print(f"[SAPI speak error: {e}]")

            # 2. macOS Native say command
            if not spoken and sys.platform == "darwin":
                res = subprocess.run(["say", "-v", "Daniel", clean_text])
                if res.returncode != 0:
                    subprocess.run(["say", "-v", "Samantha", clean_text])
                spoken = True

            # 3. pyttsx3 Cross-Platform Engine
            if not spoken and pyttsx_engine is not None:
                try:
                    pyttsx_engine.say(clean_text)
                    pyttsx_engine.runAndWait()
                    spoken = True
                except Exception as e:
                    print(f"[pyttsx3 speak error: {e}]")

            # 4. Windows PowerShell .NET Speech Synthesizer fallback
            if not spoken and sys.platform.startswith("win"):
                try:
                    safe_cmd = clean_text.replace("'", "''").replace('"', '`"')
                    subprocess.run([
                        "powershell", "-NoProfile", "-Command",
                        f"Add-Type -AssemblyName System.Speech; $synth = New-Object System.Speech.Synthesis.SpeechSynthesizer; $synth.Rate = 1; $synth.Speak('{safe_cmd}')"
                    ], timeout=10)
                    spoken = True
                except Exception as e:
                    print(f"[PowerShell speech fallback notice: {e}]")

        except Exception as e:
            print(f"[Voice output error: {e}]")
        finally:
            _is_speaking = False
            # Revert HUD state back to listening or standby
            if jarvis_brain.is_sleeping():
                jarvis_server.set_hud_state("standby", "STANDBY MODE · SAY 'OPEN JARVIS' TO WAKE")
            else:
                jarvis_server.set_hud_state("listening", "SYSTEM READY")
            if done_event:
                done_event.set()
            _speech_queue.task_done()


def _ensure_speech_worker():
    global _speech_worker_thread
    with _speech_lock:
        if _speech_worker_thread is None or not _speech_worker_thread.is_alive():
            _speech_worker_thread = threading.Thread(target=_speech_worker, daemon=True, name="JarvisTTSWorker")
            _speech_worker_thread.start()


def is_speaking():
    """Returns True if Jarvis is currently speaking aloud."""
    return _is_speaking


def is_voice_enabled():
    """Returns True if voice speech output is enabled."""
    return _voice_enabled


def set_voice_enabled(enabled):
    """Enables or disables voice speech output."""
    global _voice_enabled
    _voice_enabled = bool(enabled)
    try:
        jarvis_server.set_voice_enabled(_voice_enabled)
    except Exception:
        pass
    return _voice_enabled


def toggle_voice():
    """Toggles voice speech output on or off."""
    return set_voice_enabled(not _voice_enabled)


def speak(text, block=False):
    """
    Speaks output aloud using high-performance queue-based TTS.
    Outputs to console and triggers speech synthesis.
    """
    if not text:
        return
    try:
        print(f"\n[JARVIS]: {text}\n")
    except UnicodeEncodeError:
        safe_text = text.encode("ascii", "replace").decode("ascii")
        print(f"\n[JARVIS]: {safe_text}\n")
    if not _voice_enabled:
        return

    _ensure_speech_worker()
    done_event = threading.Event() if block else None
    _speech_queue.put((text, done_event))
    if block and done_event:
        done_event.wait()


def _text_input_loop():
    """Fallback text console loop when microphone is unavailable."""
    while True:
        try:
            user_input = input("You: ")
            if user_input.strip():
                jarvis_server.add_chat("you", user_input.strip())
                resp = jarvis_brain.think(user_input.strip())
                if resp:
                    jarvis_server.add_chat("jarvis", resp)
                    speak(resp)
        except (KeyboardInterrupt, EOFError):
            break


def ensure_single_instance():
    """Prevents multiple simultaneous voice instances from conflicting and double-firing actions."""
    if os.environ.get("JARVIS_TEST_MODE") or any("test" in arg.lower() for arg in sys.argv):
        return True

    lockfile = os.path.join(os.path.expanduser("~"), ".openjarvis", "jarvis_voice.pid")
    os.makedirs(os.path.dirname(lockfile), exist_ok=True)
    if os.path.exists(lockfile):
        try:
            import psutil
            with open(lockfile, "r") as f:
                content = f.read().strip()
            if content:
                old_pid = int(content)
                if old_pid != os.getpid() and psutil.pid_exists(old_pid):
                    p = psutil.Process(old_pid)
                    if "python" in p.name().lower():
                        try:
                            cmdline = " ".join(p.cmdline()).lower()
                            is_jarvis = any(k in cmdline for k in ("jarvis_app", "jarvis_voice"))
                        except Exception:
                            is_jarvis = False
                        if is_jarvis:
                            print(f"\n[!] Notice: Another Jarvis instance is already running (PID: {old_pid}).")
                            print("    Exiting duplicate process to prevent double actions.")
                            return False
        except Exception:
            pass

    try:
        with open(lockfile, "w") as f:
            f.write(str(os.getpid()))
    except Exception:
        pass
    return True


def listen_loop():
    """Main continuous voice recognition loop with HUD synchronization."""
    if not ensure_single_instance():
        return

    # Ensure background HUD web server is online
    try:
        jarvis_server.start_server(background=True)
    except Exception as e:
        print(f"[Server notice: {e}]")

    recognizer = sr.Recognizer()
    recognizer.dynamic_energy_threshold = True
    recognizer.dynamic_energy_adjustment_damping = 0.15
    recognizer.dynamic_energy_ratio = 1.4
    recognizer.pause_threshold = 0.65
    recognizer.non_speaking_duration = 0.4
    recognizer.phrase_threshold = 0.25

    try:
        microphone_names = sr.Microphone.list_microphone_names()
        microphone_index = _preferred_microphone_index(microphone_names)
        mic = sr.Microphone(device_index=microphone_index)
        if microphone_index is not None:
            print(f"Using microphone: {microphone_names[microphone_index]}")
    except Exception as e:
        print(f"Error accessing microphone: {e}")
        print("Falling back to text console input mode.")
        _text_input_loop()
        return

    with mic as source:
        print("\n" + "=" * 55)
        print("  [+] JARVIS AI ASSISTANT IS ACTIVE & LISTENING")
        print("  Say:")
        print("    - 'Open Jarvis' to activate from standby")
        print("    - 'Sleep, Jarvis' to return to standby")
        print("    - 'Open Chrome' / 'Open VS Code' / 'Open Calculator'")
        print("    - 'Switch to Chrome' / 'Switch to Notepad'")
        print("    - 'Delete file test.txt' (requires confirmation)")
        print("    - 'Stock market update' / 'Play lofi on YouTube'")
        print("=" * 55 + "\n")
        print("Calibrating background noise; stay quiet for a moment...")
        recognizer.adjust_for_ambient_noise(source, duration=1.5)
        print(f"Noise calibration complete (energy threshold: {recognizer.energy_threshold:.0f}).")

    jarvis_server.set_hud_state("listening", "JARVIS ONLINE & ARMED")

    while True:
        try:
            # Sync HUD state based on standby vs active
            if jarvis_brain.is_sleeping():
                jarvis_server.set_hud_state("standby", "STANDBY MODE · SAY 'OPEN JARVIS' TO WAKE")
            else:
                jarvis_server.set_hud_state("listening", "LISTENING")

            with mic as source:
                status_prompt = "Standby (Say 'Open Jarvis')... " if jarvis_brain.is_sleeping() else "Listening... "
                print(status_prompt, end="", flush=True)
                audio = recognizer.listen(source, timeout=8, phrase_time_limit=10)

            print("Processing... ", end="", flush=True)
            jarvis_server.set_hud_state("recognizing", "ANALYZING AUDIO")

            query = recognizer.recognize_google(_denoise_audio(audio)).strip()
            print(f"\nYou said: \"{query}\"")

            q_clean = query.lower()

            # Handle standby wake word
            if jarvis_brain.is_sleeping():
                if "open jarvis" in q_clean or "wake up" in q_clean:
                    jarvis_server.add_chat("you", query)
                    response = jarvis_brain.wake()
                    jarvis_server.add_chat("jarvis", response)
                    jarvis_server.set_hud_state("speaking", "JARVIS AWAKE")
                    speak(response, block=True)
                else:
                    # In standby mode, ignore ambient speech
                    print("[Standby: Ignored. Say 'Open Jarvis' to wake]")
                continue

            # Active mode processing
            jarvis_server.add_chat("you", query)
            jarvis_server.set_hud_state("thinking", f"PROCESSING: {query[:30]}")

            # Wake word filter (optional - removes prefix "jarvis" if present)
            if "jarvis" in q_clean and not any(k in q_clean for k in ("sleep jarvis", "open jarvis")):
                cleaned_query = q_clean.replace("jarvis", "").strip(" ,.!?")
                if not cleaned_query:
                    speak("Yes sir, I'm listening.", block=True)
                    continue
            else:
                cleaned_query = query

            response = jarvis_brain.think(cleaned_query)

            if response:
                jarvis_server.add_chat("jarvis", response)
                jarvis_server.set_hud_state("speaking", "JARVIS RESPONDING")
                speak(response, block=True)

        except sr.WaitTimeoutError:
            jarvis_server.push_mic_level(0.05)
            continue
        except sr.UnknownValueError:
            continue
        except sr.RequestError as e:
            print(f"Speech recognition service unavailable: {e}")
            print("Falling back to text console input mode.")
            _text_input_loop()
            break
        except KeyboardInterrupt:
            print("\nShutting down Jarvis. Goodbye!")
            jarvis_server.add_chat("sys", "Jarvis shutting down. Goodbye.")
            break
        except Exception as e:
            print(f"\n[Notice]: {e}")
            time.sleep(0.5)


if __name__ == "__main__":
    listen_loop()
