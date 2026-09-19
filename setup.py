#!/usr/bin/env python3
"""
=============================================================
  CLUB LOS POCITOS AZUFRADOS - Sistema POS
  Setup e Inicialización de Base de Datos
  Tocaima, Cundinamarca
=============================================================
"""

import os
import sys
import sqlite3
import getpass
import hashlib
import secrets
import string
import time

try:
    import bcrypt
    BCRYPT_DISPONIBLE = True
except ImportError:
    BCRYPT_DISPONIBLE = False
    print("⚠️  bcrypt no instalado. Usando hash básico.")


# ============================================================
#  CONFIGURACIÓN
# ============================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "pocitos_azufrados.db")
BACKUP_DIR = os.path.join(DATA_DIR, "backups")
LOG_DIR = os.path.join(BASE_DIR, "logs")


def crear_directorios():
    """Crea la estructura de carpetas necesaria"""
    print("\n[1/6] 📁 Creando estructura de carpetas...")
    dirs = [DATA_DIR, BACKUP_DIR, LOG_DIR,
            os.path.join(BASE_DIR, "assets"),
            os.path.join(BASE_DIR, "assets", "icons")]
    for d in dirs:
        os.makedirs(d, exist_ok=True)
        print(f"  ✅ {os.path.basename(d)}/")


