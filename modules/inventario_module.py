"""
Módulo de Inventario - Club Los Pocitos Azufrados
Gestión dinámica y visual de stock con historial de movimientos
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os, sys, datetime
import csv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from utils.tema_corporativo import (COLORES, FUENTES, crear_boton, aplicar_estilo_tabla,
                                     crear_tarjeta_kpi, format_money)
from database.connection import conexion_segura
from models.inventario import (
    registrar_movimiento_stock, editar_producto as _editar_producto_db,
    carga_masiva_productos, aprobar_producto, rechazar_producto,
    agregar_variante, eliminar_variante,
)

try:
    import openpyxl
    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False


class InventarioModule:
    def __init__(self, parent, usuario):
        self.parent = parent
        self.usuario = usuario
        self.productos = []
        self.productos_filtrados = []
        self.producto_seleccionado = None
        self.mostrar_solo_bajo_stock = False
        self.termino_busqueda = ""

        self._crear_interfaz()
        self._cargar_categorias()
        self._cargar_productos()
        self._actualizar_kpis()

    def _crear_interfaz(self):
        """Interfaz principal mejorada y dinamica"""
        # Header
        header = tk.Frame(self.parent, bg=COLORES['primario'])
        header.pack(fill='x')

        inner_hdr = tk.Frame(header, bg=COLORES['primario'], padx=15, pady=10)
        inner_hdr.pack(fill='x')

        tk.Label(inner_hdr, text="Inventario", font=FUENTES['encabezado'],
                 fg=COLORES['texto_claro'], bg=COLORES['primario']).pack(side='left')

        # Botones
        btns = tk.Frame(inner_hdr, bg=COLORES['primario'])
        btns.pack(side='right')
        crear_boton(btns, " Recargar", self._cargar_productos, tipo='primario').pack(side='left', padx=4)
        crear_boton(btns, " Carga Masiva", self._carga_masiva, tipo='acento').pack(side='left', padx=4)
        crear_boton(btns, " Exportar Excel", self._exportar_xlsx, tipo='secundario').pack(side='left', padx=4)
        # Solo administradores ven el botón de aprobación de productos pendientes
        if self.usuario.get('rol') == 'administrador':
            self.btn_aprobar = crear_boton(
                btns, " Aprobar Pendientes (0)",
                self._aprobar_productos_pendientes, tipo='advertencia'
                if 'advertencia' in COLORES else 'error'
            )
            self.btn_aprobar.pack(side='left', padx=4)
        else:
            self.btn_aprobar = None

        # ========== CUERPO PRINCIPAL ==========
        body = tk.Frame(self.parent, bg=COLORES['fondo'])
        body.pack(fill='both', expand=True, padx=15, pady=5)

        # ========== KPI CARDS ==========
        kpis_frame = tk.Frame(body, bg=COLORES['fondo'])
        kpis_frame.pack(fill='x', pady=(0, 15))

        self.kpi_total_productos, self.lbl_kpi_total = crear_tarjeta_kpi(
            kpis_frame, "Total Productos", "0", icono="", color=COLORES['primario'])
        self.kpi_total_productos.pack(side='left', padx=5, fill='both', expand=True)

        self.kpi_bajo_stock, self.lbl_kpi_bajo = crear_tarjeta_kpi(
            kpis_frame, "Bajo Stock", "0", icono="", color=COLORES['advertencia'])
        self.kpi_bajo_stock.pack(side='left', padx=5, fill='both', expand=True)

        self.kpi_sin_stock, self.lbl_kpi_sin = crear_tarjeta_kpi(
            kpis_frame, "Sin Stock", "0", icono="", color=COLORES['error'])
        self.kpi_sin_stock.pack(side='left', padx=5, fill='both', expand=True)

        self.kpi_valor_total, self.lbl_kpi_valor = crear_tarjeta_kpi(
            kpis_frame, "Valor Venta", "$ 0", icono="", color=COLORES['exito'])
        self.kpi_valor_total.pack(side='left', padx=5, fill='both', expand=True)

        self.kpi_costo_total, self.lbl_kpi_costo = crear_tarjeta_kpi(
            kpis_frame, "Costo Inventario", "$ 0", icono="", color=COLORES['agua'])
        self.kpi_costo_total.pack(side='left', padx=5, fill='both', expand=True)

        # ========== FILTROS MEJORADOS ==========
        filtros = tk.Frame(body, bg=COLORES['fondo_card'],
                          highlightbackground=COLORES['borde'], highlightthickness=1)
        filtros.pack(fill='x', pady=(0, 8))

        inner_filtros = tk.Frame(filtros, bg=COLORES['fondo_card'], padx=12, pady=10)
        inner_filtros.pack(fill='x')

        tk.Frame(inner_filtros, bg=COLORES['borde'], width=1, height=24).pack(side='left', padx=8, fill='y')

        # Categoría
        tk.Label(inner_filtros, text="Categoría:", font=FUENTES['pequena'],
                fg=COLORES['texto_secundario'], bg=COLORES['fondo_card']).pack(side='left', padx=5)

        self.combo_categoria = ttk.Combobox(inner_filtros, state='readonly', width=18, font=FUENTES['normal'])
        self.combo_categoria.pack(side='left', padx=5)
        self.combo_categoria.bind('<<ComboboxSelected>>', lambda e: self._cargar_productos())

        # Búsqueda
        tk.Label(inner_filtros, text="Buscar:", font=FUENTES['pequena'],
                fg=COLORES['texto_secundario'], bg=COLORES['fondo_card']).pack(side='left', padx=(15, 5))

        self.entry_busqueda = tk.Entry(inner_filtros, font=FUENTES['input'], width=25,
                                       relief='solid', bd=1, highlightthickness=1,
                                       highlightbackground=COLORES['borde'])
        self.entry_busqueda.pack(side='left', padx=5, ipady=4)
        self.entry_busqueda.bind('<KeyRelease>', lambda e: self._filtrar_productos())

        # Botón bajo stock
        self.btn_bajo_stock = crear_boton(inner_filtros, " Bajo Stock",
                                          self._toggle_bajo_stock, tipo='advertencia')
        self.btn_bajo_stock.pack(side='left', padx=5)

        # Espaciador
        tk.Label(inner_filtros, text="", bg=COLORES['fondo_card']).pack(side='left', padx=5, expand=True)

        # Botones de acción
        crear_boton(inner_filtros, " Editar Producto", self._editar_producto, tipo='outline').pack(side='right', padx=2)
        crear_boton(inner_filtros, "Variantes", self._gestionar_variantes, tipo='agua').pack(side='right', padx=2)

        # ========== TABLA DE PRODUCTOS ==========
        tabla_frame = tk.Frame(body, bg=COLORES['fondo_card'],
                              highlightbackground=COLORES['borde'], highlightthickness=1)
        tabla_frame.pack(fill='both', expand=True, pady=(0, 10))

        self.tree_productos = ttk.Treeview(tabla_frame, height=15,
                                          columns=('codigo', 'nombre', 'categoria', 'precio', 'stock',
                                                  'stock_visual', 'minimo', 'fecha_agregado'),
                                          show='headings')

        self.tree_productos.column('codigo', width=80, anchor='center')
        self.tree_productos.column('nombre', width=200, anchor='w')
        self.tree_productos.column('categoria', width=100, anchor='w')
        self.tree_productos.column('precio', width=85, anchor='e')
        self.tree_productos.column('stock', width=70, anchor='center')
        self.tree_productos.column('stock_visual', width=120, anchor='w')
        self.tree_productos.column('minimo', width=55, anchor='center')
        self.tree_productos.column('fecha_agregado', width=110, anchor='center')

        self.tree_productos.heading('codigo', text='Código')
        self.tree_productos.heading('nombre', text='Producto')
        self.tree_productos.heading('categoria', text='Categoría')
        self.tree_productos.heading('precio', text='Precio')
        self.tree_productos.heading('stock', text='Stock')
        self.tree_productos.heading('stock_visual', text='Estado Stock')
        self.tree_productos.heading('minimo', text='Mín.')
        self.tree_productos.heading('fecha_agregado', text='Fecha Agregado')

        aplicar_estilo_tabla(self.tree_productos)
        _sb_prod = ttk.Scrollbar(tabla_frame, orient='vertical', command=self.tree_productos.yview)
        self.tree_productos.configure(yscrollcommand=_sb_prod.set)
        self.tree_productos.pack(side='left', fill='both', expand=True, padx=1, pady=1)
        _sb_prod.pack(side='right', fill='y')
        self.tree_productos.bind('<Button-1>', self._on_producto_click)
        self.tree_productos.bind('<Double-1>', self._on_producto_double_click)

        def _scroll_inv(event):
            d = int(-1 * (event.delta / 120)) if event.delta else (1 if event.num == 5 else -1)
            self.tree_productos.yview_scroll(d, "units")
        self.tree_productos.bind_all('<MouseWheel>', _scroll_inv)
        self.tree_productos.bind_all('<Button-4>', _scroll_inv)
        self.tree_productos.bind_all('<Button-5>', _scroll_inv)

        # ========== PANEL DE MOVIMIENTOS ==========
        movimientos_frame = tk.Frame(body, bg=COLORES['fondo_card'],
                                    highlightbackground=COLORES['borde'], highlightthickness=1)
        movimientos_frame.pack(fill='x', pady=(0, 0))

        # Header del panel
        header_mov = tk.Frame(movimientos_frame, bg=COLORES['fondo_card'], padx=12, pady=8)
        header_mov.pack(fill='x')

        tk.Label(header_mov, text=" Últimos Movimientos de Inventario",
                font=FUENTES['normal_bold'], fg=COLORES['texto'],
                bg=COLORES['fondo_card']).pack(side='left')

        self.btn_expandir_mov = crear_boton(header_mov, " Expandir", self._toggle_movimientos, tipo='secundario')
        self.btn_expandir_mov.pack(side='right')

        # Contenedor de movimientos (colapsable)
        self.movimientos_container = tk.Frame(movimientos_frame, bg=COLORES['fondo_card'])
        self.movimientos_container.pack(fill='both', expand=False, padx=12, pady=(0, 8))

        self.tree_movimientos = None
        self._crear_tabla_movimientos()
        self.movimientos_expandido = True
        self._cargar_movimientos()

    def _crear_tabla_movimientos(self):
        """Crea la tabla de movimientos"""
        if self.tree_movimientos:
            self.tree_movimientos.destroy()

        self.tree_movimientos = ttk.Treeview(self.movimientos_container, height=6,
                                            columns=('fecha', 'producto', 'tipo', 'cantidad',
                                                    'stock_anterior', 'stock_nuevo', 'motivo'),
                                            show='headings')

        self.tree_movimientos.column('fecha', width=110, anchor='center')
        self.tree_movimientos.column('producto', width=180, anchor='w')
        self.tree_movimientos.column('tipo', width=70, anchor='center')
        self.tree_movimientos.column('cantidad', width=70, anchor='center')
        self.tree_movimientos.column('stock_anterior', width=70, anchor='center')
        self.tree_movimientos.column('stock_nuevo', width=70, anchor='center')
        self.tree_movimientos.column('motivo', width=200, anchor='w')

        self.tree_movimientos.heading('fecha', text='Fecha')
        self.tree_movimientos.heading('producto', text='Producto')
        self.tree_movimientos.heading('tipo', text='Tipo')
        self.tree_movimientos.heading('cantidad', text='Cantidad')
        self.tree_movimientos.heading('stock_anterior', text='Stock Ant.')
        self.tree_movimientos.heading('stock_nuevo', text='Stock Nuevo')
        self.tree_movimientos.heading('motivo', text='Motivo')

        aplicar_estilo_tabla(self.tree_movimientos)
        _sb_mov = ttk.Scrollbar(self.movimientos_container, orient='vertical', command=self.tree_movimientos.yview)
        self.tree_movimientos.configure(yscrollcommand=_sb_mov.set)
        self.tree_movimientos.pack(side='left', fill='both', expand=True)
        _sb_mov.pack(side='right', fill='y')

    def _cargar_movimientos(self):
        """Carga los últimos 10 movimientos de inventario"""
        try:
            if self.tree_movimientos:
                for item in self.tree_movimientos.get_children():
                    self.tree_movimientos.delete(item)

            with conexion_segura() as conn:
                rows = conn.execute("""
                    SELECT m.id_movimiento, m.fecha, p.nombre, m.tipo, m.cantidad,
                           m.stock_anterior, m.stock_nuevo, m.motivo
                    FROM movimientos_inventario m
                    LEFT JOIN productos p ON m.id_producto = p.id_producto
                    ORDER BY m.fecha DESC
                    LIMIT 10
              """).fetchall()

                for row in rows:
                    # Formatear fecha
                    fecha_str = "---"
                    if row['fecha']:
                        try:
                            fecha_obj = datetime.datetime.fromisoformat(row['fecha'].replace('Z', '+00:00'))
                            fecha_str = fecha_obj.strftime('%d/%m/%Y %H:%M')
                        except Exception:
                            fecha_str = row['fecha'][:16] if row['fecha'] else '---'

                    # Icono por tipo
                    tipo_icono = {
                        'ENTRADA': '',
                        'SALIDA': '',
                        'VENTA': '',
                        'AJUSTE': ''
                    }.get(row['tipo'], '-')

                    self.tree_movimientos.insert('', 'end', values=(
                        fecha_str,
                        row['nombre'] or '---',
                        f"{tipo_icono} {row['tipo']}",
                        row['cantidad'],
                        row['stock_anterior'],
                        row['stock_nuevo'],
                        row['motivo'] or '---'
                    ))

        except Exception as e:
            messagebox.showerror("Error", f"Error al cargar movimientos: {str(e)}")

    def _toggle_movimientos(self):
        """Expande/colapsa el panel de movimientos"""
        if self.movimientos_expandido:
            self.movimientos_container.pack_forget()
            self.btn_expandir_mov.config(text=" Expandir")
            self.movimientos_expandido = False
        else:
            self.movimientos_container.pack(fill='both', expand=False, padx=12, pady=(0, 8))
            self.btn_expandir_mov.config(text=" Expandir")
            self.movimientos_expandido = True

    def _actualizar_kpis(self):
        """Actualiza los KPI cards"""
        try:
            with conexion_segura() as conn:
                # Total de productos
                total = conn.execute("""
                    SELECT COUNT(*) as total FROM productos WHERE activo = 1
              """).fetchone()
                total_productos = total['total'] if total else 0

                # Bajo stock (stock <= minimo)
                bajo = conn.execute("""
                    SELECT COUNT(*) as total FROM productos
                    WHERE activo = 1 AND stock_actual > 0 AND stock_actual <= stock_minimo
              """).fetchone()
                bajo_stock = bajo['total'] if bajo else 0

                # Sin stock
                sin = conn.execute("""
                    SELECT COUNT(*) as total FROM productos
                    WHERE activo = 1 AND stock_actual = 0
              """).fetchone()
                sin_stock = sin['total'] if sin else 0

                # Valor total de inventario (precio venta)
                valor = conn.execute("""
                    SELECT SUM(stock_actual * precio_venta) as total FROM productos
                    WHERE activo = 1
              """).fetchone()
                valor_total = valor['total'] if valor and valor['total'] else 0

                # Costo total de inventario (precio costo)
                costo = conn.execute("""
                    SELECT SUM(stock_actual * precio_costo) as total FROM productos
                    WHERE activo = 1 AND precio_costo > 0
              """).fetchone()
                costo_total = costo['total'] if costo and costo['total'] else 0

                # Actualizar labels
                self.lbl_kpi_total.config(text=str(total_productos))
                self.lbl_kpi_bajo.config(text=str(bajo_stock))
                self.lbl_kpi_sin.config(text=str(sin_stock))
                self.lbl_kpi_valor.config(text=format_money(valor_total))
                self.lbl_kpi_costo.config(text=format_money(costo_total))

        except Exception as e:
            messagebox.showerror("Error", f"Error al actualizar KPIs: {str(e)}")

    def _cargar_categorias(self):
        """Carga categorías en el combo"""
        try:
            with conexion_segura() as conn:
                rows = conn.execute("""
                    SELECT id_categoria, nombre FROM categorias
                    WHERE activa = 1 ORDER BY nombre
              """).fetchall()

                categorias = ['Todas'] + [row['nombre'] for row in rows]
                self.combo_categoria['values'] = categorias
                self.combo_categoria.set('Todas')

        except Exception as e:
            messagebox.showerror("Error", f"Error al cargar categorías: {str(e)}")

    def _cargar_productos(self):
        """Carga productos en la tabla"""
        try:
            with conexion_segura() as conn:
                categoria_filtro = self.combo_categoria.get()

                if categoria_filtro == 'Todas':
                    rows = conn.execute("""
                        SELECT p.id_producto, p.codigo_barras, p.nombre, c.nombre as categoria,
                               p.precio_venta, p.stock_actual, p.stock_minimo, p.fecha_creacion
                        FROM productos p
                        LEFT JOIN categorias c ON p.id_categoria = c.id_categoria
                        WHERE p.activo = 1
                        ORDER BY p.nombre
                  """).fetchall()
                else:
                    rows = conn.execute("""
                        SELECT p.id_producto, p.codigo_barras, p.nombre, c.nombre as categoria,
                               p.precio_venta, p.stock_actual, p.stock_minimo, p.fecha_creacion
                        FROM productos p
                        LEFT JOIN categorias c ON p.id_categoria = c.id_categoria
                        WHERE p.activo = 1 AND c.nombre = ?
                        ORDER BY p.nombre
                  """, (categoria_filtro,)).fetchall()

                # Limpiar árbol
                for item in self.tree_productos.get_children():
                    self.tree_productos.delete(item)

                # Agregar productos
                self.productos = []
                for i, row in enumerate(rows):
                    stock = row['stock_actual']
                    minimo = row['stock_minimo']

                    # Formatear fecha
                    fecha_agregado = row['fecha_creacion']
                    if fecha_agregado:
                        try:
                            fecha_obj = datetime.datetime.fromisoformat(fecha_agregado.replace('Z', '+00:00'))
                            fecha_str = fecha_obj.strftime('%d/%m/%Y')
                        except Exception:
                            fecha_str = fecha_agregado[:10] if fecha_agregado else '---'
                    else:
                        fecha_str = '---'

                    # Determinar tag según stock
                    if stock == 0:
                        tag = 'critico'
                    elif stock <= minimo:
                        tag = 'alerta'
                    else:
                        tag = 'par' if i % 2 == 0 else 'impar'

                    # Crear barra visual de stock
                    stock_visual = self._crear_barra_stock(stock, minimo)

                    self.tree_productos.insert('', 'end', values=(
                        row['codigo_barras'] or '---',
                        row['nombre'],
                        row['categoria'] or 'Sin Categoría',
                        format_money(row['precio_venta']),
                        f"{stock}",
                        stock_visual,
                        f"{minimo}",
                        fecha_str
                    ), tags=(tag,), iid=row['id_producto'])

                    self.productos.append({
                        'id': row['id_producto'],
                        'nombre': row['nombre'],
                        'stock': stock,
                        'minimo': minimo,
                        'codigo_barras': row['codigo_barras'],
                        'categoria': row['categoria'],
                        'precio_venta': row['precio_venta'],
                        'fecha_creacion': fecha_str
                    })

                # Aplicar filtros
                self._filtrar_productos()
                self._actualizar_kpis()
                self._cargar_movimientos()
                self._actualizar_contador_pendientes()

        except Exception as e:
            messagebox.showerror("Error", f"Error al cargar productos: {str(e)}")

    def _crear_barra_stock(self, stock, minimo):
        """Crea representación visual del stock con emoji"""
        if stock == 0:
            return " Sin Stock"
        elif stock <= minimo:
            return f" Bajo ({stock})"
        else:
            return f" Disponible ({stock})"

    def _filtrar_productos(self):
        """Filtra productos por búsqueda y estado de stock"""
        termino = self.entry_busqueda.get().lower()

        for item in self.tree_productos.get_children():
            self.tree_productos.delete(item)

        filtrados = self.productos
        if termino:
            filtrados = [p for p in filtrados if termino in p['nombre'].lower() or
                        termino in (p['codigo_barras'] or '').lower()]

        if self.mostrar_solo_bajo_stock:
            filtrados = [p for p in filtrados if p['stock'] <= p['minimo']]

        for i, prod in enumerate(filtrados):
            stock = prod['stock']
            minimo = prod['minimo']

            # Determinar tag
            if stock == 0:
                tag = 'critico'
            elif stock <= minimo:
                tag = 'alerta'
            else:
                tag = 'par' if i % 2 == 0 else 'impar'

            stock_visual = self._crear_barra_stock(stock, minimo)

            self.tree_productos.insert('', 'end', values=(
                prod['codigo_barras'] or '---',
                prod['nombre'],
                prod['categoria'] or 'Sin Categoría',
                format_money(prod['precio_venta']),
                f"{stock}",
                stock_visual,
                f"{minimo}",
                prod['fecha_creacion']
            ), tags=(tag,), iid=prod['id'])

    def _toggle_bajo_stock(self):
        """Toggle para mostrar solo productos con bajo stock"""
        self.mostrar_solo_bajo_stock = not self.mostrar_solo_bajo_stock
        if self.mostrar_solo_bajo_stock:
            self.btn_bajo_stock.config(relief='sunken')
        else:
            self.btn_bajo_stock.config(relief='raised')
        self._filtrar_productos()

    def _on_producto_click(self, event):
        """Maneja clic en un producto"""
        item = self.tree_productos.selection()
        if item:
            self.producto_seleccionado = int(item[0])

    def _on_producto_double_click(self, event):
        """Abre edición completa del producto al doble click"""
        item = self.tree_productos.selection()
        if item:
            self.producto_seleccionado = int(item[0])
            self._editar_producto()

    def _ajuste_rapido_stock(self):
        """Diálogo mejorado de ajuste rápido de stock"""
        if self.producto_seleccionado is None:
            messagebox.showwarning("Seleccione un Producto", "Por favor seleccione un producto")
            return

        prod = next((p for p in self.productos if p['id'] == self.producto_seleccionado), None)
        if not prod:
            return

        dialog = tk.Toplevel(self.parent)
        dialog.title(f"Ajuste Rápido: {prod['nombre']}")
        dialog.geometry("400x280")
        dialog.resizable(True, True)

        # Información del producto
        info_frame = tk.Frame(dialog, bg=COLORES['fondo_card'], relief='flat')
        info_frame.pack(fill='x', padx=15, pady=(15, 10))

        tk.Label(info_frame, text=f"Producto: {prod['nombre']}", font=FUENTES['normal_bold'],
                fg=COLORES['texto'], bg=COLORES['fondo_card']).pack(anchor='w')
        tk.Label(info_frame, text=f"Stock Actual: {prod['stock']} | Mínimo: {prod['minimo']}",
                font=FUENTES['pequena'], fg=COLORES['texto_secundario'],
                bg=COLORES['fondo_card']).pack(anchor='w', pady=(4, 0))

        # Sección de entrada
        entrada_frame = tk.Frame(dialog, bg=COLORES['fondo_card'])
        entrada_frame.pack(fill='both', expand=True, padx=15, pady=10)

        tk.Label(entrada_frame, text="Nuevo Stock:", font=FUENTES['normal'],
                fg=COLORES['texto'], bg=COLORES['fondo_card']).pack(anchor='w', pady=(0, 5))

        spinbox = tk.Spinbox(entrada_frame, from_=0, to=10000, font=FUENTES['input'],
                           width=15, relief='solid', bd=1)
        spinbox.set(prod['stock'])
        spinbox.pack(anchor='w', ipady=6, pady=5)

        tk.Label(entrada_frame, text="Motivo/Observación:", font=FUENTES['normal'],
                fg=COLORES['texto'], bg=COLORES['fondo_card']).pack(anchor='w', pady=(10, 5))

        entry_motivo = tk.Entry(entrada_frame, font=FUENTES['input'], relief='solid', bd=1)
        entry_motivo.pack(fill='x', ipady=6)
        entry_motivo.insert(0, "Ajuste manual")

        def guardar():
            try:
                nuevo_stock = int(spinbox.get())
                motivo = entry_motivo.get().strip()
                diferencia = nuevo_stock - prod['stock']

                if diferencia == 0:
                    messagebox.showinfo("Información", "No hay cambios en el stock")
                    return

                tipo_mov = 'ENTRADA' if diferencia > 0 else 'SALIDA'

                registrar_movimiento_stock(
                    self.producto_seleccionado, tipo_mov, abs(diferencia),
                    prod['stock'], nuevo_stock, motivo, self.usuario['usuario']
                )

                messagebox.showinfo("Exito",
                                  f"Stock ajustado: {prod['stock']} > {nuevo_stock} unidades")
                dialog.destroy()
                self._cargar_productos()

            except ValueError:
                messagebox.showerror("Error", "Ingrese un valor numérico válido")

        # Botones
        btn_frame = tk.Frame(dialog, bg=COLORES['fondo_card'])
        btn_frame.pack(fill='x', padx=15, pady=15)
        crear_boton(btn_frame, "Guardar", guardar, tipo='exito').pack(side='left', padx=2)
        crear_boton(btn_frame, "Cancelar", dialog.destroy, tipo='secundario').pack(side='right', padx=2)

    def _gestionar_variantes(self):
        """Gestiona las variantes (opciones) de un producto"""
        if self.producto_seleccionado is None:
            messagebox.showwarning("Seleccione un Producto", "Por favor seleccione un producto de la lista")
            return

        prod = next((p for p in self.productos if p['id'] == self.producto_seleccionado), None)
        if not prod:
            return

        dlg = tk.Toplevel(self.parent)
        dlg.title(f"Variantes: {prod['nombre']}")
        dlg.geometry("500x420")
        dlg.resizable(True, True)
        dlg.configure(bg=COLORES['fondo_card'])
        dlg.grab_set()

        tk.Label(dlg, text=f"Variantes de: {prod['nombre']}", font=FUENTES['subtitulo'],
                 fg=COLORES['texto'], bg=COLORES['fondo_card']).pack(padx=16, pady=(14, 4), anchor='w')
        tk.Label(dlg, text="El precio de venta de cada variante = Precio base + Precio adicional",
                 font=FUENTES['pequena'], fg=COLORES['texto_secundario'],
                 bg=COLORES['fondo_card']).pack(padx=16, anchor='w')

        # Tabla de variantes existentes
        tabla_frame = tk.Frame(dlg, bg=COLORES['fondo_card'])
        tabla_frame.pack(fill='both', expand=True, padx=16, pady=8)

        tree_var = ttk.Treeview(tabla_frame,
                                 columns=('nombre', 'precio_adicional', 'activa'),
                                 show='headings', height=8)
        tree_var.column('nombre', width=200, anchor='w')
        tree_var.column('precio_adicional', width=120, anchor='e')
        tree_var.column('activa', width=80, anchor='center')
        tree_var.heading('nombre', text='Variante')
        tree_var.heading('precio_adicional', text='Precio Adicional')
        tree_var.heading('activa', text='Activa')
        aplicar_estilo_tabla(tree_var)

        scroll_var = ttk.Scrollbar(tabla_frame, orient='vertical', command=tree_var.yview)
        tree_var.configure(yscrollcommand=scroll_var.set)
        tree_var.pack(side='left', fill='both', expand=True)
        scroll_var.pack(side='right', fill='y')

        def cargar_variantes():
            for item in tree_var.get_children():
                tree_var.delete(item)
            try:
                with conexion_segura() as conn:
                    rows = conn.execute("""
                        SELECT id_variante, nombre_variante, precio_adicional, activa
                        FROM variantes_producto WHERE id_producto=? ORDER BY nombre_variante
                  """, (prod['id'],)).fetchall()
                    for i, r in enumerate(rows):
                        tag = 'par' if i % 2 == 0 else 'impar'
                        tree_var.insert('', 'end', iid=r['id_variante'], values=(
                            r['nombre_variante'],
                            format_money(r['precio_adicional']),
                            'Si' if r['activa'] else 'No'
                        ), tags=(tag,))
            except Exception as e:
                messagebox.showerror("Error", f"Error: {e}", parent=dlg)

        cargar_variantes()

        # Formulario para agregar variante
        add_frame = tk.Frame(dlg, bg=COLORES['fondo_card'], padx=16)
        add_frame.pack(fill='x')
        tk.Label(add_frame, text="Nueva Variante:", font=FUENTES['pequena'],
                 fg=COLORES['texto_secundario'], bg=COLORES['fondo_card']).pack(anchor='w')
        row_add = tk.Frame(add_frame, bg=COLORES['fondo_card'])
        row_add.pack(fill='x', pady=4)

        e_nombre_var = tk.Entry(row_add, font=FUENTES['input'], width=20,
                                 bg=COLORES['fondo_input'], fg=COLORES['texto'],
                                 insertbackground=COLORES['acento'], relief='solid', bd=1,
                                 placeholder_text='Ej: Pequena, Grande...' if False else None)
        e_nombre_var.pack(side='left', ipady=5, padx=(0, 6))
        tk.Label(row_add, text="+$", font=FUENTES['normal'],
                 fg=COLORES['texto_secundario'], bg=COLORES['fondo_card']).pack(side='left')
        e_precio_add = tk.Entry(row_add, font=FUENTES['input'], width=8,
                                 bg=COLORES['fondo_input'], fg=COLORES['texto'],
                                 insertbackground=COLORES['acento'], relief='solid', bd=1)
        e_precio_add.insert(0, '0')
        e_precio_add.pack(side='left', ipady=5, padx=4)

        def agregar():
            nombre_v = e_nombre_var.get().strip()
            if not nombre_v:
                messagebox.showwarning("Requerido", "Ingrese el nombre de la variante", parent=dlg)
                return
            try:
                precio_add = float(e_precio_add.get().replace(',', '.') or 0)
            except ValueError:
                messagebox.showerror("Error", "Precio adicional inválido", parent=dlg)
                return
            try:
                agregar_variante(prod['id'], nombre_v, precio_add)
                e_nombre_var.delete(0, tk.END)
                e_precio_add.delete(0, tk.END)
                e_precio_add.insert(0, '0')
                cargar_variantes()
            except Exception as e:
                messagebox.showerror("Error", f"Error al guardar: {e}", parent=dlg)

        def eliminar():
            sel = tree_var.selection()
            if not sel:
                messagebox.showwarning("Seleccione", "Seleccione una variante para eliminar", parent=dlg)
                return
            try:
                eliminar_variante(int(sel[0]))
                cargar_variantes()
            except Exception as e:
                messagebox.showerror("Error", f"Error al eliminar: {e}", parent=dlg)

        crear_boton(row_add, "Agregar", agregar, tipo='exito').pack(side='left', padx=6)

        btns = tk.Frame(dlg, bg=COLORES['fondo_card'])
        btns.pack(fill='x', padx=16, pady=10)
        crear_boton(btns, "Eliminar Seleccionada", eliminar, tipo='error').pack(side='left', padx=4)
        crear_boton(btns, "Cerrar", dlg.destroy, tipo='secundario').pack(side='right', padx=4)

    def _editar_producto(self):
        """Abre formulario completo de edición del producto seleccionado"""
        if self.producto_seleccionado is None:
            messagebox.showwarning("Seleccione un Producto", "Por favor seleccione un producto de la lista")
            return

        prod = next((p for p in self.productos if p['id'] == self.producto_seleccionado), None)
        if not prod:
            return

        # Cargar datos completos del producto
        try:
            with conexion_segura() as conn:
                datos = conn.execute("""
                    SELECT p.*, c.nombre as cat_nombre
                    FROM productos p
                    LEFT JOIN categorias c ON p.id_categoria = c.id_categoria
                    WHERE p.id_producto = ?
              """, (prod['id'],)).fetchone()
                categorias = conn.execute(
                  "SELECT id_categoria, nombre FROM categorias WHERE activa=1 ORDER BY nombre"
                ).fetchall()
        except Exception as e:
            messagebox.showerror("Error", f"Error al cargar producto: {e}")
            return

        dlg = tk.Toplevel(self.parent)
        dlg.title(f"Editar Producto: {datos['nombre']}")
        dlg.geometry("480x500")
        dlg.resizable(True, True)
        dlg.configure(bg=COLORES['fondo_card'])
        dlg.grab_set()

        tk.Label(dlg, text="Editar Producto", font=FUENTES['subtitulo'],
                 fg=COLORES['texto'], bg=COLORES['fondo_card']).pack(padx=20, pady=(16, 8), anchor='w')

        form = tk.Frame(dlg, bg=COLORES['fondo_card'])
        form.pack(fill='both', expand=True, padx=20)

        def campo(label, val=''):
            tk.Label(form, text=label, font=FUENTES['pequena'],
                     fg=COLORES['texto_secundario'], bg=COLORES['fondo_card']).pack(anchor='w', pady=(6, 0))
            e = tk.Entry(form, font=FUENTES['input'],
                         bg=COLORES['fondo_input'], fg=COLORES['texto'],
                         insertbackground=COLORES['acento'], relief='solid', bd=1)
            e.insert(0, str(val) if val is not None else '')
            e.pack(fill='x', ipady=5)
            return e

        e_nombre = campo("Nombre *", datos['nombre'])

        # Código de barras — escaneable
        tk.Label(form, text="Codigo de Barras  (escanea o digita)", font=FUENTES['pequena'],
                 fg=COLORES['texto_secundario'], bg=COLORES['fondo_card']).pack(anchor='w', pady=(6, 0))
        e_codigo = tk.Entry(form, font=('Consolas', 12),
                            bg='#FFFDE7', fg=COLORES['texto'],
                            insertbackground=COLORES['primario'], relief='solid', bd=1)
        e_codigo.insert(0, datos['codigo_barras'] or '')
        e_codigo.pack(fill='x', ipady=6)
        # Enter tras escaneo mueve el foco al siguiente campo
        # bind de Return se agrega después de crear combo_cat

        # Categoría
        tk.Label(form, text="Categoria", font=FUENTES['pequena'],
                 fg=COLORES['texto_secundario'], bg=COLORES['fondo_card']).pack(anchor='w', pady=(6, 0))
        cat_nombres = [c['nombre'] for c in categorias]
        combo_cat = ttk.Combobox(form, values=cat_nombres, state='readonly', font=FUENTES['input'])
        cat_actual = datos['cat_nombre'] or ''
        if cat_actual in cat_nombres:
            combo_cat.set(cat_actual)
        combo_cat.pack(fill='x', ipady=4)
        e_codigo.bind('<Return>', lambda e: combo_cat.focus_set())

        # Precios en fila
        precios_row = tk.Frame(form, bg=COLORES['fondo_card'])
        precios_row.pack(fill='x', pady=(6, 0))

        precio_left = tk.Frame(precios_row, bg=COLORES['fondo_card'])
        precio_left.pack(side='left', fill='x', expand=True, padx=(0, 8))
        tk.Label(precio_left, text="Precio Venta *", font=FUENTES['pequena'],
                 fg=COLORES['texto_secundario'], bg=COLORES['fondo_card']).pack(anchor='w')
        e_precio_venta = tk.Entry(precio_left, font=FUENTES['input'],
                                   bg=COLORES['fondo_input'], fg=COLORES['acento'],
                                   insertbackground=COLORES['acento'], relief='solid', bd=1)
        e_precio_venta.insert(0, str(int(datos['precio_venta'])) if datos['precio_venta'] else '0')
        e_precio_venta.pack(fill='x', ipady=5)

        precio_right = tk.Frame(precios_row, bg=COLORES['fondo_card'])
        precio_right.pack(side='right', fill='x', expand=True)
        tk.Label(precio_right, text="Precio Costo", font=FUENTES['pequena'],
                 fg=COLORES['texto_secundario'], bg=COLORES['fondo_card']).pack(anchor='w')
        e_precio_costo = tk.Entry(precio_right, font=FUENTES['input'],
                                   bg=COLORES['fondo_input'], fg=COLORES['texto'],
                                   insertbackground=COLORES['acento'], relief='solid', bd=1)
        e_precio_costo.insert(0, str(int(datos['precio_costo'])) if datos['precio_costo'] else '0')
        e_precio_costo.pack(fill='x', ipady=5)

        # Stock
        stock_row = tk.Frame(form, bg=COLORES['fondo_card'])
        stock_row.pack(fill='x', pady=(6, 0))

        stock_left = tk.Frame(stock_row, bg=COLORES['fondo_card'])
        stock_left.pack(side='left', fill='x', expand=True, padx=(0, 8))
        tk.Label(stock_left, text="Stock Minimo", font=FUENTES['pequena'],
                 fg=COLORES['texto_secundario'], bg=COLORES['fondo_card']).pack(anchor='w')
        e_stock_min = tk.Entry(stock_left, font=FUENTES['input'],
                                bg=COLORES['fondo_input'], fg=COLORES['texto'],
                                insertbackground=COLORES['acento'], relief='solid', bd=1)
        e_stock_min.insert(0, str(datos['stock_minimo'] or 5))
        e_stock_min.pack(fill='x', ipady=5)

        stock_right = tk.Frame(stock_row, bg=COLORES['fondo_card'])
        stock_right.pack(side='right', fill='x', expand=True)
        tk.Label(stock_right, text="Impuesto %", font=FUENTES['pequena'],
                 fg=COLORES['texto_secundario'], bg=COLORES['fondo_card']).pack(anchor='w')
        e_impuesto = tk.Entry(stock_right, font=FUENTES['input'],
                               bg=COLORES['fondo_input'], fg=COLORES['texto'],
                               insertbackground=COLORES['acento'], relief='solid', bd=1)
        e_impuesto.insert(0, str(datos['impuesto_porcentaje'] or 0))
        e_impuesto.pack(fill='x', ipady=5)

        # Checkboxes
        var_cocina = tk.IntVar(value=datos['requiere_cocina'] or 0)
        var_descuento = tk.IntVar(value=datos['permite_descuento'] if datos['permite_descuento'] is not None else 1)

        chk_frame = tk.Frame(form, bg=COLORES['fondo_card'])
        chk_frame.pack(fill='x', pady=(8, 0))
        tk.Checkbutton(chk_frame, text="Requiere Cocina", variable=var_cocina,
                       bg=COLORES['fondo_card'], fg=COLORES['texto'],
                       selectcolor=COLORES['primario'], activebackground=COLORES['fondo_card']).pack(side='left', padx=10)
        tk.Checkbutton(chk_frame, text="Permite Descuento", variable=var_descuento,
                       bg=COLORES['fondo_card'], fg=COLORES['texto'],
                       selectcolor=COLORES['primario'], activebackground=COLORES['fondo_card']).pack(side='left', padx=10)

        def guardar():
            nombre = e_nombre.get().strip()
            if not nombre:
                messagebox.showwarning("Requerido", "El nombre es obligatorio", parent=dlg)
                return
            try:
                precio_venta = float(e_precio_venta.get().replace(',', '.') or 0)
                precio_costo = float(e_precio_costo.get().replace(',', '.') or 0)
                stock_minimo = int(e_stock_min.get() or 5)
                impuesto = float(e_impuesto.get() or 0)
            except ValueError:
                messagebox.showerror("Error", "Valores numéricos inválidos", parent=dlg)
                return

            # Obtener id_categoria
            cat_sel = combo_cat.get()
            id_cat = next((c['id_categoria'] for c in categorias if c['nombre'] == cat_sel), None)

            try:
                _editar_producto_db(
                    prod['id'],
                    nombre=nombre,
                    codigo_barras=e_codigo.get().strip() or None,
                    id_categoria=id_cat,
                    precio_venta=precio_venta,
                    precio_costo=precio_costo,
                    stock_minimo=stock_minimo,
                    impuesto_porcentaje=impuesto,
                    requiere_cocina=var_cocina.get(),
                    permite_descuento=var_descuento.get(),
                    usuario_nombre=self.usuario['usuario'],
                )
                dlg.destroy()
                self._cargar_productos()
                self._actualizar_kpis()
            except Exception as e:
                messagebox.showerror("Error", f"Error al guardar: {e}", parent=dlg)

        btns = tk.Frame(dlg, bg=COLORES['fondo_card'])
        btns.pack(fill='x', padx=20, pady=12)
        crear_boton(btns, "Guardar", guardar, tipo='exito').pack(side='right', padx=4)
        crear_boton(btns, "Cancelar", dlg.destroy, tipo='secundario').pack(side='right', padx=4)

    def _agregar_stock(self):
        """Agrega stock a un producto"""
        if self.producto_seleccionado is None:
            messagebox.showwarning("Seleccione un Producto", "Por favor seleccione un producto")
            return

        prod = next((p for p in self.productos if p['id'] == self.producto_seleccionado), None)
        if not prod:
            messagebox.showerror("Error", "Producto no encontrado")
            return

        # Diálogo mejorado
        dialog = tk.Toplevel(self.parent.winfo_toplevel())
        dialog.title("Agregar Stock")
        dialog.geometry("400x280")
        dialog.resizable(True, True)
        dialog.grab_set()

        tk.Label(dialog, text=f"Producto: {prod['nombre']}", font=FUENTES['normal_bold'],
                fg=COLORES['texto']).pack(padx=15, pady=(15, 5))
        tk.Label(dialog, text=f"Stock Actual: {prod['stock']} unidades", font=FUENTES['pequena'],
                fg=COLORES['texto_secundario']).pack(padx=15, pady=(0, 15))

        tk.Label(dialog, text="Cantidad a Agregar:", font=FUENTES['normal']).pack(anchor='w', padx=15)
        entry_cantidad = tk.Spinbox(dialog, from_=1, to=10000, font=FUENTES['input'], width=15,
                                   relief='solid', bd=1)
        entry_cantidad.delete(0, 'end')
        entry_cantidad.insert(0, '1')
        entry_cantidad.pack(fill='x', padx=15, pady=(5, 15), ipady=6)

        tk.Label(dialog, text="Razón/Motivo:", font=FUENTES['normal']).pack(anchor='w', padx=15)
        entry_motivo = tk.Entry(dialog, font=FUENTES['input'], relief='solid', bd=1)
        entry_motivo.pack(fill='x', padx=15, pady=5, ipady=6)
        entry_motivo.insert(0, "Compra a proveedor")

        def guardar():
            try:
                cantidad = int(entry_cantidad.get())
                motivo = entry_motivo.get().strip()

                if cantidad < 1:
                    messagebox.showerror("Error", "Cantidad debe ser mayor a 0")
                    return

                nuevo_stock = prod['stock'] + cantidad
                registrar_movimiento_stock(
                    self.producto_seleccionado, 'ENTRADA', cantidad,
                    prod['stock'], nuevo_stock, motivo, self.usuario['usuario']
                )
                messagebox.showinfo("Exito", f"Se agregaron {cantidad} unidades")
                dialog.destroy()
                self._cargar_productos()

            except ValueError:
                messagebox.showerror("Error", "Ingrese una cantidad válida", parent=dialog)
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo agregar stock: {e}", parent=dialog)

        btn_frame = tk.Frame(dialog)
        btn_frame.pack(fill='x', padx=15, pady=15)
        crear_boton(btn_frame, "Guardar", guardar, tipo='exito').pack(side='left', padx=2)
        crear_boton(btn_frame, "Cancelar", dialog.destroy, tipo='secundario').pack(side='right', padx=2)

    def _reducir_stock(self):
        """Reduce stock de un producto"""
        if self.producto_seleccionado is None:
            messagebox.showwarning("Seleccione un Producto", "Por favor seleccione un producto")
            return

        prod = next((p for p in self.productos if p['id'] == self.producto_seleccionado), None)
        if not prod:
            return

        dialog = tk.Toplevel(self.parent.winfo_toplevel())
        dialog.title("Reducir Stock")
        dialog.geometry("400x280")
        dialog.resizable(True, True)
        dialog.grab_set()

        tk.Label(dialog, text=f"Producto: {prod['nombre']}", font=FUENTES['normal_bold'],
                fg=COLORES['texto']).pack(padx=15, pady=(15, 5))
        tk.Label(dialog, text=f"Stock Actual: {prod['stock']} unidades", font=FUENTES['pequena'],
                fg=COLORES['texto_secundario']).pack(padx=15, pady=(0, 15))

        tk.Label(dialog, text="Cantidad a Reducir:", font=FUENTES['normal']).pack(anchor='w', padx=15)
        entry_cantidad = tk.Spinbox(dialog, from_=1, to=10000, font=FUENTES['input'], width=15,
                                   relief='solid', bd=1)
        entry_cantidad.delete(0, 'end')
        entry_cantidad.insert(0, '1')
        entry_cantidad.pack(fill='x', padx=15, pady=(5, 15), ipady=6)

        tk.Label(dialog, text="Razón/Motivo:", font=FUENTES['normal']).pack(anchor='w', padx=15)
        entry_motivo = tk.Entry(dialog, font=FUENTES['input'], relief='solid', bd=1)
        entry_motivo.pack(fill='x', padx=15, pady=5, ipady=6)
        entry_motivo.insert(0, "Ajuste de inventario")

        def guardar():
            try:
                cantidad = int(entry_cantidad.get())
                motivo = entry_motivo.get().strip()

                if cantidad < 1:
                    messagebox.showerror("Error", "Cantidad debe ser mayor a 0")
                    return

                if cantidad > prod['stock']:
                    messagebox.showerror("Error", f"Stock insuficiente (disponible: {prod['stock']})")
                    return

                nuevo_stock = prod['stock'] - cantidad
                registrar_movimiento_stock(
                    self.producto_seleccionado, 'SALIDA', cantidad,
                    prod['stock'], nuevo_stock, motivo, self.usuario['usuario']
                )
                messagebox.showinfo("Exito", f"Se redujeron {cantidad} unidades")
                dialog.destroy()
                self._cargar_productos()

            except ValueError:
                messagebox.showerror("Error", "Ingrese una cantidad válida", parent=dialog)
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo reducir stock: {e}", parent=dialog)

        btn_frame = tk.Frame(dialog)
        btn_frame.pack(fill='x', padx=15, pady=15)
        crear_boton(btn_frame, "Guardar", guardar, tipo='error').pack(side='left', padx=2)
        crear_boton(btn_frame, "Cancelar", dialog.destroy, tipo='secundario').pack(side='right', padx=2)

    def _carga_masiva(self):
        """Carga masiva de productos desde Excel o CSV"""
        file_path = filedialog.askopenfilename(
            title="Seleccionar archivo de importación",
            filetypes=[("Excel files", "*.xlsx"), ("CSV files", "*.csv"), ("Todos", "*.*")]
        )

        if not file_path:
            return

        try:
            productos_importar = []

            if file_path.lower().endswith('.xlsx'):
                if not HAS_OPENPYXL:
                    messagebox.showerror("Error", "openpyxl no está instalado. Por favor instale con: pip install openpyxl")
                    return
                productos_importar = self._leer_excel(file_path)
            elif file_path.lower().endswith('.csv'):
                productos_importar = self._leer_csv(file_path)
            else:
                messagebox.showerror("Error", "Formato no soportado. Use .xlsx o .csv")
                return

            if not productos_importar:
                messagebox.showwarning("Advertencia", "No se encontraron registros para importar")
                return

            # Diálogo de confirmación
            dialog = tk.Toplevel(self.parent)
            dialog.title("Confirmar Carga Masiva")
            dialog.geometry("500x400")
            dialog.resizable(True, True)

            tk.Label(dialog, text="Productos a Importar:", font=FUENTES['titulo']).pack(padx=15, pady=10)

            frame_scroll = tk.Frame(dialog)
            frame_scroll.pack(fill='both', expand=True, padx=15, pady=10)

            scrollbar = ttk.Scrollbar(frame_scroll)
            scrollbar.pack(side='right', fill='y')

            listbox = tk.Listbox(frame_scroll, yscrollcommand=scrollbar.set, font=FUENTES['pequena'])
            scrollbar.config(command=listbox.yview)
            listbox.pack(fill='both', expand=True)

            for prod in productos_importar:
                info = f"{prod['nombre']} (Código: {prod['codigo_barras']}) - Stock: {prod['stock_actual']}"
                listbox.insert('end', info)

            tk.Label(dialog, text=f"Total: {len(productos_importar)} productos",
                    font=FUENTES['normal']).pack(padx=15, pady=5)

            def procesar_carga():
                try:
                    res = carga_masiva_productos(
                        productos_importar, self.usuario['usuario']
                    )
                    mensaje = (f"Carga completada:\n"
                               f"- Insertados: {res['insertados']}\n"
                               f"- Actualizados: {res['actualizados']}")
                    if res['errores']:
                        mensaje += (f"\n- Errores: {len(res['errores'])}\n\n"
                                    + "\n".join(res['errores'][:5]))
                    messagebox.showinfo("Exito", mensaje)
                    dialog.destroy()
                    self._cargar_productos()
                except Exception as e:
                    messagebox.showerror("Error", f"Error al procesar carga: {str(e)}")

            btn_frame = tk.Frame(dialog)
            btn_frame.pack(fill='x', padx=15, pady=15)
            crear_boton(btn_frame, "Importar", procesar_carga, tipo='exito').pack(side='left', padx=2)
            crear_boton(btn_frame, "Cancelar", dialog.destroy, tipo='secundario').pack(side='right', padx=2)

        except Exception as e:
            messagebox.showerror("Error", f"Error al leer archivo: {str(e)}")

    @staticmethod
    def _norm_col(texto):
        """Normaliza un nombre de columna: minúsculas, sin acentos, espacios→guion bajo."""
        import unicodedata
        txt = str(texto).lower().strip()
        txt = unicodedata.normalize('NFKD', txt)
        txt = ''.join(c for c in txt if not unicodedata.combining(c))
        txt = txt.replace(' ', '_').replace('-', '_')
        return txt

    # Alias: variantes comunes → nombre interno esperado
    _COL_ALIAS = {
        # Barcode
        'cod_barras': 'codigo_barras', 'codigo': 'codigo_barras',
        'cod': 'codigo_barras', 'barcode': 'codigo_barras',
        'ean': 'codigo_barras', 'referencia': 'codigo_barras',
        # Precio
        'precio': 'precio_venta', 'price': 'precio_venta',
        'valor': 'precio_venta', 'pvp': 'precio_venta',
        'precio_de_venta': 'precio_venta',
        # Stock actual
        'stock': 'stock_actual', 'cantidad': 'stock_actual',
        'existencia': 'stock_actual', 'existencias': 'stock_actual',
        'ctrl_stock': 'controla_stock',
        # Stock mínimo
        'stock_min': 'stock_minimo', 'minimo': 'stock_minimo',
        'min': 'stock_minimo', 'stock_minimo': 'stock_minimo',
        # Categoría
        'cat': 'categoria', 'category': 'categoria',
        'categoria': 'categoria',
        # Nombre
        'name': 'nombre', 'producto': 'nombre', 'descripcion': 'nombre',
        'nombre': 'nombre',
    }

    @staticmethod
    def _limpiar_num(val):
        """Convierte un valor de celda Excel a número float, manejando formatos como $6.000"""
        if val is None:
            return 0
        if isinstance(val, (int, float)):
            return float(val)
        s = str(val).strip().replace('$', '').replace(',', '').replace('.', '')
        # Si quedó vacío o guiones
        if not s or s in ('---', '-', ''):
            return 0
        try:
            return float(s)
        except Exception:
            return 0

    def _leer_excel(self, filepath):
        """Lee productos desde archivo Excel.
        Detecta la fila de cabeceras automáticamente (soporta fila de título decorativa
        en la fila 1, como el formato del botón Exportar Excel de este mismo sistema).
        Acepta columnas sin código de barras y salta filas de separadores de categoría.
        """
        productos = []
        try:
            wb = openpyxl.load_workbook(filepath, data_only=True)
            ws = wb.active

            # ── 1. Buscar la fila de cabeceras (filas 1–5) ──────────────────
            header_row = None
            headers = {}
            requeridas_minimas = {'nombre', 'precio_venta', 'stock_actual'}
            for ri in range(1, 6):
                candidato = {}
                for ci in range(1, ws.max_column + 1):
                    v = ws.cell(ri, ci).value
                    if v:
                        norm = self._norm_col(v)
                        norm = self._COL_ALIAS.get(norm, norm)
                        candidato[norm] = ci
                if requeridas_minimas.issubset(candidato.keys()):
                    header_row = ri
                    headers = candidato
                    break

            if header_row is None:
                # Mostrar qué hay en las primeras filas para diagnóstico
                muestras = []
                for ri in range(1, 4):
                    fila = [str(ws.cell(ri, ci).value or '') for ci in range(1, 6)]
                    muestras.append(' | '.join(fila))
                raise ValueError(
                    f"No se encontraron las cabeceras en las primeras 5 filas.\n\n"
                    f"El sistema espera columnas: Producto (o Nombre), "
                    f"Precio Venta, Stock Actual, Stock Minimo.\n\n"
                    f"Primeras filas del archivo:\n" + '\n'.join(muestras)
                )

            # ── 2. Leer filas de datos ───────────────────────────────────────
            col_nombre   = headers.get('nombre')
            col_codigo   = headers.get('codigo_barras')
            col_cat      = headers.get('categoria')
            col_precio   = headers.get('precio_venta')
            col_stock    = headers.get('stock_actual')
            col_minimo   = headers.get('stock_minimo')

            for ri in range(header_row + 1, ws.max_row + 1):
                try:
                    nombre  = ws.cell(ri, col_nombre).value if col_nombre else None
                    precio  = ws.cell(ri, col_precio).value if col_precio else None
                    stock   = ws.cell(ri, col_stock).value  if col_stock  else None
                    minimo  = ws.cell(ri, col_minimo).value if col_minimo else None
                    cat     = ws.cell(ri, col_cat).value    if col_cat    else None
                    codigo  = ws.cell(ri, col_codigo).value if col_codigo else None

                    if not nombre:
                        continue

                    nombre_str = str(nombre).strip()
                    if not nombre_str:
                        continue

                    # Saltar filas de separador de categoría:
                    # precio y stock ambos vacíos → es un encabezado de grupo
                    if precio is None and stock is None:
                        continue

                    # Normalizar código de barras
                    codigo_str = None
                    if codigo and str(codigo).strip() not in ('', '---', '-'):
                        c = str(codigo).strip()
                        # Si es número con decimales (.0) limpiarlo
                        if c.replace('.', '').replace(',', '').isdigit():
                            try:
                                codigo_str = str(int(float(c)))
                            except Exception:
                                codigo_str = c
                        else:
                            codigo_str = c

                    productos.append({
                        'nombre':        nombre_str,
                        'codigo_barras': codigo_str,
                        'categoria':     str(cat).strip() if cat else 'Sin Categoria',
                        'precio_venta':  self._limpiar_num(precio),
                        'stock_actual':  int(self._limpiar_num(stock)),
                        'stock_minimo':  int(self._limpiar_num(minimo)),
                    })
                except Exception:
                    continue

            wb.close()
        except Exception as e:
            raise Exception(f"Error leyendo Excel: {str(e)}")

        return productos

    def _leer_csv(self, filepath):
        """Lee productos desde archivo CSV"""
        productos = []
        try:
            for enc in ('utf-8', 'latin-1', 'cp1252'):
                try:
                    with open(filepath, 'r', encoding=enc) as f:
                        f.read(1024)
                    break
                except UnicodeDecodeError:
                    enc = 'latin-1'
            with open(filepath, 'r', encoding=enc) as f:
                reader = csv.DictReader(f)

                if not reader.fieldnames:
                    raise ValueError("Archivo CSV vacío")

                # Normalizar y aplicar alias
                col_map = {}
                for fn in reader.fieldnames:
                    norm = self._norm_col(fn)
                    norm = self._COL_ALIAS.get(norm, norm)
                    col_map[fn] = norm

                requeridas = {'nombre', 'codigo_barras', 'categoria', 'precio_venta', 'stock_actual', 'stock_minimo'}
                presentes = set(col_map.values())
                faltantes = requeridas - presentes
                if faltantes:
                    raise ValueError(
                        f"Columnas faltantes: {', '.join(sorted(faltantes))}\n\n"
                        f"Tu archivo tiene: {', '.join(reader.fieldnames)}\n\n"
                        f"El sistema espera: nombre, codigo_barras, categoria, "
                        f"precio_venta, stock_actual, stock_minimo"
                    )

                for row in reader:
                    try:
                        nombre = None
                        codigo = None
                        categoria = None
                        precio = None
                        stock = None
                        minimo = None

                        for key, value in row.items():
                            key_norm = col_map.get(key, self._norm_col(key))
                            if key_norm == 'nombre':
                                nombre = value
                            elif key_norm == 'codigo_barras':
                                codigo = value
                            elif key_norm == 'categoria':
                                categoria = value
                            elif key_norm == 'precio_venta':
                                precio = value
                            elif key_norm == 'stock_actual':
                                stock = value
                            elif key_norm == 'stock_minimo':
                                minimo = value

                        if not nombre or not codigo:
                            continue

                        productos.append({
                            'nombre': str(nombre).strip(),
                            'codigo_barras': str(codigo).strip(),
                            'categoria': str(categoria).strip() if categoria else 'Sin Categoría',
                            'precio_venta': float(precio) if precio else 0,
                            'stock_actual': int(float(stock)) if stock else 0,
                            'stock_minimo': int(float(minimo)) if minimo else 0
                        })
                    except Exception as e:
                        continue
        except Exception as e:
            raise Exception(f"Error leyendo CSV: {str(e)}")

        return productos

    def _exportar_xlsx(self):
        """Exporta inventario completo a Excel organizado por categoría"""
        if not HAS_OPENPYXL:
            messagebox.showerror("Error",
                "openpyxl no esta instalado.\n"
                "Ejecuta: pip install openpyxl --break-system-packages")
            return

        try:
            # Leer datos frescos de la BD
            with conexion_segura() as conn:
                rows = conn.execute("""
                    SELECT p.codigo_barras, p.nombre, c.nombre as categoria,
                           p.precio_venta, p.precio_costo, p.stock_actual,
                           p.stock_minimo, p.requiere_cocina, p.activo,
                           p.controla_stock, p.unidad_medida
                    FROM productos p
                    LEFT JOIN categorias c ON p.id_categoria = c.id_categoria
                    WHERE p.activo = 1
                    ORDER BY c.nombre, p.nombre
                """).fetchall()

            if not rows:
                messagebox.showwarning("Advertencia", "No hay productos para exportar")
                return

            file_path = filedialog.asksaveasfilename(
                defaultextension=".xlsx",
                filetypes=[("Excel", "*.xlsx"), ("Todos", "*.*")],
                initialfile=f"inventario_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            )
            if not file_path:
                return

            import openpyxl
            from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
            from openpyxl.utils import get_column_letter

            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Inventario"

            # Estilos
            verde_oscuro = "0D4020"
            verde_claro  = "E8F5E9"
            gris_fila    = "F5F5F5"
            naranja      = "FF8F00"
            rojo         = "C62828"

            hdr_font   = Font(bold=True, color="FFFFFF", size=11)
            cat_font   = Font(bold=True, color="FFFFFF", size=11)
            normal_font = Font(size=10)
            thin_border = Border(
                bottom=Side(style='thin', color="CCCCCC"),
                right=Side(style='thin', color="CCCCCC")
            )

            # Título principal
            ws.merge_cells("A1:K1")
            ws["A1"] = f"INVENTARIO CLUB LOS POCITOS AZUFRADOS — {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}"
            ws["A1"].font = Font(bold=True, color="FFFFFF", size=13)
            ws["A1"].fill = PatternFill("solid", fgColor=verde_oscuro)
            ws["A1"].alignment = Alignment(horizontal="center", vertical="center")
            ws.row_dimensions[1].height = 28

            # Cabeceras
            cabeceras = ["Código", "Producto", "Categoría", "Precio Venta",
                         "Precio Costo", "Stock Actual", "Stock Mínimo",
                         "Unidad", "Cocina", "Ctrl Stock", "Estado Stock"]
            ws.append(cabeceras)
            for col_idx, _ in enumerate(cabeceras, start=1):
                cell = ws.cell(row=2, column=col_idx)
                cell.font = hdr_font
                cell.fill = PatternFill("solid", fgColor="1B6E3A")
                cell.alignment = Alignment(horizontal="center")
                cell.border = thin_border
            ws.row_dimensions[2].height = 20

            # Agrupar por categoría
            from itertools import groupby
            rows_sorted = sorted([dict(r) for r in rows], key=lambda x: x['categoria'] or 'Sin Categoria')

            row_num = 3
            cat_actual = None
            for prod in rows_sorted:
                cat = prod['categoria'] or 'Sin Categoria'

                # Fila de categoría
                if cat != cat_actual:
                    cat_actual = cat
                    ws.merge_cells(f"A{row_num}:K{row_num}")
                    ws.cell(row=row_num, column=1).value = f"  {cat.upper()}"
                    ws.cell(row=row_num, column=1).font = cat_font
                    ws.cell(row=row_num, column=1).fill = PatternFill("solid", fgColor="2EA54E")
                    ws.cell(row=row_num, column=1).alignment = Alignment(vertical="center")
                    ws.row_dimensions[row_num].height = 18
                    row_num += 1

                # Fila de producto
                stock = prod['stock_actual'] or 0
                minimo = prod['stock_minimo'] or 0
                if stock == 0:
                    estado = "SIN STOCK"
                    color_est = rojo
                elif stock <= minimo:
                    estado = "BAJO"
                    color_est = naranja
                else:
                    estado = "OK"
                    color_est = "1B6E3A"

                fila = [
                    prod['codigo_barras'] or '',
                    prod['nombre'],
                    cat,
                    prod['precio_venta'] or 0,
                    prod['precio_costo'] or 0,
                    stock,
                    minimo,
                    prod['unidad_medida'] or 'unidad',
                    'Si' if prod['requiere_cocina'] else 'No',
                    'Si' if prod['controla_stock'] else 'No',
                    estado,
                ]
                ws.append(fila)

                # Alternar fondo
                fill_color = gris_fila if row_num % 2 == 0 else "FFFFFF"
                for col_idx in range(1, 12):
                    cell = ws.cell(row=row_num, column=col_idx)
                    cell.font = normal_font
                    cell.border = thin_border
                    if col_idx not in (11,):
                        cell.fill = PatternFill("solid", fgColor=fill_color)
                    # Colorear estado
                    if col_idx == 11:
                        cell.font = Font(bold=True, color=color_est, size=10)
                    # Formato moneda
                    if col_idx in (4, 5):
                        cell.number_format = '"$"#,##0'
                    # Centrar
                    if col_idx in (1, 7, 8, 9, 10, 11):
                        cell.alignment = Alignment(horizontal="center")

                row_num += 1

            # Anchos de columna
            anchos = [14, 30, 18, 14, 14, 13, 13, 10, 8, 10, 12]
            for i, ancho in enumerate(anchos, start=1):
                ws.column_dimensions[get_column_letter(i)].width = ancho

            # Hoja resumen
            ws2 = wb.create_sheet("Resumen")
            ws2["A1"] = "Resumen por Categoría"
            ws2["A1"].font = Font(bold=True, size=12)
            ws2.append(["Categoría", "Productos", "Sin Stock", "Bajo Stock", "Valor Inventario"])
            for col_idx in range(1, 6):
                cell = ws2.cell(row=2, column=col_idx)
                cell.font = hdr_font
                cell.fill = PatternFill("solid", fgColor="1B6E3A")
                cell.alignment = Alignment(horizontal="center")

            cat_stats = {}
            for prod in rows_sorted:
                cat = prod['categoria'] or 'Sin Categoria'
                if cat not in cat_stats:
                    cat_stats[cat] = {'n': 0, 'sin': 0, 'bajo': 0, 'valor': 0}
                cat_stats[cat]['n'] += 1
                stk = prod['stock_actual'] or 0
                mn  = prod['stock_minimo'] or 0
                if stk == 0:
                    cat_stats[cat]['sin'] += 1
                elif stk <= mn:
                    cat_stats[cat]['bajo'] += 1
                cat_stats[cat]['valor'] += stk * (prod['precio_venta'] or 0)

            for cat, s in sorted(cat_stats.items()):
                ws2.append([cat, s['n'], s['sin'], s['bajo'], s['valor']])

            ws2.column_dimensions['A'].width = 22
            for col in 'BCDE':
                ws2.column_dimensions[col].width = 14

            wb.save(file_path)
            messagebox.showinfo("Exito", f"Excel exportado:\n{file_path}")

        except Exception as e:
            messagebox.showerror("Error al exportar", str(e))

    def _actualizar_contador_pendientes(self):
        """Actualiza el texto del botón de aprobación con el número de pendientes."""
        if self.btn_aprobar is None:
            return
        try:
            with conexion_segura() as conn:
                n = conn.execute(
                    "SELECT COUNT(*) FROM productos WHERE pendiente_aprobacion = 1 AND activo = 1"
                ).fetchone()[0]
            label = f" Aprobar Pendientes ({n})"
            self.btn_aprobar.config(text=label)
        except Exception:
            pass

    def _aprobar_productos_pendientes(self):
        """Muestra la lista de productos creados por cajeros pendientes de aprobación."""
        try:
            with conexion_segura() as conn:
                pendientes = conn.execute("""
                    SELECT p.id_producto, p.nombre, p.precio_venta, p.stock_actual,
                           c.nombre as categoria, p.fecha_creacion
                    FROM productos p
                    LEFT JOIN categorias c ON p.id_categoria = c.id_categoria
                    WHERE p.pendiente_aprobacion = 1 AND p.activo = 1
                    ORDER BY p.fecha_creacion DESC
                """).fetchall()
        except Exception as e:
            messagebox.showerror("Error", f"No se pudieron cargar pendientes: {e}")
            return

        if not pendientes:
            messagebox.showinfo("Sin pendientes",
                                "No hay productos pendientes de aprobacion.")
            return

        dialog = tk.Toplevel(self.parent.winfo_toplevel())
        dialog.title(f"Productos Pendientes de Aprobacion ({len(pendientes)})")
        dialog.configure(bg=COLORES['fondo_card'])
        dialog.grab_set()

        w, h = 700, 450
        dialog.geometry(f"{w}x{h}+"
                        f"{(dialog.winfo_screenwidth()-w)//2}+"
                        f"{(dialog.winfo_screenheight()-h)//2}")

        tk.Frame(dialog, bg=COLORES['primario'], height=4).pack(fill='x')
        tk.Label(dialog, text="Productos creados por cajeros — requieren aprobacion",
                 font=FUENTES['subtitulo'], fg=COLORES['texto'],
                 bg=COLORES['fondo_card']).pack(pady=(12, 6), padx=15, anchor='w')

        frame_tabla = tk.Frame(dialog, bg=COLORES['fondo_card'])
        frame_tabla.pack(fill='both', expand=True, padx=15, pady=(0, 8))

        tree = ttk.Treeview(frame_tabla,
                            columns=('nombre', 'cat', 'precio', 'stock', 'fecha'),
                            show='headings', height=10)
        tree.column('nombre',  width=200, anchor='w')
        tree.column('cat',     width=130, anchor='w')
        tree.column('precio',  width=110, anchor='e')
        tree.column('stock',   width=80,  anchor='center')
        tree.column('fecha',   width=120, anchor='center')
        tree.heading('nombre', text='Nombre')
        tree.heading('cat',    text='Categoria')
        tree.heading('precio', text='Precio')
        tree.heading('stock',  text='Stock')
        tree.heading('fecha',  text='Creado')
        aplicar_estilo_tabla(tree)

        ids_productos = []
        for i, p in enumerate(pendientes):
            tag = 'par' if i % 2 == 0 else 'impar'
            fecha_fmt = p['fecha_creacion'][:10] if p['fecha_creacion'] else ''
            tree.insert('', 'end', iid=str(p['id_producto']), values=(
                p['nombre'], p['categoria'] or '-',
                format_money(p['precio_venta']), p['stock_actual'], fecha_fmt
            ), tags=(tag,))
            ids_productos.append(p['id_producto'])

        tree.pack(fill='both', expand=True)

        def _aprobar_sel():
            sel = tree.selection()
            if not sel:
                messagebox.showwarning("Seleccione", "Seleccione un producto.", parent=dialog)
                return
            id_prod = int(sel[0])
            nombre_prod = tree.item(sel[0])['values'][0]
            if not messagebox.askyesno("Aprobar",
                                       f"Aprobar '{nombre_prod}'?\n\n"
                                       "Quedara activo y visible normalmente.", parent=dialog):
                return
            try:
                aprobar_producto(id_prod, nombre_prod, self.usuario['usuario'])
                tree.delete(sel[0])
                self._actualizar_contador_pendientes()
                messagebox.showinfo("Aprobado", f"'{nombre_prod}' aprobado.", parent=dialog)
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=dialog)

        def _rechazar_sel():
            sel = tree.selection()
            if not sel:
                messagebox.showwarning("Seleccione", "Seleccione un producto.", parent=dialog)
                return
            id_prod = int(sel[0])
            nombre_prod = tree.item(sel[0])['values'][0]
            if not messagebox.askyesno("Rechazar",
                                       f"Rechazar y eliminar '{nombre_prod}'?", parent=dialog):
                return
            try:
                rechazar_producto(id_prod, nombre_prod, self.usuario['usuario'])
                tree.delete(sel[0])
                self._actualizar_contador_pendientes()
                messagebox.showinfo("Rechazado", f"'{nombre_prod}' eliminado.", parent=dialog)
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=dialog)

        btn_f = tk.Frame(dialog, bg=COLORES['fondo_card'])
        btn_f.pack(pady=10)
        crear_boton(btn_f, "Aprobar Seleccionado",  _aprobar_sel,  tipo='exito').pack(side='left', padx=5)
        crear_boton(btn_f, "Rechazar Seleccionado", _rechazar_sel, tipo='error').pack(side='left', padx=5)
        crear_boton(btn_f, "Cerrar", dialog.destroy, tipo='outline').pack(side='left', padx=5)

        dialog.wait_window()
        self._cargar_productos()

    def detener(self):
        try:
            self.tree_productos.unbind_all('<MouseWheel>')
            self.tree_productos.unbind_all('<Button-4>')
            self.tree_productos.unbind_all('<Button-5>')
        except Exception:
            pass
