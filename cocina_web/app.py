"""
Cocina Web - Club Los Pocitos Azufrados
Servidor Flask liviano para ver y gestionar pedidos de cocina
desde celular / tablet por WiFi.

Cómo usar:
  1. En el computador principal: python cocina_web/app.py
  2. Anota la IP del computador (ej: 192.168.1.5)
  3. En el celular/tablet (misma red WiFi): abrir http://192.168.1.5:5000

El servidor lee la misma base de datos SQLite del sistema.
"""

import os
import sys
import datetime
import functools
import hmac
import logging
import secrets
import time as _time

try:
    from zoneinfo import ZoneInfo as _ZoneInfo
    _TZ_BOGOTA = _ZoneInfo('America/Bogota')
except Exception:
    _TZ_BOGOTA = None


def _now_bogota():
    """Retorna la hora actual en Bogotá (UTC-5, sin DST)."""
    if _TZ_BOGOTA:
        return datetime.datetime.now(_TZ_BOGOTA)
    return datetime.datetime.now()

_log = logging.getLogger("pocitos")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

try:
    from flask import Flask, render_template, jsonify, request, redirect, url_for, Response
except ImportError:
    print("=" * 50)
    print("Flask no está instalado.")
    print("Ejecuta: pip install flask")
    print("=" * 50)
    sys.exit(1)

# ──────────────────────────────────────────────────────────────────────────────
# AUTENTICACIÓN — HTTP Basic Auth
# La clave se lee de configuracion → clave 'cocina_web_token'.
# Si no está configurada, usa 'cocina2025' como valor por defecto.
# Para cambiarla: Configuración en la app principal → campo cocina_web_token.
# ──────────────────────────────────────────────────────────────────────────────
COCINA_USER             = 'cocina'
COCINA_PASSWORD_DEFAULT = 'cocina2025'

from database.connection import conexion_segura


COCINA_REFRESH_DEFAULT = 15  # segundos


_pwd_cache: dict = {'value': None, 'ts': 0.0}
_PWD_TTL = 5  # segundos — TTL corto para reflejar cambios de clave casi de inmediato

_datos_cache: dict = {'value': None, 'ts': 0.0}
_DATOS_TTL = 3  # segundos — evita que múltiples celulares en autorefresh saturen la BD


def _get_password():
    """Lee el token/password de configuracion con cache de 5 segundos."""
    now = _time.monotonic()
    if _pwd_cache['value'] is not None and now - _pwd_cache['ts'] < _PWD_TTL:
        return _pwd_cache['value']
    try:
        with conexion_segura() as conn:
            row = conn.execute(
                "SELECT valor FROM configuracion WHERE clave = 'cocina_web_token'"
            ).fetchone()
            val = row['valor'].strip() if row and row['valor'] else ''
            pwd = val if val else COCINA_PASSWORD_DEFAULT
    except Exception:
        pwd = COCINA_PASSWORD_DEFAULT
    if pwd == COCINA_PASSWORD_DEFAULT:
        _log.warning(
            "cocina_web usa la clave por defecto. "
            "Cambiala en Configuracion -> Cocina Web para proteger el acceso."
        )
    _pwd_cache['value'] = pwd
    _pwd_cache['ts'] = now
    return pwd


def _get_refresh_interval():
    """Lee el intervalo de auto-refresh (segundos) desde configuracion.
    Clave: cocina_web_intervalo. Valor por defecto: 15 segundos.
    Rango válido: 5–120 s (fuera de rango → default)."""
    try:
        with conexion_segura() as conn:
            row = conn.execute(
                "SELECT valor FROM configuracion WHERE clave = 'cocina_web_intervalo'"
            ).fetchone()
            if row and row['valor']:
                val = int(row['valor'])
                if 5 <= val <= 120:
                    return val
    except Exception:
        pass
    return COCINA_REFRESH_DEFAULT


def _require_auth(f):
    """Decorador: exige HTTP Basic Auth antes de servir cualquier ruta.
    Usuario: 'cocina' / Clave: configuracion.cocina_web_token (o 'cocina2025' si no configurada)."""
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        auth = request.authorization
        pwd = _get_password()
        if not auth or auth.username != COCINA_USER or not hmac.compare_digest(auth.password, pwd):
            return Response(
                'Acceso restringido. Usuario: cocina / Clave: configurada en el sistema.',
                401,
                {'WWW-Authenticate': 'Basic realm="Cocina Pocitos"'}
            )
        return f(*args, **kwargs)
    return wrapper

