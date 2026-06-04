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
const int SENSOR_MIN_MM  = 30;
const int SENSOR_MAX_MM  = 130;

// === DEBOUNCE ===
// Número de lecturas consecutivas válidas requeridas para confirmar detección
const int DEBOUNCE_READS = 3;
const int DEBOUNCE_DELAY = 20; // ms entre lecturas de debounce

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

  // RangeStatus != 0 indica lectura no válida (4 = fuera de rango, otros = error)
  if (medicion.RangeStatus != 0) return 999.0;

  int mm = medicion.RangeMilliMeter;
  if (mm < SENSOR_MIN_MM || mm > SENSOR_MAX_MM) return 999.0;

  return mm / 10.0;
}

// Verifica con DEBOUNCE_READS lecturas consecutivas si hay un objeto presente
bool object_present_debounced(int threshold_mm) {
  int valid_count = 0;
  for (int i = 0; i < DEBOUNCE_READS; i++) {
    VL53L0X_RangingMeasurementData_t m;
    sensor.rangingTest(&m, false);
    if (m.RangeStatus == 0) {
      int mm = m.RangeMilliMeter;
      if (mm >= SENSOR_MIN_MM && mm <= threshold_mm) {
        valid_count++;
      } else {
        // Lectura fuera de rango — resetear contador
        valid_count = 0;
      }
    } else {
      valid_count = 0;
    }
    if (i < DEBOUNCE_READS - 1) delay(DEBOUNCE_DELAY);
  }
  return valid_count >= DEBOUNCE_READS;
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
  else if (command.startsWith("CHECK_OBJECT:")) {
    // CHECK_OBJECT:<threshold_mm>  → "PRESENT" o "ABSENT"
    int threshold_mm = command.substring(13).toInt();
    if (threshold_mm <= 0) threshold_mm = SENSOR_MAX_MM;
    bool present = object_present_debounced(threshold_mm);
    Serial.println(present ? "PRESENT" : "ABSENT");
  }
  else {
    Serial.println("ERROR:UNKNOWN_COMMAND");
  }
}
// Final version
