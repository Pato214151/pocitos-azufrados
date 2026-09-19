"""
Dashboard Cajero - Club Los Pocitos Azufrados
Interfaz simplificada para cajeros — sidebar doble + módulos operativos
"""

import tkinter as tk
from tkinter import ttk, messagebox
import os, sys, datetime, time, logging

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from utils.tema_corporativo import COLORES, FUENTES, SCALE, crear_boton, format_money
from database.connection import conexion_segura


class DashboardCajero:
    """Ventana principal del cajero: solo los módulos operativos del turno."""
    def __init__(self, root, usuario):
        self.root = root
        self.usuario = usuario
        self.modulo_actual = None
        self._instancia_modulo = None
        self._icon_btns = {}   # key -> (btn_icon, active_bar)
        self._text_btns = {}   # key -> btn_text
        self._after_hora_id = None

        # Limpiar widgets del login antes de dibujar el dashboard
        for w in self.root.winfo_children():
            try:
                w.destroy()
            except Exception:
                pass
        self.root.deiconify()

        self.root.title(
            f"Club Los Pocitos Azufrados - {usuario['nombre_completo']} ({usuario['rol']})"
        )
        self.root.configure(bg='white')
        try:
            self.root.state('zoomed')
        except Exception:
            w = max(900, int(1400 * SCALE))
            h = max(600, int(900 * SCALE))
            self.root.geometry(f"{w}x{h}")

        self.root.minsize(max(900, int(900 * SCALE)), max(600, int(600 * SCALE)))

        # Auto-bloqueo de pantalla por inactividad
        self._ultimo_evento = time.time()
        self._bloqueo_activo = False
        self._after_bloqueo_id = None

        def _tk_error_handler(exc_type, exc_value, exc_tb):
            import traceback, logging
            msg = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
            logging.getLogger("pocitos").error(f"Error en callback Tkinter:\n{msg}")
            try:
                for w in self.content_frame.winfo_children():
                    w.destroy()
                tk.Label(self.content_frame,
                         text=f"Error:\n{exc_value}",
                         font=FUENTES['normal'], fg=COLORES['error'],
                         bg=COLORES['fondo']).pack(pady=50)
            except Exception:
                pass
        self.root.report_callback_exception = _tk_error_handler

        self._crear_interfaz()
        self._cargar_modulo('bar')

        self.root.bind_all('<Motion>', self._registrar_actividad)
        self.root.bind_all('<KeyPress>', self._registrar_actividad)
        self.root.bind_all('<Button>', self._registrar_actividad)
        self._programar_verificacion_bloqueo()

    # ==============================================================
    #  ESTRUCTURA PRINCIPAL
    # ==============================================================

    def _crear_interfaz(self):
        """Header blanco + sidebar doble (iconos oscuro + texto blanco) + contenido"""

        # ========== HEADER (blanco, 64px) ==========
        header = tk.Frame(self.root, bg=COLORES['fondo_card'], height=64)
        header.pack(fill='x', side='top')
        header.pack_propagate(False)

        # Logo "P" circular
        tk.Label(
            header,
            text="P",
            font=('Segoe UI', 16, 'bold'),
            fg=COLORES['texto_claro'],
            bg=COLORES['primario'],
            width=3, height=1
        ).pack(side='left', padx=(16, 8), pady=12)

        tk.Label(
            header,
            text="Los Pocitos Azufrados",
            font=('Segoe UI', 13, 'bold'),
            fg=COLORES['texto'],
            bg=COLORES['fondo_card']
        ).pack(side='left', padx=(0, 20))

        # Separador vertical
        tk.Frame(header, bg=COLORES['borde'], width=1).pack(
            side='left', fill='y', pady=14)

        # Etiqueta del módulo activo (dinámica)
        self.lbl_modulo_header = tk.Label(
            header,
            text="Restaurante",
            font=FUENTES['encabezado'],
            fg=COLORES['primario'],
            bg=COLORES['fondo_card']
        )
        self.lbl_modulo_header.pack(side='left', padx=20)

        # Zona derecha: hora en vivo + nombre de usuario
        right = tk.Frame(header, bg=COLORES['fondo_card'])
        right.pack(side='right', padx=16)

        self.lbl_hora = tk.Label(
            right,
            text="",
            font=FUENTES['normal_bold'],
            fg=COLORES['texto_secundario'],
            bg=COLORES['fondo_card']
        )
        self.lbl_hora.pack(side='left', padx=(0, 14))
        self._actualizar_hora()

        tk.Label(
            right,
            text=self.usuario['nombre_completo'][0].upper(),
            font=('Segoe UI', 13, 'bold'),
            fg=COLORES['texto_claro'],
            bg=COLORES['agua'],
            width=3, height=1
        ).pack(side='left', padx=(0, 8))

        tk.Label(
            right,
            text=self.usuario['nombre_completo'],
            font=FUENTES['normal_bold'],
            fg=COLORES['texto'],
            bg=COLORES['fondo_card']
        ).pack(side='left')

        # Línea de acento verde ácido
        tk.Frame(self.root, bg=COLORES['acento'], height=2).pack(fill='x')

        # ========== CUERPO ==========
        body = tk.Frame(self.root, bg=COLORES['fondo'])
        body.pack(fill='both', expand=True)

        # ========== SIDEBAR DOBLE ==========
        self._construir_sidebar(body)

        # ========== ÁREA DE CONTENIDO ==========
        self.content_frame = tk.Frame(body, bg=COLORES['fondo'])
        self.content_frame.pack(side='left', fill='both', expand=True)

    def _construir_sidebar(self, body):
        """Sidebar de dos columnas: iconos (56px, oscuro) + texto (168px, blanco)."""
        sidebar_wrap = tk.Frame(body, bg=COLORES['fondo_card'])
        sidebar_wrap.pack(fill='y', side='left')
        tk.Frame(body, bg=COLORES['borde'], width=1).pack(fill='y', side='left')

        opciones = [
            ("\u2615", 'bar',          "Restaurante"),
            ("\u0024", 'caja',         "Caja"),
            ("\u270d", 'pedidos',      "Pedidos"),
            ("\u229e", 'cuentas',      "Cuentas Abiertas"),
            ("\u2668", 'cocina',       "Cocina"),
            ("\u21ba", 'historial',    "Historial"),
            ("\u2796", 'gastos',       "Gastos"),
            ("\u2261", 'inventario',   "Inventario"),
            ("\u26a0", 'contingencia',    "Contingencia"),
            ("\u25a6", 'proveedores',     "Proveedores"),
            ("\u26d4", 'reporte_errores', "Reporte Errores"),
        ]

        for icono, key, texto in opciones:
            row = tk.Frame(sidebar_wrap, bg=COLORES['fondo_card'])
            row.pack(fill='x')

            # Celda del icono (56px, verde oscuro)
            icon_cell = tk.Frame(row, bg=COLORES['fondo_sidebar'], width=56)
            icon_cell.pack(side='left', fill='y')
            icon_cell.pack_propagate(False)

            btn_icon = tk.Button(
                icon_cell,
                text=icono,
                font=('Segoe UI Symbol', 14),
                fg=COLORES['texto_sidebar'],
                bg=COLORES['fondo_sidebar'],
                relief='flat', bd=0,
                cursor='hand2',
                padx=0, pady=12,
                activeforeground=COLORES['acento'],
                activebackground=COLORES['primario'],
                command=lambda k=key: self._cargar_modulo(k)
            )
            btn_icon.pack(fill='both', expand=True)

            # Barra indicadora activa (3px)
            active_bar = tk.Frame(row, bg=COLORES['fondo_card'], width=3)
            active_bar.pack(side='left', fill='y')

            # Botón de texto
            btn_text = tk.Button(
                row,
                text=texto,
                font=FUENTES['normal'],
                fg=COLORES['texto_secundario'],
                bg=COLORES['fondo_card'],
                relief='flat', bd=0,
                cursor='hand2',
                anchor='w',
                padx=10, pady=12,
                activeforeground=COLORES['texto'],
                activebackground=COLORES['acento_claro'],
                command=lambda k=key: self._cargar_modulo(k)
            )
            btn_text.pack(side='left', fill='both', expand=True)

            self._icon_btns[key] = (btn_icon, active_bar)
            self._text_btns[key] = btn_text

            # Hover
            def _bind_hover(bi, bt, k):
                def on_enter(e):
                    if self.modulo_actual != k:
                        bi.config(bg=COLORES['primario'], fg=COLORES['acento'])
                        bt.config(bg=COLORES['acento_claro'], fg=COLORES['texto'])
                def on_leave(e):
                    if self.modulo_actual != k:
                        bi.config(bg=COLORES['fondo_sidebar'], fg=COLORES['texto_sidebar'])
                        bt.config(bg=COLORES['fondo_card'], fg=COLORES['texto_secundario'])
                for w in (bi, bt):
                    w.bind('<Enter>', on_enter)
                    w.bind('<Leave>', on_leave)
            _bind_hover(btn_icon, btn_text, key)

        # Spacer + logout al fondo
        tk.Frame(sidebar_wrap, bg=COLORES['fondo_card']).pack(fill='both', expand=True)

        logout_row = tk.Frame(sidebar_wrap, bg=COLORES['fondo_card'])
        logout_row.pack(fill='x')
        tk.Frame(logout_row, bg=COLORES['fondo_sidebar'], width=56).pack(side='left', fill='y')
        logout_right = tk.Frame(logout_row, bg=COLORES['fondo_card'])
        logout_right.pack(side='left', fill='both', expand=True)
        tk.Frame(logout_right, bg=COLORES['borde'], height=1).pack(fill='x', padx=8)
        tk.Button(
            logout_right,
            text="Cerrar Sesion",
            font=FUENTES['normal'],
            fg=COLORES['error'],
            bg=COLORES['fondo_card'],
            relief='flat', anchor='w',
            cursor='hand2', bd=0,
            padx=10, pady=10,
            activebackground=COLORES['gris_100'],
            activeforeground=COLORES['error'],
            command=self._salir
        ).pack(fill='x', pady=(0, 10))

    def _marcar_menu(self, key, texto):
        """Actualiza el estado visual del ítem activo."""
        self.modulo_actual = key

        if hasattr(self, 'lbl_modulo_header'):
            try:
                self.lbl_modulo_header.config(text=texto)
            except Exception:
                pass

        for k in self._icon_btns:
            btn_icon, active_bar = self._icon_btns[k]
            btn_text = self._text_btns[k]
            if k == key:
                btn_icon.config(bg=COLORES['primario'], fg=COLORES['acento'])
                active_bar.config(bg=COLORES['acento'])
                btn_text.config(
                    bg=COLORES['acento_claro'],
                    fg=COLORES['texto'],
                    font=FUENTES['normal_bold']
                )
            else:
                btn_icon.config(bg=COLORES['fondo_sidebar'], fg=COLORES['texto_sidebar'])
                active_bar.config(bg=COLORES['fondo_card'])
                btn_text.config(
                    bg=COLORES['fondo_card'],
                    fg=COLORES['texto_secundario'],
                    font=FUENTES['normal']
                )

    # ==============================================================
    #  CARGA DE MÓDULOS
    # ==============================================================

    _TEXTOS = {
        'bar': 'Restaurante', 'caja': 'Caja',
        'pedidos': 'Pedidos', 'cocina': 'Cocina',
        'cuentas': 'Cuentas Abiertas', 'historial': 'Historial',
        'gastos': 'Gastos', 'inventario': 'Inventario', 'contingencia': 'Contingencia',
        'proveedores': 'Proveedores', 'reporte_errores': 'Reporte Errores',
    }

    def _cargar_modulo(self, nombre_modulo):
        """Carga un módulo en el área de contenido."""
        if self._instancia_modulo is not None:
            if hasattr(self._instancia_modulo, 'detener'):
                try:
                    self._instancia_modulo.detener()
                except Exception:
                    pass
            self._instancia_modulo = None

        # Limpiar bindings globales de scroll si los había
        try:
            self.root.unbind_all("<MouseWheel>")
            self.root.unbind_all("<Button-4>")
            self.root.unbind_all("<Button-5>")
        except Exception:
            pass

        for widget in self.content_frame.winfo_children():
            widget.destroy()

        self._marcar_menu(nombre_modulo, self._TEXTOS.get(nombre_modulo, nombre_modulo))

        try:
            if nombre_modulo == 'bar':
                from modules.pos_module import POSModule
                self._instancia_modulo = POSModule(
                    self.content_frame, self.usuario,
                    callback_ir_caja=lambda: self._cargar_modulo('caja')
                )
            elif nombre_modulo == 'caja':
                from modules.caja_module import CajaModule
                self._instancia_modulo = CajaModule(self.content_frame, self.usuario,
                                                     callback_ir_bar=lambda: self._cargar_modulo('bar'))
            elif nombre_modulo == 'pedidos':
                from modules.pedidos_module import PedidosModule
                self._instancia_modulo = PedidosModule(self.content_frame, self.usuario)
            elif nombre_modulo == 'cuentas':
                from modules.cuentas_abiertas_module import CuentasAbiertasModule
                self._instancia_modulo = CuentasAbiertasModule(self.content_frame, self.usuario)
            elif nombre_modulo == 'cocina':
                from modules.cocina_module import CocinaModule
                self._instancia_modulo = CocinaModule(self.content_frame, self.usuario)
            elif nombre_modulo == 'historial':
                from modules.historial_ventas_module import HistorialVentasModule
                self._instancia_modulo = HistorialVentasModule(self.content_frame, self.usuario)
            elif nombre_modulo == 'gastos':
                from modules.gastos_module import GastosModule
                self._instancia_modulo = GastosModule(self.content_frame, self.usuario)
            elif nombre_modulo == 'inventario':
                from modules.inventario_module import InventarioModule
                self._instancia_modulo = InventarioModule(self.content_frame, self.usuario)
            elif nombre_modulo == 'contingencia':
                from modules.contingencia_module import ContingenciaModule
                self._instancia_modulo = ContingenciaModule(self.content_frame, self.usuario)
            elif nombre_modulo == 'proveedores':
                from modules.proveedores_module import ProveedoresModule
                self._instancia_modulo = ProveedoresModule(self.content_frame, self.usuario)
            elif nombre_modulo == 'reporte_errores':
                from modules.reporte_errores_module import ReporteErroresModule
                self._instancia_modulo = ReporteErroresModule(self.content_frame, self.usuario)
        except Exception as e:
            import traceback, logging
            logging.getLogger("pocitos").error(
                f"Error cargando modulo '{nombre_modulo}':\n{traceback.format_exc()}"
            )
            self._instancia_modulo = None
            tk.Label(
                self.content_frame,
                text=f"Error al cargar modulo:\n{str(e)}",
                font=FUENTES['normal'],
                fg=COLORES['error'],
                bg=COLORES['fondo']
            ).pack(padx=15, pady=20)

    # ==============================================================
    #  UTILIDADES
    # ==============================================================

    def _actualizar_hora(self):
        """Actualiza la hora en el header cada segundo."""
        try:
            if self.root.winfo_exists():
                self.lbl_hora.config(
                    text=datetime.datetime.now().strftime("%H:%M:%S")
                )
                self._after_hora_id = self.root.after(1000, self._actualizar_hora)
        except Exception:
            pass

    # ==============================================================
    #  AUTO-BLOQUEO DE PANTALLA
    # ==============================================================

    def _registrar_actividad(self, event=None):
        self._ultimo_evento = time.time()

    def _programar_verificacion_bloqueo(self):
        try:
            if self.root.winfo_exists():
                self._after_bloqueo_id = self.root.after(10000, self._verificar_inactividad)
        except Exception:
            pass

    def _verificar_inactividad(self):
        try:
            if not self.root.winfo_exists():
                return
        except Exception:
            return
        if not self._bloqueo_activo and time.time() - self._ultimo_evento >= 600:  # 10 minutos
            self._bloquear_pantalla()
        self._programar_verificacion_bloqueo()

    def _bloquear_pantalla(self):
        """Bloquea la pantalla tras un tiempo sin uso; se desbloquea con PIN."""
        if self._bloqueo_activo:
            return
        self._bloqueo_activo = True

        lock = tk.Toplevel(self.root)
        lock.title("Sistema Bloqueado")
        lock.configure(bg=COLORES['fondo_sidebar'])
        lock.attributes('-topmost', True)
        lock.grab_set()
        lock.protocol("WM_DELETE_WINDOW", lambda: None)
        try:
            lock.geometry(f"{self.root.winfo_width()}x{self.root.winfo_height()}"
                          f"+{self.root.winfo_x()}+{self.root.winfo_y()}")
        except Exception:
            lock.geometry("1000x700")

        center = tk.Frame(lock, bg=COLORES['fondo_sidebar'])
        center.place(relx=0.5, rely=0.5, anchor='center')

        tk.Label(center, text="Pantalla Bloqueada",
                 font=('Segoe UI', 28, 'bold'),
                 fg=COLORES['acento'], bg=COLORES['fondo_sidebar']).pack(pady=(0, 6))
        tk.Label(center, text=f"Usuario: {self.usuario['nombre_completo']}",
                 font=FUENTES['normal'],
                 fg=COLORES['texto_claro'], bg=COLORES['fondo_sidebar']).pack(pady=(0, 24))
        tk.Label(center, text="Ingrese su PIN o contrasena para continuar:",
                 font=FUENTES['normal'],
                 fg=COLORES['texto_claro'], bg=COLORES['fondo_sidebar']).pack(pady=(0, 8))

        entry_pin = tk.Entry(center, font=('Segoe UI', 20), show='*',
                             width=8, justify='center', relief='solid', bd=2)
        entry_pin.pack(pady=(0, 8))
        entry_pin.focus_set()

        lbl_err = tk.Label(center, text="", font=FUENTES['pequena'],
                           fg=COLORES['error'], bg=COLORES['fondo_sidebar'])
        lbl_err.pack(pady=(0, 12))

        def _verificar_pin(pin_ing):
            try:
                with conexion_segura() as conn:
                    row = conn.execute(
                        "SELECT pin, contrasena_hash FROM usuarios WHERE id_usuario = ? AND activo = 1",
                        (self.usuario['id_usuario'],)
                    ).fetchone()
                if not row:
                    return False
                # Si tiene PIN configurado, verificar contra él
                guardado_pin = row['pin']
                if guardado_pin:
                    if guardado_pin.startswith('$2'):
                        try:
                            import bcrypt
                            return bcrypt.checkpw(pin_ing.encode('utf-8'), guardado_pin.encode('utf-8'))
                        except Exception:
                            return False
                    import hmac
                    return hmac.compare_digest(guardado_pin, pin_ing)
                # Sin PIN: verificar contra la contraseña normal
                guardado_pw = row['contrasena_hash']
                if not guardado_pw:
                    return False
                if guardado_pw.startswith('$2'):
                    try:
                        import bcrypt
                        return bcrypt.checkpw(pin_ing.encode('utf-8'), guardado_pw.encode('utf-8'))
                    except Exception:
                        return False
                import hashlib, hmac
                return hmac.compare_digest(
                    guardado_pw,
                    hashlib.sha256(pin_ing.encode('utf-8')).hexdigest()
                )
            except Exception:
                return False

        _intentos_bloqueo = [0]
        _MAX_INTENTOS_BLOQUEO = 5

        def _desbloquear():
            pin_ing = entry_pin.get().strip()
            if _verificar_pin(pin_ing):
                self._bloqueo_activo = False
                self._ultimo_evento = time.time()
                lock.destroy()
            else:
                _intentos_bloqueo[0] += 1
                restantes = _MAX_INTENTOS_BLOQUEO - _intentos_bloqueo[0]
                if restantes <= 0:
                    logging.getLogger("pocitos").warning(
                        "Screen-lock: 5 intentos fallidos para usuario %s — cerrando app",
                        self.usuario.get('usuario', '?')
                    )
                    self.root.destroy()
                    return
                lbl_err.config(text=f"PIN incorrecto. Intentos restantes: {restantes}")
                entry_pin.delete(0, tk.END)
                entry_pin.focus_set()

        def _cerrar_app():
            if messagebox.askyesno("Cerrar aplicacion",
                                   "Si no recuerda el PIN puede cerrar la aplicacion.\n"
                                   "¿Desea salir?",
                                   parent=lock):
                self.root.destroy()

        crear_boton(center, "Desbloquear", _desbloquear, tipo='azufre').pack(fill='x', ipady=6, pady=(0, 6))
        crear_boton(center, "Cerrar aplicacion", _cerrar_app, tipo='error').pack(fill='x', ipady=4)
        entry_pin.bind('<Return>', lambda e: _desbloquear())

    def _cancelar_bloqueo_timer(self):
        if self._after_bloqueo_id:
            try:
                self.root.after_cancel(self._after_bloqueo_id)
            except Exception:
                pass
            self._after_bloqueo_id = None

    def _cerrar_sesion_db(self):
        id_sesion = self.usuario.get('id_sesion')
        if id_sesion:
            try:
                with conexion_segura() as conn:
                    conn.execute(
                        "UPDATE sesiones SET fecha_fin = datetime('now','localtime') "
                        "WHERE id_sesion = ?",
                        (id_sesion,)
                    )
            except Exception:
                pass

    def _salir(self):
        if messagebox.askyesno("Salir", "¿Desea cerrar la sesion?"):
            self._cancelar_bloqueo_timer()
            if self._after_hora_id:
                try:
                    self.root.after_cancel(self._after_hora_id)
                except Exception:
                    pass
                self._after_hora_id = None
            if self._instancia_modulo is not None and hasattr(self._instancia_modulo, 'detener'):
                try:
                    self._instancia_modulo.detener()
                except Exception:
                    pass
            self._cerrar_sesion_db()
            # Reusar root para volver al login sin nested mainloop
            try:
                for w in self.root.winfo_children():
                    try:
                        w.destroy()
                    except Exception:
                        pass
                from modules.login import LoginWindow
                LoginWindow(self.root)
            except Exception:
                try:
                    self.root.destroy()
                except Exception:
                    pass
