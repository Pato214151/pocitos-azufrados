"""
Módulo de Cocina - Club Los Pocitos Azufrados
Pantalla para el personal de cocina con pestañas:
  - Pedidos de Venta (ordenes_cocina)
  - Almuerzos (reservas_almuerzo)
  - Inventario
Se actualiza automáticamente cada 10 segundos.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import os, sys, datetime, threading

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from utils.tema_corporativo import COLORES, FUENTES, crear_boton
from database.connection import get_connection, conexion_segura


class CocinaModule:
    """Pantalla de cocina en el PC: pedidos y almuerzos, con refresco automático."""
    REFRESH_MS = 10000  # 10 segundos

    NOTIF_MS = 5000   # polling de listos cada 5 s

    def __init__(self, parent, usuario):
        self.parent = parent
        self.usuario = usuario
        self.auto_refresh = True
        self._after_id = None
        self._notif_after_id = None
        self._crear_interfaz()
        self._cargar_pedidos()
        self._iniciar_auto_refresh()
        self._iniciar_polling_listos()

    # ──────────────────────────────────────────────────────────────────────
    # INTERFAZ
    # ──────────────────────────────────────────────────────────────────────

    def _crear_interfaz(self):
        """Arma las pestañas de pedidos, almuerzos e inventario de cocina."""
        # ── Header ───────────────────────────────────────────────────────
        header = tk.Frame(self.parent, bg=COLORES['primario'])
        header.pack(fill='x')

        inner = tk.Frame(header, bg=COLORES['primario'], padx=15, pady=10)
        inner.pack(fill='x')

        tk.Label(inner, text="COCINA — Gestión de Pedidos",
                 font=FUENTES['encabezado'], fg=COLORES['texto_claro'],
                 bg=COLORES['primario']).pack(side='left')

        self.lbl_hora = tk.Label(inner, text="",
                                  font=FUENTES['normal_bold'],
                                  fg=COLORES['acento'], bg=COLORES['primario'])
        self.lbl_hora.pack(side='right')

        # ── Barra de contadores ──────────────────────────────────────────
        bar = tk.Frame(self.parent, bg=COLORES['fondo'], padx=12, pady=8)
        bar.pack(fill='x')

        self.lbl_pendientes = tk.Label(bar, text="Pendientes: 0",
                                        font=FUENTES['normal_bold'],
                                        fg=COLORES['error'], bg=COLORES['fondo'])
        self.lbl_pendientes.pack(side='left', padx=8)

        self.lbl_preparando = tk.Label(bar, text="Preparando: 0",
                                        font=FUENTES['normal_bold'],
                                        fg=COLORES['advertencia'], bg=COLORES['fondo'])
        self.lbl_preparando.pack(side='left', padx=8)

        self.lbl_listos = tk.Label(bar, text="Listos: 0",
                                    font=FUENTES['normal_bold'],
                                    fg=COLORES['exito'], bg=COLORES['fondo'])
        self.lbl_listos.pack(side='left', padx=8)

        self.lbl_almuerzos = tk.Label(bar, text="Almuerzos activos: 0",
                                       font=FUENTES['normal_bold'],
                                       fg=COLORES['info'], bg=COLORES['fondo'])
        self.lbl_almuerzos.pack(side='left', padx=8)

        crear_boton(bar, "Refrescar", self._cargar_pedidos,
                    tipo='secundario').pack(side='right', padx=4)

        # ── Notebook de pestañas ─────────────────────────────────────────
        style = ttk.Style()
        style.configure('Cocina.TNotebook', background=COLORES['fondo'],
                         tabposition='n', borderwidth=0)
        style.configure('Cocina.TNotebook.Tab',
                         font=FUENTES['normal_bold'],
                         padding=[18, 8],
                         background=COLORES['gris_200'],
                         foreground=COLORES['texto_secundario'])
        style.map('Cocina.TNotebook.Tab',
                  background=[('selected', COLORES['primario'])],
                  foreground=[('selected', COLORES['texto_claro'])])

        self.notebook = ttk.Notebook(self.parent, style='Cocina.TNotebook')
        self.notebook.pack(fill='both', expand=True, padx=8, pady=4)

        # ── Pestaña 1: Pedidos de venta ──────────────────────────────────
        tab_pedidos = tk.Frame(self.notebook, bg=COLORES['fondo'])
        self.notebook.add(tab_pedidos, text=" Pedidos de Venta ")

        canvas_v = tk.Canvas(tab_pedidos, bg=COLORES['fondo'], highlightthickness=0)
        sb_v = ttk.Scrollbar(tab_pedidos, orient='vertical', command=canvas_v.yview)
        self.pedidos_frame = tk.Frame(canvas_v, bg=COLORES['fondo'])

        self.pedidos_frame.bind(
            '<Configure>',
            lambda e: canvas_v.configure(scrollregion=canvas_v.bbox('all'))
        )
        canvas_v.create_window((0, 0), window=self.pedidos_frame, anchor='nw')
        canvas_v.configure(yscrollcommand=sb_v.set)

        sb_v.pack(side='right', fill='y')
        canvas_v.pack(side='left', fill='both', expand=True)

        canvas_v.bind_all('<MouseWheel>',
                           lambda e: canvas_v.yview_scroll(int(-1*(e.delta/120)), 'units'))

        # ── Pestaña 2: Almuerzos (reservas) ─────────────────────────────
        tab_almuerzos = tk.Frame(self.notebook, bg=COLORES['fondo'])
        self.notebook.add(tab_almuerzos, text=" Almuerzos ")

        # Indicador de capacidad arriba
        self.lbl_capacidad = tk.Label(tab_almuerzos,
                                       text="Capacidad disponible: —",
                                       font=FUENTES['normal_bold'],
                                       fg=COLORES['primario'], bg=COLORES['fondo'])
        self.lbl_capacidad.pack(anchor='w', padx=12, pady=(8, 4))

        canvas_a = tk.Canvas(tab_almuerzos, bg=COLORES['fondo'], highlightthickness=0)
        sb_a = ttk.Scrollbar(tab_almuerzos, orient='vertical', command=canvas_a.yview)
        self.almuerzos_frame = tk.Frame(canvas_a, bg=COLORES['fondo'])

        self.almuerzos_frame.bind(
            '<Configure>',
            lambda e: canvas_a.configure(scrollregion=canvas_a.bbox('all'))
        )
        canvas_a.create_window((0, 0), window=self.almuerzos_frame, anchor='nw')
        canvas_a.configure(yscrollcommand=sb_a.set)

        sb_a.pack(side='right', fill='y')
        canvas_a.pack(side='left', fill='both', expand=True)

        # ── Pestaña 3: Inventario ────────────────────────────────────────
        tab_inv = tk.Frame(self.notebook, bg=COLORES['fondo'])
        self.notebook.add(tab_inv, text=" Inventario Cocina ")

        canvas_i = tk.Canvas(tab_inv, bg=COLORES['fondo'], highlightthickness=0)
        sb_i = ttk.Scrollbar(tab_inv, orient='vertical', command=canvas_i.yview)
        self.inventory_frame = tk.Frame(canvas_i, bg=COLORES['fondo'])

        self.inventory_frame.bind(
            '<Configure>',
            lambda e: canvas_i.configure(scrollregion=canvas_i.bbox('all'))
        )
        canvas_i.create_window((0, 0), window=self.inventory_frame, anchor='nw')
        canvas_i.configure(yscrollcommand=sb_i.set)

        sb_i.pack(side='right', fill='y')
        canvas_i.pack(side='left', fill='both', expand=True)

    # ──────────────────────────────────────────────────────────────────────
    # CARGA DE DATOS
    # ──────────────────────────────────────────────────────────────────────

    def _cargar_pedidos(self):
        for w in self.pedidos_frame.winfo_children():
            w.destroy()
        for w in self.almuerzos_frame.winfo_children():
            w.destroy()
        for w in self.inventory_frame.winfo_children():
            w.destroy()

        self.lbl_hora.config(text=datetime.datetime.now().strftime("%H:%M:%S"))

        conn = None
        try:
            conn = get_connection()

            # ── Pedidos de venta (ordenes_cocina) — solo hoy ─────────────
            pedidos = conn.execute("""
                SELECT oc.*, v.mesa_numero as mesa_venta
                FROM ordenes_cocina oc
                LEFT JOIN ventas v ON oc.id_venta = v.id_venta
                WHERE oc.estado IN ('PENDIENTE', 'PREPARANDO', 'LISTO')
                  AND DATE(oc.hora_pedido) = DATE('now','localtime')
                ORDER BY
                    CASE oc.estado
                        WHEN 'PENDIENTE'  THEN 1
                        WHEN 'PREPARANDO' THEN 2
                        WHEN 'LISTO'      THEN 3
                    END,
                    oc.prioridad DESC,
                    oc.hora_pedido ASC
            """).fetchall()

            # Agrupar por venta
            por_venta = {}
            for p in pedidos:
                vid = p['id_venta']
                if vid not in por_venta:
                    por_venta[vid] = {'venta_info': p, 'items': []}
                por_venta[vid]['items'].append(p)

            pendientes = sum(1 for p in pedidos if p['estado'] == 'PENDIENTE')
            preparando = sum(1 for p in pedidos if p['estado'] == 'PREPARANDO')
            listos     = sum(1 for p in pedidos if p['estado'] == 'LISTO')

            self.lbl_pendientes.config(text=f"Pendientes: {pendientes}")
            self.lbl_preparando.config(text=f"Preparando: {preparando}")
            self.lbl_listos.config(text=f"Listos: {listos}")

            if not por_venta:
                tk.Label(self.pedidos_frame,
                         text="No hay pedidos pendientes",
                         font=FUENTES['subtitulo'], fg=COLORES['exito'],
                         bg=COLORES['fondo']).grid(row=0, column=0, columnspan=2, pady=60)
            else:
                cols = 2
                for i, (vid, grupo) in enumerate(por_venta.items()):
                    r, c = divmod(i, cols)
                    self._crear_tarjeta_pedido(self.pedidos_frame, grupo, r, c)

            # ── Inventario cocina ────────────────────────────────────────
            inventario = conn.execute("""
                SELECT p.nombre, p.stock_actual, c.nombre as categoria
                FROM productos p
                LEFT JOIN categorias c ON p.id_categoria = c.id_categoria
                WHERE (p.requiere_cocina = 1 OR LOWER(COALESCE(c.nombre,'')) LIKE '%almuerzo%'
                                              OR LOWER(COALESCE(c.nombre,'')) LIKE '%comida%')
                ORDER BY p.nombre
            """).fetchall()

            if inventario:
                for item in inventario:
                    self._crear_fila_inventario(self.inventory_frame, item)
            else:
                tk.Label(self.inventory_frame,
                         text="Sin productos de cocina registrados",
                         font=FUENTES['pequena'], fg=COLORES['texto_secundario'],
                         bg=COLORES['fondo']).pack(padx=12, pady=12)

            # ── Almuerzos (reservas) — solo hoy ─────────────────────────
            almuerzos = conn.execute("""
                SELECT id_reserva, cliente_nombre, hora_reserva,
                       hora_entrega_estimada, cantidad_almuerzos, estado,
                       tipo_almuerzo, notas
                FROM reservas_almuerzo
                WHERE estado IN ('RESERVADO', 'EN_PREPARACION', 'LISTO')
                  AND DATE(hora_reserva) = DATE('now','localtime')
                ORDER BY
                    CASE estado
                        WHEN 'RESERVADO'      THEN 1
                        WHEN 'EN_PREPARACION' THEN 2
                        WHEN 'LISTO'          THEN 3
                    END,
                    hora_entrega_estimada ASC
            """).fetchall()

            cap_row = conn.execute("""
                SELECT COALESCE(SUM(p.stock_actual), 0) as total
                FROM productos p
                LEFT JOIN categorias c ON p.id_categoria = c.id_categoria
                WHERE p.requiere_cocina = 1
                   OR LOWER(COALESCE(c.nombre,'')) LIKE '%almuerzo%'
            """).fetchone()

            capacidad = cap_row['total'] if cap_row else 0
            self.lbl_capacidad.config(
                text=f"Capacidad disponible: {capacidad} porciones"
            )
            alm_listos = sum(1 for a in almuerzos if a['estado'] == 'LISTO')
            alm_txt = f"Almuerzos: {len(almuerzos)}"
            if alm_listos:
                alm_txt += f"  |  LISTOS: {alm_listos}"
            self.lbl_almuerzos.config(text=alm_txt)

            # Checklist por reserva (solo EN_PREPARACION)
            checklist_por_reserva = {}
            for alm in almuerzos:
                if alm['estado'] == 'EN_PREPARACION':
                    items = conn.execute("""
                        SELECT id, descripcion, completado
                        FROM reserva_checklist
                        WHERE id_reserva = ?
                        ORDER BY id ASC
                    """, (alm['id_reserva'],)).fetchall()
                    checklist_por_reserva[alm['id_reserva']] = list(items)

            if almuerzos:
                for alm in almuerzos:
                    alm_dict = dict(alm)
                    checklist = checklist_por_reserva.get(alm_dict['id_reserva'], [])
                    self._crear_tarjeta_almuerzo(self.almuerzos_frame, alm_dict, checklist)
            else:
                tk.Label(self.almuerzos_frame,
                         text="Sin pedidos de almuerzo activos",
                         font=FUENTES['normal'], fg=COLORES['exito'],
                         bg=COLORES['fondo']).pack(pady=40)

        except Exception as e:
            tk.Label(self.pedidos_frame, text=f"Error: {e}",
                     font=FUENTES['normal'], fg=COLORES['error'],
                     bg=COLORES['fondo']).grid(row=99, column=0, columnspan=2, pady=20)
        finally:
            if conn:
                conn.close()

    # ──────────────────────────────────────────────────────────────────────
    # TARJETAS
    # ──────────────────────────────────────────────────────────────────────

    def _crear_tarjeta_pedido(self, parent, grupo, fila, columna):
        """Tarjeta de un pedido con sus productos y botones de estado."""
        items  = grupo['items']
        venta  = grupo['venta_info']
        estados = [i['estado'] for i in items]
        estado  = ('PENDIENTE'  if 'PENDIENTE'  in estados else
                   'PREPARANDO' if 'PREPARANDO' in estados else 'LISTO')

        estilos = {
            'PENDIENTE':  {'bg': COLORES['cocina_pendiente'],  'border': '#FF9800', 'label': 'PENDIENTE'},
            'PREPARANDO': {'bg': COLORES['cocina_preparando'], 'border': '#2196F3', 'label': 'PREPARANDO'},
            'LISTO':      {'bg': COLORES['cocina_listo'],      'border': '#4CAF50', 'label': 'LISTO'},
        }
        est = estilos.get(estado, estilos['PENDIENTE'])

        card = tk.Frame(parent, bg=est['bg'],
                        highlightbackground=est['border'], highlightthickness=3,
                        padx=12, pady=10)
        card.grid(row=fila, column=columna, padx=8, pady=8, sticky='nsew')
        parent.columnconfigure(columna, weight=1)

        # Estado + número de venta
        top = tk.Frame(card, bg=est['bg'])
        top.pack(fill='x')
        tk.Label(top, text=est['label'],
                 font=FUENTES['normal_bold'], fg=est['border'],
                 bg=est['bg']).pack(side='left')
        tk.Label(top, text=f"  #{venta['numero_venta']}",
                 font=FUENTES['encabezado'], fg=COLORES['texto'],
                 bg=est['bg']).pack(side='left')

        # Mesa
        if venta['mesa_venta']:
            tk.Label(card, text=f"Mesa {venta['mesa_venta']}",
                     font=FUENTES['normal_bold'], fg=COLORES['primario'],
                     bg=est['bg']).pack(anchor='w', pady=(4, 0))

        tk.Frame(card, height=1, bg=COLORES['borde']).pack(fill='x', pady=6)

        # Items
        for item in items:
            icono = {'PENDIENTE': '—', 'PREPARANDO': '...', 'LISTO': 'OK'}.get(item['estado'], '')
            tk.Label(card,
                     text=f"{icono}  {item['producto_nombre']}  x{item['cantidad']}",
                     font=FUENTES['normal_bold'], fg=COLORES['texto'],
                     bg=est['bg'], wraplength=260, anchor='w').pack(anchor='w', pady=1)
            if item['notas']:
                tk.Label(card, text=f"   Nota: {item['notas']}",
                         font=FUENTES['pequena'], fg=COLORES['error'],
                         bg=est['bg'], wraplength=260).pack(anchor='w')

        # Tiempo
        try:
            hp = datetime.datetime.strptime(items[0]['hora_pedido'], '%Y-%m-%d %H:%M:%S')
            mins = int((datetime.datetime.now() - hp).total_seconds() / 60)
            color_t = (COLORES['error'] if mins > 15 else
                       COLORES['advertencia'] if mins > 8 else
                       COLORES['texto_secundario'])
            tk.Label(card, text=f"Hace {mins} min",
                     font=FUENTES['pequena'], fg=color_t,
                     bg=est['bg']).pack(anchor='w', pady=(6, 2))
        except Exception:
            pass

        # Botón de acción
        acciones = {
            'PENDIENTE':  ('Preparar', 'PREPARANDO', 'advertencia'),
            'PREPARANDO': ('Listo',    'LISTO',      'exito'),
            'LISTO':      ('Entregado','ENTREGADO',  'primario'),
        }
        if estado in acciones:
            txt, nuevo, tipo = acciones[estado]
            crear_boton(card, txt,
                        lambda its=items, ne=nuevo: self._cambiar_estado_multiples(its, ne),
                        tipo=tipo).pack(fill='x', pady=(6, 0))

    def _crear_tarjeta_almuerzo(self, parent, alm, checklist=None):
        """Tarjeta de una reserva de almuerzo con botones de estado."""
        estilos = {
            'RESERVADO':      {'bg': COLORES['cocina_pendiente'],  'border': '#FF9800', 'label': 'RESERVADO'},
            'EN_PREPARACION': {'bg': COLORES['cocina_preparando'], 'border': '#2196F3', 'label': 'EN PREPARACION'},
        }
        est = estilos.get(alm['estado'], estilos['RESERVADO'])

        card = tk.Frame(parent, bg=est['bg'],
                        highlightbackground=est['border'], highlightthickness=2,
                        padx=12, pady=10)
        card.pack(fill='x', padx=10, pady=4)

        # Fila superior: estado + hora
        top_row = tk.Frame(card, bg=est['bg'])
        top_row.pack(fill='x')
        tk.Label(top_row, text=est['label'],
                 font=FUENTES['normal_bold'], fg=est['border'],
                 bg=est['bg']).pack(side='left')

        try:
            hora_str = str(alm['hora_entrega_estimada'])[:5]
        except Exception:
            hora_str = str(alm['hora_entrega_estimada'])
        tk.Label(top_row, text=f"  Entrega: {hora_str}",
                 font=FUENTES['normal_bold'], fg=COLORES['texto'],
                 bg=est['bg']).pack(side='left')

        # Nombre cliente grande
        tk.Label(card, text=alm['cliente_nombre'],
                 font=FUENTES['encabezado'], fg=COLORES['texto'],
                 bg=est['bg']).pack(anchor='w', pady=(4, 0))

        # Tipo almuerzo + cantidad — lo más importante para cocina
        tipo = alm.get('tipo_almuerzo') or 'Almuerzo'
        cant = alm['cantidad_almuerzos']
        tk.Label(card, text=f"{tipo}  x{cant}",
                 font=FUENTES['subtitulo'], fg=COLORES['primario'],
                 bg=est['bg']).pack(anchor='w', pady=(2, 0))

        # Notas / observaciones
        if alm.get('notas'):
            tk.Label(card, text=f"Obs: {alm['notas']}",
                     font=FUENTES['pequena'], fg=COLORES['error'],
                     bg=est['bg'], wraplength=260, justify='left').pack(anchor='w', pady=(4, 0))

        # ── Checklist de preparacion (solo EN_PREPARACION) ───────────────
        if alm['estado'] == 'EN_PREPARACION' and checklist:
            tk.Frame(card, height=1, bg=COLORES['borde']).pack(fill='x', pady=(8, 4))

            completados = sum(1 for it in checklist if it['completado'])
            total = len(checklist)
            prog_color = COLORES['exito'] if completados == total else COLORES['advertencia']

            tk.Label(card, text=f"Preparacion: {completados}/{total}",
                     font=FUENTES['pequena'], fg=prog_color,
                     bg=est['bg']).pack(anchor='w', pady=(0, 4))

            check_frame = tk.Frame(card, bg=est['bg'])
            check_frame.pack(fill='x', padx=4)

            for it in checklist:
                var = tk.IntVar(value=it['completado'])
                color_cb = COLORES['exito'] if it['completado'] else COLORES['texto']
                cb = tk.Checkbutton(
                    check_frame,
                    text=it['descripcion'],
                    variable=var,
                    font=FUENTES['pequena'],
                    fg=color_cb,
                    bg=est['bg'],
                    activebackground=est['bg'],
                    selectcolor=est['bg'],
                    command=lambda v=var, iid=it['id']: self._toggle_checklist_item(iid, v.get()),
                    takefocus=0
                )
                cb.pack(anchor='w')

        btn_frame = tk.Frame(card, bg=est['bg'])
        btn_frame.pack(fill='x', pady=(8, 0))

        if alm['estado'] == 'RESERVADO':
            crear_boton(btn_frame, "Iniciar Preparacion",
                       lambda a=alm: self._cambiar_estado_almuerzo(
                           a['id_reserva'], 'EN_PREPARACION', a.get('tipo_almuerzo', '')),
                       tipo='advertencia').pack(side='left')
        elif alm['estado'] == 'EN_PREPARACION':
            crear_boton(btn_frame, "Listo para entregar",
                       lambda a=alm: self._cambiar_estado_almuerzo(a['id_reserva'], 'LISTO'),
                       tipo='exito').pack(side='left')
        elif alm['estado'] == 'LISTO':
            crear_boton(btn_frame, "Marcar Entregado",
                       lambda a=alm: self._cambiar_estado_almuerzo(a['id_reserva'], 'ENTREGADO'),
                       tipo='primario').pack(side='left')

    def _crear_fila_inventario(self, parent, item):
        fila = tk.Frame(parent, bg=COLORES['fondo_card'],
                        highlightbackground=COLORES['borde'], highlightthickness=1,
                        padx=10, pady=8)
        fila.pack(fill='x', padx=12, pady=3)

        tk.Label(fila, text=item['nombre'],
                 font=FUENTES['normal_bold'], fg=COLORES['texto'],
                 bg=COLORES['fondo_card']).pack(side='left')

        stock = item['stock_actual'] or 0
        color = (COLORES['error']     if stock < 5  else
                 COLORES['advertencia'] if stock < 10 else
                 COLORES['exito'])
        tk.Label(fila, text=f"Stock: {stock}",
                 font=FUENTES['normal_bold'], fg=color,
                 bg=COLORES['fondo_card']).pack(side='right')

    # ──────────────────────────────────────────────────────────────────────
    # ACCIONES
    # ──────────────────────────────────────────────────────────────────────

    def _cambiar_estado_multiples(self, items, nuevo_estado):
        try:
            with conexion_segura() as conn:
                for item in items:
                    self._actualizar_orden_cocina(conn, item['id_orden'], nuevo_estado)
            self._cargar_pedidos()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _actualizar_orden_cocina(self, conn, id_orden, nuevo_estado):
        if nuevo_estado == 'PREPARANDO':
            conn.execute("""
                UPDATE ordenes_cocina
                SET estado = 'PREPARANDO',
                    hora_inicio = datetime('now','localtime'),
                    usuario_cocina = ?
                WHERE id_orden = ?
            """, (self.usuario['nombre_completo'], id_orden))

        elif nuevo_estado == 'LISTO':
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

        elif nuevo_estado == 'ENTREGADO':
            conn.execute("""
                UPDATE ordenes_cocina
                SET estado = 'ENTREGADO',
                    hora_entrega = datetime('now','localtime')
                WHERE id_orden = ?
            """, (id_orden,))

    def _cambiar_estado_almuerzo(self, id_reserva, nuevo_estado, tipo_almuerzo=''):
        try:
            with conexion_segura() as conn:
                if nuevo_estado == 'LISTO':
                    conn.execute("""
                        UPDATE reservas_almuerzo SET estado = ?, notificado_listo = 0
                        WHERE id_reserva = ?
                    """, (nuevo_estado, id_reserva))
                else:
                    conn.execute("""
                        UPDATE reservas_almuerzo SET estado = ?
                        WHERE id_reserva = ?
                    """, (nuevo_estado, id_reserva))

                if nuevo_estado == 'EN_PREPARACION':
                    existe = conn.execute(
                        "SELECT COUNT(*) FROM reserva_checklist WHERE id_reserva = ?",
                        (id_reserva,)
                    ).fetchone()[0]
                    if existe == 0:
                        tipo = (tipo_almuerzo or '').strip()
                        items = conn.execute("""
                            SELECT descripcion FROM almuerzo_checklist_template
                            WHERE tipo_almuerzo = ?
                            ORDER BY orden ASC
                        """, (tipo,)).fetchall()
                        if not items:
                            items = conn.execute("""
                                SELECT descripcion FROM almuerzo_checklist_template
                                WHERE tipo_almuerzo = 'General'
                                ORDER BY orden ASC
                            """).fetchall()
                        for it in items:
                            conn.execute("""
                                INSERT INTO reserva_checklist (id_reserva, descripcion, completado)
                                VALUES (?, ?, 0)
                            """, (id_reserva, it['descripcion']))

            self._cargar_pedidos()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _toggle_checklist_item(self, id_item, nuevo_valor):
        try:
            with conexion_segura() as conn:
                if nuevo_valor:
                    conn.execute("""
                        UPDATE reserva_checklist
                        SET completado = 1, hora_completado = datetime('now','localtime')
                        WHERE id = ?
                    """, (id_item,))
                else:
                    conn.execute("""
                        UPDATE reserva_checklist
                        SET completado = 0, hora_completado = NULL
                        WHERE id = ?
                    """, (id_item,))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ──────────────────────────────────────────────────────────────────────
    # AUTO-REFRESH
    # ──────────────────────────────────────────────────────────────────────

    def _iniciar_auto_refresh(self):
        if self.auto_refresh:
            try:
                if self.parent.winfo_exists():
                    self._after_id = self.parent.after(
                        self.REFRESH_MS, self._tick_refresh)
            except Exception:
                pass

    def _tick_refresh(self):
        if not self.auto_refresh:
            return
        try:
            if self.parent.winfo_exists():
                self._cargar_pedidos()
                self._after_id = self.parent.after(
                    self.REFRESH_MS, self._tick_refresh)
        except Exception:
            pass

    # ──────────────────────────────────────────────────────────────────────
    # NOTIFICACIONES DE PEDIDOS LISTOS (marcados desde cocina web)
    # ──────────────────────────────────────────────────────────────────────

    def _iniciar_polling_listos(self):
        if self.auto_refresh:
            try:
                if self.parent.winfo_exists():
                    self._notif_after_id = self.parent.after(
                        self.NOTIF_MS, self._tick_listos)
            except Exception:
                pass

    def _tick_listos(self):
        if not self.auto_refresh:
            return
        try:
            if self.parent.winfo_exists():
                self._verificar_listos_web()
                self._notif_after_id = self.parent.after(
                    self.NOTIF_MS, self._tick_listos)
        except Exception:
            pass

    def _verificar_listos_web(self):
        """Consulta la BD buscando pedidos marcados LISTO desde cocina web
        (notificado_listo = 0). Si hay, muestra popup y beep, luego marca
        notificado_listo = 1 para no repetir la alerta."""
        try:
            with conexion_segura() as conn:
                ordenes = conn.execute("""
                    SELECT id_orden, numero_venta, producto_nombre, cantidad, mesa_numero
                    FROM ordenes_cocina
                    WHERE estado = 'LISTO' AND notificado_listo = 0
                """).fetchall()
                almuerzos = conn.execute("""
                    SELECT id_reserva, cliente_nombre, cantidad_almuerzos, tipo_almuerzo
                    FROM reservas_almuerzo
                    WHERE estado = 'LISTO' AND notificado_listo = 0
                """).fetchall()

                if not ordenes and not almuerzos:
                    return

                # Marcar como notificados antes de mostrar el popup
                for o in ordenes:
                    conn.execute(
                        "UPDATE ordenes_cocina SET notificado_listo = 1 WHERE id_orden = ?",
                        (o['id_orden'],)
                    )
                for a in almuerzos:
                    conn.execute(
                        "UPDATE reservas_almuerzo SET notificado_listo = 1 WHERE id_reserva = ?",
                        (a['id_reserva'],)
                    )

            # Beep en hilo aparte para no bloquear la UI
            threading.Thread(target=self._beep, daemon=True).start()

            # Construir mensaje
            lineas = []
            for o in ordenes:
                mesa = f"  Mesa {o['mesa_numero']}" if o['mesa_numero'] else ""
                lineas.append(f"  #{o['numero_venta']}{mesa}: {o['producto_nombre']} x{o['cantidad']}")
            for a in almuerzos:
                lineas.append(f"  Almuerzo — {a['cliente_nombre']}: {a['tipo_almuerzo'] or 'Almuerzo'} x{a['cantidad_almuerzos']}")

            msg = "LISTO para retirar:\n\n" + "\n".join(lineas)
            messagebox.showinfo("Pedido Listo", msg)

        except Exception:
            pass

    @staticmethod
    def _beep():
        """Emite un beep de aviso. Funciona en Windows; silencioso en otros sistemas."""
        try:
            import winsound
            winsound.Beep(1000, 400)
            import time as _t; _t.sleep(0.15)
            winsound.Beep(1000, 400)
        except Exception:
            pass

    def detener(self):
        self.auto_refresh = False
        if self._after_id is not None:
            try:
                self.parent.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None
        if self._notif_after_id is not None:
            try:
                self.parent.after_cancel(self._notif_after_id)
            except Exception:
                pass
            self._notif_after_id = None
        try:
            self.parent.winfo_toplevel().unbind_all('<MouseWheel>')
            self.parent.winfo_toplevel().unbind_all('<Button-4>')
            self.parent.winfo_toplevel().unbind_all('<Button-5>')
        except Exception:
            pass
