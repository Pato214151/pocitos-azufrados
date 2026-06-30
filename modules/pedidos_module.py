"""
Módulo de Pedidos - Club Los Pocitos Azufrados
Gestión de pedidos de almuerzos/comidas desde la barra
Reemplaza al antiguo módulo "Reservas Almuerzo"
Se actualiza automáticamente cada 15 segundos
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import os, sys, datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from utils.tema_corporativo import COLORES, FUENTES, crear_boton, format_money
from database.connection import get_connection, conexion_segura
from utils.logger import log_auditoria


class PedidosModule:
    REFRESH_MS = 15000  # 15 segundos
    ESTADOS = ['RESERVADO', 'EN_PREPARACION', 'LISTO', 'ENTREGADO', 'CANCELADO']

    def __init__(self, parent, usuario):
        self.parent = parent
        self.usuario = usuario
        self.auto_refresh = True
        self._after_id = None
        self.pedidos_cache = {}
        self.categorias_almuerzo = []
        self.filtro_periodo = 'semana'   # 'dia' | 'semana' | 'mes'
        self._btns_filtro = {}
        self._crear_interfaz()
        self._cargar_categorias_almuerzo()
        self._cargar_pedidos()
        self._iniciar_auto_refresh()

    def _crear_interfaz(self):
        """Interfaz principal: pedidos (izquierda) + formulario (derecha)"""
        # Header
        header = tk.Frame(self.parent, bg=COLORES['primario'])
        header.pack(fill='x')

        inner_header = tk.Frame(header, bg=COLORES['primario'], padx=15, pady=10)
        inner_header.pack(fill='x')

        tk.Label(inner_header, text="PEDIDOS DE ALMUERZO",
                 font=FUENTES['encabezado'], fg=COLORES['texto_claro'],
                 bg=COLORES['primario']).pack(side='left')

        self.lbl_hora = tk.Label(inner_header, text="",
                                  font=FUENTES['normal_bold'],
                                  fg=COLORES['acento'], bg=COLORES['primario'])
        self.lbl_hora.pack(side='right')

        # Contadores
        contadores = tk.Frame(self.parent, bg=COLORES['fondo'], padx=15, pady=8)
        contadores.pack(fill='x')

        self.lbl_pendientes = tk.Label(contadores, text="Pendientes: 0",
                                        font=FUENTES['normal_bold'],
                                        fg=COLORES['advertencia'], bg=COLORES['fondo'])
        self.lbl_pendientes.pack(side='left', padx=10)

        self.lbl_preparando = tk.Label(contadores, text="Preparando: 0",
                                        font=FUENTES['normal_bold'],
                                        fg=COLORES['info'], bg=COLORES['fondo'])
        self.lbl_preparando.pack(side='left', padx=10)

        self.lbl_listos = tk.Label(contadores, text="Listos: 0",
                                    font=FUENTES['normal_bold'],
                                    fg=COLORES['exito'], bg=COLORES['fondo'])
        self.lbl_listos.pack(side='left', padx=10)

        crear_boton(contadores, "Refrescar", self._cargar_pedidos,
                    tipo='secundario').pack(side='right')

        # Filtros de período
        rol = self.usuario.get('rol', '')
        es_vendedor = (rol == 'vendedor')
        periodos = [('Semana', 'semana')] if es_vendedor else [
            ('Hoy', 'dia'), ('Semana', 'semana'), ('Mes', 'mes')
        ]
        for label, periodo in reversed(periodos):
            btn = tk.Button(
                contadores, text=label,
                font=FUENTES['pequena'],
                relief='solid', bd=1, padx=8, pady=2,
                cursor='hand2',
                command=lambda p=periodo: self._cambiar_filtro(p)
            )
            btn.pack(side='right', padx=2)
            self._btns_filtro[periodo] = btn
        self._actualizar_botones_filtro()

        # Cuerpo: pedidos a pantalla completa
        body = tk.Frame(self.parent, bg=COLORES['fondo'])
        body.pack(fill='both', expand=True, padx=15, pady=5)

        # ============================================================
        # Pedidos agrupados por estado (kanban-style)
        # ============================================================
        left_frame = tk.Frame(body, bg=COLORES['fondo'])
        left_frame.pack(fill='both', expand=True)

        tk.Label(left_frame, text="Pedidos en Cola", font=FUENTES['encabezado'],
                 fg=COLORES['texto'], bg=COLORES['fondo']).pack(anchor='w', pady=(0, 8))

        # Canvas scrollable para pedidos
        canvas = tk.Canvas(left_frame, bg=COLORES['fondo'], highlightthickness=0)
        scrollbar = ttk.Scrollbar(left_frame, orient="vertical", command=canvas.yview)
        self.pedidos_frame = tk.Frame(canvas, bg=COLORES['fondo'])

        self.pedidos_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        self._pedidos_win = canvas.create_window((0, 0), window=self.pedidos_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.bind('<Configure>',
                    lambda e: canvas.itemconfig(self._pedidos_win, width=e.width))

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        def _scroll(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _scroll)

        self.canvas_pedidos = canvas

    def _cambiar_filtro(self, periodo):
        self.filtro_periodo = periodo
        self._actualizar_botones_filtro()
        self._cargar_pedidos()

    def _actualizar_botones_filtro(self):
        for periodo, btn in self._btns_filtro.items():
            if periodo == self.filtro_periodo:
                btn.config(bg=COLORES['primario'], fg=COLORES['texto_claro'],
                           relief='flat')
            else:
                btn.config(bg=COLORES['fondo_card'], fg=COLORES['texto'],
                           relief='solid')

    def _actualizar_hora_default(self):
        """No-op: formulario de nuevo pedido removido (se crea desde Bar)"""
        pass

    def _cargar_categorias_almuerzo(self):
        """No-op: formulario de nuevo pedido removido (se crea desde Bar)"""
        pass

    def _cargar_pedidos(self):
        """Carga y muestra los pedidos agrupados por estado"""
        for w in self.pedidos_frame.winfo_children():
            w.destroy()

        # Actualizar hora
        self.lbl_hora.config(text=datetime.datetime.now().strftime("%H:%M:%S"))

        # Calcular rango de fechas según el filtro activo
        hoy = datetime.date.today()
        if self.filtro_periodo == 'dia':
            fecha_desde = hoy.isoformat()
            fecha_hasta = hoy.isoformat()
        elif self.filtro_periodo == 'mes':
            fecha_desde = hoy.replace(day=1).isoformat()
            fecha_hasta = hoy.isoformat()
        else:  # semana (lunes al domingo de la semana actual)
            lunes = hoy - datetime.timedelta(days=hoy.weekday())
            domingo = lunes + datetime.timedelta(days=6)
            fecha_desde = lunes.isoformat()
            fecha_hasta = domingo.isoformat()

        try:
            with conexion_segura() as conn:
                # ── Ordenes de cocina del día (pedidos de bar) ──────────────
                ordenes = conn.execute("""
                    SELECT oc.id_orden, oc.numero_venta, oc.producto_nombre,
                           oc.cantidad, oc.cliente_nombre, oc.estado,
                           oc.hora_pedido
                    FROM ordenes_cocina oc
                    WHERE oc.estado IN ('PENDIENTE','PREPARANDO','LISTO')
                      AND DATE(oc.hora_pedido) = DATE('now','localtime')
                    ORDER BY
                        CASE oc.estado
                            WHEN 'PENDIENTE'  THEN 1
                            WHEN 'PREPARANDO' THEN 2
                            WHEN 'LISTO'      THEN 3
                        END,
                        oc.hora_pedido ASC
                """).fetchall()
                ordenes = [dict(o) for o in ordenes]

                # ── Almuerzos reservados ─────────────────────────────────────
                pedidos = conn.execute("""
                    SELECT *
                    FROM reservas_almuerzo
                    WHERE estado IN ('RESERVADO', 'EN_PREPARACION', 'LISTO', 'ENTREGADO')
                      AND DATE(hora_reserva) >= ?
                      AND DATE(hora_reserva) <= ?
                    ORDER BY
                        CASE estado
                            WHEN 'RESERVADO' THEN 1
                            WHEN 'EN_PREPARACION' THEN 2
                            WHEN 'LISTO' THEN 3
                            WHEN 'ENTREGADO' THEN 4
                        END,
                        hora_reserva ASC
                """, (fecha_desde, fecha_hasta)).fetchall()

                self.pedidos_cache = {p['id_reserva']: dict(p) for p in pedidos}

                # Contadores (combinados)
                pendientes = sum(1 for p in pedidos if p['estado'] == 'RESERVADO')
                preparando = (sum(1 for p in pedidos if p['estado'] == 'EN_PREPARACION') +
                              sum(1 for o in ordenes if o['estado'] == 'PREPARANDO'))
                listos = (sum(1 for p in pedidos if p['estado'] == 'LISTO') +
                          sum(1 for o in ordenes if o['estado'] == 'LISTO'))

                self.lbl_pendientes.config(text=f"Pendientes: {pendientes}")
                self.lbl_preparando.config(text=f"Preparando: {preparando}")
                self.lbl_listos.config(text=f"Listos: {listos}")

                # Mostrar sección de ordenes de cocina si hay alguna
                if ordenes:
                    self._crear_seccion_cocina(self.pedidos_frame, ordenes)

                if not pedidos and not ordenes:
                    tk.Label(self.pedidos_frame,
                             text="No hay pedidos\n\n\u00a1Todo al dia!",
                             font=FUENTES['subtitulo'], fg=COLORES['exito'],
                             bg=COLORES['fondo']).pack(pady=80)
                    return

                # Agrupar almuerzos por estado
                por_estado = {}
                for estado in ['RESERVADO', 'EN_PREPARACION', 'LISTO', 'ENTREGADO']:
                    por_estado[estado] = [dict(p) for p in pedidos if p['estado'] == estado]

                for estado in ['RESERVADO', 'EN_PREPARACION', 'LISTO', 'ENTREGADO']:
                    pedidos_estado = por_estado[estado]
                    if pedidos_estado:
                        self._crear_seccion_estado(self.pedidos_frame, estado, pedidos_estado)

        except Exception as e:
            tk.Label(self.pedidos_frame, text=f"Error: {e}",
                     font=FUENTES['normal'], fg=COLORES['error'],
                     bg=COLORES['fondo']).pack(pady=30)

    def _crear_seccion_estado(self, parent, estado, pedidos):
        """Crea una sección para un estado con sus tarjetas"""
        # Colores por estado
        colores_estado = {
            'RESERVADO': {
                'bg': '#FFF3E0',
                'border': COLORES['advertencia'],
                'header_bg': '#FFB74D',
                'header_text': 'RESERVADO'
            },
            'EN_PREPARACION': {
                'bg': '#E3F2FD',
                'border': COLORES['info'],
                'header_bg': '#64B5F6',
                'header_text': 'EN PREPARACION'
            },
            'LISTO': {
                'bg': '#E8F5E9',
                'border': COLORES['exito'],
                'header_bg': '#81C784',
                'header_text': 'LISTO'
            },
            'ENTREGADO': {
                'bg': '#F5F5F5',
                'border': '#9E9E9E',
                'header_bg': '#BDBDBD',
                'header_text': 'ENTREGADO'
            }
        }

        estilo = colores_estado.get(estado, colores_estado['RESERVADO'])

        # Encabezado de sección
        section = tk.Frame(parent, bg=COLORES['fondo'])
        section.pack(fill='x', pady=(8, 0))

        header = tk.Frame(section, bg=estilo['header_bg'])
        header.pack(fill='x', padx=4)

        tk.Label(header, text=f"{estilo['header_text']} ({len(pedidos)})",
                 font=FUENTES['encabezado'], fg='white',
                 bg=estilo['header_bg']).pack(padx=10, pady=6)

        # Contenedor para tarjetas
        cards_frame = tk.Frame(section, bg=COLORES['fondo'])
        cards_frame.pack(fill='x', padx=4, pady=(4, 8))

        for pedido in pedidos:
            self._crear_tarjeta_pedido(cards_frame, pedido, estilo)

    def _crear_tarjeta_pedido(self, parent, pedido, estilo):
        """Crea una tarjeta visual para un pedido"""
        card = tk.Frame(parent, bg=estilo['bg'],
                        highlightbackground=estilo['border'],
                        highlightthickness=2, relief='flat')
        card.pack(fill='x', pady=4)

        # Contenido de la tarjeta
        content = tk.Frame(card, bg=estilo['bg'])
        content.pack(fill='both', expand=True, padx=10, pady=10)

        # Nombre cliente
        tk.Label(content, text=pedido['cliente_nombre'],
                 font=FUENTES['encabezado'], fg=COLORES['texto'],
                 bg=estilo['bg']).pack(anchor='w')

        # Tipo almuerzo y cantidad
        info_text = f"{pedido['tipo_almuerzo']} × {pedido['cantidad_almuerzos']}"
        tk.Label(content, text=info_text, font=FUENTES['normal'],
                 fg=COLORES['texto_secundario'], bg=estilo['bg']).pack(anchor='w', pady=(2, 0))

        # Tiempo estimado
        hora_est = pedido['hora_entrega_estimada']
        tk.Label(content, text=f"Hora: {hora_est}",
                 font=FUENTES['pequena'], fg=COLORES['texto_secundario'],
                 bg=estilo['bg']).pack(anchor='w', pady=(4, 0))

        # Tiempo transcurrido
        try:
            hora_res = datetime.datetime.fromisoformat(pedido['hora_reserva'])
            ahora = datetime.datetime.now()
            diff = ahora - hora_res
            minutos = int(diff.total_seconds() / 60)
            tiempo_text = f"Hace {minutos} min"
            tk.Label(content, text=tiempo_text, font=FUENTES['pequena'],
                     fg=COLORES['advertencia'], bg=estilo['bg']).pack(anchor='w')
        except Exception:
            pass

        # Notas si existen
        if pedido.get('notas'):
            tk.Label(content, text=pedido['notas'], font=FUENTES['pequena'],
                     fg=COLORES['texto_secundario'], bg=estilo['bg'],
                     wraplength=250, justify='left').pack(anchor='w', pady=(4, 0))

        # Botones de acción
        btn_frame = tk.Frame(card, bg=estilo['bg'])
        btn_frame.pack(fill='x', padx=10, pady=(0, 8))

        # Botón avanzar estado
        if pedido['estado'] != 'ENTREGADO':
            siguiente_estado = {
                'RESERVADO': 'EN_PREPARACION',
                'EN_PREPARACION': 'LISTO',
                'LISTO': 'ENTREGADO'
            }.get(pedido['estado'])

            if siguiente_estado:
                crear_boton(btn_frame, f"> {siguiente_estado}",
                           lambda id_p=pedido['id_reserva'], est=siguiente_estado:
                           self._cambiar_estado(id_p, est),
                           tipo='primario').pack(side='left', padx=2)

        # Botón cancelar
        crear_boton(btn_frame, "Cancelar",
                   lambda id_p=pedido['id_reserva']:
                   self._cancelar_pedido(id_p),
                   tipo='error').pack(side='right', padx=2)

    def _crear_seccion_cocina(self, parent, ordenes):
        """Sección de ordenes de bar en cocina (solo lectura para el bar)"""
        section = tk.Frame(parent, bg=COLORES['fondo'])
        section.pack(fill='x', pady=(4, 8))

        header = tk.Frame(section, bg=COLORES['fondo_sidebar'])
        header.pack(fill='x', padx=4)
        tk.Label(header, text=f"\u2615  PEDIDOS BAR  ({len(ordenes)})",
                 font=FUENTES['encabezado'], fg=COLORES['acento'],
                 bg=COLORES['fondo_sidebar']).pack(side='left', padx=10, pady=6)
        tk.Label(header, text="(cocina actualiza el estado)",
                 font=FUENTES['pequena'], fg=COLORES['texto_secundario'],
                 bg=COLORES['fondo_sidebar']).pack(side='right', padx=10)

        cards_frame = tk.Frame(section, bg=COLORES['fondo'])
        cards_frame.pack(fill='x', padx=4, pady=(4, 0))

        colores_orden = {
            'PENDIENTE':  ('#FFF3E0', '#FFB74D', COLORES['advertencia']),
            'PREPARANDO': ('#E3F2FD', '#64B5F6', COLORES['info']),
            'LISTO':      ('#E8F5E9', '#81C784', COLORES['exito']),
        }

        for orden in ordenes:
            bg, badge_bg, badge_fg = colores_orden.get(
                orden['estado'], ('#F5F5F5', '#BDBDBD', '#555'))

            card = tk.Frame(cards_frame, bg=bg,
                            highlightbackground=badge_bg,
                            highlightthickness=2, relief='flat')
            card.pack(fill='x', pady=3)

            top = tk.Frame(card, bg=bg)
            top.pack(fill='x', padx=10, pady=(8, 2))

            # Badge de estado
            tk.Label(top, text=f" {orden['estado']} ",
                     font=FUENTES['pequena_bold'] if 'pequena_bold' in FUENTES else FUENTES['normal_bold'],
                     fg='white', bg=badge_bg,
                     relief='flat').pack(side='right')

            # Nombre del producto y cantidad
            tk.Label(top, text=f"{orden['producto_nombre']}  ×{orden['cantidad']}",
                     font=FUENTES['normal_bold'], fg=COLORES['texto'],
                     bg=bg).pack(side='left')

            bot = tk.Frame(card, bg=bg)
            bot.pack(fill='x', padx=10, pady=(0, 8))

            cliente = orden.get('cliente_nombre') or '—'
            tk.Label(bot, text=f"Cliente: {cliente}",
                     font=FUENTES['normal'], fg=COLORES['texto_secundario'],
                     bg=bg).pack(side='left')

            try:
                hora_p = datetime.datetime.fromisoformat(orden['hora_pedido'])
                minutos = int((datetime.datetime.now() - hora_p).total_seconds() / 60)
                tk.Label(bot, text=f"Hace {minutos} min",
                         font=FUENTES['pequena'], fg=COLORES['advertencia'],
                         bg=bg).pack(side='right')
            except Exception:
                pass

    def _cambiar_estado(self, id_reserva, nuevo_estado):
        """Avanza el estado de un pedido"""
        try:
            with conexion_segura() as conn:
                conn.execute("""
                    UPDATE reservas_almuerzo
                    SET estado = ?
                    WHERE id_reserva = ?
                """, (nuevo_estado, id_reserva))

                # Log de auditoría
                log_auditoria(conn, 'reservas_almuerzo', id_reserva, 'UPDATE',
                             self.usuario.get('usuario', self.usuario.get('nombre_completo', '')),
                             f"Estado cambiado a {nuevo_estado}")

            self._cargar_pedidos()
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo cambiar el estado: {e}")

    def _cancelar_pedido(self, id_reserva):
        """Cancela un pedido con confirmación"""
        pedido = self.pedidos_cache.get(id_reserva, {})
        cliente = pedido.get('cliente_nombre', 'N/A')

        if messagebox.askyesno("Cancelar Pedido",
                               f"¿Cancelar pedido de {cliente}?"):
            try:
                with conexion_segura() as conn:
                    conn.execute("""
                        UPDATE reservas_almuerzo
                        SET estado = 'CANCELADO'
                        WHERE id_reserva = ?
                    """, (id_reserva,))

                    log_auditoria(conn, 'reservas_almuerzo', id_reserva, 'UPDATE',
                                 self.usuario.get('usuario', self.usuario.get('nombre_completo', '')),
                                 f"Pedido CANCELADO")

                self._cargar_pedidos()
                messagebox.showinfo("Éxito", "Pedido cancelado")
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo cancelar: {e}")

    def _crear_pedido(self):
        """No-op: los pedidos se crean desde Bar"""
        pass

    def _limpiar_formulario(self):
        """No-op: formulario removido"""
        pass

    def _iniciar_auto_refresh(self):
        """Inicia el auto-refresh cada 15 segundos"""
        if self.auto_refresh:
            try:
                if self.parent.winfo_exists():
                    self._cargar_pedidos()
                    self._after_id = self.parent.after(self.REFRESH_MS, self._iniciar_auto_refresh)
            except Exception:
                pass

    def detener(self):
        """Detiene el auto-refresh. Llamar antes de destruir el módulo."""
        self.auto_refresh = False
        if self._after_id is not None:
            try:
                self.parent.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None
        try:
            self.canvas_pedidos.unbind_all('<MouseWheel>')
            self.canvas_pedidos.unbind_all('<Button-4>')
            self.canvas_pedidos.unbind_all('<Button-5>')
        except Exception:
            pass

    def destruir(self):
        """Alias de compatibilidad."""
        self.detener()
