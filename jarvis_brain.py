"""
jarvis_brain.py - Hybrid Cloud + Offline AI Brain with Natural Language Understanding,
Voice Activation State Management, Safe Execution Confirmations, and Multi-Command Support.
"""

import os
import json
import time
import re
from openai import OpenAI
import jarvis_actions
import jarvis_nlu_model

# ==============================================================================
# MULTI-COMMAND SPLITTER
# ==============================================================================

# Action verbs that signal the start of a new sub-command
_SPLIT_VERBS = (
    "open", "launch", "start", "close", "exit", "quit", "kill", "terminate",
    "switch", "play", "search", "google", "find", "mute", "unmute",
    "volume", "increase", "decrease", "tell", "what", "show", "check",
    "send", "email", "message", "focus", "bring", "stop", "pause",
    "enable", "disable", "turn",
)

# Conjunctions that connect independent commands
_SPLIT_CONJUNCTIONS = re.compile(
    r"\s*(?:;|,\s*(?=(?:" + "|".join(_SPLIT_VERBS) + r")\b))"
    r"|\s+(?:and\s+then|and\s+also|and\s+after\s+that|then\s+also|and|then|also|after\s+that|,\s*)\s+"
    r"(?=(?:" + "|".join(_SPLIT_VERBS) + r")\b)",
    re.IGNORECASE,
)


def _split_commands(q):
    """
    Splits a compound natural language command into individual sub-commands.
    Only splits at conjunction boundaries immediately followed by an action verb.
    Returns a list with at least one element.
    """
    parts = _SPLIT_CONJUNCTIONS.split(q.strip())
    # Filter out empty / whitespace-only parts and strip each
    return [p.strip() for p in parts if p and p.strip()]

KEYFILE = os.path.expanduser("~/.openjarvis/free.key")
MODELS = ["openai/gpt-oss-20b", "openai/gpt-oss-120b", "qwen/qwen3.8-27b"]

_client = None
_history = []
_cooldown_until = 0.0

# State Management: Standby vs Active
_sleeping = False
_mode = "active"

# Safety: Pending Confirmation
_pending_confirmation = None

NLU_SYSTEM_PROMPT = """You are JARVIS, an elite executive Personal Assistant (PA) inspired by the iconic AI persona voiced by Paul Bettany.
You manage the user's computer, applications, schedule, and general queries with effortless competence and loyalty.

PERSONA & TONE (EXECUTIVE PERSONAL ASSISTANT / PA):
- Always address the user respectfully as "sir" (or as an esteemed executive client).
- Speak with calm sophistication, articulate charm, dry wit, and impeccable manners: polite, sharp, proactive, and always at their service.
- Keep responses concise (1-2 sentences), tailored for spoken text-to-speech audio delivery.
- Speak in the voice of a trusted, high-level PA:
  - "Right away, sir."
  - "At your service, sir. I have pulled up the details you required."
  - "Consider it done, sir."
  - "Security authorization required, sir: you requested to delete '{target}'. Shall I proceed?"
  - "Always a pleasure, sir. All core diagnostics remain optimal."
- Avoid generic AI disclaimers or robotic corporate filler. Sound like a refined, intelligent personal assistant.

CRITICAL INTENT RULES:
- For ANY technical, conceptual, educational, scientific, or general knowledge question (e.g., "tell me about machine learning", "what is machine learning", "explain quantum computing", "how does a neural network work", "tell me about Python"):
  * Your intent MUST BE "chat"!
  * NEVER return "search_web" for conceptual, educational, or explanatory questions!
  * Directly provide an articulate, insightful 1-2 sentence spoken explanation in the "response" field.
- The intent "search_web" is RESERVED STRICTLY for when the user explicitly commands a browser web search (e.g. "search Google for...", "google search...", "search the web for...").

Your job is to understand natural language user commands and return a JSON object with:
- "intent": one of "open_app", "switch_window", "close_app", "search_web", "play_youtube", "volume_control", "market_report", "mail_brief", "sensitive_action", "chat"
- "action": specific action name (e.g., "delete_file", "send_message", "purchase", "open_app", "switch_window", "close_app", "chat")
- "target": target entity (app name, window name, file path, contact name, item name, search query)
- "params": dictionary of extra parameters (e.g. {"message": "..."} or {"level": "up"})
- "is_sensitive": boolean - true ONLY IF the command involves deleting files/folders, sending messages/emails, making purchases/orders, or shutting down/restarting the PC.
- "response": A refined, natural 1-2 sentence spoken response in your PA persona. If sensitive, ask for confirmation addressing the user as "sir".
"""


