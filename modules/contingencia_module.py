"""
modules/contingencia_module.py — Club Los Pocitos Azufrados
Permite a administradores registrar ventas realizadas en talonario físico
durante cortes de energía o fallas del sistema.

Las ventas quedan marcadas con es_contingencia=1 y el número del talonario físico.
El stock se descuenta normalmente ya que la venta ya ocurrió.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import datetime

from database.connection import conexion_segura, transaccion_atomica
from models.series import obtener_proximo_numero_venta
from utils.tema_corporativo import COLORES, FUENTES, crear_boton, aplicar_estilo_tabla, format_money
from utils.logger import log_auditoria


class ContingenciaModule:
    """Registro de ventas hechas en talonario durante una falla del sistema."""
    def __init__(self, parent, usuario):
        self.parent = parent
        self.usuario = usuario
        self._items = []          # lista de dicts: {id_producto, nombre, cantidad, precio, total}
        self._after_id = None

        self._build_ui()
        self._cargar_usuarios()
        self._cargar_historial()

    # ─────────────────────────────────────────────────────────────────
    #  UI principal
    # ─────────────────────────────────────────────────────────────────

    def _build_ui(self):
        """Arma la pantalla: aviso, formulario e historial."""
        self.parent.config(bg=COLORES['fondo'])

        # Header
        hdr = tk.Frame(self.parent, bg=COLORES['primario'], height=48)
        hdr.pack(fill='x')
        hdr.pack_propagate(False)
        tk.Label(hdr, text="Ingreso de Ventas por Contingencia",
                 font=FUENTES['encabezado'], fg=COLORES['texto_claro'],
                 bg=COLORES['primario']).pack(side='left', padx=16, pady=10)

        # Cuerpo con scroll
        canvas = tk.Canvas(self.parent, bg=COLORES['fondo'], highlightthickness=0)
        scroll = ttk.Scrollbar(self.parent, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right', fill='y')
        canvas.pack(fill='both', expand=True)

        body = tk.Frame(canvas, bg=COLORES['fondo'])
        self._win = canvas.create_window((0, 0), window=body, anchor='nw')
        canvas.bind('<Configure>', lambda e: canvas.itemconfig(self._win, width=e.width))
        body.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind_all('<MouseWheel>', lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), 'units'))
        self._canvas = canvas

        self._build_aviso(body)
        self._build_form(body)
        self._build_historial(body)

    def _build_aviso(self, parent):
        aviso = tk.Frame(parent, bg='#FFF9C4', highlightbackground='#F9A825',
                         highlightthickness=1)
        aviso.pack(fill='x', padx=16, pady=(12, 4))
        tk.Label(aviso,
                 text="! Use este modulo solo para registrar ventas del talonario fisico durante cortes de energia. "
                      "El stock se descontara al registrar.",
                 font=FUENTES['normal'], fg='#5D4037', bg='#FFF9C4',
                 wraplength=700, justify='left').pack(padx=12, pady=8)

    def _build_form(self, parent):
        """Formulario para capturar una venta de talonario."""
        card = tk.Frame(parent, bg=COLORES['fondo_card'],
                        highlightbackground=COLORES['borde'], highlightthickness=1)
        card.pack(fill='x', padx=16, pady=8)

        inner = tk.Frame(card, bg=COLORES['fondo_card'], padx=18, pady=14)
        inner.inner = inner
        inner.pack(fill='x')

        tk.Label(inner, text="Nueva Venta de Contingencia",
                 font=FUENTES['normal_bold'], fg=COLORES['primario'],
                 bg=COLORES['fondo_card']).grid(row=0, column=0, columnspan=6,
                                                sticky='w', pady=(0, 10))
        tk.Frame(inner, bg=COLORES['acento'], height=2).grid(
            row=1, column=0, columnspan=6, sticky='ew', pady=(0, 10))

        # Fila 1: fecha/hora, talonario, cajero
        tk.Label(inner, text="Fecha/Hora (YYYY-MM-DD HH:MM):",
                 font=FUENTES['normal'], fg=COLORES['texto'],
                 bg=COLORES['fondo_card']).grid(row=2, column=0, sticky='w', padx=(0, 6))
        self.entry_fecha = tk.Entry(inner, font=FUENTES['input'], width=20,
                                    relief='solid', bd=1)
        self.entry_fecha.insert(0, datetime.datetime.now().strftime('%Y-%m-%d %H:%M'))
        self.entry_fecha.grid(row=2, column=1, sticky='w', padx=(0, 20), ipady=4)

        tk.Label(inner, text="N° Talonario:",
                 font=FUENTES['normal'], fg=COLORES['texto'],
                 bg=COLORES['fondo_card']).grid(row=2, column=2, sticky='w', padx=(0, 6))
        self.entry_talonario = tk.Entry(inner, font=FUENTES['input'], width=12,
                                        relief='solid', bd=1)
        self.entry_talonario.grid(row=2, column=3, sticky='w', padx=(0, 20), ipady=4)

        tk.Label(inner, text="Cajero:",
                 font=FUENTES['normal'], fg=COLORES['texto'],
                 bg=COLORES['fondo_card']).grid(row=2, column=4, sticky='w', padx=(0, 6))
        self.combo_cajero = ttk.Combobox(inner, font=FUENTES['input'], width=18,
                                          state='readonly')
        self.combo_cajero.grid(row=2, column=5, sticky='w', ipady=3)

        # Fila 2: separador y título productos
        tk.Label(inner, text="Productos",
                 font=FUENTES['normal_bold'], fg=COLORES['primario'],
                 bg=COLORES['fondo_card']).grid(row=3, column=0, columnspan=6,
                                                sticky='w', pady=(14, 4))

        # Fila 3: búsqueda de producto
        buscar_f = tk.Frame(inner, bg=COLORES['fondo_card'])
        buscar_f.grid(row=4, column=0, columnspan=6, sticky='ew', pady=(0, 6))

        tk.Label(buscar_f, text="Buscar producto:",
                 font=FUENTES['normal'], fg=COLORES['texto'],
                 bg=COLORES['fondo_card']).pack(side='left', padx=(0, 6))
        self.entry_buscar = tk.Entry(buscar_f, font=FUENTES['input'], width=28,
                                     relief='solid', bd=1)
        self.entry_buscar.pack(side='left', ipady=4, padx=(0, 6))
        self.entry_buscar.bind('<Return>', lambda e: self._mostrar_resultados())

        tk.Label(buscar_f, text="Cant:",
                 font=FUENTES['normal'], fg=COLORES['texto'],
                 bg=COLORES['fondo_card']).pack(side='left', padx=(10, 4))
        self.entry_cant = tk.Entry(buscar_f, font=FUENTES['input'], width=5,
                                   relief='solid', bd=1)
        self.entry_cant.insert(0, '1')
        self.entry_cant.pack(side='left', ipady=4, padx=(0, 6))

        tk.Label(buscar_f, text="Precio:",
                 font=FUENTES['normal'], fg=COLORES['texto'],
                 bg=COLORES['fondo_card']).pack(side='left', padx=(10, 4))
        self.entry_precio = tk.Entry(buscar_f, font=FUENTES['input'], width=10,
                                     relief='solid', bd=1)
        self.entry_precio.pack(side='left', ipady=4, padx=(0, 10))

        crear_boton(buscar_f, "Buscar", self._mostrar_resultados, tipo='secundario').pack(side='left', padx=2)
        crear_boton(buscar_f, "+ Agregar", self._agregar_item_seleccionado, tipo='primario').pack(side='left', padx=2)

        # Listbox de resultados de búsqueda
        res_f = tk.Frame(inner, bg=COLORES['fondo_card'])
        res_f.grid(row=5, column=0, columnspan=6, sticky='ew', pady=(0, 4))
        self.listbox_res = tk.Listbox(res_f, font=FUENTES['normal'], height=3,
                                      relief='solid', bd=1, selectmode='single',
                                      bg='white', fg=COLORES['texto'])
        self.listbox_res.pack(fill='x')
        self.listbox_res.bind('<Double-Button-1>', lambda e: self._agregar_item_seleccionado())
        self._resultados_bd = []   # cache de filas de BD para el listbox

        # Carrito de ítems
        cart_f = tk.Frame(inner, bg=COLORES['fondo_card'])
        cart_f.grid(row=6, column=0, columnspan=6, sticky='ew', pady=(4, 0))
        cols = ('Producto', 'Cant', 'Precio', 'Subtotal')
        self.tree_items = ttk.Treeview(cart_f, columns=cols, show='headings', height=5)
        aplicar_estilo_tabla(self.tree_items)
        for c, w in zip(cols, (260, 50, 90, 90)):
            self.tree_items.heading(c, text=c)
            self.tree_items.column(c, width=w, anchor='center' if c != 'Producto' else 'w')
        self.tree_items.pack(fill='x')

        crear_boton(cart_f, "Quitar seleccionado", self._quitar_item, tipo='error').pack(
            anchor='e', pady=(4, 0))

        # Fila 4: pago, cliente, notas, total
        pago_f = tk.Frame(inner, bg=COLORES['fondo_card'])
        pago_f.grid(row=7, column=0, columnspan=6, sticky='ew', pady=(10, 0))

        tk.Label(pago_f, text="Metodo de pago:",
                 font=FUENTES['normal'], fg=COLORES['texto'],
                 bg=COLORES['fondo_card']).pack(side='left', padx=(0, 6))
        self.combo_metodo = ttk.Combobox(pago_f, font=FUENTES['input'], width=14, state='readonly',
                                          values=['EFECTIVO', 'NEQUI', 'DAVIPLATA',
                                                  'TULLAVE', 'BANCOLOMBIA', 'TRANSFERENCIA'])
        self.combo_metodo.current(0)
        self.combo_metodo.pack(side='left', ipady=3, padx=(0, 20))

        tk.Label(pago_f, text="Cliente (opcional):",
                 font=FUENTES['normal'], fg=COLORES['texto'],
                 bg=COLORES['fondo_card']).pack(side='left', padx=(0, 6))
        self.entry_cliente = tk.Entry(pago_f, font=FUENTES['input'], width=20,
                                      relief='solid', bd=1)
        self.entry_cliente.pack(side='left', ipady=4, padx=(0, 20))

        tk.Label(pago_f, text="Notas:",
                 font=FUENTES['normal'], fg=COLORES['texto'],
                 bg=COLORES['fondo_card']).pack(side='left', padx=(0, 6))
        self.entry_notas = tk.Entry(pago_f, font=FUENTES['input'], width=22,
                                    relief='solid', bd=1)
        self.entry_notas.pack(side='left', ipady=4)

        # Total y botón registrar
        total_f = tk.Frame(inner, bg=COLORES['fondo_card'])
        total_f.grid(row=8, column=0, columnspan=6, sticky='e', pady=(10, 0))

        tk.Label(total_f, text="TOTAL:",
                 font=FUENTES['normal_bold'], fg=COLORES['texto'],
                 bg=COLORES['fondo_card']).pack(side='left', padx=(0, 8))
        self.lbl_total = tk.Label(total_f, text="$ 0",
                                  font=FUENTES['kpi_valor'], fg=COLORES['primario'],
                                  bg=COLORES['fondo_card'])
        self.lbl_total.pack(side='left', padx=(0, 20))
        crear_boton(total_f, "Registrar Venta", self._registrar_venta, tipo='exito').pack(side='left')

    def _build_historial(self, parent):
        """Lista de ventas de contingencia ya registradas."""
        card = tk.Frame(parent, bg=COLORES['fondo_card'],
                        highlightbackground=COLORES['borde'], highlightthickness=1)
        card.pack(fill='both', expand=True, padx=16, pady=(4, 16))

        hdr = tk.Frame(card, bg=COLORES['fondo_card'], padx=18, pady=10)
        hdr.pack(fill='x')
        tk.Label(hdr, text="Historial de Ventas Ingresadas por Contingencia",
                 font=FUENTES['normal_bold'], fg=COLORES['primario'],
                 bg=COLORES['fondo_card']).pack(side='left')
        crear_boton(hdr, "Actualizar", self._cargar_historial, tipo='secundario').pack(side='right')

        cols = ('Fecha/Hora', 'N° Talonario', 'N° Sistema', 'Cajero', 'Metodo', 'Items', 'Total')
        self.tree_hist = ttk.Treeview(card, columns=cols, show='headings', height=8)
        aplicar_estilo_tabla(self.tree_hist)
        anchos = (130, 100, 130, 120, 110, 50, 90)
        for c, w in zip(cols, anchos):
            self.tree_hist.heading(c, text=c)
            self.tree_hist.column(c, width=w, anchor='center')

        sb = ttk.Scrollbar(card, orient='vertical', command=self.tree_hist.yview)
        self.tree_hist.configure(yscrollcommand=sb.set)
        sb.pack(side='right', fill='y')
        self.tree_hist.pack(fill='both', expand=True, padx=10, pady=(0, 10))

        # Panel de detalle al seleccionar una fila
        det_frame = tk.Frame(card, bg=COLORES['fondo_card'], padx=18, pady=6)
        det_frame.pack(fill='x')
        tk.Label(det_frame, text="Detalle del pedido seleccionado:",
                 font=FUENTES['normal_bold'], fg=COLORES['texto_secundario'],
                 bg=COLORES['fondo_card']).pack(anchor='w')
        self.lbl_det_cont = tk.Label(det_frame, text="(Haga clic en una fila para ver los productos)",
                                     font=FUENTES['pequena'], fg=COLORES['texto_secundario'],
                                     bg=COLORES['fondo_card'], justify='left', wraplength=700)
        self.lbl_det_cont.pack(anchor='w', pady=(2, 0))

        def _on_sel(event):
            sel = self.tree_hist.selection()
            if not sel:
                return
            vals = self.tree_hist.item(sel[0])['values']
            num_venta = vals[2]  # N° Sistema
            try:
                with conexion_segura() as conn:
                    items = conn.execute("""
                        SELECT p.nombre, vd.cantidad, vd.precio_unitario, vd.total_linea
                        FROM venta_detalle vd
                        JOIN productos p ON p.id_producto = vd.id_producto
                        JOIN ventas v ON v.id_venta = vd.id_venta
                        WHERE v.numero_venta = ?
                        ORDER BY vd.id_detalle
                    """, (str(num_venta),)).fetchall()
            except Exception:
                items = []
            if items:
                lineas = [f"  {r['cantidad']}x {r['nombre']}  —  {format_money(r['total_linea'])}"
                          for r in items]
                texto = "\n".join(lineas)
            else:
                texto = "  (sin detalle de productos registrado)"
            self.lbl_det_cont.config(text=texto, fg=COLORES['texto'])

        self.tree_hist.bind('<<TreeviewSelect>>', _on_sel)

    # ─────────────────────────────────────────────────────────────────
    #  Carga de datos
    # ─────────────────────────────────────────────────────────────────

    def _cargar_usuarios(self):
        """Llena el combo de cajeros con usuarios activos."""
        try:
            with conexion_segura() as conn:
                rows = conn.execute(
                    "SELECT usuario, nombre_completo FROM usuarios WHERE activo = 1 ORDER BY nombre_completo"
                ).fetchall()
            self._usuarios = {f"{r['nombre_completo']} ({r['usuario']})": r['usuario'] for r in rows}
            self.combo_cajero['values'] = list(self._usuarios.keys())
            # Pre-seleccionar al usuario actual
            nombre_actual = f"{self.usuario.get('nombre_completo', '')} ({self.usuario.get('usuario', '')})"
            if nombre_actual in self._usuarios:
                self.combo_cajero.set(nombre_actual)
            elif self.combo_cajero['values']:
                self.combo_cajero.current(0)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudieron cargar los usuarios: {e}")

    def _cargar_historial(self):
        """Recarga el historial de ventas de contingencia."""
        try:
            for row in self.tree_hist.get_children():
                self.tree_hist.delete(row)
            with conexion_segura() as conn:
                rows = conn.execute("""
                    SELECT v.fecha_creacion, v.numero_talonario, v.numero_venta,
                           v.usuario_nombre, v.metodo_pago, v.total,
                           (SELECT COUNT(*) FROM venta_detalle WHERE id_venta = v.id_venta) AS n_items
                    FROM ventas v
                    WHERE v.es_contingencia = 1
                    ORDER BY v.fecha_creacion DESC
                    LIMIT 200
                """).fetchall()
            for r in rows:
                self.tree_hist.insert('', 'end', values=(
                    str(r['fecha_creacion'])[:16],
                    r['numero_talonario'] or '-',
                    r['numero_venta'],
                    r['usuario_nombre'] or '-',
                    r['metodo_pago'] or '-',
                    r['n_items'],
                    format_money(r['total']),
                ))
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo cargar el historial: {e}")

    # ─────────────────────────────────────────────────────────────────
    #  Gestión del carrito
    # ─────────────────────────────────────────────────────────────────

    def _mostrar_resultados(self):
        """Busca productos por nombre o código de barras y llena el listbox."""
        texto = self.entry_buscar.get().strip()
        if not texto:
            return
        try:
            with conexion_segura() as conn:
                rows = conn.execute("""
                    SELECT id_producto, nombre, precio_venta, codigo_barras, stock_actual
                    FROM productos
                    WHERE activo = 1 AND es_boleta_entrada = 0
                      AND (LOWER(nombre) LIKE ? OR codigo_barras = ?)
                    ORDER BY nombre
                    LIMIT 10
                """, (f'%{texto.lower()}%', texto)).fetchall()
            self.listbox_res.delete(0, 'end')
            self._resultados_bd = list(rows)
            for r in rows:
                self.listbox_res.insert('end',
                    f"{r['nombre']}  —  {format_money(r['precio_venta'])}  (stock: {r['stock_actual']})")
            if rows:
                self.listbox_res.selection_set(0)
                # Pre-llenar precio con el del primer resultado
                self.entry_precio.delete(0, 'end')
                self.entry_precio.insert(0, str(int(rows[0]['precio_venta'])))
        except Exception as e:
            messagebox.showerror("Error", f"Error al buscar: {e}")

    def _agregar_item_seleccionado(self):
        """Agrega el producto seleccionado en el listbox al carrito."""
        sel = self.listbox_res.curselection()
        if not sel:
            messagebox.showwarning("Sin seleccion", "Seleccione un producto de la lista primero.")
            return

        prod = self._resultados_bd[sel[0]]

        # Validar cantidad
        try:
            cant = int(self.entry_cant.get().strip())
            if cant <= 0:
                raise ValueError
        except ValueError:
            messagebox.showwarning("Cantidad invalida", "La cantidad debe ser un numero entero positivo.")
            return

        # Validar precio
        try:
            precio = float(self.entry_precio.get().strip().replace('.', '').replace(',', '.'))
            if precio < 0:
                raise ValueError
        except ValueError:
            messagebox.showwarning("Precio invalido", "El precio debe ser un numero positivo.")
            return

        # Agregar al carrito (permitir mismo producto varias veces)
        self._items.append({
            'id_producto': prod['id_producto'],
            'nombre': prod['nombre'],
            'cantidad': cant,
            'precio': precio,
            'total': cant * precio,
        })
        self._refrescar_carrito()

        # Limpiar búsqueda
        self.entry_buscar.delete(0, 'end')
        self.entry_cant.delete(0, 'end')
        self.entry_cant.insert(0, '1')
        self.entry_precio.delete(0, 'end')
        self.listbox_res.delete(0, 'end')
        self._resultados_bd = []

    def _quitar_item(self):
        """Elimina el ítem seleccionado del carrito."""
        sel = self.tree_items.selection()
        if not sel:
            return
        idx = self.tree_items.index(sel[0])
        if 0 <= idx < len(self._items):
            self._items.pop(idx)
        self._refrescar_carrito()

    def _refrescar_carrito(self):
        """Actualiza el Treeview del carrito y el label de total."""
        for row in self.tree_items.get_children():
            self.tree_items.delete(row)
        for item in self._items:
            self.tree_items.insert('', 'end', values=(
                item['nombre'],
                item['cantidad'],
                format_money(item['precio']),
                format_money(item['total']),
            ))
        total = sum(i['total'] for i in self._items)
        self.lbl_total.config(text=format_money(total))

    # ─────────────────────────────────────────────────────────────────
    #  Registro de la venta
    # ─────────────────────────────────────────────────────────────────

    def _registrar_venta(self):
        """Valida y guarda la venta de contingencia en la BD."""
        # Validaciones
        if not self._items:
            messagebox.showwarning("Sin productos", "Agregue al menos un producto.")
            return

        talonario = self.entry_talonario.get().strip()
        if not talonario:
            messagebox.showwarning("Talonario requerido", "Ingrese el numero del talonario fisico.")
            self.entry_talonario.focus_set()
            return

        fecha_str = self.entry_fecha.get().strip()
        try:
            datetime.datetime.strptime(fecha_str, '%Y-%m-%d %H:%M')
        except ValueError:
            messagebox.showwarning("Fecha invalida", "Use el formato YYYY-MM-DD HH:MM (ej. 2026-03-23 14:30).")
            self.entry_fecha.focus_set()
            return

        cajero_display = self.combo_cajero.get()
        if not cajero_display:
            messagebox.showwarning("Cajero requerido", "Seleccione el cajero que atendio la venta.")
            return
        cajero_usuario = self._usuarios.get(cajero_display, cajero_display)

        metodo = self.combo_metodo.get()
        cliente = self.entry_cliente.get().strip()
        notas = self.entry_notas.get().strip()
        total = sum(i['total'] for i in self._items)

        if not messagebox.askyesno("Confirmar registro",
                                   f"Registrar venta de contingencia:\n"
                                   f"  Talonario: {talonario}\n"
                                   f"  Fecha/Hora: {fecha_str}\n"
                                   f"  Items: {len(self._items)}\n"
                                   f"  Total: {format_money(total)}\n\n"
                                   f"El stock sera descontado. Continuar?"):
            return

        try:
            numero_venta = obtener_proximo_numero_venta()
            items_snapshot = list(self._items)

            with transaccion_atomica() as conn:
                conn.execute("""
                    INSERT INTO ventas
                        (numero_venta, tipo, estado, cliente_nombre, subtotal, total,
                         total_pagado, saldo_pendiente, metodo_pago, notas,
                         id_usuario, usuario_nombre, fecha_creacion, fecha_cierre,
                         fecha_pago, es_contingencia, numero_talonario)
                    VALUES (?, 'normal', 'PAGADA', ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?, ?, 1, ?)
                """, (
                    numero_venta, cliente or None, total, total, total,
                    metodo, notas or f"Contingencia - talonario {talonario}",
                    self.usuario['id_usuario'], cajero_usuario,
                    fecha_str, fecha_str, fecha_str, talonario,
                ))
                id_venta = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

                for item in items_snapshot:
                    conn.execute("""
                        INSERT INTO venta_detalle
                            (id_venta, id_producto, producto_nombre, cantidad,
                             precio_unitario, total_linea)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (id_venta, item['id_producto'], item['nombre'],
                          item['cantidad'], item['precio'], item['total']))

                    # Descontar stock
                    conn.execute("""
                        UPDATE productos SET stock_actual = stock_actual - ?
                        WHERE id_producto = ?
                    """, (item['cantidad'], item['id_producto']))

                    # Registrar movimiento de inventario
                    conn.execute("""
                        INSERT INTO movimientos_inventario
                            (id_producto, tipo, cantidad, motivo, id_referencia, usuario)
                        VALUES (?, 'VENTA', ?, ?, ?, ?)
                    """, (item['id_producto'], -item['cantidad'],
                          f"Venta contingencia {numero_venta} (talonario {talonario})",
                          id_venta, cajero_usuario))

                # Registrar movimiento de caja si hay caja abierta
                caja = conn.execute(
                    "SELECT id_caja FROM caja_diaria WHERE estado = 'ABIERTA' ORDER BY id_caja DESC LIMIT 1"
                ).fetchone()
                if caja:
                    conn.execute("""
                        INSERT INTO movimientos_caja
                            (id_caja, tipo, concepto, monto, metodo_pago, id_referencia, usuario)
                        VALUES (?, 'INGRESO', ?, ?, ?, ?, ?)
                    """, (caja['id_caja'],
                          f"Venta contingencia {numero_venta} (talonario {talonario})",
                          total, metodo, id_venta, cajero_usuario))

                log_auditoria(conn, 'ventas', id_venta, 'CREAR',
                              self.usuario['usuario'],
                              f"Venta contingencia registrada. Talonario: {talonario}. "
                              f"Fecha original: {fecha_str}. Total: {total}")

            messagebox.showinfo("Registrada",
                                f"Venta registrada exitosamente.\nNumero: {numero_venta}")

            # Limpiar formulario
            self._items.clear()
            self._refrescar_carrito()
            self.entry_talonario.delete(0, 'end')
            self.entry_cliente.delete(0, 'end')
            self.entry_notas.delete(0, 'end')
            self.entry_fecha.delete(0, 'end')
            self.entry_fecha.insert(0, datetime.datetime.now().strftime('%Y-%m-%d %H:%M'))
            self._cargar_historial()

        except Exception as e:
            messagebox.showerror("Error al registrar", str(e))

    # ─────────────────────────────────────────────────────────────────
    #  Ciclo de vida
    # ─────────────────────────────────────────────────────────────────

    def detener(self):
        try:
            self._canvas.unbind_all('<MouseWheel>')
            self._canvas.unbind_all('<Button-4>')
            self._canvas.unbind_all('<Button-5>')
        except Exception:
            pass
