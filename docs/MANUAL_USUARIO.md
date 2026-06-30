# Manual de Usuario — Club Los Pocitos Azufrados
## Sistema POS — Guía Rápida de Operación Diaria

---

## ROLES DE USUARIO

| Usuario       | Acceso                                                   |
|---------------|----------------------------------------------------------|
| Administrador | Todo: bar, boletas, caja, inventario, reportes, usuarios |
| Cajero        | Bar, pedidos, cocina, cuentas abiertas, caja, historial  |
| Contadora     | Panel especial con KPIs y acceso a todos los módulos     |

---

## INICIO DEL DÍA — CHECKLIST

**Antes de atender al primer cliente:**

1. Abrir la app → iniciar sesión con tu usuario y contraseña
2. Ir a **Caja** → botón **Abrir Caja** → ingresar el monto inicial en efectivo
3. Verificar que aparezca `Estado: ABIERTA` con la fecha de hoy
4. *(Si hay tablet de cocina)* Confirmar que `http://[IP-PC]:5000` carga en el navegador

> Si no abres la caja, el sistema mostrará una advertencia al intentar vender.
> Los movimientos de dinero quedan sin registrar si la caja está cerrada.

---

## MÓDULO: BOLETAS DE ENTRADA

**Cuándo usarlo:** cada vez que ingresa un visitante al club.

**Precio actual:** $35.000 por persona (configurable en Configuración → Datos del Negocio)

### Pasos para vender una boleta:

1. Ir a **Boletas de Entrada** en el menú lateral
2. Ingresar el **nombre del visitante** (requerido)
3. Ingresar la **cantidad de personas**
4. Verificar el **total calculado** automáticamente
5. Seleccionar el **método de pago**: Efectivo, Nequi, Daviplata, Bancolombia, Transferencia
6. Clic en **Registrar Entrada**
7. El sistema genera el recibo PDF y lo abre automáticamente para imprimir

**Resultado:** se registra en ventas como `tipo: boleta`, se crea el movimiento en caja, y queda en el historial.

---

## MÓDULO: BAR (POS — Punto de Venta)

**Cuándo usarlo:** para vender bebidas, licores, snacks, postres y almuerzos.

### Venta normal (pago inmediato):

1. Ir a **Bar** en el menú lateral
2. Seleccionar la **categoría** de producto (pestañas en la parte superior)
3. Clic en el botón del producto para **agregarlo al carrito**
   - Si el producto tiene variantes (ej. tamaño), aparece un diálogo para elegir
   - Si es almuerzo, aparece un diálogo para ingresar nombre del cliente y hora de entrega
4. Ajustar cantidades desde el carrito (botones `+` / `−`)
5. Ingresar el **nombre del cliente** si se requiere
6. Seleccionar el **método de pago**
7. Clic en **Cobrar** → confirmar el total
8. El PDF del recibo se genera y abre automáticamente

> Los productos que requieren preparación (Empanada, Deditos, Limonada, etc.) generan automáticamente una orden en cocina.
> Los almuerzos van a **Reservas de Almuerzo**, no a órdenes de cocina, para evitar duplicados.

### Abrir cuenta (pago al final):

1. Seguir los pasos 1–5 anteriores
2. En lugar de **Cobrar**, clic en **Cuenta Abierta**
3. La cuenta queda en **Cuentas Abiertas** para cobrarla luego

---

## MÓDULO: PEDIDOS

**Cuándo usarlo:** para gestionar órdenes que se reciben en la barra o en la tablet de cocina.

- Muestra los pedidos activos agrupados por estado: **Pendiente → Preparando → Listo → Entregado**
- Desde aquí se puede cambiar el estado de cada ítem
- La **cocina web** (tablet) también permite hacer estos cambios desde el navegador

---

## MÓDULO: COCINA (tablet/celular)

**Acceso:** desde cualquier dispositivo en la misma red WiFi
**URL:** `http://[IP-del-computador]:5000`
**Usuario:** `cocina`
**Clave:** `cocina2025` (cambiar en Configuración → cocina_web_token)

### Estados de un pedido:

| Estado      | Descripción                        | Acción disponible |
|-------------|------------------------------------|-------------------|
| PENDIENTE   | Orden recibida, sin preparar       | → Preparar        |
| PREPARANDO  | En proceso en cocina               | → Listo           |
| LISTO       | Preparado, esperando entrega       | → Entregado       |
| ENTREGADO   | Entregado al cliente               | —                 |

---

## MÓDULO: CUENTAS ABIERTAS

**Cuándo usarlo:** para cobrar cuentas pendientes de clientes que pidieron fiado o abrieron cuenta.

