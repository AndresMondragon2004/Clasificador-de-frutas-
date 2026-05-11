#!/usr/bin/env python3
"""
service.py — Autonomous fruit sorting loop (Agentic Architecture V4+).

Orchestrates the pipeline: sensor detection → image capture →
LLM agent decides (via requests) and sorts. 

Now with improved aesthetics and fruit name identification.
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
    # Status format: SUCCESS:FruitName:Direction or DISCARD:Reason
    parts = status.split(":")

    print("\n" + " " * 4 + "┏" + "━" * 50 + "┓")

    if parts[0] == "SUCCESS":
        direction = parts[2] if len(parts) > 2 else "LEFT"
        fruit = "MANZANA" if direction == "LEFT" else "NARANJA"
        icon = "🍎" if direction == "LEFT" else "🍊"
        color_bg = BG_GREEN if direction == "LEFT" else BG_BLUE

        print(" " * 4 + "┃" + f"  {icon}  {BOLD}{WHITE}FRUTA CLASIFICADA{RESET}".center(58) + "┃")
        print(" " * 4 + "┃" + f"  {BOLD}IDENTIFICADO:{RESET} {c(YELLOW, fruit)}".center(58) + "┃")
        print(" " * 4 + "┃" + f"  {BOLD}ACCIÓN:{RESET} {color_bg}{WHITE} MOVER A {direction} {RESET}".center(67) + "┃")

    elif parts[0] == "DISCARD":
        print(" " * 4 + "┃" + f"  ⚠️  {BOLD}{WHITE}OBJETO DESCARTADO{RESET}".center(58) + "┃")
        print(" " * 4 + "┃" + f"  {BOLD}MOTIVO:{RESET} {c(RED, parts[1])}".center(58) + "┃")

    else:
        print(" " * 4 + "┃" + f"  ❌  {BOLD}{RED}ERROR DE AGENTE{RESET}".center(58) + "┃")
        print(" " * 4 + "┃" + f"  {status[:46]}...".center(50) + "┃")

    print(" " * 4 + "┗" + "━" * 50 + "┛\n")


# === STATE ===
_running = False
_stats = {
    "cycles": 0, 
    "apples": 0, 
    "oranges": 0, 
    "discarded": 0
}

# === DASHBOARD ===

def print_dashboard() -> None:
    """Prints a live dashboard with current statistics."""
    total = _stats["apples"] + _stats["oranges"] + _stats["discarded"]
    
    # Simple bar chart logic
    def bar(val, total_val):
        if total_val == 0: return ""
        length = int((val / total_val) * 20)
        return "█" * length

    print(f"\n{BOLD}{CYAN}📊 DASHBOARD DE RENDIMIENTO{RESET}")
    print(f"┏━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━┓")
    print(f"┃ {BOLD}Categoría{RESET}          ┃ {BOLD}Cantidad{RESET}   ┃ {BOLD}Distribución{RESET}         ┃")
    print(f"┣━━━━━━━━━━━━━━━━━━━━╋━━━━━━━━━━━━╋━━━━━━━━━━━━━━━━━━━━━━┫")
    print(f"┃ 🍎 Manzanas         ┃ {c(GREEN, str(_stats['apples']).ljust(10))} ┃ {c(GREEN, bar(_stats['apples'], total).ljust(20))} ┃")
    print(f"┃ 🍊 Naranjas         ┃ {c(YELLOW, str(_stats['oranges']).ljust(10))} ┃ {c(YELLOW, bar(_stats['oranges'], total).ljust(20))} ┃")
    print(f"┃ ⚠️  Descartados      ┃ {c(RED, str(_stats['discarded']).ljust(10))} ┃ {c(RED, bar(_stats['discarded'], total).ljust(20))} ┃")
    print(f"┣━━━━━━━━━━━━━━━━━━━━╋━━━━━━━━━━━━╋━━━━━━━━━━━━━━━━━━━━━━┫")
    print(f"┃ {BOLD}TOTAL{RESET}              ┃ {c(WHITE, str(total).ljust(10))} ┃ {BOLD}Ciclos:{RESET} {c(CYAN, str(_stats['cycles']).ljust(12))} ┃")
    print(f"┗━━━━━━━━━━━━━━━━━━━━┻━━━━━━━━━━━━┻━━━━━━━━━━━━━━━━━━━━━━┛\n")


# === AGENT MESSAGE HANDLER ===

def _on_agent_message(role: str, content: str) -> None:
    """Log messages from the LLM agent during .act() execution."""
    if role == "tool":
        tool_name = content.split("(")[0]
        log(f"  🔧 IA → {c(YELLOW, tool_name)}", BLUE)


# === MAIN SORTING LOOP ===

def sorting_loop(threshold_cm: float = 13.0) -> None:
    global _running
    log("🟢 Iniciando hardware y verificando IA...", GREEN)
    
    # Test connection inside the loop start to show the dashboard faster
    if not llm.test_connection():
        log("❌ Error: No se pudo conectar a LMStudio (¿Server iniciado?)", RED)
        return

    log("✅ Conexión con IA establecida.", GREEN)
    log("🚀 Sistema de clasificación en marcha.", BOLD + BLUE)

    while _running:
        _stats["cycles"] += 1
        cycle = _stats["cycles"]

        try:
            log(f"🔍 Ciclo {cycle}: Esperando fruta...", DIM)

            result = arduino.wait_for_fruit(threshold_cm=threshold_cm, timeout_seconds=30)

            if not result["detected"]:
                log(f"⏳ Ciclo {cycle}: Tiempo agotado sin detección.", YELLOW)
                continue

            log(f"📦 Ciclo {cycle}: ¡Fruta detectada a {result['distance_cm']}cm!", GREEN)
            log(f"📷 Ciclo {cycle}: Capturando imagen...", CYAN)

            img_b64 = camera.get_camera_data()
            if not img_b64:
                log("❌ Error al capturar imagen de la cámara.", RED)
                continue

            log(f"🧠 Ciclo {cycle}: Analizando con IA...", MAGENTA)

            agent_status = llm.act_on_fruit(img_b64, on_message=_on_agent_message)

            if agent_status.startswith("SUCCESS"):
                parts = agent_status.split(":")
                direction = parts[2] if len(parts) > 2 else ""
                if direction == "LEFT":
                    _stats["apples"] += 1
                    log(f"🍎 Ciclo {cycle}: MANZANA → izquierda ✓", GREEN)
                else:
                    _stats["oranges"] += 1
                    log(f"🍊 Ciclo {cycle}: NARANJA → derecha ✓", YELLOW)
                # Esperar a que el Arduino termine de mover el servo y la fruta salga
                time.sleep(3.5)
            elif agent_status.startswith("DISCARD"):
                _stats["discarded"] += 1
                log(f"⚠️  Ciclo {cycle}: Descartado.", YELLOW)
                time.sleep(1.0)
            else:
                _stats["discarded"] += 1
                log(f"⚠️  Ciclo {cycle}: No reconocido — {agent_status[:60]}", YELLOW)
                time.sleep(1.0)

        except Exception as e:
            log(f"⚠️  Ciclo {cycle}: Error inesperado — {e}. Continuando...", YELLOW)
            time.sleep(1)
            continue


# === CONFIG DISPLAY ===

def _print_config() -> None:
    banner("🍓 Fruit Sorter V4+ — Agentic Runner", color=GREEN)
    
    # "Quick Cards" style config
    print(f"  {BG_BLUE}{WHITE} SISTEMA {RESET} {BOLD}Port:{RESET} {c(CYAN, arduino.SERIAL_PORT or 'AUTO')} | {BOLD}Cam:{RESET} {c(CYAN, str(camera.CAMERA_INDEX))}")
    print(f"  {BG_GREEN}{WHITE} IA PROC {RESET} {BOLD}Modl:{RESET} {c(CYAN, llm.LMSTUDIO_MODEL)}")
    print(f"  {BG_RED}{WHITE} CONFIG  {RESET} {BOLD}Thrs:{RESET} {c(YELLOW, '13.0 cm')}")
    print(f"\n  {c(DIM, 'Presiona Ctrl+C para detener el sistema.')}\n")


def signal_handler(sig, frame):
    global _running
    print(f"\n\n{YELLOW}🛑 Deteniendo sistema...{RESET}")
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

    signal.signal(signal_interruption := signal.SIGINT, signal_handler)
    _running = True

    # Setup hardware
    if args.port: arduino.SERIAL_PORT = args.port
    camera.CAMERA_INDEX = args.camera
    
    _print_config()
    
    try:
        if not llm.test_connection():
            log("❌ Error: No se pudo conectar a LMStudio (¿Server iniciado?)", RED)
            sys.exit(1)
            
        sorting_loop(threshold_cm=args.threshold)
    except Exception as e:
        log(f"💥 Error crítico: {e}", RED)
    finally:
        camera.close()
        arduino.close()
