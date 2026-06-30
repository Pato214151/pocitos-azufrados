"""
Dashboard Especial para Daniela - Club Los Pocitos Azufrados
Mismo esquema que admin (sidebar doble + content_frame) con paleta atardecer/tulipanes.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import logging
import os, sys, datetime, time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from utils.tema_corporativo import FUENTES, SCALE, format_money
from database.connection import conexion_segura

# ─── PALETA VIOLETA / ATARDECER ──────────────────────────────────────────────
_C = {
    'fondo':          '#0D0820',
    'fondo_card':     '#160E2E',
    'fondo_card_alt': '#1E1040',
    'sidebar':        '#0A061A',
    'violeta':        '#7C3AED',
    'violeta_claro':  '#A78BFA',
    'lavanda':        '#C4B5FD',
    'morado':         '#9333EA',
    'magenta':        '#C026D3',
    'sunset_pink':    '#DB2777',
    'sunset_orange':  '#EA580C',
    'sunset_amber':   '#F59E0B',
    'tulipan_lila':   '#A855F7',
    'tulipan_rosa':   '#E11D48',
    'tulipan_blanc':  '#DDD6FE',
    'tallo':          '#166534',
    'texto':          '#F5F3FF',
    'texto_sec':      '#A78BFA',
    'borde':          '#3B1F6B',
    'exito':          '#34D399',
    'advertencia':    '#FBBF24',
    'error':          '#F87171',
    'dim':            '#6B5E8A',
}

_SUNSET = [
    '#0D0820', '#150B2F', '#1E0E3D', '#2D1B69',
    '#4C1D95', '#6B21A8', '#7C3AED', '#9333EA',
    '#A21CAF', '#C026D3', '#BE185D', '#DB2777',
    '#E11D48', '#DC2626', '#EA580C', '#F97316',
    '#F59E0B', '#FBB027',
]


def _blend_hex(c1, c2, t):
    """Interpola entre dos colores #RRGGBB. t=0 → c1, t=1 → c2."""
    t = max(0.0, min(1.0, t))
    r1, g1, b1 = int(c1[1:3], 16), int(c1[3:5], 16), int(c1[5:7], 16)
    r2, g2, b2 = int(c2[1:3], 16), int(c2[3:5], 16), int(c2[5:7], 16)
    return '#{:02x}{:02x}{:02x}'.format(
        int(r1 + (r2 - r1) * t),
        int(g1 + (g2 - g1) * t),
        int(b1 + (b2 - b1) * t),
    )


