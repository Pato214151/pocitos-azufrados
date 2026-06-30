# 01 — Contexto del Sistema (C4 Level 1)

## Diagrama de Contexto

```mermaid
C4Context
  title Sistema POS — Club Los Pocitos Azufrados

  Person(admin, "Administrador / Nelly", "Gestión total: ventas, caja, reportes, usuarios, inventario")
  Person(cajero, "Cajero", "Operaciones del turno: bar, pedidos, caja, cocina, historial")
  Person(contadora, "Contadora", "Panel ejecutivo con KPIs y resumen financiero")
  Person(cocina, "Personal de Cocina", "Ve y actualiza pedidos/almuerzos desde cualquier dispositivo con navegador en la red WiFi local")

  System(pos, "Sistema POS Pocitos Azufrados", "Aplicación de escritorio local. Gestiona ventas, inventario, caja, cocina, reportes y configuración del club.")
  System(cocina_web, "Servidor Web de Cocina", "Flask/Waitress en puerto 5000. Pantalla de almuerzos, inventario y preproducción. HTTP Basic Auth.")

  System_Ext(impresora, "Impresora / Visor PDF", "Recibe PDFs de 80mm generados por ReportLab y los abre con el visor del SO")
  System_Ext(escaner, "Escáner de Código de Barras USB", "Envía código + \\n al campo de búsqueda del POS")
  System_Ext(excel, "Microsoft Excel / LibreOffice", "Abre archivos .xlsx exportados desde el módulo de Reportes")
  System_Ext(backup_dir, "Sistema de Archivos (carpeta backup)", "Recibe copia diaria de la BD SQLite como archivo .db")
  System_Ext(navegador, "Navegador Web (celular / tablet)", "Accede a cocina_web via http://[IP-PC]:5000")

  Rel(admin, pos, "Usa todos los módulos")
  Rel(cajero, pos, "Usa Bar, Pedidos, Cocina, Cuentas, Caja, Historial")
  Rel(contadora, pos, "Usa panel ejecutivo especial")
  Rel(cocina, navegador, "Abre en celular/tablet")
  Rel(navegador, cocina_web, "HTTP Basic Auth — ve almuerzos, marca LISTO/ENTREGADO")

  Rel(pos, cocina_web, "Inicia como hilo daemon al arrancar")
  Rel(cocina_web, pos, "Comparten la misma BD SQLite")
  Rel(pos, impresora, "Genera PDF 80mm y abre con SO")
  Rel(escaner, pos, "Envía código de barras por HID USB")
  Rel(pos, excel, "Exporta reporte .xlsx")
  Rel(pos, backup_dir, "Copia BD diariamente (daemon)")
```

---

## Usuarios y Roles

| Rol | Usuario(s) | Acceso | Dashboard |
|-----|-----------|--------|-----------|
| `administrador` | admin, nelly | Todo | `dashboard.py` |
| `cajero` | cajero | Bar · Pedidos · Cocina · Cuentas · Caja · Historial | `dashboard_cajero.py` |
| `vendedor` | — | Igual que admin (por ahora) | `dashboard.py` |
| _(especial)_ | contadora | Panel ejecutivo propio | `dashboard_contadora.py` |

> **Nota**: El usuario `contadora` tiene un dashboard especial que se activa por **nombre**, no por rol.

---

## Límites del Sistema

### Dentro del sistema
- Autenticación local con bcrypt
- Base de datos SQLite (archivo único)
- Generación de PDFs de recibos
- Exportación a Excel
- Backup automático local
- Auditoría en BD

### Fuera del sistema (no implementado o futuro)
- Sincronización en la nube (`sync_url`, `sync_token` en configuración — preparado pero inactivo)
- Integración con pasarelas de pago electrónico
- Multi-sede / multi-terminal concurrente

### Implementado (anteriormente marcado como futuro)
- **Facturación electrónica DIAN** — flujo completo en `pos_module.py`: validación de resolución, solicitud de datos del cliente, generación de número `LP-XXXX`, inserción en `facturas_electronicas`. Ver `models/validaciones.py` y `models/series.py`.

---

## Stakeholders

| Parte interesada | Interés |
|-----------------|---------|
| Dueño del negocio | Ventas, gastos, utilidad, reportes |
| Administrador operativo | Inventario, usuarios, configuración |
| Cajero de turno | Rapidez en POS, cierre de caja sin errores |
| Personal de cocina | Ver pedidos pendientes sin usar teclado |
| Contador | Exportar datos a Excel para contabilidad |
