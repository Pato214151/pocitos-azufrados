# 05 — Flujos Clave del Sistema

## 1. Arranque y Autenticación

```mermaid
sequenceDiagram
  actor Usuario
  participant main as main.py
  participant migrator as aplicar_migraciones()
  participant backup as iniciar_backup_automatico()
  participant cocina_web as iniciar_cocina_web()
  participant login as LoginWindow
  participant db as SQLite

  Usuario->>main: python main.py
  main->>db: Verifica data/pocitos_azufrados.db
  alt BD no existe
    main-->>Usuario: Error + sys.exit(1)
  end
  main->>migrator: aplicar_migraciones(db_path)
  migrator->>db: CREATE TABLE IF NOT EXISTS / ALTER TABLE ADD COLUMN IF NOT EXISTS
  migrator-->>main: OK
  main->>backup: iniciar_backup_automatico() → hilo daemon
  main->>cocina_web: iniciar_cocina_web() → hilo daemon
  note over cocina_web: Intenta puertos 5000-5003\nWaitress si disponible,\nflask dev server como fallback
  cocina_web-->>main: Servidor activo (o warning si no hay puerto libre)
  main->>login: LoginWindow(root)

  Usuario->>login: Ingresa usuario + contraseña
  login->>db: SELECT usuario, contrasena_hash, rol, activo

  alt Usuario bloqueado
    login-->>Usuario: "Cuenta bloqueada hasta HH:MM"
  else Credenciales incorrectas
    login->>db: UPDATE intentos_fallidos++
    alt intentos >= 5
      login->>db: UPDATE bloqueado_hasta = now + 30 min
    end
    login-->>Usuario: "Usuario o contraseña incorrectos"
  else Credenciales correctas
    login->>db: UPDATE intentos_fallidos=0, ultimo_login
    login->>db: INSERT INTO sesiones (inicio)

    alt rol = administrador / vendedor
      login->>main: Dashboard(root, usuario)
    else rol = cajero
      login->>main: DashboardCajero(root, usuario)
    else nombre = contadora
      login->>main: DashboardContadora(root, usuario)
    end
  end
```

---

## 2. Venta en el Bar (POS)

```mermaid
sequenceDiagram
  actor Cajero
  participant pos as POSModule
  participant series as models/series.py
  participant db as SQLite (transaccion_atomica)
  participant printing as utils/printing.py

  Cajero->>pos: Escanea código de barras / busca producto
  pos->>db: SELECT producto WHERE codigo_barras = ?
  db-->>pos: Producto + variantes

  alt Tiene variantes
    pos-->>Cajero: Diálogo de selección de variante
    Cajero->>pos: Elige variante
  end

  pos->>pos: Agrega al carrito (en memoria)
  Cajero->>pos: Selecciona método de pago + "Cobrar"

  pos->>series: obtener_proximo_numero_venta()
  series->>db: UPDATE series_facturacion SET consecutivo++
  series-->>pos: "POS-2026-000042"

  pos->>db: BEGIN IMMEDIATE
  pos->>db: INSERT INTO ventas (numero, total, metodo_pago…)

  loop Por cada ítem del carrito
    pos->>db: INSERT INTO venta_detalle
    pos->>db: UPDATE productos SET stock_actual = stock_actual - cantidad
    pos->>db: INSERT INTO movimientos_inventario (tipo='VENTA')

    alt Producto requiere_cocina = 1
      pos->>db: INSERT INTO ordenes_cocina (estado='PENDIENTE')
    end
  end

  pos->>db: INSERT INTO auditoria (tabla='ventas', accion='CREAR')
  pos->>db: COMMIT

  pos-->>Cajero: "Venta registrada POS-2026-000042"

  alt Usuario confirma imprimir
    pos->>printing: imprimir_recibo_venta(id_venta)
    printing->>db: SELECT venta + detalles
    printing->>printing: Genera PDF 80mm (ReportLab)
    printing->>OS: Abre PDF con visor del SO
  end
```

