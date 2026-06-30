"""
Tests para database/connection.py — context managers y retry logic.
"""
import os
import sys
import sqlite3
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from database.connection import conexion_segura, transaccion_atomica, get_connection


def _crear_tabla(db_path):
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE t (v INTEGER)")
    conn.commit()
    conn.close()


class TestConexionSegura:
    def test_commit_en_exito(self, tmp_path):
        db = str(tmp_path / "test.db")
        _crear_tabla(db)

        with conexion_segura(db_path=db) as conn:
            conn.execute("INSERT INTO t VALUES (42)")

        conn2 = sqlite3.connect(db)
        row = conn2.execute("SELECT v FROM t").fetchone()
        conn2.close()
        assert row[0] == 42

    def test_rollback_en_error(self, tmp_path):
        db = str(tmp_path / "test2.db")
        _crear_tabla(db)

        with pytest.raises(ValueError):
            with conexion_segura(db_path=db) as conn:
                conn.execute("INSERT INTO t VALUES (99)")
                raise ValueError("error intencional")

        conn2 = sqlite3.connect(db)
        row = conn2.execute("SELECT COUNT(*) FROM t").fetchone()
        conn2.close()
        assert row[0] == 0, "El rollback no se aplicó"

    def test_row_factory_activo(self, tmp_path):
        db = str(tmp_path / "test3.db")
        _crear_tabla(db)
        c = sqlite3.connect(db)
        c.execute("INSERT INTO t VALUES (7)")
        c.commit()
        c.close()

        with conexion_segura(db_path=db) as conn:
            row = conn.execute("SELECT v FROM t").fetchone()
        # row_factory=sqlite3.Row permite acceso por nombre
        assert row['v'] == 7


class TestTransaccionAtomica:
    def test_commit_en_exito(self, tmp_path):
        db = str(tmp_path / "at.db")
        _crear_tabla(db)

        with transaccion_atomica(db_path=db) as conn:
            conn.execute("INSERT INTO t VALUES (100)")

        conn2 = sqlite3.connect(db)
        assert conn2.execute("SELECT COUNT(*) FROM t").fetchone()[0] == 1
        conn2.close()

    def test_rollback_en_error(self, tmp_path):
        db = str(tmp_path / "at2.db")
        _crear_tabla(db)

        with pytest.raises(RuntimeError):
            with transaccion_atomica(db_path=db) as conn:
                conn.execute("INSERT INTO t VALUES (200)")
                raise RuntimeError("fallo forzado")

        conn2 = sqlite3.connect(db)
        assert conn2.execute("SELECT COUNT(*) FROM t").fetchone()[0] == 0
        conn2.close()


class TestGetConnection:
    def test_pragmas_aplicados(self, tmp_path):
        db = str(tmp_path / "pragma.db")
        conn = get_connection(db_path=db)
        jm = conn.execute("PRAGMA journal_mode").fetchone()[0]
        fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
        conn.close()
        assert jm == 'wal'
        assert fk == 1
