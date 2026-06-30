"""
Tests para models/ventas.py — crear_venta, abrir_cuenta_abierta, verificar_stock_minimo.
Usan BD temporal en memoria vía tmp_path; no tocan la BD de producción.
"""
import os
import sys
import sqlite3
import datetime
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from models.ventas import crear_venta, abrir_cuenta_abierta, verificar_stock_minimo

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

USUARIO = {
    'id_usuario': 1,
    'usuario': 'test_cajero',
    'nombre_completo': 'Test Cajero',
}


def _item(id_producto=1, nombre='Producto', cantidad=2, precio=5000,
          requiere_cocina=False, controla_stock=False, es_boleta=False,
          es_almuerzo=False, **extra):
    base = {
        'id_producto': id_producto,
        'nombre': nombre,
        'cantidad': cantidad,
        'precio': precio,
        'total': precio * cantidad,
        'requiere_cocina': requiere_cocina,
        'controla_stock': controla_stock,
        'es_boleta': es_boleta,
        'es_almuerzo': es_almuerzo,
    }
    base.update(extra)
    return base


def _conn(db):
    c = sqlite3.connect(db)
    c.row_factory = sqlite3.Row
    return c


def _count(db, tabla, where='1=1'):
    with _conn(db) as c:
        return c.execute(f"SELECT COUNT(*) FROM {tabla} WHERE {where}").fetchone()[0]


# ─────────────────────────────────────────────────────────────────────────────
# Fixture
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def db(tmp_path):
    """BD temporal con schema mínimo para models/ventas.py."""
    path = str(tmp_path / "ventas_test.db")
    ano = datetime.datetime.now().year
    conn = sqlite3.connect(path)
    conn.executescript(f"""
        CREATE TABLE series_facturacion (
            id_serie           INTEGER PRIMARY KEY AUTOINCREMENT,
            prefijo            TEXT NOT NULL,
            ano                INTEGER NOT NULL,
            consecutivo_actual INTEGER DEFAULT 0,
            activa             INTEGER DEFAULT 1,
            UNIQUE(prefijo, ano)
        );
        INSERT INTO series_facturacion (prefijo, ano, consecutivo_actual, activa)
            VALUES ('POS', {ano}, 0, 1);
        INSERT INTO series_facturacion (prefijo, ano, consecutivo_actual, activa)
            VALUES ('LP', {ano}, 0, 1);

        CREATE TABLE ventas (
            id_venta        INTEGER PRIMARY KEY AUTOINCREMENT,
            numero_venta    TEXT UNIQUE,
            tipo            TEXT,
            estado          TEXT,
            cliente_nombre  TEXT,
            id_cliente      INTEGER,
            subtotal        REAL DEFAULT 0,
            descuento       REAL DEFAULT 0,
            motivo_descuento TEXT,
            total           REAL DEFAULT 0,
            total_pagado    REAL DEFAULT 0,
            saldo_pendiente REAL DEFAULT 0,
            metodo_pago     TEXT,
            notas           TEXT,
            id_usuario      INTEGER,
            usuario_nombre  TEXT,
            fecha_pago      TEXT
        );
        CREATE TABLE venta_detalle (
            id_detalle      INTEGER PRIMARY KEY AUTOINCREMENT,
            id_venta        INTEGER,
            id_producto     INTEGER,
            producto_nombre TEXT,
            cantidad        INTEGER,
            precio_unitario REAL,
            total_linea     REAL,
            estado_cocina   TEXT
        );
        CREATE TABLE productos (
            id_producto        INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre             TEXT,
            stock_actual       REAL DEFAULT 0,
            stock_minimo       REAL DEFAULT 0,
            activo             INTEGER DEFAULT 1,
            fecha_actualizacion TEXT
        );
        CREATE TABLE movimientos_inventario (
            id_mov          INTEGER PRIMARY KEY AUTOINCREMENT,
            id_producto     INTEGER,
            tipo            TEXT,
            cantidad        REAL,
            motivo          TEXT,
            referencia      TEXT,
            usuario         TEXT,
            stock_anterior  REAL,
            stock_nuevo     REAL
        );
        CREATE TABLE ordenes_cocina (
            id_orden        INTEGER PRIMARY KEY AUTOINCREMENT,
            id_venta        INTEGER,
            id_detalle      INTEGER,
            numero_venta    TEXT,
            producto_nombre TEXT,
            cantidad        INTEGER,
            cliente_nombre  TEXT
        );
        CREATE TABLE reservas_almuerzo (
            id_reserva          INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_nombre      TEXT,
            cantidad_almuerzos  INTEGER,
            tipo_almuerzo       TEXT,
            hora_entrega_estimada TEXT,
            estado              TEXT,
            notas               TEXT,
            id_usuario          INTEGER
        );
        CREATE TABLE pagos (
            id_pago         INTEGER PRIMARY KEY AUTOINCREMENT,
            id_venta        INTEGER,
            valor           REAL,
            metodo_pago     TEXT,
            usuario_registro TEXT,
            monto_recibido  REAL
        );
        CREATE TABLE caja_diaria (
            id_caja         INTEGER PRIMARY KEY AUTOINCREMENT,
            estado          TEXT,
            monto_inicial   REAL DEFAULT 0,
            total_ventas    REAL DEFAULT 0,
            total_boletas   REAL DEFAULT 0,
            total_gastos    REAL DEFAULT 0,
            monto_esperado  REAL DEFAULT 0
        );
        CREATE TABLE movimientos_caja (
            id_mov          INTEGER PRIMARY KEY AUTOINCREMENT,
            id_caja         INTEGER,
            tipo            TEXT,
            concepto        TEXT,
            valor           REAL,
            metodo_pago     TEXT,
            referencia      TEXT,
            usuario         TEXT
        );
        CREATE TABLE facturas_electronicas (
            id_factura      INTEGER PRIMARY KEY AUTOINCREMENT,
            id_venta        INTEGER,
            numero_factura  TEXT,
            cliente_nombre  TEXT,
            cliente_nit     TEXT,
            cliente_email   TEXT,
            usuario_registro TEXT
        );
        CREATE TABLE auditoria (
            id_auditoria    INTEGER PRIMARY KEY AUTOINCREMENT,
            tabla_afectada  TEXT,
            id_registro     INTEGER,
            accion          TEXT,
            usuario         TEXT,
            comentario      TEXT,
            datos_anteriores TEXT,
            datos_nuevos    TEXT
        );
    """)
    conn.commit()
    conn.close()
    return path


