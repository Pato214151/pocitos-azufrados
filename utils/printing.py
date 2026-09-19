"""
utils/printing.py - Club Los Pocitos Azufrados
Generación de recibos PDF con ReportLab.

Funciones públicas:
    generar_recibo_venta(venta_id)   → path del PDF generado
    generar_recibo_boleta(boleta_id) → path del PDF generado
    imprimir_recibo_venta(venta_id)  → genera y abre el PDF
    imprimir_recibo_boleta(boleta_id)→ genera y abre el PDF
"""

import os
import sys
import datetime
import subprocess

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from database.connection import conexion_segura
from utils.tema_corporativo import format_money as _format_money_base

try:
    from reportlab.lib.pagesizes import A7, A4
    from reportlab.lib.units import mm
    from reportlab.lib.colors import HexColor, black, white
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    )
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    REPORTLAB_OK = True
except ImportError:
    REPORTLAB_OK = False

try:
    from escpos.printer import Win32Raw
    ESCPOS_OK = True
except ImportError:
    ESCPOS_OK = False


# ─────────────────────────────────────────────────────────────────────────────
#  Helpers internos
# ─────────────────────────────────────────────────────────────────────────────

def _format_money(valor):
    """Delegado a tema_corporativo.format_money para consistencia."""
    if valor is None:
        return "$ 0"
    return _format_money_base(valor)


def _recibos_dir():
    """Carpeta data/recibos (la crea si no existe)."""
    ruta = os.path.join(BASE_DIR, "data", "recibos")
    os.makedirs(ruta, exist_ok=True)
    return ruta


def _leer_config_impresora(conn):
    """Lee todos los valores de configuración de impresora en una sola consulta.
    Retorna dict con claves: ancho_mm (int), modo (str), nombre (str).
    Recibe una conexión ya abierta para evitar abrir múltiples conexiones."""
    claves = ('impresora_ancho_mm', 'impresora_modo', 'impresora_nombre')
    rows = conn.execute(
        "SELECT clave, valor FROM configuracion WHERE clave IN (?,?,?)", claves
    ).fetchall()
    cfg = {r['clave']: r['valor'] for r in rows}

    ancho_str = cfg.get('impresora_ancho_mm', '')
    ancho_mm = int(ancho_str) if ancho_str in ('58', '80') else 80

    modo = 'escpos' if cfg.get('impresora_modo') == 'escpos' else 'pdf'
    nombre = (cfg.get('impresora_nombre') or '').strip()

    return {'ancho_mm': ancho_mm, 'modo': modo, 'nombre': nombre}


def _ancho_ticket_mm():
    """Lee el ancho configurado del ticket en mm (80 o 58). Default: 80.
    Abre su propia conexión — usar _leer_config_impresora(conn) cuando ya hay una abierta."""
    try:
        with conexion_segura() as conn:
            return _leer_config_impresora(conn)['ancho_mm']
    except Exception:
        pass
    return 80


def _abrir_pdf(ruta):
    """Abre el PDF con el visor predeterminado del sistema operativo."""
    try:
        if sys.platform == "win32":
            os.startfile(ruta)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", ruta])
        else:
            subprocess.Popen(["xdg-open", ruta])
    except Exception as e:
        import logging
        logging.getLogger("pocitos").error(f"No se pudo abrir el PDF '{ruta}': {e}")
        # Mostrar la ruta al usuario para que pueda abrirlo manualmente
        try:
            import tkinter
            from tkinter import messagebox
            messagebox.showinfo(
                "PDF generado",
                f"El recibo fue generado pero no pudo abrirse automáticamente.\n\nRuta:\n{ruta}"
            )
        except Exception:
            pass


def _verificar_reportlab():
    """Avisa claramente si falta la librería ReportLab."""
    if not REPORTLAB_OK:
        raise ImportError(
            "ReportLab no está instalado.\n"
            "Ejecute:  pip install reportlab"
        )


