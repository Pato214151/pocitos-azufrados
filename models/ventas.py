"""
models/ventas.py — Lógica de BD para ventas POS.

Separa las operaciones de base de datos de la UI en pos_module.py.
"""
from database.connection import conexion_segura, transaccion_atomica
from models.series import generar_numero_venta_en_conn, generar_numero_fe_en_conn
from utils.logger import log_auditoria
from utils.tema_corporativo import format_money


def insertar_items_venta(conn, id_venta, numero, cliente, carrito,
                          usuario_nombre, id_usuario):
    """Inserta venta_detalle, actualiza inventario y crea ordenes_cocina/reservas_almuerzo.

    Retorna (tiene_cocina: bool, ids_productos: list).
    Debe llamarse dentro de un bloque transaccion_atomica ya abierto.
    """
    tiene_cocina = False
    ids_productos = []

    for item in carrito:
        estado_cocina = 'PENDIENTE' if item['requiere_cocina'] else 'N/A'
        if item['requiere_cocina']:
            tiene_cocina = True

        det_cur = conn.execute("""
            INSERT INTO venta_detalle
            (id_venta, id_producto, producto_nombre, cantidad,
             precio_unitario, total_linea, estado_cocina)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (id_venta, item['id_producto'], item['nombre'],
              item['cantidad'], item['precio'], item['total'],
              estado_cocina))
        id_detalle = det_cur.lastrowid

        if not item.get('es_boleta'):
            ids_productos.append(item['id_producto'])
            stock_row = conn.execute(
                "SELECT stock_actual FROM productos WHERE id_producto = ?",
                (item['id_producto'],)
            ).fetchone()
            stock_anterior = stock_row['stock_actual'] if stock_row else 0
            stock_nuevo = stock_anterior - item['cantidad']

            conn.execute("""
                UPDATE productos SET stock_actual = stock_actual - ?,
                fecha_actualizacion = datetime('now','localtime')
                WHERE id_producto = ?
            """, (item['cantidad'], item['id_producto']))

            conn.execute("""
                INSERT INTO movimientos_inventario
                (id_producto, tipo, cantidad, motivo, referencia, usuario,
                 stock_anterior, stock_nuevo)
                VALUES (?, 'VENTA', ?, ?, ?, ?, ?, ?)
            """, (item['id_producto'], item['cantidad'],
                  'Venta POS', numero, usuario_nombre,
                  stock_anterior, stock_nuevo))

        if item['requiere_cocina'] and not item.get('es_almuerzo'):
            conn.execute("""
                INSERT INTO ordenes_cocina
                (id_venta, id_detalle, numero_venta, producto_nombre,
                 cantidad, cliente_nombre)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (id_venta, id_detalle, numero, item['nombre'],
                  item['cantidad'], cliente))

    for item in carrito:
        if item.get('es_almuerzo') and item.get('pedido_nombre'):
            conn.execute("""
                INSERT INTO reservas_almuerzo
                (cliente_nombre, cantidad_almuerzos, tipo_almuerzo,
                 hora_entrega_estimada, estado, notas, id_usuario)
                VALUES (?, ?, ?, ?, 'RESERVADO', ?, ?)
            """, (item['pedido_nombre'], item['cantidad'], item['nombre'],
                  item['pedido_hora'], item.get('pedido_notas', ''),
                  id_usuario))

    return tiene_cocina, ids_productos


