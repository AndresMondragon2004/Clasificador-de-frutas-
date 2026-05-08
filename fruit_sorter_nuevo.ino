/*
 * Fruit Sorter — Arduino Uno
 *
 * Controla 2 servomotores + sensor láser VL53L0X (I2C)
 *
 * Protocolo serial (115200 baud):
 *   APPLE\n      → acciona servo 1 (manzana) + empuje con servo naranja
 *   ORANGE\n     → acciona servo 2 (naranja) + empuje con servo manzana
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
const int SERVO_APPLE_PIN  = 9;
const int SERVO_ORANGE_PIN = 10;
// Nota: el VL53L0X usa I2C (SDA = A4, SCL = A5 en Uno). No requiere pines digitales adicionales.

// === SERVO: ángulos principales ===
const int NEUTRAL_ANGLE = 90;
const int APPLE_ANGLE   = 135;
const int ORANGE_ANGLE  = 45;
const int RETURN_DELAY  = 3000;

// === SERVO: ángulos de empuje (pequeño desplazamiento desde neutro) ===
// El servo contrario hace un pequeño empuje hacia la fruta para ayudarla a rodar
const int PUSH_OFFSET       = 15;   // Grados de empuje (ajusta si necesitas más/menos fuerza)
const int PUSH_DELAY        = 400;  // ms que dura el empuje antes de volver a neutro
const int PUSH_START_DELAY  = 200;  // ms que espera tras abrir compuerta antes de empujar

// Dirección del empuje por servo:
// - Servo naranja empuja hacia manzana → desde neutro(90) sube hacia 135 → 90 + PUSH_OFFSET
// - Servo manzana empuja hacia naranja → desde neutro(90) baja hacia 45  → 90 - PUSH_OFFSET
const int ORANGE_PUSH_ANGLE = NEUTRAL_ANGLE + PUSH_OFFSET;  // 105°
const int APPLE_PUSH_ANGLE  = NEUTRAL_ANGLE - PUSH_OFFSET;  // 75°

// === SENSOR: rango válido (en mm para la librería, convertimos a cm al reportar) ===
// Detección máxima configurada en 13 cm (130 mm)
const int SENSOR_MIN_MM = 30;   // Mínimo: 3 cm — evita falsas lecturas muy cercanas
const int SENSOR_MAX_MM = 130;  // Máximo: 13 cm — rango de detección de la fruta

Servo servoApple;
Servo servoOrange;
String inputBuffer = "";

void setup() {
  Serial.begin(115200);

  if (!sensor.begin()) {
    Serial.println("ERROR:SENSOR_INIT");
    while (1);  // Detener si el sensor no responde
  }

  // Alta precisión para lecturas consistentes a corta distancia
  sensor.configSensor(Adafruit_VL53L0X::VL53L0X_SENSE_HIGH_ACCURACY);

  servoApple.attach(SERVO_APPLE_PIN);
  servoOrange.attach(SERVO_ORANGE_PIN);
  servoApple.write(NEUTRAL_ANGLE);
  servoOrange.write(NEUTRAL_ANGLE);

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

  // RangeStatus == 4 → lectura inválida / fuera de rango
  if (medicion.RangeStatus == 4) {
    return 999.0;
  }

  int mm = medicion.RangeMilliMeter;

  // Filtrar lecturas fuera del rango de trabajo
  if (mm < SENSOR_MIN_MM || mm > SENSOR_MAX_MM) {
    return 999.0;
  }

  // Convertir mm → cm con un decimal de precisión
  return mm / 10.0;
}

// === COMANDOS ===
void processCommand(String command) {
  command.toUpperCase();

  if (command == "APPLE") {
    sortApple();
    Serial.println("OK");
  }
  else if (command == "ORANGE") {
    sortOrange();
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

/*
 * sortApple:
 *   1. Abre compuerta manzana (APPLE_ANGLE)
 *   2. Espera PUSH_START_DELAY para que la compuerta esté abierta
 *   3. Servo naranja hace pequeño empuje (ORANGE_PUSH_ANGLE) para ayudar a rodar la fruta
 *   4. Servo naranja vuelve a neutro tras PUSH_DELAY
 *   5. Espera el resto de RETURN_DELAY y cierra compuerta manzana
 */
void sortApple() {
  servoApple.write(APPLE_ANGLE);                        // Abre compuerta manzana

  delay(PUSH_START_DELAY);                              // Espera a que esté abierta

  servoOrange.write(ORANGE_PUSH_ANGLE);                 // Empuje naranja → hacia manzana
  delay(PUSH_DELAY);                                    // Mantiene el empuje
  servoOrange.write(NEUTRAL_ANGLE);                     // Vuelve a neutro

  delay(RETURN_DELAY - PUSH_START_DELAY - PUSH_DELAY);  // Resta el tiempo ya usado
  servoApple.write(NEUTRAL_ANGLE);                      // Cierra compuerta manzana
}

/*
 * sortOrange:
 *   1. Abre compuerta naranja (ORANGE_ANGLE)
 *   2. Espera PUSH_START_DELAY para que la compuerta esté abierta
 *   3. Servo manzana hace pequeño empuje (APPLE_PUSH_ANGLE) para ayudar a rodar la fruta
 *   4. Servo manzana vuelve a neutro tras PUSH_DELAY
 *   5. Espera el resto de RETURN_DELAY y cierra compuerta naranja
 */
void sortOrange() {
  servoOrange.write(ORANGE_ANGLE);                      // Abre compuerta naranja

  delay(PUSH_START_DELAY);                              // Espera a que esté abierta

  servoApple.write(APPLE_PUSH_ANGLE);                   // Empuje manzana → hacia naranja
  delay(PUSH_DELAY);                                    // Mantiene el empuje
  servoApple.write(NEUTRAL_ANGLE);                      // Vuelve a neutro

  delay(RETURN_DELAY - PUSH_START_DELAY - PUSH_DELAY);  // Resta el tiempo ya usado
  servoOrange.write(NEUTRAL_ANGLE);                     // Cierra compuerta naranja
}
