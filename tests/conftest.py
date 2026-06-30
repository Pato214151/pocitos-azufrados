"""
conftest.py — Fixtures compartidos para todos los tests de Pocitos Azufrados.

Crea una BD SQLite en memoria con el esquema completo para cada sesión de tests,
sin tocar la BD de producción (data/pocitos_azufrados.db).
"""
import os
import sys
import sqlite3
import pytest

# Asegurar que el paquete raíz esté en el path
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def _crear_schema(conn):
    """Aplica el esquema mínimo necesario para los tests."""
    conn.executescript("""
        PRAGMA journal_mode=WAL;
        PRAGMA foreign_keys=ON;

        CREATE TABLE IF NOT EXISTS configuracion (
            id_config  INTEGER PRIMARY KEY AUTOINCREMENT,
            clave      TEXT UNIQUE NOT NULL,
            valor      TEXT,
            tipo       TEXT DEFAULT 'texto',
            descripcion TEXT
        );

        CREATE TABLE IF NOT EXISTS usuarios (
            id_usuario          INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario             TEXT UNIQUE NOT NULL,
            nombre_completo     TEXT NOT NULL,
            contrasena_hash     TEXT NOT NULL,
            rol                 TEXT NOT NULL DEFAULT 'cajero',
            activo              INTEGER DEFAULT 1,
            email               TEXT,
            avatar_color        TEXT DEFAULT '#1976D2',
            ultimo_login        TEXT,
            debe_cambiar_password INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS sesiones (
            id_sesion    INTEGER PRIMARY KEY AUTOINCREMENT,
            id_usuario   INTEGER NOT NULL,
            fecha_inicio TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            fecha_fin    TEXT,
            FOREIGN KEY (id_usuario) REFERENCES usuarios(id_usuario)
        );

        CREATE TABLE IF NOT EXISTS categorias (
            id_categoria INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre       TEXT NOT NULL,
            descripcion  TEXT,
            color        TEXT DEFAULT '#1976D2',
            icono        TEXT DEFAULT '',
            orden        INTEGER DEFAULT 0,
            activa       INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS productos (
            id_producto     INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre          TEXT NOT NULL,
            descripcion     TEXT,
            precio_venta    REAL NOT NULL DEFAULT 0,
            costo           REAL DEFAULT 0,
            stock_actual    REAL DEFAULT 0,
            stock_minimo    REAL DEFAULT 0,
            unidad_medida   TEXT DEFAULT 'UND',
            codigo_barras   TEXT,
            id_categoria    INTEGER,
            activo          INTEGER DEFAULT 1,
            requiere_cocina INTEGER DEFAULT 0,
            FOREIGN KEY (id_categoria) REFERENCES categorias(id_categoria)
        );

        CREATE TABLE IF NOT EXISTS ventas (
            id_venta        INTEGER PRIMARY KEY AUTOINCREMENT,
            numero_venta    TEXT UNIQUE,
            tipo            TEXT DEFAULT 'venta',
            estado          TEXT DEFAULT 'COMPLETADA',
            total           REAL DEFAULT 0,
            total_pagado    REAL DEFAULT 0,
            saldo_pendiente REAL DEFAULT 0,
            metodo_pago     TEXT,
            cliente_nombre  TEXT,
            usuario_cajero  TEXT,
            fecha_creacion  TEXT DEFAULT (datetime('now','localtime')),
            id_cliente      INTEGER
        );

        CREATE TABLE IF NOT EXISTS venta_detalle (
            id_detalle      INTEGER PRIMARY KEY AUTOINCREMENT,
            id_venta        INTEGER NOT NULL,
            id_producto     INTEGER,
            producto_nombre TEXT NOT NULL,
            cantidad        REAL NOT NULL DEFAULT 1,
            precio_unitario REAL NOT NULL DEFAULT 0,
            total_linea     REAL NOT NULL DEFAULT 0,
            FOREIGN KEY (id_venta) REFERENCES ventas(id_venta)
        );

        CREATE TABLE IF NOT EXISTS caja_diaria (
            id_caja      INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha        TEXT UNIQUE NOT NULL,
            saldo_inicio REAL DEFAULT 0,
            saldo_fin    REAL,
            estado       TEXT DEFAULT 'ABIERTA',
            usuario      TEXT
        );

        CREATE TABLE IF NOT EXISTS movimientos_caja (
            id_movimiento INTEGER PRIMARY KEY AUTOINCREMENT,
            id_caja       INTEGER,
            tipo          TEXT NOT NULL,
            concepto      TEXT,
            monto         REAL NOT NULL,
            usuario       TEXT,
            fecha         TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (id_caja) REFERENCES caja_diaria(id_caja)
        );

        CREATE TABLE IF NOT EXISTS gastos (
            id_gasto    INTEGER PRIMARY KEY AUTOINCREMENT,
            concepto    TEXT NOT NULL,
            valor       REAL NOT NULL,
            categoria   TEXT,
            metodo_pago TEXT DEFAULT 'EFECTIVO',
            usuario     TEXT,
            fecha       TEXT DEFAULT (datetime('now','localtime')),
            notas       TEXT
        );

        CREATE TABLE IF NOT EXISTS series_facturacion (
            id_serie            INTEGER PRIMARY KEY AUTOINCREMENT,
            prefijo             TEXT NOT NULL,
            ano                 INTEGER NOT NULL,
            consecutivo_actual  INTEGER DEFAULT 0,
            activa              INTEGER DEFAULT 1,
            UNIQUE(prefijo, ano)
        );

        CREATE TABLE IF NOT EXISTS series_boletas (
            id_serie            INTEGER PRIMARY KEY AUTOINCREMENT,
            prefijo             TEXT NOT NULL,
            ano                 INTEGER NOT NULL,
            consecutivo_actual  INTEGER DEFAULT 0,
            activa              INTEGER DEFAULT 1,
            UNIQUE(prefijo, ano)
        );

        CREATE TABLE IF NOT EXISTS auditoria (
            id_auditoria INTEGER PRIMARY KEY AUTOINCREMENT,
            tabla        TEXT,
            id_registro  INTEGER,
            accion       TEXT,
            usuario      TEXT,
            fecha        TEXT DEFAULT (datetime('now','localtime')),
            comentario   TEXT
        );
    """)
    conn.commit()


@pytest.fixture(scope="function")
def db_mem():
    """BD SQLite en memoria con esquema completo. Se destruye al terminar cada test."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    _crear_schema(conn)
    yield conn
    conn.close()
