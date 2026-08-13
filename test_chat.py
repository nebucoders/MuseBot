#!/usr/bin/env python3
"""Standalone conversation tester - no Uno, no serial port required.

Talks to whichever chat model LLM_PROVIDER selects, round-trips through
speak() (edge-tts) for audio, and can take spoken input via listen_for_question()
(Groq Whisper) with --voice. Use this to sanity-check API keys and the
LLM_PROVIDER switch before running the full musebot_main.py loop on hardware.

Two modes:
  - Default: free-form chat, not grounded in any exhibit's knowledgebase.
  - --booth N: loads knowledgebase{N}.json and uses the real production
    explainer/Q&A prompts (build_explainer_prompt / build_qa_prompt), so you
    can test that the bot actually stays restricted to that exhibit's facts.
    When a question truly isn't covered, it falls back to the model's own
    general knowledge and permanently saves the answer as a new fact in
    knowledgebase{N}.json, so the same question is answered straight from
    the knowledgebase next time instead of fetching again.

Usage:
    python3 test_chat.py                # free-form chat, type to talk
    python3 test_chat.py --booth 1      # grounded Q&A for knowledgebase1.json
    python3 test_chat.py --booth 1 --voice     # speak your questions instead of typing
    python3 test_chat.py --booth 1 --no-speak  # text only, skips edge-tts/mpg123

Type "quit" or "exit" to stop.
"""

import argparse
import sys
from typing import Dict, List

from booth_handler import GROQ_API_KEY, GOOGLE_API_KEY, LLM_PROVIDER, ROBOT_PERSONA
from booth_handler import ask_questions_prompt
from booth_handler import call_llm, is_exit_phrase, listen_for_question, load_knowledgebase, speak
from booth_handler import build_explainer_prompt, build_qa_prompt, _parse_qa_response
from booth_handler import append_fact_to_knowledgebase, fetch_answer_beyond_knowledgebase
from booth_handler import retrieve_relevant_facts

TEST_PERSONA = (
    ROBOT_PERSONA
    + " This is a live test conversation, not a museum tour - just chat "
    "naturally and answer whatever the visitor (tester) says."
)


def check_keys() -> None:
    missing = []
    if LLM_PROVIDER == "google" and not GOOGLE_API_KEY:
        missing.append("GOOGLE_API_KEY")
    if LLM_PROVIDER == "groq" and not GROQ_API_KEY:
        missing.append("GROQ_API_KEY")
    if missing:
        print(f"[test_chat] missing env vars for LLM_PROVIDER={LLM_PROVIDER!r}: "
              f"{', '.join(missing)}", file=sys.stderr)
        sys.exit(1)


def get_input(voice: bool) -> str | None:
    if voice:
        heard = listen_for_question()
        if heard is None:
            print("[test_chat] (heard nothing, try again)")
            return None
        print(f"you: {heard}")
        return heard

    try:
        typed = input("you: ").strip()
    except EOFError:
        return "quit"
    return typed or None


def run_booth_test(booth_id: int, voice: bool, no_speak: bool) -> None:
    kb = load_knowledgebase(booth_id)
    print(f"[test_chat] booth {booth_id}: {kb.get('title')} - restricted to this "
          f"exhibit's knowledgebase - type 'quit' to stop")

    explainer = call_llm(build_explainer_prompt(kb, [], [], []))
    print(f"bot: {explainer}")
    if not no_speak:
        speak(explainer)

    prompt = ask_questions_prompt()
    print(f"bot: {prompt}")
    if not no_speak:
        speak(prompt)

    while True:
        question = get_input(voice)
        if question is None:
            continue
        if question.lower() in ("quit", "exit") or is_exit_phrase(question):
            break

        relevant_facts = retrieve_relevant_facts(booth_id, question)
        raw = call_llm(build_qa_prompt(question, kb, relevant_facts, [], []))
        answer, _themes, covered, wants_to_move_on = _parse_qa_response(raw, kb.get("themes", []))

        if wants_to_move_on:
            break

        if not covered:
            fetched = fetch_answer_beyond_knowledgebase(question, kb)
            if fetched:
                answer = fetched
                append_fact_to_knowledgebase(booth_id, fetched)
                kb = load_knowledgebase(booth_id)
                print(f"[test_chat] learned a new fact for booth {booth_id}")

        print(f"bot: {answer}")
        if not no_speak:
            speak(answer)

        prompt = ask_questions_prompt()
        print(f"bot: {prompt}")
        if not no_speak:
            speak(prompt)


def run_freeform_chat(voice: bool, no_speak: bool) -> None:
    print(f"[test_chat] LLM_PROVIDER={LLM_PROVIDER!r} - free-form, not "
          f"grounded in a knowledgebase - type 'quit' to stop")
    messages: List[Dict[str, str]] = [{"role": "system", "content": TEST_PERSONA}]

    while True:
        user_text = get_input(voice)
        if user_text is None:
            continue
        if user_text.lower() in ("quit", "exit"):
            break

        messages.append({"role": "user", "content": user_text})
        reply = call_llm(messages)
        messages.append({"role": "assistant", "content": reply})

        print(f"bot: {reply}")
        if not no_speak:
            speak(reply)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--booth", type=int, default=None,
                         help="test the restricted Q&A for knowledgebase{N}.json")
    parser.add_argument("--voice", action="store_true",
                         help="capture spoken input via microphone instead of typing")
    parser.add_argument("--no-speak", action="store_true",
                         help="skip TTS playback, print replies only")
    args = parser.parse_args()

    check_keys()

    if args.booth is not None:
        run_booth_test(args.booth, args.voice, args.no_speak)
    else:
        run_freeform_chat(args.voice, args.no_speak)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[test_chat] stopped")
