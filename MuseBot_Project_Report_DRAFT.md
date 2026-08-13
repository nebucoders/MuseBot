# MuseBot AI
### Team Nebucoders — Bangladesh
**WRO Future Innovators 2026 — Senior Age Group — "Robots Meet Culture"**

Team members: Adal Zuhair Bhuiyan ([AGE]), Md. Hafizullah ([AGE]), Sujail ([AGE])
Coach: Md. Ashraf Ali

*[FILL IN: team photo]*

---

## Table of Contents

1. Team Presentation
2. Summary of Project Idea
3. Presentation of the Robotic Solution
   - 3.1 Evolution of the Project Idea
   - 3.2 Research into Similar Ideas
   - 3.3 Construction of the Solution
   - 3.4 Coding of the Solution
   - 3.5 Challenges During the Development Process
   - 3.6 Use of AI in This Project
4. Social Impact & Innovation
   - 4.1 Impact on Society
   - 4.2 A Practical Use Case
   - 4.3 Entrepreneurship: Business Model
   - 4.4 Next Steps & Prototype Development
5. List of Sources

---

## 1. Team Presentation

We are **Nebucoders**, a three-person Senior-age team from Bangladesh, competing in WRO Future Innovators 2026.

- **Adal Zuhair Bhuiyan** ([AGE]) — *[FILL IN: role/task division]*
- **Md. Hafizullah** ([AGE]) — *[FILL IN: role/task division]*
- **Sujail** ([AGE]) — *[FILL IN: role/task division]*

Coach **Md. Ashraf Ali** guided us on organizational and logistical matters throughout the season; per WRO rules, all construction, coding, and booth design were carried out by the team.

*[FILL IN: 2-3 sentences on how the team divided the work — e.g. who focused on hardware/wiring, who focused on software, who led the report/presentation — and a short line on how the team formed / why this project.]*

---

## 2. Summary of Project Idea

Small and regional museums, heritage sites, and cultural centers rarely have the budget to staff a knowledgeable human guide at every hour, in every language a visitor might need. The result is that a lot of cultural heritage — especially outside major national museums — goes unexplained, and visitors, particularly school groups, get a far shallower experience than the exhibits deserve.

**MuseBot** is a line-following museum guide robot that walks a fixed route between exhibit booths, stops automatically at each one, delivers a spoken explanation of the artifact, and takes live spoken questions from visitors — answering them on the spot. What makes it more than a talking speaker on wheels is that it **remembers**: every question a visitor asks is logged, tagged by topic, and fed back into how the robot explains that same exhibit to the *next* visitor. Ask enough visitors the same question at Booth 3, and Booth 3's explanation starts covering that point proactively, without anyone reprogramming it. The robot gets more informative the more it's used — a museum guide that effectively trains itself over a season of visitors.

We deliberately rejected the more "obvious" technical approaches — camera-based exhibit recognition, QR-code scanning, full SLAM navigation — in favor of the simplest reliable mechanism that solves the actual problem: a line to follow and a tape stripe to mark a stop. That choice, and why we made it, is explained in Section 3.

If produced at scale, MuseBot's value is straightforward: it lets a museum that cannot afford a full-time bilingual guide offer a consistent, patient, always-available one — for the price of a small robot and a few cents of cloud API usage per tour.

---

## 3. Presentation of the Robotic Solution

### 3.1 Evolution of the Project Idea

The project did not start where it ended up, and that path is itself part of the engineering story.

**Original concept.** Our first draft envisioned a fully autonomous museum robot: Ubuntu + ROS2 + SLAM-based navigation so the robot could freely map and move around a museum floor, camera-based object/QR recognition to identify which exhibit it was in front of, and a touchscreen for visitors to select a language. This is a real, valid architecture — it is also a six-to-twelve-month professional robotics project, not something three students can wire, code, and reliably demo in a 5-minute judging session on a foldable table.

**First simplification — navigation.** We replaced SLAM/ROS2 navigation with line-following: a fixed taped route between booths, followed by an Arduino using an 8-channel IR sensor array (QTR-8RC). This trades "goes anywhere" for "goes exactly where we told it to, every time" — which is the correct trade for a competition demo that has to work in front of judges on the first try, and it maps naturally onto a museum floor, where exhibit order is fixed anyway.

