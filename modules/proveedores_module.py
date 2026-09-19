"""
Módulo de Proveedores - Club Los Pocitos Azufrados
Gestión de proveedores y compras: ficha, historial de compras y saldo por pagar
"""

import logging
import tkinter as tk
from tkinter import ttk, messagebox
import os, sys, datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from utils.tema_corporativo import COLORES, FUENTES, crear_boton, format_money, aplicar_estilo_tabla
from database.connection import conexion_segura
from utils.logger import log_auditoria


_METODOS_DEFAULT = ['EFECTIVO', 'NEQUI', 'DAVIPLATA', 'BANCOLOMBIA', 'TRANSFERENCIA']


def _leer_metodos_pago():
    """Lee los métodos de pago habilitados desde configuracion (igual que otros módulos)."""
    try:
        with conexion_segura() as conn:
            row = conn.execute(
                "SELECT valor FROM configuracion WHERE clave = 'metodos_pago_habilitados'"
            ).fetchone()
            if row and row['valor']:
                return row['valor'].split(',')
    except Exception as e:
        logging.getLogger("pocitos").warning(f"No se pudo leer metodos_pago_habilitados: {e}")
    return _METODOS_DEFAULT[:]


class ProveedoresModule:
    """Pantalla de proveedores: lista, ficha, compras y saldo por pagar."""
    def __init__(self, parent, usuario):
        self.parent = parent
        self.usuario = usuario
        self.proveedor_sel = None
        self.proveedores = []
        self._metodos_pago = _leer_metodos_pago()

        self._crear_interfaz()
        self._cargar_proveedores()

    # ------------------------------------------------------------------
    # INTERFAZ
    # ------------------------------------------------------------------
    def _crear_interfaz(self):
        """Arma la pantalla: KPIs, buscador, tabla y panel de ficha."""
        header = tk.Frame(self.parent, bg=COLORES['primario'])
        header.pack(fill='x')

        inner_hdr = tk.Frame(header, bg=COLORES['primario'], padx=15, pady=10)
        inner_hdr.pack(fill='x')

        tk.Label(inner_hdr, text="Proveedores", font=FUENTES['encabezado'],
                 fg=COLORES['texto_claro'], bg=COLORES['primario']).pack(side='left')

        btns_header = tk.Frame(inner_hdr, bg=COLORES['primario'])
        btns_header.pack(side='right')
        crear_boton(btns_header, "Nuevo Proveedor", self._nuevo_proveedor,
                    tipo='primario').pack(side='left', padx=4)
        crear_boton(btns_header, "Recargar", self._cargar_proveedores,
                    tipo='secundario').pack(side='left', padx=4)

        # KPIs
        kpi_frame = tk.Frame(self.parent, bg=COLORES['fondo'])
        kpi_frame.pack(fill='x', padx=15, pady=(0, 10))

        self.lbl_total_prov = self._kpi_card(kpi_frame, "Total Proveedores", "0",
                                              COLORES['primario'])
        self.lbl_total_prov.master.pack(side='left', padx=5, fill='both', expand=True)

        self.lbl_por_pagar = self._kpi_card(kpi_frame, "Total Por Pagar", "$ 0",
                                             COLORES['error'])
        self.lbl_por_pagar.master.pack(side='left', padx=5, fill='both', expand=True)

        # Cuerpo
        body = tk.Frame(self.parent, bg=COLORES['fondo'])
        body.pack(fill='both', expand=True, padx=15, pady=5)

        # --- IZQUIERDA: lista ---
        left = tk.Frame(body, bg=COLORES['fondo_card'],
                        highlightbackground=COLORES['borde'], highlightthickness=1)
        left.pack(side='left', fill='y', padx=(0, 8))
        left.pack_propagate(False)
        left.config(width=380)

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

        tabla_frame = tk.Frame(left, bg=COLORES['fondo_card'])
        tabla_frame.pack(fill='both', expand=True, padx=10, pady=5)

        self.tree_prov = ttk.Treeview(tabla_frame,
                                       columns=('nombre', 'celular', 'por_pagar'),
                                       show='headings', height=20)
        self.tree_prov.column('nombre', width=160, anchor='w')
        self.tree_prov.column('celular', width=100, anchor='center')
        self.tree_prov.column('por_pagar', width=100, anchor='e')
        self.tree_prov.heading('nombre', text='Nombre')
        self.tree_prov.heading('celular', text='Celular')
        self.tree_prov.heading('por_pagar', text='Por Pagar')
        aplicar_estilo_tabla(self.tree_prov)

        scroll_y = ttk.Scrollbar(tabla_frame, orient='vertical', command=self.tree_prov.yview)
        self.tree_prov.configure(yscrollcommand=scroll_y.set)
        self.tree_prov.pack(side='left', fill='both', expand=True)
        scroll_y.pack(side='right', fill='y')
        self.tree_prov.bind('<ButtonRelease-1>', self._on_select)

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
        tk.Label(self.right, text="Seleccione un proveedor\npara ver su ficha",
                 font=FUENTES['normal'], fg=COLORES['texto_deshabilitado'],
                 bg=COLORES['fondo_card']).pack(expand=True)

    # ------------------------------------------------------------------
    # DATOS
    # ------------------------------------------------------------------
    def _cargar_proveedores(self):
        try:
            with conexion_segura() as conn:
                rows = conn.execute("""
                    SELECT p.id_proveedor, p.nombre, p.celular, p.documento, p.email,
                           p.notas, p.fecha_creacion,
                           COALESCE(SUM(CASE WHEN c.estado_pago = 'PENDIENTE' THEN c.valor ELSE 0 END), 0) as por_pagar
                    FROM proveedores p
                    LEFT JOIN compras_proveedor c ON c.id_proveedor = p.id_proveedor
                    GROUP BY p.id_proveedor
                    ORDER BY p.nombre
                """).fetchall()

                self.proveedores = [dict(r) for r in rows]
                total_pagar = sum(p['por_pagar'] for p in self.proveedores)
                self.lbl_total_prov.config(text=str(len(self.proveedores)))
                self.lbl_por_pagar.config(text=format_money(total_pagar))
                self._poblar_tabla(self.proveedores)

        except Exception as e:
            messagebox.showerror("Error", f"Error al cargar proveedores: {e}")

    def _poblar_tabla(self, lista):
        for item in self.tree_prov.get_children():
            self.tree_prov.delete(item)
        for i, p in enumerate(lista):
            tag = 'alerta' if p['por_pagar'] > 0 else ('par' if i % 2 == 0 else 'impar')
            self.tree_prov.insert('', 'end', iid=p['id_proveedor'], values=(
                p['nombre'],
                p['celular'] or '---',
                format_money(p['por_pagar']) if p['por_pagar'] else '$ 0'
            ), tags=(tag,))

    def _filtrar(self):
        termino = self.entry_busqueda.get().strip().lower()
        if not termino:
            self._poblar_tabla(self.proveedores)
            return
        filtrados = [p for p in self.proveedores
                     if termino in p['nombre'].lower()
                     or termino in (p['celular'] or '').lower()]
        self._poblar_tabla(filtrados)

    def _on_select(self, event):
        sel = self.tree_prov.selection()
        if sel:
            self.proveedor_sel = int(sel[0])
            prov = next((p for p in self.proveedores if p['id_proveedor'] == self.proveedor_sel), None)
            if prov:
                self._mostrar_ficha(prov)

    # ------------------------------------------------------------------
    # FICHA
    # ------------------------------------------------------------------
    def _mostrar_ficha(self, prov):
        """Muestra los datos y compras del proveedor elegido."""
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

        hdr = tk.Frame(_inner, bg=COLORES['fondo_card'], padx=16, pady=12)
        hdr.pack(fill='x')

        inicial = prov['nombre'][0].upper() if prov['nombre'] else '?'
        tk.Label(hdr, text=inicial, font=('Segoe UI', 22, 'bold'),
                 fg=COLORES['fondo'], bg=COLORES['agua'], width=2).pack(side='left', padx=(0, 12))

        info = tk.Frame(hdr, bg=COLORES['fondo_card'])
        info.pack(side='left')
        tk.Label(info, text=prov['nombre'], font=FUENTES['subtitulo'],
                 fg=COLORES['texto'], bg=COLORES['fondo_card']).pack(anchor='w')
        tk.Label(info, text=prov['celular'] or 'Sin celular',
                 font=FUENTES['pequena'], fg=COLORES['texto_secundario'],
                 bg=COLORES['fondo_card']).pack(anchor='w')

        btns_ficha = tk.Frame(hdr, bg=COLORES['fondo_card'])
        btns_ficha.pack(side='right')
        crear_boton(btns_ficha, "Registrar Compra",
                    lambda: self._registrar_compra(prov), tipo='acento').pack(side='left', padx=3)
        crear_boton(btns_ficha, "Editar",
                    lambda: self._editar_proveedor(prov), tipo='outline').pack(side='left', padx=3)
        crear_boton(btns_ficha, "Eliminar",
                    lambda: self._eliminar_proveedor(prov), tipo='error').pack(side='left', padx=3)

        tk.Frame(_inner, bg=COLORES['borde'], height=1).pack(fill='x')

        datos = tk.Frame(_inner, bg=COLORES['fondo_card'], padx=16, pady=10)
        datos.pack(fill='x')
        for label, val in [
            ('Documento', prov['documento'] or '---'),
            ('Email', prov['email'] or '---'),
            ('Registrado', (prov['fecha_creacion'] or '')[:10]),
        ]:
            row = tk.Frame(datos, bg=COLORES['fondo_card'])
            row.pack(fill='x', pady=2)
            tk.Label(row, text=f"{label}:", font=FUENTES['pequena'],
                     fg=COLORES['texto_secundario'], bg=COLORES['fondo_card'],
                     width=12, anchor='w').pack(side='left')
            tk.Label(row, text=val, font=FUENTES['normal'],
                     fg=COLORES['texto'], bg=COLORES['fondo_card']).pack(side='left')

        tk.Frame(_inner, bg=COLORES['borde'], height=1).pack(fill='x')

        # Historial de compras
        hist_hdr = tk.Frame(_inner, bg=COLORES['fondo_card'], padx=16, pady=8)
        hist_hdr.pack(fill='x')
        tk.Label(hist_hdr, text="Historial de Compras", font=FUENTES['encabezado'],
                 fg=COLORES['texto'], bg=COLORES['fondo_card']).pack(side='left')

        hist_frame = tk.Frame(_inner, bg=COLORES['fondo_card'])
        hist_frame.pack(fill='both', padx=10, pady=(0, 10))

        tree_hist = ttk.Treeview(hist_frame,
                                  columns=('fecha', 'concepto', 'valor', 'metodo', 'estado'),
                                  show='headings', height=10)
        tree_hist.column('fecha', width=90, anchor='center')
        tree_hist.column('concepto', width=150, anchor='w')
        tree_hist.column('valor', width=90, anchor='e')
        tree_hist.column('metodo', width=100, anchor='center')
        tree_hist.column('estado', width=80, anchor='center')
        tree_hist.heading('fecha', text='Fecha')
        tree_hist.heading('concepto', text='Concepto')
        tree_hist.heading('valor', text='Valor')
        tree_hist.heading('metodo', text='Metodo')
        tree_hist.heading('estado', text='Estado')
        aplicar_estilo_tabla(tree_hist)

        # Bind para marcar como pagada
        def on_right_click(event):
            row = tree_hist.identify_row(event.y)
            if row:
                tree_hist.selection_set(row)
                id_compra = int(row)
                menu = tk.Menu(self.right, tearoff=0)
                menu.add_command(label="Marcar como Pagada",
                                 command=lambda: self._marcar_pagada(id_compra, prov))
                menu.add_command(label="Eliminar",
                                 command=lambda: self._eliminar_compra(id_compra, prov))
                menu.tk_popup(event.x_root, event.y_root)

        tree_hist.bind('<Button-3>', on_right_click)

        scroll_h = ttk.Scrollbar(hist_frame, orient='vertical', command=tree_hist.yview)
        tree_hist.configure(yscrollcommand=scroll_h.set)
        tree_hist.pack(side='left', fill='both', expand=True)
        scroll_h.pack(side='right', fill='y')

        try:
            with conexion_segura() as conn:
                compras = conn.execute("""
                    SELECT id_compra, fecha, concepto, valor, metodo_pago, estado_pago
                    FROM compras_proveedor
                    WHERE id_proveedor = ?
                    ORDER BY fecha DESC
                    LIMIT 50
                """, (prov['id_proveedor'],)).fetchall()

                for i, c in enumerate(compras):
                    tag = 'alerta' if c['estado_pago'] == 'PENDIENTE' else ('par' if i % 2 == 0 else 'impar')
                    tree_hist.insert('', 'end', iid=c['id_compra'], values=(
                        (c['fecha'] or '')[:10],
                        c['concepto'],
                        format_money(c['valor']),
                        c['metodo_pago'],
                        c['estado_pago']
                    ), tags=(tag,))

                if not compras:
                    tree_hist.insert('', 'end', values=('---', 'Sin compras registradas', '---', '---', '---'))
        except Exception as e:
            messagebox.showerror("Error", f"Error al cargar historial: {e}")

    # ------------------------------------------------------------------
    # ACCIONES
    # ------------------------------------------------------------------
    def _registrar_compra(self, prov):
        """Formulario para registrar una compra al proveedor."""
        dlg = tk.Toplevel(self.parent)
        dlg.title(f"Registrar Compra - {prov['nombre']}")
        dlg.geometry("420x340")
        dlg.resizable(True, True)
        dlg.configure(bg=COLORES['fondo_card'])
        dlg.grab_set()

        tk.Label(dlg, text="Registrar Compra", font=FUENTES['subtitulo'],
                 fg=COLORES['texto'], bg=COLORES['fondo_card']).pack(padx=20, pady=(16, 10), anchor='w')

        form = tk.Frame(dlg, bg=COLORES['fondo_card'])
        form.pack(fill='both', expand=True, padx=20)

        def label_entry(texto, val=''):
            tk.Label(form, text=texto, font=FUENTES['pequena'],
                     fg=COLORES['texto_secundario'], bg=COLORES['fondo_card']).pack(anchor='w', pady=(6, 0))
            e = tk.Entry(form, font=FUENTES['input'],
                         bg=COLORES['fondo_input'], fg=COLORES['texto'],
                         insertbackground=COLORES['acento'], relief='solid', bd=1)
            e.insert(0, val)
            e.pack(fill='x', ipady=5)
            return e

        e_concepto = label_entry("Concepto / Descripcion *")
        e_valor = label_entry("Valor *")

        tk.Label(form, text="Metodo de Pago", font=FUENTES['pequena'],
                 fg=COLORES['texto_secundario'], bg=COLORES['fondo_card']).pack(anchor='w', pady=(6, 0))
        combo_metodo = ttk.Combobox(form, values=self._metodos_pago, state='readonly', font=FUENTES['input'])
        combo_metodo.set('EFECTIVO')
        combo_metodo.pack(fill='x', ipady=4)

        tk.Label(form, text="Estado", font=FUENTES['pequena'],
                 fg=COLORES['texto_secundario'], bg=COLORES['fondo_card']).pack(anchor='w', pady=(6, 0))
        combo_estado = ttk.Combobox(form, values=['PENDIENTE', 'PAGADA'], state='readonly', font=FUENTES['input'])
        combo_estado.set('PENDIENTE')
        combo_estado.pack(fill='x', ipady=4)

        def guardar():
            concepto = e_concepto.get().strip()
            valor_str = e_valor.get().strip()
            if not concepto or not valor_str:
                messagebox.showwarning("Requerido", "Concepto y valor son obligatorios", parent=dlg)
                return
            try:
                valor = float(valor_str.replace(',', '.'))
                if valor <= 0:
                    raise ValueError()
            except ValueError:
                messagebox.showerror("Error", "Ingrese un valor numérico válido", parent=dlg)
                return
            try:
                with conexion_segura() as conn:
                    conn.execute("""
                        INSERT INTO compras_proveedor
                        (id_proveedor, concepto, valor, metodo_pago, estado_pago, usuario_registro)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (prov['id_proveedor'], concepto, valor,
                          combo_metodo.get(), combo_estado.get(),
                          self.usuario['usuario']))
                dlg.destroy()
                self._cargar_proveedores()
                prov_act = next((p for p in self.proveedores if p['id_proveedor'] == prov['id_proveedor']), None)
                if prov_act:
                    self._mostrar_ficha(prov_act)
            except Exception as e:
                messagebox.showerror("Error", f"Error al guardar: {e}", parent=dlg)

        btns = tk.Frame(dlg, bg=COLORES['fondo_card'])
        btns.pack(fill='x', padx=20, pady=12)
        crear_boton(btns, "Guardar", guardar, tipo='exito').pack(side='right', padx=4)
        crear_boton(btns, "Cancelar", dlg.destroy, tipo='secundario').pack(side='right', padx=4)

    def _marcar_pagada(self, id_compra, prov):
        if not messagebox.askyesno("Confirmar", "Marcar esta compra como PAGADA?", parent=self.parent):
            return
        try:
            with conexion_segura() as conn:
                conn.execute("UPDATE compras_proveedor SET estado_pago='PAGADA' WHERE id_compra=?",
                             (id_compra,))
            self._cargar_proveedores()
            prov_act = next((p for p in self.proveedores if p['id_proveedor'] == prov['id_proveedor']), None)
            if prov_act:
                self._mostrar_ficha(prov_act)
        except Exception as e:
            messagebox.showerror("Error", f"Error: {e}")

    def _eliminar_compra(self, id_compra, prov):
        if not messagebox.askyesno("Confirmar", "Eliminar esta compra?", parent=self.parent):
            return
        try:
            with conexion_segura() as conn:
                conn.execute("DELETE FROM compras_proveedor WHERE id_compra=?", (id_compra,))
            self._cargar_proveedores()
            prov_act = next((p for p in self.proveedores if p['id_proveedor'] == prov['id_proveedor']), None)
            if prov_act:
                self._mostrar_ficha(prov_act)
        except Exception as e:
            messagebox.showerror("Error", f"Error: {e}")

    def _nuevo_proveedor(self):
        self._abrir_form(None)

    def _editar_proveedor(self, prov):
        self._abrir_form(prov)

    def _abrir_form(self, prov=None):
        """Formulario para crear o editar un proveedor."""
        es_nuevo = prov is None
        titulo = "Nuevo Proveedor" if es_nuevo else f"Editar: {prov['nombre']}"

        dlg = tk.Toplevel(self.parent)
        dlg.title(titulo)
        dlg.geometry("420x320")
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
                         insertbackground=COLORES['acento'], relief='solid', bd=1)
            e.insert(0, val)
            e.pack(fill='x', ipady=5)
            return e

        e_nombre = campo("Nombre *", '' if es_nuevo else prov['nombre'])
        e_celular = campo("Celular", '' if es_nuevo else (prov['celular'] or ''))
        e_documento = campo("Documento / NIT", '' if es_nuevo else (prov['documento'] or ''))
        e_email = campo("Email", '' if es_nuevo else (prov['email'] or ''))

        def guardar():
            nombre = e_nombre.get().strip()
            if not nombre:
                messagebox.showwarning("Requerido", "El nombre es obligatorio", parent=dlg)
                return
            try:
                with conexion_segura() as conn:
                    if es_nuevo:
                        conn.execute("""
                            INSERT INTO proveedores (nombre, celular, documento, email)
                            VALUES (?, ?, ?, ?)
                        """, (nombre, e_celular.get().strip() or None,
                              e_documento.get().strip() or None,
                              e_email.get().strip() or None))
                    else:
                        conn.execute("""
                            UPDATE proveedores SET nombre=?, celular=?, documento=?, email=?
                            WHERE id_proveedor=?
                        """, (nombre, e_celular.get().strip() or None,
                              e_documento.get().strip() or None,
                              e_email.get().strip() or None,
                              prov['id_proveedor']))
                dlg.destroy()
                self._cargar_proveedores()
            except Exception as e:
                messagebox.showerror("Error", f"Error al guardar: {e}", parent=dlg)

        btns = tk.Frame(dlg, bg=COLORES['fondo_card'])
        btns.pack(fill='x', padx=20, pady=16)
        crear_boton(btns, "Guardar", guardar, tipo='exito').pack(side='right', padx=4)
        crear_boton(btns, "Cancelar", dlg.destroy, tipo='secundario').pack(side='right', padx=4)

    def _eliminar_proveedor(self, prov):
        if not messagebox.askyesno("Confirmar",
                                    f"Eliminar proveedor '{prov['nombre']}'?\n"
                                    "Se eliminarán también todas sus compras registradas.",
                                    parent=self.parent):
            return
        try:
            with conexion_segura() as conn:
                conn.execute("DELETE FROM compras_proveedor WHERE id_proveedor=?", (prov['id_proveedor'],))
                conn.execute("DELETE FROM proveedores WHERE id_proveedor=?", (prov['id_proveedor'],))
            self.proveedor_sel = None
            self._mostrar_placeholder()
            self._cargar_proveedores()
        except Exception as e:
            messagebox.showerror("Error", f"Error al eliminar: {e}")

    def detener(self):
        pass