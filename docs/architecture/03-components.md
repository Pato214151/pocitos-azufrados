# 03 — Componentes (C4 Level 3)

## Mapa de Módulos

```mermaid
graph TD
  subgraph Entrada["Inicio"]
    MAIN[main.py]
    SETUP[setup.py]
    LOGIN[login.py]
  end

  subgraph Dashboards["Dashboards (según rol)"]
    DASH_ADMIN[dashboard.py\nAdministrador · Vendedor]
    DASH_CAJERO[dashboard_cajero.py\nCajero]
    DASH_CONTADORA[dashboard_contadora.py\nContadora - panel especial]
  end

  subgraph Operaciones["Módulos de Operación"]
    POS[pos_module.py\nBar · POS · Escáner]
    COCINA[cocina_module.py\nCocina · Auto-refresh 10s]
    PEDIDOS[pedidos_module.py\nAlmuerzos · Auto-refresh 15s]
    CUENTAS[cuentas_abiertas_module.py\nTabs por cliente]
    BOLETAS[boletas_module.py\nEntradas $35k]
    PAGOS[pagos_module.py\nCobrar cuentas]
  end

  subgraph Administracion["Módulos de Administración"]
    CAJA[caja_module.py\nApertura · Cierre · Movimientos]
    INVENTARIO[inventario_module.py\nStock · KPIs · Ajustes]
    CATEGORIAS[categorias_module.py\nCategorías + Productos]
    GASTOS[gastos_module.py\nEgresos operacionales]
    CLIENTES[clientes_module.py\nFicha de clientes]
    PROVEEDORES[proveedores_module.py\nFicha · Compras · Deudas]
    USUARIOS[usuarios_module.py\nGestión de usuarios]
    CONFIG[config_module.py\nDatos negocio · Backup · Sync]
    NOMINA[nomina_module.py\nNómina y turnos]
    SOCIOS[socios_module.py\nSocios · Membresías · Pagos]
    CONTINGENCIA[contingencia_module.py\nModo contingencia / offline]
    CONFIG_USR[config_usuarios_module.py\nPIN · permisos por usuario]
  end

  subgraph Reportes["Módulos de Consulta"]
    HISTORIAL[historial_ventas_module.py\nFiltros · Paginación 100]
    REPORTES[reportes_module.py\nKPIs · Tablas · Export Excel]
    MOVIMIENTOS[movimientos_module.py\nTabs: Resumen·Ingresos·Egresos·Caja·Reportes]
    BUSCADOR[buscador_ventas.py\nBúsqueda por número]
    RESERVAS[reservas_module.py\nPre-órdenes]
  end

  subgraph Capas["Capas Compartidas"]
    TEMA[utils/tema_corporativo.py\nCOLORES · FUENTES · crear_boton()]
    CONN[database/connection.py\nconexion_segura() · transaccion_atomica()]
    SERIES[models/series.py\nPOS-XXXX · BOL-XXXX · LP-XXXX]
    VALIDACIONES[models/validaciones.py\nvalidar_resolucion_dian()\nverificar_pin_admin()]
    LOGGER[utils/logger.py\nlog_auditoria() · RotatingFileHandler]
    PRINTING[utils/printing.py\nPDFs 80mm · ReportLab]
  end

  MAIN --> LOGIN
  SETUP -.->|"ejecutar 1 vez"| CONN

  LOGIN -->|rol admin/vendedor| DASH_ADMIN
  LOGIN -->|rol cajero| DASH_CAJERO
  LOGIN -->|nombre=contadora| DASH_CONTADORA

  DASH_ADMIN --> POS
  DASH_ADMIN --> COCINA
  DASH_ADMIN --> PEDIDOS
  DASH_ADMIN --> CUENTAS
  DASH_ADMIN --> BOLETAS
  DASH_ADMIN --> PAGOS
  DASH_ADMIN --> CAJA
  DASH_ADMIN --> INVENTARIO
  DASH_ADMIN --> CATEGORIAS
  DASH_ADMIN --> MOVIMIENTOS
  DASH_ADMIN --> CLIENTES
  DASH_ADMIN --> PROVEEDORES
  DASH_ADMIN --> USUARIOS
  DASH_ADMIN --> CONFIG
  DASH_ADMIN --> GASTOS
  DASH_ADMIN --> NOMINA
  DASH_ADMIN --> SOCIOS
  DASH_ADMIN --> CONTINGENCIA
  DASH_ADMIN --> CONFIG_USR

  DASH_CAJERO --> POS
  DASH_CAJERO --> COCINA
  DASH_CAJERO --> PEDIDOS
  DASH_CAJERO --> CUENTAS
  DASH_CAJERO --> CAJA
  DASH_CAJERO --> HISTORIAL

  %% Contadora abre módulos en ventanas Toplevel independientes (no en content_frame)
  DASH_CONTADORA --> POS
  DASH_CONTADORA --> BOLETAS
  DASH_CONTADORA --> CAJA
  DASH_CONTADORA --> PEDIDOS
  DASH_CONTADORA --> COCINA
  DASH_CONTADORA --> CUENTAS
  DASH_CONTADORA --> HISTORIAL
  DASH_CONTADORA --> PAGOS
  DASH_CONTADORA --> MOVIMIENTOS
  DASH_CONTADORA --> INVENTARIO
  DASH_CONTADORA --> CATEGORIAS
  DASH_CONTADORA --> GASTOS
  DASH_CONTADORA --> CLIENTES
  DASH_CONTADORA --> PROVEEDORES
  DASH_CONTADORA --> REPORTES
  DASH_CONTADORA --> USUARIOS
  DASH_CONTADORA --> CONFIG

  MOVIMIENTOS --> HISTORIAL
  MOVIMIENTOS --> GASTOS
  MOVIMIENTOS --> CAJA
  MOVIMIENTOS --> REPORTES

  POS --> SERIES
  POS --> PRINTING
  POS --> VALIDACIONES
  BOLETAS --> SERIES
  BOLETAS --> PRINTING

  DASH_ADMIN --> TEMA
  DASH_CAJERO --> TEMA
  DASH_CONTADORA --> TEMA

  POS --> CONN
  COCINA --> CONN
  CAJA --> CONN
  INVENTARIO --> CONN

  CAJA --> LOGGER
  POS --> LOGGER
  BOLETAS --> LOGGER
```

