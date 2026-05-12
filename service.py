#!/usr/bin/env python3
"""
service.py — Autonomous fruit sorting loop (Agentic Architecture V4+).

Orchestrates the pipeline: sensor detection → image capture →
LLM agent decides and sorts. 

Now with improved aesthetics, fruit name identification, 
and camera buffer stabilization.
"""

import argparse
import signal
import sys
import time
from datetime import datetime

import arduino
import camera
import llm

# === ANSI COLORS ===
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
CYAN = "\033[96m"
WHITE = "\033[97m"
MAGENTA = "\033[95m"
BG_GREEN = "\033[42m"
BG_BLUE = "\033[44m"
BG_RED = "\033[41m"


def c(color: str, text: str) -> str:
    return f"{color}{text}{RESET}"


def banner(title: str, color: str = CYAN) -> None:
    width = 60
    print(f"\n{color}{'━' * width}{RESET}")
    print(f"{BOLD}{color}  {title}{RESET}")
    print(f"{color}{'━' * width}{RESET}\n")


def timestamp() -> str:
    return datetime.now().strftime("%H:%M:%S")


def log(msg: str, color: str = WHITE) -> None:
    print(f"{DIM}[{timestamp()}]{RESET} {color}{msg}{RESET}")


def print_result_box(status: str) -> None:
    """Prints a beautiful summary box for the sorting result."""
    # Status format expected: SUCCESS:FruitName:Direction or DISCARD:Reason
    parts = status.split(":")
    
    print("\n" + " " * 4 + "┏" + "━" * 50 + "┓")
    
    if parts[0] == "SUCCESS" and len(parts) >= 3:
        fruit = parts[1]
        direction = parts[2]
        icon = "🍎" if direction == "LEFT" else "🍊"
        color_bg = BG_GREEN if direction == "LEFT" else BG_BLUE
        
        print(" " * 4 + "┃" + f"  {icon}  {BOLD}{WHITE}FRUTA CLASIFICADA{RESET}".center(58) + "┃")
        print(" " * 4 + "┃" + f"  {BOLD}IDENTIFICADO:{RESET} {c(YELLOW, fruit.upper())}".center(58) + "┃")
        print(" " * 4 + "┃" + f"  {BOLD}ACCIÓN:{RESET} {color_bg}{WHITE} MOVER A {direction} {RESET}".center(67) + "┃")
    
    elif parts[0] == "DISCARD":
        reason = parts[1] if len(parts) > 1 else "No reconocido"
        print(" " * 4 + "┃" + f"  ⚠️  {BOLD}{WHITE}OBJETO DESCARTADO{RESET}".center(58) + "┃")
        print(" " * 4 + "┃" + f"  {BOLD}MOTIVO:{RESET} {c(RED, reason)}".center(58) + "┃")
    
    else:
        # Handling for error strings or unexpected formats
        print(" " * 4 + "┃" + f"  ❌  {BOLD}{RED}RESULTADO NO RECONOCIDO{RESET}".center(58) + "┃")
        print(" " * 4 + "┃" + f"  {status[:46]}...".center(50) + "┃")

    print(" " * 4 + "┗" + "━" * 50 + "┛\n")


# === STATE ===
_running = False
_stats = {"cycles": 0, "sorted": 0, "discarded": 0}

# === AGENT MESSAGE HANDLER ===

def _on_agent_message(role: str, content: str) -> None:
    """Log messages from the LLM agent during .act() execution."""
    if role == "tool":
        # Extract function name from something like "sort_to_left({'fruit_name': 'Apple'})"
        tool_name = content.split("(")[0]
        log(f"  🔧 IA activando: {c(YELLOW, tool_name)}", BLUE)
    elif role == "assistant" and content:
        # Limit assistant text to avoid clutter
        log(f"  🤖 IA pensando: {c(DIM, content[:75])}...", MAGENTA)


# === MAIN SORTING LOOP ===

