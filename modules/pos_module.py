"""
Módulo Bar - Club Los Pocitos Azufrados
Venta rápida con soporte de código de barras y categorías
"""

import tkinter as tk
from tkinter import ttk, messagebox
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

import time as _time
import logging
_log = logging.getLogger("pocitos")

from utils.tema_corporativo import COLORES, FUENTES, crear_boton, format_money
from utils.logger import log_performance
from database.connection import conexion_segura
from models.series import preview_numero_venta
from models.ventas import (crear_venta, abrir_cuenta_abierta,
                           insertar_items_venta as _insertar_items_venta_model,
                           verificar_stock_minimo)
from utils.printing import imprimir_recibo_venta


class POSModule:
    """Módulo de Bar para gestión de ventas rápidas"""

    def __init__(self, parent, usuario, callback_ir_caja=None):
        self.parent = parent
        self.usuario = usuario
        self._callback_ir_caja = callback_ir_caja
        self.carrito = []
        self.total_venta = 0
        self.descuento = 0
        self.cart_items_frames = []
        self._cat_activa = None     # id_categoria activo (None = Todos)
        self._cat_botones = {}      # {id_cat: (btn, indicator_frame, color_hex)}
        self.id_cliente_sel = None  # id_cliente FK (opcional)

        self._buscar_after_id = None   # debounce para búsqueda en vivo
        self._aviso_caja_after_id = None

        self._crear_interfaz()
        self._cargar_categorias()
        self._aviso_caja_after_id = self.parent.after(300, self._avisar_si_caja_cerrada)
        self.parent.after(100, lambda: self.entry_barcode.focus_set()
                          if self.entry_barcode.winfo_exists() else None)

    # ══════════════════════════════════════════════════════════════════════
    #  INTERFAZ PRINCIPAL
    # ══════════════════════════════════════════════════════════════════════

    def _crear_interfaz(self):
        """Layout dividido: izquierda productos / derecha carrito"""
        body = tk.Frame(self.parent, bg=COLORES['fondo'])
        body.pack(fill='both', expand=True)

        # ── IZQUIERDA ──────────────────────────────────────────────────────
        left = tk.Frame(body, bg=COLORES['fondo'])
        left.pack(side='left', fill='both', expand=True)

        # Número de próxima venta — discreto arriba a la derecha
        try:
            num_preview = preview_numero_venta()
        except Exception:
            num_preview = 'POS-2026-000001'
        tk.Label(left, text=f"Siguiente: {num_preview}",
                 font=FUENTES['pequena'], fg=COLORES['texto_secundario'],
                 bg=COLORES['fondo'], anchor='e').pack(fill='x', padx=14, pady=(6, 0))

        # ── Barra de búsqueda / escáner ──
        search_wrap = tk.Frame(left, bg=COLORES['fondo_card'],
                               highlightbackground=COLORES['borde_focus'],
                               highlightthickness=1)
        search_wrap.pack(fill='x', padx=14, pady=(4, 0))

        inner_s = tk.Frame(search_wrap, bg=COLORES['fondo_card'], padx=10, pady=7)
        inner_s.pack(fill='x')
        tk.Label(inner_s, text="Buscar:",
                 font=FUENTES['normal_bold'],
                 fg=COLORES['texto_secundario'],
                 bg=COLORES['fondo_card']).pack(side='left')
        self.entry_barcode = tk.Entry(
            inner_s, font=('Consolas', 14),
            relief='flat', bd=0,
            bg=COLORES['fondo_card'],
            fg=COLORES['texto'],
            insertbackground=COLORES['acento'],
        )
        self.entry_barcode.pack(side='left', fill='x', expand=True, padx=10, ipady=4)
        self.entry_barcode.insert(0, 'Escanear código o buscar producto...')
        self.entry_barcode.config(fg=COLORES['gris_400'])

        self.entry_barcode.bind('<FocusIn>',   self._on_search_focus)
        self.entry_barcode.bind('<FocusOut>',  self._on_search_blur)
        self.entry_barcode.bind('<Return>',    self._buscar_producto)
        self.entry_barcode.bind('<KeyRelease>', self._buscar_en_vivo)

        # Botón "Nuevo producto" — solo visible para cajero (creación pendiente aprobación)
        if self.usuario.get('rol') in ('cajero', 'vendedor', 'administrador'):
            crear_boton(inner_s, "+ Prod.", self._nuevo_producto_rapido,
                        tipo='outline').pack(side='right', padx=(8, 0), ipady=2)

        # ── Resultados de búsqueda (desplegable) ──
        self.frame_resultados = tk.Frame(left, bg=COLORES['fondo_card'],
                                          highlightbackground=COLORES['primario'],
                                          highlightthickness=1)
        self.lista_resultados = tk.Listbox(
            self.frame_resultados, font=FUENTES['normal'],
            bg=COLORES['fondo_card'], fg=COLORES['texto'],
            selectbackground=COLORES['primario'],
            selectforeground='white',
            height=6, relief='flat', bd=0,
        )
        self.lista_resultados.pack(fill='x', padx=2, pady=2)
        self.lista_resultados.bind('<Double-Button-1>', self._seleccionar_resultado)
        self.lista_resultados.bind('<Return>',           self._seleccionar_resultado)
        self.resultados_data = []

        # ── Tabs de categorías (scrollable horizontal) ──
        cats_wrap = tk.Frame(left, bg=COLORES['fondo'])
        cats_wrap.pack(fill='x', padx=14, pady=(10, 0))

        self._cats_canvas = tk.Canvas(cats_wrap, bg=COLORES['fondo'],
                                      height=46, highlightthickness=0)
        self._cats_inner = tk.Frame(self._cats_canvas, bg=COLORES['fondo'])
        self._cats_canvas.create_window((0, 0), window=self._cats_inner, anchor='nw')
        self._cats_inner.bind(
            '<Configure>',
            lambda e: self._cats_canvas.configure(
                scrollregion=self._cats_canvas.bbox('all'))
        )
        self._cats_canvas.pack(fill='x', expand=True)
        self.cat_buttons_frame = self._cats_inner

        # ── Grid de productos (scrollable) ──
        self.productos_frame = tk.Frame(left, bg=COLORES['fondo'])
        self.productos_frame.pack(fill='both', expand=True, padx=14, pady=(8, 12))

        self.canvas_prod = tk.Canvas(self.productos_frame, bg=COLORES['fondo'],
                                     highlightthickness=0)
        scrollbar_prod = ttk.Scrollbar(self.productos_frame, orient='vertical',
                                       command=self.canvas_prod.yview)
        self.grid_productos = tk.Frame(self.canvas_prod, bg=COLORES['fondo'])
        self.grid_productos.bind(
            '<Configure>',
            lambda e: self.canvas_prod.configure(
                scrollregion=self.canvas_prod.bbox('all'))
        )
        self._prod_win = self.canvas_prod.create_window((0, 0), window=self.grid_productos, anchor='nw')
        self.canvas_prod.configure(yscrollcommand=scrollbar_prod.set)
        self.canvas_prod.bind('<Configure>',
                              lambda e: self.canvas_prod.itemconfig(self._prod_win, width=e.width))
        self.canvas_prod.pack(side='left', fill='both', expand=True)
        scrollbar_prod.pack(side='right', fill='y')

        def _scroll_smart(event):
            """Enruta la rueda al canvas correcto según dónde esté el cursor."""
            d = int(-1 * (event.delta / 120)) if event.delta else (1 if event.num == 5 else -1)
            # Subir por la jerarquía de widgets hasta encontrar el canvas correspondiente
            w = event.widget
            for _ in range(20):
                if w is self.canvas_carrito:
                    try: self.canvas_carrito.yview_scroll(d, 'units')
                    except Exception: pass
                    return
                if w is self.canvas_prod:
                    break
                try:
                    p = w.winfo_parent()
                    if not p:
                        break
                    w = w.nametowidget(p)
                except Exception:
                    break
            # Por defecto: scroll de productos
            try:
                self.canvas_prod.yview_scroll(d * 3, 'units')
            except Exception:
                pass

        self.canvas_prod.bind_all('<MouseWheel>', _scroll_smart)
        self.canvas_prod.bind_all('<Button-4>',   _scroll_smart)
        self.canvas_prod.bind_all('<Button-5>',   _scroll_smart)

        # ── DERECHA: Carrito ───────────────────────────────────────────────
        # Ancho adaptativo: 28% de pantalla, mínimo 260px, máximo 380px
        _sw = self.parent.winfo_screenwidth()
        _cart_w = max(260, min(380, int(_sw * 0.28)))
        right = tk.Frame(body, bg=COLORES['fondo_sidebar'], width=_cart_w)
        right.pack(side='right', fill='y')
        right.pack_propagate(False)

        # Header del carrito
        cart_hdr = tk.Frame(right, bg=COLORES['primario_oscuro'], padx=14, pady=10)
        cart_hdr.pack(fill='x')
        tk.Label(cart_hdr, text="Orden Actual",
                 font=FUENTES['subtitulo'], fg=COLORES['texto_claro'],
                 bg=COLORES['primario_oscuro']).pack(side='left')
        self.lbl_items = tk.Label(cart_hdr, text="0 items",
                                   font=FUENTES['pequena'],
                                   fg=COLORES['acento'],
                                   bg=COLORES['primario_oscuro'])
        self.lbl_items.pack(side='right')

        # Widgets ocultos — se llenan desde los diálogos de Cuenta Abierta y Pago
        self.entry_cliente = tk.Entry(right)
        self.entry_notas = tk.Entry(right)
        self.entry_descuento = tk.Entry(right)
        self.entry_descuento.insert(0, '0')

        # ── Zona fija en la parte inferior ──
        bottom = tk.Frame(right, bg=COLORES['fondo_sidebar'])
        bottom.pack(side='bottom', fill='x')

        # Total block
        total_block = tk.Frame(bottom, bg=COLORES['fondo_modal'], padx=12, pady=5)
        total_block.pack(fill='x')
        total_row = tk.Frame(total_block, bg=COLORES['fondo_modal'])
        total_row.pack(fill='x')
        tk.Label(total_row, text="TOTAL",
                 font=FUENTES['encabezado'],
                 fg=COLORES['texto_secundario'],
                 bg=COLORES['fondo_modal']).pack(side='left', pady=2)
        self.lbl_total = tk.Label(total_row, text="$ 0",
                                   font=('Consolas', 20, 'bold'),
                                   fg=COLORES['acento'],
                                   bg=COLORES['fondo_modal'])
        self.lbl_total.pack(side='right')

        # Checkbox Factura Electronica
        fe_frame = tk.Frame(bottom, bg=COLORES['fondo_modal'], padx=10, pady=2)
        fe_frame.pack(fill='x')
        self.var_factura_electronica = tk.BooleanVar(master=self.parent, value=False)
        tk.Checkbutton(
            fe_frame, text="Factura electronica (DIAN)",
            variable=self.var_factura_electronica,
            font=FUENTES['pequena'], fg=COLORES['texto'],
            bg=COLORES['fondo_modal'],
            activebackground=COLORES['fondo_modal'],
            selectcolor=COLORES['fondo_card'],
        ).pack(anchor='w')

        # Botones de pago
        pagos_frame = tk.Frame(bottom, bg=COLORES['fondo_sidebar'], padx=10, pady=6)
        pagos_frame.pack(fill='x')

        # PAGAR — botón principal
        tk.Button(
            pagos_frame, text="PAGAR",
            font=('Segoe UI', 14, 'bold'),
            fg=COLORES['fondo_sidebar'], bg=COLORES['acento'],
            relief='flat', cursor='hand2', bd=0,
            activebackground=COLORES['acento_hover'],
            activeforeground=COLORES['fondo_sidebar'],
            command=self._abrir_modal_pago,
        ).pack(fill='x', ipady=8, pady=(0, 4))

        # Cuenta Abierta y Vaciar en la misma fila
        btns_row = tk.Frame(pagos_frame, bg=COLORES['fondo_sidebar'])
        btns_row.pack(fill='x')
        tk.Button(
            btns_row, text="Cuenta Abierta",
            font=FUENTES['pequena'],
            fg=COLORES['texto_claro'], bg=COLORES['fondo_sidebar'],
            relief='solid', cursor='hand2', bd=1,
            highlightbackground=COLORES['borde'],
            activebackground=COLORES['primario_oscuro'],
            activeforeground=COLORES['texto_claro'],
            command=self._abrir_cuenta_con_busqueda,
        ).pack(side='left', fill='x', expand=True, ipady=5, padx=(0, 3))

        tk.Button(
            btns_row, text="Vaciar",
            font=FUENTES['pequena'],
            fg=COLORES['texto_deshabilitado'], bg=COLORES['fondo_sidebar'],
            relief='flat', cursor='hand2', bd=0,
            activebackground=COLORES['fondo_hover'],
            command=self._vaciar_carrito,
        ).pack(side='right', ipady=5)

        # ── Zona scrollable del carrito ──
        cart_area = tk.Frame(right, bg=COLORES['fondo'])
        cart_area.pack(fill='both', expand=True, padx=6, pady=6)

        self.canvas_carrito = tk.Canvas(cart_area, bg=COLORES['fondo'],
                                        highlightthickness=0)
        scrollbar_cart = ttk.Scrollbar(cart_area, orient='vertical',
                                       command=self.canvas_carrito.yview)
        self.cart_items_container = tk.Frame(self.canvas_carrito,
                                              bg=COLORES['fondo'])
        self.cart_items_container.bind(
            '<Configure>',
            lambda e: self.canvas_carrito.configure(
                scrollregion=self.canvas_carrito.bbox('all'))
        )
        self._cart_win = self.canvas_carrito.create_window((0, 0), window=self.cart_items_container, anchor='nw')
        self.canvas_carrito.configure(yscrollcommand=scrollbar_cart.set)
        self.canvas_carrito.bind('<Configure>',
                                 lambda e: self.canvas_carrito.itemconfig(self._cart_win, width=e.width))
        self.canvas_carrito.pack(side='left', fill='both', expand=True)
        scrollbar_cart.pack(side='right', fill='y')

    # ══════════════════════════════════════════════════════════════════════
    #  CATEGORÍAS — tabs con estado activo
    # ══════════════════════════════════════════════════════════════════════

    def _cargar_categorias(self):
        """Carga categorías como tabs estilo Treinta: texto + línea inferior activa"""
        for w in self.cat_buttons_frame.winfo_children():
            w.destroy()
        self._cat_botones = {}

        def _hacer_tab(id_cat, nombre, color):
            # Cada tab: wrapper → botón encima + línea indicadora abajo
            wrap = tk.Frame(self.cat_buttons_frame, bg=COLORES['fondo'])
            wrap.pack(side='left', padx=2, pady=(4, 0))

            btn = tk.Button(
                wrap,
                text=nombre,
                font=FUENTES['normal'],
                fg=COLORES['texto_secundario'],
                bg=COLORES['fondo'],
                relief='flat', cursor='hand2', bd=0,
                padx=14, pady=6,
                activeforeground=COLORES['texto'],
                activebackground=COLORES['fondo'],
                command=lambda c=id_cat: self._activar_categoria(c),
            )
            btn.pack()

            # Línea indicadora de 3px (oculta por defecto)
            indicator = tk.Frame(wrap, bg=COLORES['fondo'], height=3)
            indicator.pack(fill='x')

            self._cat_botones[id_cat] = (btn, indicator, color)

        _hacer_tab(None, "Todos", COLORES['primario'])

        try:
            with conexion_segura() as conn:
                cols = [r[1] for r in conn.execute("PRAGMA table_info(categorias)").fetchall()]
                tipo_cond = ("AND (COALESCE(c.tipo,'restaurante') IN ('restaurante','ambos'))"
                             if 'tipo' in cols else "")
                cats = conn.execute(f"""
                    SELECT c.*, COUNT(p.id_producto) AS n_prods
                    FROM categorias c
                    LEFT JOIN productos p ON p.id_categoria = c.id_categoria
                                        AND p.activo = 1 AND p.es_boleta_entrada = 0
                    WHERE c.activa = 1 {tipo_cond}
                    GROUP BY c.id_categoria
                    HAVING n_prods > 0
                    ORDER BY c.orden
                """).fetchall()
            for cat in cats:
                color = cat['color'] or COLORES['primario']
                _hacer_tab(cat['id_categoria'], cat['nombre'], color)
        except Exception as e:
            _log.error(f"Error cargando categorías: {e}")

        self._activar_categoria(None)

    def _activar_categoria(self, id_cat):
        """Activa el tab con línea inferior coloreada (estilo Treinta)"""
        self._cat_activa = id_cat
        for cid, (btn, indicator, color) in self._cat_botones.items():
            if cid == id_cat:
                btn.config(fg=COLORES['texto'], font=FUENTES['normal_bold'])
                indicator.config(bg=color)
            else:
                btn.config(fg=COLORES['texto_secundario'], font=FUENTES['normal'])
                indicator.config(bg=COLORES['fondo'])
        self._mostrar_productos_categoria(id_cat)

    # ══════════════════════════════════════════════════════════════════════
    #  GRID DE PRODUCTOS
    # ══════════════════════════════════════════════════════════════════════

    def _mostrar_productos_categoria(self, id_categoria):
        """Muestra los productos de una categoría en grid de 3 columnas"""
        for w in self.grid_productos.winfo_children():
            w.destroy()

        try:
            with conexion_segura() as conn:
                if id_categoria:
                    rows = conn.execute("""
                        SELECT p.*, c.icono, c.color FROM productos p
                        LEFT JOIN categorias c ON p.id_categoria = c.id_categoria
                        WHERE p.activo = 1 AND p.es_boleta_entrada = 0 AND p.id_categoria = ?
                        ORDER BY p.nombre
                    """, (id_categoria,)).fetchall()
                else:
                    rows = conn.execute("""
                        SELECT p.*, c.icono, c.color FROM productos p
                        LEFT JOIN categorias c ON p.id_categoria = c.id_categoria
                        WHERE p.activo = 1 AND p.es_boleta_entrada = 0
                        ORDER BY c.orden, p.nombre
                    """).fetchall()

            cols = 3
            for i, prod in enumerate(rows):
                r, c = divmod(i, cols)
                self._crear_card_producto(self.grid_productos, prod, r, c)

            if not rows:
                tk.Label(self.grid_productos,
                         text="No hay productos en esta categoría",
                         font=FUENTES['normal'], fg=COLORES['texto_secundario'],
                         bg=COLORES['fondo']).grid(row=0, column=0, pady=30)

        except Exception as e:
            _log.error(f"Error mostrando productos: {e}")

    def _crear_card_producto(self, parent, producto, fila, columna):
        """
        Tarjeta estilo Treinta: limpia, sin zonas de color grandes.
          - Línea superior de 3px en color de categoría
          - Icono pequeño inline + nombre + precio
          - Hover sutil en el borde
        """
        producto       = dict(producto)
        color_cat      = producto.get('color') or COLORES['primario']
        icono          = producto.get('icono') or ''
        stock          = producto.get('stock_actual') or 0
        controla_stock = producto.get('controla_stock', 0)
        agotado        = controla_stock and stock <= 0 and not producto.get('es_boleta_entrada')

        card = tk.Frame(parent, bg=COLORES['fondo_card'],
                        highlightbackground=COLORES['borde'],
                        highlightthickness=1,
                        cursor='arrow' if agotado else 'hand2')
        card.grid(row=fila, column=columna, padx=4, pady=4, sticky='nsew')
        parent.columnconfigure(columna, weight=1)

        # Línea superior de 3px — única referencia visual al color de categoría
        tk.Frame(card,
                 bg=color_cat if not agotado else COLORES['gris_400'],
                 height=3).pack(fill='x')

        # Contenido principal
        content = tk.Frame(card, bg=COLORES['fondo_card'], padx=10, pady=10)
        content.pack(fill='both', expand=True)

        # Fila: icono pequeño + nombre
        name_row = tk.Frame(content, bg=COLORES['fondo_card'])
        name_row.pack(fill='x', anchor='w')

        # category icon omitted — emojis render as boxes on Windows GDI

        tk.Label(name_row, text=producto['nombre'],
                 font=FUENTES['pequena'],
                 fg=COLORES['texto'] if not agotado else COLORES['texto_secundario'],
                 bg=COLORES['fondo_card'],
                 wraplength=130, anchor='w', justify='left').pack(side='left', fill='x')

        # Precio
        tk.Label(content, text=format_money(producto['precio_venta']),
                 font=('Consolas', 12, 'bold'),
                 fg=COLORES['acento'] if not agotado else COLORES['gris_500'],
                 bg=COLORES['fondo_card']).pack(anchor='w', pady=(5, 0))

        # Badge discreto de stock
        if agotado:
            tk.Label(content, text="Sin stock",
                     font=FUENTES['pequena'],
                     fg=COLORES['error'], bg=COLORES['fondo_card']).pack(anchor='w')
        elif stock <= 5:
            tk.Label(content, text=f"Quedan: {stock}",
                     font=FUENTES['pequena'],
                     fg=COLORES['advertencia'], bg=COLORES['fondo_card']).pack(anchor='w')

        # Click + flash
        if not agotado:
            def on_click(e, p=dict(producto)):
                self._agregar_al_carrito(p)
                card.config(highlightbackground=color_cat, highlightthickness=2)
                card.after(200, lambda c=card: c.winfo_exists() and c.config(
                    highlightbackground=COLORES['borde'], highlightthickness=1))

            for w in [card, content, name_row] + content.winfo_children() + name_row.winfo_children():
                try:
                    w.bind('<Button-1>', on_click)
                except Exception:
                    pass

        # Hover — sutil
        def on_enter(e):
            if not agotado:
                card.config(highlightbackground=color_cat)

        def on_leave(e):
            card.config(highlightbackground=COLORES['borde'])

        card.bind('<Enter>', on_enter)
        card.bind('<Leave>', on_leave)

    # ══════════════════════════════════════════════════════════════════════
    #  CARRITO — ítems con layout 2 líneas y botones grandes
    # ══════════════════════════════════════════════════════════════════════

    def _crear_fila_carrito(self, item, index):
        """
        Card de ítem del carrito:
          línea 1: nombre del producto  |  precio unitario
          línea 2: [×]  [−  qty  +]    |  subtotal
        """
        card = tk.Frame(self.cart_items_container, bg=COLORES['fondo_card'],
                        highlightbackground=COLORES['primario'], highlightthickness=1)
        card.pack(fill='x', pady=2, padx=2)

        # Línea 1: nombre + precio unitario
        top = tk.Frame(card, bg=COLORES['fondo_card'], padx=10)
        top.pack(fill='x', pady=(6, 2))
        tk.Label(top, text=item['nombre'],
                 font=FUENTES['normal_bold'], fg=COLORES['texto'],
                 bg=COLORES['fondo_card'], anchor='w').pack(side='left', fill='x', expand=True)
        tk.Label(top, text=format_money(item['precio']),
                 font=FUENTES['pequena'], fg=COLORES['texto_secundario'],
                 bg=COLORES['fondo_card']).pack(side='right')

        # Línea 2: controles + subtotal
        bot = tk.Frame(card, bg=COLORES['fondo_card'], padx=10)
        bot.pack(fill='x', pady=(2, 7))

        def remove():
            if item in self.carrito:
                self.carrito.remove(item)
                self._actualizar_carrito_visual()

        # Botón quitar (×)
        tk.Button(bot, text="×",
                  font=FUENTES['normal'], fg=COLORES['error'],
                  bg=COLORES['fondo_card'], relief='flat', bd=0,
                  cursor='hand2', padx=2,
                  activebackground=COLORES['fondo_hover'],
                  command=remove).pack(side='left')

        # Controles de cantidad
        qty_frame = tk.Frame(bot, bg=COLORES['fondo_card'])
        qty_frame.pack(side='left', padx=8)

        def decrease():
            if item['cantidad'] > 1:
                item['cantidad'] -= 1
                item['total'] = item['cantidad'] * item['precio']
                self._actualizar_carrito_visual()
            else:
                remove()

        def increase():
            controla = item.get('controla_stock', 0)
            if not item.get('es_boleta') and controla:
                if item['cantidad'] < item['stock_disponible']:
                    item['cantidad'] += 1
                    item['total'] = item['cantidad'] * item['precio']
                    self._actualizar_carrito_visual()
                else:
                    messagebox.showwarning(
                        "Stock Limitado",
                        f"Solo hay {item['stock_disponible']} unidades disponibles.")
            else:
                item['cantidad'] += 1
                item['total'] = item['cantidad'] * item['precio']
                self._actualizar_carrito_visual()

        tk.Button(qty_frame, text="−",
                  font=FUENTES['subtitulo'],
                  fg=COLORES['texto'], bg=COLORES['fondo_hover'],
                  relief='flat', bd=0, cursor='hand2',
                  padx=10, pady=2,
                  activebackground=COLORES['gris_300'],
                  command=decrease).pack(side='left')

        tk.Label(qty_frame, text=str(item['cantidad']),
                 font=('Consolas', 14, 'bold'), fg=COLORES['texto'],
                 bg=COLORES['fondo_card'], width=3,
                 anchor='center').pack(side='left', padx=4)

        tk.Button(qty_frame, text="+",
                  font=FUENTES['subtitulo'],
                  fg='white', bg=COLORES['primario'],
                  relief='flat', bd=0, cursor='hand2',
                  padx=10, pady=2,
                  activebackground=COLORES['primario_claro'],
                  command=increase).pack(side='left')

        # Subtotal de línea (derecha)
        tk.Label(bot, text=format_money(item['total']),
                 font=('Consolas', 12, 'bold'), fg=COLORES['texto'],
                 bg=COLORES['fondo_card']).pack(side='right')

    def _actualizar_carrito_visual(self):
        """Redibuja todos los ítems del carrito y actualiza el total"""
        for widget in self.cart_items_container.winfo_children():
            widget.destroy()

        subtotal = 0
        for i, item in enumerate(self.carrito):
            self._crear_fila_carrito(item, i)
            subtotal += item['total']

        # descuento se aplica desde el modal de pago (_abrir_modal_pago)
        self.total_venta = max(subtotal - self.descuento, 0)
        self.lbl_total.config(text=format_money(self.total_venta))
        self.lbl_items.config(text=f"{len(self.carrito)} items")

    def _avisar_si_caja_cerrada(self):
        """Si no hay caja abierta, bloquea el POS y ofrece ir a Caja."""
        try:
            with conexion_segura() as conn:
                caja = conn.execute(
                    "SELECT id_caja FROM caja_diaria WHERE estado = 'ABIERTA'"
                ).fetchone()
            if caja:
                return  # Caja abierta, todo bien

            # Ocultar el grid de productos para que no se pueda usar
            try:
                self.parent.winfo_toplevel().update_idletasks()
            except Exception:
                pass

            ir = messagebox.askyesno(
                "Caja no abierta",
                "No hay caja abierta para hoy.\n\n"
                "Es necesario abrir la caja antes de comenzar a vender.\n\n"
                "¿Desea ir al modulo Caja ahora para abrirla?"
            )
            if ir and self._callback_ir_caja:
                self._callback_ir_caja()
        except Exception:
            pass

    # ══════════════════════════════════════════════════════════════════════
    #  BÚSQUEDA (sin cambios funcionales)
    # ══════════════════════════════════════════════════════════════════════

    def _on_search_focus(self, event):
        if self.entry_barcode.get() == 'Escanear código o buscar producto...':
            self.entry_barcode.delete(0, tk.END)
            self.entry_barcode.config(fg=COLORES['texto'])

    def _on_search_blur(self, event):
        if not self.entry_barcode.get().strip():
            self.entry_barcode.delete(0, tk.END)
            self.entry_barcode.insert(0, 'Escanear código o buscar producto...')
            self.entry_barcode.config(fg=COLORES['gris_400'])
            self.frame_resultados.pack_forget()

    def _buscar_en_vivo(self, event=None):
        """Búsqueda en vivo mientras escribe — con debounce de 150ms."""
        if self._buscar_after_id:
            try:
                self.parent.after_cancel(self._buscar_after_id)
            except Exception:
                pass
            self._buscar_after_id = None

        texto = self.entry_barcode.get().strip()
        if not texto or texto == 'Escanear código o buscar producto...':
            self.frame_resultados.pack_forget()
            return
        if len(texto) < 2:
            self.frame_resultados.pack_forget()
            return

        self._buscar_after_id = self.parent.after(150, lambda t=texto: self._ejecutar_busqueda(t))

    def _ejecutar_busqueda(self, texto):
        """Ejecuta la consulta de búsqueda tras el debounce."""
        self._buscar_after_id = None
        try:
            t0 = _time.monotonic()
            with conexion_segura() as conn:
                rows = conn.execute("""
                    SELECT p.id_producto, p.nombre, p.precio_venta, p.stock_actual,
                           p.codigo_barras, p.controla_stock,
                           c.nombre as categoria, c.icono
                    FROM productos p
                    LEFT JOIN categorias c ON p.id_categoria = c.id_categoria
                    WHERE p.activo = 1 AND p.es_boleta_entrada = 0 AND (
                        p.nombre LIKE ? OR p.codigo_barras LIKE ? OR c.nombre LIKE ?
                    )
                    ORDER BY p.nombre LIMIT 10
                """, (f"%{texto}%", f"%{texto}%", f"%{texto}%")).fetchall()
            log_performance("buscar_en_vivo", (_time.monotonic() - t0) * 1000, texto)

            self.lista_resultados.delete(0, tk.END)
            self.resultados_data = []

            if rows:
                self.frame_resultados.pack(fill='x', before=self.productos_frame, pady=(0, 4))
                for row in rows:
                    stock_txt = f"({row['stock_actual']})" if row['stock_actual'] is not None else ""
                    self.lista_resultados.insert(
                        tk.END,
                        f"{row['nombre']}  —  {format_money(row['precio_venta'])}  {stock_txt}"
                    )
                    self.resultados_data.append(dict(row))
            else:
                self.frame_resultados.pack_forget()

        except Exception as e:
            _log.error(f"Error búsqueda: {e}")

    def _buscar_producto(self, event=None):
        """Busca por código de barras exacto (Enter / escáner)"""
        texto = self.entry_barcode.get().strip()
        if not texto or texto == 'Escanear código o buscar producto...':
            return

        try:
            with conexion_segura() as conn:
                row = conn.execute(
                    "SELECT * FROM productos WHERE codigo_barras = ? AND activo = 1",
                    (texto,)
                ).fetchone()

            if row:
                self._agregar_al_carrito(dict(row))
                self.entry_barcode.delete(0, tk.END)
                self.frame_resultados.pack_forget()
                return

            if self.resultados_data:
                self._agregar_al_carrito(self.resultados_data[0])
                self.entry_barcode.delete(0, tk.END)
                self.frame_resultados.pack_forget()

        except Exception as e:
            messagebox.showerror("Error", f"Error buscando producto: {e}")

    def _seleccionar_resultado(self, event=None):
        sel = self.lista_resultados.curselection()
        if sel and sel[0] < len(self.resultados_data):
            producto = self.resultados_data[sel[0]]
            self._agregar_al_carrito(producto)
            self.entry_barcode.delete(0, tk.END)
            self.frame_resultados.pack_forget()
            self.entry_barcode.focus_set()

    # ══════════════════════════════════════════════════════════════════════
    #  LÓGICA DE NEGOCIO (sin cambios)
    # ══════════════════════════════════════════════════════════════════════

    def _agregar_al_carrito(self, producto):
        """Agrega un producto al carrito"""
        id_prod = producto['id_producto']

        stock          = producto.get('stock_actual', 0) or 0
        es_boleta      = producto.get('es_boleta_entrada', 0)
        controla_stock = producto.get('controla_stock', 0)

        if controla_stock and stock <= 0 and not es_boleta:
            messagebox.showwarning("Sin Stock",
                                    f"'{producto['nombre']}' no tiene stock disponible.")
            return

        # Verificar variantes del producto
        variante = self._seleccionar_variante(producto)
        if variante is None:
            return  # Usuario canceló el selector de variantes
        # variante == False significa sin variantes; variante == dict significa variante elegida
        id_variante = variante['id_variante'] if variante else None
        nombre_item = f"{producto['nombre']} - {variante['nombre']}" if variante else producto['nombre']
        precio_item = variante['precio_total'] if variante else producto['precio_venta']

        # Verificar si el producto es almuerzo/comida
        es_almuerzo = False
        categoria_nombre = ""
        try:
            with conexion_segura() as conn:
                cat_row = conn.execute(
                    "SELECT nombre FROM categorias WHERE id_categoria = ?",
                    (producto.get('id_categoria'),)
                ).fetchone()

            if cat_row:
                categoria_nombre = cat_row['nombre'].lower()
                es_almuerzo = 'almuerzo' in categoria_nombre or 'comida' in categoria_nombre
        except Exception as e:
            _log.error(f"Error verificando categoría: {e}")

        pedido_nombre = None
        pedido_hora   = None
        pedido_notas  = None

        if es_almuerzo:
            dialog = self._crear_dialogo_almuerzo()
            if dialog is None:
                return
            pedido_nombre, pedido_hora, pedido_notas = dialog

        # Si ya está en el carrito (mismo producto y misma variante), incrementar
        for item in self.carrito:
            if item['id_producto'] == id_prod and item.get('id_variante') == id_variante:
                if controla_stock and item['cantidad'] >= stock and not es_boleta:
                    messagebox.showwarning("Stock Limitado",
                                            f"Solo hay {stock} unidades de '{producto['nombre']}'")
                    return
                item['cantidad'] += 1
                item['total'] = item['cantidad'] * item['precio']
                self._actualizar_carrito_visual()
                return

        item_dict = {
            'id_producto':      id_prod,
            'id_variante':      id_variante,
            'nombre':           nombre_item,
            'cantidad':         1,
            'precio':           precio_item,
            'total':            precio_item,
            'requiere_cocina':  producto.get('requiere_cocina', 0),
            'es_boleta':        es_boleta,
            'stock_disponible': stock,
        }

        if es_almuerzo:
            item_dict['es_almuerzo']   = True
            item_dict['pedido_nombre'] = pedido_nombre
            item_dict['pedido_hora']   = pedido_hora
            item_dict['pedido_notas']  = pedido_notas

        self.carrito.append(item_dict)
        self._actualizar_carrito_visual()

    def _buscar_cliente(self):
        """Abre un diálogo para buscar y seleccionar un cliente registrado"""
        dlg = tk.Toplevel(self.parent)
        dlg.title("Buscar Cliente")
        dlg.geometry("460x360")
        dlg.resizable(True, True)
        dlg.configure(bg=COLORES['fondo_card'])
        dlg.grab_set()

        tk.Label(dlg, text="Buscar Cliente", font=FUENTES['subtitulo'],
                 fg=COLORES['texto'], bg=COLORES['fondo_card']).pack(padx=16, pady=(14, 6), anchor='w')

        busq_frame = tk.Frame(dlg, bg=COLORES['fondo_card'])
        busq_frame.pack(fill='x', padx=16, pady=(0, 6))
        entry_busq = tk.Entry(busq_frame, font=FUENTES['input'],
                               bg=COLORES['fondo_input'], fg=COLORES['texto'],
                               insertbackground=COLORES['acento'], relief='solid', bd=1)
        entry_busq.pack(fill='x', ipady=6)
        entry_busq.focus_set()

        tabla_frame = tk.Frame(dlg, bg=COLORES['fondo_card'])
        tabla_frame.pack(fill='both', expand=True, padx=16, pady=4)

        tree = ttk.Treeview(tabla_frame, columns=('nombre', 'celular', 'tipo'),
                             show='headings', height=10)
        tree.column('nombre', width=220, anchor='w')
        tree.column('celular', width=110, anchor='center')
        tree.column('tipo', width=110, anchor='center')
        tree.heading('nombre', text='Nombre')
        tree.heading('celular', text='Celular')
        tree.heading('tipo', text='Tipo')
        from utils.tema_corporativo import aplicar_estilo_tabla as _est
        _est(tree)

        scroll = ttk.Scrollbar(tabla_frame, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.pack(side='left', fill='both', expand=True)
        scroll.pack(side='right', fill='y')

        # Lista combinada: clientes registrados + cuentas abiertas del día
        todos = []

        def cargar(termino=''):
            for item in tree.get_children():
                tree.delete(item)
            todos.clear()
            try:
                with conexion_segura() as conn:
                    like = f'%{termino}%' if termino else '%'

                    # Clientes registrados
                    clientes_rows = conn.execute("""
                        SELECT id_cliente, nombre, celular, documento FROM clientes
                        WHERE nombre LIKE ? OR celular LIKE ?
                        ORDER BY nombre LIMIT 40
                    """, (like, like)).fetchall()

                    # Cuentas abiertas (todas, incluyendo sin nombre de cliente)
                    cuentas_rows = conn.execute("""
                        SELECT id_venta, cliente_nombre, numero_venta
                        FROM ventas
                        WHERE tipo = 'cuenta_abierta'
                          AND estado = 'ABIERTA'
                          AND (cliente_nombre LIKE ? OR cliente_nombre IS NULL OR cliente_nombre = '')
                        ORDER BY fecha_creacion DESC LIMIT 20
                    """, (like,)).fetchall()

                    # Insertar clientes registrados
                    for i, r in enumerate(clientes_rows):
                        iid = f"c_{r['id_cliente']}"
                        todos.append({'tipo': 'cliente', 'id_cliente': r['id_cliente'],
                                      'nombre': r['nombre'], 'celular': r['celular'] or ''})
                        tag = 'par' if i % 2 == 0 else 'impar'
                        tree.insert('', 'end', iid=iid, values=(
                            r['nombre'], r['celular'] or '---', 'Cliente'
                        ), tags=(tag,))

                    # Insertar cuentas abiertas
                    nombres_clientes = {r['nombre'] for r in clientes_rows}
                    for j, r in enumerate(cuentas_rows):
                        nombre_raw = r['cliente_nombre']
                        nombre = nombre_raw if nombre_raw else f"Cuenta {r['numero_venta']}"
                        if nombre_raw and nombre_raw in nombres_clientes:
                            continue  # ya aparece como cliente registrado
                        iid = f"v_{r['id_venta']}"
                        todos.append({'tipo': 'cuenta', 'id_venta': r['id_venta'],
                                      'nombre': nombre, 'celular': ''})
                        tag = 'par' if (len(clientes_rows) + j) % 2 == 0 else 'impar'
                        tree.insert('', 'end', iid=iid, values=(
                            nombre, r['numero_venta'], 'Cuenta abierta'
                        ), tags=(tag,))
            except Exception:
                pass

        def on_key(event):
            cargar(entry_busq.get().strip())

        entry_busq.bind('<KeyRelease>', on_key)
        cargar()

        def seleccionar():
            sel = tree.selection()
            if not sel:
                return
            iid = sel[0]
            entrada = next((c for c in todos if
                            (c['tipo'] == 'cliente' and f"c_{c['id_cliente']}" == iid) or
                            (c['tipo'] == 'cuenta' and f"v_{c['id_venta']}" == iid)), None)
            if entrada:
                self.entry_cliente.delete(0, tk.END)
                self.entry_cliente.insert(0, entrada['nombre'])
                if entrada['tipo'] == 'cliente':
                    self.id_cliente_sel = entrada['id_cliente']
                else:
                    self.id_cliente_sel = None
            dlg.destroy()

        def on_double(event):
            seleccionar()

        tree.bind('<Double-1>', on_double)

        btns = tk.Frame(dlg, bg=COLORES['fondo_card'])
        btns.pack(fill='x', padx=16, pady=10)

        def _agregar_nuevo():
            nombre = entry_busq.get().strip()
            if not nombre:
                messagebox.showwarning("Nombre requerido",
                                       "Escriba el nombre del nuevo cliente.", parent=dlg)
                return
            self.entry_cliente.delete(0, tk.END)
            self.entry_cliente.insert(0, nombre)
            dlg.destroy()

        crear_boton(btns, "Nuevo Cliente", _agregar_nuevo, tipo='azufre').pack(side='left', padx=4)
        crear_boton(btns, "Seleccionar", seleccionar, tipo='exito').pack(side='right', padx=4)
        crear_boton(btns, "Cancelar", dlg.destroy, tipo='secundario').pack(side='right', padx=4)

    def _seleccionar_variante(self, producto):
        """Muestra un diálogo para elegir una variante del producto. Retorna dict o None."""
        try:
            with conexion_segura() as conn:
                variantes = conn.execute("""
                    SELECT id_variante, nombre_variante, precio_adicional
                    FROM variantes_producto
                    WHERE id_producto = ? AND activa = 1
                    ORDER BY nombre_variante
                """, (producto['id_producto'],)).fetchall()
        except Exception as e:
            import logging
            logging.getLogger("pocitos").error(f"Error consultando variantes del producto {producto.get('id_producto')}: {e}")
            return False  # Continuar sin variantes si falla la consulta

        if not variantes:
            return False  # Sin variantes, continuar normalmente

        dlg = tk.Toplevel(self.parent)
        dlg.title(f"Variantes: {producto['nombre']}")
        dlg.geometry("360x300")
        dlg.resizable(True, True)
        dlg.configure(bg=COLORES['fondo_card'])
        dlg.grab_set()

        tk.Label(dlg, text=producto['nombre'], font=FUENTES['encabezado'],
                 fg=COLORES['texto'], bg=COLORES['fondo_card']).pack(padx=16, pady=(14, 4), anchor='w')
        tk.Label(dlg, text="Seleccione una variante:", font=FUENTES['pequena'],
                 fg=COLORES['texto_secundario'], bg=COLORES['fondo_card']).pack(padx=16, anchor='w')

        resultado = [None]

        for v in variantes:
            precio_total = producto['precio_venta'] + v['precio_adicional']
            texto = f"{v['nombre_variante']}  —  {format_money(precio_total)}"
            if v['precio_adicional'] > 0:
                texto += f"  (+{format_money(v['precio_adicional'])})"

            def hacer_click(variante=v, precio=precio_total):
                resultado[0] = {
                    'id_variante': variante['id_variante'],
                    'nombre': variante['nombre_variante'],
                    'precio_total': precio
                }
                dlg.destroy()

            btn = tk.Button(dlg, text=texto, font=FUENTES['normal'],
                            fg=COLORES['texto'], bg=COLORES['fondo_hover'],
                            activebackground=COLORES['primario'],
                            activeforeground=COLORES['texto_claro'],
                            relief='flat', cursor='hand2', padx=12, pady=10,
                            command=hacer_click)
            btn.pack(fill='x', padx=16, pady=3)

        tk.Button(dlg, text="Cancelar", font=FUENTES['pequena'],
                  fg=COLORES['texto_deshabilitado'], bg=COLORES['fondo_card'],
                  relief='flat', cursor='hand2',
                  command=dlg.destroy).pack(pady=(8, 14))

        dlg.wait_window()
        return resultado[0]

    def _crear_dialogo_almuerzo(self):
        """Diálogo para capturar datos de reserva de almuerzo"""
        dialog = tk.Toplevel(self.parent)
        dialog.title("Datos de Reserva - Almuerzo")
        dialog.geometry("420x310")
        dialog.resizable(True, True)
        dialog.transient(self.parent)
        dialog.grab_set()

        dialog.update_idletasks()
        x = self.parent.winfo_x() + (self.parent.winfo_width()  // 2) - (dialog.winfo_width()  // 2)
        y = self.parent.winfo_y() + (self.parent.winfo_height() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")

        result = {'nombre': None, 'hora': None, 'notas': None, 'ok': False}

        import datetime as _dt
        _ahora = _dt.datetime.now() + _dt.timedelta(minutes=30)

        main_frame = tk.Frame(dialog, bg=COLORES['fondo'], padx=15, pady=15)
        main_frame.pack(fill='both', expand=True)

        tk.Label(main_frame, text="Nombre del Cliente:",
                 font=FUENTES['normal_bold'], fg=COLORES['texto'],
                 bg=COLORES['fondo']).pack(anchor='w', pady=(0, 4))
        entry_nombre = tk.Entry(main_frame, font=FUENTES['input'], relief='solid', bd=1)
        entry_nombre.pack(fill='x', pady=(0, 10), ipady=4)
        entry_nombre.focus_set()

        # ── Selector de hora visual ──────────────────────────────────────
        tk.Label(main_frame, text="Hora de Entrega:",
                 font=FUENTES['normal_bold'], fg=COLORES['texto'],
                 bg=COLORES['fondo']).pack(anchor='w', pady=(0, 4))

        hora_frame = tk.Frame(main_frame, bg=COLORES['fondo'])
        hora_frame.pack(anchor='w', pady=(0, 10))

        spin_hh = tk.Spinbox(hora_frame, from_=6, to=22, width=3, wrap=True,
                              format='%02.0f', justify='center',
                              font=('Segoe UI', 20, 'bold'),
                              bg=COLORES['fondo_input'], fg=COLORES['primario'],
                              relief='solid', bd=1,
                              buttonbackground=COLORES['fondo_card'])
        spin_hh.delete(0, tk.END)
        spin_hh.insert(0, f"{_ahora.hour:02d}")
        spin_hh.pack(side='left')

        tk.Label(hora_frame, text=" : ", font=('Segoe UI', 22, 'bold'),
                 fg=COLORES['primario'], bg=COLORES['fondo']).pack(side='left')

        spin_mm = tk.Spinbox(hora_frame, values=[f"{m:02d}" for m in range(0, 60, 5)],
                              width=3, wrap=True,
                              justify='center',
                              font=('Segoe UI', 20, 'bold'),
                              bg=COLORES['fondo_input'], fg=COLORES['primario'],
                              relief='solid', bd=1,
                              buttonbackground=COLORES['fondo_card'])
        spin_mm.delete(0, tk.END)
        # Redondear al múltiplo de 5 más cercano
        _min_r = round(_ahora.minute / 5) * 5
        spin_mm.insert(0, f"{min(_min_r, 55):02d}")
        spin_mm.pack(side='left')

        tk.Label(hora_frame, text="  (24h)", font=FUENTES['pequena'],
                 fg=COLORES['texto_secundario'], bg=COLORES['fondo']).pack(side='left', padx=6)

        tk.Label(main_frame, text="Observaciones (opcional):",
                 font=FUENTES['normal_bold'], fg=COLORES['texto'],
                 bg=COLORES['fondo']).pack(anchor='w', pady=(0, 4))
        entry_notas = tk.Entry(main_frame, font=FUENTES['input'], relief='solid', bd=1)
        entry_notas.pack(fill='x', pady=(0, 10), ipady=4)

        btn_frame = tk.Frame(main_frame, bg=COLORES['fondo'])
        btn_frame.pack(fill='x', pady=(4, 0))

        def aceptar():
            nombre = entry_nombre.get().strip()
            if not nombre:
                messagebox.showwarning("Falta Nombre", "El nombre del cliente es requerido.")
                entry_nombre.focus_set()
                return
            try:
                hh = int(spin_hh.get())
                mm_str = spin_mm.get().strip()
                mm = int(mm_str) if mm_str else 0
                hora = f"{hh:02d}:{mm:02d}"
            except Exception:
                hora = "12:00"

            result['nombre'] = nombre
            result['hora']   = hora
            result['notas']  = entry_notas.get().strip() or None
            result['ok']     = True
            dialog.destroy()

        def cancelar():
            dialog.destroy()

        entry_nombre.bind('<Return>', lambda e: spin_hh.focus_set())

        crear_boton(btn_frame, "Aceptar",  aceptar,  tipo='exito').pack(side='left', padx=5)
        crear_boton(btn_frame, "Cancelar", cancelar, tipo='error').pack(side='left', padx=5)

        dialog.wait_window()
        return (result['nombre'], result['hora'], result['notas']) if result['ok'] else None

    def _actualizar_total(self, event=None):
        self._actualizar_carrito_visual()

    def _vaciar_carrito(self):
        if self.carrito and messagebox.askyesno("Vaciar", "¿Vaciar toda la orden?"):
            self.carrito.clear()
            self._actualizar_carrito_visual()


    def _abrir_modal_pago(self):
        """Modal unificado de selección de método de pago."""
        if not self.carrito:
            messagebox.showwarning("Orden vacía", "Agregue productos primero.")
            return
        if self.total_venta <= 0:
            messagebox.showwarning("Total inválido", "El total debe ser mayor a 0.")
            return
        # Verificar caja abierta
        try:
            from database.connection import conexion_segura
            with conexion_segura() as conn:
                caja = conn.execute(
                    "SELECT id_caja FROM caja_diaria WHERE estado = 'ABIERTA'"
                ).fetchone()
            if not caja:
                ir = messagebox.askyesno(
                    "Caja cerrada",
                    "No hay caja abierta.\n\n¿Desea ir a Caja para abrirla ahora?"
                )
                if ir and self._callback_ir_caja:
                    self._callback_ir_caja()
                return
        except Exception as e:
            _log.error(f"Error verificando caja antes de pago: {e}")

        dlg = tk.Toplevel(self.parent)
        dlg.title("Cobrar")
        dlg.resizable(True, True)
        dlg.grab_set()
        dlg.configure(bg=COLORES['fondo_card'])
        w, h = 380, 480
        dlg.geometry(f"{w}x{h}+{(dlg.winfo_screenwidth()-w)//2}+{(dlg.winfo_screenheight()-h)//2}")

        tk.Frame(dlg, bg=COLORES['primario'], height=4).pack(fill='x')

        f = tk.Frame(dlg, bg=COLORES['fondo_card'], padx=20, pady=14)
        f.pack(fill='both', expand=True)

        subtotal_actual = sum(i['total'] for i in self.carrito)

        # Total (dinámico — se actualiza al cambiar descuento)
        tk.Label(f, text="TOTAL A COBRAR", font=FUENTES['pequena'],
                 fg=COLORES['texto_secundario'], bg=COLORES['fondo_card']).pack(anchor='w')
        lbl_total_modal = tk.Label(f, text=format_money(self.total_venta),
                                    font=('Consolas', 28, 'bold'),
                                    fg=COLORES['primario'], bg=COLORES['fondo_card'])
        lbl_total_modal.pack(anchor='w', pady=(0, 8))

        # Descuento (opcional)
        desc_frame = tk.Frame(f, bg=COLORES['fondo_card'])
        desc_frame.pack(fill='x', pady=(0, 10))
        tk.Label(desc_frame, text="Descuento (opcional):", font=FUENTES['pequena'],
                 fg=COLORES['texto_secundario'], bg=COLORES['fondo_card']).pack(side='left')
        entry_desc_modal = tk.Entry(desc_frame, font=FUENTES['normal'],
                                     width=10, relief='solid', bd=1, justify='right',
                                     bg=COLORES['fondo_input'], fg=COLORES['texto'],
                                     insertbackground=COLORES['primario'])
        entry_desc_modal.insert(0, '0')
        entry_desc_modal.pack(side='right')

        def _actualizar_desc_modal(*_):
            try:
                desc = float(entry_desc_modal.get() or 0)
            except Exception:
                desc = 0
            total_nuevo = max(subtotal_actual - desc, 0)
            lbl_total_modal.config(text=format_money(total_nuevo))

        entry_desc_modal.bind('<KeyRelease>', _actualizar_desc_modal)

        # Contenedor fijo que mantiene la posición entre descuento y btn_confirmar
        panel_container = tk.Frame(f, bg=COLORES['fondo_card'])
        panel_container.pack(fill='x', pady=(0, 4))

        # Panel de detalle (Efectivo: monto+cambio)
        detalle_frame = tk.Frame(panel_container, bg=COLORES['fondo_card'])

        lbl_detalle_titulo = tk.Label(detalle_frame, text="", font=FUENTES['normal'],
                                       fg=COLORES['texto_secundario'], bg=COLORES['fondo_card'])
        lbl_detalle_titulo.pack(anchor='w')
        entry_detalle = tk.Entry(detalle_frame, font=FUENTES['precio'], relief='solid', bd=1,
                                  bg=COLORES['fondo_input'], fg=COLORES['texto'],
                                  insertbackground=COLORES['primario'])
        lbl_cambio = tk.Label(detalle_frame, text="", font=FUENTES['encabezado'],
                               fg=COLORES['exito'], bg=COLORES['fondo_card'])

        def _actualizar_cambio(*_):
            try:
                desc = float(entry_desc_modal.get() or 0)
            except Exception:
                desc = 0
            total_con_desc = max(subtotal_actual - desc, 0)
            try:
                recibido = float(entry_detalle.get().replace(',', '').replace('.', '') or '0')
                cambio = recibido - total_con_desc
                lbl_cambio.config(
                    text=f"Cambio: {format_money(cambio)}" if cambio >= 0 else f"Faltan: {format_money(-cambio)}",
                    fg=COLORES['exito'] if cambio >= 0 else COLORES['error'])
            except Exception:
                lbl_cambio.config(text="Cambio: —", fg=COLORES['texto_secundario'])

        entry_detalle.bind('<KeyRelease>', _actualizar_cambio)

        # ── Panel MIXTO — dentro del panel_container, mismo nivel que detalle_frame ──
        mixto_frame = tk.Frame(panel_container, bg=COLORES['fondo_card'])

        tk.Label(mixto_frame, text="Efectivo recibido:", font=FUENTES['pequena'],
                 fg=COLORES['texto_secundario'], bg=COLORES['fondo_card']).pack(anchor='w')
        entry_mixto_ef = tk.Entry(mixto_frame, font=FUENTES['precio'], relief='solid', bd=1,
                                   bg=COLORES['fondo_input'], fg=COLORES['texto'],
                                   insertbackground=COLORES['primario'])
        entry_mixto_ef.pack(fill='x', ipady=5, pady=(2, 2))

        lbl_mixto_cambio = tk.Label(mixto_frame, text="", font=FUENTES['normal'],
                                     fg=COLORES['exito'], bg=COLORES['fondo_card'])
        lbl_mixto_cambio.pack(anchor='w', pady=(0, 4))

        tk.Label(mixto_frame, text="Transferencia por:", font=FUENTES['pequena'],
                 fg=COLORES['texto_secundario'], bg=COLORES['fondo_card']).pack(anchor='w')
        transfer_method = tk.StringVar(value='NEQUI')
        tf_row = tk.Frame(mixto_frame, bg=COLORES['fondo_card'])
        tf_row.pack(fill='x', pady=(2, 4))
        for lbl_t, val_t in [("Nequi", "NEQUI"), ("TuLlave", "TULLAVE")]:
            tk.Radiobutton(tf_row, text=lbl_t, variable=transfer_method, value=val_t,
                           font=FUENTES['normal'], bg=COLORES['fondo_card'],
                           fg=COLORES['texto'], selectcolor=COLORES['fondo_card'],
                           activebackground=COLORES['fondo_card']).pack(side='left', padx=6)

        tk.Label(mixto_frame, text="Monto transferencia:", font=FUENTES['pequena'],
                 fg=COLORES['texto_secundario'], bg=COLORES['fondo_card']).pack(anchor='w')
        entry_mixto_tr = tk.Entry(mixto_frame, font=FUENTES['precio'], relief='solid', bd=1,
                                   bg=COLORES['fondo_input'], fg=COLORES['texto'],
                                   insertbackground=COLORES['primario'])
        entry_mixto_tr.pack(fill='x', ipady=5, pady=(2, 2))

        lbl_mixto_pendiente = tk.Label(mixto_frame, text="", font=FUENTES['normal'],
                                        fg=COLORES['texto_secundario'], bg=COLORES['fondo_card'])
        lbl_mixto_pendiente.pack(anchor='w', pady=(0, 4))

        selected = {'metodo': None, 'pago_split': None}

        btn_confirmar = tk.Button(f, text="Confirmar Pago",
                                   font=FUENTES['encabezado'],
                                   fg=COLORES['fondo_sidebar'], bg=COLORES['gris_400'],
                                   relief='flat', cursor='hand2', bd=0,
                                   activebackground=COLORES['acento_hover'])
        btn_confirmar.pack(fill='x', ipady=10, pady=(4, 2))
        btn_confirmar.config(state='disabled')

        def _get_total_modal():
            try:
                desc = float(entry_desc_modal.get() or 0)
            except Exception:
                desc = 0
            return max(subtotal_actual - desc, 0)

        def _confirmar():
            m = selected['metodo']
            if not m:
                return
            try:
                self.descuento = float(entry_desc_modal.get() or 0)
            except Exception:
                self.descuento = 0
            self._actualizar_total()
            if m == 'EFECTIVO':
                try:
                    recibido = float(entry_detalle.get().replace(',', '').replace('.', '') or '0')
                except ValueError:
                    messagebox.showerror("Error", "Monto recibido invalido.", parent=dlg)
                    return
                if recibido < self.total_venta:
                    messagebox.showerror("Monto insuficiente",
                                         f"Faltan: {format_money(self.total_venta - recibido)}",
                                         parent=dlg)
                    return
                dlg.destroy()
                self._procesar_pago('EFECTIVO', monto_recibido=recibido)
            elif m == 'MIXTO':
                split = selected.get('pago_split')
                if not split:
                    messagebox.showerror("Error", "Ingrese los montos del pago mixto.", parent=dlg)
                    return
                if abs((split['efectivo'] + split['transferencia']) - self.total_venta) > 1:
                    messagebox.showerror("Error",
                        f"Los montos no suman el total.\n"
                        f"Efectivo + Transfer = {format_money(split['efectivo'] + split['transferencia'])}\n"
                        f"Total = {format_money(self.total_venta)}", parent=dlg)
                    return
                dlg.destroy()
                self._procesar_pago('MIXTO', pago_split=split)
            else:
                dlg.destroy()
                self._procesar_pago(m)

        btn_confirmar.config(command=_confirmar)

        # ── Panel de detalle para Efectivo simple ──
        def _seleccionar(metodo, titulo, placeholder, mostrar_cambio):
            selected['metodo'] = metodo
            selected['pago_split'] = None
            for btn_w, m in metodo_btns:
                activo = (m == metodo)
                btn_w.config(
                    bg=COLORES['primario'] if activo else COLORES['fondo_card'],
                    fg=COLORES['texto_claro'] if activo else COLORES['texto'])
            mixto_frame.pack_forget()
            lbl_detalle_titulo.config(text=titulo)
            entry_detalle.delete(0, tk.END)
            if placeholder:
                entry_detalle.insert(0, placeholder)
            lbl_cambio.config(text="")
            if titulo:
                detalle_frame.pack(fill='x', in_=panel_container)
                entry_detalle.pack(fill='x', ipady=6, pady=(2, 4))
                if mostrar_cambio:
                    lbl_cambio.pack(anchor='w', pady=(0, 4))
                    entry_detalle.focus_set()
                else:
                    lbl_cambio.pack_forget()
            else:
                detalle_frame.pack_forget()
            btn_confirmar.config(state='normal',
                                  bg=COLORES['acento'],
                                  activebackground=COLORES['acento_hover'])
            if mostrar_cambio:
                _actualizar_cambio()

        def _calc_mixto_ef(*_):
            total = _get_total_modal()
            try:
                ef = float(entry_mixto_ef.get().replace(',', '').replace('.', '') or '0')
            except Exception:
                ef = 0
            cambio_ef = ef - total
            if ef > 0 and cambio_ef >= 0:
                lbl_mixto_cambio.config(
                    text=f"Cambio efectivo: {format_money(cambio_ef)}", fg=COLORES['exito'])
            elif ef > 0:
                restante = total - ef
                lbl_mixto_cambio.config(
                    text=f"Falta en transfer: {format_money(restante)}", fg=COLORES['texto_secundario'])
                entry_mixto_tr.delete(0, tk.END)
                entry_mixto_tr.insert(0, str(int(restante)))
            else:
                lbl_mixto_cambio.config(text="")
            _actualizar_split()

        def _calc_mixto_tr(*_):
            total = _get_total_modal()
            try:
                tr = float(entry_mixto_tr.get().replace(',', '').replace('.', '') or '0')
            except Exception:
                tr = 0
            if tr > 0:
                restante_ef = total - tr
                entry_mixto_ef.delete(0, tk.END)
                entry_mixto_ef.insert(0, str(int(max(restante_ef, 0))))
                _calc_mixto_ef()
            _actualizar_split()

        def _actualizar_split(*_):
            total = _get_total_modal()
            try:
                ef = float(entry_mixto_ef.get().replace(',', '').replace('.', '') or '0')
                tr = float(entry_mixto_tr.get().replace(',', '').replace('.', '') or '0')
            except Exception:
                ef = tr = 0
            suma = ef + tr
            diferencia = suma - total
            if abs(diferencia) <= 1:
                lbl_mixto_pendiente.config(
                    text=f"Total cubierto: {format_money(suma)}  OK", fg=COLORES['exito'])
                selected['pago_split'] = {
                    'efectivo': ef, 'transferencia': tr,
                    'metodo_transfer': transfer_method.get()
                }
            else:
                lbl_mixto_pendiente.config(
                    text=f"Total: {format_money(suma)} / Requerido: {format_money(total)}",
                    fg=COLORES['error'])
                selected['pago_split'] = None

        entry_mixto_ef.bind('<FocusOut>', _calc_mixto_ef)
        entry_mixto_ef.bind('<Return>',   _calc_mixto_ef)
        entry_mixto_tr.bind('<FocusOut>', _calc_mixto_tr)
        entry_mixto_tr.bind('<Return>',   _calc_mixto_tr)

        def _seleccionar_mixto():
            selected['metodo'] = 'MIXTO'
            selected['pago_split'] = None
            for btn_w, m in metodo_btns:
                activo = (m == 'MIXTO')
                btn_w.config(
                    bg=COLORES['primario'] if activo else COLORES['fondo_card'],
                    fg=COLORES['texto_claro'] if activo else COLORES['texto'])
            detalle_frame.pack_forget()
            mixto_frame.pack(fill='x', in_=panel_container)
            entry_mixto_ef.focus_set()
            btn_confirmar.config(state='normal',
                                  bg=COLORES['acento'],
                                  activebackground=COLORES['acento_hover'])

        # Botones de método
        tk.Label(f, text="Método de pago:", font=FUENTES['normal_bold'],
                 fg=COLORES['texto'], bg=COLORES['fondo_card']).pack(anchor='w', pady=(0, 6))

        metodo_btns = []
        metodos = [
            ("Efectivo", 'EFECTIVO', "Monto recibido:", "", True),
            ("Nequi",    'NEQUI',    "",                "", False),
            ("TuLlave",  'TULLAVE',  "",                "", False),
        ]

        grid = tk.Frame(f, bg=COLORES['fondo_card'])
        grid.pack(fill='x', pady=(0, 6))
        for col in range(4):
            grid.columnconfigure(col, weight=1)

        for idx, (texto, metodo, titulo, placeholder, cambio) in enumerate(metodos):
            btn_m = tk.Button(grid, text=texto, font=FUENTES['normal'],
                              bg=COLORES['fondo_card'], fg=COLORES['texto'],
                              relief='solid', cursor='hand2', bd=1,
                              highlightbackground=COLORES['borde'],
                              activebackground=COLORES['primario'],
                              activeforeground=COLORES['texto_claro'],
                              command=lambda m=metodo, t=titulo, p=placeholder, c=cambio:
                                      _seleccionar(m, t, p, c))
            btn_m.grid(row=0, column=idx, padx=3, pady=3, sticky='nsew', ipady=8)
            metodo_btns.append((btn_m, metodo))

        # Botón Mixto
        btn_mixto = tk.Button(grid, text="Mixto\nEfec+Transfer", font=FUENTES['pequena'],
                               bg=COLORES['fondo_card'], fg=COLORES['texto'],
                               relief='solid', cursor='hand2', bd=1,
                               highlightbackground=COLORES['borde'],
                               activebackground=COLORES['primario'],
                               activeforeground=COLORES['texto_claro'],
                               command=_seleccionar_mixto)
        btn_mixto.grid(row=0, column=3, padx=3, pady=3, sticky='nsew', ipady=4)
        metodo_btns.append((btn_mixto, 'MIXTO'))

        crear_boton(f, "Cancelar", dlg.destroy, tipo='secundario').pack(fill='x', pady=(2, 0))


    def _insertar_items_venta(self, conn, id_venta, numero, cliente, carrito):
        """Delega a models.ventas.insertar_items_venta."""
        return _insertar_items_venta_model(
            conn, id_venta, numero, cliente, carrito,
            self.usuario['nombre_completo'], self.usuario['id_usuario']
        )

    def _pedir_motivo_descuento(self):
        """Solicita motivo obligatorio (min 10 chars) antes de aplicar un descuento.
        Retorna el motivo como string, o None si el usuario canceló."""
        dialogo = tk.Toplevel(self.parent.winfo_toplevel())
        dialogo.title("Motivo del Descuento")
        dialogo.resizable(False, False)
        dialogo.grab_set()
        dialogo.configure(bg=COLORES['fondo_card'])
        w, h = 420, 210
        dialogo.geometry(f"{w}x{h}+{(dialogo.winfo_screenwidth()-w)//2}+"
                         f"{(dialogo.winfo_screenheight()-h)//2}")

        tk.Frame(dialogo, bg=COLORES['primario'], height=4).pack(fill='x')
        f = tk.Frame(dialogo, bg=COLORES['fondo_card'], padx=20, pady=16)
        f.pack(fill='both', expand=True)

        tk.Label(f, text=f"Descuento: {format_money(self.descuento)}",
                 font=FUENTES['encabezado'], fg=COLORES['advertencia'],
                 bg=COLORES['fondo_card']).pack(anchor='w', pady=(0, 6))
        tk.Label(f, text="Motivo del descuento (mínimo 10 caracteres):",
                 font=FUENTES['normal'], fg=COLORES['texto'],
                 bg=COLORES['fondo_card']).pack(anchor='w')

        entry = tk.Entry(f, font=FUENTES['input'], relief='solid', bd=1,
                         bg=COLORES['fondo_input'], fg=COLORES['texto'])
        entry.pack(fill='x', ipady=6, pady=(4, 4))
        entry.focus_set()

        lbl_err = tk.Label(f, text="", font=FUENTES['pequena'],
                           fg=COLORES['error'], bg=COLORES['fondo_card'])
        lbl_err.pack(anchor='w')

        resultado = [None]

        def _confirmar(event=None):
            motivo = entry.get().strip()
            if len(motivo) < 10:
                lbl_err.config(text="El motivo debe tener al menos 10 caracteres.")
                return
            resultado[0] = motivo
            dialogo.destroy()

        def _cancelar():
            dialogo.destroy()

        btn_f = tk.Frame(f, bg=COLORES['fondo_card'])
        btn_f.pack(fill='x', pady=(8, 0))
        crear_boton(btn_f, "Confirmar", _confirmar, tipo='acento').pack(
            side='left', fill='x', expand=True, padx=(0, 4))
        crear_boton(btn_f, "Cancelar", _cancelar, tipo='secundario').pack(side='right')
        entry.bind('<Return>', _confirmar)

        self.parent.winfo_toplevel().wait_window(dialogo)
        return resultado[0]

    def _procesar_pago(self, metodo_pago, pago_split=None, monto_recibido=None):
        """Procesa el pago y crea la venta.
        pago_split (solo para MIXTO): {'efectivo': float, 'transferencia': float, 'metodo_transfer': str}
        monto_recibido (solo para EFECTIVO): cuánto entregó el cliente (para calcular cambio)
        """
        if not self.carrito:
            messagebox.showwarning("Orden vacía", "Agregue productos a la orden primero.")
            return
        if self.total_venta <= 0:
            messagebox.showwarning("Total inválido", "El total debe ser mayor a 0.")
            return

        # --- Motivo obligatorio si hay descuento ---
        motivo_descuento = None
        if self.descuento > 0:
            motivo_descuento = self._pedir_motivo_descuento()
            if motivo_descuento is None:
                return  # usuario canceló

        # --- Validación y datos de Factura Electrónica ---
        quiere_fe = self.var_factura_electronica.get()
        datos_fe = None
        numero_fe = None
        if quiere_fe:
            from models.validaciones import validar_resolucion_dian
            resultado_dian = validar_resolucion_dian()
            if resultado_dian['nivel'] == 'bloqueado':
                messagebox.showerror("Factura Electronica Bloqueada",
                                     resultado_dian['mensaje'])
                return
            if resultado_dian['nivel'] == 'advertencia':
                if not messagebox.askyesno("Advertencia DIAN",
                                           resultado_dian['mensaje'] + "\n\n"
                                           "Desea continuar y emitir la factura?"):
                    return
            datos_fe = self._pedir_datos_factura_electronica()
            if datos_fe is None:
                return  # usuario canceló el diálogo FE

        msg = f"Total: {format_money(self.total_venta)}\nMétodo: {metodo_pago}\n\n¿Confirmar venta?"
        if not messagebox.askyesno("Confirmar Venta", msg):
            return

        _t0_pago = _time.monotonic()
        try:
            resultado = crear_venta(
                carrito=self.carrito,
                total_venta=self.total_venta,
                descuento=self.descuento,
                motivo_descuento=motivo_descuento,
                metodo_pago=metodo_pago,
                pago_split=pago_split,
                monto_recibido=monto_recibido,
                id_cliente=self.id_cliente_sel,
                cliente_nombre=self.entry_cliente.get().strip() or None,
                notas=self.entry_notas.get().strip() or None,
                datos_fe=datos_fe,
                usuario=self.usuario,
            )
        except Exception as e:
            messagebox.showerror("Error", f"Error procesando venta:\n{str(e)}")
            return

        id_venta     = resultado['id_venta']
        numero       = resultado['numero']
        numero_fe    = resultado['numero_fe']
        tiene_cocina = resultado['tiene_cocina']

        # ── UI post-venta (fuera del try de transacción: si algo falla aquí la
        #    venta YA está guardada y no debe mostrarse como error de transacción) ──
        log_performance("procesar_pago", (_time.monotonic() - _t0_pago) * 1000, numero)
        cocina_msg = "\n\nPedidos enviados a COCINA" if tiene_cocina else ""
        fe_msg = f"\nFactura: {numero_fe}" if numero_fe else ""
        if pago_split:
            metodo_msg = (f"Mixto — Efectivo: {format_money(pago_split['efectivo'])} "
                          f"/ {pago_split['metodo_transfer']}: "
                          f"{format_money(pago_split['transferencia'])}")
        else:
            metodo_msg = metodo_pago
        messagebox.showinfo(
            "Venta Exitosa",
            f"Venta #{numero}\n"
            f"Total: {format_money(self.total_venta)}\n"
            f"Metodo: {metodo_msg}"
            f"{cocina_msg}"
            f"{fe_msg}"
        )

        if messagebox.askyesno("Imprimir", "¿Desea imprimir el recibo?"):
            try:
                imprimir_recibo_venta(id_venta)
            except Exception as e_print:
                _log.error(f"Error imprimiendo recibo venta {id_venta}: {e_print}")
                messagebox.showwarning("Impresión", f"Venta guardada. Error al imprimir:\n{e_print}")

        ids_vendidos = [i['id_producto'] for i in self.carrito if not i.get('es_boleta')]
        if ids_vendidos:
            self._verificar_stock_bajo(ids_vendidos)

        self.carrito.clear()
        self.id_cliente_sel = None
        self.descuento = 0
        self.entry_cliente.delete(0, tk.END)
        self.entry_notas.delete(0, tk.END)
        self._actualizar_carrito_visual()
        self._mostrar_productos_categoria(self._cat_activa)
        self.entry_barcode.focus_set()

    def _nuevo_producto_rapido(self):
        """Permite al cajero crear un producto sobre la marcha.
        Queda con pendiente_aprobacion=1 hasta que admin lo apruebe.
        El producto queda disponible inmediatamente en el POS para su turno."""
        dialog = tk.Toplevel(self.parent.winfo_toplevel())
        dialog.title("Nuevo Producto Rapido")
        dialog.configure(bg=COLORES['fondo_card'])
        dialog.resizable(True, True)
        dialog.grab_set()

        ancho, alto = 420, 380
        dialog.geometry(f"{ancho}x{alto}+"
                        f"{(dialog.winfo_screenwidth()-ancho)//2}+"
                        f"{(dialog.winfo_screenheight()-alto)//2}")

        tk.Frame(dialog, bg=COLORES['primario'], height=4).pack(fill='x')
        tk.Label(dialog, text="Crear Producto Rapido",
                 font=FUENTES['subtitulo'], fg=COLORES['texto'],
                 bg=COLORES['fondo_card']).pack(pady=(14, 4))
        tk.Label(dialog,
                 text="Quedara pendiente de aprobacion por el administrador.",
                 font=FUENTES['pequena'], fg=COLORES['advertencia']
                 if 'advertencia' in COLORES else COLORES['error'],
                 bg=COLORES['fondo_card']).pack(pady=(0, 8))

        form = tk.Frame(dialog, bg=COLORES['fondo_card'], padx=25)
        form.pack(fill='x')

        def _campo(label, default=''):
            tk.Label(form, text=label, font=FUENTES['pequena'],
                     fg=COLORES['texto_secundario'], bg=COLORES['fondo_card'],
                     anchor='w').pack(fill='x', pady=(6, 2))
            e = tk.Entry(form, font=FUENTES['input'], relief='solid', bd=1)
            e.pack(fill='x', ipady=5)
            if default:
                e.insert(0, default)
            return e

        # Cargar categorías para combo
        try:
            with conexion_segura() as conn:
                cats = conn.execute(
                    "SELECT id_categoria, nombre FROM categorias ORDER BY nombre"
                ).fetchall()
        except Exception:
            cats = []
        cat_nombres = [c['nombre'] for c in cats]
        cat_ids = {c['nombre']: c['id_categoria'] for c in cats}

        entry_nombre = _campo("Nombre del producto *")
        entry_precio = _campo("Precio de venta * ($)")
        entry_stock  = _campo("Stock inicial", "0")

        tk.Label(form, text="Categoria *", font=FUENTES['pequena'],
                 fg=COLORES['texto_secundario'], bg=COLORES['fondo_card'],
                 anchor='w').pack(fill='x', pady=(6, 2))
        combo_cat = ttk.Combobox(form, values=cat_nombres, state='readonly',
                                 font=FUENTES['input'])
        combo_cat.pack(fill='x', ipady=4)
        if cat_nombres:
            combo_cat.set(cat_nombres[0])

        def _guardar():
            nombre = entry_nombre.get().strip()
            precio_str = entry_precio.get().strip().replace('$', '').replace('.', '').replace(',', '.')
            stock_str = entry_stock.get().strip() or '0'
            cat_sel = combo_cat.get()

            if not nombre:
                messagebox.showwarning("Campo requerido", "Ingrese el nombre.", parent=dialog)
                return
            try:
                precio = float(precio_str)
                if precio <= 0:
                    raise ValueError
            except ValueError:
                messagebox.showwarning("Precio invalido",
                                       "Ingrese un precio valido mayor a 0.", parent=dialog)
                return
            if not cat_sel or cat_sel not in cat_ids:
                messagebox.showwarning("Categoria requerida",
                                       "Seleccione una categoria.", parent=dialog)
                return
            try:
                stock = int(float(stock_str))
            except ValueError:
                stock = 0

            try:
                with conexion_segura() as conn:
                    conn.execute("""
                        INSERT INTO productos
                        (nombre, precio_venta, stock_actual, stock_minimo,
                         id_categoria, activo, pendiente_aprobacion)
                        VALUES (?, ?, ?, 1, ?, 1, 1)
                    """, (nombre, precio, stock, cat_ids[cat_sel]))
                messagebox.showinfo(
                    "Producto creado",
                    f"'{nombre}' creado y disponible en el POS.\n"
                    f"El administrador debe aprobarlo en Inventario.",
                    parent=dialog
                )
                dialog.destroy()
                self._mostrar_productos_categoria(self._cat_activa)
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo crear: {e}", parent=dialog)

        btn_f = tk.Frame(dialog, bg=COLORES['fondo_card'])
        btn_f.pack(pady=12)
        crear_boton(btn_f, "Crear Producto", _guardar, tipo='primario').pack(side='left', padx=5)
        crear_boton(btn_f, "Cancelar", dialog.destroy, tipo='outline').pack(side='left', padx=5)

        entry_nombre.focus_set()
        dialog.bind('<Escape>', lambda e: dialog.destroy())
        dialog.wait_window()

    def _pedir_datos_factura_electronica(self):
        """Muestra dialogo para capturar datos del cliente para factura electronica.
        Retorna dict con nombre/nit/email, o None si el usuario cancela."""
        dialog = tk.Toplevel(self.parent.winfo_toplevel())
        dialog.title("Datos Factura Electronica")
        dialog.configure(bg=COLORES['fondo_card'])
        dialog.resizable(True, True)
        dialog.grab_set()

        ancho, alto = 420, 310
        dx = (dialog.winfo_screenwidth() - ancho) // 2
        dy = (dialog.winfo_screenheight() - alto) // 2
        dialog.geometry(f"{ancho}x{alto}+{dx}+{dy}")

        tk.Frame(dialog, bg=COLORES['primario'], height=4).pack(fill='x')
        tk.Label(dialog, text="Datos para Factura Electronica",
                 font=FUENTES['subtitulo'], fg=COLORES['texto'],
                 bg=COLORES['fondo_card']).pack(pady=(15, 5))

        form = tk.Frame(dialog, bg=COLORES['fondo_card'], padx=25)
        form.pack(fill='x')

        tk.Label(form, text="Nombre / Razon Social *", font=FUENTES['pequena'],
                 fg=COLORES['texto_secundario'], bg=COLORES['fondo_card'],
                 anchor='w').pack(fill='x', pady=(8, 2))
        entry_nombre = tk.Entry(form, font=FUENTES['input'], relief='solid', bd=1)
        entry_nombre.pack(fill='x', ipady=5)

        tk.Label(form, text="NIT o Cedula *", font=FUENTES['pequena'],
                 fg=COLORES['texto_secundario'], bg=COLORES['fondo_card'],
                 anchor='w').pack(fill='x', pady=(8, 2))
        entry_nit = tk.Entry(form, font=FUENTES['input'], relief='solid', bd=1)
        entry_nit.pack(fill='x', ipady=5)

        tk.Label(form, text="Correo electronico (opcional)", font=FUENTES['pequena'],
                 fg=COLORES['texto_secundario'], bg=COLORES['fondo_card'],
                 anchor='w').pack(fill='x', pady=(8, 2))
        entry_email = tk.Entry(form, font=FUENTES['input'], relief='solid', bd=1)
        entry_email.pack(fill='x', ipady=5)

        resultado = [None]

        def _confirmar():
            nombre = entry_nombre.get().strip()
            nit = entry_nit.get().strip()
            if not nombre:
                messagebox.showwarning("Campo requerido",
                                       "Ingrese el nombre o razon social.", parent=dialog)
                return
            if not nit:
                messagebox.showwarning("Campo requerido",
                                       "Ingrese el NIT o cedula.", parent=dialog)
                return
            resultado[0] = {
                'nombre': nombre,
                'nit': nit,
                'email': entry_email.get().strip()
            }
            dialog.destroy()

        btn_f = tk.Frame(dialog, bg=COLORES['fondo_card'])
        btn_f.pack(pady=12)
        crear_boton(btn_f, "Confirmar", _confirmar, tipo='primario').pack(side='left', padx=5)
        crear_boton(btn_f, "Cancelar", dialog.destroy, tipo='outline').pack(side='left', padx=5)

        entry_nombre.focus_set()
        entry_nombre.bind('<Return>', lambda e: entry_nit.focus_set())
        entry_nit.bind('<Return>', lambda e: entry_email.focus_set())
        entry_email.bind('<Return>', lambda e: _confirmar())
        dialog.bind('<Escape>', lambda e: dialog.destroy())

        dialog.wait_window()
        return resultado[0]

    def _abrir_cuenta_con_busqueda(self):
        """Abre búsqueda de cliente primero, luego abre la cuenta."""
        if not self.carrito:
            messagebox.showwarning("Orden vacía", "Agregue productos primero.")
            return

        dlg = tk.Toplevel(self.parent)
        dlg.title("Abrir Cuenta — Seleccionar Cliente")
        dlg.geometry("460x400")
        dlg.resizable(True, True)
        dlg.configure(bg=COLORES['fondo_card'])
        dlg.grab_set()

        tk.Frame(dlg, bg=COLORES['primario'], height=4).pack(fill='x')
        tk.Label(dlg, text="Abrir Cuenta para Cliente",
                 font=FUENTES['subtitulo'], fg=COLORES['texto'],
                 bg=COLORES['fondo_card']).pack(padx=16, pady=(12, 4), anchor='w')

        # Nombre del cliente
        tk.Label(dlg, text="Nombre del cliente:", font=FUENTES['pequena'],
                 fg=COLORES['texto_secundario'], bg=COLORES['fondo_card']
                 ).pack(anchor='w', padx=16)
        busq_frame = tk.Frame(dlg, bg=COLORES['fondo_card'])
        busq_frame.pack(fill='x', padx=16, pady=(2, 6))
        entry_busq = tk.Entry(busq_frame, font=FUENTES['input'],
                               bg=COLORES['fondo_input'], fg=COLORES['texto'],
                               insertbackground=COLORES['acento'], relief='solid', bd=1)
        entry_busq.pack(fill='x', ipady=6)
        entry_busq.focus_set()

        # Pre-cargar con el nombre ya ingresado en entry_cliente
        nombre_previo = self.entry_cliente.get().strip()
        if nombre_previo:
            entry_busq.insert(0, nombre_previo)

        # Notas para la cuenta
        tk.Label(dlg, text="Notas (opcional):", font=FUENTES['pequena'],
                 fg=COLORES['texto_secundario'], bg=COLORES['fondo_card']
                 ).pack(anchor='w', padx=16)
        entry_notas_cuenta = tk.Entry(dlg, font=FUENTES['normal'],
                                       bg=COLORES['fondo_input'], fg=COLORES['texto'],
                                       insertbackground=COLORES['acento'], relief='solid', bd=1)
        entry_notas_cuenta.pack(fill='x', padx=16, ipady=4, pady=(2, 6))

        tabla_frame = tk.Frame(dlg, bg=COLORES['fondo_card'])
        tabla_frame.pack(fill='both', expand=True, padx=16, pady=4)

        tree = ttk.Treeview(tabla_frame, columns=('nombre', 'celular'),
                             show='headings', height=8)
        tree.column('nombre', width=280, anchor='w')
        tree.column('celular', width=120, anchor='center')
        tree.heading('nombre', text='Nombre / Cliente')
        tree.heading('celular', text='Celular')
        from utils.tema_corporativo import aplicar_estilo_tabla as _est
        _est(tree)
        scroll = ttk.Scrollbar(tabla_frame, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.pack(side='left', fill='both', expand=True)
        scroll.pack(side='right', fill='y')

        registros = []

        def cargar(termino=''):
            for item in tree.get_children():
                tree.delete(item)
            registros.clear()
            try:
                with conexion_segura() as conn:
                    like = f'%{termino}%' if termino else '%'
                    rows = conn.execute("""
                        SELECT id_cliente, nombre, celular FROM clientes
                        WHERE nombre LIKE ? OR celular LIKE ?
                        ORDER BY nombre LIMIT 30
                    """, (like, like)).fetchall()
                    for i, r in enumerate(rows):
                        registros.append({'nombre': r['nombre'], 'celular': r['celular'] or ''})
                        tree.insert('', 'end', values=(r['nombre'], r['celular'] or '—'),
                                    tags=('par' if i % 2 == 0 else 'impar',))
            except Exception as e:
                _log.error(f"Error buscando clientes: {e}")

        entry_busq.bind('<KeyRelease>', lambda e: cargar(entry_busq.get().strip()))
        cargar(nombre_previo)

        def _abrir_con_seleccion():
            sel = tree.selection()
            if sel:
                idx_sel = tree.index(sel[0])
                nombre = registros[idx_sel]['nombre']
            else:
                nombre = entry_busq.get().strip()
            if not nombre:
                messagebox.showwarning("Nombre requerido",
                                       "Escriba el nombre del cliente.", parent=dlg)
                return
            self.entry_cliente.delete(0, tk.END)
            self.entry_cliente.insert(0, nombre)
            # Pasar notas al widget oculto antes de abrir la cuenta
            notas_txt = entry_notas_cuenta.get().strip()
            self.entry_notas.delete(0, tk.END)
            if notas_txt:
                self.entry_notas.insert(0, notas_txt)
            dlg.destroy()
            self._abrir_cuenta()

        tree.bind('<Double-1>', lambda e: _abrir_con_seleccion())

        btn_f = tk.Frame(dlg, bg=COLORES['fondo_card'], padx=16, pady=10)
        btn_f.pack(fill='x')
        crear_boton(btn_f, "Agregar Cuenta", _abrir_con_seleccion,
                    tipo='azufre').pack(side='left', fill='x', expand=True, padx=(0, 4))
        crear_boton(btn_f, "Cancelar", dlg.destroy,
                    tipo='secundario').pack(side='right')

    def _abrir_cuenta(self):
        """Crea una cuenta abierta (sin pagar todavía)"""
        if not self.carrito:
            messagebox.showwarning("Orden vacía", "Agregue productos primero.")
            return

        cliente = self.entry_cliente.get().strip()
        if not cliente:
            messagebox.showwarning("Cliente Requerido",
                                    "Para cuentas abiertas necesita el nombre del cliente.")
            self.entry_cliente.focus_set()
            return

        if not messagebox.askyesno("Cuenta Abierta",
                                    f"¿Abrir cuenta para '{cliente}'?\n"
                                    f"Total actual: {format_money(self.total_venta)}"):
            return

        try:
            resultado = abrir_cuenta_abierta(
                carrito=self.carrito,
                total_venta=self.total_venta,
                descuento=self.descuento,
                id_cliente=self.id_cliente_sel,
                cliente_nombre=cliente,
                notas=self.entry_notas.get().strip() or None,
                usuario=self.usuario,
            )
        except Exception as e:
            messagebox.showerror("Error", f"Error abriendo cuenta:\n{str(e)}")
            return

        numero = resultado['numero']
        messagebox.showinfo(
            "Cuenta Abierta",
            f"Cuenta #{numero} abierta para {cliente}\n"
            f"Total: {format_money(self.total_venta)}\n\n"
            "El cliente puede seguir agregando productos."
        )

        self.carrito.clear()
        self.id_cliente_sel = None
        self.descuento = 0
        self.entry_cliente.delete(0, tk.END)
        self.entry_notas.delete(0, tk.END)
        self._actualizar_carrito_visual()
        self.entry_barcode.focus_set()

    def _verificar_stock_bajo(self, ids_productos):
        """Alerta discreta si algún producto queda bajo el stock mínimo."""
        try:
            bajo_minimo = verificar_stock_minimo(
                ids_productos, self.usuario.get('usuario', '')
            )
        except Exception as e:
            _log.error(f"Error verificando stock minimo post-venta: {e}")
            return

        if bajo_minimo:
            lista = "\n".join(
                f"  - {r['nombre']}: {r['stock_actual']} (min: {r['stock_minimo']})"
                for r in bajo_minimo
            )
            messagebox.showwarning(
                "Stock Bajo",
                f"Los siguientes productos alcanzaron su stock mínimo:\n\n{lista}"
            )

    def detener(self):
        for attr in ('_buscar_after_id', '_aviso_caja_after_id'):
            after_id = getattr(self, attr, None)
            if after_id:
                try:
                    self.parent.after_cancel(after_id)
                except Exception:
                    pass
                setattr(self, attr, None)
        try:
            self.canvas_prod.unbind_all('<MouseWheel>')
            self.canvas_prod.unbind_all('<Button-4>')
            self.canvas_prod.unbind_all('<Button-5>')
        except Exception:
            pass