def _estilos_recibo():
    """Devuelve un dict con los estilos de párrafo para el recibo.
    Diseñado para impresión B&N: sin colores rellenos, solo negro puro.
    """
    styles = getSampleStyleSheet()

    titulo = ParagraphStyle(
        "titulo_recibo",
        parent=styles["Normal"],
        fontSize=14,
        fontName="Helvetica-Bold",
        textColor=black,
        alignment=TA_CENTER,
        spaceAfter=1 * mm,
    )
    subtitulo = ParagraphStyle(
        "subtitulo_recibo",
        parent=styles["Normal"],
        fontSize=8,
        fontName="Helvetica",
        textColor=black,
        alignment=TA_CENTER,
        spaceAfter=0.5 * mm,
    )
    normal = ParagraphStyle(
        "normal_recibo",
        parent=styles["Normal"],
        fontSize=8,
        fontName="Helvetica",
        textColor=black,
        spaceAfter=0.8 * mm,
    )
    negrita = ParagraphStyle(
        "negrita_recibo",
        parent=styles["Normal"],
        fontSize=8,
        fontName="Helvetica-Bold",
        textColor=black,
        spaceAfter=0.8 * mm,
    )
    total_style = ParagraphStyle(
        "total_recibo",
        parent=styles["Normal"],
        fontSize=13,
        fontName="Helvetica-Bold",
        textColor=black,
        alignment=TA_CENTER,
        spaceAfter=2 * mm,
    )
    pie = ParagraphStyle(
        "pie_recibo",
        parent=styles["Normal"],
        fontSize=7,
        fontName="Helvetica-Oblique",
        textColor=black,
        alignment=TA_CENTER,
        spaceAfter=0.5 * mm,
    )
    return {
        "titulo": titulo, "subtitulo": subtitulo,
        "normal": normal, "negrita": negrita,
        "total": total_style, "pie": pie,
    }


def _label_metodo_pago(metodo):
    """Formatea el método de pago para mostrar en el recibo."""
    if not metodo:
        return "—"
    m = str(metodo).upper()
    if m == "NEQUI":
        return "Nequi"
    if m in ("TULLAVE", "TU LLAVE", "TU_LLAVE"):
        return "TuLlave"
    if m == "EFECTIVO":
        return "Efectivo"
    if m == "TRANSFERENCIA":
        return "Transferencia"
    if m.startswith("CONSIGNACION:"):
        nombre = metodo.split(":", 1)[1].strip()
        return f"Consignacion\nA nombre de: {nombre}" if nombre else "Consignacion"
    if m == "CONSIGNACION":
        return "Consignacion"
    return metodo


def _datos_negocio(conn):
    """Lee nombre, ubicación y teléfono desde la tabla configuracion."""
    keys = ['nombre_negocio', 'ubicacion', 'telefono', 'nit']
    rows = conn.execute(
        f"SELECT clave, valor FROM configuracion WHERE clave IN ({','.join('?'*len(keys))})",
        keys
    ).fetchall()
    return {r['clave']: r['valor'] for r in rows}


# ─────────────────────────────────────────────────────────────────────────────
#  Recibo de Venta
# ─────────────────────────────────────────────────────────────────────────────

