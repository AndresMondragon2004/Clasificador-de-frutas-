/*
 * Fruit Sorter — Arduino Uno
 *
 * Controla 2 servomotores + sensor ultrasónico HC-SR04
 *
 * Protocolo serial (115200 baud):
 *   APPLE\n      → acciona servo 1 (manzana) + empuje con servo naranja
 *   ORANGE\n     → acciona servo 2 (naranja) + empuje con servo manzana
 *   PING\n         → responde PONG
 *   GET_DISTANCE\n → responde con la distancia en cm (ej. "12.34")
 *
 * Responde OK\n tras ejecutar APPLE / ORANGE.
 */
#include <Servo.h>

// === PINES ===
const int SERVO_APPLE_PIN  = 9;
const int SERVO_ORANGE_PIN = 10;
const int TRIG_PIN         = 6;
const int ECHO_PIN         = 7;

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

// === SENSOR: parámetros ===
// (sin umbral ni timeout — la lógica de detección vive ahora en Python)

Servo servoApple;
Servo servoOrange;
String inputBuffer = "";

void setup() {
  Serial.begin(115200);
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);

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
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);

  long duration = pulseIn(ECHO_PIN, HIGH, 30000);
  if (duration == 0) return 999.0;
  return (duration / 2.0) * 0.0343;
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
