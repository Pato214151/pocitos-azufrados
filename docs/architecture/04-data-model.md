# 04 — Modelo de Datos

## Grupos de Tablas

```
┌─ IDENTIDAD ───────────────────┐  ┌─ VENTAS ──────────────────────────┐
│  usuarios                     │  │  ventas                            │
│  sesiones                     │  │  venta_detalle                     │
│  auditoria                    │  │  pagos                             │
└───────────────────────────────┘  │  ordenes_cocina                    │
                                   │  boletas_entrada                   │
┌─ CATÁLOGO ────────────────────┐  │  devoluciones                      │
│  categorias                   │  │  facturas_electronicas             │
│  subcategorias                │  └────────────────────────────────────┘
│  productos                    │
│  variantes_producto           │  ┌─ ALMUERZOS / COCINA WEB ───────────┐
└───────────────────────────────┘  │  reservas_almuerzo                 │
                                   │  ordenes_cocina                    │
┌─ CONTACTOS ───────────────────┐  │  almuerzo_checklist_template       │
│  clientes                     │  │  reserva_checklist                 │
│  proveedores                  │  │  tareas_preproduccion              │
│  compras_proveedor            │  └────────────────────────────────────┘
└───────────────────────────────┘
                                   ┌─ CAJA & GASTOS ────────────────────┐
┌─ SOCIOS ──────────────────────┐  │  caja_diaria                       │
│  socios                       │  │  movimientos_caja                  │
│  pagos_membresia              │  │  gastos                            │
└───────────────────────────────┘  └────────────────────────────────────┘

┌─ NÓMINA ──────────────────────┐  ┌─ INVENTARIO ───────────────────────┐
│  nomina_empleados             │  │  movimientos_inventario             │
│  nomina_turnos                │  └────────────────────────────────────┘
└───────────────────────────────┘
                                   ┌─ SYNC ─────────────────────────────┐
┌─ SERIES & CONFIG ─────────────┐  │  sync_queue                         │
│  series_facturacion           │  └────────────────────────────────────┘
│  series_boletas               │
│  metodos_pago                 │
│  configuracion                │
└───────────────────────────────┘
```

---

## Diagrama ER Principal