_COCINA_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(
    __name__,
    template_folder=os.path.join(_COCINA_DIR, 'templates'),
    static_folder=os.path.join(_COCINA_DIR, 'static'),
)
def _cargar_o_generar_secret_key() -> bytes:
    """Carga la secret_key de Flask desde configuracion, o la genera y la persiste."""
    try:
        from database.connection import conexion_segura
        with conexion_segura() as conn:
            row = conn.execute(
                "SELECT valor FROM configuracion WHERE clave = 'flask_secret_key'"
            ).fetchone()
            if row and row[0]:
                return bytes.fromhex(row[0])
            nueva = os.urandom(32)
            conn.execute(
                "INSERT OR REPLACE INTO configuracion (clave, valor) VALUES ('flask_secret_key', ?)",
                (nueva.hex(),)
            )
            conn.commit()
            return nueva
    except Exception:
        return os.urandom(32)

app.secret_key = _cargar_o_generar_secret_key()

try:
    from flask import session
    _FLASK_SESSION_OK = True
except ImportError:
    _FLASK_SESSION_OK = False


# ──────────────────────────────────────────────────────────────────────────────
# CSRF — token por sesión, validado en todas las rutas POST
# ──────────────────────────────────────────────────────────────────────────────

def _get_csrf_token():
    """Genera (o reutiliza) el token CSRF de la sesión activa."""
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(32)
    return session['csrf_token']


def _require_csrf(f):
    """Decorador: valida que el token CSRF del formulario coincida con el de la sesión."""
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        token_form    = request.form.get('csrf_token', '')
        token_session = session.get('csrf_token', '')
        if not token_form or not token_session or not hmac.compare_digest(token_form, token_session):
            _log.warning("CSRF inválido rechazado")
            return Response("Solicitud inválida.", 403)
        return f(*args, **kwargs)
    return wrapper


@app.context_processor
def _inject_csrf():
    """Inyecta csrf_token en todos los templates automáticamente."""
    return {'csrf_token': _get_csrf_token()}


# ──────────────────────────────────────────────────────────────────────────────
# RUTAS
# ──────────────────────────────────────────────────────────────────────────────

def _obtener_tareas_hoy(conn):
    """Retorna las tareas de pre-producción del día de hoy."""
    hoy = datetime.date.today().isoformat()
    return [dict(r) for r in conn.execute("""
        SELECT id_tarea, descripcion, cantidad, completada, hora_completado, usuario
        FROM tareas_preproduccion
        WHERE fecha = ?
        ORDER BY completada ASC, id_tarea ASC
    """, (hoy,)).fetchall()]


def _obtener_datos():
    """Pedidos, almuerzos, inventario y estadísticas para la pantalla de cocina.
    Se cachea unos segundos para que varios celulares no saturen la base.
    """
    now = _time.monotonic()
    if _datos_cache['value'] is not None and now - _datos_cache['ts'] < _DATOS_TTL:
        return _datos_cache['value']
    with conexion_segura() as conn:
        result = _obtener_datos_conn(conn)
    _datos_cache['value'] = result
    _datos_cache['ts'] = now
    return result


def _invalidar_cache_datos():
    """Llama esto después de cualquier POST que modifique ordenes/almuerzos."""
    _datos_cache['value'] = None


