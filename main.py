"""
main.py — Punto de entrada principal de MAX LIMP (panel de inventario y pedidos)
Ejecutar con:  python main.py
"""
import sys
import os

# aseguramos que los imports relativos funcionen desde cualquier directorio
sys.path.insert(0, os.path.dirname(__file__))

from login import LoginApp

if __name__ == "__main__":
    app = LoginApp()
    app.mainloop()
