#!/usr/bin/env python3
"""
service.py — Autonomous fruit sorting loop (Agentic Architecture).

Orchestrates the pipeline: sensor detection → image capture →
LLM agent (.act()) decides and sorts. The LLM calls tools directly
— no hardcoded fruit conditionals in Python.

Usage:
    python service.py
    python service.py --port /dev/ttyUSB0 --threshold 15
"""

import argparse
import signal
import sys
import time
from datetime import datetime

import arduino
import camera
import llm

# === ANSI COLORS (no external deps) ===
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


def c(color: str, text: str) -> str:
    return f"{color}{text}{RESET}"


def banner(title: str, color: str = CYAN) -> None:
    width = 60
    print(f"\n{color}{'─' * width}{RESET}")
    print(f"{BOLD}{color}  {title}{RESET}")
    print(f"{color}{'─' * width}{RESET}\n")


def timestamp() -> str:
    return datetime.now().strftime("%H:%M:%S")


def log(msg: str, color: str = WHITE) -> None:
    print(f"{DIM}[{timestamp()}]{RESET} {color}{msg}{RESET}")


# === STATE ===
_running = False
_stats = {"cycles": 0, "sorted": 0, "discarded": 0, "errors": 0, "last_error": None}

# === CONFIGURATION ===
DETECTION_THRESHOLD_CM = 20.0
STABILIZATION_DELAY = 0.4
SENSOR_TIMEOUT = 30


# === AGENT MESSAGE HANDLER ===

def _on_agent_message(message) -> None:
    """Log messages from the LLM agent during .act() execution."""
    role = getattr(message, "role", "unknown")
    content = str(message) if message else ""

    if role == "tool":
        # Tool was called by the agent
        log(f"  🔧 Tool ejecutada: {content[:120]}", BLUE)
    elif role == "assistant" and content:
        log(f"  🤖 Agente: {content[:120]}", MAGENTA)


# === MAIN SORTING LOOP ===

def sorting_loop(
    sensor_timeout: int = SENSOR_TIMEOUT,
    threshold_cm: float = DETECTION_THRESHOLD_CM,
) -> None:
    """Main sorting pipeline — runs until Ctrl+C."""
    global _running

    log("🟢 Sistema de clasificación iniciado.", GREEN)
    log(f"📋 Prompt del agente: {llm.SYSTEM_PROMPT[:80]}...", DIM)

    while _running:
        _stats["cycles"] += 1
        cycle = _stats["cycles"]

        # ── Step 1: Wait for fruit ────────────────────────────────────
        log(f"🔍 Ciclo {cycle}: Esperando fruta en el sensor...", DIM)

        result = arduino.wait_for_fruit(
            threshold_cm=threshold_cm,
            timeout_seconds=sensor_timeout,
        )

        if not _running:
            break

        if result["detected"]:
            dist = result.get("distance_cm", "?")
            log(
                f"📦 Ciclo {cycle}: ¡Fruta detectada a {dist:.1f}cm! "
                f"Estabilizando ({STABILIZATION_DELAY}s)...",
                CYAN,
            )
            time.sleep(STABILIZATION_DELAY)
        else:
            log(f"⏳ Ciclo {cycle}: No hay fruta — reintentando.", DIM)
            continue

        # ── Step 2: Capture image ─────────────────────────────────────
        log(f"📷 Ciclo {cycle}: Capturando imagen...", CYAN)
        image_b64 = camera.get_camera_data()

        if not _running:
            break

        if image_b64 is None:
            log(f"⚠️  Ciclo {cycle}: Error de cámara.", YELLOW)
            _stats["errors"] += 1
            continue

        # ── Step 3: Let the agent decide and act ──────────────────────
        log(
            f"🧠 Ciclo {cycle}: Enviando imagen al agente LLM "
            f"(modelo: {llm.LMSTUDIO_MODEL})...",
            CYAN,
        )

        agent_response = llm.act_on_fruit(
            image_b64=image_b64,
            on_message=_on_agent_message,
        )

        if not _running:
            break

        # ── Log the result ────────────────────────────────────────────
        if "error" in agent_response.lower():
            _stats["errors"] += 1
            _stats["last_error"] = agent_response
            log(f"⚠️  Ciclo {cycle}: {agent_response}", YELLOW)
        elif "discard" in agent_response.lower():
            _stats["discarded"] += 1
            log(f"🚫 Ciclo {cycle}: Fruta descartada por el agente.", YELLOW)
        else:
            _stats["sorted"] += 1
            print()
            print(f"{BOLD}{GREEN}{'▓' * 50}{RESET}")
            print(f"{BOLD}{GREEN}  ✅  FRUTA CLASIFICADA — Ciclo {cycle}  ✅{RESET}")
            print(f"{GREEN}  Respuesta: {agent_response[:80]}{RESET}")
            print(f"{GREEN}  Total clasificadas: {_stats['sorted']}{RESET}")
            print(f"{BOLD}{GREEN}{'▓' * 50}{RESET}")
            print()

    log("🔴 Sistema de clasificación detenido.", RED)


