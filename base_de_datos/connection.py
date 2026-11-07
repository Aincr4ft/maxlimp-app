import os
import sys

import mysql.connector
from mysql.connector.pooling import MySQLConnectionPool
from dotenv import load_dotenv


def _ruta_env() -> str:
    """
    Localiza el archivo .env.

    - En desarrollo: en la raíz del proyecto (un nivel arriba de base_de_datos/).
    - Empaquetado con PyInstaller: junto al .exe, para poder cambiar las
      credenciales sin recompilar (load_dotenv() por sí solo no lo encontraría,
      porque dentro del .exe __file__ apunta a la carpeta temporal _MEIPASS).
    """
    if getattr(sys, "frozen", False):
        return os.path.join(os.path.dirname(sys.executable), ".env")
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"
    )


load_dotenv(_ruta_env())

_pool = None

# Nombre de la base de datos que se crea automáticamente si no existe.
# (No se puede crear desde una conexión ya apuntando a esa base, por eso
# se intenta primero conectar sin 'database' cuando falla la conexión.)
_VARIABLES_OBLIGATORIAS = ("DB_HOST", "DB_USER", "DB_PASSWORD", "DB_NAME")


def _env_int(nombre: str, defecto: int) -> int:
    valor = os.getenv(nombre)
    if valor is None or not valor.strip():
        return defecto
    try:
        return int(valor)
    except ValueError:
        raise ValueError(
            f"La variable {nombre} del .env debe ser un número (valor recibido: {valor!r})."
        )


def _config_bd() -> dict:
    """Lee y valida las credenciales del .env antes de intentar conectar."""
    faltantes = [
        nombre for nombre in _VARIABLES_OBLIGATORIAS
        if not (os.getenv(nombre) or "").strip()
    ]
    if faltantes:
        raise ValueError("Faltan variables en el .env: " + ", ".join(faltantes))
    return {
        "host": os.getenv("DB_HOST").strip(),
        "port": _env_int("DB_PORT", 3306),
        "user": os.getenv("DB_USER").strip(),
        "password": os.getenv("DB_PASSWORD"),
        "database": os.getenv("DB_NAME").strip(),
    }


def obtener_pool():
    """Crea el pool de conexiones una sola vez y lo reutiliza."""
    global _pool
    if _pool is None:
        try:
            _pool = MySQLConnectionPool(
                pool_name="maxlimp_pool",
                pool_size=10,
                pool_reset_session=True,
                autocommit=True,
                connection_timeout=15,
                **_config_bd(),
            )
        except Exception as e:
            print(f"Aviso al inicializar pool de conexiones: {e}")
            _pool = None
    return _pool


def obtener_conexion():
    """
    Devuelve una conexión activa. Intenta primero desde el pool reutilizable;
    si el pool está agotado o no disponible, abre una conexión directa de
    respaldo. Devuelve None si no hay forma de conectar.
    """
    try:
        pool = obtener_pool()
        if pool is not None:
            conn = pool.get_connection()
            if conn and conn.is_connected():
                return conn
    except Exception:
        # Pool saturado (PoolError) o credenciales inválidas: probamos directo.
        pass

    try:
        return mysql.connector.connect(
            connection_timeout=15,
            autocommit=True,
            **_config_bd(),
        )
    except Exception as e:
        print(f"Error de conexión a la base de datos: {e}")
        return None


# ── INICIALIZACIÓN DEL ESQUEMA ─────────────────────────────────────────────────

def inicializar_bd() -> bool:
    """
    Crea las tablas del esquema de Max Limp si no existen, asegura los triggers
    de stock e inserta los datos de demostración la primera vez.

    Este esquema es el MISMO que usará el flujo de WhatsApp vía n8n: un pedido
    creado desde este panel y uno creado desde WhatsApp son indistinguibles
    para la base de datos.

    Devuelve True si la base quedó lista, False si no hubo conexión.
    """
    conn = obtener_conexion()
    if not conn:
        print("No se pudo inicializar la base de datos: sin conexión.")
        return False

    cursor = conn.cursor()
    try:
        _crear_tablas(cursor)
        _asegurar_columna_hash(cursor)
        _asegurar_triggers(cursor)
        _sembrar_usuarios_demo(cursor)
        _sembrar_productos_demo(cursor)
        conn.commit()
        return True
    finally:
        try:
            cursor.close()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass


