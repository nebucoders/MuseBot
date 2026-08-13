#!/usr/bin/env python3
"""MuseBot AI - knowledgebase loading, prompt building, and STT/LLM/TTS calls.

Owns everything musebot_main.py delegates for a single booth stop: loading
knowledgebase{booth_id}.json, building the within-tour and cross-visitor
context digests, calling a chat model for the tour narration/Q&A, edge-tts
for speech output, and Groq Whisper for speech-to-text. Entirely free at
museum-demo volume: no paid API, and TTS needs no account or key at all.

Chat model is switchable via LLM_PROVIDER without touching code:
  - "google" (default): Gemini Flash-Lite - cheap, high-volume, okayish
    reasoning. Good fit for short spoken-language answers.
  - "groq": Qwen served on Groq's LPU inference - alternate cost/quality
    point, useful for A/B'ing against Gemini.

Requires: pip install pyserial SpeechRecognition pyaudio requests edge-tts python-dotenv
(pyaudio needs the portaudio system package for microphone access.)
Requires the `mpg123` binary on PATH for MP3 playback (apt install mpg123).
`edge-tts` is an unofficial wrapper around Microsoft Edge's "Read Aloud"
voices - free, no signup, but not an officially supported API, so it can
change or break without notice.
Requires GOOGLE_API_KEY (only if LLM_PROVIDER=google) and GROQ_API_KEY
(chat if LLM_PROVIDER=groq, always for Whisper STT) to be set - via a
.env file (see .env.example) or exported in the shell.
"""

import json
import math
import os
import random
import re
import struct
import subprocess
import tempfile
import time
import wave
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
from dotenv import load_dotenv

DATA_DIR = Path(__file__).parent
COMBINED_QUESTIONS_PATH = DATA_DIR / "combined_questions.json"

load_dotenv(DATA_DIR / ".env")

# ---- Chat model switcher: "google" or "groq" ----
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "google").strip().lower()

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
GOOGLE_MODEL = os.environ.get("GOOGLE_MODEL", "gemini-flash-lite-latest")
GOOGLE_URL_TEMPLATE = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)

EDGE_TTS_VOICE = os.environ.get("EDGE_TTS_VOICE", "en-US-AriaNeural")

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_QWEN_MODEL = os.environ.get("GROQ_QWEN_MODEL", "qwen/qwen3.6-27b")
GROQ_WHISPER_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
GROQ_WHISPER_MODEL = os.environ.get("GROQ_WHISPER_MODEL", "whisper-large-v3-turbo")
GROQ_WHISPER_LANGUAGE = os.environ.get("GROQ_WHISPER_LANGUAGE", "en")

LISTEN_TIMEOUT_S = 7  # seconds of silence = "no more questions" - tune live, museum noise may need more
AMBIENT_NOISE_ADJUST_S = 0.5
# How long a silence has to last before a phrase is considered "done" -
# SpeechRecognition's default (0.8s) is shorter than a normal breathing
# pause mid-sentence, which was chopping speech into fragments.
PAUSE_THRESHOLD_S = 1.5

ASK_QUESTIONS_PROMPTS = (
    "Do you have any questions?",
    "Anything you'd like to know about this one?",
    "What would you like to ask?",
    "Feel free to ask me anything about this exhibit.",
    "Curious about anything here?",
    "Go ahead, ask me anything.",
)


def ask_questions_prompt() -> str:
    return random.choice(ASK_QUESTIONS_PROMPTS)


CLOSING_LINE = "That concludes our tour today. Thank you for visiting, and goodbye!"