def crear_base_datos():
    """Crea todas las tablas de la base de datos"""
    print("\n[2/6] 🗄️  Creando base de datos...")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Configuración óptima de SQLite
    cursor.executescript("""
        PRAGMA journal_mode = WAL;
        PRAGMA synchronous = NORMAL;
        PRAGMA foreign_keys = ON;
        PRAGMA busy_timeout = 60000;
        PRAGMA cache_size = -64000;
        PRAGMA temp_store = MEMORY;
    """)

    # ==========================================
    #  TABLA: USUARIOS
    # ==========================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
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
            pin TEXT
        )
    """)

    # ==========================================
    #  TABLA: CATEGORÍAS (Dinámicas)
    # ==========================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS categorias (
            id_categoria INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT UNIQUE NOT NULL,
            descripcion TEXT,
            color TEXT DEFAULT '#1976D2',
            icono TEXT DEFAULT '📦',
            orden INTEGER DEFAULT 0,
            activa INTEGER DEFAULT 1,
            tipo TEXT DEFAULT 'restaurante' CHECK(tipo IN ('restaurante','bar','ambos')),
            fecha_creacion TEXT DEFAULT (datetime('now','localtime'))
        )
    """)

    # ==========================================
    #  TABLA: SUBCATEGORÍAS
    # ==========================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS subcategorias (
            id_subcategoria INTEGER PRIMARY KEY AUTOINCREMENT,
            id_categoria INTEGER NOT NULL,
            nombre TEXT NOT NULL,
            descripcion TEXT,
            activa INTEGER DEFAULT 1,
            fecha_creacion TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (id_categoria) REFERENCES categorias(id_categoria),
            UNIQUE(id_categoria, nombre)
        )
    """)

    # ==========================================
    #  TABLA: PRODUCTOS
    # ==========================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS productos (
            id_producto INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo_barras TEXT UNIQUE,
            nombre TEXT NOT NULL,
            id_categoria INTEGER,
            id_subcategoria INTEGER,
            descripcion TEXT,
            precio_venta REAL NOT NULL DEFAULT 0,
            precio_costo REAL DEFAULT 0,
            stock_actual INTEGER DEFAULT 0,
            stock_minimo INTEGER DEFAULT 5,
            unidad_medida TEXT DEFAULT 'unidad'
                CHECK(unidad_medida IN ('unidad','litro','kilo','porcion','boleta')),
            requiere_cocina INTEGER DEFAULT 0,
            es_boleta_entrada INTEGER DEFAULT 0,
            permite_descuento INTEGER DEFAULT 1,
            impuesto_porcentaje REAL DEFAULT 0,
            imagen_path TEXT,
            activo INTEGER DEFAULT 1,
            pendiente_aprobacion INTEGER DEFAULT 0,
            controla_stock INTEGER DEFAULT 0,
            fecha_creacion TEXT DEFAULT (datetime('now','localtime')),
            fecha_actualizacion TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (id_categoria) REFERENCES categorias(id_categoria),
            FOREIGN KEY (id_subcategoria) REFERENCES subcategorias(id_subcategoria)
        )
    """)

    # ==========================================
    #  TABLA: VENTAS (Cuentas/Órdenes)
    # ==========================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ventas (
            id_venta INTEGER PRIMARY KEY AUTOINCREMENT,
            numero_venta TEXT UNIQUE NOT NULL,
            tipo TEXT DEFAULT 'normal'
                CHECK(tipo IN ('normal','cuenta_abierta','boleta','para_llevar')),
            estado TEXT DEFAULT 'ABIERTA'
                CHECK(estado IN ('ABIERTA','CERRADA','PAGADA','ANULADA')),
            cliente_nombre TEXT,
            cliente_telefono TEXT,
            cliente_documento TEXT,
            mesa_numero INTEGER,
            num_personas INTEGER DEFAULT 1,
            subtotal REAL DEFAULT 0,
            descuento REAL DEFAULT 0,
            impuesto REAL DEFAULT 0,
            total REAL DEFAULT 0,
            total_pagado REAL DEFAULT 0,
            saldo_pendiente REAL DEFAULT 0,
            metodo_pago TEXT,
            notas TEXT,
            motivo_descuento TEXT,
            id_usuario INTEGER NOT NULL,
            usuario_nombre TEXT,
            fecha_creacion TEXT DEFAULT (datetime('now','localtime')),
            fecha_cierre TEXT,
            fecha_pago TEXT,
            sincronizado INTEGER DEFAULT 0,
            es_contingencia INTEGER DEFAULT 0,
            numero_talonario TEXT,
            FOREIGN KEY (id_usuario) REFERENCES usuarios(id_usuario)
        )
    """)

    # ==========================================
    #  TABLA: DETALLE DE VENTAS
    # ==========================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS venta_detalle (
            id_detalle INTEGER PRIMARY KEY AUTOINCREMENT,
            id_venta INTEGER NOT NULL,
            id_producto INTEGER NOT NULL,
            producto_nombre TEXT NOT NULL,
            cantidad INTEGER NOT NULL DEFAULT 1,
            precio_unitario REAL NOT NULL,
            descuento_linea REAL DEFAULT 0,
            total_linea REAL NOT NULL,
            notas TEXT,
            estado_cocina TEXT DEFAULT 'N/A'
                CHECK(estado_cocina IN ('N/A','PENDIENTE','PREPARANDO','LISTO','ENTREGADO')),
            hora_pedido TEXT DEFAULT (datetime('now','localtime')),
            hora_listo TEXT,
            sincronizado INTEGER DEFAULT 0,
            FOREIGN KEY (id_venta) REFERENCES ventas(id_venta) ON DELETE CASCADE,
            FOREIGN KEY (id_producto) REFERENCES productos(id_producto)
        )
    """)

    # ==========================================
    #  TABLA: ÓRDENES DE COCINA
    # ==========================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ordenes_cocina (
            id_orden INTEGER PRIMARY KEY AUTOINCREMENT,
            id_venta INTEGER NOT NULL,
            id_detalle INTEGER NOT NULL,
            numero_venta TEXT NOT NULL,
            producto_nombre TEXT NOT NULL,
            cantidad INTEGER NOT NULL,
            notas TEXT,
            estado TEXT DEFAULT 'PENDIENTE'
                CHECK(estado IN ('PENDIENTE','PREPARANDO','LISTO','ENTREGADO','CANCELADO')),
            mesa_numero INTEGER,
            cliente_nombre TEXT,
            prioridad INTEGER DEFAULT 0,
            hora_pedido TEXT DEFAULT (datetime('now','localtime')),
            hora_inicio TEXT,
            hora_listo TEXT,
            hora_entrega TEXT,
            usuario_cocina TEXT,
            notificado_listo INTEGER DEFAULT 0,
            sincronizado INTEGER DEFAULT 0,
            FOREIGN KEY (id_venta) REFERENCES ventas(id_venta),
            FOREIGN KEY (id_detalle) REFERENCES venta_detalle(id_detalle)
        )
    """)

    # ==========================================
    #  TABLA: BOLETAS DE ENTRADA
    # ==========================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS boletas_entrada (
            id_boleta INTEGER PRIMARY KEY AUTOINCREMENT,
            numero_boleta TEXT UNIQUE NOT NULL,
            id_venta INTEGER,
            nombre_visitante TEXT,
            documento_visitante TEXT,
            cantidad_personas INTEGER DEFAULT 1,
            precio_persona REAL DEFAULT 35000,
            total REAL NOT NULL,
            metodo_pago TEXT DEFAULT 'EFECTIVO',
            hora_entrada TEXT DEFAULT (datetime('now','localtime')),
            hora_salida TEXT,
            notas TEXT,
            id_usuario INTEGER NOT NULL,
            sincronizado INTEGER DEFAULT 0,
            FOREIGN KEY (id_venta) REFERENCES ventas(id_venta),
            FOREIGN KEY (id_usuario) REFERENCES usuarios(id_usuario)
        )
    """)

    # ==========================================
    #  TABLA: PAGOS
    # ==========================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pagos (
            id_pago INTEGER PRIMARY KEY AUTOINCREMENT,
            id_venta INTEGER NOT NULL,
            valor REAL NOT NULL,
            metodo_pago TEXT NOT NULL,
            referencia TEXT,
            fecha_pago TEXT DEFAULT (datetime('now','localtime')),
            usuario_registro TEXT,
            sincronizado INTEGER DEFAULT 0,
            monto_recibido REAL,
            FOREIGN KEY (id_venta) REFERENCES ventas(id_venta) ON DELETE CASCADE
        )
    """)

    # ==========================================
    #  TABLA: CAJA DIARIA
    # ==========================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS caja_diaria (
            id_caja INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha_apertura TEXT NOT NULL,
            fecha_cierre TEXT,
            usuario_apertura TEXT NOT NULL,
            usuario_cierre TEXT,
            monto_inicial REAL DEFAULT 0,
            total_ventas REAL DEFAULT 0,
            total_boletas REAL DEFAULT 0,
            total_gastos REAL DEFAULT 0,
            monto_esperado REAL DEFAULT 0,
            monto_real REAL,
            diferencia REAL DEFAULT 0,
            estado TEXT DEFAULT 'ABIERTA'
                CHECK(estado IN ('ABIERTA','CERRADA')),
            observaciones TEXT,
            sincronizado INTEGER DEFAULT 0
        )
    """)

    # ==========================================
    #  TABLA: MOVIMIENTOS DE CAJA
    # ==========================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS movimientos_caja (
            id_movimiento INTEGER PRIMARY KEY AUTOINCREMENT,
            id_caja INTEGER NOT NULL,
            tipo TEXT NOT NULL CHECK(tipo IN ('INGRESO','EGRESO')),
            concepto TEXT NOT NULL,
            valor REAL NOT NULL,
            metodo_pago TEXT DEFAULT 'EFECTIVO',
            referencia TEXT,
            usuario TEXT NOT NULL,
            fecha_hora TEXT DEFAULT (datetime('now','localtime')),
            sincronizado INTEGER DEFAULT 0,
            FOREIGN KEY (id_caja) REFERENCES caja_diaria(id_caja)
        )
    """)

    # ==========================================
    #  TABLA: GASTOS
    # ==========================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS gastos (
            id_gasto INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT NOT NULL,
            descripcion TEXT NOT NULL,
            valor REAL NOT NULL,
            metodo_pago TEXT DEFAULT 'EFECTIVO',
            categoria TEXT DEFAULT 'General',
            tipo_gasto TEXT DEFAULT 'OPERATIVO'
                CHECK(tipo_gasto IN ('OPERATIVO','COMPRA_INVENTARIO','SERVICIOS','NOMINA','OTRO')),
            proveedor TEXT,
            factura_proveedor TEXT,
            usuario_registro TEXT NOT NULL,
            fecha_registro TEXT DEFAULT (datetime('now','localtime')),
            sincronizado INTEGER DEFAULT 0
        )
    """)

    # ==========================================
    #  TABLA: MOVIMIENTOS DE INVENTARIO
    # ==========================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS movimientos_inventario (
            id_movimiento INTEGER PRIMARY KEY AUTOINCREMENT,
            id_producto INTEGER NOT NULL,
            tipo TEXT NOT NULL
                CHECK(tipo IN ('ENTRADA','SALIDA','AJUSTE','VENTA','DEVOLUCION')),
            cantidad INTEGER NOT NULL,
            stock_anterior INTEGER,
            stock_nuevo INTEGER,
            motivo TEXT,
            referencia TEXT,
            usuario TEXT NOT NULL,
            fecha TEXT DEFAULT (datetime('now','localtime')),
            sincronizado INTEGER DEFAULT 0,
            FOREIGN KEY (id_producto) REFERENCES productos(id_producto)
        )
    """)

    # ==========================================
    #  TABLA: MÉTODOS DE PAGO
    # ==========================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS metodos_pago (
            id_metodo INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT UNIQUE NOT NULL,
            activo INTEGER DEFAULT 1,
            orden INTEGER DEFAULT 0
        )
    """)

    # ==========================================
    #  TABLA: SERIES DE FACTURACIÓN
    # ==========================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS series_facturacion (
            id_serie INTEGER PRIMARY KEY AUTOINCREMENT,
            prefijo TEXT DEFAULT 'POS',
            ano INTEGER,
            consecutivo_actual INTEGER DEFAULT 0,
            formato TEXT DEFAULT '{prefijo}-{ano}-{consecutivo:06d}',
            activa INTEGER DEFAULT 1
        )
    """)

    # ==========================================
    #  TABLA: SERIES DE BOLETAS
    # ==========================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS series_boletas (
            id_serie INTEGER PRIMARY KEY AUTOINCREMENT,
            prefijo TEXT DEFAULT 'BOL',
            ano INTEGER,
            consecutivo_actual INTEGER DEFAULT 0,
            formato TEXT DEFAULT '{prefijo}-{ano}-{consecutivo:06d}',
            activa INTEGER DEFAULT 1
        )
    """)

    # ==========================================
    #  TABLA: FACTURAS ELECTRÓNICAS
    # ==========================================
    cursor.execute("""
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
    """)

    # ==========================================
    #  TABLA: DEVOLUCIONES
    # ==========================================
    cursor.execute("""
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
    """)

    # ==========================================
    #  TABLA: COLA DE SINCRONIZACIÓN
    # ==========================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sync_queue (
            id_sync INTEGER PRIMARY KEY AUTOINCREMENT,
            tabla TEXT NOT NULL,
            id_registro INTEGER NOT NULL,
            accion TEXT NOT NULL CHECK(accion IN ('INSERT','UPDATE','DELETE')),
            datos_json TEXT,
            intentos INTEGER DEFAULT 0,
            max_intentos INTEGER DEFAULT 5,
            estado TEXT DEFAULT 'PENDIENTE'
                CHECK(estado IN ('PENDIENTE','ENVIANDO','COMPLETADO','ERROR')),
            error_msg TEXT,
            fecha_creacion TEXT DEFAULT (datetime('now','localtime')),
            fecha_envio TEXT
        )
    """)

    # ==========================================
    #  TABLA: SOCIOS Y MEMBRESÍAS
    # ==========================================
    cursor.execute("""
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
    """)
    cursor.execute("""
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
    """)

    # ==========================================
    #  TABLA: CONFIGURACIÓN DEL SISTEMA
    # ==========================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS configuracion (
            clave TEXT PRIMARY KEY,
            valor TEXT,
            tipo TEXT DEFAULT 'texto',
            descripcion TEXT,
            fecha_actualizacion TEXT DEFAULT (datetime('now','localtime'))
        )
    """)

    # ==========================================
    #  TABLA: AUDITORÍA
    # ==========================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS auditoria (
            id_auditoria INTEGER PRIMARY KEY AUTOINCREMENT,
            tabla_afectada TEXT,
            id_registro INTEGER,
            accion TEXT,
            usuario TEXT,
            comentario TEXT,
            datos_anteriores TEXT,
            datos_nuevos TEXT,
            ip_address TEXT,
            fecha_hora TEXT DEFAULT (datetime('now','localtime'))
        )
    """)

    # ==========================================
    #  TABLA: RESERVAS DE ALMUERZO
    # ==========================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reservas_almuerzo (
            id_reserva INTEGER PRIMARY KEY AUTOINCREMENT,
            id_venta INTEGER,
            cliente_nombre TEXT NOT NULL,
            telefono TEXT,
            cantidad_almuerzos INTEGER DEFAULT 1,
            tipo_almuerzo TEXT,
            hora_reserva TEXT DEFAULT (datetime('now','localtime')),
            hora_entrega_estimada TEXT,
            estado TEXT DEFAULT 'RESERVADO'
                CHECK(estado IN ('RESERVADO','EN_PREPARACION','LISTO','ENTREGADO','CANCELADO')),
            notas TEXT,
            notificado_listo INTEGER DEFAULT 0,
            id_usuario INTEGER,
            sincronizado INTEGER DEFAULT 0,
            FOREIGN KEY (id_venta) REFERENCES ventas(id_venta),
            FOREIGN KEY (id_usuario) REFERENCES usuarios(id_usuario)
        )
    """)

    # ==========================================
    #  TABLA: TAREAS DE PRE-PRODUCCION
    # ==========================================
    cursor.execute("""
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
    """)

    # ==========================================
    #  TABLA: PLANTILLA CHECKLIST DE ALMUERZO
    # ==========================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS almuerzo_checklist_template (
            id_item INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo_almuerzo TEXT NOT NULL,
            descripcion TEXT NOT NULL,
            orden INTEGER DEFAULT 0
        )
    """)

    # ==========================================
    #  TABLA: CHECKLIST POR RESERVA
    # ==========================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reserva_checklist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_reserva INTEGER NOT NULL,
            descripcion TEXT NOT NULL,
            completado INTEGER DEFAULT 0,
            hora_completado TEXT,
            FOREIGN KEY (id_reserva) REFERENCES reservas_almuerzo(id_reserva)
        )
    """)

    # ==========================================
    #  TABLA: SESIONES DE USUARIO
    # ==========================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sesiones (
            id_sesion INTEGER PRIMARY KEY AUTOINCREMENT,
            id_usuario INTEGER NOT NULL,
            fecha_inicio TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            fecha_fin TEXT,
            FOREIGN KEY (id_usuario) REFERENCES usuarios(id_usuario)
        )
    """)

    # ==========================================
    #  ÍNDICES PARA RENDIMIENTO
    # ==========================================
    indices = [
        "CREATE INDEX IF NOT EXISTS idx_productos_codigo ON productos(codigo_barras)",
        "CREATE INDEX IF NOT EXISTS idx_productos_nombre ON productos(nombre)",
        "CREATE INDEX IF NOT EXISTS idx_productos_categoria ON productos(id_categoria)",
        "CREATE INDEX IF NOT EXISTS idx_productos_activo ON productos(activo)",
        "CREATE INDEX IF NOT EXISTS idx_ventas_estado ON ventas(estado)",
        "CREATE INDEX IF NOT EXISTS idx_ventas_fecha ON ventas(fecha_creacion)",
        "CREATE INDEX IF NOT EXISTS idx_ventas_numero ON ventas(numero_venta)",
        "CREATE INDEX IF NOT EXISTS idx_ventas_sync ON ventas(sincronizado)",
        "CREATE INDEX IF NOT EXISTS idx_venta_detalle_venta ON venta_detalle(id_venta)",
        "CREATE INDEX IF NOT EXISTS idx_venta_detalle_producto ON venta_detalle(id_producto)",
        "CREATE INDEX IF NOT EXISTS idx_ordenes_cocina_estado ON ordenes_cocina(estado)",
        "CREATE INDEX IF NOT EXISTS idx_ordenes_cocina_venta ON ordenes_cocina(id_venta)",
        "CREATE INDEX IF NOT EXISTS idx_boletas_fecha ON boletas_entrada(hora_entrada)",
        "CREATE INDEX IF NOT EXISTS idx_pagos_venta ON pagos(id_venta)",
        "CREATE INDEX IF NOT EXISTS idx_pagos_fecha ON pagos(fecha_pago)",
        "CREATE INDEX IF NOT EXISTS idx_gastos_fecha ON gastos(fecha)",
        "CREATE INDEX IF NOT EXISTS idx_gastos_categoria ON gastos(categoria)",
        "CREATE INDEX IF NOT EXISTS idx_caja_estado ON caja_diaria(estado)",
        "CREATE INDEX IF NOT EXISTS idx_caja_fecha_apertura ON caja_diaria(fecha_apertura)",
        "CREATE INDEX IF NOT EXISTS idx_movimientos_inv ON movimientos_inventario(id_producto)",
        "CREATE INDEX IF NOT EXISTS idx_sync_estado ON sync_queue(estado)",
        "CREATE INDEX IF NOT EXISTS idx_auditoria_tabla ON auditoria(tabla_afectada)",
        "CREATE INDEX IF NOT EXISTS idx_reservas_estado ON reservas_almuerzo(estado)",
        # Índices para performance y consultas de sesgo/monitoreo
        "CREATE INDEX IF NOT EXISTS idx_ventas_estado_fecha ON ventas(estado, fecha_creacion)",
        "CREATE INDEX IF NOT EXISTS idx_ventas_usuario ON ventas(id_usuario)",
        "CREATE INDEX IF NOT EXISTS idx_auditoria_lookup ON auditoria(tabla_afectada, accion, id_registro)",
        "CREATE INDEX IF NOT EXISTS idx_auditoria_usuario_accion ON auditoria(usuario, accion)",
        "CREATE INDEX IF NOT EXISTS idx_auditoria_fecha ON auditoria(fecha_hora)",
        "CREATE INDEX IF NOT EXISTS idx_movinv_prod_fecha ON movimientos_inventario(id_producto, fecha)",
        # Índices faltantes detectados en análisis de rendimiento
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
    for idx in indices:
        cursor.execute(idx)

    conn.commit()
    conn.close()
    print("  ✅ Base de datos creada con todas las tablas")


def insertar_datos_iniciales():
    """Inserta datos iniciales del sistema"""
    print("\n[3/6] 📋 Insertando datos iniciales...")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Métodos de pago
    metodos = ['EFECTIVO', 'NEQUI', 'DAVIPLATA', 'TULLAVE', 'BANCOLOMBIA', 'TRANSFERENCIA']
    for i, m in enumerate(metodos):
        cursor.execute(
            "INSERT OR IGNORE INTO metodos_pago (nombre, orden) VALUES (?, ?)",
            (m, i)
        )
    print("  ✅ Métodos de pago")

    # Series de facturación
    import datetime
    ano = datetime.datetime.now().year
    cursor.execute("""
        INSERT OR IGNORE INTO series_facturacion (prefijo, ano, consecutivo_actual, activa)
        VALUES ('POS', ?, 0, 1)
    """, (ano,))
    cursor.execute("""
        INSERT OR IGNORE INTO series_boletas (prefijo, ano, consecutivo_actual, activa)
        VALUES ('BOL', ?, 0, 1)
    """, (ano,))
    cursor.execute("""
        INSERT OR IGNORE INTO series_facturacion (prefijo, ano, consecutivo_actual, activa)
        VALUES ('LP', ?, 0, 1)
    """, (ano,))
    print("  ✅ Series de facturación, boletas y facturas electrónicas (LP)")

    # Generar clave aleatoria para cocina web (solo para instalaciones nuevas)
    _cocina_token = secrets.token_urlsafe(8)

    # Configuración inicial
    configs = [
        ('nombre_negocio', 'Club Los Pocitos Azufrados', 'texto', 'Nombre del negocio'),
        ('ubicacion', 'Tocaima, Cundinamarca', 'texto', 'Ubicación'),
        ('telefono', '', 'texto', 'Teléfono del negocio'),
        ('nit', '', 'texto', 'NIT o cédula'),
        ('precio_boleta_persona', '35000', 'numero', 'Precio por persona para entrada'),
        ('moneda', 'COP', 'texto', 'Moneda'),
        ('impuesto_defecto', '0', 'numero', 'Impuesto por defecto (%)'),
        ('sync_url', '', 'texto', 'URL del servidor web para sincronización'),
        ('sync_token', '', 'texto', 'Token de autenticación para sync'),
        ('sync_auto', '0', 'booleano', 'Sincronización automática activada'),
        ('sync_intervalo', '300', 'numero', 'Intervalo de sync en segundos (5 min)'),
        ('ticket_ancho', '80', 'numero', 'Ancho del ticket en mm'),
        ('mostrar_cocina', '1', 'booleano', 'Mostrar pantalla de cocina'),
        ('sonido_cocina', '1', 'booleano', 'Sonido al llegar pedido a cocina'),
        ('stock_alerta', '5', 'numero', 'Cantidad mínima para alerta de stock'),
        ('tema_color', '#1976D2', 'texto', 'Color principal del tema'),
        ('backup_ruta', '', 'texto', 'Carpeta de destino para backups automáticos'),
        ('ultimo_backup', '', 'texto', 'Fecha del último backup automático (YYYY-MM-DD)'),
        ('schema_version', '10', 'numero', 'Versión de esquema de BD (no editar manualmente)'),
        # Resolución DIAN
        ('resolucion_dian_numero', '', 'texto', 'Número de resolución DIAN'),
        ('resolucion_dian_fecha_desde', '', 'texto', 'Fecha de inicio de vigencia (YYYY-MM-DD)'),
        ('resolucion_dian_fecha_hasta', '', 'texto', 'Fecha de fin de vigencia (YYYY-MM-DD)'),
        ('resolucion_dian_prefijo', 'LP', 'texto', 'Prefijo de facturación electrónica'),
        ('resolucion_dian_desde', '1', 'numero', 'Número inicial del rango autorizado'),
        ('resolucion_dian_hasta', '10000', 'numero', 'Número final del rango autorizado'),
        ('impresora_ancho_mm', '80', 'numero', 'Ancho de papel del ticket de impresion: 80 o 58 mm'),
        ('impresora_modo',      'pdf',      'texto',  'Modo de impresion: pdf o escpos'),
        ('impresora_nombre',    '',         'texto',  'Nombre de la impresora ESC/POS en Windows'),
        ('cocina_web_token',    _cocina_token, 'texto', 'Clave de acceso a la cocina web'),
        ('cocina_web_intervalo','15',       'entero', 'Intervalo de auto-refresh de la cocina web (seg)'),
    ]
    for clave, valor, tipo, desc in configs:
        cursor.execute(
            "INSERT OR IGNORE INTO configuracion (clave, valor, tipo, descripcion) VALUES (?, ?, ?, ?)",
            (clave, valor, tipo, desc)
        )
    print("  ✅ Configuración del sistema")
    print(f"  🔑 Clave cocina web generada: {_cocina_token}  (cámbiala en Configuración → Cocina Web)")

    # Tablas que estaban solo en main.py:aplicar_migraciones — sincronizadas aquí
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS clientes (
            id_cliente     INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre         TEXT NOT NULL,
            celular        TEXT,
            documento      TEXT,
            email          TEXT,
            notas          TEXT,
            fecha_creacion TEXT DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS proveedores (
            id_proveedor   INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre         TEXT NOT NULL,
            celular        TEXT,
            documento      TEXT,
            email          TEXT,
            notas          TEXT,
            fecha_creacion TEXT DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS compras_proveedor (
            id_compra          INTEGER PRIMARY KEY AUTOINCREMENT,
            id_proveedor       INTEGER NOT NULL,
            concepto           TEXT NOT NULL,
            valor              REAL NOT NULL,
            metodo_pago        TEXT DEFAULT 'EFECTIVO',
            estado_pago        TEXT DEFAULT 'PENDIENTE'
                CHECK(estado_pago IN ('PENDIENTE','PAGADA')),
            fecha              TEXT DEFAULT (datetime('now','localtime')),
            usuario_registro   TEXT NOT NULL,
            notas              TEXT,
            FOREIGN KEY (id_proveedor) REFERENCES proveedores(id_proveedor)
        );
        CREATE TABLE IF NOT EXISTS variantes_producto (
            id_variante      INTEGER PRIMARY KEY AUTOINCREMENT,
            id_producto      INTEGER NOT NULL,
            nombre_variante  TEXT NOT NULL,
            precio_adicional REAL DEFAULT 0,
            activa           INTEGER DEFAULT 1,
            FOREIGN KEY (id_producto) REFERENCES productos(id_producto) ON DELETE CASCADE
        );
    """)
    print("  ✅ Tablas clientes, proveedores, compras, variantes")

    # Categorías base iniciales (el usuario creará sus propias categorías)
    categorias_base = [
        ('Boletas',  'Boletas de entrada al establecimiento', '#E91E63', '🎫', 1, 'ambos'),
        ('Bebidas',  'Bebidas en general',                    '#2196F3', '🥤', 2, 'ambos'),
    ]
    for nombre, desc, color, icono, orden, tipo in categorias_base:
        cursor.execute(
            "INSERT OR IGNORE INTO categorias (nombre, descripcion, color, icono, orden, tipo) VALUES (?, ?, ?, ?, ?, ?)",
            (nombre, desc, color, icono, orden, tipo)
        )
    print("  ✅ Categorías base creadas")

    # Plantillas de checklist de preparación por tipo de almuerzo
    checklist_items = [
        ('General',        'Sopa lista',              0),
        ('General',        'Proteina lista',           1),
        ('General',        'Arroz listo',              2),
        ('General',        'Ensalada lista',           3),
        ('Bandeja Paisa',  'Descongelar carne',        0),
        ('Bandeja Paisa',  'Preparar frijoles',        1),
        ('Bandeja Paisa',  'Chicharron',               2),
        ('Bandeja Paisa',  'Arroz listo',              3),
        ('Bandeja Paisa',  'Platano maduro',           4),
        ('Bandeja Paisa',  'Aguacate y ensalada',      5),
        ('Sobrebarriga',   'Descongelar sobrebarriga', 0),
        ('Sobrebarriga',   'Papa o yuca lista',        1),
        ('Sobrebarriga',   'Arroz listo',              2),
        ('Sobrebarriga',   'Ensalada lista',           3),
        ('Corriente',      'Sopa lista',               0),
        ('Corriente',      'Proteina lista',           1),
        ('Corriente',      'Arroz listo',              2),
        ('Corriente',      'Ensalada lista',           3),
    ]
    for tipo, desc, orden in checklist_items:
        cursor.execute(
            "INSERT OR IGNORE INTO almuerzo_checklist_template (tipo_almuerzo, descripcion, orden) VALUES (?, ?, ?)",
            (tipo, desc, orden)
        )
    print("  ✅ Plantillas de checklist de almuerzos")

    conn.commit()
    conn.close()


