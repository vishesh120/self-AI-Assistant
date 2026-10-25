import unittest
import os
import tempfile
import requests
import time
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

import jarvis_actions
import jarvis_voice
import jarvis_brain
import jarvis_server


class JarvisActionTests(unittest.TestCase):
    @patch("jarvis_actions.sys.platform", "win32")
    @patch("jarvis_actions.webbrowser.open", return_value=True)
    def test_windows_opens_urls_in_default_browser(self, open_browser):
        self.assertTrue(jarvis_actions._open(["https://example.com"]))
        open_browser.assert_called_once_with("https://example.com")

    @patch("jarvis_actions.sys.platform", "win32")
    def test_windows_resolves_common_app_aliases(self):
        self.assertEqual(jarvis_actions.find_app("vs code"), "Code.exe")
        self.assertEqual(jarvis_actions.find_app("chrome"), "chrome.exe")
        self.assertEqual(jarvis_actions.find_app("notepad"), "notepad.exe")
        self.assertEqual(jarvis_actions.find_app("calculator"), "calc.exe")
        self.assertEqual(jarvis_actions.find_app("edge"), "msedge.exe")

    @patch("jarvis_actions._open", return_value=True)
    def test_youtube_command_uses_local_action(self, open_target):
        result = jarvis_actions.try_action("play lofi on youtube")
        self.assertEqual(result, "Playing lofi on YouTube.")
        self.assertIn("youtube.com/results?search_query=lofi", open_target.call_args.args[0][0])

    @patch("jarvis_actions._open", return_value=True)
    def test_open_youtube_direct_action(self, open_target):
        result = jarvis_actions.try_action("open youtube")
        self.assertEqual(result, "Opening YouTube.")
        self.assertEqual(open_target.call_args.args[0][0], "https://www.youtube.com")

    @patch("jarvis_actions._open", return_value=True)
    def test_play_song_by_name_queries(self, open_target):
        res1 = jarvis_actions.try_action("play song kesariya")
        self.assertIn("kesariya", res1.lower())

        res2 = jarvis_actions.try_action("play believer")
        self.assertIn("believer", res2.lower())

        res3 = jarvis_actions.try_action("play song on name")
        self.assertIn("youtube", res3.lower())

    @patch("jarvis_actions.webbrowser.open", return_value=True)
    def test_open_url_debouncing(self, web_open):
        jarvis_actions._last_opened_url = ""
        jarvis_actions._last_opened_time = 0.0

        # First open call succeeds
        res1 = jarvis_actions._open(["https://example.org/test"])
        self.assertTrue(res1)
        self.assertEqual(web_open.call_count, 1)

        # Immediate duplicate call within 2.5s is debounced without re-opening
        res2 = jarvis_actions._open(["https://example.org/test"])
        self.assertTrue(res2)
        self.assertEqual(web_open.call_count, 1)

    @patch("jarvis_actions._adjust_volume", return_value=False)
    def test_volume_failure_is_reported(self, adjust_volume):
        self.assertEqual(jarvis_actions.try_action("volume up"), "I couldn't adjust the system volume.")
        adjust_volume.assert_called_once_with(15)

    @patch("jarvis_actions.sys.platform", "win32")
    @patch("jarvis_actions._open", return_value=True)
    def test_switch_window_launches_or_activates(self, open_target):
        res = jarvis_actions.switch_window("notepad")
        self.assertIn("Notepad", res)

    def test_detect_sensitive_actions(self):
        # 1. File deletion
        is_s, act, target, summary, _ = jarvis_actions.detect_sensitive_action("delete file notes.txt")
        self.assertTrue(is_s)
        self.assertEqual(act, "delete_file")
        self.assertEqual(target, "notes.txt")

        # 2. Sending WhatsApp / Email messages
        is_s, act, target, summary, _ = jarvis_actions.detect_sensitive_action("send whatsapp to Alex saying let's meet")
        self.assertTrue(is_s)
        self.assertEqual(act, "send_message")
        self.assertEqual(target.lower(), "alex")

        # 3. Purchases
        is_s, act, target, summary, _ = jarvis_actions.detect_sensitive_action("buy 5 shares of Apple")
        self.assertTrue(is_s)
        self.assertEqual(act, "purchase")

    def test_execute_sensitive_action_delete_file(self):
        with tempfile.NamedTemporaryFile(delete=False) as tf:
            tf.write(b"sensitive data")
            temp_path = tf.name

        self.assertTrue(os.path.exists(temp_path))
        res = jarvis_actions.execute_sensitive_action("delete_file", temp_path)
        self.assertIn("Successfully deleted", res)
        self.assertFalse(os.path.exists(temp_path))