def _insertar_producto(db, id_producto=1, stock=10, stock_minimo=2):
    with _conn(db) as c:
        c.execute(
            "INSERT OR REPLACE INTO productos (id_producto, nombre, stock_actual, stock_minimo, activo) "
            "VALUES (?, 'Prod Test', ?, ?, 1)",
            (id_producto, stock, stock_minimo)
        )
        c.commit()


def _abrir_caja(db, monto_inicial=100000):
    with _conn(db) as c:
        c.execute(
            "INSERT INTO caja_diaria (estado, monto_inicial, total_ventas, total_boletas, total_gastos, monto_esperado) "
            "VALUES ('ABIERTA', ?, 0, 0, 0, ?)",
            (monto_inicial, monto_inicial)
        )
        c.commit()


# ─────────────────────────────────────────────────────────────────────────────
# Tests: crear_venta
# ─────────────────────────────────────────────────────────────────────────────

class TestCrearVenta:

    def _base(self, db, **kwargs):
        defaults = dict(
            carrito=[_item()],
            total_venta=10000,
            descuento=0,
            motivo_descuento=None,
            metodo_pago='EFECTIVO',
            pago_split=None,
            monto_recibido=10000,
            id_cliente=None,
            cliente_nombre=None,
            notas=None,
            datos_fe=None,
            usuario=USUARIO,
            db_path=db,
        )
        defaults.update(kwargs)
        return crear_venta(**defaults)

    def test_retorna_id_y_numero(self, db):
        r = self._base(db)
        assert isinstance(r['id_venta'], int) and r['id_venta'] > 0
        assert r['numero'].startswith('POS-')
        assert r['numero_fe'] is None
        assert r['tiene_cocina'] is False

    def test_fila_en_ventas(self, db):
        r = self._base(db)
        assert _count(db, 'ventas', f"id_venta = {r['id_venta']}") == 1

    def test_fila_en_pagos_efectivo(self, db):
        r = self._base(db)
        assert _count(db, 'pagos', f"id_venta = {r['id_venta']}") == 1

    def test_pago_mixto_dos_filas(self, db):
        split = {'efectivo': 6000, 'transferencia': 4000, 'metodo_transfer': 'NEQUI'}
        r = self._base(db, metodo_pago='MIXTO', pago_split=split, monto_recibido=None)
        assert _count(db, 'pagos', f"id_venta = {r['id_venta']}") == 2

    def test_sin_caja_no_crea_movimiento(self, db):
        r = self._base(db)
        assert _count(db, 'movimientos_caja') == 0

    def test_con_caja_crea_movimiento(self, db):
        _abrir_caja(db)
        r = self._base(db)
        assert _count(db, 'movimientos_caja', f"referencia = '{r['numero']}'") == 1

    def test_con_caja_mixto_dos_movimientos(self, db):
        _abrir_caja(db)
        split = {'efectivo': 6000, 'transferencia': 4000, 'metodo_transfer': 'NEQUI'}
        r = self._base(db, metodo_pago='MIXTO', pago_split=split, monto_recibido=None)
        assert _count(db, 'movimientos_caja', f"id_caja = 1") == 2

    def test_descuento_registra_auditoria(self, db):
        r = self._base(db, descuento=1000, motivo_descuento='Promocion especial del dia')
        assert _count(db, 'auditoria', f"accion = 'DESCUENTO' AND id_registro = {r['id_venta']}") == 1

    def test_item_controla_stock_descuenta_inventario(self, db):
        _insertar_producto(db, stock=10)
        carrito = [_item(controla_stock=True)]
        r = self._base(db, carrito=carrito)
        with _conn(db) as c:
            stock = c.execute("SELECT stock_actual FROM productos WHERE id_producto = 1").fetchone()[0]
        assert stock == 8  # 10 - 2

    def test_stock_insuficiente_lanza_valueerror(self, db):
        _insertar_producto(db, stock=1)
        carrito = [_item(controla_stock=True, cantidad=5)]
        with pytest.raises(ValueError, match="Stock insuficiente"):
            self._base(db, carrito=carrito, total_venta=25000)

    def test_stock_insuficiente_rollback_no_guarda_venta(self, db):
        _insertar_producto(db, stock=1)
        carrito = [_item(controla_stock=True, cantidad=5)]
        try:
            self._base(db, carrito=carrito, total_venta=25000)
        except ValueError:
            pass
        assert _count(db, 'ventas') == 0

    def test_item_requiere_cocina_crea_orden(self, db):
        carrito = [_item(requiere_cocina=True)]
        r = self._base(db, carrito=carrito)
        assert r['tiene_cocina'] is True
        assert _count(db, 'ordenes_cocina', f"id_venta = {r['id_venta']}") == 1

    def test_item_almuerzo_crea_reserva_no_orden(self, db):
        carrito = [_item(requiere_cocina=True, es_almuerzo=True,
                         pedido_nombre='Juan', pedido_hora='12:30',
                         pedido_notas='Sin cebolla')]
        r = self._base(db, carrito=carrito)
        assert _count(db, 'reservas_almuerzo') == 1
        assert _count(db, 'ordenes_cocina') == 0

    def test_item_boleta_no_descuenta_inventario(self, db):
        _insertar_producto(db, stock=10)
        carrito = [_item(es_boleta=True, controla_stock=True)]
        self._base(db, carrito=carrito)
        with _conn(db) as c:
            stock = c.execute("SELECT stock_actual FROM productos WHERE id_producto = 1").fetchone()[0]
        assert stock == 10  # no cambia

    def test_con_datos_fe_genera_numero_fe(self, db):
        datos_fe = {'nombre': 'Cliente SA', 'nit': '900111222-3', 'email': 'a@b.com'}
        r = self._base(db, datos_fe=datos_fe)
        assert r['numero_fe'] is not None
        assert r['numero_fe'].startswith('LP-')
        assert _count(db, 'facturas_electronicas', f"id_venta = {r['id_venta']}") == 1

    def test_numeros_consecutivos_no_se_repiten(self, db):
        r1 = self._base(db)
        r2 = self._base(db)
        assert r1['numero'] != r2['numero']


