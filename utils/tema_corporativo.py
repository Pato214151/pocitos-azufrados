"""
Tema Corporativo - Club Los Pocitos Azufrados
Paleta "Pocitos" — Sidebar bosque oscuro · Contenido limpio · Acciones verde ácido y azul
"""

import tkinter as tk
from tkinter import ttk

# ============================================================
#  ESCALA RESPONSIVE — se calcula una sola vez al importar
# ============================================================
def _detectar_escala():
    """Detecta la resolución de pantalla usando ctypes (sin crear ventana Tk)."""
    try:
        import ctypes
        user32 = ctypes.windll.user32
        # NO llamar SetProcessDPIAware aquí: Tkinter maneja su propio DPI
        sw = user32.GetSystemMetrics(0)
        sh = user32.GetSystemMetrics(1)
        escala = max(0.75, min(1.0, sh / 1080))
        return escala, sw, sh
    except Exception:
        return 1.0, 1920, 1080

SCALE, SCREEN_W, SCREEN_H = _detectar_escala()

def _fs(size):
    """Escala un tamaño de fuente según la resolución de pantalla."""
    return max(8, int(size * SCALE))

# ============================================================
#  PALETA DE COLORES — "Pocitos"
#
#  Verde Ácido  #9BC53D  → botón principal COBRAR
#  Azul         #2E91D1  → botones secundarios
#  Terracota    #A44A3F  → cancelar / alertas
#  Naranja      #F4A261  → productos pendientes de aprobación
#  Fondo gris   #F8F9FA  → área de contenido
#  Negro carbón #1A1A1A  → texto principal
# ============================================================
COLORES = {
    # ── MARCA / ACCIONES ────────────────────────────────────
    'primario':         '#1B6E3A',   # Verde bosque — headers de módulos (bg con texto blanco)
    'primario_claro':   '#2EA54E',   # Verde bosque claro (hover en header)
    'primario_oscuro':  '#0D4020',   # Verde muy oscuro (sidebar, Treeview heading)

    # Verde ácido — botón COBRAR y acción principal del POS
    'acento':           '#9BC53D',   # Verde ácido (botón Cobrar)
    'acento_hover':     '#82A82C',   # Verde ácido oscuro (hover)
    'acento_claro':     '#D6EFA0',   # Verde ácido suave (hover sidebar, activo)
    'azufre':           '#9BC53D',   # Alias de acento

    # Azul brillante — botones secundarios (Agregar, Imprimir, etc.)
    'agua':             '#2E91D1',   # Azul brillante
    'agua_claro':       '#E8F4FC',   # Azul muy suave (hover fondo)
    'agua_hover':       '#2578B0',   # Azul oscuro (hover botón)

    # ── SIDEBAR ─────────────────────────────────────────────
    'fondo_sidebar':    '#0D4020',   # Verde bosque profundo — identidad del club
    'fondo_header':     '#0D4020',   # Header = mismo que sidebar

    # ── FONDOS ──────────────────────────────────────────────
    'fondo':            '#F8F9FA',   # Gris muy claro — fondo general del contenido
    'fondo_card':       '#FFFFFF',   # Blanco puro — tarjetas y tablas
    'fondo_hover':      '#EBF5FB',   # Hover azul muy suave
    'fondo_input':      '#FFFFFF',   # Inputs blancos
    'fondo_modal':      '#FFFFFF',   # Modales blancos

    # ── TEXTOS ──────────────────────────────────────────────
    'texto':            '#1A1A1A',   # Negro carbón — texto principal
    'texto_secundario': '#5C6B5C',   # Verde grisáceo — texto secundario
    'texto_claro':      '#FFFFFF',   # Para fondos oscuros (sidebar, headers)
    'texto_sidebar':    '#C8DDB0',   # Verde claro — ítem sidebar inactivo
    'texto_deshabilitado': '#9E9E9E',

    # ── BORDES ──────────────────────────────────────────────
    'borde':            '#DEE2E6',   # Gris neutro — borde estándar
    'borde_focus':      '#2E91D1',   # Azul brillante — foco en inputs
    'borde_hover':      '#BDD9E6',   # Azul suave — hover de borde

    # ── ESTADOS ─────────────────────────────────────────────
    'exito':            '#28A745',   # Verde éxito (confirmaciones)
    'advertencia':      '#F4A261',   # Naranja — pendientes de aprobación y alertas
    'error':            '#A44A3F',   # Terracota — cancelar / errores (identidad marca)
    'info':             '#2E91D1',   # Azul info = azul secundario

    # Naranja específico para "productos pendientes de aprobación"
    'pendiente_aprobacion': '#F4A261',

    # ── ESCALA DE GRISES ─────────────────────────────────────
    'gris_50':  '#F8F9FA',
    'gris_100': '#F1F3F5',
    'gris_200': '#DEE2E6',
    'gris_300': '#CED4DA',
    'gris_400': '#ADB5BD',
    'gris_500': '#6C757D',
    'gris_600': '#495057',
    'gris_700': '#343A40',
    'gris_800': '#212529',
    'gris_900': '#1A1A1A',

    # ── COCINA ──────────────────────────────────────────────
    'cocina_pendiente':  '#FFFDE7',
    'cocina_preparando': '#EFF6FF',
    'cocina_listo':      '#F0FFF4',
    'cocina_entregado':  '#F5F5F5',

    # ── CATEGORÍAS ──────────────────────────────────────────
    'cat_boletas':   '#EC4899',
    'cat_almuerzos': '#F97316',
    'cat_bebidas':   '#2E91D1',   # Azul brillante para bebidas
    'cat_licores':   '#A855F7',
    'cat_snacks':    '#28A745',

    # ── GRADIENTES ──────────────────────────────────────────
    'gradiente_inicio': '#9BC53D',
    'gradiente_fin':    '#2E91D1',
    'gradiente_azufre_1': '#9BC53D',
    'gradiente_azufre_2': '#82A82C',
}

