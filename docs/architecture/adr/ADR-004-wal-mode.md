# ADR-004 — SQLite en Modo WAL

**Estado**: Aceptado
**Fecha**: 2024
**Decisores**: Equipo de desarrollo

---

## Contexto

El daemon de backup necesita copiar la BD mientras la aplicación está en uso. El modo journal por defecto de SQLite (DELETE/ROLLBACK) bloquea completamente la BD durante escrituras, lo que podría interrumpir la operación si el backup coincide con una venta.

## Decisión

Activar `PRAGMA journal_mode = WAL` (Write-Ahead Logging) en cada conexión.

## Consecuencias

**Positivas:**
- Los lectores no bloquean a los escritores y viceversa
- `sqlite3.backup()` puede ejecutarse sin bloquear la app principal
- Mayor rendimiento en escrituras concurrentes
- Recuperación ante fallos más robusta (solo transacciones COMMIT son visibles)

**Negativas:**
- Genera archivos auxiliares: `pocitos_azufrados.db-wal` y `pocitos_azufrados.db-shm` — deben copiarse junto con el `.db` en backups manuales
- Checkpoint automático cada ~1000 páginas puede causar pausa breve

## Configuración completa

```python
PRAGMAS = [
    "PRAGMA journal_mode = WAL",
    "PRAGMA synchronous = NORMAL",   # Balance seguridad/velocidad (no FULL)
    "PRAGMA foreign_keys = ON",      # Integridad referencial activa
    "PRAGMA busy_timeout = 60000",   # 60 s antes de "database is locked"
    "PRAGMA cache_size = -64000",    # 64 MB de caché en RAM
    "PRAGMA temp_store = MEMORY",    # Tablas temporales en RAM
]
```

## Nota sobre sincronización

`PRAGMA synchronous = NORMAL` (en lugar de FULL) acepta un pequeño riesgo de pérdida de datos ante corte de corriente justo en el momento de escritura. Para un POS local este trade-off es aceptable a cambio de mayor velocidad.