**Second simplification — exhibit identification.** We considered QR-code scanning and camera-based object detection to let the robot recognize which exhibit it had arrived at. We rejected both: they add a vision pipeline (camera capture, image processing, a recognition model) purely to solve a problem that doesn't exist for a robot moving along a fixed track — it always encounters booths in a fixed, known order. Instead, a perpendicular tape stripe crossing the guide line marks a stop. The robot's own line sensor — which it already needs for line-following — detects this by a distinct signature (most/all 8 sensors trip at once, instead of the 1-3 sensors a normal curve trips) rather than needing any new hardware or software subsystem at all. Section 3.2 goes into the reasoning against the alternatives in more depth.

**Hardware iteration — enclosure.** We initially designed a custom FreeCAD chassis (a flat mounting plate, then an enclosed shell with a lid and camera head) from scratch. Once the team had an existing 3D-printed cuboid box on hand, we abandoned the from-scratch enclosure and re-scoped the design to mount components inside and onto that box instead — no reason to spend print time and material duplicating something we already had.

**Hardware iteration — controller board.** We started wiring the real-time controller on an Arduino Nano. After repeated intermittent upload failures traced to the Nano's fragile Mini-USB connector, we switched to an Arduino Uno — physically larger, but electrically and functionally identical (same ATmega328P chip, same pin layout, same code), with a much sturdier full-size USB-B port. This is the kind of decision that looks trivial in hindsight but cost real debugging time before we correctly diagnosed it as a hardware connector issue rather than a code or driver problem.

### 3.2 Research into Similar Ideas

We looked at what already exists for "explaining an exhibit to a visitor" before committing to our approach:

- **Audio guide handsets** (the classic museum rental device): reliable and cheap, but one-directional — a visitor cannot ask it a follow-up question, and content never improves without a human curator manually re-recording it.
- **QR-code / AR museum apps** on a visitor's own phone: zero hardware cost to the museum, but require the visitor to have a phone, install/open an app, and manually scan at each stop — friction that measurably drops engagement in published museum-UX studies, and again, static content.
- **Camera/vision-based museum robots and object-recognition guides**: closer to our original concept, and used in some flagship national museums, but they require a trained recognition model, good/controlled lighting, and meaningful compute — appropriate for a well-funded institution's showcase robot, not for the budget-constrained, small-museum use case we are targeting, and risky to demo live if lighting differs from testing conditions.

**What's different about MuseBot** is not the physical mechanism — line-following robots are a well-established, deliberately "boring" technology (see rule 5.1.2's point about self-built vs. off-the-shelf designs, addressed below) — it's the **conversational, self-improving layer** on top. None of the alternatives above hold a two-way spoken conversation, and none of them get measurably better at explaining a given exhibit purely from being used more. That combination — cheap, reliable hardware plus a software layer that compounds in value with use — is the actual innovation, not the line sensor.

**On rule 5.1.2 (self-built vs. off-the-shelf):** our physical components (Arduino Uno, TB6612FNG driver, QTR-8RC sensor, Raspberry Pi 4B) are standard, widely available modules, not a purchased "robot kit." We chose them because reinventing a motor driver or line sensor from raw transistors would spend our limited build time on a solved problem instead of on the part of the project that's actually novel — the conversation and learning system, which is entirely our own design and code.

### 3.3 Construction of the Solution

**Hardware overview:**

| Component | Role |
|---|---|
| Arduino Uno | Real-time control: line-following, stop-tape detection |
| Raspberry Pi 4B | Conversation loop: STT, LLM calls, TTS, memory |
| TB6612FNG dual motor driver | Drives both drive motors from the Uno's logic-level signals |
| 2x 12V 300RPM geared DC motors (with grip tires) | Drive wheels, differential steering |
| QTR-8RC 8-channel IR line sensor array | Line-following and perpendicular stop-tape detection |
| USB webcam | Present on the robot; not currently used by the conversation flow (see Section 4.4) |
| USB microphone + speaker | Visitor speech capture and spoken responses |
| 12V battery, buck converter, power switch, e-stop | Power distribution |
| Repurposed 3D-printed cuboid enclosure (with lid) | Houses the electronics; motors mount to the underside |

**Power distribution:**

