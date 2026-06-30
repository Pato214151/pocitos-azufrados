#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════╗
║  🏖️  CLUB LOS POCITOS AZUFRADOS                         ║
║   Sistema POS - Punto de Venta                           ║
║   Tocaima, Cundinamarca                                  ║
║   v1.0.0                                                 ║
╚══════════════════════════════════════════════════════════╝
"""

import logging
import os
import sys
import sqlite3
import threading
import datetime
import tkinter as tk
from tkinter import messagebox

# DPI awareness en Windows: evita que el sistema escale la app y todo se vea grande
if sys.platform == 'win32':
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

# Determinar directorio base
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

sys.path.insert(0, BASE_DIR)
os.chdir(BASE_DIR)


def verificar_configuracion():
    """Verifica que la base de datos existe"""
    db_path = os.path.join(BASE_DIR, "data", "pocitos_azufrados.db")

    if not os.path.exists(db_path):
        # Buscar en ubicación alternativa
        alt_path = os.path.join(os.path.dirname(BASE_DIR), "data", "pocitos_azufrados.db")
        if os.path.exists(alt_path):
            return alt_path

        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "Error de Configuración",
            "No se encontró la base de datos.\n\n"
            "Ejecute primero:\n"
            "  python setup.py\n\n"
            f"Buscado en: {db_path}"
        )
        root.destroy()
        sys.exit(1)

    return db_path


# Versión de esquema de BD — incrementar al agregar tablas/columnas en AMBOS setup.py Y aquí.
SCHEMA_VERSION = 14


def aplicar_migraciones(db_path):
    """Aplica migraciones de esquema para bases de datos existentes.
    Es idempotente: se puede ejecutar varias veces sin problemas.
    Cada paso es independiente: un fallo no impide los siguientes.
    Las migraciones críticas (tablas esenciales) bloquean el arranque si fallan."""
    import traceback
    import datetime as _dt

    errores_criticos = []
    errores_menores  = []

    conn = None
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 60000")
        cursor = conn.cursor()
    except Exception as e:
        # Sin conexión no hay nada que hacer — esto sí bloquea
        raise RuntimeError(f"No se pudo abrir la base de datos para migraciones: {e}") from e

    def _paso(desc, critico, fn):
        try:
            fn()
        except Exception as e:
            msg = f"[migración] {desc}: {e}\n{traceback.format_exc()}"
            if critico:
                errores_criticos.append(msg)
            else:
                errores_menores.append(msg)

    # ── Columnas en usuarios ────────────────────────────────────────────────
    def _col_usuarios():
        columnas = [r[1] for r in cursor.execute("PRAGMA table_info(usuarios)").fetchall()]
        if 'debe_cambiar_password' not in columnas:
            cursor.execute("ALTER TABLE usuarios ADD COLUMN debe_cambiar_password INTEGER DEFAULT 0")
        if 'pin' not in columnas:
            cursor.execute("ALTER TABLE usuarios ADD COLUMN pin TEXT")
    _paso("columnas usuarios", critico=True, fn=_col_usuarios)

    # ── Tabla sesiones ──────────────────────────────────────────────────────
    _paso("tabla sesiones", critico=True, fn=lambda: cursor.execute("""
        CREATE TABLE IF NOT EXISTS sesiones (
            id_sesion INTEGER PRIMARY KEY AUTOINCREMENT,
            id_usuario INTEGER NOT NULL,
            fecha_inicio TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            fecha_fin TEXT,
            FOREIGN KEY (id_usuario) REFERENCES usuarios(id_usuario)
        )
    """))

    # ── Tabla clientes ──────────────────────────────────────────────────────
    _paso("tabla clientes", critico=True, fn=lambda: cursor.execute("""
        CREATE TABLE IF NOT EXISTS clientes (
            id_cliente INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            celular TEXT,
            documento TEXT,
            email TEXT,
            notas TEXT,
            fecha_creacion TEXT DEFAULT (datetime('now','localtime'))
        )
    """))

    # ── Tabla proveedores ───────────────────────────────────────────────────
    _paso("tabla proveedores", critico=True, fn=lambda: cursor.execute("""
        CREATE TABLE IF NOT EXISTS proveedores (
            id_proveedor INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            celular TEXT,
            documento TEXT,
            email TEXT,
            notas TEXT,
            fecha_creacion TEXT DEFAULT (datetime('now','localtime'))
        )
    """))

    # ── Tabla compras_proveedor ─────────────────────────────────────────────
    _paso("tabla compras_proveedor", critico=True, fn=lambda: cursor.execute("""
        CREATE TABLE IF NOT EXISTS compras_proveedor (
            id_compra INTEGER PRIMARY KEY AUTOINCREMENT,
            id_proveedor INTEGER NOT NULL,
            concepto TEXT NOT NULL,
            valor REAL NOT NULL,
            metodo_pago TEXT DEFAULT 'EFECTIVO',
            estado_pago TEXT DEFAULT 'PENDIENTE'
                CHECK(estado_pago IN ('PENDIENTE','PAGADA')),
            fecha TEXT DEFAULT (datetime('now','localtime')),
            usuario_registro TEXT NOT NULL,
            notas TEXT,
            FOREIGN KEY (id_proveedor) REFERENCES proveedores(id_proveedor)
        )
    """))

    # ── Tabla variantes_producto ────────────────────────────────────────────
    _paso("tabla variantes_producto", critico=True, fn=lambda: cursor.execute("""
        CREATE TABLE IF NOT EXISTS variantes_producto (
            id_variante INTEGER PRIMARY KEY AUTOINCREMENT,
            id_producto INTEGER NOT NULL,
            nombre_variante TEXT NOT NULL,
            precio_adicional REAL DEFAULT 0,
            activa INTEGER DEFAULT 1,
            FOREIGN KEY (id_producto) REFERENCES productos(id_producto) ON DELETE CASCADE
        )
    """))

    # ── Tabla facturas_electronicas ─────────────────────────────────────────
    _paso("tabla facturas_electronicas", critico=True, fn=lambda: cursor.execute("""
        CREATE TABLE IF NOT EXISTS facturas_electronicas (
            id_factura INTEGER PRIMARY KEY AUTOINCREMENT,
            id_venta INTEGER NOT NULL,
            numero_factura TEXT UNIQUE NOT NULL,
            cliente_nombre TEXT NOT NULL,
            cliente_nit TEXT NOT NULL,
            cliente_email TEXT,
            fecha_emision TEXT DEFAULT (datetime('now','localtime')),
            usuario_registro TEXT NOT NULL,
            FOREIGN KEY (id_venta) REFERENCES ventas(id_venta)
        )
    """))

    # ── Tablas checklist de almuerzos ───────────────────────────────────────
    _paso("tabla almuerzo_checklist_template", critico=True, fn=lambda: cursor.execute("""
        CREATE TABLE IF NOT EXISTS almuerzo_checklist_template (
            id_item INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo_almuerzo TEXT NOT NULL,
            descripcion TEXT NOT NULL,
            orden INTEGER DEFAULT 0
        )
    """))
    _paso("tabla reserva_checklist", critico=True, fn=lambda: cursor.execute("""
        CREATE TABLE IF NOT EXISTS reserva_checklist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_reserva INTEGER NOT NULL,
            descripcion TEXT NOT NULL,
            completado INTEGER DEFAULT 0,
            hora_completado TEXT,
            FOREIGN KEY (id_reserva) REFERENCES reservas_almuerzo(id_reserva)
        )
    """))

    def _seed_checklist():
        count = cursor.execute("SELECT COUNT(*) FROM almuerzo_checklist_template").fetchone()[0]
        if count == 0:
            cursor.executemany(
                "INSERT INTO almuerzo_checklist_template (tipo_almuerzo, descripcion, orden) VALUES (?, ?, ?)",
                [
                    ('General',       'Sopa lista',              0),
                    ('General',       'Proteina lista',          1),
                    ('General',       'Arroz listo',             2),
                    ('General',       'Ensalada lista',          3),
                    ('Bandeja Paisa', 'Descongelar carne',       0),
                    ('Bandeja Paisa', 'Preparar frijoles',       1),
                    ('Bandeja Paisa', 'Chicharron',              2),
                    ('Bandeja Paisa', 'Arroz listo',             3),
                    ('Bandeja Paisa', 'Platano maduro',          4),
                    ('Bandeja Paisa', 'Aguacate y ensalada',     5),
                    ('Sobrebarriga',  'Descongelar sobrebarriga',0),
                    ('Sobrebarriga',  'Papa o yuca lista',       1),
                    ('Sobrebarriga',  'Arroz listo',             2),
                    ('Sobrebarriga',  'Ensalada lista',          3),
                    ('Corriente',     'Sopa lista',              0),
                    ('Corriente',     'Proteina lista',          1),
                    ('Corriente',     'Arroz listo',             2),
                    ('Corriente',     'Ensalada lista',          3),
                ]
            )
    _paso("seed checklist almuerzos", critico=False, fn=_seed_checklist)

    # ── Columnas en ventas ──────────────────────────────────────────────────
    def _col_ventas():
        cols = [r[1] for r in cursor.execute("PRAGMA table_info(ventas)").fetchall()]
        if 'id_cliente' not in cols:
            cursor.execute("ALTER TABLE ventas ADD COLUMN id_cliente INTEGER REFERENCES clientes(id_cliente)")
        if 'fecha_pago' not in cols:
            cursor.execute("ALTER TABLE ventas ADD COLUMN fecha_pago TEXT")
        if 'es_contingencia' not in cols:
            cursor.execute("ALTER TABLE ventas ADD COLUMN es_contingencia INTEGER DEFAULT 0")
        if 'numero_talonario' not in cols:
            cursor.execute("ALTER TABLE ventas ADD COLUMN numero_talonario TEXT")
        if 'motivo_descuento' not in cols:
            cursor.execute("ALTER TABLE ventas ADD COLUMN motivo_descuento TEXT")
    _paso("columnas ventas", critico=True, fn=_col_ventas)

    # ── Columnas en productos ───────────────────────────────────────────────
    def _col_productos():
        cols = [r[1] for r in cursor.execute("PRAGMA table_info(productos)").fetchall()]
        if 'pendiente_aprobacion' not in cols:
            cursor.execute("ALTER TABLE productos ADD COLUMN pendiente_aprobacion INTEGER DEFAULT 0")
        if 'controla_stock' not in cols:
            cursor.execute("ALTER TABLE productos ADD COLUMN controla_stock INTEGER DEFAULT 0")
    _paso("columnas productos", critico=True, fn=_col_productos)

    # ── Columna hora_completado en reserva_checklist ────────────────────────
    def _col_reserva_checklist():
        cols = [r[1] for r in cursor.execute("PRAGMA table_info(reserva_checklist)").fetchall()]
        if 'hora_completado' not in cols:
            cursor.execute("ALTER TABLE reserva_checklist ADD COLUMN hora_completado TEXT")
    _paso("columna reserva_checklist.hora_completado", critico=False, fn=_col_reserva_checklist)

    # ── Serie LP para facturas electrónicas ────────────────────────────────
    def _serie_lp():
        _ano = _dt.datetime.now().year
        cursor.execute(
            "INSERT OR IGNORE INTO series_facturacion (prefijo, ano, consecutivo_actual, activa) VALUES ('LP', ?, 0, 1)",
            (_ano,)
        )
    _paso("serie LP facturas", critico=False, fn=_serie_lp)

    # ── Método de pago TULLAVE ──────────────────────────────────────────────
    _paso("metodo pago TULLAVE", critico=False, fn=lambda: cursor.execute(
        "INSERT OR IGNORE INTO metodos_pago (nombre, orden) VALUES ('TULLAVE', 4)"
    ))

    # ── Columna tipo en categorias ──────────────────────────────────────────
    def _col_tipo_categoria():
        cols = [r[1] for r in cursor.execute("PRAGMA table_info(categorias)").fetchall()]
        if 'tipo' not in cols:
            cursor.execute(
                "ALTER TABLE categorias ADD COLUMN tipo TEXT DEFAULT 'restaurante' "
                "CHECK(tipo IN ('restaurante','bar','ambos'))"
            )
    _paso("columna categorias.tipo", critico=False, fn=_col_tipo_categoria)

    # ── Claves de configuración ─────────────────────────────────────────────
    def _insert_config(filas):
        for clave, valor, tipo, desc in filas:
            cursor.execute(
                "INSERT OR IGNORE INTO configuracion (clave, valor, tipo, descripcion) VALUES (?, ?, ?, ?)",
                (clave, valor, tipo, desc)
            )

    _paso("config backup/web", critico=False, fn=lambda: _insert_config([
        ('backup_ruta',          '', 'texto',  'Carpeta de destino para backups automáticos'),
        ('ultimo_backup',        '', 'texto',  'Fecha y hora del último backup exitoso'),
        ('ultimo_backup_estado', '', 'texto',  'Estado del último backup: OK o mensaje de error'),
        ('cocina_web_token',     '', 'texto',  'Token de acceso para cocina_web (vacío = sin auth)'),
        ('cocina_web_intervalo', '15', 'numero', 'Intervalo de auto-refresh de cocina_web en segundos (5-120)'),
        ('ubicacion',            '', 'texto',  'Dirección o ubicación del negocio'),
    ]))

    _paso("config DIAN", critico=False, fn=lambda: _insert_config([
        ('resolucion_dian_numero',      '', 'texto',   'Numero de resolucion DIAN'),
        ('resolucion_dian_fecha_desde', '', 'texto',   'Fecha de inicio de vigencia (YYYY-MM-DD)'),
        ('resolucion_dian_fecha_hasta', '', 'texto',   'Fecha de fin de vigencia (YYYY-MM-DD)'),
        ('resolucion_dian_prefijo',     'LP', 'texto', 'Prefijo de facturacion electronica'),
        ('resolucion_dian_desde',       '1', 'numero', 'Numero inicial del rango autorizado'),
        ('resolucion_dian_hasta',       '10000', 'numero', 'Numero final del rango autorizado'),
    ]))

    _paso("config impresora", critico=False, fn=lambda: _insert_config([
        ('impresora_ancho_mm', '80',  'numero', 'Ancho de papel del ticket: 80 o 58 mm'),
        ('impresora_modo',     'pdf', 'texto',  'Modo de impresion: pdf o escpos'),
        ('impresora_nombre',   '',    'texto',  'Nombre de la impresora ESC/POS en Windows'),
    ]))

    # ── Licencia mensual ────────────────────────────────────────────────────
    _paso("config licencia mensual", critico=False, fn=lambda: _insert_config([
        ('licencia_mes_activo', '', 'texto', 'Mes activo de licencia (YYYY-MM)'),
    ]))

    # ── SEC-03: agregar rol 'contadora' al CHECK constraint de usuarios ────
    # SQLite no soporta ALTER TABLE para modificar CHECK constraints:
    # hay que recrear la tabla copiando todos los datos.
    def _migrar_rol_contadora():
        schema_row = cursor.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='usuarios'"
        ).fetchone()
        if not schema_row or 'contadora' in schema_row[0]:
            return  # ya migrado o tabla inexistente

        # Obtener columnas actuales (puede haber extras de migraciones previas)
        cols_info = cursor.execute("PRAGMA table_info(usuarios)").fetchall()
        col_names = [c[1] for c in cols_info]

        # Calcular columnas extra más allá del schema base
        _base = {'id_usuario', 'usuario', 'nombre_completo', 'email', 'contrasena_hash',
                 'rol', 'activo', 'avatar_color', 'ultimo_login', 'intentos_fallidos',
                 'bloqueado_hasta', 'fecha_creacion', 'notas', 'debe_cambiar_password', 'pin'}
        extra_defs = []
        for c in cols_info:
            if c[1] not in _base:
                dflt = f" DEFAULT {c[4]}" if c[4] is not None else ""
                notnull = " NOT NULL" if c[3] else ""
                extra_defs.append(f"    {c[1]} {c[2] or 'TEXT'}{notnull}{dflt}")
        extra_sql = (',\n' + ',\n'.join(extra_defs)) if extra_defs else ''

        # PRAGMA foreign_keys solo funciona fuera de una transaccion activa.
        # Usamos SAVEPOINT para poder rollback si algo falla en medio del rename.
        conn.commit()
        conn.execute("SAVEPOINT migrar_rol_contadora")
        try:
            conn.execute("PRAGMA foreign_keys = OFF")
            cursor.execute("DROP TABLE IF EXISTS usuarios_new")
            cursor.execute(f"""
                CREATE TABLE usuarios_new (
                    id_usuario INTEGER PRIMARY KEY AUTOINCREMENT,
                    usuario TEXT UNIQUE NOT NULL,
                    nombre_completo TEXT NOT NULL,
                    email TEXT,
                    contrasena_hash TEXT NOT NULL,
                    rol TEXT NOT NULL DEFAULT 'cajero'
                        CHECK(rol IN ('administrador','cajero','vendedor','contadora')),
                    activo INTEGER DEFAULT 1,
                    avatar_color TEXT DEFAULT '#1976D2',
                    ultimo_login TEXT,
                    intentos_fallidos INTEGER DEFAULT 0,
                    bloqueado_hasta TEXT,
                    fecha_creacion TEXT DEFAULT (datetime('now','localtime')),
                    notas TEXT,
                    debe_cambiar_password INTEGER DEFAULT 0,
                    pin TEXT{extra_sql}
                )
            """)
            cols_str = ', '.join(col_names)
            cursor.execute(f"INSERT INTO usuarios_new ({cols_str}) SELECT {cols_str} FROM usuarios")
            cursor.execute("DROP TABLE usuarios")
            cursor.execute("ALTER TABLE usuarios_new RENAME TO usuarios")
            conn.execute("RELEASE migrar_rol_contadora")
            conn.commit()
        except Exception:
            conn.execute("ROLLBACK TO migrar_rol_contadora")
            conn.execute("RELEASE migrar_rol_contadora")
            conn.execute("PRAGMA foreign_keys = ON")
            raise
        conn.execute("PRAGMA foreign_keys = ON")

        # Asignar rol 'contadora' al usuario 'daniela' si existe con otro rol
        cursor.execute(
            "UPDATE usuarios SET rol = 'contadora' "
            "WHERE usuario = 'daniela' AND rol NOT IN ('administrador','contadora')"
        )
    _paso("rol contadora en CHECK constraint", critico=True, fn=_migrar_rol_contadora)

    # ── SEC-05: re-hashear PINs en texto plano con bcrypt ───────────────────
    def _rehashear_pins_plaintext():
        try:
            import bcrypt as _bcrypt_mig
        except ImportError:
            return  # bcrypt no disponible, no podemos migrar — se loguea advertencia
        rows = cursor.execute(
            "SELECT id_usuario, pin FROM usuarios WHERE pin IS NOT NULL AND pin != ''"
        ).fetchall()
        for row in rows:
            pin_val = row[1]
            if pin_val and not pin_val.startswith('$2'):
                # PIN en texto plano — re-hashear
                nuevo_hash = _bcrypt_mig.hashpw(
                    pin_val.encode('utf-8'), _bcrypt_mig.gensalt(12)
                ).decode('utf-8')
                cursor.execute(
                    "UPDATE usuarios SET pin = ? WHERE id_usuario = ?",
                    (nuevo_hash, row[0])
                )
    _paso("re-hashear PINs plaintext con bcrypt", critico=False, fn=_rehashear_pins_plaintext)

    # ── SEC-09: cerrar sesiones huerfanas con mas de 24 horas ───────────────
    _paso("cerrar sesiones huerfanas", critico=False, fn=lambda: cursor.execute("""
        UPDATE sesiones SET fecha_fin = datetime('now','localtime')
        WHERE fecha_fin IS NULL
          AND fecha_inicio < datetime('now','localtime','-24 hours')
    """))

    # ── Índices de rendimiento faltantes ────────────────────────────────────
    def _crear_indices_rendimiento():
        nuevos = [
            "CREATE INDEX IF NOT EXISTS idx_variantes_producto ON variantes_producto(id_producto)",
            "CREATE INDEX IF NOT EXISTS idx_ventas_id_cliente ON ventas(id_cliente)",
            "CREATE INDEX IF NOT EXISTS idx_clientes_activo ON clientes(activo)",
            "CREATE INDEX IF NOT EXISTS idx_movimientos_caja_id ON movimientos_caja(id_caja)",
            "CREATE INDEX IF NOT EXISTS idx_tareas_fecha ON tareas_preproduccion(fecha)",
            "CREATE INDEX IF NOT EXISTS idx_productos_requiere_cocina ON productos(requiere_cocina)",
            "CREATE INDEX IF NOT EXISTS idx_series_facturacion ON series_facturacion(prefijo, ano, activa)",
            "CREATE INDEX IF NOT EXISTS idx_series_boletas ON series_boletas(ano, activa)",
            "CREATE INDEX IF NOT EXISTS idx_ventas_tipo_estado ON ventas(tipo, estado)",
            "CREATE INDEX IF NOT EXISTS idx_categorias_activa_orden ON categorias(activa, orden)",
        ]
        for ddl in nuevos:
            try:
                cursor.execute(ddl)
            except Exception:
                pass  # tabla aún no existe en BDs muy antiguas; se crea cuando se migre la tabla
    _paso("índices de rendimiento", critico=False, fn=_crear_indices_rendimiento)

    # ── schema_version ──────────────────────────────────────────────────────
    def _schema_version():
        cursor.execute(
            "INSERT OR IGNORE INTO configuracion (clave, valor, tipo, descripcion) VALUES (?, ?, ?, ?)",
            ('schema_version', str(SCHEMA_VERSION), 'numero', 'Version de esquema de BD (no editar manualmente)')
        )
        cursor.execute(
            "UPDATE configuracion SET valor = ? WHERE clave = 'schema_version'",
            (str(SCHEMA_VERSION),)
        )
    _paso("schema_version", critico=False, fn=_schema_version)

    # ── Columna notificado_listo en ordenes_cocina y reservas_almuerzo ─────
    def _col_notificado():
        for tabla in ('ordenes_cocina', 'reservas_almuerzo'):
            cols = [r[1] for r in cursor.execute(f"PRAGMA table_info({tabla})").fetchall()]
            if 'notificado_listo' not in cols:
                cursor.execute(f"ALTER TABLE {tabla} ADD COLUMN notificado_listo INTEGER DEFAULT 0")
    _paso("columna notificado_listo", critico=True, fn=_col_notificado)

    # ── Columna monto_recibido en pagos ────────────────────────────────────
    def _col_monto_recibido():
        cols = [r[1] for r in cursor.execute("PRAGMA table_info(pagos)").fetchall()]
        if 'monto_recibido' not in cols:
            cursor.execute("ALTER TABLE pagos ADD COLUMN monto_recibido REAL")
    _paso("columna monto_recibido en pagos", critico=False, fn=_col_monto_recibido)

    # ── Tabla devoluciones ─────────────────────────────────────────────────
    _paso("tabla devoluciones", critico=False, fn=lambda: cursor.execute("""
        CREATE TABLE IF NOT EXISTS devoluciones (
            id_devolucion INTEGER PRIMARY KEY AUTOINCREMENT,
            id_venta INTEGER NOT NULL,
            monto REAL NOT NULL,
            motivo TEXT NOT NULL,
            usuario TEXT NOT NULL,
            fecha TEXT DEFAULT (datetime('now','localtime')),
            aplicado_caja INTEGER DEFAULT 0,
            FOREIGN KEY (id_venta) REFERENCES ventas(id_venta)
        )
    """))

    def _col_usuario_devoluciones():
        cols = [r[1] for r in cursor.execute("PRAGMA table_info(devoluciones)").fetchall()]
        if 'usuario' not in cols:
            cursor.execute("ALTER TABLE devoluciones ADD COLUMN usuario TEXT NOT NULL DEFAULT ''")
    _paso("columna usuario en devoluciones", critico=False, fn=_col_usuario_devoluciones)

    # ── Rol contadora para Daniela ──────────────────────────────────────────
    def _rol_contadora_daniela():
        cursor.execute(
            "UPDATE usuarios SET rol = 'contadora' WHERE usuario = 'daniela' AND rol != 'contadora'"
        )
    _paso("rol contadora daniela", critico=False, fn=_rol_contadora_daniela)

    # ── Tabla tareas_preproduccion ──────────────────────────────────────────
    _paso("tabla tareas_preproduccion", critico=True, fn=lambda: cursor.execute("""
        CREATE TABLE IF NOT EXISTS tareas_preproduccion (
            id_tarea INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT NOT NULL DEFAULT (date('now','localtime')),
            descripcion TEXT NOT NULL,
            cantidad TEXT,
            completada INTEGER DEFAULT 0,
            hora_completado TEXT,
            usuario TEXT,
            fecha_registro TEXT DEFAULT (datetime('now','localtime'))
        )
    """))

    # ── Índices de performance y monitoreo ──────────────────────────────────
    def _indices_nuevos():
        for sql in [
            "CREATE INDEX IF NOT EXISTS idx_ventas_estado_fecha ON ventas(estado, fecha_creacion)",
            "CREATE INDEX IF NOT EXISTS idx_ventas_usuario ON ventas(id_usuario)",
            "CREATE INDEX IF NOT EXISTS idx_auditoria_lookup ON auditoria(tabla_afectada, accion, id_registro)",
            "CREATE INDEX IF NOT EXISTS idx_auditoria_usuario_accion ON auditoria(usuario, accion)",
            "CREATE INDEX IF NOT EXISTS idx_auditoria_fecha ON auditoria(fecha_hora)",
            "CREATE INDEX IF NOT EXISTS idx_movinv_prod_fecha ON movimientos_inventario(id_producto, fecha)",
        ]:
            cursor.execute(sql)
    _paso("indices performance", critico=False, fn=_indices_nuevos)

    _paso("tabla socios", critico=True, fn=lambda: cursor.execute("""
        CREATE TABLE IF NOT EXISTS socios (
            id_socio INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            documento TEXT,
            telefono TEXT,
            email TEXT,
            tipo_membresia TEXT DEFAULT 'Individual'
                CHECK(tipo_membresia IN ('Individual','Familiar','VIP')),
            valor_cuota REAL DEFAULT 0,
            dia_pago INTEGER DEFAULT 1,
            fecha_ingreso TEXT DEFAULT (date('now','localtime')),
            estado TEXT DEFAULT 'ACTIVO'
                CHECK(estado IN ('ACTIVO','SUSPENDIDO','RETIRADO')),
            notas TEXT,
            activo INTEGER DEFAULT 1,
            fecha_creacion TEXT DEFAULT (datetime('now','localtime'))
        )
    """))

    _paso("tabla pagos_membresia", critico=True, fn=lambda: cursor.execute("""
        CREATE TABLE IF NOT EXISTS pagos_membresia (
            id_pago INTEGER PRIMARY KEY AUTOINCREMENT,
            id_socio INTEGER NOT NULL REFERENCES socios(id_socio),
            anio INTEGER NOT NULL,
            mes INTEGER NOT NULL,
            valor_pagado REAL NOT NULL,
            metodo_pago TEXT DEFAULT 'EFECTIVO',
            fecha_pago TEXT DEFAULT (datetime('now','localtime')),
            observacion TEXT,
            usuario_registro TEXT,
            UNIQUE(id_socio, anio, mes)
        )
    """))

    # ── Tabla reportes de errores ───────────────────────────────────────────
    _paso("tabla reportes_errores", critico=True, fn=lambda: cursor.execute("""
        CREATE TABLE IF NOT EXISTS reportes_errores (
            id_reporte INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT DEFAULT (datetime('now','localtime')),
            modulo TEXT,
            severidad TEXT DEFAULT 'Medio'
                CHECK(severidad IN ('Critico','Alto','Medio','Bajo')),
            descripcion TEXT NOT NULL,
            pasos TEXT,
            usuario TEXT,
            enviado INTEGER DEFAULT 0,
            fecha_envio TEXT,
            ruta_captura TEXT
        )
    """))

    # ── Claves SMTP para envío de reportes de error ─────────────────────────
    def _smtp_defaults():
        for clave, valor, tipo, desc in [
            ('smtp_servidor',          'smtp.gmail.com', 'texto',  'Servidor SMTP para envio de reportes'),
            ('smtp_puerto',            '587',            'numero', 'Puerto SMTP (587=TLS, 465=SSL)'),
            ('smtp_usuario',           '',               'texto',  'Correo remitente (cuenta Gmail)'),
            ('smtp_password',          '',               'texto',  'Contrasena de aplicacion Gmail (App Password)'),
            ('soporte_email',          '', 'texto', 'Correo destino de reportes de error'),
        ]:
            cursor.execute(
                "INSERT OR IGNORE INTO configuracion (clave, valor, tipo, descripcion) VALUES (?, ?, ?, ?)",
                (clave, valor, tipo, desc)
            )
    _paso("smtp_defaults", critico=False, fn=_smtp_defaults)

    # ── Tablas nómina (garantizar existencia antes de consumos) ────────────
    _paso("tabla nomina_empleados", critico=True, fn=lambda: cursor.execute("""
        CREATE TABLE IF NOT EXISTS nomina_empleados (
            id_empleado INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            tarifa_normal REAL DEFAULT 0,
            tarifa_festivo REAL DEFAULT 0,
            activo INTEGER DEFAULT 1,
            fecha_creacion TEXT DEFAULT (datetime('now','localtime'))
        )
    """))

    # ── Tablas consumo de empleados ─────────────────────────────────────────
    _paso("tabla consumos_empleados", critico=True, fn=lambda: cursor.execute("""
        CREATE TABLE IF NOT EXISTS consumos_empleados (
            id_consumo INTEGER PRIMARY KEY AUTOINCREMENT,
            id_empleado INTEGER NOT NULL,
            fecha TEXT DEFAULT (datetime('now','localtime')),
            total REAL DEFAULT 0,
            estado TEXT DEFAULT 'ABIERTO' CHECK(estado IN ('ABIERTO','CERRADO')),
            usuario TEXT,
            notas TEXT
        )
    """))
    _paso("tabla consumo_detalle", critico=True, fn=lambda: cursor.execute("""
        CREATE TABLE IF NOT EXISTS consumo_detalle (
            id_detalle INTEGER PRIMARY KEY AUTOINCREMENT,
            id_consumo INTEGER NOT NULL,
            id_producto INTEGER,
            producto_nombre TEXT NOT NULL,
            cantidad REAL DEFAULT 1,
            precio_unitario REAL DEFAULT 0,
            total_linea REAL DEFAULT 0
        )
    """))

    # ── Índice fecha_apertura (BD existentes no lo tienen) ─────────────────
    _paso("idx_caja_fecha_apertura", critico=False, fn=lambda: cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_caja_fecha_apertura ON caja_diaria(fecha_apertura)"
    ))

    # ── Commit y cierre ─────────────────────────────────────────────────────
    try:
        conn.commit()
    except Exception as e:
        errores_criticos.append(f"[migración] commit final: {e}")
    finally:
        conn.close()

    # ── Reporte de errores ──────────────────────────────────────────────────
    try:
        from utils.logger import configurar_logger
        log = configurar_logger()
        for msg in errores_menores:
            log.warning(msg)
        for msg in errores_criticos:
            log.error(msg)
    except Exception:
        for msg in errores_menores + errores_criticos:
            print(msg, file=sys.stderr)

    if errores_criticos:
        detalle = "\n".join(f"• {m.splitlines()[0]}" for m in errores_criticos)
        raise RuntimeError(
            f"Migraciones críticas fallidas — la aplicación no puede arrancar de forma segura:\n{detalle}"
        )


def iniciar_backup_automatico(db_path):
    """Inicia un hilo daemon que realiza backup diario de la BD al arrancar la app.
    Usa sqlite3.backup() para una copia online sin bloquear escrituras (WAL)."""

    def _hacer_backup():
        try:
            conn_cfg = sqlite3.connect(db_path)
            conn_cfg.row_factory = sqlite3.Row

            ruta_row = conn_cfg.execute(
                "SELECT valor FROM configuracion WHERE clave = 'backup_ruta'"
            ).fetchone()
            ultimo_row = conn_cfg.execute(
                "SELECT valor FROM configuracion WHERE clave = 'ultimo_backup'"
            ).fetchone()
            conn_cfg.close()

            ruta_backup = ruta_row['valor'].strip() if ruta_row and ruta_row['valor'] else ''
            ultimo_backup = ultimo_row['valor'].strip() if ultimo_row and ultimo_row['valor'] else ''
            hoy = datetime.date.today().isoformat()

            # Solo hacer backup si hay ruta configurada y no se hizo hoy
            if not ruta_backup or ultimo_backup == hoy:
                return

            os.makedirs(ruta_backup, exist_ok=True)
            nombre_archivo = f"pocitos_backup_{hoy}.db"
            destino = os.path.join(ruta_backup, nombre_archivo)

            # sqlite3.backup es seguro con WAL — no bloquea lecturas/escrituras
            src = sqlite3.connect(db_path)
            dst = sqlite3.connect(destino)
            try:
                src.backup(dst)
            finally:
                dst.close()
                src.close()

            # Verificar integridad del backup generado
            estado_backup = 'OK'
            try:
                conn_check = sqlite3.connect(destino)
                resultado_check = conn_check.execute("PRAGMA integrity_check").fetchone()
                conn_check.close()
                if not resultado_check or resultado_check[0] != 'ok':
                    estado_backup = f"ERROR_INTEGRIDAD: {resultado_check[0] if resultado_check else 'sin respuesta'}"
            except Exception as e_check:
                estado_backup = f"ERROR_VERIFICACION: {e_check}"

            # Actualizar fecha y estado del último backup
            ahora_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
            conn_upd = sqlite3.connect(db_path)
            conn_upd.execute(
                "UPDATE configuracion SET valor = ? WHERE clave = 'ultimo_backup'", (ahora_str,)
            )
            conn_upd.execute(
                "INSERT OR IGNORE INTO configuracion (clave, valor, tipo, descripcion) "
                "VALUES ('ultimo_backup_estado', ?, 'texto', 'Estado del último backup')",
                (estado_backup,)
            )
            conn_upd.execute(
                "UPDATE configuracion SET valor = ? WHERE clave = 'ultimo_backup_estado'",
                (estado_backup,)
            )
            conn_upd.commit()
            conn_upd.close()

            if estado_backup != 'OK':
                try:
                    from utils.logger import configurar_logger
                    configurar_logger().error(f"Backup creado pero con problemas: {estado_backup} → {destino}")
                except Exception:
                    print(f"BACKUP ADVERTENCIA: {estado_backup}", file=sys.stderr)

            # Limpiar backups con más de 30 días
            for archivo in os.listdir(ruta_backup):
                if archivo.startswith('pocitos_backup_') and archivo.endswith('.db'):
                    fecha_str = archivo[len('pocitos_backup_'):-len('.db')]
                    try:
                        fecha_arch = datetime.date.fromisoformat(fecha_str)
                        if (datetime.date.today() - fecha_arch).days > 30:
                            os.remove(os.path.join(ruta_backup, archivo))
                    except ValueError:
                        pass

        except Exception as e:
            import traceback
            msg = f"Error en backup automático: {e}\n{traceback.format_exc()}"
            try:
                from utils.logger import configurar_logger
                configurar_logger().error(msg)
            except Exception:
                print(msg, file=sys.stderr)
            # Registrar el error en configuracion para que el dashboard lo muestre
            try:
                conn_err = sqlite3.connect(db_path)
                conn_err.execute(
                    "INSERT OR IGNORE INTO configuracion (clave, valor, tipo, descripcion) "
                    "VALUES ('ultimo_backup_estado', ?, 'texto', 'Estado del último backup')",
                    (f"ERROR: {str(e)[:120]}",)
                )
                conn_err.execute(
                    "UPDATE configuracion SET valor = ? WHERE clave = 'ultimo_backup_estado'",
                    (f"ERROR: {str(e)[:120]}",)
                )
                conn_err.commit()
                conn_err.close()
            except Exception:
                pass

    hilo = threading.Thread(target=_hacer_backup, daemon=True, name="BackupAutomatico")
    hilo.start()



def iniciar_cocina_web():
    """Inicia el servidor web de cocina en un hilo daemon.
    Usa Waitress si está disponible (producción); cae back a Flask dev si no.
    Prueba puertos 5000-5003 hasta encontrar uno libre."""
    def _run():
        import socket
        from cocina_web.app import app as flask_app, COCINA_PASSWORD_DEFAULT

        # AUTH-04: advertencia prominente si se usa la clave por defecto
        try:
            from database.connection import conexion_segura as _cs
            with _cs() as _c:
                _r = _c.execute(
                    "SELECT valor FROM configuracion WHERE clave = 'cocina_web_token'"
                ).fetchone()
                _token = _r['valor'].strip() if _r and _r['valor'] else ''
            if not _token or _token == COCINA_PASSWORD_DEFAULT:
                _log = logging.getLogger("pocitos")
                _log.warning(
                    "SEGURIDAD: cocina_web usa la clave por defecto '%s'. "
                    "Cualquier persona en la red puede acceder a la pantalla de cocina. "
                    "Cambia la clave en Configuracion -> Sincronizacion -> Cocina Web.",
                    COCINA_PASSWORD_DEFAULT
                )
        except Exception:
            pass

        puertos = [5000, 5001, 5002, 5003]
        for puerto in puertos:
            # Verificar si el puerto está libre antes de intentar
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                if s.connect_ex(('127.0.0.1', puerto)) == 0:
                    continue  # Puerto ocupado, probar el siguiente

            try:
                try:
                    from waitress import serve
                    serve(flask_app, host='0.0.0.0', port=puerto, threads=4)
                except ImportError:
                    flask_app.run(host='0.0.0.0', port=puerto, debug=False,
                                  threaded=True, use_reloader=False)
                return  # Servidor terminó normalmente
            except OSError:
                continue  # Puerto ocupado al momento de bind, intentar siguiente
            except Exception as e:
                try:
                    from utils.logger import configurar_logger
                    configurar_logger().warning(f"Cocina web no pudo iniciarse en puerto {puerto}: {e}")
                except Exception:
                    pass
                return

        try:
            from utils.logger import configurar_logger
            configurar_logger().error("Cocina web: no se encontró ningún puerto libre (5000-5003)")
        except Exception:
            pass

    threading.Thread(target=_run, daemon=True, name="CocinaWeb").start()


def iniciar_telemetria_ducklab():
    """Manda un 'latido' al portal Ducklab para verlo 'en línea' mientras el POS
    está abierto. APAGADO por defecto: solo corre si en Configuración existen las
    claves 'ducklab_telemetry_url' y 'ducklab_api_key' (se ponen en cada cliente,
    NO vienen en el instalador público, así la API key nunca se expone)."""
    def _run():
        import time
        try:
            import requests
        except Exception:
            return
        from database.connection import conexion_segura
        time.sleep(20)
        while True:
            try:
                with conexion_segura() as conn:
                    url = conn.execute("SELECT valor FROM configuracion WHERE clave='ducklab_telemetry_url'").fetchone()
                    key = conn.execute("SELECT valor FROM configuracion WHERE clave='ducklab_api_key'").fetchone()
                url = (url['valor'] if url else '') or ''
                key = (key['valor'] if key else '') or ''
                if url and key:
                    requests.post(
                        url,
                        headers={'Authorization': f'Bearer {key}'},
                        json={'status': 'online', 'version': '1.0.0'},
                        timeout=10,
                    )
            except Exception:
                pass  # nunca tumbar la app por la telemetría
            time.sleep(180)  # cada 3 min (< 5 min de "stale" en el portal)

    threading.Thread(target=_run, daemon=True, name="TelemetriaDucklab").start()


def iniciar_respaldo_nube_ducklab():
    """Sube un respaldo de la BD al portal Ducklab cuando hay internet, para que
    las ventas estén a salvo aunque se dañe el PC. APAGADO por defecto: solo corre
    si en Configuración están 'ducklab_telemetry_url' y 'ducklab_api_key' (la URL
    de respaldo se deriva de la de telemetría). Sube un snapshot consistente
    (sqlite backup), no la BD en vivo. Cada 6 horas."""
    def _run():
        import time
        import os
        import tempfile
        import sqlite3 as _sq
        try:
            import requests
        except Exception:
            return
        from database.connection import conexion_segura, get_db_path
        time.sleep(60)
        while True:
            try:
                with conexion_segura() as conn:
                    turl = conn.execute("SELECT valor FROM configuracion WHERE clave='ducklab_telemetry_url'").fetchone()
                    key = conn.execute("SELECT valor FROM configuracion WHERE clave='ducklab_api_key'").fetchone()
                turl = (turl['valor'] if turl else '') or ''
                key = (key['valor'] if key else '') or ''
                if turl and key:
                    backup_url = turl.rsplit('/api/', 1)[0] + '/api/backup'
                    tmp = os.path.join(tempfile.gettempdir(), 'pocitos_backup_nube.db')
                    src = _sq.connect(get_db_path())
                    dst = _sq.connect(tmp)
                    with dst:
                        src.backup(dst)   # snapshot consistente (no bloquea WAL)
                    src.close()
                    dst.close()
                    with open(tmp, 'rb') as f:
                        data = f.read()
                    requests.post(
                        backup_url,
                        data=data,
                        timeout=90,
                        headers={
                            'Authorization': f'Bearer {key}',
                            'Content-Type': 'application/octet-stream',
                            'x-file-name': 'pocitos_azufrados.db',
                        },
                    )
                    try:
                        os.remove(tmp)
                    except Exception:
                        pass
            except Exception:
                pass  # nunca tumbar la app por el respaldo
            time.sleep(6 * 3600)  # cada 6 horas

    threading.Thread(target=_run, daemon=True, name="RespaldoNubeDucklab").start()


def verificar_fecha_sistema():
    """Verifica que la fecha del sistema sea razonable (año >= 2024).
    Muestra advertencia visible si el reloj del sistema parece incorrecto."""
    anio_actual = datetime.datetime.now().year
    if anio_actual < 2024:
        root_tmp = tk.Tk()
        root_tmp.withdraw()
        from tkinter import messagebox as _mb
        _mb.showwarning(
            "Fecha del sistema incorrecta",
            f"La fecha del sistema indica el año {anio_actual}.\n\n"
            "El sistema requiere año 2024 o posterior.\n"
            "Por favor corrija la fecha antes de continuar.\n\n"
            "El sistema continuará, pero las fechas de las transacciones\n"
            "pueden quedar incorrectas."
        )
        root_tmp.destroy()


try:
    from _licencia_secret import LICENCIA_SECRET as _LICENCIA_SECRET
    if not _LICENCIA_SECRET:
        raise ValueError("LICENCIA_SECRET vacío")
except (ImportError, ValueError):
    import sys as _sys_lic
    import tkinter as _tk_lic
    _r = _tk_lic.Tk(); _r.withdraw()
    _tk_lic.messagebox.showerror(
        "Error de licencia",
        "Archivo de licencia no encontrado o vacío.\n"
        "Contacte al proveedor del sistema."
    )
    _r.destroy()
    _sys_lic.exit(1)


def _generar_claves_mes(anio_mes: str):
    """Genera las 5 claves válidas para un mes (formato 'YYYY-MM').
    Cualquiera de las 5 sirve para activar ese mes.
    """
    import hashlib
    claves = []
    for i in range(1, 6):
        raw = f"{_LICENCIA_SECRET}_{anio_mes}_{i}"
        clave = hashlib.sha256(raw.encode()).hexdigest()[:8].upper()
        claves.append(clave)
    return claves


def _bloquear_licencia_portal(sin_internet=False):
    """Bloquea el sistema con un mensaje y sale."""
    import tkinter as _tk
    from tkinter import messagebox as _mb
    root = _tk.Tk()
    root.withdraw()
    if sin_internet:
        msg = ("No se pudo validar tu licencia y ya pasó el periodo permitido sin "
               "conexión.\n\nConéctate a internet una vez para reactivar el sistema.")
    else:
        msg = ("Tu plan con Ducklab está inactivo.\n\nContáctanos para reactivar el sistema.")
    _mb.showerror("Sistema bloqueado", msg)
    root.destroy()
    sys.exit(1)


def verificar_licencia_ducklab(db_path):
    """Verifica la licencia contra el portal Ducklab (control desde nuestro
    portal/launcher). Tolerancia OFFLINE: si no hay internet, usa el último
    chequeo en caché dentro de un periodo de gracia (no rompe el uso sin
    internet). Si NO hay claves configuradas, cae a la licencia mensual local."""
    import datetime as _dt
    GRACIA_DIAS = 30
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    def _leer(c):
        r = conn.execute("SELECT valor FROM configuracion WHERE clave = ?", (c,)).fetchone()
        return (r['valor'].strip() if r and r['valor'] else '')

    def _guardar(c, v):
        cur = conn.execute("UPDATE configuracion SET valor = ? WHERE clave = ?", (v, c))
        if cur.rowcount == 0:
            conn.execute("INSERT INTO configuracion (clave, valor) VALUES (?, ?)", (c, v))
        conn.commit()

    turl = _leer('ducklab_telemetry_url')
    key = _leer('ducklab_api_key')
    if not turl or not key:
        conn.close()
        # Sin claves de Ducklab configuradas: NO bloquea. La licencia la controla
        # el portal una vez que pones la API key en Configuración → Sincronización.
        # (Antes caía a la licencia mensual local, lo que trababa la instalación nueva.)
        return

    lic_url = turl.rsplit('/api/', 1)[0] + '/api/license'
    activo = None
    try:
        import requests
        r = requests.get(lic_url, headers={'Authorization': f'Bearer {key}'}, timeout=8)
        if r.status_code == 200:
            activo = bool(r.json().get('active'))
        elif r.status_code in (401, 403):
            activo = False
    except Exception:
        activo = None  # sin internet / portal inalcanzable

    if activo is True:
        _guardar('ducklab_licencia_check', _dt.date.today().isoformat())
        conn.close()
        return
    if activo is False:
        conn.close()
        _bloquear_licencia_portal(sin_internet=False)
        return

    # Sin internet → tolerancia con el último chequeo OK
    ultimo = _leer('ducklab_licencia_check')
    conn.close()
    if ultimo:
        try:
            d = _dt.date.fromisoformat(ultimo)
            if (_dt.date.today() - d).days <= GRACIA_DIAS:
                return  # dentro de la gracia → deja abrir offline
        except Exception:
            pass
    _bloquear_licencia_portal(sin_internet=True)


def verificar_licencia_mensual(db_path):
    """Sistema de licencia mensual.
    - Del 1 al 7 de cada mes: avisa que hay que ingresar la clave del mes.
    - Después del día 7 sin clave: bloquea el sistema.
    - Con clave correcta: activa el mes actual.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    def _leer(clave):
        r = conn.execute("SELECT valor FROM configuracion WHERE clave = ?", (clave,)).fetchone()
        return r['valor'].strip() if r and r['valor'] else ''

    mes_activo = _leer('licencia_mes_activo')
    conn.close()

    hoy = datetime.date.today()
    mes_actual = hoy.strftime('%Y-%m')

    # Mes ya activado — sin restriccion
    if mes_activo == mes_actual:
        return

    dia = hoy.day
    dias_restantes = max(0, 8 - dia)

    if dia <= 7:
        # Semana de gracia — mostrar aviso con opción de activar ya
        _mostrar_aviso_licencia(db_path, mes_actual, dias_restantes)
    else:
        # Semana vencida — bloquear
        _mostrar_bloqueo_mensual(db_path, mes_actual)


