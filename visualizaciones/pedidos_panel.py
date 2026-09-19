import threading
import customtkinter as ctk
from collections import deque
from sesion import Sesion
from base_de_datos.queries import (
    listar_productos, crear_pedido, listar_pedidos,
    buscar_cliente_por_telefono, crear_o_actualizar_cliente,
)
from visualizaciones._widgets import mostrar_detalle_pedido

# ── PALETA (verde, línea de productos de limpieza) ─────────────────────────────
C_BG      = "#0a120e"
C_SURFACE = "#0f1c15"
C_CARD    = "#16291f"
C_BORDER  = "#20382a"
C_ACCENT  = "#10b981"
C_GREEN   = "#10b981"
C_RED     = "#ef4444"
C_ORANGE  = "#f59e0b"
C_TEXT    = "#eafff3"
C_MUTED   = "#6b9080"
C_ROW_ALT = "#122019"

FONT_TITLE = ("Trebuchet MS", 20, "bold")
FONT_HEAD  = ("Trebuchet MS", 14, "bold")
FONT_BODY  = ("Trebuchet MS", 12)
FONT_SMALL = ("Trebuchet MS", 11)


class VentanaVendedor(ctk.CTk):

    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        self.sesion = Sesion.obtener()
        self.title(f"MAX LIMP  —  {self.sesion.nombre}")
        self.geometry("1180x720")
        self.minsize(950, 620)
        self.configure(fg_color=C_BG)
        self.carrito: dict = {}
        self.cliente_actual: dict = None
        self._construir_interfaz()
        self._cargar_catalogo()

    # ── INTERFAZ ──────────────────────────────────────────────────────────────

    def _construir_interfaz(self):
        header = ctk.CTkFrame(self, fg_color=C_SURFACE, corner_radius=0, height=62)
        header.pack(fill="x")
        header.pack_propagate(False)

        logo_frame = ctk.CTkFrame(header, fg_color=C_ACCENT, corner_radius=8, width=36, height=36)
        logo_frame.pack(side="left", padx=(18, 10), pady=13)
        logo_frame.pack_propagate(False)
        ctk.CTkLabel(logo_frame, text="M", font=("Trebuchet MS", 18, "bold"), text_color="white").place(relx=.5, rely=.5, anchor="center")

        ctk.CTkLabel(header, text="MAX LIMP", font=FONT_TITLE, text_color=C_TEXT).pack(side="left")
        ctk.CTkLabel(header, text=" / Registrar pedido", font=FONT_BODY, text_color=C_MUTED).pack(side="left", pady=4)
        ctk.CTkLabel(header, text=f"👤 {self.sesion.nombre}", font=FONT_SMALL,
                     text_color=C_MUTED).pack(side="left", padx=14)

        ctk.CTkButton(header, text="⏻  Salir", width=90, height=34,
                      fg_color=C_RED, hover_color="#b91c1c", font=FONT_SMALL,
                      corner_radius=8, command=self._cerrar_sesion).pack(side="right", padx=18, pady=14)
        ctk.CTkButton(header, text="📋  Historial de pedidos", width=170, height=34,
                      fg_color=C_SURFACE, hover_color=C_CARD, font=FONT_SMALL,
                      border_width=1, border_color=C_BORDER,
                      corner_radius=8, command=self._ver_historial).pack(side="right", padx=4, pady=14)

        # Cuerpo
        cuerpo = ctk.CTkFrame(self, fg_color="transparent")
        cuerpo.pack(fill="both", expand=True, padx=16, pady=12)
        cuerpo.grid_columnconfigure(0, weight=3)
        cuerpo.grid_columnconfigure(1, weight=1)
        cuerpo.grid_rowconfigure(0, weight=1)

        # Panel catálogo
        panel_cat = ctk.CTkFrame(cuerpo, fg_color=C_CARD, corner_radius=14,
                                 border_width=1, border_color=C_BORDER)
        panel_cat.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        ctk.CTkLabel(panel_cat, text="🧴  Catálogo de Productos",
                     font=FONT_HEAD, text_color=C_TEXT).pack(pady=(14, 8), padx=16, anchor="w")

        barra = ctk.CTkFrame(panel_cat, fg_color="transparent")
        barra.pack(fill="x", padx=14, pady=(0, 10))
        self.entry_buscar = ctk.CTkEntry(barra, placeholder_text="🔍  Buscar producto o categoría...",
                                         height=34, corner_radius=8,
                                         fg_color=C_SURFACE, border_color=C_BORDER, font=FONT_SMALL)
        self.entry_buscar.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.entry_buscar.bind("<Return>", lambda e: self._buscar())
        ctk.CTkButton(barra, text="Buscar", width=90, height=34, corner_radius=8,
                      fg_color=C_ACCENT, hover_color="#0d9668", font=FONT_SMALL,
                      command=self._buscar).pack(side="left", padx=(0, 4))
        ctk.CTkButton(barra, text="Ver todo", width=90, height=34, corner_radius=8,
                      fg_color=C_SURFACE, hover_color=C_BORDER, font=FONT_SMALL,
                      command=self._cargar_catalogo).pack(side="left")

        self.lbl_cargando = ctk.CTkLabel(panel_cat, text="", text_color=C_MUTED, font=FONT_SMALL)
        self.lbl_cargando.pack(anchor="w", padx=14)

        self.frame_catalogo = ctk.CTkScrollableFrame(panel_cat, fg_color="transparent")
        self.frame_catalogo.pack(fill="both", expand=True, padx=8, pady=(0, 10))

        self.cols_cat = {"ID": 40, "Nombre": 220, "Categoría": 120, "Precio": 80, "Stock": 60, "": 95}
        for col_i, (enc, ancho) in enumerate(self.cols_cat.items()):
            ctk.CTkLabel(self.frame_catalogo, text=enc, font=FONT_SMALL,
                         width=ancho, anchor="w", text_color=C_MUTED).grid(
                row=0, column=col_i, padx=5, pady=7)

        # Panel pedido (cliente + carrito)
        panel_pedido = ctk.CTkFrame(cuerpo, fg_color=C_CARD, corner_radius=14,
                                    border_width=1, border_color=C_BORDER)
        panel_pedido.grid(row=0, column=1, sticky="nsew")

        ctk.CTkLabel(panel_pedido, text="👤  Cliente",
                     font=FONT_HEAD, text_color=C_TEXT).pack(pady=(14, 6), padx=14, anchor="w")

        cli_frame = ctk.CTkFrame(panel_pedido, fg_color="transparent")
        cli_frame.pack(fill="x", padx=14)
        self.entry_tel = ctk.CTkEntry(cli_frame, placeholder_text="Teléfono (WhatsApp)...",
                                       height=32, corner_radius=8,
                                       fg_color=C_SURFACE, border_color=C_BORDER, font=FONT_SMALL)
        self.entry_tel.pack(side="left", fill="x", expand=True, padx=(0, 6))
        ctk.CTkButton(cli_frame, text="Buscar", width=70, height=32, corner_radius=8,
                      fg_color=C_ACCENT, hover_color="#0d9668", font=FONT_SMALL,
                      command=self._buscar_cliente).pack(side="left")

        self.lbl_cliente = ctk.CTkLabel(panel_pedido, text="Sin cliente seleccionado.",
                                        font=FONT_SMALL, text_color=C_MUTED, wraplength=260, justify="left")
        self.lbl_cliente.pack(anchor="w", padx=14, pady=(6, 10))

        divider0 = ctk.CTkFrame(panel_pedido, fg_color=C_BORDER, height=1)
        divider0.pack(fill="x", padx=14, pady=(0, 8))

        ctk.CTkLabel(panel_pedido, text="🛒  Pedido",
                     font=FONT_HEAD, text_color=C_TEXT).pack(padx=14, anchor="w")

        self.lbl_cart_count = ctk.CTkLabel(panel_pedido, text="0 productos",
                                           font=FONT_SMALL, text_color=C_MUTED)
        self.lbl_cart_count.pack(anchor="w", padx=14)

        self.frame_carrito = ctk.CTkScrollableFrame(panel_pedido, height=260, fg_color="transparent")
        self.frame_carrito.pack(fill="x", padx=10, pady=6)

        divider = ctk.CTkFrame(panel_pedido, fg_color=C_BORDER, height=1)
        divider.pack(fill="x", padx=14, pady=4)

        total_frame = ctk.CTkFrame(panel_pedido, fg_color="transparent")
        total_frame.pack(fill="x", padx=14, pady=4)
        ctk.CTkLabel(total_frame, text="Total:", font=FONT_BODY, text_color=C_MUTED).pack(side="left")
        self.lbl_total = ctk.CTkLabel(total_frame, text="$0.00",
                                      font=("Trebuchet MS", 18, "bold"), text_color=C_GREEN)
        self.lbl_total.pack(side="right")

        ctk.CTkButton(panel_pedido, text="✅  Registrar Pedido", height=42,
                      fg_color=C_GREEN, hover_color="#0d9668",
                      font=("Trebuchet MS", 13, "bold"), corner_radius=10,
                      command=self._confirmar_pedido).pack(fill="x", padx=14, pady=(6, 4))
        ctk.CTkButton(panel_pedido, text="Vaciar pedido", height=30,
                      fg_color="transparent", hover_color=C_BORDER, text_color=C_MUTED,
                      font=FONT_SMALL, corner_radius=8,
                      command=self._vaciar_carrito).pack(fill="x", padx=14, pady=(0, 8))

        self.lbl_msg = ctk.CTkLabel(panel_pedido, text="", font=FONT_SMALL, text_color=C_MUTED, wraplength=260)
        self.lbl_msg.pack(padx=14, pady=(0, 6))

        self.ultimo_pedido_id = None
        self.btn_ticket = ctk.CTkButton(panel_pedido, text="🧾 Ver / Imprimir Ticket", height=32,
                                        fg_color=C_ACCENT, hover_color="#0d9668",
                                        font=FONT_SMALL, corner_radius=8,
                                        command=self._abrir_ticket_reciente)
        # Se muestra únicamente cuando se completa un pedido

    # ── CLIENTE ───────────────────────────────────────────────────────────────

    def _buscar_cliente(self):
        telefono = self.entry_tel.get().strip()
        if not telefono:
            self.lbl_cliente.configure(text="Ingresa un teléfono.", text_color=C_RED)
            return
        cliente = buscar_cliente_por_telefono(telefono)
        if cliente:
            self.cliente_actual = cliente
            self.lbl_cliente.configure(
                text=f"✅ {cliente['nombre'] or '(sin nombre)'}  ·  {cliente['telefono']}",
                text_color=C_GREEN)
        else:
            self._crear_cliente_rapido(telefono)

    def _crear_cliente_rapido(self, telefono):
        v = ctk.CTkToplevel(self)
        v.title("Nuevo Cliente")
        v.geometry("360x260")
        v.configure(fg_color=C_SURFACE)
        v.grab_set()
        ctk.CTkLabel(v, text="Cliente no encontrado — regístralo:",
                     font=FONT_HEAD, text_color=C_TEXT).pack(pady=(20, 10))
        ctk.CTkLabel(v, text="Nombre:", font=FONT_SMALL, text_color=C_MUTED).pack(anchor="w", padx=30)
        e_nom = ctk.CTkEntry(v, width=290, height=34, corner_radius=8,
                             fg_color=C_CARD, border_color=C_BORDER, font=FONT_BODY)
        e_nom.pack(pady=(0, 8))
        ctk.CTkLabel(v, text="Dirección (opcional):", font=FONT_SMALL, text_color=C_MUTED).pack(anchor="w", padx=30)
        e_dir = ctk.CTkEntry(v, width=290, height=34, corner_radius=8,
                             fg_color=C_CARD, border_color=C_BORDER, font=FONT_BODY)
        e_dir.pack(pady=(0, 8))
        lbl = ctk.CTkLabel(v, text="", text_color=C_RED, font=FONT_SMALL)
        lbl.pack()

        def guardar():
            try:
                cliente = crear_o_actualizar_cliente(e_nom.get(), telefono, e_dir.get().strip() or None)
                self.cliente_actual = cliente
                self.lbl_cliente.configure(
                    text=f"✅ {cliente['nombre'] or '(sin nombre)'}  ·  {cliente['telefono']}",
                    text_color=C_GREEN)
                v.destroy()
            except Exception as e:
                lbl.configure(text=f"Error: {e}")

        ctk.CTkButton(v, text="Guardar cliente", width=290, height=36, corner_radius=8,
                      fg_color=C_GREEN, hover_color="#0d9668", font=FONT_BODY,
                      command=guardar).pack(pady=10)

    # ── CATÁLOGO ──────────────────────────────────────────────────────────────

    def _cargar_catalogo(self):
        self.lbl_cargando.configure(text="⏳ Cargando...")
        threading.Thread(target=self._cargar_catalogo_bg, args=(None,), daemon=True).start()

    def _buscar(self):
        filtro = self.entry_buscar.get().strip() or None
        self.lbl_cargando.configure(text="⏳ Buscando...")
        threading.Thread(target=self._cargar_catalogo_bg, args=(filtro,), daemon=True).start()

    def _cargar_catalogo_bg(self, filtro):
        productos = listar_productos(filtro=filtro, solo_activos=True)
        self.after(0, lambda: self._renderizar_catalogo(productos))

    def _renderizar_catalogo(self, productos):
        self.lbl_cargando.configure(text="")
        # CTkScrollableFrame almacena los widgets reales en ._scrollable_frame
        inner_cat = getattr(self.frame_catalogo, "_scrollable_frame", self.frame_catalogo)
        for w in list(inner_cat.winfo_children())[len(self.cols_cat):]:
            w.destroy()

        if not productos:
            ctk.CTkLabel(self.frame_catalogo, text="Sin productos.",
                         text_color=C_MUTED).grid(row=1, column=0, columnspan=6, pady=20)
            return

        for fila, p in enumerate(productos, start=1):
            color = C_ROW_ALT if fila % 2 == 0 else "transparent"
            ctk.CTkLabel(self.frame_catalogo, text=str(p["id"]), width=self.cols_cat["ID"],
                         anchor="w", fg_color=color, font=FONT_SMALL).grid(row=fila, column=0, padx=5, pady=4)
            ctk.CTkLabel(self.frame_catalogo, text=p["nombre"], width=self.cols_cat["Nombre"],
                         anchor="w", fg_color=color, font=FONT_SMALL, text_color=C_TEXT,
                         wraplength=210).grid(row=fila, column=1, padx=5, pady=4)
            ctk.CTkLabel(self.frame_catalogo, text=p["categoria"], width=self.cols_cat["Categoría"],
                         anchor="w", fg_color=color, font=FONT_SMALL).grid(row=fila, column=2, padx=5, pady=4)
            ctk.CTkLabel(self.frame_catalogo, text=f"${p['precio']:.2f}", width=self.cols_cat["Precio"],
                         anchor="w", fg_color=color, font=FONT_SMALL).grid(row=fila, column=3, padx=5, pady=4)
            color_stock = C_RED if p["stock"] < 5 else C_TEXT
            ctk.CTkLabel(self.frame_catalogo, text=str(p["stock"]), width=self.cols_cat["Stock"],
                         anchor="w", fg_color=color, font=FONT_SMALL, text_color=color_stock).grid(row=fila, column=4, padx=5, pady=4)
            ctk.CTkButton(self.frame_catalogo, text="+ Agregar", width=self.cols_cat[""], height=26,
                          corner_radius=6, fg_color=C_ACCENT, hover_color="#0d9668", font=FONT_SMALL,
                          state="normal" if p["stock"] > 0 else "disabled",
                          command=lambda prod=p: self._agregar_carrito(prod)
                          ).grid(row=fila, column=5, padx=5, pady=4)

    # ── CARRITO ───────────────────────────────────────────────────────────────

    def _agregar_carrito(self, producto):
        pid = producto["id"]
        if pid in self.carrito:
            self.carrito[pid]["cantidad"] += 1
        else:
            self.carrito[pid] = {"nombre": producto["nombre"], "precio": producto["precio"], "cantidad": 1}
        self._refrescar_carrito()

    def _refrescar_carrito(self):
        inner_cart = getattr(self.frame_carrito, "_scrollable_frame", self.frame_carrito)
        for w in inner_cart.winfo_children():
            w.destroy()

        total = 0.0
        for fila, (pid, item) in enumerate(self.carrito.items()):
            subtotal = item["precio"] * item["cantidad"]
            total += subtotal
            fila_f = ctk.CTkFrame(self.frame_carrito, fg_color=C_ROW_ALT if fila % 2 == 0 else "transparent",
                                  corner_radius=6)
            fila_f.pack(fill="x", pady=2)
            ctk.CTkLabel(fila_f, text=item["nombre"], font=FONT_SMALL, text_color=C_TEXT,
                         width=110, anchor="w", wraplength=105).grid(row=0, column=0, padx=6, pady=4)
            ctk.CTkLabel(fila_f, text=f"${subtotal:.2f}",
                         font=("Trebuchet MS", 11, "bold"), text_color=C_GREEN).grid(row=0, column=1, padx=6)
            ctrl = ctk.CTkFrame(fila_f, fg_color="transparent")
            ctrl.grid(row=0, column=2, padx=6)
            ctk.CTkButton(ctrl, text="−", width=26, height=26, corner_radius=6,
                          fg_color=C_SURFACE, hover_color=C_BORDER,
                          command=lambda p=pid: self._cambiar_cant(p, -1)).pack(side="left", padx=2)
            ctk.CTkLabel(ctrl, text=f"x{item['cantidad']}", font=FONT_SMALL,
                         text_color=C_MUTED, width=28).pack(side="left")
            ctk.CTkButton(ctrl, text="+", width=26, height=26, corner_radius=6,
                          fg_color=C_ACCENT, hover_color="#0d9668",
                          command=lambda p=pid: self._cambiar_cant(p, 1)).pack(side="left", padx=2)

        n = sum(i["cantidad"] for i in self.carrito.values())
        self.lbl_cart_count.configure(text=f"{n} producto{'s' if n != 1 else ''}")
        self.lbl_total.configure(text=f"${total:.2f}")

    def _cambiar_cant(self, pid, delta):
        if pid in self.carrito:
            self.carrito[pid]["cantidad"] += delta
            if self.carrito[pid]["cantidad"] <= 0:
                del self.carrito[pid]
        self._refrescar_carrito()

    def _vaciar_carrito(self):
        self.carrito.clear()
        self._refrescar_carrito()
        self.lbl_msg.configure(text="Pedido vaciado.", text_color=C_MUTED)

    def _confirmar_pedido(self):
        if not self.cliente_actual:
            self.lbl_msg.configure(text="⚠ Busca o registra un cliente primero.", text_color=C_RED)
            return
        if not self.carrito:
            self.lbl_msg.configure(text="El pedido está vacío.", text_color=C_RED)
            return
        self.lbl_msg.configure(text="⏳ Procesando...", text_color=C_MUTED)
        threading.Thread(target=self._confirmar_pedido_bg, daemon=True).start()

    def _confirmar_pedido_bg(self):
        try:
            resultado = crear_pedido(self.cliente_actual["id"], self.carrito)
            self.after(0, lambda: self._pedido_exitoso(resultado))
        except (ValueError, ConnectionError) as e:
            self.after(0, lambda: self.lbl_msg.configure(text=f"⚠ {e}", text_color=C_RED))
        except Exception as e:
            self.after(0, lambda: self.lbl_msg.configure(text=f"Error: {e}", text_color=C_RED))

    def _pedido_exitoso(self, resultado):
        n = len(resultado["items_ok"])
        total = resultado["total"]
        self.ultimo_pedido_id = resultado["pedido_id"]
        self.carrito.clear()
        self._refrescar_carrito()
        self._cargar_catalogo()
        self.lbl_msg.configure(
            text=f"✅ Pedido #{self.ultimo_pedido_id} OK: {n} producto(s) — ${total:,.2f}", text_color=C_GREEN)
        self.btn_ticket.pack(fill="x", padx=14, pady=(0, 10))

    def _abrir_ticket_reciente(self):
        if self.ultimo_pedido_id:
            mostrar_detalle_pedido(self, self.ultimo_pedido_id)

    # ── HISTORIAL ─────────────────────────────────────────────────────────────

    def _ver_historial(self):
        v = ctk.CTkToplevel(self)
        v.title("Historial de Pedidos")
        v.geometry("760x540")
        v.configure(fg_color=C_SURFACE)
        v.grab_set()

        ctk.CTkLabel(v, text="📋  Historial de Pedidos",
                     font=FONT_HEAD, text_color=C_TEXT).pack(pady=(18, 8))

        filtros = ctk.CTkFrame(v, fg_color=C_CARD, corner_radius=10,
                               border_width=1, border_color=C_BORDER)
        filtros.pack(fill="x", padx=16, pady=(0, 8), ipady=4)

        ctk.CTkLabel(filtros, text="Cliente:", font=FONT_SMALL, text_color=C_MUTED).grid(row=0, column=0, padx=(12,4), pady=10)
        entry_cli = ctk.CTkEntry(filtros, placeholder_text="Nombre o teléfono...", width=150, height=30,
                                  corner_radius=8, fg_color=C_SURFACE, border_color=C_BORDER, font=FONT_SMALL)
        entry_cli.grid(row=0, column=1, padx=(0, 8))
        ctk.CTkLabel(filtros, text="Desde:", font=FONT_SMALL, text_color=C_MUTED).grid(row=0, column=2, padx=(0,4))
        entry_desde = ctk.CTkEntry(filtros, placeholder_text="dd/mm/aaaa", width=100, height=30,
                                    corner_radius=8, fg_color=C_SURFACE, border_color=C_BORDER, font=FONT_SMALL)
        entry_desde.grid(row=0, column=3, padx=(0, 8))
        ctk.CTkLabel(filtros, text="Hasta:", font=FONT_SMALL, text_color=C_MUTED).grid(row=0, column=4, padx=(0,4))
        entry_hasta = ctk.CTkEntry(filtros, placeholder_text="dd/mm/aaaa", width=100, height=30,
                                    corner_radius=8, fg_color=C_SURFACE, border_color=C_BORDER, font=FONT_SMALL)
        entry_hasta.grid(row=0, column=5, padx=(0, 8))
        ctk.CTkButton(filtros, text="Filtrar", width=76, height=30, corner_radius=8,
                      fg_color=C_ACCENT, hover_color="#0d9668", font=FONT_SMALL,
                      command=lambda: _cargar(entry_cli.get().strip() or None,
                                              entry_desde.get().strip() or None,
                                              entry_hasta.get().strip() or None)
                      ).grid(row=0, column=6, padx=4)
        ctk.CTkButton(filtros, text="Ver todo", width=76, height=30, corner_radius=8,
                      fg_color=C_SURFACE, hover_color=C_BORDER, font=FONT_SMALL,
                      command=lambda: _cargar()).grid(row=0, column=7, padx=(0, 12))

        lbl_carg = ctk.CTkLabel(v, text="", text_color=C_MUTED, font=FONT_SMALL)
        lbl_carg.pack(anchor="w", padx=16)

        frame_scroll = ctk.CTkScrollableFrame(v, height=360, fg_color=C_CARD, corner_radius=12)
        frame_scroll.pack(fill="both", expand=True, padx=16, pady=(0, 12))

        cols_hist = {"#Pedido": 60, "Cliente": 160, "Total": 80, "Estado": 90, "Fecha": 150, "": 70}

        def _enc():
            for w in frame_scroll.winfo_children():
                w.destroy()
            for col_i, (enc, ancho) in enumerate(cols_hist.items()):
                ctk.CTkLabel(frame_scroll, text=enc, font=FONT_SMALL,
                             width=ancho, anchor="w", text_color=C_MUTED).grid(
                    row=0, column=col_i, padx=5, pady=7)

        def _render(pedidos):
            lbl_carg.configure(text="")
            _enc()
            if not pedidos:
                ctk.CTkLabel(frame_scroll, text="Sin pedidos registrados.",
                             text_color=C_MUTED).grid(row=1, column=0, columnspan=6, pady=20)
                return
            for fila, h in enumerate(pedidos, start=1):
                color = C_ROW_ALT if fila % 2 == 0 else "transparent"
                ctk.CTkLabel(frame_scroll, text=str(h["id"]), width=60, anchor="w",
                             fg_color=color, font=FONT_SMALL, text_color=C_TEXT).grid(row=fila, column=0, padx=5, pady=3)
                ctk.CTkLabel(frame_scroll, text=h["cliente_nombre"], width=160, anchor="w",
                             fg_color=color, font=FONT_SMALL, text_color=C_TEXT, wraplength=150).grid(row=fila, column=1, padx=5, pady=3)
                ctk.CTkLabel(frame_scroll, text=f"${h['total']:.2f}", width=80, anchor="w",
                             fg_color=color, font=FONT_SMALL, text_color=C_TEXT).grid(row=fila, column=2, padx=5, pady=3)
                ctk.CTkLabel(frame_scroll, text=h["estado"], width=90, anchor="w",
                             fg_color=color, font=FONT_SMALL, text_color=C_TEXT).grid(row=fila, column=3, padx=5, pady=3)
                ctk.CTkLabel(frame_scroll, text=h["fecha"], width=150, anchor="w",
                             fg_color=color, font=FONT_SMALL, text_color=C_TEXT).grid(row=fila, column=4, padx=5, pady=3)
                pid = h["id"]
                ctk.CTkButton(frame_scroll, text="Ver", width=70, height=26,
                              fg_color=C_ACCENT, hover_color="#0d9668", corner_radius=6,
                              font=FONT_SMALL,
                              command=lambda p=pid: mostrar_detalle_pedido(v, p)
                              ).grid(row=fila, column=5, padx=5, pady=3)

        def _cargar(filtro_cli=None, desde=None, hasta=None):
            lbl_carg.configure(text="⏳ Cargando...")
            _enc()
            def _bg():
                pedidos = listar_pedidos(filtro_cliente=filtro_cli, fecha_desde=desde, fecha_hasta=hasta)
                v.after(0, lambda: _render(pedidos))
            threading.Thread(target=_bg, daemon=True).start()

        _cargar()

    # ── SESIÓN ────────────────────────────────────────────────────────────────

    def _cerrar_sesion(self):
        Sesion.cerrar()
        self.destroy()
        from login import LoginApp
        LoginApp().mainloop()


if __name__ == '__main__':
    VentanaVendedor().mainloop()
