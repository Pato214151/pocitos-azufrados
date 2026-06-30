# Arquitectura del Sistema — Club Los Pocitos Azufrados

> Sistema POS de escritorio para bar & restaurante con cocina, caja diaria,
> inventario y reportes. Arquitectura local sin servidor, Python + Tkinter + SQLite.

---

## Índice de Documentación

| Documento | Descripción |
|-----------|-------------|
| [01 — Contexto del Sistema](01-system-context.md) | Usuarios, límites del sistema, integraciones externas |
| [02 — Contenedores](02-containers.md) | Aplicación, base de datos, archivos generados |
| [03 — Componentes](03-components.md) | Módulos internos, dashboards, capas de código |
| [04 — Modelo de Datos](04-data-model.md) | 25 tablas SQLite, índices, diagrama ER |
| [05 — Flujos Clave](05-key-flows.md) | Autenticación, venta POS, flujo cocina, cierre de caja |
| [06 — Atributos de Calidad](06-quality-attributes.md) | Seguridad, rendimiento, backup, auditoría |
| [ADR-001](adr/ADR-001-local-sqlite.md) | Por qué SQLite local en lugar de servidor |
| [ADR-002](adr/ADR-002-tkinter-desktop.md) | Por qué Tkinter en lugar de web/Electron |
| [ADR-003](adr/ADR-003-modular-pattern.md) | Patrón de módulos cargados dinámicamente |
| [ADR-004](adr/ADR-004-wal-mode.md) | SQLite en modo WAL |
| [ADR-005](adr/ADR-005-dark-to-light-theme.md) | Migración de tema oscuro a claro |

---

## Resumen Ejecutivo

```
Tecnología principal  Python 3 · Tkinter · SQLite (WAL)
Plataforma            Windows 10/11 (64-bit)
Dependencias externas Ninguna — funciona 100% offline
Usuarios concurrentes 1 proceso, múltiples roles secuenciales
Tablas BD             25 tablas · 22 índices
Módulos UI            24 módulos funcionales · 3 dashboards
Seguridad             bcrypt (passwords) · SHA-256 (fallback)
Auditoría             Tabla `auditoria` + log rotativo (5 MB × 3)
Backup                Daemon diario · últimos 30 días
Impresión             PDFs 80 mm vía ReportLab
```

---

## Stack Tecnológico

```
┌─────────────────────────────────────────────┐
│              Python 3 (aplicación)           │
├───────────────┬─────────────────────────────┤
│  GUI          │  Tkinter + ttk               │
│  Base datos   │  SQLite 3 (WAL mode)         │
│  PDF          │  ReportLab >= 3.6            │
│  Contraseñas  │  bcrypt >= 4.0               │
│  Excel export │  openpyxl >= 3.1             │
│  Código barras│  python-barcode >= 0.15      │
│  Imágenes     │  Pillow >= 9.0               │
│  HTTP (futuro)│  requests >= 2.28            │
│  Gráficos     │  matplotlib >= 3.5           │
└───────────────┴─────────────────────────────┘
```

---

## Principios Arquitectónicos

1. **Local-first** — Todo funciona sin internet. La BD está en `data/pocitos_azufrados.db`.
2. **Un proceso, un usuario** — No hay concurrencia entre usuarios simultáneos.
3. **Módulos cargados dinámicamente** — El content_frame del dashboard destruye y recrea el módulo activo en cada navegación.
4. **Separación de capas** — `utils/` (helpers) → `database/` (conexión) → `models/` (series) → `modules/` (UI + lógica).
5. **Auditoría en BD** — Acciones críticas se registran en la tabla `auditoria` dentro de la misma transacción.
6. **Migraciones idempotentes** — `main.py` aplica migraciones en cada arranque; nunca rompen una BD existente.
