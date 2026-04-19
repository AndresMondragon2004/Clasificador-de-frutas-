#!/usr/bin/env python3
"""
service.py — Autonomous fruit sorting loop.

Orchestrates the full pipeline: sensor detection → image capture →
LLM classification → servo sorting. No MCP needed — Python drives
the hardware directly.

Usage:
    python service.py
    python service.py --port /dev/ttyUSB0 --threshold 15
"""

import argparse
import signal
import sys
import time
from collections import Counter
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
ORANGE = "\033[38;5;208m"


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
_stats = {"cycles": 0, "sorted": Counter(), "last_error": None}

# === CONFIGURATION ===
DETECTION_THRESHOLD_CM = 20.0
STABILIZATION_DELAY = 0.4
SENSOR_TIMEOUT = 30


def classify_with_retries(
    min_votes: int = llm.MIN_VOTES,
    max_attempts: int = llm.MAX_ATTEMPTS,
) -> dict:
    """
    Take up to `max_attempts` photos. Stop early once any label reaches
    `min_votes` consistent answers. Returns the winning label or 'unknown'.
    """
    votes: Counter = Counter()
    errors = 0

    for attempt in range(1, max_attempts + 1):
        image_b64 = camera.get_camera_data()
        if image_b64 is None:
            errors += 1
            continue

        label = llm.classify_image(image_b64)
        if label is None:
            errors += 1
            continue

        if label not in ("apple", "orange"):
            label = "unknown"

        votes[label] += 1

        # Early exit if we have enough votes
        if votes[label] >= min_votes:
            return {
                "classification": label,
                "votes": dict(votes),
                "attempts": attempt,
                "confirmed": label != "unknown",
            }

    # All attempts exhausted
    if not votes:
        return {
            "classification": "unknown",
            "votes": {},
            "attempts": max_attempts,
            "confirmed": False,
            "error": "Camera or LMStudio unavailable during all attempts.",
        }

    best_label, best_count = votes.most_common(1)[0]
    return {
        "classification": best_label,
        "votes": dict(votes),
        "attempts": max_attempts,
        "confirmed": best_label != "unknown" and best_count >= min_votes,
    }


# === MAIN SORTING LOOP ===

def sorting_loop(
    sensor_timeout: int = SENSOR_TIMEOUT,
    threshold_cm: float = DETECTION_THRESHOLD_CM,
    min_votes: int = llm.MIN_VOTES,
    max_attempts: int = llm.MAX_ATTEMPTS,
) -> None:
    """Main sorting pipeline — runs until Ctrl+C."""
    global _running

    log("🟢 Sistema de clasificación iniciado.", GREEN)

    while _running:
        _stats["cycles"] += 1
        cycle = _stats["cycles"]

        # ── Step 1: Wait for fruit ────────────────────────────────────────
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

        # ── Step 2: Classify with retries ─────────────────────────────────
        log(
            f"📷 Ciclo {cycle}: Analizando fruta "
            f"(máx {max_attempts} fotos, necesito {min_votes} voto(s))...",
            CYAN,
        )
        cls_result = classify_with_retries(
            min_votes=min_votes, max_attempts=max_attempts
        )
        label = cls_result["classification"]
        confirmed = cls_result["confirmed"]
        votes = cls_result.get("votes", {})
        attempts = cls_result.get("attempts", 0)

        if not _running:
            break

        if cls_result.get("error"):
            log(f"⚠️  Ciclo {cycle}: Error — {cls_result['error']}", YELLOW)
            _stats["last_error"] = cls_result["error"]
            continue

        if not confirmed or label == "unknown":
            log(
                f"🚫 Ciclo {cycle}: No reconocida tras {attempts} foto(s). "
                f"Votos: {votes}. Descartando.",
                YELLOW,
            )
            continue

        # ── Detection confirmed ───────────────────────────────────────────
        emoji = "🍎" if label == "apple" else "🍊"
        nombre = "MANZANA" if label == "apple" else "NARANJA"
        color = RED if label == "apple" else ORANGE

        print()
        print(f"{BOLD}{color}{'▓' * 50}{RESET}")
        print(f"{BOLD}{color}  {emoji}  {nombre} DETECTADA  {emoji}{RESET}")
        print(f"{color}  Votos: {votes}  |  Fotos: {attempts}{RESET}")
        print(f"{BOLD}{color}{'▓' * 50}{RESET}")
        print()

        # ── Step 3: Sort ──────────────────────────────────────────────────
        direction = "izquierda" if label == "apple" else "derecha"
        log(f"🤖 Ciclo {cycle}: Girando servo hacia la {direction}...", BLUE)

        if label == "apple":
            sort_result = arduino.classify_as_apple()
        else:
            sort_result = arduino.classify_as_orange()

        if sort_result["success"]:
            _stats["sorted"][label] += 1
            total = sum(_stats["sorted"].values())
            log(
                f"🎉 Ciclo {cycle}: ¡Clasificada exitosamente! "
                f"Fruta #{total} — Total: {dict(_stats['sorted'])}",
                GREEN,
            )
        elif sort_result.get("error"):
            err = sort_result["error"]
            _stats["last_error"] = err
            log(f"⚠️  Ciclo {cycle}: Error al ordenar — {err}", YELLOW)

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
    sorted_dict = dict(_stats.get("sorted", {}))
    total = sum(sorted_dict.values())
    cycles = _stats.get("cycles", 0)

    banner("RESUMEN FINAL", color=BLUE)
    print(f"  Ciclos completados : {c(WHITE, str(cycles))}")
    print(f"  Frutas clasificadas: {c(GREEN, str(total))}")
    if sorted_dict:
        for fruit, count in sorted_dict.items():
            emoji = "🍎" if fruit == "apple" else "🍊"
            nombre = "Manzanas" if fruit == "apple" else "Naranjas"
            print(f"    {emoji}  {nombre}: {c(BOLD, str(count))}")

    last_err = _stats.get("last_error")
    if last_err:
        print(f"\n  Último error : {c(YELLOW, str(last_err))}")
    print()


