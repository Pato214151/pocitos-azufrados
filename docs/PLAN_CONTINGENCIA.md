# Plan de Contingencia — Club Los Pocitos Azufrados

**Para:** Todo el personal (cajeros, vendedores, administrador)
**Aplica cuando:** El sistema POS no está disponible (corte de luz, falla del PC, error del programa)

---

## ¿Qué hago si se va la luz o falla el sistema?

### Paso 1 — Calma. Siga vendiendo con el talonario

Cada caja debe tener siempre un **talonario de recibos físicos** con numeración consecutiva.

- Tome el talonario y un bolígrafo.
- Por cada venta, llene **una hoja del talonario** con:
  1. Número de la hoja (ya impreso en el talonario)
  2. Fecha y hora exacta
  3. Nombre del cliente (si aplica)
  4. Productos vendidos: nombre, cantidad y precio
  5. Total cobrado
  6. Método de pago (efectivo / Nequi / Daviplata / TuLlave)
  7. Su nombre o firma

- Entregue la **copia blanca** al cliente como recibo.
- Guarde la **copia amarilla** en la caja.

> **Importante:** No se saltee números de talonario. Si comete un error, cruce la hoja y escriba "ANULADO".

---

## ¿Qué hago con el dinero y los pagos?

| Situación | Acción |
|-----------|--------|
| Pago en efectivo | Reciba el dinero normalmente, guárdelo en la caja |
| Pago con Nequi / Daviplata / TuLlave | Verifique la transferencia en el celular antes de entregar el producto |
| Cuenta abierta | Anote en el talonario "CUENTA ABIERTA" y el nombre del cliente |

---

## ¿Qué hago cuando vuelve la luz / se recupera el sistema?

### Lo hace el ADMINISTRADOR

1. Encienda el PC y abra el sistema normalmente.
2. Vaya al menú **SISTEMA → Contingencia**.
3. Por cada hoja del talonario, haga lo siguiente:

   a. En **Fecha/Hora**, escriba la fecha y hora que aparece en el talonario (ej. `2026-03-23 14:30`).
   b. En **N° Talonario**, escriba el número de la hoja.
   c. En **Cajero**, seleccione el cajero que atendió la venta.
   d. Busque cada producto y agréguelo. Si el precio fue diferente al del sistema, cámbielo.
   e. Seleccione el **Método de pago**.
   f. Haga clic en **Registrar Venta**.

4. Repita para cada hoja del talonario en orden.
5. Al terminar, haga clic en **Actualizar** en la tabla de historial para confirmar que todas quedaron registradas.

> El sistema descuenta el stock automáticamente al registrar cada venta.

---

## ¿Qué pasa si el corte duró varios días?

- Ingrese las ventas de cada día en orden cronológico.
- Si el talonario tiene ventas de días diferentes, ingréselas por día para que los reportes sean correctos.
- Si hay cuentas abiertas del talonario, créelas desde el módulo **Bar → Cuenta Abierta** una vez que el sistema esté funcionando.

---

## Checklist para el administrador al restaurar el sistema

- [ ] Verificar que el PC arrancó sin errores (el sistema muestra la pantalla de login normal)
- [ ] Contar las hojas del talonario usadas durante el corte
- [ ] Ingresar todas las ventas en **SISTEMA → Contingencia** (una por una, en orden)
- [ ] Verificar el stock en **Inventario** — debe coincidir con lo que queda físicamente
- [ ] Si hay diferencias de stock, usar **Ajuste** en Inventario con motivo "Ajuste post-contingencia"
- [ ] Hacer un backup manual desde **Configuracion → Mantenimiento → Crear Backup**
- [ ] Avisar al personal que el sistema está operativo nuevamente

---

## ¿Qué guardo y por cuánto tiempo?

| Documento | Tiempo mínimo |
|-----------|---------------|
| Hojas del talonario usadas | 5 años (obligatorio por DIAN) |
| Hojas anuladas | 5 años (no tirar) |
| Talonarios vacíos de repuesto | Siempre tener al menos 2 disponibles |

---

## Preguntas frecuentes

**¿Puedo vender sin el talonario?**
No. Sin talonario no hay soporte ante la DIAN ni control de caja. Si se acaba el talonario, avise al administrador de inmediato.

**¿Qué precio pongo si no recuerdo el precio exacto?**
Use la lista de precios pegada en la caja (el administrador debe tenerla impresa y actualizada). En caso de duda, cobre el precio de la última vez y anote la observación.

**¿Qué pasa si el sistema no reconoce un producto al ingresar la contingencia?**
Busque el producto por nombre. Si no aparece, es posible que se llame diferente. Si definitivamente no existe, contáctese con el administrador — él puede crearlo desde el módulo de Inventario antes de ingresar la venta.

**¿El cliente puede pedir factura electrónica de una venta de contingencia?**
Sí, pero solo después de que la venta quede registrada en el sistema. El administrador la genera desde **Historial de Ventas**.

---

## Contacto de soporte

En caso de falla técnica del sistema (no solo corte de luz):

- Anote el mensaje de error exacto que aparece en pantalla.
- Llame al administrador o al soporte técnico.
- **No intente reinstalar el programa** — puede perder datos.

---

*Versión 1.0 — Club Los Pocitos Azufrados — 2026*
