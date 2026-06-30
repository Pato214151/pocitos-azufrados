"""
Validaciones de negocio centralizadas — Club Los Pocitos Azufrados
"""

import datetime
from database.connection import conexion_segura

try:
    import bcrypt as _bcrypt
    _BCRYPT_OK = True
except ImportError:
    _BCRYPT_OK = False


def validar_resolucion_dian(db_path=None):
    """Verifica si se puede emitir una factura electrónica según la resolución DIAN.

    Retorna un dict:
        {
            'puede_emitir': bool,
            'nivel': 'ok' | 'advertencia' | 'bloqueado',
            'mensaje': str   # vacío si nivel == 'ok'
        }

    Reglas:
    - Nivel 'advertencia': faltan <= 500 números O la fecha vence en <= 30 días.
    - Nivel 'bloqueado': faltan <= 50 números O la fecha vence en <= 3 días O ya venció.
    - Si la resolución no está configurada (número vacío) retorna 'ok' sin bloquear.
    """
    try:
        with conexion_segura(db_path=db_path) as conn:
            rows = conn.execute(
                "SELECT clave, valor FROM configuracion WHERE clave LIKE 'resolucion_dian_%'"
            ).fetchall()
            cfg = {r['clave']: r['valor'] for r in rows}

            numero = cfg.get('resolucion_dian_numero', '').strip()
            # Si no hay resolución configurada, no bloqueamos
            if not numero:
                return {'puede_emitir': True, 'nivel': 'ok', 'mensaje': ''}

            fecha_hasta_str = cfg.get('resolucion_dian_fecha_hasta', '').strip()
            prefijo = cfg.get('resolucion_dian_prefijo', 'LP').strip() or 'LP'
            rango_hasta = int(cfg.get('resolucion_dian_hasta', '10000') or '10000')

            # Consecutivo actual de la serie LP
            row_serie = conn.execute(
                "SELECT consecutivo_actual FROM series_facturacion WHERE prefijo = ? AND activa = 1 ORDER BY ano DESC LIMIT 1",
                (prefijo,)
            ).fetchone()
            consecutivo_actual = row_serie['consecutivo_actual'] if row_serie else 0
            restantes = rango_hasta - consecutivo_actual

            # Validación por rango
            if restantes <= 0:
                return {
                    'puede_emitir': False,
                    'nivel': 'bloqueado',
                    'mensaje': f"La resolución DIAN ha agotado su rango ({rango_hasta} facturas). Renueve la resolución antes de emitir."
                }
            if restantes <= 50:
                return {
                    'puede_emitir': False,
                    'nivel': 'bloqueado',
                    'mensaje': f"Quedan solo {restantes} numeros en la resolucion DIAN. Renueve antes de continuar."
                }
            if restantes <= 500:
                return {
                    'puede_emitir': True,
                    'nivel': 'advertencia',
                    'mensaje': f"Atencion: quedan {restantes} numeros en la resolucion DIAN. Programe su renovacion."
                }

            # Validación por fecha
            if fecha_hasta_str:
                try:
                    fecha_vencimiento = datetime.datetime.strptime(fecha_hasta_str, '%Y-%m-%d').date()
                    hoy = datetime.date.today()
                    dias_restantes = (fecha_vencimiento - hoy).days

                    if dias_restantes < 0:
                        return {
                            'puede_emitir': False,
                            'nivel': 'bloqueado',
                            'mensaje': f"La resolucion DIAN vencio el {fecha_hasta_str}. Renuevela antes de emitir facturas."
                        }
                    if dias_restantes <= 3:
                        return {
                            'puede_emitir': False,
                            'nivel': 'bloqueado',
                            'mensaje': f"La resolucion DIAN vence en {dias_restantes} dia(s) ({fecha_hasta_str}). Renuevela urgente."
                        }
                    if dias_restantes <= 30:
                        return {
                            'puede_emitir': True,
                            'nivel': 'advertencia',
                            'mensaje': f"La resolucion DIAN vence en {dias_restantes} dias ({fecha_hasta_str}). Programe su renovacion."
                        }
                except ValueError:
                    pass  # fecha mal formateada, no bloqueamos

            return {'puede_emitir': True, 'nivel': 'ok', 'mensaje': ''}

    except Exception as e:
        # Error al consultar BD: no bloqueamos la venta, pero sí avisamos
        return {
            'puede_emitir': True,
            'nivel': 'advertencia',
            'mensaje': f"No se pudo verificar la resolucion DIAN: {e}"
        }


def verificar_pin_admin(pin_ingresado, db_path=None):
    """Verifica que el PIN ingresado corresponda a algún usuario administrador activo.

    Retorna (valido: bool, nombre_usuario: str | None).
    """
    if not pin_ingresado or len(pin_ingresado) != 4 or not pin_ingresado.isdigit():
        return False, None
    try:
        with conexion_segura(db_path=db_path) as conn:
            rows = conn.execute(
                "SELECT nombre_completo, pin FROM usuarios "
                "WHERE pin IS NOT NULL AND rol = 'administrador' AND activo = 1"
            ).fetchall()
            for row in rows:
                pin_guardado = row['pin']
                if not pin_guardado:
                    continue
                ok = False
                if pin_guardado.startswith('$2') and _BCRYPT_OK:
                    try:
                        ok = _bcrypt.checkpw(pin_ingresado.encode(), pin_guardado.encode())
                    except Exception:
                        ok = False
                else:
                    # Fallback para PINs legados aún sin hashear (migración).
                    # Una vez que el admin actualice el PIN desde Usuarios, este path
                    # quedará sin efecto porque todos los nuevos PINs se guardan con bcrypt.
                    import hmac
                    import logging
                    logging.getLogger("pocitos").warning(
                        f"Verificación de PIN usando comparación plaintext (hash legado). "
                        "El administrador debe actualizar el PIN desde el módulo Usuarios para migrar a bcrypt."
                    )
                    ok = hmac.compare_digest(pin_guardado, pin_ingresado)
                if ok:
                    return True, row['nombre_completo']
            return False, None
    except Exception:
        return False, None
