# ROADMAP — Club Los Pocitos Azufrados POS
Auditoría completa · 47 ítems · 5 niveles de prioridad
Última actualización: 2026-03-22

---

## DECISIONES DE NEGOCIO REGISTRADAS

| Decisión | Valor | Fecha |
|---|---|---|
| Clave acceso cocina web | `cocina2025` | 2026-03-22 |
| buscador_ventas.py | Legacy — no está en ningún menú, se deja como archivo muerto | 2026-03-22 |
| Usuario contadora | Sigue detectándose por nombre de usuario, no por rol | 2026-03-22 |
| Dirección en recibos | `Tocaima, Cundinamarca` (ya correcto en código) | 2026-03-22 |
| Backup en nube | Pendiente decisión — de momento ruta local o carpeta Drive/OneDrive sincronizada | — |
| 2do terminal | Pendiente — definir antes de producción | — |

---

## NIVEL 0 — CRÍTICO (bloquea operación segura)

> **Meta**: completar ANTES del primer turno en producción.

| # | Ítem | Archivo(s) | Estado |
|---|---|---|---|
| C-1 | Autenticación en cocina_web — HTTP Basic Auth con clave `cocina2025` | `cocina_web/app.py` | ✅ 2026-03-22 |
| C-2 | SHA-256 fallback silencioso — bloquear login si bcrypt no disponible, loguear error | `modules/login.py` | ✅ 2026-03-22 |
| C-3 | Backup sin verificación — `PRAGMA integrity_check` ya en `main.py` + indicador visible en sidebar del dashboard | `modules/dashboard.py` | ✅ 2026-03-22 |

---

## NIVEL 1 — ALTO (riesgo operativo real) — ALTO [███████████] 11/11 ✅ Completo

> **Meta**: completar en la primera semana de uso.

### Estabilidad y bugs silenciosos

| # | Ítem | Archivo(s) | Estado |
|---|---|---|---|
| A-1 | `bare except` en migraciones — capturar `Exception as e` + log + mensaje usuario | `main.py ~L151` | ✅ 2026-03-22 |
| A-2 | `bare except` en backup daemon — misma corrección | `main.py ~L215` | ✅ 2026-03-22 |
| A-3 | `bare except` en `ejecutar_con_retry()` — log explícito | `database/connection.py ~L65` | ✅ Ya correcto |
| A-4 | `bare except` en `_abrir_pdf()` — loguear y mostrar ruta al usuario | `utils/printing.py` | ✅ Ya correcto |

### Auto-refresh sin `detener()`

| # | Ítem | Archivo(s) | Estado |
|---|---|---|---|
| A-5 | `CuentasAbiertasModule` — verificar e implementar `detener()` si falta | `modules/cuentas_abiertas_module.py` | ✅ Ya implementado |
| A-6 | Auditoría de todos los módulos con `after()` | Todos los módulos | ✅ 2026-03-22 |

### Acceso directo a BD

| # | Ítem | Archivo(s) | Estado |
|---|---|---|---|
| A-7 | `get_connection()` directo — reemplazar con `conexion_segura()` en todos los módulos | 4 archivos corregidos | ✅ 2026-03-22 |
| A-8 | Auditar todos los módulos: buscar `get_connection()` fuera de `database/connection.py` | Todos los módulos | ✅ 2026-03-22 |

### Configuración inconsistente

| # | Ítem | Archivo(s) | Estado |
|---|---|---|---|
| A-9 | Métodos de pago hardcodeados en gastos — leer de `configuracion` en BD | `modules/gastos_module.py` | ✅ Ya implementado |
| A-10 | Métodos de pago hardcodeados en proveedores — misma corrección | `modules/proveedores_module.py` | ✅ Ya implementado |
| A-11 | `config_module.py` — validar ruta de backup antes de guardar | `modules/config_module.py` | ✅ Ya manejado (makedirs + try/except) |

---

## NIVEL 2 — MEDIO (deuda técnica)

> **Meta**: sprint próximo (primeras 2 semanas de uso).

### Código duplicado / muerto

| # | Ítem | Estado |
|---|---|---|
| M-1 | `buscador_ventas.py` es legacy — mover a `_legacy/` | ✅ 2026-03-22 — movido a `modules/_legacy/` |
| M-2 | Limpiar dependencias huérfanas: `requests`, `python-barcode`, `Pillow` | ✅ Ya limpio (comentados desde sesión anterior) |

### Módulos grandes

| # | Ítem | Estado |
|---|---|---|
| M-3 | `pos_module.py` (1296 líneas) — separar carrito, variantes y lógica de venta | ⏳ Diferido — riesgo alto sin tests de UI |
| M-4 | `inventario_module.py` (1289 líneas) — separar carga masiva CSV/Excel | ⏳ Diferido |
| M-5 | `categorias_module.py` (1057 líneas) — simplificar si posible | ⏳ Diferido |