---

## Inventario de Módulos

### Módulos Operacionales

| Módulo | Archivo | Auto-refresh | Descripción |
|--------|---------|:------------:|-------------|
| Bar / POS | `pos_module.py` | — | Punto de venta rápido. Búsqueda por nombre o código de barras, carrito, variantes de producto, métodos de pago, cuentas abiertas. |
| Cocina | `cocina_module.py` | 10 s | Pantalla dedicada para cocina. Muestra órdenes en cola con estado PENDIENTE → PREPARANDO → LISTO → ENTREGADO. Sidebar de inventario. |
| Pedidos | `pedidos_module.py` | 15 s | Gestión de pedidos de almuerzo. Pre-órdenes con estado, hora de entrega estimada. |
| Cuentas Abiertas | `cuentas_abiertas_module.py` | sí | Tabs por cliente. Visualizar y cobrar cuentas en curso. |
| Boletas de Entrada | `boletas_module.py` | — | Registro de entradas al club ($35.000 COP/persona, configurable). |
| Pagos | `pagos_module.py` | — | Cobro de cuentas abiertas con múltiples métodos de pago. |

### Módulos Administrativos

| Módulo | Archivo | Descripción |
|--------|---------|-------------|
| Caja Diaria | `caja_module.py` | Apertura con monto inicial, movimientos manuales, cierre con monto real vs esperado. |
| Inventario | `inventario_module.py` | KPIs de stock, ajustes manuales, movimientos, carga masiva. Alerta stock bajo. |
| Categorías | `categorias_module.py` | Gestión de categorías + productos anidados en la misma pantalla. |
| Gastos | `gastos_module.py` | Registro de egresos operacionales con categoría, método de pago y proveedor. |
| Clientes | `clientes_module.py` | Ficha de clientes: nombre, celular, documento, email. |
| Proveedores | `proveedores_module.py` | Ficha de proveedores + registro de compras y deudas (PENDIENTE/PAGADA). |
| Usuarios | `usuarios_module.py` | Alta/baja/edición de usuarios, cambio de contraseña, roles. |
| Configuración | `config_module.py` | Datos del negocio, NIT, precio boleta, ruta backup, URL sync, cocina web token. |
| Nómina | `nomina_module.py` | Gestión de empleados, turnos y pagos de nómina. |
| Socios | `socios_module.py` | Registro de socios, membresías y pagos de membresía. |
| Contingencia | `contingencia_module.py` | Modo de operación en contingencia / sin conectividad. |
| Config Usuarios | `config_usuarios_module.py` | Configuración de PIN y permisos por usuario. |