def _crear_tablas(cursor) -> None:
    # ── usuarios del panel (staff interno: admin / vendedor) ──────────────
    # Esta tabla es interna del panel administrativo, NO forma parte del
    # esquema compartido con n8n/WhatsApp (los clientes finales están en
    # la tabla 'clientes', más abajo).
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id            INT AUTO_INCREMENT PRIMARY KEY,
            nombre        VARCHAR(255) NOT NULL,
            usuario       VARCHAR(255) NOT NULL UNIQUE,
            password_hash VARCHAR(255) NOT NULL,
            rol           VARCHAR(50)  NOT NULL DEFAULT 'vendedor'
        )
    """)

    # ── esquema oficial de Max Limp (idéntico al documento de contexto) ───
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS productos (
            id INT AUTO_INCREMENT PRIMARY KEY,
            nombre VARCHAR(100) NOT NULL,
            categoria VARCHAR(50),
            descripcion VARCHAR(255),
            precio DECIMAL(10,2) NOT NULL,
            stock INT NOT NULL DEFAULT 0,
            imagen_url VARCHAR(255),
            activo BOOLEAN DEFAULT TRUE,
            creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS clientes (
            id INT AUTO_INCREMENT PRIMARY KEY,
            nombre VARCHAR(100),
            telefono VARCHAR(20) UNIQUE NOT NULL,
            direccion VARCHAR(255),
            creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pedidos (
            id INT AUTO_INCREMENT PRIMARY KEY,
            cliente_id INT NOT NULL,
            estado ENUM('pendiente','confirmado','entregado','cancelado') DEFAULT 'pendiente',
            total DECIMAL(10,2) NOT NULL DEFAULT 0,
            creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (cliente_id) REFERENCES clientes(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS detalle_pedido (
            id INT AUTO_INCREMENT PRIMARY KEY,
            pedido_id INT NOT NULL,
            producto_id INT NOT NULL,
            cantidad INT NOT NULL,
            precio_unitario DECIMAL(10,2) NOT NULL,
            FOREIGN KEY (pedido_id) REFERENCES pedidos(id),
            FOREIGN KEY (producto_id) REFERENCES productos(id)
        )
    """)


def _asegurar_columna_hash(cursor) -> None:
    """
    Amplía password_hash a VARCHAR(255) solo si la tabla ya existía con un
    tamaño menor. Antes se lanzaba un ALTER TABLE en cada arranque, lo que
    añadía una consulta DDL innecesaria (y lenta) contra Railway.
    """
    cursor.execute("""
        SELECT CHARACTER_MAXIMUM_LENGTH
        FROM information_schema.columns
        WHERE table_schema = DATABASE()
          AND table_name = 'usuarios'
          AND column_name = 'password_hash'
    """)
    fila = cursor.fetchone()
    if fila and fila[0] is not None and fila[0] < 255:
        cursor.execute(
            "ALTER TABLE usuarios MODIFY COLUMN password_hash VARCHAR(255) NOT NULL"
        )


def _asegurar_triggers(cursor) -> None:
    """
    Crea o actualiza los triggers de stock.

    Se recrean solo si faltan o si todavía tienen la versión anterior (sin
    bloqueo de fila), para no lanzar DDL en cada arranque.
    """
    cursor.execute("""
        SELECT trigger_name, action_statement
        FROM information_schema.triggers
        WHERE trigger_schema = DATABASE()
    """)
    existentes = {
        r[0].lower(): (r[1] or "").lower() for r in cursor.fetchall()
    }

    validar = existentes.get("validar_stock_antes_de_insertar")
    if validar is None or "for update" not in validar:
        _crear_trigger_validar_stock(cursor)

    if "descontar_stock" not in existentes:
        _crear_trigger_descontar_stock(cursor)