# ─────────────────────────────────────────────────────────────────────────────
# Tests: abrir_cuenta_abierta
# ─────────────────────────────────────────────────────────────────────────────

class TestAbrirCuentaAbierta:

    def _base(self, db, **kwargs):
        defaults = dict(
            carrito=[_item()],
            total_venta=10000,
            descuento=0,
            id_cliente=None,
            cliente_nombre='Mesa 3',
            notas=None,
            usuario=USUARIO,
            db_path=db,
        )
        defaults.update(kwargs)
        return abrir_cuenta_abierta(**defaults)

    def test_retorna_id_y_numero(self, db):
        r = self._base(db)
        assert isinstance(r['id_venta'], int) and r['id_venta'] > 0
        assert r['numero'].startswith('POS-')

    def test_tipo_y_estado_correctos(self, db):
        r = self._base(db)
        with _conn(db) as c:
            row = c.execute("SELECT tipo, estado FROM ventas WHERE id_venta = ?",
                            (r['id_venta'],)).fetchone()
        assert row['tipo'] == 'cuenta_abierta'
        assert row['estado'] == 'ABIERTA'

    def test_detalle_insertado(self, db):
        r = self._base(db)
        assert _count(db, 'venta_detalle', f"id_venta = {r['id_venta']}") == 1

    def test_no_crea_pago(self, db):
        r = self._base(db)
        assert _count(db, 'pagos', f"id_venta = {r['id_venta']}") == 0

    def test_item_cocina_crea_orden(self, db):
        r = self._base(db, carrito=[_item(requiere_cocina=True)])
        assert _count(db, 'ordenes_cocina', f"id_venta = {r['id_venta']}") == 1


