"""
Modulo unificado Inventario + Categorias
Agrupa ambos en un Notebook con dos pestanas:
  - Productos (InventarioModule)
  - Categorias (CategoriasModule)
"""

import tkinter as tk
from tkinter import ttk
import os, sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from utils.tema_corporativo import COLORES, FUENTES


class InventarioCategoriasModule:
    """Pestañas de Productos y Categorías en un solo panel."""
    def __init__(self, parent, usuario):
        self.parent = parent
        self.usuario = usuario
        self._instancias = []

        style = ttk.Style()
        style.configure("InvCat.TNotebook",
                        background=COLORES['fondo'],
                        borderwidth=0)
        style.configure("InvCat.TNotebook.Tab",
                        font=FUENTES['normal_bold'],
                        background=COLORES['fondo_sidebar'],
                        foreground=COLORES['texto_secundario'],
                        padding=(18, 8))
        style.map("InvCat.TNotebook.Tab",
                  background=[('selected', COLORES['primario'])],
                  foreground=[('selected', COLORES['acento'])])

        self.notebook = ttk.Notebook(parent, style="InvCat.TNotebook")
        self.notebook.pack(fill='both', expand=True)

        self._crear_tab_inventario()
        self._crear_tab_categorias()

    def _crear_tab_inventario(self):
        frame = tk.Frame(self.notebook, bg=COLORES['fondo'])
        self.notebook.add(frame, text='  Productos  ')
        from modules.inventario_module import InventarioModule
        inst = InventarioModule(frame, self.usuario)
        self._instancias.append(inst)

    def _crear_tab_categorias(self):
        frame = tk.Frame(self.notebook, bg=COLORES['fondo'])
        self.notebook.add(frame, text='  Categorias  ')
        from modules.categorias_module import CategoriasModule
        inst = CategoriasModule(frame, self.usuario)
        self._instancias.append(inst)

    def detener(self):
        for inst in self._instancias:
            if hasattr(inst, 'detener'):
                try:
                    inst.detener()
                except Exception:
                    pass
