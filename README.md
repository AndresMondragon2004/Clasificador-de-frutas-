# Fruit Sorter: AI-Powered Fruit Classifier (Apples & Oranges)

Este proyecto es un sistema de clasificación de frutas automatizado que utiliza Inteligencia Artificial local y hardware de código abierto. Combina el poder de los modelos de lenguaje visual (VLM) con la precisión de Arduino para crear una solución de clasificación física.

## Cómo funciona 

1.  **Captura de imagen:** Una cámara web monitoriza el área de clasificación.
2.  **Visión Artificial Local:** Un servidor Python (FastMCP) captura la imagen y la envía a **LMStudio**, donde un modelo **Qwen3-VL** identifica si se trata de una manzana o una naranja.
3.  **Clasificación Física:** Tras la identificación, el servidor envía un comando serial a un **Arduino Uno**, el cual acciona servomotores para desviar la fruta hacia el contenedor correspondiente.

## Tecnologías utilizadas

-   **Inteligencia Artificial:** [LMStudio](https://lmstudio.ai/) con el modelo `qwen3-vl-4b`.
-   **Software:**
    -   **Python 3.x**
    -   **FastMCP:** Para la creación del bridge de herramientas.
    -   **OpenCV:** Gestión de cámara y procesamiento de imagen.
    -   **Serial (PySerial):** Comunicación con hardware.
-   **Hardware:**
    -   **Arduino Uno**
    -   **Servomotores (2x)**: Para el mecanismo de desvío.
    -   **Cámara Web USB:** Para la visión.

## Estructura del repositorio

-   `server.py`: Servidor central en Python que conecta la IA con el hardware.
-   `fruit_sorter.ino`: Código de Arduino para el control de los servomotores.

## Configuración rápida

1.  **LMStudio:**
    -   Carga un modelo Vision (ej. `qwen3-vl-4b`).
    -   Inicia el servidor local en el puerto `1235`.
2.  **Arduino:**
    -   Carga `fruit_sorter.ino` en tu placa.
    -   Asegúrate de que los servos estén en los pines 9 (Manzanas) y 10 (Naranjas).
3.  **Python:**
    -   Instala dependencias: `pip install fastmcp opencv-python pyserial requests`.
    -   Verifica el puerto serial en `server.py` (ej. `COM8` o `/dev/ttyUSB0`).
    -   Ejecuta: `python server.py`.

## Uso con MCP

Este proyecto está diseñado para funcionar como un servidor **MCP (Model Context Protocol)**. Puedes conectarlo a Claude Desktop o cualquier cliente compatible para controlar el clasificador mediante lenguaje natural.

---
Mantenido por **Andrés**.
