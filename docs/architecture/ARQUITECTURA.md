# Arquitectura — Club Los Pocitos Azufrados POS
_Última actualización: 2026-05-17_

---

## 0. Diagrama de capas

```
main.py (orquestador)
  │
  ├── utils/          (tema, logger, printing)              ← sin dependencias locales
  ├── database/       (connection.py)                       ← sin dependencias locales
  ├── models/         (ventas, inventario, series, validaciones) ← depende de database/, utils/
  ├── modules/        (25 módulos UI)                       ← depende de todo lo anterior
  └── cocina_web/     (Flask server)                        ← depende solo de database/
```

El flujo de dependencias es **estrictamente unidireccional**:
`main → modules → models → database/utils`

Ninguna capa importa a la capa superior. `utils/` y `database/` no importan nada local.

---

## 1. Capas del sistema (Mermaid)

```mermaid
graph TB
    subgraph ENTRY["Punto de entrada"]
        main["main.py<br/>migraciones · backup daemon · cocina daemon · login"]
    end

    subgraph UI["UI Layer — modules/"]
        direction TB
        DA["dashboard.py<br/><i>administrador / vendedor</i>"]
        DC["dashboard_cajero.py<br/><i>cajero</i>"]
        DK["dashboard_contadora.py<br/><i>contadora</i>"]
        LG["login.py"]
    end

    subgraph MODS["Módulos funcionales — modules/"]
        direction LR
        POS["pos_module<br/>Bar / POS"]
        INV["inventario_module<br/>+ categorias_module"]
        CAJ["caja_module"]
        CUE["cuentas_abiertas_module"]
        COC["cocina_module"]
        HIS["historial_ventas_module"]
        BOL["boletas_module"]
        REP["reportes_module"]
        NOM["nomina_module"]
        SOC["socios_module"]
        CLI["clientes_module"]
        PRO["proveedores_module"]
        GAS["gastos_module"]
        MOV["movimientos_module"]
        PED["pedidos_module"]
        PAG["pagos_module"]
        USU["usuarios_module"]
        CFG["config_module"]
        CON["contingencia_module"]
        ERR["reporte_errores_module"]
    end

    subgraph BL["Business Logic — models/"]
        MV["ventas.py<br/>crear_venta · abrir_cuenta_abierta<br/>verificar_stock_minimo"]
        MI["inventario.py<br/>registrar_movimiento_stock<br/>editar_producto · carga_masiva<br/>aprobar / rechazar · variantes"]
        MS["series.py<br/>POS / BOL / LP numbers<br/>thread-safe + SQLite lock"]
        MVal["validaciones.py<br/>validar_resolucion_dian<br/>verificar_pin_admin"]
    end

    subgraph UTILS["Utilidades — utils/"]
        TC["tema_corporativo.py<br/>colores · fuentes · widgets"]
        LGR["logger.py<br/>log_auditoria · log_performance"]
        PR["printing.py<br/>PDF 80mm/58mm · ESC/POS"]
    end

    subgraph DB["Data Layer"]
        CONN["database/connection.py<br/>conexion_segura · transaccion_atomica"]
        SQLITE[("SQLite WAL<br/>pocitos_azufrados.db")]
    end

    subgraph WEB["Web — cocina_web/"]
        FLASK["app.py Flask :5000<br/>Waitress (prod) · Basic Auth"]
        HTML["templates/cocina.html"]
        CSS["static/cocina.css"]
    end

    main --> LG
    LG --> DA & DC & DK
    DA & DC & DK --> MODS
    POS --> MV & MS & MVal
    INV --> MI
    BOL --> MS
    CON --> MV & MS
    MODS --> CONN
    BL --> CONN & LGR
    CONN --> SQLITE
    FLASK --> CONN
    FLASK --> HTML & CSS
    POS & BOL & HIS --> PR
    MODS --> TC
```

---

## 2. Acceso por rol (Dashboard → Módulos)

