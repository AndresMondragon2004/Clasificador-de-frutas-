import arduino
import time

print("Intentando conectar con Arduino...")
print(f"Puerto detectado/configurado: {arduino._auto_detect_port() or arduino.SERIAL_PORT}")

try:
    print("Enviando PING...")
    res = arduino.ping()
    print(f"Respuesta de PING: {res}")
    
    print("\nIniciando lectura de GET_DISTANCE...")
    for i in range(10):
        res = arduino.send_command("GET_DISTANCE")
        print(f"Lectura {i+1} RAW: {res}")
        time.sleep(0.5)
        
except Exception as e:
    print(f"Error fatal en python: {e}")
finally:
    arduino.close()
    print("Conexión cerrada.")