# === SIGNAL HANDLER ===

def _handle_sigint(sig, frame) -> None:
    global _running
    if not _running:
        sys.exit(0)
    _running = False
    print(c(YELLOW, "\n\n⛔  Interrupción recibida. Deteniendo al terminar el ciclo..."))


# === SUMMARY ===

def _print_summary() -> None:
    banner("RESUMEN FINAL", color=BLUE)
    print(f"  Ciclos completados  : {c(WHITE, str(_stats['cycles']))}")
    print(f"  Frutas clasificadas : {c(GREEN, str(_stats['sorted']))}")
    print(f"  Frutas descartadas  : {c(YELLOW, str(_stats['discarded']))}")
    print(f"  Errores             : {c(RED, str(_stats['errors']))}")

    last_err = _stats.get("last_error")
    if last_err:
        print(f"\n  Último error : {c(YELLOW, str(last_err)[:80])}")
    print()


# === CONFIG DISPLAY ===

def _print_config(args: argparse.Namespace) -> None:
    banner("🍓 Fruit Sorter V3 — Agentic Runner", color=GREEN)
    port = arduino.SERIAL_PORT or "(auto-detect)"
    print(f"  Puerto serial   : {c(CYAN, port)}")
    print(f"  Baud rate       : {c(CYAN, str(arduino.SERIAL_BAUD))}")
    print(f"  LMStudio SDK    : {c(CYAN, 'lmstudio (WebSocket, auto-connect)')}")
    print(f"  API Key         : {c(CYAN, llm.LMSTUDIO_API_KEY)}")
    print(f"  Modelo          : {c(CYAN, llm.LMSTUDIO_MODEL)}")
    print(f"  Cámara index    : {c(CYAN, str(camera.CAMERA_INDEX))}")
    print(f"  Umbral sensor   : {c(CYAN, str(args.threshold))}cm")
    print(f"  Timeout sensor  : {c(CYAN, str(args.sensor_timeout))}s")
    print(f"\n  {c(DIM, 'Presiona Ctrl+C para detener limpiamente.')}\n")


# === CLI ARGS ===

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="service.py",
        description="Fruit Sorter V3 — Agentic sorting pipeline.",
    )
    parser.add_argument(
        "--port", default=None,
        help="Serial port (default: auto-detect)",
    )
    parser.add_argument(
        "--baud", type=int, default=115200,
        help="Baud rate (default: 115200)",
    )
    parser.add_argument(
        "--camera", type=int, default=0,
        help="Camera index (default: 0)",
    )
    parser.add_argument(
        "--lm-model", default="qwen/qwen3-vl-4b", dest="lm_model",
        help="LMStudio model name (default: qwen/qwen3-vl-4b)",
    )
    parser.add_argument(
        "--threshold", type=float, default=20.0,
        help="Detection threshold in cm (default: 20.0)",
    )
    parser.add_argument(
        "--sensor-timeout", type=int, default=30, dest="sensor_timeout",
        help="Sensor wait timeout in seconds (default: 30)",
    )
    return parser.parse_args()


# === ENTRYPOINT ===

def main() -> None:
    global _running

    args = parse_args()

    # Apply CLI overrides to modules
    if args.port:
        arduino.SERIAL_PORT = args.port
    arduino.SERIAL_BAUD = args.baud
    camera.CAMERA_INDEX = args.camera
    llm.LMSTUDIO_MODEL = args.lm_model

    _print_config(args)

    # Test LLM connection
    log("🔗 Verificando conexión con LMStudio...", CYAN)
    if not llm.test_connection():
        log("❌ No se pudo conectar a LMStudio. ¿Está corriendo con el modelo cargado?", RED)
        log("   Asegúrate de que LMStudio está corriendo con el modelo cargado.", RED)
        sys.exit(1)
    log("✅ LMStudio conectado.", GREEN)

    signal.signal(signal.SIGINT, _handle_sigint)

    _running = True

    try:
        sorting_loop(
            sensor_timeout=args.sensor_timeout,
            threshold_cm=args.threshold,
        )
    except Exception as exc:
        print(c(RED, f"\n💥 Error inesperado: {exc}"))
        raise
    finally:
        arduino.close()
        camera.close()
        _print_summary()


if __name__ == "__main__":
    main()