ROBOT_PERSONA = (
    "You are MuseBot, a real museum tour guide who genuinely loves this "
    "collection - not a robot reciting an encyclopedia entry. Talk the way "
    "an enthusiastic human docent talks: warm, a little conversational, "
    "with real curiosity about the object in front of you. Speak in short, "
    "spoken-language sentences suitable for text-to-speech: no markdown, "
    "no bullet points, no headings.\n\n"
    "Vary how you open - don't default to \"This is a...\" every time. "
    "Lead with whatever's most interesting or surprising about this "
    "specific fact: a striking detail, a question the visitor might be "
    "wondering about, a quick contrast (\"you'd expect X, but actually...\"), "
    "or a small aside directed at the visitor (\"take a look at...\", "
    "\"notice how...\"). Let facts connect to each other with natural "
    "transitions instead of reading like a list of unrelated bullet points "
    "- \"and that's actually why...\", \"which is what makes this one "
    "different...\", \"here's the part most people don't expect...\". "
    "Match your energy to the content: genuinely interesting details get "
    "delivered with a bit of enthusiasm, not the same flat tone throughout.\n\n"
    "None of this changes what you're allowed to say: only use the facts "
    "given to you below about the current exhibit - never invent details, "
    "never guess, and never draw on outside knowledge beyond what is "
    "given, even if you happen to know more about the topic. If a question "
    "is only partly covered by the given facts, answer the part you do "
    "know directly and confidently, and only briefly note that you don't "
    "have detail on the rest - don't open with a disclaimer like 'I don't "
    "have that information' when you actually have something useful to "
    "say. Only say you don't have the information at all when none of the "
    "given facts are relevant to the question, then steer back to a fact "
    "you do know instead of guessing."
)

EXIT_PHRASES = (
    "no", "nope", "nothing", "that's all", "thats all", "no thanks",
    "i'm good", "im good", "that's it", "thats it", "no more questions",
    "move on", "next",
)

# ---- TTS (edge-tts: free, no account/key, unofficial Edge "Read Aloud") ----

# Pin the output sink explicitly by name rather than relying on PipeWire's
# default routing to pick the right one - run `wpctl status` to find your
# sink's name and set AUDIO_OUTPUT_DEVICE if it differs.
AUDIO_OUTPUT_DEVICE = os.environ.get("AUDIO_OUTPUT_DEVICE", "Baseus USB Audio Analog Stereo")


def _play_audio(path: str) -> None:
    """Play an audio file via pw-play, routed to AUDIO_OUTPUT_DEVICE.

    Raw ALSA tools (aplay/mpg123) opening the hardware device directly fight
    PipeWire/WirePlumber for the card and fail with "Device or resource
    busy" - pw-play goes through the running PipeWire session instead, like
    every other client on this machine, so there's nothing to contend with."""
    subprocess.run(["pw-play", "--target", AUDIO_OUTPUT_DEVICE, path], check=True)