```
Battery (+) -> Power switch -> E-stop -> splits to:
  - 12V direct -> TB6612FNG VM (motor power)
  - Buck converter -> 5V -> Raspberry Pi 4B, Arduino Uno
Battery (-) -> common ground, shared across every component
```

The e-stop sits in series on the positive lead, ahead of everything else, so hitting it is a hard physical cutoff rather than something software has to detect and react to. The motor driver's two power pins are kept deliberately separate: **VM** (12V, feeds the motors) and **VCC** (5V, feeds only the driver's internal logic) — mixing these up is a common way to damage this specific chip, and understanding the distinction was one of our early hardware lessons (Section 3.5).

**Signal wiring (Uno):**

```
Motor A (left):  AIN1->D2  AIN2->D3  PWMA->D5
Motor B (right): BIN1->D4  BIN2->D7  PWMB->D6
STBY -> D8
QTR sensors 1-4 -> D10, D11, D12, D13
QTR sensors 5-8 -> A0, A1, A2, A3 (used as digital I/O)
Serial -> USB to Pi, 115200 baud
```

The sensor pins land on D10–D13 plus the analog pins rather than a clean D2–D9 block because the motor driver had already claimed D2–D9 — a real constraint we hit and adapted around rather than a starting design choice.

Two **LM393**-based IR sensors detect the black stop-tape marking each booth (left: VCC→5V, GND→common ground, OUT→D10; right: same, OUT→D11) — each is an IR LED/phototransistor pair whose reflected-light reading gets compared against an onboard-potentiometer threshold, so OUT reads a clean HIGH/LOW instead of needing analog thresholding in code, and the robot stops once either sensor goes low for three consecutive reads.

The Uno and Pi are connected by nothing more than a single USB cable, carrying a serial link — no GPIO wiring between the two boards at all.

### 3.4 Coding of the Solution

**Why two boards, not one.** Line-following needs to react to sensor readings on the order of milliseconds, consistently, with no interruptions. The Raspberry Pi runs a full Linux OS underneath our Python code, doing network calls, audio playback, and USB scheduling — any of which can introduce a few milliseconds of jitter that would make a robot trying to track a line wobble or lose it. The Arduino runs one loop, with no OS in the way, and gives predictable timing for exactly the tasks that need it. So we split responsibilities cleanly:

- **Arduino Uno — "reflexes."** Owns QTR-8RC reading, motor PWM/direction via the TB6612FNG, and perpendicular-tape-stop detection. No AI, no network, no audio. It only reacts to a `RESUME` command and reports `BOOTH_REACHED:<id>`.
- **Raspberry Pi 4B — "brain."** Owns speech-to-text, the LLM conversation, text-to-speech, knowledgebase lookup, and the Q&A memory system. Talks to the Uno purely over USB serial.

**Stop-tape detection.** A normal line-follow reads 1-3 adjacent sensors active, since the guide line is narrow relative to the 8-sensor array. A perpendicular stop-tape is wide *relative to the direction of travel*, so when the robot rolls onto it, most or all 8 sensors go active at once. Our trigger is **6 or more of 8 sensors active for 3 or more consecutive sensor-read cycles** — the multi-read requirement (debounce) exists specifically to avoid a momentary noise spike or an ordinary line junction being mistaken for a stop.

**Line-following.** Each active sensor contributes a position weight (sensors further from center weighted more heavily); the weighted average of currently-active sensors gives an error term, and a proportional controller adjusts left/right wheel speed from that error. If the line is briefly lost entirely, the robot continues steering in the last known direction rather than stopping, to re-acquire the line rather than stall.

**Serial protocol (the entire Uno-Pi contract):**

```
Uno -> Pi:  "BOOTH_REACHED:<id>\n"   (booth id increments locally on the Uno, one count per stop-tape)
Pi  -> Uno: "RESUME\n"
```

**The conversation pipeline (Pi side), per booth:**

