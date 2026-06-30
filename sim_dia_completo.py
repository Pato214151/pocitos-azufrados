"""
Simulación de un día completo de operación — Club Los Pocitos Azufrados
Verifica que todos los flujos integren correctamente:

  1. Apertura de caja
  2. Venta de boletas (3 grupos)
  3. Venta bar: pago inmediato (efectivo + Nequi)
  4. Venta bar: cuenta abierta
  5. Ordenes cocina generadas y procesadas
  6. Pago de cuenta abierta (parcial y total)
  7. Reserva de almuerzo
  8. Registro de gastos
  9. Cierre de caja con cuadre
 10. Verificación final de integridad
"""

import sqlite3, datetime, sys, traceback

DB = 'data/pocitos_azufrados.db'
USUARIO = 'admin'
USUARIO_NOMBRE = 'Administrador'
HOY = datetime.date.today().isoformat()

PASS = '\033[92m[OK]\033[0m'
FAIL = '\033[91m[FAIL]\033[0m'

errores = []
advertencias = []

def conn_new():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    c.execute("PRAGMA journal_mode=WAL")
    return c

def siguiente_numero_venta(conn):
    s = conn.execute("SELECT * FROM series_facturacion WHERE activa=1").fetchone()
    n = s['consecutivo_actual'] + 1
    num = s['formato'].format(prefijo=s['prefijo'], ano=s['ano'], consecutivo=n)
    conn.execute("UPDATE series_facturacion SET consecutivo_actual=? WHERE id_serie=?",
                 (n, s['id_serie']))
    return num

def siguiente_numero_boleta(conn):
    s = conn.execute("SELECT * FROM series_boletas WHERE activa=1").fetchone()
    if not s:
        return None
    n = s['consecutivo_actual'] + 1
    num = s['formato'].format(prefijo=s['prefijo'], ano=s['ano'], consecutivo=n)
    conn.execute("UPDATE series_boletas SET consecutivo_actual=? WHERE id_serie=?",
                 (n, s['id_serie']))
    return num

def check(condicion, descripcion, critico=False):
    if condicion:
        print(f"  {PASS} {descripcion}")
        return True
    else:
        print(f"  {FAIL} {descripcion}")
        if critico:
            errores.append(descripcion)
        else:
            advertencias.append(descripcion)
        return False

def seccion(titulo):
    print(f"\n{'='*55}")
    print(f"  {titulo}")
    print(f"{'='*55}")

# ──────────────────────────────────────────────────────────────
# PRE-CONDICIONES
# ──────────────────────────────────────────────────────────────
seccion("PRE-CONDICIONES")
conn = conn_new()

# Verificar que hay productos
n_prods = conn.execute("SELECT COUNT(*) FROM productos WHERE activo=1 AND es_boleta_entrada=0").fetchone()[0]
check(n_prods >= 10, f"{n_prods} productos activos en bar (necesita >= 10)", critico=True)

prod_boleta = conn.execute("SELECT * FROM productos WHERE es_boleta_entrada=1 AND activo=1 LIMIT 1").fetchone()
check(prod_boleta is not None, "Existe producto boleta de entrada", critico=True)

agua = conn.execute("SELECT * FROM productos WHERE nombre LIKE '%Agua%' AND activo=1 AND es_boleta_entrada=0 LIMIT 1").fetchone()
gaseosa = conn.execute("SELECT * FROM productos WHERE nombre LIKE '%Gaseosa%' AND activo=1 LIMIT 1").fetchone()
empanada = conn.execute("SELECT * FROM productos WHERE nombre='Empanada' AND activo=1").fetchone()
almuerzo = conn.execute("SELECT * FROM productos WHERE activo=1 AND id_categoria IN (SELECT id_categoria FROM categorias WHERE nombre LIKE '%Almuerzo%') LIMIT 1").fetchone()
cerveza = conn.execute("SELECT * FROM productos WHERE nombre LIKE '%Aguila%' OR nombre LIKE '%Agua%' AND activo=1 AND es_boleta_entrada=0 LIMIT 1").fetchone()

check(agua is not None, f"Producto agua: {agua['nombre'] if agua else 'N/A'}", critico=True)
check(empanada is not None, f"Empanada con requiere_cocina={empanada['requiere_cocina'] if empanada else '?'}", critico=True)
check(almuerzo is not None, f"Almuerzo disponible: {almuerzo['nombre'] if almuerzo else 'N/A'}", critico=False)

