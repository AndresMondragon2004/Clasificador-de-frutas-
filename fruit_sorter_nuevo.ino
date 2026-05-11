/*
 * Fruit Sorter — Arduino Uno
 * Servo Izquierdo (pin 9) → 75° inicial
 * Servo Derecho   (pin 11) → 90° inicial
 */

#include <Servo.h>
#include "Adafruit_VL53L0X.h"

// === SENSOR ===
Adafruit_VL53L0X sensor;

// === PINES ===
const int SERVO_LEFT_PIN  = 9;
const int SERVO_RIGHT_PIN = 11;

// === ÁNGULOS ===
const int INITIAL_LEFT  = 75;
const int INITIAL_RIGHT = 90;
const int APPLE_ANGLE   = 135;   // Abre compuerta izquierda
const int ORANGE_ANGLE  = 45;    // Abre compuerta derecha

const int RETURN_DELAY = 3000;   // ms que la compuerta permanece abierta

// === SENSOR ===
const int SENSOR_MIN_MM = 30;
const int SENSOR_MAX_MM = 130;

Servo servoLeft;
Servo servoRight;
String inputBuffer = "";

void setup() {
  Serial.begin(115200);

  if (!sensor.begin()) {
    Serial.println("ERROR:SENSOR_INIT");
    while (1);
  }

  // HIGH_SPEED: ~20ms por lectura
  sensor.configSensor(Adafruit_VL53L0X::VL53L0X_SENSE_HIGH_SPEED);

  servoLeft.attach(SERVO_LEFT_PIN);
  servoRight.attach(SERVO_RIGHT_PIN);

  servoLeft.write(INITIAL_LEFT);
  servoRight.write(INITIAL_RIGHT);

  Serial.println("READY");
}

void loop() {
  while (Serial.available() > 0) {
    char c = Serial.read();
    if (c == '\n') {
      inputBuffer.trim();
      processCommand(inputBuffer);
      inputBuffer = "";
    } else {
      inputBuffer += c;
    }
  }
}

float get_distance() {
  VL53L0X_RangingMeasurementData_t medicion;
  sensor.rangingTest(&medicion, false);

  if (medicion.RangeStatus == 4) return 999.0;

  int mm = medicion.RangeMilliMeter;
  if (mm < SENSOR_MIN_MM || mm > SENSOR_MAX_MM) return 999.0;

  return mm / 10.0;
}

void processCommand(String command) {
  command.toUpperCase();

  if (command == "APPLE") {
    servoLeft.write(APPLE_ANGLE);
    delay(RETURN_DELAY);
    servoLeft.write(INITIAL_LEFT);
    Serial.println("OK");
  }
  else if (command == "ORANGE") {
    servoRight.write(ORANGE_ANGLE);
    delay(RETURN_DELAY);
    servoRight.write(INITIAL_RIGHT);
    Serial.println("OK");
  }
  else if (command == "PING") {
    Serial.println("PONG");
  }
  else if (command == "GET_DISTANCE") {
    Serial.println(get_distance());
  }
  else {
    Serial.println("ERROR:UNKNOWN_COMMAND");
  }
}
