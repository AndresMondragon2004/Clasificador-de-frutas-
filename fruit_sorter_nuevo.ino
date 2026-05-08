/*
 * Fruit Sorter — Arduino Uno (V4 - Optimized)
 *
 * Controla 2 servomotores + sensor láser VL53L0X (I2C)
 * Versión simplificada: Elimina la lógica de empuje del segundo servo.
 *
 * Protocolo serial (115200 baud):
 *   APPLE\n      → acciona servo 1 (manzana/izquierda)
 *   ORANGE\n     → acciona servo 2 (naranja/derecha)
 *   PING\n       → responde PONG
 *   GET_DISTANCE\n → responde con la distancia en cm (ej. "12.34")
 *
 * Responde OK\n tras ejecutar APPLE / ORANGE.
 */
#include <Servo.h>
#include "Adafruit_VL53L0X.h"

// === SENSOR LÁSER VL53L0X ===
Adafruit_VL53L0X sensor;

// === PINES ===
const int SERVO_LEFT_PIN   = 9;
const int SERVO_RIGHT_PIN  = 10;

// === SERVO: ángulos principales ===
const int NEUTRAL_ANGLE = 90;
const int LEFT_ANGLE    = 135;
const int RIGHT_ANGLE   = 45;
const int RETURN_DELAY  = 2500; // Tiempo que la compuerta permanece abierta

// === SENSOR: rango válido (en mm) ===
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

  // Alta precisión para lecturas consistentes
  sensor.configSensor(Adafruit_VL53L0X::VL53L0X_SENSE_HIGH_ACCURACY);

  servoLeft.attach(SERVO_LEFT_PIN);
  servoRight.attach(SERVO_RIGHT_PIN);
  
  // Posición inicial neutra
  servoLeft.write(NEUTRAL_ANGLE);
  servoRight.write(NEUTRAL_ANGLE);

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

// === SENSOR ===
float get_distance() {
  VL53L0X_RangingMeasurementData_t medicion;
  sensor.rangingTest(&medicion, false);

  if (medicion.RangeStatus == 4) return 999.0;

  int mm = medicion.RangeMilliMeter;
  if (mm < SENSOR_MIN_MM || mm > SENSOR_MAX_MM) return 999.0;

  return mm / 10.0;
}

// === COMANDOS ===
void processCommand(String command) {
  command.toUpperCase();

  if (command == "APPLE") {
    // Comando APPLE ahora solo mueve el servo izquierdo sin empujes extra
    servoLeft.write(LEFT_ANGLE);
    delay(RETURN_DELAY);
    servoLeft.write(NEUTRAL_ANGLE);
    Serial.println("OK");
  }
  else if (command == "ORANGE") {
    // Comando ORANGE ahora solo mueve el servo derecho sin empujes extra
    servoRight.write(RIGHT_ANGLE);
    delay(RETURN_DELAY);
    servoRight.write(NEUTRAL_ANGLE);
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
