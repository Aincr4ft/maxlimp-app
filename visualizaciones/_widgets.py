"""
_widgets.py — Helpers de UI compartidos entre las vistas.
Expone mostrar_detalle_pedido, que abre un modal con la cabecera del
pedido y la lista de ítems (producto, precio unitario, cantidad, subtotal),
así como la opción de previsualizar y exportar un ticket de compra.
"""
from tkinter import filedialog
import customtkinter as ctk
from base_de_datos.queries import obtener_detalle_pedido


def generar_texto_ticket(detalle: dict) -> str:
    """Genera una representación en texto plano formateada estilo recibo/ticket."""
    lineas = [
        "========================================",
        "               MAX LIMP",
        "     Productos de Limpieza y Hogar",
        "========================================",
        f"Pedido #: {detalle['id']}",
        f"Fecha:   {detalle['fecha']}",
        f"Estado:  {detalle['estado'].upper()}",
        f"Cliente: {detalle['cliente_nombre']}",
    ]
    if detalle.get("cliente_telefono"):
        lineas.append(f"Tel:     {detalle['cliente_telefono']}")
    lineas.extend([
        "----------------------------------------",
        f"{'CANT':<5} {'PRODUCTO':<23} {'SUBTOTAL':>10}",
        "----------------------------------------",
    ])
    for item in detalle.get("items", []):
        nombre = item["producto_nombre"]
        if len(nombre) > 22:
            nombre = nombre[:20] + ".."
        cant_str = f"{item['cantidad']}x"
        sub_str = f"${item['subtotal']:.2f}"
        lineas.append(f"{cant_str:<5} {nombre:<23} {sub_str:>10}")
    total_str = f"${detalle['total']:.2f}"
    lineas.extend([
        "----------------------------------------",
        f"{'TOTAL A PAGAR:':<28} {total_str:>10}",
        "========================================",
        "      ¡Gracias por su preferencia!",
        "========================================",
    ])
    return "\n".join(lineas)


def abrir_ventana_ticket(parent, detalle: dict) -> None:
    """Abre ventana con vista previa del ticket monospaciado y opciones de guardado/copiado."""
    t_win = ctk.CTkToplevel(parent)
    t_win.title(f"Ticket - Pedido #{detalle['id']}")
    t_win.geometry("450x520")
    t_win.grab_set()

    ctk.CTkLabel(t_win, text=f"🧾  Ticket de Venta — Pedido #{detalle['id']}",
                 font=("Trebuchet MS", 14, "bold")).pack(pady=(14, 8))

    texto_ticket = generar_texto_ticket(detalle)

    tb = ctk.CTkTextbox(t_win, font=("Courier New", 12), width=390, height=360)
    tb.pack(padx=20, pady=(0, 10))
    tb.insert("1.0", texto_ticket)
    tb.configure(state="disabled")

    lbl_aviso = ctk.CTkLabel(t_win, text="", font=("Trebuchet MS", 11), text_color="#10b981")
    lbl_aviso.pack(pady=(0, 6))

    btn_frame = ctk.CTkFrame(t_win, fg_color="transparent")
    btn_frame.pack(fill="x", padx=20, pady=(0, 12))

    def guardar_txt():
        ruta = filedialog.asksaveasfilename(
            parent=t_win,
            title="Guardar Ticket",
            defaultextension=".txt",
            initialfile=f"ticket_pedido_{detalle['id']}.txt",
            filetypes=[("Archivos de texto", "*.txt"), ("Todos los archivos", "*.*")]
        )
        if ruta:
            try:
                with open(ruta, "w", encoding="utf-8") as f:
                    f.write(texto_ticket)
                lbl_aviso.configure(text="✅ Ticket guardado exitosamente.")
            except Exception as e:
                lbl_aviso.configure(text=f"❌ Error al guardar: {e}", text_color="#ef4444")

    def copiar_clipboard():
        t_win.clipboard_clear()
        t_win.clipboard_append(texto_ticket)
        lbl_aviso.configure(text="📋 ¡Ticket copiado al portapapeles!")

    ctk.CTkButton(btn_frame, text="💾 Guardar TXT", width=120, height=32,
                  fg_color="#10b981", hover_color="#0d9668",
                  command=guardar_txt).pack(side="left", padx=4)
    ctk.CTkButton(btn_frame, text="📋 Copiar", width=110, height=32,
                  fg_color="#3b82f6", hover_color="#2563eb",
                  command=copiar_clipboard).pack(side="left", padx=4)
    ctk.CTkButton(btn_frame, text="Cerrar", width=90, height=32,
                  fg_color="#374151", hover_color="#4b5563",
                  command=t_win.destroy).pack(side="right", padx=4)