def _get_api_key():
    if os.environ.get("GROQ_API_KEY"):
        return os.environ["GROQ_API_KEY"].strip()
    if os.path.exists(KEYFILE):
        with open(KEYFILE, "r", encoding="utf-8") as f:
            return f.read().strip()
    return None


def ready():
    """Returns True if the cloud brain is active and not currently rate-limited."""
    key = _get_api_key()
    if not key:
        return False
    return time.time() >= _cooldown_until


def _is_rate_limited(e):
    status = getattr(e, "status_code", None)
    if status == 429:
        return True
    s = str(e).lower()
    return any(w in s for w in ("429", "rate limit", "too many requests", "rate_limit", "exceeded"))


def _retry_after_seconds(e, default=60):
    s = str(e).lower()
    m = re.search(r"try again in\s*(\d+)m\s*([0-9]+(?:\.[0-9]+)?)s", s)
    if m:
        return int(float(m.group(1)) * 60 + float(m.group(2))) + 2
    m = re.search(r"try again in\s*([0-9]+(?:\.[0-9]+)?)s", s)
    if m:
        return int(float(m.group(1))) + 2
    return default


def _set_cooldown(secs):
    global _cooldown_until
    _cooldown_until = max(_cooldown_until, time.time() + float(secs))


# ==============================================================================
# STANDBY / SLEEP STATE MANAGEMENT
# ==============================================================================

def is_sleeping():
    """Returns True if Jarvis is currently in standby mode."""
    return _sleeping


def wake():
    """Wakes Jarvis up to active mode."""
    global _sleeping, _mode
    _sleeping = False
    _mode = "active"
    return "Jarvis is online and ready, sir."


def sleep():
    """Puts Jarvis into standby mode."""
    global _sleeping, _mode
    _sleeping = True
    _mode = "standby"
    return "Entering standby mode. Say 'Open Jarvis' when you need me."


def toggle_sleep():
    """Toggles between standby and active modes."""
    if _sleeping:
        return False, wake()
    else:
        return True, sleep()


def get_mode():
    return _mode


# ==============================================================================
# CONFIRMATION / SAFE EXECUTION MANAGEMENT
# ==============================================================================

def get_pending_confirmation():
    return _pending_confirmation


def set_pending_confirmation(action_type, target, summary, details=None):
    global _pending_confirmation
    _pending_confirmation = {
        "id": str(int(time.time() * 1000)),
        "action_type": action_type,
        "target": target,
        "summary": summary,
        "details": details or {},
        "timestamp": time.time(),
    }
    return _pending_confirmation


def clear_pending_confirmation():
    global _pending_confirmation
    _pending_confirmation = None


def resolve_confirmation(approved):
    """
    Resolves the pending sensitive action: executes if approved, cancels if rejected.
    """
    global _pending_confirmation
    if not _pending_confirmation:
        return "There are no pending actions waiting for confirmation."

    conf = _pending_confirmation
    _pending_confirmation = None

    if approved:
        res = jarvis_actions.execute_sensitive_action(
            conf["action_type"], conf["target"], conf.get("details", {})
        )
        return res
    else:
        return "Action aborted, sir. No changes were made."


# ==============================================================================
# LOCAL NLU & FALLBACK ENGINE
# ==============================================================================