def boost_speaker_volume() -> None:
    """Set the output sink's volume to 100% - call once at startup.

    Best-effort: the museum floor is noisy and a speaker left at whatever
    level the OS last had it doesn't reliably carry, so pin it to max
    rather than assuming it was left alone. Silently does nothing if
    wpctl/the sink isn't available."""
    try:
        subprocess.run(
            ["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", "1.0"],
            check=True, capture_output=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        print(f"[musebot] could not set speaker volume: {exc}")


def speak(text: str) -> None:
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        audio_path = f.name

    try:
        subprocess.run(
            [
                "edge-tts",
                "--voice", EDGE_TTS_VOICE,
                "--text", text,
                "--write-media", audio_path,
            ],
            check=True,
        )
        _play_audio(audio_path)
    finally:
        os.remove(audio_path)


# ---- STT (mic capture via SpeechRecognition, transcription via Groq Whisper) ----

# Pin the input device explicitly - "default"/pulse routing can pick a noisy
# or wrong device (see mic_check.py).
#
# The real mic is the USB webcam's built-in mic (Logitech C310, USB ID
# 046d:081b) - the separate "Baseus USB Audio" dongle is speaker-only in
# this build (see AUDIO_OUTPUT_DEVICE) and its input jack has nothing
# plugged into it, so recording from it just captures silence.
#
# Prefer MIC_DEVICE_NAME_MATCH (substring of the device name/identity, e.g.
# "046d:081b") over MIC_DEVICE_INDEX (a raw PortAudio index). PortAudio's
# index is just a position in enumeration order, which shifts whenever
# another USB audio device appears/disappears - confirmed on this rig, a
# number that pointed at the right device on one boot pointed at the wrong
# one on the next. Matching on the vendor:product ID instead of a name
# string or index survives reboots, replugs, and hub state changes, since
# it's the one identifier that doesn't depend on enumeration order or which
# port/hub something is plugged into. Run `python3 mic_check.py --list` to
# see current names/indices.
_MIC_DEVICE_INDEX_RAW = os.environ.get("MIC_DEVICE_INDEX")
MIC_DEVICE_INDEX = int(_MIC_DEVICE_INDEX_RAW) if _MIC_DEVICE_INDEX_RAW else None
MIC_DEVICE_NAME_MATCH = os.environ.get("MIC_DEVICE_NAME_MATCH")


def _resolve_mic_device_index(sr) -> Optional[int]:
    """Return the PyAudio device index to use, preferring a live name match.

    Re-resolved on every call rather than cached once at import time, since
    the whole point is to stay correct across reboots/replugs where the
    numeric index for the same physical mic can change."""
    if not MIC_DEVICE_NAME_MATCH:
        return MIC_DEVICE_INDEX

    pyaudio = sr.Microphone.get_pyaudio()
    p = pyaudio.PyAudio()
    try:
        for i in range(p.get_device_count()):
            info = p.get_device_info_by_index(i)
            if info["maxInputChannels"] > 0 and MIC_DEVICE_NAME_MATCH.lower() in info["name"].lower():
                return i
    finally:
        p.terminate()

    raise RuntimeError(
        f"no input device name matched MIC_DEVICE_NAME_MATCH={MIC_DEVICE_NAME_MATCH!r} "
        "(run `python3 mic_check.py --list` to see what's currently connected)"
    )

# PipeWire's own default input source can silently revert to a different
# device (e.g. the Baseus dongle's unused input jack) between sessions -
# it's re-asserted here on every listen rather than relying on it staying
# set from a one-off call. This is also what makes leaving
# MIC_DEVICE_NAME_MATCH/MIC_DEVICE_INDEX blank in .env the right move now
# that pipewire-alsa is installed: PortAudio's own "default" device routes
# through PipeWire instead of opening ALSA hardware directly, which is both
# what avoids racing WirePlumber for the node (see _open_microphone) *and*
# what makes this reassertion actually take effect - pinning a raw hw index
# instead would bypass PipeWire's routing entirely and make this a no-op.
#
# There's no PulseAudio daemon here, only pipewire-pulse - and its `pactl`
# CLI isn't installed, only `wpctl`, which needs a numeric object id rather
# than a name. `pw-dump` gives the full PipeWire object graph as JSON, so
# the id is looked up from MIC_PULSE_SOURCE_NAME (a node.name, find yours
# with `pw-dump | grep node.name` or `wpctl status`) on every call rather
# than cached, since that id isn't guaranteed stable across a PipeWire
# restart. Best-effort: silently does nothing if the tools aren't available
# or the name doesn't match a real source.
MIC_PULSE_SOURCE_NAME = os.environ.get("MIC_PULSE_SOURCE_NAME")


def _ensure_pulse_source() -> None:
    if not MIC_PULSE_SOURCE_NAME:
        return
    try:
        dump = subprocess.run(
            ["pw-dump"], check=True, capture_output=True, text=True, timeout=5,
        ).stdout
        for obj in json.loads(dump):
            props = ((obj.get("info") or {}).get("props")) or {}
            if props.get("media.class") != "Audio/Source":
                continue
            if props.get("node.name") == MIC_PULSE_SOURCE_NAME:
                subprocess.run(
                    ["wpctl", "set-default", str(obj["id"])],
                    check=True, capture_output=True,
                )
                return
    except (
        subprocess.CalledProcessError,
        subprocess.TimeoutExpired,
        FileNotFoundError,
        json.JSONDecodeError,
    ):
        pass


LISTEN_CUE_FREQUENCY_HZ = 880
LISTEN_CUE_DURATION_S = 0.35
LISTEN_CUE_VOLUME = 0.9


def _play_listen_cue() -> None:
    """Beep marking the exact moment capture starts - visitors (and
    testers) have no other way to know when it's their turn to talk."""
    sample_rate = 44100
    n_samples = int(sample_rate * LISTEN_CUE_DURATION_S)
    frames = b"".join(
        struct.pack(
            "<h",
            int(32767 * LISTEN_CUE_VOLUME * math.sin(2 * math.pi * LISTEN_CUE_FREQUENCY_HZ * t / sample_rate)),
        )
        for t in range(n_samples)
    )

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        cue_path = f.name
    try:
        with wave.open(cue_path, "w") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(frames)
        _play_audio(cue_path)
    finally:
        os.remove(cue_path)


MIC_OPEN_RETRIES = 8
MIC_OPEN_RETRY_DELAY_S = 1.5


def _open_microphone(sr):
    """Retries constructing sr.Microphone - PortAudio's device count can lag
    the real hardware for a second or two right after the service (re)starts
    (seen: the USB mic transiently missing from the count, raising
    AssertionError on a device_index that's valid a moment later), so one bad
    read here shouldn't be treated as fatal.

    Also retries past "Device or resource busy": PyAudio opens the raw ALSA
    hw device directly rather than going through PipeWire (there's no
    pipewire-alsa plugin installed on this rig - see AUDIO_OUTPUT_DEVICE's
    docstring for the same issue on the playback side, fixed there by using
    pw-play instead). That means it's racing WirePlumber, which also holds
    the webcam's audio node open/closed as it suspends and resumes it -
    reproduced live: the exact same `arecord -D hw:3,0` call failed with
    "Device or resource busy" once and succeeded two seconds later with
    nothing else changed. The proper fix is `sudo apt install pipewire-alsa`
    so ALSA opens get routed through the running PipeWire session instead of
    fighting it for the hardware - this retry loop is a mitigation, not a
    substitute for that."""
    last_exc: Optional[Exception] = None
    for attempt in range(1, MIC_OPEN_RETRIES + 1):
        try:
            return sr.Microphone(device_index=_resolve_mic_device_index(sr))
        except Exception as exc:
            last_exc = exc
            print(
                f"[booth_handler] mic open attempt {attempt}/{MIC_OPEN_RETRIES} "
                f"failed: {exc}",
                flush=True,
            )
            time.sleep(MIC_OPEN_RETRY_DELAY_S)
    raise last_exc


def listen_for_question(timeout_s: float = LISTEN_TIMEOUT_S) -> Optional[str]:
    # Imported lazily so code that only needs the other booth_handler
    # functions (e.g. test_chat.py's text-only mode) doesn't need
    # pyaudio/portaudio installed just to import this module.
    import speech_recognition as sr

    _ensure_pulse_source()
    recognizer = sr.Recognizer()
    recognizer.pause_threshold = PAUSE_THRESHOLD_S

    # Any failure here (mic never became available, device busy, etc.) is
    # treated the same as "visitor didn't say anything" rather than crashing
    # the whole tour - a systemd restart mid-tour was showing up as the
    # robot silently bailing all the way back to the welcome line instead of
    # just moving on to the next booth.
    try:
        with _open_microphone(sr) as source:
            recognizer.adjust_for_ambient_noise(source, duration=AMBIENT_NOISE_ADJUST_S)
            _play_listen_cue()
            print("[booth_handler] listening now - speak", flush=True)
            try:
                audio = recognizer.listen(source, timeout=timeout_s, phrase_time_limit=15)
            except sr.WaitTimeoutError:
                return None
    except Exception as exc:
        print(f"[booth_handler] could not capture a question this round: {exc}", flush=True)
        return None

    return _transcribe_with_whisper(audio.get_wav_data())


def _transcribe_with_whisper(wav_bytes: bytes) -> Optional[str]:
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY environment variable is not set")

    response = requests.post(
        GROQ_WHISPER_URL,
        headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
        files={"file": ("question.wav", wav_bytes, "audio/wav")},
        # Force the language - Whisper's auto-detect can misfire on short or
        # unclear clips (seen: a mumbled phrase transcribed as Japanese).
        data={"model": GROQ_WHISPER_MODEL, "language": GROQ_WHISPER_LANGUAGE},
        timeout=30,
    )
    try:
        response.raise_for_status()
    except requests.HTTPError:
        return None

    text = response.json().get("text", "").strip()
    return text or None


def is_exit_phrase(text: str) -> bool:
    # Exact match on the whole utterance, not a substring check - "no" would
    # otherwise match inside real questions like "does it have no arms?".
    lowered = text.lower().strip().strip(".!?,")
    return lowered in EXIT_PHRASES


# ---- LLM (switchable via LLM_PROVIDER: "google" or "groq") ----

def call_llm(
    messages: List[Dict[str, str]], max_tokens: int = 400, use_search: bool = False
) -> str:
    if LLM_PROVIDER == "groq":
        return _call_llm_groq_qwen(messages, max_tokens)
    if LLM_PROVIDER == "google":
        return _call_llm_google(messages, max_tokens, use_search=use_search)
    raise RuntimeError(
        f"Unknown LLM_PROVIDER={LLM_PROVIDER!r}, expected 'google' or 'groq'"
    )


def _call_llm_google(
    messages: List[Dict[str, str]], max_tokens: int, use_search: bool = False
) -> str:
    if not GOOGLE_API_KEY:
        raise RuntimeError("GOOGLE_API_KEY environment variable is not set")

    system_text, contents = _messages_to_gemini_payload(messages)
    body: Dict[str, Any] = {
        "contents": contents,
        "generationConfig": {"maxOutputTokens": max_tokens},
    }
    if system_text:
        body["system_instruction"] = {"parts": [{"text": system_text}]}
    if use_search:
        # Grounds the answer in live Google Search results instead of just
        # the model's frozen training data - this is what makes the
        # beyond-knowledgebase fallback actual internet research rather
        # than a guess from memory. Only supported by Gemini, not Groq/Qwen.
        body["tools"] = [{"google_search": {}}]

    response = requests.post(
        GOOGLE_URL_TEMPLATE.format(model=GOOGLE_MODEL),
        headers={"x-goog-api-key": GOOGLE_API_KEY, "Content-Type": "application/json"},
        json=body,
        timeout=20,
    )
    response.raise_for_status()
    data = response.json()
    return data["candidates"][0]["content"]["parts"][0]["text"].strip()


def _messages_to_gemini_payload(
    messages: List[Dict[str, str]]
) -> Tuple[str, List[Dict[str, Any]]]:
    """Split OpenAI-style messages into a Gemini system instruction + contents
    list. Gemini has no "system" role and calls the assistant role "model"."""
    system_parts: List[str] = []
    contents: List[Dict[str, Any]] = []
    for msg in messages:
        role = msg["role"]
        if role == "system":
            system_parts.append(msg["content"])
            continue
        gemini_role = "model" if role == "assistant" else "user"
        contents.append({"role": gemini_role, "parts": [{"text": msg["content"]}]})
    return "\n\n".join(system_parts), contents


def _call_llm_groq_qwen(messages: List[Dict[str, str]], max_tokens: int) -> str:
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY environment variable is not set")

    response = requests.post(
        GROQ_CHAT_URL,
        headers={
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": GROQ_QWEN_MODEL,
            "messages": messages,
            "max_tokens": max_tokens,
            # Qwen3 defaults to an extended <think> reasoning pass that can
            # burn the whole max_tokens budget before writing any visible
            # content, and isn't something we want spoken aloud anyway.
            "reasoning_effort": "none",
        },
        timeout=20,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"].strip()


# ---- Knowledgebase / Q&A log I/O ----

def load_knowledgebase(booth_id: int) -> Dict[str, Any]:
    path = DATA_DIR / f"knowledgebase{booth_id}.json"
    with open(path) as f:
        return json.load(f)


def load_combined_questions() -> List[Dict[str, Any]]:
    if not COMBINED_QUESTIONS_PATH.exists():
        return []
    with open(COMBINED_QUESTIONS_PATH) as f:
        return json.load(f)


def append_combined_question(entry: Dict[str, Any]) -> None:
    questions = load_combined_questions()
    questions.append(entry)
    with open(COMBINED_QUESTIONS_PATH, "w") as f:
        json.dump(questions, f, indent=2)


# ---- Keyword search over facts ----
#
# knowledgebase{N}.json's "facts" list stays small and hand-curated - it's
# what the spoken explainer always uses, so it needs to stay reviewable and
# bounded regardless of how big the Q&A corpus gets.
#
# For Q&A, drop a knowledgebase{N}_corpus.jsonl file next to
# knowledgebase{N}.json (one JSON object per line, {"text": "..."}) to add
# more facts - the distilled corpora here run up to ~6k facts per booth.
# At query time only the top-K facts that share the most words with the
# visitor's actual question are retrieved and put in the prompt, so prompt
# size (and cost/latency) stays flat regardless of corpus size. Plain word
# overlap over a few thousand short strings is fast enough to score fresh
# on every question - no precomputed index needed.

_STOPWORDS = frozenset((
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "do", "does", "did", "and", "or", "but", "if", "of", "on", "in", "to",
    "for", "with", "about", "as", "at", "by", "it", "its", "this", "that",
    "what", "when", "where", "who", "why", "how", "can", "could", "will",
    "would", "should", "have", "has", "had", "i", "you", "your", "my",
))

_WORD_RE = re.compile(r"[a-z0-9]+")


def _keywords(text: str) -> List[str]:
    return [w for w in _WORD_RE.findall(text.lower()) if w not in _STOPWORDS]


def _load_booth_corpus(booth_id: int) -> List[str]:
    """Every fact available for Q&A retrieval: the curated explainer facts
    plus the optional bulk corpus file, if one exists for this booth."""
    kb = load_knowledgebase(booth_id)
    texts = list(dict.fromkeys(kb.get("facts", [])))  # de-dup, keep order

    corpus_path = DATA_DIR / f"knowledgebase{booth_id}_corpus.jsonl"
    if corpus_path.exists():
        seen = set(texts)
        with open(corpus_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    text = json.loads(line)["text"]
                except (json.JSONDecodeError, KeyError, TypeError):
                    continue
                if text not in seen:
                    texts.append(text)
                    seen.add(text)
    return texts


def retrieve_relevant_facts(booth_id: int, query: str, top_k: int = 12) -> List[str]:
    """Top-K facts that share the most keywords with a visitor's question.
    Scored fresh every call - a few thousand short strings is cheap enough
    that no precomputed index is worth the complexity."""
    texts = _load_booth_corpus(booth_id)
    if not texts:
        return []

    query_words = set(_keywords(query))
    if not query_words:
        return texts[:top_k]

    scored = [
        (len(query_words & set(_keywords(text))), text) for text in texts
    ]
    scored = [pair for pair in scored if pair[0] > 0]
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [text for _, text in scored[:top_k]]


# ---- Context digests ----

def get_within_tour_digest(
    kb: Dict[str, Any], tour_id: str, questions: List[Dict[str, Any]], limit: int = 3
) -> List[Dict[str, Any]]:
    booth_themes = set(kb.get("themes", []))
    matches = [
        q for q in questions
        if q.get("tour_id") == tour_id and set(q.get("themes", [])) & booth_themes
    ]
    return matches[-limit:]


def get_cross_visitor_faq(
    booth_id: int, questions: List[Dict[str, Any]], top_n: int = 3
) -> List[Dict[str, Any]]:
    booth_questions = [q for q in questions if q.get("booth_id") == booth_id]
    if not booth_questions:
        return []

    theme_counts: Counter = Counter()
    for q in booth_questions:
        theme_counts.update(q.get("themes", []))

    top_themes = [theme for theme, _ in theme_counts.most_common(top_n)]

    faq = []
    for theme in top_themes:
        representative = next(
            (q for q in reversed(booth_questions) if theme in q.get("themes", [])),
            None,
        )
        if representative:
            faq.append(representative)
    return faq


def get_visited_booths_context(
    current_booth_id: int, tour_id: str, questions: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Every earlier booth in this same tour, with whatever this visitor
    asked there - so booth N's explainer/Q&A can draw real connections to
    booth 1..N-1 instead of treating each stop as an isolated island. Booths
    are always visited in ascending order (see musebot_lfr.ino's boothCount),
    so 1..current-1 is exactly "already seen this tour"."""
    visited = []
    for booth_id in range(1, current_booth_id):
        try:
            kb = load_knowledgebase(booth_id)
        except FileNotFoundError:
            continue
        booth_questions = [
            q for q in questions
            if q.get("tour_id") == tour_id and q.get("booth_id") == booth_id
        ]
        visited.append({
            "booth_id": booth_id,
            "title": kb.get("title"),
            "themes": kb.get("themes", []),
            "questions": booth_questions,
        })
    return visited


# ---- Prompt building ----

def _visited_booths_lines(visited_booths: List[Dict[str, Any]]) -> str:
    lines = []
    for v in visited_booths:
        lines.append(f"- Booth {v['booth_id']}: {v['title']} (themes: {', '.join(v['themes'])})")
        for q in v["questions"]:
            lines.append(f"    visitor asked: \"{q['question']}\" -> {q['answer']}")
    return "\n".join(lines)


def build_explainer_prompt(
    kb: Dict[str, Any],
    within_tour_digest: List[Dict[str, Any]],
    cross_visitor_faq: List[Dict[str, Any]],
    visited_booths: List[Dict[str, Any]],
) -> List[Dict[str, str]]:
    facts = "\n".join(f"- {fact}" for fact in kb.get("facts", []))
    context_parts = [f"Booth: {kb.get('title')}\nFacts:\n{facts}"]

    if within_tour_digest:
        digest_lines = "\n".join(
            f"- Q: {q['question']} A: {q['answer']}" for q in within_tour_digest
        )
        context_parts.append(
            "Earlier in this same tour, the visitor already asked about:\n"
            f"{digest_lines}\n"
            "Briefly reference this earlier context if it's relevant here, "
            "without repeating it in full."
        )

    if visited_booths:
        context_parts.append(
            "Earlier in this same tour, the visitor already saw these other "
            "exhibits:\n"
            f"{_visited_booths_lines(visited_booths)}\n"
            "This tour is one continuous story, not isolated stops - when a "
            "genuine connection exists (shared origin, shared purpose, a "
            "contrast worth pointing out, something they asked about "
            "before), draw it explicitly. Stay grounded in the facts given "
            "for each exhibit; don't invent a connection that isn't there."
        )

    if cross_visitor_faq:
        faq_lines = "\n".join(f"- {q['question']}" for q in cross_visitor_faq)
        context_parts.append(
            "Visitors at this booth frequently ask about:\n"
            f"{faq_lines}\n"
            "Proactively weave these points into the explainer so visitors "
            "don't need to ask."
        )

    context_parts.append(
        "Write the explainer for this booth now, 3-5 sentences, spoken aloud "
        "to a visitor standing in front of the exhibit. Pick whichever fact "
        "above is the most interesting hook and open with that, not "
        "necessarily the definition - save the plain \"what is it\" framing "
        "for later in the explainer if it's needed at all."
    )

    return [
        {"role": "system", "content": ROBOT_PERSONA},
        {"role": "user", "content": "\n\n".join(context_parts)},
    ]


def build_qa_prompt(
    question: str,
    kb: Dict[str, Any],
    relevant_facts: List[str],
    within_tour_digest: List[Dict[str, Any]],
    visited_booths: List[Dict[str, Any]],
) -> List[Dict[str, str]]:
    facts = "\n".join(f"- {fact}" for fact in relevant_facts)
    context_parts = [f"Booth: {kb.get('title')}\nFacts:\n{facts}"]

    if within_tour_digest:
        digest_lines = "\n".join(
            f"- Q: {q['question']} A: {q['answer']}" for q in within_tour_digest
        )
        context_parts.append(f"Earlier in this tour, the visitor also asked:\n{digest_lines}")

    if visited_booths:
        context_parts.append(
            "Earlier in this same tour, the visitor already saw these other "
            "exhibits (draw a connection only if genuinely relevant to "
            "their question):\n"
            f"{_visited_booths_lines(visited_booths)}"
        )

    context_parts.append(
        f'The visitor just said: "{question}"\n'
        "First decide whether this is an actual question about the "
        "exhibit, or whether the visitor is instead signaling they're "
        "done and want to move on - this can be phrased any number of "
        "ways (\"no more questions\", \"let's continue\", \"I think "
        "that's it\", \"we're good, keep going\", \"end tour\", a plain "
        "\"no\", etc.) - judge the intent of the whole sentence, not "
        "just whether it contains a specific keyword. If it's a wrap-up "
        "signal, set \"is_wrap_up\" to true and leave \"answer\" empty. "
        "Otherwise answer using only the facts listed above for this "
        "exhibit. If the question is only partly covered, answer the "
        "part you know directly and only briefly note what you don't - "
        "don't lead with a disclaimer when you have something relevant "
        "to say. Set \"covered\" to false only when none of the given "
        "facts are relevant to the question at all, in which case "
        "briefly say you don't have that information instead of "
        "guessing. Answer like you're actually talking to them, not "
        "reading a fact card - it's fine to react to the question itself "
        "(\"good question\", \"ah, that's a common one\", \"funny you ask\") "
        "when it genuinely fits, but don't force an opener onto every "
        "answer. "
        "Reply with a JSON object only, no other text, in this exact shape: "
        '{"is_wrap_up": true or false, '
        '"answer": "1-3 spoken sentences answering the question, or '
        'empty string if is_wrap_up is true", '
        '"themes": ["up to 3 short topic tags"], '
        '"covered": true or false}'
    )

    return [
        {"role": "system", "content": ROBOT_PERSONA},
        {"role": "user", "content": "\n\n".join(context_parts)},
    ]


def _parse_qa_response(
    raw: str, fallback_themes: List[str]
) -> Tuple[str, List[str], bool, bool]:
    try:
        data = json.loads(raw)
        return (
            data.get("answer", ""),
            data.get("themes") or fallback_themes,
            bool(data.get("covered", True)),
            bool(data.get("is_wrap_up", False)),
        )
    except (json.JSONDecodeError, KeyError, TypeError):
        return raw, fallback_themes, True, False


# ---- Learning beyond the knowledgebase ----

FETCH_PERSONA = (
    "You are a factual research assistant helping a museum exhibit expand "
    "its own knowledge base. Given the name of an exhibit and a visitor's "
    "question about it, research the answer and reply briefly and "
    "factually in 1-2 spoken-language sentences suitable for text-to-speech "
    "and for being saved as a permanent reference fact about this exhibit. "
    "If the question is not actually about this exhibit or its topic, or "
    "you cannot find a confident factual answer, respond with exactly: "
    "NOT_APPLICABLE"
)


def fetch_answer_beyond_knowledgebase(question: str, kb: Dict[str, Any]) -> Optional[str]:
    """Falls back to live internet research (Google Search grounding, when
    LLM_PROVIDER=google) when nothing in the given facts covers the
    question - otherwise falls back to the model's own general knowledge."""
    messages = [
        {"role": "system", "content": FETCH_PERSONA},
        {
            "role": "user",
            "content": (
                f"Exhibit: {kb.get('title')}\n"
                f"Known themes: {', '.join(kb.get('themes', []))}\n"
                f'Visitor question: "{question}"'
            ),
        },
    ]
    answer = call_llm(messages, max_tokens=150, use_search=True).strip()
    if not answer or answer.upper() == "NOT_APPLICABLE":
        return None
    return answer


def append_fact_to_knowledgebase(booth_id: int, fact: str) -> None:
    """Persists a newly learned fact so future questions are answered
    straight from the knowledgebase instead of fetching again."""
    path = DATA_DIR / f"knowledgebase{booth_id}.json"
    with open(path) as f:
        kb = json.load(f)
    if fact not in kb.get("facts", []):
        kb.setdefault("facts", []).append(fact)
        with open(path, "w") as f:
            json.dump(kb, f, indent=2)


# ---- Per-booth sequence ----

def run_booth_sequence(booth_id: int, tour_id: str) -> bool:
    kb = load_knowledgebase(booth_id)
    questions = load_combined_questions()

    within_tour_digest = get_within_tour_digest(kb, tour_id, questions)
    cross_visitor_faq = get_cross_visitor_faq(booth_id, questions)
    visited_booths = get_visited_booths_context(booth_id, tour_id, questions)

    explainer_prompt = build_explainer_prompt(
        kb, within_tour_digest, cross_visitor_faq, visited_booths
    )
    explainer_text = call_llm(explainer_prompt)
    speak(explainer_text)

    speak(ask_questions_prompt())

    while True:
        heard = listen_for_question()
        if heard is None or is_exit_phrase(heard):
            break

        relevant_facts = retrieve_relevant_facts(booth_id, heard)
        qa_prompt = build_qa_prompt(heard, kb, relevant_facts, within_tour_digest, visited_booths)
        raw_response = call_llm(qa_prompt)
        answer, themes, covered, wants_to_move_on = _parse_qa_response(
            raw_response, kb.get("themes", [])
        )

        if wants_to_move_on:
            break

        if not covered:
            fetched = fetch_answer_beyond_knowledgebase(heard, kb)
            if fetched:
                answer = fetched
                append_fact_to_knowledgebase(booth_id, fetched)
                kb = load_knowledgebase(booth_id)

        speak(answer)

        append_combined_question({
            "booth_id": booth_id,
            "question": heard,
            "answer": answer,
            "themes": themes,
            "tour_id": tour_id,
        })

        speak(ask_questions_prompt())

    is_final = bool(kb.get("final", False))
    if is_final:
        speak(CLOSING_LINE)

    return is_final