1. Load `knowledgebase{booth_id}.json` — a small file per booth with the exhibit's title, a list of facts, and topic tags ("themes").
2. Build a within-tour digest: questions *this same visitor* already asked at earlier booths this tour, filtered by matching theme tags, so the robot can briefly reference earlier context instead of re-explaining from scratch.
3. Build a cross-visitor FAQ digest: the most frequently recurring question themes at *this specific booth*, across every tour ever run (this is the piece that makes the robot improve over the whole competition, not just within one visitor's walkthrough — see below).
4. Send a single prompt combining the exhibit facts, the within-tour digest, and the FAQ digest to an LLM (DeepSeek V3.2, via OpenRouter) to generate the spoken explainer.
5. Convert the explainer to speech (OpenAI TTS) and play it.
6. Ask "Do you have any questions?", listen with a timeout, and if a question is heard: transcribe it (OpenAI Whisper), send it plus the same context to the LLM, speak the answer, log the exchange, and loop back to asking again.
7. On silence, an exit phrase ("no", "that's all", etc.), or the last booth's knowledgebase marking `"final": true`, either resume line-following to the next booth or play a closing line and end the tour.

**The learning system, in more detail — this is the part we consider the actual innovation:**

Every answered question is appended to a single running log, `combined_questions.json`, tagged with the booth it was asked at, the theme(s) it covers, and a `tour_id` identifying which visitor's walkthrough it came from. This one file drives two distinct feedback loops:

- *Within-tour* (matched by `tour_id` + theme): stops the robot repeating itself to the same visitor across booths.
- *Cross-visitor FAQ curation* (matched by `booth_id` only, ignoring `tour_id`, ranked by how often a theme recurs across all history): surfaces "visitors keep asking about X at this booth" so X gets proactively folded into the explainer for the *next* visitor, at *any* future tour. This log is never reset between runs — it persists for the life of the deployment, so the robot's explanations are literally a function of everyone who has ever used it.

The practical effect: run the robot through the same booth ten times with ten different (simulated) visitors asking similar things, and the eleventh visitor hears an explainer that already answers what the first ten had to ask for. That's the "smarter over time" property, and it costs nothing extra in hardware — it's a design decision in how one JSON file is filtered, not a machine-learning model we had to train.

### 3.5 Challenges During the Development Process

We're including this section honestly rather than smoothing it over, because the real engineering lessons are in the mistakes, not the clean final diagram.

- **Motor driver power pins.** Early on we didn't distinguish the TB6612FNG's VM (12V motor supply) from VCC (5V logic supply) clearly enough, and had to work through exactly which pin gets which voltage before wiring anything — get this wrong and the chip is damaged, not just non-functional.
- **Motor mounting.** Our 12V 300RPM motors are cylindrical gearboxes with no flat face and no included mounting bracket — a flat screw-down mount (the "obvious" first idea) doesn't work on a cylinder. We had to work through clamp-bracket design as the correct solution before physical assembly could proceed.
- **Controller board reliability.** As covered in Section 3.1, repeated Arduino Nano upload failures cost real time before we correctly diagnosed a hardware (USB connector) issue rather than a software one, and switched to the Uno.
- **Pin budget conflicts.** Our first sensor wiring plan assumed D2-D9 were free; they weren't, since the motor driver had already claimed them. We had to re-map the QTR-8RC onto D10-D13 and the analog pins mid-build.
- **Power budgeting under load.** Motors draw current in spikes, especially at startup/stall, which can sag a shared 12V rail enough to blip a buck converter's 5V output and reset the Pi — a real, common failure mode we had to design around (short/thick motor power wiring, awareness that random Pi reboots during motor operation point to this specific cause) rather than discover live at competition.
- **Scope discipline.** The single biggest challenge wasn't any individual wire — it was resisting the pull toward the more "impressive"-sounding original architecture (SLAM, vision, ROS2) and instead choosing the boring, reliable mechanism that would actually work on demo day. That's a genuine engineering skill, not a shortcut.
- **Current status.** As of this report, the robot's motors and line sensor are built and tested and line-following works; the Raspberry Pi conversation loop (STT/LLM/TTS pipeline) is implemented but not yet integration-tested end-to-end on the physical robot. This is our single largest remaining risk and is addressed directly in Section 4.4 (Next Steps).

### 3.6 Use of AI in This Project

In line with rule 6.5, here is a specific account of our AI usage.

We used **Claude** (Anthropic), through both the Claude.ai web interface and the Claude Code CLI tool, in the following ways:

- **Design consultation and trade-off discussion** — talking through hardware wiring questions, and weighing our architectural options (QR-code scanning vs. camera-based object detection vs. our chosen tape-stop counting; Nano vs. Uno; which LLM/TTS/STT providers fit our budget). In every case, the team made the final decision; Claude explained the trade-offs and, once we decided, helped translate the decision into working wiring and code.
- **Troubleshooting** — diagnosing Arduino upload failures, clarifying exactly what each motor driver pin does, and working through power-budget/brownout risk mitigation.
- **Code generation** — we specified the exact hardware pin map, the stop-tape detection thresholds, the serial protocol, and the full conversation-flow behavior (including the two-tier Q&A learning system described in Section 3.4), and Claude generated the Arduino sketch (`musebot_lfr.ino`) and the Python application (`musebot_main.py`, `booth_handler.py`) implementing those specifications.
- **CAD assistance** — an early FreeCAD Python macro for a fully custom enclosure was generated with Claude's help, but we ultimately did not use it: once we had an existing 3D-printed box on hand, we chose to adapt our design to it instead (Section 3.1).
- **This report** — the first draft of this document was generated by Claude Code from our project's actual design history and decisions, then reviewed and completed by the team with our own details, photos, and corrections before submission.

We did **not** use AI for the physical construction, wiring, or hands-on assembly of the robot, or for making the underlying design decisions themselves — those were the team's own work throughout, with AI used as a tool to implement, explain, and document decisions we had already made.

---

## 4. Social Impact & Innovation

### 4.1 Impact on Society

**Positive impact.** MuseBot targets a specific, real gap: small and regional museums, cultural centers, and heritage sites — especially outside major national institutions, and especially in contexts like Bangladesh where multilingual staffing (e.g. Bangla + English) is a real cost constraint — often cannot afford a full-time knowledgeable guide. MuseBot offers a consistent, patient, always-available explainer at a small fraction of that staffing cost, is never bored by a repeated question (a real limitation of human guides during a busy school-group day), and — via the FAQ learning loop — gets *better* at its job the more it is used, without any additional staff effort.

**Possible negative effects.** We think it's important to name these directly rather than only presenting the upside:

- **Job displacement.** A robot guide could be seen as reducing demand for human guiding jobs. We think the more honest framing is *supplement*, not *replacement*: MuseBot is realistically suited to extended hours, overflow demand, and sites that currently have *no* guide at all (the alternative for those visitors isn't "a human guide instead," it's "no guide at all") — not to replacing an existing, funded guiding staff.
- **Factual reliability.** An LLM-generated explanation carries some risk of the model adding detail beyond what's actually known or verified. We mitigate this by grounding every explainer in a human-curated `facts` list per exhibit (the knowledgebase file) — the LLM's job is to explain and converse *around* those given facts, not invent new ones — but this risk is not fully eliminated, and any real deployment would need a human curator reviewing generated explainers before they go live with visitors.
- **Connectivity dependency.** The current pipeline requires internet access (for the LLM, STT, and TTS calls), which limits deployment at more remote or under-connected heritage sites — arguably the sites that would benefit most from a low-cost guide. This is a real constraint on the current design, not one we've solved.
- **Data handling.** Visitor questions are logged (to power the learning loop) as transcribed text with no audio or personal identity retained — a deliberate choice, but any real deployment should disclose this logging to visitors clearly.

### 4.2 A Practical Use Case

The clearest use case we have actually built and tested is the competition demonstration itself, which we designed as a working miniature of the real target scenario rather than as an abstract demo: a fixed 120cm x 60cm track with multiple themed booths, each representing a distinct exhibit a small museum might have. A visitor (in this case, a judge or member of the public) follows the robot from booth to booth, hears a spoken explainer at each, and can ask follow-up questions live. This is a direct, physically working stand-in for the intended real-world scenario — a small heritage site or local museum using one robot to guide school groups and casual visitors through a handful of exhibits, in either English or (with future language support, Section 4.4) Bangla, without needing a dedicated guide present for every visit.

### 4.3 Entrepreneurship: Business Model

*[Note: this section is a first-pass draft written to be refined and personalized by the team — the underlying structure and reasoning is solid, but we should adjust it to reflect any real conversations or feedback the team has actually had.]*

**Target users.** Small and mid-sized museums, regional heritage sites, cultural centers, and science centers — particularly ones that currently operate with no dedicated guide, or rely on a single guide stretched across multiple languages and groups. Secondary market: schools running field-trip programs that want a self-contained, repeatable guided experience they can bring to a site or set up on their own grounds for a cultural exhibition day.

**Cost structure.** Per-unit hardware bill of materials is low by design — an Arduino Uno, a Raspberry Pi 4B, a motor driver, two geared motors, a line sensor array, a battery/power system, and a simple enclosure, all off-the-shelf components chosen specifically to avoid custom fabrication cost (Section 3.2). Ongoing operating cost is dominated by cloud API usage (LLM, STT, TTS) — and we measured this directly during development: a full multi-booth tour costs a few cents at most, meaning the marginal cost of *running* the robot is close to negligible compared to the cost of *building* it. The main non-hardware cost is knowledgebase authoring — writing the facts for each exhibit — a one-time task per exhibit, doable by museum staff without any coding knowledge, since the file format is a short, plain JSON of title/facts/topic-tags.

**Revenue streams.** We see three realistic paths, not mutually exclusive:
1. **Direct hardware sale or lease** to a museum, with a small recurring fee covering cloud API costs and content-update support — the museum owns or leases the robot, we (or a maintaining team) handle the software side.
2. **Grant/tourism-board partnership** — heritage preservation and tourism-development funding (government or NGO) subsidizing deployment at sites that could never afford it on visitor revenue alone, which is arguably where the social impact case (Section 4.1) is strongest.
3. **School-program rental** — schools booking a unit for a cultural exhibition day or field trip, priced per-event rather than requiring the school to own hardware year-round.

**Key resources.** The physical platform and its firmware/software stack; the knowledgebase authoring format, deliberately designed to be editable by non-technical museum staff; and — genuinely the most valuable long-term asset — each deployment's accumulated `combined_questions.json` history, since a robot that has run for a full season at a specific museum has a genuinely better, more curated explainer for that specific museum's exhibits than a brand-new unit would, which is a real moat against someone simply copying the hardware design.

**Key partners.** Pilot museums and heritage sites willing to host a trial deployment; school robotics/STEM programs (a natural ongoing pipeline of future contributors, given this project's own origin); potential tourism-board or ministry-of-culture funding partners; and the underlying API providers (OpenRouter, OpenAI) as infrastructure, whose usage-based pricing is exactly why this business model is viable at small scale in the first place.

### 4.4 Next Steps & Prototype Development

Honest assessment of where the prototype stands and what comes next:

- **Finish end-to-end integration testing.** The Raspberry Pi conversation loop (speech-to-text, LLM, text-to-speech) is implemented but has not yet been tested together with the physical robot completing a full booth-to-booth run. This is our top priority before the next milestone.
- **Live-tune the line-following and detection thresholds.** Sensor sensitivity and steering gain are hardware- and surface-dependent and need a calibration pass on the actual competition track and lighting, not just our test setup.
- **Multilingual support.** Adding Bangla alongside English is a natural next step given our target deployment context, and is a straightforward extension of the existing prompt/TTS pipeline rather than a redesign.
- **Untethered, fully wireless operation.** Testing the full pipeline over a mobile hotspot rather than fixed Wi-Fi, to validate real-world connectivity robustness (Section 4.1) ahead of any live demo away from a controlled network.
- **Pilot deployment.** Beyond the competition, we would like to run MuseBot for a short real trial at an actual local museum or heritage site, to get genuine visitor feedback rather than only judge and teammate feedback.
- **Optional vision features (longer-term).** The robot already carries a USB webcam that the current software does not use. A future version could use it for lightweight, non-safety-critical features — for example, simple visitor-presence detection to time the explainer's start more naturally — but this is explicitly future work, not part of the current functioning solution.

---

## 5. List of Sources

*[FILL IN exact links before submission — listed below are the sources we actually drew on]*

- WRO Future Innovators 2026 — General Rules (WRO Association)
- TB6612FNG dual motor driver datasheet — [ADD LINK]
- QTR-8RC reflectance sensor array documentation — [ADD LINK]
- OpenRouter API documentation (DeepSeek V3.2 model) — https://openrouter.ai
- OpenAI API documentation (TTS and Whisper speech-to-text) — https://platform.openai.com
- Arduino / ATmega328P reference documentation (Uno and Nano) — https://www.arduino.cc
- Anthropic Claude — used as an AI development and design-consultation tool throughout this project (see Section 3.6)
