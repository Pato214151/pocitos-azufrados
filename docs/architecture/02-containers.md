# 02 — Contenedores (C4 Level 2)

## Diagrama de Contenedores

```mermaid
C4Container
  title Contenedores — Sistema POS Pocitos Azufrados

  Person(usuario, "Usuario", "Admin · Cajero · Contadora")

  Person(cocina_staff, "Personal de Cocina", "Celular / Tablet")

  Container_Boundary(app, "Proceso Python (único)") {
    Container(gui, "Interfaz Gráfica", "Python · Tkinter/ttk", "Ventanas, dashboards, módulos UI. Toda la interacción con el usuario.")
    Container(logic, "Lógica de Negocio", "Python", "Validaciones, cálculos de ventas, generación de números, reportes.")
    Container(db_layer, "Capa de Base de Datos", "Python · sqlite3", "connection.py: conexion_segura(), transaccion_atomica(), get_connection()")
    Container(pdf_gen, "Generador de PDFs", "Python · ReportLab", "printing.py: recibos de venta y boletas en formato 80mm")
    Container(backup, "Daemon de Backup", "Python · threading", "Copia diaria de la BD al directorio configurado. Hilo daemon.")
    Container(migrator, "Migrador de Esquema", "Python · sqlite3", "main.py: aplica_migraciones() en cada arranque. Idempotente.")
    Container(cocina_web, "Servidor Web de Cocina", "Python · Flask · Waitress", "cocina_web/app.py · Daemon thread · puerto 5000 (fallback 5001-5003)\nHTTP Basic Auth (usuario: cocina)\nPestañas: Almuerzos · Inventario · Preproducción\nCSRF habilitado · Auto-refresh configurable 5-120s")
  }

  ContainerDb(db, "Base de Datos SQLite", "SQLite 3 · WAL mode", "data/pocitos_azufrados.db\n35+ tablas · 22 índices\n~64 MB cache en RAM")

  System_Ext(fs_recibos, "data/recibos/", "Sistema de archivos", "PDFs de recibos generados")
  System_Ext(fs_backups, "Directorio de backups", "Sistema de archivos", "Copias diarias de la BD (30 días) — ruta configurable")
  System_Ext(fs_logs, "logs/", "Sistema de archivos", "app.log — rotativo 5 MB × 3 · performance.log")
  System_Ext(browser, "Navegador Web", "HTTP", "Accede via http://[IP-PC]:5000")

  Rel(usuario, gui, "Interactúa", "Mouse / Teclado / Escáner USB")
  Rel(cocina_staff, browser, "Usa")
  Rel(browser, cocina_web, "HTTP GET/POST + Basic Auth")
  Rel(gui, logic, "Llama funciones de negocio")
  Rel(logic, db_layer, "Lee/escribe datos")
  Rel(db_layer, db, "SQL", "sqlite3 (archivo local)")
  Rel(cocina_web, db_layer, "Lee/escribe datos", "SQLite compartido")
  Rel(logic, pdf_gen, "Solicita generar recibo")
  Rel(pdf_gen, fs_recibos, "Escribe PDF 80mm")
  Rel(backup, db, "sqlite3.backup()", "Copia caliente sin bloquear")
  Rel(backup, fs_backups, "Escribe copia .db")
  Rel(migrator, db, "ALTER TABLE / CREATE TABLE IF NOT EXISTS")
  Rel(logic, fs_logs, "Escribe eventos y auditoría")
```

---

## Descripción de Contenedores

### Interfaz Gráfica (`modules/`, `utils/tema_corporativo.py`)
- **Tecnología**: Tkinter nativo de Python — sin dependencias de sistema adicionales
- **Patrón**: Single-window con content_frame dinámico. El dashboard limpia el frame y carga el módulo activo.
- **Dashboards**: 3 (admin, cajero, contadora). Cada uno decide qué módulos expone en el sidebar.
- **Módulos**: 24 clases, cada una recibe `(parent: tk.Frame, usuario: dict)` y dibuja en ese frame.

### Capa de Base de Datos (`database/connection.py`)
- **3 funciones públicas**:
  - `get_connection()` — conexión simple sin context manager
  - `conexion_segura()` — context manager para lectura/escritura con `row_factory = sqlite3.Row`
  - `transaccion_atomica()` — context manager con `BEGIN IMMEDIATE`, commit o rollback automático
- **Configuración SQLite**: WAL · foreign_keys ON · busy_timeout 60s · cache 64MB

### Daemon de Backup (`main.py → iniciar_backup_automatico()`)
- Hilo `daemon=True` — se cancela automáticamente al cerrar la app
- Copia con `sqlite3.backup()` (sin bloquear la BD activa)
- Conserva los últimos 30 archivos
- Ruta configurable desde `configuracion.backup_ruta`

### Migrador de Esquema (`main.py → aplicar_migraciones()`)
- Se ejecuta en **cada arranque** antes de mostrar login
- Solo usa `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` y `CREATE TABLE IF NOT EXISTS`
- **Nunca** elimina datos ni tablas existentes

---

## Estructura de Archivos en Disco

```
PocitosAzufrados-Desktop/
├── main.py                     ← Punto de entrada
├── setup.py                    ← Creación inicial de BD (ejecutar 1 vez)
├── requirements.txt
├── INICIAR.bat / INSTALAR.bat  ← Scripts Windows
│
├── data/
│   ├── pocitos_azufrados.db    ← Base de datos principal
│   ├── backups/                ← Copias diarias (nombre: pocitos_YYYYMMDD_HHMMSS.db)
│   └── recibos/                ← PDFs generados (nombre: recibo_POS-XXXX.pdf)
│
├── logs/
│   └── app.log                 ← Log rotativo (5 MB × 3 archivos)
│
├── database/
│   └── connection.py
├── models/
│   └── series.py               ← Generadores thread-safe POS-XXXX, BOL-XXXX
├── utils/
│   ├── tema_corporativo.py     ← Paleta · Fuentes · Helpers UI
│   ├── logger.py               ← RotatingFileHandler + log_auditoria()
│   └── printing.py             ← Generación PDFs ReportLab
└── modules/
    └── *.py                    ← 24 módulos funcionales
```
