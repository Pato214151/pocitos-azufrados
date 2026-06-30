import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os, sys, datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from utils.tema_corporativo import COLORES, FUENTES, crear_boton, crear_tarjeta_kpi, format_money, aplicar_estilo_tabla
from database.connection import get_connection, conexion_segura, transaccion_atomica
from utils.logger import log_auditoria
from utils.printing import imprimir_recibo_venta


class HistorialVentasModule:
    """Módulo de Historial de Ventas - Reemplaza Buscador de Ventas"""

    def __init__(self, parent, usuario):
        self.parent = parent
        self.usuario = usuario
        self.venta_seleccionada = None
        self.filtro_activo = "hoy"
        self._pagina = 0
        self._por_pagina = 50
        self._total_registros = 0
        self._kpi_last_filter = None  # (fecha_inicio, fecha_fin) del último cálculo de KPIs

        # Main container
        self.main_frame = ttk.Frame(parent)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Build UI
        self._crear_filtros()
        self._crear_resumen_kpi()
        self._crear_tabla_ventas()
        self._crear_panel_detalle()
        self._crear_botones_accion()
        self._crear_paginacion()

        # Load initial data
        self._actualizar_datos()

    def _crear_filtros(self):
        """Create filter section with quick buttons and date range pickers"""
        filtro_frame = ttk.LabelFrame(self.main_frame, text="Filtros", padding=10)
        filtro_frame.pack(fill=tk.X, pady=(0, 10))

        # Quick filter buttons
        botones_frame = ttk.Frame(filtro_frame)
        botones_frame.pack(fill=tk.X, pady=(0, 10))

        self.botones_filtro = {}
        filtros = [
            ("Hoy", "hoy"),
            ("Ayer", "ayer"),
            ("Esta Semana", "semana"),
            ("Este Mes", "mes")
        ]

        for texto, key in filtros:
            btn = tk.Button(
                botones_frame,
                text=texto,
                command=lambda k=key: self._cambiar_filtro(k),
                bg=COLORES['primario'] if key == "hoy" else COLORES['fondo_card'],
                fg='white' if key == "hoy" else COLORES['texto'],
                font=FUENTES['normal_bold'],
                relief=tk.RAISED,
                padx=15,
                pady=8
            )
            btn.pack(side=tk.LEFT, padx=5)
            self.botones_filtro[key] = btn

        # Date range pickers
        rango_frame = ttk.Frame(filtro_frame)
        rango_frame.pack(fill=tk.X, pady=10)

        ttk.Label(rango_frame, text="Rango personalizado:").pack(side=tk.LEFT, padx=5)
        ttk.Label(rango_frame, text="Desde:").pack(side=tk.LEFT, padx=5)
        self.entrada_fecha_inicio = ttk.Entry(rango_frame, width=12)
        self.entrada_fecha_inicio.pack(side=tk.LEFT, padx=2)
        self.entrada_fecha_inicio.insert(0, datetime.date.today().strftime("%Y-%m-%d"))

        ttk.Label(rango_frame, text="Hasta:").pack(side=tk.LEFT, padx=5)
        self.entrada_fecha_fin = ttk.Entry(rango_frame, width=12)
        self.entrada_fecha_fin.pack(side=tk.LEFT, padx=2)
        self.entrada_fecha_fin.insert(0, datetime.date.today().strftime("%Y-%m-%d"))

        btn_aplicar = crear_boton(
            rango_frame,
            "Aplicar Rango",
            self._aplicar_rango_personalizado,
            tipo='secundario'
        )
        btn_aplicar.pack(side=tk.LEFT, padx=10)

    def _cambiar_filtro(self, filtro):
        """Change active filter and update button styles"""
        self.filtro_activo = filtro
        self._pagina = 0
        self._kpi_last_filter = None  # forzar recálculo de KPIs

        for key, btn in self.botones_filtro.items():
            if key == filtro:
                btn.config(bg=COLORES['primario'], fg='white')
            else:
                btn.config(bg=COLORES['fondo_card'], fg=COLORES['texto'])

        self.venta_seleccionada = None
        self._actualizar_datos()

    def _aplicar_rango_personalizado(self):
        """Apply custom date range filter"""
        try:
            fecha_inicio = self.entrada_fecha_inicio.get()
            fecha_fin = self.entrada_fecha_fin.get()

            datetime.datetime.strptime(fecha_inicio, "%Y-%m-%d")
            datetime.datetime.strptime(fecha_fin, "%Y-%m-%d")

            self.filtro_activo = "personalizado"
            self.venta_seleccionada = None
            self._pagina = 0
            self._kpi_last_filter = None  # forzar recálculo de KPIs

            for btn in self.botones_filtro.values():
                btn.config(bg=COLORES['fondo_card'], fg=COLORES['texto'])

            self._actualizar_datos()
        except ValueError:
            messagebox.showerror("Error", "Formato de fecha inválido. Usa YYYY-MM-DD")

    def _crear_resumen_kpi(self):
        """Create KPI summary bar"""
        kpi_frame = ttk.Frame(self.main_frame)
        kpi_frame.pack(fill=tk.X, pady=(0, 10))

        # Total Ventas
        self.kpi_total_card, self.kpi_total_valor = crear_tarjeta_kpi(
            kpi_frame, "Total Ventas", "$0", "", COLORES['primario']
        )
        self.kpi_total_card.pack(side=tk.LEFT, padx=5, fill=tk.BOTH, expand=True)

        # Número de Transacciones
        self.kpi_transacciones_card, self.kpi_transacciones_valor = crear_tarjeta_kpi(
            kpi_frame, "Transacciones", "0", "", COLORES['primario']
        )
        self.kpi_transacciones_card.pack(side=tk.LEFT, padx=5, fill=tk.BOTH, expand=True)

        # Ticket Promedio
        self.kpi_promedio_card, self.kpi_promedio_valor = crear_tarjeta_kpi(
            kpi_frame, "Ticket Promedio", "$0", "", COLORES['primario']
        )
        self.kpi_promedio_card.pack(side=tk.LEFT, padx=5, fill=tk.BOTH, expand=True)

        # Producto Estrella
        self.kpi_producto_card, self.kpi_producto_valor = crear_tarjeta_kpi(
            kpi_frame, "Producto Estrella", "—", "", COLORES['primario_claro']
        )
        self.kpi_producto_card.pack(side=tk.LEFT, padx=5, fill=tk.BOTH, expand=True)

    def _crear_tabla_ventas(self):
        """Create main sales table"""
        tabla_frame = ttk.LabelFrame(self.main_frame, text="Historial de Ventas", padding=10)
        tabla_frame.pack(fill=tk.BOTH, expand=False, pady=(0, 10))

        # Scrollbars
        vsb = ttk.Scrollbar(tabla_frame, orient=tk.VERTICAL)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        hsb = ttk.Scrollbar(tabla_frame, orient=tk.HORIZONTAL)
        hsb.pack(side=tk.BOTTOM, fill=tk.X)

        # Treeview
        self.tabla_ventas = ttk.Treeview(
            tabla_frame,
            columns=("venta_id", "cliente", "total", "metodo_pago", "estado", "fecha_hora"),
            height=12,
            yscrollcommand=vsb.set,
            xscrollcommand=hsb.set
        )

        vsb.config(command=self.tabla_ventas.yview)
        hsb.config(command=self.tabla_ventas.xview)

        # Column definitions
        self.tabla_ventas.column("#0", width=0, stretch=tk.NO)
        self.tabla_ventas.column("venta_id", anchor=tk.CENTER, width=80)
        self.tabla_ventas.column("cliente", anchor=tk.W, width=150)
        self.tabla_ventas.column("total", anchor=tk.E, width=100)
        self.tabla_ventas.column("metodo_pago", anchor=tk.CENTER, width=100)
        self.tabla_ventas.column("estado", anchor=tk.CENTER, width=100)
        self.tabla_ventas.column("fecha_hora", anchor=tk.CENTER, width=150)

        # Headings
        self.tabla_ventas.heading("#0", text="", anchor=tk.W)
        self.tabla_ventas.heading("venta_id", text="Nº Venta", anchor=tk.CENTER)
        self.tabla_ventas.heading("cliente", text="Cliente", anchor=tk.W)
        self.tabla_ventas.heading("total", text="Total", anchor=tk.E)
        self.tabla_ventas.heading("metodo_pago", text="Método Pago", anchor=tk.CENTER)
        self.tabla_ventas.heading("estado", text="Estado", anchor=tk.CENTER)
        self.tabla_ventas.heading("fecha_hora", text="Fecha/Hora", anchor=tk.CENTER)

        # Apply table style
        aplicar_estilo_tabla(self.tabla_ventas)
        self.tabla_ventas.tag_configure('devolucion', foreground='#CC2200', background='#FFF0EE')
        self.tabla_ventas.tag_configure('con_dev',    foreground='#8B4400', background='#FFF8F0')

        self.tabla_ventas.pack(fill=tk.BOTH, expand=True)
        self.tabla_ventas.bind("<<TreeviewSelect>>", self._on_venta_seleccionada)
        self.tabla_ventas.bind("<Double-1>", lambda e: self._ver_detalles_popup())

        def _scroll_hist(event):
            d = int(-1 * (event.delta / 120)) if event.delta else (1 if event.num == 5 else -1)
            self.tabla_ventas.yview_scroll(d, "units")
        self.tabla_ventas.bind_all('<MouseWheel>', _scroll_hist)
        self.tabla_ventas.bind_all('<Button-4>', _scroll_hist)
        self.tabla_ventas.bind_all('<Button-5>', _scroll_hist)

    def _crear_panel_detalle(self):
        """Create detail panel for selected sale items"""
        detalle_frame = ttk.LabelFrame(self.main_frame, text="Detalle de Venta", padding=10)
        detalle_frame.pack(fill=tk.BOTH, expand=False, pady=(0, 10))

        # Scrollbars for detail table
        vsb_detalle = ttk.Scrollbar(detalle_frame, orient=tk.VERTICAL)
        vsb_detalle.pack(side=tk.RIGHT, fill=tk.Y)

        # Detail Treeview
        self.tabla_detalle = ttk.Treeview(
            detalle_frame,
            columns=("producto", "cantidad", "precio_unitario", "subtotal"),
            height=6,
            yscrollcommand=vsb_detalle.set
        )

        vsb_detalle.config(command=self.tabla_detalle.yview)

        # Column definitions
        self.tabla_detalle.column("#0", width=0, stretch=tk.NO)
        self.tabla_detalle.column("producto", anchor=tk.W, width=250)
        self.tabla_detalle.column("cantidad", anchor=tk.CENTER, width=80)
        self.tabla_detalle.column("precio_unitario", anchor=tk.E, width=120)
        self.tabla_detalle.column("subtotal", anchor=tk.E, width=120)

        # Headings
        self.tabla_detalle.heading("#0", text="", anchor=tk.W)
        self.tabla_detalle.heading("producto", text="Producto", anchor=tk.W)
        self.tabla_detalle.heading("cantidad", text="Cantidad", anchor=tk.CENTER)
        self.tabla_detalle.heading("precio_unitario", text="Precio Unit.", anchor=tk.E)
        self.tabla_detalle.heading("subtotal", text="Subtotal", anchor=tk.E)

        aplicar_estilo_tabla(self.tabla_detalle)

        self.tabla_detalle.pack(fill=tk.BOTH, expand=True)

    def _crear_paginacion(self):
        """Crea la barra de navegación de páginas."""
        pag_frame = tk.Frame(self.main_frame, bg=COLORES['fondo'])
        pag_frame.pack(fill=tk.X, pady=(0, 4))

        self.btn_anterior = crear_boton(
            pag_frame, " Anterior", self._pagina_anterior, tipo='secundario'
        )
        self.btn_anterior.pack(side=tk.LEFT, padx=5)

        self.lbl_pagina = tk.Label(
            pag_frame, text="Página 1 de 1",
            font=FUENTES['normal'], fg=COLORES['texto_secundario'],
            bg=COLORES['fondo']
        )
        self.lbl_pagina.pack(side=tk.LEFT, padx=10)

        self.btn_siguiente = crear_boton(
            pag_frame, "Siguiente ", self._pagina_siguiente, tipo='secundario'
        )
        self.btn_siguiente.pack(side=tk.LEFT, padx=5)

        self.lbl_registros = tk.Label(
            pag_frame, text="",
            font=FUENTES['pequena'], fg=COLORES['texto_secundario'],
            bg=COLORES['fondo']
        )
        self.lbl_registros.pack(side=tk.RIGHT, padx=10)

    def _pagina_anterior(self):
        if self._pagina > 0:
            self._pagina -= 1
            self._actualizar_datos()

    def _pagina_siguiente(self):
        total_paginas = max(1, -(-self._total_registros // self._por_pagina))
        if self._pagina < total_paginas - 1:
            self._pagina += 1
            self._actualizar_datos()

    def _actualizar_paginacion(self):
        total_paginas = max(1, -(-self._total_registros // self._por_pagina))
        pagina_actual = self._pagina + 1
        self.lbl_pagina.config(text=f"Página {pagina_actual} de {total_paginas}")
        self.lbl_registros.config(
            text=f"{self._total_registros} registros en total"
        )
        self.btn_anterior.config(state='normal' if self._pagina > 0 else 'disabled')
        self.btn_siguiente.config(
            state='normal' if pagina_actual < total_paginas else 'disabled'
        )

    def _crear_botones_accion(self):
        """Create action buttons"""
        botones_frame = ttk.Frame(self.main_frame)
        botones_frame.pack(fill=tk.X, pady=10)

        self.btn_ver_detalles = crear_boton(
            botones_frame,
            "Ver Detalles",
            self._ver_detalles_popup,
            tipo='primario'
        )
        self.btn_ver_detalles.pack(side=tk.LEFT, padx=5)

        self.btn_anular = crear_boton(
            botones_frame,
            "Anular Venta",
            self._anular_venta,
            tipo='error'
        )
        self.btn_anular.pack(side=tk.LEFT, padx=5)

        # Export button
        btn_exportar = crear_boton(
            botones_frame,
            "Exportar",
            self._exportar_datos,
            tipo='secundario'
        )
        btn_exportar.pack(side=tk.LEFT, padx=5)

        # Print button
        btn_imprimir = crear_boton(
            botones_frame,
            "Imprimir Recibo",
            self._imprimir_recibo,
            tipo='primario'
        )
        btn_imprimir.pack(side=tk.LEFT, padx=5)

    def _on_venta_seleccionada(self, event):
        """Handle sale selection"""
        selection = self.tabla_ventas.selection()
        if selection:
            item = selection[0]
            self.venta_seleccionada = self.tabla_ventas.item(item)['values'][0]  # venta_id
            self._cargar_detalle_venta()
        else:
            self.venta_seleccionada = None
            self.tabla_detalle.delete(*self.tabla_detalle.get_children())

    def _cargar_detalle_venta(self):
        """Load detail items for selected sale"""
        self.tabla_detalle.delete(*self.tabla_detalle.get_children())

        if not self.venta_seleccionada:
            return

        try:
            with conexion_segura() as conn:
                query = """
                    SELECT
                        pd.producto_nombre,
                        pd.cantidad,
                        pd.precio_unitario,
                        (pd.cantidad * pd.precio_unitario) as subtotal
                    FROM venta_detalle pd
                    WHERE pd.id_venta = ?
                    ORDER BY pd.id_detalle ASC
                """
                rows = conn.execute(query, (self.venta_seleccionada,)).fetchall()

                for row in rows:
                    self.tabla_detalle.insert(
                        "",
                        tk.END,
                        values=(
                            row[0],  # producto_nombre
                            row[1],  # cantidad
                            format_money(row[2]),  # precio_unitario
                            format_money(row[3])   # subtotal
                        )
                    )
        except Exception as e:
            import logging
            logging.getLogger("pocitos").error(f"Error cargando detalle venta: {e}")

    def _ver_detalles_popup(self):
        """Show sale details in a popup"""
        if not self.venta_seleccionada:
            messagebox.showwarning("Advertencia", "Selecciona una venta primero")
            return

        try:
            with conexion_segura() as conn:
                venta = conn.execute("""
                    SELECT v.id_venta, v.numero_venta, v.cliente_nombre, v.total,
                           v.metodo_pago, v.estado, v.fecha_creacion, v.notas, v.tipo
                    FROM ventas v
                    WHERE v.id_venta = ?
                """, (self.venta_seleccionada,)).fetchone()

                if not venta:
                    messagebox.showerror("Error", "Venta no encontrada")
                    return

                items = conn.execute("""
                    SELECT p.nombre, vd.cantidad, vd.precio_unitario,
                           (vd.cantidad * vd.precio_unitario) as subtotal
                    FROM venta_detalle vd
                    LEFT JOIN productos p ON vd.id_producto = p.id_producto
                    WHERE vd.id_venta = ?
                    ORDER BY vd.id_detalle
                """, (self.venta_seleccionada,)).fetchall()

                pagos_venta = conn.execute("""
                    SELECT metodo_pago, valor, monto_recibido
                    FROM pagos
                    WHERE id_venta = ?
                    ORDER BY id_pago
                """, (self.venta_seleccionada,)).fetchall()

        except Exception as e:
            messagebox.showerror("Error", f"Error cargando detalles: {e}")
            return

        # Dimensionar según pantalla
        popup = tk.Toplevel(self.parent)
        popup.title(f"Venta {venta['numero_venta'] or '#' + str(venta['id_venta'])}")
        popup.resizable(True, True)
        popup.grab_set()
        sw = popup.winfo_screenwidth()
        sh = popup.winfo_screenheight()
        w = min(680, int(sw * 0.80))
        h = min(580, int(sh * 0.80))
        x = (sw - w) // 2
        y = (sh - h) // 2
        popup.geometry(f"{w}x{h}+{x}+{y}")
        popup.configure(bg=COLORES['fondo_card'])

        # Encabezado
        hdr = tk.Frame(popup, bg=COLORES['primario'], height=50)
        hdr.pack(fill='x')
        hdr.pack_propagate(False)
        tk.Label(hdr,
                 text=f"Venta {venta['numero_venta'] or '#' + str(venta['id_venta'])}  —  {venta['tipo'] or ''}",
                 font=FUENTES['encabezado'], fg=COLORES['texto_claro'],
                 bg=COLORES['primario']).pack(side='left', padx=16, pady=12)

        body = tk.Frame(popup, bg=COLORES['fondo_card'])
        body.pack(fill='both', expand=True, padx=16, pady=12)

        # Fila de datos principales
        def dato(parent, label, valor, col):
            f = tk.Frame(parent, bg=COLORES['fondo_card'])
            f.grid(row=0, column=col, sticky='nw', padx=(0, 24))
            tk.Label(f, text=label, font=FUENTES['pequena'],
                     fg=COLORES['texto_secundario'], bg=COLORES['fondo_card']).pack(anchor='w')
            tk.Label(f, text=str(valor or '—'), font=FUENTES['normal_bold'],
                     fg=COLORES['texto'], bg=COLORES['fondo_card']).pack(anchor='w')

        info_row = tk.Frame(body, bg=COLORES['fondo_card'])
        info_row.pack(fill='x', pady=(0, 8))
        dato(info_row, "Cliente",        venta['cliente_nombre'] or 'Mostrador', 0)
        dato(info_row, "Método de pago", venta['metodo_pago'],                   1)
        dato(info_row, "Estado",         venta['estado'],                        2)
        dato(info_row, "Fecha / Hora",   venta['fecha_creacion'],                3)

        if venta['notas']:
            tk.Label(body, text=f"Nota: {venta['notas']}",
                     font=FUENTES['pequena'], fg=COLORES['texto_secundario'],
                     bg=COLORES['fondo_card'], wraplength=w - 60, justify='left').pack(anchor='w', pady=(0, 6))

        tk.Frame(body, bg=COLORES['borde'], height=1).pack(fill='x', pady=(0, 8))

        # Tabla de ítems
        tk.Label(body, text="Productos", font=FUENTES['normal_bold'],
                 fg=COLORES['texto'], bg=COLORES['fondo_card']).pack(anchor='w', pady=(0, 4))

        tree_frame = tk.Frame(body, bg=COLORES['fondo_card'])
        tree_frame.pack(fill='both', expand=True)

        vsb = ttk.Scrollbar(tree_frame, orient='vertical')
        vsb.pack(side='right', fill='y')

        tree = ttk.Treeview(tree_frame,
                            columns=('producto', 'cant', 'precio', 'subtotal'),
                            show='headings', yscrollcommand=vsb.set, height=8)
        vsb.config(command=tree.yview)
        aplicar_estilo_tabla(tree)

        tree.heading('producto',  text='Producto')
        tree.heading('cant',      text='Cant.')
        tree.heading('precio',    text='Precio unit.')
        tree.heading('subtotal',  text='Subtotal')
        tree.column('producto',  width=260, anchor='w')
        tree.column('cant',      width=60,  anchor='center')
        tree.column('precio',    width=110, anchor='e')
        tree.column('subtotal',  width=110, anchor='e')
        tree.pack(fill='both', expand=True)

        for it in items:
            tree.insert('', 'end', values=(
                it['nombre'] or '—',
                it['cantidad'],
                format_money(it['precio_unitario']),
                format_money(it['subtotal']),
            ))

        # Total al pie
        tk.Frame(body, bg=COLORES['borde'], height=1).pack(fill='x', pady=(8, 4))
        total_row = tk.Frame(body, bg=COLORES['fondo_card'])
        total_row.pack(fill='x')
        tk.Label(total_row, text="TOTAL", font=FUENTES['normal_bold'],
                 fg=COLORES['texto_secundario'], bg=COLORES['fondo_card']).pack(side='left')
        tk.Label(total_row, text=format_money(venta['total']),
                 font=FUENTES['kpi_valor'], fg=COLORES['acento'],
                 bg=COLORES['fondo_card']).pack(side='right')

        # Desglose de pagos (especialmente útil para MIXTO)
        if pagos_venta:
            tk.Frame(body, bg=COLORES['borde'], height=1).pack(fill='x', pady=(6, 4))
            tk.Label(body, text="Como se pagó:", font=FUENTES['normal_bold'],
                     fg=COLORES['texto'], bg=COLORES['fondo_card']).pack(anchor='w')
            pago_frame = tk.Frame(body, bg=COLORES['fondo_input'],
                                   relief='solid', bd=1)
            pago_frame.pack(fill='x', pady=(4, 0))
            for pago in pagos_venta:
                fila = tk.Frame(pago_frame, bg=COLORES['fondo_input'])
                fila.pack(fill='x', padx=10, pady=3)
                metodo = pago['metodo_pago'] or '—'
                color_m = (COLORES['exito'] if metodo == 'EFECTIVO'
                           else COLORES['primario'])
                tk.Label(fila, text=f"  {metodo}",
                         font=FUENTES['normal_bold'], fg=color_m,
                         bg=COLORES['fondo_input'],
                         width=16, anchor='w').pack(side='left')
                tk.Label(fila, text=format_money(pago['valor']),
                         font=FUENTES['normal_bold'], fg=COLORES['texto'],
                         bg=COLORES['fondo_input']).pack(side='right', padx=10)
                # Mostrar monto recibido y cambio si aplica
                if metodo == 'EFECTIVO' and pago['monto_recibido'] and pago['monto_recibido'] > pago['valor']:
                    cambio = pago['monto_recibido'] - pago['valor']
                    fila2 = tk.Frame(pago_frame, bg=COLORES['fondo_input'])
                    fila2.pack(fill='x', padx=10, pady=(0, 3))
                    tk.Label(fila2, text=f"    Recibio: {format_money(pago['monto_recibido'])}",
                             font=FUENTES['normal'], fg=COLORES['texto_secundario'],
                             bg=COLORES['fondo_input']).pack(side='left')
                    tk.Label(fila2, text=f"Cambio: {format_money(cambio)}",
                             font=FUENTES['normal_bold'], fg=COLORES['exito'],
                             bg=COLORES['fondo_input']).pack(side='right', padx=10)

        # Botones finales
        btn_row = tk.Frame(popup, bg=COLORES['fondo_card'])
        btn_row.pack(pady=10)
        if venta['estado'] not in ('ANULADA',):
            crear_boton(btn_row, "Registrar Devolucion",
                        lambda: self._procesar_devolucion(venta, popup),
                        tipo='advertencia').pack(side='left', padx=6)
        crear_boton(btn_row, "Cerrar", popup.destroy, tipo='secundario').pack(side='left', padx=6)

    def _procesar_devolucion(self, venta, popup_padre):
        """Registra una devolucion parcial o total de una venta."""
        id_venta = venta['id_venta']
        total_venta = venta['total']

        # Verificar cuánto ya fue devuelto
        try:
            with conexion_segura() as conn:
                ya_devuelto = conn.execute(
                    "SELECT COALESCE(SUM(monto), 0) FROM devoluciones WHERE id_venta = ?",
                    (id_venta,)
                ).fetchone()[0]
        except Exception:
            ya_devuelto = 0

        pendiente = total_venta - ya_devuelto
        if pendiente <= 0:
            messagebox.showinfo("Sin pendiente",
                                "Esta venta ya fue devuelta completamente.",
                                parent=popup_padre)
            return

        dlg = tk.Toplevel(popup_padre)
        dlg.title("Registrar Devolucion")
        dlg.resizable(False, False)
        dlg.grab_set()
        dlg.configure(bg=COLORES['fondo_card'])
        w, h = 420, 320
        sw, sh = dlg.winfo_screenwidth(), dlg.winfo_screenheight()
        dlg.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

        # Header
        hdr = tk.Frame(dlg, bg=COLORES['advertencia'], height=44)
        hdr.pack(fill='x')
        hdr.pack_propagate(False)
        tk.Label(hdr, text="Devolucion de venta",
                 font=FUENTES['encabezado'], fg=COLORES['texto_claro'],
                 bg=COLORES['advertencia']).pack(side='left', padx=14, pady=10)

        body = tk.Frame(dlg, bg=COLORES['fondo_card'])
        body.pack(fill='both', expand=True, padx=20, pady=14)

        info_txt = f"Venta: {venta['numero_venta'] or '#'+str(id_venta)}  —  Total: {format_money(total_venta)}"
        if ya_devuelto > 0:
            info_txt += f"\nYa devuelto: {format_money(ya_devuelto)}  |  Pendiente: {format_money(pendiente)}"
        tk.Label(body, text=info_txt,
                 font=FUENTES['normal_bold'], fg=COLORES['texto'],
                 bg=COLORES['fondo_card'], justify='left').pack(anchor='w', pady=(0, 10))

        tk.Label(body, text="Monto a devolver:", font=FUENTES['normal'],
                 fg=COLORES['texto'], bg=COLORES['fondo_card']).pack(anchor='w')
        entry_monto = tk.Entry(body, font=FUENTES['normal'], width=20)
        entry_monto.insert(0, str(int(pendiente)))
        entry_monto.pack(anchor='w', pady=(2, 10))

        tk.Label(body, text="Motivo (obligatorio):", font=FUENTES['normal'],
                 fg=COLORES['texto'], bg=COLORES['fondo_card']).pack(anchor='w')
        entry_motivo = tk.Entry(body, font=FUENTES['normal'], width=40)
        entry_motivo.pack(anchor='w', pady=(2, 10))
        entry_motivo.focus_set()

        var_inventario = tk.BooleanVar(value=True)
        tk.Checkbutton(body, text="Restaurar productos al inventario",
                       variable=var_inventario, font=FUENTES['normal'],
                       fg=COLORES['texto'], bg=COLORES['fondo_card'],
                       activebackground=COLORES['fondo_card']).pack(anchor='w', pady=(0, 6))

        lbl_error = tk.Label(body, text="", font=FUENTES['pequena'],
                             fg=COLORES['error'], bg=COLORES['fondo_card'])
        lbl_error.pack(anchor='w')

        def _confirmar():
            try:
                monto = float(entry_monto.get().replace(',', '').replace('.', '') or '0')
            except ValueError:
                lbl_error.config(text="Monto invalido.")
                return
            motivo = entry_motivo.get().strip()
            if monto <= 0:
                lbl_error.config(text="El monto debe ser mayor a 0.")
                return
            if monto > pendiente:
                lbl_error.config(text=f"Maximo a devolver: {format_money(pendiente)}.")
                return
            if not motivo:
                lbl_error.config(text="El motivo es obligatorio.")
                return

            try:
                with transaccion_atomica() as conn:
                    conn.execute("""
                        INSERT INTO devoluciones (id_venta, monto, motivo, usuario, aplicado_caja)
                        VALUES (?, ?, ?, ?, 0)
                    """, (id_venta, monto, motivo, self.usuario['usuario']))

                    # Descontar de caja si hay una abierta
                    caja = conn.execute(
                        "SELECT id_caja FROM caja_diaria WHERE estado='ABIERTA'"
                    ).fetchone()
                    aplicado = 0
                    if caja:
                        conn.execute("""
                            INSERT INTO movimientos_caja
                            (id_caja, tipo, concepto, valor, metodo_pago, usuario)
                            VALUES (?, 'EGRESO', ?, ?, 'EFECTIVO', ?)
                        """, (caja['id_caja'],
                              f"Devolucion venta {venta['numero_venta'] or '#'+str(id_venta)}: {motivo}",
                              monto, self.usuario['usuario']))
                        aplicado = 1
                        conn.execute("""
                            UPDATE devoluciones SET aplicado_caja=1
                            WHERE id_devolucion = (
                                SELECT id_devolucion FROM devoluciones
                                WHERE id_venta=? AND motivo=?
                                ORDER BY id_devolucion DESC LIMIT 1
                            )
                        """, (id_venta, motivo))

                    # Restaurar inventario si se marcó el checkbox
                    if var_inventario.get():
                        items = conn.execute("""
                            SELECT vd.id_producto, vd.cantidad, p.nombre, p.controla_stock,
                                   p.stock_actual
                            FROM venta_detalle vd
                            JOIN productos p ON vd.id_producto = p.id_producto
                            WHERE vd.id_venta = ?
                        """, (id_venta,)).fetchall()
                        for item in items:
                            if item['controla_stock']:
                                stock_ant = item['stock_actual']
                                stock_nuevo = stock_ant + item['cantidad']
                                conn.execute("""
                                    UPDATE productos SET stock_actual = ?
                                    WHERE id_producto = ?
                                """, (stock_nuevo, item['id_producto']))
                                conn.execute("""
                                    INSERT INTO movimientos_inventario
                                    (id_producto, tipo, cantidad, stock_anterior, stock_nuevo,
                                     motivo, referencia, usuario, fecha)
                                    VALUES (?, 'ENTRADA', ?, ?, ?,
                                            'Devolucion', ?, ?, datetime('now','localtime'))
                                """, (item['id_producto'], item['cantidad'],
                                      stock_ant, stock_nuevo,
                                      motivo,
                                      venta['numero_venta'] or f"#{id_venta}",
                                      self.usuario['usuario']))

                    from utils.logger import log_auditoria
                    log_auditoria(conn, 'devoluciones', id_venta, 'DEVOLUCION',
                                  self.usuario['usuario'],
                                  f"Devolucion {format_money(monto)} — {motivo}")

                msg_caja = "\nDescontado de caja automaticamente." if aplicado else \
                           "\nNo hay caja abierta — anotalo manualmente."
                messagebox.showinfo("Devolucion registrada",
                                    f"Devolucion de {format_money(monto)} registrada.{msg_caja}",
                                    parent=dlg)
                dlg.destroy()
                self._actualizar_datos()

            except Exception as e:
                lbl_error.config(text=f"Error: {e}")

        btn_row2 = tk.Frame(body, bg=COLORES['fondo_card'])
        btn_row2.pack(anchor='e', pady=(6, 0))
        crear_boton(btn_row2, "Confirmar", _confirmar, tipo='error').pack(side='left', padx=4)
        crear_boton(btn_row2, "Cancelar", dlg.destroy, tipo='secundario').pack(side='left', padx=4)

    def _anular_venta(self):
        """Anula una venta con motivo obligatorio y verificacion de PIN para montos altos."""
        if not self.venta_seleccionada:
            messagebox.showwarning("Advertencia", "Selecciona una venta primero")
            return

        # Obtener datos de la venta
        try:
            with conexion_segura() as conn:
                venta = conn.execute(
                    "SELECT numero_venta, total, estado FROM ventas WHERE id_venta = ?",
                    (self.venta_seleccionada,)
                ).fetchone()
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo obtener la venta: {e}")
            return

        if not venta:
            messagebox.showwarning("Advertencia", "Venta no encontrada.")
            return

        if venta['estado'] == 'ANULADA':
            messagebox.showwarning("Advertencia", "Esta venta ya esta anulada.")
            return

        total_venta = float(venta['total'] or 0)

        # --- Diálogo de motivo obligatorio ---
        motivo = self._pedir_motivo_anulacion(venta['numero_venta'], total_venta)
        if motivo is None:
            return  # usuario canceló

        # --- Verificación PIN admin si monto > $50.000 ---
        if total_venta > 50000:
            autorizado = self._verificar_pin_admin_anulacion(total_venta)
            if not autorizado:
                return

        # --- Ejecutar anulación ---
        try:
            with transaccion_atomica() as conn:
                # 1. Marcar la venta como anulada
                conn.execute(
                    "UPDATE ventas SET estado = 'ANULADA' WHERE id_venta = ?",
                    (self.venta_seleccionada,)
                )

                # 2. Revertir stock e insertar movimiento de devolución por cada ítem
                items = conn.execute(
                    """SELECT id_producto, cantidad, producto_nombre
                       FROM venta_detalle
                       WHERE id_venta = ?""",
                    (self.venta_seleccionada,)
                ).fetchall()

                for item in items:
                    # Solo revertir productos que controlan stock
                    controla = conn.execute(
                        "SELECT controla_stock FROM productos WHERE id_producto = ?",
                        (item['id_producto'],)
                    ).fetchone()
                    if controla and controla['controla_stock']:
                        conn.execute(
                            """UPDATE productos
                               SET stock_actual = stock_actual + ?,
                                   fecha_actualizacion = datetime('now','localtime')
                               WHERE id_producto = ?""",
                            (item['cantidad'], item['id_producto'])
                        )
                    conn.execute(
                        """INSERT INTO movimientos_inventario
                           (id_producto, tipo, cantidad, motivo, referencia, usuario)
                           VALUES (?, 'DEVOLUCION', ?, ?, ?, ?)""",
                        (item['id_producto'], item['cantidad'],
                         f"Anulación venta {venta['numero_venta']}. {motivo}",
                         venta['numero_venta'], self.usuario['nombre_completo'])
                    )

                # 3. Registrar egreso en caja y descontar del total
                caja = conn.execute(
                    "SELECT id_caja FROM caja_diaria WHERE estado = 'ABIERTA'"
                ).fetchone()
                if caja:
                    conn.execute(
                        """INSERT INTO movimientos_caja
                           (id_caja, tipo, concepto, valor, referencia, usuario)
                           VALUES (?, 'EGRESO', ?, ?, ?, ?)""",
                        (caja['id_caja'],
                         f"Anulación venta {venta['numero_venta']}",
                         total_venta, venta['numero_venta'],
                         self.usuario['nombre_completo'])
                    )
                    conn.execute(
                        """UPDATE caja_diaria
                           SET total_ventas = total_ventas - ?,
                               monto_esperado = monto_esperado - ?
                           WHERE id_caja = ?""",
                        (total_venta, total_venta, caja['id_caja'])
                    )

                # 4. Auditoría dentro de la misma transacción
                log_auditoria(
                    conn, "ventas", self.venta_seleccionada, "ANULAR",
                    self.usuario['usuario'],
                    f"Venta {venta['numero_venta']} anulada. Motivo: {motivo}. Total: ${total_venta:,.0f}"
                )

            messagebox.showinfo("Anulacion exitosa",
                                f"Venta {venta['numero_venta']} anulada correctamente.")
            self.venta_seleccionada = None
            self._actualizar_datos()

        except Exception as e:
            messagebox.showerror("Error", f"Error al anular venta: {e}")

    def _pedir_motivo_anulacion(self, numero_venta, total_venta):
        """Muestra un dialogo para ingresar el motivo de anulacion (min 10 chars).
        Retorna el motivo ingresado, o None si el usuario cancelo."""
        dialogo = tk.Toplevel(self.parent.winfo_toplevel())
        dialogo.title("Motivo de Anulacion")
        dialogo.resizable(True, True)
        dialogo.grab_set()

        # Centrar
        dialogo.update_idletasks()
        w, h = 450, 240
        x = dialogo.winfo_screenwidth() // 2 - w // 2
        y = dialogo.winfo_screenheight() // 2 - h // 2
        dialogo.geometry(f"{w}x{h}+{x}+{y}")
        dialogo.configure(bg=COLORES['fondo_card'])

        tk.Label(dialogo,
                 text=f"Anular venta {numero_venta}  —  Total: $ {total_venta:,.0f}",
                 font=FUENTES['encabezado'], fg=COLORES['texto'],
                 bg=COLORES['fondo_card']).pack(padx=20, pady=(15, 5))

        tk.Label(dialogo, text="Motivo de anulacion (minimo 10 caracteres):",
                 font=FUENTES['normal'], fg=COLORES['texto'],
                 bg=COLORES['fondo_card']).pack(padx=20, anchor='w')

        text_motivo = tk.Text(dialogo, font=FUENTES['normal'], height=4,
                              relief='solid', bd=1, wrap='word')
        text_motivo.pack(fill='x', padx=20, pady=(4, 5))

        lbl_contador = tk.Label(dialogo, text="0 / 10 caracteres minimos",
                                font=FUENTES['pequena'], fg=COLORES['texto_secundario'],
                                bg=COLORES['fondo_card'])
        lbl_contador.pack(anchor='e', padx=20)

        resultado = [None]

        def _on_key(event=None):
            n = len(text_motivo.get('1.0', 'end-1c').strip())
            color = COLORES['exito'] if n >= 10 else COLORES['error']
            lbl_contador.config(text=f"{n} caracteres{' — OK' if n >= 10 else ' — minimo 10'}",
                                fg=color)

        text_motivo.bind('<KeyRelease>', _on_key)

        def _confirmar():
            motivo = text_motivo.get('1.0', 'end-1c').strip()
            if len(motivo) < 10:
                messagebox.showwarning("Motivo insuficiente",
                                       "El motivo debe tener al menos 10 caracteres.",
                                       parent=dialogo)
                return
            resultado[0] = motivo
            dialogo.destroy()

        def _cancelar():
            dialogo.destroy()

        btn_f = tk.Frame(dialogo, bg=COLORES['fondo_card'])
        btn_f.pack(fill='x', padx=20, pady=(0, 15))
        crear_boton(btn_f, "Confirmar", _confirmar, tipo='error').pack(side='right', padx=5)
        crear_boton(btn_f, "Cancelar", _cancelar, tipo='secundario').pack(side='right')

        dialogo.wait_window()
        return resultado[0]

    def _verificar_pin_admin_anulacion(self, total_venta):
        """Pide el PIN de un administrador para autorizar la anulacion.
        Retorna True si el PIN es valido, False en caso contrario."""
        from models.validaciones import verificar_pin_admin

        dialogo = tk.Toplevel(self.parent.winfo_toplevel())
        dialogo.title("Autorizacion Requerida")
        dialogo.resizable(True, True)
        dialogo.grab_set()

        w, h = 380, 200
        x = dialogo.winfo_screenwidth() // 2 - w // 2
        y = dialogo.winfo_screenheight() // 2 - h // 2
        dialogo.geometry(f"{w}x{h}+{x}+{y}")
        dialogo.configure(bg=COLORES['fondo_card'])

        tk.Label(dialogo,
                 text=f"Monto a anular: $ {total_venta:,.0f}",
                 font=FUENTES['encabezado'], fg=COLORES['error'],
                 bg=COLORES['fondo_card']).pack(padx=20, pady=(15, 4))

        tk.Label(dialogo,
                 text="Se requiere PIN de administrador para\nanulaciones mayores a $ 50.000",
                 font=FUENTES['normal'], fg=COLORES['texto'],
                 bg=COLORES['fondo_card']).pack(padx=20, pady=(0, 8))

        pin_f = tk.Frame(dialogo, bg=COLORES['fondo_card'])
        pin_f.pack()
        tk.Label(pin_f, text="PIN (4 digitos):", font=FUENTES['normal'],
                 fg=COLORES['texto'], bg=COLORES['fondo_card']).pack(side='left')
        entry_pin = tk.Entry(pin_f, font=FUENTES['input'], width=8, show='*',
                              relief='solid', bd=1)
        entry_pin.pack(side='left', padx=8, ipady=4)
        entry_pin.focus_set()

        autorizado = [False]

        def _verificar():
            valido, nombre = verificar_pin_admin(entry_pin.get().strip())
            if valido:
                autorizado[0] = True
                dialogo.destroy()
            else:
                messagebox.showerror("PIN incorrecto",
                                     "El PIN ingresado no corresponde a ningun administrador.",
                                     parent=dialogo)
                entry_pin.delete(0, tk.END)
                entry_pin.focus_set()

        def _cancelar():
            dialogo.destroy()

        entry_pin.bind('<Return>', lambda e: _verificar())

        btn_f = tk.Frame(dialogo, bg=COLORES['fondo_card'])
        btn_f.pack(pady=10)
        crear_boton(btn_f, "Autorizar", _verificar, tipo='primario').pack(side='left', padx=5)
        crear_boton(btn_f, "Cancelar", _cancelar, tipo='secundario').pack(side='left')

        dialogo.wait_window()
        return autorizado[0]

    def _imprimir_recibo(self):
        """Genera e imprime el recibo PDF de la venta seleccionada"""
        if not self.venta_seleccionada:
            messagebox.showwarning("Advertencia", "Selecciona una venta primero")
            return
        imprimir_recibo_venta(self.venta_seleccionada)

    def _exportar_datos(self):
        """Export sales data to CSV"""
        try:
            import csv

            default_name = f"historial_ventas_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            filename = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV", "*.csv")],
                initialfile=default_name,
                title="Guardar historial de ventas"
            )
            if not filename:
                return

            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["Nº Venta", "Cliente", "Total", "Método Pago", "Estado", "Fecha/Hora"])

                for item in self.tabla_ventas.get_children():
                    values = self.tabla_ventas.item(item)['values']
                    writer.writerow(values)

            messagebox.showinfo("Exito", f"Datos exportados a {filename}")

            with conexion_segura() as conn:
                log_auditoria(
                    conn,
                    "ventas",
                    0,
                    "EXPORTAR",
                    self.usuario['usuario'],
                    f"Exportado a {filename}"
                )

        except Exception as e:
            messagebox.showerror("Error", f"Error exportando datos: {e}")

    def _obtener_rango_fechas(self):
        """Get date range based on active filter"""
        hoy = datetime.date.today()

        if self.filtro_activo == "hoy":
            return hoy, hoy
        elif self.filtro_activo == "ayer":
            ayer = hoy - datetime.timedelta(days=1)
            return ayer, ayer
        elif self.filtro_activo == "semana":
            inicio_semana = hoy - datetime.timedelta(days=hoy.weekday())
            return inicio_semana, hoy
        elif self.filtro_activo == "mes":
            inicio_mes = hoy.replace(day=1)
            return inicio_mes, hoy
        elif self.filtro_activo == "personalizado":
            try:
                fecha_inicio = datetime.datetime.strptime(
                    self.entrada_fecha_inicio.get(), "%Y-%m-%d"
                ).date()
                fecha_fin = datetime.datetime.strptime(
                    self.entrada_fecha_fin.get(), "%Y-%m-%d"
                ).date()
                return fecha_inicio, fecha_fin
            except Exception:
                return hoy, hoy

        return hoy, hoy

    def _actualizar_datos(self):
        """Refresca la tabla con paginación LIMIT/OFFSET."""
        self.tabla_ventas.delete(*self.tabla_ventas.get_children())
        self.tabla_detalle.delete(*self.tabla_detalle.get_children())

        fecha_inicio, fecha_fin = self._obtener_rango_fechas()

        try:
            with conexion_segura() as conn:
                # Contar total de registros para la paginación
                count = conn.execute("""
                    SELECT COUNT(*)
                    FROM ventas v
                    WHERE DATE(v.fecha_creacion) >= ?
                      AND DATE(v.fecha_creacion) <= ?
                """, (fecha_inicio, fecha_fin)).fetchone()[0]

                self._total_registros = count

                # Obtener sólo la página actual
                ventas = conn.execute("""
                    SELECT
                        v.id_venta,
                        v.cliente_nombre,
                        v.total,
                        v.metodo_pago,
                        v.estado,
                        v.fecha_creacion
                    FROM ventas v
                    WHERE DATE(v.fecha_creacion) >= ?
                      AND DATE(v.fecha_creacion) <= ?
                    ORDER BY v.fecha_creacion DESC
                    LIMIT ? OFFSET ?
                """, (fecha_inicio, fecha_fin,
                      self._por_pagina, self._pagina * self._por_pagina)).fetchall()

                # Para ventas MIXTO, obtener desglose de pagos
                mixto_ids = [v[0] for v in ventas if v[3] == 'MIXTO']
                mixto_splits = {}
                for id_v in mixto_ids:
                    filas = conn.execute(
                        "SELECT metodo_pago, valor FROM pagos WHERE id_venta = ? ORDER BY id_pago",
                        (id_v,)
                    ).fetchall()
                    partes = " + ".join(
                        f"{r['metodo_pago']}: {format_money(r['valor'])}" for r in filas
                    )
                    mixto_splits[id_v] = f"MIXTO ({partes})" if partes else "MIXTO"

                # Devoluciones del período para marcar ventas y mostrar filas
                ids_ventas = [v[0] for v in ventas]
                devs_por_venta = {}
                if ids_ventas:
                    placeholders = ','.join('?' * len(ids_ventas))
                    devs = conn.execute(f"""
                        SELECT id_venta, id_devolucion, monto, motivo, usuario, fecha
                        FROM devoluciones
                        WHERE id_venta IN ({placeholders})
                        ORDER BY fecha ASC
                    """, ids_ventas).fetchall()
                    for d in devs:
                        devs_por_venta.setdefault(d['id_venta'], []).append(d)

                for venta in ventas:
                    metodo_display = mixto_splits.get(venta[0], venta[3] or '—')
                    tiene_dev = venta[0] in devs_por_venta
                    estado_display = (venta[4] + ' (Dev)') if tiene_dev else venta[4]
                    tag = ('con_dev',) if tiene_dev else ()
                    self.tabla_ventas.insert(
                        "", tk.END,
                        values=(
                            venta[0],
                            venta[1] or '—',
                            format_money(venta[2]),
                            metodo_display,
                            estado_display,
                            str(venta[5])
                        ),
                        tags=tag
                    )
                    # Filas de devolución en rojo debajo de la venta
                    for d in devs_por_venta.get(venta[0], []):
                        self.tabla_ventas.insert(
                            "", tk.END,
                            values=(
                                '',
                                f"Dev: {d['motivo'][:30]}",
                                f"- {format_money(d['monto'])}",
                                'DEVOLUCION',
                                d['usuario'],
                                str(d['fecha'])
                            ),
                            tags=('devolucion',)
                        )

                # Solo recalcular KPIs si cambió el filtro de fechas
                filtro_actual = (fecha_inicio, fecha_fin)
                if filtro_actual != self._kpi_last_filter:
                    self._actualizar_kpis(conn, fecha_inicio, fecha_fin)
                    self._kpi_last_filter = filtro_actual

        except Exception as e:
            import logging
            logging.getLogger("pocitos").error(f"Error actualizando datos historial: {e}")

        self._actualizar_paginacion()

    def _actualizar_kpis(self, conn, fecha_inicio, fecha_fin):
        """Update KPI values"""
        try:
            # Total ventas
            query_total = """
                SELECT COALESCE(SUM(total), 0)
                FROM ventas
                WHERE DATE(fecha_creacion) >= ?
                  AND DATE(fecha_creacion) <= ?
                  AND estado != 'ANULADA'
            """
            total_ventas = conn.execute(query_total, (fecha_inicio, fecha_fin)).fetchone()[0]

            # Restar devoluciones del período
            total_devoluciones = conn.execute("""
                SELECT COALESCE(SUM(d.monto), 0)
                FROM devoluciones d
                JOIN ventas v ON d.id_venta = v.id_venta
                WHERE DATE(d.fecha) >= ? AND DATE(d.fecha) <= ?
            """, (fecha_inicio, fecha_fin)).fetchone()[0]
            total_ventas = max(0, total_ventas - total_devoluciones)

            self.kpi_total_valor.config(text=format_money(total_ventas))

            # Número de transacciones
            query_transacciones = """
                SELECT COUNT(*)
                FROM ventas
                WHERE DATE(fecha_creacion) >= ?
                  AND DATE(fecha_creacion) <= ?
                  AND estado != 'ANULADA'
            """
            num_transacciones = conn.execute(query_transacciones, (fecha_inicio, fecha_fin)).fetchone()[0]
            self.kpi_transacciones_valor.config(text=str(num_transacciones))

            # Ticket promedio
            ticket_promedio = total_ventas / num_transacciones if num_transacciones > 0 else 0
            self.kpi_promedio_valor.config(text=format_money(ticket_promedio))

            # Producto estrella
            query_producto = """
                SELECT pd.producto_nombre, SUM(pd.cantidad) as total_cantidad
                FROM venta_detalle pd
                JOIN ventas v ON pd.id_venta = v.id_venta
                WHERE DATE(v.fecha_creacion) >= ?
                  AND DATE(v.fecha_creacion) <= ?
                  AND v.estado != 'ANULADA'
                GROUP BY pd.producto_nombre
                ORDER BY total_cantidad DESC
                LIMIT 1
            """
            producto_resultado = conn.execute(query_producto, (fecha_inicio, fecha_fin)).fetchone()

            if producto_resultado:
                self.kpi_producto_valor.config(text=producto_resultado[0])
            else:
                self.kpi_producto_valor.config(text="—")

        except Exception as e:
            import logging
            logging.getLogger("pocitos").error(f"Error calculando KPIs: {e}")

    def get_frame(self):
        """Return the main frame for embedding in parent"""
        return self.main_frame

    def detener(self):
        try:
            self.tabla_ventas.unbind_all('<MouseWheel>')
            self.tabla_ventas.unbind_all('<Button-4>')
            self.tabla_ventas.unbind_all('<Button-5>')
        except Exception:
            pass
