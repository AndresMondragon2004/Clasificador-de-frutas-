#!/usr/bin/env python3
"""
sorter_runner.py — Bucle autónomo del clasificador de frutas.

Reemplaza a LMStudio como orquestador: ejecuta el bucle de clasificación
llamando a las mismas tools de server.py (wait_for_fruit, classify_fruit,
sort_fruit) en secuencia.

Requiere que el servidor de inferencia de visión esté corriendo
(LMStudio, Ollama, o cualquier API compatible con OpenAI).

Uso:
    python sorter_runner.py
    python sorter_runner.py --port COM5 --sensor-timeout 30 --min-votes 2
"""

import argparse
import signal
import sys
import time
from collections import Counter
from datetime import datetime

# ── ANSI color codes (sin dependencias externas) ──────────────────────────────

RESET  = "\033[0m"
BOLD   = "\033[1m"
DIM    = "\033[2m"

RED    = "\033[91m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
BLUE   = "\033[94m"
CYAN   = "\033[96m"
WHITE  = "\033[97m"
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


# ── Import server.py ──────────────────────────────────────────────────────────

try:
    import server as _srv
except ImportError:
    print(c(RED, "ERROR: No se encontró server.py en el directorio actual."))
    print(c(DIM, "  Asegúrate de ejecutar este script desde fruit_sorter/"))
    sys.exit(1)

# Referenciar las TOOLS (la API pública, no las funciones internas)
wait_for_fruit  = _srv.wait_for_fruit       # @app.tool
classify_fruit  = _srv.classify_fruit       # @app.tool
sort_fruit      = _srv.sort_fruit           # @app.tool
# También necesitamos classify_with_retries para multi-voto
classify_with_retries = _srv.classify_with_retries

STABILIZATION_DELAY = _srv.STABILIZATION_DELAY


# ── State ─────────────────────────────────────────────────────────────────────

_running = False
_stats   = {"cycles": 0, "sorted": Counter(), "last_error": None}


# ── Sorting loop (uses tools) ────────────────────────────────────────────────

def run_sorting_loop(
    sensor_timeout: int,
    min_votes: int,
    max_attempts: int,
) -> None:
    """
    Bucle principal de clasificación.
    Llama a las TOOLS de server.py como lo haría LMStudio,
    pero directamente desde Python.
    """
    global _running

    log("🟢 Sistema de clasificación iniciado.", GREEN)

    while _running:
        _stats["cycles"] += 1
        cycle = _stats["cycles"]

        # ── Step 1: Esperar fruta (tool: wait_for_fruit) ──────────────────
        log(f"🔍 Ciclo {cycle}: Esperando fruta en el sensor...", DIM)

        result = wait_for_fruit(timeout_seconds=sensor_timeout)

        if not _running:
            break

        if result.get("detected"):
            log(f"📦 Ciclo {cycle}: ¡Fruta detectada! Estabilizando ({STABILIZATION_DELAY}s)...", CYAN)
            time.sleep(STABILIZATION_DELAY)

        elif "Timeout" in result.get("message", ""):
            log(f"⏳ Ciclo {cycle}: No hay fruta — reintentando.", DIM)
            continue

        elif result.get("error"):
            err = result["error"]
            _stats["last_error"] = err
            log(f"⚠️  Ciclo {cycle}: Error — {err}. Reintentando en 3s.", YELLOW)
            time.sleep(3)
            continue

        else:
            log(f"⚠️  Ciclo {cycle}: Respuesta inesperada: {result}. Reintentando.", YELLOW)
            time.sleep(1)
            continue

        # ── Step 2: Clasificar fruta (tool: classify_fruit / retries) ─────
        log(f"📷 Ciclo {cycle}: Analizando fruta (máx {max_attempts} fotos, necesito {min_votes} voto(s))...", CYAN)

        if min_votes > 1 or max_attempts > 1:
            # Usa el sistema de multi-voto
            cls_result = classify_with_retries(
                min_votes=min_votes, max_attempts=max_attempts
            )
            label     = cls_result["classification"]
            confirmed = cls_result["confirmed"]
            votes     = cls_result.get("votes", {})
            attempts  = cls_result.get("attempts", 0)
        else:
            # Usa la tool simple de una sola foto
            cls_result = classify_fruit()
            label      = cls_result.get("classification", "unknown")
            confirmed  = label in ("apple", "orange")
            votes      = {label: 1} if confirmed else {}
            attempts   = 1

        if not _running:
            break

        if cls_result.get("error"):
            log(f"⚠️  Ciclo {cycle}: Error de clasificación — {cls_result['error']}", YELLOW)
            _stats["last_error"] = cls_result["error"]
            continue

        if not confirmed or label == "unknown":
            log(
                f"🚫 Ciclo {cycle}: No reconocida tras {attempts} foto(s). "
                f"Votos: {votes}. Descartando.",
                YELLOW,
            )
            continue

        # ── Detección confirmada — mostrar banner ─────────────────────────
        emoji  = "🍎" if label == "apple"  else "🍊"
        nombre = "MANZANA"  if label == "apple"  else "NARANJA"
        color  = RED        if label == "apple"  else ORANGE

        print()
        print(f"{BOLD}{color}{'▓' * 50}{RESET}")
        print(f"{BOLD}{color}  {emoji}  {nombre} DETECTADA  {emoji}{RESET}")
        print(f"{color}  Votos: {votes}  |  Fotos tomadas: {attempts}{RESET}")
        print(f"{BOLD}{color}{'▓' * 50}{RESET}")
        print()

        # ── Step 3: Ordenar fruta (tool: sort_fruit) ──────────────────────
        direction = "izquierda" if label == "apple" else "derecha"
        log(f"🤖 Ciclo {cycle}: Girando servo hacia la {direction}...", BLUE)

        sort_result = sort_fruit(fruit=label)

        if sort_result.get("status") == "success":
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