def _obtener_datos_conn(conn):
    """Hace las consultas de _obtener_datos con una conexión ya abierta."""

    # Pedidos de venta
    pedidos_raw = conn.execute("""
        SELECT oc.*, v.mesa_numero as mesa_venta
        FROM ordenes_cocina oc
        LEFT JOIN ventas v ON oc.id_venta = v.id_venta
        WHERE oc.estado IN ('PENDIENTE', 'PREPARANDO', 'LISTO')
        ORDER BY
            CASE oc.estado
                WHEN 'PENDIENTE'  THEN 1
                WHEN 'PREPARANDO' THEN 2
                WHEN 'LISTO'      THEN 3
            END,
            oc.prioridad DESC,
            oc.hora_pedido ASC
    """).fetchall()

    por_venta = {}
    for p in pedidos_raw:
        vid = p['id_venta']
        if vid not in por_venta:
            por_venta[vid] = {
                'numero_venta': p['numero_venta'],
                'mesa_venta':   p['mesa_venta'],
                'items':        [],
                'ids':          [],
            }
        por_venta[vid]['items'].append(dict(p))
        por_venta[vid]['ids'].append(p['id_orden'])

    pedidos = []
    for vid, g in por_venta.items():
        estados = [i['estado'] for i in g['items']]
        estado_general = ('PENDIENTE'  if 'PENDIENTE'  in estados else
                          'PREPARANDO' if 'PREPARANDO' in estados else 'LISTO')
        try:
            hp = datetime.datetime.strptime(g['items'][0]['hora_pedido'], '%Y-%m-%d %H:%M:%S')
            mins = int((datetime.datetime.now() - hp).total_seconds() / 60)
        except Exception:
            mins = 0
        g['estado_general'] = estado_general
        g['mins'] = mins
        pedidos.append(g)

    # Almuerzos
    almuerzos_raw = conn.execute("""
        SELECT id_reserva, cliente_nombre, hora_entrega_estimada,
               cantidad_almuerzos, estado, tipo_almuerzo, notas
        FROM reservas_almuerzo
        WHERE estado IN ('RESERVADO', 'EN_PREPARACION', 'LISTO')
        ORDER BY
            CASE estado
                WHEN 'RESERVADO'      THEN 1
                WHEN 'EN_PREPARACION' THEN 2
                WHEN 'LISTO'          THEN 3
            END,
            hora_entrega_estimada ASC
    """).fetchall()

    almuerzos = []
    for a in almuerzos_raw:
        d = dict(a)
        try:
            d['hora_entrega'] = str(a['hora_entrega_estimada'])
        except Exception:
            d['hora_entrega'] = ''
        almuerzos.append(d)

    now_hm = _now_bogota().strftime('%H:%M')
    for d in almuerzos:
        try:
            d['urgente'] = bool(
                d['hora_entrega']
                and d['estado'] in ('RESERVADO', 'EN_PREPARACION')
                and str(d['hora_entrega'])[:5] < now_hm
            )
        except Exception:
            d['urgente'] = False

    # Inventario
    inventario_raw = conn.execute("""
        SELECT p.nombre, p.stock_actual
        FROM productos p
        LEFT JOIN categorias c ON p.id_categoria = c.id_categoria
        WHERE p.requiere_cocina = 1
           OR LOWER(COALESCE(c.nombre,'')) LIKE '%almuerzo%'
           OR LOWER(COALESCE(c.nombre,'')) LIKE '%comida%'
        ORDER BY p.nombre
    """).fetchall()
    inventario = [dict(i) for i in inventario_raw]

    # Capacidad
    cap_row = conn.execute("""
        SELECT COALESCE(SUM(p.stock_actual), 0) as total
        FROM productos p
        LEFT JOIN categorias c ON p.id_categoria = c.id_categoria
        WHERE p.requiere_cocina = 1
           OR LOWER(COALESCE(c.nombre,'')) LIKE '%almuerzo%'
    """).fetchone()
    capacidad = cap_row['total'] if cap_row else 0

    stats = {
        'pendientes':    sum(1 for p in pedidos_raw if p['estado'] == 'PENDIENTE'),
        'preparando':    sum(1 for p in pedidos_raw if p['estado'] == 'PREPARANDO'),
        'listos':        sum(1 for p in pedidos_raw if p['estado'] == 'LISTO'),
        'almuerzos':     len(almuerzos),
        'total_pedidos': len(pedidos),
        'alm_reservados':  sum(1 for a in almuerzos if a['estado'] == 'RESERVADO'),
        'alm_preparando':  sum(1 for a in almuerzos if a['estado'] == 'EN_PREPARACION'),
        'alm_listos':      sum(1 for a in almuerzos if a['estado'] == 'LISTO'),
    }

    return pedidos, almuerzos, inventario, capacidad, stats


@app.route('/')
@_require_auth
def index():
    """Pantalla principal de cocina (se refresca sola en el navegador)."""
    try:
        pedidos, almuerzos, inventario, capacidad, stats = _obtener_datos()
        with conexion_segura() as conn:
            tareas = _obtener_tareas_hoy(conn)
    except Exception as e:
        _log.error(f"cocina_web /index error: {e}")
        return "<h2>Error interno del servidor</h2>", 500

    hora = _now_bogota().strftime('%H:%M:%S')
    tareas_pendientes = sum(1 for t in tareas if not t['completada'])
    return render_template(
        'cocina.html',
        pedidos=pedidos,
        almuerzos=almuerzos,
        inventario=inventario,
        capacidad=capacidad,
        stats=stats,
        hora=hora,
        refresh_interval=_get_refresh_interval(),
        tareas=tareas,
        tareas_pendientes=tareas_pendientes,
    )


