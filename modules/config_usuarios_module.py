"""
Módulo unificado: Configuración + Usuarios
Wrapper Notebook que combina ambos módulos en un solo panel con tabs.
"""
import tkinter as tk
from tkinter import ttk
import os, sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from utils.tema_corporativo import COLORES, FUENTES


class ConfigUsuariosModule:
    """Pestañas de Configuración y Usuarios en un solo panel."""
    def __init__(self, parent, usuario):
        self.parent = parent
        self.usuario = usuario
        self._instancias = []

        style = ttk.Style()
        style.configure("ConfigUsr.TNotebook",
                        background=COLORES['fondo'], borderwidth=0)
        style.configure("ConfigUsr.TNotebook.Tab",
                        font=FUENTES['normal_bold'],
                        background=COLORES['fondo_sidebar'],
                        foreground=COLORES['texto_secundario'],
                        padding=(16, 8))
        style.map("ConfigUsr.TNotebook.Tab",
                  background=[('selected', COLORES['primario'])],
                  foreground=[('selected', COLORES['acento'])])

        self.notebook = ttk.Notebook(parent, style="ConfigUsr.TNotebook")
        self.notebook.pack(fill='both', expand=True)

        self._crear_tab_config()
        self._crear_tab_usuarios()

    def _crear_tab_config(self):
        frame = tk.Frame(self.notebook, bg=COLORES['fondo'])
        self.notebook.add(frame, text='  Configuracion  ')
        from modules.config_module import ConfigModule
        inst = ConfigModule(frame, self.usuario)
        self._instancias.append(inst)

    def _crear_tab_usuarios(self):
        frame = tk.Frame(self.notebook, bg=COLORES['fondo'])
        self.notebook.add(frame, text='  Usuarios  ')
        from modules.usuarios_module import UsuariosModule
        inst = UsuariosModule(frame, self.usuario)
        self._instancias.append(inst)

    def detener(self):
        for inst in self._instancias:
            if hasattr(inst, 'detener'):
                try:
                    inst.detener()
                except Exception:
                    pass