LOCAL_TECHNICAL_KNOWLEDGE = {
    "machine learning": "Machine learning, sir, is a branch of artificial intelligence where algorithms learn patterns from data to make decisions or predictions without explicit programming.",
    "artificial intelligence": "Artificial intelligence, sir, is the field of computer science dedicated to developing systems capable of performing cognitive tasks such as reasoning, learning, and problem-solving.",
    "ai": "Artificial intelligence, sir, is the simulation of human intelligence processes by computer systems, encompassing learning, reasoning, and self-correction.",
    "deep learning": "Deep learning, sir, is a specialized branch of machine learning utilizing multi-layered artificial neural networks to model intricate patterns in large datasets.",
    "neural network": "A neural network, sir, is a computational model inspired by the human brain, using interconnected layers of nodes to process complex information.",
    "neural networks": "Neural networks, sir, are computational architectures inspired by biological brains, designed to recognize underlying relationships in data.",
    "python": "Python, sir, is a high-level, versatile programming language renowned for its readable syntax and vast ecosystem across data science, AI, and automation.",
    "data science": "Data science, sir, combines mathematics, statistics, and machine learning to analyze large volumes of complex data and extract actionable strategic intelligence.",
    "quantum computing": "Quantum computing, sir, harnesses the principles of quantum mechanics, such as superposition and entanglement, to perform computations exponentially faster than classical computers for specific problems.",
    "cloud computing": "Cloud computing, sir, delivers on-demand computing services—including servers, storage, databases, and networking—over the internet with high scalability.",
    "cybersecurity": "Cybersecurity, sir, is the practice of protecting computer systems, networks, and sensitive data from digital attacks, unauthorized access, and damage.",
    "natural language processing": "Natural language processing, sir, is the AI discipline that enables computers to understand, interpret, and generate human language intelligently.",
    "nlp": "Natural language processing, sir, enables computational systems to process and comprehend human language for communication, sentiment, and translation.",
}


def _get_local_technical_answer(q_clean):
    """Returns a direct personal assistant technical answer for core topics if available."""
    for key, answer in LOCAL_TECHNICAL_KNOWLEDGE.items():
        if key in q_clean:
            return answer
    return None


def _local_fallback(q):
    """
    Called when Groq API is temporarily rate-limited or offline.
    Uses enhanced local natural language matching with safety checks.
    """
    q_clean = q.lower().strip(" .,!?")

    # 1. Check for sensitive actions first
    is_sens, act_type, target, summary, details = jarvis_actions.detect_sensitive_action(q)
    if is_sens:
        set_pending_confirmation(act_type, target, summary, details)
        return (
            f"Security confirmation required: You requested to {summary}. "
            "Please confirm with 'yes' or 'no'."
        )

    # 2. Check for local technical knowledge explanation
    tech_ans = _get_local_technical_answer(q_clean)
    if tech_ans:
        return tech_ans

    # 3. Try deterministic local actions
    action_res = jarvis_actions.try_action(q)
    if action_res:
        return action_res

    # 4. Neural Intent Classification (Offline TF-IDF Subword Neural Network)
    if jarvis_nlu_model.is_available():
        pred_intent, conf, _ = jarvis_nlu_model.predict_intent(q)
        if conf >= 0.70:
            target = jarvis_nlu_model.extract_entity_target(q, pred_intent)
            if pred_intent in ("open_app", "close_app", "switch_window", "play_youtube", "market_report", "datetime_query"):
                exec_res = jarvis_actions.execute_intent(pred_intent, target, pred_intent)
                if exec_res:
                    return exec_res
            elif pred_intent == "chat":
                ans = _get_local_technical_answer(q_clean)
                if ans:
                    return ans
                return f"Certainly, sir. Regarding your inquiry on {target or q_clean}, my local neural core confirms this topic. Allow me to assist further when online connectivity resumes."

    # 5. General intelligent local response
    return (
        "At your service, sir. While my cloud neural link is momentarily cooling down, "
        "my local assistant core is active to launch your applications, switch windows, or monitor markets."
    )


# ==============================================================================
# MAIN THINKING / COMMAND ENTRY POINT
# ==============================================================================

def _clean_text(s):
    if not isinstance(s, str):
        return s
    return (
        s.replace("\u2011", "-")
        .replace("\u2013", "-")
        .replace("\u2014", "-")
        .replace("\u2018", "'")
        .replace("\u2019", "'")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
    )


