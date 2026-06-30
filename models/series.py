"""
Generador de Números Consecutivos Thread-Safe
Club Los Pocitos Azufrados
"""

import threading
import datetime
from database.connection import get_db_path, get_connection

# Nota de diseño: se usan AMBAS protecciones intencionalmente.
# - threading.Lock(): serializa accesos dentro del mismo proceso (hilos de UI, daemons).
# - BEGIN IMMEDIATE: serializa accesos cross-proceso (scripts externos, herramienta de backup).
# Para una app desktop single-process son redundantes en la práctica, pero
# el costo es despreciable y proveen seguridad ante usos futuros o accesos externos.
_lock_ventas = threading.Lock()
_lock_boletas = threading.Lock()
_lock_fe = threading.Lock()


def obtener_proximo_numero_venta(db_path=None):
    """Genera el siguiente número de venta (POS-2026-000001)"""
    if db_path is None:
        db_path = get_db_path()

    with _lock_ventas:
        conn = get_connection(db_path)
        try:
            conn.execute("BEGIN IMMEDIATE")
            ano_actual = datetime.datetime.now().year

            row = conn.execute(
                "SELECT id_serie, consecutivo_actual FROM series_facturacion "
                "WHERE prefijo = 'POS' AND ano = ? AND activa = 1",
                (ano_actual,)
            ).fetchone()

            if row:
                nuevo = row['consecutivo_actual'] + 1
                conn.execute(
                    "UPDATE series_facturacion SET consecutivo_actual = ? WHERE id_serie = ?",
                    (nuevo, row['id_serie'])
                )
            else:
                nuevo = 1
                conn.execute(
                    "INSERT INTO series_facturacion (prefijo, ano, consecutivo_actual, activa) VALUES ('POS', ?, 1, 1)",
                    (ano_actual,)
                )

            conn.commit()
            return f"POS-{ano_actual}-{nuevo:06d}"
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


def obtener_proximo_numero_boleta(db_path=None):
    """Genera el siguiente número de boleta (BOL-2026-000001)"""
    if db_path is None:
        db_path = get_db_path()

    with _lock_boletas:
        conn = get_connection(db_path)
        try:
            conn.execute("BEGIN IMMEDIATE")
            ano_actual = datetime.datetime.now().year

            row = conn.execute(
                "SELECT id_serie, consecutivo_actual FROM series_boletas WHERE ano = ? AND activa = 1",
                (ano_actual,)
            ).fetchone()

            if row:
                nuevo = row['consecutivo_actual'] + 1
                conn.execute(
                    "UPDATE series_boletas SET consecutivo_actual = ? WHERE id_serie = ?",
                    (nuevo, row['id_serie'])
                )
            else:
                nuevo = 1
                conn.execute(
                    "INSERT INTO series_boletas (prefijo, ano, consecutivo_actual, activa) VALUES ('BOL', ?, 1, 1)",
                    (ano_actual,)
                )

            conn.commit()
            return f"BOL-{ano_actual}-{nuevo:06d}"
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


def obtener_proximo_numero_factura_electronica(db_path=None):
    """Genera el siguiente número de factura electrónica (LP-2026-000001).
    Thread-safe. Lanza excepción si no hay serie LP activa para el año."""
    if db_path is None:
        db_path = get_db_path()

    with _lock_fe:
        conn = get_connection(db_path)
        try:
            conn.execute("BEGIN IMMEDIATE")
            ano_actual = datetime.datetime.now().year

            row = conn.execute(
                "SELECT id_serie, consecutivo_actual FROM series_facturacion WHERE prefijo = 'LP' AND ano = ? AND activa = 1",
                (ano_actual,)
            ).fetchone()

            if row:
                nuevo = row['consecutivo_actual'] + 1
                conn.execute(
                    "UPDATE series_facturacion SET consecutivo_actual = ? WHERE id_serie = ?",
                    (nuevo, row['id_serie'])
                )
            else:
                nuevo = 1
                conn.execute(
                    "INSERT INTO series_facturacion (prefijo, ano, consecutivo_actual, activa) VALUES ('LP', ?, 1, 1)",
                    (ano_actual,)
                )

            conn.commit()
            return f"LP-{ano_actual}-{nuevo:06d}"
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


def generar_numero_venta_en_conn(conn):
    """Genera el siguiente número POS usando una conexión ya abierta.
    Diseñada para usarse dentro de un bloque transaccion_atomica().
    El caller maneja el commit/rollback — esta función NO hace commit.
    Thread-safe: usa el mismo lock que obtener_proximo_numero_venta."""
    with _lock_ventas:
        ano_actual = datetime.datetime.now().year
        row = conn.execute(
            "SELECT id_serie, consecutivo_actual FROM series_facturacion "
            "WHERE prefijo = 'POS' AND ano = ? AND activa = 1",
            (ano_actual,)
        ).fetchone()
        if row:
            nuevo = row['consecutivo_actual'] + 1
            conn.execute(
                "UPDATE series_facturacion SET consecutivo_actual = ? WHERE id_serie = ?",
                (nuevo, row['id_serie'])
            )
        else:
            nuevo = 1
            conn.execute(
                "INSERT INTO series_facturacion (prefijo, ano, consecutivo_actual, activa) "
                "VALUES ('POS', ?, 1, 1)",
                (ano_actual,)
            )
        return f"POS-{ano_actual}-{nuevo:06d}"


def generar_numero_fe_en_conn(conn):
    """Genera el siguiente número LP usando una conexión ya abierta.
    Diseñada para usarse dentro de un bloque transaccion_atomica().
    El caller maneja el commit/rollback — esta función NO hace commit.
    Thread-safe: usa el mismo lock que obtener_proximo_numero_factura_electronica."""
    with _lock_fe:
        ano_actual = datetime.datetime.now().year
        row = conn.execute(
            "SELECT id_serie, consecutivo_actual FROM series_facturacion "
            "WHERE prefijo = 'LP' AND ano = ? AND activa = 1",
            (ano_actual,)
        ).fetchone()
        if row:
            nuevo = row['consecutivo_actual'] + 1
            conn.execute(
                "UPDATE series_facturacion SET consecutivo_actual = ? WHERE id_serie = ?",
                (nuevo, row['id_serie'])
            )
        else:
            nuevo = 1
            conn.execute(
                "INSERT INTO series_facturacion (prefijo, ano, consecutivo_actual, activa) "
                "VALUES ('LP', ?, 1, 1)",
                (ano_actual,)
            )
        return f"LP-{ano_actual}-{nuevo:06d}"


def preview_numero_venta(db_path=None):
    """Muestra el siguiente número sin incrementar"""
    if db_path is None:
        db_path = get_db_path()
    conn = get_connection(db_path)
    try:
        ano = datetime.datetime.now().year
        row = conn.execute(
            "SELECT consecutivo_actual FROM series_facturacion "
            "WHERE prefijo = 'POS' AND ano = ? AND activa = 1",
            (ano,)
        ).fetchone()
        siguiente = (row['consecutivo_actual'] + 1) if row else 1
        return f"POS-{ano}-{siguiente:06d}"
    finally:
        conn.close()