---

## 3. Flujo de Cocina

```mermaid
stateDiagram-v2
  [*] --> PENDIENTE : Venta creada con producto de cocina
  PENDIENTE --> PREPARANDO : Cocinero hace clic "Iniciar"
  PREPARANDO --> LISTO : Cocinero hace clic "Listo"
  LISTO --> ENTREGADO : Cajero/mesero hace clic "Entregar"
  PENDIENTE --> CANCELADO : Anulación de venta
  PREPARANDO --> CANCELADO : Anulación de venta

  note right of PENDIENTE
    CocinaModule refresca
    cada 10 segundos
    via root.after(10000)
  end note

  note right of LISTO
    Se actualiza tanto
    ordenes_cocina.estado
    como venta_detalle.estado_cocina
  end note
```

---

## 4. Apertura y Cierre de Caja

```mermaid
flowchart TD
  A([Cajero abre módulo Caja]) --> B{¿Hay caja abierta hoy?}
  B -->|No| C[Formulario: monto inicial]
  C --> D[INSERT caja_diaria estado=ABIERTA]
  D --> E[Pantalla de movimientos activa]

  B -->|Sí| E

  E --> F{Acción del cajero}
  F -->|Ingreso manual| G[INSERT movimientos_caja tipo=INGRESO]
  F -->|Egreso manual| H[INSERT movimientos_caja tipo=EGRESO]
  F -->|Cerrar caja| I[Formulario: monto real contado]

  I --> J[Calcula monto_esperado\n= inicial + ventas + boletas - gastos]
  J --> K[Muestra diferencia\nmonto_real vs esperado]
  K --> L[UPDATE caja_diaria\nestado=CERRADA, diferencia, fecha_cierre]
  L --> M([Caja cerrada])

  G --> E
  H --> E
```

---

## 5. Generación de Número Consecutivo (Thread-Safe)

```mermaid
sequenceDiagram
  participant M1 as Módulo A
  participant M2 as Módulo B (hipotético)
  participant series as models/series.py
  participant db as SQLite

  note over series: _lock = threading.Lock()

  M1->>series: obtener_proximo_numero_venta()
  series->>series: acquire(_lock)

  M2->>series: obtener_proximo_numero_venta()
  note over M2,series: Bloqueado hasta que M1 libere

  series->>db: BEGIN IMMEDIATE
  series->>db: SELECT consecutivo_actual WHERE prefijo='POS' AND ano=2026
  db-->>series: 41
  series->>db: UPDATE series_facturacion SET consecutivo=42
  series->>db: COMMIT
  series->>series: release(_lock)
  series-->>M1: "POS-2026-000042"

  series->>series: acquire(_lock) [M2 continúa]
  series->>db: BEGIN IMMEDIATE
  series->>db: SELECT + UPDATE → 43
  series-->>M2: "POS-2026-000043"
```

---

## 6. Backup Automático (Daemon)

```mermaid
flowchart LR
  A([main.py arranca]) --> B[Hilo daemon\nbackup_thread]
  B --> C{¿backup_ruta\nconfigurado?}
  C -->|No| D[Duerme 1 hora\ny vuelve a checar]
  D --> C
  C -->|Sí| E{¿Último backup\n> 24 horas?}
  E -->|No| D
  E -->|Sí| F[sqlite3.backup\na archivo .db\nen backup_ruta]
  F --> G[Elimina archivos\n> 30 días]
  G --> H[UPDATE configuracion\nultimo_backup = now]
  H --> D
```

---

## 7. Navegación entre Módulos (Dashboard)