def generar_recibo_venta(venta_id):
    """Genera un PDF de recibo para la venta dada.

    Retorna la ruta absoluta del archivo generado.
    Lanza ImportError si ReportLab no está disponible.
    Lanza ValueError si la venta no existe.
    """
    _verificar_reportlab()

    with conexion_segura() as conn:
        venta = conn.execute(
            "SELECT * FROM ventas WHERE id_venta = ?", (venta_id,)
        ).fetchone()
        if not venta:
            raise ValueError(f"Venta {venta_id} no encontrada")

        detalles = conn.execute(
            "SELECT * FROM venta_detalle WHERE id_venta = ? ORDER BY id_detalle",
            (venta_id,)
        ).fetchall()

        negocio  = _datos_negocio(conn)
        cfg_imp  = _leer_config_impresora(conn)   # una sola conexión para todo

    estilos = _estilos_recibo()
    nombre_archivo = f"recibo_venta_{venta['numero_venta']}.pdf"
    ruta = os.path.join(_recibos_dir(), nombre_archivo)

    ancho_mm = cfg_imp['ancho_mm']
    ancho  = ancho_mm * mm
    alto   = 220 * mm
    margen = 4 * mm if ancho_mm == 58 else 5 * mm
    doc = SimpleDocTemplate(
        ruta,
        pagesize=(ancho, alto),
        leftMargin=margen, rightMargin=margen,
        topMargin=6 * mm, bottomMargin=6 * mm,
    )

    story = []

    # ── Encabezado ──
    story.append(Paragraph(negocio.get('nombre_negocio', 'Club Los Pocitos Azufrados'), estilos["titulo"]))
    if negocio.get('ubicacion'):
        story.append(Paragraph(negocio['ubicacion'], estilos["subtitulo"]))
    if negocio.get('telefono'):
        story.append(Paragraph(f"Tel: {negocio['telefono']}", estilos["subtitulo"]))
    if negocio.get('nit'):
        story.append(Paragraph(f"NIT: {negocio['nit']}", estilos["subtitulo"]))

    story.append(HRFlowable(width="100%", thickness=1.5, color=black, spaceAfter=2 * mm))

    # ── Datos de la venta ──
    fecha_str = str(venta['fecha_creacion'])[:16] if venta['fecha_creacion'] else ''
    story.append(Paragraph(f"<b>No.:</b> {venta['numero_venta']}", estilos["normal"]))
    story.append(Paragraph(f"<b>Fecha:</b> {fecha_str}", estilos["normal"]))
    if venta['cliente_nombre']:
        story.append(Paragraph(f"<b>Cliente:</b> {venta['cliente_nombre']}", estilos["normal"]))
    if venta['mesa_numero']:
        story.append(Paragraph(f"<b>Mesa:</b> {venta['mesa_numero']}", estilos["normal"]))
    if venta['notas']:
        story.append(Paragraph(f"<b>Notas:</b> {venta['notas']}", estilos["normal"]))

    # Método de pago — con detalle Nequi/TuLlave/Consignación
    metodo_display = _label_metodo_pago(venta['metodo_pago'])
    lineas_metodo = metodo_display.split('\n')
    for i, linea in enumerate(lineas_metodo):
        story.append(Paragraph(f"<b>Pago:</b> {linea}" if i == 0
                               else f"          {linea}", estilos["normal"]))

    story.append(HRFlowable(width="100%", thickness=0.5, color=black, spaceAfter=2 * mm))

    # ── Tabla de productos ──
    col_ancho = [34 * mm, 8 * mm, 22 * mm]
    data = [["Producto", "Cant", "Subtotal"]]
    for det in detalles:
        data.append([
            det['producto_nombre'] or '—',
            str(int(det['cantidad'])),
            _format_money(det['total_linea']),
        ])

    tabla_estilo = TableStyle([
        ("FONTNAME",      (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, -1), 8),
        ("ALIGN",         (1, 0), (1, -1),  "CENTER"),
        ("ALIGN",         (2, 0), (2, -1),  "RIGHT"),
        ("TEXTCOLOR",     (0, 0), (-1, -1), black),
        ("LINEBELOW",     (0, 0), (-1, 0),  1, black),
        ("LINEABOVE",     (0, 0), (-1, 0),  1, black),
        ("LINEBELOW",     (0, -1), (-1, -1), 0.5, black),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [white, HexColor("#F0F0F0")]),
        ("TOPPADDING",    (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING",   (0, 0), (0, -1),  0),
    ])

    tabla = Table(data, colWidths=col_ancho)
    tabla.setStyle(tabla_estilo)
    story.append(tabla)
    story.append(Spacer(1, 2 * mm))

    # ── Totales ──
    if venta['descuento']:
        story.append(Paragraph(f"Subtotal:  {_format_money(venta['subtotal'])}", estilos["normal"]))
        story.append(Paragraph(f"Descuento: -{_format_money(venta['descuento'])}", estilos["normal"]))

    story.append(HRFlowable(width="100%", thickness=1.5, color=black, spaceAfter=2 * mm))
    story.append(Paragraph(f"TOTAL: {_format_money(venta['total'])}", estilos["total"]))
    story.append(HRFlowable(width="100%", thickness=1.5, color=black, spaceAfter=3 * mm))

    story.append(Paragraph("Gracias por su visita!", estilos["pie"]))
    story.append(Paragraph(negocio.get('ubicacion', 'Tocaima, Cundinamarca'), estilos["pie"]))

    doc.build(story)
    return ruta


# ─────────────────────────────────────────────────────────────────────────────
#  Recibo de Boleta de Entrada
# ─────────────────────────────────────────────────────────────────────────────

def generar_recibo_boleta(boleta_id):
    """Genera un PDF de recibo para la boleta de entrada dada.

    Retorna la ruta absoluta del archivo generado.
    """
    _verificar_reportlab()

    with conexion_segura() as conn:
        boleta = conn.execute(
            "SELECT * FROM boletas_entrada WHERE id_boleta = ?", (boleta_id,)
        ).fetchone()
        if not boleta:
            raise ValueError(f"Boleta {boleta_id} no encontrada")

        negocio  = _datos_negocio(conn)
        cfg_imp  = _leer_config_impresora(conn)   # una sola conexión para todo

    estilos = _estilos_recibo()
    nombre_archivo = f"boleta_{boleta['numero_boleta']}.pdf"
    ruta = os.path.join(_recibos_dir(), nombre_archivo)

    ancho_mm = cfg_imp['ancho_mm']
    ancho = ancho_mm * mm
    alto  = 150 * mm
    margen = 4 * mm if ancho_mm == 58 else 5 * mm
    doc = SimpleDocTemplate(
        ruta,
        pagesize=(ancho, alto),
        leftMargin=margen, rightMargin=margen,
        topMargin=6 * mm, bottomMargin=6 * mm,
    )

    story = []

    story.append(Paragraph(negocio.get('nombre_negocio', 'Club Los Pocitos Azufrados'), estilos["titulo"]))
    if negocio.get('ubicacion'):
        story.append(Paragraph(negocio['ubicacion'], estilos["subtitulo"]))

    story.append(HRFlowable(width="100%", thickness=1, color=HexColor("#1B5E20"), spaceAfter=3 * mm))

    story.append(Paragraph("BOLETA DE ENTRADA", estilos["titulo"]))
    story.append(Spacer(1, 2 * mm))

    hora_str = str(boleta['hora_entrada'])[:16] if boleta['hora_entrada'] else '—'
    datos = [
        ("Boleta:",      boleta['numero_boleta']),
        ("Visitante:",   boleta['nombre_visitante']),
        ("Documento:",   boleta['documento_visitante'] or '—'),
        ("Personas:",    str(boleta['cantidad_personas'])),
        ("Fecha/Hora:",  hora_str),
        ("Método Pago:", boleta['metodo_pago'] or '—'),
    ]
    for label, valor in datos:
        story.append(Paragraph(f"<b>{label}</b> {valor}", estilos["normal"]))

    story.append(HRFlowable(width="100%", thickness=1, color=HexColor("#1B5E20"), spaceAfter=2 * mm))
    story.append(Paragraph(f"TOTAL: {_format_money(boleta['total'])}", estilos["total"]))

    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph("Esta boleta es personal e intransferible.", estilos["pie"]))
    story.append(Paragraph("¡Disfrute su visita!", estilos["pie"]))

    doc.build(story)
    return ruta