1. Ir a **Cuentas Abiertas**
2. Seleccionar la cuenta de la lista (lado derecho) o del combo (lado izquierdo)
3. Verificar el **saldo pendiente** que aparece en la info
4. Ingresar el **monto a pagar** (puede ser parcial)
5. Seleccionar método de pago y opcionalmente una referencia
6. Clic en **Registrar Pago**

> Si el pago cubre el total, la cuenta se cierra automáticamente (estado: PAGADA).

---

## MÓDULO: CAJA

### Apertura (inicio del día):

1. Clic en **Abrir Caja**
2. Ingresar el **monto inicial** en efectivo que hay en la caja
3. Confirmar → estado cambia a `ABIERTA`

### Registrar gastos durante el día:

Ir a **Gastos** → completar descripción, monto, categoría y método de pago.
Esto descuenta del monto esperado en caja.

### Cierre (fin del día):

1. Ir a **Caja** → clic en **Cerrar Caja**
2. Contar el dinero físico e ingresar el **monto real** en caja
3. El sistema calcula la diferencia:
   - `Diferencia = 0` → cuadre perfecto
   - `Diferencia negativa` → faltante (revisar transacciones)
   - `Diferencia positiva` → sobrante
4. Opcionalmente ingresar observaciones y confirmar cierre

**Fórmula de cuadre:**

```
Monto Esperado = Monto Inicial + Total Ventas + Total Boletas − Total Gastos
Diferencia     = Monto Real − Monto Esperado
```

---

## MÓDULO: HISTORIAL DE VENTAS

- Buscar ventas por fecha, número o cliente
- Ver el detalle de cada venta (ítems, método de pago, usuario)
- **Reimprimir recibo**: seleccionar una venta → clic en **Imprimir Recibo**
- **Anular venta**: solo administradores pueden anular; queda como estado `ANULADA` en el historial

---

## MÓDULO: GASTOS

**Cuándo usarlo:** para registrar cualquier salida de dinero operativa (hielo, servilletas, gas, nómina diaria, etc.)

1. Ir a **Gastos** (dentro de Movimientos)
2. Completar: descripción, valor, categoría, método de pago
3. Clic en **Guardar** → queda registrado y descuenta del cierre de caja

---

## CIERRE DEL DÍA — CHECKLIST

1. Cobrar todas las **cuentas abiertas** pendientes
2. Verificar que todos los pedidos de cocina estén en **ENTREGADO**
3. Ir a **Caja** → registrar **gastos** del día que no se hayan ingresado
4. Ir a **Caja** → **Cerrar Caja** → ingresar monto real y confirmar
5. Verificar el resumen: ventas, boletas, gastos, diferencia

---

## ERRORES FRECUENTES Y SOLUCIONES

| Error | Causa | Solución |
|-------|-------|----------|
| "No hay caja abierta" al vender | Se olvidó abrir la caja | Ir a Caja → Abrir Caja |
| El carrito no muestra los botones | Pantalla muy pequeña o bug de resolución | Ampliar la ventana o reiniciar el módulo |
| "Error al registrar pago" | La venta ya fue pagada o el monto excede el saldo | Verificar saldo en Cuentas Abiertas |
| La cocina web no carga | El servidor no arrancó o hay problema de red | Reiniciar la app principal; verificar que estén en la misma WiFi |
| PDF no se abre | No hay visor PDF instalado | Instalar Adobe Reader o el visor de Windows |
| "Hash inválido" al iniciar sesión | Contraseña corrupta o bcrypt no instalado | Ejecutar `pip install bcrypt` y reiniciar |

---

## ACCESOS RÁPIDOS (TECLADO)

| Acción | Combinación |
|--------|-------------|
| Buscar producto (barra de búsqueda) | Escribir directamente en el campo de búsqueda |
| Escanear código de barras | Apuntar escáner al producto → Enter automático |
| Navegar módulos | Clic en el sidebar izquierdo |

---

## CONTINGENCIA (CORTE DE LUZ / FALLA DEL SISTEMA)

Si el sistema no está disponible, use el **talonario de recibos físicos** para seguir vendiendo. Al restaurarse el sistema, el administrador ingresa esas ventas desde **SISTEMA → Contingencia**.

Consulte el instructivo completo en: `docs/PLAN_CONTINGENCIA.md`

---

## CONTACTO Y SOPORTE TÉCNICO

El sistema guarda logs en `data/logs/pocitos.log`. En caso de error grave, compartir ese archivo para diagnóstico.

*Club Los Pocitos Azufrados — Tocaima, Cundinamarca*
