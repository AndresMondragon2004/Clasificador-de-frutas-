/*
 * Fruit Sorter — Arduino Uno
 *
 * Controla 2 servomotores + sensor ultrasónico HC-SR04
 *
 * Protocolo serial (9600 baud):
 *   APPLE\n      → acciona servo 1 (manzana)
 *   ORANGE\n     → acciona servo 2 (naranja)
 *   PING\n       → responde PONG
 *   WAIT_FRUIT\n → espera hasta detectar objeto < umbral, responde DETECTED
 *                  o TIMEOUT si pasan 30 s sin detección
 *
 * Responde OK\n tras ejecutar APPLE / ORANGE.
 */

#include <Servo.h>

// === PINES ===
const int SERVO_APPLE_PIN  = 9;
const int SERVO_ORANGE_PIN = 10;
const int TRIG_PIN         = 6;
const int ECHO_PIN         = 7;

// === SERVO: ángulos ===
const int NEUTRAL_ANGLE = 90;
const int APPLE_ANGLE   = 45;
const int ORANGE_ANGLE  = 135;
const int RETURN_DELAY  = 3000;

// === SENSOR: parámetros ===
const float DETECT_THRESHOLD_CM = 10.0;  // Distancia mínima para considerar que hay fruta
const unsigned long WAIT_TIMEOUT_MS = 30000; // 30 s de timeout
const int POLL_INTERVAL_MS = 100;            // Medir cada 100 ms

Servo servoApple;
Servo servoOrange;
String inputBuffer = "";

void setup() {
  Serial.begin(9600);

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

float measureDistanceCm() {
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);

  long duration = pulseIn(ECHO_PIN, HIGH, 30000); // timeout 30 ms
  if (duration == 0) return 999.0; // sin eco = objeto muy lejos o error
  return (duration / 2.0) * 0.0343;
}

void waitForFruit() {
  unsigned long startTime = millis();

  while (millis() - startTime < WAIT_TIMEOUT_MS) {
    float dist = measureDistanceCm();

    if (dist > 0 && dist < DETECT_THRESHOLD_CM) {
      // Pequeña pausa para confirmar que no es ruido
      delay(80);
      float confirm = measureDistanceCm();
      if (confirm > 0 && confirm < DETECT_THRESHOLD_CM) {
        Serial.println("DETECTED");
        return;
      }
    }

    delay(POLL_INTERVAL_MS);
  }

  Serial.println("TIMEOUT");
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
  else if (command == "WAIT_FRUIT") {
    waitForFruit();
  }
  else {
    Serial.println("ERROR:UNKNOWN_COMMAND");
  }
}

void sortApple() {
  servoApple.write(APPLE_ANGLE);
  delay(RETURN_DELAY);
  servoApple.write(NEUTRAL_ANGLE);
}

void sortOrange() {
  servoOrange.write(ORANGE_ANGLE);
  delay(RETURN_DELAY);
  servoOrange.write(NEUTRAL_ANGLE);
}