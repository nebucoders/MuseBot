// MuseBot AI - Arduino Uno
// Standalone IR sensor test: reads both FC-51 modules continuously and
// prints raw pin state + interpreted onLine() reading, so wiring and
// SENSOR_ACTIVE_LOW polarity can be confirmed before trusting them on the
// track. Wave a hand or the black tape under each sensor and watch the
// values flip.
// Not part of the main musebot_lfr.ino build -- upload this standalone,
// confirm sensors, then re-upload musebot_lfr.ino for normal operation.

#include <Arduino.h>

// ---- FC-51 IR sensor pins -- must match musebot_lfr.ino ----
const uint8_t LEFT_IR_PIN = 10;
const uint8_t RIGHT_IR_PIN = 11;

// Most FC-51 clones are active-LOW (OUT drops LOW when it detects a
// reflection). If onLine reads backwards below (1 over floor, 0 over tape),
// flip this to false and re-upload -- see musebot_lfr.ino for the full
// explanation of why "on tape" means "no reflection detected".
const bool SENSOR_ACTIVE_LOW = true;

void setup() {
  Serial.begin(115200);
  pinMode(LEFT_IR_PIN, INPUT);
  pinMode(RIGHT_IR_PIN, INPUT);
}

void loop() {
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

// True when the given FC-51 is over the dark line/tape (i.e. NOT reflecting
// IR back), false when it's over bare floor.
bool onLine(uint8_t pin) {
  bool raw = digitalRead(pin);
  bool objectDetected = SENSOR_ACTIVE_LOW ? (raw == LOW) : (raw == HIGH);
  return !objectDetected;
}
