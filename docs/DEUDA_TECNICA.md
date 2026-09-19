# Deuda Técnica — Pocitos Azufrados POS
_Última actualización: 2026-05-17_

Diagnóstico completo del sistema. Los ítems marcados ✅ ya fueron corregidos.

---

## Prioridad ALTA — Riesgo de pérdida de datos o bugs silenciosos en producción

### DT-01 — `except Exception: pass` en operaciones críticas
**Archivos:** `pos_module.py` (líneas 180, 486, 625, 649, 912, 1160, 1868, 1997, 2005),
`caja_module.py` (586, 590, 703), `cocina_module.py` (624, 635, 648, 659, 708, 719, 727, 733, 740),
`dashboard.py` (62, 375, 388, 395, 409, 836, 849, 856, 986, 1102, 1117),
`dashboard_cajero.py` (30, 61, 270, 309, 318, 371, 385, 501, 515, 524), y otros.

**Impacto:** Los errores desaparecen silenciosamente. Un fallo en el POS durante una venta, en
caja durante el cierre, o en cocina durante un pedido no aparece en ningún log. El sistema parece
funcionar cuando en realidad falló una operación.

**Nota:** NO tocar los `pass` en métodos `detener()` — ahí son intencionales (el widget puede
no existir al momento del unbind). Solo atacar los que están dentro de operaciones de negocio.

**Cuándo atacarlo:** En la próxima iteración de cada módulo. Cambio mínimo: reemplazar `pass`
por `logging.getLogger("pocitos").warning(f"...: {e}")`. No requiere refactor.

---

### DT-02 — Métodos de pago con inconsistencia activa entre módulos
**Archivos:** `socios_module.py` (línea 21), `gastos_module.py` (línea 20),
`proveedores_module.py` (línea 18), `pagos_module.py` (línea 29).

**Impacto:** ✅ `socios_module.py` ya corregido (faltaba BANCOLOMBIA). El problema raíz
persiste: hay 4 listas hardcodeadas en lugar de una sola fuente de verdad. Si en Configuración
se agrega un nuevo método de pago, no aparece en Socios (que ignora la BD).

**Cuándo atacarlo:** Cuando se toque `socios_module.py` por otra razón. La corrección es
reemplazar la lista estática por una llamada a `_leer_metodos_pago()` igual a la que ya usan
los otros módulos (~8 líneas). Sin refactor.

---

### DT-03 — `SELECT *` en queries sobre tablas con migraciones frecuentes
**Archivos:** `caja_module.py:183`, `categorias_module.py:551`, `login.py:226,300`,
`pos_module.py:709`, `pedidos_module.py:198` y ~5 más.

**Impacto:** Cada vez que una migración agrega una columna, estas queries retornan una columna
extra. Si algún código consume las filas por posición (índice numérico en vez de nombre), se
rompe silenciosamente. El riesgo aumenta con cada `SCHEMA_VERSION`.

**Cuándo atacarlo:** Antes de agregar la próxima columna a cualquiera de las tablas afectadas
(`caja_diaria`, `productos`, `usuarios`, `ventas`). Cambio mecánico: listar columnas explícitas.

---

### DT-04 — Audit log usa `str()` en vez de JSON ✅ CORREGIDO
**Archivo:** `utils/logger.py:93`

**Impacto antes de corrección:** `datos_anteriores` y `datos_nuevos` se guardaban como
`str(dict)` (ej. `"{'precio': 5000, 'nombre': \"Aguardiente\"}"`) — imposible parsear con
herramientas estándar. Cada auditoría era irrecuperable si se necesitaba comparar estados.

**Estado:** Corregido a `json.dumps(..., default=str)`. Los registros históricos anteriores
a 2026-03-28 siguen en formato `str()`; los nuevos son JSON válido.

---

## Prioridad MEDIA — Mantenibilidad y riesgo de regresión al hacer cambios

### DT-05 — `pos_module.py` es un monolito de 2.006 líneas (~80 métodos)
**Archivo:** `modules/pos_module.py`

**Impacto:** Es el módulo más crítico y el más difícil de modificar. Cualquier cambio en el
flujo de pago requiere leer ~2.000 líneas para entender el contexto. La lógica del carrito,
el procesamiento de pagos, las órdenes de cocina y la UI están entrelazadas. No tiene tests.

**Cuándo atacarlo:** Solo cuando haya un período de baja operación (ej. semana sin eventos).
Extracción sugerida: `CartManager` (agrega/quita/calcula) como clase sin dependencias de
Tkinter — esto lo haría testeable sin tocar la UI.

**Riesgo del refactor:** ALTO. Requiere regresión completa del flujo de venta.

---

### DT-06 — Sidebar duplicado en los 3 dashboards
**Archivos:** `dashboard.py`, `dashboard_cajero.py`, `dashboard_contadora.py`

**Impacto:** Cambiar el color, fuente o comportamiento del sidebar requiere tocar 3 archivos.
Ya ocurrió al menos una divergencia: `dashboard_contadora.py` abre módulos en `Toplevel`
mientras los otros usan `content_frame`.

