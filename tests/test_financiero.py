"""
Tests de lógica financiera — totales, descuentos, cierre de caja.
Todos usan BD en memoria (fixture db_mem de conftest.py).
"""
import os
import sys
import datetime
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


# ---------------------------------------------------------------------------
# Helpers de inserción directa (sin Tkinter ni módulos de UI)
# ---------------------------------------------------------------------------

def _insertar_venta(conn, total, estado='COMPLETADA', tipo='venta'):
    cur = conn.execute(
        """INSERT INTO ventas (numero_venta, tipo, estado, total, total_pagado, saldo_pendiente,
                               metodo_pago, usuario_cajero, fecha_creacion)
           VALUES (?, ?, ?, ?, ?, ?, 'EFECTIVO', 'test', datetime('now','localtime'))""",
        (f"POS-{conn.execute('SELECT COUNT(*) FROM ventas').fetchone()[0]+1:04d}",
         tipo, estado, total, total, 0)
    )
    conn.commit()
    return cur.lastrowid


def _insertar_detalle(conn, id_venta, nombre, cantidad, precio):
    conn.execute(
        """INSERT INTO venta_detalle (id_venta, producto_nombre, cantidad, precio_unitario, total_linea)
           VALUES (?, ?, ?, ?, ?)""",
        (id_venta, nombre, cantidad, precio, round(cantidad * precio, 2))
    )
    conn.commit()


def _total_ventas_hoy(conn):
    hoy = datetime.date.today().isoformat()
    row = conn.execute(
        "SELECT COALESCE(SUM(total), 0) as t FROM ventas WHERE date(fecha_creacion) = ? AND estado != 'ANULADA'",
        (hoy,)
    ).fetchone()
    return row['t']


# ---------------------------------------------------------------------------
# Tests: cálculo de totales de venta
# ---------------------------------------------------------------------------

class TestTotalesVenta:
    def test_total_linea_es_cantidad_por_precio(self, db_mem):
        id_v = _insertar_venta(db_mem, 30000)
        _insertar_detalle(db_mem, id_v, "Cerveza", 3, 10000)
        row = db_mem.execute(
            "SELECT total_linea FROM venta_detalle WHERE id_venta = ?", (id_v,)
        ).fetchone()
        assert row['total_linea'] == 30000

    def test_venta_anulada_no_suma_en_totales(self, db_mem):
        _insertar_venta(db_mem, 50000, estado='COMPLETADA')
        _insertar_venta(db_mem, 20000, estado='ANULADA')
        total = _total_ventas_hoy(db_mem)
        assert total == 50000, f"Las anuladas no deben sumarse, obtuvo {total}"

    def test_suma_multiples_ventas(self, db_mem):
        _insertar_venta(db_mem, 15000)
        _insertar_venta(db_mem, 25000)
        _insertar_venta(db_mem, 10000)
        total = _total_ventas_hoy(db_mem)
        assert total == 50000

    def test_cuenta_abierta_no_completada(self, db_mem):
        """Una cuenta abierta (saldo_pendiente > 0) no debe contarse como cobrada."""
        cur = db_mem.execute(
            """INSERT INTO ventas (numero_venta, tipo, estado, total, total_pagado, saldo_pendiente,
                                   metodo_pago, usuario_cajero, fecha_creacion)
               VALUES ('POS-TEST', 'cuenta_abierta', 'ABIERTA', 40000, 0, 40000,
                       'EFECTIVO', 'test', datetime('now','localtime'))"""
        )
        db_mem.commit()
        row = db_mem.execute(
            "SELECT COUNT(*) as c FROM ventas WHERE tipo = 'cuenta_abierta' AND estado = 'ABIERTA'"
        ).fetchone()
        assert row['c'] == 1


# ---------------------------------------------------------------------------
# Tests: lógica de caja diaria
# ---------------------------------------------------------------------------

class TestCajaDiaria:
    def test_caja_se_crea_con_estado_abierta(self, db_mem):
        hoy = datetime.date.today().isoformat()
        db_mem.execute(
            "INSERT INTO caja_diaria (fecha, saldo_inicio, estado, usuario) VALUES (?, 100000, 'ABIERTA', 'admin')",
            (hoy,)
        )
        db_mem.commit()
        row = db_mem.execute(
            "SELECT estado FROM caja_diaria WHERE fecha = ?", (hoy,)
        ).fetchone()
        assert row['estado'] == 'ABIERTA'

    def test_no_duplicate_caja_mismo_dia(self, db_mem):
        hoy = datetime.date.today().isoformat()
        db_mem.execute(
            "INSERT INTO caja_diaria (fecha, saldo_inicio, estado, usuario) VALUES (?, 50000, 'ABIERTA', 'admin')",
            (hoy,)
        )
        db_mem.commit()
        with pytest.raises(Exception):
            db_mem.execute(
                "INSERT INTO caja_diaria (fecha, saldo_inicio, estado, usuario) VALUES (?, 30000, 'ABIERTA', 'admin')",
                (hoy,)
            )
            db_mem.commit()

    def test_movimiento_registra_monto(self, db_mem):
        hoy = datetime.date.today().isoformat()
        db_mem.execute(
            "INSERT INTO caja_diaria (fecha, saldo_inicio, estado, usuario) VALUES (?, 0, 'ABIERTA', 'admin')",
            (hoy,)
        )
        db_mem.commit()
        id_caja = db_mem.execute("SELECT id_caja FROM caja_diaria WHERE fecha = ?", (hoy,)).fetchone()['id_caja']
        db_mem.execute(
            "INSERT INTO movimientos_caja (id_caja, tipo, concepto, monto, usuario) VALUES (?, 'INGRESO', 'Venta', 25000, 'admin')",
            (id_caja,)
        )
        db_mem.commit()
        row = db_mem.execute(
            "SELECT COALESCE(SUM(monto), 0) as total FROM movimientos_caja WHERE id_caja = ? AND tipo = 'INGRESO'",
            (id_caja,)
        ).fetchone()
        assert row['total'] == 25000


# ---------------------------------------------------------------------------
# Tests: gastos
# ---------------------------------------------------------------------------

class TestGastos:
    def test_gasto_se_inserta(self, db_mem):
        db_mem.execute(
            "INSERT INTO gastos (concepto, valor, categoria, metodo_pago, usuario) VALUES (?, ?, ?, ?, ?)",
            ("Papel higiénico", 8000, "Insumos", "EFECTIVO", "admin")
        )
        db_mem.commit()
        row = db_mem.execute("SELECT COUNT(*) as c FROM gastos").fetchone()
        assert row['c'] == 1

    def test_suma_gastos_del_mes(self, db_mem):
        mes_inicio = datetime.date.today().replace(day=1).isoformat()
        for valor in [5000, 10000, 3000]:
            db_mem.execute(
                "INSERT INTO gastos (concepto, valor, categoria, metodo_pago, usuario, fecha) VALUES (?, ?, ?, ?, ?, datetime('now','localtime'))",
                ("Test", valor, "Insumos", "EFECTIVO", "admin")
            )
        db_mem.commit()
        row = db_mem.execute(
            "SELECT COALESCE(SUM(valor), 0) as t FROM gastos WHERE date(fecha) >= ?",
            (mes_inicio,)
        ).fetchone()
        assert row['t'] == 18000
