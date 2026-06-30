# ADR-005 — Migración de Tema Oscuro a Tema Claro Moderno

**Estado**: Aceptado
**Fecha**: 2026-03-22
**Decisores**: Propietario del negocio · Equipo de desarrollo

---

## Contexto

El tema original ("Azufre & Naturaleza") era un dark theme con fondo `#1a1f14` y acento amarillo azufre `#FDD835`. Tras comparar con aplicaciones modernas de referencia (Treinta, Linear, Notion), el propietario solicitó una interfaz más "actual, pasiva y con verde limón/neon".

## Decisión

Migrar a un tema "Bosque Moderno" con:
- **Sidebar** verde bosque oscuro (`#0D4020`) — mantiene identidad de marca
- **Contenido** blanco puro (`#FFFFFF`) / casi blanco (`#F4F9F4`)
- **Acento** lima neon (`#AAFF00`) — el nuevo color firma
- **Texto** casi negro (`#0D1A0D`) sobre blanco

## Cambios realizados

| Archivo | Cambio |
|---------|--------|
| `utils/tema_corporativo.py` | Paleta completa reescrita. `crear_boton()` actualizado. `aplicar_estilo_tabla()` adaptado para fondo claro. |
| `modules/gastos_module.py` | Headers `bg=COLORES['acento']` → `bg=COLORES['primario']` (blanco sobre lima era ilegible) |
| `modules/pedidos_module.py` | Ídem |
| `modules/cocina_module.py` | Ídem |
| `modules/caja_module.py` | Ídem |
| `modules/categorias_module.py` | Badge: `fg='white'` → `fg='#0D1A0D'` (texto oscuro sobre lima neon) |

## Problema resuelto: contraste en headers

El acento lima (`#AAFF00`) tiene ratio ~1.2:1 con blanco — completamente ilegible. La solución fue:
- `COLORES['acento']` = lima neon → **solo para accents** (barras 3px, active states, focus borders)
- `COLORES['primario']` = verde oscuro → **para fondos con texto blanco**

```
Barra acento 3px en cards      → lima neon   ✓ (decorativo)
Header de módulo con texto     → primario    ✓ (contraste ~6:1 con blanco)
Item activo sidebar            → primario bg + acento text  ✓ (~8:1)
Heading Treeview               → primario_oscuro bg + acento text ✓
```

## Alternativas descartadas

| Opción | Razón del descarte |
|--------|-------------------|
| Mantener dark theme | Usuario explícitamente pidió cambio a blanco |
| Neon verde (#00FF00) puro | Demasiado agresivo. Lima (`#AAFF00`) es más legible |
| Tema completamente blanco sin sidebar oscuro | Sidebar claro pierde distinción visual entre menú y contenido |

## Impacto en mantenimiento

- Todo módulo futuro debe usar `COLORES['primario']` (no `acento`) para fondos con texto blanco
- `acento` es solo para efectos visuales: barras de color, borders de focus, estado activo
- No usar `fg='white'` hardcodeado — usar `COLORES['texto_claro']` para que respete el tema
