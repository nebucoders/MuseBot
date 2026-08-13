// MuseBot AI - Arduino Uno
// Standalone combined test: drives both wheels forward continuously and
// stops only when BOTH FC-51 sensors read black (1,1) at once -- confirms
// the full "drive until tape" behavior end to end before trusting
// musebot_lfr.ino on the real track.
// Not part of the main musebot_lfr.ino build -- upload this standalone,
// confirm behavior, then re-upload musebot_lfr.ino for normal operation.

#include <Arduino.h>

// ---- Motor pins (TB6612FNG) -- must match musebot_lfr.ino ----
const uint8_t AIN1 = 2;
const uint8_t AIN2 = 3;
const uint8_t PWMA = 5;
const uint8_t BIN1 = 4;
const uint8_t BIN2 = 7;
const uint8_t PWMB = 6;
const uint8_t STBY = 8;

// ---- FC-51 IR sensor pins -- must match musebot_lfr.ino ----
const uint8_t LEFT_IR_PIN = 10;
const uint8_t RIGHT_IR_PIN = 11;

// Most FC-51 clones are active-LOW (OUT drops LOW when it detects a
// reflection). Flip if your sensor_test.ino results came out inverted.
const bool SENSOR_ACTIVE_LOW = true;

// Consecutive "both black" reads required before it counts as a real stop,
// so a single noisy/flickery read can't trigger a false stop mid-drive.
const uint8_t STOP_DEBOUNCE_READS = 3;

const uint8_t BASE_SPEED = 150;  // 0-255, matches musebot_lfr.ino

uint8_t stopDebounceCounter = 0;
bool stopped = false;

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
  Serial.println("driving forward...");
}

void loop() {
  if (stopped) {
    return;  // stays stopped forever -- re-upload to run the test again
  }

  bool leftOnTape = onLine(LEFT_IR_PIN);
  bool rightOnTape = onLine(RIGHT_IR_PIN);

  if (leftOnTape && rightOnTape) {
    stopDebounceCounter++;
  } else {
    stopDebounceCounter = 0;
  }

  if (stopDebounceCounter >= STOP_DEBOUNCE_READS) {
    stopMotors();
    stopped = true;
    Serial.println("STOPPED -- both sensors detected black");
    return;
  }

  driveMotor(AIN1, AIN2, PWMA, BASE_SPEED);
  driveMotor(BIN1, BIN2, PWMB, BASE_SPEED);
}

// True when the given FC-51 is over the dark line/tape (i.e. NOT reflecting
// IR back), false when it's over bare floor.
bool onLine(uint8_t pin) {
  bool raw = digitalRead(pin);
  bool objectDetected = SENSOR_ACTIVE_LOW ? (raw == LOW) : (raw == HIGH);
  return !objectDetected;
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
