# ADR-002 — Tkinter como Framework de UI de Escritorio

**Estado**: Aceptado
**Fecha**: 2024 (inicial)
**Decisores**: Equipo de desarrollo

---

## Contexto

Se necesita una aplicación de escritorio para Windows 10/11 que funcione offline, con acceso a hardware local (escáner USB, impresora), y que no requiera instalación compleja por parte del negocio.

## Decisión

Usar **Tkinter** (biblioteca estándar de Python) como framework de interfaz gráfica de escritorio.

## Alternativas consideradas

| Opción | Pros | Contras |
|--------|------|---------|
| **Tkinter** ← elegida | Stdlib — sin deps extra. Liviano. Funciona en cualquier Python. | Estética limitada. No nativo. Widgets básicos. |
| PyQt6 / PySide6 | Rico en widgets. Nativo. Estética moderna. | Licencia comercial (Qt). Binarios grandes. |
| wxPython | Look nativo. Maduro. | Instalación compleja en Windows. |
| Electron / Tauri | UI web moderna. Ecosistema JS. | Runtime pesado (Chromium). Requiere Node.js. |
| Flask + navegador | Familiar para web devs. | Requiere servidor local. Más complejo. |
| Kivy | Moderno. Multi-plataforma + móvil. | Curva de aprendizaje alta. |

## Consecuencias

**Positivas:**
- Sin dependencias adicionales para la UI — Tkinter viene con Python
- Acceso directo al sistema operativo (abrir PDFs, rutas de archivo)
- Compatible con escáner USB (HID → `bind('<Return>', ...)` en Entry)
- Instalación simple: `pip install -r requirements.txt` + ejecutar `main.py`

**Negativas:**
- La estética requiere esfuerzo manual (ver `utils/tema_corporativo.py`)
- No hay componentes modernos nativos — todo construido con `Frame`, `Label`, `Button`, `ttk.Treeview`
- Los emojis no se renderizan en color en Windows/GDI (motivo por el cual se evitan en la UI)

## Decisión de tema visual

Dado que Tkinter no ofrece tema moderno por defecto, se creó `utils/tema_corporativo.py` como fuente única de verdad para colores, fuentes y helpers. El tema actual es "Bosque Moderno": sidebar verde oscuro + contenido blanco + acento lima neon (`#AAFF00`).
