import csv
import threading
from tkinter import filedialog, messagebox
import customtkinter as ctk
from sesion import Sesion
from base_de_datos.queries import (
    listar_productos, insertar_producto, actualizar_precio, actualizar_stock,
    eliminar_producto, reactivar_producto,
    listar_pedidos, cambiar_estado_pedido,
    listar_clientes,
    listar_usuarios, crear_usuario, editar_usuario, eliminar_usuario,
    resumen_negocio, estadisticas_ventas_7_dias, estadisticas_por_categoria,
)
from visualizaciones._widgets import mostrar_detalle_pedido
from visualizaciones.graficos import crear_grafico_ventas, crear_grafico_categorias

REFRESH_MS = 120_000

# ── PALETA (verde, línea de productos de limpieza) ─────────────────────────────
C_BG       = "#0a120e"
C_SURFACE  = "#0f1c15"
C_CARD     = "#16291f"
C_BORDER   = "#20382a"
C_ACCENT   = "#10b981"
C_ACCENT2  = "#3b82f6"
C_GREEN    = "#10b981"
C_RED      = "#ef4444"
C_ORANGE   = "#f59e0b"
C_PURPLE   = "#8b5cf6"
C_TEXT     = "#eafff3"
C_MUTED    = "#6b9080"
C_ROW_ALT  = "#122019"

FONT_TITLE  = ("Trebuchet MS", 22, "bold")
FONT_HEAD   = ("Trebuchet MS", 14, "bold")
FONT_BODY   = ("Trebuchet MS", 12)
FONT_SMALL  = ("Trebuchet MS", 11)
FONT_METRIC = ("Trebuchet MS", 24, "bold")

ESTADOS = ["pendiente", "confirmado", "entregado", "cancelado"]