# ─────────────────────────────────────────────────────────────────────────────
# Tests: verificar_stock_minimo
# ─────────────────────────────────────────────────────────────────────────────

class TestVerificarStockMinimo:

    def test_lista_vacia_retorna_vacia(self, db):
        assert verificar_stock_minimo([], 'cajero', db_path=db) == []

    def test_sin_productos_bajo_minimo_retorna_vacia(self, db):
        _insertar_producto(db, stock=10, stock_minimo=2)
        result = verificar_stock_minimo([1], 'cajero', db_path=db)
        assert result == []

    def test_producto_bajo_minimo_retorna_fila(self, db):
        _insertar_producto(db, stock=1, stock_minimo=5)
        result = verificar_stock_minimo([1], 'cajero', db_path=db)
        assert len(result) == 1
        assert result[0]['id_producto'] == 1

    def test_producto_igual_minimo_retorna_fila(self, db):
        _insertar_producto(db, stock=3, stock_minimo=3)
        result = verificar_stock_minimo([1], 'cajero', db_path=db)
        assert len(result) == 1

    def test_producto_bajo_minimo_registra_auditoria(self, db):
        _insertar_producto(db, stock=1, stock_minimo=5)
        verificar_stock_minimo([1], 'cajero', db_path=db)
        assert _count(db, 'auditoria', "accion = 'STOCK_BAJO'") == 1

    def test_id_inexistente_ignorado(self, db):
        result = verificar_stock_minimo([9999], 'cajero', db_path=db)
        assert result == []