```mermaid
erDiagram
  usuarios {
    INTEGER id_usuario PK
    TEXT usuario UK
    TEXT nombre_completo
    TEXT contrasena_hash
    TEXT rol
    INTEGER activo
    INTEGER intentos_fallidos
    TEXT bloqueado_hasta
  }

  sesiones {
    INTEGER id_sesion PK
    INTEGER id_usuario FK
    TEXT fecha_inicio
    TEXT fecha_fin
  }

  categorias {
    INTEGER id_categoria PK
    TEXT nombre UK
    TEXT color
    TEXT icono
    INTEGER orden
  }

  subcategorias {
    INTEGER id_subcategoria PK
    INTEGER id_categoria FK
    TEXT nombre
  }

  productos {
    INTEGER id_producto PK
    TEXT codigo_barras UK
    TEXT nombre
    INTEGER id_categoria FK
    INTEGER id_subcategoria FK
    REAL precio_venta
    REAL precio_costo
    INTEGER stock_actual
    INTEGER stock_minimo
    TEXT unidad_medida
    INTEGER requiere_cocina
    INTEGER es_boleta_entrada
  }

  variantes_producto {
    INTEGER id_variante PK
    INTEGER id_producto FK
    TEXT nombre
    REAL precio_adicional
  }

  ventas {
    INTEGER id_venta PK
    TEXT numero_venta UK
    TEXT tipo
    TEXT estado
    TEXT cliente_nombre
    INTEGER mesa_numero
    REAL subtotal
    REAL descuento
    REAL total
    REAL total_pagado
    REAL saldo_pendiente
    TEXT metodo_pago
    INTEGER id_usuario FK
    TEXT fecha_creacion
  }

  venta_detalle {
    INTEGER id_detalle PK
    INTEGER id_venta FK
    INTEGER id_producto FK
    TEXT producto_nombre
    INTEGER cantidad
    REAL precio_unitario
    REAL total_linea
    TEXT estado_cocina
  }

  pagos {
    INTEGER id_pago PK
    INTEGER id_venta FK
    REAL valor
    TEXT metodo_pago
    TEXT fecha_pago
  }

  ordenes_cocina {
    INTEGER id_orden PK
    INTEGER id_venta FK
    INTEGER id_detalle FK
    TEXT producto_nombre
    INTEGER cantidad
    TEXT estado
    INTEGER prioridad
    TEXT hora_pedido
    TEXT hora_listo
  }

  boletas_entrada {
    INTEGER id_boleta PK
    TEXT numero_boleta UK
    INTEGER id_venta FK
    INTEGER cantidad_personas
    REAL precio_persona
    REAL total
    TEXT hora_entrada
    INTEGER id_usuario FK
  }

  caja_diaria {
    INTEGER id_caja PK
    TEXT fecha_apertura
    TEXT fecha_cierre
    TEXT usuario_apertura
    REAL monto_inicial
    REAL total_ventas
    REAL total_gastos
    REAL monto_esperado
    REAL monto_real
    REAL diferencia
    TEXT estado
  }

  movimientos_caja {
    INTEGER id_movimiento PK
    INTEGER id_caja FK
    TEXT tipo
    TEXT concepto
    REAL valor
    TEXT usuario
  }

  gastos {
    INTEGER id_gasto PK
    TEXT fecha
    TEXT descripcion
    REAL valor
    TEXT categoria
    TEXT tipo_gasto
    TEXT proveedor
    TEXT usuario_registro
  }

  clientes {
    INTEGER id_cliente PK
    TEXT nombre
    TEXT celular
    TEXT documento
    TEXT email
  }

  proveedores {
    INTEGER id_proveedor PK
    TEXT nombre
    TEXT nit
    TEXT contacto
    TEXT telefono
  }

  compras_proveedor {
    INTEGER id_compra PK
    INTEGER id_proveedor FK
    TEXT descripcion
    REAL valor
    TEXT estado_pago
    TEXT fecha
  }

  movimientos_inventario {
    INTEGER id_movimiento PK
    INTEGER id_producto FK
    TEXT tipo
    INTEGER cantidad
    INTEGER stock_anterior
    INTEGER stock_nuevo
    TEXT usuario
    TEXT fecha
  }

  auditoria {
    INTEGER id_auditoria PK
    TEXT tabla_afectada
    INTEGER id_registro
    TEXT accion
    TEXT usuario
    TEXT comentario
    TEXT fecha_hora
  }

  usuarios ||--o{ sesiones : "tiene"
  usuarios ||--o{ ventas : "realiza"
  categorias ||--o{ subcategorias : "contiene"
  categorias ||--o{ productos : "clasifica"
  subcategorias ||--o{ productos : "clasifica"
  productos ||--o{ variantes_producto : "tiene"
  productos ||--o{ venta_detalle : "aparece en"
  productos ||--o{ movimientos_inventario : "registra"
  ventas ||--o{ venta_detalle : "contiene"
  ventas ||--o{ pagos : "recibe"
  ventas ||--o{ ordenes_cocina : "genera"
  ventas ||--o{ boletas_entrada : "incluye"
  venta_detalle ||--o{ ordenes_cocina : "origina"
  caja_diaria ||--o{ movimientos_caja : "tiene"
  proveedores ||--o{ compras_proveedor : "tiene"

  reservas_almuerzo {
    INTEGER id_reserva PK
    TEXT numero_reserva UK
    INTEGER id_venta FK
    TEXT cliente_nombre
    INTEGER cantidad_personas
    TEXT tipo_almuerzo
    TEXT estado
    INTEGER notificado_listo
    TEXT hora_reserva
    TEXT hora_entrega_estimada
  }

  facturas_electronicas {
    INTEGER id_factura PK
    INTEGER id_venta FK
    TEXT numero_factura UK
    TEXT cliente_nombre
    TEXT cliente_nit
    TEXT cliente_email
    TEXT fecha_emision
  }

  almuerzo_checklist_template {
    INTEGER id PK
    TEXT tipo_almuerzo
    TEXT item
    INTEGER orden
  }

  reserva_checklist {
    INTEGER id PK
    INTEGER id_reserva FK
    TEXT item
    INTEGER completado
    TEXT usuario
    TEXT hora_completado
  }

  tareas_preproduccion {
    INTEGER id PK
    TEXT fecha
    TEXT descripcion
    TEXT cantidad
    INTEGER completada
    TEXT hora_completado
    TEXT usuario
  }

  socios {
    INTEGER id_socio PK
    TEXT nombre
    TEXT documento UK
    TEXT celular
    TEXT email
    TEXT tipo_membresia
    TEXT fecha_ingreso
    INTEGER activo
  }

  pagos_membresia {
    INTEGER id_pago PK
    INTEGER id_socio FK
    REAL valor
    TEXT periodo
    TEXT fecha_pago
    TEXT metodo_pago
  }

  nomina_empleados {
    INTEGER id_empleado PK
    TEXT nombre
    TEXT documento UK
    TEXT cargo
    REAL salario_base
    INTEGER activo
  }

  nomina_turnos {
    INTEGER id_turno PK
    INTEGER id_empleado FK
    TEXT fecha
    TEXT hora_entrada
    TEXT hora_salida
    REAL valor_turno
  }

  ventas ||--o{ reservas_almuerzo : "genera"
  ventas ||--o{ facturas_electronicas : "tiene"
  reservas_almuerzo ||--o{ reserva_checklist : "genera"
  almuerzo_checklist_template ||--o{ reserva_checklist : "plantilla"
  socios ||--o{ pagos_membresia : "tiene"
  nomina_empleados ||--o{ nomina_turnos : "tiene"
```