### Tests

| # | Ítem | Estado |
|---|---|---|
| M-6 | Estructura `tests/` con pytest | ✅ 2026-03-22 — `tests/`, `conftest.py`, `pytest.ini` |
| M-7 | Tests de lógica financiera (totales, caja, gastos) contra BD `:memory:` | ✅ 2026-03-22 — 9 tests en `test_financiero.py` |
| M-8 | Tests de `models/series.py` y `database/connection.py` | ✅ 2026-03-22 — 6 tests series + 6 tests conexión |
| M-9 | `pytest.ini` mínimo | ✅ 2026-03-22 — 21/21 tests pasan |

### Migración y schema

| # | Ítem | Estado |
|---|---|---|
| M-10 | Verificación de divergencia `setup.py` ↔ `main.py` al arrancar | ✅ 2026-03-22 — `SCHEMA_VERSION = 2` en `main.py` |
| M-11 | Clave `schema_version` en tabla `configuracion` | ✅ 2026-03-22 — se actualiza en cada migración |

### Seguridad adicional

| # | Ítem | Estado |
|---|---|---|
| M-12 | `usuarios_module.py` — confirmar contraseña del admin para cambio de rol o reset | ✅ 2026-03-22 — `_confirmar_admin()` + bcrypt en reset |
| M-13 | Sesiones sin expiración — verificar invalidación al relog | ✅ 2026-03-22 — `_registrar_sesion()` cierra sesiones abiertas previas |

---

## NIVEL 3 — BAJO (calidad y mantenibilidad)

> **Meta**: backlog activo, atacar cuando se toque el archivo por otra razón.

| # | Ítem | Estado |
|---|---|---|
| B-1 | `tema_corporativo.py` — `'Segoe UI'` hardcodeado en `crear_tarjeta_kpi()` | ✅ Ya resuelto — no aparece en fuentes |
| B-2 | `dashboard_cajero.py` — `'Segoe UI'` hardcodeado en header | ✅ Ya resuelto — no aparece en fuentes |
| B-3 | Auditar emoji en widgets Tkinter (Label, Button, Treeview) — no se renderizan en color en Windows | ⬜ Pendiente |
| B-4 | `cocina_web/app.py` — HTML/CSS inline → mover a templates Jinja2 y estáticos | ⬜ Pendiente |
| B-5 | Actualización cocina web configurable (actualmente 15s fija) | ⬜ Pendiente |
| B-6 | `requirements.txt` — agregar comentario `# Requiere Python 3.9+` | ⬜ Pendiente |

---

## NIVEL 4 — VISIÓN (3–18 meses)

| # | Ítem | Notas |
|---|---|---|
| V-1 | Backup al inicio de sesión (además del nocturno) | Garantiza snapshot antes de cada turno |
| V-2 | Indicador de backup en dashboard (fecha último exitoso, alerta si >24h) | Depende de C-3 |
| V-3 | Documentar formalmente la estrategia ante un 2do terminal | Decidir arquitectura antes de que lo pidan en producción |
| V-4 | Usuario `contadora` → flag `rol = 'propietario'` en tabla `usuarios` | Eliminar dependencia del nombre hardcodeado |
| V-5 | Paginación en reportes (queries sin LIMIT bloquearán UI con BD grande) | Urgente en 1-2 años de operación |
| V-6 | Extraer lógica de negocio a módulos puros (testing sin Tkinter) | Habilita M-7 y M-8 realmente |

---

## PROGRESO GENERAL

```
CRÍTICO  [██████] 3/3  ✅ Completo
ALTO     [███████████] 11/11 ✅ Completo
MEDIO    [██████████] 10/13 (3 diferidos — refactor módulos grandes)
BAJO     [████] 2/6 + 2 resueltos implícitamente
VISIÓN   [░░░░░░] 0/6
─────────────────────────
TOTAL    3/39 implementados (8 ya estaban antes de la auditoría)
```

---

## NOTAS DE ARQUITECTURA

### Por qué no se usa un servidor central
El sistema es **single-terminal intencionalmente**: SQLite sin servidor, todo local, sin dependencia de red. Esto es correcto para el volumen actual (1 caja, 1 cocina). Si se necesita un 2do terminal simultáneo, la opción menos costosa es migrar a **PostgreSQL local** con un servidor en el mismo PC y clientes en red.

### Cocina web vs 2do terminal
`cocina_web` NO es un 2do terminal de ventas — es solo visualización y actualización de estados de cocina. Esto está bien. El riesgo es que alguien lo trate como un terminal completo; documentar claramente qué puede y qué no puede hacer.

### Backup recomendado
La solución más simple: apuntar `backup_ruta` a una carpeta de Google Drive o OneDrive que esté sincronizada automáticamente. Así el backup existe en la nube sin implementar nada adicional.
