# Pocitos Azufrados — POS de escritorio para bar y restaurante

![Python](https://img.shields.io/badge/Python-3.9%2B-3776AB?logo=python&logoColor=white)
![Tkinter](https://img.shields.io/badge/UI-Tkinter-555)
![SQLite](https://img.shields.io/badge/DB-SQLite%20(WAL)-003B57?logo=sqlite&logoColor=white)
![Flask](https://img.shields.io/badge/Cocina-Flask%20%2B%20Waitress-000?logo=flask)
![pytest](https://img.shields.io/badge/Tests-pytest-0A9EDC?logo=pytest&logoColor=white)

Sistema de punto de venta de escritorio para el bar y restaurante de un club recreativo: ventas, caja diaria, inventario, cocina, nómina y reportes. Funciona **sin internet y sin servidor externo**.

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