### Módulos de Consulta

| Módulo | Archivo | Descripción |
|--------|---------|-------------|
| Historial Ventas | `historial_ventas_module.py` | Filtros: hoy/ayer/semana/mes/personalizado. Paginación 100 registros. Reimprimir recibo. |
| Reportes | `reportes_module.py` | KPIs por período. Tablas: categorías, top productos, métodos de pago. Export Excel. Botones rápidos de fecha. |
| Movimientos | `movimientos_module.py` | Contenedor `ttk.Notebook` con 5 tabs: Resumen · Ingresos · Egresos · Caja · Reportes. |
| Buscador Ventas | `buscador_ventas.py` | Búsqueda por número de venta o nombre de cliente. |
| Reservas | `reservas_module.py` | Pre-órdenes de almuerzo con gestión de estado. |

---

## Patrón de Módulo (Convención)

```python
class MiModulo:
    def __init__(self, parent: tk.Frame, usuario: dict):
        self.parent = parent
        self.usuario = usuario
        self._crear_interfaz()   # Dibuja widgets en parent
        self._cargar_datos()     # Primera carga desde BD

    def detener(self):           # OPCIONAL — sólo si tiene after() activo
        self.auto_refresh = False
        if self._after_id:
            self.parent.after_cancel(self._after_id)
```

El dashboard llama a `detener()` antes de destruir el content_frame:

```python
def _limpiar_contenido(self):
    if self._instancia_modulo and hasattr(self._instancia_modulo, 'detener'):
        self._instancia_modulo.detener()
    for widget in self.content_frame.winfo_children():
        widget.destroy()
```

---

## Capas Compartidas

### `utils/tema_corporativo.py`
Fuente única de verdad para todo lo visual.

```
COLORES         Diccionario completo de colores del tema
FUENTES         Tuplas de font para Tkinter
crear_boton()   Botón estilizado con 9 tipos (primario, acento, error…)
crear_tarjeta_kpi()  Tarjeta con barra superior de color
aplicar_estilo_tabla()  Estilo Pocitos.Treeview para ttk.Treeview
format_money()  "$  12.500" (COP, sin decimales)
parse_money()   "$ 12.500" → 12500.0
```

### `database/connection.py`
```
get_connection()          Conexión bare, row_factory=sqlite3.Row, todos los PRAGMA
conexion_segura()         Context manager — commit automático, close garantizado
transaccion_atomica()     BEGIN IMMEDIATE — commit o rollback automático
ejecutar_con_retry()      Reintenta N veces en "database is locked"
```

### `models/series.py`
```
obtener_proximo_numero_venta()              POS-2026-000001  (thread-safe con Lock)
obtener_proximo_numero_boleta()             BOL-2026-000001  (thread-safe con Lock)
obtener_proximo_numero_factura_electronica() LP-2026-000001   (lanza excepción si no hay serie activa)
preview_numero_venta()                      Muestra siguiente sin incrementar
```

### `models/validaciones.py`
```
validar_resolucion_dian()   → {'puede_emitir': bool, 'nivel': 'ok'|'advertencia'|'bloqueado', 'mensaje': str}
                              Bloquea si: rango agotado, ≤50 restantes, fecha vencida o ≤3 días
                              Advierte si: ≤500 restantes o ≤30 días
verificar_pin_admin(pin)    → (valido: bool, nombre: str) — valida PIN de 4 dígitos contra tabla usuarios
```

### `utils/logger.py`
```
configurar_logger()   RotatingFileHandler → logs/app.log (5 MB × 3)
log_auditoria()       INSERT en tabla auditoria (requiere conn abierta)
```

### `utils/printing.py`
```
imprimir_recibo_venta(venta_id)    Genera PDF 80mm + abre con SO
imprimir_recibo_boleta(boleta_id)  Genera PDF 80mm + abre con SO
```
