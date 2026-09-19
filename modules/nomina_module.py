"""
Módulo de Nómina Semanal - Club Los Pocitos Azufrados
Control de turnos y pago de empleados por semana (lunes a domingo).
Acceso: administrador y contadora.
"""
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import os, sys, datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from utils.tema_corporativo import COLORES, FUENTES, crear_boton, format_money, aplicar_estilo_tabla
from database.connection import conexion_segura
from utils.logger import log_auditoria


DIAS_SEMANA = ['Lunes', 'Martes', 'Miercoles', 'Jueves', 'Viernes', 'Sabado', 'Domingo']
TIPO_TURNO  = ['Normal', 'Festivo']


class NominaModule:
    """Pantalla de nómina semanal: turnos por empleado y pago."""
    def __init__(self, parent, usuario):
        self.parent = parent
        self.usuario = usuario
        self._semana_offset = 0   # 0 = semana actual, -1 = semana pasada, etc.
        self._empleado_sel = None
        self._crear_interfaz()
        self._asegurar_tablas()
        self._cargar_empleados()
        self._cargar_semana()

    # ─── UI ───────────────────────────────────────────────────────────────────
    def _crear_interfaz(self):
        """Arma la pantalla: selector de semana, empleados y grilla de turnos."""
        # Header
        header = tk.Frame(self.parent, bg=COLORES['primario'])
        header.pack(fill='x')
        inner_hdr = tk.Frame(header, bg=COLORES['primario'], padx=15, pady=10)
        inner_hdr.pack(fill='x')
        tk.Label(inner_hdr, text="Nomina Semanal",
                 font=FUENTES['encabezado'], fg=COLORES['texto_claro'],
                 bg=COLORES['primario']).pack(side='left')
        self.lbl_semana = tk.Label(inner_hdr, text="",
                                    font=FUENTES['normal_bold'],
                                    fg=COLORES['acento'], bg=COLORES['primario'])
        self.lbl_semana.pack(side='right')

        # Barra de navegación de semana
        nav = tk.Frame(self.parent, bg=COLORES['fondo'], padx=15, pady=8)
        nav.pack(fill='x')
        crear_boton(nav, "< Semana anterior", self._semana_anterior,
                    tipo='secundario').pack(side='left', padx=(0, 4))
        crear_boton(nav, "Semana actual", self._semana_actual,
                    tipo='primario').pack(side='left', padx=4)
        crear_boton(nav, "Semana siguiente >", self._semana_siguiente,
                    tipo='secundario').pack(side='left', padx=4)
        crear_boton(nav, "+ Empleado", self._agregar_empleado,
                    tipo='exito').pack(side='right')

        # Cuerpo con Canvas scrollable para que el panel detalle y botones sean siempre visibles
        outer = tk.Frame(self.parent, bg=COLORES['fondo'])
        outer.pack(fill='both', expand=True)

        self._canvas_nom = tk.Canvas(outer, bg=COLORES['fondo'], highlightthickness=0)
        _sb_nom = ttk.Scrollbar(outer, orient='vertical', command=self._canvas_nom.yview)
        self._canvas_nom.configure(yscrollcommand=_sb_nom.set)
        _sb_nom.pack(side='right', fill='y')
        self._canvas_nom.pack(side='left', fill='both', expand=True)

        body = tk.Frame(self._canvas_nom, bg=COLORES['fondo'])
        self._win_nom = self._canvas_nom.create_window((0, 0), window=body, anchor='nw')
        self._canvas_nom.bind('<Configure>',
                              lambda e: self._canvas_nom.itemconfig(self._win_nom, width=e.width))
        body.bind('<Configure>',
                  lambda e: self._canvas_nom.configure(scrollregion=self._canvas_nom.bbox('all')))

        def _scroll_nom_canvas(event):
            d = int(-1 * (event.delta / 120)) if event.delta else (1 if event.num == 5 else -1)
            self._canvas_nom.yview_scroll(d, 'units')
        self._canvas_nom.bind_all('<MouseWheel>', _scroll_nom_canvas)
        self._canvas_nom.bind_all('<Button-4>', _scroll_nom_canvas)
        self._canvas_nom.bind_all('<Button-5>', _scroll_nom_canvas)

        body_inner = tk.Frame(body, bg=COLORES['fondo'], padx=15, pady=8)
        body_inner.pack(fill='both', expand=True)
        body = body_inner  # alias para que el resto del código no cambie

        # Tabla de turnos
        tabla_frame = tk.Frame(body, bg=COLORES['fondo_card'],
                               highlightbackground=COLORES['borde'], highlightthickness=1)
        tabla_frame.pack(fill='x', pady=(0, 8))

        cols = ['empleado'] + [d[:3] for d in DIAS_SEMANA] + ['total_turnos', 'a_pagar', 'estado']
        self.tree = ttk.Treeview(tabla_frame, columns=cols, show='headings', height=10)
        aplicar_estilo_tabla(self.tree)

        self.tree.column('empleado', width=130, anchor='w')
        self.tree.heading('empleado', text='Empleado')
        for d in DIAS_SEMANA:
            col = d[:3]
            self.tree.column(col, width=60, anchor='center')
            self.tree.heading(col, text=d[:3])
        self.tree.column('total_turnos', width=65, anchor='center')
        self.tree.column('a_pagar', width=90, anchor='e')
        self.tree.column('estado', width=80, anchor='center')
        self.tree.heading('total_turnos', text='Turnos')
        self.tree.heading('a_pagar', text='A Pagar')
        self.tree.heading('estado', text='Estado')

        scrollbar = ttk.Scrollbar(tabla_frame, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        self.tree.bind('<<TreeviewSelect>>', self._on_select)
        self.tree.bind('<Double-1>', self._editar_turno_dia)

        # El scroll global lo maneja el canvas (definido arriba)

        # Panel inferior: detalle del empleado seleccionado
        self.panel_detalle = tk.Frame(body, bg=COLORES['fondo_card'],
                                       highlightbackground=COLORES['borde'], highlightthickness=1)
        self.panel_detalle.pack(fill='x', pady=(0, 4))
        self.lbl_detalle = tk.Label(self.panel_detalle,
                                     text="Seleccione un empleado para ver detalles.\n"
                                          "Doble clic en una fila para editar turnos del dia.",
                                     font=FUENTES['normal'], fg=COLORES['texto_secundario'],
                                     bg=COLORES['fondo_card'])
        self.lbl_detalle.pack(padx=15, pady=12)

        # Botones de acción
        btn_bar = tk.Frame(body, bg=COLORES['fondo'])
        btn_bar.pack(fill='x')
        self.btn_marcar_pagado = crear_boton(btn_bar, "Marcar Pagado",
                                              self._marcar_pagado, tipo='exito')
        self.btn_marcar_pagado.pack(side='left', padx=(0, 4))
        self.btn_editar_tarifas = crear_boton(btn_bar, "Editar Tarifas",
                                               self._editar_tarifas, tipo='agua')
        self.btn_editar_tarifas.pack(side='left', padx=4)
        crear_boton(btn_bar, "Exportar Excel", self._exportar_excel,
                    tipo='agua').pack(side='left', padx=4)

        # Resumen total semana
        self.lbl_total_semana = tk.Label(btn_bar, text="Total semana: $ 0",
                                          font=FUENTES['encabezado'],
                                          fg=COLORES['texto'], bg=COLORES['fondo'])
        self.lbl_total_semana.pack(side='right')

    # ─── DB ───────────────────────────────────────────────────────────────────
    def _asegurar_tablas(self):
        """Crea las tablas si no existen (idempotente)."""
        try:
            with conexion_segura() as conn:
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
                    CREATE TABLE IF NOT EXISTS nomina_turnos (
                        id_turno INTEGER PRIMARY KEY AUTOINCREMENT,
                        id_empleado INTEGER NOT NULL REFERENCES nomina_empleados(id_empleado),
                        semana_inicio TEXT NOT NULL,
                        dia_semana INTEGER NOT NULL,
                        tipo TEXT NOT NULL DEFAULT 'Normal'
                            CHECK(tipo IN ('Normal','Festivo','No trabajo')),
                        pagado INTEGER DEFAULT 0,
                        fecha_registro TEXT DEFAULT (datetime('now','localtime')),
                        UNIQUE(id_empleado, semana_inicio, dia_semana)
                    )
                """)
        except Exception as e:
            messagebox.showerror("Error BD", f"Error creando tablas de nomina: {e}")

    # ─── Navegación de semana ─────────────────────────────────────────────────
    def _lunes_de_semana(self):
        hoy = datetime.date.today()
        lunes = hoy - datetime.timedelta(days=hoy.weekday()) + datetime.timedelta(weeks=self._semana_offset)
        return lunes

    def _semana_anterior(self):
        self._semana_offset -= 1
        self._cargar_semana()

    def _semana_actual(self):
        self._semana_offset = 0
        self._cargar_semana()

    def _semana_siguiente(self):
        self._semana_offset += 1
        self._cargar_semana()

    # ─── Carga de datos ───────────────────────────────────────────────────────
    def _cargar_empleados(self):
        try:
            with conexion_segura() as conn:
                self.empleados = [dict(r) for r in conn.execute(
                    "SELECT * FROM nomina_empleados WHERE activo=1 ORDER BY nombre"
                ).fetchall()]
        except Exception:
            self.empleados = []

    def _cargar_semana(self):
        lunes = self._lunes_de_semana()
        domingo = lunes + datetime.timedelta(days=6)
        self.lbl_semana.config(
            text=f"Semana: {lunes.strftime('%d/%m')} — {domingo.strftime('%d/%m/%Y')}")

        for item in self.tree.get_children():
            self.tree.delete(item)

        total_semana = 0
        try:
            with conexion_segura() as conn:
                turnos_rows = conn.execute("""
                    SELECT id_empleado, dia_semana, tipo, pagado
                    FROM nomina_turnos
                    WHERE semana_inicio = ?
                """, (lunes.isoformat(),)).fetchall()

            turnos = {}
            for t in turnos_rows:
                turnos[(t['id_empleado'], t['dia_semana'])] = dict(t)

            for i, emp in enumerate(self.empleados):
                dias_cel = []
                n_normal = n_festivo = 0
                pagado = False
                for dia_idx in range(7):
                    t = turnos.get((emp['id_empleado'], dia_idx))
                    if t:
                        tipo = t['tipo']
                        if tipo == 'Normal':
                            dias_cel.append('N')
                            n_normal += 1
                        elif tipo == 'Festivo':
                            dias_cel.append('F')
                            n_festivo += 1
                        else:
                            dias_cel.append('-')
                        if t['pagado']:
                            pagado = True
                    else:
                        dias_cel.append('')

                a_pagar = (n_normal * (emp['tarifa_normal'] or 0) +
                           n_festivo * (emp['tarifa_festivo'] or 0))
                total_semana += a_pagar
                estado = "PAGADO" if pagado else ("PENDIENTE" if (n_normal + n_festivo) > 0 else "—")
                tag = 'pagado' if pagado else ('par' if i % 2 == 0 else 'impar')

                self.tree.insert('', 'end', iid=str(emp['id_empleado']),
                                  values=([emp['nombre']] + dias_cel +
                                          [n_normal + n_festivo, format_money(a_pagar), estado]),
                                  tags=(tag,))

            self.tree.tag_configure('pagado', background='#E8F5E9', foreground='#1B6E3A')
            self.lbl_total_semana.config(text=f"Total semana: {format_money(total_semana)}")

        except Exception as e:
            tk.Label(self.parent, text=f"Error: {e}", fg=COLORES['error'],
                     bg=COLORES['fondo']).pack()

    # ─── Selección y edición ──────────────────────────────────────────────────
    def _on_select(self, event=None):
        """Carga los turnos de la semana del empleado elegido."""
        sel = self.tree.selection()
        if not sel:
            self._empleado_sel = None
            return
        id_emp = int(sel[0])
        emp = next((e for e in self.empleados if e['id_empleado'] == id_emp), None)
        if not emp:
            return
        self._empleado_sel = emp
        lunes = self._lunes_de_semana()

        # Mostrar detalle
        for w in self.panel_detalle.winfo_children():
            w.destroy()

        f = tk.Frame(self.panel_detalle, bg=COLORES['fondo_card'], padx=15, pady=10)
        f.pack(fill='x')

        tk.Label(f, text=emp['nombre'], font=FUENTES['subtitulo'],
                 fg=COLORES['acento'], bg=COLORES['fondo_card']).grid(row=0, column=0, sticky='w', columnspan=4)
        tk.Label(f, text=f"Tarifa Normal: {format_money(emp['tarifa_normal'] or 0)}/turno",
                 font=FUENTES['normal'], fg=COLORES['texto_secundario'],
                 bg=COLORES['fondo_card']).grid(row=1, column=0, sticky='w', padx=(0, 20))
        tk.Label(f, text=f"Tarifa Festivo: {format_money(emp['tarifa_festivo'] or 0)}/turno",
                 font=FUENTES['normal'], fg=COLORES['texto_secundario'],
                 bg=COLORES['fondo_card']).grid(row=1, column=1, sticky='w')

        # Grid de días
        tk.Label(f, text="Turnos:", font=FUENTES['normal_bold'],
                 fg=COLORES['texto'], bg=COLORES['fondo_card']).grid(row=2, column=0, sticky='w', pady=(8, 4))

        try:
            with conexion_segura() as conn:
                turnos_emp = {t['dia_semana']: dict(t) for t in conn.execute("""
                    SELECT dia_semana, tipo, pagado FROM nomina_turnos
                    WHERE id_empleado=? AND semana_inicio=?
                """, (id_emp, lunes.isoformat())).fetchall()}
        except Exception:
            turnos_emp = {}

        dias_frame = tk.Frame(f, bg=COLORES['fondo_card'])
        dias_frame.grid(row=3, column=0, columnspan=6, sticky='w', pady=4)

        for dia_idx, dia_nombre in enumerate(DIAS_SEMANA):
            fecha_dia = lunes + datetime.timedelta(days=dia_idx)
            t = turnos_emp.get(dia_idx)
            tipo = t['tipo'] if t else None
            if tipo == 'Normal':
                bg_d, txt_d = '#E8F5E9', 'N'
            elif tipo == 'Festivo':
                bg_d, txt_d = '#FFF3E0', 'F'
            else:
                bg_d, txt_d = COLORES['gris_100'], '—'

            col_frame = tk.Frame(dias_frame, bg=COLORES['fondo_card'])
            col_frame.pack(side='left', padx=3)
            tk.Label(col_frame, text=dia_nombre[:3], font=FUENTES['pequena'],
                     fg=COLORES['texto_secundario'], bg=COLORES['fondo_card']).pack()
            tk.Label(col_frame, text=fecha_dia.strftime('%d'), font=FUENTES['pequena'],
                     fg=COLORES['texto_secundario'], bg=COLORES['fondo_card']).pack()
            btn_dia = tk.Button(col_frame, text=txt_d, width=4, height=2,
                                 font=FUENTES['normal_bold'], bg=bg_d,
                                 fg=COLORES['texto'], relief='solid', bd=1, cursor='hand2',
                                 command=lambda d=dia_idx: self._toggle_turno(d))
            btn_dia.pack()

        tk.Label(f, text="Clic en el dia para cambiar: vacio -> Normal -> Festivo -> vacio",
                 font=FUENTES['pequena'], fg=COLORES['texto_secundario'],
                 bg=COLORES['fondo_card']).grid(row=4, column=0, columnspan=6, sticky='w', pady=(4, 0))

    def _toggle_turno(self, dia_idx):
        if not self._empleado_sel:
            return
        lunes = self._lunes_de_semana()
        id_emp = self._empleado_sel['id_empleado']
        try:
            with conexion_segura() as conn:
                t = conn.execute("""
                    SELECT tipo FROM nomina_turnos
                    WHERE id_empleado=? AND semana_inicio=? AND dia_semana=?
                """, (id_emp, lunes.isoformat(), dia_idx)).fetchone()

                if not t:
                    nuevo = 'Normal'
                    conn.execute("""
                        INSERT INTO nomina_turnos (id_empleado, semana_inicio, dia_semana, tipo)
                        VALUES (?, ?, ?, ?)
                    """, (id_emp, lunes.isoformat(), dia_idx, nuevo))
                elif t['tipo'] == 'Normal':
                    nuevo = 'Festivo'
                    conn.execute("""
                        UPDATE nomina_turnos SET tipo=?
                        WHERE id_empleado=? AND semana_inicio=? AND dia_semana=?
                    """, (nuevo, id_emp, lunes.isoformat(), dia_idx))
                else:
                    conn.execute("""
                        DELETE FROM nomina_turnos
                        WHERE id_empleado=? AND semana_inicio=? AND dia_semana=?
                    """, (id_emp, lunes.isoformat(), dia_idx))

        except Exception as e:
            messagebox.showerror("Error", str(e))

        self._cargar_semana()
        try:
            self.tree.selection_set(str(id_emp))
            self._on_select()
        except Exception:
            pass

    def _editar_turno_dia(self, event=None):
        """Doble clic en la tabla abre el panel de detalle con toggle de dias."""
        self._on_select()

    def _marcar_pagado(self):
        if not self._empleado_sel:
            messagebox.showwarning("Seleccione", "Seleccione un empleado primero")
            return
        lunes = self._lunes_de_semana()
        id_emp = self._empleado_sel['id_empleado']
        try:
            with conexion_segura() as conn:
                n = conn.execute("""
                    SELECT COUNT(*) FROM nomina_turnos
                    WHERE id_empleado=? AND semana_inicio=? AND tipo IN ('Normal','Festivo')
                """, (id_emp, lunes.isoformat())).fetchone()[0]
                if n == 0:
                    messagebox.showinfo("Sin turnos", "Este empleado no tiene turnos registrados esta semana.")
                    return
                if not messagebox.askyesno("Confirmar",
                    f"Marcar todos los turnos de {self._empleado_sel['nombre']} como PAGADOS?"):
                    return
                conn.execute("""
                    UPDATE nomina_turnos SET pagado=1
                    WHERE id_empleado=? AND semana_inicio=?
                """, (id_emp, lunes.isoformat()))
                log_auditoria(conn, 'nomina_turnos', id_emp, 'UPDATE',
                              self.usuario.get('usuario', ''),
                              f"Pago marcado semana {lunes.isoformat()}")
            self._cargar_semana()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _editar_tarifas(self):
        """Diálogo para cambiar las tarifas por turno."""
        if not self._empleado_sel:
            messagebox.showwarning("Seleccione", "Seleccione un empleado primero")
            return
        emp = self._empleado_sel

        dlg = tk.Toplevel(self.parent.winfo_toplevel())
        dlg.title(f"Tarifas — {emp['nombre']}")
        dlg.geometry("320x240")
        dlg.resizable(False, False)
        dlg.grab_set()
        dlg.configure(bg=COLORES['fondo_card'])

        tk.Frame(dlg, bg=COLORES['primario'], height=4).pack(fill='x')
        f = tk.Frame(dlg, bg=COLORES['fondo_card'], padx=20, pady=16)
        f.pack(fill='both', expand=True)

        tk.Label(f, text=emp['nombre'], font=FUENTES['subtitulo'],
                 fg=COLORES['texto'], bg=COLORES['fondo_card']).pack(anchor='w', pady=(0, 12))

        tk.Label(f, text="Tarifa turno Normal ($):", font=FUENTES['normal'],
                 fg=COLORES['texto'], bg=COLORES['fondo_card']).pack(anchor='w')
        e_normal = tk.Entry(f, font=FUENTES['input'], relief='solid', bd=1)
        e_normal.insert(0, str(int(emp['tarifa_normal'] or 0)))
        e_normal.pack(fill='x', ipady=5, pady=(2, 10))

        tk.Label(f, text="Tarifa turno Festivo ($):", font=FUENTES['normal'],
                 fg=COLORES['texto'], bg=COLORES['fondo_card']).pack(anchor='w')
        e_festivo = tk.Entry(f, font=FUENTES['input'], relief='solid', bd=1)
        e_festivo.insert(0, str(int(emp['tarifa_festivo'] or 0)))
        e_festivo.pack(fill='x', ipady=5, pady=(2, 12))

        def guardar():
            try:
                tn = float(e_normal.get().replace(',', '').strip())
                tf = float(e_festivo.get().replace(',', '').strip())
            except ValueError:
                messagebox.showerror("Error", "Ingresa valores numericos.", parent=dlg)
                return
            try:
                # Advertir si hay semanas ya pagadas que no se recalcularán
                with conexion_segura() as conn:
                    semanas_pagadas = conn.execute("""
                        SELECT COUNT(DISTINCT semana_inicio) FROM nomina_turnos
                        WHERE id_empleado=? AND pagado=1
                    """, (emp['id_empleado'],)).fetchone()[0]
                if semanas_pagadas > 0:
                    if not messagebox.askyesno(
                        "Advertencia",
                        f"{emp['nombre']} tiene {semanas_pagadas} semana(s) ya marcadas como pagadas.\n"
                        "Cambiar la tarifa NO recalcula esos pagos anteriores.\n\n"
                        "¿Continuar de todas formas?",
                        parent=dlg
                    ):
                        return
                with conexion_segura() as conn:
                    conn.execute("""
                        UPDATE nomina_empleados SET tarifa_normal=?, tarifa_festivo=?
                        WHERE id_empleado=?
                    """, (tn, tf, emp['id_empleado']))
                messagebox.showinfo("Guardado", "Tarifas actualizadas.", parent=dlg)
                dlg.destroy()
                self._cargar_empleados()
                self._cargar_semana()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=dlg)

        btn_f = tk.Frame(f, bg=COLORES['fondo_card'])
        btn_f.pack(fill='x')
        crear_boton(btn_f, "Guardar", guardar, tipo='exito').pack(side='left', fill='x', expand=True, padx=(0, 4))
        crear_boton(btn_f, "Cancelar", dlg.destroy, tipo='secundario').pack(side='right')

    def _agregar_empleado(self):
        nombre = simpledialog.askstring("Nuevo Empleado", "Nombre del empleado:",
                                         parent=self.parent)
        if not nombre or not nombre.strip():
            return
        try:
            with conexion_segura() as conn:
                conn.execute(
                    "INSERT INTO nomina_empleados (nombre, tarifa_normal, tarifa_festivo) VALUES (?, 0, 0)",
                    (nombre.strip(),))
            self._cargar_empleados()
            self._cargar_semana()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _exportar_excel(self):
        """Exporta la nómina de la semana visible a Excel con formato."""
        try:
            import openpyxl
            from openpyxl.styles import (Font, PatternFill, Alignment,
                                          Border, Side, GradientFill)
            from openpyxl.utils import get_column_letter
        except ImportError:
            messagebox.showerror(
                "Dependencia faltante",
                "Se necesita openpyxl.\nEjecute: pip install openpyxl"
            )
            return

        lunes  = self._lunes_de_semana()
        domingo = lunes + datetime.timedelta(days=6)

        try:
            with conexion_segura() as conn:
                turnos_rows = conn.execute("""
                    SELECT id_empleado, dia_semana, tipo, pagado
                    FROM nomina_turnos WHERE semana_inicio=?
                """, (lunes.isoformat(),)).fetchall()
        except Exception as e:
            messagebox.showerror("Error", f"Error al leer datos: {e}")
            return

        turnos = {}
        for t in turnos_rows:
            turnos[(t['id_empleado'], t['dia_semana'])] = dict(t)

        # ── Estilos ──────────────────────────────────────────────────────
        verde_osc  = "0D4020"
        verde_med  = "1B6E3A"
        lima       = "AAFF00"
        verde_cla  = "E8F5E9"
        amarillo   = "FFF9C4"
        rojo_cla   = "FFEBEE"
        gris_cla   = "F5F5F5"
        blanco     = "FFFFFF"

        hdr_font   = Font(bold=True, color=blanco, size=11)
        titulo_font= Font(bold=True, color=verde_osc, size=14)
        sub_font   = Font(bold=True, color=verde_med, size=10)
        bold_font  = Font(bold=True, size=10)
        norm_font  = Font(size=10)

        hdr_fill   = PatternFill("solid", fgColor=verde_med)
        hdr2_fill  = PatternFill("solid", fgColor=verde_osc)
        pag_fill   = PatternFill("solid", fgColor=verde_cla)
        pend_fill  = PatternFill("solid", fgColor=amarillo)
        sin_fill   = PatternFill("solid", fgColor=gris_cla)
        total_fill = PatternFill("solid", fgColor="C8E6C9")
        n_fill     = PatternFill("solid", fgColor="DCEDC8")   # Normal
        f_fill     = PatternFill("solid", fgColor=amarillo)   # Festivo

        thin = Side(style="thin", color="BDBDBD")
        borde= Border(left=thin, right=thin, top=thin, bottom=thin)
        center = Alignment(horizontal="center", vertical="center", wrap_text=True)
        left   = Alignment(horizontal="left",   vertical="center")
        right  = Alignment(horizontal="right",  vertical="center")

        def _cell(ws, row, col, value="", font=None, fill=None,
                  align=None, border=True, num_fmt=None):
            c = ws.cell(row=row, column=col, value=value)
            if font:   c.font   = font
            if fill:   c.fill   = fill
            if align:  c.alignment = align
            if border: c.border = borde
            if num_fmt: c.number_format = num_fmt
            return c

        # ── Libro ────────────────────────────────────────────────────────
        wb = openpyxl.Workbook()

        # ════════════════════════════════════════════════════════════════
        # HOJA 1 — RESUMEN DE LA SEMANA
        # ════════════════════════════════════════════════════════════════
        ws = wb.active
        ws.title = "Nomina Semanal"
        ws.sheet_view.showGridLines = False

        # Título
        ws.merge_cells("A1:N1")
        t = ws["A1"]
        t.value = f"NOMINA SEMANAL — Club Los Pocitos Azufrados"
        t.font  = Font(bold=True, color=blanco, size=15)
        t.fill  = PatternFill("solid", fgColor=verde_osc)
        t.alignment = center

        ws.merge_cells("A2:N2")
        s = ws["A2"]
        s.value = f"Semana del {lunes.strftime('%d/%m/%Y')} al {domingo.strftime('%d/%m/%Y')}"
        s.font  = Font(bold=True, color=verde_med, size=11, italic=True)
        s.alignment = center

        ws.row_dimensions[1].height = 28
        ws.row_dimensions[2].height = 18

        # Encabezados columna — fila 4
        NCOLS_DIA = 7
        # Col: A=Empleado B=T.Normal C=T.Festivo D..J=Lun..Dom K=N.Normal L=N.Festivo M=Turnos N=A Pagar O=Estado
        headers = (
            ["Empleado", "Tarifa\nNormal", "Tarifa\nFestivo"]
            + [f"{d[:3]}\n{(lunes+datetime.timedelta(days=i)).strftime('%d/%m')}"
               for i, d in enumerate(DIAS_SEMANA)]
            + ["T.\nNormal", "T.\nFestivo", "Total\nTurnos", "A Pagar", "Estado"]
        )
        ws.row_dimensions[4].height = 32
        for ci, h in enumerate(headers, 1):
            _cell(ws, 4, ci, h, font=hdr_font, fill=hdr_fill, align=center)

        # Filas de empleados
        total_general = 0
        fila = 5
        for emp in self.empleados:
            dias_cel = []
            n_normal = n_festivo = 0
            pagado = False
            for dia_idx in range(7):
                t_row = turnos.get((emp['id_empleado'], dia_idx))
                if t_row:
                    tipo = t_row['tipo']
                    if tipo == 'Normal':
                        dias_cel.append(('N', n_fill))
                        n_normal += 1
                    elif tipo == 'Festivo':
                        dias_cel.append(('F', f_fill))
                        n_festivo += 1
                    else:
                        dias_cel.append(('-', None))
                    if t_row['pagado']:
                        pagado = True
                else:
                    dias_cel.append(('', None))

            a_pagar = (n_normal * (emp['tarifa_normal'] or 0) +
                       n_festivo * (emp['tarifa_festivo'] or 0))
            total_general += a_pagar

            tiene_turnos = (n_normal + n_festivo) > 0
            if pagado:
                estado_txt  = "PAGADO"
                fila_fill   = pag_fill
                est_font    = Font(bold=True, color="1B6E3A", size=10)
            elif tiene_turnos:
                estado_txt  = "PENDIENTE"
                fila_fill   = pend_fill
                est_font    = Font(bold=True, color="E65100", size=10)
            else:
                estado_txt  = "—"
                fila_fill   = sin_fill
                est_font    = norm_font

            ws.row_dimensions[fila].height = 18
            _cell(ws, fila, 1, emp['nombre'], font=bold_font, fill=fila_fill, align=left)
            _cell(ws, fila, 2, emp['tarifa_normal'] or 0, font=norm_font,
                  fill=fila_fill, align=right, num_fmt='$ #,##0')
            _cell(ws, fila, 3, emp['tarifa_festivo'] or 0, font=norm_font,
                  fill=fila_fill, align=right, num_fmt='$ #,##0')

            for ci, (txt, dc_fill) in enumerate(dias_cel, 4):
                fill_uso = dc_fill if dc_fill else fila_fill
                _cell(ws, fila, ci, txt, font=Font(bold=bool(txt and txt != '-'), size=10),
                      fill=fill_uso, align=center)

            _cell(ws, fila, 11, n_normal,          font=norm_font, fill=fila_fill, align=center)
            _cell(ws, fila, 12, n_festivo,          font=norm_font, fill=fila_fill, align=center)
            _cell(ws, fila, 13, n_normal+n_festivo, font=bold_font, fill=fila_fill, align=center)
            _cell(ws, fila, 14, a_pagar, font=Font(bold=True, color=verde_med, size=10),
                  fill=fila_fill, align=right, num_fmt='$ #,##0')
            _cell(ws, fila, 15, estado_txt, font=est_font, fill=fila_fill, align=center)
            fila += 1

        # Fila total
        ws.merge_cells(f"A{fila}:M{fila}")
        _cell(ws, fila, 1, "TOTAL A PAGAR", font=Font(bold=True, color=blanco, size=11),
              fill=PatternFill("solid", fgColor=verde_med), align=right)
        _cell(ws, fila, 14, total_general,
              font=Font(bold=True, color=blanco, size=12),
              fill=PatternFill("solid", fgColor=verde_osc), align=right,
              num_fmt='$ #,##0')
        _cell(ws, fila, 15, "", fill=PatternFill("solid", fgColor=verde_osc), align=center)
        ws.row_dimensions[fila].height = 22

        # Ancho columnas
        ws.column_dimensions['A'].width = 22
        ws.column_dimensions['B'].width = 11
        ws.column_dimensions['C'].width = 11
        for ci in range(4, 11):   # días
            ws.column_dimensions[get_column_letter(ci)].width = 8
        ws.column_dimensions['K'].width = 8
        ws.column_dimensions['L'].width = 8
        ws.column_dimensions['M'].width = 9
        ws.column_dimensions['N'].width = 13
        ws.column_dimensions['O'].width = 11

        # ════════════════════════════════════════════════════════════════
        # HOJA 2 — DETALLE POR EMPLEADO (qué día le toca cobrar)
        # ════════════════════════════════════════════════════════════════
        ws2 = wb.create_sheet("Detalle por Empleado")
        ws2.sheet_view.showGridLines = False

        ws2.merge_cells("A1:E1")
        t2 = ws2["A1"]
        t2.value = f"Detalle de Pagos — Semana {lunes.strftime('%d/%m/%Y')} al {domingo.strftime('%d/%m/%Y')}"
        t2.font  = Font(bold=True, color=blanco, size=13)
        t2.fill  = PatternFill("solid", fgColor=verde_osc)
        t2.alignment = center
        ws2.row_dimensions[1].height = 26

        for ci, h in enumerate(["Empleado", "Dia", "Fecha", "Tipo de Turno", "Valor del Turno"], 1):
            _cell(ws2, 3, ci, h, font=hdr_font, fill=hdr_fill, align=center)
        ws2.row_dimensions[3].height = 20

        fila2 = 4
        for emp in self.empleados:
            tiene_dias = False
            emp_rows = []
            for dia_idx in range(7):
                t_row = turnos.get((emp['id_empleado'], dia_idx))
                if t_row and t_row['tipo'] in ('Normal', 'Festivo'):
                    fecha_dia = lunes + datetime.timedelta(days=dia_idx)
                    tarifa = (emp['tarifa_normal'] if t_row['tipo'] == 'Normal'
                              else emp['tarifa_festivo']) or 0
                    emp_rows.append((DIAS_SEMANA[dia_idx], fecha_dia.strftime('%d/%m/%Y'),
                                     t_row['tipo'], tarifa, t_row['pagado']))
                    tiene_dias = True

            if not tiene_dias:
                continue

            # Sub-encabezado del empleado
            ws2.merge_cells(f"A{fila2}:E{fila2}")
            c = ws2.cell(row=fila2, column=1,
                         value=f"{emp['nombre']}  —  T.Normal: ${int(emp['tarifa_normal'] or 0):,}  |  T.Festivo: ${int(emp['tarifa_festivo'] or 0):,}")
            c.font  = Font(bold=True, color=blanco, size=10)
            c.fill  = PatternFill("solid", fgColor=verde_med)
            c.alignment = left
            c.border= borde
            ws2.row_dimensions[fila2].height = 18
            fila2 += 1

            subtotal = 0
            for dia_nom, fecha_str, tipo, valor, pagado in emp_rows:
                fill_d = n_fill if tipo == 'Normal' else f_fill
                _cell(ws2, fila2, 1, emp['nombre'], font=norm_font, fill=fill_d, align=left)
                _cell(ws2, fila2, 2, dia_nom,       font=norm_font, fill=fill_d, align=center)
                _cell(ws2, fila2, 3, fecha_str,     font=norm_font, fill=fill_d, align=center)
                _cell(ws2, fila2, 4, tipo,          font=norm_font, fill=fill_d, align=center)
                _cell(ws2, fila2, 5, valor, font=Font(bold=True, size=10),
                      fill=fill_d, align=right, num_fmt='$ #,##0')
                ws2.row_dimensions[fila2].height = 16
                subtotal += valor
                fila2 += 1

            # Subtotal empleado
            ws2.merge_cells(f"A{fila2}:D{fila2}")
            _cell(ws2, fila2, 1, f"Total {emp['nombre']}:",
                  font=Font(bold=True, color=verde_med, size=10),
                  fill=total_fill, align=right)
            _cell(ws2, fila2, 5, subtotal,
                  font=Font(bold=True, color=verde_med, size=10),
                  fill=total_fill, align=right, num_fmt='$ #,##0')
            ws2.row_dimensions[fila2].height = 18
            fila2 += 2   # espacio entre empleados

        ws2.column_dimensions['A'].width = 22
        ws2.column_dimensions['B'].width = 12
        ws2.column_dimensions['C'].width = 13
        ws2.column_dimensions['D'].width = 16
        ws2.column_dimensions['E'].width = 15

        # ── Guardar ──────────────────────────────────────────────────────
        nombre_archivo = f"nomina_{lunes.isoformat()}.xlsx"
        ruta = os.path.join(BASE_DIR, 'data', nombre_archivo)
        try:
            wb.save(ruta)
            messagebox.showinfo(
                "Excel exportado",
                f"Archivo guardado en:\n{ruta}\n\n"
                f"Hojas:\n  - Nomina Semanal (resumen)\n  - Detalle por Empleado"
            )
            try:
                import subprocess
                subprocess.Popen(['start', '', ruta], shell=True)
            except Exception:
                pass
        except Exception as e:
            messagebox.showerror("Error al guardar", str(e))

    def detener(self):
        try:
            self._canvas_nom.unbind_all('<MouseWheel>')
            self._canvas_nom.unbind_all('<Button-4>')
            self._canvas_nom.unbind_all('<Button-5>')
        except Exception:
            pass