def _generar_password_temporal():
    """Genera una contraseña temporal segura de 12 caracteres."""
    alfabeto = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alfabeto) for _ in range(12))


def _hashear(contrasena):
    """Hash de una contraseña con bcrypt (o SHA-256 si bcrypt no está instalado)."""
    if BCRYPT_DISPONIBLE:
        return bcrypt.hashpw(contrasena.encode('utf-8'), bcrypt.gensalt(12)).decode('utf-8')
    return hashlib.sha256(contrasena.encode()).hexdigest()


def crear_usuario_admin():
    """Crea el usuario administrador y los usuarios iniciales del sistema."""
    print("\n[4/6] 👤 Creando usuarios del sistema...")

    # Admin principal — contraseña elegida por el instalador
    while True:
        contrasena = getpass.getpass("  Contraseña para admin (min 6 caracteres): ")
        if len(contrasena) >= 6:
            break
        print("  Contraseña demasiado corta. Intente de nuevo.")

    # Contraseñas temporales generadas aleatoriamente (se muestran al final)
    pw_nelly   = _generar_password_temporal()
    pw_contadora = _generar_password_temporal()
    pw_cajero  = _generar_password_temporal()

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Admin principal
    cursor.execute("""
        INSERT OR IGNORE INTO usuarios (usuario, nombre_completo, contrasena_hash, rol, avatar_color)
        VALUES (?, ?, ?, ?, ?)
    """, ('admin', 'Administrador', _hashear(contrasena), 'administrador', '#1976D2'))

    # Nelly - Co-administradora
    cursor.execute("""
        INSERT OR IGNORE INTO usuarios (usuario, nombre_completo, contrasena_hash, rol, avatar_color, notas, debe_cambiar_password)
        VALUES (?, ?, ?, ?, ?, ?, 1)
    """, ('nelly', 'Nelly', _hashear(pw_nelly), 'administrador', '#E91E63',
          'Co-administradora del negocio'))

    # Contadora - Administradora especial
    cursor.execute("""
        INSERT OR IGNORE INTO usuarios (usuario, nombre_completo, contrasena_hash, rol, avatar_color, notas, debe_cambiar_password)
        VALUES (?, ?, ?, ?, ?, ?, 1)
    """, ('contadora', 'Contadora', _hashear(pw_contadora), 'administrador', '#FF6B35',
          'Administradora principal - Panel especial Contadora'))

    # Cajero por defecto
    cursor.execute("""
        INSERT OR IGNORE INTO usuarios (usuario, nombre_completo, contrasena_hash, rol, avatar_color, debe_cambiar_password)
        VALUES (?, ?, ?, ?, ?, 1)
    """, ('cajero', 'Cajero', _hashear(pw_cajero), 'cajero', '#4CAF50'))

    conn.commit()
    conn.close()

    print("  ✅ admin (Administrador)")
    print("  ✅ nelly (Co-administradora)")
    print("  ✅ contadora (Administradora - Panel Especial)")
    print("  ✅ cajero (Cajero)")
    print()
    print("  *** CONTRASEÑAS TEMPORALES — ANOTE Y GUARDE EN LUGAR SEGURO ***")
    print(f"     nelly   : {pw_nelly}")
    print(f"     contadora : {pw_contadora}")
    print(f"     cajero  : {pw_cajero}")
    print("  *** Cada usuario debe cambiar su contraseña en el primer login ***")
    # Retornar para poder mostrar en resumen también
    return pw_nelly, pw_contadora, pw_cajero