def _crear_trigger_validar_stock(cursor) -> None:
    """
    Valida el stock antes de insertar una línea de pedido.

    Usa SELECT ... FOR UPDATE para bloquear la fila del producto: así dos
    pedidos simultáneos (por ejemplo, el panel y el workflow de n8n) no pueden
    leer el mismo stock y sobrevender.

    Si el servidor MySQL no permite el bloqueo dentro de un trigger, se cae a
    la versión sin bloqueo para no dejar la tabla sin validación.
    """
    cursor.execute("DROP TRIGGER IF EXISTS validar_stock_antes_de_insertar")
    try:
        cursor.execute("""
            CREATE TRIGGER validar_stock_antes_de_insertar
            BEFORE INSERT ON detalle_pedido
            FOR EACH ROW
            BEGIN
                DECLARE stock_disp INT DEFAULT NULL;
                SELECT stock INTO stock_disp
                FROM productos
                WHERE id = NEW.producto_id
                FOR UPDATE;
                IF stock_disp IS NULL OR stock_disp < NEW.cantidad THEN
                    SIGNAL SQLSTATE '45000'
                    SET MESSAGE_TEXT = 'Error: Stock insuficiente para procesar el pedido.';
                END IF;
            END
        """)
    except Exception as e:
        print(
            "Aviso: no se pudo crear el trigger con bloqueo "
            f"({e}). Se usa la versión sin bloqueo."
        )
        cursor.execute("DROP TRIGGER IF EXISTS validar_stock_antes_de_insertar")
        cursor.execute("""
            CREATE TRIGGER validar_stock_antes_de_insertar
            BEFORE INSERT ON detalle_pedido
            FOR EACH ROW
            BEGIN
                DECLARE stock_disp INT DEFAULT 0;
                SELECT stock INTO stock_disp FROM productos WHERE id = NEW.producto_id;
                IF stock_disp < NEW.cantidad THEN
                    SIGNAL SQLSTATE '45000'
                    SET MESSAGE_TEXT = 'Error: Stock insuficiente para procesar el pedido.';
                END IF;
            END
        """)


def _crear_trigger_descontar_stock(cursor) -> None:
    cursor.execute("DROP TRIGGER IF EXISTS descontar_stock")
    cursor.execute("""
        CREATE TRIGGER descontar_stock
        AFTER INSERT ON detalle_pedido
        FOR EACH ROW
        BEGIN
            UPDATE productos
            SET stock = stock - NEW.cantidad
            WHERE id = NEW.producto_id;
        END
    """)


def _sembrar_usuarios_demo(cursor) -> None:
    """
    Crea las cuentas de demostración SOLO si la tabla usuarios está vacía.

    Antes se usaba INSERT IGNORE en cada arranque, lo que resucitaba la cuenta
    admin/admin123 aunque se hubiera borrado desde el panel. Con esta versión,
    borrar la cuenta demo es definitivo.
    """
    cursor.execute("SELECT COUNT(*) FROM usuarios")
    if cursor.fetchone()[0] > 0:
        return

    from cifrado import cifrar_contrasena

    cursor.execute(
        "INSERT INTO usuarios (nombre, usuario, password_hash, rol) VALUES (%s, %s, %s, %s)",
        ("Administrador", "admin", cifrar_contrasena("admin123"), "admin"),
    )
    cursor.execute(
        "INSERT INTO usuarios (nombre, usuario, password_hash, rol) VALUES (%s, %s, %s, %s)",
        ("Vendedor Demo", "vendedor", cifrar_contrasena("vendedor123"), "vendedor"),
    )


def _sembrar_productos_demo(cursor) -> None:
    cursor.execute("SELECT COUNT(*) FROM productos")
    if cursor.fetchone()[0] > 0:
        return

    productos_demo = [
        ("Detergente Líquido 1L",      "Lavandería",    "Detergente concentrado para ropa",           3.50,  60, None),
        ("Cloro 1L",                   "Desinfección",  "Blanqueador y desinfectante multiuso",       1.80,  80, None),
        ("Jabón en Polvo 500g",        "Lavandería",    "Jabón para lavado a mano y máquina",         2.20,  70, None),
        ("Desinfectante Multiusos 1L", "Desinfección",  "Aroma a lavanda, para pisos y superficies",  2.90,  50, None),
        ("Limpiavidrios 500ml",        "Hogar",         "Fórmula sin residuos para vidrios y espejos",2.10,  40, None),
        ("Escoba Plástica",            "Herramientas",  "Cerdas resistentes, mango de 1.2m",          4.00,  25, None),
        ("Trapeador Absorbente",       "Herramientas",  "Microfibra, cabezal reemplazable",           5.50,  20, None),
        ("Guantes de Limpieza (par)",  "Protección",    "Látex, talla única",                         1.50,  90, None),
        ("Ambientador en Spray 360ml", "Hogar",         "Aroma floral de larga duración",             3.20,  35, None),
        ("Esponjas Multiuso (x3)",     "Herramientas",  "Esponja + fibra verde para cocina",          1.20, 100, None),
    ]
    cursor.executemany(
        "INSERT INTO productos (nombre, categoria, descripcion, precio, stock, imagen_url) "
        "VALUES (%s,%s,%s,%s,%s,%s)",
        productos_demo,
    )
