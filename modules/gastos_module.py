"""
Módulo de Gastos - Club Los Pocitos Azufrados
Registro y control de gastos operacionales
"""

import logging
import tkinter as tk
from tkinter import ttk, messagebox
import os, sys, datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from utils.tema_corporativo import COLORES, FUENTES, crear_boton, crear_tarjeta_kpi, format_money, aplicar_estilo_tabla
from database.connection import get_connection, conexion_segura
from utils.logger import log_auditoria


_CATEGORIAS_DEFAULT = ['Compras Insumos', 'Compras Licor', 'Compras Alimentos',
                       'Servicios Públicos', 'Nómina', 'Transporte', 'Mantenimiento', 'Otros']
_METODOS_DEFAULT    = ['EFECTIVO', 'NEQUI', 'DAVIPLATA', 'BANCOLOMBIA', 'TRANSFERENCIA']


def _leer_config_gastos():
    """Lee categorías de gastos y métodos de pago desde la tabla configuracion."""
    categorias = _CATEGORIAS_DEFAULT[:]
    metodos    = _METODOS_DEFAULT[:]
    try:
        with conexion_segura() as conn:
            row_cat = conn.execute(
                "SELECT valor FROM configuracion WHERE clave = 'categorias_gastos'"
            ).fetchone()
            if row_cat and row_cat['valor']:
                categorias = row_cat['valor'].split(',')

            row_met = conn.execute(
                "SELECT valor FROM configuracion WHERE clave = 'metodos_pago_habilitados'"
            ).fetchone()
            if row_met and row_met['valor']:
                metodos = row_met['valor'].split(',')
    except Exception as e:
        logging.getLogger("pocitos").warning(f"No se pudo leer config de gastos: {e}")
    return categorias, metodos


