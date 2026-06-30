"""
models/inventario.py — Operaciones de BD para el módulo de inventario.

Separa la lógica de base de datos de la UI en inventario_module.py.
"""
from database.connection import conexion_segura
from utils.logger import log_auditoria


def registrar_movimiento_stock(id_producto, tipo, cantidad,
                                stock_anterior, stock_nuevo,
                                motivo, usuario_nombre, db_path=None):
    """Actualiza stock de un producto y registra el movimiento en auditoría.

    tipo — 'ENTRADA' | 'SALIDA'
    """
    with conexion_segura(db_path=db_path) as conn:
        conn.execute(
            "UPDATE productos SET stock_actual = ? WHERE id_producto = ?",
            (stock_nuevo, id_producto)
        )
        conn.execute("""
            INSERT INTO movimientos_inventario
            (id_producto, tipo, cantidad, stock_anterior, stock_nuevo, motivo, usuario)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (id_producto, tipo, cantidad, stock_anterior, stock_nuevo,
              motivo, usuario_nombre))
        log_auditoria(conn, 'productos', id_producto, 'UPDATE',
                      usuario_nombre, f"Ajuste {tipo.lower()}: {motivo}")


def editar_producto(id_producto, *, nombre, codigo_barras, id_categoria,
                    precio_venta, precio_costo, stock_minimo,
                    impuesto_porcentaje, requiere_cocina, permite_descuento,
                    usuario_nombre, db_path=None):
    """Actualiza los campos editables de un producto."""
    with conexion_segura(db_path=db_path) as conn:
        conn.execute("""
            UPDATE productos
            SET nombre=?, codigo_barras=?, id_categoria=?, precio_venta=?,
                precio_costo=?, stock_minimo=?, impuesto_porcentaje=?,
                requiere_cocina=?, permite_descuento=?,
                fecha_actualizacion=datetime('now','localtime')
            WHERE id_producto=?
        """, (nombre, codigo_barras, id_categoria, precio_venta, precio_costo,
              stock_minimo, impuesto_porcentaje, requiere_cocina,
              permite_descuento, id_producto))
        log_auditoria(conn, 'productos', id_producto, 'UPDATE',
                      usuario_nombre, f"Editar producto: {nombre}")


def carga_masiva_productos(productos, usuario_nombre, db_path=None):
    """Inserta o actualiza productos en bloque.

    productos — lista de dicts con claves:
        nombre, codigo_barras, categoria, precio_venta, stock_actual, stock_minimo

    Retorna dict: {insertados: int, actualizados: int, errores: list[str]}
    """
    insertados = 0
    actualizados = 0
    errores = []

    with conexion_segura(db_path=db_path) as conn:
        for prod in productos:
            try:
                cat_row = conn.execute("""
                    SELECT id_categoria FROM categorias
                    WHERE nombre = ? AND activa = 1 LIMIT 1
                """, (prod['categoria'],)).fetchone()
                id_categoria = cat_row['id_categoria'] if cat_row else None

                existe = None
                if prod['codigo_barras']:
                    existe = conn.execute("""
                        SELECT id_producto FROM productos
                        WHERE codigo_barras = ? LIMIT 1
                    """, (prod['codigo_barras'],)).fetchone()
                if not existe:
                    existe = conn.execute("""
                        SELECT id_producto FROM productos
                        WHERE LOWER(nombre) = LOWER(?) LIMIT 1
                    """, (prod['nombre'],)).fetchone()

                if existe:
                    conn.execute("""
                        UPDATE productos
                        SET nombre = ?, id_categoria = ?, precio_venta = ?,
                            stock_actual = ?, stock_minimo = ?,
                            fecha_actualizacion = datetime('now','localtime')
                        WHERE id_producto = ?
                    """, (prod['nombre'], id_categoria, prod['precio_venta'],
                          prod['stock_actual'], prod['stock_minimo'],
                          existe['id_producto']))
                    log_auditoria(conn, 'productos', existe['id_producto'], 'UPDATE',
                                  usuario_nombre, 'Actualizacion por carga masiva')
                    actualizados += 1
                else:
                    conn.execute("""
                        INSERT INTO productos
                        (codigo_barras, nombre, id_categoria, precio_venta,
                         stock_actual, stock_minimo, activo, fecha_creacion)
                        VALUES (?, ?, ?, ?, ?, ?, 1, datetime('now','localtime'))
                    """, (prod['codigo_barras'], prod['nombre'], id_categoria,
                          prod['precio_venta'], prod['stock_actual'],
                          prod['stock_minimo']))
                    insertados += 1

            except Exception as e:
                errores.append(f"{prod['nombre']}: {str(e)}")

    return {'insertados': insertados, 'actualizados': actualizados, 'errores': errores}


def aprobar_producto(id_producto, nombre, usuario_nombre, db_path=None):
    """Aprueba un producto pendiente de revisión (pendiente_aprobacion → 0)."""
    with conexion_segura(db_path=db_path) as conn:
        conn.execute(
            "UPDATE productos SET pendiente_aprobacion = 0 WHERE id_producto = ?",
            (id_producto,)
        )
        log_auditoria(conn, 'productos', id_producto, 'APROBAR',
                      usuario_nombre,
                      f"Producto '{nombre}' aprobado por administrador")


def rechazar_producto(id_producto, nombre, usuario_nombre, db_path=None):
    """Rechaza y desactiva un producto pendiente."""
    with conexion_segura(db_path=db_path) as conn:
        conn.execute(
            "UPDATE productos SET activo = 0, pendiente_aprobacion = 0 "
            "WHERE id_producto = ?",
            (id_producto,)
        )
        log_auditoria(conn, 'productos', id_producto, 'RECHAZAR',
                      usuario_nombre,
                      f"Producto '{nombre}' rechazado y desactivado")


def agregar_variante(id_producto, nombre_variante, precio_adicional,
                     db_path=None):
    """Inserta una variante nueva para un producto."""
    with conexion_segura(db_path=db_path) as conn:
        conn.execute("""
            INSERT INTO variantes_producto (id_producto, nombre_variante, precio_adicional)
            VALUES (?, ?, ?)
        """, (id_producto, nombre_variante, precio_adicional))


def eliminar_variante(id_variante, db_path=None):
    """Elimina una variante de producto."""
    with conexion_segura(db_path=db_path) as conn:
        conn.execute(
            "DELETE FROM variantes_producto WHERE id_variante = ?",
            (id_variante,)
        )