def sorting_loop(threshold_cm: float = 13.0) -> None:
    global _running
    log("🟢 Iniciando hardware y verificando IA...", GREEN)
    
    if not llm.test_connection():
        log("❌ Error: No se pudo conectar a LMStudio (¿Server iniciado?)", RED)
        return

    log("🚀 Sistema de clasificación en marcha.", BOLD + BLUE)

    while _running:
        _stats["cycles"] += 1
        cycle = _stats["cycles"]

        log(f"🔍 Ciclo {cycle}: Esperando fruta en el sensor...", DIM)

        # 1. Bloquear hasta detectar fruta
        result = arduino.wait_for_fruit(threshold_cm=threshold_cm, timeout_seconds=30)
        
        # In this version of arduino.py, result might have different keys
        detected = result.get("detected") or result.get("success")
        dist = result.get("distance_cm") or result.get("distance")

        if not detected:
            log(f"⏳ Ciclo {cycle}: Tiempo agotado sin detección.", YELLOW)
            continue

        log(f"📦 Ciclo {cycle}: ¡Fruta detectada a {dist}cm!", GREEN)
        
        # 2. ESTABILIZACIÓN: Muy importante para el buffer de cámara y exposición
        time.sleep(0.6)
        
        log(f"📷 Ciclo {cycle}: Capturando imagen...", CYAN)
        
        img_b64 = camera.get_camera_data()
        if not img_b64:
            log("❌ Error al capturar imagen de la cámara.", RED)
            continue

        # 3. Llamar al Agente
        log(f"🧠 Ciclo {cycle}: Analizando con IA (V4+)...", MAGENTA)
        agent_status = llm.act_on_fruit(img_b64, on_message=_on_agent_message)
        
        # 4. Mostrar resultado estético
        print_result_box(agent_status)
        
        if agent_status.startswith("SUCCESS"):
            _stats["sorted"] += 1
            # Darle tiempo al Arduino para terminar el movimiento físico
            time.sleep(3.0)
        else:
            _stats["discarded"] += 1
            time.sleep(1.0)


# === CONFIG DISPLAY ===

def _print_config() -> None:
    banner("🍓 Fruit Sorter V4+ — Agentic Runner", color=GREEN)
    print(f"  {BOLD}Puerto Serial{RESET} : {c(CYAN, arduino.SERIAL_PORT or 'AUTO-DETECT')}")
    print(f"  {BOLD}Comunicación {RESET} : {c(CYAN, 'HTTP (OpenAI standard)')}")
    print(f"  {BOLD}API Key      {RESET} : {c(YELLOW, llm.LMSTUDIO_API_KEY)}")
    print(f"  {BOLD}Modelo       {RESET} : {c(CYAN, llm.LMSTUDIO_MODEL)}")
    print(f"  {BOLD}Cámara Index {RESET} : {c(CYAN, str(camera.CAMERA_INDEX))}")
    print(f"\n  {c(DIM, 'Presiona Ctrl+C para detener el sistema de forma segura.')}\n")


def signal_handler(sig, frame):
    global _running
    print(f"\n\n{YELLOW}🛑 Deteniendo sistema y liberando recursos...{RESET}")
    _running = False
    camera.close()
    arduino.close()
    sys.exit(0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=str, help="Serial port")
    parser.add_argument("--camera", type=int, default=0, help="Camera index")
    parser.add_argument("--threshold", type=float, default=13.0, help="Sensor threshold in cm")
    args = parser.parse_args()

    signal.signal(signal.SIGINT, signal_handler)
    _running = True

    # Override defaults if args provided
    if args.port: arduino.SERIAL_PORT = args.port
    camera.CAMERA_INDEX = args.camera
    
    _print_config()
    
    try:
        sorting_loop(threshold_cm=args.threshold)
    except Exception as e:
        log(f"💥 Error crítico en el loop: {e}", RED)
    finally:
        camera.close()
        arduino.close()