def _think_single(q):
    """
    Processes a single, atomic command.
    Internal implementation used by think() after multi-command splitting.
    """
    global _client, _history, _pending_confirmation

    q_raw = q.strip()
    q_clean = q_raw.lower().strip(" .,!?")

    # 1. Voice Activation: Wake Commands
    wake_phrases = (
        "open jarvis", "wake up jarvis", "wake up, jarvis", "wake up",
        "activate jarvis", "start jarvis", "hey jarvis", "hello jarvis"
    )
    if any(q_clean == p or q_clean.startswith("open jarvis") for p in wake_phrases):
        return wake()

    # 2. Voice Activation: Sleep / Standby Commands
    sleep_phrases = (
        "sleep jarvis", "sleep, jarvis", "go to sleep jarvis", "go to sleep, jarvis",
        "jarvis sleep", "sleep", "standby", "go to standby"
    )
    if any(q_clean == p or q_clean.startswith("sleep jarvis") or q_clean.endswith("sleep jarvis") for p in sleep_phrases):
        return sleep()

    # 3. Standby Mode Check: If sleeping, ignore any commands except "Open Jarvis"
    if _sleeping:
        if "open jarvis" in q_clean or "wake" in q_clean:
            return wake()
        return None

    # 4. Safe Task Execution: Handle Pending Confirmation
    if _pending_confirmation is not None:
        # Check affirmative
        affirmatives = ("yes", "confirm", "proceed", "do it", "sure", "affirmative", "go ahead", "approve", "yes jarvis")
        if any(w in q_clean.split() or q_clean == w for w in affirmatives):
            return resolve_confirmation(True)

        # Check negative
        negatives = ("no", "cancel", "abort", "stop", "don't", "negative", "never mind", "reject", "no jarvis")
        if any(w in q_clean.split() or q_clean == w for w in negatives):
            return resolve_confirmation(False)

        # Still waiting
        return (
            f"Security authorization pending: Do you want me to {_pending_confirmation['summary']}? "
            "Say 'yes' to proceed, or 'no' to cancel."
        )

    # 5. Fast Path: Check Sensitive Action locally before hitting API
    is_sens, act_type, target, summary, details = jarvis_actions.detect_sensitive_action(q_raw)
    if is_sens:
        set_pending_confirmation(act_type, target, summary, details)
        return (
            f"Security confirmation required: You requested to {summary}. "
            "Please confirm with 'yes' or 'no'."
        )

    # 6. Immediate deterministic local action check (fast-path for simple commands)
    local_done = jarvis_actions.try_action(q_raw)
    if local_done:
        return local_done

    # 7. AI Command Understanding via Cloud LLM API
    key = _get_api_key()
    if not key or time.time() < _cooldown_until:
        return _local_fallback(q_raw)

    if _client is None:
        _client = OpenAI(api_key=key, base_url="https://api.groq.com/openai/v1")

    msgs = (
        [{"role": "system", "content": NLU_SYSTEM_PROMPT}]
        + _history[-6:]
        + [{"role": "user", "content": q_raw}]
    )

    for model in MODELS:
        try:
            resp = _client.chat.completions.create(
                model=model,
                messages=msgs,
                max_tokens=400,
                temperature=0.2,
                response_format={"type": "json_object"},
            )
            raw_content = _clean_text(resp.choices[0].message.content.strip())

            try:
                parsed = json.loads(raw_content)
            except Exception:
                # If model returned plaintext despite json_object
                _history += [{"role": "user", "content": q_raw}, {"role": "assistant", "content": raw_content}]
                return raw_content

            intent = parsed.get("intent", "chat")
            target_entity = parsed.get("target", "")
            action_name = parsed.get("action", "")
            params = parsed.get("params", {})
            spoken_resp = _clean_text(parsed.get("response", ""))
            is_sensitive = parsed.get("is_sensitive", False)

            # Safety check from AI classification
            if is_sensitive or action_name in ("delete_file", "send_message", "purchase", "system_shutdown"):
                summary_text = f"{action_name.replace('_', ' ')} '{target_entity}'"
                set_pending_confirmation(action_name, target_entity, summary_text, params)
                return (
                    f"Security confirmation required: You requested to {summary_text}. "
                    "Please confirm with 'yes' or 'no'."
                )

            # Safeguard: Never trigger search_web for informational or technical inquiries
            informational_patterns = (
                "tell me about", "tell me", "what is", "what are", "what was", "what were",
                "who is", "who was", "who were", "explain", "describe", "how does", "how do",
                "can you explain", "teach me", "why is", "why does", "why do", "meaning of", "definition of"
            )
            is_info_query = any(p in q_clean for p in informational_patterns)
            if intent == "search_web" and is_info_query:
                intent = "chat"

            # Execute intent if it is an actionable command
            if intent in ("open_app", "switch_window", "close_app", "search_web", "play_youtube", "volume_control", "market_report"):
                exec_result = jarvis_actions.execute_intent(intent, target_entity, action_name, params)
                final_answer = _clean_text(spoken_resp or exec_result or f"Action {intent} executed.")
                _history += [{"role": "user", "content": q_raw}, {"role": "assistant", "content": final_answer}]
                return final_answer

            # Conversational / Technical explanation query
            if not spoken_resp or spoken_resp.lower().startswith("searching google"):
                spoken_resp = _get_local_technical_answer(q_clean) or spoken_resp or f"Certainly, sir. Regarding {target_entity or q_raw}, allow me to assist."

            spoken_resp = _clean_text(spoken_resp)
            _history += [{"role": "user", "content": q_raw}, {"role": "assistant", "content": spoken_resp}]
            return spoken_resp

        except Exception as e:
            if _is_rate_limited(e):
                wait_sec = _retry_after_seconds(e)
                _set_cooldown(wait_sec)
                print(f"[Rate-limit triggered: cooldown for {wait_sec}s]")
                return _local_fallback(q_raw)
            print(f"[Model {model} failed: {e}]")

    return _local_fallback(q_raw)


