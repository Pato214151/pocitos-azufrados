"""
Módulo de Reporte de Errores - Club Los Pocitos Azufrados
Permite registrar errores con capturas de pantalla y enviarlos por correo al soporte.
"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import logging
import os
import sys
import smtplib
import shutil
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime

BASE_DIR = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) \
           else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

from utils.tema_corporativo import (COLORES, FUENTES, crear_boton,
                                    format_money, aplicar_estilo_tabla)
from database.connection import conexion_segura, transaccion_atomica
from utils.logger import log_auditoria

_log = logging.getLogger("pocitos")

MODULOS = [
    'Bar / POS', 'Caja', 'Inventario', 'Categorias', 'Cocina',
    'Pedidos', 'Cuentas / Consumo empleados', 'Boletas', 'Historial ventas',
    'Reportes', 'Gastos', 'Clientes', 'Proveedores', 'Nomina',
    'Usuarios', 'Configuracion', 'Cocina Web', 'Login', 'Otro'
]
SEVERIDADES = ['Critico', 'Alto', 'Medio', 'Bajo']
COLOR_SEV = {
    'Critico': '#c62828',
    'Alto':    '#e65100',
    'Medio':   '#f9a825',
    'Bajo':    '#2e7d32',
}


class ReporteErroresModule:
    """Módulo para reportar errores con capturas y envío por correo."""

    def __init__(self, parent, usuario):
        self.parent = parent
        self.usuario = usuario
        self._ruta_captura_actual = None
        self._id_sel = None

        self._crear_interfaz()
        self._cargar_reportes()

    # ── Interfaz ─────────────────────────────────────────────────────────────

    def _crear_interfaz(self):
        """Arma las pestañas: nuevo reporte, historial y configuración de correo."""
        self.parent.configure(bg=COLORES['fondo'])

        hdr = tk.Frame(self.parent, bg=COLORES['primario'], pady=10)
        hdr.pack(fill='x')
        tk.Label(hdr, text="Reporte de Errores",
                 font=FUENTES['titulo'], fg=COLORES['texto_claro'],
                 bg=COLORES['primario']).pack()
        tk.Label(hdr, text="Documenta problemas y envialos al soporte tecnico",
                 font=FUENTES['normal'], fg=COLORES['acento'],
                 bg=COLORES['primario']).pack()

        nb = ttk.Notebook(self.parent)
        nb.pack(fill='both', expand=True, padx=10, pady=8)

        tab_nuevo   = tk.Frame(nb, bg=COLORES['fondo'])
        tab_historial = tk.Frame(nb, bg=COLORES['fondo'])
        tab_config  = tk.Frame(nb, bg=COLORES['fondo'])

        nb.add(tab_nuevo,    text='  Nuevo reporte  ')
        nb.add(tab_historial, text='  Historial  ')
        nb.add(tab_config,   text='  Config. correo  ')

        self._tab_nuevo(tab_nuevo)
        self._tab_historial(tab_historial)
        self._tab_config(tab_config)

    # ── Tab: Nuevo reporte ───────────────────────────────────────────────────

    def _tab_nuevo(self, parent):
        """Formulario para describir el error y adjuntar una captura."""
        canvas = tk.Canvas(parent, bg=COLORES['fondo'], highlightthickness=0)
        sb = ttk.Scrollbar(parent, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side='right', fill='y')
        canvas.pack(side='left', fill='both', expand=True)

        frame = tk.Frame(canvas, bg=COLORES['fondo'])
        win_id = canvas.create_window((0, 0), window=frame, anchor='nw')
        canvas.bind('<Configure>', lambda e: canvas.itemconfig(win_id, width=e.width))
        frame.bind('<Configure>', lambda e: canvas.configure(
            scrollregion=canvas.bbox('all')))

        def _lbl(text, bold=False):
            tk.Label(frame, text=text,
                     font=FUENTES['normal_bold'] if bold else FUENTES['normal'],
                     fg=COLORES['texto'], bg=COLORES['fondo']).pack(anchor='w', pady=(10, 2), padx=16)

        def _entry_frame():
            f = tk.Frame(frame, bg=COLORES['fondo'])
            f.pack(fill='x', padx=16)
            return f

        # Módulo y severidad en la misma fila
        fila1 = tk.Frame(frame, bg=COLORES['fondo'])
        fila1.pack(fill='x', padx=16, pady=(12, 0))

        col_mod = tk.Frame(fila1, bg=COLORES['fondo'])
        col_mod.pack(side='left', fill='x', expand=True, padx=(0, 10))
        tk.Label(col_mod, text="Modulo con el error:",
                 font=FUENTES['normal_bold'], fg=COLORES['texto'],
                 bg=COLORES['fondo']).pack(anchor='w')
        self.var_modulo = tk.StringVar(value=MODULOS[0])
        ttk.Combobox(col_mod, values=MODULOS, textvariable=self.var_modulo,
                     state='readonly', font=FUENTES['input'],
                     width=28).pack(fill='x', pady=(4, 0))

        col_sev = tk.Frame(fila1, bg=COLORES['fondo'])
        col_sev.pack(side='left', padx=(0, 0))
        tk.Label(col_sev, text="Severidad:",
                 font=FUENTES['normal_bold'], fg=COLORES['texto'],
                 bg=COLORES['fondo']).pack(anchor='w')
        self.var_severidad = tk.StringVar(value='Medio')
        self.combo_sev = ttk.Combobox(col_sev, values=SEVERIDADES,
                                      textvariable=self.var_severidad,
                                      state='readonly', font=FUENTES['input'], width=12)
        self.combo_sev.pack(pady=(4, 0))

        # Descripción
        _lbl("Descripcion del error: *", bold=True)
        self.txt_desc = tk.Text(_entry_frame(), height=5, font=FUENTES['input'],
                                bg=COLORES['fondo_input'], fg=COLORES['texto'],
                                relief='solid', bd=1, wrap='word')
        self.txt_desc.pack(fill='x')
        tk.Label(frame, text="Describe que estabas haciendo cuando ocurrio el error.",
                 font=FUENTES['pequena'], fg=COLORES['texto_secundario'],
                 bg=COLORES['fondo']).pack(anchor='w', padx=16)

        # Pasos para reproducir
        _lbl("Pasos para reproducir (opcional):", bold=True)
        self.txt_pasos = tk.Text(_entry_frame(), height=4, font=FUENTES['input'],
                                 bg=COLORES['fondo_input'], fg=COLORES['texto'],
                                 relief='solid', bd=1, wrap='word')
        self.txt_pasos.pack(fill='x')
        tk.Label(frame, text="Ej: 1. Abri Caja  2. Di clic en Cerrar  3. Aparecio el error",
                 font=FUENTES['pequena'], fg=COLORES['texto_secundario'],
                 bg=COLORES['fondo']).pack(anchor='w', padx=16)

        # Captura de pantalla
        _lbl("Captura de pantalla (opcional):", bold=True)
        cap_frame = tk.Frame(frame, bg=COLORES['fondo_card'],
                             relief='solid', bd=1, pady=8)
        cap_frame.pack(fill='x', padx=16)

        btn_row_cap = tk.Frame(cap_frame, bg=COLORES['fondo_card'])
        btn_row_cap.pack(fill='x', padx=8)
        crear_boton(btn_row_cap, "Adjuntar imagen",
                    self._adjuntar_captura, tipo='outline').pack(side='left', padx=(0, 8))
        crear_boton(btn_row_cap, "Quitar imagen",
                    self._quitar_captura, tipo='secundario').pack(side='left')

        self.lbl_captura = tk.Label(cap_frame,
                                    text="Sin imagen adjunta",
                                    font=FUENTES['pequena'],
                                    fg=COLORES['texto_secundario'],
                                    bg=COLORES['fondo_card'])
        self.lbl_captura.pack(anchor='w', padx=8, pady=(6, 0))

        self.lbl_preview = tk.Label(cap_frame, bg=COLORES['fondo_card'])
        self.lbl_preview.pack(pady=4)

        # Botones de acción
        tk.Frame(frame, bg=COLORES['borde'], height=1).pack(fill='x', padx=16, pady=12)
        btn_row = tk.Frame(frame, bg=COLORES['fondo'], pady=4)
        btn_row.pack(padx=16, fill='x')
        crear_boton(btn_row, "Guardar y enviar por correo",
                    self._guardar_y_enviar, tipo='primario').pack(side='left', padx=(0, 8), ipady=4)
        crear_boton(btn_row, "Solo guardar (sin enviar)",
                    self._solo_guardar, tipo='outline').pack(side='left', ipady=4)
        crear_boton(btn_row, "Limpiar formulario",
                    self._limpiar_formulario, tipo='secundario').pack(side='right', ipady=4)

        # Logs del sistema (adjuntos automáticos)
        tk.Frame(frame, bg=COLORES['borde'], height=1).pack(fill='x', padx=16, pady=(4, 0))
        tk.Label(frame,
                 text="Se adjuntan automaticamente: logs/errores.log y logs/pocitos.log",
                 font=FUENTES['pequena'], fg=COLORES['texto_secundario'],
                 bg=COLORES['fondo']).pack(anchor='w', padx=16, pady=(4, 16))

    # ── Tab: Historial ───────────────────────────────────────────────────────

    def _tab_historial(self, parent):
        """Lista de reportes enviados."""
        toolbar = tk.Frame(parent, bg=COLORES['fondo'], pady=6)
        toolbar.pack(fill='x', padx=10)
        crear_boton(toolbar, "Actualizar", self._cargar_reportes,
                    tipo='secundario').pack(side='left', padx=(0, 8))
        crear_boton(toolbar, "Reenviar seleccionado",
                    self._reenviar_seleccionado, tipo='outline').pack(side='left')

        cols = ('fecha', 'modulo', 'severidad', 'descripcion', 'enviado')
        self.tree_hist = ttk.Treeview(parent, columns=cols, show='headings')
        self.tree_hist.heading('fecha',       text='Fecha')
        self.tree_hist.heading('modulo',      text='Modulo')
        self.tree_hist.heading('severidad',   text='Severidad')
        self.tree_hist.heading('descripcion', text='Descripcion')
        self.tree_hist.heading('enviado',     text='Estado')
        self.tree_hist.column('fecha',       width=135)
        self.tree_hist.column('modulo',      width=160)
        self.tree_hist.column('severidad',   width=80,  anchor='center')
        self.tree_hist.column('descripcion', width=320)
        self.tree_hist.column('enviado',     width=90,  anchor='center')
        aplicar_estilo_tabla(self.tree_hist)

        sb = ttk.Scrollbar(parent, orient='vertical', command=self.tree_hist.yview)
        self.tree_hist.configure(yscrollcommand=sb.set)
        sb.pack(side='right', fill='y')
        self.tree_hist.pack(fill='both', expand=True, padx=10, pady=(0, 8))
        self.tree_hist.bind('<<TreeviewSelect>>', self._on_hist_select)

    # ── Tab: Configuración correo ────────────────────────────────────────────

    def _tab_config(self, parent):
        """Configuración SMTP para enviar los reportes."""
        frame = tk.Frame(parent, bg=COLORES['fondo'], padx=20, pady=16)
        frame.pack(fill='both', expand=True)

        tk.Label(frame,
                 text="Configuracion del correo para envio de reportes",
                 font=FUENTES['subtitulo'], fg=COLORES['texto'],
                 bg=COLORES['fondo']).pack(anchor='w', pady=(0, 4))
        tk.Label(frame,
                 text="Use una cuenta Gmail con 'Contrasena de aplicacion' (App Password) activada.",
                 font=FUENTES['pequena'], fg=COLORES['texto_secundario'],
                 bg=COLORES['fondo']).pack(anchor='w', pady=(0, 12))

        campos = [
            ('smtp_servidor',  'Servidor SMTP:',            'smtp.gmail.com'),
            ('smtp_puerto',    'Puerto SMTP:',               '587'),
            ('smtp_usuario',   'Correo remitente (Gmail):', ''),
            ('smtp_password',  'Contrasena de aplicacion:', ''),
            ('soporte_email',  'Correo destino (soporte):',
             'jramirezramirez2005@gmail.com'),
        ]
        self._entries_config = {}
        for clave, etiqueta, placeholder in campos:
            tk.Label(frame, text=etiqueta, font=FUENTES['normal'],
                     fg=COLORES['texto'], bg=COLORES['fondo']).pack(anchor='w', pady=(8, 2))
            show = '*' if clave == 'smtp_password' else ''
            e = tk.Entry(frame, font=FUENTES['input'], show=show,
                         bg=COLORES['fondo_input'], fg=COLORES['texto'],
                         relief='solid', bd=1)
            e.pack(fill='x', ipady=4)
            self._entries_config[clave] = e

        self._cargar_config_correo()

        btn_row = tk.Frame(frame, bg=COLORES['fondo'], pady=12)
        btn_row.pack(fill='x')
        crear_boton(btn_row, "Guardar configuracion",
                    self._guardar_config_correo, tipo='primario').pack(side='left', padx=(0, 8))
        crear_boton(btn_row, "Probar conexion",
                    self._probar_conexion, tipo='outline').pack(side='left')

        tk.Label(frame,
                 text="Como obtener App Password de Gmail:\n"
                      "1. Ve a myaccount.google.com\n"
                      "2. Seguridad -> Verificacion en dos pasos (debe estar activa)\n"
                      "3. Contrasenas de aplicaciones -> Generar\n"
                      "4. Copia los 16 caracteres y pegalo aqui",
                 font=FUENTES['pequena'], fg=COLORES['texto_secundario'],
                 bg=COLORES['fondo'], justify='left').pack(anchor='w', pady=(12, 0))

    # ── Carga de datos ───────────────────────────────────────────────────────

    def _cargar_reportes(self):
        try:
            with conexion_segura() as conn:
                rows = conn.execute("""
                    SELECT id_reporte, fecha, modulo, severidad,
                           descripcion, enviado
                    FROM reportes_errores
                    ORDER BY fecha DESC
                    LIMIT 200
                """).fetchall()
        except Exception as e:
            _log.error(f"Error cargando reportes: {e}")
            return

        for item in self.tree_hist.get_children():
            self.tree_hist.delete(item)
        for r in rows:
            estado = 'Enviado' if r['enviado'] else 'Pendiente'
            desc_corta = (r['descripcion'] or '')[:60]
            self.tree_hist.insert('', 'end', iid=str(r['id_reporte']),
                values=(r['fecha'][:16], r['modulo'] or '-',
                        r['severidad'], desc_corta, estado))

    def _on_hist_select(self, event=None):
        sel = self.tree_hist.selection()
        self._id_sel = int(sel[0]) if sel else None

    def _cargar_config_correo(self):
        try:
            with conexion_segura() as conn:
                rows = conn.execute(
                    "SELECT clave, valor FROM configuracion "
                    "WHERE clave IN ('smtp_servidor','smtp_puerto',"
                    "'smtp_usuario','smtp_password','soporte_email')"
                ).fetchall()
            vals = {r['clave']: r['valor'] for r in rows}
            for clave, entry in self._entries_config.items():
                entry.delete(0, tk.END)
                entry.insert(0, vals.get(clave, ''))
        except Exception as e:
            _log.error(f"Error cargando config correo: {e}")

    # ── Acciones formulario ──────────────────────────────────────────────────

    def _adjuntar_captura(self):
        ruta = filedialog.askopenfilename(
            title="Seleccionar captura de pantalla",
            filetypes=[
                ("Imagenes", "*.png *.jpg *.jpeg *.bmp *.gif *.webp"),
                ("Todos los archivos", "*.*")
            ]
        )
        if not ruta:
            return
        capturas_dir = os.path.join(BASE_DIR, 'data', 'capturas_errores')
        os.makedirs(capturas_dir, exist_ok=True)
        nombre = f"captura_{datetime.now().strftime('%Y%m%d_%H%M%S')}{os.path.splitext(ruta)[1]}"
        destino = os.path.join(capturas_dir, nombre)
        shutil.copy2(ruta, destino)
        self._ruta_captura_actual = destino
        self.lbl_captura.config(text=f"Adjunto: {nombre}",
                                fg=COLORES['exito'])
        self._mostrar_preview(destino)

    def _mostrar_preview(self, ruta):
        try:
            from PIL import Image, ImageTk
            img = Image.open(ruta)
            img.thumbnail((300, 180))
            photo = ImageTk.PhotoImage(img)
            self.lbl_preview.config(image=photo)
            self.lbl_preview.image = photo
        except Exception:
            self.lbl_preview.config(image='', text='(vista previa no disponible)')

    def _quitar_captura(self):
        self._ruta_captura_actual = None
        self.lbl_captura.config(text="Sin imagen adjunta",
                                fg=COLORES['texto_secundario'])
        self.lbl_preview.config(image='', text='')
        self.lbl_preview.image = None

    def _validar_formulario(self):
        desc = self.txt_desc.get('1.0', tk.END).strip()
        if len(desc) < 10:
            messagebox.showerror("Requerido",
                "La descripcion debe tener al menos 10 caracteres.")
            self.txt_desc.focus()
            return None
        return {
            'modulo':    self.var_modulo.get(),
            'severidad': self.var_severidad.get(),
            'descripcion': desc,
            'pasos':     self.txt_pasos.get('1.0', tk.END).strip() or None,
            'usuario':   self.usuario.get('usuario', ''),
            'ruta_captura': self._ruta_captura_actual,
        }

    def _guardar_en_bd(self, datos, enviado=0):
        with transaccion_atomica() as conn:
            conn.execute("""
                INSERT INTO reportes_errores
                    (modulo, severidad, descripcion, pasos,
                     usuario, enviado, ruta_captura)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (datos['modulo'], datos['severidad'],
                  datos['descripcion'], datos['pasos'],
                  datos['usuario'], enviado,
                  datos['ruta_captura']))
            return conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    def _guardar_y_enviar(self):
        datos = self._validar_formulario()
        if not datos:
            return
        try:
            id_rep = self._guardar_en_bd(datos, enviado=0)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo guardar el reporte: {e}")
            return

        exito = self._enviar_correo(datos, id_rep)
        if exito:
            try:
                with transaccion_atomica() as conn:
                    conn.execute(
                        "UPDATE reportes_errores SET enviado=1, "
                        "fecha_envio=datetime('now','localtime') WHERE id_reporte=?",
                        (id_rep,))
            except Exception:
                pass
            messagebox.showinfo("Listo",
                "Reporte guardado y enviado por correo correctamente.")
        else:
            messagebox.showwarning("Guardado sin enviar",
                "El reporte se guardo localmente pero NO se pudo enviar por correo.\n"
                "Revisa la configuracion del correo en la pestana 'Config. correo'.")
        self._limpiar_formulario()
        self._cargar_reportes()

    def _solo_guardar(self):
        datos = self._validar_formulario()
        if not datos:
            return
        try:
            self._guardar_en_bd(datos, enviado=0)
            messagebox.showinfo("Guardado",
                "Reporte guardado localmente. Puedes enviarlo despues desde el Historial.")
            self._limpiar_formulario()
            self._cargar_reportes()
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo guardar: {e}")

    def _limpiar_formulario(self):
        self.var_modulo.set(MODULOS[0])
        self.var_severidad.set('Medio')
        self.txt_desc.delete('1.0', tk.END)
        self.txt_pasos.delete('1.0', tk.END)
        self._quitar_captura()

    def _reenviar_seleccionado(self):
        if not self._id_sel:
            messagebox.showwarning("Selecciona", "Selecciona un reporte de la lista.")
            return
        try:
            with conexion_segura() as conn:
                row = conn.execute(
                    "SELECT * FROM reportes_errores WHERE id_reporte=?",
                    (self._id_sel,)).fetchone()
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo leer el reporte: {e}")
            return
        datos = dict(row)
        exito = self._enviar_correo(datos, datos['id_reporte'])
        if exito:
            try:
                with transaccion_atomica() as conn:
                    conn.execute(
                        "UPDATE reportes_errores SET enviado=1, "
                        "fecha_envio=datetime('now','localtime') WHERE id_reporte=?",
                        (self._id_sel,))
            except Exception:
                pass
            messagebox.showinfo("Enviado", "Reporte enviado correctamente.")
            self._cargar_reportes()
        else:
            messagebox.showerror("Error de envio",
                "No se pudo enviar. Revisa la configuracion del correo.")

    # ── Envío de correo ──────────────────────────────────────────────────────

    def _leer_config_smtp(self):
        try:
            with conexion_segura() as conn:
                rows = conn.execute(
                    "SELECT clave, valor FROM configuracion "
                    "WHERE clave IN ('smtp_servidor','smtp_puerto',"
                    "'smtp_usuario','smtp_password','soporte_email')"
                ).fetchall()
            return {r['clave']: r['valor'] for r in rows}
        except Exception:
            return {}

    def _enviar_correo(self, datos, id_reporte):
        cfg = self._leer_config_smtp()
        servidor  = cfg.get('smtp_servidor', '').strip()
        puerto    = int(cfg.get('smtp_puerto', 587) or 587)
        usuario   = cfg.get('smtp_usuario', '').strip()
        password  = cfg.get('smtp_password', '').strip()
        destino   = cfg.get('soporte_email', '').strip()

        if not all([servidor, usuario, password, destino]):
            return False

        try:
            sev  = datos.get('severidad') or datos.get('severidad', 'Medio')
            mod  = datos.get('modulo', '-')
            desc = datos.get('descripcion', '')
            pasos = datos.get('pasos') or 'No especificados'
            usr  = datos.get('usuario', '')
            fecha = datetime.now().strftime('%Y-%m-%d %H:%M')

            asunto = f"[POCITOS ERROR #{id_reporte}] [{sev}] {mod} — {desc[:60]}"

            cuerpo = f"""
==============================================
  REPORTE DE ERROR - POCITOS AZUFRADOS
==============================================

ID Reporte:   #{id_reporte}
Fecha:        {fecha}
Usuario:      {usr}
Modulo:       {mod}
Severidad:    {sev}

--- DESCRIPCION ---
{desc}

--- PASOS PARA REPRODUCIR ---
{pasos}

--- ARCHIVOS ADJUNTOS ---
- logs/errores.log (errores del sistema)
- logs/pocitos.log (log general)
{f'- Captura de pantalla adjunta' if datos.get('ruta_captura') else '- Sin captura adjunta'}

==============================================
Enviado automaticamente desde el sistema POS
Club Los Pocitos Azufrados
"""
            msg = MIMEMultipart()
            msg['From']    = usuario
            msg['To']      = destino
            msg['Subject'] = asunto
            msg.attach(MIMEText(cuerpo, 'plain', 'utf-8'))

            # Adjuntar logs
            for nombre_log in ['errores.log', 'pocitos.log']:
                ruta_log = os.path.join(BASE_DIR, 'logs', nombre_log)
                if os.path.exists(ruta_log):
                    self._adjuntar_archivo(msg, ruta_log, nombre_log)

            # Adjuntar captura si existe
            ruta_cap = datos.get('ruta_captura')
            if ruta_cap and os.path.exists(ruta_cap):
                self._adjuntar_archivo(msg, ruta_cap,
                                       os.path.basename(ruta_cap))

            with smtplib.SMTP(servidor, puerto, timeout=15) as smtp:
                smtp.ehlo()
                smtp.starttls()
                smtp.login(usuario, password)
                smtp.sendmail(usuario, destino, msg.as_string())

            _log.info(f"Reporte de error #{id_reporte} enviado a {destino}")
            return True

        except Exception as e:
            _log.error(f"Error enviando reporte por correo: {e}")
            return False

    def _adjuntar_archivo(self, msg, ruta, nombre):
        try:
            with open(ruta, 'rb') as f:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header('Content-Disposition',
                            f'attachment; filename="{nombre}"')
            msg.attach(part)
        except Exception as e:
            _log.warning(f"No se pudo adjuntar {nombre}: {e}")

    # ── Config correo ────────────────────────────────────────────────────────

    def _guardar_config_correo(self):
        try:
            with transaccion_atomica() as conn:
                for clave, entry in self._entries_config.items():
                    conn.execute(
                        "INSERT OR REPLACE INTO configuracion (clave, valor) "
                        "VALUES (?, ?)",
                        (clave, entry.get().strip()))
            messagebox.showinfo("Guardado",
                "Configuracion de correo guardada correctamente.")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo guardar: {e}")

    def _probar_conexion(self):
        cfg = self._leer_config_smtp()
        servidor = cfg.get('smtp_servidor', '').strip()
        puerto   = int(cfg.get('smtp_puerto', 587) or 587)
        usuario  = cfg.get('smtp_usuario', '').strip()
        password = cfg.get('smtp_password', '').strip()

        if not all([servidor, usuario, password]):
            messagebox.showwarning("Incompleto",
                "Completa servidor, usuario y contrasena antes de probar.")
            return
        try:
            with smtplib.SMTP(servidor, puerto, timeout=10) as smtp:
                smtp.ehlo()
                smtp.starttls()
                smtp.login(usuario, password)
            messagebox.showinfo("Conexion exitosa",
                f"Conexion a {servidor}:{puerto} correcta.\n"
                "El correo esta listo para enviar reportes.")
        except Exception as e:
            messagebox.showerror("Error de conexion",
                f"No se pudo conectar:\n{e}\n\n"
                "Verifica que usas una App Password de Gmail\n"
                "y que el servidor/puerto son correctos.")

    def detener(self):
        pass
