"""
Tests para models/validaciones.py — lógica DIAN y PIN admin.
Cubren todos los niveles de validación sin tocar la BD de producción.
"""
import os
import sys
import sqlite3
import datetime
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from models.validaciones import validar_resolucion_dian, verificar_pin_admin


# ─────────────────────────────────────────────────────────────────────────────
# Fixture: BD temporal con schema mínimo para validaciones
# ─────────────────────────────────────────────────────────────────────────────

def _fecha(delta_dias):
    """Retorna (hoy + delta_dias) como string YYYY-MM-DD."""
    return (datetime.date.today() + datetime.timedelta(days=delta_dias)).strftime('%Y-%m-%d')


@pytest.fixture
def db_validaciones(tmp_path):
    """BD temporal con tablas configuracion, series_facturacion y usuarios."""
    db = str(tmp_path / "val_test.db")
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    ano = datetime.datetime.now().year
    conn.executescript(f"""
        CREATE TABLE configuracion (
            id_config INTEGER PRIMARY KEY AUTOINCREMENT,
            clave TEXT UNIQUE NOT NULL,
            valor TEXT
        );
        CREATE TABLE series_facturacion (
            id_serie           INTEGER PRIMARY KEY AUTOINCREMENT,
            prefijo            TEXT NOT NULL,
            ano                INTEGER NOT NULL,
            consecutivo_actual INTEGER DEFAULT 0,
            activa             INTEGER DEFAULT 1,
            UNIQUE(prefijo, ano)
        );
        CREATE TABLE usuarios (
            id_usuario      INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario         TEXT UNIQUE NOT NULL,
            nombre_completo TEXT NOT NULL,
            contrasena_hash TEXT NOT NULL DEFAULT '',
            rol             TEXT NOT NULL DEFAULT 'cajero',
            activo          INTEGER DEFAULT 1,
            pin             TEXT
        );
        INSERT INTO series_facturacion (prefijo, ano, consecutivo_actual, activa)
            VALUES ('LP', {ano}, 0, 1);
    """)
    conn.commit()
    conn.close()
    return db


def _cfg(db, **kwargs):
    """Inserta o reemplaza claves en configuracion."""
    conn = sqlite3.connect(db)
    for clave, valor in kwargs.items():
        conn.execute(
            "INSERT OR REPLACE INTO configuracion (clave, valor) VALUES (?, ?)",
            (clave, str(valor))
        )
    conn.commit()
    conn.close()


def _serie(db, consecutivo):
    """Actualiza el consecutivo de la serie LP."""
    conn = sqlite3.connect(db)
    conn.execute(
        "UPDATE series_facturacion SET consecutivo_actual = ? WHERE prefijo = 'LP'",
        (consecutivo,)
    )
    conn.commit()
    conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# Tests: validar_resolucion_dian
# ─────────────────────────────────────────────────────────────────────────────