class JarvisVoiceActivationAndSafetyTests(unittest.TestCase):
    def setUp(self):
        jarvis_brain.wake()
        jarvis_brain.clear_pending_confirmation()

    def tearDown(self):
        jarvis_brain.wake()
        jarvis_brain.clear_pending_confirmation()

    def test_voice_activation_wake_and_sleep(self):
        # 1. Sleep command
        res_sleep = jarvis_brain.think("Sleep, Jarvis")
        self.assertIn("standby", res_sleep.lower())
        self.assertTrue(jarvis_brain.is_sleeping())

        # 2. While asleep, commands are ignored
        self.assertIsNone(jarvis_brain.think("open chrome"))

        # 3. Wake command
        res_wake = jarvis_brain.think("Open Jarvis")
        self.assertIn("online", res_wake.lower())
        self.assertFalse(jarvis_brain.is_sleeping())

    def test_safe_task_execution_with_affirmative_confirmation(self):
        jarvis_brain.wake()
        # Request sensitive file deletion
        res = jarvis_brain.think("delete file test_dummy.txt")
        self.assertIn("Security confirmation required", res)
        self.assertIsNotNone(jarvis_brain.get_pending_confirmation())

        # Confirm with "yes"
        confirm_res = jarvis_brain.think("yes")
        self.assertIn("Confirmed", confirm_res)
        self.assertIsNone(jarvis_brain.get_pending_confirmation())

    def test_safe_task_execution_with_negative_cancellation(self):
        jarvis_brain.wake()
        # Request sensitive action
        res = jarvis_brain.think("delete file backup.bak")
        self.assertIn("Security confirmation required", res)
        self.assertIsNotNone(jarvis_brain.get_pending_confirmation())

        # Cancel with "no"
        cancel_res = jarvis_brain.think("no")
        self.assertIn("Action aborted", cancel_res)
        self.assertIsNone(jarvis_brain.get_pending_confirmation())


class JarvisServerAndDesktopUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = jarvis_server.start_server(background=True)
        time.sleep(0.5)
        port = cls.server.server_address[1] if hasattr(cls.server, "server_address") else jarvis_server.PORT
        cls.base_url = f"http://{jarvis_server.HOST}:{port}"

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "server") and cls.server:
            try:
                cls.server.shutdown()
                cls.server.server_close()
            except Exception:
                pass
        jarvis_server._server_instance = None

    def setUp(self):
        jarvis_brain.wake()
        jarvis_voice.set_voice_enabled(True)

    def test_api_state_endpoint(self):
        r = requests.get(f"{self.base_url}/api/state")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("state", data)
        self.assertIn("sys", data)
        self.assertIn("chat", data)
        self.assertIn("cpu", data["sys"])

    def test_api_command_endpoint(self):
        r = requests.post(f"{self.base_url}/api/command", json={"query": "what time is it"})
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("response", data)
        self.assertIn(":", data["response"])

    def test_api_confirmation_endpoint(self):
        # Set a pending confirmation
        jarvis_brain.set_pending_confirmation("delete_file", "dummy.txt", "delete dummy.txt")
        # Cancel it via API
        r = requests.post(f"{self.base_url}/api/confirm", json={"approved": False})
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("Action aborted", data["response"])
        self.assertIsNone(jarvis_brain.get_pending_confirmation())

    def test_api_toggle_sleep_endpoint(self):
        jarvis_brain.wake()
        r = requests.post(f"{self.base_url}/api/toggle_sleep")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["sleeping"])

        # Toggle back to awake
        r2 = requests.post(f"{self.base_url}/api/toggle_sleep")
        self.assertEqual(r2.status_code, 200)
        self.assertFalse(r2.json()["sleeping"])

    def test_api_toggle_voice_endpoint(self):
        jarvis_voice.set_voice_enabled(True)
        r = requests.post(f"{self.base_url}/api/toggle_voice")
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.json()["voice_enabled"])

        # Toggle back to enabled
        r2 = requests.post(f"{self.base_url}/api/toggle_voice")
        self.assertEqual(r2.status_code, 200)
        self.assertTrue(r2.json()["voice_enabled"])


