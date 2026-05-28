import serial
import time
import sys

# Cambia esto si el puerto es diferente
PUERTO = "COM5"
BAUD = 115200

print(f"=======================================")
print(f"🔍 INICIANDO DIAGNÓSTICO EN {PUERTO}")
print(f"=======================================\n")

try:
    print(f"1. Intentando abrir el puerto {PUERTO}...")
    s = serial.Serial(PUERTO, BAUD, timeout=2)
    print("✅ Puerto abierto con éxito. (El IDE de Arduino no lo está bloqueando).")
    
    print("\n2. Esperando 2 segundos para que el Arduino se reinicie...")
    time.sleep(2)
    
    # Limpiar cualquier basura de inicio (como el READY)
    s.reset_input_buffer()
    
    print("\n3. Solicitando lectura del láser (GET_DISTANCE)...")
    s.write(b"GET_DISTANCE\n")
    
    # Leer la respuesta
    respuesta_cruda = s.readline()
    print(f"Respuesta recibida (cruda en bytes): {respuesta_cruda}")
    
    respuesta_texto = respuesta_cruda.decode('utf-8', errors='ignore').strip()
    print(f"Respuesta decodificada (texto): '{respuesta_texto}'")
    
    if respuesta_texto == "":
        print("\n❌ ERROR: El Arduino no respondió nada. Puede que el código subido no sea el correcto (fruit_sorter_nuevo.ino) o los pines de comunicación estén fallando.")
    elif respuesta_texto == "999.00" or respuesta_texto == "999.0":
        print("\n⚠️ AVISO: El Arduino respondió 999.0. Esto significa que la comunicación es PERFECTA, pero el sensor no está detectando nada a menos de 13 cm de distancia.")
    else:
        try:
            dist = float(respuesta_texto)
            print(f"\n✅ ÉXITO ABSOLUTO: Comunicación perfecta. Distancia detectada: {dist} cm.")
            if dist < 13.0:
                print("🍎 Esta distancia es menor al umbral (13cm). El clasificador debería detectar la fruta sin problema.")
            else:
                print("📏 Ojo: La distancia es mayor a 13.0cm, acércalo más para que el clasificador lo valide.")
        except ValueError:
            print("\n❌ ERROR: El Arduino respondió texto que no es un número. ¿Seguro que está corriendo fruit_sorter_nuevo.ino y no el código de prueba anterior?")
            
    s.close()
    
except serial.SerialException as e:
    print(f"\n❌ ERROR FATAL DE PUERTO: {e}")
    print("\nPosibles causas:")
    print("1. El Monitor Serie del IDE de Arduino está abierto. CIÉRRALO.")
    print("2. El puerto COM5 no es el correcto para el Arduino.")
    print("3. El cable USB está fallando o desconectado.")
except Exception as e:
    print(f"\n❌ OTRO ERROR: {e}")

print("\nPresiona Enter para salir...")
input()
