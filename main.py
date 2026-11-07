"""
main.py — Punto de entrada principal de MAX LIMP (panel de inventario y pedidos)
Ejecutar con:  python main.py
"""
import sys
import os

# aseguramos que los imports funcionen desde cualquier directorio
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _destruir(ventana):
    """
    Cierra una ventana sin romper el bucle principal.

    Antes de destruirla se cancelan los callbacks `after` pendientes. Si no se
    hace, Tcl los intenta ejecutar sobre una ventana ya destruida y escribe en
    la consola cosas como `invalid command name "...check_dpi_scaling"`.
    """
    try:
        if not ventana.winfo_exists():
            return
        try:
            pendientes = ventana.tk.call("after", "info")
            if isinstance(pendientes, str):
                pendientes = ventana.tk.splitlist(pendientes)
            for after_id in pendientes:
                try:
                    ventana.after_cancel(after_id)
                except Exception:
                    pass
        except Exception:
            pass
        ventana.destroy()
    except Exception:
        pass


def main():
    """
    Bucle principal de la aplicación.

    Cada ventana corre su propio mainloop de forma SECUENCIAL: cuando una
    termina (login, panel o cierre de sesión), mainloop devuelve el control y
    recién ahí se crea la siguiente. Antes se llamaba a `Ventana().mainloop()`
    desde dentro del callback de otra ventana, lo que anidaba mainloops y
    provocaba `TclError: main thread is not in main loop` al cerrar la app.
    """
    from login import LoginApp

    while True:
        login = LoginApp()
        login.mainloop()
        rol = getattr(login, "siguiente_rol", None)
        _destruir(login)

        if not rol:
            break  # el usuario cerró la ventana de login

        if rol == "admin":
            from visualizaciones.dashboard import VentanaAdmin
            ventana = VentanaAdmin()
        else:
            from visualizaciones.pedidos_panel import VentanaVendedor
            ventana = VentanaVendedor()

        ventana.mainloop()
        cerrar_sesion = getattr(ventana, "cerrar_sesion", False)
        _destruir(ventana)

        if not cerrar_sesion:
            break  # el usuario cerró la ventana del panel


if __name__ == "__main__":
    main()
