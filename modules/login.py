"""
Módulo de Login - Club Los Pocitos Azufrados
Pantalla de inicio de sesión - Tema Oscuro Azufre & Naturaleza
"""

import tkinter as tk
from tkinter import messagebox
import os
import sys
import datetime
import hashlib

try:
    import bcrypt
    BCRYPT_DISPONIBLE = True
except ImportError:
    BCRYPT_DISPONIBLE = False
    import logging
    logging.getLogger("pocitos").critical(
        "bcrypt NO está instalado. Las contraseñas se verificarán con SHA-256 (inseguro). "
        "Instale con: pip install bcrypt"
    )
    print(
        "[SEGURIDAD] bcrypt no está instalado. Login usando SHA-256. "
        "Ejecute: pip install bcrypt",
        file=sys.stderr
    )

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from database.connection import get_connection, get_db_path, conexion_segura, transaccion_atomica
from utils.tema_corporativo import COLORES, FUENTES, crear_boton


class LoginWindow:
    """Ventana de inicio de sesión (usuario + contraseña o PIN). Según el rol
    abre el dashboard de admin, cajero o contadora.
    """
    MAX_INTENTOS = 5
    TIEMPO_BLOQUEO = 1800  # segundos (30 minutos)

    def __init__(self, root=None):
        if root is not None:
            # Reusar root existente (al cerrar sesión desde el dashboard)
            self.root = root
            self.root.title("Club Los Pocitos Azufrados - Iniciar Sesión")
            self.root.configure(bg=COLORES['fondo'])
            self.root.resizable(False, False)
            ancho, alto = 480, 650
            x = (self.root.winfo_screenwidth() - ancho) // 2
            y = (self.root.winfo_screenheight() - alto) // 2
            self.root.geometry(f"{ancho}x{alto}+{x}+{y}")
            self.root.deiconify()
        else:
            self.root = tk.Tk()
            self.root.title("Club Los Pocitos Azufrados - Iniciar Sesión")
            self.root.configure(bg=COLORES['fondo'])
            ancho, alto = 480, 650
            x = (self.root.winfo_screenwidth() - ancho) // 2
            y = (self.root.winfo_screenheight() - alto) // 2
            self.root.geometry(f"{ancho}x{alto}+{x}+{y}")
            self.root.resizable(False, False)
            try:
                self.root.iconbitmap(os.path.join(BASE_DIR, "assets", "icon.ico"))
            except Exception:
                pass

        self.intentos = 0
        self.bloqueado = False
        self._after_countdown = None

        self._crear_interfaz()
        self.entry_usuario.focus_set()

        # Navegación por teclado
        self.entry_usuario.bind('<Return>', lambda e: self.entry_contrasena.focus_set())
        self.entry_contrasena.bind('<Return>', lambda e: self._login())
        self.root.bind('<Escape>', self._limpiar_formulario)

    def _crear_interfaz(self):
        """Construye la interfaz de login - Dark Theme"""
        # Contenedor principal oscuro
        main = tk.Frame(self.root, bg=COLORES['fondo'])
        main.pack(expand=True, fill='both', padx=40, pady=20)

        # Barra superior decorativa (gradiente simulado: verde  azufre)
        barra_top = tk.Frame(main, bg=COLORES['acento'], height=3)
        barra_top.pack(fill='x')

        # Card central (glass card oscura)
        card = tk.Frame(main, bg=COLORES['fondo_card'],
                       highlightbackground=COLORES['acento'], highlightthickness=2)
        card.pack(fill='both', expand=True, pady=(0, 0))

        inner = tk.Frame(card, bg=COLORES['fondo_card'], padx=30, pady=20)
        inner.pack(fill='both', expand=True)

        # Logo: iniciales del club
        tk.Label(inner, text="LPA", font=('Segoe UI', 42, 'bold'),
                 fg=COLORES['acento'], bg=COLORES['fondo_card']).pack(pady=(10, 5))

        # Título
        tk.Label(inner, text="Club Los Pocitos",
                 font=FUENTES['titulo'],
                 fg=COLORES['acento'], bg=COLORES['fondo_card']).pack()
        tk.Label(inner, text="Azufrados",
                 font=FUENTES['subtitulo'],
                 fg=COLORES['primario_claro'], bg=COLORES['fondo_card']).pack()
        tk.Label(inner, text="Tocaima, Cundinamarca",
                 font=FUENTES['pequena'],
                 fg=COLORES['texto_secundario'], bg=COLORES['fondo_card']).pack(pady=(2, 15))

        # Línea separadora sutil
        tk.Frame(inner, bg=COLORES['borde'], height=1).pack(fill='x', pady=5)

        # Campo Usuario
        tk.Label(inner, text="Usuario", font=FUENTES['normal_bold'],
                 fg=COLORES['texto'], bg=COLORES['fondo_card'], anchor='w').pack(fill='x', pady=(15, 4))
        self.entry_usuario = tk.Entry(
            inner, font=FUENTES['input'], relief='solid', bd=1,
            highlightthickness=2, highlightcolor=COLORES['acento'],
            highlightbackground=COLORES['borde'],
            bg=COLORES['fondo_input'], fg=COLORES['texto'],
            insertbackground=COLORES['acento'],
        )
        self.entry_usuario.pack(fill='x', ipady=8)

        # Campo Contraseña
        tk.Label(inner, text="Contraseña", font=FUENTES['normal_bold'],
                 fg=COLORES['texto'], bg=COLORES['fondo_card'], anchor='w').pack(fill='x', pady=(15, 4))

        frame_pass = tk.Frame(inner, bg=COLORES['fondo_card'])
        frame_pass.pack(fill='x')

        self.entry_contrasena = tk.Entry(
            frame_pass, font=FUENTES['input'], show='*', relief='solid', bd=1,
            highlightthickness=2, highlightcolor=COLORES['acento'],
            highlightbackground=COLORES['borde'],
            bg=COLORES['fondo_input'], fg=COLORES['texto'],
            insertbackground=COLORES['acento'],
        )
        self.entry_contrasena.pack(fill='x', ipady=8, side='left', expand=True)

        # Botón mostrar/ocultar contraseña — target mínimo 44×44px, fuera del tab order
        self.mostrar_pass = False
        self.btn_ojo = tk.Button(
            frame_pass, text="Ver", font=FUENTES['pequena'],
            bg=COLORES['fondo_card'], fg=COLORES['texto_secundario'],
            relief='flat', cursor='hand2', bd=0,
            activebackground=COLORES['fondo_hover'],
            activeforeground=COLORES['texto'],
            command=self._toggle_password,
            padx=10, pady=6, width=5,
            takefocus=0,
        )
        self.btn_ojo.pack(side='right', padx=(5, 0))

        # Mensaje de estado
        self.lbl_estado = tk.Label(
            inner, text="", font=FUENTES['pequena'],
            fg=COLORES['error'], bg=COLORES['fondo_card']
        )
        self.lbl_estado.pack(pady=(10, 0))

        # Botón Login (azufre prominente)
        self.btn_login = crear_boton(
            inner, "Iniciar Sesión", self._login, tipo='azufre'
        )
        self.btn_login.pack(fill='x', pady=(15, 5), ipady=4)

        # Enlace de login con PIN
        tk.Button(
            inner, text="Ingresar con PIN de 4 digitos",
            font=FUENTES['pequena'],
            fg=COLORES['texto_secundario'], bg=COLORES['fondo_card'],
            relief='flat', cursor='hand2', bd=0,
            activebackground=COLORES['fondo_card'],
            activeforeground=COLORES['primario'],
            command=self._login_pin_dialog,
        ).pack(pady=(8, 0))

        # Footer
        tk.Label(inner, text="v1.0.0 | Sistema POS Los Pocitos",
                 font=FUENTES['pequena'],
                 fg=COLORES['texto_deshabilitado'], bg=COLORES['fondo_card']).pack(side='bottom', pady=(15, 0))

    def _login_pin_dialog(self):
        """Abre un dialogo de login alternativo usando PIN de 4 digitos."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Ingresar con PIN")
        dialog.configure(bg=COLORES['fondo_card'])
        dialog.resizable(True, True)
        dialog.grab_set()

        w, h = 320, 250
        x = (self.root.winfo_screenwidth() - w) // 2
        y = (self.root.winfo_screenheight() - h) // 2
        dialog.geometry(f"{w}x{h}+{x}+{y}")

        tk.Frame(dialog, bg=COLORES['acento'], height=3).pack(fill='x')

        inner_d = tk.Frame(dialog, bg=COLORES['fondo_card'], padx=25, pady=20)
        inner_d.pack(fill='both', expand=True)

        tk.Label(inner_d, text="Acceso con PIN",
                 font=FUENTES['subtitulo'], fg=COLORES['texto'],
                 bg=COLORES['fondo_card']).pack(pady=(0, 12))

        tk.Label(inner_d, text="Usuario:", font=FUENTES['pequena'],
                 fg=COLORES['texto_secundario'], bg=COLORES['fondo_card'],
                 anchor='w').pack(fill='x')
        entry_usr = tk.Entry(inner_d, font=FUENTES['input'], relief='solid', bd=1)
        entry_usr.pack(fill='x', ipady=6, pady=(2, 8))
        entry_usr.insert(0, self.entry_usuario.get().strip())

        tk.Label(inner_d, text="PIN (4 digitos):", font=FUENTES['pequena'],
                 fg=COLORES['texto_secundario'], bg=COLORES['fondo_card'],
                 anchor='w').pack(fill='x')
        entry_pin = tk.Entry(inner_d, font=FUENTES['input'], show='*',
                             relief='solid', bd=1, width=10, justify='center')
        entry_pin.pack(ipady=6, pady=(2, 6))

        lbl_err = tk.Label(inner_d, text="", font=FUENTES['pequena'],
                           fg=COLORES['error'], bg=COLORES['fondo_card'])
        lbl_err.pack()

        _pin_intentos = {'n': 0}
        _PIN_MAX_INTENTOS = 5

        def _intentar_pin():
            if _pin_intentos['n'] >= _PIN_MAX_INTENTOS:
                lbl_err.config(text="Cuenta bloqueada 30 min por demasiados intentos.")
                return

            usuario_str = entry_usr.get().strip().lower()
            pin_str = entry_pin.get().strip()
            if not usuario_str or not pin_str:
                lbl_err.config(text="Ingrese usuario y PIN.")
                return
            if not pin_str.isdigit() or len(pin_str) != 4:
                lbl_err.config(text="El PIN debe ser exactamente 4 digitos.")
                return
            try:
                with conexion_segura() as conn:
                    row = conn.execute(
                        "SELECT id_usuario, usuario, nombre_completo, rol, pin, "
                        "bloqueado_hasta, intentos_fallidos "
                        "FROM usuarios WHERE usuario = ? AND activo = 1",
                        (usuario_str,)
                    ).fetchone()
                ok = False
                if row and row['pin']:
                    guardado = row['pin']
                    if guardado.startswith('$2'):
                        try:
                            ok = bcrypt.checkpw(pin_str.encode('utf-8'), guardado.encode('utf-8'))
                        except Exception:
                            ok = False
                    else:
                        # Fallback para PINs legados aún sin hashear (migración).
                        # Una vez que el admin actualice el PIN desde Usuarios, este path
                        # quedará sin efecto porque todos los nuevos PINs se guardan con bcrypt.
                        import hmac
                        ok = hmac.compare_digest(guardado, pin_str)
                if ok:
                    dialog.destroy()
                    self._login_exitoso(dict(row))
                else:
                    _pin_intentos['n'] += 1
                    restantes = _PIN_MAX_INTENTOS - _pin_intentos['n']
                    if restantes > 0:
                        lbl_err.config(text=f"PIN incorrecto. {restantes} intento(s) restantes.")
                    else:
                        # Bloquear la cuenta en BD igual que el flujo de contraseña
                        if row:
                            try:
                                import datetime as _dt
                                bloqueo = (_dt.datetime.now() +
                                           _dt.timedelta(minutes=30)).strftime('%Y-%m-%d %H:%M:%S')
                                with conexion_segura() as _c:
                                    _c.execute(
                                        "UPDATE usuarios SET bloqueado_hasta = ? "
                                        "WHERE id_usuario = ?",
                                        (bloqueo, row['id_usuario'])
                                    )
                            except Exception:
                                pass
                        lbl_err.config(text="Cuenta bloqueada 30 min por demasiados intentos.")
                    entry_pin.delete(0, tk.END)
                    entry_pin.focus_set()
            except Exception as e:
                lbl_err.config(text=f"Error: {str(e)[:40]}")

        crear_boton(inner_d, "Ingresar", _intentar_pin, tipo='azufre').pack(
            fill='x', ipady=4, pady=(8, 0))

        entry_usr.bind('<Return>', lambda e: entry_pin.focus_set())
        entry_pin.bind('<Return>', lambda e: _intentar_pin())
        dialog.bind('<Escape>', lambda e: dialog.destroy())

        if entry_usr.get():
            entry_pin.focus_set()
        else:
            entry_usr.focus_set()

        dialog.wait_window()

    def _toggle_password(self):
        """Muestra/oculta la contraseña"""
        self.mostrar_pass = not self.mostrar_pass
        self.entry_contrasena.config(show='' if self.mostrar_pass else '*')
        self.btn_ojo.config(text='Ocultar' if self.mostrar_pass else 'Ver')

    def _limpiar_formulario(self, event=None):
        """Limpia el formulario y devuelve el foco al campo usuario (Escape)"""
        try:
            self.entry_usuario.delete(0, tk.END)
            self.entry_contrasena.delete(0, tk.END)
            self.lbl_estado.config(text="")
            self.entry_usuario.focus_set()
        except Exception:
            pass

    def _login(self):
        """Procesa el intento de login"""
        if self.bloqueado:
            return

        usuario = self.entry_usuario.get().strip().lower()
        contrasena = self.entry_contrasena.get()

        if not usuario or not contrasena:
            self.lbl_estado.config(text="Ingrese usuario y contraseña")
            return

        # Feedback inmediato: deshabilitar mientras verifica bcrypt
        self.btn_login.config(state='disabled', text="Verificando...")
        self.lbl_estado.config(text="")
        self.root.update_idletasks()

        try:
            with conexion_segura() as conn:
                row = conn.execute(
                    "SELECT id_usuario, usuario, nombre_completo, rol, contrasena_hash, pin, "
                    "bloqueado_hasta, intentos_fallidos, ultimo_login, debe_cambiar_password "
                    "FROM usuarios WHERE usuario = ? AND activo = 1",
                    (usuario,)
                ).fetchone()

            if not row:
                self._login_fallido("Credenciales incorrectas")
                return

            # Verificar bloqueo temporal en BD
            if row['bloqueado_hasta']:
                bloqueado = datetime.datetime.strptime(row['bloqueado_hasta'], '%Y-%m-%d %H:%M:%S')
                if datetime.datetime.now() < bloqueado:
                    self.bloqueado = True
                    self.btn_login.config(state='disabled', text="Bloqueado")
                    self._iniciar_cuenta_regresiva(bloqueado)
                    return

            # Verificar contraseña
            hash_guardado = row['contrasena_hash']
            password_ok = False

            if hash_guardado.startswith('$2'):
                # Hash bcrypt moderno
                if not BCRYPT_DISPONIBLE:
                    # bcrypt no instalado — bloquear con mensaje visible; no fallback silencioso
                    import logging
                    logging.getLogger("pocitos").critical(
                        f"Intento de login de '{usuario}' bloqueado: bcrypt no está instalado "
                        "y la cuenta tiene hash bcrypt. Instale: pip install bcrypt"
                    )
                    self.lbl_estado.config(
                        text="Error de seguridad: bcrypt no instalado.\n"
                             "Ejecute: pip install bcrypt"
                    )
                    return
                password_ok = bcrypt.checkpw(
                    contrasena.encode('utf-8'),
                    hash_guardado.encode('utf-8')
                )
            else:
                # Hash SHA-256 legado — permitir login con advertencia visible
                import logging
                logging.getLogger("pocitos").warning(
                    f"Login de '{usuario}' usando SHA-256 (hash legado). "
                    "Regenere la contraseña desde Usuarios para migrar a bcrypt."
                )
                password_ok = (hashlib.sha256(contrasena.encode()).hexdigest() == hash_guardado)
                if password_ok:
                    # Mostrar advertencia visible al usuario luego de autenticar
                    self._advertencia_hash_legado = True

            if password_ok:
                self._login_exitoso(dict(row))
            else:
                self._login_fallido("Credenciales incorrectas", row['id_usuario'])

        except Exception as e:
            self.lbl_estado.config(text=f"Error: {str(e)[:50]}")
        finally:
            # Restaurar botón solo si no fue bloqueado por demasiados intentos
            if not self.bloqueado:
                try:
                    self.btn_login.config(state='normal', text="Iniciar Sesión")
                except Exception:
                    pass

    def _login_fallido(self, mensaje, id_usuario=None):
        """Maneja un intento fallido"""
        self.intentos += 1
        restantes = self.MAX_INTENTOS - self.intentos

        if id_usuario:
            with transaccion_atomica() as conn:
                conn.execute(
                    "UPDATE usuarios SET intentos_fallidos = intentos_fallidos + 1 WHERE id_usuario = ?",
                    (id_usuario,)
                )
                if restantes <= 0:
                    bloqueo = (datetime.datetime.now() +
                               datetime.timedelta(seconds=self.TIEMPO_BLOQUEO))
                    conn.execute(
                        "UPDATE usuarios SET bloqueado_hasta = ? WHERE id_usuario = ?",
                        (bloqueo.strftime('%Y-%m-%d %H:%M:%S'), id_usuario)
                    )

        if restantes <= 0:
            self.bloqueado = True
            self.btn_login.config(state='disabled', text="Bloqueado")
            desbloqueo = datetime.datetime.now() + datetime.timedelta(seconds=self.TIEMPO_BLOQUEO)
            self._iniciar_cuenta_regresiva(desbloqueo)
        else:
            self.lbl_estado.config(
                text=f"{mensaje} ({restantes} intentos restantes)"
            )
        self.entry_contrasena.delete(0, tk.END)
        self.entry_contrasena.focus_set()

    def _iniciar_cuenta_regresiva(self, hasta: datetime.datetime):
        """Muestra un contador regresivo en lbl_estado y desbloquea al llegar a 0."""
        if not self.root.winfo_exists():
            return
        restante = (hasta - datetime.datetime.now()).total_seconds()
        if restante <= 0:
            self._desbloquear()
            return
        mins = int(restante) // 60
        segs = int(restante) % 60
        self.lbl_estado.config(
            text=f"Demasiados intentos. Espere {mins:02d}:{segs:02d} min"
        )
        self._after_countdown = self.root.after(
            1000, lambda: self._iniciar_cuenta_regresiva(hasta)
        )

    def _desbloquear(self):
        """Desbloquea la cuenta después del tiempo de espera."""
        self.bloqueado = False
        self.intentos = 0
        if hasattr(self, '_after_countdown') and self._after_countdown:
            try:
                self.root.after_cancel(self._after_countdown)
            except Exception:
                pass
            self._after_countdown = None
        try:
            if self.root.winfo_exists():
                self.btn_login.config(state='normal', text="Iniciar Sesión")
                self.lbl_estado.config(text="Desbloqueado. Intente de nuevo.")
        except Exception:
            pass

    def _login_exitoso(self, usuario_data):
        """Login exitoso - verifica cambio de contraseña, registra sesión y abre dashboard."""
        with transaccion_atomica() as conn:
            conn.execute(
                "UPDATE usuarios SET ultimo_login = datetime('now','localtime'), "
                "intentos_fallidos = 0, bloqueado_hasta = NULL WHERE id_usuario = ?",
                (usuario_data['id_usuario'],)
            )

        # Advertir si la cuenta usó hash SHA-256 legado
        if getattr(self, '_advertencia_hash_legado', False):
            from tkinter import messagebox
            messagebox.showwarning(
                "Contraseña desactualizada",
                f"La cuenta '{usuario_data['usuario']}' usa un hash de contraseña legado (SHA-256).\n\n"
                "Para mayor seguridad, el administrador debe regenerar la contraseña\n"
                "desde el módulo Usuarios."
            )
            self._advertencia_hash_legado = False

        # Forzar cambio de contraseña si el flag está activo
        if usuario_data.get('debe_cambiar_password'):
            if not self._cambio_contrasena_obligatorio(usuario_data):
                # Usuario cerró el diálogo sin cambiar — no dejamos entrar
                self.root.deiconify()
                self.lbl_estado.config(
                    text=" Debe cambiar su contraseña para continuar"
                )
                return

        # Registrar inicio de sesión
        usuario_data['id_sesion'] = self._registrar_sesion(usuario_data['id_usuario'])

        # Cancelar timers y bindings del login antes de ceder el root al dashboard
        if hasattr(self, '_after_countdown') and self._after_countdown:
            try:
                self.root.after_cancel(self._after_countdown)
            except Exception:
                pass
            self._after_countdown = None
        try:
            self.root.unbind('<Escape>')
        except Exception:
            pass

        self.root.withdraw()

        # Determinar qué dashboard abrir
        rol = usuario_data['rol']
        nombre = usuario_data['nombre_completo']
        usuario_login = usuario_data['usuario']

        try:
            if rol == 'contadora':
                from modules.dashboard_contadora import DashboardContadora
                DashboardContadora(self.root, usuario_data)
            elif rol == 'administrador':
                from modules.dashboard import Dashboard
                Dashboard(self.root, usuario_data)
            elif rol == 'cajero':
                from modules.dashboard_cajero import DashboardCajero
                DashboardCajero(self.root, usuario_data)
            else:
                from modules.dashboard import Dashboard
                Dashboard(self.root, usuario_data)
        except ImportError:
            messagebox.showinfo(
                "En Desarrollo",
                f"Bienvenido(a) {nombre}!\n\nEl panel para '{rol}' está en desarrollo.\nSe abrirá el panel principal.",
            )
            from modules.dashboard import Dashboard
            Dashboard(self.root, usuario_data)
        except Exception as e:
            import traceback, logging
            logging.getLogger("pocitos").error(
                f"Error abriendo dashboard para {usuario_login}:\n{traceback.format_exc()}"
            )
            messagebox.showerror("Error al abrir panel",
                                 f"No se pudo abrir el panel:\n{e}")

    def _registrar_sesion(self, id_usuario):
        """Cierra sesiones abiertas del usuario (crash recovery) e inserta una nueva."""
        try:
            with transaccion_atomica() as conn:
                # Cerrar sesiones abiertas previas (app cerrada sin logout)
                conn.execute(
                    "UPDATE sesiones SET fecha_fin = datetime('now','localtime') "
                    "WHERE id_usuario = ? AND fecha_fin IS NULL",
                    (id_usuario,)
                )
                cursor = conn.execute(
                    "INSERT INTO sesiones (id_usuario) VALUES (?)", (id_usuario,)
                )
                return cursor.lastrowid
        except Exception:
            return None

    def _cambio_contrasena_obligatorio(self, usuario_data):
        """Muestra diálogo de cambio obligatorio de contraseña.
        Devuelve True si el cambio fue exitoso, False si el usuario canceló."""
        dialogo = tk.Toplevel(self.root)
        dialogo.title(" Cambio de Contraseña Obligatorio")
        dialogo.geometry("420x380")
        dialogo.resizable(True, True)
        dialogo.configure(bg=COLORES['fondo_card'])
        dialogo.transient(self.root)
        dialogo.grab_set()
        # Impedir cerrar el diálogo con la X
        dialogo.protocol("WM_DELETE_WINDOW", lambda: None)

        main = tk.Frame(dialogo, bg=COLORES['fondo_card'], padx=30, pady=20)
        main.pack(fill='both', expand=True)

        tk.Label(main, text="Cambio de Contrasena Requerido",
                 font=FUENTES['encabezado'], fg=COLORES['acento'],
                 bg=COLORES['fondo_card']).pack(anchor='w', pady=(0, 5))

        tk.Label(main,
                 text="Por seguridad debe establecer una nueva contraseña\nantes de continuar.",
                 font=FUENTES['normal'], fg=COLORES['texto_secundario'],
                 bg=COLORES['fondo_card'], justify='left').pack(anchor='w', pady=(0, 20))

        # Campo nueva contraseña
        tk.Label(main, text="Nueva contraseña:", font=FUENTES['normal_bold'],
                 fg=COLORES['texto'], bg=COLORES['fondo_card']).pack(anchor='w', pady=(0, 4))
        entry_nueva = tk.Entry(main, font=FUENTES['input'], show='*',
                               relief='solid', bd=1, highlightthickness=1,
                               highlightbackground=COLORES['borde'],
                               bg=COLORES['fondo_input'], fg=COLORES['texto'],
                               insertbackground=COLORES['acento'])
        entry_nueva.pack(fill='x', ipady=7, pady=(0, 12))
        entry_nueva.focus_set()

        # Campo confirmar contraseña
        tk.Label(main, text="Confirmar contraseña:", font=FUENTES['normal_bold'],
                 fg=COLORES['texto'], bg=COLORES['fondo_card']).pack(anchor='w', pady=(0, 4))
        entry_confirmar = tk.Entry(main, font=FUENTES['input'], show='*',
                                   relief='solid', bd=1, highlightthickness=1,
                                   highlightbackground=COLORES['borde'],
                                   bg=COLORES['fondo_input'], fg=COLORES['texto'],
                                   insertbackground=COLORES['acento'])
        entry_confirmar.pack(fill='x', ipady=7, pady=(0, 8))

        lbl_error = tk.Label(main, text="", font=FUENTES['pequena'],
                             fg=COLORES['error'], bg=COLORES['fondo_card'])
        lbl_error.pack(anchor='w', pady=(0, 12))

        resultado = {'ok': False}

        def guardar(event=None):
            nueva = entry_nueva.get()
            confirmar = entry_confirmar.get()

            if len(nueva) < 8:
                lbl_error.config(text=" La contraseña debe tener al menos 8 caracteres")
                return
            if nueva != confirmar:
                lbl_error.config(text=" Las contraseñas no coinciden")
                entry_confirmar.delete(0, tk.END)
                entry_confirmar.focus_set()
                return

            try:
                if BCRYPT_DISPONIBLE:
                    nuevo_hash = bcrypt.hashpw(
                        nueva.encode('utf-8'), bcrypt.gensalt(12)
                    ).decode('utf-8')
                else:
                    nuevo_hash = hashlib.sha256(nueva.encode()).hexdigest()

                with transaccion_atomica() as conn:
                    conn.execute(
                        "UPDATE usuarios SET contrasena_hash = ?, "
                        "debe_cambiar_password = 0 WHERE id_usuario = ?",
                        (nuevo_hash, usuario_data['id_usuario'])
                    )
                    # Registrar en auditoría
                    conn.execute("""
                        INSERT INTO auditoria
                        (tabla_afectada, id_registro, accion, usuario, comentario)
                        VALUES ('usuarios', ?, 'CAMBIO_CONTRASENA', ?, 'Cambio de contrasena en primer inicio')
                    """, (usuario_data['id_usuario'], usuario_data['usuario']))
                resultado['ok'] = True
                messagebox.showinfo("Listo", "Contraseña actualizada correctamente.")
                dialogo.destroy()
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo guardar la contraseña: {e}")

        crear_boton(dialogo, "Guardar", guardar, tipo='exito').pack(pady=10)
        dialogo.wait_window(dialogo)
        return resultado['ok']