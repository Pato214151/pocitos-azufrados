# 06 — Atributos de Calidad y Preocupaciones Transversales

## Seguridad

### Autenticación
| Mecanismo | Implementación |
|-----------|---------------|
| Hash de contraseñas | `bcrypt` (cost factor por defecto ~12) con fallback a SHA-256 para cuentas antiguas |
| Bloqueo por intentos | 5 intentos fallidos → cuenta bloqueada 30 minutos |
| Sesiones | INSERT en tabla `sesiones` al login, UPDATE `fecha_fin` al logout |
| Roles | CHECK constraint en BD: `administrador`, `cajero`, `vendedor` |
| Usuario especial | `contadora` — acceso por nombre, no por rol; panel distinto |

### Autorización
```
Administrador → Acceso total a todos los módulos
Cajero        → Bar · Pedidos · Cocina · Cuentas Abiertas · Caja · Historial
Vendedor      → Igual que administrador (pendiente de refinar)
Contadora       → Panel ejecutivo de KPIs únicamente
```

### Auditoría
```python
# Toda operación crítica registra en tabla `auditoria`
log_auditoria(conn, tabla='ventas', id_registro=id_venta,
              accion='CREAR', usuario=self.usuario['usuario'],
              comentario='Venta POS-2026-000042')

# Campos registrados:
# - tabla_afectada, id_registro, accion (CREAR/EDITAR/ELIMINAR/CERRAR)
# - usuario, comentario, datos_anteriores, datos_nuevos
# - fecha_hora (datetime localtime)
```

### Vulnerabilidades conocidas / deuda de seguridad
- Contraseñas iniciales `cajero123`, `nelly123`, `contadora123` — deben cambiarse en primer uso (flag `debe_cambiar_password = 1` en BD).
- `sync_token` se almacena en texto plano en tabla `configuracion`.
- No hay control de acceso a nivel de registro (cualquier cajero ve todos los datos de su turno).

---

## Integridad de Datos

### Transacciones
```python
# Operaciones simples
with conexion_segura() as conn:
    conn.execute("UPDATE productos SET stock_actual = ?", (nuevo_stock,))
    # commit automático al salir del with

# Operaciones críticas (venta completa, cierre de caja)
with transaccion_atomica() as conn:
    conn.execute("INSERT INTO ventas ...")
    conn.execute("INSERT INTO venta_detalle ...")
    conn.execute("UPDATE productos SET stock_actual ...")
    # rollback automático si cualquier línea falla
```

### Restricciones de BD
- `FOREIGN KEY ... ON DELETE CASCADE` en `venta_detalle` respecto a `ventas`
- 13+ restricciones CHECK de dominio
- UNIQUE en campos críticos: `numero_venta`, `numero_boleta`, `codigo_barras`, `usuario`

### Concurrencia
- **Un proceso, un usuario activo** — no hay escenario real de concurrencia entre sesiones
- `WAL mode` + `busy_timeout = 60 000 ms` previene "database is locked" en el daemon de backup
- `threading.Lock` en `models/series.py` previene duplicados de número de venta si en el futuro hubiera hilos simultáneos

---

## Confiabilidad

### Modo WAL (Write-Ahead Logging)
```sql
PRAGMA journal_mode = WAL;
-- Permite lecturas simultáneas mientras se escribe
-- El daemon de backup usa sqlite3.backup() sin bloquear la BD
```

### Backup automático
```
- Frecuencia: 1 vez al día (configurable)
- Mecanismo: sqlite3.backup() — hot backup sin cerrar la BD
- Retención: últimos 30 archivos
- Naming: pocitos_YYYYMMDD_HHMMSS.db
- Destino: ruta configurable en tabla configuracion
```

### Recuperación ante fallos
1. **Corte de luz durante venta**: WAL garantiza que solo transacciones completas (COMMITed) son visibles tras reinicio.
2. **Corrupción de BD**: Restaurar desde el backup más reciente en `data/backups/`.
3. **Módulo falla al cargar**: `_abrir_modulo()` captura la excepción y muestra mensaje en el content_frame sin crashear el dashboard.

---

## Rendimiento

### Estrategias implementadas
| Área | Estrategia |
|------|-----------|
| Caché SQLite | `PRAGMA cache_size = -64000` (64 MB en RAM) |
| Tablas temporales | `PRAGMA temp_store = MEMORY` |
| Índices | 22 índices para búsquedas frecuentes (productos por código, ventas por fecha/estado) |
| Paginación | `historial_ventas_module.py` carga 100 registros por página |
| Auto-refresh | Cocina: 10 s · Pedidos: 15 s (no más frecuente para no saturar UI) |

### Limitaciones conocidas
- `LIMIT 100` en historial de ventas sin paginación real (ver ADR backlog)
- `buscador_ventas.py` no tiene paginación
- Los módulos dentro de `MovimientosModule` se instancian todos al abrir el contenedor (carga inicial puede ser lenta si hay muchos datos)

---

## Mantenibilidad

### Convenciones de código
- Cada módulo es **una clase**, sin ventanas independientes
- Todo color/fuente en `utils/tema_corporativo.py` — ningún valor hardcodeado (excepto migraciones en proceso)
- Migraciones en `main.py:aplicar_migraciones()` — nunca en `setup.py` después del primer deploy
- Logging con `utils/logger.py` — no `print()` en producción

### Estructura de carpetas por responsabilidad
```
utils/    ← Solo helpers genéricos (no lógica de negocio)
database/ ← Solo conexión y context managers (no queries de negocio)
models/   ← Solo generadores de datos (no UI)
modules/  ← UI + lógica de negocio juntos (trade-off deliberado, ver ADR-003)
```

### Deuda técnica identificada
| ID | Descripción | Impacto | Esfuerzo |
|----|-------------|---------|---------|
| DT-01 | `get_connection()` usada directamente en `dashboard.py` — debería usar `conexion_segura()` | Bajo | Bajo |
| DT-02 | Lógica de negocio mezclada con UI en módulos grandes (>1000 líneas) | Medio | Alto |
| DT-03 | `sync_queue` y `sync_engine.py` (si existe) nunca activados — feature creep | Bajo | Bajo (eliminar) |
| DT-04 | Historial de ventas sin paginación real (solo LIMIT 100) | Medio | Medio |
| DT-05 | `'Segoe UI'` hardcodeada en algunos headers de módulos | Bajo | Bajo |
| DT-06 | `requests` en requirements sin uso activo | Bajo | Bajo (eliminar) |

---

## Observabilidad

### Logging
```
Archivo: logs/app.log
Rotación: 5 MB máximo, conserva 3 archivos (15 MB total)
Nivel: INFO por defecto
Formato: [FECHA] [NIVEL] [MÓDULO] mensaje
```

### Auditoría de negocio
```sql
-- Tabla auditoria registra:
-- - Apertura/cierre de caja
-- - Creación y anulación de ventas
-- - Registro de gastos
-- - Alta/baja/edición de usuarios
-- - Ajustes de inventario
```

### Métricas en dashboard
El `dashboard.py` y `dashboard_contadora.py` calculan en tiempo real al abrir:
- Ventas hoy / Ventas del mes
- Gastos del mes / Utilidad neta
- Stock bajo (productos con stock ≤ mínimo)
- Comparativo % vs período anterior (ventas hoy vs ayer, mes vs mes anterior)