class TestValidarResolucionDian:

    def test_sin_resolucion_configurada_permite_emitir(self, db_validaciones):
        """Sin resolución configurada → ok, puede emitir."""
        r = validar_resolucion_dian(db_path=db_validaciones)
        assert r['puede_emitir'] is True
        assert r['nivel'] == 'ok'

    def test_resolucion_configurada_rango_amplio_fecha_lejana(self, db_validaciones):
        """Resolución con rango amplio y fecha lejana → ok."""
        _cfg(db_validaciones,
             resolucion_dian_numero='18764001234567',
             resolucion_dian_hasta='10000',
             resolucion_dian_prefijo='LP',
             resolucion_dian_fecha_hasta=_fecha(365))
        _serie(db_validaciones, 0)
        r = validar_resolucion_dian(db_path=db_validaciones)
        assert r['puede_emitir'] is True
        assert r['nivel'] == 'ok'

    def test_rango_agotado_bloquea(self, db_validaciones):
        """Rango agotado (consecutivo >= hasta) → bloqueado."""
        _cfg(db_validaciones,
             resolucion_dian_numero='18764001234567',
             resolucion_dian_hasta='100',
             resolucion_dian_prefijo='LP',
             resolucion_dian_fecha_hasta=_fecha(365))
        _serie(db_validaciones, 100)
        r = validar_resolucion_dian(db_path=db_validaciones)
        assert r['puede_emitir'] is False
        assert r['nivel'] == 'bloqueado'

    def test_rango_menor_50_bloquea(self, db_validaciones):
        """Quedan <= 50 números → bloqueado."""
        _cfg(db_validaciones,
             resolucion_dian_numero='18764001234567',
             resolucion_dian_hasta='100',
             resolucion_dian_prefijo='LP',
             resolucion_dian_fecha_hasta=_fecha(365))
        _serie(db_validaciones, 55)  # 100 - 55 = 45 restantes
        r = validar_resolucion_dian(db_path=db_validaciones)
        assert r['puede_emitir'] is False
        assert r['nivel'] == 'bloqueado'

    def test_rango_menor_500_advierte(self, db_validaciones):
        """Quedan <= 500 y > 50 números → advertencia."""
        _cfg(db_validaciones,
             resolucion_dian_numero='18764001234567',
             resolucion_dian_hasta='1000',
             resolucion_dian_prefijo='LP',
             resolucion_dian_fecha_hasta=_fecha(365))
        _serie(db_validaciones, 700)  # 1000 - 700 = 300 restantes
        r = validar_resolucion_dian(db_path=db_validaciones)
        assert r['puede_emitir'] is True
        assert r['nivel'] == 'advertencia'

    def test_fecha_vencida_bloquea(self, db_validaciones):
        """Fecha de resolución ya venció → bloqueado."""
        _cfg(db_validaciones,
             resolucion_dian_numero='18764001234567',
             resolucion_dian_hasta='10000',
             resolucion_dian_prefijo='LP',
             resolucion_dian_fecha_hasta=_fecha(-1))
        _serie(db_validaciones, 0)
        r = validar_resolucion_dian(db_path=db_validaciones)
        assert r['puede_emitir'] is False
        assert r['nivel'] == 'bloqueado'

    def test_fecha_vence_en_2_dias_bloquea(self, db_validaciones):
        """Fecha vence en <= 3 días → bloqueado (urgente)."""
        _cfg(db_validaciones,
             resolucion_dian_numero='18764001234567',
             resolucion_dian_hasta='10000',
             resolucion_dian_prefijo='LP',
             resolucion_dian_fecha_hasta=_fecha(2))
        _serie(db_validaciones, 0)
        r = validar_resolucion_dian(db_path=db_validaciones)
        assert r['puede_emitir'] is False
        assert r['nivel'] == 'bloqueado'

    def test_fecha_vence_en_15_dias_advierte(self, db_validaciones):
        """Fecha vence en <= 30 días → advertencia."""
        _cfg(db_validaciones,
             resolucion_dian_numero='18764001234567',
             resolucion_dian_hasta='10000',
             resolucion_dian_prefijo='LP',
             resolucion_dian_fecha_hasta=_fecha(15))
        _serie(db_validaciones, 0)
        r = validar_resolucion_dian(db_path=db_validaciones)
        assert r['puede_emitir'] is True
        assert r['nivel'] == 'advertencia'

    def test_fecha_mal_formateada_no_bloquea(self, db_validaciones):
        """Fecha con formato inválido no bloquea (falla silenciosa)."""
        _cfg(db_validaciones,
             resolucion_dian_numero='18764001234567',
             resolucion_dian_hasta='10000',
             resolucion_dian_prefijo='LP',
             resolucion_dian_fecha_hasta='31/12/2099')  # formato incorrecto
        _serie(db_validaciones, 0)
        r = validar_resolucion_dian(db_path=db_validaciones)
        assert r['puede_emitir'] is True

    def test_rango_agota_tiene_prioridad_sobre_fecha(self, db_validaciones):
        """Rango agotado bloquea aunque la fecha sea lejana."""
        _cfg(db_validaciones,
             resolucion_dian_numero='18764001234567',
             resolucion_dian_hasta='50',
             resolucion_dian_prefijo='LP',
             resolucion_dian_fecha_hasta=_fecha(365))
        _serie(db_validaciones, 50)
        r = validar_resolucion_dian(db_path=db_validaciones)
        assert r['nivel'] == 'bloqueado'