def mostrar_detalle_pedido(parent, pedido_id: int) -> None:
    """Abre un CTkToplevel con el detalle del pedido. Si no existe, muestra error."""
    detalle = obtener_detalle_pedido(pedido_id)
    if not detalle:
        v = ctk.CTkToplevel(parent)
        v.title("Error")
        v.geometry("320x120")
        v.grab_set()
        ctk.CTkLabel(v, text=f"No se encontró el pedido #{pedido_id}.",
                     text_color="#e74c3c", font=("Arial", 12)).pack(expand=True, padx=20, pady=20)
        return

    v = ctk.CTkToplevel(parent)
    v.title(f"Detalle Pedido #{detalle['id']}")
    v.geometry("640x480")
    v.grab_set()

    # Cabecera
    header = ctk.CTkFrame(v, fg_color="#0f3d2e", corner_radius=0)
    header.pack(fill="x")
    telefono = f" · {detalle['cliente_telefono']}" if detalle.get("cliente_telefono") else ""
    ctk.CTkLabel(
        header,
        text=f"🧾  Pedido #{detalle['id']}  —  {detalle['cliente_nombre']}{telefono}",
        font=("Arial", 14, "bold"), text_color="white",
    ).pack(side="left", padx=15, pady=10)
    ctk.CTkLabel(
        header,
        text=f"{detalle['fecha']}  •  {detalle['estado']}",
        font=("Arial", 11), text_color="#a8e6c1",
    ).pack(side="right", padx=15)

    # Tabla de ítems
    frame = ctk.CTkScrollableFrame(v, fg_color="transparent")
    frame.pack(fill="both", expand=True, padx=15, pady=12)

    cols = {"Producto": 260, "Precio unit.": 110, "Cant.": 60, "Subtotal": 110}
    for col_i, (enc, ancho) in enumerate(cols.items()):
        ctk.CTkLabel(
            frame, text=enc, font=("Arial", 12, "bold"),
            width=ancho, anchor="w", text_color="#a8e6c1",
        ).grid(row=0, column=col_i, padx=5, pady=6)

    if not detalle["items"]:
        ctk.CTkLabel(frame, text="Este pedido no tiene ítems.",
                     text_color="gray").grid(row=1, column=0, columnspan=4, pady=20)
    else:
        for i, item in enumerate(detalle["items"], start=1):
            color = "#16241e" if i % 2 == 0 else "transparent"
            ctk.CTkLabel(
                frame, text=item["producto_nombre"], width=cols["Producto"],
                anchor="w", fg_color=color, wraplength=250,
            ).grid(row=i, column=0, padx=5, pady=3)
            ctk.CTkLabel(
                frame, text=f"${item['precio_unitario']:.2f}",
                width=cols["Precio unit."], anchor="w", fg_color=color,
            ).grid(row=i, column=1, padx=5, pady=3)
            ctk.CTkLabel(
                frame, text=str(item["cantidad"]),
                width=cols["Cant."], anchor="w", fg_color=color,
            ).grid(row=i, column=2, padx=5, pady=3)
            ctk.CTkLabel(
                frame, text=f"${item['subtotal']:.2f}",
                width=cols["Subtotal"], anchor="w", fg_color=color,
            ).grid(row=i, column=3, padx=5, pady=3)

    # Pie con total y acciones
    pie = ctk.CTkFrame(v, fg_color="transparent")
    pie.pack(fill="x", padx=15, pady=(0, 8))

    ctk.CTkButton(pie, text="🖨️ Generar Ticket", width=140, height=32,
                  fg_color="#10b981", hover_color="#0d9668",
                  command=lambda: abrir_ventana_ticket(v, detalle)).pack(side="left")

    ctk.CTkLabel(
        pie, text=f"Total: ${detalle['total']:,.2f}",
        font=("Arial", 15, "bold"), text_color="#2ecc71",
    ).pack(side="right")

    ctk.CTkButton(v, text="Cerrar", width=100, command=v.destroy).pack(pady=(0, 10))

