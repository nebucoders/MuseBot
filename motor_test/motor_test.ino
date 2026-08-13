// MuseBot AI - Arduino Uno
// Standalone motor test: cycles each wheel forward, then reverse, one at a
// time, then both together, printing what's running to the Serial Monitor.
// Prop the chassis on blocks (wheels off the ground -- this drives them for
// real) before running. A wiring mix-up shows up as "the wrong wheel spun"
// or "spun backwards" instead of confusing combined drift on the full robot.
// Not part of the main musebot_lfr.ino build -- upload this standalone,
// confirm wiring, then re-upload musebot_lfr.ino for normal operation.

#include <Arduino.h>

// ---- Motor pins (TB6612FNG) -- must match musebot_lfr.ino ----
const uint8_t AIN1 = 2;
const uint8_t AIN2 = 3;
const uint8_t PWMA = 5;
const uint8_t BIN1 = 4;
const uint8_t BIN2 = 7;
const uint8_t PWMB = 6;
const uint8_t STBY = 8;

const uint8_t TEST_SPEED = 150;  // 0-255, matches musebot_lfr.ino's BASE_SPEED

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

  stopMotors();
}

void loop() {
  Serial.println("LEFT forward");
  driveMotor(AIN1, AIN2, PWMA, TEST_SPEED);
  driveMotor(BIN1, BIN2, PWMB, 0);
  delay(1500);

  Serial.println("LEFT reverse");
  driveMotor(AIN1, AIN2, PWMA, -TEST_SPEED);
  driveMotor(BIN1, BIN2, PWMB, 0);
  delay(1500);

  Serial.println("RIGHT forward");
  driveMotor(AIN1, AIN2, PWMA, 0);
  driveMotor(BIN1, BIN2, PWMB, TEST_SPEED);
  delay(1500);

  Serial.println("RIGHT reverse");
  driveMotor(AIN1, AIN2, PWMA, 0);
  driveMotor(BIN1, BIN2, PWMB, -TEST_SPEED);
  delay(1500);

  Serial.println("BOTH forward (straight)");
  driveMotor(AIN1, AIN2, PWMA, TEST_SPEED);
  driveMotor(BIN1, BIN2, PWMB, TEST_SPEED);
  delay(1500);

  stopMotors();
  Serial.println("stopped -- pausing before repeat");
  delay(2000);
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
