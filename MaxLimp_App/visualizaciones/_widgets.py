"""
_widgets.py — Helpers de UI compartidos entre las vistas.
Expone mostrar_detalle_pedido, que abre un modal con la cabecera del
pedido y la lista de ítems (producto, precio unitario, cantidad, subtotal).
Reutilizado por el vendedor (registrar pedido) y el admin (tab de pedidos).
"""
import customtkinter as ctk
from base_de_datos.queries import obtener_detalle_pedido


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
    v.geometry("620x440")
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

    # Pie con total
    pie = ctk.CTkFrame(v, fg_color="transparent")
    pie.pack(fill="x", padx=15, pady=(0, 12))
    ctk.CTkLabel(
        pie, text=f"Total: ${detalle['total']:,.2f}",
        font=("Arial", 15, "bold"), text_color="#2ecc71",
    ).pack(side="right")

    ctk.CTkButton(v, text="Cerrar", width=100, command=v.destroy).pack(pady=(0, 12))