**Cuándo atacarlo:** Cuando se necesite cambiar algo visual del sidebar. Extraer
`_construir_sidebar()` a `utils/tema_corporativo.py` o a una clase base.

---

### DT-07 — Umbrales DIAN hardcodeados, no configurables
**Archivo:** `models/validaciones.py` líneas 26–98

**Valores hardcodeados:**
- Advertencia: ≤ 500 facturas restantes
- Bloqueo: ≤ 50 facturas restantes
- Bloqueo: ≤ 3 días para vencimiento
- Advertencia: ≤ 30 días para vencimiento

**Impacto:** Si la DIAN o el contador cambia los umbrales recomendados, requiere editar código
y recompilar el exe. Debería vivir en la tabla `configuracion`.

**Cuándo atacarlo:** Cuando se venza la próxima resolución DIAN y haya que renovar la config.
Cambio pequeño: mover 4 constantes a `configuracion` con valores por defecto.

---

### DT-08 — Cobertura de tests: ~3% de lógica de negocio, 0% de UI
**Estado parcial ✅** — `models/ventas.py` ahora tiene 27 tests. Total: 70 tests.

**Archivos de test:** `test_ventas.py` (27), `test_financiero.py` (9), `test_series.py`,
`test_validaciones.py`, `test_connection.py`, `test_dia_completo_vendedor.py`, `test_pos_integracion.py`.

**Cobertura actual:**
- `models/ventas.py` — buena (27 casos: pagos, stock, cocina, FE, rollback)
- `models/series.py`, `models/validaciones.py` — cubiertos
- `models/inventario.py` — sin tests dedicados
- `caja_module.py`, `gastos_module.py`, `boletas_module.py`, `cocina_module.py` — sin ningún test

**Sin test de UI** — 0 tests con Tkinter. Ningún test verifica que los widgets se rendericen,
que los popups aparezcan, o que los flujos de navegación entre módulos funcionen.

**Cuándo atacarlo:** Priorizar `models/inventario.py` (sin tests), luego `caja_module` como
integración. No intentar testear la UI de Tkinter directamente — demasiado frágil. Objetivo
siguiente: tests para los modelos pendientes de extracción (caja, gastos, boletas).

---

### DT-09 — `dashboard_contadora.py` usa `Toplevel`; los otros usan `content_frame`
**Archivos:** `dashboard_contadora.py` vs `dashboard.py` / `dashboard_cajero.py`

**Impacto:** Comportamiento inconsistente: en los dashboards estándar los módulos se abren
dentro de la ventana principal; en el de contadora se abren como ventanas separadas. Si el
módulo no implementa correctamente `detener()`, en contadora se acumulan ventanas sin cerrar.

**Cuándo atacarlo:** Si hay quejas de comportamiento errático en el dashboard de contadora
(ventanas que no cierran, memoria que crece). Cambio moderado (1–2 horas).

---

### DT-10 — Excepción silenciosa en lectura de config de inicio ✅ CORREGIDO (parcialmente)
**Archivos:** `boletas_module.py:41`, `gastos_module.py:40`, `proveedores_module.py:30`,
`pagos_module.py:27`

**Estado:** Corregido. Ahora estas excepciones emiten `WARNING` en `pocitos.log` en lugar
de desaparecer. El fallback a valores por defecto se mantiene.

**Pendiente (DT-01):** Los `pass` dentro de operaciones de negocio (no lecturas de config)
siguen silenciosos.

---

## Prioridad BAJA — Deuda de diseño, impacto en escalabilidad futura

### DT-11 — Módulo legacy sin uso confirmado ✅ RESUELTO
**Archivo:** `modules/_legacy/buscador_ventas.py` (eliminado 2026-05-17)

Confirmado huérfano. Eliminado junto con la carpeta `modules/_legacy/`.

---

### DT-12 — `config_module.py` mezcla configuración de negocio, sistema y usuarios
**Archivo:** `modules/config_module.py` (1.024 líneas)

**Impacto:** Para cambiar cómo se configura la DIAN hay que leer ~1.000 líneas que también
manejan impresoras, backups y contraseñas. Bajo riesgo hoy; problemático si crece.

**Cuándo atacarlo:** Si se agrega una nueva sección de configuración. Separar en pestañas
dentro del mismo módulo no requiere refactor de modelo.

---

### DT-13 — `models/` incompleto — extracción parcial de lógica de BD
**Estado parcial ✅** — `pos_module.py` e `inventario_module.py` ya refactorizados a `models/ventas.py`
y `models/inventario.py` (2026-05-17, DT-10 cerrado).

**Pendiente:** Los demás módulos (`caja_module`, `gastos_module`, `boletas_module`, `cocina_module`, etc.)
siguen ejecutando SQL directamente con `conexion_segura()`. Si cambia el esquema, hay que rastrear
las queries en los módulos uno por uno.

**Cuándo atacarlo:** Priorizar `caja_module` (el más crítico) y `boletas_module` (menor riesgo).
Seguir el mismo patrón: extraer a `models/caja.py`, `models/boletas.py` con `db_path=None` y tests.

---