def insertar_productos_ejemplo():
    """Sistema entregado sin productos - el usuario creará sus propios productos"""
    print("\n[5/6] 🛒 Sistema listo para agregar productos...")
    print("  ℹ️  No se insertaron productos de ejemplo")
    print("  ℹ️  Crear productos desde el módulo de administración")


def mostrar_resumen():
    """Muestra resumen de la instalación"""
    print("\n[6/6] 📊 Resumen de instalación")
    print("=" * 55)
    print("  🏖️  CLUB LOS POCITOS AZUFRADOS")
    print("  📍 Tocaima, Cundinamarca")
    print("=" * 55)
    print(f"  📁 Base de datos: {DB_PATH}")
    print(f"  📦 Tamaño: {os.path.getsize(DB_PATH) / 1024:.1f} KB")
    print()

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    tablas = cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    print(f"  📋 Tablas creadas: {len(tablas)}")
    for t in tablas:
        count = cursor.execute("SELECT COUNT(*) FROM [" + t[0] + "]").fetchone()[0]
        if count > 0:
            print(f"     - {t[0]}: {count} registros")

    conn.close()

    print()
    print("  ✅ ¡Instalación completada!")
    print()
    print("  Para iniciar el sistema ejecute:")
    print("    python main.py")
    print()
    print("  Usuarios creados:")
    print("    admin    → Administrador (contraseña ingresada en el setup)")
    print("    nelly    → Co-admin (contraseña temporal mostrada arriba)")
    print("    contadora → Admin Especial (contraseña temporal mostrada arriba)")
    print("    cajero   → Cajero (contraseña temporal mostrada arriba)")
    print()


def main():
    """Instalación completa: carpetas, base de datos, datos iniciales, usuarios y productos."""
    print()
    print("╔══════════════════════════════════════════════════╗")
    print("║   🏖️  CLUB LOS POCITOS AZUFRADOS               ║")
    print("║   Sistema POS - Instalación                     ║")
    print("║   Tocaima, Cundinamarca                         ║")
    print("╚══════════════════════════════════════════════════╝")

    crear_directorios()
    crear_base_datos()
    insertar_datos_iniciales()
    crear_usuario_admin()
    insertar_productos_ejemplo()
    mostrar_resumen()


if __name__ == "__main__":
    main()
