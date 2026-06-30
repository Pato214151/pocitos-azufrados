"""
Módulo de Movimientos - Club Los Pocitos Azufrados
Agrupa en un solo panel con tabs: Resumen financiero, Ingresos,
Egresos, Caja y Reportes. Reemplaza las 4 entradas de menú separadas.
"""

import tkinter as tk
from tkinter import ttk
import os, sys, datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from utils.tema_corporativo import COLORES, FUENTES, format_money
from database.connection import conexion_segura


class MovimientosModule:
    def __init__(self, parent, usuario):
        self.parent = parent
        self.usuario = usuario
        self._instancias = []

        # Estilo del notebook
        style = ttk.Style()
        style.configure("Movimientos.TNotebook",
                        background=COLORES['fondo'],
                        borderwidth=0)
        style.configure("Movimientos.TNotebook.Tab",
                        font=FUENTES['normal_bold'],
                        background=COLORES['fondo_sidebar'],
                        foreground=COLORES['texto_secundario'],
                        padding=(16, 8))
        style.map("Movimientos.TNotebook.Tab",
                  background=[('selected', COLORES['primario'])],
                  foreground=[('selected', COLORES['acento'])])

        self.notebook = ttk.Notebook(parent, style="Movimientos.TNotebook")
        self.notebook.pack(fill='both', expand=True)

        self._crear_tab_resumen()
        self._crear_tab_ingresos()
        self._crear_tab_egresos()
        self._crear_tab_caja()
        self._crear_tab_reportes()
        self._crear_tab_graficas()

    #  TAB 1: RESUMEN 
    def _crear_tab_resumen(self):
        frame = tk.Frame(self.notebook, bg=COLORES['fondo'])
        self.notebook.add(frame, text='  Resumen  ')
        self._render_resumen(frame)

    def _render_resumen(self, frame):
        canvas = tk.Canvas(frame, bg=COLORES['fondo'], highlightthickness=0)
        scroll = ttk.Scrollbar(frame, orient='vertical', command=canvas.yview)
        inner = tk.Frame(canvas, bg=COLORES['fondo'])

        inner.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.create_window((0, 0), window=inner, anchor='nw')
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side='left', fill='both', expand=True)
        scroll.pack(side='right', fill='y')

        canvas.bind_all('<MouseWheel>', lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), 'units'))

        # Cabecera
        hdr = tk.Frame(inner, bg=COLORES['fondo'])
        hdr.pack(fill='x', padx=20, pady=(15, 5))
        tk.Label(hdr, text="Resumen Financiero",
                 font=FUENTES['titulo'], fg=COLORES['texto'],
                 bg=COLORES['fondo']).pack(anchor='w')
        hoy = datetime.date.today()
        tk.Label(hdr, text=hoy.strftime("%d de %B de %Y"),
                 font=FUENTES['normal'], fg=COLORES['texto_secundario'],
                 bg=COLORES['fondo']).pack(anchor='w')

        # Obtener datos
        ventas_hoy = ventas_mes = gastos_hoy = gastos_mes = 0
        try:
            with conexion_segura() as conn:
                hoy_str = hoy.isoformat()
                mes_inicio = hoy.replace(day=1).isoformat()
                ventas_hoy = conn.execute(
                    "SELECT COALESCE(SUM(total),0) FROM ventas "
                    "WHERE fecha_creacion>=? AND fecha_creacion<date(?,'+1 day') AND estado!='ANULADA'",
                    (hoy_str, hoy_str)).fetchone()[0]
                ventas_mes = conn.execute(
                    "SELECT COALESCE(SUM(total),0) FROM ventas "
                    "WHERE fecha_creacion>=? AND estado!='ANULADA'",
                    (mes_inicio,)).fetchone()[0]
                gastos_hoy = conn.execute(
                    "SELECT COALESCE(SUM(valor),0) FROM gastos "
                    "WHERE fecha>=? AND fecha<date(?,'+1 day')",
                    (hoy_str, hoy_str)).fetchone()[0]
                gastos_mes = conn.execute(
                    "SELECT COALESCE(SUM(valor),0) FROM gastos WHERE fecha>=?",
                    (mes_inicio,)).fetchone()[0]
        except Exception as e:
            print(f"Error resumen movimientos: {e}")

        # KPI cards
        kpi_frame = tk.Frame(inner, bg=COLORES['fondo'])
        kpi_frame.pack(fill='x', padx=20, pady=15)

        kpis = [
            ("Ventas Hoy",     format_money(ventas_hoy),  COLORES['acento']),
            ("Ventas del Mes", format_money(ventas_mes),  COLORES['primario_claro']),
            ("Gastos Hoy",     format_money(gastos_hoy),  COLORES['error']),
            ("Gastos del Mes", format_money(gastos_mes),  COLORES['advertencia']),
        ]

        for i, (titulo, valor, color) in enumerate(kpis):
            kpi_frame.columnconfigure(i, weight=1)
            card = tk.Frame(kpi_frame, bg=COLORES['fondo_card'],
                            highlightbackground=COLORES['borde'], highlightthickness=1)
            card.grid(row=0, column=i, padx=6, sticky='nsew')
            tk.Frame(card, bg=color, height=3).pack(fill='x')
            inner_card = tk.Frame(card, bg=COLORES['fondo_card'], padx=16, pady=14)
            inner_card.pack(fill='both', expand=True)
            tk.Label(inner_card, text=titulo, font=FUENTES['kpi_label'],
                     fg=COLORES['texto_secundario'], bg=COLORES['fondo_card']).pack(anchor='w')
            tk.Label(inner_card, text=valor, font=FUENTES['kpi_valor'],
                     fg=COLORES['texto'], bg=COLORES['fondo_card'], anchor='w').pack(fill='x', pady=(4, 0))

        # Utilidad neta
        utilidad = ventas_mes - gastos_mes
        util_color = COLORES['exito'] if utilidad >= 0 else COLORES['error']
        util_card = tk.Frame(inner, bg=COLORES['fondo_card'],
                             highlightbackground=COLORES['borde'], highlightthickness=1)
        util_card.pack(fill='x', padx=20, pady=(0, 20))
        tk.Frame(util_card, bg=util_color, height=3).pack(fill='x')
        util_row = tk.Frame(util_card, bg=COLORES['fondo_card'], padx=20, pady=14)
        util_row.pack(fill='x')
        tk.Label(util_row, text="Utilidad Neta del Mes",
                 font=FUENTES['encabezado'], fg=COLORES['texto_secundario'],
                 bg=COLORES['fondo_card']).pack(side='left')
        tk.Label(util_row, text=format_money(utilidad),
                 font=('Consolas', 22, 'bold'), fg=util_color,
                 bg=COLORES['fondo_card']).pack(side='right')

    #  TAB 2: INGRESOS (Historial Ventas) 
    def _crear_tab_ingresos(self):
        frame = tk.Frame(self.notebook, bg=COLORES['fondo'])
        self.notebook.add(frame, text='  Ingresos  ')
        from modules.historial_ventas_module import HistorialVentasModule
        inst = HistorialVentasModule(frame, self.usuario)
        self._instancias.append(inst)

    #  TAB 3: EGRESOS (Gastos) 
    def _crear_tab_egresos(self):
        frame = tk.Frame(self.notebook, bg=COLORES['fondo'])
        self.notebook.add(frame, text='  Egresos  ')
        from modules.gastos_module import GastosModule
        inst = GastosModule(frame, self.usuario)
        self._instancias.append(inst)

    #  TAB 4: CAJA 
    def _crear_tab_caja(self):
        frame = tk.Frame(self.notebook, bg=COLORES['fondo'])
        self.notebook.add(frame, text='  Caja  ')
        from modules.caja_module import CajaModule
        inst = CajaModule(frame, self.usuario)
        self._instancias.append(inst)

    #  TAB 5: REPORTES 
    def _crear_tab_reportes(self):
        frame = tk.Frame(self.notebook, bg=COLORES['fondo'])
        self.notebook.add(frame, text='  Reportes  ')
        from modules.reportes_module import ReportesModule
        inst = ReportesModule(frame, self.usuario)
        self._instancias.append(inst)

    #  TAB 6: GRAFICAS
    def _crear_tab_graficas(self):
        frame = tk.Frame(self.notebook, bg=COLORES['fondo'])
        self.notebook.add(frame, text='  Graficas  ')
        self._render_graficas(frame)

    def _render_graficas(self, frame):
        # Canvas scrollable
        canvas = tk.Canvas(frame, bg=COLORES['fondo'], highlightthickness=0)
        scroll = ttk.Scrollbar(frame, orient='vertical', command=canvas.yview)
        inner = tk.Frame(canvas, bg=COLORES['fondo'])
        inner.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        _win = canvas.create_window((0, 0), window=inner, anchor='nw')
        canvas.configure(yscrollcommand=scroll.set)
        canvas.bind('<Configure>', lambda e: canvas.itemconfig(_win, width=e.width))
        canvas.pack(side='left', fill='both', expand=True)
        scroll.pack(side='right', fill='y')

        # Obtener datos
        hoy = datetime.date.today()
        mes_inicio = hoy.replace(day=1).isoformat()
        ventas_7d = []
        metodos_mes = []
        total_mes = 0
        mejor_dia = ('—', 0)

        try:
            with conexion_segura() as conn:
                # Ventas últimos 7 días
                for i in range(6, -1, -1):
                    dia = hoy - datetime.timedelta(days=i)
                    total = conn.execute(
                        "SELECT COALESCE(SUM(total),0) FROM ventas "
                        "WHERE DATE(fecha_creacion)=? AND estado!='ANULADA'",
                        (dia.isoformat(),)).fetchone()[0]
                    ventas_7d.append((dia.strftime('%d/%m'), float(total)))

                # Métodos de pago del mes
                metodos_mes = conn.execute("""
                    SELECT COALESCE(metodo_pago,'Sin especificar') as metodo,
                           COALESCE(SUM(total),0) as total
                    FROM ventas
                    WHERE DATE(fecha_creacion) >= ? AND estado != 'ANULADA'
                    GROUP BY metodo_pago ORDER BY total DESC LIMIT 6
                """, (mes_inicio,)).fetchall()
                metodos_mes = [(r['metodo'], float(r['total'])) for r in metodos_mes]

                total_mes = sum(v for _, v in ventas_7d)
                if ventas_7d:
                    mejor = max(ventas_7d, key=lambda x: x[1])
                    mejor_dia = mejor
        except Exception as e:
            tk.Label(inner, text=f"Error al cargar datos: {e}",
                     font=FUENTES['normal'], fg=COLORES['error'],
                     bg=COLORES['fondo']).pack(pady=20)
            return

        # --- Header ---
        hdr = tk.Frame(inner, bg=COLORES['primario'])
        hdr.pack(fill='x')
        tk.Label(hdr, text="Graficas Financieras", font=FUENTES['encabezado'],
                 fg=COLORES['texto_claro'], bg=COLORES['primario']).pack(side='left', padx=15, pady=8)
        tk.Label(hdr, text=hoy.strftime("%B %Y").capitalize(),
                 font=FUENTES['normal'], fg=COLORES['acento'],
                 bg=COLORES['primario']).pack(side='right', padx=15)

        # --- KPIs rápidos ---
        kpi_row = tk.Frame(inner, bg=COLORES['fondo'])
        kpi_row.pack(fill='x', padx=15, pady=12)
        for i in range(3):
            kpi_row.columnconfigure(i, weight=1)

        kpis = [
            ("Ventas Ultimos 7 Dias", format_money(sum(v for _, v in ventas_7d)), COLORES['primario']),
            ("Promedio Diario",        format_money(sum(v for _, v in ventas_7d) / max(len(ventas_7d), 1)), COLORES['agua']),
            (f"Mejor Dia ({mejor_dia[0]})", format_money(mejor_dia[1]), COLORES['exito']),
        ]
        for i, (titulo, valor, color) in enumerate(kpis):
            card = tk.Frame(kpi_row, bg=COLORES['fondo_card'],
                            highlightbackground=COLORES['borde'], highlightthickness=1)
            card.grid(row=0, column=i, padx=4, sticky='nsew')
            tk.Frame(card, bg=color, height=3).pack(fill='x')
            inner_card = tk.Frame(card, bg=COLORES['fondo_card'], padx=12, pady=10)
            inner_card.pack()
            tk.Label(inner_card, text=titulo, font=FUENTES['pequena'],
                     fg=COLORES['texto_secundario'], bg=COLORES['fondo_card']).pack(anchor='w')
            tk.Label(inner_card, text=valor, font=FUENTES['precio'],
                     fg=COLORES['texto'], bg=COLORES['fondo_card']).pack(anchor='w')

        # --- Gráfico de barras: ventas últimos 7 días ---
        tk.Label(inner, text="Ventas — Ultimos 7 Dias",
                 font=FUENTES['encabezado'], fg=COLORES['texto'],
                 bg=COLORES['fondo']).pack(anchor='w', padx=15, pady=(8, 4))

        chart1 = tk.Canvas(inner, bg=COLORES['fondo_card'], height=200,
                            highlightbackground=COLORES['borde'], highlightthickness=1)
        chart1.pack(fill='x', padx=15, pady=(0, 12))

        def _draw_barras_7d(c):
            c.delete('all')
            W = c.winfo_width() or 600
            H = 200
            pad_l, pad_r, pad_t, pad_b = 60, 20, 20, 40
            chart_w = W - pad_l - pad_r
            chart_h = H - pad_t - pad_b
            max_v = max((v for _, v in ventas_7d), default=1) or 1
            n = len(ventas_7d)
            bar_w = chart_w / n * 0.6
            gap   = chart_w / n

            # Líneas de referencia (4 líneas)
            for k in range(5):
                y = pad_t + chart_h - k * chart_h / 4
                val = max_v * k / 4
                c.create_line(pad_l, y, W - pad_r, y, fill=COLORES['borde'], dash=(3, 4))
                c.create_text(pad_l - 4, y, text=f"${int(val/1000)}k" if val >= 1000 else f"${int(val)}",
                              anchor='e', font=('Segoe UI', 8), fill=COLORES['texto_secundario'])

            for idx, (label, valor) in enumerate(ventas_7d):
                x_center = pad_l + gap * idx + gap / 2
                bar_h = (valor / max_v) * chart_h if max_v > 0 else 0
                x0 = x_center - bar_w / 2
                x1 = x_center + bar_w / 2
                y0 = pad_t + chart_h - bar_h
                y1 = pad_t + chart_h
                color = COLORES['acento'] if idx == len(ventas_7d) - 1 else COLORES['primario_claro']
                c.create_rectangle(x0, y0, x1, y1, fill=color, outline='', width=0)
                if valor > 0:
                    c.create_text(x_center, y0 - 4, text=f"${int(valor/1000)}k" if valor >= 1000 else f"${int(valor)}",
                                  anchor='s', font=('Segoe UI', 8, 'bold'), fill=COLORES['texto'])
                c.create_text(x_center, H - pad_b + 6, text=label,
                              anchor='n', font=('Segoe UI', 8), fill=COLORES['texto_secundario'])

        chart1.bind('<Configure>', lambda e: _draw_barras_7d(chart1))
        chart1.after(100, lambda: _draw_barras_7d(chart1))

        # --- Gráfico horizontal: métodos de pago del mes ---
        if metodos_mes:
            tk.Label(inner, text="Metodos de Pago — Este Mes",
                     font=FUENTES['encabezado'], fg=COLORES['texto'],
                     bg=COLORES['fondo']).pack(anchor='w', padx=15, pady=(8, 4))

            chart2 = tk.Canvas(inner, bg=COLORES['fondo_card'],
                                height=max(40 * len(metodos_mes), 120),
                                highlightbackground=COLORES['borde'], highlightthickness=1)
            chart2.pack(fill='x', padx=15, pady=(0, 12))

            def _draw_metodos(c):
                c.delete('all')
                W = c.winfo_width() or 600
                H = max(40 * len(metodos_mes), 120)
                pad_l, pad_r, pad_t = 120, 100, 12
                max_v = max((v for _, v in metodos_mes), default=1) or 1
                bar_h = 22
                gap = (H - pad_t) / max(len(metodos_mes), 1)
                colores_m = [COLORES['primario'], COLORES['agua'], COLORES['exito'],
                             COLORES['advertencia'], COLORES['info'], COLORES['error']]
                for idx, (metodo, valor) in enumerate(metodos_mes):
                    y_center = pad_t + gap * idx + gap / 2
                    bar_w = (valor / max_v) * (W - pad_l - pad_r) if max_v > 0 else 0
                    x0, y0 = pad_l, y_center - bar_h / 2
                    x1, y1 = pad_l + bar_w, y_center + bar_h / 2
                    color = colores_m[idx % len(colores_m)]
                    c.create_rectangle(x0, y0, x1, y1, fill=color, outline='', width=0)
                    c.create_text(pad_l - 6, y_center, text=metodo[:14],
                                  anchor='e', font=('Segoe UI', 9), fill=COLORES['texto'])
                    c.create_text(x1 + 6, y_center, text=format_money(valor),
                                  anchor='w', font=('Segoe UI', 8, 'bold'), fill=COLORES['texto'])

            chart2.bind('<Configure>', lambda e: _draw_metodos(chart2))
            chart2.after(100, lambda: _draw_metodos(chart2))

    def detener(self):
        for inst in self._instancias:
            if hasattr(inst, 'detener'):
                try:
                    inst.detener()
                except Exception:
                    pass
        try:
            self.parent.winfo_toplevel().unbind_all('<MouseWheel>')
            self.parent.winfo_toplevel().unbind_all('<Button-4>')
            self.parent.winfo_toplevel().unbind_all('<Button-5>')
        except Exception:
            pass