# ============================================================
#  TIPOGRAFÍA — Segoe UI (Windows nativo, limpio y legible)
# ============================================================
FUENTES = {
    'titulo':       ('Segoe UI', _fs(22), 'bold'),
    'subtitulo':    ('Segoe UI', _fs(16), 'bold'),
    'encabezado':   ('Segoe UI', _fs(13), 'bold'),
    'normal':       ('Segoe UI', _fs(11)),
    'normal_bold':  ('Segoe UI', _fs(11), 'bold'),
    'pequena':      ('Segoe UI', _fs(10)),
    'precio':       ('Consolas', _fs(18), 'bold'),
    'kpi_valor':    ('Consolas', _fs(28), 'bold'),
    'kpi_label':    ('Segoe UI', _fs(10)),
    'boton':        ('Segoe UI', _fs(11), 'bold'),
    'input':        ('Segoe UI', _fs(11)),
    'codigo':       ('Consolas', _fs(11)),
    'tabla':        ('Segoe UI', _fs(10)),
    'tabla_header': ('Segoe UI', _fs(10), 'bold'),
    'badge':        ('Segoe UI', _fs(9), 'bold'),
}


# ============================================================
#  FUNCIONES DE UI
# ============================================================

def crear_boton(parent, texto, comando=None, tipo='primario', ancho=None, icono=None):
    """Crea un botón estilizado.
    Tipos disponibles: primario, acento, azufre, exito, error, advertencia,
                       secundario, outline, agua
    """
    colores_boton = {
        # Verde ácido — acción principal POS (Cobrar, Confirmar)
        'primario':    ('#9BC53D', '#1A1A1A', '#82A82C'),
        'acento':      ('#9BC53D', '#1A1A1A', '#82A82C'),
        'azufre':      ('#9BC53D', '#1A1A1A', '#82A82C'),
        # Azul — acciones secundarias (Agregar, Imprimir, Buscar)
        'agua':        ('#2E91D1', '#FFFFFF',  '#2578B0'),
        # Verde éxito — guardado, confirmaciones internas
        'exito':       ('#28A745', '#FFFFFF',  '#1E7A36'),
        # Terracota — cancelar, eliminar, alertas
        'error':       ('#A44A3F', '#FFFFFF',  '#8A3A30'),
        # Naranja — advertencias, pendientes
        'advertencia': ('#F4A261', '#1A1A1A', '#D4834A'),
        # Gris — acciones neutras (secundario, cerrar)
        'secundario':  ('#DEE2E6', '#1A1A1A', '#CED4DA'),
        # Outline — borde verde bosque, fondo blanco
        'outline':     ('#FFFFFF', '#1B6E3A',  '#EEF7D6'),
    }

    bg, fg, hover = colores_boton.get(tipo, colores_boton['primario'])
    label_texto = f"{icono} {texto}" if icono else texto

    # Borde sutil: outline usa verde primario, secundario usa gris, el resto usa el hover
    if tipo == 'outline':
        borde = COLORES['primario']
    elif tipo == 'secundario':
        borde = COLORES['gris_300']
    else:
        borde = hover

    btn = tk.Button(
        parent,
        text=label_texto,
        command=comando,
        bg=bg, fg=fg,
        font=FUENTES['boton'],
        relief='flat',
        cursor='hand2',
        padx=20, pady=8,
        activebackground=hover,
        activeforeground=fg,
        bd=0,
        highlightthickness=1,
        highlightbackground=borde,
        highlightcolor=hover,
    )
    if ancho:
        btn.config(width=ancho)

    def on_enter(e):
        btn.config(bg=hover, highlightbackground=hover)
    def on_leave(e):
        btn.config(bg=bg, highlightbackground=borde)

    btn.bind('<Enter>', on_enter)
    btn.bind('<Leave>', on_leave)
    return btn


