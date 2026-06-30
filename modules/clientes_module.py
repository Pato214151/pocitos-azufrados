"""
Módulo de Clientes - Club Los Pocitos Azufrados
Gestión de clientes: ficha, historial de ventas y saldo por cobrar
"""

import tkinter as tk
from tkinter import ttk, messagebox
import os, sys, datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from utils.tema_corporativo import COLORES, FUENTES, crear_boton, format_money, aplicar_estilo_tabla
from database.connection import conexion_segura
from utils.logger import log_auditoria


class ClientesModule:
    def __init__(self, parent, usuario):
        self.parent = parent
        self.usuario = usuario
        self.cliente_sel = None
        self.clientes = []

        self._crear_interfaz()
        self._cargar_clientes()

    # ------------------------------------------------------------------
    # INTERFAZ
    # ------------------------------------------------------------------
    def _crear_interfaz(self):
        # Header
        header = tk.Frame(self.parent, bg=COLORES['primario'])
        header.pack(fill='x')

        inner_hdr = tk.Frame(header, bg=COLORES['primario'], padx=15, pady=10)
        inner_hdr.pack(fill='x')

        tk.Label(inner_hdr, text="Clientes", font=FUENTES['encabezado'],
                 fg=COLORES['texto_claro'], bg=COLORES['primario']).pack(side='left')

        btns_header = tk.Frame(inner_hdr, bg=COLORES['primario'])
        btns_header.pack(side='right')
        crear_boton(btns_header, "Nuevo Cliente", self._nuevo_cliente,
                    tipo='primario').pack(side='left', padx=4)
        crear_boton(btns_header, "Recargar", self._cargar_clientes,
                    tipo='secundario').pack(side='left', padx=4)

        # KPIs
        kpi_frame = tk.Frame(self.parent, bg=COLORES['fondo'])
        kpi_frame.pack(fill='x', padx=15, pady=(0, 10))

        self.lbl_total_clientes = self._kpi_card(kpi_frame, "Total Clientes", "0",
                                                  COLORES['primario'])
        self.lbl_total_clientes.master.pack(side='left', padx=5, fill='both', expand=True)

        self.lbl_por_cobrar = self._kpi_card(kpi_frame, "Total Por Cobrar", "$ 0",
                                             COLORES['advertencia'])
        self.lbl_por_cobrar.master.pack(side='left', padx=5, fill='both', expand=True)

        # Cuerpo
        body = tk.Frame(self.parent, bg=COLORES['fondo'])
        body.pack(fill='both', expand=True, padx=15, pady=5)

        # --- IZQUIERDA: lista ---
        left = tk.Frame(body, bg=COLORES['fondo_card'],
                        highlightbackground=COLORES['borde'], highlightthickness=1)
        left.pack(side='left', fill='y', padx=(0, 8))
        left.pack_propagate(False)
        left.config(width=380)

        # Búsqueda
        busq_frame = tk.Frame(left, bg=COLORES['fondo_card'])
        busq_frame.pack(fill='x', padx=10, pady=(10, 6))

        tk.Label(busq_frame, text="Buscar", font=FUENTES['pequena'],
                 fg=COLORES['texto_secundario'], bg=COLORES['fondo_card']).pack(anchor='w')
        self.entry_busqueda = tk.Entry(busq_frame, font=FUENTES['input'],
                                       bg=COLORES['fondo_input'], fg=COLORES['texto'],
                                       insertbackground=COLORES['acento'],
                                       relief='solid', bd=1)
        self.entry_busqueda.pack(fill='x', ipady=5)
        self.entry_busqueda.bind('<KeyRelease>', lambda e: self._filtrar())

        # Tabla clientes
        tabla_frame = tk.Frame(left, bg=COLORES['fondo_card'])
        tabla_frame.pack(fill='both', expand=True, padx=10, pady=5)

        self.tree_clientes = ttk.Treeview(tabla_frame,
                                           columns=('nombre', 'celular', 'saldo'),
                                           show='headings', height=20)
        self.tree_clientes.column('nombre', width=160, anchor='w')
        self.tree_clientes.column('celular', width=100, anchor='center')
        self.tree_clientes.column('saldo', width=100, anchor='e')
        self.tree_clientes.heading('nombre', text='Nombre')
        self.tree_clientes.heading('celular', text='Celular')
        self.tree_clientes.heading('saldo', text='Por Cobrar')
        aplicar_estilo_tabla(self.tree_clientes)

        scroll_y = ttk.Scrollbar(tabla_frame, orient='vertical',
                                  command=self.tree_clientes.yview)
        self.tree_clientes.configure(yscrollcommand=scroll_y.set)
        self.tree_clientes.pack(side='left', fill='both', expand=True)
        scroll_y.pack(side='right', fill='y')
        self.tree_clientes.bind('<ButtonRelease-1>', self._on_select)

        # --- DERECHA: ficha ---
        self.right = tk.Frame(body, bg=COLORES['fondo_card'],
                               highlightbackground=COLORES['borde'], highlightthickness=1)
        self.right.pack(side='right', fill='both', expand=True)

        self._mostrar_placeholder()

    def _kpi_card(self, parent, titulo, valor, color):
        card = tk.Frame(parent, bg=COLORES['fondo_card'],
                        highlightbackground=COLORES['borde'], highlightthickness=1)
        tk.Frame(card, bg=color, height=3).pack(fill='x')
        inner = tk.Frame(card, bg=COLORES['fondo_card'], padx=16, pady=10)
        inner.pack(fill='both', expand=True)
        tk.Label(inner, text=titulo, font=FUENTES['kpi_label'],
                 fg=COLORES['texto_secundario'], bg=COLORES['fondo_card']).pack(anchor='w')
        lbl = tk.Label(inner, text=valor, font=FUENTES['kpi_valor'],
                       fg=COLORES['texto'], bg=COLORES['fondo_card'], anchor='w')
        lbl.pack(fill='x')
        return lbl

    def _mostrar_placeholder(self):
        for w in self.right.winfo_children():
            w.destroy()
        tk.Label(self.right, text="Seleccione un cliente\npara ver su ficha",
                 font=FUENTES['normal'], fg=COLORES['texto_deshabilitado'],
                 bg=COLORES['fondo_card']).pack(expand=True)

    # ------------------------------------------------------------------
    # DATOS
    # ------------------------------------------------------------------
    def _cargar_clientes(self):
        try:
            with conexion_segura() as conn:
                rows = conn.execute("""
                    SELECT c.id_cliente, c.nombre, c.celular, c.documento, c.email, c.notas,
                           c.fecha_creacion,
                           COALESCE(SUM(v.saldo_pendiente), 0) as total_por_cobrar
                    FROM clientes c
                    LEFT JOIN ventas v ON v.id_cliente = c.id_cliente AND v.estado = 'ABIERTA'
                    GROUP BY c.id_cliente
                    ORDER BY c.nombre
                """).fetchall()

                self.clientes = [dict(r) for r in rows]

                total_cobrar = sum(c['total_por_cobrar'] for c in self.clientes)
                self.lbl_total_clientes.config(text=str(len(self.clientes)))
                self.lbl_por_cobrar.config(text=format_money(total_cobrar))

                self._poblar_tabla(self.clientes)

        except Exception as e:
            messagebox.showerror("Error", f"Error al cargar clientes: {e}")

    def _poblar_tabla(self, lista):
        for item in self.tree_clientes.get_children():
            self.tree_clientes.delete(item)
        for i, c in enumerate(lista):
            tag = 'alerta' if c['total_por_cobrar'] > 0 else ('par' if i % 2 == 0 else 'impar')
            self.tree_clientes.insert('', 'end', iid=c['id_cliente'], values=(
                c['nombre'],
                c['celular'] or '---',
                format_money(c['total_por_cobrar']) if c['total_por_cobrar'] else '$ 0'
            ), tags=(tag,))

    def _filtrar(self):
        termino = self.entry_busqueda.get().strip().lower()
        if not termino:
            self._poblar_tabla(self.clientes)
            return
        filtrados = [c for c in self.clientes
                     if termino in c['nombre'].lower()
                     or termino in (c['celular'] or '').lower()
                     or termino in (c['documento'] or '').lower()]
        self._poblar_tabla(filtrados)

    def _on_select(self, event):
        sel = self.tree_clientes.selection()
        if sel:
            self.cliente_sel = int(sel[0])
            cliente = next((c for c in self.clientes if c['id_cliente'] == self.cliente_sel), None)
            if cliente:
                self._mostrar_ficha(cliente)

    # ------------------------------------------------------------------
    # FICHA
    # ------------------------------------------------------------------
    def _mostrar_ficha(self, cliente):
        for w in self.right.winfo_children():
            w.destroy()

        # Panel derecho scrollable
        _dc = tk.Canvas(self.right, bg=COLORES['fondo_card'], highlightthickness=0)
        _dc_sb = ttk.Scrollbar(self.right, orient='vertical', command=_dc.yview)
        _dc.configure(yscrollcommand=_dc_sb.set)
        _dc_sb.pack(side='right', fill='y')
        _dc.pack(side='left', fill='both', expand=True)
        _inner = tk.Frame(_dc, bg=COLORES['fondo_card'])
        _dc_win = _dc.create_window((0, 0), window=_inner, anchor='nw')
        _inner.bind('<Configure>', lambda e: _dc.configure(scrollregion=_dc.bbox('all')))
        _dc.bind('<Configure>', lambda e: _dc.itemconfig(_dc_win, width=e.width))

        # Header ficha
        hdr = tk.Frame(_inner, bg=COLORES['fondo_card'], padx=16, pady=12)
        hdr.pack(fill='x')

        nombre_inicial = cliente['nombre'][0].upper() if cliente['nombre'] else '?'
        avatar = tk.Label(hdr, text=nombre_inicial, font=('Segoe UI', 22, 'bold'),
                          fg=COLORES['fondo'], bg=COLORES['primario'],
                          width=2, height=1)
        avatar.pack(side='left', padx=(0, 12))

        info = tk.Frame(hdr, bg=COLORES['fondo_card'])
        info.pack(side='left')
        tk.Label(info, text=cliente['nombre'], font=FUENTES['subtitulo'],
                 fg=COLORES['texto'], bg=COLORES['fondo_card']).pack(anchor='w')
        tk.Label(info, text=cliente['celular'] or 'Sin celular',
                 font=FUENTES['pequena'], fg=COLORES['texto_secundario'],
                 bg=COLORES['fondo_card']).pack(anchor='w')

        btns_ficha = tk.Frame(hdr, bg=COLORES['fondo_card'])
        btns_ficha.pack(side='right')
        crear_boton(btns_ficha, "Editar", lambda: self._editar_cliente(cliente),
                    tipo='outline').pack(side='left', padx=3)
        crear_boton(btns_ficha, "Eliminar", lambda: self._eliminar_cliente(cliente),
                    tipo='error').pack(side='left', padx=3)

        tk.Frame(_inner, bg=COLORES['borde'], height=1).pack(fill='x')

        # Datos
        datos = tk.Frame(_inner, bg=COLORES['fondo_card'], padx=16, pady=10)
        datos.pack(fill='x')
        campos = [
            ('Documento', cliente['documento'] or '---'),
            ('Email', cliente['email'] or '---'),
            ('Registrado', (cliente['fecha_creacion'] or '')[:10]),
        ]
        for label, val in campos:
            row = tk.Frame(datos, bg=COLORES['fondo_card'])
            row.pack(fill='x', pady=2)
            tk.Label(row, text=f"{label}:", font=FUENTES['pequena'],
                     fg=COLORES['texto_secundario'], bg=COLORES['fondo_card'],
                     width=12, anchor='w').pack(side='left')
            tk.Label(row, text=val, font=FUENTES['normal'],
                     fg=COLORES['texto'], bg=COLORES['fondo_card']).pack(side='left')

        if cliente['notas']:
            tk.Label(datos, text=f"Notas: {cliente['notas']}",
                     font=FUENTES['pequena'], fg=COLORES['texto_secundario'],
                     bg=COLORES['fondo_card'], wraplength=300, justify='left').pack(anchor='w', pady=(4, 0))

        tk.Frame(_inner, bg=COLORES['borde'], height=1).pack(fill='x')

        # Historial de ventas
        hist_hdr = tk.Frame(_inner, bg=COLORES['fondo_card'], padx=16, pady=8)
        hist_hdr.pack(fill='x')
        tk.Label(hist_hdr, text="Historial de Ventas", font=FUENTES['encabezado'],
                 fg=COLORES['texto'], bg=COLORES['fondo_card']).pack(side='left')

        hist_frame = tk.Frame(_inner, bg=COLORES['fondo_card'])
        hist_frame.pack(fill='both', padx=10, pady=(0, 10))

        tree_hist = ttk.Treeview(hist_frame,
                                  columns=('numero', 'fecha', 'total', 'saldo', 'estado'),
                                  show='headings', height=10)
        tree_hist.column('numero', width=130, anchor='center')
        tree_hist.column('fecha', width=90, anchor='center')
        tree_hist.column('total', width=90, anchor='e')
        tree_hist.column('saldo', width=90, anchor='e')
        tree_hist.column('estado', width=80, anchor='center')
        tree_hist.heading('numero', text='# Venta')
        tree_hist.heading('fecha', text='Fecha')
        tree_hist.heading('total', text='Total')
        tree_hist.heading('saldo', text='Saldo')
        tree_hist.heading('estado', text='Estado')
        aplicar_estilo_tabla(tree_hist)

        scroll_h = ttk.Scrollbar(hist_frame, orient='vertical', command=tree_hist.yview)
        tree_hist.configure(yscrollcommand=scroll_h.set)
        tree_hist.pack(side='left', fill='both', expand=True)
        scroll_h.pack(side='right', fill='y')

        try:
            with conexion_segura() as conn:
                ventas = conn.execute("""
                    SELECT numero_venta, fecha_creacion, total, saldo_pendiente, estado
                    FROM ventas
                    WHERE id_cliente = ?
                    ORDER BY fecha_creacion DESC
                    LIMIT 50
                """, (cliente['id_cliente'],)).fetchall()

                for i, v in enumerate(ventas):
                    tag = 'alerta' if v['saldo_pendiente'] > 0 else ('par' if i % 2 == 0 else 'impar')
                    tree_hist.insert('', 'end', values=(
                        v['numero_venta'],
                        (v['fecha_creacion'] or '')[:10],
                        format_money(v['total']),
                        format_money(v['saldo_pendiente']),
                        v['estado']
                    ), tags=(tag,))

                if not ventas:
                    tree_hist.insert('', 'end', values=('---', '---', '---', '---', '---'))

        except Exception as e:
            messagebox.showerror("Error", f"Error al cargar historial: {e}")

    # ------------------------------------------------------------------
    # FORMULARIO NUEVO / EDITAR
    # ------------------------------------------------------------------
    def _nuevo_cliente(self):
        self._abrir_form(None)

    def _editar_cliente(self, cliente):
        self._abrir_form(cliente)

    def _abrir_form(self, cliente=None):
        es_nuevo = cliente is None
        titulo = "Nuevo Cliente" if es_nuevo else f"Editar: {cliente['nombre']}"

        dlg = tk.Toplevel(self.parent)
        dlg.title(titulo)
        dlg.geometry("420x360")
        dlg.resizable(True, True)
        dlg.configure(bg=COLORES['fondo_card'])
        dlg.grab_set()

        tk.Label(dlg, text=titulo, font=FUENTES['subtitulo'],
                 fg=COLORES['texto'], bg=COLORES['fondo_card']).pack(padx=20, pady=(16, 10), anchor='w')

        form = tk.Frame(dlg, bg=COLORES['fondo_card'])
        form.pack(fill='both', expand=True, padx=20)

        def campo(label, val=''):
            tk.Label(form, text=label, font=FUENTES['pequena'],
                     fg=COLORES['texto_secundario'], bg=COLORES['fondo_card']).pack(anchor='w', pady=(6, 0))
            e = tk.Entry(form, font=FUENTES['input'],
                         bg=COLORES['fondo_input'], fg=COLORES['texto'],
                         insertbackground=COLORES['acento'],
                         relief='solid', bd=1)
            e.insert(0, val)
            e.pack(fill='x', ipady=5)
            return e

        e_nombre = campo("Nombre *", '' if es_nuevo else cliente['nombre'])
        e_celular = campo("Celular", '' if es_nuevo else (cliente['celular'] or ''))
        e_documento = campo("Documento", '' if es_nuevo else (cliente['documento'] or ''))
        e_email = campo("Email", '' if es_nuevo else (cliente['email'] or ''))
        e_notas = campo("Notas", '' if es_nuevo else (cliente['notas'] or ''))

        def guardar():
            nombre = e_nombre.get().strip()
            if not nombre:
                messagebox.showwarning("Requerido", "El nombre es obligatorio", parent=dlg)
                return
            try:
                with conexion_segura() as conn:
                    if es_nuevo:
                        cur = conn.execute("""
                            INSERT INTO clientes (nombre, celular, documento, email, notas)
                            VALUES (?, ?, ?, ?, ?)
                        """, (nombre, e_celular.get().strip() or None,
                              e_documento.get().strip() or None,
                              e_email.get().strip() or None,
                              e_notas.get().strip() or None))
                        log_auditoria(conn, 'clientes', cur.lastrowid, 'INSERT',
                                      self.usuario['usuario'], f"Nuevo cliente: {nombre}")
                    else:
                        conn.execute("""
                            UPDATE clientes SET nombre=?, celular=?, documento=?, email=?, notas=?
                            WHERE id_cliente=?
                        """, (nombre, e_celular.get().strip() or None,
                              e_documento.get().strip() or None,
                              e_email.get().strip() or None,
                              e_notas.get().strip() or None,
                              cliente['id_cliente']))
                        log_auditoria(conn, 'clientes', cliente['id_cliente'], 'UPDATE',
                                      self.usuario['usuario'], f"Editar cliente: {nombre}")
                dlg.destroy()
                self._cargar_clientes()
            except Exception as e:
                messagebox.showerror("Error", f"Error al guardar: {e}", parent=dlg)

        btns = tk.Frame(dlg, bg=COLORES['fondo_card'])
        btns.pack(fill='x', padx=20, pady=16)
        crear_boton(btns, "Guardar", guardar, tipo='exito').pack(side='right', padx=4)
        crear_boton(btns, "Cancelar", dlg.destroy, tipo='secundario').pack(side='right', padx=4)

    def _eliminar_cliente(self, cliente):
        if not messagebox.askyesno("Confirmar",
                                    f"¿Eliminar a '{cliente['nombre']}'?\n"
                                    "Las ventas asociadas conservarán su historial.",
                                    parent=self.parent):
            return
        try:
            with conexion_segura() as conn:
                conn.execute("DELETE FROM clientes WHERE id_cliente = ?",
                             (cliente['id_cliente'],))
                log_auditoria(conn, 'clientes', cliente['id_cliente'], 'DELETE',
                              self.usuario['usuario'], f"Eliminar cliente: {cliente['nombre']}")
            self.cliente_sel = None
            self._mostrar_placeholder()
            self._cargar_clientes()
        except Exception as e:
            messagebox.showerror("Error", f"Error al eliminar: {e}")

    def detener(self):
        pass