class JarvisVoiceTests(unittest.TestCase):
    def test_clean_for_speech_removes_formatting_and_urls(self):
        raw = "Check **bold** and `code` with [link](https://example.com) and ```def test(): pass```!"
        cleaned = jarvis_voice.clean_for_speech(raw)
        self.assertNotIn("**", cleaned)
        self.assertNotIn("`", cleaned)
        self.assertNotIn("https://", cleaned)
        self.assertIn("Check bold and code with link and code snippet omitted!", cleaned)

    def test_voice_toggle_and_state(self):
        jarvis_voice.set_voice_enabled(True)
        self.assertTrue(jarvis_voice.is_voice_enabled())
        jarvis_voice.toggle_voice()
        self.assertFalse(jarvis_voice.is_voice_enabled())
        jarvis_voice.set_voice_enabled(True)

    def test_voice_action_commands(self):
        res1 = jarvis_actions.try_action("disable voice")
        self.assertIn("disabled", res1.lower())
        self.assertFalse(jarvis_voice.is_voice_enabled())

        res2 = jarvis_actions.try_action("enable voice")
        self.assertIn("enabled", res2.lower())
        self.assertTrue(jarvis_voice.is_voice_enabled())

    @patch("jarvis_actions._open")
    def test_technical_inquiry_does_not_open_web(self, mock_open):
        ans = jarvis_brain.think("tell me about machine learning")
        self.assertIn("machine learning", ans.lower())
        # Ensure web browser open was never triggered!
        mock_open.assert_not_called()

    def test_local_technical_knowledge_fallback(self):
        ans = jarvis_brain._get_local_technical_answer("tell me about machine learning")
        self.assertIsNotNone(ans)
        self.assertIn("machine learning", ans.lower())
        self.assertIn("artificial intelligence", ans.lower())
    def test_denoising_returns_transcribable_audio(self):
        reducer = SimpleNamespace(reduce_noise=lambda y, **kwargs: y)
        audio = jarvis_voice.sr.AudioData(b"\x00\x00" * 160, 16000, 2)
        with patch.dict("sys.modules", {"noisereduce": reducer}):
            cleaned = jarvis_voice._denoise_audio(audio)
        self.assertIsInstance(cleaned, jarvis_voice.sr.AudioData)
        self.assertEqual(cleaned.sample_rate, 16000)
        self.assertEqual(cleaned.sample_width, 2)

    def test_realtek_microphone_is_preferred_over_virtual_default(self):
        names = ["VoiceWave Microphone (EaseUS Virtual Device)", "Microphone Array (Realtek(R) Audio)"]
        self.assertEqual(jarvis_voice._preferred_microphone_index(names), 1)

    @patch.dict("os.environ", {"JARVIS_MIC_DEVICE_INDEX": "0"})
    def test_configured_microphone_index_overrides_preference(self):
        self.assertEqual(jarvis_voice._preferred_microphone_index(["Realtek microphone"]), 0)

    @patch("jarvis_voice.speak")
    @patch("jarvis_voice.jarvis_brain.think", return_value="It is noon.")
    @patch("builtins.input", side_effect=["what time is it", EOFError])
    @patch("jarvis_voice.sr.Microphone", side_effect=OSError("no microphone"))
    def test_microphone_error_falls_back_to_console(self, microphone, user_input, think, speak):
        jarvis_voice.listen_loop()
        think.assert_called_once_with("what time is it")
        speak.assert_called_once_with("It is noon.")

    @patch("jarvis_voice.speak")
    @patch("jarvis_voice.jarvis_brain.think", return_value="Console response")
    @patch("builtins.input", side_effect=EOFError)
    @patch("jarvis_voice.sr.Microphone")
    @patch("jarvis_voice.sr.Recognizer")
    def test_recognition_service_error_falls_back_to_console(
        self, recognizer_class, microphone_class, user_input, think, speak
    ):
        source = object()
        microphone = unittest.mock.MagicMock()
        microphone.__enter__.return_value = source
        microphone_class.return_value = microphone
        recognizer = recognizer_class.return_value
        recognizer.energy_threshold = 300
        recognizer.listen.return_value = object()
        recognizer.recognize_google.side_effect = jarvis_voice.sr.RequestError("offline")

        jarvis_voice.listen_loop()

        recognizer.recognize_google.assert_called_once()
        user_input.assert_called_once()
        think.assert_not_called()
        speak.assert_not_called()


class JarvisNeuralNLUModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import jarvis_nlu_model
        cls.nlu = jarvis_nlu_model

    def test_nlu_model_loads_successfully(self):
        self.assertTrue(self.nlu.is_available())

    def test_intent_predictions(self):
        intent, conf, _ = self.nlu.predict_intent("launch vs code")
        self.assertEqual(intent, "open_app")
        self.assertGreater(conf, 0.70)

        intent, conf, _ = self.nlu.predict_intent("tell me about machine learning")
        self.assertEqual(intent, "chat")
        self.assertGreater(conf, 0.70)

        intent, conf, _ = self.nlu.predict_intent("delete file old_logs.txt")
        self.assertEqual(intent, "sensitive_action")
        self.assertGreater(conf, 0.70)

    def test_entity_target_extraction(self):
        target = self.nlu.extract_entity_target("launch vs code", "open_app")
        self.assertEqual(target.lower(), "vs code")

        target = self.nlu.extract_entity_target("delete file test.log", "sensitive_action")
        self.assertEqual(target.lower(), "test.log")

    def test_sub_millisecond_latency(self):
        import time
        # Warmup
        _ = self.nlu.predict_intent("tell me about machine learning")
        t0 = time.perf_counter()
        runs = 500
        for _ in range(runs):
            _ = self.nlu.predict_intent("tell me about machine learning")
        avg_ms = ((time.perf_counter() - t0) / runs) * 1000.0
        self.assertLess(avg_ms, 1.0)


if __name__ == "__main__":

    unittest.main()