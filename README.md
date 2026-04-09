<div align="center">

# Clasificador de Frutas con IA (Manzanas y Naranjas)

</div>



## Sobre el Proyecto

Este proyecto es un sistema de clasificación de frutas automatizado que utiliza **Inteligencia Artificial local** y hardware de código abierto. Combina el poder de los modelos de lenguaje visual (VLM) con la precisión de **Arduino** para crear una solución de clasificación física en tiempo real.

---

## Características Principales

- **Completamente Automático:** Operación continua ("endless loop") sin intervención manual una vez iniciado.
- **Inferencia Local:** Privacidad total y procesamiento local sin depender de la nube gracias a **LMStudio** y **Qwen3-VL**.
- **Hardware Accesible:** Diseñado con componentes compatibles con Arduino baratos y fáciles de encontrar.
- **Integración con MCP:** Listo para ser controlado como herramienta a través del protocolo FastMCP.

---

## Cómo funciona

1.  **Detección de Presencia:** Un sensor ultrasónico espera a que una fruta llegue a la posición de escaneo.
2.  **Captura de Imagen:** Una cámara web monitoriza el área de clasificación.
3.  **Visión Artificial Local:** Un servidor Python (**FastMCP**) captura la imagen y la envía a **LMStudio**, donde un modelo **Qwen3-VL** identifica si se trata de una manzana o una naranja.
4.  **Clasificación Física:** Tras la identificación, el servidor envía un comando serial al **Arduino Uno**, el cual acciona servomotores para desviar la fruta hacia el contenedor correspondiente.

---

## Tech Stack

<div align="center">

### IA & Visión
![LMStudio](https://img.shields.io/badge/LMStudio-v0.2.19-black?style=flat-square)
![Qwen3-VL](https://img.shields.io/badge/Model-Qwen3--VL--4b-9333EA?style=flat-square)
![OpenCV](https://img.shields.io/badge/OpenCV-4.x-5C3EE8?style=flat-square&logo=opencv&logoColor=white)

### Software
![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)
![FastMCP](https://img.shields.io/badge/FastMCP-Latest-orange?style=flat-square)
![PySerial](https://img.shields.io/badge/PySerial-3.5-yellow?style=flat-square)

### Hardware
![Arduino](https://img.shields.io/badge/Arduino_Uno-R3-00979D?style=flat-square&logo=arduino&logoColor=white)
![Servos](https://img.shields.io/badge/Servos-SG90-red?style=flat-square)
![Sensor](https://img.shields.io/badge/Sensor-HC--SR04-blue?style=flat-square)

</div>

---

## Estructura del Repositorio

- `server.py`: Servidor central en Python que conecta la IA con el hardware.
- `fruit_sorter.ino`: Código de Arduino para el control de los servomotores y sensor.

---

## Configuración Rápida

### 1. LMStudio
- Carga un modelo Vision (ej. `qwen/qwen3-vl-4b`).
- Inicia el servidor local en el puerto `1235`.

### 2. Arduino
- Carga `fruit_sorter.ino` en tu placa.
- **Pines:** 9 (Manzana), 10 (Naranja), 6 (Trig), 7 (Echo).

### 3. Python
- Instala dependencias:
  ```bash
  pip install fastmcp opencv-python pyserial requests
  ```
- Verifica el puerto serial en `server.py` (ej. `COM8`).
- Ejecuta el servidor:
  ```bash
  python server.py
  ```

---

## Uso con MCP

Este proyecto funciona como un servidor **MCP (Model Context Protocol)**. Puedes conectarlo a Claude Desktop o cualquier cliente compatible para controlar el clasificador mediante lenguaje natural.

---

<div align="center">

**Hecho por [Jesús Andrés Mondragón Tenorio](https://github.com/AndresMondragon2004)**

[![GitHub](https://img.shields.io/badge/GitHub-181717?style=for-the-badge&logo=github&logoColor=white)](https://github.com/AndresMondragon2004)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-0077B5?style=for-the-badge&logo=linkedin&logoColor=white)](https://www.linkedin.com/in/andres-mondragon-tenorio/)

</div>