class DashboardContadora:
    def __init__(self, root, usuario):
        self.root = root
        self.usuario = usuario
        self.modulo_actual = None
        self._instancia_modulo = None
        self._icon_btns = {}   # nombre -> (btn_icon, active_bar)
        self._text_btns = {}   # nombre -> btn_text

        self.root.title(f"Los Pocitos Azufrados — {usuario.get('nombre_completo','')}")
        self.root.configure(bg=_C['fondo'])
        # Limpiar widgets del login antes de mostrar el dashboard
        for w in self.root.winfo_children():
            try:
                w.destroy()
            except Exception:
                pass
        self.root.deiconify()
        try:
            self.root.state('normal')
        except Exception:
            pass
        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        w  = int(sw * 0.92)
        h  = int((sh - 48) * 0.92)
        x  = (sw - w) // 2
        y  = max(0, (sh - 48 - h) // 4)
        self.root.geometry(f"{w}x{h}+{x}+{y}")
        self.root.resizable(True, True)
        self.root.minsize(max(900, int(900 * SCALE)), max(600, int(600 * SCALE)))
        self.root.protocol("WM_DELETE_WINDOW", self._cerrar)

        # Auto-bloqueo
        self._ultimo_evento = time.time()
        self._bloqueo_activo = False
        self._after_bloqueo_id = None

        def _tk_error_handler(exc_type, exc_value, exc_tb):
            import traceback, logging
            msg = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
            logging.getLogger("pocitos").error(f"Error en callback Tkinter:\n{msg}")
            try:
                for w in self.content_frame.winfo_children():
                    w.destroy()
                tk.Label(self.content_frame,
                         text=f"Error:\n{exc_value}",
                         font=FUENTES['normal'], fg=_C['error'],
                         bg=_C['fondo']).pack(pady=50)
            except Exception:
                pass
        self.root.report_callback_exception = _tk_error_handler

        self._crear_interfaz()
        self._cargar_dashboard()

        self.root.bind_all('<Motion>',   self._registrar_actividad)
        self.root.bind_all('<KeyPress>', self._registrar_actividad)
        self.root.bind_all('<Button>',   self._registrar_actividad)
        self._programar_verificacion_bloqueo()

    # ─── HELPERS VISUALES ─────────────────────────────────────────────────────

    def _tulipan(self, canvas, cx, cy_base, s=1.0, color_petalo='#A855F7'):
        """Tulipán premium: copa realista, 5 pétalos con gradiente, cáliz, hojas con vena, glow avanzado."""
        bg       = _C['fondo']
        v_oscuro = '#0C3619'
        v_tallo  = '#1A5C2E'
        v_hoja   = '#236B38'
        v_luz    = '#3E9E5A'

        stem_h = int(75 * s)
        top_y  = cy_base - stem_h

        # ── Glow avanzado (7 capas, cálido) ───────────────────────────────
        glow_warm = _blend_hex(color_petalo, '#FF6B9D', 0.35)
        for gex, ratio in [
            (int(35*s), 0.04), (int(26*s), 0.09), (int(18*s), 0.15),
            (int(12*s), 0.23), (int(7*s),  0.33), (int(4*s),  0.46),
            (int(2*s),  0.60),
        ]:
            gc = _blend_hex(glow_warm, bg, 1.0 - ratio)
            canvas.create_oval(
                cx - int(18*s) - gex, top_y - int(28*s) - gex,
                cx + int(18*s) + gex, top_y + int(14*s) + gex,
                fill=gc, outline='')

        # ── Tallo con luz (3 líneas paralelas) ────────────────────────────
        for dx, col in [(-1, v_oscuro), (0, v_tallo), (1, v_luz)]:
            canvas.create_line(
                cx + dx, cy_base,
                cx + dx + int(4*s), cy_base - int(stem_h * 0.42),
                cx + dx + int(2*s), cy_base - int(stem_h * 0.70),
                cx + dx,            top_y + int(11*s),
                smooth=True, fill=col,
                width=max(1, int(1.5*s)), capstyle='round')

        # ── Hojas con vena ────────────────────────────────────────────────
        mid_y = cy_base - int(stem_h * 0.38)
        lx, ly = int(18*s), int(24*s)
        canvas.create_polygon(
            cx + int(1*s),       mid_y,
            cx - lx,             mid_y - ly,
            cx - int(lx*0.55),   mid_y - int(ly*1.28),
            cx - int(lx*0.10),   mid_y + int(ly*0.50),
            fill=v_hoja, outline='', smooth=True)
        canvas.create_line(
            cx, mid_y,
            cx - int(lx*0.52), mid_y - int(ly*0.62),
            cx - int(lx*0.44), mid_y - int(ly*1.10),
            smooth=True, fill=v_luz, width=1)
        canvas.create_polygon(
            cx - int(1*s),        mid_y - int(5*s),
            cx + lx + int(4*s),   mid_y - int(ly*1.18),
            cx + int(lx*0.60),    mid_y - int(ly*1.42),
            cx + int(lx*0.12),    mid_y + int(ly*0.35),
            fill=v_tallo, outline='', smooth=True)
        canvas.create_line(
            cx - int(1*s), mid_y - int(5*s),
            cx + int(lx*0.54), mid_y - int(ly*0.68),
            cx + int(lx*0.48), mid_y - int(ly*1.18),
            smooth=True, fill=v_luz, width=1)

        # ── Cáliz / sépalos ───────────────────────────────────────────────
        cw, ch = int(15*s), int(14*s)
        canvas.create_polygon(
            cx,             top_y + int(8*s),
            cx - cw,        top_y + ch + int(4*s),
            cx - int(4*s),  top_y + ch,
            fill=v_oscuro, outline='', smooth=True)
        canvas.create_polygon(
            cx,             top_y + int(8*s),
            cx + cw,        top_y + ch + int(4*s),
            cx + int(4*s),  top_y + ch,
            fill=v_tallo, outline='', smooth=True)
        canvas.create_polygon(
            cx - int(cw*0.45), top_y + int(8*s),
            cx,                top_y + ch + int(2*s),
            cx + int(cw*0.45), top_y + int(8*s),
            fill=v_hoja, outline='', smooth=True)

        # ── Pétalos (5: 2 traseros + 2 laterales + 1 central) ─────────────
        pw, ph   = int(13*s), int(27*s)
        c_dark   = _blend_hex(color_petalo, '#000000', 0.22)
        c_inner  = _blend_hex(color_petalo, '#FFFFFF', 0.30)
        c_hl     = _blend_hex(color_petalo, '#FFFFFF', 0.58)

        # Pétalos traseros (más oscuros, detrás)
        for sx in (-1, 1):
            canvas.create_polygon(
                cx + sx*int(pw*0.6),  top_y + int(ph*0.22),
                cx + sx*int(pw*2.1),  top_y - int(ph*0.50),
                cx + sx*int(pw*1.55), top_y - ph - int(6*s),
                cx + sx*int(pw*0.25), top_y - int(ph*0.72),
                fill=c_dark, outline='', smooth=True)

        # Pétalos laterales frontales + highlight
        for sx in (-1, 1):
            canvas.create_polygon(
                cx + sx*int(pw*0.35), top_y + int(ph*0.35),
                cx + sx*int(pw*2.25), top_y - int(ph*0.28),
                cx + sx*int(pw*1.85), top_y - ph - int(3*s),
                cx + sx*int(pw*0.15), top_y - int(ph*0.75),
                fill=color_petalo, outline='', smooth=True)
            canvas.create_polygon(
                cx + sx*int(pw*0.45), top_y + int(ph*0.22),
                cx + sx*int(pw*1.55), top_y - int(ph*0.22),
                cx + sx*int(pw*1.25), top_y - ph,
                cx + sx*int(pw*0.22), top_y - int(ph*0.58),
                fill=c_inner, outline='', smooth=True)

        # Pétalo central (más prominente)
        canvas.create_polygon(
            cx - int(pw*0.78), top_y + int(ph*0.38),
            cx - int(pw*1.12), top_y - int(ph*0.55),
            cx,                top_y - ph - int(10*s),
            cx + int(pw*1.12), top_y - int(ph*0.55),
            cx + int(pw*0.78), top_y + int(ph*0.38),
            fill=color_petalo, outline='', smooth=True)
        canvas.create_polygon(
            cx - int(pw*0.30), top_y + int(ph*0.18),
            cx - int(pw*0.40), top_y - int(ph*0.42),
            cx,                top_y - ph - int(5*s),
            cx + int(pw*0.40), top_y - int(ph*0.42),
            cx + int(pw*0.30), top_y + int(ph*0.18),
            fill=c_hl, outline='', smooth=True)

        # Sombra interior del cuenco
        shadow_c = _blend_hex(color_petalo, '#000000', 0.32)
        canvas.create_oval(
            cx - int(pw*0.82), top_y + int(ph*0.14),
            cx + int(pw*0.82), top_y + int(ph*0.44),
            fill=shadow_c, outline='')

        # Pistilo dorado con brillo
        py = top_y - int(ph * 0.10)
        pistil_c = _blend_hex('#F59E0B', color_petalo, 0.35)
        canvas.create_oval(
            cx - int(3.5*s), py - int(3.5*s),
            cx + int(3.5*s), py + int(3.5*s),
            fill=pistil_c, outline='')
        canvas.create_oval(
            cx - int(1.5*s), py - int(1.5*s),
            cx + int(1.5*s), py + int(1.5*s),
            fill='#FEF3C7', outline='')

    def _render_header(self, canvas, w, h):
        """Degradado atardecer suave + nebulosas + estrellas + tulipanes mejorados + texto con glow."""
        import random
        canvas.delete('all')

        # ── Gradiente suave (interpolado, no bandas) ──────────────────────
        n_strips = max(h, 1)
        stops = _SUNSET
        for i in range(n_strips):
            t = i / max(n_strips - 1, 1) * (len(stops) - 1)
            idx = min(int(t), len(stops) - 2)
            col = _blend_hex(stops[idx], stops[idx + 1], t - idx)
            canvas.create_line(0, i, w, i, fill=col)

        # ── Nebulosas (halos de color difuso en el fondo) ─────────────────
        nebulas = [
            (int(w * 0.18), int(h * 0.35), int(w * 0.14), _C['morado']),
            (int(w * 0.82), int(h * 0.28), int(w * 0.12), _C['violeta']),
            (int(w * 0.50), int(h * 0.60), int(w * 0.10), _C['magenta']),
        ]
        mid_col = stops[len(stops) // 2]
        for nx, ny, nr, nc in nebulas:
            for extra in (38, 26, 16, 8):
                gc = _blend_hex(nc, mid_col, 1.0 - extra / 45.0)
                canvas.create_oval(nx-nr-extra, ny-nr-extra,
                                   nx+nr+extra, ny+nr+extra,
                                   fill=gc, outline='')

        # ── Estrellas y destellos ─────────────────────────────────────────
        rng = random.Random(42)
        star_cols = ['#FFFFFF', '#DDD6FE', '#FBB027', '#C4B5FD', '#FEF9C3']
        for _ in range(110):
            sx = rng.randint(8, w - 8)
            sy = rng.randint(2, int(h * 0.78))
            r  = rng.choice([1, 1, 1, 1, 2, 2])
            ac = rng.choice(star_cols)
            if rng.random() < 0.22:
                # Destello de 4 puntas
                ln = r * 4
                canvas.create_line(sx - ln, sy, sx + ln, sy, fill=ac, width=1)
                canvas.create_line(sx, sy - ln, sx, sy + ln, fill=ac, width=1)
                canvas.create_oval(sx - r, sy - r, sx + r, sy + r,
                                   fill=ac, outline='')
            else:
                canvas.create_oval(sx - r, sy - r, sx + r, sy + r,
                                   fill=ac, outline='')

        # ── Tulipanes (8 en total, 4 por lado, tamaños escalonados) ───────
        configs = [
            # izquierda (de afuera hacia adentro)
            (0.012, 0,  1.00, _C['tulipan_lila']),
            (0.052, 4,  0.82, _C['lavanda']),
            (0.092, 8,  0.67, _C['tulipan_rosa']),
            (0.132, 12, 0.54, _C['morado']),
            (0.168, 16, 0.42, _C['violeta_claro']),
            (0.200, 19, 0.32, _C['sunset_pink']),
            # derecha (de afuera hacia adentro)
            (0.988, 0,  1.00, _C['tulipan_rosa']),
            (0.948, 4,  0.82, _C['lavanda']),
            (0.908, 8,  0.67, _C['tulipan_lila']),
            (0.868, 12, 0.54, _C['violeta_claro']),
            (0.832, 16, 0.42, _C['morado']),
            (0.800, 19, 0.32, _C['sunset_amber']),
        ]
        for xr, yo, sc, col in configs:
            self._tulipan(canvas, int(w * xr), h + 4 + yo, sc, col)

        # ── Texto con efecto glow ─────────────────────────────────────────
        nombre = self.usuario.get('nombre_completo', '')
        saludo = f"Bienvenida, {nombre}"
        tx, ty = w // 2, h // 2 - 16
        # Linea dorada decorativa
        line_w = min(320, int(w * 0.28))
        for off, alpha in ((3, 0.15), (2, 0.35), (1, 0.65), (0, 1.0)):
            lc = _blend_hex(_C['sunset_amber'], _C['fondo'], 1.0 - alpha)
            canvas.create_line(tx - line_w + off, ty + 38 + off,
                               tx + line_w + off, ty + 38 + off,
                               fill=lc, width=1)
        # Glow del texto
        for off, gcol in ((6, '#1A0A40'), (5, '#2D1B69'), (4, '#3B1F8A'),
                          (3, '#4C1D95'), (2, '#7C3AED'), (1, '#A78BFA')):
            canvas.create_text(tx + off, ty + off,
                               text=saludo,
                               font=('Segoe UI', 18, 'bold'),
                               fill=gcol, anchor='center')
        canvas.create_text(tx, ty,
                           text=saludo,
                           font=('Segoe UI', 18, 'bold'),
                           fill='#FFFFFF', anchor='center')
        # Subtítulo
        canvas.create_text(tx, ty + 22,
                           text="\u2014  Los Pocitos Azufrados  \u2022  Panel Financiero  \u2014",
                           font=('Segoe UI', 9, 'italic'),
                           fill='#C4B5FD', anchor='center')

        # ── Módulo activo y fecha ─────────────────────────────────────────
        if self.modulo_actual:
            canvas.create_text(174, h // 2,
                               text=f"▶  {self.modulo_actual}",
                               font=('Segoe UI', 10, 'bold'),
                               fill=_C['sunset_amber'], anchor='w')
        dias  = ['Lunes','Martes','Miercoles','Jueves','Viernes','Sabado','Domingo']
        meses = ['enero','feb','mar','abr','may','jun','jul','ago','sep','oct','nov','dic']
        hoy   = datetime.datetime.now()
        fstr  = f"{dias[hoy.weekday()]} {hoy.day} de {meses[hoy.month-1]}, {hoy.year}"
        canvas.create_text(w - 18, h // 2,
                           text=fstr,
                           font=('Segoe UI', 9),
                           fill=_C['sunset_amber'], anchor='e')

    # ─── ESTRUCTURA PRINCIPAL ─────────────────────────────────────────────────

    def _crear_interfaz(self):
        # ── HEADER: canvas con degradado atardecer y tulipanes ────────────────
        HDR_H = 130
        self._canvas_hdr = tk.Canvas(self.root, height=HDR_H,
                                     highlightthickness=0, bd=0)
        self._canvas_hdr.pack(fill='x', side='top')

        def _on_hdr_resize(evt):
            self._render_header(self._canvas_hdr, evt.width, HDR_H)
        self._canvas_hdr.bind('<Configure>', _on_hdr_resize)

        # Línea de acento violeta (3px)
        tk.Frame(self.root, bg=_C['violeta'], height=3).pack(fill='x')

        # ── CUERPO ────────────────────────────────────────────────────────────
        body = tk.Frame(self.root, bg=_C['fondo'])
        body.pack(fill='both', expand=True)

        # ── SIDEBAR DOBLE ─────────────────────────────────────────────────────
        self._construir_sidebar(body)

        # ── ÁREA DE CONTENIDO ─────────────────────────────────────────────────
        self.content_frame = tk.Frame(body, bg=_C['fondo'])
        self.content_frame.pack(fill='both', expand=True)

    def _construir_sidebar(self, body):
        """Sidebar de dos columnas: iconos (52px oscuro) + texto (160px violeta oscuro)."""
        sidebar_wrap = tk.Frame(body, bg=_C['fondo_card'])
        sidebar_wrap.pack(fill='y', side='left')
        tk.Frame(body, bg=_C['borde'], width=1).pack(fill='y', side='left')

        # Logout fijo al fondo (se empaca primero con side='bottom')
        logout_row = tk.Frame(sidebar_wrap, bg=_C['fondo_card'])
        logout_row.pack(fill='x', side='bottom')
        tk.Frame(logout_row, bg=_C['sidebar'], width=52).pack(side='left', fill='y')
        logout_right = tk.Frame(logout_row, bg=_C['fondo_card'])
        logout_right.pack(side='left', fill='both', expand=True)
        tk.Frame(logout_right, bg=_C['borde'], height=1).pack(fill='x', padx=8)
        tk.Button(
            logout_right, text='Cerrar Sesion',
            font=('Segoe UI', 9),
            fg=_C['error'], bg=_C['fondo_card'],
            relief='flat', anchor='w', cursor='hand2', bd=0,
            padx=10, pady=8,
            activebackground=_C['fondo_card_alt'],
            activeforeground=_C['error'],
            command=self._cerrar_sesion
        ).pack(fill='x', pady=(0, 6))

        # Canvas scrollable para los ítems del menú
        sb_canvas = tk.Canvas(sidebar_wrap, bg=_C['fondo_card'], width=212,
                              highlightthickness=0, bd=0)
        sb_canvas.pack(fill='both', expand=True)
        sb_inner = tk.Frame(sb_canvas, bg=_C['fondo_card'])
        _sb_win = sb_canvas.create_window((0, 0), window=sb_inner, anchor='nw')
        sb_inner.bind('<Configure>', lambda e: sb_canvas.configure(
            scrollregion=sb_canvas.bbox('all')))
        sb_canvas.bind('<Configure>', lambda e: sb_canvas.itemconfig(_sb_win, width=e.width))

        def _sb_scroll(event):
            d = int(-1 * (event.delta / 120)) if event.delta else (1 if event.num == 5 else -1)
            sb_canvas.yview_scroll(d, 'units')

        def _bind_sb_scroll(widget):
            """Propaga la rueda de cualquier widget hijo al canvas del sidebar."""
            widget.bind('<MouseWheel>', _sb_scroll)
            widget.bind('<Button-4>', lambda e: _sb_scroll(e))
            widget.bind('<Button-5>', lambda e: _sb_scroll(e))

        sb_canvas.bind('<MouseWheel>', _sb_scroll)
        sb_canvas.bind('<Button-4>', lambda e: _sb_scroll(e))
        sb_canvas.bind('<Button-5>', lambda e: _sb_scroll(e))
        sb_inner.bind('<MouseWheel>', _sb_scroll)
        sb_inner.bind('<Button-4>', lambda e: _sb_scroll(e))
        sb_inner.bind('<Button-5>', lambda e: _sb_scroll(e))

        menu_grupos = [
            (None, [
                ('\u2302', 'Dashboard',       self._cargar_dashboard),
            ]),
            ('OPERACIONES', [
                ('\u0024', 'Caja',            self._abrir_caja),
                ('\u2615', 'Restaurante',     self._abrir_bar),
                ('\u270d', 'Pedidos',         self._abrir_pedidos),
                ('\u229e', 'Cuentas',         self._abrir_cuentas_abiertas),
                ('\u26a1', 'Contingencia',    self._abrir_contingencia),
            ]),
            ('INFORMES', [
                ('\u2261', 'Movimientos',     self._abrir_movimientos),
                ('\u2318', 'Reportes',        self._abrir_reportes),
                ('\u2630', 'Historial',       self._abrir_historial),
                ('\u2212', 'Gastos',          self._abrir_gastos),
                ('\u25a4', 'Boletas',         self._abrir_boletas),
                ('\u263a', 'Clientes',        self._abrir_clientes),
            ]),
            ('ADMINISTRACION', [
                ('\u2295', 'Inventario',      self._abrir_inventario),
                ('\u21c5', 'Proveedores',     self._abrir_proveedores),
                ('\u0024\u0024', 'Nomina',    self._abrir_nomina),
                ('\u2764', 'Socios',          self._abrir_socios),
            ]),
            ('SISTEMA', [
                ('\u2699', 'Usuarios',        self._abrir_usuarios),
                ('\u2714', 'Configuracion',   self._abrir_config),
            ]),
        ]

        for grupo, items in menu_grupos:
            if grupo is not None:
                grp_row = tk.Frame(sb_inner, bg=_C['fondo_card'])
                grp_row.pack(fill='x')
                tk.Frame(grp_row, bg=_C['sidebar'], width=52).pack(side='left', fill='y')
                grp_label_area = tk.Frame(grp_row, bg=_C['fondo_card'])
                grp_label_area.pack(side='left', fill='both', expand=True)
                tk.Frame(grp_label_area, bg=_C['borde'], height=1).pack(
                    fill='x', padx=8, pady=(6, 2))
                tk.Label(grp_label_area, text=grupo,
                         font=('Segoe UI', 7, 'bold'),
                         fg=_C['dim'], bg=_C['fondo_card']
                         ).pack(anchor='w', padx=10, pady=(0, 2))

            for icono, texto, comando in items:
                row = tk.Frame(sb_inner, bg=_C['fondo_card'])
                row.pack(fill='x')
                _bind_sb_scroll(row)

                icon_cell = tk.Frame(row, bg=_C['sidebar'], width=52)
                icon_cell.pack(side='left', fill='y')
                icon_cell.pack_propagate(False)
                _bind_sb_scroll(icon_cell)

                btn_icon = tk.Button(
                    icon_cell, text=icono,
                    font=('Segoe UI Symbol', 13),
                    fg=_C['lavanda'], bg=_C['sidebar'],
                    relief='flat', bd=0, cursor='hand2',
                    padx=0, pady=7,
                    activeforeground=_C['tulipan_lila'],
                    activebackground=_C['violeta'],
                    command=comando
                )
                btn_icon.pack(fill='both', expand=True)
                _bind_sb_scroll(btn_icon)

                active_bar = tk.Frame(row, bg=_C['fondo_card'], width=3)
                active_bar.pack(side='left', fill='y')
                _bind_sb_scroll(active_bar)

                btn_text = tk.Button(
                    row, text=texto,
                    font=('Segoe UI', 9),
                    fg=_C['texto_sec'], bg=_C['fondo_card'],
                    relief='flat', bd=0, cursor='hand2',
                    anchor='w', padx=10, pady=7,
                    activeforeground=_C['texto'],
                    activebackground=_C['fondo_card_alt'],
                    command=comando
                )
                btn_text.pack(side='left', fill='both', expand=True)
                _bind_sb_scroll(btn_text)

                self._icon_btns[texto] = (btn_icon, active_bar)
                self._text_btns[texto] = btn_text

                def _bind_hover(bi, bt, nom):
                    def on_enter(e):
                        if self.modulo_actual != nom:
                            bi.config(bg=_C['violeta'], fg=_C['tulipan_lila'])
                            bt.config(bg=_C['fondo_card_alt'], fg=_C['texto'])
                    def on_leave(e):
                        if self.modulo_actual != nom:
                            bi.config(bg=_C['sidebar'], fg=_C['lavanda'])
                            bt.config(bg=_C['fondo_card'], fg=_C['texto_sec'])
                    for w in (bi, bt):
                        w.bind('<Enter>', on_enter)
                        w.bind('<Leave>', on_leave)
                _bind_hover(btn_icon, btn_text, texto)


    # ─── NAVEGACIÓN Y ESTADO DEL MENÚ ─────────────────────────────────────────

    def _limpiar_contenido(self):
        # Limpiar scroll del dashboard home si estaba activo
        try:
            self.root.unbind_all('<MouseWheel>')
            self.root.unbind_all('<Button-4>')
            self.root.unbind_all('<Button-5>')
        except Exception:
            pass
        if self._instancia_modulo is not None:
            if hasattr(self._instancia_modulo, 'detener'):
                try:
                    self._instancia_modulo.detener()
                except Exception:
                    pass
            self._instancia_modulo = None
        try:
            for widget in self.content_frame.winfo_children():
                try:
                    widget.destroy()
                except Exception:
                    pass
        except Exception:
            pass

    def _marcar_menu(self, nombre):
        self.modulo_actual = nombre
        # Refrescar el nombre del modulo en el header
        try:
            w = self._canvas_hdr.winfo_width()
            h = self._canvas_hdr.winfo_height()
            if w > 10:
                self._render_header(self._canvas_hdr, w, h)
        except Exception:
            pass
        for key in self._icon_btns:
            btn_icon, active_bar = self._icon_btns[key]
            btn_text = self._text_btns[key]
            if key == nombre:
                btn_icon.config(bg=_C['violeta'], fg=_C['tulipan_lila'])
                active_bar.config(bg=_C['tulipan_lila'])
                btn_text.config(bg=_C['fondo_card_alt'], fg=_C['texto'],
                                font=('Segoe UI', 9, 'bold'))
            else:
                btn_icon.config(bg=_C['sidebar'], fg=_C['lavanda'])
                active_bar.config(bg=_C['fondo_card'])
                btn_text.config(bg=_C['fondo_card'], fg=_C['texto_sec'],
                                font=('Segoe UI', 9))

    def _abrir_modulo(self, nombre, clase_modulo, *args):
        self.root.update_idletasks()
        self._limpiar_contenido()
        self._marcar_menu(nombre)
        try:
            self._instancia_modulo = clase_modulo(self.content_frame, self.usuario, *args)
        except Exception as e:
            import traceback, logging
            logging.getLogger("pocitos").error(
                f"Error abriendo '{nombre}':\n{traceback.format_exc()}"
            )
            self._instancia_modulo = None
            tk.Label(self.content_frame,
                     text=f"Error al cargar '{nombre}':\n{str(e)}",
                     font=('Segoe UI', 11), fg=_C['error'],
                     bg=_C['fondo']).pack(pady=50)
            return
        # Scroll genérico: la rueda del mouse funciona en cualquier widget scrollable
        def _wheel_generic(event, _d=0):
            d = _d or (int(-1 * (event.delta / 120)) if event.delta else 0)
            w = event.widget
            for _ in range(8):
                if hasattr(w, 'yview_scroll'):
                    try:
                        w.yview_scroll(d, 'units')
                        return
                    except Exception:
                        pass
                w = getattr(w, 'master', None)
                if not w:
                    break
        self.root.bind_all('<MouseWheel>', _wheel_generic)
        self.root.bind_all('<Button-4>', lambda e: _wheel_generic(e, -1))
        self.root.bind_all('<Button-5>', lambda e: _wheel_generic(e, 1))

    # ─── DASHBOARD HOME ───────────────────────────────────────────────────────

    def _cargar_dashboard(self):
        self._limpiar_contenido()
        self._marcar_menu('Dashboard')

        canvas = tk.Canvas(self.content_frame, bg=_C['fondo'], highlightthickness=0)
        sb = ttk.Scrollbar(self.content_frame, orient='vertical', command=canvas.yview)
        sf = tk.Frame(canvas, bg=_C['fondo'])
        sf.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        _win = canvas.create_window((0, 0), window=sf, anchor='nw')
        canvas.configure(yscrollcommand=sb.set)
        canvas.bind('<Configure>', lambda e: canvas.itemconfig(_win, width=e.width))
        canvas.pack(side='left', fill='both', expand=True)
        sb.pack(side='right', fill='y')

        # Scroll con mousewheel: solo cuando el cursor está sobre este canvas
        # (no secuestra el scroll de treeviews u otros widgets)
        def _scroll_canvas(e):
            canvas.yview_scroll(int(-1 * (e.delta / 120)), 'units')
        def _scroll_up(e):
            canvas.yview_scroll(-1, 'units')
        def _scroll_dn(e):
            canvas.yview_scroll(1, 'units')
        def _bind_scroll(e=None):
            self.root.bind_all('<MouseWheel>', _scroll_canvas)
            self.root.bind_all('<Button-4>', _scroll_up)
            self.root.bind_all('<Button-5>', _scroll_dn)
        def _unbind_scroll(e=None):
            try:
                self.root.unbind_all('<MouseWheel>')
                self.root.unbind_all('<Button-4>')
                self.root.unbind_all('<Button-5>')
            except Exception:
                pass
        canvas.bind('<Enter>', _bind_scroll)
        canvas.bind('<Leave>', _unbind_scroll)
        sf.bind('<Enter>', _bind_scroll)
        # Activar inmediatamente (la pantalla ya está mostrando el dashboard)
        _bind_scroll()

        # Saludo
        hdr = tk.Frame(sf, bg=_C['fondo'])
        hdr.pack(fill='x', padx=24, pady=(18, 6))
        hoy = datetime.datetime.now()
        saludo = ('Buenos dias' if hoy.hour < 12
                  else 'Buenas tardes' if hoy.hour < 18
                  else 'Buenas noches')
        tk.Label(hdr, text=f"{saludo}, {self.usuario.get('nombre_completo','')}",
                 font=('Segoe UI', 18, 'bold'),
                 fg=_C['texto'], bg=_C['fondo']).pack(anchor='w')
        tk.Label(hdr, text=hoy.strftime('%A, %d de %B de %Y'),
                 font=('Segoe UI', 10),
                 fg=_C['texto_sec'], bg=_C['fondo']).pack(anchor='w')

        # KPIs
        kpis = self._obtener_kpis()

        def _delta(actual, anterior):
            if anterior == 0:
                return None, None
            pct = (actual - anterior) / anterior * 100
            flecha = '\u25b2' if pct >= 0 else '\u25bc'
            sign = '+' if pct >= 0 else ''
            color = _C['exito'] if pct >= 0 else _C['error']
            return f"{flecha} {sign}{pct:.0f}% vs anterior", color

        def _kpi_card(parent, col_idx, n_cols, titulo, valor, barra_col, delta, cmd):
            parent.columnconfigure(col_idx, weight=1)
            shadow = tk.Frame(parent, bg=_C['borde'])
            shadow.grid(row=0, column=col_idx, padx=5, pady=(2, 6), sticky='nsew')
            card = tk.Frame(shadow, bg=_C['fondo_card'])
            card.pack(fill='both', expand=True, padx=(0, 2), pady=(0, 2))
            tk.Frame(card, bg=barra_col, height=4).pack(fill='x')
            inner = tk.Frame(card, bg=_C['fondo_card'], padx=14, pady=12)
            inner.pack(fill='both', expand=True)
            tk.Label(inner, text=titulo, font=('Segoe UI', 8, 'bold'),
                     fg=_C['texto_sec'], bg=_C['fondo_card']).pack(anchor='w')
            tk.Label(inner, text=valor, font=('Consolas', 18, 'bold'),
                     fg=_C['texto'], bg=_C['fondo_card'], anchor='w').pack(fill='x', pady=(3, 0))
            delta_txt, delta_col = delta if delta else (None, None)
            if delta_txt:
                tk.Label(inner, text=delta_txt, font=('Segoe UI', 8),
                         fg=delta_col, bg=_C['fondo_card'], anchor='w').pack(fill='x', pady=(1, 3))
            else:
                tk.Frame(inner, bg=_C['fondo_card'], height=4).pack()
            if cmd:
                tk.Frame(inner, bg=_C['borde'], height=1).pack(fill='x', pady=(3, 3))
                lbl = tk.Label(inner, text='Ver detalle  >', font=('Segoe UI', 8),
                               fg=_C['violeta_claro'], bg=_C['fondo_card'],
                               cursor='hand2', anchor='e')
                lbl.pack(fill='x')
                lbl.bind('<Button-1>', lambda e, c=cmd: c())

        # Fila 1: financiero
        row1 = tk.Frame(sf, bg=_C['fondo'])
        row1.pack(fill='x', padx=24, pady=(12, 2))
        _kpi_card(row1, 0, 4, 'Ventas Hoy',      format_money(kpis['ventas_hoy']),
                  _C['violeta'],       _delta(kpis['ventas_hoy'],  kpis['ventas_ayer']),           self._abrir_movimientos)
        _kpi_card(row1, 1, 4, 'Ventas del Mes',   format_money(kpis['ventas_mes']),
                  _C['violeta_claro'], _delta(kpis['ventas_mes'],  kpis['ventas_mes_anterior']),    self._abrir_movimientos)
        _kpi_card(row1, 2, 4, 'Gastos del Mes',   format_money(kpis['gastos_mes']),
                  _C['error'],         _delta(kpis['gastos_mes'],  kpis['gastos_mes_anterior']),    self._abrir_gastos)
        utilidad   = kpis['ventas_mes'] - kpis['gastos_mes']
        util_color = _C['exito'] if utilidad >= 0 else _C['error']
        _kpi_card(row1, 3, 4, 'Utilidad Neta',    format_money(utilidad),
                  util_color,          None,                                                        self._abrir_reportes)

        # Fila 2: operacional / socios
        row2 = tk.Frame(sf, bg=_C['fondo'])
        row2.pack(fill='x', padx=24, pady=(2, 8))
        _kpi_card(row2, 0, 4, 'Socios Activos',   str(kpis['socios_activos']),
                  _C['exito'],         None,                                                        self._abrir_socios)
        mora_col = _C['error'] if kpis['socios_mora'] > 0 else _C['exito']
        _kpi_card(row2, 1, 4, 'Socios en Mora',   str(kpis['socios_mora']),
                  mora_col,            None,                                                        self._abrir_socios)
        _kpi_card(row2, 2, 4, 'Nomina del Mes',   format_money(kpis['nomina_mes']),
                  _C['sunset_amber'],  None,                                                        self._abrir_nomina)
        _kpi_card(row2, 3, 4, 'Boletas (personas)',str(int(kpis['boletas_mes'])),
                  _C['tulipan_rosa'],  None,                                                        self._abrir_boletas)

        # Alertas + Métodos de pago (lado a lado)
        alertas_row = tk.Frame(sf, bg=_C['fondo'])
        alertas_row.pack(fill='x', padx=24, pady=(0, 10))
        alertas_row.columnconfigure(0, weight=2)
        alertas_row.columnconfigure(1, weight=3)

        # Panel alertas
        al_sh = tk.Frame(alertas_row, bg=_C['borde'])
        al_sh.grid(row=0, column=0, padx=(0, 6), sticky='nsew')
        al_card = tk.Frame(al_sh, bg=_C['fondo_card'])
        al_card.pack(fill='both', expand=True, padx=(0, 2), pady=(0, 2))
        tk.Frame(al_card, bg=_C['advertencia'], height=4).pack(fill='x')
        tk.Label(al_card, text='Alertas', font=('Segoe UI', 10, 'bold'),
                 fg=_C['texto'], bg=_C['fondo_card']).pack(anchor='w', padx=14, pady=(8, 4))
        alertas = self._obtener_alertas(kpis)
        if alertas:
            for emoji, msg, col in alertas:
                row_al = tk.Frame(al_card, bg=_C['fondo_card'])
                row_al.pack(fill='x', padx=10, pady=2)
                tk.Label(row_al, text=emoji, font=('Segoe UI', 10),
                         fg=col, bg=_C['fondo_card'], width=2).pack(side='left')
                tk.Label(row_al, text=msg, font=('Segoe UI', 9),
                         fg=col, bg=_C['fondo_card'], anchor='w', wraplength=220,
                         justify='left').pack(side='left', padx=(4, 0))
        else:
            tk.Label(al_card, text='Sin alertas — todo en orden',
                     font=('Segoe UI', 10), fg=_C['exito'],
                     bg=_C['fondo_card']).pack(pady=16)
        tk.Frame(al_card, bg=_C['fondo_card'], height=10).pack()

        # Panel metodos de pago
        mp_sh = tk.Frame(alertas_row, bg=_C['borde'])
        mp_sh.grid(row=0, column=1, padx=(6, 0), sticky='nsew')
        mp_card = tk.Frame(mp_sh, bg=_C['fondo_card'])
        mp_card.pack(fill='both', expand=True, padx=(0, 2), pady=(0, 2))
        tk.Frame(mp_card, bg=_C['morado'], height=4).pack(fill='x')
        hoy_mp = datetime.date.today()
        mes_ini_mp = hoy_mp.replace(day=1).isoformat()
        tk.Label(mp_card, text='Ingresos por Metodo de Pago — Mes actual',
                 font=('Segoe UI', 10, 'bold'), fg=_C['texto'],
                 bg=_C['fondo_card']).pack(anchor='w', padx=14, pady=(8, 4))
        try:
            with conexion_segura() as conn:
                mp_rows = conn.execute("""
                    SELECT metodo_pago,
                           COUNT(*) AS transacciones,
                           COALESCE(SUM(total),0) AS total
                    FROM ventas
                    WHERE estado != 'ANULADA'
                      AND fecha_creacion >= ?
                    GROUP BY metodo_pago
                    ORDER BY total DESC
                """, (mes_ini_mp,)).fetchall()
            total_mp = sum(r['total'] for r in mp_rows) or 1
            colores_mp = [_C['violeta'], _C['tulipan_lila'], _C['exito'],
                          _C['sunset_amber'], _C['magenta'], _C['advertencia']]
            for i, r in enumerate(mp_rows):
                pct = r['total'] / total_mp * 100
                col_mp = colores_mp[i % len(colores_mp)]
                fila_mp = tk.Frame(mp_card, bg=_C['fondo_card'])
                fila_mp.pack(fill='x', padx=14, pady=3)
                tk.Label(fila_mp, text=r['metodo_pago'], font=('Segoe UI', 9),
                         fg=_C['texto_sec'], bg=_C['fondo_card'], width=14,
                         anchor='w').pack(side='left')
                bar_bg = tk.Frame(fila_mp, bg=_C['fondo_card_alt'], height=14)
                bar_bg.pack(side='left', fill='x', expand=True, padx=(4, 8))
                bar_bg.update_idletasks()
                bar_fill = tk.Frame(bar_bg, bg=col_mp, height=14)
                bar_fill.place(relwidth=min(pct / 100, 1.0), relheight=1)
                tk.Label(fila_mp, text=format_money(r['total']), font=('Segoe UI', 9, 'bold'),
                         fg=col_mp, bg=_C['fondo_card'], width=12, anchor='e').pack(side='right')
        except Exception:
            tk.Label(mp_card, text='Sin datos este mes', font=('Segoe UI', 9),
                     fg=_C['dim'], bg=_C['fondo_card']).pack(pady=12)
        tk.Frame(mp_card, bg=_C['fondo_card'], height=10).pack()

        # Cuentas abiertas pendientes
        if kpis['cuentas_abiertas'] > 0:
            ca_sh = tk.Frame(sf, bg=_C['borde'])
            ca_sh.pack(fill='x', padx=24, pady=(0, 10))
            ca_card = tk.Frame(ca_sh, bg=_C['fondo_card'])
            ca_card.pack(fill='both', expand=True, padx=(0, 2), pady=(0, 2))
            tk.Frame(ca_card, bg=_C['error'], height=4).pack(fill='x')
            ca_inner = tk.Frame(ca_card, bg=_C['fondo_card'], padx=20, pady=12)
            ca_inner.pack(fill='x')
            tk.Label(ca_inner, text='Cuentas Abiertas Pendientes',
                     font=('Segoe UI', 11, 'bold'),
                     fg=_C['texto_sec'], bg=_C['fondo_card']).pack(side='left')
            tk.Label(ca_inner,
                     text=f"{int(kpis['cuentas_abiertas'])} cuentas   |   {format_money(kpis['cuentas_monto'])}",
                     font=('Consolas', 16, 'bold'),
                     fg=_C['advertencia'], bg=_C['fondo_card']).pack(side='right')

        # Accesos Rapidos
        acc_frame = tk.Frame(sf, bg=_C['fondo'])
        acc_frame.pack(fill='x', padx=24, pady=(4, 10))
        tk.Label(acc_frame, text='Accesos Rapidos', font=('Segoe UI', 12, 'bold'),
                 fg=_C['texto'], bg=_C['fondo']).pack(anchor='w', pady=(0, 8))
        btns = tk.Frame(acc_frame, bg=_C['fondo'])
        btns.pack(fill='x')
        for txt, cmd, col in [
            ('Reportes',   self._abrir_reportes,         _C['violeta']),
            ('Gastos',     self._abrir_gastos,           _C['error']),
            ('Socios',     self._abrir_socios,           _C['morado']),
            ('Nomina',     self._abrir_nomina,           _C['sunset_amber']),
            ('Historial',  self._abrir_historial,        _C['tulipan_lila']),
            ('Inventario', self._abrir_inventario,       _C['tallo']),
        ]:
            tk.Button(btns, text=txt, command=cmd,
                      font=('Segoe UI', 9, 'bold'),
                      bg=col, fg=_C['texto'],
                      relief='flat', bd=0, cursor='hand2',
                      activebackground=_C['violeta_claro'],
                      activeforeground=_C['fondo'],
                      padx=8, pady=9).pack(side='left', fill='x', expand=True, padx=(0, 5))

        # Grafica ventas del mes
        self._mostrar_grafica_ventas(sf)

        # Mas Vendidos
        self._mostrar_productos_top(sf)

    def _obtener_alertas(self, kpis):
        """Retorna lista de (emoji, mensaje, color) con alertas criticas."""
        alertas = []
        # Stock bajo
        if kpis['stock_bajo'] > 0:
            alertas.append(('!', f"{int(kpis['stock_bajo'])} productos con stock bajo o agotado",
                            _C['advertencia']))
        # Socios en mora
        if kpis['socios_mora'] > 0:
            alertas.append(('!', f"{int(kpis['socios_mora'])} socios activos sin pagar cuota de este mes",
                            _C['error']))
        # Cuentas abiertas
        if kpis['cuentas_abiertas'] > 0:
            alertas.append(('!', f"{int(kpis['cuentas_abiertas'])} cuentas abiertas pendientes por cobrar",
                            _C['advertencia']))
        # Resolucion DIAN
        try:
            from models.validaciones import validar_resolucion_dian
            res = validar_resolucion_dian()
            if res['nivel'] in ('advertencia', 'bloqueado'):
                col = _C['error'] if res['nivel'] == 'bloqueado' else _C['advertencia']
                alertas.append(('!', f"DIAN: {res['mensaje']}", col))
        except Exception:
            pass
        # Nomina no registrada
        hoy = datetime.date.today()
        if hoy.day >= 25 and kpis['nomina_mes'] == 0:
            alertas.append(('!', 'No se ha registrado nomina este mes (dia >= 25)',
                            _C['advertencia']))
        return alertas

    def _mostrar_grafica_ventas(self, parent):
        """Gráfica de barras — ventas diarias del mes actual vs mes anterior."""
        import calendar
        try:
            from matplotlib.figure import Figure
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        except ImportError:
            return

        sh = tk.Frame(parent, bg=_C['borde'])
        sh.pack(fill='x', padx=24, pady=(0, 12))
        card = tk.Frame(sh, bg=_C['fondo_card'])
        card.pack(fill='both', expand=True, padx=(0, 2), pady=(0, 2))
        tk.Frame(card, bg=_C['violeta'], height=4).pack(fill='x')
        header = tk.Frame(card, bg=_C['fondo_card'], padx=16, pady=10)
        header.pack(fill='x')
        hoy = datetime.date.today()
        mes_nombre = ['Enero','Febrero','Marzo','Abril','Mayo','Junio',
                      'Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre'][hoy.month - 1]
        tk.Label(header, text=f'Ventas Diarias — {mes_nombre} {hoy.year}',
                 font=('Segoe UI', 11, 'bold'),
                 fg=_C['texto'], bg=_C['fondo_card']).pack(side='left')

        try:
            dias_mes   = calendar.monthrange(hoy.year, hoy.month)[1]
            mes_inicio = hoy.replace(day=1).isoformat()
            mes_fin    = hoy.replace(day=dias_mes).isoformat()
            prim_ant   = (hoy.replace(day=1) - datetime.timedelta(days=1)).replace(day=1)
            dias_ant   = calendar.monthrange(prim_ant.year, prim_ant.month)[1]

            with conexion_segura() as conn:
                rows_act = conn.execute("""
                    SELECT CAST(strftime('%d', fecha_creacion) AS INTEGER) AS dia,
                           COALESCE(SUM(total), 0) AS total
                    FROM ventas
                    WHERE estado != 'ANULADA'
                      AND fecha_creacion >= ? AND fecha_creacion < date(?, '+1 day')
                    GROUP BY dia ORDER BY dia
                """, (mes_inicio, mes_fin)).fetchall()

                rows_ant = conn.execute("""
                    SELECT CAST(strftime('%d', fecha_creacion) AS INTEGER) AS dia,
                           COALESCE(SUM(total), 0) AS total
                    FROM ventas
                    WHERE estado != 'ANULADA'
                      AND fecha_creacion >= ? AND fecha_creacion < date(?, '+1 day')
                    GROUP BY dia ORDER BY dia
                """, (prim_ant.isoformat(), prim_ant.replace(day=dias_ant).isoformat())).fetchall()

            dias_x   = list(range(1, dias_mes + 1))
            vals_act  = {r['dia']: r['total'] for r in rows_act}
            vals_ant  = {r['dia']: r['total'] for r in rows_ant}
            y_act = [vals_act.get(d, 0) / 1000 for d in dias_x]   # en miles
            y_ant = [vals_ant.get(d, 0) / 1000 for d in dias_x]

            fig = Figure(figsize=(12, 2.8), dpi=96)
            fig.patch.set_facecolor(_C['fondo_card'])
            ax = fig.add_subplot(111)
            ax.set_facecolor(_C['fondo_card'])

            ancho = 0.38
            xs = list(range(len(dias_x)))
            bars_ant = ax.bar([x - ancho/2 for x in xs], y_ant, ancho,
                              color=_C['dim'], alpha=0.55, label='Mes anterior')
            bars_act = ax.bar([x + ancho/2 for x in xs], y_act, ancho,
                              color=_C['violeta'], label='Mes actual')

            # Marcar hoy con línea
            ax.axvline(x=hoy.day - 1, color=_C['tulipan_rosa'], linewidth=1.2,
                       linestyle='--', alpha=0.7)

            ax.set_xticks(xs)
            ax.set_xticklabels([str(d) if d % 5 == 0 or d == 1 else '' for d in dias_x],
                                fontsize=7, color=_C['texto_sec'])
            ax.tick_params(axis='y', labelsize=7, colors=_C['texto_sec'])
            ax.yaxis.set_major_formatter(
                __import__('matplotlib.ticker', fromlist=['FuncFormatter']).FuncFormatter(
                    lambda v, _: f'${v:.0f}k'))
            for spine in ax.spines.values():
                spine.set_color(_C['borde'])
            ax.tick_params(colors=_C['texto_sec'])
            ax.legend(fontsize=7, facecolor=_C['fondo_card'],
                      labelcolor=_C['texto_sec'], framealpha=0.8,
                      edgecolor=_C['borde'])
            fig.tight_layout(pad=0.6)

            canvas_fig = FigureCanvasTkAgg(fig, master=card)
            canvas_fig.draw()
            canvas_fig.get_tk_widget().pack(fill='x', padx=6, pady=(0, 8))
        except Exception as e:
            tk.Label(card, text=f'Sin datos de ventas aún ({e})',
                     font=('Segoe UI', 10), fg=_C['dim'],
                     bg=_C['fondo_card']).pack(pady=16)

    def _obtener_kpis(self):
        import calendar
        kpis = {
            'ventas_hoy': 0, 'ventas_ayer': 0, 'stock_bajo': 0,
            'ventas_mes': 0, 'ventas_mes_anterior': 0,
            'gastos_mes': 0, 'gastos_mes_anterior': 0,
            'socios_activos': 0, 'socios_mora': 0,
            'nomina_mes': 0, 'boletas_mes': 0,
            'cuentas_abiertas': 0, 'cuentas_monto': 0,
        }
        try:
            hoy        = datetime.date.today()
            hoy_str    = hoy.isoformat()
            ayer_str   = (hoy - datetime.timedelta(days=1)).isoformat()
            mes_inicio = hoy.replace(day=1).isoformat()
            prim_ant   = (hoy.replace(day=1) - datetime.timedelta(days=1)).replace(day=1)
            dias_ant   = calendar.monthrange(prim_ant.year, prim_ant.month)[1]
            ant_inicio = prim_ant.isoformat()
            ant_fin    = prim_ant.replace(day=min(hoy.day, dias_ant)).isoformat()
            with conexion_segura() as conn:
                for key, qry, params in [
                    ('ventas_hoy',          "SELECT COALESCE(SUM(total),0) t FROM ventas WHERE fecha_creacion>=? AND fecha_creacion<date(?,'+1 day') AND estado!='ANULADA'", (hoy_str, hoy_str)),
                    ('ventas_ayer',         "SELECT COALESCE(SUM(total),0) t FROM ventas WHERE fecha_creacion>=? AND fecha_creacion<date(?,'+1 day') AND estado!='ANULADA'", (ayer_str, ayer_str)),
                    ('stock_bajo',          "SELECT COUNT(*) t FROM productos WHERE activo=1 AND stock_actual<=stock_minimo AND stock_actual>=0", ()),
                    ('ventas_mes',          "SELECT COALESCE(SUM(total),0) t FROM ventas WHERE fecha_creacion>=? AND estado!='ANULADA'", (mes_inicio,)),
                    ('ventas_mes_anterior', "SELECT COALESCE(SUM(total),0) t FROM ventas WHERE fecha_creacion>=? AND fecha_creacion<date(?,'+1 day') AND estado!='ANULADA'", (ant_inicio, ant_fin)),
                    ('gastos_mes',          "SELECT COALESCE(SUM(valor),0) t FROM gastos WHERE fecha>=?", (mes_inicio,)),
                    ('gastos_mes_anterior', "SELECT COALESCE(SUM(valor),0) t FROM gastos WHERE fecha>=? AND fecha<date(?,'+1 day')", (ant_inicio, ant_fin)),
                    ('nomina_mes',          "SELECT COALESCE(SUM(valor),0) t FROM gastos WHERE tipo_gasto='NOMINA' AND fecha>=?", (mes_inicio,)),
                    ('boletas_mes',         "SELECT COALESCE(SUM(cantidad_personas),0) t FROM boletas_entrada WHERE hora_entrada>=?", (mes_inicio,)),
                    ('cuentas_abiertas',    "SELECT COUNT(*) t FROM ventas WHERE tipo='cuenta_abierta' AND estado='PENDIENTE'", ()),
                    ('cuentas_monto',       "SELECT COALESCE(SUM(total),0) t FROM ventas WHERE tipo='cuenta_abierta' AND estado='PENDIENTE'", ()),
                ]:
                    kpis[key] = conn.execute(qry, params).fetchone()['t']
                # Socios en mora: activos sin pago este mes — un solo LEFT JOIN
                kpis['socios_activos'] = conn.execute(
                    "SELECT COUNT(*) FROM socios WHERE estado='ACTIVO' AND activo=1"
                ).fetchone()[0]
                kpis['socios_mora'] = conn.execute("""
                    SELECT COUNT(*) FROM socios s
                    LEFT JOIN pagos_membresia p
                           ON s.id_socio = p.id_socio AND p.anio = ? AND p.mes = ?
                    WHERE s.estado = 'ACTIVO' AND s.activo = 1 AND p.id_socio IS NULL
                """, (hoy.year, hoy.month)).fetchone()[0]
        except Exception as e:
            print(f"Error KPIs contadora: {e}")
        return kpis

    def _mostrar_productos_top(self, parent):
        frame = tk.Frame(parent, bg=_C['fondo'])
        frame.pack(fill='x', padx=24, pady=(0, 20))
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        mes_inicio = datetime.date.today().replace(day=1).isoformat()
        for col_idx, (titulo, color_barra, req_cocina) in enumerate([
            ('Mas Vendidos — Bar',    _C['violeta_claro'], 0),
            ('Mas Vendidos — Cocina', _C['tulipan_lila'],  1),
        ]):
            pad = (0, 6) if col_idx == 0 else (6, 0)
            sh = tk.Frame(frame, bg=_C['borde'])
            sh.grid(row=0, column=col_idx, padx=pad, sticky='nsew')
            frm = tk.Frame(sh, bg=_C['fondo_card'])
            frm.pack(fill='both', expand=True, padx=(0, 2), pady=(0, 2))
            tk.Frame(frm, bg=color_barra, height=4).pack(fill='x')
            tk.Label(frm, text=titulo, font=('Segoe UI', 11, 'bold'),
                     fg=_C['texto'], bg=_C['fondo_card']).pack(padx=14, pady=(10, 5), anchor='w')
            try:
                with conexion_segura() as conn:
                    datos = conn.execute("""
                        SELECT vd.producto_nombre,
                               SUM(vd.cantidad)    AS total_vendido,
                               SUM(vd.total_linea) AS total_dinero
                        FROM venta_detalle vd
                        JOIN ventas    v ON vd.id_venta    = v.id_venta
                        JOIN productos p ON vd.id_producto = p.id_producto
                        WHERE v.estado!='ANULADA'
                          AND v.fecha_creacion>=?
                          AND p.requiere_cocina=?
                        GROUP BY vd.producto_nombre
                        ORDER BY total_vendido DESC
                        LIMIT 8
                    """, (mes_inicio, req_cocina)).fetchall()
                self._render_top_list(frm, datos, color_barra)
            except Exception:
                tk.Label(frm, text='Sin datos aun', font=('Segoe UI', 10),
                         fg=_C['dim'], bg=_C['fondo_card']).pack(pady=20)

    def _render_top_list(self, parent, datos, color):
        if not datos:
            tk.Label(parent, text='Sin ventas registradas aun', font=('Segoe UI', 10),
                     fg=_C['dim'], bg=_C['fondo_card']).pack(pady=20)
            return
        for i, row in enumerate(datos):
            bg = _C['fondo_card_alt'] if i % 2 == 0 else _C['fondo_card']
            item = tk.Frame(parent, bg=bg)
            item.pack(fill='x', padx=14, pady=1)
            pos = ['1.', '2.', '3.'][i] if i < 3 else f'{i+1}.'
            tk.Label(item, text=pos, font=('Segoe UI', 10, 'bold'),
                     fg=color, bg=bg, width=4).pack(side='left')
            tk.Label(item, text=row['producto_nombre'], font=('Segoe UI', 10),
                     fg=_C['texto'], bg=bg).pack(side='left', padx=(4, 0))
            tk.Label(item, text=format_money(row['total_dinero']), font=('Segoe UI', 9),
                     fg=_C['texto_sec'], bg=bg).pack(side='right', padx=(0, 8))
            tk.Label(item, text=f"{row['total_vendido']} uds", font=('Segoe UI', 10, 'bold'),
                     fg=color, bg=bg).pack(side='right', padx=(0, 8))
        tk.Frame(parent, bg=_C['fondo_card'], height=10).pack()

    # ─── NAVEGACIÓN A MÓDULOS ─────────────────────────────────────────────────

    def _abrir_bar(self):
        from modules.pos_module import POSModule
        self._limpiar_contenido()
        self._marcar_menu('Restaurante')
        self._instancia_modulo = POSModule(
            self.content_frame, self.usuario,
            callback_ir_caja=lambda: self._abrir_caja()
        )

    def _abrir_caja(self):
        from modules.caja_module import CajaModule
        self._abrir_modulo('Caja', CajaModule, lambda: self._abrir_bar())

    def _abrir_pedidos(self):
        from modules.pedidos_module import PedidosModule
        self._abrir_modulo('Pedidos', PedidosModule)

    def _abrir_cuentas_abiertas(self):
        from modules.cuentas_abiertas_module import CuentasAbiertasModule
        self._abrir_modulo('Cuentas', CuentasAbiertasModule)

    def _abrir_movimientos(self):
        from modules.movimientos_module import MovimientosModule
        self._abrir_modulo('Movimientos', MovimientosModule)

    def _abrir_reportes(self):
        from modules.reportes_module import ReportesModule
        self._abrir_modulo('Reportes', ReportesModule)

    def _abrir_historial(self):
        from modules.historial_ventas_module import HistorialVentasModule
        self._abrir_modulo('Historial', HistorialVentasModule)

    def _abrir_gastos(self):
        from modules.gastos_module import GastosModule
        self._abrir_modulo('Gastos', GastosModule)

    def _abrir_inventario(self):
        from modules.inventario_module import InventarioModule
        self._abrir_modulo('Inventario', InventarioModule)

    def _abrir_clientes(self):
        from modules.clientes_module import ClientesModule
        self._abrir_modulo('Clientes', ClientesModule)

    def _abrir_boletas(self):
        from modules.boletas_module import BoletasModule
        self._abrir_modulo('Boletas', BoletasModule)

    def _abrir_proveedores(self):
        from modules.proveedores_module import ProveedoresModule
        self._abrir_modulo('Proveedores', ProveedoresModule)

    def _abrir_nomina(self):
        from modules.nomina_module import NominaModule
        self._abrir_modulo('Nomina', NominaModule)

    def _abrir_socios(self):
        from modules.socios_module import SociosModule
        self._abrir_modulo('Socios', SociosModule)

    def _abrir_contingencia(self):
        from modules.contingencia_module import ContingenciaModule
        self._abrir_modulo('Contingencia', ContingenciaModule)

    def _abrir_usuarios(self):
        from modules.usuarios_module import UsuariosModule
        self._abrir_modulo('Usuarios', UsuariosModule)

    def _abrir_config(self):
        from modules.config_module import ConfigModule
        self._abrir_modulo('Configuracion', ConfigModule)

    # ─── AUTO-BLOQUEO ─────────────────────────────────────────────────────────

    def _registrar_actividad(self, event=None):
        self._ultimo_evento = time.time()

    def _programar_verificacion_bloqueo(self):
        try:
            if self.root.winfo_exists():
                self._after_bloqueo_id = self.root.after(
                    10000, self._verificar_inactividad)
        except Exception:
            pass

    def _verificar_inactividad(self):
        try:
            if not self.root.winfo_exists():
                return
        except Exception:
            return
        if not self._bloqueo_activo and time.time() - self._ultimo_evento >= 600:
            self._bloquear_pantalla()
        self._programar_verificacion_bloqueo()

    def _bloquear_pantalla(self):
        if self._bloqueo_activo:
            return
        self._bloqueo_activo = True

        lock = tk.Toplevel(self.root)
        lock.title('Sistema Bloqueado')
        lock.configure(bg=_C['fondo'])
        lock.attributes('-topmost', True)
        lock.grab_set()
        lock.protocol('WM_DELETE_WINDOW', lambda: None)
        try:
            lock.geometry(
                f"{self.root.winfo_width()}x{self.root.winfo_height()}"
                f"+{self.root.winfo_x()}+{self.root.winfo_y()}"
            )
        except Exception:
            lock.geometry('1200x800')

        bg_canvas = tk.Canvas(lock, highlightthickness=0, bd=0)
        bg_canvas.place(relx=0, rely=0, relwidth=1, relheight=1)

        def _draw_lock_bg(evt=None):
            w = bg_canvas.winfo_width()
            h = bg_canvas.winfo_height()
            if w < 10:
                return
            bg_canvas.delete('all')
            n = len(_SUNSET)
            strip = max(1, h // n)
            for i, col in enumerate(_SUNSET):
                bg_canvas.create_rectangle(0, i * strip, w,
                                           min(h, (i + 1) * strip),
                                           fill=col, outline='')
            for tx, ts, tc in [
                (40,  0.8, _C['tulipan_lila']),
                (90,  0.65, _C['tulipan_blanc']),
                (w - 40, 0.8, _C['tulipan_rosa']),
                (w - 90, 0.65, _C['lavanda']),
            ]:
                self._tulipan(bg_canvas, tx, h + 4, ts, tc)

        bg_canvas.bind('<Configure>', lambda e: _draw_lock_bg())
        bg_canvas.after(50, _draw_lock_bg)

        center = tk.Frame(lock, bg=_C['fondo_card'],
                          highlightbackground=_C['violeta'], highlightthickness=2)
        center.place(relx=0.5, rely=0.5, anchor='center', width=360)
        tk.Frame(center, bg=_C['violeta'], height=4).pack(fill='x')

        inner_lock = tk.Frame(center, bg=_C['fondo_card'], padx=30, pady=28)
        inner_lock.pack(fill='both', expand=True)

        tk.Label(inner_lock, text='Pantalla Bloqueada',
                 font=('Segoe UI', 20, 'bold'),
                 fg=_C['lavanda'], bg=_C['fondo_card']).pack(pady=(0, 6))
        tk.Label(inner_lock,
                 text=f"Usuario: {self.usuario.get('nombre_completo','')}",
                 font=('Segoe UI', 10),
                 fg=_C['texto_sec'], bg=_C['fondo_card']).pack(pady=(0, 20))
        tk.Label(inner_lock, text='Ingrese su PIN para continuar:',
                 font=('Segoe UI', 10),
                 fg=_C['texto'], bg=_C['fondo_card']).pack(pady=(0, 8))

        entry_pin = tk.Entry(inner_lock, font=('Segoe UI', 18),
                             show='*', width=8, justify='center',
                             relief='solid', bd=1,
                             bg=_C['fondo_card_alt'], fg=_C['lavanda'],
                             insertbackground=_C['lavanda'])
        entry_pin.pack(pady=(0, 8))
        entry_pin.focus_set()

        lbl_err = tk.Label(inner_lock, text='',
                           font=('Segoe UI', 9),
                           fg=_C['error'], bg=_C['fondo_card'])
        lbl_err.pack(pady=(0, 12))

        def _verificar_pin(pin_ing):
            try:
                with conexion_segura() as conn:
                    row = conn.execute(
                        'SELECT pin FROM usuarios WHERE id_usuario=? AND activo=1',
                        (self.usuario['id_usuario'],)
                    ).fetchone()
                if not row or not row['pin']:
                    return False
                guardado = row['pin']
                if guardado.startswith('$2'):
                    try:
                        import bcrypt
                        return bcrypt.checkpw(pin_ing.encode('utf-8'),
                                              guardado.encode('utf-8'))
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
                lbl_err.config(text=f'PIN incorrecto. Intentos restantes: {restantes}')
                entry_pin.delete(0, tk.END)
                entry_pin.focus_set()

        def _cerrar_app():
            if messagebox.askyesno('Cerrar aplicacion',
                                   'Si no recuerda el PIN puede cerrar la aplicacion.\n'
                                   '¿Desea salir?', parent=lock):
                self.root.destroy()

        btn_des = tk.Button(inner_lock, text='Desbloquear', command=_desbloquear,
                            font=('Segoe UI', 10, 'bold'),
                            bg=_C['violeta'], fg=_C['texto'],
                            relief='flat', bd=0, cursor='hand2',
                            activebackground=_C['morado'],
                            activeforeground=_C['texto'])
        btn_des.pack(fill='x', ipady=6, pady=(0, 6))
        tk.Button(inner_lock, text='Cerrar aplicacion', command=_cerrar_app,
                  font=('Segoe UI', 9),
                  bg=_C['error'], fg='white',
                  relief='flat', bd=0, cursor='hand2',
                  activebackground='#DC2626',
                  activeforeground='white').pack(fill='x', ipady=4)

        entry_pin.bind('<Return>', lambda e: _desbloquear())

    # ─── CERRAR SESIÓN / SALIR ────────────────────────────────────────────────

    def _cancelar_bloqueo_timer(self):
        if self._after_bloqueo_id:
            try:
                self.root.after_cancel(self._after_bloqueo_id)
            except Exception:
                pass
            self._after_bloqueo_id = None

    def _cerrar_sesion_db(self):
        id_sesion = self.usuario.get('id_sesion')
        if id_sesion:
            try:
                with conexion_segura() as conn:
                    conn.execute(
                        "UPDATE sesiones SET fecha_fin=datetime('now','localtime') "
                        'WHERE id_sesion=?', (id_sesion,)
                    )
            except Exception:
                pass

    def _cerrar_sesion(self):
        if messagebox.askyesno('Cerrar Sesion', '¿Desea cerrar sesion?'):
            self._cancelar_bloqueo_timer()
            self._limpiar_contenido()
            self._cerrar_sesion_db()
            # Reusar el root — limpiar y abrir login sin llamar mainloop de nuevo
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
        if messagebox.askyesno('Salir', '¿Desea cerrar el sistema?'):
            self._cancelar_bloqueo_timer()
            # Detener módulo activo antes de destruir
            if self._instancia_modulo is not None:
                if hasattr(self._instancia_modulo, 'detener'):
                    try:
                        self._instancia_modulo.detener()
                    except Exception:
                        pass
                self._instancia_modulo = None
            self._cerrar_sesion_db()
            try:
                self.root.destroy()
            except Exception:
                pass
