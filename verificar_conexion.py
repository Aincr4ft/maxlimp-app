"""
verificar_conexion.py — Diagnóstico de la conexión a la base de datos.

No crea ni modifica nada: solo comprueba que el .env esté completo, que el
servidor MySQL responda y qué tablas/triggers existen. Útil cuando la app
dice "sin conexión" y no sabes si el problema es Railway o el .env.

Uso:  python verificar_conexion.py
"""
import sys

from base_de_datos.connection import obtener_conexion


ESPERADAS = {"usuarios", "productos", "clientes", "pedidos", "detalle_pedido"}


def main() -> int:
    print("Comprobando conexión con la base de datos...")
    conn = obtener_conexion()
    if not conn:
        print("\n[FALLO] No se pudo conectar.")
        print("  1. Revisa que el .env exista y tenga DB_HOST, DB_PORT, DB_USER,")
        print("     DB_PASSWORD y DB_NAME.")
        print("  2. Revisa en Railway que el servicio MySQL esté activo y que el")
        print("     puerto del proxy TCP no haya cambiado.")
        return 1

    cursor = conn.cursor()
    try:
        cursor.execute("SELECT VERSION(), DATABASE(), CURRENT_USER()")
        version, base, usuario = cursor.fetchone()
        print(f"[OK] Conectado a MySQL {version}")
        print(f"     Base de datos : {base}")
        print(f"     Usuario       : {usuario}")

        cursor.execute("SHOW TABLES")
        tablas = [r[0] for r in cursor.fetchall()]
        print(f"\nTablas ({len(tablas)}): {', '.join(tablas) or '(ninguna)'}")

        faltan = ESPERADAS - set(tablas)
        if faltan:
            print(f"  [AVISO] Faltan tablas: {', '.join(sorted(faltan))}")
            print("          Ejecuta la app (python main.py) para crearlas.")

        cursor.execute(
            "SELECT trigger_name FROM information_schema.triggers "
            "WHERE trigger_schema = DATABASE()"
        )
        triggers = [r[0] for r in cursor.fetchall()]
        print(f"Triggers ({len(triggers)}): {', '.join(triggers) or '(ninguno)'}")

        if tablas:
            print("\nFilas por tabla:")
            for tabla in sorted(set(tablas) & ESPERADAS):
                cursor.execute(f"SELECT COUNT(*) FROM {tabla}")
                print(f"  {tabla:<15} {cursor.fetchone()[0]:>6}")

        return 0
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
