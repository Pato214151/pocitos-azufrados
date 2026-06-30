"""
Tests para models/series.py — generadores de números consecutivos.
Cubren thread-safety, formato de salida e independencia entre series.
"""
import os
import sys
import sqlite3
import threading
import datetime
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from models.series import obtener_proximo_numero_venta, obtener_proximo_numero_boleta


# ---------------------------------------------------------------------------
# Fixture: BD temporal con schema mínimo para series
# ---------------------------------------------------------------------------

@pytest.fixture
def db_series(tmp_path):
    """BD en archivo temporal con las tablas de series necesarias."""
    db = str(tmp_path / "series_test.db")
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    ano = datetime.datetime.now().year
    conn.executescript(f"""
        CREATE TABLE series_facturacion (
            id_serie           INTEGER PRIMARY KEY AUTOINCREMENT,
            prefijo            TEXT NOT NULL,
            ano                INTEGER NOT NULL,
            consecutivo_actual INTEGER DEFAULT 0,
            activa             INTEGER DEFAULT 1,
            UNIQUE(prefijo, ano)
        );
        CREATE TABLE series_boletas (
            id_serie           INTEGER PRIMARY KEY AUTOINCREMENT,
            prefijo            TEXT NOT NULL,
            ano                INTEGER NOT NULL,
            consecutivo_actual INTEGER DEFAULT 0,
            activa             INTEGER DEFAULT 1,
            UNIQUE(prefijo, ano)
        );
        INSERT INTO series_facturacion (prefijo, ano, consecutivo_actual, activa)
            VALUES ('POS', {ano}, 0, 1);
        INSERT INTO series_boletas (prefijo, ano, consecutivo_actual, activa)
            VALUES ('BOL', {ano}, 0, 1);
    """)
    conn.commit()
    conn.close()
    return db


# ---------------------------------------------------------------------------
# Tests: obtener_proximo_numero_venta
# ---------------------------------------------------------------------------

class TestNumerosVenta:
    def test_formato_pos(self, db_series):
        num = obtener_proximo_numero_venta(db_series)
        assert num.startswith("POS-"), f"Esperaba prefijo POS-, obtuvo: {num}"

    def test_consecutivo_incrementa(self, db_series):
        n1 = obtener_proximo_numero_venta(db_series)
        n2 = obtener_proximo_numero_venta(db_series)
        # Formato: POS-YYYY-000001
        seq1 = int(n1.split("-")[2])
        seq2 = int(n2.split("-")[2])
        assert seq2 == seq1 + 1, f"Esperaba {seq1+1}, obtuvo {seq2}"

    def test_no_duplicados_concurrentes(self, db_series):
        """50 hilos piden número simultáneamente — deben ser todos únicos."""
        resultados = []
        lock = threading.Lock()

        def pedir():
            num = obtener_proximo_numero_venta(db_series)
            with lock:
                resultados.append(num)

        hilos = [threading.Thread(target=pedir) for _ in range(50)]
        for h in hilos:
            h.start()
        for h in hilos:
            h.join()

        assert len(resultados) == 50
        assert len(resultados) == len(set(resultados)), "Se generaron números de venta duplicados"


# ---------------------------------------------------------------------------
# Tests: obtener_proximo_numero_boleta
# ---------------------------------------------------------------------------

class TestNumerosBoleta:
    def test_formato_bol(self, db_series):
        num = obtener_proximo_numero_boleta(db_series)
        assert num.startswith("BOL-"), f"Esperaba prefijo BOL-, obtuvo: {num}"

    def test_independiente_de_ventas(self, db_series):
        """El consecutivo de boletas es independiente del de ventas."""
        for _ in range(5):
            obtener_proximo_numero_venta(db_series)
        b1 = obtener_proximo_numero_boleta(db_series)
        seq_b = int(b1.split("-")[2])
        assert seq_b == 1, f"Boletas deben reiniciar en 1 independiente de ventas, obtuvo {seq_b}"

    def test_no_duplicados_concurrentes(self, db_series):
        resultados = []
        lock = threading.Lock()

        def pedir():
            num = obtener_proximo_numero_boleta(db_series)
            with lock:
                resultados.append(num)

        hilos = [threading.Thread(target=pedir) for _ in range(50)]
        for h in hilos:
            h.start()
        for h in hilos:
            h.join()

        assert len(resultados) == len(set(resultados)), "Se generaron números de boleta duplicados"