def crear_venta(*, carrito, total_venta, descuento, motivo_descuento,
                metodo_pago, pago_split, monto_recibido, id_cliente,
                cliente_nombre, notas, datos_fe, usuario, db_path=None):
    """Persiste una venta completa en una transacción atómica.

    Parámetros (keyword-only):
        carrito          — lista de items del carrito
        total_venta      — float
        descuento        — float
        motivo_descuento — str | None
        metodo_pago      — str ('EFECTIVO', 'TRANSFERENCIA', 'MIXTO', ...)
        pago_split       — dict | None: {'efectivo', 'transferencia', 'metodo_transfer'}
        monto_recibido   — float | None (solo EFECTIVO, para calcular cambio)
        id_cliente       — int | None
        cliente_nombre   — str | None
        notas            — str | None
        datos_fe         — dict | None: {'nombre', 'nit', 'email'}
        usuario          — dict: {id_usuario, usuario, nombre_completo}

    Retorna dict: {id_venta, numero, numero_fe, tiene_cocina, ids_productos}
    Lanza ValueError si hay stock insuficiente para algún ítem.
    """
    with transaccion_atomica(db_path=db_path) as conn:
        numero = generar_numero_venta_en_conn(conn)
        subtotal = sum(i['total'] for i in carrito)

        cursor = conn.execute("""
            INSERT INTO ventas
            (numero_venta, tipo, estado, cliente_nombre, id_cliente, subtotal,
             descuento, motivo_descuento, total, total_pagado, saldo_pendiente,
             metodo_pago, notas, id_usuario, usuario_nombre, fecha_pago)
            VALUES (?, 'normal', 'PAGADA', ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?,
                    datetime('now','localtime'))
        """, (numero, cliente_nombre, id_cliente, subtotal, descuento,
              motivo_descuento, total_venta, total_venta,
              metodo_pago, notas, usuario['id_usuario'],
              usuario['nombre_completo']))

        id_venta = cursor.lastrowid

        if descuento > 0:
            log_auditoria(conn, 'ventas', id_venta, 'DESCUENTO',
                          usuario['usuario'],
                          f"Descuento {format_money(descuento)} en venta {numero}. "
                          f"Motivo: {motivo_descuento}")

        for item in carrito:
            if item.get('controla_stock') and not item.get('es_boleta'):
                row = conn.execute(
                    "SELECT stock_actual FROM productos WHERE id_producto = ?",
                    (item['id_producto'],)
                ).fetchone()
                stock_disp = (row['stock_actual'] if row else 0) or 0
                if stock_disp < item['cantidad']:
                    raise ValueError(
                        f"Stock insuficiente para '{item['nombre']}': "
                        f"disponible {stock_disp}, solicitado {item['cantidad']}"
                    )

        tiene_cocina, ids_productos = insertar_items_venta(
            conn, id_venta, numero, cliente_nombre, carrito,
            usuario['nombre_completo'], usuario['id_usuario']
        )

        if pago_split:
            conn.execute("""
                INSERT INTO pagos (id_venta, valor, metodo_pago, usuario_registro)
                VALUES (?, ?, 'EFECTIVO', ?)
            """, (id_venta, pago_split['efectivo'], usuario['nombre_completo']))
            conn.execute("""
                INSERT INTO pagos (id_venta, valor, metodo_pago, usuario_registro)
                VALUES (?, ?, ?, ?)
            """, (id_venta, pago_split['transferencia'],
                  pago_split['metodo_transfer'], usuario['nombre_completo']))
        else:
            conn.execute("""
                INSERT INTO pagos
                (id_venta, valor, metodo_pago, usuario_registro, monto_recibido)
                VALUES (?, ?, ?, ?, ?)
            """, (id_venta, total_venta, metodo_pago,
                  usuario['nombre_completo'], monto_recibido))

        caja = conn.execute(
            "SELECT id_caja FROM caja_diaria WHERE estado = 'ABIERTA'"
        ).fetchone()
        if caja:
            if pago_split:
                conn.execute("""
                    INSERT INTO movimientos_caja
                    (id_caja, tipo, concepto, valor, metodo_pago, referencia, usuario)
                    VALUES (?, 'INGRESO', ?, ?, 'EFECTIVO', ?, ?)
                """, (caja['id_caja'], f"Venta {numero} (efectivo)",
                      pago_split['efectivo'], numero, usuario['nombre_completo']))
                conn.execute("""
                    INSERT INTO movimientos_caja
                    (id_caja, tipo, concepto, valor, metodo_pago, referencia, usuario)
                    VALUES (?, 'INGRESO', ?, ?, ?, ?, ?)
                """, (caja['id_caja'], f"Venta {numero} (transfer)",
                      pago_split['transferencia'], pago_split['metodo_transfer'],
                      numero, usuario['nombre_completo']))
            else:
                conn.execute("""
                    INSERT INTO movimientos_caja
                    (id_caja, tipo, concepto, valor, metodo_pago, referencia, usuario)
                    VALUES (?, 'INGRESO', ?, ?, ?, ?, ?)
                """, (caja['id_caja'], f"Venta {numero}",
                      total_venta, metodo_pago, numero,
                      usuario['nombre_completo']))

            conn.execute("""
                UPDATE caja_diaria
                SET total_ventas   = total_ventas + ?,
                    monto_esperado = monto_inicial
                                     + (total_ventas + ?)
                                     + total_boletas
                                     - total_gastos
                WHERE id_caja = ?
            """, (total_venta, total_venta, caja['id_caja']))

        numero_fe = None
        if datos_fe:
            numero_fe = generar_numero_fe_en_conn(conn)
            conn.execute("""
                INSERT INTO facturas_electronicas
                (id_venta, numero_factura, cliente_nombre, cliente_nit,
                 cliente_email, usuario_registro)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (id_venta, numero_fe, datos_fe['nombre'], datos_fe['nit'],
                  datos_fe.get('email', ''), usuario['nombre_completo']))

    return {
        'id_venta':      id_venta,
        'numero':        numero,
        'numero_fe':     numero_fe,
        'tiene_cocina':  tiene_cocina,
        'ids_productos': ids_productos,
    }


def abrir_cuenta_abierta(*, carrito, total_venta, descuento, id_cliente,
                          cliente_nombre, notas, usuario, db_path=None):
    """Persiste una cuenta abierta (sin cobrar) en una transacción atómica.

    Parámetros (keyword-only):
        carrito        — lista de items del carrito
        total_venta    — float
        descuento      — float
        id_cliente     — int | None
        cliente_nombre — str  (requerido)
        notas          — str | None
        usuario        — dict: {id_usuario, nombre_completo}

    Retorna dict: {id_venta, numero}
    """
    with transaccion_atomica(db_path=db_path) as conn:
        numero = generar_numero_venta_en_conn(conn)
        subtotal = sum(i['total'] for i in carrito)

        cursor = conn.execute("""
            INSERT INTO ventas
            (numero_venta, tipo, estado, cliente_nombre, id_cliente, subtotal,
             descuento, total, total_pagado, saldo_pendiente,
             notas, id_usuario, usuario_nombre)
            VALUES (?, 'cuenta_abierta', 'ABIERTA', ?, ?, ?, ?, ?, 0, ?, ?, ?, ?)
        """, (numero, cliente_nombre, id_cliente, subtotal, descuento,
              total_venta, total_venta,
              notas, usuario['id_usuario'], usuario['nombre_completo']))

        id_venta = cursor.lastrowid

        insertar_items_venta(
            conn, id_venta, numero, cliente_nombre, carrito,
            usuario['nombre_completo'], usuario['id_usuario']
        )

    return {'id_venta': id_venta, 'numero': numero}


def verificar_stock_minimo(ids_productos, usuario_nombre, db_path=None):
    """Consulta productos bajo su stock mínimo y registra auditoría para cada uno.

    Retorna lista de filas con {id_producto, nombre, stock_actual, stock_minimo}.
    Lista vacía si ninguno está bajo mínimo o si ids_productos está vacío.
    """
    if not ids_productos:
        return []
    with conexion_segura(db_path=db_path) as conn:
        placeholders = ','.join('?' * len(ids_productos))
        bajo_minimo = conn.execute(f"""
            SELECT id_producto, nombre, stock_actual, stock_minimo
            FROM productos
            WHERE id_producto IN ({placeholders})
              AND stock_actual <= stock_minimo
              AND activo = 1
            ORDER BY stock_actual ASC
        """, ids_productos).fetchall()

        for r in bajo_minimo:
            log_auditoria(
                conn, tabla='productos', id_registro=r['id_producto'],
                accion='STOCK_BAJO',
                usuario=usuario_nombre,
                comentario=f"Stock {r['stock_actual']} <= minimo {r['stock_minimo']}",
            )

    return bajo_minimo
