/*
 * Fruit Sorter — Arduino Uno
 * 
 * Controla 2 servomotores para clasificar frutas:
 * - Servo 1 (Pin 9):  Manzana → gira 45° a la izquierda
 * - Servo 2 (Pin 10): Naranja → gira 45° a la derecha
 * 
 * Protocolo serial (9600 baud):
 *   APPLE\n   → acciona servo 1
 *   ORANGE\n  → acciona servo 2
 *   PING\n    → responde PONG (health check)
 * 
 * Responde OK\n tras ejecutar cada comando.
 */

#include <Servo.h>

// === CONFIGURACIÓN DE PINES ===
const int SERVO_APPLE_PIN  = 9;   // Servo para manzana
const int SERVO_ORANGE_PIN = 10;  // Servo para naranja

// === CONFIGURACIÓN DE MOVIMIENTO ===
const int NEUTRAL_ANGLE = 90;     // Posición neutral (centro)
const int APPLE_ANGLE   = 45;    // 90 - 45 = giro a la izquierda
const int ORANGE_ANGLE  = 135;   // 90 + 45 = giro a la derecha
const int RETURN_DELAY   = 3000; // 3 segundos antes de volver a neutral

// === OBJETOS SERVO ===
Servo servoApple;
Servo servoOrange;

// === BUFFER SERIAL ===
String inputBuffer = "";

void setup() {
  Serial.begin(9600);
  
  // Conectar servos a sus pines
  servoApple.attach(SERVO_APPLE_PIN);
  servoOrange.attach(SERVO_ORANGE_PIN);
  
  // Posición inicial: neutral (90°)
  servoApple.write(NEUTRAL_ANGLE);
  servoOrange.write(NEUTRAL_ANGLE);
  
  Serial.println("READY");
}

void loop() {
  // Leer datos del puerto serial
  while (Serial.available() > 0) {
    char c = Serial.read();
    
    if (c == '\n') {
      // Comando completo recibido
      inputBuffer.trim();
      processCommand(inputBuffer);
      inputBuffer = "";
    } else {
      inputBuffer += c;
    }
  }
}

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
  else {
    Serial.println("ERROR:UNKNOWN_COMMAND");
  }
}

void sortApple() {
  // Girar servo de manzana 45° a la izquierda
  servoApple.write(APPLE_ANGLE);
  
  // Esperar a que pase la fruta
  delay(RETURN_DELAY);
  
  // Regresar a posición neutral
  servoApple.write(NEUTRAL_ANGLE);
}

void sortOrange() {
  // Girar servo de naranja 45° a la derecha
  servoOrange.write(ORANGE_ANGLE);
  
  // Esperar a que pase la fruta
  delay(RETURN_DELAY);
  
  // Regresar a posición neutral
  servoOrange.write(NEUTRAL_ANGLE);
}