```mermaid
graph LR
    LOGIN["login.py<br/>bcrypt / PIN fallback"]

    LOGIN -->|"rol = administrador<br/>rol = vendedor"| ADM["dashboard.py"]
    LOGIN -->|"rol = cajero"| CAJ["dashboard_cajero.py"]
    LOGIN -->|"usuario = contadora"| CON["dashboard_contadora.py"]

    ADM --> A1["Bar / POS"]
    ADM --> A2["Inventario + Categorias"]
    ADM --> A3["Caja"]
    ADM --> A4["Pedidos"]
    ADM --> A5["Cocina"]
    ADM --> A6["Cuentas Abiertas"]
    ADM --> A7["Boletas"]
    ADM --> A8["Historial Ventas"]
    ADM --> A9["Gastos"]
    ADM --> A10["Movimientos"]
    ADM --> A11["Clientes"]
    ADM --> A12["Proveedores"]
    ADM --> A13["Pagos"]
    ADM --> A14["Socios"]
    ADM --> A15["Nomina"]
    ADM --> A16["Reportes"]
    ADM --> A17["Usuarios"]
    ADM --> A18["Configuracion"]
    ADM --> A19["Contingencia"]
    ADM --> A20["Reporte Errores"]

    CAJ --> C1["Bar / POS"]
    CAJ --> C2["Caja"]
    CAJ --> C3["Pedidos"]
    CAJ --> C4["Cocina"]
    CAJ --> C5["Cuentas Abiertas"]
    CAJ --> C6["Historial Ventas"]
    CAJ --> C7["Gastos"]
    CAJ --> C8["Movimientos"]
    CAJ --> C9["Inventario"]
    CAJ --> C10["Proveedores"]
    CAJ --> C11["Contingencia"]
    CAJ --> C12["Reporte Errores"]

    CON --> K1["Bar / POS"]
    CON --> K2["Caja"]
    CON --> K3["Inventario"]
    CON --> K4["Clientes"]
    CON --> K5["Cuentas Abiertas"]
    CON --> K6["Gastos"]
    CON --> K7["Movimientos"]
    CON --> K8["Nomina"]
    CON --> K9["Pedidos"]
    CON --> K10["Historial Ventas"]
    CON --> K11["Reportes"]
    CON --> K12["Usuarios"]
    CON --> K13["Socios"]
    CON --> K14["Boletas"]
    CON --> K15["Configuracion"]
    CON --> K16["Proveedores"]
    CON --> K17["Categorias"]
    CON --> K18["Contingencia"]
```

---

## 3. Flujo de una venta POS

```mermaid
sequenceDiagram
    actor Cajero
    participant POS as pos_module.py
    participant Val as models/validaciones.py
    participant VM as models/ventas.py
    participant Ser as models/series.py
    participant DB as SQLite (WAL)
    participant Log as utils/logger.py
    participant Print as utils/printing.py

    Cajero->>POS: Confirmar cobro
    POS->>Val: validar_resolucion_dian() [si FE]
    Val-->>POS: ok / advertencia / bloqueado

    POS->>VM: crear_venta(carrito, total, metodo_pago, ...)
    activate VM
        VM->>DB: BEGIN IMMEDIATE (transaccion_atomica)
        VM->>Ser: generar_numero_venta_en_conn(conn)
        Ser-->>VM: "POS-2026-000042"
        VM->>DB: INSERT INTO ventas
        VM->>DB: SELECT stock FROM productos [validar]
        Note over VM,DB: ValueError si stock insuficiente → rollback
        VM->>DB: INSERT INTO venta_detalle (x items)
        VM->>DB: UPDATE productos SET stock_actual - cantidad
        VM->>DB: INSERT INTO movimientos_inventario
        VM->>DB: INSERT INTO ordenes_cocina [si requiere_cocina]
        VM->>DB: INSERT INTO reservas_almuerzo [si es_almuerzo]
        VM->>DB: INSERT INTO pagos
        VM->>DB: INSERT INTO movimientos_caja [si caja abierta]
        VM->>Log: log_auditoria('DESCUENTO') [si aplica]
        VM->>Ser: generar_numero_fe_en_conn(conn) [si FE]
        VM->>DB: INSERT INTO facturas_electronicas [si FE]
        VM->>DB: COMMIT
    deactivate VM

    VM-->>POS: {id_venta, numero, numero_fe, tiene_cocina}
    POS->>POS: verificar_stock_minimo(ids_productos)
    POS->>Print: imprimir_recibo_venta(id_venta)
    POS->>Cajero: Mostrar cambio / UI reset
```