---

## Tablas de Configuración y Series

### `configuracion` (clave/valor)

| Clave | Valor por defecto | Descripción |
|-------|-------------------|-------------|
| `nombre_negocio` | Club Los Pocitos Azufrados | Aparece en recibos PDF |
| `ubicacion` | Tocaima, Cundinamarca | Aparece en recibos PDF |
| `nit` | _(vacío)_ | Número de identificación tributaria |
| `precio_boleta_persona` | 35000 | COP — leído por `boletas_module.py` |
| `metodos_pago_habilitados` | EFECTIVO,NEQUI,DAVIPLATA,… | CSV — leído por POS y gastos |
| `backup_ruta` | _(vacío)_ | Ruta del directorio de backups |
| `backup_intervalo_horas` | 24 | Intervalo del daemon de backup |
| `categorias_gastos` | Compras Insumos,… | CSV — leído por gastos_module |

### `series_facturacion` y `series_boletas`

```
Formato: {prefijo}-{año}-{consecutivo:06d}
Ejemplo ventas: POS-2026-000001
Ejemplo boletas: BOL-2026-000001

El año se resetea automáticamente cuando cambia el año calendario.
Thread-safe via threading.Lock en models/series.py.
```

---

## Índices de Rendimiento (22 total)

```sql
-- Búsqueda de productos (POS con escáner)
idx_productos_codigo    ON productos(codigo_barras)
idx_productos_nombre    ON productos(nombre)
idx_productos_categoria ON productos(id_categoria)
idx_productos_activo    ON productos(activo)

-- Consultas de ventas
idx_ventas_estado       ON ventas(estado)
idx_ventas_fecha        ON ventas(fecha_creacion)
idx_ventas_numero       ON ventas(numero_venta)
idx_venta_detalle_venta ON venta_detalle(id_venta)

-- Cocina (auto-refresh)
idx_ordenes_cocina_estado ON ordenes_cocina(estado)
idx_ordenes_cocina_venta  ON ordenes_cocina(id_venta)

-- Reportes financieros
idx_boletas_fecha       ON boletas_entrada(hora_entrada)
idx_gastos_fecha        ON gastos(fecha)
idx_gastos_categoria    ON gastos(categoria)
idx_caja_estado         ON caja_diaria(estado)
idx_pagos_venta         ON pagos(id_venta)
idx_movimientos_inv     ON movimientos_inventario(id_producto)

-- Auditoría y sync
idx_auditoria_tabla     ON auditoria(tabla_afectada)
idx_sync_estado         ON sync_queue(estado)
```

---

## Restricciones de Dominio (CHECK)

```sql
usuarios.rol           IN ('administrador','cajero','vendedor')
productos.unidad_medida IN ('unidad','litro','kilo','porcion','boleta')
ventas.tipo            IN ('normal','cuenta_abierta','boleta','para_llevar')
ventas.estado          IN ('ABIERTA','CERRADA','PAGADA','ANULADA')
venta_detalle.estado_cocina IN ('N/A','PENDIENTE','PREPARANDO','LISTO','ENTREGADO')
ordenes_cocina.estado  IN ('PENDIENTE','PREPARANDO','LISTO','ENTREGADO','CANCELADO')
gastos.tipo_gasto      IN ('OPERATIVO','COMPRA_INVENTARIO','SERVICIOS','NOMINA','OTRO')
caja_diaria.estado     IN ('ABIERTA','CERRADA')
movimientos_inventario.tipo IN ('ENTRADA','SALIDA','AJUSTE','VENTA','DEVOLUCION')
compras_proveedor.estado_pago IN ('PENDIENTE','PAGADA')
movimientos_caja.tipo  IN ('INGRESO','EGRESO')
sync_queue.accion      IN ('INSERT','UPDATE','DELETE')
sync_queue.estado      IN ('PENDIENTE','ENVIANDO','COMPLETADO','ERROR')
```