# ─────────────────────────────────────────────────────────────────────────────
#  ESC/POS — helpers internos
# ─────────────────────────────────────────────────────────────────────────────

def _modo_impresora():
    """Retorna 'pdf' (default) o 'escpos' según la configuración."""
    try:
        with conexion_segura() as conn:
            return _leer_config_impresora(conn)['modo']
    except Exception:
        return 'pdf'


def _nombre_impresora():
    """Retorna el nombre de la impresora Windows configurada para ESC/POS."""
    try:
        with conexion_segura() as conn:
            return _leer_config_impresora(conn)['nombre']
    except Exception:
        return ''


def _col_width_from_cfg(cfg):
    """Retorna el ancho en caracteres dado un dict de config ya leído."""
    return 32 if cfg['ancho_mm'] == 58 else 48


def _escpos_abrir_impresora(nombre):
    """Crea y retorna un objeto Win32Raw. Lanza excepciones descriptivas si falla."""
    if not ESCPOS_OK:
        raise ImportError(
            "python-escpos no esta instalado.\n"
            "Ejecute: pip install python-escpos pywin32"
        )
    if not nombre:
        raise ValueError(
            "No se ha configurado el nombre de la impresora ESC/POS.\n"
            "Vaya a Configuracion > Datos del Negocio > Impresora."
        )
    return Win32Raw(nombre)


def _escpos_cabecera(p, negocio, col):
    """Imprime el encabezado del negocio en la impresora ESC/POS."""
    p.set(align='center', bold=True, double_height=True, double_width=False)
    nombre = negocio.get('nombre_negocio', 'Club Los Pocitos Azufrados')
    p.text(nombre[:col] + '\n')
    p.set(align='center', bold=False, double_height=False)
    if negocio.get('ubicacion'):
        p.text(negocio['ubicacion'][:col] + '\n')
    if negocio.get('telefono'):
        p.text(f"Tel: {negocio['telefono']}\n")
    if negocio.get('nit'):
        p.text(f"NIT: {negocio['nit']}\n")
    p.text('-' * col + '\n')


