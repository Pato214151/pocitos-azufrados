"""
Módulo de Pagos - Club Los Pocitos Azufrados
Gestión de pagos de cuentas abiertas (parciales o completos)
"""

import logging
import tkinter as tk
from tkinter import ttk, messagebox
import os, sys, datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from utils.tema_corporativo import COLORES, FUENTES, crear_boton, format_money, aplicar_estilo_tabla
from database.connection import get_connection, conexion_segura
from utils.logger import log_auditoria


def _leer_metodos_pago():
    """Lee los métodos de pago habilitados desde la tabla configuracion."""
    try:
        with conexion_segura() as conn:
            row = conn.execute(
                "SELECT valor FROM configuracion WHERE clave = 'metodos_pago_habilitados'"
            ).fetchone()
            if row and row['valor']:
                return row['valor'].split(',')
    except Exception as e:
        logging.getLogger("pocitos").warning(f"No se pudo leer metodos_pago_habilitados: {e}")
    return ['EFECTIVO', 'NEQUI', 'DAVIPLATA', 'BANCOLOMBIA', 'TRANSFERENCIA']


class PagosModule:
    def __init__(self, parent, usuario):
        self.parent = parent
        self.usuario = usuario
        self.venta_seleccionada = None
        self.ventas_abiertas = []

        self._crear_interfaz()
        self._cargar_cuentas_abiertas()

    def _crear_interfaz(self):
        """Interfaz principal de pagos"""
        # Header
        header = tk.Frame(self.parent, bg=COLORES['primario'])
        header.pack(fill='x')

        inner_hdr = tk.Frame(header, bg=COLORES['primario'], padx=15, pady=10)
        inner_hdr.pack(fill='x')

        tk.Label(inner_hdr, text="Gestion de Pagos",
                 font=FUENTES['encabezado'], fg=COLORES['texto_claro'],
                 bg=COLORES['primario']).pack(side='left')

        # ========== CUERPO PRINCIPAL ==========
        body = tk.Frame(self.parent, bg=COLORES['fondo'])
        body.pack(fill='both', expand=True, padx=15, pady=5)

        # ========== IZQUIERDA: Formulario de pago ==========
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

        tk.Label(_finner, text="Registrar Pago", font=FUENTES['encabezado'],
                 fg=COLORES['texto'], bg=COLORES['fondo_card']).pack(padx=15, pady=(15, 10), anchor='w')

        # Venta/Número
        frame_venta = tk.Frame(_finner, bg=COLORES['fondo_card'])
        frame_venta.pack(fill='x', padx=15, pady=8)
        tk.Label(frame_venta, text="Venta/Cuenta", font=FUENTES['pequena'],
                 fg=COLORES['texto_secundario'], bg=COLORES['fondo_card']).pack(anchor='w')
        self.combo_venta = ttk.Combobox(frame_venta, state='readonly', font=FUENTES['input'])
        self.combo_venta.pack(fill='x', ipady=6)
        self.combo_venta.bind('<<ComboboxSelected>>', self._on_venta_select)

        # Info de saldo
        self.lbl_info = tk.Label(_finner, text="", font=FUENTES['pequena'],
                                 fg=COLORES['primario'], bg=COLORES['fondo_card'])
        self.lbl_info.pack(anchor='w', padx=15, pady=8)

        # Monto del pago
        frame_monto = tk.Frame(_finner, bg=COLORES['fondo_card'])
        frame_monto.pack(fill='x', padx=15, pady=8)
        tk.Label(frame_monto, text="Monto a Pagar", font=FUENTES['pequena'],
                 fg=COLORES['texto_secundario'], bg=COLORES['fondo_card']).pack(anchor='w')
        self.entry_monto = tk.Entry(frame_monto, font=FUENTES['input'],
                                    relief='solid', bd=1, highlightthickness=1,
                                    highlightbackground=COLORES['borde'])
        self.entry_monto.pack(fill='x', ipady=6)

        # Método de pago
        frame_metodo = tk.Frame(_finner, bg=COLORES['fondo_card'])
        frame_metodo.pack(fill='x', padx=15, pady=8)
        tk.Label(frame_metodo, text="Método de Pago", font=FUENTES['pequena'],
                 fg=COLORES['texto_secundario'], bg=COLORES['fondo_card']).pack(anchor='w')
        self.combo_metodo = ttk.Combobox(frame_metodo, state='readonly', font=FUENTES['input'],
                                         values=_leer_metodos_pago())
        self.combo_metodo.set('EFECTIVO')
        self.combo_metodo.pack(fill='x', ipady=6)

        # Referencia (para transferencias)
        frame_ref = tk.Frame(_finner, bg=COLORES['fondo_card'])
        frame_ref.pack(fill='x', padx=15, pady=8)
        tk.Label(frame_ref, text="Referencia (Opcional)", font=FUENTES['pequena'],
                 fg=COLORES['texto_secundario'], bg=COLORES['fondo_card']).pack(anchor='w')
        self.entry_ref = tk.Entry(frame_ref, font=FUENTES['input'],
                                  relief='solid', bd=1, highlightthickness=1,
                                  highlightbackground=COLORES['borde'])
        self.entry_ref.pack(fill='x', ipady=6)

        # Botones
        btn_frame = tk.Frame(_finner, bg=COLORES['fondo_card'])
        btn_frame.pack(fill='x', padx=15, pady=(10, 15))

        crear_boton(btn_frame, "Registrar Pago", self._registrar_pago,
                   tipo='exito').pack(fill='x', pady=4)
        crear_boton(btn_frame, "Limpiar", self._limpiar_formulario,
                   tipo='secundario').pack(fill='x')

        # ========== DERECHA: Tabla de cuentas abiertas ==========
        right = tk.Frame(body, bg=COLORES['fondo'])
        right.pack(side='right', fill='both', expand=True)

        tk.Label(right, text="Cuentas Abiertas (Pendientes de Pago)", font=FUENTES['subtitulo'],
                 fg=COLORES['texto'], bg=COLORES['fondo']).pack(anchor='w', pady=(0, 8))

        tabla_frame = tk.Frame(right, bg=COLORES['fondo_card'],
                               highlightbackground=COLORES['borde'], highlightthickness=1)
        tabla_frame.pack(fill='both', expand=True)

        self.tree_cuentas = ttk.Treeview(tabla_frame, height=15,
                                         columns=('numero', 'cliente', 'total', 'pagado', 'saldo', 'fecha'),
                                         show='headings')

        self.tree_cuentas.column('numero', width=120, anchor='center')
        self.tree_cuentas.column('cliente', width=150, anchor='w')
        self.tree_cuentas.column('total', width=100, anchor='e')
        self.tree_cuentas.column('pagado', width=100, anchor='e')
        self.tree_cuentas.column('saldo', width=100, anchor='e')
        self.tree_cuentas.column('fecha', width=130, anchor='center')

        self.tree_cuentas.heading('numero', text='Nº Venta')
        self.tree_cuentas.heading('cliente', text='Cliente')
        self.tree_cuentas.heading('total', text='Total')
        self.tree_cuentas.heading('pagado', text='Pagado')
        self.tree_cuentas.heading('saldo', text='Saldo')
        self.tree_cuentas.heading('fecha', text='Fecha')

        aplicar_estilo_tabla(self.tree_cuentas)
        _tsb = ttk.Scrollbar(tabla_frame, orient='vertical', command=self.tree_cuentas.yview)
        self.tree_cuentas.configure(yscrollcommand=_tsb.set)
        self.tree_cuentas.pack(side='left', fill='both', expand=True)
        _tsb.pack(side='right', fill='y')
        self.tree_cuentas.bind('<Button-1>', self._on_cuenta_click)

    def _cargar_cuentas_abiertas(self):
        """Carga las cuentas abiertas (con saldo pendiente)"""
        try:
            with conexion_segura() as conn:
                rows = conn.execute("""
                    SELECT id_venta, numero_venta, cliente_nombre, total, total_pagado, saldo_pendiente, fecha_creacion
                    FROM ventas
                    WHERE estado = 'ABIERTA' AND saldo_pendiente > 0
                    ORDER BY fecha_creacion DESC
                """).fetchall()

                # Actualizar combo
                opciones = [f"{row['numero_venta']} - {row['cliente_nombre']}" for row in rows]
                self.combo_venta['values'] = opciones

                # Actualizar tabla
                for item in self.tree_cuentas.get_children():
                    self.tree_cuentas.delete(item)

                self.ventas_abiertas = []

                for i, row in enumerate(rows):
                    tag = 'alerta'  # Todas las cuentas abiertas son alerta
                    self.tree_cuentas.insert('', 'end', values=(
                        row['numero_venta'],
                        row['cliente_nombre'],
                        format_money(row['total']),
                        format_money(row['total_pagado']),
                        format_money(row['saldo_pendiente']),
                        row['fecha_creacion'][:10]
                    ), tags=(tag,), iid=row['id_venta'])

                    self.ventas_abiertas.append(row)

        except Exception as e:
            messagebox.showerror("Error", f"Error al cargar cuentas abiertas: {str(e)}")

    def _on_cuenta_click(self, event):
        """Maneja clic en una cuenta"""
        item = self.tree_cuentas.selection()
        if item:
            self.venta_seleccionada = int(item[0])
            venta = next((v for v in self.ventas_abiertas if v['id_venta'] == self.venta_seleccionada), None)
            if venta:
                idx = next((i for i, v in enumerate(self.ventas_abiertas) if v['id_venta'] == self.venta_seleccionada), 0)
                self.combo_venta.current(idx)
                self._on_venta_select()

    def _on_venta_select(self, event=None):
        """Maneja selección de venta en el combo"""
        sel = self.combo_venta.current()
        if sel >= 0 and sel < len(self.ventas_abiertas):
            venta = self.ventas_abiertas[sel]
            self.venta_seleccionada = venta['id_venta']

            info_text = f"Total: {format_money(venta['total'])} | Pagado: {format_money(venta['total_pagado'])} | Saldo: {format_money(venta['saldo_pendiente'])}"
            self.lbl_info.config(text=info_text)

            # Llenar monto con saldo pendiente
            self.entry_monto.delete(0, tk.END)
            self.entry_monto.insert(0, str(int(venta['saldo_pendiente'])))

    def _registrar_pago(self):
        """Registra un pago para una cuenta abierta"""
        if self.venta_seleccionada is None:
            messagebox.showwarning("Seleccione una Cuenta", "Por favor seleccione una cuenta de la lista")
            return

        venta = next((v for v in self.ventas_abiertas if v['id_venta'] == self.venta_seleccionada), None)
        if not venta:
            messagebox.showerror("Error", "Venta no encontrada")
            return

        monto_str = self.entry_monto.get().strip()
        if not monto_str:
            messagebox.showwarning("Campo Requerido", "Por favor ingrese el monto a pagar")
            return

        try:
            monto = float(monto_str)
            if monto <= 0:
                raise ValueError()

            if monto > venta['saldo_pendiente']:
                messagebox.showerror("Error", f"El monto no puede exceder el saldo pendiente ({format_money(venta['saldo_pendiente'])})")
                return

        except ValueError:
            messagebox.showerror("Error", "Ingrese un monto válido")
            return

        metodo = self.combo_metodo.get()
        referencia = self.entry_ref.get().strip() or None

        try:
            with conexion_segura() as conn:
                # Registrar pago
                conn.execute("""
                    INSERT INTO pagos (id_venta, valor, metodo_pago, referencia, usuario_registro)
                    VALUES (?, ?, ?, ?, ?)
                """, (self.venta_seleccionada, monto, metodo, referencia, self.usuario['usuario']))

                # Actualizar venta
                nuevo_pagado = venta['total_pagado'] + monto
                nuevo_saldo = venta['total'] - nuevo_pagado

                nuevo_estado = 'PAGADA' if nuevo_saldo <= 0 else 'ABIERTA'

                conn.execute("""
                    UPDATE ventas
                    SET total_pagado = ?, saldo_pendiente = ?, estado = ?, fecha_pago = datetime('now','localtime')
                    WHERE id_venta = ?
                """, (nuevo_pagado, max(0, nuevo_saldo), nuevo_estado, self.venta_seleccionada))

                log_auditoria(conn, 'pagos', self.venta_seleccionada, 'INSERT',
                            self.usuario['usuario'], f"Pago de {format_money(monto)} - {metodo}")

            msg = f"Pago registrado: {format_money(monto)}"
            if nuevo_estado == 'PAGADA':
                msg += "\nCuenta cerrada completamente"

            messagebox.showinfo("Exito", msg)
            self._limpiar_formulario()
            self._cargar_cuentas_abiertas()

        except Exception as e:
            messagebox.showerror("Error", f"Error al registrar pago: {str(e)}")

    def _limpiar_formulario(self):
        """Limpia el formulario"""
        self.combo_venta.set('')
        self.entry_monto.delete(0, tk.END)
        self.combo_metodo.set('EFECTIVO')
        self.entry_ref.delete(0, tk.END)
        self.lbl_info.config(text="")
        self.venta_seleccionada = None

    def detener(self):
        try:
            self._form_canvas.unbind_all('<MouseWheel>')
            self._form_canvas.unbind_all('<Button-4>')
            self._form_canvas.unbind_all('<Button-5>')
        except Exception:
            pass