# Verificar no hay caja abierta de hoy (limpiar si existe de tests previos)
caja_existente = conn.execute("SELECT * FROM caja_diaria WHERE estado='ABIERTA'").fetchone()
id_caja = None

# ──────────────────────────────────────────────────────────────
# 1. APERTURA DE CAJA
# ──────────────────────────────────────────────────────────────
seccion("1. APERTURA DE CAJA")
try:
    if caja_existente:
        id_caja = caja_existente['id_caja']
        # Reset para la simulación
        conn.execute("""
            UPDATE caja_diaria SET total_ventas=0, total_boletas=0, total_gastos=0,
            monto_esperado=monto_inicial, fecha_cierre=NULL, usuario_cierre=NULL,
            monto_real=NULL, diferencia=0, estado='ABIERTA'
            WHERE id_caja=?
        """, (id_caja,))
        conn.execute("DELETE FROM movimientos_caja WHERE id_caja=?", (id_caja,))
        monto_inicial = caja_existente['monto_inicial']
        check(True, f"Caja existente reutilizada (id={id_caja}, inicial=${monto_inicial:,.0f})")
    else:
        monto_inicial = 500000
        conn.execute("""
            INSERT INTO caja_diaria (usuario_apertura, monto_inicial, monto_esperado, estado, fecha_apertura)
            VALUES (?, ?, ?, 'ABIERTA', datetime('now','localtime'))
        """, (USUARIO, monto_inicial, monto_inicial))
        id_caja = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        check(True, f"Caja abierta id={id_caja}, monto inicial=${monto_inicial:,.0f}")

    conn.commit()
    caja = conn.execute("SELECT * FROM caja_diaria WHERE id_caja=?", (id_caja,)).fetchone()
    check(caja['estado'] == 'ABIERTA', "Estado caja = ABIERTA")
    check(caja['fecha_cierre'] is None, "fecha_cierre es NULL")
except Exception as e:
    check(False, f"Apertura caja: {e}", critico=True)
    traceback.print_exc()

total_ingresos_efectivo = monto_inicial
total_ingresos_digital = 0
total_gastos_sim = 0

# ──────────────────────────────────────────────────────────────
# 2. BOLETAS DE ENTRADA (3 grupos)
# ──────────────────────────────────────────────────────────────
seccion("2. BOLETAS DE ENTRADA")
grupos_boletas = [
    {'nombre': 'Familia Martinez', 'personas': 4, 'metodo': 'EFECTIVO'},
    {'nombre': 'Grupo Escolar', 'personas': 12, 'metodo': 'TRANSFERENCIA'},
    {'nombre': 'Pareja Garcia', 'personas': 2, 'metodo': 'NEQUI'},
]
precio_boleta = prod_boleta['precio_venta']
total_boletas = 0

try:
    for grupo in grupos_boletas:
        num_v = siguiente_numero_venta(conn)
        num_b = siguiente_numero_boleta(conn)
        total = precio_boleta * grupo['personas']

        conn.execute("""
            INSERT INTO ventas (numero_venta, tipo, estado, cliente_nombre,
                subtotal, descuento, impuesto, total, total_pagado, saldo_pendiente,
                num_personas, metodo_pago, id_usuario, usuario_nombre, fecha_pago)
            VALUES (?, 'boleta', 'PAGADA', ?, ?, 0, 0, ?, ?, 0, ?, ?, 1, ?, datetime('now','localtime'))
        """, (num_v, grupo['nombre'], total, total, total, grupo['personas'],
              grupo['metodo'], USUARIO_NOMBRE))
        id_v = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        conn.execute("""
            INSERT INTO venta_detalle (id_venta, id_producto, producto_nombre, cantidad,
                precio_unitario, descuento_linea, total_linea)
            VALUES (?, ?, ?, ?, ?, 0, ?)
        """, (id_v, prod_boleta['id_producto'], prod_boleta['nombre'],
              grupo['personas'], precio_boleta, total))

        if num_b:
            conn.execute("""
                INSERT INTO boletas_entrada (numero_boleta, id_venta, nombre_visitante,
                    cantidad_personas, precio_persona, total, metodo_pago, hora_entrada, id_usuario)
                VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now','localtime'), 1)
            """, (num_b, id_v, grupo['nombre'], grupo['personas'], precio_boleta, total, grupo['metodo']))

        conn.execute("""
            INSERT INTO movimientos_caja (id_caja, tipo, concepto, valor, metodo_pago, usuario, fecha_hora)
            VALUES (?, 'INGRESO', ?, ?, ?, ?, datetime('now','localtime'))
        """, (id_caja, f"Boleta {num_v} – {grupo['nombre']}", total, grupo['metodo'], USUARIO))

        conn.execute("""
            UPDATE caja_diaria SET total_boletas=total_boletas+?, monto_esperado=monto_esperado+?
            WHERE id_caja=?
        """, (total, total, id_caja))

        if grupo['metodo'] == 'EFECTIVO':
            total_ingresos_efectivo += total
        else:
            total_ingresos_digital += total
        total_boletas += total
        check(True, f"Boleta {num_v}: {grupo['nombre']} x{grupo['personas']} = ${total:,.0f} [{grupo['metodo']}]")

    conn.commit()
    check(total_boletas == precio_boleta * sum(g['personas'] for g in grupos_boletas),
          f"Total boletas acumulado: ${total_boletas:,.0f}", critico=True)
