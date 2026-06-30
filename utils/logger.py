"""
Sistema de Logging - Club Los Pocitos Azufrados
"""

import json
import os
import sys
import time
import logging
from logging.handlers import RotatingFileHandler
from database.connection import get_db_path, conexion_segura

_PERF_THRESHOLD_MS = 80  # registra solo operaciones que superen este umbral

# Mismo patrón que connection.py: usar directorio del exe cuando está congelado
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR = os.path.join(BASE_DIR, "logs")


def log_performance(operacion: str, duracion_ms: float, detalle: str = ""):
    """Registra operaciones lentas (> _PERF_THRESHOLD_MS ms) en logs/performance.log."""
    if duracion_ms <= _PERF_THRESHOLD_MS:
        return
    os.makedirs(LOG_DIR, exist_ok=True)
    perf_log = logging.getLogger("pocitos.performance")
    if not perf_log.handlers:
        fh = RotatingFileHandler(
            os.path.join(LOG_DIR, "performance.log"),
            maxBytes=2*1024*1024, backupCount=2, encoding='utf-8'
        )
        fh.setFormatter(logging.Formatter('%(asctime)s | %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
        perf_log.addHandler(fh)
        perf_log.setLevel(logging.INFO)
        perf_log.propagate = False
    perf_log.info(f"LENTO {duracion_ms:.1f}ms | {operacion} | {detalle[:120]}")


def configurar_logger(nombre="pocitos", nivel=logging.INFO):
    """Configura el logger principal"""
    os.makedirs(LOG_DIR, exist_ok=True)
    logger = logging.getLogger(nombre)

    if logger.handlers:
        return logger

    logger.setLevel(nivel)
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(funcName)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Archivo general (rotación 5MB, 3 backups)
    fh = RotatingFileHandler(
        os.path.join(LOG_DIR, "pocitos.log"),
        maxBytes=5*1024*1024, backupCount=3, encoding='utf-8'
    )
    fh.setLevel(nivel)
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    # Archivo de errores
    eh = RotatingFileHandler(
        os.path.join(LOG_DIR, "errores.log"),
        maxBytes=5*1024*1024, backupCount=3, encoding='utf-8'
    )
    eh.setLevel(logging.ERROR)
    eh.setFormatter(formatter)
    logger.addHandler(eh)

    # Consola (solo warnings+)
    ch = logging.StreamHandler()
    ch.setLevel(logging.WARNING)
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    return logger


def log_auditoria(conn, tabla, id_registro, accion, usuario, comentario="",
                  datos_anteriores=None, datos_nuevos=None):
    """Registra una acción en la tabla de auditoría.
    Retorna True si el registro fue exitoso, False si falló.
    El error siempre se loguea; nunca se relanza para no interrumpir la transacción del caller."""
    try:
        conn.execute("""
            INSERT INTO auditoria
            (tabla_afectada, id_registro, accion, usuario, comentario,
             datos_anteriores, datos_nuevos)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (tabla, id_registro, accion, usuario,
              comentario,
              json.dumps(datos_anteriores, default=str),
              json.dumps(datos_nuevos, default=str)))
        return True
    except Exception as e:
        logger = logging.getLogger("pocitos")
        logger.error(f"AUDITORIA FALLIDA — {accion} en {tabla} id={id_registro} por {usuario}: {e}")
        return False