def crear_tarjeta(parent, **kwargs):
    """Crea un contenedor tipo tarjeta con borde sutil"""
    frame = tk.Frame(
        parent,
        bg=kwargs.get('bg', COLORES['fondo_card']),
        highlightbackground=COLORES['borde'],
        highlightthickness=1,
        padx=kwargs.get('padx', 16),
        pady=kwargs.get('pady', 12),
    )
    return frame


def crear_tarjeta_kpi(parent, titulo, valor, icono="", color=None):
    """Crea una tarjeta KPI con barra superior de color"""
    if color is None:
        color = COLORES['acento']

    card = tk.Frame(parent, bg=COLORES['fondo_card'],
                    highlightbackground=COLORES['borde'], highlightthickness=1)
    card.pack_propagate(False)

    barra = tk.Frame(card, bg=color, height=6)
    barra.pack(fill='x', side='top')

    content = tk.Frame(card, bg=COLORES['fondo_card'], padx=16, pady=12)
    content.pack(fill='both', expand=True)

    header = tk.Frame(content, bg=COLORES['fondo_card'])
    header.pack(fill='x')

    if icono:
        tk.Label(header, text=icono, font=('Segoe UI', 18),
                 bg=COLORES['fondo_card']).pack(side='left')
    tk.Label(header, text=titulo, font=FUENTES['kpi_label'],
             fg=COLORES['texto_secundario'], bg=COLORES['fondo_card']).pack(
                 side='left', padx=(8 if icono else 0, 0))

    lbl_valor = tk.Label(content, text=str(valor), font=FUENTES['kpi_valor'],
                         fg=COLORES['texto'], bg=COLORES['fondo_card'], anchor='w')
    lbl_valor.pack(fill='x', pady=(4, 0))

    return card, lbl_valor


def crear_header(parent, titulo, subtitulo=None):
    """Crea un encabezado de sección"""
    frame = tk.Frame(parent, bg=COLORES['fondo'])
    tk.Label(frame, text=titulo, font=FUENTES['subtitulo'],
             fg=COLORES['texto'], bg=COLORES['fondo']).pack(anchor='w')
    if subtitulo:
        tk.Label(frame, text=subtitulo, font=FUENTES['pequena'],
                 fg=COLORES['texto_secundario'], bg=COLORES['fondo']).pack(anchor='w')
    return frame


def crear_input(parent, label_texto, ancho=30, tipo='text'):
    """Crea un campo de entrada con label"""
    frame = tk.Frame(parent, bg=COLORES['fondo_card'])

    tk.Label(frame, text=label_texto, font=FUENTES['normal'],
             fg=COLORES['texto_secundario'], bg=COLORES['fondo_card']).pack(anchor='w')

    entry_kwargs = dict(
        font=FUENTES['input'],
        width=ancho,
        relief='solid',
        bd=1,
        highlightthickness=2,
        highlightcolor=COLORES['borde_focus'],
        highlightbackground=COLORES['borde'],
        bg=COLORES['fondo_input'],
        fg=COLORES['texto'],
        insertbackground=COLORES['primario'],
    )
    if tipo == 'password':
        entry_kwargs['show'] = '●'

    entry = tk.Entry(frame, **entry_kwargs)
    entry.pack(fill='x', pady=(4, 0), ipady=6)
    return frame, entry


