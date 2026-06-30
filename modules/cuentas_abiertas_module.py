"""
Módulo de Consumo de Empleados - Club Los Pocitos Azufrados
Reemplaza Cuentas Abiertas: registro interno sin cobro, descuenta inventario.
"""
import tkinter as tk
from tkinter import ttk, messagebox
import logging

from utils.tema_corporativo import (COLORES, FUENTES, crear_boton,
                                    format_money, aplicar_estilo_tabla)
from database.connection import conexion_segura, transaccion_atomica
from utils.logger import log_auditoria

_log = logging.getLogger("pocitos")


class CuentasAbiertasModule:
    """Consumo de empleados: registra productos consumidos sin cobro."""

    def __init__(self, parent, usuario):
        self.parent = parent
        self.usuario = usuario
        self.auto_refresh = True
        self._after_id = None
        self._id_consumo_sel = None
        self.empleados = []

        self._asegurar_tablas()
        self._crear_interfaz()
        self._cargar_empleados()
        self._cargar_consumos()
        self._iniciar_refresh()

    # ── Garantizar tablas ────────────────────────────────────────────────────

    def _asegurar_tablas(self):
        try:
            with transaccion_atomica() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS nomina_empleados (
                        id_empleado INTEGER PRIMARY KEY AUTOINCREMENT,
                        nombre TEXT NOT NULL,
                        tarifa_normal REAL DEFAULT 0,
                        tarifa_festivo REAL DEFAULT 0,
                        activo INTEGER DEFAULT 1,
                        fecha_creacion TEXT DEFAULT (datetime('now','localtime'))
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS consumos_empleados (
                        id_consumo INTEGER PRIMARY KEY AUTOINCREMENT,
                        id_empleado INTEGER NOT NULL,
                        fecha TEXT DEFAULT (datetime('now','localtime')),
                        total REAL DEFAULT 0,
                        estado TEXT DEFAULT 'ABIERTO'
                            CHECK(estado IN ('ABIERTO','CERRADO')),
                        usuario TEXT,
                        notas TEXT
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS consumo_detalle (
                        id_detalle INTEGER PRIMARY KEY AUTOINCREMENT,
                        id_consumo INTEGER NOT NULL,
                        id_producto INTEGER,
                        producto_nombre TEXT NOT NULL,
                        cantidad REAL DEFAULT 1,
                        precio_unitario REAL DEFAULT 0,
                        total_linea REAL DEFAULT 0
                    )
                """)
        except Exception as e:
            _log.error(f"Error creando tablas consumo: {e}")

    # ── Interfaz ─────────────────────────────────────────────────────────────

    def _crear_interfaz(self):
        self.parent.configure(bg=COLORES['fondo'])

        hdr = tk.Frame(self.parent, bg=COLORES['primario'], pady=10)
        hdr.pack(fill='x')
        tk.Label(hdr, text="Consumo de Empleados",
                 font=FUENTES['titulo'], fg=COLORES['texto_claro'],
                 bg=COLORES['primario']).pack()
        tk.Label(hdr, text="Registro interno sin cobro — descuenta inventario",
                 font=FUENTES['normal'], fg=COLORES['acento'],
                 bg=COLORES['primario']).pack()

        kpi_frame = tk.Frame(self.parent, bg=COLORES['fondo'], pady=6)
        kpi_frame.pack(fill='x', padx=12)
        self.lbl_kpi_abiertos = self._kpi(kpi_frame, "Tabs abiertos hoy", "0")
        self.lbl_kpi_cerrados = self._kpi(kpi_frame, "Cerrados hoy", "0")
        self.lbl_kpi_total    = self._kpi(kpi_frame, "Total consumido hoy", "$ 0")

        body = tk.Frame(self.parent, bg=COLORES['fondo'])
        body.pack(fill='both', expand=True, padx=12, pady=6)
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=2)
        body.rowconfigure(0, weight=1)
        self._panel_izq(body)
        self._panel_der(body)

    def _kpi(self, parent, titulo, valor_inicial):
        card = tk.Frame(parent, bg=COLORES['fondo_card'], relief='solid', bd=1,
                        padx=10, pady=6)
        card.pack(side='left', expand=True, fill='both', padx=4)
        tk.Frame(card, bg=COLORES['primario'], height=3).pack(fill='x')
        tk.Label(card, text=titulo, font=FUENTES['pequena'],
                 fg=COLORES['texto_secundario'],
                 bg=COLORES['fondo_card']).pack()
        lbl = tk.Label(card, text=valor_inicial, font=FUENTES['normal_bold'],
                       fg=COLORES['primario'], bg=COLORES['fondo_card'])
        lbl.pack()
        return lbl

    def _panel_izq(self, parent):
        frame = tk.Frame(parent, bg=COLORES['fondo_card'], relief='solid', bd=1)
        frame.grid(row=0, column=0, sticky='nsew', padx=(0, 6))
        frame.rowconfigure(2, weight=1)
        frame.rowconfigure(4, weight=1)
        frame.columnconfigure(0, weight=1)

        toolbar = tk.Frame(frame, bg=COLORES['primario'], pady=6)
        toolbar.grid(row=0, column=0, columnspan=2, sticky='ew')
        tk.Label(toolbar, text="Tabs del dia",
                 font=FUENTES['subtitulo'], fg=COLORES['texto_claro'],
                 bg=COLORES['primario']).pack(anchor='w', padx=8)
        btn_row = tk.Frame(toolbar, bg=COLORES['primario'])
        btn_row.pack(anchor='w', padx=6, pady=4)
        crear_boton(btn_row, "+ Nueva tab",   self._nueva_tab,        tipo='exito').pack(side='left', padx=2)
        crear_boton(btn_row, "+ Empleado",    self._agregar_empleado, tipo='outline').pack(side='left', padx=2)
        crear_boton(btn_row, "Actualizar",    self._cargar_consumos,  tipo='secundario').pack(side='left', padx=2)

        tk.Label(frame, text="ABIERTOS", font=FUENTES['pequena'],
                 fg=COLORES['texto_secundario'],
                 bg=COLORES['fondo_card']).grid(row=1, column=0, sticky='w', padx=8, pady=(6, 2))

        self.tree_abiertos = ttk.Treeview(
            frame, columns=('empleado', 'hora', 'items', 'total'),
            show='headings', height=8)
        self.tree_abiertos.heading('empleado', text='Empleado')
        self.tree_abiertos.heading('hora',     text='Desde')
        self.tree_abiertos.heading('items',    text='Items')
        self.tree_abiertos.heading('total',    text='Total')
        self.tree_abiertos.column('empleado', width=140)
        self.tree_abiertos.column('hora',     width=55, anchor='center')
        self.tree_abiertos.column('items',    width=45, anchor='center')
        self.tree_abiertos.column('total',    width=90, anchor='e')
        aplicar_estilo_tabla(self.tree_abiertos)
        sb_a = ttk.Scrollbar(frame, orient='vertical', command=self.tree_abiertos.yview)
        self.tree_abiertos.configure(yscrollcommand=sb_a.set)
        sb_a.grid(row=2, column=1, sticky='ns')
        self.tree_abiertos.grid(row=2, column=0, sticky='nsew', padx=(4, 0))
        self.tree_abiertos.bind('<<TreeviewSelect>>', self._on_select_abierto)

        tk.Label(frame, text="CERRADOS HOY", font=FUENTES['pequena'],
                 fg=COLORES['texto_secundario'],
                 bg=COLORES['fondo_card']).grid(row=3, column=0, sticky='w', padx=8, pady=(8, 2))

        self.tree_cerrados = ttk.Treeview(
            frame, columns=('empleado', 'hora', 'total'),
            show='headings', height=5)
        self.tree_cerrados.heading('empleado', text='Empleado')
        self.tree_cerrados.heading('hora',     text='Hora cierre')
        self.tree_cerrados.heading('total',    text='Total')
        self.tree_cerrados.column('empleado', width=150)
        self.tree_cerrados.column('hora',     width=75, anchor='center')
        self.tree_cerrados.column('total',    width=90, anchor='e')
        aplicar_estilo_tabla(self.tree_cerrados)
        sb_c = ttk.Scrollbar(frame, orient='vertical', command=self.tree_cerrados.yview)
        self.tree_cerrados.configure(yscrollcommand=sb_c.set)
        sb_c.grid(row=4, column=1, sticky='ns')
        self.tree_cerrados.grid(row=4, column=0, sticky='nsew', padx=(4, 0), pady=(0, 6))

    def _panel_der(self, parent):
        frame = tk.Frame(parent, bg=COLORES['fondo_card'], relief='solid', bd=1)
        frame.grid(row=0, column=1, sticky='nsew')
        frame.rowconfigure(2, weight=1)

        hdr = tk.Frame(frame, bg=COLORES['primario'], pady=6)
        hdr.pack(fill='x')
        self.lbl_empleado_sel = tk.Label(
            hdr, text="Seleccione una tab de la lista",
            font=FUENTES['subtitulo'], fg=COLORES['texto_claro'],
            bg=COLORES['primario'])
        self.lbl_empleado_sel.pack(padx=8)

        btn_frame = tk.Frame(frame, bg=COLORES['fondo_card'], pady=6)
        btn_frame.pack(fill='x', padx=8)
        self.btn_agregar = crear_boton(btn_frame, "+ Agregar producto",
                                       self._agregar_item, tipo='primario')
        self.btn_agregar.pack(side='left', padx=(0, 6))
        self.btn_cerrar = crear_boton(btn_frame, "Cerrar consumo del dia",
                                      self._cerrar_consumo, tipo='error')
        self.btn_cerrar.pack(side='left')
        self.btn_agregar.config(state='disabled')
        self.btn_cerrar.config(state='disabled')

        self.tree_det = ttk.Treeview(
            frame, columns=('producto', 'cant', 'precio', 'total'),
            show='headings')
        self.tree_det.heading('producto', text='Producto')
        self.tree_det.heading('cant',     text='Cant.')
        self.tree_det.heading('precio',   text='Precio unit.')
        self.tree_det.heading('total',    text='Total')
        self.tree_det.column('producto', width=260)
        self.tree_det.column('cant',     width=55,  anchor='center')
        self.tree_det.column('precio',   width=110, anchor='e')
        self.tree_det.column('total',    width=110, anchor='e')
        aplicar_estilo_tabla(self.tree_det)
        sb_d = ttk.Scrollbar(frame, orient='vertical', command=self.tree_det.yview)
        self.tree_det.configure(yscrollcommand=sb_d.set)
        sb_d.pack(side='right', fill='y')
        self.tree_det.pack(fill='both', expand=True, padx=4, pady=4)

        total_bar = tk.Frame(frame, bg=COLORES['fondo_card'], pady=4)
        total_bar.pack(fill='x', padx=8)
        tk.Label(total_bar, text="Total consumo:",
                 font=FUENTES['normal_bold'], bg=COLORES['fondo_card'],
                 fg=COLORES['texto']).pack(side='left')
        self.lbl_total_det = tk.Label(total_bar, text="$ 0",
                                      font=FUENTES['normal_bold'],
                                      bg=COLORES['fondo_card'],
                                      fg=COLORES['primario'])
        self.lbl_total_det.pack(side='right')

    # ── Carga de datos ───────────────────────────────────────────────────────

    def _cargar_empleados(self):
        try:
            with conexion_segura() as conn:
                rows = conn.execute(
                    "SELECT id_empleado, nombre FROM nomina_empleados "
                    "WHERE activo=1 ORDER BY nombre"
                ).fetchall()
            self.empleados = [dict(r) for r in rows]
        except Exception as e:
            _log.error(f"Error cargando empleados: {e}")

    def _cargar_consumos(self):
        try:
            with conexion_segura() as conn:
                rows = conn.execute("""
                    SELECT c.id_consumo, c.estado, c.total, c.fecha,
                           COALESCE(e.nombre, 'Empleado') AS nombre_empleado,
                           (SELECT COUNT(*) FROM consumo_detalle d
                            WHERE d.id_consumo = c.id_consumo) AS n_items
                    FROM consumos_empleados c
                    LEFT JOIN nomina_empleados e ON e.id_empleado = c.id_empleado
                    WHERE DATE(c.fecha) = date('now','localtime')
                    ORDER BY c.estado, c.fecha DESC
                """).fetchall()
        except Exception as e:
            _log.error(f"Error cargando consumos: {e}")
            return

        abiertos = [r for r in rows if r['estado'] == 'ABIERTO']
        cerrados = [r for r in rows if r['estado'] == 'CERRADO']

        self.lbl_kpi_abiertos.config(text=str(len(abiertos)))
        self.lbl_kpi_cerrados.config(text=str(len(cerrados)))
        self.lbl_kpi_total.config(text=format_money(sum(r['total'] for r in rows)))

        for item in self.tree_abiertos.get_children():
            self.tree_abiertos.delete(item)
        for r in abiertos:
            hora = r['fecha'][11:16] if r['fecha'] else ''
            self.tree_abiertos.insert('', 'end', iid=str(r['id_consumo']),
                values=(r['nombre_empleado'], hora, r['n_items'],
                        format_money(r['total'])))

        for item in self.tree_cerrados.get_children():
            self.tree_cerrados.delete(item)
        for r in cerrados:
            hora = r['fecha'][11:16] if r['fecha'] else ''
            self.tree_cerrados.insert('', 'end',
                values=(r['nombre_empleado'], hora, format_money(r['total'])))

        if self._id_consumo_sel:
            ids_abiertos = {str(r['id_consumo']) for r in abiertos}
            if str(self._id_consumo_sel) not in ids_abiertos:
                self._limpiar_seleccion()

    def _cargar_detalle(self, id_consumo):
        try:
            with conexion_segura() as conn:
                rows = conn.execute("""
                    SELECT producto_nombre, cantidad, precio_unitario, total_linea
                    FROM consumo_detalle WHERE id_consumo = ?
                    ORDER BY id_detalle
                """, (id_consumo,)).fetchall()
                total = conn.execute(
                    "SELECT COALESCE(SUM(total_linea),0) FROM consumo_detalle "
                    "WHERE id_consumo=?", (id_consumo,)
                ).fetchone()[0]
        except Exception as e:
            _log.error(f"Error cargando detalle: {e}")
            return

        for item in self.tree_det.get_children():
            self.tree_det.delete(item)
        for i, r in enumerate(rows):
            tag = 'par' if i % 2 == 0 else 'impar'
            self.tree_det.insert('', 'end', tags=(tag,), values=(
                r['producto_nombre'], r['cantidad'],
                format_money(r['precio_unitario']),
                format_money(r['total_linea'])))
        self.lbl_total_det.config(text=format_money(total))

    # ── Eventos ──────────────────────────────────────────────────────────────

    def _on_select_abierto(self, event=None):
        sel = self.tree_abiertos.selection()
        if not sel:
            return
        id_consumo = int(sel[0])
        self._id_consumo_sel = id_consumo
        vals = self.tree_abiertos.item(sel[0], 'values')
        nombre = vals[0] if vals else ''
        self.lbl_empleado_sel.config(text=f"Tab de: {nombre}")
        self.btn_agregar.config(state='normal')
        self.btn_cerrar.config(state='normal')
        self._cargar_detalle(id_consumo)

    def _limpiar_seleccion(self):
        self._id_consumo_sel = None
        self.lbl_empleado_sel.config(text="Seleccione una tab de la lista")
        self.btn_agregar.config(state='disabled')
        self.btn_cerrar.config(state='disabled')
        for item in self.tree_det.get_children():
            self.tree_det.delete(item)
        self.lbl_total_det.config(text="$ 0")

    # ── Acciones ─────────────────────────────────────────────────────────────

    def _nueva_tab(self):
        if not self.empleados:
            messagebox.showwarning("Sin empleados",
                "No hay empleados registrados.\n"
                "Use '+ Empleado' para agregar uno primero.")
            return

        dlg = tk.Toplevel(self.parent)
        dlg.title("Nueva tab de consumo")
        dlg.geometry("360x230")
        dlg.transient(self.parent)
        dlg.grab_set()
        dlg.configure(bg=COLORES['fondo'])

        tk.Frame(dlg, bg=COLORES['primario'], pady=8).pack(fill='x')
        hdr = dlg.winfo_children()[-1]
        tk.Label(hdr, text="Seleccionar empleado",
                 font=FUENTES['subtitulo'], fg=COLORES['texto_claro'],
                 bg=COLORES['primario']).pack()

        frame = tk.Frame(dlg, bg=COLORES['fondo'], padx=16, pady=12)
        frame.pack(fill='both', expand=True)

        tk.Label(frame, text="Empleado:", font=FUENTES['normal'],
                 bg=COLORES['fondo'], fg=COLORES['texto']).pack(anchor='w')
        nombres = [e['nombre'] for e in self.empleados]
        var_emp = tk.StringVar(value=nombres[0])
        combo = ttk.Combobox(frame, values=nombres, textvariable=var_emp,
                             state='readonly', font=FUENTES['input'])
        combo.pack(fill='x', pady=(4, 10))

        tk.Label(frame, text="Notas (opcional):", font=FUENTES['pequena'],
                 bg=COLORES['fondo'], fg=COLORES['texto_secundario']).pack(anchor='w')
        entry_notas = tk.Entry(frame, font=FUENTES['input'],
                               bg=COLORES['fondo_input'], fg=COLORES['texto'])
        entry_notas.pack(fill='x', pady=(4, 10))

        def confirmar():
            emp = next((e for e in self.empleados if e['nombre'] == var_emp.get()), None)
            if not emp:
                messagebox.showerror("Requerido", "Seleccione un empleado.", parent=dlg)
                return
            try:
                with transaccion_atomica() as conn:
                    conn.execute("""
                        INSERT INTO consumos_empleados (id_empleado, usuario, notas)
                        VALUES (?, ?, ?)
                    """, (emp['id_empleado'],
                          self.usuario.get('usuario', ''),
                          entry_notas.get().strip() or None))
                dlg.destroy()
                self._cargar_consumos()
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo crear la tab: {e}", parent=dlg)

        btn_row = tk.Frame(frame, bg=COLORES['fondo'])
        btn_row.pack()
        crear_boton(btn_row, "Crear tab",  confirmar,   tipo='primario').pack(side='left', padx=(0, 6))
        crear_boton(btn_row, "Cancelar",   dlg.destroy, tipo='secundario').pack(side='left')

    def _agregar_empleado(self):
        dlg = tk.Toplevel(self.parent)
        dlg.title("Nuevo empleado")
        dlg.geometry("340x170")
        dlg.transient(self.parent)
        dlg.grab_set()
        dlg.configure(bg=COLORES['fondo'])

        hdr = tk.Frame(dlg, bg=COLORES['primario'], pady=8)
        hdr.pack(fill='x')
        tk.Label(hdr, text="Agregar empleado",
                 font=FUENTES['subtitulo'], fg=COLORES['texto_claro'],
                 bg=COLORES['primario']).pack()

        frame = tk.Frame(dlg, bg=COLORES['fondo'], padx=16, pady=12)
        frame.pack(fill='both', expand=True)
        tk.Label(frame, text="Nombre completo:", font=FUENTES['normal'],
                 bg=COLORES['fondo'], fg=COLORES['texto']).pack(anchor='w')
        entry = tk.Entry(frame, font=FUENTES['input'],
                         bg=COLORES['fondo_input'], fg=COLORES['texto'])
        entry.pack(fill='x', pady=(4, 12))
        entry.focus()

        def confirmar():
            nombre = entry.get().strip()
            if len(nombre) < 2:
                messagebox.showerror("Requerido", "Ingrese el nombre del empleado.", parent=dlg)
                if entry.winfo_exists():
                    entry.focus()
                return
            try:
                with transaccion_atomica() as conn:
                    conn.execute("INSERT INTO nomina_empleados (nombre) VALUES (?)", (nombre,))
                dlg.destroy()
                self._cargar_empleados()
                messagebox.showinfo("Listo", f"Empleado '{nombre}' agregado.")
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo agregar: {e}", parent=dlg)

        btn_row = tk.Frame(frame, bg=COLORES['fondo'])
        btn_row.pack()
        crear_boton(btn_row, "Guardar",  confirmar,   tipo='primario').pack(side='left', padx=(0, 6))
        crear_boton(btn_row, "Cancelar", dlg.destroy, tipo='secundario').pack(side='left')

    def _agregar_item(self):
        if not self._id_consumo_sel:
            return
        try:
            with conexion_segura() as conn:
                productos = conn.execute("""
                    SELECT p.id_producto, p.nombre, p.precio_venta,
                           p.controla_stock, p.stock_actual
                    FROM productos p
                    WHERE p.activo = 1
                      AND p.pendiente_aprobacion = 0
                      AND p.es_boleta_entrada = 0
                    ORDER BY p.nombre
                """).fetchall()
        except Exception as e:
            messagebox.showerror("Error", f"No se pudieron cargar productos: {e}")
            return

        dlg = tk.Toplevel(self.parent)
        dlg.title("Agregar producto al consumo")
        dlg.geometry("500x460")
        dlg.transient(self.parent)
        dlg.grab_set()
        dlg.configure(bg=COLORES['fondo'])

        hdr = tk.Frame(dlg, bg=COLORES['primario'], pady=8)
        hdr.pack(fill='x')
        tk.Label(hdr, text="Seleccionar producto",
                 font=FUENTES['subtitulo'], fg=COLORES['texto_claro'],
                 bg=COLORES['primario']).pack()

        frame = tk.Frame(dlg, bg=COLORES['fondo'], padx=12, pady=8)
        frame.pack(fill='both', expand=True)

        tk.Label(frame, text="Buscar:", font=FUENTES['pequena'],
                 bg=COLORES['fondo'], fg=COLORES['texto_secundario']).pack(anchor='w')
        entry_buscar = tk.Entry(frame, font=FUENTES['input'],
                                bg=COLORES['fondo_input'], fg=COLORES['texto'])
        entry_buscar.pack(fill='x', pady=(2, 6))

        list_frame = tk.Frame(frame, bg=COLORES['fondo'])
        list_frame.pack(fill='both', expand=True)
        sb = tk.Scrollbar(list_frame)
        sb.pack(side='right', fill='y')
        listbox = tk.Listbox(list_frame, yscrollcommand=sb.set,
                             font=FUENTES['normal'],
                             bg=COLORES['fondo_card'], fg=COLORES['texto'],
                             selectbackground=COLORES['primario'],
                             selectforeground=COLORES['texto_claro'],
                             height=12)
        listbox.pack(fill='both', expand=True)
        sb.config(command=listbox.yview)

        prods_filtrados = list(productos)

        def filtrar(event=None):
            nonlocal prods_filtrados
            q = entry_buscar.get().lower()
            prods_filtrados = [p for p in productos if q in p['nombre'].lower()]
            listbox.delete(0, tk.END)
            for p in prods_filtrados:
                stock_txt = f" [stock: {int(p['stock_actual'])}]" if p['controla_stock'] else ""
                listbox.insert(tk.END,
                    f"{p['nombre']}  —  {format_money(p['precio_venta'])}{stock_txt}")

        entry_buscar.bind('<KeyRelease>', filtrar)
        filtrar()

        cant_frame = tk.Frame(frame, bg=COLORES['fondo'], pady=6)
        cant_frame.pack(fill='x')
        tk.Label(cant_frame, text="Cantidad:", font=FUENTES['normal'],
                 bg=COLORES['fondo'], fg=COLORES['texto']).pack(side='left')
        entry_cant = tk.Entry(cant_frame, font=FUENTES['input'], width=8,
                              bg=COLORES['fondo_input'], fg=COLORES['texto'])
        entry_cant.insert(0, "1")
        entry_cant.pack(side='left', padx=8)

        def confirmar():
            sel = listbox.curselection()
            if not sel:
                messagebox.showerror("Requerido", "Seleccione un producto.", parent=dlg)
                return
            prod = prods_filtrados[sel[0]]
            try:
                cant = float(entry_cant.get().replace(',', '.'))
                if cant <= 0:
                    raise ValueError
            except ValueError:
                messagebox.showerror("Cantidad invalida",
                                     "Ingrese una cantidad mayor a 0.", parent=dlg)
                return
            if prod['controla_stock'] and prod['stock_actual'] < cant:
                messagebox.showerror("Stock insuficiente",
                    f"Stock disponible: {int(prod['stock_actual'])}", parent=dlg)
                return
            total_linea = round(cant * prod['precio_venta'], 2)
            try:
                with transaccion_atomica() as conn:
                    conn.execute("""
                        INSERT INTO consumo_detalle
                            (id_consumo, id_producto, producto_nombre,
                             cantidad, precio_unitario, total_linea)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (self._id_consumo_sel, prod['id_producto'],
                          prod['nombre'], cant, prod['precio_venta'], total_linea))
                    conn.execute("""
                        UPDATE consumos_empleados SET total = total + ?
                        WHERE id_consumo = ?
                    """, (total_linea, self._id_consumo_sel))
                    if prod['controla_stock']:
                        stock_nuevo = prod['stock_actual'] - cant
                        conn.execute(
                            "UPDATE productos SET stock_actual = ? WHERE id_producto = ?",
                            (stock_nuevo, prod['id_producto']))
                        conn.execute("""
                            INSERT INTO movimientos_inventario
                                (id_producto, tipo, cantidad, stock_anterior, stock_nuevo,
                                 motivo, referencia, usuario, fecha)
                            VALUES (?, 'SALIDA', ?, ?, ?,
                                    'Consumo empleado',
                                    ?, ?, datetime('now','localtime'))
                        """, (prod['id_producto'], cant,
                              prod['stock_actual'], stock_nuevo,
                              f"CONSUMO-{self._id_consumo_sel}",
                              self.usuario.get('usuario', '')))
                dlg.destroy()
                self._cargar_consumos()
                self._cargar_detalle(self._id_consumo_sel)
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo agregar: {e}", parent=dlg)

        btn_row = tk.Frame(frame, bg=COLORES['fondo'])
        btn_row.pack(fill='x', pady=6)
        crear_boton(btn_row, "Agregar al consumo", confirmar,   tipo='primario').pack(side='left', padx=(0, 6))
        crear_boton(btn_row, "Cancelar",            dlg.destroy, tipo='secundario').pack(side='left')

    def _cerrar_consumo(self):
        if not self._id_consumo_sel:
            return
        sel = self.tree_abiertos.selection()
        nombre = self.tree_abiertos.item(sel[0], 'values')[0] if sel else 'este empleado'
        total_txt = self.lbl_total_det.cget('text')

        if not messagebox.askyesno("Cerrar consumo",
                f"Cerrar el consumo de {nombre}?\n"
                f"Total registrado: {total_txt}\n\n"
                "No se generara cobro. Solo queda en el informe del dia."):
            return
        try:
            with transaccion_atomica() as conn:
                conn.execute("""
                    UPDATE consumos_empleados
                    SET estado = 'CERRADO', fecha = datetime('now','localtime')
                    WHERE id_consumo = ?
                """, (self._id_consumo_sel,))
                log_auditoria(conn, 'consumos_empleados', self._id_consumo_sel,
                              'CERRAR', self.usuario.get('usuario', ''),
                              f"Consumo cerrado. Total: {total_txt}")
            self._limpiar_seleccion()
            self._cargar_consumos()
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo cerrar: {e}")

    # ── Auto-refresh ─────────────────────────────────────────────────────────

    def _iniciar_refresh(self):
        if self.auto_refresh:
            self._after_id = self.parent.winfo_toplevel().after(30_000, self._refresh)

    def _refresh(self):
        if not self.auto_refresh:
            return
        self._cargar_consumos()
        if self._id_consumo_sel:
            self._cargar_detalle(self._id_consumo_sel)
        self._iniciar_refresh()

    def detener(self):
        self.auto_refresh = False
        if self._after_id:
            try:
                self.parent.winfo_toplevel().after_cancel(self._after_id)
            except Exception:
                pass
