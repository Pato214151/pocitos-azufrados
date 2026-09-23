# Pocitos Azufrados — POS de escritorio para bar y restaurante

![Python](https://img.shields.io/badge/Python-3.9%2B-3776AB?logo=python&logoColor=white)
![Tkinter](https://img.shields.io/badge/UI-Tkinter-555)
![SQLite](https://img.shields.io/badge/DB-SQLite%20(WAL)-003B57?logo=sqlite&logoColor=white)
![Flask](https://img.shields.io/badge/Cocina-Flask%20%2B%20Waitress-000?logo=flask)
![pytest](https://img.shields.io/badge/Tests-pytest-0A9EDC?logo=pytest&logoColor=white)

Sistema de punto de venta de escritorio que el bar y restaurante de un club recreativo usa todos los días: ventas, caja diaria, inventario, cocina, nómina y reportes. Funciona **sin internet y sin servidor externo**.

---

## Qué problema resuelve

El club necesitaba registrar ventas y cierres de caja de forma confiable en un computador local, con varios roles trabajando al mismo tiempo, sin depender de conexión a internet.

## Funcionalidades

- **Ventas y comprobantes** con numeración consecutiva por serie.
- **Caja diaria:** apertura, movimientos y cierre.
- **Inventario** con registro de cada movimiento.
- **Módulo de cocina** servido por web en la red local (Flask + Waitress, puerto 5000): la cocina ve y actualiza los pedidos desde cualquier dispositivo con navegador.
- **Roles:** administrador, cajero, vendedor, contadora (panel con indicadores) y cocina.
- **Impresión térmica** de tickets (80 mm y 58 mm) y reportes en PDF con ReportLab.
- **Respaldos automáticos** de la base de datos.

## Decisiones técnicas

| Problema | Solución |
|---|---|
| Una venta no puede quedar a medias | Transacciones atómicas con *context manager* y rollback automático (`database/connection.py`). |
| Dos cajeros vendiendo a la vez podrían repetir un número de comprobante | Numeración *thread-safe* con un `threading.Lock` por serie (`models/series.py`). |
| Lecturas y escrituras simultáneas en SQLite | Modo `WAL` activado en la conexión. |
| Saber quién hizo cada operación sensible | Auditoría registrada dentro de la misma transacción que la operación. |

La arquitectura completa (modelo C4, modelo de datos, flujos clave y ADRs) está en [`docs/architecture/`](docs/architecture/README.md).

## Stack

Python · Tkinter · SQLite · Flask · Waitress · ReportLab · openpyxl · matplotlib · bcrypt · pytest

## Cómo correrlo

Requisitos: Windows y Python 3.9 o superior.

```bash
pip install -r requirements.txt
copy _licencia_secret.example.py _licencia_secret.py   # y pon tu propio valor
python setup.py       # crea la base de datos
python main.py
```

En el PC del club, `INSTALAR.bat` hace lo mismo automáticamente.

## Pruebas

```bash
pytest -q                  # 70 pruebas: ventas, series, caja, validaciones, integración
python sim_dia_completo.py # simula un día completo de operación y valida la integridad al final
```

## Seguridad y datos

- El repositorio **no incluye** la base de datos, los respaldos, los recibos ni los secretos: están en `.gitignore`.
- `_licencia_secret.py` es local; el repositorio solo trae [`_licencia_secret.example.py`](_licencia_secret.example.py) con un valor vacío.
- Contraseñas y PIN con bcrypt, bloqueo automático de pantalla por inactividad y autenticación HTTP Basic en el servidor web de cocina.

---

## Lo que salió mal (y cómo lo arreglé)

> El club lo usa todos los días en el bar y la cocina, y la página web del club (carpeta `pagina pocitos/`) supera las 6.000 visualizaciones cada 28 días. Estos son los problemas que más me enseñaron.

**Dos cajeros, el mismo número de recibo.**
En un bar lleno, dos cajeros pueden vender en el mismo segundo. Sin control, los dos podían sacar el mismo número de comprobante. Puse un bloqueo por serie para que la numeración sea consecutiva aunque haya ventas simultáneas.

**Una venta a medias.**
Si algo fallaba en la mitad de una venta, podía quedar registrado el cobro sin el descuento del inventario, o al revés. Ahora cada venta es una transacción atómica: o se guarda todo o no se guarda nada.

**Los PIN estaban en texto plano.**
En una revisión de seguridad encontré que los PIN de los usuarios se guardaban tal cual. Hice una migración que, al arrancar, convierte los PIN existentes a hash con bcrypt, sin que nadie tenga que volver a crear su usuario.

**Errores que desaparecían.**
Revisando el código encontré muchos `except Exception: pass` dentro de operaciones de venta, caja y cocina. Eso significa que si algo fallaba, el sistema seguía como si nada y no quedaba rastro. Lo documenté como deuda técnica con archivo y línea, y el plan es reemplazar cada uno por un registro en el log. Todavía no está terminado y lo digo así.

**Un método de pago que no aparecía.**
Había cuatro listas de métodos de pago escritas a mano en cuatro módulos distintos. En una faltaba Bancolombia. Lo corregí y dejé documentado que la solución de fondo es tener una sola fuente de verdad.