@app.route('/accion', methods=['POST'])
@_require_auth
@_require_csrf
def accion():
    """Cambia el estado de uno o varios pedidos (PREPARANDO → LISTO → ENTREGADO)."""
    _ESTADOS_VALIDOS = ('PREPARANDO', 'LISTO', 'ENTREGADO')
    ids_str    = request.form.get('ids', '')
    nuevo      = request.form.get('nuevo_estado', '')
    if not ids_str or not nuevo or nuevo not in _ESTADOS_VALIDOS:
        return redirect('/')

    ids = [int(x) for x in ids_str.split(',') if x.strip().isdigit()]
    try:
        with conexion_segura() as conn:
            for id_orden in ids:
                if nuevo == 'PREPARANDO':
                    conn.execute("""
                        UPDATE ordenes_cocina
                        SET estado = 'PREPARANDO',
                            hora_inicio = datetime('now','localtime'),
                            usuario_cocina = 'cocina_web'
                        WHERE id_orden = ?
                    """, (id_orden,))
                elif nuevo == 'LISTO':
                    conn.execute("""
                        UPDATE ordenes_cocina
                        SET estado = 'LISTO',
                            hora_listo = datetime('now','localtime'),
                            notificado_listo = 0
                        WHERE id_orden = ?
                    """, (id_orden,))
                    orden = conn.execute(
                        "SELECT id_detalle FROM ordenes_cocina WHERE id_orden = ?",
                        (id_orden,)
                    ).fetchone()
                    if orden:
                        conn.execute("""
                            UPDATE venta_detalle
                            SET estado_cocina = 'LISTO',
                                hora_listo = datetime('now','localtime')
                            WHERE id_detalle = ?
                        """, (orden['id_detalle'],))
                elif nuevo == 'ENTREGADO':
                    conn.execute("""
                        UPDATE ordenes_cocina
                        SET estado = 'ENTREGADO',
                            hora_entrega = datetime('now','localtime')
                        WHERE id_orden = ?
                    """, (id_orden,))
    except Exception as e:
        _log.error(f"cocina_web /accion error: {e}")
        return "<h2>Error interno del servidor</h2>", 500

    _invalidar_cache_datos()
    return redirect('/')


@app.route('/accion_almuerzo', methods=['POST'])
@_require_auth
@_require_csrf
def accion_almuerzo():
    """Cambia el estado de una reserva de almuerzo."""
    _ESTADOS_ALMUERZO_VALIDOS = ('RESERVADO', 'EN_PREPARACION', 'LISTO', 'ENTREGADO', 'CANCELADO')
    id_reserva = request.form.get('id_reserva')
    nuevo      = request.form.get('nuevo_estado', '').strip().upper()
    if not id_reserva or nuevo not in _ESTADOS_ALMUERZO_VALIDOS:
        return redirect('/')
    try:
        with conexion_segura() as conn:
            notif = 0 if nuevo == 'LISTO' else None
            if notif is not None:
                conn.execute("""
                    UPDATE reservas_almuerzo SET estado = ?, notificado_listo = ?
                    WHERE id_reserva = ?
                """, (nuevo, notif, int(id_reserva)))
            else:
                conn.execute("""
                    UPDATE reservas_almuerzo SET estado = ?
                    WHERE id_reserva = ?
                """, (nuevo, int(id_reserva)))
    except Exception as e:
        _log.error(f"cocina_web /accion_almuerzo error: {e}")
        return "<h2>Error interno del servidor</h2>", 500
    _invalidar_cache_datos()
    return redirect('/')


@app.route('/api/listos_pendientes')
@_require_auth
def api_listos_pendientes():
    """Devuelve pedidos en estado LISTO que aún no han sido notificados al POS.
    El POS hace polling a este endpoint cada 5 segundos."""
    try:
        with conexion_segura() as conn:
            ordenes = conn.execute("""
                SELECT id_orden, numero_venta, producto_nombre, cantidad,
                       mesa_numero, hora_listo
                FROM ordenes_cocina
                WHERE estado = 'LISTO' AND notificado_listo = 0
            """).fetchall()
            almuerzos = conn.execute("""
                SELECT id_reserva, cliente_nombre, cantidad_almuerzos,
                       tipo_almuerzo, hora_entrega_estimada
                FROM reservas_almuerzo
                WHERE estado = 'LISTO' AND notificado_listo = 0
            """).fetchall()
        return jsonify({
            'ok': True,
            'ordenes':   [dict(r) for r in ordenes],
            'almuerzos': [dict(r) for r in almuerzos],
        })
    except Exception as e:
        _log.error(f"cocina_web /api/listos_pendientes error: {e}")
        return jsonify({'ok': False, 'error': 'Error interno del servidor'}), 500