def _mostrar_aviso_licencia(db_path, mes_actual, dias_restantes):
    """Aviso de renovación días 1–7: deja entrar pero ofrece activar la clave ya."""
    nombres_mes = {
        '01': 'Enero', '02': 'Febrero', '03': 'Marzo', '04': 'Abril',
        '05': 'Mayo', '06': 'Junio', '07': 'Julio', '08': 'Agosto',
        '09': 'Septiembre', '10': 'Octubre', '11': 'Noviembre', '12': 'Diciembre'
    }
    anio, mes = mes_actual.split('-')
    nombre_mes = nombres_mes.get(mes, mes)

    root_av = tk.Tk()
    root_av.title("Renovacion pendiente")
    root_av.configure(bg='#1a1a2e')
    root_av.geometry("480x380")
    root_av.resizable(False, False)
    try:
        root_av.attributes('-topmost', True)
    except Exception:
        pass

    tk.Label(root_av, text="RENOVACION PENDIENTE",
             font=('Segoe UI', 13, 'bold'), fg='#FFD700', bg='#1a1a2e').pack(pady=(28, 6))

    tk.Label(root_av,
             text=f"Faltan {dias_restantes} dia(s) para activar {nombre_mes} {anio}.\n"
                  "Si ya tienes la clave, ingresala ahora:",
             font=('Segoe UI', 10), fg='#CCCCCC', bg='#1a1a2e',
             justify='center').pack(pady=(4, 12))

    entry_codigo = tk.Entry(root_av, font=('Segoe UI', 16), width=18,
                            justify='center', bg='#FFFFFF', fg='#000000',
                            relief='solid', bd=2)
    entry_codigo.pack(pady=6, ipady=8)
    entry_codigo.focus_set()

    lbl_msg = tk.Label(root_av, text="", font=('Segoe UI', 10),
                       fg='#FF6B6B', bg='#1a1a2e')
    lbl_msg.pack(pady=4)

    def _activar():
        codigo = entry_codigo.get().strip().upper()
        if not codigo:
            lbl_msg.config(text="Escribe la clave antes de presionar Activar.")
            return
        claves_validas = _generar_claves_mes(mes_actual)
        if codigo in claves_validas:
            try:
                conn2 = sqlite3.connect(db_path)
                conn2.execute(
                    "INSERT OR IGNORE INTO configuracion(clave,valor,tipo,descripcion) "
                    "VALUES('licencia_mes_activo','','texto','Mes activo de licencia (YYYY-MM)')"
                )
                conn2.execute(
                    "UPDATE configuracion SET valor = ? WHERE clave = 'licencia_mes_activo'",
                    (mes_actual,)
                )
                conn2.commit()
                conn2.close()
            except Exception:
                pass
            root_av.destroy()
        else:
            lbl_msg.config(text="Clave incorrecta. Contacta a tu proveedor.")
            entry_codigo.delete(0, tk.END)
            entry_codigo.focus_set()

    def _entrar_sin_clave():
        root_av.destroy()

    tk.Button(root_av, text="  ACTIVAR  ", command=_activar,
              bg='#4CAF50', fg='white', font=('Segoe UI', 11, 'bold'),
              relief='flat', padx=20, pady=7, cursor='hand2').pack(pady=6)

    tk.Button(root_av, text="Entrar sin activar (quedan {} dias)".format(dias_restantes),
              command=_entrar_sin_clave,
              bg='#2a2a4a', fg='#AAAAAA', font=('Segoe UI', 9),
              relief='flat', padx=10, pady=4, cursor='hand2').pack(pady=2)

    tk.Label(root_av, text="Contacta a tu proveedor para obtener la clave del mes",
             font=('Segoe UI', 9), fg='#666688', bg='#1a1a2e').pack(pady=(10, 0))

    root_av.mainloop()