# ─────────────────────────────────────────────────────────────────────────────
# Tests: verificar_pin_admin
# ─────────────────────────────────────────────────────────────────────────────

class TestVerificarPinAdmin:

    def _insertar_admin(self, db, nombre, pin_plaintext):
        conn = sqlite3.connect(db)
        conn.execute(
            "INSERT INTO usuarios (usuario, nombre_completo, rol, pin) VALUES (?, ?, 'administrador', ?)",
            (nombre.lower(), nombre, pin_plaintext)
        )
        conn.commit()
        conn.close()

    def test_pin_invalido_formato_rechaza(self, db_validaciones):
        """PIN con letras o longitud incorrecta → False."""
        assert verificar_pin_admin("abc1", db_path=db_validaciones) == (False, None)
        assert verificar_pin_admin("12345", db_path=db_validaciones) == (False, None)
        assert verificar_pin_admin("", db_path=db_validaciones) == (False, None)
        assert verificar_pin_admin(None, db_path=db_validaciones) == (False, None)

    def test_sin_admins_rechaza(self, db_validaciones):
        """Sin administradores en BD → False."""
        ok, nombre = verificar_pin_admin("1234", db_path=db_validaciones)
        assert ok is False
        assert nombre is None

    def test_pin_correcto_plaintext_acepta(self, db_validaciones):
        """PIN legado en plaintext correcto → True + nombre."""
        self._insertar_admin(db_validaciones, "Julian Admin", "5678")
        ok, nombre = verificar_pin_admin("5678", db_path=db_validaciones)
        assert ok is True
        assert nombre == "Julian Admin"

    def test_pin_incorrecto_rechaza(self, db_validaciones):
        """PIN incorrecto → False."""
        self._insertar_admin(db_validaciones, "Julian Admin", "5678")
        ok, nombre = verificar_pin_admin("9999", db_path=db_validaciones)
        assert ok is False

    def test_cajero_con_mismo_pin_no_valida(self, db_validaciones):
        """Un cajero con el mismo PIN no debe validar (solo admins)."""
        conn = sqlite3.connect(db_validaciones)
        conn.execute(
            "INSERT INTO usuarios (usuario, nombre_completo, rol, pin) VALUES ('cajero1', 'Cajero Test', 'cajero', '1111')"
        )
        conn.commit()
        conn.close()
        ok, nombre = verificar_pin_admin("1111", db_path=db_validaciones)
        assert ok is False

    def test_admin_inactivo_no_valida(self, db_validaciones):
        """Admin con activo=0 no debe validar."""
        conn = sqlite3.connect(db_validaciones)
        conn.execute(
            "INSERT INTO usuarios (usuario, nombre_completo, rol, activo, pin) "
            "VALUES ('admin_inactivo', 'Admin Inactivo', 'administrador', 0, '2222')"
        )
        conn.commit()
        conn.close()
        ok, _ = verificar_pin_admin("2222", db_path=db_validaciones)
        assert ok is False

    def test_admin_sin_pin_no_bloquea_a_otros(self, db_validaciones):
        """Admin sin PIN configurado no causa error para el admin con PIN."""
        conn = sqlite3.connect(db_validaciones)
        conn.execute(
            "INSERT INTO usuarios (usuario, nombre_completo, rol, pin) "
            "VALUES ('admin_sin_pin', 'Admin Sin PIN', 'administrador', NULL)"
        )
        conn.execute(
            "INSERT INTO usuarios (usuario, nombre_completo, rol, pin) "
            "VALUES ('admin_con_pin', 'Admin Con PIN', 'administrador', '3333')"
        )
        conn.commit()
        conn.close()
        ok, nombre = verificar_pin_admin("3333", db_path=db_validaciones)
        assert ok is True
        assert nombre == "Admin Con PIN"