@app.route('/api/marcar_notificado', methods=['POST'])
@_require_auth
@_require_csrf
def api_marcar_notificado():
    """No-op: el POS es el único autorizado a marcar notificado_listo.
    Si cocina_web lo marcara primero, el cajero perdería el aviso.
    El endpoint se conserva por compatibilidad de URL."""
    return jsonify({'ok': True})


@app.route('/api/tareas')
@_require_auth
def api_tareas():
    """Devuelve las tareas de pre-producción del día."""
    try:
        with conexion_segura() as conn:
            tareas = _obtener_tareas_hoy(conn)
        return jsonify({'ok': True, 'tareas': tareas})
    except Exception as e:
        _log.error(f"cocina_web /api/tareas error: {e}")
        return jsonify({'ok': False, 'error': 'Error interno del servidor'}), 500


@app.route('/api/tarea_completar', methods=['POST'])
@_require_auth
@_require_csrf
def api_tarea_completar():
    """Marca o desmarca una tarea de pre-producción."""
    id_tarea   = request.form.get('id_tarea', '')
    completada = request.form.get('completada', '0')
    if not id_tarea.isdigit():
        return redirect('/')
    completada_val = 1 if completada == '1' else 0
    try:
        with conexion_segura() as conn:
            if completada_val:
                conn.execute("""
                    UPDATE tareas_preproduccion
                    SET completada = 1, hora_completado = datetime('now','localtime')
                    WHERE id_tarea = ?
                """, (int(id_tarea),))
            else:
                conn.execute("""
                    UPDATE tareas_preproduccion
                    SET completada = 0, hora_completado = NULL
                    WHERE id_tarea = ?
                """, (int(id_tarea),))
    except Exception as e:
        _log.error(f"cocina_web /api/tarea_completar error: {e}")
        return "<h2>Error interno del servidor</h2>", 500
    return redirect('/#tab-preproduccion')


@app.route('/api/tarea_nueva', methods=['POST'])
@_require_auth
@_require_csrf
def api_tarea_nueva():
    """Crea una nueva tarea de pre-producción para hoy."""
    descripcion = request.form.get('descripcion', '').strip()
    cantidad    = request.form.get('cantidad', '').strip()
    if not descripcion:
        return redirect('/')
    hoy = datetime.date.today().isoformat()
    try:
        with conexion_segura() as conn:
            conn.execute("""
                INSERT INTO tareas_preproduccion (fecha, descripcion, cantidad, completada)
                VALUES (?, ?, ?, 0)
            """, (hoy, descripcion[:200], cantidad[:50] if cantidad else None))
    except Exception as e:
        _log.error(f"cocina_web /api/tarea_nueva error: {e}")
        return "<h2>Error interno del servidor</h2>", 500
    return redirect('/')


@app.route('/api/estado')
@_require_auth
def api_estado():
    """Endpoint JSON para integraciones futuras"""
    try:
        pedidos, almuerzos, inventario, capacidad, stats = _obtener_datos()
        return jsonify({'ok': True, 'stats': stats})
    except Exception as e:
        _log.error(f"cocina_web /api/estado error: {e}")
        return jsonify({'ok': False, 'error': 'Error interno del servidor'}), 500


# ──────────────────────────────────────────────────────────────────────────────
# PUNTO DE ENTRADA
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    import socket

    # Mostrar IP local para que el usuario sepa a qué conectarse
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip_local = s.getsockname()[0]
        s.close()
    except Exception:
        ip_local = '127.0.0.1'

    print("=" * 55)
    print("  COCINA WEB — Club Los Pocitos Azufrados")
    print("=" * 55)
    print(f"  Desde este computador:  http://localhost:5000")
    print(f"  Desde celular/tablet:   http://{ip_local}:5000")
    print(f"  (el celular debe estar en la misma red WiFi)")
    print("=" * 55)
    print("  Presiona Ctrl+C para detener")
    print()

    app.run(host='0.0.0.0', port=5000, debug=False)
