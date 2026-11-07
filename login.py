import os
import threading

import customtkinter as ctk
from PIL import Image

from sesion import Sesion
from base_de_datos.connection import inicializar_bd
from base_de_datos.queries import autenticar_usuario

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("green")

ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
LOGO_FULL_PATH = os.path.join(ASSETS_DIR, "logo_full.png")


class LoginApp(ctk.CTk):

    def __init__(self):
        super().__init__()
        # main.py lee este atributo para decidir qué ventana abrir después.
        self.siguiente_rol = None
        self._db_listo = False
        self._db_ok = False

        self.title("MAX LIMP - Iniciar Sesión")
        self.geometry('450x600')
        self.resizable(False, False)
        self._construir_interfaz()

        # La conexión a Railway tarda: se hace en segundo plano para que la
        # ventana aparezca de inmediato (antes la app se congelaba al arrancar).
        self.after(50, self._preparar_bd)

    # ── INTERFAZ ──────────────────────────────────────────────────────────────

    def _construir_interfaz(self):
        if os.path.exists(LOGO_FULL_PATH):
            logo_pil = Image.open(LOGO_FULL_PATH)
            ancho = 260
            alto = int(logo_pil.height * (ancho / logo_pil.width))
            self._logo_img = ctk.CTkImage(logo_pil, size=(ancho, alto))
            ctk.CTkLabel(self, image=self._logo_img, text="").pack(pady=(30, 5))
        else:
            ctk.CTkLabel(self, text="MAX LIMP", font=("Arial", 32, "bold")).pack(pady=(40, 5))

        ctk.CTkLabel(self, text="Panel de Inventario y Pedidos", font=("Arial", 14)).pack(pady=(0, 20))

        ctk.CTkLabel(self, text="Usuario:", anchor="w").pack(fill="x", padx=60)
        self.entry_usuario = ctk.CTkEntry(self, placeholder_text="Ingresa tu usuario", width=330)
        self.entry_usuario.pack(pady=(0, 12))
        self.entry_usuario.bind("<Return>", lambda e: self.entry_pass.focus_set())

        ctk.CTkLabel(self, text="Contraseña:", anchor="w").pack(fill="x", padx=60)
        self.entry_pass = ctk.CTkEntry(self, placeholder_text="Ingresa tu contraseña",
                                       show="*", width=330)
        self.entry_pass.pack(pady=(0, 8))
        self.entry_pass.bind("<Return>", lambda e: self._autenticar())

        self.lbl_error = ctk.CTkLabel(self, text="", text_color="red", font=("Arial", 11),
                                      wraplength=330)
        self.lbl_error.pack(pady=4)

        self.btn_ingresar = ctk.CTkButton(self, text="Ingresar", width=330,
                                          command=self._autenticar, state="disabled")
        self.btn_ingresar.pack(pady=(6, 0))

        self.lbl_estado = ctk.CTkLabel(self, text="⏳ Conectando a la base de datos...",
                                       font=("Arial", 10), text_color="gray", wraplength=330)
        self.lbl_estado.pack(pady=(12, 0))

        # credenciales de demo visibles para facilitar pruebas
        ctk.CTkLabel(self, text="Demo → admin / admin123  |  vendedor / vendedor123",
                     font=("Arial", 10), text_color="gray").pack(pady=(10, 0))

    # ── BASE DE DATOS ─────────────────────────────────────────────────────────

    def _preparar_bd(self):
        threading.Thread(target=self._preparar_bd_bg, daemon=True).start()

    def _preparar_bd_bg(self):
        try:
            ok = inicializar_bd()
            error = None
        except Exception as e:
            ok = False
            error = str(e)
        try:
            self.after(0, lambda: self._bd_resultado(ok, error))
        except Exception:
            pass  # la ventana ya se cerró

    def _bd_resultado(self, ok: bool, error: str = None):
        self._db_listo = True
        self._db_ok = ok
        self.btn_ingresar.configure(state="normal")
        if ok:
            self.lbl_estado.configure(text="✅ Conectado a la base de datos",
                                      text_color="#10b981")
        else:
            detalle = f"\n{error}" if error else ""
            self.lbl_estado.configure(
                text="⚠ Sin conexión a la base de datos. Revisa el .env y que el "
                     "servicio MySQL esté activo." + detalle,
                text_color="#ef4444")

    # ── AUTENTICACIÓN ─────────────────────────────────────────────────────────

    def _autenticar(self):
        if not self._db_listo:
            self.lbl_error.configure(text="Espera, conectando a la base de datos...")
            return
        if not self._db_ok:
            self.lbl_error.configure(
                text="Sin conexión a la base de datos. No se puede iniciar sesión.")
            return

        usuario = self.entry_usuario.get().strip()
        contrasena = self.entry_pass.get()

        if not usuario or not contrasena:
            self.lbl_error.configure(text="Completa todos los campos.")
            return

        try:
            resultado = autenticar_usuario(usuario, contrasena)
        except ConnectionError:
            self._db_ok = False
            self.lbl_error.configure(
                text="Se perdió la conexión con la base de datos. Intenta de nuevo.")
            return
        except Exception as e:
            self.lbl_error.configure(text=f"Error inesperado: {e}")
            return

        if resultado:
            Sesion.crear(resultado["id"], resultado["nombre"], resultado["rol"])
            self.siguiente_rol = resultado["rol"]
            # main.py se encarga de destruir esta ventana y abrir el panel.
            self.quit()
        else:
            self.entry_pass.delete(0, "end")
            self.lbl_error.configure(text="Usuario o contraseña incorrectos.")


if __name__ == '__main__':
    LoginApp().mainloop()