def _mostrar_bloqueo_mensual(db_path, mes_actual):
    """Pantalla de bloqueo mensual. Solo se desbloquea con la clave del mes."""
    import locale
    try:
        locale.setlocale(locale.LC_TIME, 'es_ES.UTF-8')
    except Exception:
        pass

    anio, mes = mes_actual.split('-')
    nombres_mes = {
        '01': 'Enero', '02': 'Febrero', '03': 'Marzo', '04': 'Abril',
        '05': 'Mayo', '06': 'Junio', '07': 'Julio', '08': 'Agosto',
        '09': 'Septiembre', '10': 'Octubre', '11': 'Noviembre', '12': 'Diciembre'
    }
    nombre_mes = nombres_mes.get(mes, mes)

    root_blq = tk.Tk()
    root_blq.title("Renovacion requerida")
    root_blq.configure(bg='#1a1a2e')
    root_blq.geometry("480x420")
    root_blq.resizable(False, False)
    try:
        root_blq.attributes('-topmost', True)
    except Exception:
        pass

    tk.Label(root_blq, text="RENOVACION MENSUAL REQUERIDA",
             font=('Segoe UI', 14, 'bold'), fg='#FF6B6B', bg='#1a1a2e').pack(pady=(30, 8))

    tk.Label(root_blq, text=f"Mes: {nombre_mes} {anio}",
             font=('Segoe UI', 11), fg='#FFFFFF', bg='#1a1a2e').pack(pady=(0, 16))

    tk.Label(root_blq, text="Ingresa la clave del mes aqui:",
             font=('Segoe UI', 11, 'bold'), fg='#CCCCCC', bg='#1a1a2e').pack()

    entry_codigo = tk.Entry(root_blq, font=('Segoe UI', 16), width=18,
                            justify='center', bg='#FFFFFF', fg='#000000',
                            relief='solid', bd=2)
    entry_codigo.pack(pady=12, ipady=8)
    entry_codigo.focus_set()

    lbl_msg = tk.Label(root_blq, text="", font=('Segoe UI', 10),
                       fg='#FF6B6B', bg='#1a1a2e')
    lbl_msg.pack(pady=4)

    def _verificar():
        codigo = entry_codigo.get().strip().upper()
        if not codigo:
            lbl_msg.config(text="Escribe la clave antes de presionar Activar.")
            return
        claves_validas = _generar_claves_mes(mes_actual)
        if codigo in claves_validas:
            try:
                conn2 = sqlite3.connect(db_path)
                conn2.execute(
                    "INSERT OR IGNORE INTO configuracion(clave,valor,tipo,descripcion) "
                    "VALUES('licencia_mes_activo','','texto','Mes activo de licencia (YYYY-MM)')"
                )
                conn2.execute(
                    "UPDATE configuracion SET valor = ? WHERE clave = 'licencia_mes_activo'",
                    (mes_actual,)
                )
                conn2.commit()
                conn2.close()
            except Exception:
                pass
            root_blq.destroy()
        else:
            lbl_msg.config(text="Clave incorrecta. Contacta a tu proveedor.")
            entry_codigo.delete(0, tk.END)
            entry_codigo.focus_set()

    tk.Button(root_blq, text="  ACTIVAR  ", command=_verificar,
              bg='#4CAF50', fg='white', font=('Segoe UI', 12, 'bold'),
              relief='flat', padx=24, pady=8, cursor='hand2').pack(pady=8)
    entry_codigo.bind('<Return>', lambda e: _verificar())

    tk.Label(root_blq, text="Contacta a tu proveedor para obtener la clave del mes",
             font=('Segoe UI', 9), fg='#666688', bg='#1a1a2e').pack(pady=(8, 0))

    root_blq.mainloop()
    sys.exit(0)