# ── Signal handler (Ctrl+C) ───────────────────────────────────────────────────

def _handle_sigint(sig, frame) -> None:
    global _running
    if not _running:
        sys.exit(0)
    _running = False
    print(c(YELLOW, "\n\n⛔  Interrupción recibida. Deteniendo al terminar el ciclo actual..."))


# ── Summary ───────────────────────────────────────────────────────────────────

def _print_summary() -> None:
    sorted_dict = dict(_stats.get("sorted", {}))
    total  = sum(sorted_dict.values())
    cycles = _stats.get("cycles", 0)

    banner("RESUMEN FINAL", color=BLUE)
    print(f"  Ciclos completados : {c(WHITE, str(cycles))}")
    print(f"  Frutas clasificadas: {c(GREEN, str(total))}")
    if sorted_dict:
        for fruit, count in sorted_dict.items():
            emoji  = "🍎" if fruit == "apple" else "🍊"
            nombre = "Manzanas" if fruit == "apple" else "Naranjas"
            print(f"    {emoji}  {nombre}: {c(BOLD, str(count))}")

    last_err = _stats.get("last_error")
    if last_err:
        print(f"\n  Último error : {c(YELLOW, str(last_err))}")
    print()


# ── Config display ────────────────────────────────────────────────────────────

def _print_config(args: argparse.Namespace) -> None:
    banner("🍓 Clasificador de Frutas — Runner Autónomo", color=GREEN)
    print(f"  Puerto serial   : {c(CYAN, args.port)}")
    print(f"  Baud rate       : {c(CYAN, str(args.baud))}")
    print(f"  Vision API      : {c(CYAN, _srv.LMSTUDIO_URL)}")
    print(f"  Modelo          : {c(CYAN, _srv.LMSTUDIO_MODEL)}")
    print(f"  Timeout sensor  : {c(CYAN, str(args.sensor_timeout))}s")
    print(f"  Votos mínimos   : {c(CYAN, str(args.min_votes))}")
    print(f"  Intentos máx.   : {c(CYAN, str(args.max_attempts))}")
    print(f"\n  {c(DIM, 'Presiona Ctrl+C para detener limpiamente.')}\n")


# ── CLI args ──────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="sorter_runner.py",
        description="Bucle autónomo del clasificador de frutas.",
    )
    parser.add_argument("--port", default=_srv.SERIAL_PORT,
                        help=f"Puerto serial del Arduino (default: {_srv.SERIAL_PORT})")
    parser.add_argument("--baud", type=int, default=_srv.SERIAL_BAUD,
                        help=f"Baud rate (default: {_srv.SERIAL_BAUD})")
    parser.add_argument("--sensor-timeout", type=int, default=30, dest="sensor_timeout",
                        help="Segundos de espera por detección (default: 30)")
    parser.add_argument("--min-votes", type=int, default=_srv.MIN_VOTES, dest="min_votes",
                        help=f"Votos mínimos para confirmar (default: {_srv.MIN_VOTES})")
    parser.add_argument("--max-attempts", type=int, default=_srv.MAX_ATTEMPTS, dest="max_attempts",
                        help=f"Máximo de fotos por detección (default: {_srv.MAX_ATTEMPTS})")
    return parser.parse_args()


# ── Entrypoint ────────────────────────────────────────────────────────────────

def main() -> None:
    global _running

    args = parse_args()

    # Aplicar overrides de CLI al módulo server
    _srv.SERIAL_PORT = args.port
    _srv.SERIAL_BAUD = args.baud

    _print_config(args)
    signal.signal(signal.SIGINT, _handle_sigint)

    _running = True

    try:
        run_sorting_loop(
            sensor_timeout=args.sensor_timeout,
            min_votes=args.min_votes,
            max_attempts=args.max_attempts,
        )
    except Exception as exc:
        print(c(RED, f"\n💥 Error inesperado: {exc}"))
        raise
    finally:
        # Cerrar conexiones de hardware
        try:
            if _srv._serial_conn and _srv._serial_conn.is_open:
                _srv._serial_conn.close()
                print(c(DIM, "  Serial cerrado."))
        except Exception:
            pass
        try:
            if _srv._camera_conn and _srv._camera_conn.isOpened():
                _srv._camera_conn.release()
                print(c(DIM, "  Cámara liberada."))
        except Exception:
            pass

        _print_summary()


if __name__ == "__main__":
    main()