### DT-14 — Schema de BD duplicado en 3 lugares
**Archivos:** `setup.py`, `main.py:aplicar_migraciones()`, y cada fixture de test en `tests/`

**Impacto:** Frágil: `conftest.py` puede usar nombres de columna distintos a `setup.py`
(ej. `costo` vs `precio_costo`). Una columna nueva en `setup.py` que no se refleje en la
fixture silencia el error hasta que alguien corre ese test específico contra la BD real.

**Cuándo atacarlo:** Al agregar la próxima columna. Crear un helper `tests/schema_helpers.py`
que ejecute el mismo `CREATE TABLE` de `setup.py` (o leer el DDL desde un archivo compartido).

---

### DT-15 — Acoplamiento módulo-BD vía `get_connection()` directo
**Archivos:** `cocina_module.py:_cargar_pedidos()` y posibles usos dispersos.

**Impacto:** `get_connection()` no usa context manager, requiere `try/finally conn.close()`
manual. Si el bloque `finally` falla o se omite, la conexión queda abierta. La guía interna lo
documenta como anti-patrón con una sola excepción aceptada (`cocina_module`). Verificar que
no haya otros usos no documentados.

**Cuándo atacarlo:** Auditar con `grep -r "get_connection()" modules/`. Para `cocina_module`
la excepción es válida (su `except` dibuja un `Label` en la UI, incompatible con el re-raise
de `conexion_segura`); el resto debe migrarse a `conexion_segura()`.

---

### DT-16 — Concurrencia Flask + SQLite en un solo proceso
**Archivos:** `cocina_web/app.py`, `main.py:iniciar_cocina_web()`

**Impacto:** El servidor Flask comparte la BD SQLite con la app de escritorio. Con WAL mode
funciona en la mayoría de casos, pero dos escrituras simultáneas (p.ej. cierre de caja mientras
la web actualiza una reserva) pueden causar `database is locked` con `busy_timeout=60s`.
Bajo volumen actual es aceptable; problemático si se agregan más clientes web concurrentes.

**Cuándo atacarlo:** Si aparecen errores `database is locked` en producción. Solución mínima:
aumentar `busy_timeout`. Solución estructural: cola de escrituras o Dockerizar `cocina_web`
con su propia conexión de solo lectura.

---

## Recomendaciones (2026-05-17)

| Prioridad | Acción | Impacto |
|-----------|--------|---------|
| Alta | Estandarizar schema de tests — crear helper compartido con `setup.py` | Tests más confiables, menos falsos positivos |
| Alta | Extraer `caja_module`, `gastos_module`, `boletas_module`, `cocina_module` a `models/` | Centraliza lógica de BD, facilita cambios de esquema |
| Media | Auditar y reemplazar `get_connection()` directo en todos los módulos | Elimina fugas de conexión, código consistente |
| Media | Agregar tests para `models/inventario.py` (actualmente sin cobertura) | Cierra el hueco más obvio de DT-08 |
| Media | Unificar constantes mágicas (umbral $50k PIN admin, $20k descuento, etc.) en `models/validaciones.py` o `configuracion` | Configurable sin tocar código |
| Baja | Agregar type hints a `models/` y `database/` | Mejora mantenibilidad, permite `mypy` |
| Baja | Evaluar Dockerizar `cocina_web` para despliegue separado opcional | Desacopla concurrencia Flask/SQLite |

---

## Resumen ejecutivo

| ID | Descripción corta | Estado | Riesgo si no se atiende |
|----|-------------------|--------|------------------------|
| DT-01 | `pass` silencioso en operaciones de negocio | Pendiente | Alto — bugs invisibles |
| DT-02 | Métodos de pago duplicados / inconsistentes | Parcial ✅ | Medio — datos incorrectos en socios |
| DT-03 | `SELECT *` en tablas con migraciones | Pendiente | Medio — regresión en próxima migración |
| DT-04 | Audit log sin JSON | ✅ Resuelto | — |
| DT-05 | `pos_module.py` monolito | Pendiente | Medio — costo alto de cambios |
| DT-06 | Sidebar triplicado | Pendiente | Bajo — solo cosmético |
| DT-07 | Umbrales DIAN hardcodeados | Pendiente | Bajo — requiere recompilación para cambiarlos |
| DT-08 | Cobertura de tests baja (0% UI, parcial models/) | Parcial ✅ | Medio — sin red de seguridad en UI |
| DT-09 | Comportamiento inconsistente en contadora | Pendiente | Bajo — ya conocido |
| DT-10 | `pass` en lecturas de config | ✅ Resuelto | — |
| DT-11 | Módulo legacy `_legacy/` | ✅ Resuelto | — |
| DT-12 | `config_module.py` mezcla concerns | Pendiente | Bajo |
| DT-13 | `models/` incompleto — extracción parcial | Parcial ✅ | Medio — queries dispersas en módulos |
| DT-14 | Schema BD duplicado en 3 lugares | Pendiente | Medio — fixtures desincronizadas |
| DT-15 | `get_connection()` directo en módulos | Pendiente | Bajo — fugas de conexión |
| DT-16 | Concurrencia Flask + SQLite proceso único | Pendiente | Bajo hoy, medio si escala |