def _imprimir_escpos_venta(venta_id):
    """Envía el recibo de venta directamente a la impresora ESC/POS."""
    # Leer todos los datos y config en una sola conexión
    with conexion_segura() as conn:
        cfg_imp  = _leer_config_impresora(conn)
        venta = conn.execute(
            "SELECT * FROM ventas WHERE id_venta = ?", (venta_id,)
        ).fetchone()
        if not venta:
            raise ValueError(f"Venta {venta_id} no encontrada")
        detalles = conn.execute(
            "SELECT * FROM venta_detalle WHERE id_venta = ? ORDER BY id_detalle",
            (venta_id,)
        ).fetchall()
        negocio = _datos_negocio(conn)
        fe = conn.execute(
            "SELECT * FROM facturas_electronicas WHERE id_venta = ?", (venta_id,)
        ).fetchone()

    nombre = cfg_imp['nombre']
    col    = _col_width_from_cfg(cfg_imp)
    p = _escpos_abrir_impresora(nombre)

    try:

        _escpos_cabecera(p, negocio, col)

        # Datos de la venta
        p.set(align='left')
        fecha_str = str(venta['fecha_creacion'])[:16] if venta['fecha_creacion'] else ''
        p.text(f"No: {venta['numero_venta']}\n")
        p.text(f"Fecha: {fecha_str}\n")
        if venta['cliente_nombre']:
            p.text(f"Cliente: {venta['cliente_nombre']}\n")
        p.text(f"Metodo: {venta['metodo_pago'] or '-'}\n")
        if fe:
            p.text(f"Factura: {fe['numero_factura']}\n")
            p.text(f"NIT cli.: {fe['cliente_nit']}\n")
        p.text('-' * col + '\n')

        # Productos — nombre (col-11 chars) | cant (3) | subtotal (8)
        n_ancho = col - 12
        p.set(bold=True)
        encabezado = f"{'Producto':<{n_ancho}}{'Cant':>3}{'Subtotal':>9}"
        p.text(encabezado[:col] + '\n')
        p.set(bold=False)
        p.text('-' * col + '\n')
        for det in detalles:
            nombre_prod = (det['producto_nombre'] or '-')[:n_ancho]
            cant = str(int(det['cantidad']))
            sub = _format_money(det['total_linea'])
            p.text(f"{nombre_prod:<{n_ancho}}{cant:>3}{sub:>9}\n")
        p.text('-' * col + '\n')

        # Totales
        if venta['descuento']:
            p.text(f"Subtotal:{_format_money(venta['subtotal']):>{col-8}}\n")
            p.text(f"Descuento:{('-' + _format_money(venta['descuento'])):>{col-9}}\n")
            p.text('-' * col + '\n')

        p.set(bold=True, double_height=True)
        total_txt = f"TOTAL: {_format_money(venta['total'])}"
        p.text(total_txt.center(col) + '\n')
        p.set(bold=False, double_height=False)

        # Pie
        p.text('\n')
        p.set(align='center')
        p.text('Gracias por su visita!\n')
        ubicacion = negocio.get('ubicacion', 'Tocaima, Cundinamarca')
        p.text(ubicacion[:col] + '\n')
        p.text('\n\n\n')
        p.cut()
        p.cashdraw(2)
    finally:
        p.close()


