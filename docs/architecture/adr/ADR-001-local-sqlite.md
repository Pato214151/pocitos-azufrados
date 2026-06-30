# ADR-001 — SQLite Local como Base de Datos

**Estado**: Aceptado
**Fecha**: 2024 (inicial) · Revisado 2026-03
**Decisores**: Equipo de desarrollo

---

## Contexto

El Club Los Pocitos Azufrados es un establecimiento en Tocaima, Cundinamarca. La conectividad a internet puede ser inestable o inexistente. El sistema debe funcionar sin interrupciones durante el servicio (almuerzos, bar, caja).

## Decisión

Usar **SQLite 3** como base de datos local embebida, con el archivo en `data/pocitos_azufrados.db`.

## Alternativas consideradas

| Opción | Pros | Contras |
|--------|------|---------|
| **SQLite local** ← elegida | Sin servidor. Sin internet. Cero configuración. | Un solo proceso. Sin multi-usuario simultáneo. |
| PostgreSQL local | Multi-usuario real. Tipos de datos ricos. | Requiere instalar y administrar servidor. |
| MySQL/MariaDB | Familiar para muchos desarrolladores. | Requiere servidor. Más pesado. |
| Firebase / Supabase | Acceso desde múltiples dispositivos. | Requiere internet constante. Costo. |
| SQLite + replicación | Multi-sede posible. | Complejidad de sincronización. |

## Consecuencias

**Positivas:**
- Cero dependencias de red — funciona 100% offline
- Backup con un solo archivo `.db`
- Sin instalación adicional — Python trae `sqlite3` en stdlib
- WAL mode permite backup en caliente sin bloquear la app

**Negativas:**
- Un solo escritor simultáneo (no es problema para este caso de uso)
- No apto para múltiples cajas simultáneas sin sincronización
- Migración a servidor requeriría reescribir la capa de datos

## Notas de implementación

```python
# Configuración en cada conexión
PRAGMA journal_mode = WAL
PRAGMA foreign_keys = ON
PRAGMA busy_timeout = 60000
PRAGMA cache_size = -64000
PRAGMA synchronous = NORMAL
```
