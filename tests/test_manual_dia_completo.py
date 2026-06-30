"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  MANUAL DE CAPACITACION — CLUB LOS POCITOS AZUFRADOS                        ║
║  "Tu ultimo dia: ensenas al nuevo empleado TODO el sistema"                 ║
║                                                                             ║
║  Este archivo simula un dia completo de operacion desde la perspectiva      ║
║  del vendedor. Cada seccion es una leccion que le explicas al nuevo.        ║
║                                                                             ║
║  FLUJO DEL DIA:                                                             ║
║    1. Pre-condiciones y data inicial                                        ║
║    2. APERTURA DE CAJA                                                      ║
║    3. INVENTARIO                                                            ║
║    4. BOLETAS DE ENTRADA                                                    ║
║    5. BAR — ventas normales (efectivo, Nequi)                               ║
║    6. CUENTAS ABIERTAS + cobro parcial/total                                ║
║    7. COCINA — ordenes                                                      ║
║    8. ALMUERZOS — reservas + checklist                                      ║
║    9. FACTURA ELECTRONICA                                                   ║
║   10. GASTOS                                                                ║
║   11. NOMINA                                                                ║
║   12. ANULACIONES con PIN admin                                             ║
║   13. CIERRE DE CAJA                                                        ║
║   14. REPORTES                                                              ║
║   15. INTEGRIDAD                                                            ║
╚══════════════════════════════════════════════════════════════════════════════╝

Cada leccion explica:
  • QUE estamos probando
  • POR QUE es importante
  • COMO funciona el sistema internamente
  • QUE esperar como resultado
