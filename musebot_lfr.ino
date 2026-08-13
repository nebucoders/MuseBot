// MuseBot AI - Arduino Uno
// Straight-line drive + black-tape stop detection + serial state machine.
// Owns: FC-51 IR sensor reading, TB6612FNG motor drive, stop-tape detection, serial protocol.
// Does NOT own: AI, audio, network. Only reacts to "RESUME" and reports "BOOTH_REACHED:<id>".
// No line-following: the robot just drives straight until a sensor sees black
// tape. There is no steering correction, so it can't recover from drift --
// see "Straight-line accuracy" in README.md before relying on this on a long run.

#include <Arduino.h>
#include <string.h>

// ---- Motor pins (TB6612FNG) ----
const uint8_t AIN1 = 2;
const uint8_t AIN2 = 3;
const uint8_t PWMA = 5;
const uint8_t BIN1 = 4;
const uint8_t BIN2 = 7;
const uint8_t PWMB = 6;
const uint8_t STBY = 8;

// ---- FC-51 IR sensor pins ----
// No steering role anymore -- these exist purely to detect the black
// stop-tape marking each booth. Read as BOTH sensors seeing black (see
// checkStopTape()), so a stray reflection or one sensor drifting off the
// tape can't trigger a false stop -- the robot has to be squarely aligned.
const uint8_t LEFT_IR_PIN = 10;
const uint8_t RIGHT_IR_PIN = 11;

// FC-51's OUT pin is a comparator output: it goes active when the IR beam
// reflects back strongly, i.e. over light/reflective floor at close range.
// Black tape absorbs IR instead of reflecting it, so a sensor sitting over
// the line reads as "no object detected" -- the opposite of what you'd
// naively expect from something called a "line sensor". Most FC-51 clones
// are active-LOW (OUT drops LOW when an object/reflection is detected).
// Verify this on your actual boards with SENSOR_TEST_MODE below before
// trusting it -- flip to false if your readings come out inverted.
const bool SENSOR_ACTIVE_LOW = true;

// Set true, re-upload, open the Serial Monitor at 115200 baud, and wave the
// sensors over floor/tape to confirm wiring + SENSOR_ACTIVE_LOW before
// running the robot for real. Leave false for normal operation.
const bool SENSOR_TEST_MODE = false;

// Consecutive "sees black" reads required before it counts as a real stop,
// so a single noisy/flickery read can't trigger a false stop mid-drive.
const uint8_t STOP_DEBOUNCE_READS = 3;

// ---- Drive tuning ----
const uint8_t BASE_SPEED = 150;  // straight-line speed, 0-255

enum State { STATE_DRIVING, STATE_STOPPED };
// Starts stopped and waits for RESUME from the Pi, rather than driving off
// immediately on power-up/reset - the Pi sends RESUME only once the welcome
// line has finished speaking, so the robot never rolls before it's done talking.
State state = STATE_STOPPED;

uint16_t boothCount = 0;
uint8_t stopDebounceCounter = 0;

void setup() {
  Serial.begin(115200);

  pinMode(AIN1, OUTPUT);
  pinMode(AIN2, OUTPUT);
  pinMode(PWMA, OUTPUT);
  pinMode(BIN1, OUTPUT);
  pinMode(BIN2, OUTPUT);
  pinMode(PWMB, OUTPUT);
  pinMode(STBY, OUTPUT);
  digitalWrite(STBY, HIGH);

  pinMode(LEFT_IR_PIN, INPUT);
  pinMode(RIGHT_IR_PIN, INPUT);

  stopMotors();
}

void loop() {
  if (SENSOR_TEST_MODE) {
    testSensors();
    return;
  }

  handleSerial();

  if (state == STATE_DRIVING) {
    bool leftOnTape = onLine(LEFT_IR_PIN);
    bool rightOnTape = onLine(RIGHT_IR_PIN);

    if (checkStopTape(leftOnTape, rightOnTape)) {
      stopMotors();
      boothCount++;
      state = STATE_STOPPED;
      stopDebounceCounter = 0;
      Serial.print("BOOTH_REACHED:");
      Serial.println(boothCount);
      return;
    }

    driveStraight();
  }
  // STATE_STOPPED: motors already off, waiting for RESUME via handleSerial().
}

// True when the given FC-51 is over the dark line/tape (i.e. NOT reflecting
// IR back), false when it's over bare floor.
bool onLine(uint8_t pin) {
  bool raw = digitalRead(pin);
  bool objectDetected = SENSOR_ACTIVE_LOW ? (raw == LOW) : (raw == HIGH);
  return !objectDetected;
}

void testSensors() {
  Serial.print("LEFT raw=");
  Serial.print(digitalRead(LEFT_IR_PIN));
  Serial.print(" onLine=");
  Serial.print(onLine(LEFT_IR_PIN));
  Serial.print("   RIGHT raw=");
  Serial.print(digitalRead(RIGHT_IR_PIN));
  Serial.print(" onLine=");
  Serial.println(onLine(RIGHT_IR_PIN));
  delay(200);
}

bool checkStopTape(bool leftOnTape, bool rightOnTape) {
  if (leftOnTape && rightOnTape) {
    stopDebounceCounter++;
  } else {
    stopDebounceCounter = 0;
  }

  return stopDebounceCounter >= STOP_DEBOUNCE_READS;
}

void driveStraight() {
  driveMotor(AIN1, AIN2, PWMA, BASE_SPEED);
  driveMotor(BIN1, BIN2, PWMB, BASE_SPEED);
}

void driveMotor(uint8_t in1, uint8_t in2, uint8_t pwm, int16_t speed) {
  if (speed >= 0) {
    digitalWrite(in1, HIGH);
    digitalWrite(in2, LOW);
  } else {
    digitalWrite(in1, LOW);
    digitalWrite(in2, HIGH);
    speed = -speed;
  }
  analogWrite(pwm, speed);
}

void stopMotors() {
  digitalWrite(AIN1, LOW);
  digitalWrite(AIN2, LOW);
  digitalWrite(BIN1, LOW);
  digitalWrite(BIN2, LOW);
  analogWrite(PWMA, 0);
  analogWrite(PWMB, 0);
}

// Reads "RESUME\n" from the Pi over USB serial. Uses a static char buffer
// instead of the String class to avoid heap fragmentation over long uptimes.
void handleSerial() {
  static char buf[16];
  static uint8_t idx = 0;

  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\r') continue;
    if (c == '\n') {
      buf[idx] = '\0';
      if (strcmp(buf, "RESUME") == 0 && state == STATE_STOPPED) {
        state = STATE_DRIVING;
      }
      idx = 0;
    } else if (idx < sizeof(buf) - 1) {
      buf[idx++] = c;
    }
  }
}
