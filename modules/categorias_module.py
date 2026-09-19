"""
Módulo de Categorías y Productos - Club Los Pocitos Azufrados
Gestión dinámica de categorías, subcategorías y productos - Versión Mejorada
Carga masiva por categoría, búsqueda, filtrado y interfaz visual moderna
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, colorchooser, filedialog
import os, sys, csv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from utils.tema_corporativo import COLORES, FUENTES, crear_boton, format_money, aplicar_estilo_tabla
from database.connection import get_connection, conexion_segura


class CategoriasModule:
    """Pantalla de categorías, subcategorías y productos."""
    def __init__(self, parent, usuario):
        self.parent = parent
        self.usuario = usuario
        self.categoria_seleccionada = None
        self.categorias_data = []
        self.productos_data = []
        self.filtro_busqueda = ""
        self._crear_interfaz()
        self._cargar_categorias()

    def _crear_interfaz(self):
        """Interfaz principal mejorada con cards, búsqueda y mejor visualización"""

        # ===== HEADER CON TÍTULO Y BOTONES =====
        header = tk.Frame(self.parent, bg=COLORES['fondo'])
        header.pack(fill='x', padx=15, pady=(10, 5))

        tk.Label(header, text=" Categorías y Productos",
                 font=FUENTES['titulo'], fg=COLORES['texto'],
                 bg=COLORES['fondo']).pack(side='left')

        btns = tk.Frame(header, bg=COLORES['fondo'])
        btns.pack(side='right')
        crear_boton(btns, " Nueva Categoría", self._nueva_categoria, tipo='primario').pack(side='left', padx=4)
        crear_boton(btns, " Nuevo Producto", self._nuevo_producto, tipo='acento').pack(side='left', padx=4)
        crear_boton(btns, " Carga Masiva", self._carga_masiva, tipo='exito').pack(side='left', padx=4)

        # ===== RESUMEN (KPI BAR) =====
        summary = tk.Frame(self.parent, bg=COLORES['fondo_card'],
                          highlightbackground=COLORES['borde'], highlightthickness=1)
        summary.pack(fill='x', padx=15, pady=(5, 10))

        self.lbl_total_cats = tk.Label(summary, text=" Categorías: 0",
                                        font=FUENTES['normal'], fg=COLORES['texto'],
                                        bg=COLORES['fondo_card'])
        self.lbl_total_cats.pack(side='left', padx=15, pady=10)

        self.lbl_total_prods = tk.Label(summary, text=" Productos: 0",
                                         font=FUENTES['normal'], fg=COLORES['texto'],
                                         bg=COLORES['fondo_card'])
        self.lbl_total_prods.pack(side='left', padx=15, pady=10)

        # ===== CUERPO DIVIDIDO =====
        body = tk.Frame(self.parent, bg=COLORES['fondo'])
        body.pack(fill='both', expand=True, padx=15, pady=5)

        # ===== IZQUIERDA: CATEGORÍAS CON CARDS =====
        left = tk.Frame(body, bg=COLORES['fondo_card'],
                       highlightbackground=COLORES['borde'], highlightthickness=1)
        left.pack(side='left', fill='y', padx=(0, 8), ipady=10)
        left.pack_propagate(False)

        cat_header = tk.Frame(left, bg=COLORES['fondo_card'])
        cat_header.pack(fill='x', padx=10, pady=(8, 8))

        tk.Label(cat_header, text=" Categorías", font=FUENTES['encabezado'],
                 fg=COLORES['texto'], bg=COLORES['fondo_card']).pack(anchor='w')

        # Canvas con scrollbar para categorías
        canvas_frame = tk.Frame(left, bg=COLORES['fondo_card'])
        canvas_frame.pack(fill='both', expand=True, padx=8, pady=4)

        self.canvas_cats = tk.Canvas(canvas_frame, bg=COLORES['fondo_card'],
                                      highlightthickness=0, width=280)
        scrollbar = ttk.Scrollbar(canvas_frame, orient='vertical', command=self.canvas_cats.yview)

        self.scrollable_frame_cats = tk.Frame(self.canvas_cats, bg=COLORES['fondo_card'])
        self.scrollable_frame_cats.bind(
          "<Configure>",
            lambda e: self.canvas_cats.configure(scrollregion=self.canvas_cats.bbox("all"))
        )

        _cats_win = self.canvas_cats.create_window((0, 0), window=self.scrollable_frame_cats, anchor="nw")
        self.canvas_cats.bind('<Configure>', lambda e: self.canvas_cats.itemconfig(_cats_win, width=e.width))
        self.canvas_cats.configure(yscrollcommand=scrollbar.set)

        self.canvas_cats.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        self.categorias_data = []
        self.categoria_cards = []

        # Botones de categoría
        cat_btns = tk.Frame(left, bg=COLORES['fondo_card'], padx=8, pady=8)
        cat_btns.pack(fill='x')

        crear_boton(cat_btns, "", self._mover_categoria_arriba, tipo='secundario').pack(side='left', padx=2)
        crear_boton(cat_btns, "", self._mover_categoria_abajo, tipo='secundario').pack(side='left', padx=2)
        crear_boton(cat_btns, " Editar", self._editar_categoria, tipo='secundario').pack(side='left', padx=2)
        crear_boton(cat_btns, "", self._eliminar_categoria, tipo='error').pack(side='right', padx=2)

        # ===== DERECHA: PRODUCTOS =====
        right = tk.Frame(body, bg=COLORES['fondo'])
        right.pack(side='right', fill='both', expand=True)

        # Encabezado con nombre de categoría
        self.lbl_cat_actual = tk.Label(
            right, text="Seleccione una categoría", font=FUENTES['subtitulo'],
            fg=COLORES['texto'], bg=COLORES['fondo']
        )
        self.lbl_cat_actual.pack(anchor='w', pady=(0, 8))

        # ===== BÚSQUEDA DE PRODUCTOS =====
        search_frame = tk.Frame(right, bg=COLORES['fondo_card'],
                               highlightbackground=COLORES['borde'], highlightthickness=1)
        search_frame.pack(fill='x', padx=0, pady=(0, 8))

        tk.Label(search_frame, text="", font=FUENTES['normal'],
                 fg=COLORES['texto_secundario'], bg=COLORES['fondo_card']).pack(side='left', padx=10, pady=8)

        self.entry_busqueda = tk.Entry(search_frame, font=FUENTES['input'],
                                        relief='flat', bd=0, bg=COLORES['fondo_card'],
                                        fg=COLORES['texto'])
        self.entry_busqueda.insert(0, "Buscar productos...")
        self.entry_busqueda.pack(side='left', fill='both', expand=True, pady=8, padx=(0, 10))
        self.entry_busqueda.bind('<KeyRelease>', self._aplicar_filtro)
        self.entry_busqueda.bind('<FocusIn>', self._on_busqueda_focus_in)
        self.entry_busqueda.bind('<FocusOut>', self._on_busqueda_focus_out)

        # ===== QUICK-ADD INLINE PARA PRODUCTOS =====
        quick_add = tk.Frame(right, bg=COLORES['fondo_card'],
                            highlightbackground=COLORES['borde'], highlightthickness=1)
        quick_add.pack(fill='x', padx=0, pady=(0, 8))

        tk.Label(quick_add, text=" Agregar Rápido", font=FUENTES['encabezado'],
                 fg=COLORES['texto'], bg=COLORES['fondo_card']).pack(anchor='w', padx=10, pady=(8, 5))

        quick_form = tk.Frame(quick_add, bg=COLORES['fondo_card'])
        quick_form.pack(fill='x', padx=10, pady=(0, 8))

        # Fila 0: Categoría
        tk.Label(quick_form, text="Categoría:", font=FUENTES['pequena'],
                 fg=COLORES['texto'], bg=COLORES['fondo_card']).grid(row=0, column=0, sticky='w', padx=(0, 5))
        self.combo_quick_cat = ttk.Combobox(quick_form, font=FUENTES['pequena'],
                                             state='readonly', width=18)
        self.combo_quick_cat.grid(row=0, column=1, padx=(0, 10), ipady=2)

        tk.Label(quick_form, text="Nombre:", font=FUENTES['pequena'],
                 fg=COLORES['texto'], bg=COLORES['fondo_card']).grid(row=0, column=2, sticky='w', padx=(0, 5))
        self.entry_quick_nombre = tk.Entry(quick_form, font=FUENTES['input'],
                                            relief='solid', bd=1, width=18)
        self.entry_quick_nombre.grid(row=0, column=3, padx=(0, 10), ipady=3)

        tk.Label(quick_form, text="Precio:", font=FUENTES['pequena'],
                 fg=COLORES['texto'], bg=COLORES['fondo_card']).grid(row=0, column=4, sticky='w', padx=(0, 5))
        self.entry_quick_precio = tk.Entry(quick_form, font=FUENTES['input'],
                                            relief='solid', bd=1, width=10)
        self.entry_quick_precio.grid(row=0, column=5, padx=(0, 10), ipady=3)

        tk.Label(quick_form, text="Stock:", font=FUENTES['pequena'],
                 fg=COLORES['texto'], bg=COLORES['fondo_card']).grid(row=0, column=6, sticky='w', padx=(0, 5))
        self.entry_quick_stock = tk.Entry(quick_form, font=FUENTES['input'],
                                           relief='solid', bd=1, width=8)
        self.entry_quick_stock.insert(0, "0")
        self.entry_quick_stock.grid(row=0, column=7, padx=(0, 10), ipady=3)

        crear_boton(quick_form, " Agregar", self._agregar_producto_rapido,
                   tipo='exito').grid(row=0, column=8, padx=5)

        # ===== TABLA DE PRODUCTOS =====
        table_frame = tk.Frame(right, bg=COLORES['fondo'])
        table_frame.pack(fill='both', expand=True, pady=(0, 8))

        cols = ("icon", "id", "codigo", "nombre", "precio", "costo", "stock", "min", "unidad", "cocina")
        self.tree = ttk.Treeview(table_frame, columns=cols, show='headings', height=15)

        self.tree.heading("icon", text="")
        self.tree.heading("id", text="ID")
        self.tree.heading("codigo", text="Código Barras")
        self.tree.heading("nombre", text="Nombre")
        self.tree.heading("precio", text="Precio Venta")
        self.tree.heading("costo", text="Costo")
        self.tree.heading("stock", text="Stock")
        self.tree.heading("min", text="Mín.")
        self.tree.heading("unidad", text="Unidad")
        self.tree.heading("cocina", text="Cocina")

        self.tree.column("icon", width=30, anchor='center')
        self.tree.column("id", width=40)
        self.tree.column("codigo", width=120)
        self.tree.column("nombre", width=200)
        self.tree.column("precio", width=100, anchor='e')
        self.tree.column("costo", width=90, anchor='e')
        self.tree.column("stock", width=60, anchor='center')
        self.tree.column("min", width=40, anchor='center')
        self.tree.column("unidad", width=80)
        self.tree.column("cocina", width=60, anchor='center')

        aplicar_estilo_tabla(self.tree)
        self.tree.pack(fill='both', expand=True)
        self.tree.bind('<Double-1>', lambda e: self._editar_producto())

        # ===== BOTONES DE PRODUCTO =====
        prod_btns = tk.Frame(right, bg=COLORES['fondo'], pady=8)
        prod_btns.pack(fill='x')
        crear_boton(prod_btns, " Editar Producto", self._editar_producto, tipo='primario').pack(side='left', padx=4)
        crear_boton(prod_btns, " Asignar Código Barras", self._asignar_barcode, tipo='acento').pack(side='left', padx=4)
        crear_boton(prod_btns, " Desactivar", self._desactivar_producto, tipo='error').pack(side='right', padx=4)

    # ===== MÉTODOS DE CATEGORÍAS =====

    def _cargar_categorias(self):
        """Carga y visualiza las categorías como cards"""
        for card in self.categoria_cards:
            card.destroy()
        self.categoria_cards = []
        self.categorias_data = []

        try:
            with conexion_segura() as conn:
                cats = conn.execute("""
                    SELECT c.*, COUNT(p.id_producto) as num_productos
                    FROM categorias c
                    LEFT JOIN productos p ON c.id_categoria = p.id_categoria AND p.activo = 1
                    WHERE c.activa = 1
                    GROUP BY c.id_categoria
                    ORDER BY c.orden
              """).fetchall()

            for cat in cats:
                cat_dict = dict(cat)
                self.categorias_data.append(cat_dict)
                self._crear_card_categoria(cat_dict)

            # Actualizar combo del quick-add
            nombres_cats = [c['nombre'] for c in self.categorias_data]
            self.combo_quick_cat['values'] = nombres_cats
            if nombres_cats and not self.combo_quick_cat.get():
                self.combo_quick_cat.current(0)

            self.lbl_total_cats.config(text=f" Categorías: {len(self.categorias_data)}")
            self._actualizar_total_productos()

        except Exception as e:
            messagebox.showerror("Error", f"Error cargando categorías: {e}")

    def _crear_card_categoria(self, cat):
        """Crea una tarjeta visual para una categoría"""
        card = tk.Frame(self.scrollable_frame_cats, bg=COLORES['fondo_card'],
                       highlightbackground=cat['color'], highlightthickness=3,
                       relief='flat', cursor='hand2')
        card.pack(fill='x', padx=0, pady=4)

        def on_select(event=None):
            self.categoria_seleccionada = cat
            self._on_categoria_select(cat['id_categoria'])
            # Resalta visualmente la tarjeta seleccionada
            for c in self.categoria_cards:
                c.config(bg=COLORES['fondo_card'])
            card.config(bg=COLORES['primario_claro'])

        card.bind('<Button-1>', on_select)
        for widget in card.winfo_children():
            widget.bind('<Button-1>', on_select)

        # Contenido de la tarjeta
        content = tk.Frame(card, bg=COLORES['fondo_card'])
        content.pack(fill='both', expand=True, padx=12, pady=10)
        content.bind('<Button-1>', on_select)

        # Fila superior: emoji + nombre
        top = tk.Frame(content, bg=COLORES['fondo_card'])
        top.pack(fill='x', pady=(0, 5))
        top.bind('<Button-1>', on_select)

        # Color swatch — emojis no renderizan bien en Windows GDI (cajas negras)
        color_swatch = tk.Frame(top, bg=cat['color'], width=32, height=32)
        color_swatch.pack(side='left', padx=(0, 10))
        color_swatch.pack_propagate(False)
        color_swatch.bind('<Button-1>', on_select)

        name_frame = tk.Frame(top, bg=COLORES['fondo_card'])
        name_frame.pack(side='left', fill='both', expand=True)
        name_frame.bind('<Button-1>', on_select)

        name_label = tk.Label(name_frame, text=cat['nombre'], font=FUENTES['normal_bold'],
                             fg=COLORES['texto'], bg=COLORES['fondo_card'], justify='left', wraplength=150)
        name_label.pack(anchor='w')
        name_label.bind('<Button-1>', on_select)

        if cat['descripcion']:
            desc_label = tk.Label(name_frame, text=cat['descripcion'], font=FUENTES['pequena'],
                                 fg=COLORES['texto_secundario'], bg=COLORES['fondo_card'], justify='left', wraplength=150)
            desc_label.pack(anchor='w')
            desc_label.bind('<Button-1>', on_select)

        # Badge de cantidad de productos
        badge = tk.Label(top, text=f"{cat['num_productos']}", font=FUENTES['badge'],
                        bg=COLORES['acento'], fg=COLORES['texto'], padx=8, pady=2)
        badge.pack(side='right')
        badge.bind('<Button-1>', on_select)

        # Color bar inferior
        color_bar = tk.Frame(content, bg=cat['color'], height=3)
        color_bar.pack(fill='x', pady=(5, 0))

        self.categoria_cards.append(card)

    def _on_categoria_select(self, id_categoria):
        """Al seleccionar una categoría, muestra sus productos"""
        if self.categoria_seleccionada:
            self.lbl_cat_actual.config(
                text=f"{self.categoria_seleccionada['nombre']} — Productos"
            )
            self._cargar_productos(id_categoria)
            self.entry_busqueda.delete(0, tk.END)
            self.entry_busqueda.insert(0, "Buscar productos...")
            self.filtro_busqueda = ""

    def _mover_categoria_arriba(self):
        """Mueve la categoría seleccionada hacia arriba en el orden"""
        if not self.categoria_seleccionada:
            messagebox.showwarning("Seleccione", "Seleccione una categoría primero")
            return

        cat = self.categoria_seleccionada
        try:
            with conexion_segura() as conn:
                anterior = conn.execute("""
                    SELECT id_categoria, orden FROM categorias
                    WHERE orden < ? AND activa = 1
                    ORDER BY orden DESC LIMIT 1
              """, (cat['orden'],)).fetchone()

                if anterior:
                    conn.execute("UPDATE categorias SET orden = ? WHERE id_categoria = ?",
                               (anterior['orden'], cat['id_categoria']))
                    conn.execute("UPDATE categorias SET orden = ? WHERE id_categoria = ?",
                               (cat['orden'], anterior['id_categoria']))

            if anterior:
                self._cargar_categorias()

        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _mover_categoria_abajo(self):
        """Mueve la categoría seleccionada hacia abajo en el orden"""
        if not self.categoria_seleccionada:
            messagebox.showwarning("Seleccione", "Seleccione una categoría primero")
            return

        cat = self.categoria_seleccionada
        try:
            with conexion_segura() as conn:
                siguiente = conn.execute("""
                    SELECT id_categoria, orden FROM categorias
                    WHERE orden > ? AND activa = 1
                    ORDER BY orden ASC LIMIT 1
              """, (cat['orden'],)).fetchone()

                if siguiente:
                    conn.execute("UPDATE categorias SET orden = ? WHERE id_categoria = ?",
                               (siguiente['orden'], cat['id_categoria']))
                    conn.execute("UPDATE categorias SET orden = ? WHERE id_categoria = ?",
                               (cat['orden'], siguiente['id_categoria']))

            if siguiente:
                self._cargar_categorias()

        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _nueva_categoria(self):
        """Diálogo mejorado para crear nueva categoría con preview"""
        win = tk.Toplevel(self.parent)
        win.title("Nueva Categoría")
        win.geometry("450x450")
        win.configure(bg=COLORES['fondo_card'])
        win.transient(self.parent)
        win.grab_set()

        tk.Label(win, text=" Nueva Categoría", font=FUENTES['subtitulo'],
                 bg=COLORES['fondo_card']).pack(pady=10)

        fields = tk.Frame(win, bg=COLORES['fondo_card'], padx=20)
        fields.pack(fill='x', expand=True)

        # Nombre
        tk.Label(fields, text="Nombre:", font=FUENTES['normal'],
                 bg=COLORES['fondo_card']).pack(anchor='w', pady=(8, 2))
        entry_nombre = tk.Entry(fields, font=FUENTES['input'], relief='solid', bd=1)
        entry_nombre.pack(fill='x', ipady=4)

        # Descripción
        tk.Label(fields, text="Descripción:", font=FUENTES['normal'],
                 bg=COLORES['fondo_card']).pack(anchor='w', pady=(8, 2))
        entry_desc = tk.Entry(fields, font=FUENTES['input'], relief='solid', bd=1)
        entry_desc.pack(fill='x', ipady=4)

        # Icono con preview y sugerencias
        tk.Label(fields, text="Icono (emoji):", font=FUENTES['normal'],
                 bg=COLORES['fondo_card']).pack(anchor='w', pady=(8, 2))

        emoji_frame = tk.Frame(fields, bg=COLORES['fondo_card'])
        emoji_frame.pack(fill='x', pady=(0, 4))

        entry_icono = tk.Entry(emoji_frame, font=FUENTES['input'], relief='solid', bd=1, width=5)
        entry_icono.insert(0, "")
        entry_icono.pack(side='left', ipady=4)

        self.emoji_preview = tk.Label(emoji_frame, text="", font=('Segoe UI', 26),
                                       bg=COLORES['fondo_card'])
        self.emoji_preview.pack(side='left', padx=15)

        def actualizar_emoji(event=None):
            emoji = entry_icono.get().strip() or ""
            self.emoji_preview.config(text=emoji[:1])

        entry_icono.bind('<KeyRelease>', actualizar_emoji)

        # Sugerencias de emoji
        suggestions_label = tk.Label(fields, text="Sugerencias:            ",
                                    font=FUENTES['pequena'], fg=COLORES['texto_secundario'],
                                    bg=COLORES['fondo_card'], wraplength=400, justify='left')
        suggestions_label.pack(anchor='w', pady=(0, 8))

        # Color con preview
        tk.Label(fields, text="Color:", font=FUENTES['normal'],
                 bg=COLORES['fondo_card']).pack(anchor='w', pady=(8, 2))

        self.nuevo_color = COLORES['primario']

        color_frame = tk.Frame(fields, bg=COLORES['fondo_card'])
        color_frame.pack(fill='x', pady=(0, 8))

        def elegir_color():
            c = colorchooser.askcolor(initialcolor=self.nuevo_color)
            if c[1]:
                self.nuevo_color = c[1]
                btn_color.config(bg=self.nuevo_color)
                color_preview.config(bg=self.nuevo_color)

        btn_color = tk.Button(color_frame, text="Elegir Color", bg=self.nuevo_color,
                              fg='white', command=elegir_color, relief='flat', cursor='hand2')
        btn_color.pack(side='left', padx=(0, 10))

        color_preview = tk.Frame(color_frame, bg=self.nuevo_color, width=40, height=30)
        color_preview.pack(side='left')
        color_preview.pack_propagate(False)

        def guardar():
            nombre = entry_nombre.get().strip()
            if not nombre:
                messagebox.showwarning("Error", "Ingrese un nombre", parent=win)
                return
            try:
                with conexion_segura() as conn:
                    conn.execute("""
                        INSERT INTO categorias (nombre, descripcion, color, icono)
                        VALUES (?, ?, ?, ?)
                  """, (nombre, entry_desc.get().strip(), self.nuevo_color,
                          entry_icono.get().strip() or ''))
                win.destroy()
                self._cargar_categorias()
                messagebox.showinfo("Exito", f"Categoría '{nombre}' creada")
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=win)

        crear_boton(win, " Guardar", guardar, tipo='primario').pack(pady=15)
        entry_nombre.focus_set()

    def _editar_categoria(self):
        """Edita la categoría seleccionada"""
        if not self.categoria_seleccionada:
            messagebox.showwarning("Seleccione", "Seleccione una categoría primero")
            return
        cat = self.categoria_seleccionada
        win = tk.Toplevel(self.parent)
        win.title("Editar Categoría")
        win.geometry("380x300")
        win.configure(bg=COLORES['fondo_card'])
        win.transient(self.parent)
        win.grab_set()

        tk.Label(win, text=" Editar Categoría", font=FUENTES['subtitulo'],
                 bg=COLORES['fondo_card']).pack(pady=10)

        fields = tk.Frame(win, bg=COLORES['fondo_card'], padx=20)
        fields.pack(fill='x')

        tk.Label(fields, text="Nombre:", font=FUENTES['normal'],
                 bg=COLORES['fondo_card']).pack(anchor='w', pady=(8, 2))
        entry_nombre = tk.Entry(fields, font=FUENTES['input'], relief='solid', bd=1)
        entry_nombre.insert(0, cat['nombre'])
        entry_nombre.pack(fill='x', ipady=4)

        def guardar():
            nuevo_nombre = entry_nombre.get().strip()
            if not nuevo_nombre:
                messagebox.showwarning("Error", "Ingrese un nombre", parent=win)
                return
            try:
                with conexion_segura() as conn:
                    conn.execute(
                        "UPDATE categorias SET nombre = ? WHERE id_categoria = ?",
                        (nuevo_nombre, cat['id_categoria'])
                    )
                win.destroy()
                self._cargar_categorias()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=win)

        crear_boton(win, " Guardar", guardar, tipo='primario').pack(pady=15)
        entry_nombre.focus_set()

    def _eliminar_categoria(self):
        """Desactiva la categoría seleccionada"""
        if not self.categoria_seleccionada:
            return
        cat = self.categoria_seleccionada
        if messagebox.askyesno("Confirmar", f"¿Desactivar categoría '{cat['nombre']}'?\nLos productos quedarán sin categoría."):
            try:
                with conexion_segura() as conn:
                    conn.execute("UPDATE categorias SET activa = 0 WHERE id_categoria = ?",
                                (cat['id_categoria'],))
                self._cargar_categorias()
                self.tree.delete(*self.tree.get_children())
                self.categoria_seleccionada = None
                self.lbl_cat_actual.config(text="Seleccione una categoría")
            except Exception as e:
                messagebox.showerror("Error", str(e))

    # ===== MÉTODOS DE PRODUCTOS =====

    def _cargar_productos(self, id_categoria):
        """Carga productos de una categoría"""
        self.tree.delete(*self.tree.get_children())
        self.productos_data = []
        try:
            with conexion_segura() as conn:
                rows = conn.execute("""
                    SELECT * FROM productos WHERE id_categoria = ? AND activo = 1
                    ORDER BY nombre
              """, (id_categoria,)).fetchall()

            for i, p in enumerate(rows):
                self.productos_data.append(dict(p))

                # Icono de stock
                if p['stock_actual'] == 0:
                    icon = ""
                elif p['stock_actual'] <= p['stock_minimo']:
                    icon = ""
                else:
                    icon = ""

                tag = 'par' if i % 2 == 0 else 'impar'
                if p['stock_actual'] <= p['stock_minimo']:
                    tag = 'alerta' if p['stock_actual'] > 0 else 'critico'

                self.tree.insert('', 'end', values=(
                    icon,
                    p['id_producto'],
                    p['codigo_barras'] or '-',
                    p['nombre'],
                    format_money(p['precio_venta']),
                    format_money(p['precio_costo']),
                    p['stock_actual'],
                    p['stock_minimo'],
                    p['unidad_medida'],
                    '' if p['requiere_cocina'] else '-'
                ), tags=(tag,))

            self._actualizar_total_productos()
        except Exception as e:
            messagebox.showerror("Error", f"Error cargando productos: {e}")

    def _actualizar_total_productos(self):
        """Actualiza el total de productos en el resumen"""
        total = len([p for p in self.productos_data if p.get('activo', 1)])
        self.lbl_total_prods.config(text=f" Productos: {total}")

    def _on_busqueda_focus_in(self, event=None):
        """Limpia el placeholder al enfocar"""
        if self.entry_busqueda.get() == "Buscar productos...":
            self.entry_busqueda.delete(0, tk.END)

    def _on_busqueda_focus_out(self, event=None):
        """Restaura el placeholder si está vacío"""
        if not self.entry_busqueda.get():
            self.entry_busqueda.insert(0, "Buscar productos...")

    def _aplicar_filtro(self, event=None):
        """Filtra productos según búsqueda"""
        if not self.categoria_seleccionada:
            return

        filtro = self.entry_busqueda.get().lower()
        if filtro == "buscar productos...":
            filtro = ""

        self.filtro_busqueda = filtro

        self.tree.delete(*self.tree.get_children())

        for i, p in enumerate(self.productos_data):
            # Filtrar por nombre o código
            if filtro and filtro not in p['nombre'].lower() and filtro not in str(p.get('codigo_barras', '')).lower():
                continue

            # Icono de stock
            if p['stock_actual'] == 0:
                icon = ""
            elif p['stock_actual'] <= p['stock_minimo']:
                icon = ""
            else:
                icon = ""

            tag = 'par' if i % 2 == 0 else 'impar'
            if p['stock_actual'] <= p['stock_minimo']:
                tag = 'alerta' if p['stock_actual'] > 0 else 'critico'

            self.tree.insert('', 'end', values=(
                icon,
                p['id_producto'],
                p['codigo_barras'] or '-',
                p['nombre'],
                format_money(p['precio_venta']),
                format_money(p['precio_costo']),
                p['stock_actual'],
                p['stock_minimo'],
                p['unidad_medida'],
                '' if p['requiere_cocina'] else '-'
            ), tags=(tag,))

    def _agregar_producto_rapido(self):
        """Agrega un producto rápidamente sin diálogo"""
        # Determinar categoría: combo del quick-add tiene prioridad; fallback a selección lateral
        cat_nombre = self.combo_quick_cat.get().strip()
        cat_obj = next((c for c in self.categorias_data if c['nombre'] == cat_nombre), None)
        if not cat_obj and self.categoria_seleccionada:
            cat_obj = self.categoria_seleccionada
        if not cat_obj:
            messagebox.showwarning("Seleccione", "Seleccione una categoría en el combo de arriba")
            return

        nombre = self.entry_quick_nombre.get().strip()
        if not nombre:
            messagebox.showwarning("Error", "Ingrese nombre del producto")
            return

        try:
            precio = float(self.entry_quick_precio.get() or 0)
            stock = int(self.entry_quick_stock.get() or 0)
        except ValueError:
            messagebox.showwarning("Error", "Valores numéricos inválidos")
            return

        try:
            with conexion_segura() as conn:
                conn.execute("""
                    INSERT INTO productos
                    (nombre, id_categoria, precio_venta, stock_actual, stock_minimo, unidad_medida)
                    VALUES (?, ?, ?, ?, 5, 'unidad')
              """, (nombre, cat_obj['id_categoria'], precio, stock))

            self._cargar_productos(cat_obj['id_categoria'])
            self.entry_quick_nombre.delete(0, tk.END)
            self.entry_quick_precio.delete(0, tk.END)
            self.entry_quick_stock.delete(0, tk.END)
            self.entry_quick_stock.insert(0, "0")
            self.entry_quick_nombre.focus_set()

        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _nuevo_producto(self):
        """Diálogo completo para crear nuevo producto"""
        win = tk.Toplevel(self.parent)
        win.title("Nuevo Producto")
        win.geometry("500x600")
        win.configure(bg=COLORES['fondo_card'])
        win.transient(self.parent)
        win.grab_set()

        tk.Label(win, text=" Nuevo Producto", font=FUENTES['subtitulo'],
                 bg=COLORES['fondo_card']).pack(pady=10)

        form = tk.Frame(win, bg=COLORES['fondo_card'], padx=20)
        form.pack(fill='x', expand=True)

        # Categoría
        tk.Label(form, text="Categoría:", font=FUENTES['normal'],
                 bg=COLORES['fondo_card']).pack(anchor='w', pady=(8, 2))
        combo_cat = ttk.Combobox(form, font=FUENTES['input'], state='readonly')
        cats_list = [(c['id_categoria'], c['nombre']) for c in self.categorias_data]
        combo_cat['values'] = [c[1] for c in cats_list]
        if self.categoria_seleccionada:
            for i, c in enumerate(cats_list):
                if c[0] == self.categoria_seleccionada['id_categoria']:
                    combo_cat.current(i)
                    break
        combo_cat.pack(fill='x')

        # Nombre
        tk.Label(form, text="Nombre:", font=FUENTES['normal'],
                 bg=COLORES['fondo_card']).pack(anchor='w', pady=(8, 2))
        entry_nombre = tk.Entry(form, font=FUENTES['input'], relief='solid', bd=1)
        entry_nombre.pack(fill='x', ipady=4)

        # Código de barras
        tk.Label(form, text="Código de Barras (opcional):", font=FUENTES['normal'],
                 bg=COLORES['fondo_card']).pack(anchor='w', pady=(8, 2))
        entry_barcode = tk.Entry(form, font=('Consolas', 12), relief='solid', bd=1)
        entry_barcode.pack(fill='x', ipady=4)
        tk.Label(form, text=" Escanee el código o déjelo vacío",
                 font=FUENTES['pequena'], fg=COLORES['texto_secundario'],
                 bg=COLORES['fondo_card']).pack(anchor='w')

        # Precios
        precios = tk.Frame(form, bg=COLORES['fondo_card'])
        precios.pack(fill='x', pady=(8, 0))

        tk.Label(precios, text="Precio Venta:", font=FUENTES['normal'],
                 bg=COLORES['fondo_card']).grid(row=0, column=0, sticky='w')
        entry_precio = tk.Entry(precios, font=FUENTES['input'], relief='solid',
                                bd=1, width=15)
        entry_precio.grid(row=1, column=0, ipady=4, padx=(0, 10))

        tk.Label(precios, text="Precio Costo:", font=FUENTES['normal'],
                 bg=COLORES['fondo_card']).grid(row=0, column=1, sticky='w')
        entry_costo = tk.Entry(precios, font=FUENTES['input'], relief='solid',
                               bd=1, width=15)
        entry_costo.insert(0, "0")
        entry_costo.grid(row=1, column=1, ipady=4)

        # Stock
        stock_frame = tk.Frame(form, bg=COLORES['fondo_card'])
        stock_frame.pack(fill='x', pady=(8, 0))

        tk.Label(stock_frame, text="Stock Inicial:", font=FUENTES['normal'],
                 bg=COLORES['fondo_card']).grid(row=0, column=0, sticky='w')
        entry_stock = tk.Entry(stock_frame, font=FUENTES['input'], relief='solid',
                               bd=1, width=10)
        entry_stock.insert(0, "0")
        entry_stock.grid(row=1, column=0, ipady=4, padx=(0, 10))

        tk.Label(stock_frame, text="Stock Mínimo:", font=FUENTES['normal'],
                 bg=COLORES['fondo_card']).grid(row=0, column=1, sticky='w')
        entry_min = tk.Entry(stock_frame, font=FUENTES['input'], relief='solid',
                             bd=1, width=10)
        entry_min.insert(0, "5")
        entry_min.grid(row=1, column=1, ipady=4)

        # Opciones
        var_cocina = tk.BooleanVar()
        var_boleta = tk.BooleanVar()

        tk.Checkbutton(form, text=" Requiere cocina (enviar pedido a cocina)",
                       variable=var_cocina, font=FUENTES['normal'],
                       bg=COLORES['fondo_card']).pack(anchor='w', pady=(12, 2))
        tk.Checkbutton(form, text=" Es boleta de entrada",
                       variable=var_boleta, font=FUENTES['normal'],
                       bg=COLORES['fondo_card']).pack(anchor='w', pady=2)

        # Unidad
        tk.Label(form, text="Unidad de medida:", font=FUENTES['normal'],
                 bg=COLORES['fondo_card']).pack(anchor='w', pady=(8, 2))
        combo_unidad = ttk.Combobox(form, font=FUENTES['input'], state='readonly',
                                    values=['unidad', 'litro', 'kilo', 'porcion', 'boleta'])
        combo_unidad.current(0)
        combo_unidad.pack(fill='x')

        def guardar():
            nombre = entry_nombre.get().strip()
            if not nombre:
                messagebox.showwarning("Error", "Ingrese nombre del producto", parent=win)
                return

            try:
                precio = float(entry_precio.get() or 0)
                costo = float(entry_costo.get() or 0)
                stock = int(entry_stock.get() or 0)
                minimo = int(entry_min.get() or 5)
            except ValueError:
                messagebox.showwarning("Error", "Valores numéricos inválidos", parent=win)
                return

            cat_idx = combo_cat.current()
            id_cat = cats_list[cat_idx][0] if cat_idx >= 0 else None
            barcode = entry_barcode.get().strip() or None

            try:
                with conexion_segura() as conn:
                    conn.execute("""
                        INSERT INTO productos
                        (codigo_barras, nombre, id_categoria, precio_venta, precio_costo,
                         stock_actual, stock_minimo, unidad_medida, requiere_cocina,
                         es_boleta_entrada)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                  """, (barcode, nombre, id_cat, precio, costo, stock, minimo,
                          combo_unidad.get(), int(var_cocina.get()),
                          int(var_boleta.get())))

                win.destroy()
                if self.categoria_seleccionada:
                    self._cargar_productos(self.categoria_seleccionada['id_categoria'])
                self._cargar_categorias()
                messagebox.showinfo("Exito", f"Producto '{nombre}' creado")
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=win)

        crear_boton(win, " Guardar Producto", guardar, tipo='primario').pack(pady=15)
        entry_nombre.focus_set()

    def _carga_masiva(self):
        """Carga masiva mejorada con ayuda y template"""
        if not self.categoria_seleccionada:
            messagebox.showinfo(
              "Carga Masiva",
              "Seleccione primero una categoría.\n\n"
              "Luego podrá agregar múltiples productos de golpe:\n"
              "- Ingresando nombre, precio y stock\n"
              "- O importando desde CSV"
            )
            return

        cat = self.categoria_seleccionada
        win = tk.Toplevel(self.parent)
        win.title(f"Carga Masiva - {cat['nombre']}")
        win.geometry("750x550")
        win.configure(bg=COLORES['fondo_card'])
        win.transient(self.parent)
        win.grab_set()

        tk.Label(win, text=f" Carga Masiva > {cat['nombre']}",
                 font=FUENTES['subtitulo'], bg=COLORES['fondo_card']).pack(pady=10)

        # Sección de ayuda
        help_frame = tk.Frame(win, bg=COLORES['fondo'],
                             highlightbackground=COLORES['borde'], highlightthickness=1)
        help_frame.pack(fill='x', padx=20, pady=(0, 10))

        tk.Label(help_frame, text=" Formato CSV", font=FUENTES['encabezado'],
                 fg=COLORES['texto'], bg=COLORES['fondo']).pack(anchor='w', padx=10, pady=(8, 5))

        help_text = tk.Label(help_frame,
                            text="Ingrese un producto por línea:\n"
                               "nombre, precio_venta, stock_inicial\n\n"
                               "Ejemplo:\n"
                               "Águila Original, 4000, 200\n"
                               "Águila Light, 4000, 100\n"
                               "Poker, 3500, 150",
                            font=FUENTES['pequena'], fg=COLORES['texto_secundario'],
                            bg=COLORES['fondo'], justify='left')
        help_text.pack(anchor='w', padx=10, pady=(0, 8))

        text_frame = tk.Frame(win, bg=COLORES['fondo_card'], padx=20)
        text_frame.pack(fill='both', expand=True, pady=8)

        self.text_masiva = tk.Text(text_frame, font=('Consolas', 11),
                                    relief='solid', bd=1, wrap='none')
        self.text_masiva.pack(fill='both', expand=True)

        # Opciones
        opts = tk.Frame(win, bg=COLORES['fondo_card'], padx=20)
        opts.pack(fill='x')

        var_cocina_masiva = tk.BooleanVar()
        tk.Checkbutton(opts, text=" Todos requieren cocina",
                       variable=var_cocina_masiva, font=FUENTES['normal'],
                       bg=COLORES['fondo_card']).pack(side='left')

        btns = tk.Frame(win, bg=COLORES['fondo_card'], padx=20, pady=10)
        btns.pack(fill='x')

        def descargar_template():
            """Descarga un archivo CSV de template"""
            path = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV", "*.csv")],
                initialfile=f"template_{cat['nombre'].replace(' ', '_').lower()}.csv",
                parent=win
            )
            if path:
                try:
                    with open(path, 'w', encoding='utf-8', newline='') as f:
                        f.write("nombre,precio_venta,stock_inicial\n")
                        f.write(f"Producto Ejemplo,1000,50\n")
                    messagebox.showinfo("Exito", f"Template descargado a:\n{path}", parent=win)
                except Exception as e:
                    messagebox.showerror("Error", str(e), parent=win)

        def importar_csv():
            path = filedialog.askopenfilename(
                title="Importar CSV",
                filetypes=[("CSV", "*.csv"), ("Todos", "*.*")],
                parent=win
            )
            if path:
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        reader = csv.reader(f)
                        for row in reader:
                            if len(row) >= 2:
                                linea = ', '.join(row[:3]) if len(row) >= 3 else ', '.join(row) + ', 0'
                                self.text_masiva.insert(tk.END, linea + '\n')
                except Exception as e:
                    messagebox.showerror("Error", f"Error leyendo CSV: {e}", parent=win)

        crear_boton(btns, " Descargar Template", descargar_template, tipo='secundario').pack(side='left', padx=4)
        crear_boton(btns, " Importar CSV", importar_csv, tipo='secundario').pack(side='left', padx=4)

        def procesar():
            texto = self.text_masiva.get("1.0", tk.END).strip()
            if not texto:
                messagebox.showwarning("Vacío", "Ingrese productos", parent=win)
                return

            lineas = [l.strip() for l in texto.split('\n') if l.strip()]
            productos = []
            errores = []

            for i, linea in enumerate(lineas):
                partes = [p.strip() for p in linea.split(',')]
                if len(partes) < 2:
                    errores.append(f"Línea {i+1}: formato inválido")
                    continue
                nombre = partes[0]
                try:
                    precio = float(partes[1])
                    stock = int(partes[2]) if len(partes) > 2 else 0
                    productos.append((nombre, precio, stock))
                except ValueError:
                    errores.append(f"Línea {i+1}: valores inválidos")

            if errores:
                messagebox.showwarning("Errores", "\n".join(errores), parent=win)

            if not productos:
                return

            if not messagebox.askyesno("Confirmar",
                                        f"¿Agregar {len(productos)} productos a '{cat['nombre']}'?",
                                        parent=win):
                return

            try:
                cocina = int(var_cocina_masiva.get())
                with conexion_segura() as conn:
                    for nombre, precio, stock in productos:
                        conn.execute("""
                            INSERT OR IGNORE INTO productos
                            (nombre, id_categoria, precio_venta, stock_actual,
                             stock_minimo, requiere_cocina)
                            VALUES (?, ?, ?, ?, 5, ?)
                      """, (nombre, cat['id_categoria'], precio, stock, cocina))

                win.destroy()
                self._cargar_productos(cat['id_categoria'])
                self._cargar_categorias()
                messagebox.showinfo("Exito",
                                    f" {len(productos)} productos agregados a '{cat['nombre']}'")
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=win)

        crear_boton(btns, " Procesar Carga", procesar, tipo='primario').pack(side='right', padx=4)

    def _editar_producto(self):
        """Edita el producto seleccionado"""
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Seleccione", "Seleccione un producto de la tabla")
            return

        valores = self.tree.item(sel[0])['values']
        id_producto = valores[1]

        try:
            with conexion_segura() as conn:
                prod = conn.execute("SELECT * FROM productos WHERE id_producto = ?",
                                    (id_producto,)).fetchone()
        except Exception:
            return

        if not prod:
            return

        prod_dict = dict(prod)

        win = tk.Toplevel(self.parent)
        win.title(f"Editar Producto: {prod_dict['nombre']}")
        win.geometry("460x530")
        win.configure(bg=COLORES['fondo_card'])
        win.transient(self.parent)
        win.grab_set()

        tk.Frame(win, bg=COLORES['primario'], height=4).pack(fill='x')
        tk.Label(win, text=f"Editar Producto", font=FUENTES['subtitulo'],
                 bg=COLORES['fondo_card']).pack(anchor='w', padx=20, pady=(10, 0))

        form = tk.Frame(win, bg=COLORES['fondo_card'], padx=20, pady=6)
        form.pack(fill='x', expand=True)

        # Nombre
        tk.Label(form, text="Nombre *", font=FUENTES['normal'],
                 fg=COLORES['texto_secundario'], bg=COLORES['fondo_card']).pack(anchor='w', pady=(6, 1))
        entry_nombre = tk.Entry(form, font=FUENTES['input'], relief='solid', bd=1)
        entry_nombre.insert(0, prod_dict['nombre'])
        entry_nombre.pack(fill='x', ipady=4)

        # Código de barras — escaneable
        tk.Label(form, text="Codigo de Barras", font=FUENTES['normal'],
                 fg=COLORES['texto_secundario'], bg=COLORES['fondo_card']).pack(anchor='w', pady=(8, 1))
        barcode_frame = tk.Frame(form, bg=COLORES['fondo_card'])
        barcode_frame.pack(fill='x')
        entry_barras = tk.Entry(barcode_frame, font=('Consolas', 12), relief='solid', bd=1,
                                bg='#FFFDE7', insertbackground=COLORES['primario'])
        entry_barras.insert(0, prod_dict.get('codigo_barras') or '')
        entry_barras.pack(side='left', fill='x', expand=True, ipady=5)
        tk.Label(barcode_frame, text=" Scan/Digita", font=FUENTES['pequena'],
                 fg=COLORES['texto_secundario'], bg=COLORES['fondo_card']).pack(side='left', padx=6)

        # Precios en fila
        precios_row = tk.Frame(form, bg=COLORES['fondo_card'])
        precios_row.pack(fill='x', pady=(8, 0))
        for col, (lbl, key) in enumerate([("Precio Venta *", 'precio_venta'), ("Precio Costo", 'precio_costo')]):
            f = tk.Frame(precios_row, bg=COLORES['fondo_card'])
            f.pack(side='left', expand=True, fill='x', padx=(0, 8) if col == 0 else (0, 0))
            tk.Label(f, text=lbl, font=FUENTES['normal'],
                     fg=COLORES['texto_secundario'], bg=COLORES['fondo_card']).pack(anchor='w', pady=(0, 1))
            e = tk.Entry(f, font=FUENTES['input'], relief='solid', bd=1)
            e.insert(0, str(prod_dict.get(key) or 0))
            e.pack(fill='x', ipady=4)
            if col == 0:
                entry_precio = e
            else:
                entry_costo = e

        # Stock en fila
        stock_row = tk.Frame(form, bg=COLORES['fondo_card'])
        stock_row.pack(fill='x', pady=(8, 0))
        for col, (lbl, key) in enumerate([("Stock Actual", 'stock_actual'), ("Stock Minimo", 'stock_minimo')]):
            f = tk.Frame(stock_row, bg=COLORES['fondo_card'])
            f.pack(side='left', expand=True, fill='x', padx=(0, 8) if col == 0 else (0, 0))
            tk.Label(f, text=lbl, font=FUENTES['normal'],
                     fg=COLORES['texto_secundario'], bg=COLORES['fondo_card']).pack(anchor='w', pady=(0, 1))
            e = tk.Entry(f, font=FUENTES['input'], relief='solid', bd=1)
            e.insert(0, str(prod_dict.get(key) or 0))
            e.pack(fill='x', ipady=4)
            if col == 0:
                entry_stock = e
            else:
                entry_minimo = e

        var_cocina = tk.BooleanVar(value=bool(prod_dict.get('requiere_cocina')))
        tk.Checkbutton(form, text="Requiere Cocina", variable=var_cocina,
                       font=FUENTES['normal'], bg=COLORES['fondo_card'],
                       fg=COLORES['texto']).pack(anchor='w', pady=(10, 0))

        # Reemplazar referencias en guardar
        entries = {
            "Nombre:":       entry_nombre,
            "Código Barras:": entry_barras,
            "Precio Venta:":  entry_precio,
            "Precio Costo:":  entry_costo,
            "Stock Actual:":  entry_stock,
            "Stock Mínimo:":  entry_minimo,
        }

        def guardar():
            try:
                with conexion_segura() as conn:
                    conn.execute("""
                        UPDATE productos SET
                        nombre = ?, codigo_barras = ?, precio_venta = ?, precio_costo = ?,
                        stock_actual = ?, stock_minimo = ?, requiere_cocina = ?,
                        fecha_actualizacion = datetime('now','localtime')
                        WHERE id_producto = ?
                  """, (
                        entries["Nombre:"].get().strip(),
                        entries["Código Barras:"].get().strip() or None,
                        float(entries["Precio Venta:"].get()),
                        float(entries["Precio Costo:"].get()),
                        int(entries["Stock Actual:"].get()),
                        int(entries["Stock Mínimo:"].get()),
                        int(var_cocina.get()),
                        id_producto
                    ))
                win.destroy()
                if self.categoria_seleccionada:
                    self._cargar_productos(self.categoria_seleccionada['id_categoria'])
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=win)

        btns_row = tk.Frame(win, bg=COLORES['fondo_card'])
        btns_row.pack(fill='x', padx=20, pady=10)
        crear_boton(btns_row, "Cancelar", win.destroy, tipo='secundario').pack(side='right', padx=(4, 0))
        crear_boton(btns_row, " Guardar", guardar, tipo='primario').pack(side='right')

        entry_nombre.focus_set()

    def _asignar_barcode(self):
        """Asigna código de barras escaneando"""
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Seleccione", "Seleccione un producto")
            return

        valores = self.tree.item(sel[0])['values']
        id_producto = valores[1]
        nombre = valores[3]

        code = simpledialog.askstring(
          "Escanear Código",
            f"Escanee el código de barras para:\n{nombre}\n\n"
          "(Coloque el cursor aquí y escanee)",
            parent=self.parent
        )
        if code and code.strip():
            try:
                with conexion_segura() as conn:
                    conn.execute(
                      "UPDATE productos SET codigo_barras = ? WHERE id_producto = ?",
                        (code.strip(), id_producto)
                    )
                if self.categoria_seleccionada:
                    self._cargar_productos(self.categoria_seleccionada['id_categoria'])
                messagebox.showinfo("Exito", f"Código '{code.strip()}' asignado a '{nombre}'")
            except Exception as e:
                messagebox.showerror("Error", str(e))

    def _desactivar_producto(self):
        """Desactiva un producto"""
        sel = self.tree.selection()
        if not sel:
            return
        valores = self.tree.item(sel[0])['values']
        if messagebox.askyesno("Confirmar", f"¿Desactivar '{valores[3]}'?"):
            try:
                with conexion_segura() as conn:
                    conn.execute("UPDATE productos SET activo = 0 WHERE id_producto = ?",
                                (valores[1],))
                if self.categoria_seleccionada:
                    self._cargar_productos(self.categoria_seleccionada['id_categoria'])
                self._cargar_categorias()
            except Exception as e:
                messagebox.showerror("Error", str(e))

    def detener(self):
        pass
