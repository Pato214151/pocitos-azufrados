"""
Módulo de Usuarios - Club Los Pocitos Azufrados
Gestión de usuarios (admin only)
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import os, sys, datetime
import hashlib

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from utils.tema_corporativo import COLORES, FUENTES, crear_boton, aplicar_estilo_tabla
from database.connection import get_connection, conexion_segura
from utils.logger import log_auditoria

try:
    import bcrypt as _bcrypt
    _BCRYPT_OK = True
except ImportError:
    _BCRYPT_OK = False


class UsuariosModule:
    ROLES = ['administrador', 'cajero', 'vendedor', 'contadora']
    _MIN_PASSWORD_LEN = 8

    def __init__(self, parent, usuario):
        self.parent = parent
        self.usuario = usuario
        self.usuario_seleccionado = None
        self.usuarios = []

        # Verificar que sea admin
        if usuario['rol'] != 'administrador':
            tk.Label(self.parent, text=" Acceso Denegado: Solo administradores pueden acceder",
                     font=FUENTES['titulo'], fg=COLORES['error'],
                     bg=COLORES['fondo']).pack(padx=15, pady=20)
            return

        self._crear_interfaz()
        self._cargar_usuarios()

    def _crear_interfaz(self):
        """Interfaz principal de usuarios"""
        # Header
        header = tk.Frame(self.parent, bg=COLORES['primario'])
        header.pack(fill='x')

        inner_hdr = tk.Frame(header, bg=COLORES['primario'], padx=15, pady=10)
        inner_hdr.pack(fill='x')

        tk.Label(inner_hdr, text="Gestion de Usuarios",
                 font=FUENTES['encabezado'], fg=COLORES['texto_claro'],
                 bg=COLORES['primario']).pack(side='left')

        # Botón nuevo
        crear_boton(inner_hdr, "Nuevo Usuario", self._nuevo_usuario, tipo='acento').pack(side='right')

        # ========== CUERPO PRINCIPAL ==========
        body = tk.Frame(self.parent, bg=COLORES['fondo'])
        body.pack(fill='both', expand=True, padx=15, pady=5)

        # Tabla de usuarios
        tabla_frame = tk.Frame(body, bg=COLORES['fondo_card'],
                               highlightbackground=COLORES['borde'], highlightthickness=1)
        tabla_frame.pack(fill='both', expand=True)

        self.tree_usuarios = ttk.Treeview(tabla_frame, height=15,
                                          columns=('usuario', 'nombre', 'email', 'rol', 'activo', 'ultimo_login'),
                                          show='headings')

        self.tree_usuarios.column('usuario', width=120, anchor='w')
        self.tree_usuarios.column('nombre', width=150, anchor='w')
        self.tree_usuarios.column('email', width=180, anchor='w')
        self.tree_usuarios.column('rol', width=120, anchor='center')
        self.tree_usuarios.column('activo', width=80, anchor='center')
        self.tree_usuarios.column('ultimo_login', width=150, anchor='center')

        self.tree_usuarios.heading('usuario', text='Usuario')
        self.tree_usuarios.heading('nombre', text='Nombre')
        self.tree_usuarios.heading('email', text='Email')
        self.tree_usuarios.heading('rol', text='Rol')
        self.tree_usuarios.heading('activo', text='Activo')
        self.tree_usuarios.heading('ultimo_login', text='Último Login')

        aplicar_estilo_tabla(self.tree_usuarios)
        self.tree_usuarios.pack(fill='both', expand=True)
        self.tree_usuarios.bind('<Button-1>', self._on_usuario_click)

        # Frame de acciones
        action_frame = tk.Frame(body, bg=COLORES['fondo'])
        action_frame.pack(fill='x', pady=(8, 0))

        crear_boton(action_frame, " Editar", self._editar_usuario, tipo='secundario').pack(side='left', padx=2)
        crear_boton(action_frame, " Cambiar Contrasena", self._cambiar_password, tipo='acento').pack(side='left', padx=2)
        crear_boton(action_frame, " PIN", self._gestionar_pin, tipo='agua').pack(side='left', padx=2)
        crear_boton(action_frame, " Desactivar", self._desactivar_usuario, tipo='advertencia').pack(side='left', padx=2)
        crear_boton(action_frame, " Ver Actividad", self._ver_actividad, tipo='primario').pack(side='left', padx=2)

    def _cargar_usuarios(self):
        """Carga todos los usuarios"""
        try:
            with conexion_segura() as conn:
                rows = conn.execute("""
                    SELECT id_usuario, usuario, nombre_completo, email, rol, activo, ultimo_login
                    FROM usuarios
                    ORDER BY usuario
              """).fetchall()

                # Limpiar árbol
                for item in self.tree_usuarios.get_children():
                    self.tree_usuarios.delete(item)

                self.usuarios = []

                for i, row in enumerate(rows):
                    tag = 'par' if i % 2 == 0 else 'impar'
                    if not row['activo']:
                        tag = 'critico'

                    self.tree_usuarios.insert('', 'end', values=(
                        row['usuario'],
                        row['nombre_completo'],
                        row['email'] or '---',
                        row['rol'].upper(),
                        '' if row['activo'] else '',
                        row['ultimo_login'][:16] if row['ultimo_login'] else '---'
                    ), tags=(tag,), iid=row['id_usuario'])

                    self.usuarios.append(row)

        except Exception as e:
            messagebox.showerror("Error", f"Error al cargar usuarios: {str(e)}")

    def _on_usuario_click(self, event):
        """Maneja clic en un usuario"""
        item = self.tree_usuarios.selection()
        if item:
            self.usuario_seleccionado = int(item[0])

    def _nuevo_usuario(self):
        """Crea un nuevo usuario"""
        dialog = tk.Toplevel(self.parent)
        dialog.title("Nuevo Usuario")
        dialog.geometry("400x350")
        dialog.resizable(True, True)

        # Usuario
        tk.Label(dialog, text="Usuario:", font=FUENTES['normal']).pack(anchor='w', padx=15, pady=(15, 0))
        entry_usuario = tk.Entry(dialog, font=FUENTES['input'], width=40)
        entry_usuario.pack(fill='x', padx=15, pady=5, ipady=6)

        # Nombre
        tk.Label(dialog, text="Nombre Completo:", font=FUENTES['normal']).pack(anchor='w', padx=15, pady=(10, 0))
        entry_nombre = tk.Entry(dialog, font=FUENTES['input'], width=40)
        entry_nombre.pack(fill='x', padx=15, pady=5, ipady=6)

        # Email
        tk.Label(dialog, text="Email:", font=FUENTES['normal']).pack(anchor='w', padx=15, pady=(10, 0))
        entry_email = tk.Entry(dialog, font=FUENTES['input'], width=40)
        entry_email.pack(fill='x', padx=15, pady=5, ipady=6)

        # Rol
        tk.Label(dialog, text="Rol:", font=FUENTES['normal']).pack(anchor='w', padx=15, pady=(10, 0))
        combo_rol = ttk.Combobox(dialog, values=self.ROLES, state='readonly', font=FUENTES['input'])
        combo_rol.set('cajero')
        combo_rol.pack(fill='x', padx=15, pady=5, ipady=6)

        # Contraseña
        tk.Label(dialog, text="Contraseña:", font=FUENTES['normal']).pack(anchor='w', padx=15, pady=(10, 0))
        entry_pass = tk.Entry(dialog, font=FUENTES['input'], width=40, show='*')
        entry_pass.pack(fill='x', padx=15, pady=5, ipady=6)

        def guardar():
            usuario = entry_usuario.get().strip()
            nombre = entry_nombre.get().strip()
            email = entry_email.get().strip()
            rol = combo_rol.get()
            password = entry_pass.get()

            if not usuario or not nombre or not password:
                messagebox.showwarning("Campos Requeridos", "Complete usuario, nombre y contraseña")
                return
            if len(password) < self._MIN_PASSWORD_LEN:
                messagebox.showwarning("Contraseña muy corta",
                                       f"La contraseña debe tener al menos {self._MIN_PASSWORD_LEN} caracteres")
                return

            try:
                if _BCRYPT_OK:
                    pass_hash = _bcrypt.hashpw(password.encode(), _bcrypt.gensalt(12)).decode()
                else:
                    pass_hash = hashlib.sha256(password.encode()).hexdigest()

                with conexion_segura() as conn:
                    conn.execute("""
                        INSERT INTO usuarios (usuario, nombre_completo, email, contrasena_hash, rol, activo)
                        VALUES (?, ?, ?, ?, ?, 1)
                  """, (usuario, nombre, email or None, pass_hash, rol))

                    user_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

                    log_auditoria(conn, 'usuarios', user_id, 'INSERT', self.usuario['usuario'],
                                f"Nuevo usuario: {usuario} ({rol})")

                messagebox.showinfo("Exito", f"Usuario {usuario} creado exitosamente")
                dialog.destroy()
                self._cargar_usuarios()

            except Exception as e:
                messagebox.showerror("Error", f"Error al crear usuario: {str(e)}")

        btn_frame = tk.Frame(dialog)
        btn_frame.pack(fill='x', padx=15, pady=15)
        crear_boton(btn_frame, "Guardar", guardar, tipo='exito').pack(side='left', padx=2)
        crear_boton(btn_frame, "Cancelar", dialog.destroy, tipo='secundario').pack(side='right', padx=2)

    def _confirmar_admin(self, titulo="Confirmación requerida"):
        """Pide al admin su contraseña y la verifica. Devuelve True si es correcta."""
        dialog = tk.Toplevel(self.parent)
        dialog.title(titulo)
        dialog.geometry("360x160")
        dialog.resizable(True, True)
        dialog.grab_set()

        tk.Label(dialog, text="Confirme su contraseña de administrador:",
                 font=FUENTES['normal']).pack(anchor='w', padx=15, pady=(15, 0))
        entry_pw = tk.Entry(dialog, font=FUENTES['input'], width=35, show='*')
        entry_pw.pack(fill='x', padx=15, pady=8, ipady=6)
        entry_pw.focus_set()

        resultado = {'ok': False}
        _intentos = [0]
        _MAX_INTENTOS = 5

        def confirmar():
            pw = entry_pw.get()
            try:
                with conexion_segura() as conn:
                    row = conn.execute(
                      "SELECT contrasena_hash FROM usuarios WHERE usuario = ?",
                        (self.usuario['usuario'],)
                    ).fetchone()
                if not row:
                    messagebox.showerror("Error", "No se encontró el usuario.", parent=dialog)
                    return
                h = row['contrasena_hash']
                if h.startswith('$2') and _BCRYPT_OK:
                    ok = _bcrypt.checkpw(pw.encode(), h.encode())
                else:
                    ok = (hashlib.sha256(pw.encode()).hexdigest() == h)
                if ok:
                    resultado['ok'] = True
                    dialog.destroy()
                else:
                    _intentos[0] += 1
                    restantes = _MAX_INTENTOS - _intentos[0]
                    if restantes <= 0:
                        messagebox.showerror("Acceso bloqueado",
                                           "Demasiados intentos fallidos.", parent=dialog)
                        dialog.destroy()
                        return
                    messagebox.showerror("Contraseña incorrecta",
                                       f"La contraseña no es correcta. Intentos restantes: {restantes}",
                                       parent=dialog)
                    entry_pw.delete(0, tk.END)
                    entry_pw.focus_set()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=dialog)

        btn_frame = tk.Frame(dialog)
        btn_frame.pack(fill='x', padx=15, pady=10)
        crear_boton(btn_frame, "Confirmar", confirmar, tipo='exito').pack(side='left', padx=2)
        crear_boton(btn_frame, "Cancelar", dialog.destroy, tipo='secundario').pack(side='right', padx=2)
        dialog.bind('<Return>', lambda e: confirmar())

        dialog.wait_window()
        return resultado['ok']

    def _editar_usuario(self):
        """Edita un usuario seleccionado"""
        if self.usuario_seleccionado is None:
            messagebox.showwarning("Seleccione un Usuario", "Por favor seleccione un usuario")
            return

        usuario = next((u for u in self.usuarios if u['id_usuario'] == self.usuario_seleccionado), None)
        if not usuario:
            return

        dialog = tk.Toplevel(self.parent)
        dialog.title(f"Editar Usuario: {usuario['usuario']}")
        dialog.geometry("400x300")
        dialog.resizable(True, True)

        tk.Label(dialog, text="Nombre Completo:", font=FUENTES['normal']).pack(anchor='w', padx=15, pady=(15, 0))
        entry_nombre = tk.Entry(dialog, font=FUENTES['input'], width=40)
        entry_nombre.insert(0, usuario['nombre_completo'])
        entry_nombre.pack(fill='x', padx=15, pady=5, ipady=6)

        tk.Label(dialog, text="Email:", font=FUENTES['normal']).pack(anchor='w', padx=15, pady=(10, 0))
        entry_email = tk.Entry(dialog, font=FUENTES['input'], width=40)
        entry_email.insert(0, usuario['email'] or '')
        entry_email.pack(fill='x', padx=15, pady=5, ipady=6)

        tk.Label(dialog, text="Rol:", font=FUENTES['normal']).pack(anchor='w', padx=15, pady=(10, 0))
        combo_rol = ttk.Combobox(dialog, values=self.ROLES, state='readonly', font=FUENTES['input'])
        combo_rol.set(usuario['rol'])
        combo_rol.pack(fill='x', padx=15, pady=5, ipady=6)

        def guardar():
            nombre = entry_nombre.get().strip()
            email = entry_email.get().strip()
            rol = combo_rol.get()

            if not nombre:
                messagebox.showwarning("Campo Requerido", "El nombre es requerido")
                return

            # Confirmar contraseña del admin si el rol cambia
            if rol != usuario['rol']:
                dialog.grab_release()
                ok = self._confirmar_admin("Confirmar cambio de rol")
                if not ok:
                    return

            try:
                with conexion_segura() as conn:
                    conn.execute("""
                        UPDATE usuarios
                        SET nombre_completo = ?, email = ?, rol = ?
                        WHERE id_usuario = ?
                  """, (nombre, email or None, rol, self.usuario_seleccionado))

                    comentario = f"Edición de usuario" + (f" - rol: {usuario['rol']} > {rol}" if rol != usuario['rol'] else "")
                    log_auditoria(conn, 'usuarios', self.usuario_seleccionado, 'UPDATE',
                                self.usuario['usuario'], comentario)

                messagebox.showinfo("Exito", "Usuario actualizado")
                dialog.destroy()
                self._cargar_usuarios()

            except Exception as e:
                messagebox.showerror("Error", f"Error al editar: {str(e)}")

        btn_frame = tk.Frame(dialog)
        btn_frame.pack(fill='x', padx=15, pady=15)
        crear_boton(btn_frame, "Guardar", guardar, tipo='exito').pack(side='left', padx=2)
        crear_boton(btn_frame, "Cancelar", dialog.destroy, tipo='secundario').pack(side='right', padx=2)

    def _gestionar_pin(self):
        """Asigna o cambia el PIN de 4 digitos de un usuario."""
        if self.usuario_seleccionado is None:
            messagebox.showwarning("Seleccione un Usuario", "Seleccione un usuario primero.")
            return

        usuario_obj = next((u for u in self.usuarios if u['id_usuario'] == self.usuario_seleccionado), None)
        if not usuario_obj:
            return

        dialog = tk.Toplevel(self.parent)
        dialog.title(f"PIN — {usuario_obj['usuario']}")
        dialog.geometry("360x210")
        dialog.resizable(True, True)
        dialog.grab_set()
        dialog.configure(bg=COLORES['fondo_card'])

        tk.Label(dialog, text=f"Gestionar PIN de: {usuario_obj['nombre_completo']}",
                 font=FUENTES['encabezado'], fg=COLORES['texto'],
                 bg=COLORES['fondo_card']).pack(padx=15, pady=(15, 8))

        tk.Label(dialog, text="Nuevo PIN (4 digitos numericos):",
                 font=FUENTES['normal'], fg=COLORES['texto'],
                 bg=COLORES['fondo_card']).pack(anchor='w', padx=15)
        entry_pin = tk.Entry(dialog, font=FUENTES['input'], width=10, show='*', relief='solid', bd=1)
        entry_pin.pack(anchor='w', padx=15, pady=(3, 8), ipady=5)
        entry_pin.focus_set()

        tk.Label(dialog, text="Confirmar PIN:",
                 font=FUENTES['normal'], fg=COLORES['texto'],
                 bg=COLORES['fondo_card']).pack(anchor='w', padx=15)
        entry_pin2 = tk.Entry(dialog, font=FUENTES['input'], width=10, show='*', relief='solid', bd=1)
        entry_pin2.pack(anchor='w', padx=15, pady=(3, 8), ipady=5)

        def _guardar_pin():
            pin1 = entry_pin.get().strip()
            pin2 = entry_pin2.get().strip()
            if not pin1:
                messagebox.showwarning("Campo requerido", "Ingrese el PIN.", parent=dialog)
                return
            if not pin1.isdigit() or len(pin1) != 4:
                messagebox.showwarning("PIN invalido", "El PIN debe ser exactamente 4 digitos numericos.", parent=dialog)
                return
            if pin1 != pin2:
                messagebox.showwarning("No coinciden", "Los PINs no coinciden.", parent=dialog)
                return
            try:
                # Hashear el PIN con bcrypt antes de guardar
                if _BCRYPT_OK:
                    pin_a_guardar = _bcrypt.hashpw(pin1.encode(), _bcrypt.gensalt(12)).decode()
                else:
                    pin_a_guardar = pin1  # fallback sin bcrypt (inseguro, pero funcional)
                with conexion_segura() as conn:
                    conn.execute("UPDATE usuarios SET pin = ? WHERE id_usuario = ?",
                                 (pin_a_guardar, self.usuario_seleccionado))
                    log_auditoria(conn, 'usuarios', self.usuario_seleccionado, 'UPDATE',
                                  self.usuario['usuario'],
                                  f"PIN actualizado para usuario {usuario_obj['usuario']}")
                messagebox.showinfo("Exito", f"PIN actualizado para {usuario_obj['usuario']}.")
                dialog.destroy()
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo guardar el PIN: {e}", parent=dialog)

        def _quitar_pin():
            if messagebox.askyesno("Quitar PIN",
                                   f"Quitar el PIN de {usuario_obj['usuario']}?",
                                   parent=dialog):
                try:
                    with conexion_segura() as conn:
                        conn.execute("UPDATE usuarios SET pin = NULL WHERE id_usuario = ?",
                                     (self.usuario_seleccionado,))
                        log_auditoria(conn, 'usuarios', self.usuario_seleccionado, 'UPDATE',
                                      self.usuario['usuario'],
                                      f"PIN eliminado para usuario {usuario_obj['usuario']}")
                    messagebox.showinfo("Exito", "PIN eliminado.")
                    dialog.destroy()
                except Exception as e:
                    messagebox.showerror("Error", f"Error: {e}", parent=dialog)

        btn_f = tk.Frame(dialog, bg=COLORES['fondo_card'])
        btn_f.pack(fill='x', padx=15, pady=(0, 12))
        crear_boton(btn_f, "Guardar PIN", _guardar_pin, tipo='exito').pack(side='left', padx=4)
        crear_boton(btn_f, "Quitar PIN", _quitar_pin, tipo='advertencia').pack(side='left', padx=4)
        crear_boton(btn_f, "Cancelar", dialog.destroy, tipo='secundario').pack(side='right', padx=4)

    def _cambiar_password(self):
        """Cambia la contraseña de un usuario (requiere confirmar contraseña del admin)"""
        if self.usuario_seleccionado is None:
            messagebox.showwarning("Seleccione un Usuario", "Por favor seleccione un usuario")
            return

        usuario = next((u for u in self.usuarios if u['id_usuario'] == self.usuario_seleccionado), None)
        if not usuario:
            return

        # Confirmar contraseña del admin antes de continuar
        if not self._confirmar_admin("Confirmar reset de contraseña"):
            return

        dialog = tk.Toplevel(self.parent)
        dialog.title(f"Nueva Contraseña: {usuario['usuario']}")
        dialog.geometry("350x170")
        dialog.resizable(True, True)
        dialog.grab_set()

        tk.Label(dialog, text="Nueva Contraseña:", font=FUENTES['normal']).pack(anchor='w', padx=15, pady=(15, 0))
        entry_pass = tk.Entry(dialog, font=FUENTES['input'], width=35, show='*')
        entry_pass.pack(fill='x', padx=15, pady=5, ipady=6)
        entry_pass.focus_set()

        tk.Label(dialog, text="Repetir Contraseña:", font=FUENTES['normal']).pack(anchor='w', padx=15, pady=(5, 0))
        entry_pass2 = tk.Entry(dialog, font=FUENTES['input'], width=35, show='*')
        entry_pass2.pack(fill='x', padx=15, pady=5, ipady=6)

        def guardar():
            password = entry_pass.get()
            password2 = entry_pass2.get()

            if not password:
                messagebox.showwarning("Campo Requerido", "Ingrese una contraseña", parent=dialog)
                return
            if password != password2:
                messagebox.showwarning("No coinciden", "Las contraseñas no coinciden", parent=dialog)
                return
            if len(password) < self._MIN_PASSWORD_LEN:
                messagebox.showwarning("Muy corta",
                                       f"La contraseña debe tener al menos {self._MIN_PASSWORD_LEN} caracteres",
                                       parent=dialog)
                return

            try:
                if _BCRYPT_OK:
                    pass_hash = _bcrypt.hashpw(password.encode(), _bcrypt.gensalt(12)).decode()
                else:
                    pass_hash = hashlib.sha256(password.encode()).hexdigest()

                with conexion_segura() as conn:
                    conn.execute(
                      "UPDATE usuarios SET contrasena_hash = ? WHERE id_usuario = ?",
                        (pass_hash, self.usuario_seleccionado)
                    )
                    log_auditoria(conn, 'usuarios', self.usuario_seleccionado, 'UPDATE',
                                  self.usuario['usuario'], "Reset de contraseña por admin")

                messagebox.showinfo("Exito", "Contraseña actualizada")
                dialog.destroy()

            except Exception as e:
                messagebox.showerror("Error", f"Error: {str(e)}", parent=dialog)

        btn_frame = tk.Frame(dialog)
        btn_frame.pack(fill='x', padx=15, pady=10)
        crear_boton(btn_frame, "Guardar", guardar, tipo='exito').pack(side='left', padx=2)
        crear_boton(btn_frame, "Cancelar", dialog.destroy, tipo='secundario').pack(side='right', padx=2)
        dialog.bind('<Return>', lambda e: guardar())

    def _desactivar_usuario(self):
        """Desactiva un usuario"""
        if self.usuario_seleccionado is None:
            messagebox.showwarning("Seleccione un Usuario", "Por favor seleccione un usuario")
            return

        usuario = next((u for u in self.usuarios if u['id_usuario'] == self.usuario_seleccionado), None)
        if not usuario:
            return

        if messagebox.askyesno("Confirmar", f"¿Desactivar usuario {usuario['usuario']}?"):
            try:
                with conexion_segura() as conn:
                    conn.execute("""
                        UPDATE usuarios
                        SET activo = 0
                        WHERE id_usuario = ?
                  """, (self.usuario_seleccionado,))

                    log_auditoria(conn, 'usuarios', self.usuario_seleccionado, 'UPDATE',
                                self.usuario['usuario'], "Usuario desactivado")

                messagebox.showinfo("Exito", "Usuario desactivado")
                self._cargar_usuarios()

            except Exception as e:
                messagebox.showerror("Error", f"Error: {str(e)}")

    def _ver_actividad(self):
        """Muestra el historial de auditoría del usuario seleccionado"""
        if self.usuario_seleccionado is None:
            messagebox.showwarning("Seleccione un Usuario", "Por favor seleccione un usuario")
            return

        usuario = next((u for u in self.usuarios if u['id_usuario'] == self.usuario_seleccionado), None)
        if not usuario:
            return

        dialog = tk.Toplevel(self.parent)
        dialog.title(f"Actividad: {usuario['usuario']}")
        dialog.geometry("860x520")
        dialog.grab_set()

        tk.Label(dialog,
                 text=f" Actividad de: {usuario['nombre_completo']} ({usuario['usuario']})",
                 font=FUENTES['encabezado']).pack(padx=15, pady=(15, 5), anchor='w')

        tree_frame = tk.Frame(dialog)
        tree_frame.pack(fill='both', expand=True, padx=15, pady=(0, 5))

        tree = ttk.Treeview(
            tree_frame,
            columns=('fecha', 'accion', 'tabla', 'id_reg', 'comentario'),
            show='headings', height=20
        )
        tree.heading('fecha',      text='Fecha')
        tree.heading('accion',     text='Acción')
        tree.heading('tabla',      text='Tabla')
        tree.heading('id_reg',     text='ID')
        tree.heading('comentario', text='Comentario')
        tree.column('fecha',      width=140)
        tree.column('accion',     width=90, anchor='center')
        tree.column('tabla',      width=110)
        tree.column('id_reg',     width=50, anchor='center')
        tree.column('comentario', width=400)

        aplicar_estilo_tabla(tree)

        sb = ttk.Scrollbar(tree_frame, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        sb.pack(side='right', fill='y')
        tree.pack(fill='both', expand=True)

        try:
            with conexion_segura() as conn:
                rows = conn.execute("""
                    SELECT fecha_hora as fecha, accion, tabla_afectada as tabla, id_registro, comentario
                    FROM auditoria
                    WHERE usuario = ?
                    ORDER BY fecha DESC
                    LIMIT 500
              """, (usuario['usuario'],)).fetchall()

            for i, row in enumerate(rows):
                tag = 'par' if i % 2 == 0 else 'impar'
                tree.insert('', 'end', values=(
                    str(row['fecha'])[:16],
                    row['accion'],
                    row['tabla'],
                    str(row['id_registro'] or ''),
                    row['comentario'] or ''
                ), tags=(tag,))
        except Exception:
            pass