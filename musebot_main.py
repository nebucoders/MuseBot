#!/usr/bin/env python3
"""MuseBot AI - Raspberry Pi conversation loop + serial listener.

Owns: serial connection to the Uno, tour lifecycle (tour_id, welcome line,
booth-to-booth looping, end-of-tour exit). Delegates knowledgebase loading,
prompt building, and STT/LLM/TTS calls to booth_handler.py.
"""

import sys
from datetime import datetime

import serial

from booth_handler import boost_speaker_volume, speak, run_booth_sequence

SERIAL_PORT = "/dev/ttyACM0"
BAUD_RATE = 115200
SERIAL_TIMEOUT = 1  # seconds, passed to pyserial so readline() doesn't block forever

WELCOME_LINE = "Welcome to the museum, please follow me."


def make_tour_id() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def main() -> None:
    tour_id = make_tour_id()
    print(f"[musebot] starting tour {tour_id}")

    try:
        uno = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=SERIAL_TIMEOUT)
    except serial.SerialException as exc:
        print(f"[musebot] could not open {SERIAL_PORT}: {exc}", file=sys.stderr)
        sys.exit(1)

    boost_speaker_volume()
    speak(WELCOME_LINE)

    uno.write(b"RESUME\n")
    print("[musebot] welcome line done, sent RESUME to start driving")

    try:
        while True:
            raw = uno.readline()
            if not raw:
                continue  # read timed out with no data, keep waiting

            line = raw.decode(errors="ignore").strip()
            if not line.startswith("BOOTH_REACHED:"):
                continue

            try:
                booth_id = int(line.split(":", 1)[1])
            except (IndexError, ValueError):
                print(f"[musebot] malformed line from Uno: {line!r}", file=sys.stderr)
                continue

            print(f"[musebot] booth reached: {booth_id}")
            is_final = run_booth_sequence(booth_id, tour_id)

            if is_final:
                print("[musebot] tour complete, ending program")
                break

            uno.write(b"RESUME\n")
            print("[musebot] sent RESUME")
    finally:
        uno.close()


if __name__ == "__main__":
    main()