# ==============================================================================
# PUBLIC ENTRY POINT: Multi-Command Dispatcher
# ==============================================================================

def think(q):
    """
    Main public entry point for all queries.
    Automatically detects and processes multi-command inputs such as
    'open chrome and play music' or 'close notepad then open calculator'.
    Each sub-command is executed sequentially and responses are joined.
    """
    q_stripped = q.strip()

    # Always process wake/sleep commands as atomic (never split them)
    q_lower = q_stripped.lower().strip(" .,!?")
    special_phrases = (
        "open jarvis", "wake up jarvis", "wake up", "sleep jarvis", "go to sleep",
        "activate jarvis", "hey jarvis", "hello jarvis", "standby",
    )
    is_special = any(q_lower == p or q_lower.startswith(p) for p in special_phrases)

    # Also keep pending-confirmation responses atomic
    is_confirmation = _pending_confirmation is not None

    if is_special or is_confirmation:
        return _think_single(q_stripped)

    # Try to split into multiple sub-commands
    parts = _split_commands(q_stripped)

    if len(parts) <= 1:
        # Single command: process normally
        return _think_single(q_stripped)

    # Multi-command: process each sub-command sequentially
    responses = []
    for part in parts:
        if not part:
            continue
        result = _think_single(part)
        if result:
            responses.append(result.strip())

    if not responses:
        return "Done, sir."

    # Join the multiple responses into a coherent reply
    if len(responses) == 1:
        return responses[0]

    # Combine: number the responses only when there are 3+, otherwise join naturally
    if len(responses) == 2:
        return f"{responses[0]} Also, {responses[1].lower()[0]}{responses[1][1:]}" if responses[1] else responses[0]

    joined = " ".join(
        f"({i + 1}) {r}" for i, r in enumerate(responses)
    )
    return f"Executed {len(responses)} commands, sir. {joined}"


if __name__ == "__main__":
    print("Testing Jarvis Brain...")
    print("Wake:", think("Open Jarvis"))
    print("Sleep:", think("Sleep, Jarvis"))
    print("Sleeping status:", is_sleeping())
    print("Command while asleep:", think("Open Chrome"))
    print("Wake:", think("Open Jarvis"))
    print("Delete test:", think("Delete the test.log file"))
    print("Pending confirmation:", get_pending_confirmation())
    print("Confirm yes:", think("yes"))
