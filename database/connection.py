"""
Conexión segura a SQLite con reintentos y WAL mode
Club Los Pocitos Azufrados
"""

import os
import sys
import shutil
import sqlite3
import logging
from contextlib import contextmanager

logger = logging.getLogger("pocitos")

# ── Ubicación de los DATOS ──
# Como .exe: los datos viven en %LOCALAPPDATA%\PocitosAzufrados\data, FUERA de la
# carpeta del programa. Así, cuando el launcher actualiza la app (reemplaza sus
# archivos), la base de datos con las ventas NO se toca.
# En desarrollo: junto al proyecto, como siempre.
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
    _USER_DIR = os.path.join(os.environ.get('LOCALAPPDATA') or os.path.expanduser('~'), 'PocitosAzufrados')
    DATA_DIR = os.path.join(_USER_DIR, 'data')
    _BUNDLED_DATA = os.path.join(BASE_DIR, 'data')   # 'data' semilla que viene en el paquete
else:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DATA_DIR = os.path.join(BASE_DIR, 'data')
    _BUNDLED_DATA = None

DB_PATH = os.path.join(DATA_DIR, "pocitos_azufrados.db")


def ensure_data_ready():
    """Garantiza que exista la carpeta de datos del usuario con la BD.

    Primera ejecución del .exe: copia el 'data' semilla del paquete (incluye la
    BD inicial). En adelante, esta carpeta persiste entre actualizaciones,
    conservando las ventas. Debe llamarse al arrancar, ANTES de abrir conexiones.
    """
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(DB_PATH) and _BUNDLED_DATA and os.path.isdir(_BUNDLED_DATA):
        for name in os.listdir(_BUNDLED_DATA):
            src = os.path.join(_BUNDLED_DATA, name)
            dst = os.path.join(DATA_DIR, name)
            try:
                if os.path.isdir(src):
                    shutil.copytree(src, dst, dirs_exist_ok=True)
                elif not os.path.exists(dst):
                    shutil.copy2(src, dst)
            except Exception:
                logger.exception("No se pudo copiar datos iniciales: %s", name)
    return DB_PATH


def get_db_path():
    """Retorna la ruta de la base de datos (carpeta de datos del usuario)."""
    return DB_PATH


def get_connection(db_path=None):
    """Crea conexión optimizada a SQLite"""
    if db_path is None:
        db_path = get_db_path()

    conn = sqlite3.connect(db_path, timeout=60)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=60000")
    return conn



@contextmanager
def conexion_segura(db_path=None):
    """Context manager para conexiones seguras"""
    if db_path is None:
        db_path = get_db_path()
    conn = get_connection(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@contextmanager
def transaccion_atomica(db_path=None):
    """Transacción atómica con commit/rollback automático"""
    if db_path is None:
        db_path = get_db_path()
    conn = get_connection(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
