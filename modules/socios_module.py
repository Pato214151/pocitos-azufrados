"""
Módulo de Socios y Membresías - Club Los Pocitos Azufrados
Gestión de socios: ficha, cuotas mensuales e historial de pagos.
Acceso: administrador y contadora.
"""
import tkinter as tk
from tkinter import ttk, messagebox
import os, sys, datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from utils.tema_corporativo import COLORES, FUENTES, crear_boton, format_money, aplicar_estilo_tabla
from database.connection import conexion_segura, transaccion_atomica
from utils.logger import log_auditoria

MESES = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun',
         'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
TIPOS = ['Individual', 'Familiar', 'VIP']
ESTADOS = ['ACTIVO', 'SUSPENDIDO', 'RETIRADO']
METODOS_PAGO = ['EFECTIVO', 'NEQUI', 'DAVIPLATA', 'BANCOLOMBIA', 'TRANSFERENCIA']


class SociosModule:
    """Pantalla de socios: ficha, cuotas mensuales e historial de pagos."""
    def __init__(self, parent, usuario):
        self.parent = parent
        self.usuario = usuario
        self._socio_sel = None
        self._anio_visible = datetime.date.today().year
        self._crear_interfaz()
        self._cargar_socios()

    # ─── UI ───────────────────────────────────────────────────────────────────

    def _crear_interfaz(self):
        """Arma la pantalla: lista de socios, KPIs y panel de detalle."""
        # Header
        header = tk.Frame(self.parent, bg=COLORES['primario'])
        header.pack(fill='x')
        inner = tk.Frame(header, bg=COLORES['primario'], padx=15, pady=10)
        inner.pack(fill='x')
        tk.Label(inner, text="Socios y Membresias", font=FUENTES['encabezado'],
                 fg=COLORES['texto_claro'], bg=COLORES['primario']).pack(side='left')
        btns = tk.Frame(inner, bg=COLORES['primario'])
        btns.pack(side='right')
        crear_boton(btns, "+ Nuevo Socio", self._nuevo_socio, tipo='exito').pack(side='left', padx=4)
        crear_boton(btns, "Recargar", self._cargar_socios, tipo='secundario').pack(side='left', padx=4)

        # KPIs
        kpi_row = tk.Frame(self.parent, bg=COLORES['fondo'])
        kpi_row.pack(fill='x', padx=15, pady=(10, 4))
        self._kpis = {}
        defs = [
            ('total',     'Total Socios',     COLORES['primario']),
            ('activos',   'Activos',          COLORES['exito']),
            ('mora',      'En Mora',          COLORES['error']),
            ('recaudado', 'Recaudado Mes',    COLORES['agua']),
        ]
        for key, titulo, color in defs:
            card = tk.Frame(kpi_row, bg=COLORES['fondo_card'],
                            highlightbackground=color, highlightthickness=2)
            card.pack(side='left', fill='both', expand=True, padx=4)
            tk.Frame(card, bg=color, height=4).pack(fill='x')
            tk.Label(card, text=titulo, font=FUENTES['kpi_label'],
                     fg=COLORES['texto_secundario'], bg=COLORES['fondo_card']).pack(padx=10, pady=(6, 0))
            lbl = tk.Label(card, text="—", font=FUENTES['kpi_valor'],
                           fg=COLORES['texto'], bg=COLORES['fondo_card'])
            lbl.pack(padx=10, pady=(0, 8))
            self._kpis[key] = lbl

        # Cuerpo: lista izquierda + detalle derecha
        body = tk.Frame(self.parent, bg=COLORES['fondo'])
        body.pack(fill='both', expand=True, padx=15, pady=6)

        # ── Panel izquierdo: lista ──
        left = tk.Frame(body, bg=COLORES['fondo_card'],
                        highlightbackground=COLORES['borde'], highlightthickness=1)
        left.pack(side='left', fill='y', padx=(0, 8))
        left.pack_propagate(False)
        left.config(width=310)

        busq = tk.Frame(left, bg=COLORES['fondo_card'])
        busq.pack(fill='x', padx=10, pady=(10, 4))
        tk.Label(busq, text="Buscar", font=FUENTES['pequena'],
                 fg=COLORES['texto_secundario'], bg=COLORES['fondo_card']).pack(anchor='w')
        self.entry_busq = tk.Entry(busq, font=FUENTES['input'],
                                   bg=COLORES['fondo_input'], fg=COLORES['texto'],
                                   insertbackground=COLORES['acento'])
        self.entry_busq.pack(fill='x', ipady=5)
        self.entry_busq.bind('<KeyRelease>', lambda e: self._filtrar_lista())

        # Filtro estado
        fil = tk.Frame(left, bg=COLORES['fondo_card'])
        fil.pack(fill='x', padx=10, pady=(4, 6))
        tk.Label(fil, text="Filtrar:", font=FUENTES['pequena'],
                 fg=COLORES['texto_secundario'], bg=COLORES['fondo_card']).pack(side='left')
        self.var_filtro = tk.StringVar(master=self.parent, value='TODOS')
        for op in ['TODOS', 'ACTIVO', 'SUSPENDIDO', 'RETIRADO']:
            tk.Radiobutton(fil, text=op.capitalize(), variable=self.var_filtro, value=op,
                           command=self._filtrar_lista,
                           font=FUENTES['pequena'], bg=COLORES['fondo_card'],
                           fg=COLORES['texto'], selectcolor=COLORES['fondo_card'],
                           activebackground=COLORES['fondo_card']).pack(side='left', padx=3)

        lista_frame = tk.Frame(left, bg=COLORES['fondo_card'])
        lista_frame.pack(fill='both', expand=True, padx=6, pady=(0, 8))

        cols_l = ('nombre', 'tipo', 'estado')
        self.tree_socios = ttk.Treeview(lista_frame, columns=cols_l, show='headings', height=20)
        aplicar_estilo_tabla(self.tree_socios)
        self.tree_socios.column('nombre', width=145, anchor='w')
        self.tree_socios.column('tipo',   width=80,  anchor='center')
        self.tree_socios.column('estado', width=75,  anchor='center')
        self.tree_socios.heading('nombre', text='Nombre')
        self.tree_socios.heading('tipo',   text='Tipo')
        self.tree_socios.heading('estado', text='Estado')
        sb_l = ttk.Scrollbar(lista_frame, orient='vertical', command=self.tree_socios.yview)
        self.tree_socios.configure(yscrollcommand=sb_l.set)
        self.tree_socios.pack(side='left', fill='both', expand=True)
        sb_l.pack(side='right', fill='y')
        self.tree_socios.bind('<<TreeviewSelect>>', self._on_select_socio)

        # ── Panel derecho: detalle ──
        self.right = tk.Frame(body, bg=COLORES['fondo_card'],
                              highlightbackground=COLORES['borde'], highlightthickness=1)
        self.right.pack(side='left', fill='both', expand=True)
        self._render_placeholder()

    def _render_placeholder(self):
        for w in self.right.winfo_children():
            w.destroy()
        tk.Label(self.right, text="Seleccione un socio para ver su ficha.",
                 font=FUENTES['normal'], fg=COLORES['texto_secundario'],
                 bg=COLORES['fondo_card']).pack(expand=True)

    def _render_detalle(self, socio):
        """Muestra la ficha y las cuotas del socio elegido."""
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

        # ── Encabezado de ficha ──
        fich_hdr = tk.Frame(_inner, bg=COLORES['primario'], padx=15, pady=10)
        fich_hdr.pack(fill='x')
        tk.Label(fich_hdr, text=socio['nombre'], font=FUENTES['subtitulo'],
                 fg=COLORES['texto_claro'], bg=COLORES['primario']).pack(side='left')
        btns_fich = tk.Frame(fich_hdr, bg=COLORES['primario'])
        btns_fich.pack(side='right')
        crear_boton(btns_fich, "Editar", lambda: self._editar_socio(socio),
                    tipo='primario').pack(side='left', padx=3)
        if socio['estado'] == 'ACTIVO':
            crear_boton(btns_fich, "Suspender",
                        lambda: self._cambiar_estado(socio, 'SUSPENDIDO'),
                        tipo='advertencia').pack(side='left', padx=3)
        elif socio['estado'] == 'SUSPENDIDO':
            crear_boton(btns_fich, "Reactivar",
                        lambda: self._cambiar_estado(socio, 'ACTIVO'),
                        tipo='exito').pack(side='left', padx=3)
        if socio['estado'] != 'RETIRADO':
            crear_boton(btns_fich, "Retirar",
                        lambda: self._cambiar_estado(socio, 'RETIRADO'),
                        tipo='error').pack(side='left', padx=3)

        # ── Datos personales ──
        datos = tk.Frame(_inner, bg=COLORES['fondo_card'], padx=15, pady=10)
        datos.pack(fill='x')
        campos = [
            ("Documento",     socio['documento'] or '—'),
            ("Telefono",      socio['telefono']  or '—'),
            ("Email",         socio['email']     or '—'),
            ("Membresia",     socio['tipo_membresia']),
            ("Cuota mensual", format_money(socio['valor_cuota'])),
            ("Dia de pago",   f"Dia {socio['dia_pago']} de cada mes"),
            ("Ingreso",       socio['fecha_ingreso'] or '—'),
            ("Estado",        socio['estado']),
        ]
        for i, (lbl, val) in enumerate(campos):
            r = i // 2
            c = (i % 2) * 2
            tk.Label(datos, text=f"{lbl}:", font=FUENTES['pequena'],
                     fg=COLORES['texto_secundario'], bg=COLORES['fondo_card']).grid(
                row=r, column=c, sticky='w', padx=(0, 4), pady=2)
            tk.Label(datos, text=val, font=FUENTES['normal'],
                     fg=COLORES['texto'], bg=COLORES['fondo_card']).grid(
                row=r, column=c+1, sticky='w', padx=(0, 20), pady=2)
        if socio['notas']:
            r_n = len(campos) // 2
            tk.Label(datos, text="Notas:", font=FUENTES['pequena'],
                     fg=COLORES['texto_secundario'], bg=COLORES['fondo_card']).grid(
                row=r_n, column=0, sticky='nw', pady=2)
            tk.Label(datos, text=socio['notas'], font=FUENTES['pequena'],
                     fg=COLORES['texto'], bg=COLORES['fondo_card'], wraplength=380,
                     justify='left').grid(row=r_n, column=1, columnspan=3, sticky='w', pady=2)

        # ── Cuotas del año ──
        anio_frame = tk.Frame(_inner, bg=COLORES['fondo_card'], padx=15, pady=4)
        anio_frame.pack(fill='x')
        nav = tk.Frame(anio_frame, bg=COLORES['fondo_card'])
        nav.pack(side='left')
        crear_boton(nav, "<", lambda: self._cambiar_anio(-1, socio), tipo='outline').pack(side='left')
        self.lbl_anio = tk.Label(nav, text=str(self._anio_visible),
                                 font=FUENTES['normal_bold'], fg=COLORES['texto'],
                                 bg=COLORES['fondo_card'], width=6)
        self.lbl_anio.pack(side='left', padx=6)
        crear_boton(nav, ">", lambda: self._cambiar_anio(1, socio), tipo='outline').pack(side='left')

        crear_boton(anio_frame, "+ Registrar Pago",
                    lambda: self._registrar_pago(socio), tipo='exito').pack(side='right')

        self.cuotas_frame = tk.Frame(_inner, bg=COLORES['fondo_card'], padx=15, pady=6)
        self.cuotas_frame.pack(fill='x')
        self._render_cuotas(socio)

        # ── Historial de pagos ──
        tk.Label(_inner, text="Historial de pagos", font=FUENTES['subtitulo'],
                 fg=COLORES['texto'], bg=COLORES['fondo_card']).pack(anchor='w', padx=15, pady=(6, 2))
        hist_frame = tk.Frame(_inner, bg=COLORES['fondo_card'], padx=15, pady=(0, 10))
        hist_frame.pack(fill='both')

        cols_h = ('fecha', 'periodo', 'valor', 'metodo', 'obs')
        self.tree_hist = ttk.Treeview(hist_frame, columns=cols_h, show='headings', height=6)
        aplicar_estilo_tabla(self.tree_hist)
        self.tree_hist.column('fecha',   width=130, anchor='center')
        self.tree_hist.column('periodo', width=90,  anchor='center')
        self.tree_hist.column('valor',   width=100, anchor='e')
        self.tree_hist.column('metodo',  width=110, anchor='center')
        self.tree_hist.column('obs',     width=180, anchor='w')
        self.tree_hist.heading('fecha',   text='Fecha Pago')
        self.tree_hist.heading('periodo', text='Periodo')
        self.tree_hist.heading('valor',   text='Valor')
        self.tree_hist.heading('metodo',  text='Metodo')
        self.tree_hist.heading('obs',     text='Observacion')
        sb_h = ttk.Scrollbar(hist_frame, orient='vertical', command=self.tree_hist.yview)
        self.tree_hist.configure(yscrollcommand=sb_h.set)
        self.tree_hist.pack(side='left', fill='both', expand=True)
        sb_h.pack(side='right', fill='y')
        self._cargar_historial(socio['id_socio'])

    def _render_cuotas(self, socio):
        for w in self.cuotas_frame.winfo_children():
            w.destroy()
        pagados = set()
        hoy = datetime.date.today()
        with conexion_segura() as conn:
            rows = conn.execute(
                "SELECT mes FROM pagos_membresia WHERE id_socio=? AND anio=?",
                (socio['id_socio'], self._anio_visible)
            ).fetchall()
            pagados = {r['mes'] for r in rows}

        for i, nombre_mes in enumerate(MESES):
            mes_num = i + 1
            pagado = mes_num in pagados
            es_futuro = (self._anio_visible > hoy.year or
                         (self._anio_visible == hoy.year and mes_num > hoy.month))
            if pagado:
                bg, fg, borde = COLORES['exito'], COLORES['texto_claro'], COLORES['exito']
            elif es_futuro:
                bg, fg, borde = COLORES['fondo'], COLORES['texto_deshabilitado'], COLORES['borde']
            else:
                bg, fg, borde = COLORES['error'], COLORES['texto_claro'], COLORES['error']

            cel = tk.Frame(self.cuotas_frame, bg=borde, padx=1, pady=1)
            cel.grid(row=0, column=i, padx=2, pady=2)
            tk.Label(cel, text=nombre_mes, font=FUENTES['pequena'],
                     bg=bg, fg=fg, width=4, pady=4).pack()

    def _cargar_historial(self, id_socio):
        self.tree_hist.delete(*self.tree_hist.get_children())
        with conexion_segura() as conn:
            rows = conn.execute("""
                SELECT fecha_pago, anio, mes, valor_pagado, metodo_pago, observacion
                FROM pagos_membresia
                WHERE id_socio=?
                ORDER BY anio DESC, mes DESC
            """, (id_socio,)).fetchall()
        for r in rows:
            periodo = f"{MESES[r['mes']-1]} {r['anio']}"
            self.tree_hist.insert('', 'end', values=(
                r['fecha_pago'][:16],
                periodo,
                format_money(r['valor_pagado']),
                r['metodo_pago'],
                r['observacion'] or ''
            ))

    # ─── DATOS ────────────────────────────────────────────────────────────────

    def _cargar_socios(self):
        self._todos = []
        with conexion_segura() as conn:
            rows = conn.execute("""
                SELECT id_socio, nombre, documento, telefono, email,
                       tipo_membresia, valor_cuota, dia_pago,
                       fecha_ingreso, estado, notas, activo
                FROM socios WHERE activo=1
                ORDER BY nombre
            """).fetchall()
            self._todos = [dict(r) for r in rows]
        self._filtrar_lista()
        self._actualizar_kpis()

    def _filtrar_lista(self):
        texto = self.entry_busq.get().lower()
        filtro = self.var_filtro.get()
        self.tree_socios.delete(*self.tree_socios.get_children())
        for s in self._todos:
            if filtro != 'TODOS' and s['estado'] != filtro:
                continue
            if texto and texto not in s['nombre'].lower() and texto not in (s['documento'] or '').lower():
                continue
            self.tree_socios.insert('', 'end', iid=str(s['id_socio']),
                                    values=(s['nombre'], s['tipo_membresia'], s['estado']))

    def _actualizar_kpis(self):
        hoy = datetime.date.today()
        total = len(self._todos)
        activos = sum(1 for s in self._todos if s['estado'] == 'ACTIVO')
        # Socios activos sin pago del mes actual
        with conexion_segura() as conn:
            pagados_mes = {r['id_socio'] for r in conn.execute(
                "SELECT id_socio FROM pagos_membresia WHERE anio=? AND mes=?",
                (hoy.year, hoy.month)
            ).fetchall()}
            recaudado = conn.execute(
                "SELECT COALESCE(SUM(valor_pagado),0) as tot FROM pagos_membresia WHERE anio=? AND mes=?",
                (hoy.year, hoy.month)
            ).fetchone()['tot']
        mora = sum(1 for s in self._todos
                   if s['estado'] == 'ACTIVO' and s['id_socio'] not in pagados_mes)
        self._kpis['total'].config(text=str(total))
        self._kpis['activos'].config(text=str(activos))
        self._kpis['mora'].config(text=str(mora))
        self._kpis['recaudado'].config(text=format_money(recaudado))

    # ─── EVENTOS ──────────────────────────────────────────────────────────────

    def _on_select_socio(self, event=None):
        sel = self.tree_socios.selection()
        if not sel:
            return
        id_s = int(sel[0])
        socio = next((s for s in self._todos if s['id_socio'] == id_s), None)
        if socio:
            self._socio_sel = socio
            self._render_detalle(socio)

    def _cambiar_anio(self, delta, socio):
        self._anio_visible += delta
        self.lbl_anio.config(text=str(self._anio_visible))
        self._render_cuotas(socio)

    # ─── ACCIONES ─────────────────────────────────────────────────────────────

    def _nuevo_socio(self):
        self._dialogo_socio(None)

    def _editar_socio(self, socio):
        self._dialogo_socio(socio)

    def _dialogo_socio(self, socio):
        """Formulario para crear o editar un socio."""
        es_nuevo = socio is None
        dlg = tk.Toplevel(self.parent)
        dlg.title("Nuevo Socio" if es_nuevo else "Editar Socio")
        dlg.configure(bg=COLORES['fondo'])
        dlg.grab_set()
        dlg.resizable(False, False)

        inner = tk.Frame(dlg, bg=COLORES['fondo'], padx=20, pady=15)
        inner.pack(fill='both', expand=True)

        def campo(label, row, val='', ancho=30):
            tk.Label(inner, text=label, font=FUENTES['pequena'],
                     fg=COLORES['texto_secundario'], bg=COLORES['fondo']).grid(
                row=row, column=0, sticky='w', pady=4)
            e = tk.Entry(inner, font=FUENTES['input'], width=ancho,
                         bg=COLORES['fondo_input'], fg=COLORES['texto'],
                         insertbackground=COLORES['acento'])
            e.insert(0, val)
            e.grid(row=row, column=1, sticky='ew', padx=(8, 0), pady=4, ipady=5)
            return e

        e_nombre   = campo("Nombre *",       0, socio['nombre']         if socio else '')
        e_doc      = campo("Documento",      1, socio['documento']      if socio else '')
        e_tel      = campo("Telefono",       2, socio['telefono']       if socio else '')
        e_email    = campo("Email",          3, socio['email']          if socio else '')
        e_cuota    = campo("Cuota mensual",  5, str(int(socio['valor_cuota'])) if socio else '0')
        e_dia      = campo("Dia de pago",    6, str(socio['dia_pago']) if socio else '1', 5)

        tk.Label(inner, text="Tipo membresia", font=FUENTES['pequena'],
                 fg=COLORES['texto_secundario'], bg=COLORES['fondo']).grid(row=4, column=0, sticky='w', pady=4)
        var_tipo = tk.StringVar(value=socio['tipo_membresia'] if socio else 'Individual')
        ttk.Combobox(inner, textvariable=var_tipo, values=TIPOS,
                     state='readonly', font=FUENTES['input'], width=18).grid(
            row=4, column=1, sticky='w', padx=(8, 0), pady=4)

        tk.Label(inner, text="Estado", font=FUENTES['pequena'],
                 fg=COLORES['texto_secundario'], bg=COLORES['fondo']).grid(row=7, column=0, sticky='w', pady=4)
        var_est = tk.StringVar(value=socio['estado'] if socio else 'ACTIVO')
        ttk.Combobox(inner, textvariable=var_est, values=ESTADOS,
                     state='readonly', font=FUENTES['input'], width=18).grid(
            row=7, column=1, sticky='w', padx=(8, 0), pady=4)

        tk.Label(inner, text="Notas", font=FUENTES['pequena'],
                 fg=COLORES['texto_secundario'], bg=COLORES['fondo']).grid(row=8, column=0, sticky='nw', pady=4)
        txt_notas = tk.Text(inner, font=FUENTES['input'], width=30, height=3,
                            bg=COLORES['fondo_input'], fg=COLORES['texto'])
        txt_notas.grid(row=8, column=1, sticky='ew', padx=(8, 0), pady=4)
        if socio and socio['notas']:
            txt_notas.insert('1.0', socio['notas'])

        lbl_err = tk.Label(inner, text='', font=FUENTES['pequena'],
                           fg=COLORES['error'], bg=COLORES['fondo'])
        lbl_err.grid(row=9, column=0, columnspan=2, pady=4)

        def _guardar():
            nombre = e_nombre.get().strip()
            if not nombre:
                lbl_err.config(text="El nombre es obligatorio.")
                return
            try:
                cuota = float(e_cuota.get().replace(',', '.') or 0)
                dia   = int(e_dia.get() or 1)
                if not (1 <= dia <= 28):
                    raise ValueError
            except ValueError:
                lbl_err.config(text="Cuota debe ser numero y dia entre 1 y 28.")
                return
            notas = txt_notas.get('1.0', 'end').strip()
            fi = socio['fecha_ingreso'] if socio else datetime.date.today().isoformat()
            try:
                with transaccion_atomica() as conn:
                    if es_nuevo:
                        cur = conn.execute("""
                            INSERT INTO socios
                                (nombre, documento, telefono, email, tipo_membresia,
                                 valor_cuota, dia_pago, fecha_ingreso, estado, notas)
                            VALUES (?,?,?,?,?,?,?,?,?,?)
                        """, (nombre, e_doc.get().strip(), e_tel.get().strip(),
                              e_email.get().strip(), var_tipo.get(), cuota, dia,
                              fi, var_est.get(), notas))
                        log_auditoria(conn, tabla='socios', id_registro=cur.lastrowid,
                                      accion='CREAR', usuario=self.usuario['usuario'],
                                      comentario=f'Nuevo socio: {nombre}')
                    else:
                        conn.execute("""
                            UPDATE socios SET nombre=?, documento=?, telefono=?, email=?,
                                tipo_membresia=?, valor_cuota=?, dia_pago=?, estado=?, notas=?
                            WHERE id_socio=?
                        """, (nombre, e_doc.get().strip(), e_tel.get().strip(),
                              e_email.get().strip(), var_tipo.get(), cuota, dia,
                              var_est.get(), notas, socio['id_socio']))
                        log_auditoria(conn, tabla='socios', id_registro=socio['id_socio'],
                                      accion='EDITAR', usuario=self.usuario['usuario'],
                                      comentario=f'Edicion socio: {nombre}')
            except Exception as ex:
                lbl_err.config(text=f"Error: {ex}")
                return
            dlg.destroy()
            self._cargar_socios()

        btn_row = tk.Frame(inner, bg=COLORES['fondo'])
        btn_row.grid(row=10, column=0, columnspan=2, pady=10)
        crear_boton(btn_row, "Guardar", _guardar, tipo='primario').pack(side='left', padx=6)
        crear_boton(btn_row, "Cancelar", dlg.destroy, tipo='secundario').pack(side='left', padx=6)
        inner.columnconfigure(1, weight=1)
        dlg.update_idletasks()
        dlg.geometry(f"+{dlg.winfo_screenwidth()//2 - 220}+{dlg.winfo_screenheight()//2 - 280}")

    def _cambiar_estado(self, socio, nuevo_estado):
        if not messagebox.askyesno("Confirmar",
                                   f"¿Cambiar estado de '{socio['nombre']}' a {nuevo_estado}?"):
            return
        try:
            with transaccion_atomica() as conn:
                conn.execute("UPDATE socios SET estado=? WHERE id_socio=?",
                             (nuevo_estado, socio['id_socio']))
                log_auditoria(conn, tabla='socios', id_registro=socio['id_socio'],
                              accion='ESTADO', usuario=self.usuario['usuario'],
                              comentario=f'Estado -> {nuevo_estado}')
        except Exception as ex:
            messagebox.showerror("Error", str(ex))
            return
        self._cargar_socios()

    def _registrar_pago(self, socio):
        """Registra el pago de una cuota."""
        hoy = datetime.date.today()
        dlg = tk.Toplevel(self.parent)
        dlg.title("Registrar Pago de Membresia")
        dlg.configure(bg=COLORES['fondo'])
        dlg.grab_set()
        dlg.resizable(False, False)

        inner = tk.Frame(dlg, bg=COLORES['fondo'], padx=20, pady=15)
        inner.pack(fill='both', expand=True)

        tk.Label(inner, text=f"Socio: {socio['nombre']}", font=FUENTES['normal_bold'],
                 fg=COLORES['texto'], bg=COLORES['fondo']).pack(anchor='w', pady=(0, 10))

        fila = tk.Frame(inner, bg=COLORES['fondo'])
        fila.pack(fill='x', pady=4)
        tk.Label(fila, text="Mes:", font=FUENTES['pequena'],
                 fg=COLORES['texto_secundario'], bg=COLORES['fondo']).pack(side='left')
        meses_opts = [f"{MESES[m-1]} {hoy.year}" for m in range(1, 13)]
        var_mes = tk.StringVar(value=f"{MESES[hoy.month-1]} {hoy.year}")
        ttk.Combobox(fila, textvariable=var_mes, values=meses_opts,
                     state='readonly', font=FUENTES['input'], width=14).pack(side='left', padx=8)

        fila2 = tk.Frame(inner, bg=COLORES['fondo'])
        fila2.pack(fill='x', pady=4)
        tk.Label(fila2, text="Valor:", font=FUENTES['pequena'],
                 fg=COLORES['texto_secundario'], bg=COLORES['fondo']).pack(side='left')
        e_val = tk.Entry(fila2, font=FUENTES['input'], width=12,
                         bg=COLORES['fondo_input'], fg=COLORES['texto'],
                         insertbackground=COLORES['acento'])
        e_val.insert(0, str(int(socio['valor_cuota'])))
        e_val.pack(side='left', padx=8, ipady=5)

        fila3 = tk.Frame(inner, bg=COLORES['fondo'])
        fila3.pack(fill='x', pady=4)
        tk.Label(fila3, text="Metodo:", font=FUENTES['pequena'],
                 fg=COLORES['texto_secundario'], bg=COLORES['fondo']).pack(side='left')
        var_met = tk.StringVar(value='EFECTIVO')
        ttk.Combobox(fila3, textvariable=var_met, values=METODOS_PAGO,
                     state='readonly', font=FUENTES['input'], width=14).pack(side='left', padx=8)

        tk.Label(inner, text="Observacion:", font=FUENTES['pequena'],
                 fg=COLORES['texto_secundario'], bg=COLORES['fondo']).pack(anchor='w', pady=(8, 2))
        e_obs = tk.Entry(inner, font=FUENTES['input'], width=35,
                         bg=COLORES['fondo_input'], fg=COLORES['texto'],
                         insertbackground=COLORES['acento'])
        e_obs.pack(fill='x', ipady=5)

        lbl_err = tk.Label(inner, text='', font=FUENTES['pequena'],
                           fg=COLORES['error'], bg=COLORES['fondo'])
        lbl_err.pack(pady=4)

        def _guardar():
            try:
                valor = float(e_val.get().replace(',', '.'))
                if valor <= 0:
                    raise ValueError
            except ValueError:
                lbl_err.config(text="Ingrese un valor valido mayor a 0.")
                return
            mes_str = var_mes.get()
            mes_idx = MESES.index(mes_str[:3]) + 1
            anio_p  = int(mes_str[-4:])
            try:
                with transaccion_atomica() as conn:
                    conn.execute("""
                        INSERT INTO pagos_membresia
                            (id_socio, anio, mes, valor_pagado, metodo_pago,
                             observacion, usuario_registro)
                        VALUES (?,?,?,?,?,?,?)
                    """, (socio['id_socio'], anio_p, mes_idx, valor,
                          var_met.get(), e_obs.get().strip(),
                          self.usuario['usuario']))
                    log_auditoria(conn, tabla='pagos_membresia', id_registro=socio['id_socio'],
                                  accion='PAGO', usuario=self.usuario['usuario'],
                                  comentario=f"Pago {MESES[mes_idx-1]} {anio_p}: {format_money(valor)}")
            except Exception as ex:
                if 'UNIQUE' in str(ex):
                    lbl_err.config(text="Ya existe un pago registrado para ese mes.")
                else:
                    lbl_err.config(text=f"Error: {ex}")
                return
            dlg.destroy()
            self._cargar_socios()
            if self._socio_sel and self._socio_sel['id_socio'] == socio['id_socio']:
                self._render_detalle(socio)

        btn_row = tk.Frame(inner, bg=COLORES['fondo'])
        btn_row.pack(pady=10)
        crear_boton(btn_row, "Registrar Pago", _guardar, tipo='exito').pack(side='left', padx=6)
        crear_boton(btn_row, "Cancelar", dlg.destroy, tipo='secundario').pack(side='left', padx=6)
        dlg.update_idletasks()
        dlg.geometry(f"+{dlg.winfo_screenwidth()//2 - 200}+{dlg.winfo_screenheight()//2 - 200}")

    def detener(self):
        pass