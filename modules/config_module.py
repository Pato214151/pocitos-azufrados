"""
Módulo de Configuración - Club Los Pocitos Azufrados
Configuración del sistema (admin only)
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os, sys, datetime, shutil, sqlite3

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from utils.tema_corporativo import COLORES, FUENTES, crear_boton
from database.connection import get_connection, conexion_segura, get_db_path
from utils.logger import log_auditoria


# Tablas permitidas para operaciones con f-string SQL (SELECT COUNT/MAX y DELETE en limpieza).
# Nunca interpolar nombres de tabla que vengan del usuario — solo los de esta lista.
_TABLAS_PERMITIDAS = {
    'ventas', 'productos', 'usuarios', 'facturas_electronicas', 'pagos',
    'venta_detalle', 'movimientos_caja', 'caja_diaria', 'movimientos_inventario',
    'ordenes_cocina', 'reserva_checklist', 'reservas_almuerzo', 'boletas_entrada',
    'gastos', 'auditoria', 'sesiones', 'tareas_preproduccion',
}

_COLUMNAS_FECHA_PERMITIDAS = {'fecha_creacion', 'fecha', 'fecha_inicio', 'fecha_pago'}


class ConfigModule:
    def __init__(self, parent, usuario):
        self.parent = parent
        self.usuario = usuario
        self._canvas_list = []  # Para guardar referencias de canvas

        # Verificar que sea admin
        if usuario['rol'] != 'administrador':
            tk.Label(self.parent, text=" Acceso Denegado: Solo administradores pueden acceder",
                     font=FUENTES['titulo'], fg=COLORES['error'],
                     bg=COLORES['fondo']).pack(padx=15, pady=20)
            return

        self._crear_interfaz()
        self._cargar_configuracion()

    def _crear_interfaz(self):
        """Interfaz principal de configuración"""
        # Header
        header = tk.Frame(self.parent, bg=COLORES['primario'])
        header.pack(fill='x')

        inner_hdr = tk.Frame(header, bg=COLORES['primario'], padx=15, pady=10)
        inner_hdr.pack(fill='x')

        tk.Label(inner_hdr, text="Configuracion del Sistema",
                 font=FUENTES['encabezado'], fg=COLORES['texto_claro'],
                 bg=COLORES['primario']).pack(side='left')

        # ========== CUERPO PRINCIPAL ==========
        body = tk.Frame(self.parent, bg=COLORES['fondo'])
        body.pack(fill='both', expand=True, padx=15, pady=5)

        # Notebook para tabs
        notebook = ttk.Notebook(body)
        notebook.pack(fill='both', expand=True)

        # ========== TAB 1: NEGOCIO ==========
        tab1 = tk.Frame(notebook, bg=COLORES['fondo'])
        notebook.add(tab1, text='Datos del Negocio')

        # Canvas scrollable para tab1
        canvas1 = tk.Canvas(tab1, bg=COLORES['fondo'], highlightthickness=0)
        sb1 = ttk.Scrollbar(tab1, orient='vertical', command=canvas1.yview)
        canvas1.configure(yscrollcommand=sb1.set)
        sb1.pack(side='right', fill='y')
        canvas1.pack(side='left', fill='both', expand=True)

        scroll_frame1 = tk.Frame(canvas1, bg=COLORES['fondo'])
        _win1 = canvas1.create_window((0, 0), window=scroll_frame1, anchor='nw')
        canvas1.bind('<Configure>', lambda e: canvas1.itemconfig(_win1, width=e.width))
        scroll_frame1.bind('<Configure>', lambda e: canvas1.configure(scrollregion=canvas1.bbox('all')))

        # MouseWheel
        def _on_wheel1(e):
            canvas1.yview_scroll(int(-1*(e.delta/120)), "units")
        canvas1.bind_all('<MouseWheel>', _on_wheel1)
        canvas1.bind_all('<Button-4>', lambda e: canvas1.yview_scroll(-1, 'units'))
        canvas1.bind_all('<Button-5>', lambda e: canvas1.yview_scroll(1, 'units'))
        self._canvas_list.append(canvas1)

        form1 = tk.Frame(scroll_frame1, bg=COLORES['fondo_card'],
                        highlightbackground=COLORES['borde'], highlightthickness=1)
        form1.pack(fill='both', expand=True, padx=15, pady=15)

        form_inner = tk.Frame(form1, bg=COLORES['fondo_card'], padx=20, pady=20)
        form_inner.pack(fill='x')

        # Nombre del negocio
        tk.Label(form_inner, text="Nombre del Negocio:", font=FUENTES['normal'],
                 fg=COLORES['texto'], bg=COLORES['fondo_card']).pack(anchor='w')
        self.entry_nombre = tk.Entry(form_inner, font=FUENTES['input'], width=50,
                                     relief='solid', bd=1, highlightthickness=1,
                                     highlightbackground=COLORES['borde'])
        self.entry_nombre.pack(fill='x', ipady=6, pady=(0, 15))

        # Teléfono
        tk.Label(form_inner, text="Teléfono:", font=FUENTES['normal'],
                 fg=COLORES['texto'], bg=COLORES['fondo_card']).pack(anchor='w')
        self.entry_telefono = tk.Entry(form_inner, font=FUENTES['input'], width=50,
                                       relief='solid', bd=1, highlightthickness=1,
                                       highlightbackground=COLORES['borde'])
        self.entry_telefono.pack(fill='x', ipady=6, pady=(0, 15))

        # NIT
        tk.Label(form_inner, text="NIT / Cédula:", font=FUENTES['normal'],
                 fg=COLORES['texto'], bg=COLORES['fondo_card']).pack(anchor='w')
        self.entry_nit = tk.Entry(form_inner, font=FUENTES['input'], width=50,
                                  relief='solid', bd=1, highlightthickness=1,
                                  highlightbackground=COLORES['borde'])
        self.entry_nit.pack(fill='x', ipady=6, pady=(0, 15))

        # Dirección / Ubicación
        tk.Label(form_inner, text="Dirección / Ubicación:", font=FUENTES['normal'],
                 fg=COLORES['texto'], bg=COLORES['fondo_card']).pack(anchor='w')
        self.entry_ubicacion = tk.Entry(form_inner, font=FUENTES['input'], width=50,
                                        relief='solid', bd=1, highlightthickness=1,
                                        highlightbackground=COLORES['borde'])
        self.entry_ubicacion.pack(fill='x', ipady=6, pady=(0, 15))

        # Precio boleta
        tk.Label(form_inner, text="Precio de Boleta (COP):", font=FUENTES['normal'],
                 fg=COLORES['texto'], bg=COLORES['fondo_card']).pack(anchor='w')
        self.entry_precio_boleta = tk.Entry(form_inner, font=FUENTES['input'], width=50,
                                           relief='solid', bd=1, highlightthickness=1,
                                           highlightbackground=COLORES['borde'])
        self.entry_precio_boleta.pack(fill='x', ipady=6, pady=(0, 15))

        # ===== Resolución DIAN =====
        sep = tk.Frame(form_inner, bg=COLORES['borde'], height=1)
        sep.pack(fill='x', pady=(10, 0))

        tk.Label(form_inner, text="Resolucion DIAN",
                 font=FUENTES['encabezado'], fg=COLORES['texto'],
                 bg=COLORES['fondo_card']).pack(anchor='w', pady=(10, 4))

        tk.Label(form_inner, text="Numero de Resolucion:",
                 font=FUENTES['normal'], fg=COLORES['texto'],
                 bg=COLORES['fondo_card']).pack(anchor='w')
        self.entry_res_numero = tk.Entry(form_inner, font=FUENTES['input'], width=50,
                                         relief='solid', bd=1,
                                         highlightbackground=COLORES['borde'], highlightthickness=1)
        self.entry_res_numero.pack(fill='x', ipady=6, pady=(0, 10))

        fechas_f = tk.Frame(form_inner, bg=COLORES['fondo_card'])
        fechas_f.pack(fill='x', pady=(0, 10))
        tk.Label(fechas_f, text="Vigencia Desde (YYYY-MM-DD):",
                 font=FUENTES['normal'], fg=COLORES['texto'],
                 bg=COLORES['fondo_card']).pack(side='left')
        self.entry_res_fecha_desde = tk.Entry(fechas_f, font=FUENTES['input'], width=13,
                                               relief='solid', bd=1)
        self.entry_res_fecha_desde.pack(side='left', padx=(5, 15), ipady=4)
        tk.Label(fechas_f, text="Hasta (YYYY-MM-DD):",
                 font=FUENTES['normal'], fg=COLORES['texto'],
                 bg=COLORES['fondo_card']).pack(side='left')
        self.entry_res_fecha_hasta = tk.Entry(fechas_f, font=FUENTES['input'], width=13,
                                               relief='solid', bd=1)
        self.entry_res_fecha_hasta.pack(side='left', padx=5, ipady=4)

        rango_f = tk.Frame(form_inner, bg=COLORES['fondo_card'])
        rango_f.pack(fill='x', pady=(0, 10))
        tk.Label(rango_f, text="Prefijo:",
                 font=FUENTES['normal'], fg=COLORES['texto'],
                 bg=COLORES['fondo_card']).pack(side='left')
        self.entry_res_prefijo = tk.Entry(rango_f, font=FUENTES['input'], width=6,
                                           relief='solid', bd=1)
        self.entry_res_prefijo.pack(side='left', padx=(5, 20), ipady=4)
        tk.Label(rango_f, text="Rango Desde:",
                 font=FUENTES['normal'], fg=COLORES['texto'],
                 bg=COLORES['fondo_card']).pack(side='left')
        self.entry_res_desde = tk.Entry(rango_f, font=FUENTES['input'], width=8,
                                         relief='solid', bd=1)
        self.entry_res_desde.pack(side='left', padx=5, ipady=4)
        tk.Label(rango_f, text="Hasta:",
                 font=FUENTES['normal'], fg=COLORES['texto'],
                 bg=COLORES['fondo_card']).pack(side='left')
        self.entry_res_hasta = tk.Entry(rango_f, font=FUENTES['input'], width=8,
                                         relief='solid', bd=1)
        self.entry_res_hasta.pack(side='left', padx=5, ipady=4)

        # ===== Impresora =====
        tk.Label(form_inner, text="Impresora",
                 font=FUENTES['normal_bold'], fg=COLORES['primario'],
                 bg=COLORES['fondo_card']).pack(anchor='w', pady=(18, 4))
        tk.Frame(form_inner, bg=COLORES['acento'], height=2).pack(fill='x', pady=(0, 8))

        imp_row = tk.Frame(form_inner, bg=COLORES['fondo_card'])
        imp_row.pack(anchor='w')
        tk.Label(imp_row, text="Ancho del ticket:",
                 font=FUENTES['normal'], fg=COLORES['texto'],
                 bg=COLORES['fondo_card']).pack(side='left', padx=(0, 10))
        self.var_ancho_ticket = tk.StringVar(master=self.parent, value='80')
        for ancho_val, ancho_lbl in [('80', '80 mm (estandar)'), ('58', '58 mm (mini)')]:
            tk.Radiobutton(imp_row, text=ancho_lbl, variable=self.var_ancho_ticket,
                           value=ancho_val,
                           font=FUENTES['normal'], fg=COLORES['texto'],
                           bg=COLORES['fondo_card'],
                           activebackground=COLORES['fondo_card'],
                           selectcolor=COLORES['primario']).pack(side='left', padx=8)

        # Modo de impresión
        modo_row = tk.Frame(form_inner, bg=COLORES['fondo_card'])
        modo_row.pack(anchor='w', pady=(8, 0))
        tk.Label(modo_row, text="Modo de impresion:",
                 font=FUENTES['normal'], fg=COLORES['texto'],
                 bg=COLORES['fondo_card']).pack(side='left', padx=(0, 10))
        self.var_modo_impresora = tk.StringVar(master=self.parent, value='pdf')
        for val, lbl in [('pdf', 'PDF (visor del sistema)'), ('escpos', 'ESC/POS (termica directa)')]:
            tk.Radiobutton(modo_row, text=lbl, variable=self.var_modo_impresora,
                           value=val, command=self._toggle_escpos,
                           font=FUENTES['normal'], fg=COLORES['texto'],
                           bg=COLORES['fondo_card'],
                           activebackground=COLORES['fondo_card'],
                           selectcolor=COLORES['primario']).pack(side='left', padx=8)

        # Nombre de impresora ESC/POS
        nombre_row = tk.Frame(form_inner, bg=COLORES['fondo_card'])
        nombre_row.pack(anchor='w', fill='x', pady=(6, 0))
        tk.Label(nombre_row, text="Nombre impresora (Windows):",
                 font=FUENTES['normal'], fg=COLORES['texto'],
                 bg=COLORES['fondo_card']).pack(side='left', padx=(0, 8))
        self.entry_impresora_nombre = tk.Entry(nombre_row, font=FUENTES['input'], width=28,
                                               relief='solid', bd=1, state='disabled')
        self.entry_impresora_nombre.pack(side='left', ipady=4, padx=(0, 8))
        self.btn_probar_impresora = crear_boton(
            nombre_row, "Probar", self._probar_impresora, tipo='secundario'
        )
        self.btn_probar_impresora.pack(side='left')
        self.btn_probar_impresora.config(state='disabled')

        # Botón guardar
        crear_boton(form_inner, " Guardar Cambios", self._guardar_negocio, tipo='exito').pack(pady=10)

        # ========== TAB 2: MÉTODOS DE PAGO ==========
        tab2 = tk.Frame(notebook, bg=COLORES['fondo'])
        notebook.add(tab2, text='Métodos de Pago')

        # Canvas scrollable para tab2
        canvas2 = tk.Canvas(tab2, bg=COLORES['fondo'], highlightthickness=0)
        sb2 = ttk.Scrollbar(tab2, orient='vertical', command=canvas2.yview)
        canvas2.configure(yscrollcommand=sb2.set)
        sb2.pack(side='right', fill='y')
        canvas2.pack(side='left', fill='both', expand=True)

        scroll_frame2 = tk.Frame(canvas2, bg=COLORES['fondo'])
        _win2 = canvas2.create_window((0, 0), window=scroll_frame2, anchor='nw')
        canvas2.bind('<Configure>', lambda e: canvas2.itemconfig(_win2, width=e.width))
        scroll_frame2.bind('<Configure>', lambda e: canvas2.configure(scrollregion=canvas2.bbox('all')))

        # MouseWheel
        def _on_wheel2(e):
            canvas2.yview_scroll(int(-1*(e.delta/120)), "units")
        canvas2.bind_all('<MouseWheel>', _on_wheel2)
        canvas2.bind_all('<Button-4>', lambda e: canvas2.yview_scroll(-1, 'units'))
        canvas2.bind_all('<Button-5>', lambda e: canvas2.yview_scroll(1, 'units'))
        self._canvas_list.append(canvas2)

        frame_metodos = tk.Frame(scroll_frame2, bg=COLORES['fondo_card'],
                                highlightbackground=COLORES['borde'], highlightthickness=1)
        frame_metodos.pack(fill='both', expand=True, padx=15, pady=15)

        tk.Label(frame_metodos, text="Métodos de Pago Disponibles", font=FUENTES['encabezado'],
                 fg=COLORES['texto'], bg=COLORES['fondo_card']).pack(padx=15, pady=(15, 10), anchor='w')

        # Crear lista de métodos
        self.var_metodos = {}
        metodos_nombres = ['EFECTIVO', 'NEQUI', 'DAVIPLATA', 'TULLAVE', 'BANCOLOMBIA', 'TRANSFERENCIA']

        metodos_frame = tk.Frame(frame_metodos, bg=COLORES['fondo_card'])
        metodos_frame.pack(fill='x', padx=15, pady=10)

        for metodo in metodos_nombres:
            self.var_metodos[metodo] = tk.BooleanVar(master=self.parent, value=True)
            check = tk.Checkbutton(metodos_frame, text=metodo, font=FUENTES['normal'],
                                  variable=self.var_metodos[metodo],
                                  bg=COLORES['fondo_card'], fg=COLORES['texto'],
                                  activebackground=COLORES['fondo_card'],
                                  selectcolor=COLORES['primario'])
            check.pack(anchor='w', pady=5)

        crear_boton(metodos_frame, " Guardar", self._guardar_metodos, tipo='exito').pack(pady=10)

        # ========== TAB 3: SINCRONIZACIÓN ==========
        tab3 = tk.Frame(notebook, bg=COLORES['fondo'])
        notebook.add(tab3, text='Sincronización')

        # Canvas scrollable para tab3
        canvas3 = tk.Canvas(tab3, bg=COLORES['fondo'], highlightthickness=0)
        sb3 = ttk.Scrollbar(tab3, orient='vertical', command=canvas3.yview)
        canvas3.configure(yscrollcommand=sb3.set)
        sb3.pack(side='right', fill='y')
        canvas3.pack(side='left', fill='both', expand=True)

        scroll_frame3 = tk.Frame(canvas3, bg=COLORES['fondo'])
        _win3 = canvas3.create_window((0, 0), window=scroll_frame3, anchor='nw')
        canvas3.bind('<Configure>', lambda e: canvas3.itemconfig(_win3, width=e.width))
        scroll_frame3.bind('<Configure>', lambda e: canvas3.configure(scrollregion=canvas3.bbox('all')))

        # MouseWheel
        def _on_wheel3(e):
            canvas3.yview_scroll(int(-1*(e.delta/120)), "units")
        canvas3.bind_all('<MouseWheel>', _on_wheel3)
        canvas3.bind_all('<Button-4>', lambda e: canvas3.yview_scroll(-1, 'units'))
        canvas3.bind_all('<Button-5>', lambda e: canvas3.yview_scroll(1, 'units'))
        self._canvas_list.append(canvas3)

        form3 = tk.Frame(scroll_frame3, bg=COLORES['fondo_card'],
                        highlightbackground=COLORES['borde'], highlightthickness=1)
        form3.pack(fill='both', expand=True, padx=15, pady=15)

        form3_inner = tk.Frame(form3, bg=COLORES['fondo_card'], padx=20, pady=20)
        form3_inner.pack(fill='x')

        tk.Label(form3_inner, text="URL del Servidor:", font=FUENTES['normal'],
                 fg=COLORES['texto'], bg=COLORES['fondo_card']).pack(anchor='w')
        self.entry_sync_url = tk.Entry(form3_inner, font=FUENTES['input'], width=50,
                                       relief='solid', bd=1, highlightthickness=1,
                                       highlightbackground=COLORES['borde'])
        self.entry_sync_url.pack(fill='x', ipady=6, pady=(0, 15))

        tk.Label(form3_inner, text="Token de Autenticación:", font=FUENTES['normal'],
                 fg=COLORES['texto'], bg=COLORES['fondo_card']).pack(anchor='w')
        self.entry_sync_token = tk.Entry(form3_inner, font=FUENTES['input'], width=50,
                                         relief='solid', bd=1, highlightthickness=1,
                                         highlightbackground=COLORES['borde'])
        self.entry_sync_token.pack(fill='x', ipady=6, pady=(0, 15))

        self.var_sync_auto = tk.BooleanVar(master=self.parent, value=False)
        tk.Checkbutton(form3_inner, text="Sincronización automática", font=FUENTES['normal'],
                      variable=self.var_sync_auto,
                      bg=COLORES['fondo_card'], fg=COLORES['texto'],
                      activebackground=COLORES['fondo_card'],
                      selectcolor=COLORES['primario']).pack(anchor='w', pady=10)

        crear_boton(form3_inner, " Guardar Sincronización", self._guardar_sync, tipo='exito').pack(pady=10)

        # ── Cocina Web ──────────────────────────────────────────────────────
        tk.Frame(form3_inner, bg=COLORES['borde'], height=1).pack(fill='x', pady=(15, 10))
        tk.Label(form3_inner, text="Cocina Web (WiFi)", font=FUENTES['normal_bold'],
                 fg=COLORES['texto'], bg=COLORES['fondo_card']).pack(anchor='w')

        tk.Label(form3_inner, text="Clave de acceso (usuario: cocina):", font=FUENTES['normal'],
                 fg=COLORES['texto'], bg=COLORES['fondo_card']).pack(anchor='w', pady=(8, 2))
        self.entry_cocina_token = tk.Entry(form3_inner, font=FUENTES['input'], width=30,
                                           relief='solid', bd=1,
                                           highlightbackground=COLORES['borde'])
        self.entry_cocina_token.pack(fill='x', ipady=6, pady=(0, 10))

        tk.Label(form3_inner, text="Intervalo de actualización (seg, 5-120):", font=FUENTES['normal'],
                 fg=COLORES['texto'], bg=COLORES['fondo_card']).pack(anchor='w', pady=(0, 2))
        self.entry_cocina_intervalo = tk.Entry(form3_inner, font=FUENTES['input'], width=10,
                                               relief='solid', bd=1,
                                               highlightbackground=COLORES['borde'])
        self.entry_cocina_intervalo.pack(anchor='w', ipady=6, pady=(0, 10))

        crear_boton(form3_inner, " Guardar Cocina Web", self._guardar_cocina_web, tipo='primario').pack(pady=5)

        # ── Conexion con Ducklab (portal) ───────────────────────────────────
        tk.Frame(form3_inner, bg=COLORES['borde'], height=1).pack(fill='x', pady=(15, 10))
        tk.Label(form3_inner, text="Conexion con Ducklab (portal)", font=FUENTES['normal_bold'],
                 fg=COLORES['texto'], bg=COLORES['fondo_card']).pack(anchor='w')
        tk.Label(form3_inner, text="Activa licencia, telemetria y respaldo en la nube. Pega la API key del sistema (la genera Ducklab) y guarda.",
                 font=FUENTES['normal'], fg=COLORES['texto'], bg=COLORES['fondo_card'],
                 wraplength=520, justify='left').pack(anchor='w', pady=(4, 8))

        tk.Label(form3_inner, text="URL del portal:", font=FUENTES['normal'],
                 fg=COLORES['texto'], bg=COLORES['fondo_card']).pack(anchor='w', pady=(0, 2))
        self.entry_ducklab_url = tk.Entry(form3_inner, font=FUENTES['input'], width=50,
                                          relief='solid', bd=1, highlightbackground=COLORES['borde'])
        self.entry_ducklab_url.pack(fill='x', ipady=6, pady=(0, 10))

        tk.Label(form3_inner, text="API key del sistema:", font=FUENTES['normal'],
                 fg=COLORES['texto'], bg=COLORES['fondo_card']).pack(anchor='w', pady=(0, 2))
        self.entry_ducklab_key = tk.Entry(form3_inner, font=FUENTES['input'], width=50,
                                          relief='solid', bd=1, highlightbackground=COLORES['borde'])
        self.entry_ducklab_key.pack(fill='x', ipady=6, pady=(0, 10))

        crear_boton(form3_inner, " Guardar Conexion Ducklab", self._guardar_ducklab, tipo='primario').pack(pady=5)

        # ========== TAB 4: MANTENIMIENTO ==========
        tab4 = tk.Frame(notebook, bg=COLORES['fondo'])
        notebook.add(tab4, text='Mantenimiento')

        # Canvas scrollable para tab4
        canvas4 = tk.Canvas(tab4, bg=COLORES['fondo'], highlightthickness=0)
        sb4 = ttk.Scrollbar(tab4, orient='vertical', command=canvas4.yview)
        canvas4.configure(yscrollcommand=sb4.set)
        sb4.pack(side='right', fill='y')
        canvas4.pack(side='left', fill='both', expand=True)

        scroll_frame4 = tk.Frame(canvas4, bg=COLORES['fondo'])
        _win4 = canvas4.create_window((0, 0), window=scroll_frame4, anchor='nw')
        canvas4.bind('<Configure>', lambda e: canvas4.itemconfig(_win4, width=e.width))
        scroll_frame4.bind('<Configure>', lambda e: canvas4.configure(scrollregion=canvas4.bbox('all')))

        # MouseWheel
        def _on_wheel4(e):
            canvas4.yview_scroll(int(-1*(e.delta/120)), "units")
        canvas4.bind_all('<MouseWheel>', _on_wheel4)
        canvas4.bind_all('<Button-4>', lambda e: canvas4.yview_scroll(-1, 'units'))
        canvas4.bind_all('<Button-5>', lambda e: canvas4.yview_scroll(1, 'units'))
        self._canvas_list.append(canvas4)

        maint_frame = tk.Frame(scroll_frame4, bg=COLORES['fondo_card'],
                              highlightbackground=COLORES['borde'], highlightthickness=1)
        maint_frame.pack(fill='both', expand=True, padx=15, pady=15)

        maint_inner = tk.Frame(maint_frame, bg=COLORES['fondo_card'], padx=20, pady=20)
        maint_inner.pack(fill='x')

        tk.Label(maint_inner, text="Tareas de Mantenimiento", font=FUENTES['encabezado'],
                 fg=COLORES['texto'], bg=COLORES['fondo_card']).pack(anchor='w', pady=(0, 15))

        crear_boton(maint_inner, " Crear Backup", self._crear_backup, tipo='primario').pack(fill='x', pady=5)
        crear_boton(maint_inner, " Verificar Backup", self._verificar_backup, tipo='secundario').pack(fill='x', pady=5)
        crear_boton(maint_inner, " Restaurar Backup", self._restaurar_backup, tipo='acento').pack(fill='x', pady=5)
        crear_boton(maint_inner, " Limpiar Logs", self._limpiar_logs, tipo='advertencia').pack(fill='x', pady=5)
        crear_boton(maint_inner, " Información del Sistema", self._info_sistema, tipo='secundario').pack(fill='x', pady=5)

        tk.Frame(maint_inner, bg=COLORES['borde'], height=1).pack(fill='x', pady=(15, 5))
        tk.Label(maint_inner, text="Zona Peligrosa",
                 font=FUENTES['normal_bold'], fg=COLORES['error'],
                 bg=COLORES['fondo_card']).pack(anchor='w', pady=(0, 4))
        tk.Label(maint_inner,
                 text="Borra todas las ventas, movimientos, caja, boletas y registros\n"
                      "de operacion. Conserva usuarios, productos y configuracion.",
                 font=FUENTES['pequena'], fg=COLORES['texto_secundario'],
                 bg=COLORES['fondo_card'], justify='left').pack(anchor='w', pady=(0, 6))
        crear_boton(maint_inner, " Limpiar Datos de Operacion",
                    self._limpiar_datos_operacion, tipo='error').pack(fill='x', pady=5)

    def _cargar_configuracion(self):
        """Carga la configuración actual"""
        try:
            with conexion_segura() as conn:
                configs = conn.execute("SELECT clave, valor FROM configuracion").fetchall()

                config_dict = {row['clave']: row['valor'] for row in configs}

                self.entry_nombre.delete(0, tk.END)
                self.entry_nombre.insert(0, config_dict.get('nombre_negocio', 'Club Los Pocitos Azufrados'))

                self.entry_telefono.delete(0, tk.END)
                self.entry_telefono.insert(0, config_dict.get('telefono', ''))

                self.entry_nit.delete(0, tk.END)
                self.entry_nit.insert(0, config_dict.get('nit', ''))

                self.entry_ubicacion.delete(0, tk.END)
                self.entry_ubicacion.insert(0, config_dict.get('ubicacion', ''))

                self.entry_precio_boleta.delete(0, tk.END)
                self.entry_precio_boleta.insert(0, config_dict.get('precio_boleta_persona', '35000'))

                # Resolución DIAN
                self.entry_res_numero.delete(0, tk.END)
                self.entry_res_numero.insert(0, config_dict.get('resolucion_dian_numero', ''))
                self.entry_res_fecha_desde.delete(0, tk.END)
                self.entry_res_fecha_desde.insert(0, config_dict.get('resolucion_dian_fecha_desde', ''))
                self.entry_res_fecha_hasta.delete(0, tk.END)
                self.entry_res_fecha_hasta.insert(0, config_dict.get('resolucion_dian_fecha_hasta', ''))
                self.entry_res_prefijo.delete(0, tk.END)
                self.entry_res_prefijo.insert(0, config_dict.get('resolucion_dian_prefijo', 'LP'))
                self.entry_res_desde.delete(0, tk.END)
                self.entry_res_desde.insert(0, config_dict.get('resolucion_dian_desde', '1'))
                self.entry_res_hasta.delete(0, tk.END)
                self.entry_res_hasta.insert(0, config_dict.get('resolucion_dian_hasta', '10000'))

                # Ancho del ticket de impresora y modo ESC/POS
                self.var_ancho_ticket.set(config_dict.get('impresora_ancho_mm', '80'))
                self.var_modo_impresora.set(config_dict.get('impresora_modo', 'pdf'))
                self.entry_impresora_nombre.config(state='normal')
                self.entry_impresora_nombre.delete(0, tk.END)
                self.entry_impresora_nombre.insert(0, config_dict.get('impresora_nombre', ''))
                self._toggle_escpos()

                self.entry_sync_url.delete(0, tk.END)
                self.entry_sync_url.insert(0, config_dict.get('sync_url', ''))

                self.entry_sync_token.delete(0, tk.END)
                self.entry_sync_token.insert(0, config_dict.get('sync_token', ''))

                self.var_sync_auto.set(config_dict.get('sync_auto', '0') == '1')

                self.entry_cocina_token.delete(0, tk.END)
                self.entry_cocina_token.insert(0, config_dict.get('cocina_web_token', ''))

                self.entry_cocina_intervalo.delete(0, tk.END)
                self.entry_cocina_intervalo.insert(0, config_dict.get('cocina_web_intervalo', '15'))

                # Conexion con Ducklab (URL pre-llenada por defecto)
                DUCKLAB_URL_DEFAULT = 'https://mi-pagina-web-two-lilac.vercel.app/api/telemetry'
                self.entry_ducklab_url.delete(0, tk.END)
                self.entry_ducklab_url.insert(0, config_dict.get('ducklab_telemetry_url', '') or DUCKLAB_URL_DEFAULT)
                self.entry_ducklab_key.delete(0, tk.END)
                self.entry_ducklab_key.insert(0, config_dict.get('ducklab_api_key', ''))

                # Restaurar métodos de pago habilitados
                metodos_guardados = config_dict.get('metodos_pago_habilitados', '')
                if metodos_guardados:
                    habilitados = set(metodos_guardados.split(','))
                    for metodo, var in self.var_metodos.items():
                        var.set(metodo in habilitados)

        except Exception as e:
            messagebox.showerror("Error", f"Error al cargar configuración: {str(e)}")

    def _guardar_negocio(self):
        """Guarda los datos del negocio y la resolución DIAN"""
        precio_str = self.entry_precio_boleta.get().strip()
        try:
            precio_val = int(float(precio_str))
            if precio_val <= 0:
                raise ValueError
        except (ValueError, TypeError):
            messagebox.showwarning("Valor invalido", "El precio de boleta debe ser un numero positivo.")
            self.entry_precio_boleta.focus_set()
            return

        # Validar fechas DIAN si están ingresadas
        fecha_desde = self.entry_res_fecha_desde.get().strip()
        fecha_hasta = self.entry_res_fecha_hasta.get().strip()
        for lbl, val in [("Fecha Desde DIAN", fecha_desde), ("Fecha Hasta DIAN", fecha_hasta)]:
            if val:
                try:
                    datetime.datetime.strptime(val, '%Y-%m-%d')
                except ValueError:
                    messagebox.showwarning("Fecha invalida", f"{lbl}: use el formato YYYY-MM-DD (ej. 2026-01-01).")
                    return

        # Validar rango numérico DIAN
        desde_num = self.entry_res_desde.get().strip() or '1'
        hasta_num = self.entry_res_hasta.get().strip() or '10000'
        try:
            int(desde_num)
            int(hasta_num)
        except ValueError:
            messagebox.showwarning("Rango invalido", "El rango de la resolucion DIAN debe ser numerico.")
            return

        try:
            with conexion_segura() as conn:
                configs = [
                    ('nombre_negocio',           self.entry_nombre.get().strip(),    'texto'),
                    ('telefono',                 self.entry_telefono.get().strip(),   'texto'),
                    ('nit',                      self.entry_nit.get().strip(),        'texto'),
                    ('ubicacion',                self.entry_ubicacion.get().strip(),  'texto'),
                    ('precio_boleta_persona',    str(precio_val),                     'numero'),
                    # Resolución DIAN
                    ('resolucion_dian_numero',      self.entry_res_numero.get().strip(),     'texto'),
                    ('resolucion_dian_fecha_desde', fecha_desde,                             'texto'),
                    ('resolucion_dian_fecha_hasta', fecha_hasta,                             'texto'),
                    ('resolucion_dian_prefijo',     self.entry_res_prefijo.get().strip() or 'LP', 'texto'),
                    ('resolucion_dian_desde',       desde_num,                               'numero'),
                    ('resolucion_dian_hasta',       hasta_num,                               'numero'),
                    ('impresora_ancho_mm',  self.var_ancho_ticket.get(),                    'numero'),
                    ('impresora_modo',      self.var_modo_impresora.get(),                  'texto'),
                    ('impresora_nombre',    self.entry_impresora_nombre.get().strip(),       'texto'),
                ]

                for clave, valor, tipo in configs:
                    conn.execute(
                        "INSERT OR REPLACE INTO configuracion (clave, valor, tipo) VALUES (?, ?, ?)",
                        (clave, valor, tipo)
                    )

                log_auditoria(conn, 'configuracion', 0, 'UPDATE',
                              self.usuario['usuario'], "Actualizacion de datos del negocio y resolucion DIAN")

            messagebox.showinfo("Exito", "Configuracion guardada correctamente.")

        except Exception as e:
            messagebox.showerror("Error", f"Error al guardar: {str(e)}")

    def _toggle_escpos(self):
        """Habilita/deshabilita los controles de impresora ESC/POS según el modo."""
        state = 'normal' if self.var_modo_impresora.get() == 'escpos' else 'disabled'
        self.entry_impresora_nombre.config(state=state)
        self.btn_probar_impresora.config(state=state)

    def _probar_impresora(self):
        """Envía una página de prueba a la impresora ESC/POS configurada."""
        nombre = self.entry_impresora_nombre.get().strip()
        if not nombre:
            messagebox.showwarning("Sin nombre", "Ingrese el nombre de la impresora antes de probar.")
            return
        from utils.printing import imprimir_prueba_escpos
        imprimir_prueba_escpos(nombre)

    def _guardar_metodos(self):
        """Guarda los métodos de pago habilitados en la tabla configuracion"""
        habilitados = [m for m, var in self.var_metodos.items() if var.get()]
        if not habilitados:
            messagebox.showwarning("Advertencia", "Debe habilitar al menos un método de pago.")
            return
        try:
            with conexion_segura() as conn:
                conn.execute(
                  "INSERT OR REPLACE INTO configuracion (clave, valor, tipo) VALUES (?, ?, ?)",
                    ('metodos_pago_habilitados', ','.join(habilitados), 'texto')
                )
                log_auditoria(conn, 'configuracion', 0, 'UPDATE',
                             self.usuario['usuario'], "Métodos de pago actualizados")
            messagebox.showinfo("Exito", f"Métodos guardados:\n{', '.join(habilitados)}")
        except Exception as e:
            messagebox.showerror("Error", f"Error al guardar métodos: {str(e)}")

    def _guardar_sync(self):
        """Guarda la configuración de sincronización"""
        try:
            with conexion_segura() as conn:
                configs = [
                    ('sync_url', self.entry_sync_url.get(), 'texto'),
                    ('sync_token', self.entry_sync_token.get(), 'texto'),
                    ('sync_auto', '1' if self.var_sync_auto.get() else '0', 'booleano'),
                ]

                for clave, valor, tipo in configs:
                    conn.execute("""
                        INSERT OR REPLACE INTO configuracion (clave, valor, tipo)
                        VALUES (?, ?, ?)
                  """, (clave, valor, tipo))

                log_auditoria(conn, 'configuracion', 0, 'UPDATE',
                            self.usuario['usuario'], "Actualización de configuración de sincronización")

            messagebox.showinfo("Exito", "Sincronización configurada")

        except Exception as e:
            messagebox.showerror("Error", f"Error: {str(e)}")

    def _guardar_cocina_web(self):
        """Guarda la clave y el intervalo de la cocina web"""
        token = self.entry_cocina_token.get().strip()
        intervalo_str = self.entry_cocina_intervalo.get().strip()
        try:
            intervalo = int(intervalo_str)
            if not (5 <= intervalo <= 120):
                raise ValueError
        except (ValueError, TypeError):
            messagebox.showwarning("Valor invalido", "El intervalo debe ser un numero entre 5 y 120.")
            self.entry_cocina_intervalo.focus_set()
            return
        try:
            with conexion_segura() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO configuracion (clave, valor, tipo) VALUES (?, ?, ?)",
                    ('cocina_web_token', token, 'texto')
                )
                conn.execute(
                    "INSERT OR REPLACE INTO configuracion (clave, valor, tipo) VALUES (?, ?, ?)",
                    ('cocina_web_intervalo', str(intervalo), 'entero')
                )
                log_auditoria(conn, 'configuracion', 0, 'UPDATE',
                              self.usuario['usuario'], "Configuracion Cocina Web actualizada")
            messagebox.showinfo("Exito", "Configuracion de Cocina Web guardada.")
        except Exception as e:
            messagebox.showerror("Error", f"Error al guardar: {str(e)}")

    def _guardar_ducklab(self):
        """Guarda la conexion con el portal Ducklab (URL + API key)."""
        url = self.entry_ducklab_url.get().strip()
        key = self.entry_ducklab_key.get().strip()
        try:
            with conexion_segura() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO configuracion (clave, valor, tipo) VALUES (?, ?, ?)",
                    ('ducklab_telemetry_url', url, 'texto')
                )
                conn.execute(
                    "INSERT OR REPLACE INTO configuracion (clave, valor, tipo) VALUES (?, ?, ?)",
                    ('ducklab_api_key', key, 'texto')
                )
                log_auditoria(conn, 'configuracion', 0, 'UPDATE',
                              self.usuario['usuario'], "Conexion Ducklab actualizada")
            if url and key:
                messagebox.showinfo("Exito", "Conexion con Ducklab guardada.\n\nReinicia el sistema para que tome efecto (licencia, telemetria y respaldo en la nube).")
            else:
                messagebox.showinfo("Guardado", "Conexion con Ducklab desactivada (campos vacios).")
        except Exception as e:
            messagebox.showerror("Error", f"Error al guardar: {str(e)}")

    def _crear_backup(self):
        """Crea un hot-backup de la BD usando sqlite3.backup() (seguro con WAL activo)."""
        try:
            db_path = get_db_path()
            backup_dir = os.path.join(os.path.dirname(db_path), 'backups')
            os.makedirs(backup_dir, exist_ok=True)

            fecha = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = os.path.join(backup_dir, f"pocitos_azufrados_backup_{fecha}.db")

            src = sqlite3.connect(db_path)
            dst = sqlite3.connect(backup_path)
            src.backup(dst)
            src.close()
            dst.close()

            with conexion_segura() as conn:
                log_auditoria(conn, 'sistema', 0, 'BACKUP',
                              self.usuario['usuario'], f"Backup creado: {backup_path}")

            messagebox.showinfo("Backup creado",
                                f"Backup guardado exitosamente:\n{backup_path}")

        except Exception as e:
            messagebox.showerror("Error", f"Error al crear backup: {str(e)}")

    def _verificar_backup(self):
        """Verifica la integridad de un archivo de backup y muestra sus estadísticas
        sin tocar la base de datos de producción."""
        archivo = filedialog.askopenfilename(
            title="Seleccionar Backup para Verificar",
            filetypes=[("Base de Datos SQLite", "*.db"), ("Todos", "*.*")]
        )
        if not archivo:
            return

        TABLAS_REQUERIDAS = {
            'ventas', 'venta_detalle', 'usuarios', 'productos',
            'caja_diaria', 'configuracion', 'auditoria',
        }

        errores = []
        stats = {}
        try:
            conn_b = sqlite3.connect(f"file:{archivo}?mode=ro", uri=True)
            conn_b.row_factory = sqlite3.Row

            # PRAGMA integrity_check
            resultado = conn_b.execute("PRAGMA integrity_check").fetchone()[0]
            stats['integridad'] = resultado  # 'ok' si está bien

            # Verificar tablas requeridas
            tablas_presentes = {
                r[0] for r in conn_b.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            faltantes = TABLAS_REQUERIDAS - tablas_presentes
            if faltantes:
                errores.append(f"Tablas faltantes: {', '.join(sorted(faltantes))}")

            # Estadísticas básicas
            for tabla, col_fecha in [
                ('ventas',    'fecha_creacion'),
                ('productos', None),
                ('usuarios',  None),
            ]:
                if tabla not in _TABLAS_PERMITIDAS:
                    raise ValueError(f"Tabla no permitida: {tabla}")
                if col_fecha is not None and col_fecha not in _COLUMNAS_FECHA_PERMITIDAS:
                    raise ValueError(f"Columna no permitida: {col_fecha}")
                if tabla in tablas_presentes:
                    n = conn_b.execute(f"SELECT COUNT(*) FROM {tabla}").fetchone()[0]
                    stats[f'n_{tabla}'] = n
                    if col_fecha:
                        ultima = conn_b.execute(
                            f"SELECT MAX({col_fecha}) FROM {tabla}"
                        ).fetchone()[0]
                        stats[f'ultima_{tabla}'] = str(ultima)[:16] if ultima else 'Sin registros'

            # Schema version
            sv = conn_b.execute(
                "SELECT valor FROM configuracion WHERE clave='schema_version'"
            ).fetchone()
            stats['schema_version'] = sv[0] if sv else '?'

            conn_b.close()

        except sqlite3.DatabaseError as e:
            errores.append(f"Archivo SQLite invalido o corrupto: {e}")
        except Exception as e:
            errores.append(f"Error al leer el backup: {e}")

        # Comparar con BD actual para mostrar diferencias
        try:
            with conexion_segura() as conn_act:
                stats['actual_ventas'] = conn_act.execute(
                    "SELECT COUNT(*) FROM ventas").fetchone()[0]
                stats['actual_usuarios'] = conn_act.execute(
                    "SELECT COUNT(*) FROM usuarios").fetchone()[0]
        except Exception:
            pass

        # Mostrar resultado en diálogo
        dlg = tk.Toplevel(self.parent)
        dlg.title("Verificacion de Backup")
        dlg.geometry("480x440")
        dlg.transient(self.parent)
        dlg.grab_set()
        dlg.configure(bg=COLORES['fondo_card'])

        f = tk.Frame(dlg, bg=COLORES['fondo_card'], padx=22, pady=16)
        f.pack(fill='both', expand=True)

        # Color del encabezado según resultado
        valido = not errores and stats.get('integridad') == 'ok'
        color_hdr = COLORES['primario'] if valido else '#C62828'
        estado_txt = "BACKUP VALIDO — LISTO PARA RESTAURAR" if valido else "BACKUP CON PROBLEMAS"

        hdr = tk.Frame(f, bg=color_hdr)
        hdr.pack(fill='x', pady=(0, 14))
        tk.Label(hdr, text=estado_txt,
                 font=FUENTES['encabezado'], fg=COLORES['texto_claro'],
                 bg=color_hdr).pack(pady=8)

        # Archivo verificado
        tk.Label(f, text=f"Archivo: {os.path.basename(archivo)}",
                 font=FUENTES['normal_bold'], fg=COLORES['texto'],
                 bg=COLORES['fondo_card']).pack(anchor='w')
        tam_kb = os.path.getsize(archivo) // 1024
        tk.Label(f, text=f"Tamanio: {tam_kb} KB",
                 font=FUENTES['normal'], fg=COLORES['texto_secundario'],
                 bg=COLORES['fondo_card']).pack(anchor='w', pady=(0, 10))

        tk.Frame(f, bg=COLORES['borde'], height=1).pack(fill='x', pady=(0, 10))

        # Estadísticas
        filas = [
            ("Integridad SQLite:", stats.get('integridad', '?')),
            ("Schema version:", stats.get('schema_version', '?')),
            ("Ventas en backup:", str(stats.get('n_ventas', '?'))),
            ("  ultima venta:", stats.get('ultima_ventas', '-')),
            ("Productos en backup:", str(stats.get('n_productos', '?'))),
            ("Usuarios en backup:", str(stats.get('n_usuarios', '?'))),
        ]
        if 'actual_ventas' in stats:
            filas.append(("Ventas en BD actual:", str(stats['actual_ventas'])))
        if 'actual_usuarios' in stats:
            filas.append(("Usuarios en BD actual:", str(stats['actual_usuarios'])))

        for lbl, val in filas:
            row = tk.Frame(f, bg=COLORES['fondo_card'])
            row.pack(fill='x', pady=1)
            tk.Label(row, text=lbl, font=FUENTES['normal'],
                     fg=COLORES['texto'], bg=COLORES['fondo_card'],
                     width=26, anchor='w').pack(side='left')
            color_val = COLORES['primario'] if 'ok' in str(val).lower() or val.isdigit() else COLORES['texto']
            tk.Label(row, text=val, font=FUENTES['normal_bold'],
                     fg=color_val, bg=COLORES['fondo_card']).pack(side='left')

        # Errores si los hay
        if errores:
            tk.Frame(f, bg='#C62828', height=1).pack(fill='x', pady=(10, 6))
            for err in errores:
                tk.Label(f, text=f"• {err}", font=FUENTES['normal'],
                         fg='#C62828', bg=COLORES['fondo_card'],
                         wraplength=420, justify='left').pack(anchor='w')

        tk.Frame(f, bg=COLORES['borde'], height=1).pack(fill='x', pady=(12, 8))
        crear_boton(f, "Cerrar", dlg.destroy, tipo='secundario').pack(anchor='e')

    def _restaurar_backup(self):
        """Restaura desde un backup. Crea un safety-backup antes de sobrescribir."""
        archivo = filedialog.askopenfilename(
            title="Seleccionar Backup para Restaurar",
            filetypes=[("Base de Datos SQLite", "*.db"), ("Todos", "*.*")]
        )
        if not archivo:
            return

        # Verificar integridad antes de restaurar
        try:
            conn_b = sqlite3.connect(f"file:{archivo}?mode=ro", uri=True)
            resultado = conn_b.execute("PRAGMA integrity_check").fetchone()[0]
            conn_b.close()
            if resultado != 'ok':
                messagebox.showerror("Backup invalido",
                                     f"El archivo seleccionado no pasa la verificacion de integridad.\n"
                                     f"Resultado: {resultado}\n\nSeleccione un backup valido.")
                return
        except Exception as e:
            messagebox.showerror("Backup invalido",
                                 f"No se pudo abrir el archivo como base de datos SQLite:\n{e}")
            return

        if not messagebox.askyesno(
            "Confirmar Restauracion",
            f"Se va a restaurar desde:\n{os.path.basename(archivo)}\n\n"
            "Antes de restaurar se creara un safety-backup de la BD actual.\n\n"
            "La aplicacion debe reiniciarse despues.\n\n"
            "¿Continuar?"
        ):
            return

        try:
            db_path = get_db_path()

            # Safety-backup de la BD actual antes de sobrescribir
            backup_dir = os.path.join(os.path.dirname(db_path), 'backups')
            os.makedirs(backup_dir, exist_ok=True)
            ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            safety_path = os.path.join(backup_dir, f"safety_pre_restauracion_{ts}.db")
            src = sqlite3.connect(db_path)
            dst = sqlite3.connect(safety_path)
            src.backup(dst)
            src.close()
            dst.close()

            # Restaurar: copiar el backup sobre la BD de producción
            shutil.copy2(archivo, db_path)

            messagebox.showinfo(
                "Restauracion exitosa",
                f"Base de datos restaurada correctamente.\n\n"
                f"Safety-backup guardado en:\n{safety_path}\n\n"
                "Reinicie la aplicacion para continuar."
            )

        except Exception as e:
            messagebox.showerror("Error al restaurar", str(e))

    def _limpiar_logs(self):
        """Elimina registros de auditoría y archivos de log con más de 90 días"""
        if not messagebox.askyesno(
          "Limpiar Logs",
          "Se eliminarán registros de auditoría y archivos de log con más de 90 días.\n\n¿Continuar?"
        ):
            return
        try:
            with conexion_segura() as conn:
                deleted_bd = conn.execute(
                  "DELETE FROM auditoria WHERE fecha < datetime('now', '-90 days', 'localtime')"
                ).rowcount
                log_auditoria(conn, 'sistema', 0, 'DELETE',
                             self.usuario['usuario'],
                             f"Limpieza de logs: {deleted_bd} registros eliminados")

            # Limpiar archivos .log antiguos
            log_dir = os.path.join(BASE_DIR, 'logs')
            deleted_files = 0
            if os.path.exists(log_dir):
                limite = datetime.datetime.now() - datetime.timedelta(days=90)
                for fname in os.listdir(log_dir):
                    ruta = os.path.join(log_dir, fname)
                    if os.path.isfile(ruta):
                        mtime = datetime.datetime.fromtimestamp(os.path.getmtime(ruta))
                        if mtime < limite:
                            os.remove(ruta)
                            deleted_files += 1

            messagebox.showinfo(
              " Limpiar Logs",
                f"Registros de auditoría eliminados: {deleted_bd}\n"
                f"Archivos de log eliminados: {deleted_files}"
            )
        except Exception as e:
            messagebox.showerror("Error", f"Error al limpiar logs: {str(e)}")

    def _info_sistema(self):
        """Muestra información del sistema"""
        try:
            db_path = get_db_path()
            db_size = os.path.getsize(db_path) / (1024 * 1024)  # MB

            with conexion_segura() as conn:
                version = "1.0"
                usuarios = conn.execute("SELECT COUNT(*) as total FROM usuarios").fetchone()
                productos = conn.execute("SELECT COUNT(*) as total FROM productos").fetchone()
                ventas = conn.execute("SELECT COUNT(*) as total FROM ventas").fetchone()

            info = f"""
