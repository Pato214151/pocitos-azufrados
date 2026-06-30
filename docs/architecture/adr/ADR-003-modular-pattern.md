# ADR-003 — Patrón de Módulos Cargados Dinámicamente

**Estado**: Aceptado
**Fecha**: 2024 (inicial)
**Decisores**: Equipo de desarrollo

---

## Contexto

La aplicación tiene más de 20 funcionalidades distintas. Se necesita una forma de navegar entre ellas sin abrir múltiples ventanas y sin cargar todo al inicio.

## Decisión

Cada funcionalidad es una **clase Python** que recibe `(parent: tk.Frame, usuario: dict)` y dibuja su UI dentro de ese frame. El dashboard destruye y recrea el módulo activo al navegar.

```python
def _abrir_modulo(self, nombre, clase_modulo, *args):
    self._limpiar_contenido()          # Destruye widgets + llama detener()
    self._marcar_menu(nombre)          # Resalta ítem activo en sidebar
    self._instancia_modulo = clase_modulo(self.content_frame, self.usuario, *args)
```

Los imports son **lazy** (dentro del método `_abrir_*`):
```python
def _abrir_bar(self):
    from modules.pos_module import POSModule   # ← import solo cuando se abre
    self._abrir_modulo("Bar", POSModule)
```

## Alternativas consideradas

| Opción | Pros | Contras |
|--------|------|---------|
| **Un frame por módulo, carga dinámica** ← elegida | Bajo consumo de memoria. Fácil de añadir módulos. | Recarga al navegar (no conserva estado). |
| Múltiples ventanas Toplevel | Estado independiente por módulo. | UX confusa. Gestión de z-order. |
| Todos los módulos cargados al inicio | Navegación instantánea. | Alto consumo de memoria. Arranque lento. |
| `ttk.Notebook` global | Tabs familiares. Estado persistente. | Sidebar sería redundante. Limitado para 20+ módulos. |

## Consecuencias

**Positivas:**
- Arranque rápido (imports lazy)
- Bajo consumo de RAM (solo un módulo activo a la vez)
- Fácil agregar módulos sin tocar el dashboard (solo añadir entrada de menú y método `_abrir_*`)
- Cada módulo es independiente y testeable aisladamente

**Negativas:**
- Al navegar, el estado del módulo anterior se pierde (filtros, selección actual)
- Los módulos con `after()` (auto-refresh) DEBEN implementar `detener()` — convención no forzada por el tipo
- Módulos grandes (>1000 líneas) mezclan UI y lógica de negocio (trade-off vs complejidad de capas)

## Convención obligatoria para auto-refresh

```python
class MiModuloConRefresh:
    def __init__(self, parent, usuario):
        self.auto_refresh = True
        self._after_id = None
        self._iniciar_refresh()

    def _iniciar_refresh(self):
        if self.auto_refresh:
            self._after_id = self.parent.winfo_toplevel().after(
                10000, self._cargar_datos_y_refrescar
            )

    def detener(self):               # ← OBLIGATORIO si usa after()
        self.auto_refresh = False
        if self._after_id:
            try:
                self.parent.winfo_toplevel().after_cancel(self._after_id)
            except Exception:
                pass
```
