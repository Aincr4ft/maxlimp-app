import os
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
        inicializar_bd()  # crea tablas, trigger y datos iniciales si no existen
        self.title("MAX LIMP - Iniciar Sesión")
        self.geometry('450x560')
        self.resizable(False, False)
        self._construir_interfaz()

    def _construir_interfaz(self):
        if os.path.exists(LOGO_FULL_PATH):
            logo_pil = Image.open(LOGO_FULL_PATH)
            ancho = 260
            alto = int(logo_pil.height * (ancho / logo_pil.width))
            self._logo_img = ctk.CTkImage(logo_pil, size=(ancho, alto))
            ctk.CTkLabel(self, image=self._logo_img, text="").pack(pady=(30, 5))
        else:
            ctk.CTkLabel(self, text="MAX LIMP", font=("Arial", 32, "bold")).pack(pady=(40, 5))

        ctk.CTkLabel(self, text="Panel de Inventario y Pedidos", font=("Arial", 14)).pack(pady=(0, 25))

        ctk.CTkLabel(self, text="Usuario:", anchor="w").pack(fill="x", padx=60)
        self.entry_usuario = ctk.CTkEntry(self, placeholder_text="Ingresa tu usuario", width=330)
        self.entry_usuario.pack(pady=(0, 15))

        ctk.CTkLabel(self, text="Contraseña:", anchor="w").pack(fill="x", padx=60)
        self.entry_pass = ctk.CTkEntry(self, placeholder_text="Ingresa tu contraseña",
                                       show="*", width=330)
        self.entry_pass.pack(pady=(0, 10))

        self.lbl_error = ctk.CTkLabel(self, text="", text_color="red", font=("Arial", 11))
        self.lbl_error.pack(pady=5)

        ctk.CTkButton(self, text="Ingresar", width=330,
                      command=self._autenticar).pack(pady=(10, 0))

        # credenciales de demo visibles para facilitar pruebas
        ctk.CTkLabel(self, text="Demo → admin / admin123  |  vendedor / vendedor123",
                     font=("Arial", 10), text_color="gray").pack(pady=(20, 0))

        self.entry_pass.bind("<Return>", lambda e: self._autenticar())

    def _autenticar(self):
        usuario = self.entry_usuario.get().strip()
        contrasena = self.entry_pass.get()

        if not usuario or not contrasena:
            self.lbl_error.configure(text="Completa todos los campos.")
            return

        resultado = autenticar_usuario(usuario, contrasena)

        if resultado:
            Sesion.crear(resultado["id"], resultado["nombre"], resultado["rol"])
            self.destroy()
            self._abrir_panel(resultado["rol"])
        else:
            self.lbl_error.configure(text="Usuario o contraseña incorrectos.")

    def _abrir_panel(self, rol: str):
        if rol == 'admin':
            from visualizaciones.dashboard import VentanaAdmin
            VentanaAdmin().mainloop()
        else:
            from visualizaciones.pedidos_panel import VentanaVendedor
            VentanaVendedor().mainloop()


if __name__ == '__main__':
    LoginApp().mainloop()
