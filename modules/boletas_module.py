"""
Módulo de Boletas de Entrada - Club Los Pocitos Azufrados
Venta rápida de entradas al balneario (35,000 COP por persona)
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import logging
import os, sys, datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from utils.tema_corporativo import COLORES, FUENTES, crear_boton, format_money, aplicar_estilo_tabla
from database.connection import get_connection, conexion_segura
from models.series import obtener_proximo_numero_boleta
from utils.logger import log_auditoria
from utils.printing import imprimir_recibo_boleta


class BoletasModule:
    PRECIO_PERSONA = 35000  # Valor fallback; se sobreescribe desde tabla configuracion

    def __init__(self, parent, usuario):
        self.parent = parent
        self.usuario = usuario
        self.boletas_hoy = []
        self.PRECIO_PERSONA = self._leer_precio_boleta()

        self._crear_interfaz()
        self._cargar_boletas_hoy()

    def _leer_precio_boleta(self):
        """Lee el precio por persona desde la tabla configuracion."""
        try:
            with conexion_segura() as conn:
                row = conn.execute(
                    "SELECT valor FROM configuracion WHERE clave = 'precio_boleta_persona'"
                ).fetchone()
                if row and row['valor']:
                    return int(float(row['valor']))
        except Exception as e:
            logging.getLogger("pocitos").warning(f"No se pudo leer precio_boleta_persona: {e}")
        return 35000  # Fallback si la BD no tiene el valor

    def _crear_interfaz(self):
        """Interfaz principal de boletas de entrada"""
        # Header
        header = tk.Frame(self.parent, bg=COLORES['primario'])
        header.pack(fill='x')

        inner_hdr = tk.Frame(header, bg=COLORES['primario'], padx=15, pady=10)
        inner_hdr.pack(fill='x')

        tk.Label(inner_hdr, text="Boletas de Entrada",
                 font=FUENTES['encabezado'], fg=COLORES['texto_claro'],
                 bg=COLORES['primario']).pack(side='left')

        # Precio por persona
        info_frame = tk.Frame(inner_hdr, bg=COLORES['primario'])
        info_frame.pack(side='right')
        tk.Label(info_frame, text=f"Precio: {format_money(self.PRECIO_PERSONA)} por persona",
                 font=FUENTES['normal'], fg=COLORES['acento'],
                 bg=COLORES['primario']).pack()

        # ========== CUERPO PRINCIPAL ==========
        body_outer = tk.Frame(self.parent, bg=COLORES['fondo'])
        body_outer.pack(fill='both', expand=True)

        # Canvas scrollable
        self._canvas_boletas = tk.Canvas(body_outer, bg=COLORES['fondo'], highlightthickness=0)
        sb = ttk.Scrollbar(body_outer, orient='vertical', command=self._canvas_boletas.yview)
        self._canvas_boletas.configure(yscrollcommand=sb.set)
        sb.pack(side='right', fill='y')
        self._canvas_boletas.pack(side='left', fill='both', expand=True)

        scroll_frame = tk.Frame(self._canvas_boletas, bg=COLORES['fondo'])
        self._win = self._canvas_boletas.create_window((0, 0), window=scroll_frame, anchor='nw')
        self._canvas_boletas.bind('<Configure>', lambda e: self._canvas_boletas.itemconfig(self._win, width=e.width))
        scroll_frame.bind('<Configure>', lambda e: self._canvas_boletas.configure(scrollregion=self._canvas_boletas.bbox('all')))

        # MouseWheel binding
        def _on_wheel(e):
            self._canvas_boletas.yview_scroll(int(-1*(e.delta/120)), "units")
        self._canvas_boletas.bind_all('<MouseWheel>', _on_wheel)
        self._canvas_boletas.bind_all('<Button-4>', lambda e: self._canvas_boletas.yview_scroll(-1, 'units'))
        self._canvas_boletas.bind_all('<Button-5>', lambda e: self._canvas_boletas.yview_scroll(1, 'units'))

        # Agregar padding interior
        body = tk.Frame(scroll_frame, bg=COLORES['fondo'])
        body.pack(fill='both', expand=True, padx=15, pady=5)

        # ========== IZQUIERDA: Formulario ==========
        left = tk.Frame(body, bg=COLORES['fondo_card'],
                       highlightbackground=COLORES['borde'], highlightthickness=1)
        left.pack(side='left', fill='y', padx=(0, 8), ipady=15)
        left.pack_propagate(False)
        left.config(width=300)

        tk.Label(left, text="Nueva Boleta", font=FUENTES['encabezado'],
                 fg=COLORES['texto'], bg=COLORES['fondo_card']).pack(padx=15, pady=(15, 10), anchor='w')

        # Nombre del visitante
        frame_nombre = tk.Frame(left, bg=COLORES['fondo_card'])
        frame_nombre.pack(fill='x', padx=15, pady=8)
        tk.Label(frame_nombre, text="Nombre del Visitante", font=FUENTES['pequena'],
                 fg=COLORES['texto_secundario'], bg=COLORES['fondo_card']).pack(anchor='w')
        self.entry_nombre = tk.Entry(frame_nombre, font=FUENTES['input'],
                                     relief='solid', bd=1, highlightthickness=1,
                                     highlightbackground=COLORES['borde'])
        self.entry_nombre.pack(fill='x', ipady=6)

        # Documento
        frame_doc = tk.Frame(left, bg=COLORES['fondo_card'])
        frame_doc.pack(fill='x', padx=15, pady=8)
        tk.Label(frame_doc, text="Documento de Identidad", font=FUENTES['pequena'],
                 fg=COLORES['texto_secundario'], bg=COLORES['fondo_card']).pack(anchor='w')
        self.entry_documento = tk.Entry(frame_doc, font=FUENTES['input'],
                                        relief='solid', bd=1, highlightthickness=1,
                                        highlightbackground=COLORES['borde'])
        self.entry_documento.pack(fill='x', ipady=6)

        # Número de personas
        frame_personas = tk.Frame(left, bg=COLORES['fondo_card'])
        frame_personas.pack(fill='x', padx=15, pady=8)
        tk.Label(frame_personas, text="Cantidad de Personas", font=FUENTES['pequena'],
                 fg=COLORES['texto_secundario'], bg=COLORES['fondo_card']).pack(anchor='w')

        personas_inner = tk.Frame(frame_personas, bg=COLORES['fondo_card'])
        personas_inner.pack(fill='x')

        self.entry_personas = tk.Spinbox(personas_inner, from_=1, to=100, font=FUENTES['input'],
                                         relief='solid', bd=1, highlightthickness=1,
                                         highlightbackground=COLORES['borde'], width=10)
        self.entry_personas.delete(0, 'end')
        self.entry_personas.insert(0, '1')
        self.entry_personas.pack(side='left', ipady=6)
        self.entry_personas.bind('<KeyRelease>', self._actualizar_total)

        # Total
        tk.Label(personas_inner, text="", font=FUENTES['precio'],
                 fg=COLORES['primario'], bg=COLORES['fondo_card']).pack(side='right', padx=10)
        self.lbl_total = personas_inner.winfo_children()[-1]

        self._actualizar_total()

        # Método de pago
        frame_metodo = tk.Frame(left, bg=COLORES['fondo_card'])
        frame_metodo.pack(fill='x', padx=15, pady=8)
        tk.Label(frame_metodo, text="Método de Pago", font=FUENTES['pequena'],
                 fg=COLORES['texto_secundario'], bg=COLORES['fondo_card']).pack(anchor='w')

        self.combo_metodo = ttk.Combobox(frame_metodo, state='readonly', font=FUENTES['input'],
                                         values=['EFECTIVO', 'NEQUI', 'DAVIPLATA', 'BANCOLOMBIA', 'TRANSFERENCIA'])
        self.combo_metodo.set('EFECTIVO')
        self.combo_metodo.pack(fill='x', ipady=6)

        # Notas
        frame_notas = tk.Frame(left, bg=COLORES['fondo_card'])
        frame_notas.pack(fill='x', padx=15, pady=8)
        tk.Label(frame_notas, text="Notas (Opcional)", font=FUENTES['pequena'],
                 fg=COLORES['texto_secundario'], bg=COLORES['fondo_card']).pack(anchor='w')
        self.text_notas = tk.Text(frame_notas, font=FUENTES['normal'], height=3,
                                  relief='solid', bd=1, highlightthickness=1,
                                  highlightbackground=COLORES['borde'])
        self.text_notas.pack(fill='x', ipady=6)

        # Botones
        btn_frame = tk.Frame(left, bg=COLORES['fondo_card'])
        btn_frame.pack(fill='x', padx=15, pady=(10, 15))

        crear_boton(btn_frame, "Guardar Boleta", self._guardar_boleta,
                   tipo='exito').pack(fill='x', pady=4)
        crear_boton(btn_frame, "Limpiar", self._limpiar_formulario,
                   tipo='secundario').pack(fill='x')

        # ========== DERECHA: Historial de boletas hoy ==========
        right = tk.Frame(body, bg=COLORES['fondo'])
        right.pack(side='right', fill='both', expand=True)

        tk.Label(right, text="Boletas de Hoy", font=FUENTES['subtitulo'],
                 fg=COLORES['texto'], bg=COLORES['fondo']).pack(anchor='w', pady=(0, 8))

        # Tabla de boletas
        tabla_frame = tk.Frame(right, bg=COLORES['fondo_card'],
                               highlightbackground=COLORES['borde'], highlightthickness=1)
        tabla_frame.pack(fill='both', expand=True)

        self.tree_boletas = ttk.Treeview(tabla_frame, height=15,
                                         columns=('numero', 'visitante', 'personas', 'total', 'metodo', 'hora'),
                                         show='headings')

        self.tree_boletas.column('numero', width=120, anchor='center')
        self.tree_boletas.column('visitante', width=150, anchor='w')
        self.tree_boletas.column('personas', width=80, anchor='center')
        self.tree_boletas.column('total', width=100, anchor='e')
        self.tree_boletas.column('metodo', width=100, anchor='center')
        self.tree_boletas.column('hora', width=100, anchor='center')

        self.tree_boletas.heading('numero', text='Boleta')
        self.tree_boletas.heading('visitante', text='Visitante')
        self.tree_boletas.heading('personas', text='Personas')
        self.tree_boletas.heading('total', text='Total')
        self.tree_boletas.heading('metodo', text='Método')
        self.tree_boletas.heading('hora', text='Hora')

        aplicar_estilo_tabla(self.tree_boletas)
        self.tree_boletas.pack(fill='both', expand=True)

    def _actualizar_total(self, event=None):
        """Actualiza el total según cantidad de personas"""
        try:
            personas = int(self.entry_personas.get())
            total = personas * self.PRECIO_PERSONA
            self.lbl_total.config(text=format_money(total))
        except ValueError:
            self.lbl_total.config(text=format_money(0))

    def _cargar_boletas_hoy(self):
        """Carga boletas de hoy"""
        try:
            with conexion_segura() as conn:
                hoy = datetime.date.today().isoformat()
                rows = conn.execute("""
                    SELECT numero_boleta, nombre_visitante, cantidad_personas, total, metodo_pago, hora_entrada
                    FROM boletas_entrada
                    WHERE DATE(hora_entrada) = ?
                    ORDER BY hora_entrada DESC
                """, (hoy,)).fetchall()

                # Limpiar árbol
                for item in self.tree_boletas.get_children():
                    self.tree_boletas.delete(item)

                # Agregar filas
                for i, row in enumerate(rows):
                    tag = 'par' if i % 2 == 0 else 'impar'
                    self.tree_boletas.insert('', 'end', values=(
                        row['numero_boleta'],
                        row['nombre_visitante'],
                        row['cantidad_personas'],
                        format_money(row['total']),
                        row['metodo_pago'],
                        row['hora_entrada'][11:16]  # Solo hora
                    ), tags=(tag,))

                self.boletas_hoy = rows
        except Exception as e:
            messagebox.showerror("Error", f"Error al cargar boletas: {str(e)}")

    def _guardar_boleta(self):
        """Guarda una nueva boleta"""
        # Validar campos
        nombre = self.entry_nombre.get().strip()
        documento = self.entry_documento.get().strip()

        if not nombre or not documento:
            messagebox.showwarning("Campos Requeridos", "Por favor complete nombre y documento")
            return

        try:
            personas = int(self.entry_personas.get())
            if personas < 1:
                raise ValueError("Mínimo 1 persona")
        except ValueError:
            messagebox.showerror("Error", "Ingrese un número válido de personas")
            return

        # Generar número de boleta
        try:
            numero_boleta = obtener_proximo_numero_boleta()
        except Exception as e:
            messagebox.showerror("Error al generar boleta", f"Error: {str(e)}")
            return

        total = personas * self.PRECIO_PERSONA
        metodo = self.combo_metodo.get()
        notas = self.text_notas.get("1.0", "end").strip()

        try:
            with conexion_segura() as conn:
                # Crear venta asociada
                num_venta = f"BOL-{datetime.date.today().isoformat()}-{numero_boleta[-6:]}"

                conn.execute("""
                    INSERT INTO ventas (
                        numero_venta, tipo, estado, cliente_nombre, cliente_documento,
                        num_personas, subtotal, descuento, impuesto, total, total_pagado,
                        saldo_pendiente, metodo_pago, id_usuario, usuario_nombre
                    ) VALUES (?, 'boleta', 'PAGADA', ?, ?, ?, ?, 0, 0, ?, ?, 0, ?, ?, ?)
                """, (num_venta, nombre, documento, personas, total, total, total,
                      metodo, self.usuario['id_usuario'], self.usuario['usuario']))

                venta_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

                # Crear boleta
                cursor_b = conn.execute("""
                    INSERT INTO boletas_entrada (
                        numero_boleta, id_venta, nombre_visitante, documento_visitante,
                        cantidad_personas, precio_persona, total, metodo_pago, notas, id_usuario
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (numero_boleta, venta_id, nombre, documento, personas,
                      self.PRECIO_PERSONA, total, metodo, notas, self.usuario['id_usuario']))

                boleta_id = cursor_b.lastrowid

                # Registrar en auditoría
                log_auditoria(conn, 'boletas_entrada', venta_id, 'INSERT',
                            self.usuario['usuario'], f"Boleta {numero_boleta}")

            messagebox.showinfo("Exito", f"Boleta {numero_boleta} registrada exitosamente\nTotal: {format_money(total)}")

            # Ofrecer imprimir boleta
            if messagebox.askyesno("Imprimir", "Desea imprimir la boleta?"):
                imprimir_recibo_boleta(boleta_id)

            self._limpiar_formulario()
            self._cargar_boletas_hoy()

        except Exception as e:
            messagebox.showerror("Error", f"Error al guardar boleta: {str(e)}")

    def _limpiar_formulario(self):
        """Limpia todos los campos del formulario"""
        self.entry_nombre.delete(0, tk.END)
        self.entry_documento.delete(0, tk.END)
        self.entry_personas.delete(0, 'end')
        self.entry_personas.insert(0, '1')
        self.combo_metodo.set('EFECTIVO')
        self.text_notas.delete("1.0", "end")
        self._actualizar_total()
        self.entry_nombre.focus()

    def detener(self):
        try:
            self._canvas_boletas.unbind_all('<MouseWheel>')
            self._canvas_boletas.unbind_all('<Button-4>')
            self._canvas_boletas.unbind_all('<Button-5>')
        except Exception:
            pass