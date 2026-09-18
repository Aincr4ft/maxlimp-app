import os
import hashlib
import mysql.connector
from mysql.connector.pooling import MySQLConnectionPool
from dotenv import load_dotenv

load_dotenv()

_pool = None


def obtener_pool() -> MySQLConnectionPool:
    """Crea el pool de conexiones una sola vez y lo reutiliza."""
    global _pool
    if _pool is None:
        _pool = MySQLConnectionPool(
            pool_name="maxlimp_pool",
            pool_size=5,
            pool_reset_session=True,
            host=os.getenv("DB_HOST"),
            port=int(os.getenv("DB_PORT", 3306)),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            database=os.getenv("DB_NAME"),
            connection_timeout=10,
        )
    return _pool


def obtener_conexion() -> mysql.connector.MySQLConnection:
    """Devuelve una conexión del pool. Mucho más rápido que abrir una nueva."""
    try:
        return obtener_pool().get_connection()
    except mysql.connector.Error as e:
        print(f"Error al obtener conexión del pool: {e}")
        return None


def inicializar_bd():
    """
    Crea las tablas del esquema de Max Limp si no existen, el trigger de
    descuento automático de stock, e inserta datos iniciales de demo.

    Este esquema es el MISMO que usará el flujo de WhatsApp vía n8n
    (ver documento de contexto del proyecto), por lo que un pedido creado
    desde este panel y un pedido creado desde WhatsApp son indistinguibles
    para la base de datos: ambos pasan por 'pedidos' + 'detalle_pedido' y
    ambos disparan el mismo trigger de stock.
    """
    conn = obtener_conexion()
    if not conn:
        print("No se pudo inicializar la base de datos: sin conexión.")
        return

    cursor = conn.cursor()

    # ── usuarios del panel (staff interno: admin / vendedor) ──────────────
    # Esta tabla es interna del panel administrativo, NO forma parte del
    # esquema compartido con n8n/WhatsApp (los clientes finales están en
    # la tabla 'clientes', más abajo).
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id            INT AUTO_INCREMENT PRIMARY KEY,
            nombre        VARCHAR(255) NOT NULL,
            usuario       VARCHAR(255) NOT NULL UNIQUE,
            password_hash VARCHAR(64)  NOT NULL,
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

    # ── trigger de descuento automático de stock ──────────────────────────
    # Se dispara tanto si el INSERT en detalle_pedido lo hace este panel
    # como si lo hace el workflow de n8n al confirmar un pedido de WhatsApp.
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

    # ── usuarios de demo del panel ─────────────────────────────────────────
    hash_admin = hashlib.sha256("admin123".encode()).hexdigest()
    cursor.execute("""
        INSERT IGNORE INTO usuarios (nombre, usuario, password_hash, rol)
        VALUES ('Administrador', 'admin', %s, 'admin')
    """, (hash_admin,))

    hash_vend = hashlib.sha256("vendedor123".encode()).hexdigest()
    cursor.execute("""
        INSERT IGNORE INTO usuarios (nombre, usuario, password_hash, rol)
        VALUES ('Vendedor Demo', 'vendedor', %s, 'vendedor')
    """, (hash_vend,))

    # ── catálogo de demo (productos de limpieza) ───────────────────────────
    cursor.execute("SELECT COUNT(*) FROM productos")
    count = cursor.fetchone()[0]
    if count == 0:
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
            productos_demo
        )

    conn.commit()
    cursor.close()
    conn.close()