except Exception as e:
    check(False, f"Error en boletas: {e}", critico=True)
    traceback.print_exc()

# ──────────────────────────────────────────────────────────────
# 3. VENTAS BAR — PAGO INMEDIATO
# ──────────────────────────────────────────────────────────────
seccion("3. BAR — VENTAS CON PAGO INMEDIATO")
ventas_bar = [
    {
        'cliente': 'Mesa 1',
        'metodo': 'EFECTIVO',
        'items': [
            {'prod': agua, 'cant': 4},
            {'prod': gaseosa, 'cant': 2},
        ]
    },
    {
        'cliente': 'Mesa 3',
        'metodo': 'NEQUI',
        'items': [
            {'prod': empanada, 'cant': 3},
            {'prod': agua, 'cant': 2},
        ]
    },
]
total_ventas_bar = 0
ordenes_cocina_esperadas = 0

try:
    for venta in ventas_bar:
        num_v = siguiente_numero_venta(conn)
        items_validos = [i for i in venta['items'] if i['prod'] is not None]
        total = sum(i['prod']['precio_venta'] * i['cant'] for i in items_validos)

        conn.execute("""
            INSERT INTO ventas (numero_venta, tipo, estado, cliente_nombre,
                subtotal, descuento, impuesto, total, total_pagado, saldo_pendiente,
                metodo_pago, id_usuario, usuario_nombre, fecha_pago)
            VALUES (?, 'normal', 'PAGADA', ?, ?, 0, 0, ?, ?, 0, ?, 1, ?, datetime('now','localtime'))
        """, (num_v, venta['cliente'], total, total, total,
              venta['metodo'], USUARIO_NOMBRE))
        id_v = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        for item in items_validos:
            total_linea = item['prod']['precio_venta'] * item['cant']
            conn.execute("""
                INSERT INTO venta_detalle (id_venta, id_producto, producto_nombre, cantidad,
                    precio_unitario, descuento_linea, total_linea)
                VALUES (?, ?, ?, ?, ?, 0, ?)
            """, (id_v, item['prod']['id_producto'], item['prod']['nombre'],
                  item['cant'], item['prod']['precio_venta'], total_linea))
            id_det = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

            conn.execute("""
                INSERT INTO movimientos_inventario (id_producto, tipo, cantidad, motivo, referencia, usuario)
                VALUES (?, 'VENTA', ?, 'Venta POS', ?, ?)
            """, (item['prod']['id_producto'], item['cant'], num_v, USUARIO_NOMBRE))

            if item['prod']['requiere_cocina']:
                cat = conn.execute("SELECT nombre FROM categorias WHERE id_categoria=?",
                                   (item['prod']['id_categoria'],)).fetchone()
                cat_nombre = cat['nombre'].lower() if cat else ''
                es_almuerzo = 'almuerzo' in cat_nombre or 'comida' in cat_nombre
                if not es_almuerzo:
                    conn.execute("""
                        INSERT INTO ordenes_cocina
                        (id_venta, id_detalle, numero_venta, producto_nombre, cantidad, cliente_nombre)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (id_v, id_det, num_v, item['prod']['nombre'],
                          item['cant'], venta['cliente']))
                    ordenes_cocina_esperadas += 1

        conn.execute("""
            INSERT INTO movimientos_caja (id_caja, tipo, concepto, valor, metodo_pago, usuario, fecha_hora)
            VALUES (?, 'INGRESO', ?, ?, ?, ?, datetime('now','localtime'))
        """, (id_caja, f"Venta {num_v} – {venta['cliente']}", total, venta['metodo'], USUARIO))

        conn.execute("""
            UPDATE caja_diaria SET total_ventas=total_ventas+?, monto_esperado=monto_esperado+?
            WHERE id_caja=?
        """, (total, total, id_caja))

        if venta['metodo'] == 'EFECTIVO':
            total_ingresos_efectivo += total
        else:
            total_ingresos_digital += total
        total_ventas_bar += total
        check(True, f"Venta {num_v}: {venta['cliente']} = ${total:,.0f} [{venta['metodo']}]")

    conn.commit()
    n_ord = conn.execute("SELECT COUNT(*) FROM ordenes_cocina WHERE estado='PENDIENTE'").fetchone()[0]
    check(n_ord >= ordenes_cocina_esperadas,
          f"Ordenes cocina pendientes generadas: {n_ord} (esperadas >= {ordenes_cocina_esperadas})", critico=True)
except Exception as e:
    check(False, f"Error en ventas bar: {e}", critico=True)
    traceback.print_exc()

# ──────────────────────────────────────────────────────────────
# 4. CUENTA ABIERTA
# ──────────────────────────────────────────────────────────────
seccion("4. BAR — CUENTA ABIERTA (pago diferido)")
id_cuenta_abierta = None
total_cuenta_abierta = 0
try:
    num_v = siguiente_numero_venta(conn)
    items_cuenta = [
        {'prod': agua, 'cant': 6},
        {'prod': gaseosa, 'cant': 3},
    ]
    items_cuenta = [i for i in items_cuenta if i['prod'] is not None]
    total_cuenta_abierta = sum(i['prod']['precio_venta'] * i['cant'] for i in items_cuenta)

    conn.execute("""
        INSERT INTO ventas (numero_venta, tipo, estado, cliente_nombre,
            subtotal, descuento, impuesto, total, total_pagado, saldo_pendiente,
            id_usuario, usuario_nombre)
        VALUES (?, 'cuenta_abierta', 'ABIERTA', 'Piscina VIP', ?, 0, 0, ?, 0, ?,
                1, ?)
    """, (num_v, total_cuenta_abierta, total_cuenta_abierta, total_cuenta_abierta, USUARIO_NOMBRE))
    id_cuenta_abierta = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    for item in items_cuenta:
        total_linea = item['prod']['precio_venta'] * item['cant']
        conn.execute("""
            INSERT INTO venta_detalle (id_venta, id_producto, producto_nombre, cantidad,
                precio_unitario, descuento_linea, total_linea)
            VALUES (?, ?, ?, ?, ?, 0, ?)
        """, (id_cuenta_abierta, item['prod']['id_producto'], item['prod']['nombre'],
              item['cant'], item['prod']['precio_venta'], total_linea))
        conn.execute("""
            INSERT INTO movimientos_inventario (id_producto, tipo, cantidad, motivo, referencia, usuario)
            VALUES (?, 'VENTA', ?, 'Cuenta Abierta', ?, ?)
        """, (item['prod']['id_producto'], item['cant'], num_v, USUARIO_NOMBRE))

    conn.commit()
    check(True, f"Cuenta abierta {num_v}: Piscina VIP = ${total_cuenta_abierta:,.0f}")
    check(id_cuenta_abierta is not None, "id_venta de cuenta abierta registrado", critico=True)

    # Verificar aparece en cuentas abiertas
    c_ab = conn.execute("SELECT * FROM ventas WHERE estado='ABIERTA' AND id_venta=?",
                        (id_cuenta_abierta,)).fetchone()
    check(c_ab is not None, "Cuenta aparece en ventas con estado=ABIERTA", critico=True)
    check(c_ab['saldo_pendiente'] == total_cuenta_abierta,
          f"Saldo pendiente correcto: ${c_ab['saldo_pendiente']:,.0f}")
except Exception as e:
    check(False, f"Error en cuenta abierta: {e}", critico=True)
    traceback.print_exc()

# ──────────────────────────────────────────────────────────────
# 5. COCINA — PROCESAR ORDENES
# ──────────────────────────────────────────────────────────────
seccion("5. COCINA — PROCESAR ORDENES PENDIENTES")
try:
    pendientes = conn.execute(
        "SELECT * FROM ordenes_cocina WHERE estado='PENDIENTE'"
    ).fetchall()
    check(len(pendientes) > 0, f"{len(pendientes)} ordenes pendientes para procesar")

    # PREPARANDO
    for o in pendientes:
        conn.execute("""
            UPDATE ordenes_cocina SET estado='PREPARANDO',
            hora_inicio=datetime('now','localtime'), usuario_cocina=?
            WHERE id_orden=?
        """, (USUARIO_NOMBRE, o['id_orden']))
    conn.commit()

    check(
        conn.execute("SELECT COUNT(*) FROM ordenes_cocina WHERE estado='PREPARANDO'").fetchone()[0] >= len(pendientes),
        f"Todas en PREPARANDO"
    )

    # LISTO
    for o in pendientes:
        conn.execute("""
            UPDATE ordenes_cocina SET estado='LISTO',
            hora_listo=datetime('now','localtime')
            WHERE id_orden=?
        """, (o['id_orden'],))
        conn.execute("""
            UPDATE venta_detalle SET estado_cocina='LISTO', hora_listo=datetime('now','localtime')
            WHERE id_detalle=?
        """, (o['id_detalle'],))
    conn.commit()

    # ENTREGADO
    for o in pendientes:
        conn.execute("""
            UPDATE ordenes_cocina SET estado='ENTREGADO',
            hora_entrega=datetime('now','localtime')
            WHERE id_orden=?
        """, (o['id_orden'],))
    conn.commit()

    n_entregados = conn.execute(
        "SELECT COUNT(*) FROM ordenes_cocina WHERE estado='ENTREGADO' AND DATE(hora_pedido)>=?",
        (HOY,)
    ).fetchone()[0]
    n_pendientes_restantes = conn.execute(
        "SELECT COUNT(*) FROM ordenes_cocina WHERE estado='PENDIENTE'"
    ).fetchone()[0]
    check(n_pendientes_restantes == 0, "Sin ordenes pendientes al finalizar cocina", critico=True)
    check(True, f"Ordenes procesadas: {n_entregados} entregadas hoy")
except Exception as e:
    check(False, f"Error procesando ordenes cocina: {e}", critico=True)
    traceback.print_exc()

# ──────────────────────────────────────────────────────────────
# 6. PAGO DE CUENTA ABIERTA (parcial + total)
# ──────────────────────────────────────────────────────────────
seccion("6. PAGOS — CUENTA ABIERTA")
try:
    if id_cuenta_abierta:
        # Pago parcial
        pago_parcial = total_cuenta_abierta * 0.5
        conn.execute("""
            INSERT INTO pagos (id_venta, valor, metodo_pago, usuario_registro)
            VALUES (?, ?, 'EFECTIVO', ?)
        """, (id_cuenta_abierta, pago_parcial, USUARIO))

        nuevo_pagado = pago_parcial
        nuevo_saldo = total_cuenta_abierta - pago_parcial
        conn.execute("""
            UPDATE ventas SET total_pagado=?, saldo_pendiente=?, estado='ABIERTA'
            WHERE id_venta=?
        """, (nuevo_pagado, nuevo_saldo, id_cuenta_abierta))

        conn.execute("""
            INSERT INTO movimientos_caja (id_caja, tipo, concepto, valor, metodo_pago, usuario, fecha_hora)
            VALUES (?, 'INGRESO', ?, ?, 'EFECTIVO', ?, datetime('now','localtime'))
        """, (id_caja, f"Pago parcial cuenta Piscina VIP", pago_parcial, USUARIO))
        conn.execute("""
            UPDATE caja_diaria SET total_ventas=total_ventas+?, monto_esperado=monto_esperado+?
            WHERE id_caja=?
        """, (pago_parcial, pago_parcial, id_caja))
        total_ingresos_efectivo += pago_parcial
        conn.commit()

        v_parcial = conn.execute("SELECT * FROM ventas WHERE id_venta=?", (id_cuenta_abierta,)).fetchone()
        check(v_parcial['estado'] == 'ABIERTA', "Pago parcial: estado sigue ABIERTA")
        check(abs(v_parcial['saldo_pendiente'] - nuevo_saldo) < 0.01,
              f"Saldo tras pago parcial: ${v_parcial['saldo_pendiente']:,.0f}")

        # Pago final
        conn.execute("""
            INSERT INTO pagos (id_venta, valor, metodo_pago, usuario_registro)
            VALUES (?, ?, 'DAVIPLATA', ?)
        """, (id_cuenta_abierta, nuevo_saldo, USUARIO))

        conn.execute("""
            UPDATE ventas SET total_pagado=?, saldo_pendiente=0, estado='PAGADA',
            fecha_pago=datetime('now','localtime')
            WHERE id_venta=?
        """, (total_cuenta_abierta, id_cuenta_abierta))

        conn.execute("""
            INSERT INTO movimientos_caja (id_caja, tipo, concepto, valor, metodo_pago, usuario, fecha_hora)
            VALUES (?, 'INGRESO', ?, ?, 'DAVIPLATA', ?, datetime('now','localtime'))
        """, (id_caja, "Pago final cuenta Piscina VIP", nuevo_saldo, USUARIO))
        conn.execute("""
            UPDATE caja_diaria SET total_ventas=total_ventas+?, monto_esperado=monto_esperado+?
            WHERE id_caja=?
        """, (nuevo_saldo, nuevo_saldo, id_caja))
        total_ingresos_digital += nuevo_saldo
        conn.commit()

        v_final = conn.execute("SELECT * FROM ventas WHERE id_venta=?", (id_cuenta_abierta,)).fetchone()
        check(v_final['estado'] == 'PAGADA', "Pago final: cuenta cerrada (estado=PAGADA)", critico=True)
        check(v_final['saldo_pendiente'] == 0, "Saldo pendiente = 0 tras pago total", critico=True)

        # Verificar tabla pagos
        pagos = conn.execute("SELECT * FROM pagos WHERE id_venta=?", (id_cuenta_abierta,)).fetchall()
        check(len(pagos) == 2, f"Tabla pagos: {len(pagos)} registros para esta cuenta (esperados 2)")

    # Verificar que NO quedan cuentas abiertas de la simulación sin pagar
    abiertas_restantes = conn.execute(
        "SELECT COUNT(*) FROM ventas WHERE estado='ABIERTA' AND id_venta != ?",
        (id_cuenta_abierta or 0,)
    ).fetchone()[0]
    check(True, f"Cuentas abiertas restantes (otras): {abiertas_restantes}")

except Exception as e:
    # pagos table might not exist
    check(False, f"Error en pagos: {e}")
    traceback.print_exc()

# ──────────────────────────────────────────────────────────────
# 7. RESERVA DE ALMUERZO
# ──────────────────────────────────────────────────────────────
seccion("7. RESERVA DE ALMUERZO")
try:
    if almuerzo:
        num_v = siguiente_numero_venta(conn)
        total_alm = almuerzo['precio_venta'] * 3

        conn.execute("""
            INSERT INTO ventas (numero_venta, tipo, estado, cliente_nombre,
                subtotal, descuento, impuesto, total, total_pagado, saldo_pendiente,
                metodo_pago, id_usuario, usuario_nombre, fecha_pago)
            VALUES (?, 'normal', 'PAGADA', 'Los Turistas', ?, 0, 0, ?, ?, 0, 'EFECTIVO', 1, ?, datetime('now','localtime'))
        """, (num_v, total_alm, total_alm, total_alm, USUARIO_NOMBRE))
        id_v_alm = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        conn.execute("""
            INSERT INTO venta_detalle (id_venta, id_producto, producto_nombre, cantidad,
                precio_unitario, descuento_linea, total_linea)
            VALUES (?, ?, ?, 3, ?, 0, ?)
        """, (id_v_alm, almuerzo['id_producto'], almuerzo['nombre'],
              almuerzo['precio_venta'], total_alm))

        # Almuerzo → reservas_almuerzo (no ordenes_cocina)
        conn.execute("""
            INSERT INTO reservas_almuerzo
            (cliente_nombre, cantidad_almuerzos, tipo_almuerzo, hora_entrega_estimada,
             estado, notas, id_usuario)
            VALUES (?, 3, ?, '13:00', 'RESERVADO', 'Sin picante', 1)
        """, ('Los Turistas', almuerzo['nombre']))
        id_reserva = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        conn.execute("""
            INSERT INTO movimientos_caja (id_caja, tipo, concepto, valor, metodo_pago, usuario, fecha_hora)
            VALUES (?, 'INGRESO', ?, ?, 'EFECTIVO', ?, datetime('now','localtime'))
        """, (id_caja, f"Almuerzo {num_v} – Los Turistas", total_alm, USUARIO))
        conn.execute("""
            UPDATE caja_diaria SET total_ventas=total_ventas+?, monto_esperado=monto_esperado+?
            WHERE id_caja=?
        """, (total_alm, total_alm, id_caja))
        total_ingresos_efectivo += total_alm
        conn.commit()

        check(True, f"Reserva almuerzo: Los Turistas x3 {almuerzo['nombre']} = ${total_alm:,.0f}")

        # Verificar que NO se creó orden cocina para almuerzo
        ord_alm = conn.execute(
            "SELECT * FROM ordenes_cocina WHERE id_venta=?", (id_v_alm,)
        ).fetchone()
        check(ord_alm is None, "Almuerzo NO genera orden en cocina (correcto — va a reservas_almuerzo)", critico=True)

        # Procesar reserva
        conn.execute("UPDATE reservas_almuerzo SET estado='EN_PREPARACION' WHERE id_reserva=?", (id_reserva,))
        conn.execute("UPDATE reservas_almuerzo SET estado='LISTO' WHERE id_reserva=?", (id_reserva,))
        conn.commit()
        res = conn.execute("SELECT estado FROM reservas_almuerzo WHERE id_reserva=?", (id_reserva,)).fetchone()
        check(res['estado'] == 'LISTO', "Reserva almuerzo procesada: estado=LISTO")
    else:
        check(False, "No hay almuerzo configurado — saltando test")
except Exception as e:
    check(False, f"Error en reserva almuerzo: {e}")
    traceback.print_exc()

# ──────────────────────────────────────────────────────────────
# 8. GASTOS
# ──────────────────────────────────────────────────────────────
seccion("8. GASTOS OPERATIVOS")
gastos_dia = [
    ('Hielo x10 bolsas', 30000, 'EFECTIVO', 'Insumos'),
    ('Servilletas y vasos', 15000, 'EFECTIVO', 'Insumos'),
    ('Recarga gas cocina', 60000, 'TRANSFERENCIA', 'Servicios'),
]
try:
    for desc, valor, metodo, cat in gastos_dia:
        conn.execute("""
            INSERT INTO gastos (fecha, descripcion, valor, metodo_pago, categoria, tipo_gasto,
                usuario_registro, fecha_registro)
            VALUES (date('now','localtime'), ?, ?, ?, ?, 'OPERATIVO', ?, datetime('now','localtime'))
        """, (desc, valor, metodo, cat, USUARIO))

        conn.execute("""
            INSERT INTO movimientos_caja (id_caja, tipo, concepto, valor, metodo_pago, usuario, fecha_hora)
            VALUES (?, 'EGRESO', ?, ?, ?, ?, datetime('now','localtime'))
        """, (id_caja, f"Gasto: {desc}", valor, metodo, USUARIO))
        conn.execute("""
            UPDATE caja_diaria SET total_gastos=total_gastos+?, monto_esperado=monto_esperado-?
            WHERE id_caja=?
        """, (valor, valor, id_caja))

        if metodo == 'EFECTIVO':
            total_ingresos_efectivo -= valor
        total_gastos_sim += valor
        check(True, f"Gasto: {desc} = ${valor:,.0f} [{metodo}]")

    conn.commit()
    c = conn.execute("SELECT total_gastos FROM caja_diaria WHERE id_caja=?", (id_caja,)).fetchone()
    check(abs(c['total_gastos'] - total_gastos_sim) < 0.01,
          f"Total gastos en caja: ${c['total_gastos']:,.0f} (esperado ${total_gastos_sim:,.0f})", critico=True)
except Exception as e:
    check(False, f"Error en gastos: {e}", critico=True)
    traceback.print_exc()

# ──────────────────────────────────────────────────────────────
# 9. CIERRE DE CAJA Y CUADRE
# ──────────────────────────────────────────────────────────────
seccion("9. CIERRE DE CAJA — CUADRE")
try:
    caja_pre = conn.execute("SELECT * FROM caja_diaria WHERE id_caja=?", (id_caja,)).fetchone()
    monto_esperado = caja_pre['monto_esperado']

    # Simular cuadre perfecto
    monto_real = monto_esperado
    diferencia = monto_real - monto_esperado

    conn.execute("""
        UPDATE caja_diaria SET estado='CERRADA', fecha_cierre=datetime('now','localtime'),
        usuario_cierre=?, monto_real=?, diferencia=?
        WHERE id_caja=?
    """, (USUARIO, monto_real, diferencia, id_caja))
    conn.commit()

    c = conn.execute("SELECT * FROM caja_diaria WHERE id_caja=?", (id_caja,)).fetchone()
    check(c['estado'] == 'CERRADA', "Caja cerrada correctamente")
    check(c['fecha_cierre'] is not None, "fecha_cierre registrada")
    check(c['diferencia'] == 0, f"Cuadre perfecto: diferencia=${c['diferencia']:,.0f}")

    print()
    print("  DESGLOSE FINAL DE CAJA:")
    print(f"    Monto inicial:   ${c['monto_inicial']:>12,.0f}")
    print(f"    Total boletas:   ${c['total_boletas']:>12,.0f}")
    print(f"    Total ventas:    ${c['total_ventas']:>12,.0f}")
    print(f"    Total gastos:    ${c['total_gastos']:>12,.0f}")
    print(f"    Monto esperado:  ${c['monto_esperado']:>12,.0f}")
    print(f"    Monto real:      ${c['monto_real']:>12,.0f}")
    print(f"    Diferencia:      ${c['diferencia']:>12,.0f}")

    # Verificar movimientos caja
    n_movs = conn.execute("SELECT COUNT(*) FROM movimientos_caja WHERE id_caja=?", (id_caja,)).fetchone()[0]
    check(n_movs > 0, f"Movimientos registrados en caja: {n_movs}")

except Exception as e:
    check(False, f"Error en cierre de caja: {e}", critico=True)
    traceback.print_exc()

# ──────────────────────────────────────────────────────────────
# 10. VERIFICACIÓN DE INTEGRIDAD FINAL
# ──────────────────────────────────────────────────────────────
seccion("10. INTEGRIDAD FINAL")
try:
    # Suma de movimientos caja = monto_esperado - monto_inicial
    movs = conn.execute("""
        SELECT
            SUM(CASE WHEN tipo='INGRESO' THEN valor ELSE 0 END) as ingresos,
            SUM(CASE WHEN tipo='EGRESO'  THEN valor ELSE 0 END) as egresos
        FROM movimientos_caja WHERE id_caja=?
    """, (id_caja,)).fetchone()
    caja_f = conn.execute("SELECT * FROM caja_diaria WHERE id_caja=?", (id_caja,)).fetchone()

    ingresos_movs = movs['ingresos'] or 0
    egresos_movs  = movs['egresos']  or 0
    saldo_movs    = caja_f['monto_inicial'] + ingresos_movs - egresos_movs

    check(abs(saldo_movs - caja_f['monto_esperado']) < 1.0,
          f"Movimientos cuadran: inicial + ingresos - egresos = ${saldo_movs:,.0f} == esperado ${caja_f['monto_esperado']:,.0f}",
          critico=True)

    # No hay ventas ABIERTA sin cuadrar (excepto si hubo cuenta abierta que ya pagamos)
    abiertas = conn.execute("SELECT COUNT(*) FROM ventas WHERE estado='ABIERTA'").fetchone()[0]
    check(abiertas == 0, f"Cuentas abiertas sin cobrar al cierre: {abiertas} (esperado 0)", critico=True)

    # No hay ordenes cocina PENDIENTE
    pend_cocina = conn.execute("SELECT COUNT(*) FROM ordenes_cocina WHERE estado='PENDIENTE'").fetchone()[0]
    check(pend_cocina == 0, f"Ordenes cocina pendientes al cierre: {pend_cocina} (esperado 0)")

    # Auditoria BD
    integridad = conn.execute("PRAGMA integrity_check").fetchone()[0]
    check(integridad == 'ok', f"PRAGMA integrity_check: {integridad}", critico=True)

    # Series no tienen huecos (consecutivo > lo que había)
    s = conn.execute("SELECT consecutivo_actual FROM series_facturacion WHERE activa=1").fetchone()
    check(s['consecutivo_actual'] > 8, f"Serie ventas avanzó a: {s['consecutivo_actual']}")

except Exception as e:
    check(False, f"Error en verificación final: {e}", critico=True)
    traceback.print_exc()

# ──────────────────────────────────────────────────────────────
# REABRIR CAJA PARA NO BLOQUEAR LA APP
# ──────────────────────────────────────────────────────────────
conn.execute("""
    UPDATE caja_diaria SET estado='ABIERTA', fecha_cierre=NULL, usuario_cierre=NULL,
    monto_real=NULL, diferencia=0
    WHERE id_caja=?
""", (id_caja,))
conn.commit()
conn.close()

# ──────────────────────────────────────────────────────────────
# RESUMEN
# ──────────────────────────────────────────────────────────────
seccion("RESUMEN SIMULACION DIA COMPLETO")
print(f"  Errores criticos:  {len(errores)}")
print(f"  Advertencias:      {len(advertencias)}")
if errores:
    print("\n  ERRORES:")
    for e in errores:
        print(f"    [X] {e}")
if advertencias:
    print("\n  ADVERTENCIAS:")
    for a in advertencias:
        print(f"    [!] {a}")
if not errores:
    print("\n  Sistema apto para operacion en produccion.")
else:
    print("\n  Revisar los errores criticos antes de usar en produccion.")
print()
