"""
Dashboard Principal - Club Los Pocitos Azufrados
Panel de administración - Sidebar doble (iconos + texto) + KPI cards modernas
"""

import tkinter as tk
from tkinter import ttk, messagebox
import logging
import os
import sys
import datetime
import time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from utils.tema_corporativo import (
    COLORES, FUENTES, SCALE, SCREEN_W, SCREEN_H,
    crear_boton, crear_tarjeta_kpi, format_money,
    aplicar_estilo_tabla, crear_separador
)
from database.connection import conexion_segura


class Dashboard:
    """Ventana principal del administrador: menú lateral con todos los módulos,
    KPIs del día y bloqueo automático por inactividad.
    """
    def __init__(self, login_root, usuario_data):
        self.login_root = login_root
        self.usuario = usuario_data
        self.modulo_actual = None
        self._instancia_modulo = None
        self._icon_btns = {}   # nombre -> (btn_icon, active_bar)
        self._text_btns = {}   # nombre -> btn_text
        self._badge_stock_label = None  # badge rojo de stock bajo en sidebar

        self.root = tk.Toplevel()
        self.root.title(f"Los Pocitos Azufrados - {usuario_data['nombre_completo']}")
        self.root.configure(bg=COLORES['fondo'])

        try:
            self.root.state('zoomed')
        except Exception:
            w = max(900, int(1400 * SCALE))
            h = max(600, int(900 * SCALE))
            self.root.geometry(f"{w}x{h}")

        self.root.minsize(max(900, int(900 * SCALE)), max(600, int(600 * SCALE)))
        self.root.protocol("WM_DELETE_WINDOW", self._cerrar)

        # Auto-bloqueo de pantalla por inactividad
        self._ultimo_evento = time.time()
        self._bloqueo_activo = False
        self._after_bloqueo_id = None

        # Capturar CUALQUIER excepción en callbacks de Tkinter y mostrarla/loguearla
        def _tk_error_handler(exc_type, exc_value, exc_tb):
            import traceback, logging
            msg = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
            logging.getLogger("pocitos").error(f"Error en callback Tkinter:\n{msg}")
            try:
                for w in self.content_frame.winfo_children():
                    w.destroy()
                tk.Label(self.content_frame,
                         text=f"Error:\n{exc_value}",
                         font=FUENTES['normal'], fg=COLORES['error'],
                         bg=COLORES['fondo']).pack(pady=50)
            except Exception:
                pass
        self.root.report_callback_exception = _tk_error_handler

        self._crear_interfaz()
        self._cargar_dashboard()
        self._actualizar_badge_stock()

        # Registrar actividad en eventos de mouse y teclado
        self.root.bind_all('<Motion>', self._registrar_actividad)
        self.root.bind_all('<KeyPress>', self._registrar_actividad)
        self.root.bind_all('<Button>', self._registrar_actividad)
        self._programar_verificacion_bloqueo()

    # ==============================================================
    #  ESTRUCTURA PRINCIPAL
    # ==============================================================

    def _crear_interfaz(self):
        """Crea la estructura principal: header blanco + sidebar doble + contenido"""

        # ========== HEADER (blanco, 64px) ==========
        self.header = tk.Frame(self.root, bg=COLORES['fondo_card'], height=64)
        self.header.pack(fill='x', side='top')
        self.header.pack_propagate(False)

        # Logo circular "P"
        tk.Label(
            self.header,
            text="P",
            font=('Segoe UI', 16, 'bold'),
            fg=COLORES['texto_claro'],
            bg=COLORES['primario'],
            width=3, height=1
        ).pack(side='left', padx=(16, 8), pady=12)

        tk.Label(
            self.header,
            text="Los Pocitos Azufrados",
            font=('Segoe UI', 13, 'bold'),
            fg=COLORES['texto'],
            bg=COLORES['fondo_card']
        ).pack(side='left', padx=(0, 20))

        # Separador vertical
        tk.Frame(self.header, bg=COLORES['borde'], width=1).pack(
            side='left', fill='y', pady=14)

        # Título dinámico del módulo activo
        self.lbl_modulo_header = tk.Label(
            self.header,
            text="Dashboard",
            font=FUENTES['encabezado'],
            fg=COLORES['primario'],
            bg=COLORES['fondo_card']
        )
        self.lbl_modulo_header.pack(side='left', padx=20)

        # Zona derecha: fecha + avatar + nombre
        right = tk.Frame(self.header, bg=COLORES['fondo_card'])
        right.pack(side='right', padx=16)

        hoy = datetime.datetime.now()
        tk.Label(
            right,
            text=hoy.strftime("%d %b %Y"),
            font=FUENTES['pequena'],
            fg=COLORES['texto_secundario'],
            bg=COLORES['fondo_card']
        ).pack(side='left', padx=(0, 12))

        tk.Label(
            right,
            text=self.usuario['nombre_completo'][0].upper(),
            font=('Segoe UI', 13, 'bold'),
            fg=COLORES['texto_claro'],
            bg=COLORES['agua'],
            width=3, height=1
        ).pack(side='left', padx=(0, 8))

        tk.Label(
            right,
            text=self.usuario['nombre_completo'],
            font=FUENTES['normal_bold'],
            fg=COLORES['texto'],
            bg=COLORES['fondo_card']
        ).pack(side='left')

        # Línea de acento verde ácido (2px)
        tk.Frame(self.root, bg=COLORES['acento'], height=2).pack(fill='x')

        # ========== CUERPO ==========
        body = tk.Frame(self.root, bg=COLORES['fondo'])
        body.pack(fill='both', expand=True)

        # ========== SIDEBAR DOBLE ==========
        self._construir_sidebar(body)

        # ========== ÁREA DE CONTENIDO ==========
        self.content_frame = tk.Frame(body, bg=COLORES['fondo'])
        self.content_frame.pack(fill='both', expand=True)

    def _construir_sidebar(self, body):
        """Sidebar de dos columnas: iconos (56px oscuro) + texto (168px blanco)."""
        sidebar_wrap = tk.Frame(body, bg=COLORES['fondo_card'])
        sidebar_wrap.pack(fill='y', side='left')
        tk.Frame(body, bg=COLORES['borde'], width=1).pack(fill='y', side='left')

        menu_grupos = [
            (None, [
                ("\u2302",  "Dashboard",        self._cargar_dashboard),
            ]),
            ("OPERACIONES", [
                ("\u0024",  "Caja",             self._abrir_caja),
                ("\u2615",  "Restaurante",      self._abrir_bar),
                ("\u270d",  "Pedidos",          self._abrir_pedidos),
                ("\u229e",  "Cuentas Abiertas", self._abrir_cuentas_abiertas),
            ]),
            ("ADMINISTRACION", [
                ("\u2261",  "Inventario",       self._abrir_inventario),
                ("\u21c5",  "Movimientos",      self._abrir_movimientos),
                ("\u2295",  "Proveedores",      self._abrir_proveedores),
                ("\u0024\u0024", "Nomina",       self._abrir_nomina),
                ("\u2764",  "Socios",           self._abrir_socios),
            ]),
            ("SISTEMA", [
                ("\u2699",  "Config & Usuarios", self._abrir_config_usuarios),
                ("\u26a0",  "Contingencia",      self._abrir_contingencia),
                ("\u26d2",  "Reporte Errores",   self._abrir_reporte_errores),
            ]),
        ]

        for grupo, items in menu_grupos:
            if grupo is not None:
                # Fila de encabezado de grupo
                grp_row = tk.Frame(sidebar_wrap, bg=COLORES['fondo_card'])
                grp_row.pack(fill='x')

                # Espaciador del panel de iconos
                tk.Frame(grp_row, bg=COLORES['fondo_sidebar'], width=56).pack(
                    side='left', fill='y')

                # Área de etiqueta del grupo
                grp_label_area = tk.Frame(grp_row, bg=COLORES['fondo_card'])
                grp_label_area.pack(side='left', fill='both', expand=True)
                tk.Frame(grp_label_area, bg=COLORES['borde'], height=1).pack(
                    fill='x', padx=8, pady=(8, 2))
                tk.Label(
                    grp_label_area,
                    text=grupo,
                    font=('Segoe UI', 8, 'bold'),
                    fg=COLORES['texto_deshabilitado'],
                    bg=COLORES['fondo_card']
                ).pack(anchor='w', padx=10, pady=(0, 2))

            for icono, texto, comando in items:
                # Fila de ítem: celda de icono + barra activa + botón de texto
                row = tk.Frame(sidebar_wrap, bg=COLORES['fondo_card'])
                row.pack(fill='x')

                # Celda del icono (56px, verde oscuro)
                icon_cell = tk.Frame(row, bg=COLORES['fondo_sidebar'], width=56)
                icon_cell.pack(side='left', fill='y')
                icon_cell.pack_propagate(False)

                btn_icon = tk.Button(
                    icon_cell,
                    text=icono,
                    font=('Segoe UI Symbol', 14),
                    fg=COLORES['texto_sidebar'],
                    bg=COLORES['fondo_sidebar'],
                    relief='flat', bd=0,
                    cursor='hand2',
                    padx=0, pady=10,
                    activeforeground=COLORES['acento'],
                    activebackground=COLORES['primario'],
                    command=comando
                )
                btn_icon.pack(fill='both', expand=True)

                # Barra indicadora activa (3px, izquierda del texto)
                active_bar = tk.Frame(row, bg=COLORES['fondo_card'], width=3)
                active_bar.pack(side='left', fill='y')

                # Badge de alerta de stock (solo para Inventario, al lado derecho)
                if texto == 'Inventario':
                    badge_cell = tk.Frame(row, bg=COLORES['fondo_card'], width=28)
                    badge_cell.pack(side='right', fill='y', padx=(0, 6))
                    badge_cell.pack_propagate(False)
                    self._badge_stock_label = tk.Label(
                        badge_cell,
                        text='0',
                        font=('Segoe UI', 7, 'bold'),
                        fg=COLORES['texto_claro'],
                        bg=COLORES['error'],
                        padx=3, pady=2
                    )
                    # Empieza oculto — _actualizar_badge_stock lo mostrará si hay alertas

                # Botón de texto
                btn_text = tk.Button(
                    row,
                    text=texto,
                    font=FUENTES['normal'],
                    fg=COLORES['texto_secundario'],
                    bg=COLORES['fondo_card'],
                    relief='flat', bd=0,
                    cursor='hand2',
                    anchor='w',
                    padx=10, pady=10,
                    activeforeground=COLORES['texto'],
                    activebackground=COLORES['acento_claro'],
                    command=comando
                )
                btn_text.pack(side='left', fill='both', expand=True)

                self._icon_btns[texto] = (btn_icon, active_bar)
                self._text_btns[texto] = btn_text

                # Hover effects (solo cuando no está activo)
                def _bind_hover(b_icon, b_text, nombre):
                    def on_enter(e):
                        if self.modulo_actual != nombre:
                            b_icon.config(bg=COLORES['primario'], fg=COLORES['acento'])
                            b_text.config(bg=COLORES['acento_claro'], fg=COLORES['texto'])
                    def on_leave(e):
                        if self.modulo_actual != nombre:
                            b_icon.config(bg=COLORES['fondo_sidebar'], fg=COLORES['texto_sidebar'])
                            b_text.config(bg=COLORES['fondo_card'], fg=COLORES['texto_secundario'])
                    for w in (b_icon, b_text):
                        w.bind('<Enter>', on_enter)
                        w.bind('<Leave>', on_leave)
                _bind_hover(btn_icon, btn_text, texto)

        # --- Backup y logout pegados al fondo del sidebar ---
        spacer = tk.Frame(sidebar_wrap, bg=COLORES['fondo_card'])
        spacer.pack(fill='both', expand=True)

        # Fila de estado de backup
        bk_row = tk.Frame(sidebar_wrap, bg=COLORES['fondo_card'])
        bk_row.pack(fill='x')
        tk.Frame(bk_row, bg=COLORES['fondo_sidebar'], width=56).pack(side='left', fill='y')
        bk_right = tk.Frame(bk_row, bg=COLORES['fondo_card'])
        bk_right.pack(side='left', fill='both', expand=True)
        tk.Frame(bk_right, bg=COLORES['borde'], height=1).pack(fill='x', padx=8, pady=(6, 3))
        self.lbl_backup_status = tk.Label(
            bk_right,
            text="Backup: cargando...",
            font=('Segoe UI', 8),
            fg=COLORES['texto_deshabilitado'],
            bg=COLORES['fondo_card'],
            anchor='w', padx=10,
            wraplength=155, justify='left'
        )
        self.lbl_backup_status.pack(fill='x', pady=(0, 4))
        self._actualizar_indicador_backup()

        # Fila de cerrar sesión
        logout_row = tk.Frame(sidebar_wrap, bg=COLORES['fondo_card'])
        logout_row.pack(fill='x')
        tk.Frame(logout_row, bg=COLORES['fondo_sidebar'], width=56).pack(side='left', fill='y')
        logout_right = tk.Frame(logout_row, bg=COLORES['fondo_card'])
        logout_right.pack(side='left', fill='both', expand=True)
        tk.Frame(logout_right, bg=COLORES['borde'], height=1).pack(fill='x', padx=8)
        tk.Button(
            logout_right,
            text="Cerrar Sesion",
            font=FUENTES['normal'],
            fg=COLORES['error'],
            bg=COLORES['fondo_card'],
            relief='flat', anchor='w',
            cursor='hand2', bd=0,
            padx=10, pady=10,
            activebackground=COLORES['gris_100'],
            activeforeground=COLORES['error'],
            command=self._cerrar_sesion
        ).pack(fill='x', pady=(0, 10))

    # ==============================================================
    #  INDICADOR DE BACKUP
    # ==============================================================

    def _actualizar_indicador_backup(self):
        """Lee el estado del último backup y actualiza el label del sidebar."""
        try:
            with conexion_segura() as conn:
                row_fecha  = conn.execute(
                    "SELECT valor FROM configuracion WHERE clave = 'ultimo_backup'"
                ).fetchone()
                row_estado = conn.execute(
                    "SELECT valor FROM configuracion WHERE clave = 'ultimo_backup_estado'"
                ).fetchone()

            fecha  = row_fecha['valor'].strip()  if row_fecha  and row_fecha['valor']  else ''
            estado = row_estado['valor'].strip()  if row_estado and row_estado['valor'] else ''

            if not fecha:
                texto = "Backup: sin realizar"
                color = COLORES['advertencia']
            elif estado == 'OK':
                fecha_corta = fecha[:10] if len(fecha) >= 10 else fecha
                texto = f"Backup OK: {fecha_corta}"
                color = COLORES['exito']
            else:
                texto = f"Backup: ERROR\n{estado[:40]}"
                color = COLORES['error']

            # SEC-11: advertir si cocina_web usa la clave por defecto
            row_token = conn.execute(
                "SELECT valor FROM configuracion WHERE clave = 'cocina_web_token'"
            ).fetchone()
            token_val = row_token['valor'].strip() if row_token and row_token['valor'] else ''
            if not token_val or token_val == 'cocina2025':
                texto += "\n[!] Cocina web: clave por defecto"
                color = COLORES['advertencia']

        except Exception:
            texto = "Backup: no disponible"
            color = COLORES['texto_deshabilitado']

        if hasattr(self, 'lbl_backup_status'):
            try:
                self.lbl_backup_status.config(text=texto, fg=color)
            except Exception:
                pass

    # ==============================================================
    #  NAVEGACIÓN Y ESTADO DEL MENÚ
    # ==============================================================

    def _limpiar_contenido(self):
        # Eliminar bindings globales de scroll del dashboard
        try:
            self.root.unbind_all("<MouseWheel>")
            self.root.unbind_all("<Button-4>")
            self.root.unbind_all("<Button-5>")
        except Exception:
            pass

        if self._instancia_modulo is not None:
            if hasattr(self._instancia_modulo, 'detener'):
                try:
                    self._instancia_modulo.detener()
                except Exception:
                    pass
            self._instancia_modulo = None

        for widget in self.content_frame.winfo_children():
            widget.destroy()

    def _marcar_menu(self, nombre):
        """Actualiza el estado visual del ítem activo en el sidebar doble."""
        self.modulo_actual = nombre

        if hasattr(self, 'lbl_modulo_header'):
            try:
                self.lbl_modulo_header.config(text=nombre)
            except Exception:
                pass

        for key in self._icon_btns:
            btn_icon, active_bar = self._icon_btns[key]
            btn_text = self._text_btns[key]
            if key == nombre:
                btn_icon.config(bg=COLORES['primario'], fg=COLORES['acento'])
                active_bar.config(bg=COLORES['acento'])
                btn_text.config(
                    bg=COLORES['acento_claro'],
                    fg=COLORES['texto'],
                    font=FUENTES['normal_bold']
                )
            else:
                btn_icon.config(bg=COLORES['fondo_sidebar'], fg=COLORES['texto_sidebar'])
                active_bar.config(bg=COLORES['fondo_card'])
                btn_text.config(
                    bg=COLORES['fondo_card'],
                    fg=COLORES['texto_secundario'],
                    font=FUENTES['normal']
                )

    # ==============================================================
    #  DASHBOARD - KPI CARDS MODERNAS
    # ==============================================================

    def _cargar_dashboard(self):
        """Dashboard con KPIs modernos (sombra, delta, detalle) + productos top"""
        self._limpiar_contenido()
        self._marcar_menu("Dashboard")

        canvas = tk.Canvas(self.content_frame, bg=COLORES['fondo'], highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.content_frame, orient="vertical", command=canvas.yview)
        scroll_frame = tk.Frame(canvas, bg=COLORES['fondo'])

        scroll_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        _win = canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.bind('<Configure>', lambda e: canvas.itemconfig(_win, width=e.width))

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        canvas.bind_all("<MouseWheel>",
                        lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))
        canvas.bind_all("<Button-4>", lambda e: canvas.yview_scroll(-1, "units"))
        canvas.bind_all("<Button-5>", lambda e: canvas.yview_scroll(1, "units"))

        # ── Saludo ──────────────────────────────────────────────────
        hdr = tk.Frame(scroll_frame, bg=COLORES['fondo'])
        hdr.pack(fill='x', padx=24, pady=(18, 6))

        hoy = datetime.datetime.now()
        saludo = ("Buenos dias" if hoy.hour < 12
                  else "Buenas tardes" if hoy.hour < 18
                  else "Buenas noches")
        tk.Label(hdr, text=f"{saludo}, {self.usuario['nombre_completo']}",
                 font=FUENTES['titulo'], fg=COLORES['texto'],
                 bg=COLORES['fondo']).pack(anchor='w')
        tk.Label(hdr, text=hoy.strftime("%A, %d de %B de %Y"),
                 font=FUENTES['normal'], fg=COLORES['texto_secundario'],
                 bg=COLORES['fondo']).pack(anchor='w')

        # ── KPI Cards ──────────────────────────────────────────────
        kpis = self._obtener_kpis()

        kpi_row = tk.Frame(scroll_frame, bg=COLORES['fondo'])
        kpi_row.pack(fill='x', padx=24, pady=(12, 6))

        def _delta(actual, anterior):
            """Retorna (texto_flecha, color) para comparativo."""
            if anterior == 0:
                return None, None
            pct = (actual - anterior) / anterior * 100
            flecha = "\u25b2" if pct >= 0 else "\u25bc"
            sign   = "+" if pct >= 0 else ""
            color  = COLORES['exito'] if pct >= 0 else COLORES['error']
            return f"{flecha} {sign}{pct:.0f}% vs anterior", color

        kpi_data = [
            {
                "titulo":    "Ventas Hoy",
                "valor":     format_money(kpis['ventas_hoy']),
                "barra_col": COLORES['acento'],
                "delta":     _delta(kpis['ventas_hoy'], kpis['ventas_ayer']),
                "detalle":   self._abrir_movimientos,
            },
            {
                "titulo":    "Ventas del Mes",
                "valor":     format_money(kpis['ventas_mes']),
                "barra_col": COLORES['agua'],
                "delta":     _delta(kpis['ventas_mes'], kpis['ventas_mes_anterior']),
                "detalle":   self._abrir_movimientos,
            },
            {
                "titulo":    "Gastos del Mes",
                "valor":     format_money(kpis['gastos_mes']),
                "barra_col": COLORES['error'],
                "delta":     _delta(kpis['gastos_mes'], kpis['gastos_mes_anterior']),
                "detalle":   self._abrir_movimientos,
            },
            {
                "titulo":    "Inventario Bajo",
                "valor":     str(kpis['stock_bajo']),
                "barra_col": COLORES['advertencia'],
                "delta":     (None, None),
                "detalle":   self._abrir_inventario,
            },
        ]

        for i, kpi in enumerate(kpi_data):
            kpi_row.columnconfigure(i, weight=1)

            # Sombra simulada: frame gris exterior + card blanca interior con offset
            shadow = tk.Frame(kpi_row, bg=COLORES['gris_300'])
            shadow.grid(row=0, column=i, padx=6, pady=(2, 6), sticky='nsew')

            card = tk.Frame(shadow, bg=COLORES['fondo_card'])
            card.pack(fill='both', expand=True, padx=(0, 2), pady=(0, 2))

            # Barra de color superior (4px)
            tk.Frame(card, bg=kpi['barra_col'], height=4).pack(fill='x')

            inner = tk.Frame(card, bg=COLORES['fondo_card'], padx=16, pady=14)
            inner.pack(fill='both', expand=True)

            # Título
            tk.Label(inner, text=kpi['titulo'], font=FUENTES['kpi_label'],
                     fg=COLORES['texto_secundario'],
                     bg=COLORES['fondo_card']).pack(anchor='w')

            # Valor grande
            tk.Label(inner, text=kpi['valor'], font=FUENTES['kpi_valor'],
                     fg=COLORES['texto'],
                     bg=COLORES['fondo_card'], anchor='w').pack(fill='x', pady=(4, 0))

            # Delta (flecha + porcentaje)
            delta_txt, delta_col = kpi['delta']
            if delta_txt:
                tk.Label(inner, text=delta_txt, font=FUENTES['pequena'],
                         fg=delta_col,
                         bg=COLORES['fondo_card'], anchor='w').pack(fill='x', pady=(2, 4))
            else:
                tk.Frame(inner, bg=COLORES['fondo_card'], height=6).pack()

            # Separador y enlace "Ver detalle >"
            tk.Frame(inner, bg=COLORES['borde'], height=1).pack(fill='x', pady=(4, 4))
            lbl_det = tk.Label(inner, text="Ver detalle  >",
                               font=FUENTES['pequena'],
                               fg=COLORES['agua'],
                               bg=COLORES['fondo_card'],
                               cursor='hand2', anchor='e')
            lbl_det.pack(fill='x')
            lbl_det.bind('<Button-1>', lambda e, cmd=kpi['detalle']: cmd())

        # ── Banner alerta de stock bajo ────────────────────────────
        if kpis['stock_bajo'] > 0:
            alerta_shadow = tk.Frame(scroll_frame, bg=COLORES['advertencia'])
            alerta_shadow.pack(fill='x', padx=24, pady=(0, 6))
            alerta_card = tk.Frame(alerta_shadow, bg='#FFF8E1')
            alerta_card.pack(fill='both', expand=True, padx=(0, 2), pady=(0, 2))
            tk.Frame(alerta_card, bg=COLORES['advertencia'], height=3).pack(fill='x')
            alerta_inner = tk.Frame(alerta_card, bg='#FFF8E1', padx=16, pady=10)
            alerta_inner.pack(fill='x')
            msg = (f"{kpis['stock_bajo']} producto(s) con stock bajo o agotado"
                   if kpis['stock_bajo'] > 1 else "1 producto con stock bajo o agotado")
            tk.Label(alerta_inner, text=f"\u26a0  {msg}",
                     font=FUENTES['normal_bold'],
                     fg='#7A4F00', bg='#FFF8E1').pack(side='left')
            lbl_ir = tk.Label(alerta_inner, text="Ir a Inventario  >",
                              font=FUENTES['pequena'],
                              fg=COLORES['advertencia'], bg='#FFF8E1',
                              cursor='hand2')
            lbl_ir.pack(side='right')
            lbl_ir.bind('<Button-1>', lambda e: self._abrir_inventario())

        # ── Utilidad Neta ──────────────────────────────────────────
        utilidad    = kpis['ventas_mes'] - kpis['gastos_mes']
        util_color  = COLORES['exito'] if utilidad >= 0 else COLORES['error']

        util_shadow = tk.Frame(scroll_frame, bg=COLORES['gris_300'])
        util_shadow.pack(fill='x', padx=24, pady=(0, 10))
        util_card = tk.Frame(util_shadow, bg=COLORES['fondo_card'])
        util_card.pack(fill='both', expand=True, padx=(0, 2), pady=(0, 2))

        tk.Frame(util_card, bg=util_color, height=4).pack(fill='x')
        util_inner = tk.Frame(util_card, bg=COLORES['fondo_card'], padx=20, pady=12)
        util_inner.pack(fill='x')
        tk.Label(util_inner, text="Utilidad Neta del Mes",
                 font=FUENTES['encabezado'],
                 fg=COLORES['texto_secundario'],
                 bg=COLORES['fondo_card']).pack(side='left')
        tk.Label(util_inner, text=format_money(utilidad),
                 font=('Consolas', 22, 'bold'),
                 fg=util_color,
                 bg=COLORES['fondo_card']).pack(side='right')

        # ── Accesos Rápidos ────────────────────────────────────────
        acc_frame = tk.Frame(scroll_frame, bg=COLORES['fondo'])
        acc_frame.pack(fill='x', padx=24, pady=(4, 10))

        tk.Label(acc_frame, text="Accesos Rapidos",
                 font=FUENTES['encabezado'],
                 fg=COLORES['texto'],
                 bg=COLORES['fondo']).pack(anchor='w', pady=(0, 8))

        btns = tk.Frame(acc_frame, bg=COLORES['fondo'])
        btns.pack(fill='x')

        accesos = [
            ("Restaurante",      self._abrir_bar,              'primario'),
            ("Nuevo Pedido",     self._abrir_pedidos,          'azufre'),
            ("Cuentas Abiertas", self._abrir_cuentas_abiertas, 'advertencia'),
            ("Inventario",       self._abrir_inventario,       'secundario'),
        ]
        for texto, cmd, tipo in accesos:
            crear_boton(btns, texto, cmd, tipo=tipo).pack(side='left', padx=5, pady=5)

        # ── Productos más vendidos ─────────────────────────────────
        self._mostrar_productos_top(scroll_frame)

    # ==============================================================
    #  DATOS PARA EL DASHBOARD
    # ==============================================================

    def _obtener_kpis(self):
        """Obtiene KPIs del dashboard con datos comparativos del periodo anterior."""
        import calendar
        kpis = {
            'ventas_hoy': 0, 'ventas_ayer': 0,
            'stock_bajo': 0,
            'ventas_mes': 0, 'ventas_mes_anterior': 0,
            'gastos_mes': 0, 'gastos_mes_anterior': 0,
        }
        try:
            hoy = datetime.date.today()
            hoy_str    = hoy.isoformat()
            ayer_str   = (hoy - datetime.timedelta(days=1)).isoformat()
            mes_inicio = hoy.replace(day=1).isoformat()

            primer_dia_mes_ant = (hoy.replace(day=1) - datetime.timedelta(days=1)).replace(day=1)
            dias_en_mes_ant    = calendar.monthrange(
                primer_dia_mes_ant.year, primer_dia_mes_ant.month)[1]
            dia_comparable  = min(hoy.day, dias_en_mes_ant)
            mes_ant_inicio  = primer_dia_mes_ant.isoformat()
            mes_ant_fin     = primer_dia_mes_ant.replace(day=dia_comparable).isoformat()

            with conexion_segura() as conn:
                r = conn.execute(
                    "SELECT COALESCE(SUM(total), 0) AS total FROM ventas "
                    "WHERE fecha_creacion >= ? AND fecha_creacion < date(?, '+1 day') AND estado != 'ANULADA'",
                    (hoy_str, hoy_str)
                ).fetchone()
                kpis['ventas_hoy'] = r['total']

                r = conn.execute(
                    "SELECT COALESCE(SUM(total), 0) AS total FROM ventas "
                    "WHERE fecha_creacion >= ? AND fecha_creacion < date(?, '+1 day') AND estado != 'ANULADA'",
                    (ayer_str, ayer_str)
                ).fetchone()
                kpis['ventas_ayer'] = r['total']

                r = conn.execute(
                    "SELECT COUNT(*) AS total FROM productos "
                    "WHERE activo = 1 AND stock_minimo > 0 AND stock_actual <= stock_minimo"
                ).fetchone()
                kpis['stock_bajo'] = r['total']

                r = conn.execute(
                    "SELECT COALESCE(SUM(total), 0) AS total FROM ventas "
                    "WHERE fecha_creacion >= ? AND estado != 'ANULADA'",
                    (mes_inicio,)
                ).fetchone()
                kpis['ventas_mes'] = r['total']

                r = conn.execute(
                    "SELECT COALESCE(SUM(total), 0) AS total FROM ventas "
                    "WHERE fecha_creacion >= ? AND fecha_creacion < date(?, '+1 day') AND estado != 'ANULADA'",
                    (mes_ant_inicio, mes_ant_fin)
                ).fetchone()
                kpis['ventas_mes_anterior'] = r['total']

                r = conn.execute(
                    "SELECT COALESCE(SUM(valor), 0) AS total FROM gastos "
                    "WHERE fecha >= ?",
                    (mes_inicio,)
                ).fetchone()
                kpis['gastos_mes'] = r['total']

                r = conn.execute(
                    "SELECT COALESCE(SUM(valor), 0) AS total FROM gastos "
                    "WHERE fecha >= ? AND fecha < date(?, '+1 day')",
                    (mes_ant_inicio, mes_ant_fin)
                ).fetchone()
                kpis['gastos_mes_anterior'] = r['total']

        except Exception as e:
            print(f"Error KPIs: {e}")

        return kpis

    def _mostrar_productos_top(self, parent):
        """Muestra productos más vendidos en dos columnas (Bar y Cocina)."""
        frame = tk.Frame(parent, bg=COLORES['fondo'])
        frame.pack(fill='x', padx=24, pady=(0, 20))
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)

        # ---- TOP BAR ----
        bar_shadow = tk.Frame(frame, bg=COLORES['gris_300'])
        bar_shadow.grid(row=0, column=0, padx=(0, 6), sticky='nsew')
        bar_frame = tk.Frame(bar_shadow, bg=COLORES['fondo_card'])
        bar_frame.pack(fill='both', expand=True, padx=(0, 2), pady=(0, 2))

        tk.Frame(bar_frame, bg=COLORES['agua'], height=4).pack(fill='x')
        tk.Label(bar_frame, text="Mas Vendidos — Bar",
                 font=FUENTES['encabezado'],
                 fg=COLORES['texto'],
                 bg=COLORES['fondo_card']).pack(padx=14, pady=(10, 5), anchor='w')

        # ---- TOP COCINA ----
        coc_shadow = tk.Frame(frame, bg=COLORES['gris_300'])
        coc_shadow.grid(row=0, column=1, padx=(6, 0), sticky='nsew')
        cocina_frame = tk.Frame(coc_shadow, bg=COLORES['fondo_card'])
        cocina_frame.pack(fill='both', expand=True, padx=(0, 2), pady=(0, 2))

        tk.Frame(cocina_frame, bg=COLORES['acento'], height=4).pack(fill='x')
        tk.Label(cocina_frame, text="Mas Vendidos — Cocina",
                 font=FUENTES['encabezado'],
                 fg=COLORES['texto'],
                 bg=COLORES['fondo_card']).pack(padx=14, pady=(10, 5), anchor='w')

        try:
            mes_inicio = datetime.date.today().replace(day=1).isoformat()
            with conexion_segura() as conn:
                top_bar = conn.execute("""
                    SELECT vd.producto_nombre,
                           SUM(vd.cantidad)   AS total_vendido,
                           SUM(vd.total_linea) AS total_dinero
                    FROM venta_detalle vd
                    JOIN ventas   v ON vd.id_venta    = v.id_venta
                    JOIN productos p ON vd.id_producto = p.id_producto
                    WHERE v.estado != 'ANULADA'
                      AND date(v.fecha_creacion) >= ?
                      AND p.requiere_cocina = 0
                    GROUP BY vd.producto_nombre
                    ORDER BY total_vendido DESC
                    LIMIT 8
                """, (mes_inicio,)).fetchall()

                top_cocina = conn.execute("""
                    SELECT vd.producto_nombre,
                           SUM(vd.cantidad)   AS total_vendido,
                           SUM(vd.total_linea) AS total_dinero
                    FROM venta_detalle vd
                    JOIN ventas   v ON vd.id_venta    = v.id_venta
                    JOIN productos p ON vd.id_producto = p.id_producto
                    WHERE v.estado != 'ANULADA'
                      AND date(v.fecha_creacion) >= ?
                      AND p.requiere_cocina = 1
                    GROUP BY vd.producto_nombre
                    ORDER BY total_vendido DESC
                    LIMIT 8
                """, (mes_inicio,)).fetchall()

            self._render_top_list(bar_frame,    top_bar,    COLORES['agua'])
            self._render_top_list(cocina_frame, top_cocina, COLORES['acento'])

        except Exception as e:
            print(f"Error top productos: {e}")
            for frm in (bar_frame, cocina_frame):
                tk.Label(frm, text="Sin datos aun",
                         font=FUENTES['normal'],
                         fg=COLORES['texto_deshabilitado'],
                         bg=COLORES['fondo_card']).pack(pady=20)

    def _render_top_list(self, parent, datos, color):
        """Renderiza una lista de top productos."""
        if not datos:
            tk.Label(parent, text="Sin ventas registradas aun",
                     font=FUENTES['normal'],
                     fg=COLORES['texto_deshabilitado'],
                     bg=COLORES['fondo_card']).pack(pady=20)
            return

        for i, row in enumerate(datos):
            bg = COLORES['gris_50'] if i % 2 == 0 else COLORES['fondo_card']
            item = tk.Frame(parent, bg=bg)
            item.pack(fill='x', padx=14, pady=1)

            pos = ["1.", "2.", "3."][i] if i < 3 else f"{i+1}."
            tk.Label(item, text=pos, font=FUENTES['normal_bold'],
                     fg=color, bg=bg, width=4).pack(side='left')

            tk.Label(item, text=row['producto_nombre'],
                     font=FUENTES['normal'], fg=COLORES['texto'],
                     bg=bg).pack(side='left', padx=(4, 0))

            tk.Label(item, text=format_money(row['total_dinero']),
                     font=FUENTES['pequena'], fg=COLORES['texto_secundario'],
                     bg=bg).pack(side='right', padx=(0, 8))

            tk.Label(item, text=f"{row['total_vendido']} uds",
                     font=FUENTES['normal_bold'], fg=color,
                     bg=bg).pack(side='right', padx=(0, 8))

        tk.Frame(parent, bg=COLORES['fondo_card'], height=10).pack()

    # ==============================================================
    #  BADGE DE STOCK BAJO (sidebar)
    # ==============================================================

    def _actualizar_badge_stock(self):
        """Consulta productos con stock bajo y actualiza el badge rojo en Inventario."""
        n = 0
        try:
            with conexion_segura() as conn:
                r = conn.execute(
                    "SELECT COUNT(*) AS total FROM productos "
                    "WHERE activo = 1 AND stock_minimo > 0 AND stock_actual <= stock_minimo"
                ).fetchone()
                n = r['total'] if r else 0
        except Exception:
            pass

        lbl = self._badge_stock_label
        if lbl:
            try:
                if n > 0:
                    lbl.config(text=str(n) if n <= 99 else '99+')
                    if not lbl.winfo_ismapped():
                        lbl.pack(expand=True)
                else:
                    if lbl.winfo_ismapped():
                        lbl.pack_forget()
            except Exception:
                pass

        # Reprogramar cada 60 segundos
        try:
            if self.root.winfo_exists():
                self.root.after(60_000, self._actualizar_badge_stock)
        except Exception:
            pass

    # ==============================================================
    #  NAVEGACIÓN A MÓDULOS
    # ==============================================================

    def _abrir_modulo(self, nombre, clase_modulo, *args):
        self._limpiar_contenido()
        self._marcar_menu(nombre)
        try:
            self._instancia_modulo = clase_modulo(self.content_frame, self.usuario, *args)
        except Exception as e:
            import traceback
            traceback.print_exc()
            self._instancia_modulo = None
            tk.Label(self.content_frame,
                     text=f"Error cargando modulo '{nombre}':\n{str(e)}",
                     font=FUENTES['normal'], fg=COLORES['error'],
                     bg=COLORES['fondo']).pack(pady=50)

    def _abrir_bar(self):
        try:
            from modules.pos_module import POSModule
            self._limpiar_contenido()
            self._marcar_menu("Restaurante")
            self._instancia_modulo = POSModule(
                self.content_frame, self.usuario,
                callback_ir_caja=lambda: self._abrir_modulo("Caja", CajaModule,
                                                             lambda: self._abrir_bar())
            )
        except Exception as e:
            import traceback
            import logging
            logging.getLogger("pocitos").error(f"Error abriendo Restaurante: {e}\n{traceback.format_exc()}")
            self._instancia_modulo = None
            for w in self.content_frame.winfo_children():
                w.destroy()
            tk.Label(self.content_frame,
                     text=f"Error cargando Restaurante:\n{str(e)}",
                     font=FUENTES['normal'], fg=COLORES['error'],
                     bg=COLORES['fondo']).pack(pady=50)

    def _abrir_boletas(self):
        from modules.boletas_module import BoletasModule
        self._abrir_modulo("Boletas", BoletasModule)

    def _abrir_pedidos(self):
        from modules.pedidos_module import PedidosModule
        self._abrir_modulo("Pedidos", PedidosModule)

    def _abrir_cocina(self):
        from modules.cocina_module import CocinaModule
        self._abrir_modulo("Cocina", CocinaModule)

    def _abrir_cuentas_abiertas(self):
        from modules.cuentas_abiertas_module import CuentasAbiertasModule
        self._abrir_modulo("Cuentas Abiertas", CuentasAbiertasModule)

    def _abrir_historial(self):
        from modules.historial_ventas_module import HistorialVentasModule
        self._abrir_modulo("Historial Ventas", HistorialVentasModule)

    def _abrir_inventario(self):
        from modules.inventario_module import InventarioModule
        self._abrir_modulo("Inventario", InventarioModule)

    def _abrir_gastos(self):
        from modules.gastos_module import GastosModule
        self._abrir_modulo("Gastos", GastosModule)

    def _abrir_caja(self):
        from modules.caja_module import CajaModule
        self._abrir_modulo("Caja", CajaModule, lambda: self._abrir_bar())

    def _abrir_movimientos(self):
        from modules.movimientos_module import MovimientosModule
        self._abrir_modulo("Movimientos", MovimientosModule)

    def _abrir_reportes(self):
        from modules.reportes_module import ReportesModule
        self._abrir_modulo("Reportes", ReportesModule)

    def _abrir_usuarios(self):
        from modules.usuarios_module import UsuariosModule
        self._abrir_modulo("Usuarios", UsuariosModule)

    def _abrir_clientes(self):
        from modules.clientes_module import ClientesModule
        self._abrir_modulo("Clientes", ClientesModule)

    def _abrir_proveedores(self):
        from modules.proveedores_module import ProveedoresModule
        self._abrir_modulo("Proveedores", ProveedoresModule)

    def _abrir_config(self):
        from modules.config_module import ConfigModule
        self._abrir_modulo("Configuracion", ConfigModule)

    def _abrir_contingencia(self):
        from modules.contingencia_module import ContingenciaModule
        self._abrir_modulo("Contingencia", ContingenciaModule)

    def _abrir_nomina(self):
        from modules.nomina_module import NominaModule
        self._abrir_modulo("Nomina", NominaModule)

    def _abrir_socios(self):
        from modules.socios_module import SociosModule
        self._abrir_modulo("Socios", SociosModule)

    def _abrir_config_usuarios(self):
        from modules.config_usuarios_module import ConfigUsuariosModule
        self._abrir_modulo("Config & Usuarios", ConfigUsuariosModule)

    def _abrir_reporte_errores(self):
        try:
            from modules.reporte_errores_module import ReporteErroresModule
            self._abrir_modulo("Reporte Errores", ReporteErroresModule)
        except Exception as e:
            import traceback, logging
            logging.getLogger("pocitos").error(traceback.format_exc())
            import tkinter as tk
            tk.Label(self.content_frame, text=f"Error:\n{e}",
                     bg='#fff', fg='red').pack(pady=20)

    # ==============================================================
    #  CERRAR SESIÓN / SALIR
    # ==============================================================

    # ==============================================================
    #  AUTO-BLOQUEO DE PANTALLA
    # ==============================================================

    def _registrar_actividad(self, event=None):
        self._ultimo_evento = time.time()

    def _programar_verificacion_bloqueo(self):
        try:
            if self.root.winfo_exists():
                self._after_bloqueo_id = self.root.after(10000, self._verificar_inactividad)
        except Exception:
            pass

    def _verificar_inactividad(self):
        try:
            if not self.root.winfo_exists():
                return
        except Exception:
            return
        if not self._bloqueo_activo:
            if time.time() - self._ultimo_evento >= 600:  # 10 minutos
                self._bloquear_pantalla()
        self._programar_verificacion_bloqueo()

    def _bloquear_pantalla(self):
        """Bloquea la pantalla tras un tiempo sin uso; se desbloquea con PIN."""
        if self._bloqueo_activo:
            return
        self._bloqueo_activo = True

        lock = tk.Toplevel(self.root)
        lock.title("Sistema Bloqueado")
        lock.configure(bg=COLORES['fondo_sidebar'])
        lock.attributes('-topmost', True)
        lock.grab_set()
        lock.protocol("WM_DELETE_WINDOW", lambda: None)  # no cerrar con X

        try:
            w = self.root.winfo_width()
            h = self.root.winfo_height()
            x = self.root.winfo_x()
            y = self.root.winfo_y()
            lock.geometry(f"{w}x{h}+{x}+{y}")
        except Exception:
            lock.geometry("1000x700")

        center = tk.Frame(lock, bg=COLORES['fondo_sidebar'])
        center.place(relx=0.5, rely=0.5, anchor='center')

        tk.Label(center, text="Pantalla Bloqueada",
                 font=('Segoe UI', 28, 'bold'),
                 fg=COLORES['acento'], bg=COLORES['fondo_sidebar']).pack(pady=(0, 6))

        tk.Label(center, text=f"Usuario: {self.usuario['nombre_completo']}",
                 font=FUENTES['normal'],
                 fg=COLORES['texto_claro'], bg=COLORES['fondo_sidebar']).pack(pady=(0, 24))

        tk.Label(center, text="Ingrese su PIN para continuar:",
                 font=FUENTES['normal'],
                 fg=COLORES['texto_claro'], bg=COLORES['fondo_sidebar']).pack(pady=(0, 8))

        entry_pin = tk.Entry(center, font=('Segoe UI', 20), show='*',
                             width=8, justify='center', relief='solid', bd=2,
                             highlightthickness=2, highlightcolor=COLORES['acento'],
                             highlightbackground=COLORES['borde_focus']
                             if 'borde_focus' in COLORES else COLORES['borde'])
        entry_pin.pack(pady=(0, 8))
        entry_pin.focus_set()

        lbl_err = tk.Label(center, text="", font=FUENTES['pequena'],
                           fg=COLORES['error'], bg=COLORES['fondo_sidebar'])
        lbl_err.pack(pady=(0, 12))

        def _verificar_pin(pin_ing):
            """Verifica PIN soportando texto plano y bcrypt."""
            try:
                with conexion_segura() as conn:
                    row = conn.execute(
                        "SELECT pin FROM usuarios WHERE id_usuario = ? AND activo = 1",
                        (self.usuario['id_usuario'],)
                    ).fetchone()
                if not row or not row['pin']:
                    return False
                guardado = row['pin']
                if guardado.startswith('$2'):
                    try:
                        import bcrypt
                        return bcrypt.checkpw(pin_ing.encode('utf-8'), guardado.encode('utf-8'))
                    except Exception:
                        return False
                import hmac
                return hmac.compare_digest(guardado, pin_ing)
            except Exception:
                return False

        _intentos_bloqueo = [0]
        _MAX_INTENTOS_BLOQUEO = 5

        def _desbloquear():
            pin_ing = entry_pin.get().strip()
            if _verificar_pin(pin_ing):
                self._bloqueo_activo = False
                self._ultimo_evento = time.time()
                lock.destroy()
            else:
                _intentos_bloqueo[0] += 1
                restantes = _MAX_INTENTOS_BLOQUEO - _intentos_bloqueo[0]
                if restantes <= 0:
                    logging.getLogger("pocitos").warning(
                        "Screen-lock: 5 intentos fallidos para usuario %s — cerrando app",
                        self.usuario.get('usuario', '?')
                    )
                    self.root.destroy()
                    return
                lbl_err.config(text=f"PIN incorrecto. Intentos restantes: {restantes}")
                entry_pin.delete(0, tk.END)
                entry_pin.focus_set()

        def _cerrar_app():
            if messagebox.askyesno("Cerrar aplicacion",
                                   "Si no recuerda el PIN puede cerrar la aplicacion.\n"
                                   "¿Desea salir?",
                                   parent=lock):
                self.root.destroy()

        crear_boton(center, "Desbloquear", _desbloquear, tipo='azufre').pack(fill='x', ipady=6, pady=(0, 6))
        crear_boton(center, "Cerrar aplicacion", _cerrar_app, tipo='error').pack(fill='x', ipady=4)

        tk.Label(center,
                 text="Solo el usuario actual puede desbloquear con su PIN.",
                 font=FUENTES['pequena'],
                 fg=COLORES['texto_deshabilitado'], bg=COLORES['fondo_sidebar']).pack(pady=(8, 0))

        entry_pin.bind('<Return>', lambda e: _desbloquear())

    def _cancelar_bloqueo_timer(self):
        if self._after_bloqueo_id:
            try:
                self.root.after_cancel(self._after_bloqueo_id)
            except Exception:
                pass
            self._after_bloqueo_id = None

    def _cerrar_sesion_db(self):
        """Actualiza la fecha de fin de sesión en la BD."""
        id_sesion = self.usuario.get('id_sesion')
        if id_sesion:
            try:
                with conexion_segura() as conn:
                    conn.execute(
                        "UPDATE sesiones SET fecha_fin = datetime('now','localtime') "
                        "WHERE id_sesion = ?",
                        (id_sesion,)
                    )
            except Exception:
                pass

    def _cerrar_sesion(self):
        """Botón Cerrar Sesión del sidebar: pregunta, limpia y vuelve al login."""
        if not messagebox.askyesno("Cerrar Sesion", "¿Desea cerrar la sesion?"):
            return
        self._cancelar_bloqueo_timer()
        if self._instancia_modulo and hasattr(self._instancia_modulo, 'detener'):
            try:
                self._instancia_modulo.detener()
            except Exception:
                pass
        self._cerrar_sesion_db()
        # Reusar el mismo root: limpiar widgets y abrir login sin llamar mainloop de nuevo
        try:
            for w in self.root.winfo_children():
                try:
                    w.destroy()
                except Exception:
                    pass
            from modules.login import LoginWindow
            LoginWindow(self.root)
        except Exception:
            try:
                self.root.destroy()
            except Exception:
                pass

    def _cerrar(self):
        """Cierra el dashboard, registra sesión y destruye la ventana."""
        self._cancelar_bloqueo_timer()
        if self._instancia_modulo and hasattr(self._instancia_modulo, 'detener'):
            try:
                self._instancia_modulo.detener()
            except Exception:
                pass
        self._cerrar_sesion_db()
        try:
            self.login_root.destroy()
        except Exception:
            pass