---

## 4. Operaciones de inventario

```mermaid
flowchart TD
    INV["inventario_module.py<br/><i>solo UI y lecturas</i>"]

    INV -->|"conexion_segura"| R1["cargar_productos()"]
    INV -->|"conexion_segura"| R2["cargar_categorias()"]
    INV -->|"conexion_segura"| R3["buscar productos / filtros"]

    INV -->|"models/inventario"| W1["registrar_movimiento_stock()<br/>ENTRADA · SALIDA"]
    INV -->|"models/inventario"| W2["editar_producto()"]
    INV -->|"models/inventario"| W3["carga_masiva_productos()<br/>CSV / Excel"]
    INV -->|"models/inventario"| W4["aprobar_producto()"]
    INV -->|"models/inventario"| W5["rechazar_producto()"]
    INV -->|"models/inventario"| W6["agregar_variante()"]
    INV -->|"models/inventario"| W7["eliminar_variante()"]

    W1 & W2 & W3 & W4 & W5 --> DB[("SQLite WAL")]
    W6 & W7 --> DB

    W1 & W2 & W3 & W4 & W5 --> AUD["log_auditoria()<br/>tabla auditoria"]
    AUD --> DB
```

---

## 5. Generacion de numeros consecutivos

```mermaid
flowchart LR
    subgraph SER["models/series.py"]
        LV["_lock_ventas\nthreading.Lock"]
        LB["_lock_boletas\nthreading.Lock"]
        LF["_lock_fe\nthreading.Lock"]
    end

    POS["pos_module"] -->|"generar_numero_venta_en_conn(conn)"| LV
    BOL["boletas_module"] -->|"generar_numero_boleta_en_conn(conn)"| LB
    VM["models/ventas.py"] -->|"generar_numero_fe_en_conn(conn)"| LF
    VM -->|"generar_numero_venta_en_conn(conn)"| LV

    LV -->|"SELECT + UPDATE series_facturacion\nBEGIN IMMEDIATE"| DB[("SQLite")]
    LB -->|"SELECT + UPDATE series_boletas\nBEGIN IMMEDIATE"| DB
    LF -->|"SELECT + UPDATE series_facturacion LP\nBEGIN IMMEDIATE"| DB

    DB -->|"POS-2026-000042"| POS
    DB -->|"BOL-2026-000015"| BOL
    DB -->|"LP-2026-000003"| VM
```

---

## 6. Fortalezas

1. **Separación clara de capas** — `utils/` no importa `modules/`, `models/` no importa `modules/`. Flujo unidireccional garantizado.
2. **Context managers para BD** — `conexion_segura()` y `transaccion_atomica()` eliminan fugas de conexión y garantizan rollback automático.
3. **Números consecutivos thread-safe** — `models/series.py` usa `threading.Lock()` + `BEGIN IMMEDIATE`. Probado con 50 hilos concurrentes sin duplicados.
4. **Lazy imports en dashboards** — cada `_abrir_*` importa su módulo dentro de un `try`, evitando que un módulo roto tumbe todo el dashboard.
5. **Patrón `detener()` obligatorio** — resuelve el problema clásico de Tkinter con `after()` zombie en módulos destruidos.
6. **Auditoría en misma transacción** — `log_auditoria(conn, ...)` recibe la conexión abierta; si la operación falla, el registro de auditoría también se revierte.
7. **Test coverage sólido** — 70 tests, incluyendo simulación de día completo, validaciones DIAN, PIN admin y lógica de ventas con 27 casos.

---

## 7. Métricas actuales

| Métrica | Valor |
|---------|-------|
| Líneas de código (Python) | ~18.000 |
| Módulos UI | 25 |
| Tablas BD | 30+ |
| Tests automatizados | 70 |
| Cobertura lógica de negocio (`models/`) | Buena — ventas, inventario, validaciones, series |
| Cobertura de UI | Nula |
| Cobertura de integración (día completo) | Excelente — 2 suites distintas |