INFORMACIÓN DEL SISTEMA

Versión: {version}
Fecha: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

BASE DE DATOS
Ruta: {db_path}
Tamaño: {db_size:.2f} MB

ESTADÍSTICAS
Usuarios: {usuarios['total']}
Productos: {productos['total']}
Ventas: {ventas['total']}

Sistema: Club Los Pocitos Azufrados
Tocaima, Cundinamarca
          """

            messagebox.showinfo("Información del Sistema", info)

        except Exception as e:
            messagebox.showerror("Error", f"Error: {str(e)}")

    def _limpiar_datos_operacion(self):
        """Borra todos los datos de operacion (ventas, caja, movimientos, etc.)
        conservando usuarios, productos, categorias y configuracion."""
        from models.validaciones import verificar_pin_admin

        # Paso 1: PIN de administrador
        dlg = tk.Toplevel(self.parent.winfo_toplevel())
        dlg.title("Limpiar Datos de Operacion")
        dlg.resizable(False, False)
        dlg.grab_set()
        dlg.configure(bg=COLORES['fondo_card'])
        w, h = 420, 300
        dlg.geometry(f"{w}x{h}+{(dlg.winfo_screenwidth()-w)//2}+{(dlg.winfo_screenheight()-h)//2}")

        tk.Frame(dlg, bg=COLORES['error'], height=4).pack(fill='x')
        f = tk.Frame(dlg, bg=COLORES['fondo_card'], padx=24, pady=20)
        f.pack(fill='both', expand=True)

        tk.Label(f, text="ADVERTENCIA", font=FUENTES['encabezado'],
                 fg=COLORES['error'], bg=COLORES['fondo_card']).pack(anchor='w')
        tk.Label(f,
                 text="Esta accion borra PERMANENTEMENTE:\n"
                      "  - Ventas e historial\n"
                      "  - Registros de caja\n"
                      "  - Movimientos de inventario\n"
                      "  - Boletas, pedidos, ordenes de cocina\n"
                      "  - Gastos y auditoria\n\n"
                      "Se conservan: usuarios, productos, categorias y configuracion.",
                 font=FUENTES['pequena'], fg=COLORES['texto'],
                 bg=COLORES['fondo_card'], justify='left').pack(anchor='w', pady=(6, 12))

        tk.Label(f, text="PIN de administrador:", font=FUENTES['normal'],
                 fg=COLORES['texto'], bg=COLORES['fondo_card']).pack(anchor='w')
        entry_pin = tk.Entry(f, font=FUENTES['normal'], show='*', width=12,
                             relief='solid', bd=1,
                             bg=COLORES['fondo_input'], fg=COLORES['texto'])
        entry_pin.pack(anchor='w', ipady=4, pady=(2, 10))
        entry_pin.focus_set()

        def _ejecutar():
            pin = entry_pin.get().strip()
            valido, _ = verificar_pin_admin(pin)
            if not valido:
                messagebox.showerror("PIN incorrecto",
                                     "PIN de administrador incorrecto.", parent=dlg)
                return
            if not messagebox.askyesno(
                "Confirmar limpieza",
                "Esta accion es IRREVERSIBLE.\n\n"
                "¿Está seguro de borrar todos los datos de operacion?",
                parent=dlg
            ):
                return
            dlg.destroy()
            try:
                from database.connection import transaccion_atomica
                with transaccion_atomica() as conn:
                    tablas = [
                        'facturas_electronicas', 'pagos', 'venta_detalle', 'ventas',
                        'movimientos_caja', 'caja_diaria',
                        'movimientos_inventario',
                        'ordenes_cocina', 'reserva_checklist', 'reservas_almuerzo',
                        'boletas_entrada',
                        'gastos',
                        'auditoria', 'sesiones',
                        'tareas_preproduccion',
                    ]
                    for tabla in tablas:
                        if tabla not in _TABLAS_PERMITIDAS:
                            raise ValueError(f"Tabla no permitida: {tabla}")
                        try:
                            conn.execute(f"DELETE FROM {tabla}")
                        except Exception:
                            pass
                    # Reiniciar series de facturacion al inicio
                    conn.execute("UPDATE series_facturacion SET numero_actual = 0")
                messagebox.showinfo(
                    "Limpieza completada",
                    "Los datos operativos han sido eliminados.\nUsuarios, productos y configuracion se mantienen intactos."
                )
                self._cargar_config()
            except Exception as e:
                messagebox.showerror("Error", f"Error al limpiar datos: {e}")

    def _cargar_config(self):
        """Alias de _cargar_configuracion para recargar tras cambios."""
        self._cargar_configuracion()

    def detener(self):
        try:
            for c in self._canvas_list:
                c.unbind_all('<MouseWheel>')
                c.unbind_all('<Button-4>')
                c.unbind_all('<Button-5>')
        except Exception:
            pass