def crear_badge(parent, texto, color=None):
    """Crea un badge/etiqueta de estado"""
    if color is None:
        color = COLORES['info']

    badge = tk.Label(parent, text=f"  {texto}  ", font=FUENTES['badge'],
                     fg='white', bg=color, relief='flat')
    return badge


def aplicar_estilo_tabla(tree):
    """Aplica estilo moderno a un Treeview"""
    style = ttk.Style()
    style.theme_use('clam')

    style.configure("Pocitos.Treeview",
                    font=FUENTES['tabla'],
                    rowheight=max(28, int(38 * SCALE)),
                    background=COLORES['fondo_card'],
                    foreground=COLORES['texto'],
                    fieldbackground=COLORES['fondo_card'],
                    borderwidth=0,
                    padding=(6, 0, 0, 0))

    style.configure("Pocitos.Treeview.Heading",
                    font=FUENTES['tabla_header'],
                    background=COLORES['primario_oscuro'],
                    foreground='#C8DDB0',
                    borderwidth=0,
                    relief='flat')

    style.map("Pocitos.Treeview",
              background=[('selected', COLORES['agua'])],
              foreground=[('selected', COLORES['texto_claro'])])

    style.map("Pocitos.Treeview.Heading",
              background=[('active', COLORES['primario'])])

    tree.configure(style="Pocitos.Treeview")
    tree.tag_configure('par',    background=COLORES['fondo_card'])
    tree.tag_configure('impar',  background=COLORES['gris_50'])
    tree.tag_configure('alerta', background='#FFF3E0')
    tree.tag_configure('critico', background='#FDECEA')
    tree.tag_configure('exito',  background='#E8F5E9')
    # Tag especial para productos pendientes de aprobación (naranja)
    tree.tag_configure('pendiente', background='#FFF0E6', foreground='#C15A1A')

    return tree


def aplicar_tema_oscuro_widgets(widget):
    """Aplica el tema recursivamente a todos los widgets hijos."""
    try:
        widget_class = widget.winfo_class()
        if widget_class in ('Frame', 'Labelframe'):
            widget.config(bg=COLORES['fondo'])
        elif widget_class == 'Label':
            widget.config(bg=COLORES['fondo'], fg=COLORES['texto'])
        elif widget_class == 'Button':
            widget.config(bg=COLORES['fondo_card'], fg=COLORES['texto'],
                         activebackground=COLORES['fondo_hover'])
        elif widget_class == 'Entry':
            widget.config(bg=COLORES['fondo_input'], fg=COLORES['texto'],
                         insertbackground=COLORES['primario'])
    except tk.TclError:
        pass

    for child in widget.winfo_children():
        aplicar_tema_oscuro_widgets(child)


def crear_separador(parent, orientacion='horizontal'):
    """Crea un separador sutil"""
    if orientacion == 'horizontal':
        sep = tk.Frame(parent, bg=COLORES['borde'], height=1)
        sep.pack(fill='x', pady=8)
    else:
        sep = tk.Frame(parent, bg=COLORES['borde'], width=1)
        sep.pack(fill='y', padx=8)
    return sep


def crear_tooltip(widget, texto):
    """Crea un tooltip elegante para un widget"""
    tip = None

    def show_tip(event):
        nonlocal tip
        x = widget.winfo_rootx() + 20
        y = widget.winfo_rooty() + widget.winfo_height() + 5
        tip = tk.Toplevel(widget)
        tip.wm_overrideredirect(True)
        tip.wm_geometry(f"+{x}+{y}")
        label = tk.Label(tip, text=texto, font=FUENTES['pequena'],
                        bg=COLORES['primario_oscuro'], fg=COLORES['texto_claro'],
                        relief='flat', bd=0,
                        padx=10, pady=5)
        label.pack()

    def hide_tip(event):
        nonlocal tip
        if tip:
            tip.destroy()
            tip = None

    widget.bind('<Enter>', show_tip)
    widget.bind('<Leave>', hide_tip)


def format_money(valor):
    """Formatea un valor como moneda colombiana"""
    try:
        valor = float(valor)
        if valor < 0:
            return f"-$ {abs(valor):,.0f}".replace(",", ".")
        return f"$ {valor:,.0f}".replace(",", ".")
    except (ValueError, TypeError):
        return "$ 0"


def parse_money(texto):
    """Convierte texto de moneda a float"""
    try:
        limpio = str(texto).replace("$", "").replace(".", "").replace(",", ".").strip()
        return float(limpio)
    except (ValueError, TypeError):
        return 0.0
