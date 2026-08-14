# MuseBot AI

**Team Nebucoders** — a bot made for WRO Future Innovators, a
museum guide robot built for the WRO Future Innovators
2026 season ("Robots Meet Culture"). It follows a taped line between exhibit booths,
stops at each one, explains the artifact out loud, and answers visitor
questions — getting more informative at each booth over the course of
the competition as it accumulates what past visitors have asked.

![MuseBot on the competition track](https://iili.io/CPURt9V.md.png))
<!--
  IMAGE: hero.jpg — main repo banner, shown at the top of the README.
  Wide shot of the finished robot on the taped track with a booth in
  frame. This is the single image most people will see first (repo
  preview, README top), so pick/generate the best one.
-->

## Table of contents

- [Why it's built this way](#why-its-built-this-way)
- [Hardware](#hardware)
- [Conversation flow](#conversation-flow)
- [Files](#files)
- [APIs / services](#apis--services)
- [Setup](#setup)
- [Transfer and test](#transfer-and-test)
- [Known open items](#known-open-items)
- [Images](#images)

## Why it's built this way

Early design passes considered QR-code scanning and camera-based object
detection to identify each booth. Both were dropped: too slow, and add a
vision pipeline for no real benefit when a robot moving along a fixed
track always encounters booths in the same order anyway. A perpendicular
tape stripe crossing the line is enough to mark a stop, detected by the
line sensors that already exist for line-following. Cheaper, faster, and
one less thing to get wrong on the day.

The system is split across two boards for the same reason a lot of hobby
robots are: line-following needs sub-5ms-consistent sensor reads and
motor timing, which a full Linux OS doing network calls and audio
playback cannot reliably guarantee. So:

- **Arduino Uno** — real-time control only. Reads the line sensor, drives
  the motors, detects the stop-tape, and reports over serial. No AI, no
  network, no audio. Originally an Arduino Nano; switched to Uno after
  repeated upload failures traced to the Nano's fragile Mini-USB port —
  the code and pin map didn't need to change, just the board.
- **Raspberry Pi 4B** — everything "smart": STT, LLM calls, TTS,
  knowledgebase lookup, the conversation loop, and Q&A memory. Talks to
  the Uno over a single USB cable (serial), nothing else.

![System architecture: Uno <-> Pi split](https://github.com/user-attachments/assets/c2f06efc-1cdd-4270-ac8b-336a1ca8f408)
<!--
  IMAGE: architecture.png — block diagram. Two boxes (Arduino Uno /
  Raspberry Pi 4B) connected by a labeled "USB serial, 115200 baud" arrow.
  Uno box lists: line sensors, motor driver, stop-tape detection. Pi box
  lists: STT, LLM, TTS, knowledgebase, Q&A memory. Could be AI-generated
  from a prompt describing this layout, or a clean hand-drawn diagram
  (draw.io / excalidraw export works well here).
-->

## Hardware

- Arduino Uno
- Raspberry Pi 4B + USB webcam (webcam is present but unused by the
  current conversation flow — no vision calls are made)
- TB6612FNG dual motor driver
- 2x 12V 300RPM geared DC motors with wheels
- 2x FC-51 IR obstacle/reflectance sensors (line sensing) — swapped in for
  the original QTR-8RC array; see below for why the pin map and
  line-following logic changed as a result
- USB mic + speaker (or USB webcam's built-in mic, if it has one)
- 12V battery, buck converter (12V → 5V), power switch, e-stop (wired in
  series on the positive lead, ahead of everything else)

![Full hardware parts laid out](https://github.com/user-attachments/assets/82c3b936-28d0-4ede-bf88-54f19e1951bd))
<!--
  IMAGE: hardware-parts.jpg — flat-lay photo of every component listed
  above, laid out on a table before assembly: Uno, Pi 4B, webcam,
  TB6612FNG, both DC motors, both FC-51 sensors, mic/speaker, battery,
  buck converter, switch, e-stop. Useful as a "parts list at a glance"
  reference photo. Take this before final assembly while everything is
  still separable.
-->

### Pin map (Uno)

```
Motor A (left):  AIN1->D2  AIN2->D3  PWMA->D5
Motor B (right): BIN1->D4  BIN2->D7  PWMB->D6
STBY -> D8
Left FC-51:  VCC->5V  GND->common GND  OUT->D10
Right FC-51: VCC->5V  GND->common GND  OUT->D11
Serial -> USB to Pi, 115200 baud
```

D2–D9 are claimed by the motor driver, so both FC-51s land on D10/D11 —
plain `digitalRead`, no analog pins needed (unlike the old QTR-8RC's
RC-charge trick), leaving A0–A5 free for anything added later.

![Uno wiring diagram](images/wiring-diagram.png)
<!--
  IMAGE: wiring-diagram.png — schematic/fritzing-style diagram matching
  the pin map above exactly: Uno with TB6612FNG, both DC motors, both
  FC-51 sensors, and the serial line to the Pi, each wire labeled with
  its pin name (AIN1, PWMA, D10, etc.). This is the one diagram worth
  getting pixel-accurate since people will wire directly from it —
  prefer a real Fritzing/KiCad export over an AI-generated illustration
  if precision matters more than polish.
-->

### FC-51 wiring and mounting

Each FC-51 has 3 pins: VCC, GND, OUT (a digital comparator output — not an
analog reading like the QTR-8RC gave). Mount both sensors on the front
underside of the chassis, facing straight down, 0.5–1.5cm above the floor
(exact height needs a pass on your actual floor/tape — start close and
back off if it never triggers). Space the two sensors apart so the taped
line normally runs *between* them — e.g. sensor centers ~20–25mm apart for
15–20mm tape — since the code assumes "neither sensor sees the line" is
the normal straight-driving state (see `musebot_lfr.ino`'s `followLine()`
comment). Each module has an onboard potentiometer; adjust it so the
onboard LED lights up reliably over the reflective floor and turns off
over the black tape, using `SENSOR_TEST_MODE` in the sketch to confirm on
the Serial Monitor before trusting it on the track.

FC-51 clones vary on whether OUT is active-LOW or active-HIGH when it
detects a reflection — the sketch defaults to active-LOW
(`SENSOR_ACTIVE_LOW = true`) as the most common wiring, but verify this on
your actual boards and flip it if needed (see "Testing" below).

**Two-sensor tradeoff:** the original QTR-8RC's 8-sensor weighted average
gave proportional steering and could tell "on track" apart from "line
lost entirely" (zero sensors active). With only 2 discrete digital
sensors, "neither active" means both "driving straight, line centered
between sensors" *and* "line lost completely" — the code can't tell them
apart, so there's no lost-line recovery behavior; if the robot overshoots
a curve badly enough to miss the line on both sensors, it just keeps
driving straight. Keep `BASE_SPEED` conservative and turns gentle on the
physical track to avoid this, or consider adding a 3rd (center) FC-51
later for a lost-line signal if this proves unreliable in testing.

![FC-51 sensor mounting close-up](images/fc51-mounting.jpg)
<!--
  IMAGE: fc51-mounting.jpg — close-up photo of the two FC-51 sensors
  mounted on the underside of the chassis, showing the spacing between
  them relative to a piece of the actual tape used for the track. Should
  make the ~20-25mm spacing described above visually obvious.
-->

### Power

```
Battery (+) -> Power switch -> E-stop -> splits to:
  - 12V direct -> TB6612FNG VM (motor power)
  - Buck converter -> 5V -> Pi 4B, Uno VIN (or Uno via USB from the Pi)
Battery (-) -> common GND (shared across battery, buck converter, Pi, Uno, driver)
```

VM (motor power, 12V) and VCC (driver logic, 5V) on the TB6612FNG are
separate pins — do not cross them, VCC max is 5.5V. STBY must be pulled
HIGH for the driver to run at all (handled in code, tied to D8).

![Power distribution diagram](images/power-diagram.png)
<!--
  IMAGE: power-diagram.png — simple flowchart matching the ASCII diagram
  above: battery -> switch -> e-stop -> splits into "12V to motor driver"
  and "buck converter -> 5V to Pi/Uno" branches, with the shared ground
  return path shown. A quick AI-generated or hand-drawn flowchart works
  fine here, precision matters less than for the wiring diagram above.
-->

## Conversation flow

1. Robot says "Welcome to the museum, please follow me" once, at tour start.
2. Uno line-follows until 6+ of 8 sensors go active for 3+ consecutive
   reads (a perpendicular tape stripe, as opposed to the 1-3 sensors a
   normal curve trips) — stops motors, sends `BOOTH_REACHED:<id>` to the Pi.
3. Pi loads `knowledgebase{id}.json`, builds a prompt (booth facts +
   within-tour context + cross-visitor FAQ), calls the LLM, TTS's the
   explainer, plays it.
4. Pi asks "Do you have any questions?", listens with a timeout.
5. Each question heard gets answered (LLM + TTS) and logged to
   `combined_questions.json`; loops back to asking until silence or an
   exit phrase ("no", "that's all", etc.).
6. Pi sends `RESUME`, Uno continues to the next booth. Repeats until a
   booth's knowledgebase has `"final": true`.

![Conversation flow diagram](images/conversation-flow.png)
<!--
  IMAGE: conversation-flow.png — flowchart/sequence diagram of the
  6 numbered steps above, ideally drawn as a loop (steps 3-6 repeat per
  booth, exiting the loop only when a booth's knowledgebase has
  final: true). A sequence diagram with two lanes (Uno / Pi) showing the
  BOOTH_REACHED / RESUME messages crossing between them would also work
  well and ties directly into the "Serial protocol" section below.
-->

Two feedback loops make the robot get smarter over time, not just react:

- **Within-tour digest** — questions this same visitor already asked at
  earlier booths (matched by `tour_id` + overlapping `themes`) get
  referenced briefly rather than re-explained.
- **Cross-visitor FAQ curation** — questions frequently asked at a given
  booth across *all* past tours (ignoring `tour_id`, grouped by theme
  frequency) get proactively woven into that booth's explainer, so
  common follow-ups migrate from "asked after" to "baked into the intro"
  as more visitors go through. `combined_questions.json` persists across
  restarts for this to work — it is never reset.

## Files

| File | Role |
|---|---|
| `musebot_lfr.ino` | Uno: line-follow (2x FC-51 IR sensors), stop-tape detection, serial state machine (`STATE_FOLLOWING` / `STATE_STOPPED`) |
| `musebot_main.py` | Pi: serial listener, tour lifecycle (tour_id, welcome line, booth loop, end-of-tour exit) |
| `musebot.service` | systemd user unit — symlink into `~/.config/systemd/user/` to run `musebot_main.py` on every boot (see "Pi: run on boot" below) |
| `booth_handler.py` | Pi: knowledgebase loading, within-tour/cross-visitor digest building, prompt building, LLM/TTS/STT calls |
| `knowledgebase_template.json` | Copy to `knowledgebase{N}.json` per booth and fill in |
| `knowledgebase{1,2,3}.json` | Per-booth title/facts/themes used to build prompts |
| `knowledgebase{1,2,3}_corpus.jsonl` | Distilled fact corpus per booth, searched by `retrieve_relevant_facts` for Q&A |
| `combined_questions.json` | Generated at runtime — running Q&A log, persists across tours (not included here; gitignored) |
| `test_chat.py` | Standalone LLM chat smoke test, no hardware needed |
| `mic_check.py` | Standalone mic/STT smoke test, no hardware needed |
| `motor_test/motor_test.ino` | Uno sketch: drive each motor independently to verify wiring/direction |
| `sensor_test/sensor_test.ino` | Uno sketch: print raw FC-51 reads to Serial Monitor |
| `combined_test/combined_test.ino` | Uno sketch: motors + sensors together, pre-integration check |

### Serial protocol

```
Uno -> Pi:  "BOOTH_REACHED:<id>\n"   (booth id increments locally on the Uno)
Pi  -> Uno: "RESUME\n"
```

## APIs / services

| Purpose | Provider | Model |
|---|---|---|
| Chat / explainer & Q&A generation | Google (default) or Groq — switch via `LLM_PROVIDER` | `gemini-2.5-flash-lite` / `qwen/qwen3-32b` |
| Text-to-speech | edge-tts (unofficial, Microsoft Edge voices) | `en-US-AriaNeural` |
| Speech-to-text | Groq | `whisper-large-v3-turbo` |

Env vars required: `GOOGLE_API_KEY` (chat only, if `LLM_PROVIDER=google`),
`GROQ_API_KEY` (STT always, chat if `LLM_PROVIDER=groq`). TTS needs no key
or account at all.

`LLM_PROVIDER` (`google` | `groq`, default `google`) switches the chat model
between Gemini Flash-Lite — cheap, high-volume, okayish reasoning, good
enough for short spoken answers — and Qwen served on Groq, as an alternate
cost/quality point to A/B against.

**Cost: $0.** LLM and STT are fractions of a cent per booth at this volume
on their respective free tiers. TTS runs through `edge-tts`, an unofficial
wrapper around Microsoft Edge's "Read Aloud" feature — free, no signup, no
quota, no GCP-style console setup. Tradeoff: it's not an officially
supported API, so Microsoft could change the underlying service without
notice; if `speak()` starts failing, that's the first thing to check.
Google Cloud TTS and OpenAI TTS were considered — both work but need a
paid-capable account and (for GCP) an API enabled in a cloud console,
which is more setup than this project needs. ElevenLabs was also
considered for more natural demo-day audio but is paid at this volume.

## Setup

```bash
pip install pyserial SpeechRecognition pyaudio requests edge-tts python-dotenv
sudo apt install portaudio19-dev mpg123   # portaudio for pyaudio/mic, mpg123 for TTS playback
cp .env.example .env   # then fill in GOOGLE_API_KEY / GROQ_API_KEY
```

`booth_handler.py` loads `.env` automatically on import (via `python-dotenv`),
so no need to `export` anything by hand. `.env` is gitignored — never commit
real keys. See `.env.example` for every field it reads.

Q&A over the corpus is a plain keyword-overlap search (`retrieve_relevant_facts`
in `booth_handler.py`) — no embedding model, no index to build, no laptop
transfer step. It re-scores each `knowledgebase{N}_corpus.jsonl` against the
visitor's question on the spot, which is fast enough at this corpus's
distilled size (thousands, not millions, of facts per booth).

Copy `knowledgebase_template.json` to `knowledgebase1.json`, `knowledgebase2.json`,
etc., filling in `title`, `facts`, and `themes` per booth. Mark the last
booth's file with `"final": true`.

> **Note on source data:** the `knowledgebase{N}_corpus.jsonl` files here are
> the distilled fact corpora the code actually reads. The much larger raw
> research dumps used to build them (per-artifact text files, tens to
> hundreds of MB each) are kept outside this repo — too large for a normal
> git push and not needed to run the code, only to regenerate the corpora.

## Transfer and test

### 1. Uno: upload and bench-test the sketch

1. Wire the 2x FC-51 sensors per the pin map above, TB6612FNG per the
   existing motor wiring — don't power the motors yet.
2. Open `musebot_lfr.ino` in Arduino IDE, select Board: **Arduino Uno** and
   the correct Port, and upload (this is the "transfer" step for the Uno —
   no separate copy/flash tool needed, the IDE does it over the same USB
   cable used later for serial).
3. Flip `SENSOR_TEST_MODE` to `true` in the sketch, re-upload, and open the
   Serial Monitor at 115200 baud. Move each FC-51 by hand between the
   floor and the tape and watch `onLine=` flip 0/1 as expected (0 over
   floor, 1 over tape). If both read backwards, flip `SENSOR_ACTIVE_LOW`
   and re-upload — don't skip this, it silently inverts every steering
   decision if wrong.
4. Set `SENSOR_TEST_MODE` back to `false`, re-upload. Prop the chassis up
   on blocks (wheels off the ground) and power the motors — confirm both
   wheels spin the correct direction under `followLine()` before setting
   it on the actual track.
5. On the real track: place the robot on the line and check it corrects
   drift smoothly (adjust `BASE_SPEED`/`TURN_SPEED` if it overcorrects or
   undercorrects) and stops cleanly at a perpendicular stop-tape strip
   (adjust `STOP_DEBOUNCE_READS` if it stops too eagerly/late).

![Robot on the track mid-run](images/track-test.jpg)
<!--
  IMAGE: track-test.jpg — action photo/GIF of the robot mid-line-follow
  on the actual competition-style track, ideally approaching or stopped
  at a stop-tape strip. Good candidate for a GIF instead of a static
  image if you have one, since this is an inherently motion-based test.
-->

### 2. Pi: transfer and run the conversation loop

1. Get the repo onto the Pi (`git clone`/`git pull` if it has network,
   otherwise `scp` the files over or copy via USB drive).
2. Run the `pip install`/`apt install`/`.env` steps above on the Pi itself.
3. Connect the Uno to the Pi via USB, confirm it enumerates as
   `/dev/ttyACM0` (`ls /dev/ttyACM*` — adjust `SERIAL_PORT` in
   `musebot_main.py` if it comes up as something else, e.g. `ttyUSB0`).
4. With at least `knowledgebase1.json` filled in, run
   `python3 musebot_main.py`. It should speak the welcome line, then wait.
5. Manually trigger a booth stop on the Uno (cross the stop-tape, or
   temporarily hardcode a stop in the sketch) and confirm the Pi prints
   `[musebot] booth reached: 1`, runs the explainer + Q&A, then prints
   `[musebot] sent RESUME` and the Uno resumes driving — that round trip
   is the full serial handshake working end-to-end.

### 3. Pi: run on boot (systemd)

`musebot_main.py` exits once a tour completes (`is_final: true` booth
reached), so for the robot to pick up the *next* visitor automatically it
needs to be relaunched, not looped internally. A user-level systemd
service with `Restart=always` does this: each exit gets restarted with a
fresh `tour_id`.

Run it as a **user** service, not system-level — mic/speaker access goes
through the logged-in user's PipeWire/PulseAudio session, which a system
service can't reach cleanly. Enable lingering so it still starts at boot
without a physical login:

```bash
sudo loginctl enable-linger $USER
mkdir -p ~/.config/systemd/user
```

The unit file is tracked in the repo as `musebot.service` — it hardcodes
this machine's absolute paths (repo dir, `.venv/bin` on `PATH` so
`edge-tts` resolves inside the service, same as `mpg123`/`aplay` from
`/usr/bin`), so re-generate it if the repo ever moves to a different path
or user. Symlink it in rather than copying, so future edits to the repo's
copy take effect after a `daemon-reload` without re-copying:

```bash
ln -sf "$(pwd)/musebot.service" ~/.config/systemd/user/musebot.service
systemctl --user daemon-reload
systemctl --user enable --now musebot.service
```

> **Note:** this `ln -sf` symlink is created on the *deployed Pi*, at run
> time, in `~/.config/systemd/user/` — it's how systemd expects user
> units to be installed and is unrelated to (and doesn't reintroduce) the
> repo-symlink issue this `github/` folder was created to avoid.

Check status and tail logs:

```bash
systemctl --user status musebot
journalctl --user -u musebot -f
```

To stop it autostarting later: `systemctl --user disable --now musebot`.

`After=network-online.target` makes the service wait for network on
boot, but the pipeline still needs a live connection to actually work —
see "Known open items" below for the mobile-hotspot fallback plan. If a
second USB-serial device ever gets plugged in, `/dev/ttyACM0` can shift
to `ttyACM1`; a udev rule pinning the Uno's vendor/product ID to a fixed
symlink is the fix if that becomes a problem in practice.

## Known open items

- **Timeout tuning** — 7s silence = "no more questions" is a starting
  guess; museum ambient noise may need it longer. Tune live.
- **FC-51 threshold/height and drive tuning** — each module's onboard
  potentiometer, sensor mounting height, and `BASE_SPEED`/`TURN_SPEED` in
  the `.ino` are all hardware-dependent and need a pass on the actual
  chassis/floor/tape (see "Transfer and test" above).
- **Lost-line recovery** — with only 2 discrete FC-51 sensors (down from
  the QTR-8RC's 8), the robot can't distinguish "centered on a straight
  line" from "missed the line entirely" — see the FC-51 tradeoff note
  under Hardware. Watch for this on sharp curves during testing.
- **Track layout** — competition table is 120x60cm; plan for at least
  one turn and 3-4 booth stops, spaced far enough apart that a turn
  can't be mistaken for a stop-tape by the debounce logic.
- **Venue connectivity** — the whole pipeline needs internet (Google/Groq
  APIs). Bring a mobile hotspot as backup and test real latency over it
  before competition day; consider a pre-recorded fallback line in case
  the connection drops mid-demo.
- **AI-use disclosure** — WRO Future Innovators rule 6.5 requires the
  team's written report to disclose which AI systems were used and for
  what (this repo's code and design were built with Claude). Not a
  violation, but needs to be stated explicitly in the report to avoid a
  scoring penalty.

## Images

All images referenced above live in `images/` and are **not included yet**
— this section is a shot list so photos (or AI-generated stand-ins/diagrams)
can be dropped in later without touching the README again. Save each file
under the exact name below and it'll pick up automatically.

| File | Type | Description |
|---|---|---|
| `images/hero.jpg` | Photo | Wide shot of the finished robot on the track, booth in frame. Top-of-README banner. |
| `images/architecture.png` | Diagram | Two-box block diagram: Uno vs Pi, responsibilities listed, serial link labeled between them. |
| `images/hardware-parts.jpg` | Photo | Flat-lay of every component in the Hardware list, before assembly. |
| `images/wiring-diagram.png` | Diagram | Precise schematic matching the Pin map table — prefer Fritzing/KiCad export over AI art here. |
| `images/fc51-mounting.jpg` | Photo | Close-up of both FC-51 sensors mounted underneath the chassis, showing spacing next to a piece of the track tape. |
| `images/power-diagram.png` | Diagram | Flowchart matching the Power section: battery → switch → e-stop → motor/logic split, shared ground return. |
| `images/conversation-flow.png` | Diagram | Flowchart or two-lane sequence diagram of the 6-step conversation loop, including the BOOTH_REACHED/RESUME handshake. |
| `images/track-test.jpg` | Photo/GIF | Robot mid-line-follow on the real track, ideally at a stop-tape strip. GIF preferred if available. |

Diagrams (`architecture.png`, `power-diagram.png`, `conversation-flow.png`)
are good candidates for AI generation since they're conceptual, not
precise — a prompt built from that row's description plus the relevant
section text above should be enough. `wiring-diagram.png` is the
exception: get it from a real schematic tool if possible, since people
will wire directly from it and small AI-art inaccuracies (wrong pin,
wrong wire color) are actively misleading there.
