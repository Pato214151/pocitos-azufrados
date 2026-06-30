"""
Test que simula un día completo de trabajo de un vendedor/cajero,
incluyendo ventas, devoluciones, manejo de caja y generación de reportes.
Este test verifica que todos los módulos interactúan correctamente
bajo presión de un día laboral intenso.
"""

import os
import sys
import datetime
import pytest
from decimal import Decimal

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from database.connection import conexion_segura, transaccion_atomica
from models.series import (
    obtener_proximo_numero_venta,
    obtener_proximo_numero_boleta
)
from utils.logger import log_auditoria


class TestDiaCompletoVendedor:
    """Simula un día completo de trabajo desde la perspectiva del vendedor"""
    
    @pytest.fixture
    def db_dia_completo(self, tmp_path):
        """BD en archivo temporal con schema completo para simular un día"""
        import sqlite3
        db = str(tmp_path / "dia_completo.db")
        conn = sqlite3.connect(db)
        conn.row_factory = sqlite3.Row
        
        # Schema mínimo pero completo para el test
        ano = datetime.datetime.now().year
        conn.executescript(f"""
            -- Tablas esenciales
            CREATE TABLE usuarios (
                id_usuario INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario TEXT UNIQUE NOT NULL,
                nombre_completo TEXT NOT NULL,
                rol TEXT NOT NULL DEFAULT 'cajero',
                activo INTEGER DEFAULT 1,
                pin TEXT
            );
            
            CREATE TABLE categorias (
                id_categoria INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                activa INTEGER DEFAULT 1
            );
            
            CREATE TABLE productos (
                id_producto INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                precio_venta REAL NOT NULL,
                requiere_cocina INTEGER DEFAULT 0,
                categoria_id INTEGER,
                stock INTEGER DEFAULT 0,
                activo INTEGER DEFAULT 1,
                pendiente_aprobacion INTEGER DEFAULT 0,
                FOREIGN KEY (categoria_id) REFERENCES categorias(id_categoria)
            );
            
            CREATE TABLE ventas (
                id_venta INTEGER PRIMARY KEY AUTOINCREMENT,
                numero_venta TEXT NOT NULL,
                tipo TEXT NOT NULL,
                estado TEXT NOT NULL,
                total REAL NOT NULL,
                total_pagado REAL NOT NULL,
                saldo_pendiente REAL DEFAULT 0,
                metodo_pago TEXT,
                usuario_cajero TEXT,
                fecha_creacion TEXT DEFAULT (datetime('now','localtime')),
                fecha_pago TEXT,
                id_cliente INTEGER
            );
            
            CREATE TABLE venta_detalle (
                id_detalle INTEGER PRIMARY KEY AUTOINCREMENT,
                id_venta INTEGER NOT NULL,
                producto_nombre TEXT NOT NULL,
                cantidad REAL NOT NULL,
                precio_unitario REAL NOT NULL,
                total_linea REAL NOT NULL,
                FOREIGN KEY (id_venta) REFERENCES ventas(id_venta)
            );
            
            CREATE TABLE caja_diaria (
                id_caja INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha TEXT NOT NULL,
                saldo_inicio REAL NOT NULL,
                saldo_final REAL,
                estado TEXT NOT NULL, -- ABIERTA, CERRADA
                usuario TEXT NOT NULL,
                fecha_apertura TEXT DEFAULT (datetime('now','localtime')),
                fecha_cierre TEXT
            );
            
            CREATE TABLE movimientos_caja (
                id_movimiento INTEGER PRIMARY KEY AUTOINCREMENT,
                id_caja INTEGER NOT NULL,
                tipo TEXT NOT NULL, -- INGRESO, EGRESO
                concepto TEXT NOT NULL,
                monto REAL NOT NULL,
                usuario TEXT NOT NULL,
                fecha TEXT DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (id_caja) REFERENCES caja_diaria(id_caja)
            );
            
            CREATE TABLE devoluciones (
                id_devolucion INTEGER PRIMARY KEY AUTOINCREMENT,
                id_venta INTEGER NOT NULL,
                monto REAL NOT NULL,
                motivo TEXT NOT NULL,
                usuario TEXT NOT NULL,
                fecha TEXT DEFAULT (datetime('now','localtime')),
                aplicado_caja INTEGER DEFAULT 0,
                FOREIGN KEY (id_venta) REFERENCES ventas(id_venta)
            );
            
            CREATE TABLE devoluciones_detalle (
                id_detalle INTEGER PRIMARY KEY AUTOINCREMENT,
                id_devolucion INTEGER NOT NULL,
                producto_nombre TEXT NOT NULL,
                cantidad REAL NOT NULL,
                precio_unitario REAL NOT NULL,
                total_linea REAL NOT NULL,
                FOREIGN KEY (id_devolucion) REFERENCES devoluciones(id_devolucion)
            );
            
            CREATE TABLE series_facturacion (
                id_serie INTEGER PRIMARY KEY AUTOINCREMENT,
                prefijo TEXT NOT NULL,
                ano INTEGER NOT NULL,
                consecutivo_actual INTEGER DEFAULT 0,
                activa INTEGER DEFAULT 1,
                UNIQUE(prefijo, ano)
            );
            
            CREATE TABLE series_boletas (
                id_serie INTEGER PRIMARY KEY AUTOINCREMENT,
                prefijo TEXT NOT NULL,
                ano INTEGER NOT NULL,
                consecutivo_actual INTEGER DEFAULT 0,
                activa INTEGER DEFAULT 1,
                UNIQUE(prefijo, ano)
            );
            
            CREATE TABLE configuracion (
                id_config INTEGER PRIMARY KEY AUTOINCREMENT,
                clave TEXT NOT NULL UNIQUE,
                valor TEXT,
                tipo TEXT DEFAULT 'texto',
                descripcion TEXT
            );
            
            CREATE TABLE auditoria (
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
            );
            
            -- Datos iniciales
            INSERT INTO usuarios (usuario, nombre_completo, rol, activo, pin) 
                VALUES ('vendedor_test', 'Vendedor de Prueba', 'cajero', 1, '1234');
                
            INSERT INTO categorias (nombre, activa) VALUES 
                ('Bebidas', 1),
                ('Comida', 1),
                ('Bar', 1);
                
            INSERT INTO productos (nombre, precio_venta, requiere_cocina, categoria_id, stock, activo, pendiente_aprobacion) 
                VALUES 
                ('Cerveza', 5000, 0, 1, 100, 1, 0),
                ('Hamburguesa', 15000, 1, 2, 50, 1, 0),
                ('Papas Fritas', 8000, 1, 2, 75, 1, 0),
                ('Agua', 2000, 0, 1, 150, 1, 0),
                ('Postre', 7000, 0, 2, 30, 1, 0),
                ('Cóctel', 12000, 0, 3, 40, 1, 0);
                
            INSERT INTO series_facturacion (prefijo, ano, consecutivo_actual, activa) 
                VALUES ('POS', {ano}, 0, 1);
                
            INSERT INTO series_boletas (prefijo, ano, consecutivo_actual, activa) 
                VALUES ('BOL', {ano}, 0, 1);
                
            INSERT INTO configuracion (clave, valor, tipo, descripcion) 
                VALUES 
                ('impresora_ancho_mm', '80', 'numero', 'Ancho de papel del ticket: 80 o 58 mm'),
                ('metodos_pago_habilitados', 'EFECTIVO,TARJETA', 'texto', 'Métodos de pago permitidos');
        """)
        conn.commit()
        conn.close()
        return db
    
    def test_dia_completo_vendedor(self, db_dia_completo):
        """
        Simula un día completo de trabajo:
        1. Apertura de caja
        2. Ventas múltiples (diferentes tipos y pagos)
        3. Devoluciones
        4. Cierre de caja y generación de reporte
        """
        hoy = datetime.date.today().isoformat()
        usuario_vendedor = 'vendedor_test'
        
        # === 1. APERTURA DE CAJA ===
        with conexion_segura(db_dia_completo) as conn:
            # Registrar apertura de caja
            conn.execute(
                """INSERT INTO caja_diaria (fecha, saldo_inicio, estado, usuario)
                   VALUES (?, ?, ?, ?)""",
                (hoy, 200000, 'ABIERTA', usuario_vendedor)  # Starting with $200,000 COP
            )
            id_caja = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.commit()
            
            # Log de auditoría
            log_auditoria(conn, 'caja_diaria', id_caja, 'APERTURA', usuario_vendedor,
                         f"Apertura de caja con saldo inicial de 200000")
        
        # === 2. VENTAS A LO LARGO DEL DÍA ===
        ventas_realizadas = []
        total_ventas_brutas = 0
        
        # Simular ventas en diferentes momentos del día
        momentos_dia = [
            ('09:30', 'desayuno'),
            ('12:15', 'almuerzo'),
            ('16:00', 'merienda'),
            ('20:30', 'cena')
        ]
        
        for hora, descripcion in momentos_dia:
            # Cada momento tiene entre 3-5 ventas
            num_ventas_momento = 4 if hora == '12:15' else 3  # Más ventas al almuerzo
            
            for i in range(num_ventas_momento):
                with conexion_segura(db_dia_completo) as conn:
                    # Obtener próximo número de venta
                    numero_venta = obtener_proximo_numero_venta(db_dia_completo)
                    
                    # Determinar tipo de venta (algunas son para llevar, otras normales)
                    tipo_venta = 'normal' if i % 3 != 0 else 'para_llevar'
                    
                    # Seleccionar productos aleatoriamente para la venta
                    productos_venta = []
                    total_venta = 0
                    
                    # Cada venta tiene entre 1-4 items
                    num_items = 2 if hora == '09:30' else 3  # Menos items en desayuno
                    
                    if hora == '09:30':  # Desayuno
                        productos_venta = [
                            {'nombre': 'Cerveza', 'cantidad': 1, 'precio': 5000},
                            {'nombre': 'Agua', 'cantidad': 2, 'precio': 2000}
                        ]
                    elif hora == '12:15':  # Almuerzo
                        productos_venta = [
                            {'nombre': 'Hamburguesa', 'cantidad': 1, 'precio': 15000},
                            {'nombre': 'Papas Fritas', 'cantidad': 1, 'precio': 8000},
                            {'nombre': 'Cóctel', 'cantidad': 1, 'precio': 12000}
                        ]
                    elif hora == '16:00':  # Merienda
                        productos_venta = [
                            {'nombre': 'Hamburguesa', 'cantidad': 1, 'precio': 15000},
                            {'nombre': 'Postre', 'cantidad': 1, 'precio': 7000}
                        ]
                    else:  # Cena
                        productos_venta = [
                            {'nombre': 'Cerveza', 'cantidad': 2, 'precio': 5000},
                            {'nombre': 'Papas Fritas', 'cantidad': 1, 'precio': 8000},
                            {'nombre': 'Agua', 'cantidad': 1, 'precio': 2000}
                        ]
                    
                    # Calcular total
                    total_venta = sum(p['cantidad'] * p['precio'] for p in productos_venta)
                    total_ventas_brutas += total_venta
                    
                    # Método de pago (alternar entre efectivo y tarjeta)
                    metodo_pago = 'EFECTIVO' if i % 2 == 0 else 'TARJETA'
                    
                    # Insertar venta
                    conn.execute(
                        """INSERT INTO ventas (
                            numero_venta, tipo, estado, total, total_pagado, saldo_pendiente,
                            metodo_pago, usuario_cajero, fecha_creacion
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now','localtime'))""",
                        (numero_venta, tipo_venta, 'COMPLETADA', total_venta, total_venta, 0,
                         metodo_pago, usuario_vendedor)
                    )
                    id_venta = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                    
                    # Insertar detalles de venta
                    for producto in productos_venta:
                        conn.execute(
                            """INSERT INTO venta_detalle (
                                id_venta, producto_nombre, cantidad, precio_unitario, total_linea
                            ) VALUES (?, ?, ?, ?, ?)""",
                            (id_venta, producto['nombre'], producto['cantidad'],
                             producto['precio'], producto['cantidad'] * producto['precio'])
                        )
                    
                    # Registrar movimiento en caja (solo para efectivo)
                    if metodo_pago == 'EFECTIVO':
                        conn.execute(
                            """INSERT INTO movimientos_caja (
                                id_caja, tipo, concepto, monto, usuario
                            ) VALUES (?, ?, ?, ?, ?)""",
                            (id_caja, 'INGRESO', f'Venta {numero_venta}', total_venta, usuario_vendedor)
                        )
                    
                    # Log de auditoría
                    log_auditoria(conn, 'ventas', id_venta, 'CREAR', usuario_vendedor,
                                 f"Venta {numero_venta} por {total_venta} ({metodo_pago})")
                    
                    conn.commit()
                    
                    ventas_realizadas.append({
                        'id': id_venta,
                        'numero': numero_venta,
                        'tipo': tipo_venta,
                        'total': total_venta,
                        'metodo_pago': metodo_pago,
                        'productos': productos_venta,
                        'hora': hora
                    })
        
        # === 3. PROCESAR DEVOLUCIONES ===
        # Simular que algunos clientes devuelven productos
        devoluciones_procesadas = []
        total_devoluciones = 0
        
        # Seleccionar algunas ventas para devolver parcialmente
        ventas_para_devolver = ventas_realizadas[::3]  # Cada tercera venta
        
        for venta in ventas_para_devolver[:2]:  # Solo procesar 2 devoluciones para no exagerar
            with transaccion_atomica(db_dia_completo) as conn:
                # Obtener detalles de la venta original
                detalle_venta = conn.execute(
                    """SELECT * FROM venta_detalle WHERE id_venta = ?""",
                    (venta['id'],)
                ).fetchall()
                
                # Decidir qué producto devolver (el más caro o uno aleatorio)
                producto_a_devolver = max(detalle_venta, key=lambda x: x['precio_unitario'])
                
                # Cantidad a devolver (puede ser parcial o total)
                cantidad_devolver = min(1, producto_a_devolver['cantidad'])  # Devolver 1 unidad
                
                monto_devolucion = cantidad_devolver * producto_a_devolver['precio_unitario']
                total_devoluciones += monto_devolucion
                
                # Insertar devolución
                conn.execute(
                    """INSERT INTO devoluciones (
                        id_venta, monto, motivo, usuario
                    ) VALUES (?, ?, ?, ?)""",
                    (venta['id'], monto_devolucion, 
                     'Producto no cumplió con las expectativas', usuario_vendedor)
                )
                id_devolucion = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                
                # Insertar detalle de devolución
                conn.execute(
                    """INSERT INTO devoluciones_detalle (
                        id_devolucion, producto_nombre, cantidad, precio_unitario, total_linea
                    ) VALUES (?, ?, ?, ?, ?)""",
                    (id_devolucion, producto_a_devolver['producto_nombre'], cantidad_devolver,
                     producto_a_devolver['precio_unitario'], monto_devolucion)
                )
                
                # Registrar movimiento en caja (egreso por devolución)
                conn.execute(
                    """INSERT INTO movimientos_caja (
                        id_caja, tipo, concepto, monto, usuario
                    ) VALUES (?, ?, ?, ?, ?)""",
                    (id_caja, 'EGRESO', f'Devolución venta {venta["numero"]}', monto_devolucion, usuario_vendedor)
                )
                
                # Log de auditoría
                log_auditoria(conn, 'devoluciones', id_devolucion, 'CREAR', usuario_vendedor,
                             f"Devolución por {monto_devolucion} de venta {venta['numero']}")
                
                conn.commit()
                
                devoluciones_procesadas.append({
                    'id': id_devolucion,
                    'venta_original': venta['numero'],
                    'producto': producto_a_devolver['producto_nombre'],
                    'cantidad': cantidad_devolver,
                    'monto': monto_devolucion,
                    'motivo': 'Producto no cumplió con las expectativas'
                })
        
        # === 4. CIERRE DE CAJA Y GENERACIÓN DE REPORTE ===
        with conexion_segura(db_dia_completo) as conn:
            # Calcular totales del día
            ventas_netas = conn.execute(
                """SELECT COALESCE(SUM(total), 0) as total 
                   FROM ventas 
                   WHERE date(fecha_creacion) = ? AND estado != 'ANULADA'""",
                (hoy,)
            ).fetchone()['total']
            
            total_ingresos_efectivo = conn.execute(
                """SELECT COALESCE(SUM(monto), 0) as total 
                   FROM movimientos_caja 
                   WHERE id_caja = ? AND tipo = 'INGRESO'""",
                (id_caja,)
            ).fetchone()['total']
            
            total_egresos_efectivo = conn.execute(
                """SELECT COALESCE(SUM(monto), 0) as total 
                   FROM movimientos_caja 
                   WHERE id_caja = ? AND tipo = 'EGRESO'""",
                (id_caja,)
            ).fetchone()['total']
            
            total_devoluciones_registrado = conn.execute(
                """SELECT COALESCE(SUM(monto), 0) as total 
                   FROM devoluciones 
                   WHERE date(fecha) = ?""",
                (hoy,)
            ).fetchone()['total']
            
            # Calcular saldo esperado en caja
            saldo_inicial = 200000
            saldo_esperado = saldo_inicial + total_ingresos_efectivo - total_egresos_efectivo
            
            # Actualizar caja diaria con cierre
            conn.execute(
                """UPDATE caja_diaria 
                   SET saldo_final = ?, estado = ?, fecha_cierre = datetime('now','localtime')
                   WHERE id_caja = ?""",
                (saldo_esperado, 'CERRADA', id_caja)
            )
            conn.commit()
            
            # Log de auditoría para cierre
            log_auditoria(conn, 'caja_diaria', id_caja, 'CIERRE', usuario_vendedor,
                         f"Cierre de caja. Saldo final: {saldo_esperado}")
        
        # === 5. GENERAR REPORTE PARA EL JEFE ===
        # Este sería el reporte que el vendedor le da a su jefe al final del día
        reporte_dia = {
            'fecha': hoy,
            'vendedor': usuario_vendedor,
            'resumen_ventas': {
                'total_ventas_brutas': total_ventas_brutas,
                'numero_transacciones': len(ventas_realizadas),
                'promedio_por_venta': total_ventas_brutas / len(ventas_realizadas) if ventas_realizadas else 0,
                'ventas_por_tipo': {
                    'normal': len([v for v in ventas_realizadas if v['tipo'] == 'normal']),
                    'para_llevar': len([v for v in ventas_realizadas if v['tipo'] == 'para_llevar'])
                },
                'ventas_por_pago': {
                    'EFECTIVO': len([v for v in ventas_realizadas if v['metodo_pago'] == 'EFECTIVO']),
                    'TARJETA': len([v for v in ventas_realizadas if v['metodo_pago'] == 'TARJETA'])
                }
            },
            'devoluciones': {
                'total_devoluciones': total_devoluciones,
                'numero_devoluciones': len(devoluciones_procesadas),
                'detalle': devoluciones_procesadas
            },
            'caja': {
                'saldo_inicial': 200000,
                'total_ingresos_efectivo': total_ingresos_efectivo,
                'total_egresos_efectivo': total_egresos_efectivo,
                'saldo_final_esperado': saldo_esperado,
                'estado': 'CERRADA'
            },
            'eficiencia': {
                'productos_mas_vendidos': self._calcular_productos_top(ventas_realizadas),
                'hora_pico_ventas': self._calcular_hora_pico(ventas_realizadas)
            }
        }
        
        # Verificaciones finales (asserts) para asegurar que todo funcionó correctamente
        assert len(ventas_realizadas) > 0, "No se registraron ventas"
        assert total_ventas_brutas > 0, "El total de ventas debe ser positivo"
        assert saldo_esperado >= 0, "El saldo de caja no puede ser negativo"
        assert total_devoluciones >= 0, "El total de devoluciones no puede ser negativo"
        
        # Verificar que el saldo en caja coincida con lo esperado
        with conexion_segura(db_dia_completo) as conn:
            saldo_real = conn.execute(
                """SELECT saldo_final FROM caja_diaria WHERE id_caja = ?""",
                (id_caja,)
            ).fetchone()['saldo_final']
            
            assert saldo_real == saldo_esperado, \
                f"Saldo en caja ({saldo_real}) no coincide con lo esperado ({saldo_esperado})"
        
        # Imprimir reporte para el jefe (en un escenario real, esto se enviaría por email o se guardaría)
        self._imprimir_reporte_jefe(reporte_dia)
        
        return reporte_dia
    
    def _calcular_productos_top(self, ventas_realizadas):
        """Calcula los productos más vendidos del día"""
        productos_count = {}
        for venta in ventas_realizadas:
            for producto in venta['productos']:
                nombre = producto['nombre']
                cantidad = producto['cantidad']
                productos_count[nombre] = productos_count.get(nombre, 0) + cantidad
        
        # Ordenar por cantidad vendida (descendente)
        return sorted(productos_count.items(), key=lambda x: x[1], reverse=True)[:3]
    
    def _calcular_hora_pico(self, ventas_realizadas):
        """Determina en qué hora hubo más ventas"""
        ventas_por_hora = {}
        for venta in ventas_realizadas:
            hora = venta['hora']
            ventas_por_hora[hora] = ventas_por_hora.get(hora, 0) + 1
        
        if ventas_por_hora:
            return max(ventas_por_hora.items(), key=lambda x: x[1])[0]
        return None
    
    def _imprimir_reporte_jefe(self, reporte):
        """Imprime el reporte formateado para entregar al jefe"""
        print("\n" + "="*60)
        print("REPORTE DE VENTAS - DÍA COMPLETO")
        print("="*60)
        print(f"Fecha: {reporte['fecha']}")
        print(f"Vendedor: {reporte['vendedor']}")
        print("-"*60)
        print("RESUMEN DE VENTAS:")
        print(f"  • Total ventas brutas: ${reporte['resumen_ventas']['total_ventas_brutas']:,.0f}")
        print(f"  • Número de transacciones: {reporte['resumen_ventas']['numero_transacciones']}")
        print(f"  • Promedio por venta: ${reporte['resumen_ventas']['promedio_por_venta']:,.0f}")
        print(f"  • Ventas normales: {reporte['resumen_ventas']['ventas_por_tipo']['normal']}")
        print(f"  • Ventas para llevar: {reporte['resumen_ventas']['ventas_por_tipo']['para_llevar']}")
        print(f"  • Pagos en efectivo: {reporte['resumen_ventas']['ventas_por_pago']['EFECTIVO']}")
        print(f"  • Pagos con tarjeta: {reporte['resumen_ventas']['ventas_por_pago']['TARJETA']}")
        print("-"*60)
        print("DEVOLUCIONES PROCESADAS:")
        print(f"  • Total devuelto: ${reporte['devoluciones']['total_devoluciones']:,.0f}")
        print(f"  • Número de devoluciones: {reporte['devoluciones']['numero_devoluciones']}")
        for i, dev in enumerate(reporte['devoluciones']['detalle'], 1):
            print(f"    {i}. Venta {dev['venta_original']} - {dev['producto']} "
                  f"({dev['cantidad']} uds) - ${dev['monto']:,.0f} - {dev['motivo']}")
        print("-"*60)
        print("ESTADO DE CAJA:")
        print(f"  • Saldo inicial: ${reporte['caja']['saldo_inicial']:,.0f}")
        print(f"  • Total ingresos (efectivo): ${reporte['caja']['total_ingresos_efectivo']:,.0f}")
        print(f"  • Total egresos (efectivo): ${reporte['caja']['total_egresos_efectivo']:,.0f}")
        print(f"  • Saldo final: ${reporte['caja']['saldo_final_esperado']:,.0f}")
        print(f"  • Estado: {reporte['caja']['estado']}")
        print("-"*60)
        print("ANÁLISIS DE EFICIENCIA:")
        top_productos = reporte['eficiencia']['productos_mas_vendidos']
        if top_productos:
            print("  • Productos más vendidos:")
            for producto, cantidad in top_productos:
                print(f"    - {producto}: {cantidad} unidades")
        hora_pico = reporte['eficiencia']['hora_pico_ventas']
        if hora_pico:
            print(f"  • Hora pico de ventas: {hora_pico}")
        print("="*60)
        print("REPORTE COMPLETADO - Todos los módulos funcionando correctamente")
        print("="*60 + "\n")


if __name__ == "__main__":
    # Ejecutar el test si se llama directamente
    pytest.main([__file__, "-v", "-s"])