# === CONFIG DISPLAY ===

def _print_config(args: argparse.Namespace) -> None:
    banner("🍓 Fruit Sorter V2 — Autonomous Runner", color=GREEN)
    port = arduino.SERIAL_PORT or "(auto-detect)"
    print(f"  Puerto serial   : {c(CYAN, port)}")
    print(f"  Baud rate       : {c(CYAN, str(arduino.SERIAL_BAUD))}")
    print(f"  Vision API      : {c(CYAN, llm.LMSTUDIO_URL)}")
    print(f"  Modelo          : {c(CYAN, llm.LMSTUDIO_MODEL)}")
    print(f"  Cámara index    : {c(CYAN, str(camera.CAMERA_INDEX))}")
    print(f"  Umbral sensor   : {c(CYAN, str(args.threshold))}cm")
    print(f"  Timeout sensor  : {c(CYAN, str(args.sensor_timeout))}s")
    print(f"  Votos mínimos   : {c(CYAN, str(args.min_votes))}")
    print(f"  Intentos máx.   : {c(CYAN, str(args.max_attempts))}")
    print(f"\n  {c(DIM, 'Presiona Ctrl+C para detener limpiamente.')}\n")


# === CLI ARGS ===

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="service.py",
        description="Fruit Sorter V2 — Autonomous sorting pipeline.",
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
        "--lm-url", default="http://127.0.0.1:1234/v1/chat/completions",
        dest="lm_url",
        help="LMStudio API URL",
    )
    parser.add_argument(
        "--lm-model", default="qwen3-vl-4b", dest="lm_model",
        help="LMStudio model name",
    )
    parser.add_argument(
        "--threshold", type=float, default=20.0,
        help="Detection threshold in cm (default: 20.0)",
    )
    parser.add_argument(
        "--sensor-timeout", type=int, default=30, dest="sensor_timeout",
        help="Sensor wait timeout in seconds (default: 30)",
    )
    parser.add_argument(
        "--min-votes", type=int, default=1, dest="min_votes",
        help="Minimum votes to confirm classification (default: 1)",
    )
    parser.add_argument(
        "--max-attempts", type=int, default=3, dest="max_attempts",
        help="Max photos per detection (default: 3)",
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
    llm.LMSTUDIO_URL = args.lm_url
    llm.LMSTUDIO_MODEL = args.lm_model

    _print_config(args)

    # Test LLM connection
    log("🔗 Verificando conexión con LMStudio...", CYAN)
    if not llm.test_connection():
        log(f"❌ No se pudo conectar a LMStudio en {llm.LMSTUDIO_URL}", RED)
        log("   Asegúrate de que LMStudio está corriendo con el modelo cargado.", RED)
        sys.exit(1)
    log("✅ LMStudio conectado.", GREEN)

    signal.signal(signal.SIGINT, _handle_sigint)

    _running = True

    try:
        sorting_loop(
            sensor_timeout=args.sensor_timeout,
            threshold_cm=args.threshold,
            min_votes=args.min_votes,
            max_attempts=args.max_attempts,
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