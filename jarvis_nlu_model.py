"""
jarvis_nlu_model.py - Local TF-IDF Subword Neural NLU Intent Classifier Engine
Provides high-speed (<0.25 ms), fully offline intent prediction and confidence scoring
using the trained multi-layer neural network model.
"""

import os
import re
import joblib

MODELS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
_vectorizer = None
_model = None
_label_encoder = None
_is_loaded = False


def load_model():
    """Loads the trained subword vectorizer and neural network classifier."""
    global _vectorizer, _model, _label_encoder, _is_loaded
    if _is_loaded:
        return True

    vec_path = os.path.join(MODELS_DIR, "jarvis_tfidf_subword_vectorizer.joblib")
    model_path = os.path.join(MODELS_DIR, "jarvis_neural_intent_model.joblib")
    enc_path = os.path.join(MODELS_DIR, "label_encoder.joblib")

    if not (os.path.exists(vec_path) and os.path.exists(model_path) and os.path.exists(enc_path)):
        return False

    try:
        _vectorizer = joblib.load(vec_path)
        _model = joblib.load(model_path)
        _label_encoder = joblib.load(enc_path)
        _is_loaded = True
        return True
    except Exception as e:
        print(f"[NLU Model Load Warning: {e}]")
        return False


def is_available():
    """Returns True if the trained local NLU neural model is loaded and ready."""
    return load_model()


def predict_intent(text):
    """
    Predicts intent for a given user utterance with calibrated confidence.
    Returns: (intent_name: str, confidence: float, class_probs: dict)
    """
    if not is_available() or not text:
        return "chat", 0.0, {}

    try:
        text_clean = text.strip()
        vec = _vectorizer.transform([text_clean])
        probs = _model.predict_proba(vec)[0]
        max_idx = probs.argmax()
        intent = str(_label_encoder.classes_[max_idx])
        confidence = float(probs[max_idx])

        # Return full probability distribution for transparency
        class_probs = {
            str(_label_encoder.classes_[i]): float(probs[i])
            for i in range(len(probs))
        }

        return intent, confidence, class_probs
    except Exception as e:
        print(f"[NLU Prediction Error: {e}]")
        return "chat", 0.0, {}


def extract_entity_target(text, intent):
    """Extracts target entities (app name, stock, song, contact, file) from command text."""
    t = text.lower().strip()
    
    if intent in ("open_app", "close_app", "switch_window"):
        patterns = [
            r"(?:open|launch|start|run|close|exit|terminate|kill|switch to|focus|bring up)\s+(?:the\s+)?([a-zA-Z0-9_\s\.\-]+)",
            r"(?:app|application|program)\s+([a-zA-Z0-9_\s\.\-]+)"
        ]
        for p in patterns:
            m = re.search(p, t)
            if m:
                cand = m.group(1).replace("jarvis", "").strip(" .,!?")
                if cand:
                    return cand
        return ""

    elif intent == "play_youtube":
        m = re.search(r"(?:play|put on|stream|listen to)\s+(?:song\s+)?(.+?)(?:\s+on youtube|\s+music)?$", t)
        if m:
            return m.group(1).replace("youtube", "").strip(" .,!?")
        return t

    elif intent == "market_report":
        for s in ("reliance", "tcs", "infosys", "nifty", "sensex", "apple", "nvidia", "tesla", "bitcoin", "crypto"):
            if s in t:
                return s
        return "nifty"

    elif intent == "send_message":
        m = re.search(r"(?:to|message)\s+([a-zA-Z]+)", t)
        if m:
            return m.group(1).capitalize()
        return "Contact"

    elif intent == "sensitive_action":
        m = re.search(r"(?:delete|remove|erase|kill|wipe)\s+(?:file|folder|directory)?\s*([a-zA-Z0-9_\.\-]+)", t)
        if m:
            return m.group(1)
        return "system_action"

    return ""


if __name__ == "__main__":
    load_model()
    test_queries = [
        "Open Chrome browser",
        "Could you please launch VS Code",
        "Tell me about machine learning",
        "Delete file old_logs.txt",
        "What is the time right now",
        "Play lofi on YouTube",
        "Turn up the volume by 20 percent",
        "Sleep Jarvis"
    ]
    print(f"Local Neural NLU Model Loaded: {_is_loaded}")
    print("-" * 65)
    for q in test_queries:
        intent, conf, _ = predict_intent(q)
        target = extract_entity_target(q, intent)
        print(f"Utterance: \"{q}\"")
        print(f" -> Predicted Intent: {intent:<16} Confidence: {conf * 100:.2f}%  Target: '{target}'")
