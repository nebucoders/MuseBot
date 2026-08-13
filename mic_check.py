#!/usr/bin/env python3
"""Standalone mic diagnostic - run this directly, not through test_chat.py.

Lists input devices, shows which one speech_recognition picks by default,
and records a few seconds so you can see (not just hear) whether your voice
is actually reaching the mic as a signal.

Usage:
    python3 mic_check.py                # use default input device
    python3 mic_check.py --list         # just list devices and exit
    python3 mic_check.py --device 4     # force a specific device index
"""

import argparse
import audioop

import pyaudio
import speech_recognition as sr


def list_devices() -> None:
    p = pyaudio.PyAudio()
    try:
        try:
            default = p.get_default_input_device_info()
            print(f"PortAudio default input: [{default['index']}] {default['name']}")
        except Exception as exc:
            print(f"PortAudio has no default input device: {exc}")
        print("\nAll input-capable devices:")
        for i in range(p.get_device_count()):
            info = p.get_device_info_by_index(i)
            if info["maxInputChannels"] > 0:
                print(f"  [{i}] {info['name']}  (channels={info['maxInputChannels']}, "
                      f"rate={int(info['defaultSampleRate'])})")
    finally:
        p.terminate()


def record_and_measure(device_index: int | None, seconds: int = 4) -> None:
    recognizer = sr.Recognizer()
    with sr.Microphone(device_index=device_index) as source:
        print(f"Using device: {source.device_index if source.device_index is not None else 'system default'}")
        print(f"Sample rate: {source.SAMPLE_RATE}, sample width: {source.SAMPLE_WIDTH}")

        print("Calibrating ambient noise for 1s - stay quiet...")
        recognizer.adjust_for_ambient_noise(source, duration=1)
        print(f"energy_threshold after calibration: {recognizer.energy_threshold:.0f}")
        print("(for reference: a quiet room is usually under ~500-1000; "
              "anything in the thousands means high background noise or "
              "the wrong device is being picked up)")

        print(f"\nRecording {seconds}s now - talk normally, at a normal distance...")
        frames = source.stream.read(int(source.SAMPLE_RATE * seconds))
        rms = audioop.rms(frames, source.SAMPLE_WIDTH)
        print(f"RMS amplitude of what was captured: {rms}")
        print("(silence/no mic signal is usually under ~100-300; normal speech "
              "at a normal distance is typically several thousand or more)")

        if rms < 300:
            print("\n-> Looks like little or no signal reached this device. "
                  "Try --list to see other devices, then --device <index> to "
                  "pick your real mic explicitly.")
        elif rms < recognizer.energy_threshold:
            print(f"\n-> Signal was captured (RMS {rms}) but it's BELOW the "
                  f"calibrated energy_threshold ({recognizer.energy_threshold:.0f}), "
                  "which is why speech_recognition's listen() would treat this "
                  "as silence and time out. Speak louder/closer, or the ambient "
                  "noise in the room is too high for the default threshold.")
        else:
            print("\n-> Signal look fine and above threshold - listen_for_question() "
                  "should be able to detect phrase start here.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true", help="list input devices and exit")
    parser.add_argument("--device", type=int, default=None, help="force a specific input device index")
    parser.add_argument("--seconds", type=int, default=4, help="how long to record for the RMS test")
    args = parser.parse_args()

    list_devices()
    if args.list:
        return

    print()
    record_and_measure(args.device, args.seconds)


if __name__ == "__main__":
    main()