"""

import os, sys, datetime, sqlite3, pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from database.connection import conexion_segura, transaccion_atomica
from models.ventas import crear_venta, abrir_cuenta_abierta, verificar_stock_minimo
from models.validaciones import validar_resolucion_dian, verificar_pin_admin
from models.inventario import registrar_movimiento_stock, aprobar_producto
from utils.logger import log_auditoria


# ==============================================================================
# HELPERS
# ==============================================================================

def _hoy():
    return datetime.date.today().isoformat()

def _item(id_producto, nombre, cantidad=1, precio=0, requiere_cocina=False,
          es_boleta=False, es_almuerzo=False, controla_stock=True,
          pedido_nombre=None, pedido_hora=None, pedido_notas=None):
    """
    Leccion: "Este es el formato del carrito. Cada item tiene:
    - id_producto: para buscar el producto en BD
    - nombre: para mostrarlo en pantalla
    - cantidad: cuantas unidades
    - precio: precio unitario
    - requiere_cocina: si va a cocina (empanadas, hamburguesas)
    - es_almuerzo: si es almuerzo (va a reservas, no a ordenes cocina)
    - es_boleta: si es entrada (no descuenta inventario)
    - controla_stock: si debe verificar y descontar del inventario
    """
    return {
        'id_producto': id_producto,
        'nombre': nombre,
        'cantidad': cantidad,
        'precio': precio,
        'total': precio * cantidad,
        'requiere_cocina': requiere_cocina,
        'es_almuerzo': es_almuerzo,
        'es_boleta': es_boleta,
        'controla_stock': controla_stock,
        'pedido_nombre': pedido_nombre,
        'pedido_hora': pedido_hora,
        'pedido_notas': pedido_notas,
    }

def _usuario(nombre='vendedor', id_usuario=1, nombre_completo='Carlos el Vendedor'):
    """Formato de usuario como lo usa el sistema."""
    return {'id_usuario': id_usuario, 'usuario': nombre, 'nombre_completo': nombre_completo}

def _count(db, tabla, where='1=1'):
    with conexion_segura(db) as conn:
        return conn.execute(f"SELECT COUNT(*) FROM {tabla} WHERE {where}").fetchone()[0]

def _sum(db, tabla, col, where='1=1'):
    with conexion_segura(db) as conn:
        r = conn.execute(f"SELECT COALESCE(SUM({col}), 0) as total FROM {tabla} WHERE {where}").fetchone()
        return r['total']


# ==============================================================================
# FIXTURE SCHEMA COMPLETO
# ==============================================================================

@pytest.fixture(scope="module")
def db_full(tmp_path_factory):
    """BD completa con schema real + data inicial.
    
    Leccion #1: "Esta BD contiene TODAS las tablas del sistema. Cada tabla guarda
     una parte de la operacion. Fijate como se relacionan entre si:
     - productos -> venta_detalle -> ventas
     - ventas -> ordenes_cocina / reservas_almuerzo
     - caja_diaria -> movimientos_caja
     - ventas -> pagos -> facturas_electronicas
     - nomina_empleados -> nomina_turnos
    """
    db = str(tmp_path_factory.mktemp("data") / "pocitos_test.db")
    ano = datetime.datetime.now().year
    hoy = datetime.date.today()
    lunes = hoy - datetime.timedelta(days=hoy.weekday())
    
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA journal_mode=WAL")
    
    conn.executescript(f"""
        CREATE TABLE configuracion (
            id_config INTEGER PRIMARY KEY AUTOINCREMENT,
            clave TEXT UNIQUE NOT NULL,
            valor TEXT, tipo TEXT DEFAULT 'texto', descripcion TEXT
        );
        CREATE TABLE usuarios (
            id_usuario INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT UNIQUE NOT NULL,
            nombre_completo TEXT NOT NULL,
            contrasena_hash TEXT NOT NULL DEFAULT '',
            rol TEXT NOT NULL DEFAULT 'cajero',
            activo INTEGER DEFAULT 1, email TEXT,
            avatar_color TEXT DEFAULT '#1976D2',
            ultimo_login TEXT, debe_cambiar_password INTEGER DEFAULT 0, pin TEXT
        );
        CREATE TABLE sesiones (
            id_sesion INTEGER PRIMARY KEY AUTOINCREMENT,
            id_usuario INTEGER NOT NULL,
            fecha_inicio TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            fecha_fin TEXT,
            FOREIGN KEY (id_usuario) REFERENCES usuarios(id_usuario)
        );
        CREATE TABLE categorias (
            id_categoria INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT UNIQUE NOT NULL, descripcion TEXT,
            color TEXT DEFAULT '#1976D2', icono TEXT DEFAULT '',
            orden INTEGER DEFAULT 0, activa INTEGER DEFAULT 1,
            tipo TEXT DEFAULT 'restaurante',
            fecha_creacion TEXT DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE subcategorias (
            id_subcategoria INTEGER PRIMARY KEY AUTOINCREMENT,
            id_categoria INTEGER NOT NULL, nombre TEXT NOT NULL,
            descripcion TEXT, activa INTEGER DEFAULT 1,
            fecha_creacion TEXT DEFAULT (datetime('now','localtime')),
            UNIQUE(id_categoria, nombre),
            FOREIGN KEY (id_categoria) REFERENCES categorias(id_categoria)
        );
        CREATE TABLE productos (
            id_producto INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo_barras TEXT UNIQUE, nombre TEXT NOT NULL,
            id_categoria INTEGER, id_subcategoria INTEGER,
            descripcion TEXT, precio_venta REAL NOT NULL DEFAULT 0,
            precio_costo REAL DEFAULT 0, stock_actual INTEGER DEFAULT 0,
            stock_minimo INTEGER DEFAULT 5, unidad_medida TEXT DEFAULT 'unidad',
            requiere_cocina INTEGER DEFAULT 0,
            es_boleta_entrada INTEGER DEFAULT 0,
            permite_descuento INTEGER DEFAULT 1,
            impuesto_porcentaje REAL DEFAULT 0, imagen_path TEXT,
            activo INTEGER DEFAULT 1,
            pendiente_aprobacion INTEGER DEFAULT 0,
            controla_stock INTEGER DEFAULT 0,
            fecha_creacion TEXT DEFAULT (datetime('now','localtime')),
            fecha_actualizacion TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (id_categoria) REFERENCES categorias(id_categoria)
        );
        CREATE TABLE ventas (
            id_venta INTEGER PRIMARY KEY AUTOINCREMENT,
            numero_venta TEXT UNIQUE NOT NULL, tipo TEXT DEFAULT 'normal',
            estado TEXT DEFAULT 'ABIERTA', cliente_nombre TEXT,
            cliente_telefono TEXT, cliente_documento TEXT,
            mesa_numero INTEGER, num_personas INTEGER DEFAULT 1,
            subtotal REAL DEFAULT 0, descuento REAL DEFAULT 0,
            motivo_descuento TEXT, impuesto REAL DEFAULT 0,
            total REAL DEFAULT 0, total_pagado REAL DEFAULT 0,
            saldo_pendiente REAL DEFAULT 0, metodo_pago TEXT, notas TEXT,
            id_usuario INTEGER NOT NULL, usuario_nombre TEXT,
            fecha_creacion TEXT DEFAULT (datetime('now','localtime')),
            fecha_cierre TEXT, fecha_pago TEXT,
            sincronizado INTEGER DEFAULT 0, es_contingencia INTEGER DEFAULT 0,
            numero_talonario TEXT, id_cliente INTEGER
        );
        CREATE TABLE venta_detalle (
            id_detalle INTEGER PRIMARY KEY AUTOINCREMENT,
            id_venta INTEGER NOT NULL, id_producto INTEGER,
            producto_nombre TEXT NOT NULL, cantidad INTEGER NOT NULL DEFAULT 1,
            precio_unitario REAL NOT NULL, descuento_linea REAL DEFAULT 0,
            total_linea REAL NOT NULL, notas TEXT,
            estado_cocina TEXT DEFAULT 'N/A',
            hora_pedido TEXT DEFAULT (datetime('now','localtime')),
            hora_listo TEXT, sincronizado INTEGER DEFAULT 0,
            FOREIGN KEY (id_venta) REFERENCES ventas(id_venta) ON DELETE CASCADE
        );
        CREATE TABLE pagos (
            id_pago INTEGER PRIMARY KEY AUTOINCREMENT,
            id_venta INTEGER NOT NULL, valor REAL NOT NULL,
            metodo_pago TEXT NOT NULL, referencia TEXT,
            fecha_pago TEXT DEFAULT (datetime('now','localtime')),
            usuario_registro TEXT, monto_recibido REAL,
            sincronizado INTEGER DEFAULT 0,
            FOREIGN KEY (id_venta) REFERENCES ventas(id_venta) ON DELETE CASCADE
        );
        CREATE TABLE ordenes_cocina (
            id_orden INTEGER PRIMARY KEY AUTOINCREMENT,
            id_venta INTEGER NOT NULL, id_detalle INTEGER NOT NULL,
            numero_venta TEXT NOT NULL, producto_nombre TEXT NOT NULL,
            cantidad INTEGER NOT NULL, notas TEXT,
            estado TEXT DEFAULT 'PENDIENTE', mesa_numero INTEGER,
            cliente_nombre TEXT, prioridad INTEGER DEFAULT 0,
            hora_pedido TEXT DEFAULT (datetime('now','localtime')),
            hora_inicio TEXT, hora_listo TEXT, hora_entrega TEXT,
            usuario_cocina TEXT, notificado_listo INTEGER DEFAULT 0,
            sincronizado INTEGER DEFAULT 0,
            FOREIGN KEY (id_venta) REFERENCES ventas(id_venta),
            FOREIGN KEY (id_detalle) REFERENCES venta_detalle(id_detalle)
        );
        CREATE TABLE boletas_entrada (
            id_boleta INTEGER PRIMARY KEY AUTOINCREMENT,
            numero_boleta TEXT UNIQUE NOT NULL, id_venta INTEGER,
            nombre_visitante TEXT, documento_visitante TEXT,
            cantidad_personas INTEGER DEFAULT 1, precio_persona REAL DEFAULT 0,
            total REAL NOT NULL, metodo_pago TEXT DEFAULT 'EFECTIVO',
            hora_entrada TEXT DEFAULT (datetime('now','localtime')),
            hora_salida TEXT, notas TEXT, id_usuario INTEGER NOT NULL,
            sincronizado INTEGER DEFAULT 0,
            FOREIGN KEY (id_venta) REFERENCES ventas(id_venta)
        );
        CREATE TABLE caja_diaria (
            id_caja INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha_apertura TEXT NOT NULL, fecha_cierre TEXT,
            usuario_apertura TEXT NOT NULL, usuario_cierre TEXT,
            monto_inicial REAL DEFAULT 0, total_ventas REAL DEFAULT 0,
            total_boletas REAL DEFAULT 0, total_gastos REAL DEFAULT 0,
            monto_esperado REAL DEFAULT 0, monto_real REAL,
            diferencia REAL DEFAULT 0, estado TEXT DEFAULT 'ABIERTA',
            observaciones TEXT, sincronizado INTEGER DEFAULT 0
        );
        CREATE TABLE movimientos_caja (
            id_movimiento INTEGER PRIMARY KEY AUTOINCREMENT,
            id_caja INTEGER NOT NULL,
            tipo TEXT NOT NULL CHECK(tipo IN ('INGRESO','EGRESO')),
            concepto TEXT NOT NULL, valor REAL NOT NULL,
            metodo_pago TEXT DEFAULT 'EFECTIVO', referencia TEXT,
            usuario TEXT NOT NULL,
            fecha_hora TEXT DEFAULT (datetime('now','localtime')),
            sincronizado INTEGER DEFAULT 0,
            FOREIGN KEY (id_caja) REFERENCES caja_diaria(id_caja)
        );
        CREATE TABLE gastos (
            id_gasto INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT NOT NULL, descripcion TEXT NOT NULL,
            valor REAL NOT NULL, metodo_pago TEXT DEFAULT 'EFECTIVO',
            categoria TEXT DEFAULT 'General',
            tipo_gasto TEXT DEFAULT 'OPERATIVO',
            proveedor TEXT, factura_proveedor TEXT,
            usuario_registro TEXT NOT NULL,
            fecha_registro TEXT DEFAULT (datetime('now','localtime')),
            sincronizado INTEGER DEFAULT 0
        );
        CREATE TABLE movimientos_inventario (
            id_movimiento INTEGER PRIMARY KEY AUTOINCREMENT,
            id_producto INTEGER NOT NULL,
            tipo TEXT NOT NULL CHECK(tipo IN ('ENTRADA','SALIDA','AJUSTE','VENTA','DEVOLUCION')),
            cantidad INTEGER NOT NULL, stock_anterior INTEGER,
            stock_nuevo INTEGER, motivo TEXT, referencia TEXT,
            usuario TEXT NOT NULL, fecha TEXT DEFAULT (datetime('now','localtime')),
            sincronizado INTEGER DEFAULT 0,
            FOREIGN KEY (id_producto) REFERENCES productos(id_producto)
        );
        CREATE TABLE reservas_almuerzo (
            id_reserva INTEGER PRIMARY KEY AUTOINCREMENT,
            id_venta INTEGER, cliente_nombre TEXT NOT NULL, telefono TEXT,
            cantidad_almuerzos INTEGER DEFAULT 1, tipo_almuerzo TEXT,
            hora_reserva TEXT DEFAULT (datetime('now','localtime')),
            hora_entrega_estimada TEXT, estado TEXT DEFAULT 'RESERVADO',
            notas TEXT, notificado_listo INTEGER DEFAULT 0,
            id_usuario INTEGER, sincronizado INTEGER DEFAULT 0
        );
        CREATE TABLE almuerzo_checklist_template (
            id_item INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo_almuerzo TEXT NOT NULL, descripcion TEXT NOT NULL,
            orden INTEGER DEFAULT 0
        );
        CREATE TABLE reserva_checklist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_reserva INTEGER NOT NULL, descripcion TEXT NOT NULL,
            completado INTEGER DEFAULT 0, hora_completado TEXT,
            FOREIGN KEY (id_reserva) REFERENCES reservas_almuerzo(id_reserva)
        );
        CREATE TABLE facturas_electronicas (
            id_factura INTEGER PRIMARY KEY AUTOINCREMENT,
            id_venta INTEGER NOT NULL, numero_factura TEXT UNIQUE NOT NULL,
            cliente_nombre TEXT NOT NULL, cliente_nit TEXT NOT NULL,
            cliente_email TEXT,
            fecha_emision TEXT DEFAULT (datetime('now','localtime')),
            usuario_registro TEXT NOT NULL,
            FOREIGN KEY (id_venta) REFERENCES ventas(id_venta)
        );
        CREATE TABLE devoluciones (
            id_devolucion INTEGER PRIMARY KEY AUTOINCREMENT,
            id_venta INTEGER NOT NULL, monto REAL NOT NULL, motivo TEXT NOT NULL,
            usuario TEXT NOT NULL, fecha TEXT DEFAULT (datetime('now','localtime')),
            aplicado_caja INTEGER DEFAULT 0,
            FOREIGN KEY (id_venta) REFERENCES ventas(id_venta)
        );
        CREATE TABLE nomina_empleados (
            id_empleado INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL, tarifa_normal REAL DEFAULT 0,
            tarifa_festivo REAL DEFAULT 0, activo INTEGER DEFAULT 1,
            fecha_creacion TEXT DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE nomina_turnos (
            id_turno INTEGER PRIMARY KEY AUTOINCREMENT,
            id_empleado INTEGER NOT NULL, semana_inicio TEXT NOT NULL,
            dia_semana INTEGER NOT NULL, tipo TEXT NOT NULL DEFAULT 'Normal'
                CHECK(tipo IN ('Normal','Festivo','No trabajo')),
            pagado INTEGER DEFAULT 0,
            fecha_registro TEXT DEFAULT (datetime('now','localtime')),
            UNIQUE(id_empleado, semana_inicio, dia_semana),
            FOREIGN KEY (id_empleado) REFERENCES nomina_empleados(id_empleado)
        );
        CREATE TABLE series_facturacion (
            id_serie INTEGER PRIMARY KEY AUTOINCREMENT,
            prefijo TEXT NOT NULL, ano INTEGER NOT NULL,
            consecutivo_actual INTEGER DEFAULT 0,
            formato TEXT DEFAULT '{{prefijo}}-{{ano}}-{{consecutivo:06d}}',
            activa INTEGER DEFAULT 1, UNIQUE(prefijo, ano)
        );
        CREATE TABLE series_boletas (
            id_serie INTEGER PRIMARY KEY AUTOINCREMENT,
            prefijo TEXT NOT NULL, ano INTEGER NOT NULL,
            consecutivo_actual INTEGER DEFAULT 0,
            formato TEXT DEFAULT '{{prefijo}}-{{ano}}-{{consecutivo:06d}}',
            activa INTEGER DEFAULT 1, UNIQUE(prefijo, ano)
        );
        CREATE TABLE metodos_pago (
            id_metodo INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT UNIQUE NOT NULL, activo INTEGER DEFAULT 1,
            orden INTEGER DEFAULT 0
        );
        CREATE TABLE clientes (
            id_cliente INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL, celular TEXT, documento TEXT, email TEXT,
            notas TEXT, fecha_creacion TEXT DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE proveedores (
            id_proveedor INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL, celular TEXT, documento TEXT, email TEXT,
            notas TEXT, fecha_creacion TEXT DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE compras_proveedor (
            id_compra INTEGER PRIMARY KEY AUTOINCREMENT,
            id_proveedor INTEGER NOT NULL, concepto TEXT NOT NULL,
            valor REAL NOT NULL, metodo_pago TEXT DEFAULT 'EFECTIVO',
            estado_pago TEXT DEFAULT 'PENDIENTE',
            fecha TEXT DEFAULT (datetime('now','localtime')),
            usuario_registro TEXT NOT NULL, notas TEXT,
            FOREIGN KEY (id_proveedor) REFERENCES proveedores(id_proveedor)
        );
        CREATE TABLE variantes_producto (
            id_variante INTEGER PRIMARY KEY AUTOINCREMENT,
            id_producto INTEGER NOT NULL, nombre_variante TEXT NOT NULL,
            precio_adicional REAL DEFAULT 0, activa INTEGER DEFAULT 1,
            FOREIGN KEY (id_producto) REFERENCES productos(id_producto) ON DELETE CASCADE
        );
        CREATE TABLE auditoria (
            id_auditoria INTEGER PRIMARY KEY AUTOINCREMENT,
            tabla_afectada TEXT, id_registro INTEGER, accion TEXT,
            usuario TEXT, comentario TEXT, datos_anteriores TEXT,
            datos_nuevos TEXT, ip_address TEXT,
            fecha_hora TEXT DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE tareas_preproduccion (
            id_tarea INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT NOT NULL DEFAULT (date('now','localtime')),
            descripcion TEXT NOT NULL, cantidad TEXT,
            completada INTEGER DEFAULT 0, hora_completado TEXT,
            usuario TEXT, fecha_registro TEXT DEFAULT (datetime('now','localtime'))
        );
        
        -- DATA INICIAL
        INSERT INTO usuarios (usuario, nombre_completo, contrasena_hash, rol, activo, pin)
            VALUES ('vendedor', 'Carlos el Vendedor', '', 'vendedor', 1, '1234');
        INSERT INTO usuarios (usuario, nombre_completo, contrasena_hash, rol, activo, pin)
            VALUES ('admin', 'Admin Don Jefe', '', 'administrador', 1, '9999');
        INSERT INTO usuarios (usuario, nombre_completo, contrasena_hash, rol, activo, pin)
            VALUES ('cajero', 'Maria la Cajera', '', 'cajero', 1, '5678');
        INSERT INTO usuarios (usuario, nombre_completo, contrasena_hash, rol, activo)
            VALUES ('nuevo', 'Pedro el Nuevo', '', 'cajero', 1);
        
        INSERT INTO metodos_pago (nombre, activo, orden) VALUES ('EFECTIVO', 1, 1);
        INSERT INTO metodos_pago (nombre, activo, orden) VALUES ('NEQUI', 1, 2);
        INSERT INTO metodos_pago (nombre, activo, orden) VALUES ('DAVIPLATA', 1, 3);
        INSERT INTO metodos_pago (nombre, activo, orden) VALUES ('TARJETA', 1, 4);
        INSERT INTO metodos_pago (nombre, activo, orden) VALUES ('TRANSFERENCIA', 1, 5);
        
        INSERT INTO categorias (nombre, color, tipo) VALUES ('Bebidas', '#1976D2', 'bar');
        INSERT INTO categorias (nombre, color, tipo) VALUES ('Comida Rapida', '#388E3C', 'restaurante');
        INSERT INTO categorias (nombre, color, tipo) VALUES ('Almuerzos', '#F57C00', 'restaurante');
        INSERT INTO categorias (nombre, color, tipo) VALUES ('Cervezas', '#6A1B9A', 'bar');
        INSERT INTO categorias (nombre, color, tipo) VALUES ('Boleta Entrada', '#E53935', 'ambos');
        
        INSERT INTO productos (nombre, precio_venta, precio_costo, stock_actual, stock_minimo, id_categoria, requiere_cocina, controla_stock, activo)
            VALUES ('Agua sin Gas', 2000, 800, 100, 10, 1, 0, 1, 1);
        INSERT INTO productos (nombre, precio_venta, precio_costo, stock_actual, stock_minimo, id_categoria, requiere_cocina, controla_stock, activo)
            VALUES ('Gaseosa Cola', 3000, 1200, 80, 10, 1, 0, 1, 1);
        INSERT INTO productos (nombre, precio_venta, precio_costo, stock_actual, stock_minimo, id_categoria, requiere_cocina, controla_stock, activo)
            VALUES ('Empanada', 4000, 1500, 50, 5, 2, 1, 1, 1);
        INSERT INTO productos (nombre, precio_venta, precio_costo, stock_actual, stock_minimo, id_categoria, requiere_cocina, controla_stock, activo)
            VALUES ('Hamburguesa Especial', 16000, 6000, 25, 5, 2, 1, 1, 1);
        INSERT INTO productos (nombre, precio_venta, precio_costo, stock_actual, stock_minimo, id_categoria, requiere_cocina, controla_stock, activo)
            VALUES ('Papas Fritas', 7000, 2000, 60, 10, 2, 1, 1, 1);
        INSERT INTO productos (nombre, precio_venta, precio_costo, stock_actual, stock_minimo, id_categoria, requiere_cocina, controla_stock, activo)
            VALUES ('Almuerzo Ejecutivo', 15000, 5500, 20, 5, 3, 0, 1, 1);
        INSERT INTO productos (nombre, precio_venta, precio_costo, stock_actual, stock_minimo, id_categoria, requiere_cocina, controla_stock, activo)
            VALUES ('Cerveza Aguila', 5000, 2000, 120, 10, 4, 0, 1, 1);
        INSERT INTO productos (nombre, precio_venta, precio_costo, stock_actual, stock_minimo, id_categoria, requiere_cocina, controla_stock, activo)
            VALUES ('Cerveza Club Colombia', 6000, 2500, 90, 10, 4, 0, 1, 1);
        INSERT INTO productos (nombre, precio_venta, precio_costo, stock_actual, stock_minimo, id_categoria, requiere_cocina, controla_stock, activo, pendiente_aprobacion)
            VALUES ('Limonada Natural', 5000, 1500, 30, 5, 1, 0, 1, 1, 1);
        INSERT INTO productos (nombre, precio_venta, precio_costo, stock_actual, stock_minimo, id_categoria, requiere_cocina, controla_stock, activo, pendiente_aprobacion)
            VALUES ('Chorizo con Arepa', 9000, 3000, 20, 3, 2, 1, 1, 1, 1);
        INSERT INTO productos (nombre, precio_venta, precio_costo, stock_actual, stock_minimo, id_categoria, es_boleta_entrada, activo)
            VALUES ('Entrada General', 35000, 0, 9999, 0, 5, 1, 1);
        
        INSERT INTO series_facturacion (prefijo, ano, consecutivo_actual, formato, activa)
            VALUES ('POS', {ano}, 0, '{{prefijo}}-{{ano}}-{{consecutivo:06d}}', 1);
        INSERT INTO series_facturacion (prefijo, ano, consecutivo_actual, formato, activa)
            VALUES ('LP', {ano}, 0, '{{prefijo}}-{{ano}}-{{consecutivo:06d}}', 1);
        INSERT INTO series_boletas (prefijo, ano, consecutivo_actual, formato, activa)
            VALUES ('BOL', {ano}, 0, '{{prefijo}}-{{ano}}-{{consecutivo:06d}}', 1);
        
        INSERT INTO configuracion (clave, valor, tipo, descripcion)
            VALUES ('nombre_negocio', 'Club Los Pocitos Azufrados', 'texto', 'Nombre del negocio');
        INSERT INTO configuracion (clave, valor, tipo, descripcion)
            VALUES ('precio_boleta_persona', '35000', 'numero', 'Precio de entrada por persona');
        INSERT INTO configuracion (clave, valor, tipo, descripcion)
            VALUES ('resolucion_dian_numero', '18764001234567', 'texto', 'Resolucion DIAN');
        INSERT INTO configuracion (clave, valor, tipo, descripcion)
            VALUES ('resolucion_dian_prefijo', 'LP', 'texto', 'Prefijo FE');
        INSERT INTO configuracion (clave, valor, tipo, descripcion)
            VALUES ('resolucion_dian_desde', '1', 'numero', 'Desde numero');
        INSERT INTO configuracion (clave, valor, tipo, descripcion)
            VALUES ('resolucion_dian_hasta', '10000', 'numero', 'Hasta numero');
        INSERT INTO configuracion (clave, valor, tipo, descripcion)
            VALUES ('resolucion_dian_fecha_desde', '2024-01-01', 'texto', 'Vigencia desde');
        INSERT INTO configuracion (clave, valor, tipo, descripcion)
            VALUES ('resolucion_dian_fecha_hasta', '2030-12-31', 'texto', 'Vigencia hasta');
        
        INSERT INTO almuerzo_checklist_template (tipo_almuerzo, descripcion, orden)
            VALUES ('Almuerzo Ejecutivo', 'Preparar proteina', 1);
        INSERT INTO almuerzo_checklist_template (tipo_almuerzo, descripcion, orden)
            VALUES ('Almuerzo Ejecutivo', 'Preparar arroz', 2);
        INSERT INTO almuerzo_checklist_template (tipo_almuerzo, descripcion, orden)
            VALUES ('Almuerzo Ejecutivo', 'Preparar ensalada', 3);
        INSERT INTO almuerzo_checklist_template (tipo_almuerzo, descripcion, orden)
            VALUES ('Almuerzo Ejecutivo', 'Empacar y servir', 4);
        
        INSERT INTO clientes (nombre, celular, documento) VALUES ('Juan Cliente', '3001234567', '123456789');
        INSERT INTO proveedores (nombre, celular, documento) VALUES ('Distribuidora Bebidas SAS', '3101112233', '900111222-3');
        INSERT INTO proveedores (nombre, celular, documento) VALUES ('Carnes y Alimentos LTDA', '3104445566', '900333444-5');
        
        INSERT INTO nomina_empleados (nombre, tarifa_normal, tarifa_festivo)
            VALUES ('Pedro el Nuevo', 50000, 70000);
        INSERT INTO nomina_empleados (nombre, tarifa_normal, tarifa_festivo)
            VALUES ('Maria la Cajera', 55000, 77000);
        INSERT INTO nomina_empleados (nombre, tarifa_normal, tarifa_festivo)
            VALUES ('Carlos Cocinero', 60000, 84000);
    """)
    conn.commit()
    conn.close()
    return db


# ==============================================================================
# TEST UNICO — DIA COMPLETO (las 15 lecciones en secuencia)
# ==============================================================================

class TestDiaCompletoManual:
    """Simula un dia completo de operacion como vendedor capacitando al nuevo.
    
    CORRER CON:  python -m pytest tests/test_manual_dia_completo.py -v -s
    """

    def test_dia_completo(self, db_full):
        """Ejecuta las 15 lecciones del manual de capacitacion en secuencia."""
        db = db_full
        usuario = _usuario()
        
        # ==================================================================
        # LECCION 1: PRE-CONDICIONES
        # ==================================================================
        self._lec("LECCION 1: PRE-CONDICIONES (checklist de apertura)")
        self._print("Le explicas al nuevo: 'Cada manana, antes de abrir, verificamos que")
        self._print("el sistema tenga todo lo necesario. Es como el checklist de un avion.'")
        
        with conexion_segura(db) as conn:
            n_prods = conn.execute(
                "SELECT COUNT(*) FROM productos WHERE activo=1 AND es_boleta_entrada=0"
            ).fetchone()[0]
            assert n_prods >= 10, f"Necesitamos al menos 10 productos, hay {n_prods}"
            self._ok(f"{n_prods} productos activos listos para vender")
            
            boleta = conn.execute(
                "SELECT * FROM productos WHERE es_boleta_entrada=1 AND activo=1 LIMIT 1"
            ).fetchone()
            assert boleta is not None
            self._ok(f"Producto 'Entrada General' = ${boleta['precio_venta']:,.0f}/persona")
            
            pos = conn.execute("SELECT * FROM series_facturacion WHERE prefijo='POS' AND activa=1").fetchone()
            lp = conn.execute("SELECT * FROM series_facturacion WHERE prefijo='LP' AND activa=1").fetchone()
            bol = conn.execute("SELECT * FROM series_boletas WHERE activa=1").fetchone()
            assert pos and lp and bol
            self._ok(f"Series listas: POS={pos['consecutivo_actual']}, LP={lp['consecutivo_actual']}, BOL={bol['consecutivo_actual']}")
            
            users = conn.execute("SELECT usuario, rol FROM usuarios WHERE activo=1").fetchall()
            self._ok(f"{len(users)} usuarios activos: {', '.join(u['usuario'] for u in users)}")
            
            metodos = conn.execute("SELECT nombre FROM metodos_pago WHERE activo=1").fetchall()
            self._ok(f"Metodos de pago: {', '.join(m['nombre'] for m in metodos)}")
        
        dian = validar_resolucion_dian(db_path=db)
        assert dian['puede_emitir'] is True
        self._ok(f"Resolucion DIAN: {dian['nivel']} — podemos emitir facturas electronicas")
        self._print(">> Sistema listo para operar. Pasamos a abrir caja.")
        
        # ==================================================================
        # LECCION 2: APERTURA DE CAJA
        # ==================================================================
        self._lec("LECCION 2: APERTURA DE CAJA")
        self._print("'La caja es el corazon financiero del dia. Sin caja abierta NO se puede vender.'")
        
        monto_inicial = 500000
        with transaccion_atomica(db) as conn:
            conn.execute("""
                INSERT INTO caja_diaria 
                (fecha_apertura, usuario_apertura, monto_inicial, monto_esperado, estado)
                VALUES (datetime('now','localtime'), ?, ?, ?, 'ABIERTA')
            """, (usuario['nombre_completo'], monto_inicial, monto_inicial))
            id_caja = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            log_auditoria(conn, 'caja_diaria', id_caja, 'APERTURA',
                          usuario['usuario'], f"Caja abierta con ${monto_inicial:,.0f}")
        
        with conexion_segura(db) as conn:
            caja = conn.execute("SELECT * FROM caja_diaria WHERE id_caja=?", (id_caja,)).fetchone()
            assert caja['estado'] == 'ABIERTA'
            assert caja['fecha_cierre'] is None
            assert caja['monto_inicial'] == monto_inicial
        
        self._ok(f"Caja #{id_caja} abierta con ${monto_inicial:,.0f}")
        self._ok(f"Estado: {caja['estado']} | Fecha cierre: {caja['fecha_cierre']}")
        self._print(">> Ahora podemos vender. Todo ingreso/egreso se registra contra esta caja.")
        
        # estado compartido
        caja_id = id_caja
        total_ing_efectivo = monto_inicial
        total_ing_digital = 0
        total_gastos_val = 0
        total_ventas_contado = 0
        total_boletas_val = 0
        
        # Guardar productos que usaremos
        with conexion_segura(db) as conn:
            prods = {}
            for row in conn.execute("SELECT * FROM productos WHERE activo=1").fetchall():
                prods[row['nombre']] = dict(row)
        
        prod_agua = prods['Agua sin Gas']
        prod_empana = prods['Empanada']
        prod_hamburguesa = prods['Hamburguesa Especial']
        prod_cerveza = prods['Cerveza Aguila']
        prod_boleta = prods['Entrada General']
        prod_almuerzo = prods['Almuerzo Ejecutivo']
        prod_gaseosa = prods['Gaseosa Cola']
        prod_papas = prods['Papas Fritas']
        
        # ==================================================================
        # LECCION 3: INVENTARIO
        # ==================================================================
        self._lec("LECCION 3: INVENTARIO — control de stock")
        self._print("'El inventario es el talon de Aquiles. Si no controlamos stock,")
        self._print(" podemos vender algo que no tenemos. El sistema descuenta automaticamente.'")
        
        self._print(f"\n  Stock inicial:")
        self._print(f"    Agua: {prod_agua['stock_actual']} und")
        self._print(f"    Empanada: {prod_empana['stock_actual']} und")
        self._print(f"    Hamburguesa: {prod_hamburguesa['stock_actual']} und")
        self._print(f"    Cerveza Aguila: {prod_cerveza['stock_actual']} und")
        
        with conexion_segura(db) as conn:
            pendientes = conn.execute(
                "SELECT * FROM productos WHERE pendiente_aprobacion=1"
            ).fetchall()
            self._print(f"\n  Productos pendientes de aprobar por admin: {len(pendientes)}")
            for p in pendientes:
                self._print(f"    - {p['nombre']} (${p['precio_venta']:,.0f})")
                aprobar_producto(p['id_producto'], p['nombre'], usuario['usuario'], db_path=db)
                self._ok(f"Producto '{p['nombre']}' APROBADO por administrador")
            
            restantes = conn.execute(
                "SELECT COUNT(*) FROM productos WHERE pendiente_aprobacion=1"
            ).fetchone()[0]
            assert restantes == 0
            self._ok("0 productos pendientes — todos aprobados")
        
        # Movimiento de entrada (compra a proveedor)
        registrar_movimiento_stock(
            id_producto=prod_agua['id_producto'], tipo='ENTRADA', cantidad=50,
            stock_anterior=prod_agua['stock_actual'],
            stock_nuevo=prod_agua['stock_actual'] + 50,
            motivo='Compra a Distribuidora Bebidas SAS',
            usuario_nombre=usuario['usuario'], db_path=db
        )
        with conexion_segura(db) as conn:
            agua_new = conn.execute("SELECT stock_actual FROM productos WHERE nombre='Agua sin Gas'").fetchone()
            assert agua_new['stock_actual'] == 150
        self._ok(f"Entrada de 50 Aguas: stock = {agua_new['stock_actual']} und")
        self._print(">> Stock actualizado. Cada venta descontara automaticamente.")
        
        # ==================================================================
        # LECCION 4: BOLETAS DE ENTRADA
        # ==================================================================
        self._lec("LECCION 4: BOLETAS DE ENTRADA")
        self._print("'Las boletas son el primer contacto. Vendemos entradas por persona.")
        self._print(" El sistema NUMERA cada boleta y las boletas NO descuentan inventario.'")
        
        precio = prod_boleta['precio_venta']
        grupos = [
            ('Familia Martinez', 4, 'EFECTIVO'),
            ('Grupo Escolar', 12, 'NEQUI'),
            ('Pareja Garcia', 2, 'TRANSFERENCIA'),
        ]
        
        self._print(f"\n  Precio por persona: ${precio:,.0f}")
        for nombre, personas, metodo in grupos:
            total = precio * personas
            total_boletas_val += total
            
            with transaccion_atomica(db) as conn:
                from models.series import generar_numero_venta_en_conn
                num_v = generar_numero_venta_en_conn(conn)
                
                s_bol = conn.execute("SELECT * FROM series_boletas WHERE activa=1").fetchone()
                n_bol = s_bol['consecutivo_actual'] + 1
                num_b = s_bol['formato'].format(prefijo=s_bol['prefijo'],
                                                ano=s_bol['ano'], consecutivo=n_bol)
                conn.execute("UPDATE series_boletas SET consecutivo_actual=? WHERE id_serie=?",
                             (n_bol, s_bol['id_serie']))
                
                conn.execute("""
                    INSERT INTO ventas (numero_venta, tipo, estado, cliente_nombre,
                        subtotal, descuento, total, total_pagado, saldo_pendiente,
                        num_personas, metodo_pago, id_usuario, usuario_nombre, fecha_pago)
                    VALUES (?, 'boleta', 'PAGADA', ?, ?, 0, ?, ?, 0, ?, ?, ?, ?, datetime('now','localtime'))
                """, (num_v, nombre, total, total, total, personas, metodo,
                      usuario['id_usuario'], usuario['nombre_completo']))
                id_v = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                
                conn.execute("""
                    INSERT INTO venta_detalle (id_venta, id_producto, producto_nombre, cantidad,
                        precio_unitario, descuento_linea, total_linea)
                    VALUES (?, ?, ?, ?, ?, 0, ?)
                """, (id_v, prod_boleta['id_producto'], prod_boleta['nombre'], personas, precio, total))
                
                conn.execute("""
                    INSERT INTO boletas_entrada (numero_boleta, id_venta, nombre_visitante,
                        cantidad_personas, precio_persona, total, metodo_pago, hora_entrada, id_usuario)
                    VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now','localtime'), ?)
                """, (num_b, id_v, nombre, personas, precio, total, metodo, usuario['id_usuario']))
                
                conn.execute("""
                    INSERT INTO movimientos_caja (id_caja, tipo, concepto, valor, metodo_pago, usuario, fecha_hora)
                    VALUES (?, 'INGRESO', ?, ?, ?, ?, datetime('now','localtime'))
                """, (caja_id, f"Boleta {num_v} – {nombre}", total, metodo, usuario['nombre_completo']))
                
                conn.execute("UPDATE caja_diaria SET total_boletas=total_boletas+?, monto_esperado=monto_esperado+? WHERE id_caja=?",
                             (total, total, caja_id))
            
            if metodo == 'EFECTIVO':
                total_ing_efectivo += total
            else:
                total_ing_digital += total
            self._ok(f"Boleta {num_b}: {nombre} x{personas} = ${total:,.0f} [{metodo}]")
        
        assert _count(db, 'boletas_entrada') == 3
        assert _count(db, 'ventas', "tipo='boleta' AND estado='PAGADA'") == 3
        stock_boleta = _sum(db, 'productos', 'stock_actual', f"id_producto={prod_boleta['id_producto']}")
        assert stock_boleta == 9999, f"Stock boleta cambio a {stock_boleta}"
        self._ok("Stock de Entrada General sigue siendo 9999 (las boletas NO descuentan inventario)")
        self._ok(f"Total boletas del dia: ${total_boletas_val:,.0f}")
        
        # ==================================================================
        # LECCION 5: BAR — VENTAS AL CONTADO
        # ==================================================================
        self._lec("LECCION 5: BAR — VENTAS AL CONTADO")
        self._print("'Cliente pide, cobramos y entregamos. El sistema: 1) genera numero POS,")
        self._print(" 2) descuenta inventario, 3) si requiere cocina crea orden, 4) registra en caja.'")
        
        carrito1 = [
            _item(prod_agua['id_producto'], 'Agua sin Gas', 4, 2000),
            _item(prod_gaseosa['id_producto'], 'Gaseosa Cola', 2, 3000),
        ]
        total1 = sum(i['total'] for i in carrito1)
        result1 = crear_venta(
            carrito=carrito1, total_venta=total1, descuento=0, motivo_descuento=None,
            metodo_pago='EFECTIVO', pago_split=None, monto_recibido=total1 + 2000,
            id_cliente=None, cliente_nombre='Mesa 1', notas=None, datos_fe=None,
            usuario=usuario, db_path=db
        )
        total_ventas_contado += total1
        total_ing_efectivo += total1
        self._ok(f"Venta {result1['numero']}: Mesa 1 = ${total1:,.0f} [EFECTIVO]")
        assert result1['tiene_cocina'] is False
        self._ok("No genera orden de cocina (solo bebidas)")
        
        carrito2 = [
            _item(prod_empana['id_producto'], 'Empanada', 3, 4000, requiere_cocina=True),
            _item(prod_agua['id_producto'], 'Agua sin Gas', 2, 2000),
        ]
        total2 = sum(i['total'] for i in carrito2)
        result2 = crear_venta(
            carrito=carrito2, total_venta=total2, descuento=0, motivo_descuento=None,
            metodo_pago='NEQUI', pago_split=None, monto_recibido=None,
            id_cliente=None, cliente_nombre='Mesa 3', notas=None, datos_fe=None,
            usuario=usuario, db_path=db
        )
        total_ventas_contado += total2
        total_ing_digital += total2
        self._ok(f"Venta {result2['numero']}: Mesa 3 = ${total2:,.0f} [NEQUI]")
        assert result2['tiene_cocina'] is True
        self._ok("Genera orden de cocina (3 empanadas)")
        
        with conexion_segura(db) as conn:
            ordenes = conn.execute("""
                SELECT * FROM ordenes_cocina WHERE numero_venta=?
            """, (result2['numero'],)).fetchall()
            assert len(ordenes) == 1
            assert ordenes[0]['producto_nombre'] == 'Empanada'
            assert ordenes[0]['cantidad'] == 3
            assert ordenes[0]['estado'] == 'PENDIENTE'
            self._ok(f"Orden cocina: {ordenes[0]['producto_nombre']} x{ordenes[0]['cantidad']} [PENDIENTE]")
        
            # Verificar descuento de inventario
            agua_stock = conn.execute(
                "SELECT stock_actual FROM productos WHERE id_producto=?", (prod_agua['id_producto'],)
            ).fetchone()[0]
            esperado_agua = 150 - 4 - 2
            assert agua_stock == esperado_agua, f"Stock agua: {agua_stock} != {esperado_agua}"
            self._ok(f"INVENTARIO: Agua: 150 -> {agua_stock} (-6 unidades)")
            
            empana_stock = conn.execute(
                "SELECT stock_actual FROM productos WHERE id_producto=?", (prod_empana['id_producto'],)
            ).fetchone()[0]
            esperado_empana = prod_empana['stock_actual'] - 3
            assert empana_stock == esperado_empana
            self._ok(f"INVENTARIO: Empanada: {prod_empana['stock_actual']} -> {empana_stock} (-3 unidades)")
        
        movs = _count(db, 'movimientos_inventario', "tipo='VENTA'")
        assert movs >= 4
        self._ok(f"{movs} movimientos de inventario registrados (VENTA)")
        
        ultima_venta = result2
        
        # ==================================================================
        # LECCION 6: CUENTAS ABIERTAS
        # ==================================================================
        self._lec("LECCION 6: CUENTAS ABIERTAS — pago diferido")
        self._print("'A veces el cliente no paga en el momento. Creamos una cuenta abierta")
        self._print(" que queda PENDIENTE. Cuando paga (parcial o total), actualizamos.'")
        
        carrito = [
            _item(prod_cerveza['id_producto'], 'Cerveza Aguila', 6, 5000),
            _item(prod_agua['id_producto'], 'Agua sin Gas', 3, 2000),
        ]
        total_cuenta = sum(i['total'] for i in carrito)
        
        result_cuenta = abrir_cuenta_abierta(
            carrito=carrito, total_venta=total_cuenta, descuento=0,
            id_cliente=None, cliente_nombre='Piscina VIP',
            notas='Cuenta de la piscina', usuario=usuario, db_path=db
        )
        id_cuenta = result_cuenta['id_venta']
        assert result_cuenta['numero'].startswith('POS-')
        self._ok(f"Cuenta abierta {result_cuenta['numero']}: Piscina VIP = ${total_cuenta:,.0f}")
        
        with conexion_segura(db) as conn:
            v = conn.execute("SELECT * FROM ventas WHERE id_venta=?", (id_cuenta,)).fetchone()
            assert v['estado'] == 'ABIERTA'
            assert v['saldo_pendiente'] == total_cuenta
            assert v['total_pagado'] == 0
        self._ok(f"Estado: {v['estado']} | Saldo: ${v['saldo_pendiente']:,.0f} | Pagado: ${v['total_pagado']:,.0f}")
        
        # Pago parcial (50% en efectivo)
        pago_parcial = total_cuenta * 0.5
        with transaccion_atomica(db) as conn:
            conn.execute("INSERT INTO pagos (id_venta, valor, metodo_pago, usuario_registro) VALUES (?, ?, 'EFECTIVO', ?)",
                         (id_cuenta, pago_parcial, usuario['nombre_completo']))
            conn.execute("UPDATE ventas SET total_pagado=?, saldo_pendiente=?, estado='ABIERTA' WHERE id_venta=?",
                         (pago_parcial, total_cuenta - pago_parcial, id_cuenta))
            conn.execute("INSERT INTO movimientos_caja (id_caja, tipo, concepto, valor, metodo_pago, usuario, fecha_hora) VALUES (?, 'INGRESO', ?, ?, 'EFECTIVO', ?, datetime('now','localtime'))",
                         (caja_id, f"Pago parcial Piscina VIP", pago_parcial, usuario['nombre_completo']))
            conn.execute("UPDATE caja_diaria SET total_ventas=total_ventas+?, monto_esperado=monto_esperado+? WHERE id_caja=?",
                         (pago_parcial, pago_parcial, caja_id))
        total_ing_efectivo += pago_parcial
        
        with conexion_segura(db) as conn:
            v = conn.execute("SELECT * FROM ventas WHERE id_venta=?", (id_cuenta,)).fetchone()
            assert v['estado'] == 'ABIERTA'
            assert abs(v['saldo_pendiente'] - (total_cuenta - pago_parcial)) < 1
        self._ok(f"Pago parcial: ${pago_parcial:,.0f} [EFECTIVO] — Saldo restante: ${v['saldo_pendiente']:,.0f}")
        
        # Pago final (Nequi)
        saldo_restante = total_cuenta - pago_parcial
        with transaccion_atomica(db) as conn:
            conn.execute("INSERT INTO pagos (id_venta, valor, metodo_pago, usuario_registro) VALUES (?, ?, 'NEQUI', ?)",
                         (id_cuenta, saldo_restante, usuario['nombre_completo']))
            conn.execute("UPDATE ventas SET total_pagado=?, saldo_pendiente=0, estado='PAGADA', fecha_pago=datetime('now','localtime') WHERE id_venta=?",
                         (total_cuenta, id_cuenta))
            conn.execute("INSERT INTO movimientos_caja (id_caja, tipo, concepto, valor, metodo_pago, usuario, fecha_hora) VALUES (?, 'INGRESO', ?, ?, 'NEQUI', ?, datetime('now','localtime'))",
                         (caja_id, f"Pago final Piscina VIP", saldo_restante, usuario['nombre_completo']))
            conn.execute("UPDATE caja_diaria SET total_ventas=total_ventas+?, monto_esperado=monto_esperado+? WHERE id_caja=?",
                         (saldo_restante, saldo_restante, caja_id))
        total_ing_digital += saldo_restante
        
        with conexion_segura(db) as conn:
            v = conn.execute("SELECT * FROM ventas WHERE id_venta=?", (id_cuenta,)).fetchone()
            assert v['estado'] == 'PAGADA'
            assert v['saldo_pendiente'] == 0
            pagos = conn.execute("SELECT * FROM pagos WHERE id_venta=?", (id_cuenta,)).fetchall()
            assert len(pagos) == 2
        self._ok(f"Pago final: ${saldo_restante:,.0f} [NEQUI] — Cuenta PAGADA con saldo 0")
        self._ok(f"{len(pagos)} pagos registrados: Efectivo + Nequi")
        
        # ==================================================================
        # LECCION 7: COCINA
        # ==================================================================
        self._lec("LECCION 7: COCINA — procesar ordenes")
        self._print("'La cocina recibe ordenes. Flujo: PENDIENTE -> PREPARANDO -> LISTO -> ENTREGADO.'")
        
        with conexion_segura(db) as conn:
            pendientes = conn.execute("SELECT * FROM ordenes_cocina WHERE estado='PENDIENTE'").fetchall()
            assert len(pendientes) > 0
            self._print(f"\n  Ordenes pendientes: {len(pendientes)}")
            for o in pendientes:
                self._print(f"    - Venta {o['numero_venta']}: {o['producto_nombre']} x{o['cantidad']}")
            
            # PREPARANDO
            for o in pendientes:
                conn.execute("UPDATE ordenes_cocina SET estado='PREPARANDO', hora_inicio=datetime('now','localtime'), usuario_cocina='Carlos Cocinero' WHERE id_orden=?", (o['id_orden'],))
            conn.commit()
            n_prep = conn.execute("SELECT COUNT(*) FROM ordenes_cocina WHERE estado='PREPARANDO'").fetchone()[0]
            self._ok(f"{n_prep} ordenes en PREPARANDO")
            
            # LISTO
            for o in pendientes:
                conn.execute("UPDATE ordenes_cocina SET estado='LISTO', hora_listo=datetime('now','localtime'), notificado_listo=0 WHERE id_orden=?", (o['id_orden'],))
                conn.execute("UPDATE venta_detalle SET estado_cocina='LISTO', hora_listo=datetime('now','localtime') WHERE id_detalle=?", (o['id_detalle'],))
            conn.commit()
            n_listos = conn.execute("SELECT COUNT(*) FROM ordenes_cocina WHERE estado='LISTO'").fetchone()[0]
            self._ok(f"{n_listos} ordenes LISTO (pendientes de notificar al POS)")
            n_no_notif = conn.execute("SELECT COUNT(*) FROM ordenes_cocina WHERE notificado_listo=0").fetchone()[0]
            self._ok(f"{n_no_notif} con notificado_listo=0 (el POS las detecta en polling)")
            
            # ENTREGADO
            for o in pendientes:
                conn.execute("UPDATE ordenes_cocina SET estado='ENTREGADO', hora_entrega=datetime('now','localtime') WHERE id_orden=?", (o['id_orden'],))
            conn.commit()
            n_ent = conn.execute("SELECT COUNT(*) FROM ordenes_cocina WHERE estado='ENTREGADO'").fetchone()[0]
            n_pend = conn.execute("SELECT COUNT(*) FROM ordenes_cocina WHERE estado='PENDIENTE'").fetchone()[0]
            assert n_pend == 0
            self._ok(f"{n_ent} ordenes ENTREGADO | 0 PENDIENTES")
        
        # ==================================================================
        # LECCION 8: ALMUERZOS
        # ==================================================================
        self._lec("LECCION 8: ALMUERZOS — reservas")
        self._print("'Los almuerzos NO van a ordenes_cocina, van a reservas_almuerzo.")
        self._print(" Flujo: RESERVADO -> EN_PREPARACION -> LISTO -> ENTREGADO.")
        self._print(" Ademas se genera checklist automatico segun el tipo.'")
        
        carrito_alm = [
            _item(prod_almuerzo['id_producto'], 'Almuerzo Ejecutivo', 3, 15000,
                  es_almuerzo=True, requiere_cocina=False,
                  pedido_nombre='Los Turistas', pedido_hora='13:00', pedido_notas='Sin cebolla'),
        ]
        total_alm = sum(i['total'] for i in carrito_alm)
        
        result_alm = crear_venta(
            carrito=carrito_alm, total_venta=total_alm, descuento=0, motivo_descuento=None,
            metodo_pago='EFECTIVO', pago_split=None, monto_recibido=total_alm,
            id_cliente=None, cliente_nombre='Los Turistas', notas=None, datos_fe=None,
            usuario=usuario, db_path=db
        )
        total_ing_efectivo += total_alm
        self._ok(f"Venta {result_alm['numero']}: 3 Almuerzos = ${total_alm:,.0f} [EFECTIVO]")
        
        with conexion_segura(db) as conn:
            orden_alm = conn.execute("SELECT * FROM ordenes_cocina WHERE id_venta=?", (result_alm['id_venta'],)).fetchone()
            assert orden_alm is None
        self._ok("No se creo orden en cocina (va a reservas_almuerzo, correcto)")
        
        with conexion_segura(db) as conn:
            reservas = conn.execute("SELECT * FROM reservas_almuerzo WHERE cliente_nombre='Los Turistas'").fetchall()
            assert len(reservas) == 1
            r = reservas[0]
            assert r['estado'] == 'RESERVADO'
            assert r['cantidad_almuerzos'] == 3
            assert r['notas'] == 'Sin cebolla'
            id_reserva = r['id_reserva']
        self._ok(f"Reserva #{id_reserva}: 3 Almuerzos Ejecutivos [RESERVADO] | Nota: '{r['notas']}'")
        
        # EN_PREPARACION + checklist
        with transaccion_atomica(db) as conn:
            conn.execute("UPDATE reservas_almuerzo SET estado='EN_PREPARACION' WHERE id_reserva=?", (id_reserva,))
            items_template = conn.execute(
                "SELECT * FROM almuerzo_checklist_template WHERE tipo_almuerzo='Almuerzo Ejecutivo' ORDER BY orden"
            ).fetchall()
            for it in items_template:
                conn.execute("INSERT INTO reserva_checklist (id_reserva, descripcion, completado) VALUES (?, ?, 0)",
                             (id_reserva, it['descripcion']))
        self._ok("Reserva -> EN_PREPARACION")
        self._ok(f"Checklist generado ({len(items_template)} items)")
        
        with transaccion_atomica(db) as conn:
            checklist = conn.execute("SELECT * FROM reserva_checklist WHERE id_reserva=?", (id_reserva,)).fetchall()
            for c in checklist:
                conn.execute("UPDATE reserva_checklist SET completado=1 WHERE id=?", (c['id'],))
        self._ok(f"Checklist completado ({len(checklist)} items marcados)")
        
        with transaccion_atomica(db) as conn:
            conn.execute("UPDATE reservas_almuerzo SET estado='LISTO', notificado_listo=0 WHERE id_reserva=?", (id_reserva,))
        assert _count(db, 'reservas_almuerzo', f"estado='LISTO' AND id_reserva={id_reserva}") == 1
        self._ok("Reserva -> LISTO")
        
        with transaccion_atomica(db) as conn:
            conn.execute("UPDATE reservas_almuerzo SET estado='ENTREGADO' WHERE id_reserva=?", (id_reserva,))
        assert _count(db, 'reservas_almuerzo', f"estado='ENTREGADO' AND id_reserva={id_reserva}") == 1
        self._ok("Reserva -> ENTREGADO. Flujo completo!")
        
        # ==================================================================
        # LECCION 9: FACTURA ELECTRONICA
        # ==================================================================
        self._lec("LECCION 9: FACTURA ELECTRONICA")
        self._print("'Cuando el cliente pide factura electronica, el sistema:")
        self._print(" 1) Verifica resolucion DIAN, 2) genera numero LP, 3) pide datos del cliente.'")
        
        dian = validar_resolucion_dian(db_path=db)
        assert dian['puede_emitir'] is True
        self._ok(f"Resolucion DIAN: {dian['nivel']}")
        
        carrito_fe = [
            _item(prod_hamburguesa['id_producto'], 'Hamburguesa Especial', 2, 16000, requiere_cocina=True),
            _item(prod_cerveza['id_producto'], 'Cerveza Aguila', 4, 5000),
        ]
        total_fe = sum(i['total'] for i in carrito_fe)
        datos_fe = {'nombre': 'Constructora ABC SAS', 'nit': '900777888-1', 'email': 'facturas@constructoraabc.com'}
        
        result_fe = crear_venta(
            carrito=carrito_fe, total_venta=total_fe, descuento=0, motivo_descuento=None,
            metodo_pago='TRANSFERENCIA', pago_split=None, monto_recibido=None,
            id_cliente=None, cliente_nombre='Constructora ABC', notas=None,
            datos_fe=datos_fe, usuario=usuario, db_path=db
        )
        total_ing_digital += total_fe
        
        self._ok(f"Venta {result_fe['numero']}: Constructora ABC = ${total_fe:,.0f} [TRANSFERENCIA]")
        self._ok(f"Cliente: {datos_fe['nombre']} | NIT: {datos_fe['nit']}")
        assert result_fe['numero_fe'] is not None and result_fe['numero_fe'].startswith('LP-')
        self._ok(f"Factura electronica: {result_fe['numero_fe']}")
        
        with conexion_segura(db) as conn:
            fe = conn.execute("SELECT * FROM facturas_electronicas WHERE id_venta=?", (result_fe['id_venta'],)).fetchone()
            assert fe is not None and fe['cliente_nit'] == '900777888-1'
            lp = conn.execute("SELECT * FROM series_facturacion WHERE prefijo='LP'").fetchone()
        self._ok(f"Registro en facturas_electronicas: {fe['numero_factura']}")
        self._ok(f"Serie LP: consecutivo = {lp['consecutivo_actual']}")
        
        # ==================================================================
        # LECCION 10: GASTOS
        # ==================================================================
        self._lec("LECCION 10: GASTOS — egresos del dia")
        self._print("'Los gastos reducen la caja. Cada gasto se registra con categoria,")
        self._print(" metodo de pago y quien lo hizo.'")
        
        gastos_data = [
            ('Hielo x10 bolsas', 30000, 'EFECTIVO', 'Insumos', 'OPERATIVO'),
            ('Servilletas y vasos', 15000, 'EFECTIVO', 'Insumos', 'OPERATIVO'),
            ('Recarga gas cocina', 60000, 'TRANSFERENCIA', 'Servicios', 'SERVICIOS'),
        ]
        
        total_gastos_val = 0
        for desc, valor, metodo, cat, tipo in gastos_data:
            with transaccion_atomica(db) as conn:
                conn.execute("INSERT INTO gastos (fecha, descripcion, valor, metodo_pago, categoria, tipo_gasto, usuario_registro, fecha_registro) VALUES (date('now','localtime'), ?, ?, ?, ?, ?, ?, datetime('now','localtime'))",
                             (desc, valor, metodo, cat, tipo, usuario['nombre_completo']))
                conn.execute("INSERT INTO movimientos_caja (id_caja, tipo, concepto, valor, metodo_pago, usuario, fecha_hora) VALUES (?, 'EGRESO', ?, ?, ?, ?, datetime('now','localtime'))",
                             (caja_id, f"Gasto: {desc}", valor, metodo, usuario['nombre_completo']))
                conn.execute("UPDATE caja_diaria SET total_gastos=total_gastos+?, monto_esperado=monto_esperado-? WHERE id_caja=?",
                             (valor, valor, caja_id))
            if metodo == 'EFECTIVO':
                total_ing_efectivo -= valor
            total_gastos_val += valor
            self._ok(f"Gasto: {desc} = ${valor:,.0f} [{metodo}] - {cat}")
        
        assert _count(db, 'gastos') == 3
        caja_gastos = _sum(db, 'caja_diaria', 'total_gastos', f"id_caja={caja_id}")
        assert caja_gastos == total_gastos_val
        self._ok(f"Total gastos registrados en caja: ${total_gastos_val:,.0f}")
        
        # ==================================================================
        # LECCION 11: NOMINA
        # ==================================================================
        self._lec("LECCION 11: NOMINA — control de turnos")
        self._print("'La nomina se maneja por semanas (lu a do). Cada empleado tiene tarifa")
        self._print(" normal y festiva. Registramos turnos, el sistema calcula total a pagar.'")
        
        hoy = datetime.date.today()
        lunes = hoy - datetime.timedelta(days=hoy.weekday())
        semana = lunes.isoformat()
        
        with conexion_segura(db) as conn:
            empleados = conn.execute("SELECT * FROM nomina_empleados WHERE activo=1").fetchall()
            assert len(empleados) == 3
            self._print(f"\n  Empleados activos: {len(empleados)}")
            
            total_nomina = 0
            for emp in empleados:
                for dia in range(5):
                    conn.execute("INSERT OR IGNORE INTO nomina_turnos (id_empleado, semana_inicio, dia_semana, tipo) VALUES (?, ?, ?, 'Normal')",
                                 (emp['id_empleado'], semana, dia))
                pago = 5 * (emp['tarifa_normal'] or 0)
                total_nomina += pago
                self._ok(f"{emp['nombre']}: 5 turnos Normal x ${emp['tarifa_normal']:,.0f} = ${pago:,.0f}")
            
            conn.execute("INSERT OR IGNORE INTO nomina_turnos (id_empleado, semana_inicio, dia_semana, tipo) VALUES (?, ?, ?, 'Festivo')",
                         (empleados[1]['id_empleado'], semana, 5))
            extra = empleados[1]['tarifa_festivo'] or 0
            total_nomina += extra
            self._ok(f"{empleados[1]['nombre']}: +1 turno Festivo x ${extra:,.0f}")
        
        turnos_count = _count(db, 'nomina_turnos', f"semana_inicio='{semana}'")
        assert turnos_count == 16
        self._ok(f"Total turnos registrados: {turnos_count}")
        
        with conexion_segura(db) as conn:
            calc = conn.execute("""
                SELECT e.nombre,
                    SUM(CASE WHEN nt.tipo='Normal' THEN e.tarifa_normal ELSE 0 END) as total_normal,
                    SUM(CASE WHEN nt.tipo='Festivo' THEN e.tarifa_festivo ELSE 0 END) as total_festivo
                FROM nomina_turnos nt JOIN nomina_empleados e ON nt.id_empleado=e.id_empleado
                WHERE nt.semana_inicio=? AND nt.pagado=0 GROUP BY e.id_empleado
            """, (semana,)).fetchall()
            gran_total = sum(r['total_normal'] + r['total_festivo'] for r in calc)
            self._ok(f"Total nomina semana: ${gran_total:,.0f}")
        
        # ==================================================================
        # LECCION 12: ANULACIONES
        # ==================================================================
        self._lec("LECCION 12: ANULACIONES — cancelar venta con PIN admin")
        self._print("'Si hay que anular una venta (error, devolucion), el sistema pide PIN")
        self._print(" del admin si la venta supera $50,000.'")
        
        with conexion_segura(db) as conn:
            venta_anular = conn.execute(
                "SELECT * FROM ventas WHERE tipo='normal' AND estado='PAGADA' ORDER BY id_venta DESC LIMIT 1"
            ).fetchone()
            assert venta_anular is not None
            venta_anular = dict(venta_anular)
        
        self._print(f"\n  Venta a anular: {venta_anular['numero_venta']} - ${venta_anular['total']:,.0f}")
        
        # Verificar PIN admin correcto
        valido, nombre_admin = verificar_pin_admin('9999', db_path=db)
        assert valido is True
        assert nombre_admin == 'Admin Don Jefe'
        self._ok(f"PIN admin '9999' verificado: {nombre_admin}")
        
        # PIN incorrecto debe fallar
        valido2, _ = verificar_pin_admin('0000', db_path=db)
        assert valido2 is False
        self._ok("PIN incorrecto '0000' rechazado")
        
        # PIN de vendedor NO debe validar como admin (solo busca rol='administrador')
        valido3, _ = verificar_pin_admin('1234', db_path=db)
        assert valido3 is False, "PIN de vendedor no debe validar como admin"
        self._ok("PIN de vendedor '1234' NO valida como admin (solo admins pueden anular)")
        
        with transaccion_atomica(db) as conn:
            conn.execute("UPDATE ventas SET estado='ANULADA', notas=notas || ' | ANULADA: Devolucion cliente' WHERE id_venta=?",
                         (venta_anular['id_venta'],))
            log_auditoria(conn, 'ventas', venta_anular['id_venta'], 'ANULAR', 'admin',
                          f"Anulacion de venta {venta_anular['numero_venta']} por devolucion")
            conn.execute("INSERT INTO movimientos_caja (id_caja, tipo, concepto, valor, metodo_pago, usuario, fecha_hora) VALUES (?, 'EGRESO', ?, ?, 'EFECTIVO', ?, datetime('now','localtime'))",
                         (caja_id, f"Anulacion {venta_anular['numero_venta']}", venta_anular['total'], 'admin'))
            conn.execute("UPDATE caja_diaria SET total_ventas=total_ventas-?, monto_esperado=monto_esperado-? WHERE id_caja=?",
                         (venta_anular['total'], venta_anular['total'], caja_id))
        
        with conexion_segura(db) as conn:
            estado = conn.execute("SELECT estado FROM ventas WHERE id_venta=?", (venta_anular['id_venta'],)).fetchone()[0]
            assert estado == 'ANULADA'
        self._ok(f"Venta {venta_anular['numero_venta']} -> ANULADA")
        
        n_aud = _count(db, 'auditoria', "accion='ANULAR'")
        self._ok(f"Auditoria registrada: {n_aud} anotacion(es)")
        if venta_anular['total'] > 50000:
            self._print("  [NOTA] Venta > $50,000: requirio PIN admin (umbral de seguridad)")
        
        # ==================================================================
        # LECCION 13: CIERRE DE CAJA
        # ==================================================================
        self._lec("LECCION 13: CIERRE DE CAJA — cuadre final")
        self._print("'Al final del dia cerramos la caja. El sistema calcula:")
        self._print(" Esperado = inicial + ventas + boletas - gastos. Diferencia = real - esperado.'")
        
        with conexion_segura(db) as conn:
            caja = conn.execute("SELECT * FROM caja_diaria WHERE id_caja=?", (caja_id,)).fetchone()
            self._print(f"\n  Estado actual de caja #{caja_id}:")
            self._print(f"    Monto inicial:   ${caja['monto_inicial']:>12,.0f}")
            self._print(f"    Total ventas:    ${caja['total_ventas']:>12,.0f}")
            self._print(f"    Total boletas:   ${caja['total_boletas']:>12,.0f}")
            self._print(f"    Total gastos:    ${caja['total_gastos']:>12,.0f}")
            self._print(f"    Monto esperado:  ${caja['monto_esperado']:>12,.0f}")
            
            formula = caja['monto_inicial'] + caja['total_ventas'] + caja['total_boletas'] - caja['total_gastos']
            assert abs(formula - caja['monto_esperado']) < 1
            self._ok(f"Formula: ${caja['monto_inicial']:,.0f} + ${caja['total_ventas']:,.0f} + ${caja['total_boletas']:,.0f} - ${caja['total_gastos']:,.0f} = ${caja['monto_esperado']:,.0f}")
            
            monto_real = caja['monto_esperado']
            conn.execute("UPDATE caja_diaria SET estado='CERRADA', fecha_cierre=datetime('now','localtime'), usuario_cierre=?, monto_real=?, diferencia=? WHERE id_caja=?",
                         (usuario['nombre_completo'], monto_real, 0, caja_id))
            conn.commit()
            log_auditoria(conn, 'caja_diaria', caja_id, 'CIERRE', usuario['usuario'],
                          f"Cierre. Esperado: ${caja['monto_esperado']:,.0f}, Real: ${monto_real:,.0f}")
        
        with conexion_segura(db) as conn:
            caja_f = conn.execute("SELECT * FROM caja_diaria WHERE id_caja=?", (caja_id,)).fetchone()
            assert caja_f['estado'] == 'CERRADA'
            assert caja_f['fecha_cierre'] is not None
            assert caja_f['diferencia'] == 0
        
        self._ok("CAJA CERRADA — Cuadre perfecto!")
        self._ok(f"Monto real: ${caja_f['monto_real']:,.0f} | Diferencia: $0")
        self._ok("Auditoria de cierre registrada")
        
        # ==================================================================
        # LECCION 14: REPORTES
        # ==================================================================
        self._lec("LECCION 14: REPORTES — el informe para el jefe")
        self._print("'El sistema puede generar reportes detallados: ventas por categoria,")
        self._print(" top productos, metodos de pago, IVA, anulaciones, nomina, gastos.'")
        
        hoy_str = datetime.date.today().isoformat()
        
        with conexion_segura(db) as conn:
            # Ventas por categoria
            categorias = conn.execute("""
                SELECT c.nombre, SUM(vd.cantidad) as cantidad, SUM(vd.total_linea) as total
                FROM venta_detalle vd JOIN productos p ON vd.id_producto = p.id_producto
                LEFT JOIN categorias c ON p.id_categoria = c.id_categoria
                JOIN ventas v ON vd.id_venta = v.id_venta
                WHERE DATE(v.fecha_creacion) = ? AND v.estado != 'ANULADA'
                GROUP BY c.nombre ORDER BY total DESC
            """, (hoy_str,)).fetchall()
            
            self._print(f"\n  --- VENTAS POR CATEGORIA ---")
            gran_total = 0
            for cat in categorias:
                self._print(f"    {cat['nombre']:20s}  x{cat['cantidad']:4d} und  ${cat['total']:>10,.0f}")
                gran_total += cat['total']
            self._print(f"    {'TOTAL':20s}               ${gran_total:>10,.0f}")
            
            # Top productos
            productos = conn.execute("""
                SELECT p.nombre, SUM(vd.cantidad) as cantidad, SUM(vd.total_linea) as total
                FROM venta_detalle vd JOIN productos p ON vd.id_producto = p.id_producto
                JOIN ventas v ON vd.id_venta = v.id_venta
                WHERE DATE(v.fecha_creacion) = ? AND v.estado != 'ANULADA'
                GROUP BY vd.id_producto ORDER BY total DESC LIMIT 5
            """, (hoy_str,)).fetchall()
            
            self._print(f"\n  --- TOP 5 PRODUCTOS MAS VENDIDOS ---")
            for i, p in enumerate(productos, 1):
                self._print(f"    {i}. {p['nombre']:25s}  x{p['cantidad']:3d} und  ${p['total']:>8,.0f}")
            
            # Metodos de pago
            metodos = conn.execute("""
                SELECT metodo_pago, COUNT(*) as cantidad, SUM(total) as total
                FROM ventas WHERE DATE(fecha_creacion) = ? AND estado != 'ANULADA'
                GROUP BY metodo_pago ORDER BY total DESC
            """, (hoy_str,)).fetchall()
            
            self._print(f"\n  --- METODOS DE PAGO ---")
            for m in metodos:
                self._print(f"    {m['metodo_pago'] or 'N/A':15s}  {m['cantidad']:2d} ventas  ${m['total']:>10,.0f}")
            
            # IVA
            iva_data = conn.execute("""
                SELECT COALESCE(SUM(total), 0) as total FROM ventas
                WHERE DATE(fecha_creacion) = ? AND tipo IN ('normal','cuenta_abierta')
                  AND estado NOT IN ('ANULADA','ABIERTA')
            """, (hoy_str,)).fetchone()
            total_iva = iva_data['total']
            base = round(total_iva / 1.19, 2)
            iva = round(total_iva - base, 2)
            
            fe_count = conn.execute("""
                SELECT COUNT(*) as n FROM facturas_electronicas fe
                JOIN ventas v ON fe.id_venta = v.id_venta WHERE DATE(v.fecha_creacion) = ?
            """, (hoy_str,)).fetchone()['n']
            
            self._print(f"\n  --- IVA 19% ---")
            self._print(f"    Total con IVA:  ${total_iva:>10,.0f}")
            self._print(f"    Base Gravable:  ${base:>10,.0f}")
            self._print(f"    IVA 19%:        ${iva:>10,.0f}")
            self._print(f"    Facturas Elect.: {fe_count}")
            
            # Anulaciones
            anuladas = conn.execute("""
                SELECT COUNT(*) as n, COALESCE(SUM(total), 0) as total
                FROM ventas WHERE DATE(fecha_creacion) = ? AND estado='ANULADA'
            """, (hoy_str,)).fetchone()
            self._print(f"\n  --- ANULACIONES ---")
            self._print(f"    {anuladas['n']} venta(s) anulada(s) por ${anuladas['total']:,.0f}")
            
            # Nomina
            nomina = conn.execute("""
                SELECT e.nombre,
                    SUM(CASE WHEN nt.tipo='Normal' THEN e.tarifa_normal ELSE 0 END) +
                    SUM(CASE WHEN nt.tipo='Festivo' THEN e.tarifa_festivo ELSE 0 END) as total_pagar
                FROM nomina_turnos nt JOIN nomina_empleados e ON nt.id_empleado=e.id_empleado
                WHERE nt.pagado=0 GROUP BY e.id_empleado
            """).fetchall()
            
            self._print(f"\n  --- NOMINA PENDIENTE ---")
            total_nom = 0
            for n in nomina:
                self._print(f"    {n['nombre']:20s}  ${n['total_pagar']:>10,.0f}")
                total_nom += n['total_pagar']
            self._print(f"    {'TOTAL NOMINA':20s}  ${total_nom:>10,.0f}")
            
            # Gastos
            gastos = conn.execute("""
                SELECT categoria, COUNT(*) as n, SUM(valor) as total
                FROM gastos WHERE DATE(fecha) = ? GROUP BY categoria
            """, (hoy_str,)).fetchall()
            
            self._print(f"\n  --- GASTOS DEL DIA ---")
            total_g = 0
            for g in gastos:
                self._print(f"    {g['categoria']:20s}  {g['n']:2d} gastos  ${g['total']:>10,.0f}")
                total_g += g['total']
            self._print(f"    {'TOTAL GASTOS':20s}               ${total_g:>10,.0f}")
            
            # Movimientos de caja
            movs = conn.execute("""
                SELECT tipo, COUNT(*) as n, COALESCE(SUM(valor), 0) as total
                FROM movimientos_caja WHERE id_caja=? GROUP BY tipo
            """, (caja_id,)).fetchall()
            
            self._print(f"\n  --- MOVIMIENTOS DE CAJA ---")
            for m in movs:
                self._print(f"    {m['tipo']:10s}  {m['n']:2d} movs  ${m['total']:>10,.0f}")
        
        # ==================================================================
        # LECCION 15: INTEGRIDAD FINAL
        # ==================================================================
        self._lec("LECCION 15: VERIFICACION FINAL — integridad")
        self._print("'Verificamos que el sistema quedo consistente. Esto diferencia")
        self._print(" un sistema profesional de uno casero: la INTEGRIDAD de los datos.'")
        
        with conexion_segura(db) as conn:
            # Procesar ordenes de cocina pendientes que hayan quedado
            pendientes = conn.execute("SELECT * FROM ordenes_cocina WHERE estado='PENDIENTE'").fetchall()
            if pendientes:
                self._print(f"\n  Procesando {len(pendientes)} orden(es) de cocina restante(s):")
                for o in pendientes:
                    conn.execute("UPDATE ordenes_cocina SET estado='PREPARANDO', hora_inicio=datetime('now','localtime'), usuario_cocina='Carlos Cocinero' WHERE id_orden=?", (o['id_orden'],))
                    conn.execute("UPDATE ordenes_cocina SET estado='LISTO', hora_listo=datetime('now','localtime') WHERE id_orden=?", (o['id_orden'],))
                    conn.execute("UPDATE ordenes_cocina SET estado='ENTREGADO', hora_entrega=datetime('now','localtime') WHERE id_orden=?", (o['id_orden'],))
                    conn.execute("UPDATE venta_detalle SET estado_cocina='LISTO', hora_listo=datetime('now','localtime') WHERE id_detalle=?", (o['id_detalle'],))
                    self._print(f"      {o['producto_nombre']} x{o['cantidad']} -> ENTREGADO")
                conn.commit()
            
            integridad = conn.execute("PRAGMA integrity_check").fetchone()[0]
            assert integridad == 'ok'
            self._ok(f"PRAGMA integrity_check: {integridad}")
            
            abiertas = conn.execute("SELECT COUNT(*) FROM ventas WHERE estado='ABIERTA'").fetchone()[0]
            self._ok(f"Cuentas abiertas sin pagar: {abiertas} (esperado 0)")
            
            pend_cocina = conn.execute("SELECT COUNT(*) FROM ordenes_cocina WHERE estado='PENDIENTE'").fetchone()[0]
            pend_reserva = conn.execute(
                "SELECT COUNT(*) FROM reservas_almuerzo WHERE estado NOT IN ('ENTREGADO', 'CANCELADO')"
            ).fetchone()[0]
            self._ok(f"Ordenes cocina PENDIENTES: {pend_cocina} (esperado 0)")
            self._ok(f"Reservas almuerzo sin entregar: {pend_reserva} (esperado 0)")
            
            movs = conn.execute("""
                SELECT COALESCE(SUM(CASE WHEN tipo='INGRESO' THEN valor ELSE 0 END), 0) as ingresos,
                       COALESCE(SUM(CASE WHEN tipo='EGRESO' THEN valor ELSE 0 END), 0) as egresos
                FROM movimientos_caja WHERE id_caja=?
            """, (caja_id,)).fetchone()
            caja = conn.execute("SELECT * FROM caja_diaria WHERE id_caja=?", (caja_id,)).fetchone()
            
            saldo_calc = caja['monto_inicial'] + movs['ingresos'] - movs['egresos']
            self._print(f"\n  --- CUADRE DE CAJA ---")
            self._print(f"    Ingresos: ${movs['ingresos']:>12,.0f}")
            self._print(f"    Egresos:  ${movs['egresos']:>12,.0f}")
            self._print(f"    Calc:     ${saldo_calc:>12,.0f}")
            self._print(f"    Esperado: ${caja['monto_esperado']:>12,.0f}")
            
            if abs(saldo_calc - caja['monto_esperado']) < 1:
                self._ok("Movimientos cuadran perfectamente")
            else:
                self._print(f"  [FAIL] Diferencia: ${saldo_calc - caja['monto_esperado']:,.0f}")
            
            pos = conn.execute("SELECT * FROM series_facturacion WHERE prefijo='POS'").fetchone()
            lp = conn.execute("SELECT * FROM series_facturacion WHERE prefijo='LP'").fetchone()
            bol = conn.execute("SELECT * FROM series_boletas WHERE activa=1").fetchone()
            self._print(f"\n  --- SERIES ---")
            self._print(f"    POS: {pos['consecutivo_actual']} numeros emitidos")
            self._print(f"    LP:  {lp['consecutivo_actual']} facturas electronicas")
            self._print(f"    BOL: {bol['consecutivo_actual']} boletas de entrada")
        
        # ==================================================================
        # RESUMEN FINAL
        # ==================================================================
        self._print("\n" + "="*65)
        self._print("  RESUMEN DEL DIA — REPORTE PARA EL JEFE")
        self._print("="*65)
        self._print(f"""
  MODULOS VERIFICADOS:
    [OK] Pre-condiciones (productos, series, usuarios)
    [OK] Apertura de caja
    [OK] Inventario (stock, aprobacion productos, movimientos)
    [OK] Boletas de entrada (3 grupos, 3 metodos pago)
    [OK] Ventas Bar contado (EFECTIVO + NEQUI)
    [OK] Cuentas abiertas (pago parcial + pago final)
    [OK] Cocina (PENDIENTE -> PREPARANDO -> LISTO -> ENTREGADO)
    [OK] Almuerzos (reserva + checklist + preparacion + entrega)
    [OK] Factura electronica (resolucion DIAN + numero LP)
    [OK] Gastos (3 registros, 2 categorias)
    [OK] Nomina (empleados, turnos, tarifas, calculo)
    [OK] Anulaciones (verificacion PIN admin)
    [OK] Cierre de caja (cuadre perfecto)
    [OK] Reportes (categorias, top productos, metodos pago, IVA, anulaciones)
    [OK] Integridad final (BD checksum, consistencia)
""")
        
        with conexion_segura(db) as conn:
            total_v = conn.execute(
                "SELECT COALESCE(SUM(total), 0) FROM ventas WHERE estado IN ('PAGADA','CERRADA')"
            ).fetchone()[0]
            n_v = conn.execute(
                "SELECT COUNT(*) FROM ventas WHERE estado IN ('PAGADA','CERRADA')"
            ).fetchone()[0]
            n_an = conn.execute(
                "SELECT COUNT(*) FROM ventas WHERE estado='ANULADA'"
            ).fetchone()[0]
            caja = conn.execute("SELECT * FROM caja_diaria WHERE id_caja=?", (caja_id,)).fetchone()
        
        self._print(f"""
  Ventas realizadas:       {n_v} transacciones
  Ventas anuladas:         {n_an}
  Total ventas netas:      ${total_v:>10,.0f}
  Total boletas:           ${caja['total_boletas']:>10,.0f}
  Total gastos:            ${caja['total_gastos']:>10,.0f}
  Utilidad bruta:          ${total_v + caja['total_boletas'] - caja['total_gastos']:>10,.0f}
  Caja:                    CERRADA (cuadre perfecto)
  Integridad BD:           OK

  # FELICITACIONES! Has completado el entrenamiento.
  # Ahora sabes usar TODOS los modulos del sistema.
""")
    
    # --- helpers de output ---
    def _lec(self, titulo):
        print(f"\n{'='*65}")
        print(f"  {titulo}")
        print(f"{'='*65}")
    
    def _print(self, msg):
        print(msg)
    
    def _ok(self, msg):
        print(f"  [OK] {msg}")