def _imprimir_escpos_boleta(boleta_id):
    """Envía la boleta de entrada directamente a la impresora ESC/POS."""
    with conexion_segura() as conn:
        cfg_imp = _leer_config_impresora(conn)
        boleta = conn.execute(
            "SELECT * FROM boletas_entrada WHERE id_boleta = ?", (boleta_id,)
        ).fetchone()
        if not boleta:
            raise ValueError(f"Boleta {boleta_id} no encontrada")
        negocio = _datos_negocio(conn)

    nombre = cfg_imp['nombre']
    col    = _col_width_from_cfg(cfg_imp)
    p = _escpos_abrir_impresora(nombre)

    try:
        _escpos_cabecera(p, negocio, col)

        p.set(align='center', bold=True)
        p.text('BOLETA DE ENTRADA\n')
        p.set(align='left', bold=False)
        p.text('-' * col + '\n')

        hora_str = str(boleta['hora_entrada'])[:16] if boleta['hora_entrada'] else '-'
        datos = [
            ('Boleta:',     boleta['numero_boleta']),
            ('Visitante:',  boleta['nombre_visitante']),
            ('Documento:',  boleta['documento_visitante'] or '-'),
            ('Personas:',   str(boleta['cantidad_personas'])),
            ('Fecha/Hora:', hora_str),
            ('Metodo:',     boleta['metodo_pago'] or '-'),
        ]
        lbl_ancho = 11
        for lbl, val in datos:
            linea = f"{lbl:<{lbl_ancho}}{val}"
            p.text(linea[:col] + '\n')

        p.text('-' * col + '\n')
        p.set(bold=True, double_height=True)
        total_txt = f"TOTAL: {_format_money(boleta['total'])}"
        p.text(total_txt.center(col) + '\n')
        p.set(bold=False, double_height=False)

        p.text('\n')
        p.set(align='center')
        p.text('Boleta personal e intransferible.\n')
        p.text('Disfrute su visita!\n')
        p.text('\n\n\n')
        p.cut()
        p.cashdraw(2)
    finally:
        p.close()


def imprimir_prueba_escpos(nombre_impresora):
    """Imprime una página de prueba en la impresora ESC/POS indicada.
    Retorna True si tuvo éxito, False si hubo error (muestra messagebox)."""
    try:
        p = _escpos_abrir_impresora(nombre_impresora)
        with conexion_segura() as conn:
            cfg = _leer_config_impresora(conn)
        col = _col_width_from_cfg(cfg)
        try:
            p.set(align='center', bold=True, double_height=True)
            p.text('PRUEBA DE IMPRESION\n')
            p.set(bold=False, double_height=False)
            p.text('-' * col + '\n')
            p.text('Club Los Pocitos Azufrados\n')
            p.text('Impresora ESC/POS OK\n')
            p.text('-' * col + '\n')
            p.text('\n\n\n')
            p.cut()
        finally:
            p.close()
        from tkinter import messagebox
        messagebox.showinfo("Prueba exitosa", f"La impresora '{nombre_impresora}' respondio correctamente.")
        return True
    except Exception as e:
        from tkinter import messagebox
        messagebox.showerror("Error de impresora", str(e))
        return False


# ─────────────────────────────────────────────────────────────────────────────
#  Funciones de conveniencia (genera + abre)
# ─────────────────────────────────────────────────────────────────────────────

def imprimir_recibo_venta(venta_id):
    """Imprime el recibo de venta. Usa ESC/POS o PDF según la configuración.
    En modo PDF devuelve la ruta del archivo; en modo ESC/POS devuelve True.
    Retorna None si hubo error."""
    try:
        # El modo se lee dentro de _imprimir_escpos_venta / generar_recibo_venta,
        # cada una en su propia conexión. Para decidir cuál llamar abrimos una sola vez.
        with conexion_segura() as conn:
            modo = _leer_config_impresora(conn)['modo']
        if modo == 'escpos':
            _imprimir_escpos_venta(venta_id)
            return True
        ruta = generar_recibo_venta(venta_id)
        _abrir_pdf(ruta)
        return ruta
    except ImportError as e:
        from tkinter import messagebox
        messagebox.showerror("Modulo faltante", str(e))
        return None
    except Exception as e:
        from tkinter import messagebox
        messagebox.showerror("Error al imprimir recibo", str(e))
        return None


def imprimir_recibo_boleta(boleta_id):
    """Imprime la boleta de entrada. Usa ESC/POS o PDF según la configuración."""
    try:
        with conexion_segura() as conn:
            modo = _leer_config_impresora(conn)['modo']
        if modo == 'escpos':
            _imprimir_escpos_boleta(boleta_id)
            return True
        ruta = generar_recibo_boleta(boleta_id)
        _abrir_pdf(ruta)
        return ruta
    except ImportError as e:
        from tkinter import messagebox
        messagebox.showerror("Modulo faltante", str(e))
        return None
    except Exception as e:
        from tkinter import messagebox
        messagebox.showerror("Error al imprimir boleta", str(e))
        return None