```mermaid
sequenceDiagram
  actor Admin
  participant sidebar as Sidebar
  participant dash as Dashboard._limpiar_contenido()
  participant old as MóduloAnterior
  participant new as MóduloNuevo
  participant frame as content_frame

  Admin->>sidebar: Clic en "Bar"
  sidebar->>dash: _abrir_bar()
  dash->>old: detener() [si existe]
  dash->>frame: Destruye todos los widgets hijos
  dash->>sidebar: _marcar_menu("Bar") — resalta botón activo
  dash->>new: POSModule(content_frame, usuario)
  new->>frame: Dibuja interfaz del módulo
  new-->>Admin: Módulo Bar visible
```

---

## 8. Factura Electrónica DIAN

```mermaid
sequenceDiagram
  actor Cajero
  participant pos as POSModule
  participant validaciones as models/validaciones.py
  participant series as models/series.py
  participant db as SQLite (transaccion_atomica)

  Cajero->>pos: Activa checkbox "Factura electrónica"
  Cajero->>pos: "Cobrar" (pago confirmado)

  pos->>validaciones: validar_resolucion_dian()
  validaciones->>db: SELECT resolucion_dian_* FROM configuracion
  db-->>validaciones: datos de resolución

  alt nivel = 'bloqueado' (rango agotado / fecha vencida / ≤50 restantes)
    validaciones-->>pos: puede_emitir=False
    pos-->>Cajero: messagebox.showerror — se aborta
  else nivel = 'advertencia' (≤500 restantes / ≤30 días)
    validaciones-->>pos: puede_emitir=True, nivel='advertencia'
    pos-->>Cajero: messagebox.showwarning — continúa
  else nivel = 'ok'
    validaciones-->>pos: puede_emitir=True
  end

  pos-->>Cajero: Diálogo modal: cliente_nombre · cliente_nit · cliente_email
  Cajero->>pos: Ingresa datos del cliente

  pos->>series: obtener_proximo_numero_factura_electronica()
  series->>db: UPDATE series_facturacion WHERE prefijo='LP'
  series-->>pos: "LP-2026-000001"

  pos->>db: BEGIN IMMEDIATE
  pos->>db: INSERT INTO ventas (...)
  pos->>db: INSERT INTO facturas_electronicas (id_venta, numero_factura, cliente_*)
  pos->>db: COMMIT

  pos-->>Cajero: Recibo incluye datos cliente + número LP
```

---

## 9. Cocina Web — Ciclo de Estado de Almuerzo

```mermaid
sequenceDiagram
  actor Cocinero
  participant browser as Navegador (celular)
  participant flask as cocina_web/app.py
  participant db as SQLite
  participant cocina as cocina_module.py (polling 5s)
  actor Cajero

  Cocinero->>browser: GET http://[IP]:5000
  browser->>flask: GET / + Basic Auth
  flask->>db: SELECT reservas_almuerzo WHERE estado IN ('RESERVADO','EN_PREPARACION','LISTO')
  db-->>flask: lista de almuerzos
  flask-->>browser: HTML renderizado (Jinja2)

  Cocinero->>browser: Clic "Iniciar" → estado RESERVADO→EN_PREPARACION
  browser->>flask: POST /almuerzo/<id>/estado {estado: EN_PREPARACION}
  flask->>db: UPDATE reservas_almuerzo SET estado='EN_PREPARACION'

  Cocinero->>browser: Clic "Listo" → estado EN_PREPARACION→LISTO
  browser->>flask: POST /almuerzo/<id>/estado {estado: LISTO}
  flask->>db: UPDATE reservas_almuerzo SET estado='LISTO', notificado_listo=0

  note over cocina: Polling cada 5s
  cocina->>db: SELECT * FROM reservas_almuerzo WHERE estado='LISTO' AND notificado_listo=0
  db-->>cocina: pedido listo
  cocina->>db: UPDATE notificado_listo=1
  cocina-->>Cajero: Popup + beep — "Almuerzo LISTO"

  Cajero->>cocina: Clic "Entregar" en módulo cocina (desktop)
  cocina->>db: UPDATE reservas_almuerzo SET estado='ENTREGADO'
```