def main():
    """Punto de entrada principal."""
    # Preparar base de datos en la carpeta de datos del usuario (%LOCALAPPDATA%
    # cuando es .exe). La primera vez copia la BD semilla del paquete; en adelante
    # persiste entre actualizaciones. DEBE ir antes de abrir cualquier conexión.
    from database.connection import ensure_data_ready, get_db_path
    ensure_data_ready()
    db_path = get_db_path()
    if not os.path.exists(db_path):
        root_tmp = tk.Tk()
        root_tmp.withdraw()
        messagebox.showerror(
            "Error de Configuracion",
            f"No se pudo preparar la base de datos.\n\nBuscado en: {db_path}"
        )
        root_tmp.destroy()
        sys.exit(1)

    # Configurar logger
    try:
        from utils.logger import configurar_logger
        logger = configurar_logger()
        logger.info("=" * 50)
        logger.info("CLUB LOS POCITOS AZUFRADOS - Iniciando sistema")
        logger.info(f"Base de datos: {db_path}")
        logger.info("=" * 50)
    except Exception:
        pass

    # Migraciones
    try:
        aplicar_migraciones(db_path)
    except RuntimeError as e:
        root_tmp = tk.Tk()
        root_tmp.withdraw()
        messagebox.showerror("Error al Iniciar", str(e))
        root_tmp.destroy()
        sys.exit(1)

    # Backup automático
    iniciar_backup_automatico(db_path)

    # Servidor cocina web
    iniciar_cocina_web()

    # Telemetría al portal Ducklab (apagada si no hay claves en Configuración)
    iniciar_telemetria_ducklab()

    # Respaldo de la BD a la nube Ducklab (apagado si no hay claves)
    iniciar_respaldo_nube_ducklab()

    # Verificaciones de arranque
    verificar_fecha_sistema()
    verificar_licencia_ducklab(db_path)

    # Login → dashboard
    try:
        from modules.login import LoginWindow
        app = LoginWindow()
        app.root.mainloop()
    except Exception as e:
        import traceback
        root_tmp = tk.Tk()
        root_tmp.withdraw()
        messagebox.showerror(
            "Error al Iniciar",
            f"No se pudo iniciar el sistema:\n\n{e}\n\n"
            "Verifique que ejecuto 'python setup.py' primero.\n\n"
            f"Traceback (most recent call last):\n{traceback.format_exc()}"
        )
        root_tmp.destroy()
        sys.exit(1)


if __name__ == '__main__':
    main()