class GastosModule:
    def __init__(self, parent, usuario):
        self.parent = parent
        self.usuario = usuario
        self.gastos = []
        self.gasto_seleccionado = None

        self.CATEGORIAS, self._metodos_pago = _leer_config_gastos()

        self._crear_interfaz()
        self._cargar_gastos()

    def _crear_interfaz(self):
        """Interfaz principal de gastos"""
        # Header
        header = tk.Frame(self.parent, bg=COLORES['primario'])
        header.pack(fill='x')

        inner_header = tk.Frame(header, bg=COLORES['primario'], padx=15, pady=10)
        inner_header.pack(fill='x')

        tk.Label(inner_header, text="Registro de Gastos",
                 font=FUENTES['encabezado'], fg=COLORES['texto_claro'],
                 bg=COLORES['primario']).pack(side='left')

        # ========== SECCIÓN DE KPIs ==========
        kpis_frame = tk.Frame(self.parent, bg=COLORES['fondo'])
        kpis_frame.pack(fill='x', padx=15, pady=15)

        # KPI Cards
        self.kpi_hoy, self.lbl_kpi_hoy = crear_tarjeta_kpi(
            kpis_frame, "Gastos Hoy", "$ 0", "", COLORES['error']
        )
        self.kpi_hoy.pack(side='left', fill='both', expand=True, padx=(0, 8))

        self.kpi_semana, self.lbl_kpi_semana = crear_tarjeta_kpi(
            kpis_frame, "Gastos Esta Semana", "$ 0", "", COLORES['primario']
        )
        self.kpi_semana.pack(side='left', fill='both', expand=True, padx=(0, 8))

        self.kpi_mes, self.lbl_kpi_mes = crear_tarjeta_kpi(
            kpis_frame, "Gastos Este Mes", "$ 0", "", COLORES['exito']
        )
        self.kpi_mes.pack(side='left', fill='both', expand=True)

        # ========== CUERPO PRINCIPAL ==========
        body = tk.Frame(self.parent, bg=COLORES['fondo'])
        body.pack(fill='both', expand=True, padx=15, pady=5)

        # ========== IZQUIERDA: Formulario ==========
        left = tk.Frame(body, bg=COLORES['fondo_card'],
                       highlightbackground=COLORES['borde'], highlightthickness=1)
        left.pack(side='left', fill='y', padx=(0, 8), ipady=15)
        left.pack_propagate(False)
        left.config(width=320)

        # Canvas scrollable para el formulario (pantallas pequeñas)
        self._form_canvas = tk.Canvas(left, bg=COLORES['fondo_card'], highlightthickness=0)
        _fsb = ttk.Scrollbar(left, orient='vertical', command=self._form_canvas.yview)
        _finner = tk.Frame(self._form_canvas, bg=COLORES['fondo_card'])
        _fwin = self._form_canvas.create_window((0, 0), window=_finner, anchor='nw')
        _finner.bind('<Configure>', lambda e: self._form_canvas.configure(scrollregion=self._form_canvas.bbox('all')))
        self._form_canvas.bind('<Configure>', lambda e: self._form_canvas.itemconfig(_fwin, width=e.width))
        self._form_canvas.configure(yscrollcommand=_fsb.set)
        _fsb.pack(side='right', fill='y')
        self._form_canvas.pack(fill='both', expand=True)

        def _scroll_form(event):
            d = int(-1 * (event.delta / 120)) if event.delta else (1 if event.num == 5 else -1)
            self._form_canvas.yview_scroll(d, 'units')
        self._form_canvas.bind_all('<MouseWheel>', _scroll_form)
        self._form_canvas.bind_all('<Button-4>', _scroll_form)
        self._form_canvas.bind_all('<Button-5>', _scroll_form)

        # Header coloreado del formulario
        form_header = tk.Frame(_finner, bg=COLORES['primario'])
        form_header.pack(fill='x', pady=(0, 15))

        tk.Label(form_header, text="Nuevo Gasto", font=FUENTES['encabezado'],
                 fg=COLORES['texto_claro'], bg=COLORES['primario']).pack(padx=15, pady=10, anchor='w')

        # Descripción
        frame_desc = tk.Frame(_finner, bg=COLORES['fondo_card'])
        frame_desc.pack(fill='x', padx=15, pady=8)
        tk.Label(frame_desc, text="Descripción", font=FUENTES['pequena'],
                 fg=COLORES['texto_secundario'], bg=COLORES['fondo_card']).pack(anchor='w')
        self.entry_desc = tk.Entry(frame_desc, font=FUENTES['input'],
                                   relief='solid', bd=1, highlightthickness=1,
                                   highlightbackground=COLORES['borde'])
        self.entry_desc.pack(fill='x', ipady=6)

        # Monto
        frame_monto = tk.Frame(_finner, bg=COLORES['fondo_card'])
        frame_monto.pack(fill='x', padx=15, pady=8)
        tk.Label(frame_monto, text="Monto", font=FUENTES['pequena'],
                 fg=COLORES['texto_secundario'], bg=COLORES['fondo_card']).pack(anchor='w')
        self.entry_monto = tk.Entry(frame_monto, font=FUENTES['input'],
                                    relief='solid', bd=1, highlightthickness=1,
                                    highlightbackground=COLORES['borde'])
        self.entry_monto.pack(fill='x', ipady=6)

        # Categoría
        frame_cat = tk.Frame(_finner, bg=COLORES['fondo_card'])
        frame_cat.pack(fill='x', padx=15, pady=8)
        tk.Label(frame_cat, text="Categoría", font=FUENTES['pequena'],
                 fg=COLORES['texto_secundario'], bg=COLORES['fondo_card']).pack(anchor='w')
        self.combo_categoria = ttk.Combobox(frame_cat, values=self.CATEGORIAS, state='readonly', font=FUENTES['input'])
        self.combo_categoria.set('Otros')
        self.combo_categoria.pack(fill='x', ipady=6)

        # Método de pago
        frame_metodo = tk.Frame(_finner, bg=COLORES['fondo_card'])
        frame_metodo.pack(fill='x', padx=15, pady=8)
        tk.Label(frame_metodo, text="Método de Pago", font=FUENTES['pequena'],
                 fg=COLORES['texto_secundario'], bg=COLORES['fondo_card']).pack(anchor='w')
        self.combo_metodo = ttk.Combobox(frame_metodo, values=self._metodos_pago,
                                         state='readonly', font=FUENTES['input'])
        self.combo_metodo.set('EFECTIVO')
        self.combo_metodo.pack(fill='x', ipady=6)

        # Proveedor (opcional)
        frame_prov = tk.Frame(_finner, bg=COLORES['fondo_card'])
        frame_prov.pack(fill='x', padx=15, pady=8)
        tk.Label(frame_prov, text="Proveedor (Opcional)", font=FUENTES['pequena'],
                 fg=COLORES['texto_secundario'], bg=COLORES['fondo_card']).pack(anchor='w')
        self.entry_proveedor = tk.Entry(frame_prov, font=FUENTES['input'],
                                        relief='solid', bd=1, highlightthickness=1,
                                        highlightbackground=COLORES['borde'])
        self.entry_proveedor.pack(fill='x', ipady=6)

        # Factura (opcional)
        frame_fact = tk.Frame(_finner, bg=COLORES['fondo_card'])
        frame_fact.pack(fill='x', padx=15, pady=8)
        tk.Label(frame_fact, text="Nº Factura (Opcional)", font=FUENTES['pequena'],
                 fg=COLORES['texto_secundario'], bg=COLORES['fondo_card']).pack(anchor='w')
        self.entry_factura = tk.Entry(frame_fact, font=FUENTES['input'],
                                      relief='solid', bd=1, highlightthickness=1,
                                      highlightbackground=COLORES['borde'])
        self.entry_factura.pack(fill='x', ipady=6)

        # Botones
        btn_frame = tk.Frame(_finner, bg=COLORES['fondo_card'])
        btn_frame.pack(fill='x', padx=15, pady=(10, 15))

        crear_boton(btn_frame, "Guardar Gasto", self._guardar_gasto,
                   tipo='exito').pack(fill='x', pady=4)
        crear_boton(btn_frame, "Limpiar", self._limpiar_formulario,
                   tipo='secundario').pack(fill='x', pady=4)
        self.btn_eliminar = crear_boton(btn_frame, "Eliminar Gasto Seleccionado",
                                        self._eliminar_gasto, tipo='error')
        self.btn_eliminar.pack(fill='x')

        # ========== DERECHA: Tabla de gastos ==========
        right = tk.Frame(body, bg=COLORES['fondo'])
        right.pack(side='right', fill='both', expand=True)

        # Filtros
        filtro_frame = tk.Frame(right, bg=COLORES['fondo_card'],
                               highlightbackground=COLORES['borde'], highlightthickness=1)
        filtro_frame.pack(fill='x', padx=0, pady=(0, 8))

        filtro_inner = tk.Frame(filtro_frame, bg=COLORES['fondo_card'], padx=12, pady=10)
        filtro_inner.pack(fill='x')

        tk.Label(filtro_inner, text="Filtrar Categoría:", font=FUENTES['pequena'],
                 fg=COLORES['texto_secundario'], bg=COLORES['fondo_card']).pack(side='left', padx=5)

        self.combo_filtro = ttk.Combobox(filtro_inner, values=['Todas'] + self.CATEGORIAS, state='readonly', font=FUENTES['normal'], width=15)
        self.combo_filtro.set('Todas')
        self.combo_filtro.pack(side='left', padx=5)
        self.combo_filtro.bind('<<ComboboxSelected>>', lambda e: self._cargar_gastos())

        tk.Label(filtro_inner, text="", bg=COLORES['fondo_card']).pack(side='left', expand=True)

        tk.Label(filtro_inner, text="Total Hoy:", font=FUENTES['pequena'],
                 fg=COLORES['texto_secundario'], bg=COLORES['fondo_card']).pack(side='right', padx=(20, 5))
        self.lbl_total = tk.Label(filtro_inner, text="$ 0", font=FUENTES['encabezado'],
                                  fg=COLORES['error'], bg=COLORES['fondo_card'])
        self.lbl_total.pack(side='right', padx=5)

        tk.Label(right, text="Gastos Recientes", font=FUENTES['subtitulo'],
                 fg=COLORES['texto'], bg=COLORES['fondo']).pack(anchor='w', pady=(0, 8))

        tabla_frame = tk.Frame(right, bg=COLORES['fondo_card'],
                               highlightbackground=COLORES['borde'], highlightthickness=1)
        tabla_frame.pack(fill='both', expand=True)

        self.tree_gastos = ttk.Treeview(tabla_frame, height=15,
                                        columns=('descripcion', 'categoria', 'monto', 'metodo', 'proveedor', 'hora'),
                                        show='headings')

        self.tree_gastos.column('descripcion', width=180, anchor='w')
        self.tree_gastos.column('categoria', width=100, anchor='center')
        self.tree_gastos.column('monto', width=100, anchor='e')
        self.tree_gastos.column('metodo', width=100, anchor='center')
        self.tree_gastos.column('proveedor', width=120, anchor='w')
        self.tree_gastos.column('hora', width=100, anchor='center')

        self.tree_gastos.heading('descripcion', text='Descripción')
        self.tree_gastos.heading('categoria', text='Categoría')
        self.tree_gastos.heading('monto', text='Monto')
        self.tree_gastos.heading('metodo', text='Método Pago')
        self.tree_gastos.heading('proveedor', text='Proveedor')
        self.tree_gastos.heading('hora', text='Hora')

        aplicar_estilo_tabla(self.tree_gastos)
        tree_sb = ttk.Scrollbar(tabla_frame, orient='vertical', command=self.tree_gastos.yview)
        self.tree_gastos.configure(yscrollcommand=tree_sb.set)
        self.tree_gastos.pack(side='left', fill='both', expand=True)
        tree_sb.pack(side='right', fill='y')
        self.tree_gastos.bind('<Button-1>', self._on_gasto_click)

    def _cargar_gastos(self):
        """Carga gastos de hoy con filtro opcional"""
        try:
            with conexion_segura() as conn:
                hoy = datetime.date.today().isoformat()
                categoria_filtro = self.combo_filtro.get()

                # Cargar KPIs
                self._actualizar_kpis(conn, hoy)

                if categoria_filtro == 'Todas':
                    rows = conn.execute("""
                        SELECT * FROM gastos
                        WHERE DATE(fecha) = ?
                        ORDER BY fecha DESC
                    """, (hoy,)).fetchall()
                else:
                    rows = conn.execute("""
                        SELECT * FROM gastos
                        WHERE DATE(fecha) = ? AND categoria = ?
                        ORDER BY fecha DESC
                    """, (hoy, categoria_filtro)).fetchall()

                # Limpiar árbol
                for item in self.tree_gastos.get_children():
                    self.tree_gastos.delete(item)

                self.gastos = []
                total = 0

                for i, row in enumerate(rows):
                    tag = 'par' if i % 2 == 0 else 'impar'
                    self.tree_gastos.insert('', 'end', values=(
                        row['descripcion'],
                        row['categoria'],
                        format_money(row['valor']),
                        row['metodo_pago'],
                        row['proveedor'] or '---',
                        row['fecha'][11:16]
                    ), tags=(tag,), iid=row['id_gasto'])

                    self.gastos.append(row)
                    total += row['valor']

                self.lbl_total.config(text=format_money(total))

        except Exception as e:
            messagebox.showerror("Error", f"Error al cargar gastos: {str(e)}")

    def _actualizar_kpis(self, conn, hoy):
        """Actualiza los KPI cards con datos calculados"""
        import datetime as dt
        hoy_date = dt.datetime.strptime(hoy, '%Y-%m-%d').date()

        # Gastos hoy
        gasto_hoy = conn.execute("""
            SELECT SUM(valor) FROM gastos WHERE DATE(fecha) = ?
        """, (hoy,)).fetchone()[0] or 0
        self.lbl_kpi_hoy.config(text=format_money(gasto_hoy))

        # Gastos esta semana (últimos 7 días)
        hace_semana = (hoy_date - dt.timedelta(days=7)).isoformat()
        gasto_semana = conn.execute("""
            SELECT SUM(valor) FROM gastos WHERE DATE(fecha) >= ? AND DATE(fecha) <= ?
        """, (hace_semana, hoy)).fetchone()[0] or 0
        self.lbl_kpi_semana.config(text=format_money(gasto_semana))

        # Gastos este mes
        primer_dia = hoy_date.replace(day=1).isoformat()
        gasto_mes = conn.execute("""
            SELECT SUM(valor) FROM gastos WHERE DATE(fecha) >= ? AND DATE(fecha) <= ?
        """, (primer_dia, hoy)).fetchone()[0] or 0
        self.lbl_kpi_mes.config(text=format_money(gasto_mes))

    def _on_gasto_click(self, event):
        """Maneja clic en un gasto"""
        item = self.tree_gastos.selection()
        if item:
            self.gasto_seleccionado = int(item[0])

    def _guardar_gasto(self):
        """Guarda un nuevo gasto"""
        descripcion = self.entry_desc.get().strip()
        if not descripcion:
            messagebox.showwarning("Campo Requerido", "Por favor ingrese una descripción")
            return
        if len(descripcion) < 10:
            messagebox.showwarning("Descripción insuficiente",
                                   "La descripción debe tener al menos 10 caracteres.")
            return

        monto_str = self.entry_monto.get().strip()
        if not monto_str:
            messagebox.showwarning("Campo Requerido", "Por favor ingrese el monto")
            return

        try:
            monto = float(monto_str)
            if monto <= 0:
                raise ValueError()
        except ValueError:
            messagebox.showerror("Error", "Ingrese un monto válido")
            return

        categoria = self.combo_categoria.get()
        metodo = self.combo_metodo.get()
        proveedor = self.entry_proveedor.get().strip() or None
        factura = self.entry_factura.get().strip() or None

        try:
            with conexion_segura() as conn:
                conn.execute("""
                    INSERT INTO gastos (
                        fecha, descripcion, valor, categoria, metodo_pago, proveedor,
                        factura_proveedor, usuario_registro, tipo_gasto
                    ) VALUES (datetime('now','localtime'), ?, ?, ?, ?, ?, ?, ?, 'OPERATIVO')
                """, (descripcion, monto, categoria, metodo, proveedor, factura, self.usuario['usuario']))

                gasto_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

                log_auditoria(conn, 'gastos', gasto_id, 'INSERT',
                            self.usuario['usuario'], f"Gasto: {descripcion} - {format_money(monto)}")

            messagebox.showinfo("Exito", f"Gasto registrado: {format_money(monto)}")
            self._limpiar_formulario()
            self._cargar_gastos()

        except Exception as e:
            messagebox.showerror("Error", f"Error al guardar gasto: {str(e)}")

    def _limpiar_formulario(self):
        """Limpia el formulario"""
        self.entry_desc.delete(0, tk.END)
        self.entry_monto.delete(0, tk.END)
        self.combo_categoria.set('Otros')
        self.combo_metodo.set('EFECTIVO')
        self.entry_proveedor.delete(0, tk.END)
        self.entry_factura.delete(0, tk.END)
        self.entry_desc.focus()

    def _eliminar_gasto(self):
        """Elimina el gasto seleccionado previa confirmación."""
        if not self.gasto_seleccionado:
            messagebox.showwarning("Sin selección", "Selecciona un gasto de la tabla primero.")
            return

        # Buscar descripción y monto para mostrar en la confirmación
        gasto = next((g for g in self.gastos if g['id_gasto'] == self.gasto_seleccionado), None)
        if not gasto:
            messagebox.showwarning("Sin selección", "Selecciona un gasto de la tabla primero.")
            return

        confirmar = messagebox.askyesno(
            "Confirmar eliminación",
            f"¿Eliminar este gasto?\n\n"
            f"Descripción: {gasto['descripcion']}\n"
            f"Monto: {format_money(gasto['valor'])}\n"
            f"Categoría: {gasto['categoria']}\n\n"
            "Esta acción no se puede deshacer."
        )
        if not confirmar:
            return

        try:
            with conexion_segura() as conn:
                log_auditoria(conn, 'gastos', self.gasto_seleccionado, 'DELETE',
                              self.usuario['usuario'],
                              f"Eliminado: {gasto['descripcion']} - {format_money(gasto['valor'])}")
                conn.execute("DELETE FROM gastos WHERE id_gasto = ?", (self.gasto_seleccionado,))

            self.gasto_seleccionado = None
            self._cargar_gastos()
            messagebox.showinfo("Listo", "Gasto eliminado correctamente.")

        except Exception as e:
            messagebox.showerror("Error", f"No se pudo eliminar el gasto: {str(e)}")

    def detener(self):
        try:
            self._form_canvas.unbind_all('<MouseWheel>')
            self._form_canvas.unbind_all('<Button-4>')
            self._form_canvas.unbind_all('<Button-5>')
        except Exception:
            pass
      