class VentanaAdmin(ctk.CTk):

    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        sesion = Sesion.obtener()
        self.title(f"MAX LIMP  ·  Panel Admin  —  {sesion.nombre}")
        self.geometry("1240x780")
        self.configure(fg_color=C_BG)
        self._construir_interfaz()
        self._actualizar_metricas()
        self._cargar_productos()
        self._programar_refresh()

    # ── HEADER ────────────────────────────────────────────────────────────────

    def _construir_interfaz(self):
        header = ctk.CTkFrame(self, fg_color=C_SURFACE, corner_radius=0, height=62)
        header.pack(fill="x")
        header.pack_propagate(False)

        logo_frame = ctk.CTkFrame(header, fg_color=C_ACCENT, corner_radius=8, width=36, height=36)
        logo_frame.pack(side="left", padx=(18, 10), pady=13)
        logo_frame.pack_propagate(False)
        ctk.CTkLabel(logo_frame, text="M", font=("Trebuchet MS", 18, "bold"), text_color="white").place(relx=.5, rely=.5, anchor="center")

        ctk.CTkLabel(header, text="MAX LIMP", font=FONT_TITLE, text_color=C_TEXT).pack(side="left")
        ctk.CTkLabel(header, text=" / Admin", font=FONT_BODY, text_color=C_MUTED).pack(side="left", pady=4)

        sesion = Sesion.obtener()
        ctk.CTkButton(header, text="⏻  Cerrar sesión", width=140, height=34,
                      fg_color=C_RED, hover_color="#b91c1c",
                      font=FONT_SMALL, corner_radius=8,
                      command=self._cerrar_sesion).pack(side="right", padx=18, pady=14)
        ctk.CTkLabel(header, text=f"👤 {sesion.nombre}", font=FONT_SMALL,
                     text_color=C_MUTED).pack(side="right", padx=10)

        dot_frame = ctk.CTkFrame(header, fg_color="transparent")
        dot_frame.pack(side="right", padx=4)
        ctk.CTkLabel(dot_frame, text="⬤", font=("Trebuchet MS", 9), text_color=C_GREEN).pack(side="left")
        ctk.CTkLabel(dot_frame, text=" Railway", font=FONT_SMALL, text_color=C_MUTED).pack(side="left")

        # Métricas
        self.frame_metricas = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_metricas.pack(fill="x", padx=20, pady=(16, 8))
        self.metricas_labels = {}
        cards = [
            ("💰", "Ingresos",  C_GREEN,   "pedidos no cancelados"),
            ("🧾", "Pedidos",   C_ACCENT2, "no cancelados"),
            ("🧴", "Productos", C_PURPLE,  "activos en catálogo"),
            ("👥", "Clientes",  C_ORANGE,  "registrados"),
            ("⚠️", "Bajo stock", C_RED,    "menos de 5 unidades"),
        ]
        for col, (ico, titulo, color, sub) in enumerate(cards):
            self.frame_metricas.grid_columnconfigure(col, weight=1)
            card = ctk.CTkFrame(self.frame_metricas, fg_color=C_CARD,
                                corner_radius=14, border_width=1, border_color=C_BORDER)
            card.grid(row=0, column=col, padx=6, sticky="ew", ipady=6)

            accent_bar = ctk.CTkFrame(card, fg_color=color, height=3, corner_radius=2)
            accent_bar.pack(fill="x", padx=0, pady=(0, 8))

            ctk.CTkLabel(card, text=f"{ico}  {titulo}", font=FONT_SMALL,
                         text_color=C_MUTED).pack(padx=14, anchor="w")
            lbl = ctk.CTkLabel(card, text="—", font=FONT_METRIC, text_color=C_TEXT)
            lbl.pack(padx=14, anchor="w")
            ctk.CTkLabel(card, text=sub, font=("Trebuchet MS", 10),
                         text_color=C_MUTED).pack(padx=14, anchor="w", pady=(0, 10))
            self.metricas_labels[titulo] = lbl

        # Tabs
        tab_bar = ctk.CTkFrame(self, fg_color=C_SURFACE, corner_radius=0, height=46)
        tab_bar.pack(fill="x")
        tab_bar.pack_propagate(False)
        self.btn_tabs = {}
        for texto, cmd in [("📊  Resumen",    self._mostrar_tab_resumen),
                           ("🧴  Productos",  self._mostrar_tab_productos),
                           ("🧾  Pedidos",    self._mostrar_tab_pedidos),
                           ("👥  Clientes",   self._mostrar_tab_clientes),
                           ("🔐  Usuarios",   self._mostrar_tab_usuarios)]:
            b = ctk.CTkButton(tab_bar, text=texto, width=140, height=36,
                              fg_color="transparent", hover_color=C_CARD,
                              text_color=C_MUTED, font=FONT_SMALL,
                              corner_radius=0, command=cmd)
            b.pack(side="left", padx=2)
            self.btn_tabs[texto] = b

        self.frame_tab = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_tab.pack(fill="both", expand=True, padx=20, pady=12)

        self._construir_tab_resumen()
        self._construir_tab_productos()
        self._construir_tab_pedidos()
        self._construir_tab_clientes()
        self._construir_tab_usuarios()
        self._mostrar_tab_resumen()

    def _activar_tab(self, nombre: str):
        for k, b in self.btn_tabs.items():
            if k == nombre:
                b.configure(fg_color=C_CARD, text_color=C_ACCENT, border_width=0)
            else:
                b.configure(fg_color="transparent", text_color=C_MUTED)

    def _ocultar_tabs(self):
        for f in (self.tab_resumen, self.tab_productos, self.tab_pedidos,
                  self.tab_clientes, self.tab_usuarios):
            f.pack_forget()

    # ── TAB RESUMEN (gráficos) ───────────────────────────────────────────────

    def _construir_tab_resumen(self):
        self.tab_resumen = ctk.CTkFrame(self.frame_tab, fg_color="transparent")
        self.frame_graficos = ctk.CTkFrame(self.tab_resumen, fg_color="transparent")
        self.frame_graficos.pack(fill="both", expand=True)
        self.frame_graficos.grid_columnconfigure(0, weight=1)
        self.frame_graficos.grid_columnconfigure(1, weight=1)
        self._render_graficos()

    def _render_graficos(self):
        for w in self.frame_graficos.winfo_children():
            w.destroy()

        card1 = ctk.CTkFrame(self.frame_graficos, fg_color=C_CARD, corner_radius=14,
                             border_width=1, border_color=C_BORDER)
        card1.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=4)
        card2 = ctk.CTkFrame(self.frame_graficos, fg_color=C_CARD, corner_radius=14,
                             border_width=1, border_color=C_BORDER)
        card2.grid(row=0, column=1, sticky="nsew", padx=(8, 0), pady=4)

        def _bg():
            ventas7 = estadisticas_ventas_7_dias()
            cats = estadisticas_por_categoria()
            self.after(0, lambda: _dibujar(ventas7, cats))

        def _dibujar(ventas7, cats):
            if ventas7:
                w1 = crear_grafico_ventas(card1, ventas7)
                w1.pack(padx=10, pady=10, fill="both", expand=True)
            else:
                ctk.CTkLabel(card1, text="Sin ventas en los últimos 7 días.",
                             text_color=C_MUTED).pack(expand=True, pady=40)
            if cats:
                w2 = crear_grafico_categorias(card2, cats)
                w2.pack(padx=10, pady=10, fill="both", expand=True)
            else:
                ctk.CTkLabel(card2, text="Sin ventas por categoría todavía.",
                             text_color=C_MUTED).pack(expand=True, pady=40)

        threading.Thread(target=_bg, daemon=True).start()

    def _mostrar_tab_resumen(self):
        self._ocultar_tabs()
        self.tab_resumen.pack(fill="both", expand=True)
        self._activar_tab("📊  Resumen")
        self._render_graficos()

    # ── TAB PRODUCTOS ─────────────────────────────────────────────────────────

    def _construir_tab_productos(self):
        self.tab_productos = ctk.CTkFrame(self.frame_tab, fg_color="transparent")

        acc = ctk.CTkFrame(self.tab_productos, fg_color=C_CARD,
                           corner_radius=10, border_width=1, border_color=C_BORDER)
        acc.pack(fill="x", pady=(0, 8), ipady=6)

        self.prod_entry_buscar = ctk.CTkEntry(acc, placeholder_text="🔍  Buscar producto...",
                                              width=220, height=32, corner_radius=8,
                                              fg_color=C_SURFACE, border_color=C_BORDER,
                                              font=FONT_SMALL)
        self.prod_entry_buscar.pack(side="left", padx=(12, 4), pady=8)
        self.prod_entry_buscar.bind("<Return>", lambda e: self._buscar_productos())

        ctk.CTkButton(acc, text="Buscar", width=80, height=32, corner_radius=8,
                      fg_color=C_ACCENT, hover_color="#0d9668", font=FONT_SMALL,
                      command=self._buscar_productos).pack(side="left", padx=4)
        ctk.CTkButton(acc, text="Ver todo", width=80, height=32, corner_radius=8,
                      fg_color=C_SURFACE, hover_color=C_BORDER, font=FONT_SMALL,
                      command=self._cargar_productos).pack(side="left", padx=4)
        ctk.CTkButton(acc, text="📥 Exportar CSV", width=110, height=32, corner_radius=8,
                      fg_color=C_SURFACE, hover_color=C_BORDER, font=FONT_SMALL,
                      command=self._exportar_productos_csv).pack(side="left", padx=4)

        ctk.CTkButton(acc, text="➕ Nuevo", width=100, height=32, corner_radius=8,
                      fg_color=C_GREEN, hover_color="#0d9668", font=FONT_SMALL,
                      command=self._nuevo_producto).pack(side="right", padx=4)
        ctk.CTkButton(acc, text="✏️ Precio", width=90, height=32, corner_radius=8,
                      fg_color=C_ORANGE, hover_color="#d97706", font=FONT_SMALL,
                      command=self._modificar_precio).pack(side="right", padx=4)
        ctk.CTkButton(acc, text="📦 Stock", width=90, height=32, corner_radius=8,
                      fg_color=C_ACCENT2, hover_color="#2563eb", font=FONT_SMALL,
                      command=self._modificar_stock).pack(side="right", padx=4)
        ctk.CTkButton(acc, text="🗑 Dar de baja", width=110, height=32, corner_radius=8,
                      fg_color=C_RED, hover_color="#b91c1c", font=FONT_SMALL,
                      command=self._eliminar_producto).pack(side="right", padx=4)

        # Banner de stock crítico
        self.banner_stock_prod = ctk.CTkFrame(self.tab_productos, fg_color="#3b1515", corner_radius=8,
                                              border_width=1, border_color=C_RED)
        self.lbl_banner_stock = ctk.CTkLabel(self.banner_stock_prod, text="", font=FONT_SMALL, text_color="#fca5a5")
        self.lbl_banner_stock.pack(side="left", padx=12, pady=6)

        self.prod_lbl_cargando = ctk.CTkLabel(self.tab_productos, text="", text_color=C_MUTED, font=FONT_SMALL)
        self.prod_lbl_cargando.pack(anchor="w")

        self.frame_prod_tabla = ctk.CTkScrollableFrame(self.tab_productos, fg_color=C_CARD, corner_radius=12,
                                                        border_width=1, border_color=C_BORDER)
        self.frame_prod_tabla.pack(fill="both", expand=True, pady=(4, 0))

        self.cols_prod = {"ID": 45, "Nombre": 230, "Categoría": 130, "Precio": 80, "Stock": 65, "Activo": 60}
        self._render_prod_encabezado()

    def _render_prod_encabezado(self):
        # CTkScrollableFrame wraps widgets inside ._scrollable_frame internamente.
        # winfo_children() en el frame externo sólo devuelve el canvas/scrollbar
        # de la infraestructura de CTk, NO nuestras filas. Hay que limpiar el frame interno.
        inner = getattr(self.frame_prod_tabla, "_scrollable_frame", self.frame_prod_tabla)
        for w in inner.winfo_children():
            w.destroy()
        for col_i, (enc, ancho) in enumerate(self.cols_prod.items()):
            ctk.CTkLabel(self.frame_prod_tabla, text=enc, font=FONT_SMALL,
                         width=ancho, anchor="w", text_color=C_MUTED).grid(
                row=0, column=col_i, padx=5, pady=7)

    def _mostrar_tab_productos(self):
        self._ocultar_tabs()
        self.tab_productos.pack(fill="both", expand=True)
        self._activar_tab("🧴  Productos")
        self._cargar_productos()

    def _cargar_productos(self):
        self.prod_lbl_cargando.configure(text="⏳ Cargando productos...")
        threading.Thread(target=self._cargar_productos_bg, args=(None,), daemon=True).start()

    def _buscar_productos(self):
        filtro = self.prod_entry_buscar.get().strip() or None
        self.prod_lbl_cargando.configure(text="⏳ Buscando...")
        threading.Thread(target=self._cargar_productos_bg, args=(filtro,), daemon=True).start()

    def _cargar_productos_bg(self, filtro):
        try:
            productos = listar_productos(filtro=filtro, solo_activos=False)
            self.after(0, lambda: self._render_productos(productos))
        except Exception as e:
            self.after(0, lambda: self.prod_lbl_cargando.configure(
                text=f"❌ Error al cargar productos: {e}", text_color=C_RED
            ))

    def _render_productos(self, productos):
        self.prod_lbl_cargando.configure(text="")
        self._render_prod_encabezado()
        if not productos:
            ctk.CTkLabel(self.frame_prod_tabla, text="Sin productos.",
                         text_color=C_MUTED).grid(row=1, column=0, columnspan=6, pady=20)
            return
        for fila, p in enumerate(productos, start=1):
            color = C_ROW_ALT if fila % 2 == 0 else "transparent"
            vals = [str(p["id"]), p["nombre"], p["categoria"], f"${p['precio']:.2f}", str(p["stock"])]
            for col_i, val in enumerate(vals):
                text_color = C_RED if (col_i == 4 and p["stock"] < 5) else C_TEXT
                ctk.CTkLabel(self.frame_prod_tabla, text=val, width=list(self.cols_prod.values())[col_i],
                             anchor="w", fg_color=color, font=FONT_SMALL, text_color=text_color,
                             wraplength=220 if col_i == 1 else None).grid(row=fila, column=col_i, padx=5, pady=3)
            act_txt = "Sí" if p["activo"] else "No"
            act_color = C_GREEN if p["activo"] else C_MUTED
            ctk.CTkLabel(self.frame_prod_tabla, text=act_txt, width=self.cols_prod["Activo"],
                         anchor="w", fg_color=color, font=FONT_SMALL, text_color=act_color).grid(
                row=fila, column=5, padx=5, pady=3)

    def _popup(self, titulo, w, h):
        v = ctk.CTkToplevel(self)
        v.title(titulo)
        v.geometry(f"{w}x{h}")
        v.configure(fg_color=C_SURFACE)
        v.grab_set()
        ctk.CTkLabel(v, text=titulo, font=FONT_HEAD, text_color=C_TEXT).pack(pady=(18, 10))
        return v

    def _nuevo_producto(self):
        v = self._popup("➕  Nuevo Producto", 400, 480)
        campos = {}
        for campo, ph in [("Nombre", ""), ("Categoría", ""), ("Descripción", "Opcional"),
                          ("Precio", "0.00"), ("Stock inicial", "0"), ("Imagen (URL)", "Opcional")]:
            ctk.CTkLabel(v, text=campo+":", font=FONT_SMALL, text_color=C_MUTED).pack(anchor="w", padx=30)
            e = ctk.CTkEntry(v, width=330, height=32, corner_radius=8,
                             fg_color=C_CARD, border_color=C_BORDER, font=FONT_BODY, placeholder_text=ph)
            e.pack(pady=(0, 6))
            campos[campo] = e
        lbl = ctk.CTkLabel(v, text="", text_color=C_RED, font=FONT_SMALL)
        lbl.pack()

        def guardar():
            try:
                datos = {
                    "nombre": campos["Nombre"].get(),
                    "categoria": campos["Categoría"].get(),
                    "descripcion": campos["Descripción"].get(),
                    "precio": float(campos["Precio"].get() or 0),
                    "stock": int(campos["Stock inicial"].get() or 0),
                    "imagen_url": campos["Imagen (URL)"].get(),
                }
                insertar_producto(datos)
                v.destroy(); self._cargar_productos(); self._actualizar_metricas()
            except Exception as e:
                lbl.configure(text=f"Error: {e}")

        ctk.CTkButton(v, text="Guardar", width=330, height=38, corner_radius=8,
                      fg_color=C_GREEN, hover_color="#0d9668", font=FONT_BODY,
                      command=guardar).pack(pady=10)

    def _modificar_precio(self):
        v = self._popup("✏️  Modificar Precio", 380, 240)
        ctk.CTkLabel(v, text="ID del producto:", font=FONT_SMALL, text_color=C_MUTED).pack(anchor="w", padx=30)
        e_id = ctk.CTkEntry(v, width=310, height=34, corner_radius=8,
                            fg_color=C_CARD, border_color=C_BORDER, font=FONT_BODY)
        e_id.pack(pady=(0, 8))
        ctk.CTkLabel(v, text="Nuevo precio ($):", font=FONT_SMALL, text_color=C_MUTED).pack(anchor="w", padx=30)
        e_precio = ctk.CTkEntry(v, width=310, height=34, corner_radius=8,
                                fg_color=C_CARD, border_color=C_BORDER, font=FONT_BODY)
        e_precio.pack(pady=(0, 8))
        lbl = ctk.CTkLabel(v, text="", text_color=C_RED, font=FONT_SMALL)
        lbl.pack()
        def guardar():
            try:
                actualizar_precio(int(e_id.get()), float(e_precio.get()))
                v.destroy(); self._cargar_productos()
            except Exception as e:
                lbl.configure(text=f"Error: {e}")
        ctk.CTkButton(v, text="Actualizar", width=310, height=36, corner_radius=8,
                      fg_color=C_ORANGE, hover_color="#d97706", font=FONT_BODY,
                      command=guardar).pack(pady=8)

    def _modificar_stock(self):
        v = self._popup("📦  Reponer / Ajustar Stock", 380, 260)
        ctk.CTkLabel(v, text="ID del producto:", font=FONT_SMALL, text_color=C_MUTED).pack(anchor="w", padx=30)
        e_id = ctk.CTkEntry(v, width=310, height=34, corner_radius=8,
                            fg_color=C_CARD, border_color=C_BORDER, font=FONT_BODY)
        e_id.pack(pady=(0, 8))
        ctk.CTkLabel(v, text="Nuevo stock total:", font=FONT_SMALL, text_color=C_MUTED).pack(anchor="w", padx=30)
        e_stock = ctk.CTkEntry(v, width=310, height=34, corner_radius=8,
                               fg_color=C_CARD, border_color=C_BORDER, font=FONT_BODY)
        e_stock.pack(pady=(0, 8))
        ctk.CTkLabel(v, text="(Para reponer, súmale a la cantidad actual)",
                     font=("Trebuchet MS", 10), text_color=C_MUTED).pack()
        lbl = ctk.CTkLabel(v, text="", text_color=C_RED, font=FONT_SMALL)
        lbl.pack()
        def guardar():
            try:
                actualizar_stock(int(e_id.get()), int(e_stock.get()))
                v.destroy(); self._cargar_productos()
            except Exception as e:
                lbl.configure(text=f"Error: {e}")
        ctk.CTkButton(v, text="Actualizar", width=310, height=36, corner_radius=8,
                      fg_color=C_ACCENT2, hover_color="#2563eb", font=FONT_BODY,
                      command=guardar).pack(pady=8)

    def _eliminar_producto(self):
        v = self._popup("🗑  Dar de baja / Reactivar Producto", 400, 240)
        ctk.CTkLabel(v, text="ID del producto:", font=FONT_SMALL, text_color=C_MUTED).pack(anchor="w", padx=30)
        e_id = ctk.CTkEntry(v, width=330, height=34, corner_radius=8,
                            fg_color=C_CARD, border_color=C_BORDER, font=FONT_BODY)
        e_id.pack(pady=(0, 4))
        ctk.CTkLabel(v, text="Se marca como inactivo (no se borra el historial).",
                     font=("Trebuchet MS", 10), text_color=C_MUTED).pack()
        lbl = ctk.CTkLabel(v, text="", text_color=C_RED, font=FONT_SMALL)
        lbl.pack(pady=4)
        botones = ctk.CTkFrame(v, fg_color="transparent")
        botones.pack(pady=8)
        def dar_baja():
            try:
                eliminar_producto(int(e_id.get()))
                v.destroy(); self._cargar_productos(); self._actualizar_metricas()
            except Exception as e:
                lbl.configure(text=f"Error: {e}")
        def reactivar():
            try:
                reactivar_producto(int(e_id.get()))
                v.destroy(); self._cargar_productos(); self._actualizar_metricas()
            except Exception as e:
                lbl.configure(text=f"Error: {e}")
        ctk.CTkButton(botones, text="Dar de baja", width=150, height=36, corner_radius=8,
                      fg_color=C_RED, hover_color="#b91c1c", font=FONT_BODY,
                      command=dar_baja).pack(side="left", padx=4)
        ctk.CTkButton(botones, text="Reactivar", width=150, height=36, corner_radius=8,
                      fg_color=C_GREEN, hover_color="#0d9668", font=FONT_BODY,
                      command=reactivar).pack(side="left", padx=4)

    # ── TAB PEDIDOS ───────────────────────────────────────────────────────────

    def _construir_tab_pedidos(self):
        self.tab_pedidos = ctk.CTkFrame(self.frame_tab, fg_color="transparent")

        acc = ctk.CTkFrame(self.tab_pedidos, fg_color=C_CARD,
                           corner_radius=10, border_width=1, border_color=C_BORDER)
        acc.pack(fill="x", pady=(0, 8), ipady=6)

        self.ped_entry_cliente = ctk.CTkEntry(acc, placeholder_text="Cliente (nombre o teléfono)...",
                                              width=200, height=32, corner_radius=8,
                                              fg_color=C_SURFACE, border_color=C_BORDER, font=FONT_SMALL)
        self.ped_entry_cliente.pack(side="left", padx=(12, 4), pady=8)

        self.ped_estado_var = ctk.StringVar(value="Todos")
        estado_menu = ctk.CTkOptionMenu(acc, values=["Todos"] + ESTADOS, variable=self.ped_estado_var,
                                        width=130, height=32, fg_color=C_SURFACE, button_color=C_ACCENT,
                                        font=FONT_SMALL)
        estado_menu.pack(side="left", padx=4)

        ctk.CTkButton(acc, text="Filtrar", width=80, height=32, corner_radius=8,
                      fg_color=C_ACCENT, hover_color="#0d9668", font=FONT_SMALL,
                      command=self._buscar_pedidos).pack(side="left", padx=4)
        ctk.CTkButton(acc, text="Ver todo", width=80, height=32, corner_radius=8,
                      fg_color=C_SURFACE, hover_color=C_BORDER, font=FONT_SMALL,
                      command=self._cargar_pedidos).pack(side="left", padx=4)
        ctk.CTkButton(acc, text="📥 Exportar CSV", width=110, height=32, corner_radius=8,
                      fg_color=C_SURFACE, hover_color=C_BORDER, font=FONT_SMALL,
                      command=self._exportar_pedidos_csv).pack(side="left", padx=4)
        ctk.CTkButton(acc, text="Cambiar estado", width=120, height=32, corner_radius=8,
                      fg_color=C_ORANGE, hover_color="#d97706", font=FONT_SMALL,
                      command=self._cambiar_estado_ui).pack(side="right", padx=(4, 12))

        self.ped_lbl_cargando = ctk.CTkLabel(self.tab_pedidos, text="", text_color=C_MUTED, font=FONT_SMALL)
        self.ped_lbl_cargando.pack(anchor="w")

        self.frame_ped_tabla = ctk.CTkScrollableFrame(self.tab_pedidos, fg_color=C_CARD, corner_radius=12,
                                                       border_width=1, border_color=C_BORDER)
        self.frame_ped_tabla.pack(fill="both", expand=True, pady=(4, 0))

        self.cols_ped = {"#Pedido": 60, "Cliente": 180, "Teléfono": 110, "Total": 80,
                         "Estado": 90, "Fecha": 150, "": 70}
        self._render_ped_encabezado()

    def _render_ped_encabezado(self):
        inner = getattr(self.frame_ped_tabla, "_scrollable_frame", self.frame_ped_tabla)
        for w in inner.winfo_children():
            w.destroy()
        for col_i, (enc, ancho) in enumerate(self.cols_ped.items()):
            ctk.CTkLabel(self.frame_ped_tabla, text=enc, font=FONT_SMALL,
                         width=ancho, anchor="w", text_color=C_MUTED).grid(
                row=0, column=col_i, padx=5, pady=7)

    def _mostrar_tab_pedidos(self):
        self._ocultar_tabs()
        self.tab_pedidos.pack(fill="both", expand=True)
        self._activar_tab("🧾  Pedidos")
        self._cargar_pedidos()

    def _cargar_pedidos(self):
        self.ped_lbl_cargando.configure(text="⏳ Cargando pedidos...")
        threading.Thread(target=self._cargar_pedidos_bg, args=(None, None), daemon=True).start()

    def _buscar_pedidos(self):
        filtro = self.ped_entry_cliente.get().strip() or None
        estado = self.ped_estado_var.get()
        estado = None if estado == "Todos" else estado
        self.ped_lbl_cargando.configure(text="⏳ Buscando...")
        threading.Thread(target=self._cargar_pedidos_bg, args=(filtro, estado), daemon=True).start()

    def _cargar_pedidos_bg(self, filtro, estado):
        try:
            pedidos = listar_pedidos(filtro_cliente=filtro, estado=estado)
            self.after(0, lambda: self._render_pedidos(pedidos))
        except Exception as e:
            self.after(0, lambda: self.ped_lbl_cargando.configure(
                text=f"❌ Error al cargar pedidos: {e}", text_color=C_RED
            ))

    def _render_pedidos(self, pedidos):
        self.ped_lbl_cargando.configure(text="")
        self._render_ped_encabezado()
        if not pedidos:
            ctk.CTkLabel(self.frame_ped_tabla, text="Sin pedidos.",
                         text_color=C_MUTED).grid(row=1, column=0, columnspan=7, pady=20)
            return
        for fila, h in enumerate(pedidos, start=1):
            color = C_ROW_ALT if fila % 2 == 0 else "transparent"
            estado_color = {"pendiente": C_ORANGE, "confirmado": C_ACCENT2,
                            "entregado": C_GREEN, "cancelado": C_RED}.get(h["estado"], C_TEXT)
            vals = [str(h["id"]), h["cliente_nombre"], h["cliente_telefono"] or "",
                   f"${h['total']:.2f}"]
            for col_i, val in enumerate(vals):
                ctk.CTkLabel(self.frame_ped_tabla, text=val, width=list(self.cols_ped.values())[col_i],
                             anchor="w", fg_color=color, font=FONT_SMALL, text_color=C_TEXT,
                             wraplength=170 if col_i == 1 else None).grid(row=fila, column=col_i, padx=5, pady=3)
            ctk.CTkLabel(self.frame_ped_tabla, text=h["estado"], width=self.cols_ped["Estado"],
                         anchor="w", fg_color=color, font=FONT_SMALL, text_color=estado_color).grid(
                row=fila, column=4, padx=5, pady=3)
            ctk.CTkLabel(self.frame_ped_tabla, text=h["fecha"], width=self.cols_ped["Fecha"],
                         anchor="w", fg_color=color, font=FONT_SMALL, text_color=C_TEXT).grid(
                row=fila, column=5, padx=5, pady=3)
            pid = h["id"]
            ctk.CTkButton(self.frame_ped_tabla, text="Ver", width=70, height=26,
                          fg_color=C_ACCENT, hover_color="#0d9668", corner_radius=6, font=FONT_SMALL,
                          command=lambda p=pid: mostrar_detalle_pedido(self, p)
                          ).grid(row=fila, column=6, padx=5, pady=3)

    def _cambiar_estado_ui(self):
        v = self._popup("🔄  Cambiar Estado de Pedido", 380, 300)
        ctk.CTkLabel(v, text="# de Pedido:", font=FONT_SMALL, text_color=C_MUTED).pack(anchor="w", padx=30)
        e_id = ctk.CTkEntry(v, width=310, height=34, corner_radius=8,
                            fg_color=C_CARD, border_color=C_BORDER, font=FONT_BODY)
        e_id.pack(pady=(0, 8))
        ctk.CTkLabel(v, text="Nuevo estado:", font=FONT_SMALL, text_color=C_MUTED).pack(anchor="w", padx=30)
        estado_var = ctk.StringVar(value=ESTADOS[0])
        menu = ctk.CTkOptionMenu(v, values=ESTADOS, variable=estado_var, width=310, height=34,
                                 fg_color=C_CARD, button_color=C_ACCENT, font=FONT_BODY)
        menu.pack(pady=(0, 8))
        ctk.CTkLabel(v, text="Cancelar un pedido devuelve el stock reservado.",
                     font=("Trebuchet MS", 10), text_color=C_MUTED).pack()
        lbl = ctk.CTkLabel(v, text="", text_color=C_RED, font=FONT_SMALL)
        lbl.pack(pady=4)
        def guardar():
            try:
                cambiar_estado_pedido(int(e_id.get()), estado_var.get())
                v.destroy(); self._cargar_pedidos(); self._actualizar_metricas(); self._cargar_productos()
            except Exception as e:
                lbl.configure(text=f"Error: {e}")
        ctk.CTkButton(v, text="Guardar", width=310, height=36, corner_radius=8,
                      fg_color=C_GREEN, hover_color="#0d9668", font=FONT_BODY,
                      command=guardar).pack(pady=8)

    # ── TAB CLIENTES ──────────────────────────────────────────────────────────

    def _construir_tab_clientes(self):
        self.tab_clientes = ctk.CTkFrame(self.frame_tab, fg_color="transparent")

        acc = ctk.CTkFrame(self.tab_clientes, fg_color=C_CARD,
                           corner_radius=10, border_width=1, border_color=C_BORDER)
        acc.pack(fill="x", pady=(0, 8), ipady=6)

        self.cli_entry_buscar = ctk.CTkEntry(acc, placeholder_text="🔍  Buscar por nombre o teléfono...",
                                             width=260, height=32, corner_radius=8,
                                             fg_color=C_SURFACE, border_color=C_BORDER, font=FONT_SMALL)
        self.cli_entry_buscar.pack(side="left", padx=(12, 4), pady=8)
        self.cli_entry_buscar.bind("<Return>", lambda e: self._buscar_clientes())

        ctk.CTkButton(acc, text="Buscar", width=80, height=32, corner_radius=8,
                      fg_color=C_ACCENT, hover_color="#0d9668", font=FONT_SMALL,
                      command=self._buscar_clientes).pack(side="left", padx=4)
        ctk.CTkButton(acc, text="Ver todo", width=80, height=32, corner_radius=8,
                      fg_color=C_SURFACE, hover_color=C_BORDER, font=FONT_SMALL,
                      command=self._cargar_clientes).pack(side="left", padx=4)

        self.frame_cli_tabla = ctk.CTkScrollableFrame(self.tab_clientes, fg_color=C_CARD, corner_radius=12,
                                                       border_width=1, border_color=C_BORDER)
        self.frame_cli_tabla.pack(fill="both", expand=True, pady=(4, 0))

        self.cols_cli = {"ID": 45, "Nombre": 220, "Teléfono": 140, "Dirección": 280}
        self._render_cli_encabezado()

    def _render_cli_encabezado(self):
        inner = getattr(self.frame_cli_tabla, "_scrollable_frame", self.frame_cli_tabla)
        for w in inner.winfo_children():
            w.destroy()
        for col_i, (enc, ancho) in enumerate(self.cols_cli.items()):
            ctk.CTkLabel(self.frame_cli_tabla, text=enc, font=FONT_SMALL,
                         width=ancho, anchor="w", text_color=C_MUTED).grid(
                row=0, column=col_i, padx=5, pady=7)

    def _mostrar_tab_clientes(self):
        self._ocultar_tabs()
        self.tab_clientes.pack(fill="both", expand=True)
        self._activar_tab("👥  Clientes")
        self._cargar_clientes()

    def _cargar_clientes(self):
        threading.Thread(target=self._cargar_clientes_bg, args=(None,), daemon=True).start()

    def _buscar_clientes(self):
        filtro = self.cli_entry_buscar.get().strip() or None
        threading.Thread(target=self._cargar_clientes_bg, args=(filtro,), daemon=True).start()

    def _cargar_clientes_bg(self, filtro):
        clientes = listar_clientes(filtro=filtro)
        self.after(0, lambda: self._render_clientes(clientes))

    def _render_clientes(self, clientes):
        self._render_cli_encabezado()
        if not clientes:
            ctk.CTkLabel(self.frame_cli_tabla, text="Sin clientes registrados todavía.",
                         text_color=C_MUTED).grid(row=1, column=0, columnspan=4, pady=20)
            return
        for fila, c in enumerate(clientes, start=1):
            color = C_ROW_ALT if fila % 2 == 0 else "transparent"
            vals = [str(c["id"]), c["nombre"], c["telefono"], c["direccion"]]
            for col_i, val in enumerate(vals):
                ctk.CTkLabel(self.frame_cli_tabla, text=val, width=list(self.cols_cli.values())[col_i],
                             anchor="w", fg_color=color, font=FONT_SMALL, text_color=C_TEXT,
                             wraplength=260 if col_i == 3 else None).grid(row=fila, column=col_i, padx=5, pady=4)

    # ── TAB USUARIOS (staff del panel) ───────────────────────────────────────

    def _construir_tab_usuarios(self):
        self.tab_usuarios = ctk.CTkFrame(self.frame_tab, fg_color="transparent")

        acc = ctk.CTkFrame(self.tab_usuarios, fg_color=C_CARD,
                           corner_radius=10, border_width=1, border_color=C_BORDER)
        acc.pack(fill="x", pady=(0, 8), ipady=6)

        ctk.CTkLabel(acc, text="Cuentas de acceso al panel (admin / vendedor)",
                     font=FONT_SMALL, text_color=C_MUTED).pack(side="left", padx=12)
        ctk.CTkButton(acc, text="➕ Nuevo", width=100, height=32, corner_radius=8,
                      fg_color=C_GREEN, hover_color="#0d9668", font=FONT_SMALL,
                      command=self._nuevo_usuario).pack(side="right", padx=4)
        ctk.CTkButton(acc, text="✏️ Editar", width=90, height=32, corner_radius=8,
                      fg_color=C_ORANGE, hover_color="#d97706", font=FONT_SMALL,
                      command=self._editar_usuario_ui).pack(side="right", padx=4)
        ctk.CTkButton(acc, text="🗑 Eliminar", width=100, height=32, corner_radius=8,
                      fg_color=C_RED, hover_color="#b91c1c", font=FONT_SMALL,
                      command=self._eliminar_usuario_ui).pack(side="right", padx=4)

        self.frame_usr_tabla = ctk.CTkScrollableFrame(self.tab_usuarios, fg_color=C_CARD, corner_radius=12,
                                                       border_width=1, border_color=C_BORDER)
        self.frame_usr_tabla.pack(fill="both", expand=True, pady=(4, 0))

        self.cols_usr = {"ID": 50, "Nombre": 220, "Usuario": 180, "Rol": 120}
        self._render_usr_encabezado()

    def _render_usr_encabezado(self):
        inner = getattr(self.frame_usr_tabla, "_scrollable_frame", self.frame_usr_tabla)
        for w in inner.winfo_children():
            w.destroy()
        for col_i, (enc, ancho) in enumerate(self.cols_usr.items()):
            ctk.CTkLabel(self.frame_usr_tabla, text=enc, font=FONT_SMALL,
                         width=ancho, anchor="w", text_color=C_MUTED).grid(
                row=0, column=col_i, padx=5, pady=7)

    def _mostrar_tab_usuarios(self):
        self._ocultar_tabs()
        self.tab_usuarios.pack(fill="both", expand=True)
        self._activar_tab("🔐  Usuarios")
        self._cargar_usuarios_tabla()

    def _cargar_usuarios_tabla(self):
        self._render_usr_encabezado()
        usuarios = listar_usuarios()
        if not usuarios:
            ctk.CTkLabel(self.frame_usr_tabla, text="Sin usuarios.",
                         text_color=C_MUTED).grid(row=1, column=0, columnspan=4, pady=20)
            return
        for fila, u in enumerate(usuarios, start=1):
            color = C_ROW_ALT if fila % 2 == 0 else "transparent"
            vals = [str(u["id"]), u["nombre"], u["usuario"], u["rol"]]
            for col_i, val in enumerate(vals):
                ctk.CTkLabel(self.frame_usr_tabla, text=val, width=list(self.cols_usr.values())[col_i],
                             anchor="w", fg_color=color, font=FONT_SMALL, text_color=C_TEXT).grid(
                row=fila, column=col_i, padx=5, pady=4)

    def _form_usuario(self, titulo, defaults=None, on_guardar=None):
        v = ctk.CTkToplevel(self)
        v.title(titulo)
        v.geometry("440x460")
        v.configure(fg_color=C_SURFACE)
        v.grab_set()
        defaults = defaults or {}
        ctk.CTkLabel(v, text=titulo, font=FONT_HEAD, text_color=C_TEXT).pack(pady=(20, 10))
        entries = {}
        for campo, ph in [("Nombre completo", ""), ("Nombre de usuario", ""), ("Contraseña", "Dejar vacío para no cambiar")]:
            ctk.CTkLabel(v, text=campo+":", font=FONT_SMALL, text_color=C_MUTED).pack(anchor="w", padx=30)
            e = ctk.CTkEntry(v, width=370, height=34, corner_radius=8,
                             fg_color=C_CARD, border_color=C_BORDER, font=FONT_BODY,
                             show="*" if campo == "Contraseña" else "",
                             placeholder_text=ph)
            if campo in defaults:
                e.insert(0, defaults[campo])
            e.pack(pady=(0, 8))
            entries[campo] = e
        ctk.CTkLabel(v, text="Rol:", font=FONT_SMALL, text_color=C_MUTED).pack(anchor="w", padx=30)
        rol_var = ctk.StringVar(value=defaults.get("Rol", "vendedor"))
        frame_rol = ctk.CTkFrame(v, fg_color="transparent")
        frame_rol.pack(anchor="w", padx=30, pady=(0, 8))
        ctk.CTkRadioButton(frame_rol, text="Vendedor", variable=rol_var, value="vendedor",
                           font=FONT_SMALL).pack(side="left", padx=(0, 16))
        ctk.CTkRadioButton(frame_rol, text="Admin", variable=rol_var, value="admin",
                           font=FONT_SMALL).pack(side="left")
        lbl = ctk.CTkLabel(v, text="", text_color=C_RED, font=FONT_SMALL)
        lbl.pack()
        def guardar():
            try:
                on_guardar(entries["Nombre completo"].get(),
                           entries["Nombre de usuario"].get(),
                           entries["Contraseña"].get(), rol_var.get())
                v.destroy(); self._cargar_usuarios_tabla()
            except Exception as e:
                lbl.configure(text=f"Error: {e}")
        ctk.CTkButton(v, text="Guardar", width=370, height=38, corner_radius=8,
                      fg_color=C_GREEN, hover_color="#0d9668", font=FONT_BODY,
                      command=guardar).pack(pady=12)

    def _nuevo_usuario(self):
        def on_guardar(nombre, usuario, pw, rol):
            if not pw: raise ValueError("La contraseña es obligatoria.")
            crear_usuario(nombre, usuario, pw, rol)
        self._form_usuario("➕  Nuevo Usuario del Panel", on_guardar=on_guardar)

    def _editar_usuario_ui(self):
        v = self._popup("✏️  Editar — Seleccionar ID", 360, 180)
        e_id = ctk.CTkEntry(v, width=290, height=34, corner_radius=8,
                            fg_color=C_CARD, border_color=C_BORDER, font=FONT_BODY)
        e_id.pack(pady=(0, 8))
        lbl = ctk.CTkLabel(v, text="", text_color=C_RED, font=FONT_SMALL)
        lbl.pack()
        def abrir():
            try:
                uid = int(e_id.get())
                usuarios = listar_usuarios()
                u = next((x for x in usuarios if x["id"] == uid), None)
                if not u: lbl.configure(text=f"No existe usuario con ID {uid}."); return
                v.destroy()
                def on_guardar(nombre, usuario, pw, rol):
                    editar_usuario(uid, nombre, usuario, rol, pw if pw.strip() else None)
                self._form_usuario(f"✏️  Editar Usuario #{uid}",
                    defaults={"Nombre completo": u["nombre"], "Nombre de usuario": u["usuario"], "Rol": u["rol"]},
                    on_guardar=on_guardar)
            except ValueError as e:
                lbl.configure(text=str(e))
        ctk.CTkButton(v, text="Continuar", width=290, height=36, corner_radius=8,
                      fg_color=C_ACCENT, hover_color="#0d9668", font=FONT_BODY,
                      command=abrir).pack(pady=8)

    def _eliminar_usuario_ui(self):
        v = self._popup("🗑  Eliminar Usuario", 380, 220)
        e_id = ctk.CTkEntry(v, width=310, height=34, corner_radius=8,
                            fg_color=C_CARD, border_color=C_BORDER, font=FONT_BODY)
        e_id.pack(pady=(0, 4))
        ctk.CTkLabel(v, text="No puedes eliminar tu propia cuenta.",
                     font=("Trebuchet MS", 10), text_color=C_MUTED).pack()
        lbl_err = ctk.CTkLabel(v, text="", text_color=C_RED, font=FONT_SMALL)
        lbl_err.pack(pady=4)
        def eliminar():
            try:
                uid = int(e_id.get())
                if uid == Sesion.obtener().usuario_id:
                    lbl_err.configure(text="No puedes eliminar tu propia cuenta."); return
                eliminar_usuario(uid)
                v.destroy(); self._cargar_usuarios_tabla()
            except Exception as e:
                lbl_err.configure(text=f"Error: {e}")
        ctk.CTkButton(v, text="Eliminar", width=310, height=36, corner_radius=8,
                      fg_color=C_RED, hover_color="#b91c1c", font=FONT_BODY,
                      command=eliminar).pack(pady=8)

    # ── MÉTRICAS ──────────────────────────────────────────────────────────────

    def _actualizar_metricas(self):
        threading.Thread(target=self._actualizar_metricas_bg, daemon=True).start()

    def _actualizar_metricas_bg(self):
        resumen = resumen_negocio()
        self.after(0, lambda: self._pintar_metricas(resumen))

    def _pintar_metricas(self, r):
        self.metricas_labels["Ingresos"].configure(text=f"${r['ingresos']:,.2f}")
        self.metricas_labels["Pedidos"].configure(text=str(r["total_pedidos"]))
        self.metricas_labels["Productos"].configure(text=str(r["productos"]))
        self.metricas_labels["Clientes"].configure(text=str(r["clientes"]))
        self.metricas_labels["Bajo stock"].configure(text=str(r["bajo_stock"]))

        # Alerta visual en pestaña de productos si hay bajo stock
        if hasattr(self, "banner_stock_prod"):
            if r["bajo_stock"] > 0:
                self.lbl_banner_stock.configure(
                    text=f"⚠️  Atención: Hay {r['bajo_stock']} producto(s) con stock crítico (< 5 unidades)."
                )
                self.banner_stock_prod.pack(fill="x", pady=(0, 6), before=self.prod_lbl_cargando)
            else:
                self.banner_stock_prod.pack_forget()

    # ── EXPORTACIÓN CSV ───────────────────────────────────────────────────────

    def _exportar_productos_csv(self):
        ruta = filedialog.asksaveasfilename(
            parent=self,
            title="Exportar Catálogo de Productos",
            defaultextension=".csv",
            initialfile="productos_maxlimp.csv",
            filetypes=[("Archivos CSV", "*.csv"), ("Todos los archivos", "*.*")]
        )
        if not ruta:
            return

        def _bg():
            try:
                productos = listar_productos(solo_activos=False)
                with open(ruta, "w", newline="", encoding="utf-8-sig") as f:
                    writer = csv.writer(f)
                    writer.writerow(["ID", "Nombre", "Categoría", "Descripción", "Precio", "Stock", "Activo"])
                    for p in productos:
                        writer.writerow([
                            p["id"],
                            p["nombre"],
                            p["categoria"],
                            p["descripcion"],
                            f"{p['precio']:.2f}",
                            p["stock"],
                            "Sí" if p["activo"] else "No",
                        ])
                self.after(0, lambda: messagebox.showinfo(
                    "Exportación Exitosa", f"Se exportaron {len(productos)} productos a:\n{ruta}"
                ))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror(
                    "Error de Exportación", f"No se pudo exportar el catálogo: {e}"
                ))

        threading.Thread(target=_bg, daemon=True).start()

    def _exportar_pedidos_csv(self):
        ruta = filedialog.asksaveasfilename(
            parent=self,
            title="Exportar Historial de Pedidos",
            defaultextension=".csv",
            initialfile="pedidos_maxlimp.csv",
            filetypes=[("Archivos CSV", "*.csv"), ("Todos los archivos", "*.*")]
        )
        if not ruta:
            return

        filtro = self.ped_entry_cliente.get().strip() or None
        estado = self.ped_estado_var.get()
        estado = None if estado == "Todos" else estado

        def _bg():
            try:
                pedidos = listar_pedidos(filtro_cliente=filtro, estado=estado)
                with open(ruta, "w", newline="", encoding="utf-8-sig") as f:
                    writer = csv.writer(f)
                    writer.writerow(["# Pedido", "Cliente", "Teléfono", "Total ($)", "Estado", "Fecha", "Cant. Ítems"])
                    for h in pedidos:
                        writer.writerow([
                            h["id"],
                            h["cliente_nombre"],
                            h["cliente_telefono"] or "",
                            f"{h['total']:.2f}",
                            h["estado"],
                            h["fecha"],
                            h.get("items", 0),
                        ])
                self.after(0, lambda: messagebox.showinfo(
                    "Exportación Exitosa", f"Se exportaron {len(pedidos)} pedidos a:\n{ruta}"
                ))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror(
                    "Error de Exportación", f"No se pudo exportar los pedidos: {e}"
                ))

        threading.Thread(target=_bg, daemon=True).start()

    def _programar_refresh(self):
        self.after(REFRESH_MS, self._refresh_periodico)

    def _refresh_periodico(self):
        self._actualizar_metricas()
        self._programar_refresh()

    # ── SESIÓN ────────────────────────────────────────────────────────────────

    def _cerrar_sesion(self):
        Sesion.cerrar()
        self.destroy()
        from login import LoginApp
        LoginApp().mainloop()


if __name__ == '__main__':
    VentanaAdmin().mainloop()
