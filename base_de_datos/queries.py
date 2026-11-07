from collections import deque
from contextlib import contextmanager
from datetime import datetime

from base_de_datos.connection import obtener_conexion
from cifrado import cifrar_contrasena, verificar_contrasena, es_hash_legacy


SIN_CONEXION = "Sin conexión a la base de datos."


@contextmanager
def _conexion():
    """
    Abre una conexión y garantiza que el cursor y la conexión se cierren
    siempre, incluso si la consulta lanza una excepción.

    Lanza ConnectionError cuando no hay base de datos, para que la interfaz
    pueda distinguir "no hay servidor" de "la consulta no devolvió filas".
    Antes las funciones devolvían listas vacías y la UI mostraba "Sin datos",
    ocultando el problema real.
    """
    conn = obtener_conexion()
    if not conn:
        raise ConnectionError(SIN_CONEXION)
    cursor = None
    try:
        cursor = conn.cursor()
        yield cursor, conn
    finally:
        if cursor is not None:
            try:
                cursor.close()
            except Exception:
                pass
        try:
            conn.close()
        except Exception:
            pass


def _parse_fecha(texto: str):
    """Acepta 'dd/mm/aaaa' y devuelve 'aaaa-mm-dd' para SQL, o None si está vacío."""
    if not texto or not texto.strip():
        return None
    try:
        return datetime.strptime(texto.strip(), "%d/%m/%Y").strftime("%Y-%m-%d")
    except ValueError:
        raise ValueError(f"Fecha inválida: '{texto}'. Usa el formato dd/mm/aaaa.")


def _fmt_fecha(f) -> str:
    """Formatea un datetime de MySQL a string legible."""
    if f is None:
        return ""
    if hasattr(f, "strftime"):
        return f.strftime("%d/%m/%Y %H:%M")
    return str(f)


def _contar_admins(cursor) -> int:
    cursor.execute("SELECT COUNT(*) FROM usuarios WHERE rol = 'admin'")
    return cursor.fetchone()[0]


def _existe(cursor, tabla: str, id_: int) -> bool:
    """
    Comprueba si una fila existe. Se usa tras un UPDATE para no confundir
    "no se encontró la fila" con "la fila ya tenía esos valores": MySQL
    devuelve rowcount=0 en ambos casos, y antes eso provocaba errores falsos.
    """
    cursor.execute(f"SELECT 1 FROM {tabla} WHERE id=%s", (id_,))
    return cursor.fetchone() is not None


# ── USUARIOS DEL PANEL (staff interno) ─────────────────────────────────────────

def autenticar_usuario(usuario: str, password_plano: str):
    """
    Verifica las credenciales del usuario.
    Si el hash almacenado es legacy (SHA-256 plano), lo migra automáticamente
    a PBKDF2 con salt en la base de datos tras verificar que es correcto.
    """
    with _conexion() as (cursor, conn):
        cursor.execute(
            "SELECT id, nombre, rol, password_hash FROM usuarios WHERE usuario=%s",
            (usuario,)
        )
        fila = cursor.fetchone()
        if not fila:
            return None

        user_id, nombre, rol, hash_guardado = fila
        if not verificar_contrasena(password_plano, hash_guardado):
            return None

        # Si es hash legacy, actualizamos silenciosamente a PBKDF2 con salt
        if es_hash_legacy(hash_guardado):
            try:
                nuevo_hash = cifrar_contrasena(password_plano)
                cursor.execute(
                    "UPDATE usuarios SET password_hash=%s WHERE id=%s",
                    (nuevo_hash, user_id)
                )
                conn.commit()
            except Exception:
                pass  # no interrumpir el login si la migración del hash falla

        return {"id": user_id, "nombre": nombre, "rol": rol}


def listar_usuarios() -> deque:
    with _conexion() as (cursor, _conn):
        cursor.execute("SELECT id, nombre, usuario, rol FROM usuarios ORDER BY nombre")
        return deque(
            {"id": r[0], "nombre": r[1], "usuario": r[2], "rol": r[3]}
            for r in cursor.fetchall()
        )


def crear_usuario(nombre: str, usuario: str, contrasena: str, rol: str = "vendedor"):
    if not nombre.strip() or not usuario.strip() or not contrasena:
        raise ValueError("Todos los campos son obligatorios.")
    hash_pass = cifrar_contrasena(contrasena)
    try:
        with _conexion() as (cursor, conn):
            cursor.execute(
                "INSERT INTO usuarios (nombre, usuario, password_hash, rol) VALUES (%s, %s, %s, %s)",
                (nombre.strip(), usuario.strip(), hash_pass, rol)
            )
            conn.commit()
    except ConnectionError:
        raise
    except Exception as e:
        raise ValueError(f"No se pudo crear el usuario: {e}")


def editar_usuario(usuario_id: int, nombre: str, usuario: str, rol: str, contrasena: str = None):
    if not nombre.strip() or not usuario.strip():
        raise ValueError("Nombre y usuario son obligatorios.")
    try:
        with _conexion() as (cursor, conn):
            cursor.execute("SELECT rol FROM usuarios WHERE id=%s", (usuario_id,))
            fila = cursor.fetchone()
            if not fila:
                raise ValueError(f"No se encontró usuario con ID {usuario_id}.")

            if fila[0] == "admin" and rol != "admin" and _contar_admins(cursor) <= 1:
                raise ValueError("No puedes quitar el rol de admin al último administrador.")

            if contrasena:
                hash_pass = cifrar_contrasena(contrasena)
                cursor.execute(
                    "UPDATE usuarios SET nombre=%s, usuario=%s, rol=%s, password_hash=%s WHERE id=%s",
                    (nombre.strip(), usuario.strip(), rol, hash_pass, usuario_id)
                )
            else:
                cursor.execute(
                    "UPDATE usuarios SET nombre=%s, usuario=%s, rol=%s WHERE id=%s",
                    (nombre.strip(), usuario.strip(), rol, usuario_id)
                )
            conn.commit()
    except (ConnectionError, ValueError):
        raise
    except Exception as e:
        raise ValueError(f"Error al editar usuario: {e}")


def eliminar_usuario(usuario_id: int):
    try:
        with _conexion() as (cursor, conn):
            cursor.execute("SELECT rol FROM usuarios WHERE id=%s", (usuario_id,))
            fila = cursor.fetchone()
            if not fila:
                raise ValueError(f"No se encontró un usuario con ID {usuario_id}.")
            if fila[0] == "admin" and _contar_admins(cursor) <= 1:
                raise ValueError("No puedes eliminar al último administrador.")
            cursor.execute("DELETE FROM usuarios WHERE id = %s", (usuario_id,))
            conn.commit()
    except (ConnectionError, ValueError):
        raise
    except Exception as e:
        raise ValueError(f"Error al eliminar usuario: {e}")


# ── PRODUCTOS ───────────────────────────────────────────────────────────────────

def listar_productos(filtro: str = None, solo_activos: bool = True) -> deque:
    """Retorna deque de dicts. Si hay filtro, busca por nombre o categoría."""
    with _conexion() as (cursor, _conn):
        sql = ("SELECT id, nombre, categoria, descripcion, precio, stock, imagen_url, activo "
               "FROM productos WHERE 1=1")
        params = []
        if solo_activos:
            sql += " AND activo = TRUE"
        if filtro:
            sql += " AND (nombre LIKE %s OR categoria LIKE %s)"
            params += [f"%{filtro}%", f"%{filtro}%"]
        sql += " ORDER BY categoria, nombre"
        cursor.execute(sql, tuple(params))
        return deque(
            {"id": r[0], "nombre": r[1], "categoria": r[2] or "", "descripcion": r[3] or "",
             "precio": float(r[4]), "stock": r[5], "imagen_url": r[6], "activo": bool(r[7])}
            for r in cursor.fetchall()
        )


def insertar_producto(datos: dict):
    if not datos.get("nombre", "").strip():
        raise ValueError("El nombre del producto es obligatorio.")
    if not datos.get("categoria", "").strip():
        raise ValueError("La categoría es obligatoria.")
    if datos.get("precio", -1) < 0:
        raise ValueError("El precio debe ser mayor o igual a 0.")
    if datos.get("stock", -1) < 0:
        raise ValueError("El stock debe ser mayor o igual a 0.")
    with _conexion() as (cursor, conn):
        cursor.execute(
            "INSERT INTO productos (nombre, categoria, descripcion, precio, stock, imagen_url) "
            "VALUES (%s,%s,%s,%s,%s,%s)",
            (datos["nombre"].strip(), datos["categoria"].strip(), datos.get("descripcion", "").strip() or None,
             datos["precio"], datos["stock"], datos.get("imagen_url", "").strip() or None)
        )
        conn.commit()


def actualizar_precio(producto_id: int, nuevo_precio: float):
    if nuevo_precio < 0:
        raise ValueError("El precio no puede ser negativo.")
    with _conexion() as (cursor, conn):
        cursor.execute("UPDATE productos SET precio=%s WHERE id=%s", (nuevo_precio, producto_id))
        if cursor.rowcount == 0 and not _existe(cursor, "productos", producto_id):
            raise ValueError(f"No se encontró producto con ID {producto_id}.")
        conn.commit()


def actualizar_stock(producto_id: int, nuevo_stock: int):
    """Reposición manual de stock: fija el stock total (no suma)."""
    if nuevo_stock < 0:
        raise ValueError("El stock no puede ser negativo.")
    with _conexion() as (cursor, conn):
        cursor.execute("UPDATE productos SET stock=%s WHERE id=%s", (nuevo_stock, producto_id))
        if cursor.rowcount == 0 and not _existe(cursor, "productos", producto_id):
            raise ValueError(f"No se encontró producto con ID {producto_id}.")
        conn.commit()


def eliminar_producto(producto_id: int):
    """
    Baja lógica (activo = FALSE) en vez de DELETE: un producto ya vendido
    tiene filas en detalle_pedido y borrarlo rompería ese historial.
    El catálogo de WhatsApp solo debe listar productos con activo = TRUE.
    """
    with _conexion() as (cursor, conn):
        cursor.execute("UPDATE productos SET activo = FALSE WHERE id=%s", (producto_id,))
        if cursor.rowcount == 0 and not _existe(cursor, "productos", producto_id):
            raise ValueError(f"No se encontró producto con ID {producto_id}.")
        conn.commit()


def reactivar_producto(producto_id: int):
    with _conexion() as (cursor, conn):
        cursor.execute("UPDATE productos SET activo = TRUE WHERE id=%s", (producto_id,))
        if cursor.rowcount == 0 and not _existe(cursor, "productos", producto_id):
            raise ValueError(f"No se encontró producto con ID {producto_id}.")
        conn.commit()


# ── CLIENTES ────────────────────────────────────────────────────────────────────

def buscar_cliente_por_telefono(telefono: str):
    with _conexion() as (cursor, _conn):
        cursor.execute(
            "SELECT id, nombre, telefono, direccion FROM clientes WHERE telefono=%s",
            (telefono.strip(),)
        )
        fila = cursor.fetchone()
        if fila:
            return {"id": fila[0], "nombre": fila[1], "telefono": fila[2], "direccion": fila[3]}
        return None


def crear_o_actualizar_cliente(nombre: str, telefono: str, direccion: str = None) -> dict:
    """
    Upsert por teléfono (igual que hará n8n cuando escriba un cliente nuevo
    desde WhatsApp): si el teléfono ya existe, actualiza solo los campos que
    llegan con valor. Antes se guardaba NULL cuando el vendedor dejaba el
    nombre o la dirección en blanco, borrando los datos que ya existían.
    """
    telefono = telefono.strip()
    if not telefono:
        raise ValueError("El teléfono es obligatorio.")
    nombre = (nombre or "").strip()
    direccion = (direccion or "").strip()

    with _conexion() as (cursor, conn):
        cursor.execute("SELECT id FROM clientes WHERE telefono=%s", (telefono,))
        fila = cursor.fetchone()
        if fila:
            cliente_id = fila[0]
            cursor.execute(
                "UPDATE clientes SET nombre = COALESCE(NULLIF(%s, ''), nombre), "
                "direccion = COALESCE(NULLIF(%s, ''), direccion) WHERE id=%s",
                (nombre, direccion, cliente_id)
            )
        else:
            cursor.execute(
                "INSERT INTO clientes (nombre, telefono, direccion) VALUES (%s,%s,%s)",
                (nombre or None, telefono, direccion or None)
            )
            cliente_id = cursor.lastrowid
        conn.commit()

        cursor.execute(
            "SELECT id, nombre, telefono, direccion FROM clientes WHERE id=%s",
            (cliente_id,)
        )
        r = cursor.fetchone()
        return {"id": r[0], "nombre": r[1], "telefono": r[2], "direccion": r[3]}


def listar_clientes(filtro: str = None) -> list:
    with _conexion() as (cursor, _conn):
        if filtro:
            cursor.execute(
                "SELECT id, nombre, telefono, direccion FROM clientes "
                "WHERE nombre LIKE %s OR telefono LIKE %s ORDER BY nombre",
                (f"%{filtro}%", f"%{filtro}%")
            )
        else:
            cursor.execute("SELECT id, nombre, telefono, direccion FROM clientes ORDER BY nombre")
        return [
            {"id": r[0], "nombre": r[1] or "(sin nombre)", "telefono": r[2], "direccion": r[3] or ""}
            for r in cursor.fetchall()
        ]


# ── PEDIDOS ─────────────────────────────────────────────────────────────────────

def crear_pedido(cliente_id: int, items_carrito: dict) -> dict:
    """
    Crea un pedido con su detalle. El stock se descuenta automáticamente
    por el trigger 'descontar_stock' al insertar en detalle_pedido (mismo
    trigger que usará el flujo de WhatsApp/n8n).

    items_carrito: {producto_id: {"nombre", "precio", "cantidad"}, ...}
    Retorna {"pedido_id", "total", "items_ok": [nombres...]}.
    """
    if not items_carrito:
        raise ValueError("El carrito está vacío.")

    with _conexion() as (cursor, conn):
        try:
            conn.start_transaction()

            total = 0.0
            items_ok = []
            detalles = []

            for pid, item in items_carrito.items():
                cantidad = int(item["cantidad"])
                if cantidad <= 0:
                    raise ValueError("La cantidad debe ser mayor a cero.")

                # bloquea la fila para evitar sobreventa si hay otro pedido concurrente
                cursor.execute(
                    "SELECT nombre, precio, stock, activo FROM productos WHERE id=%s FOR UPDATE",
                    (pid,)
                )
                fila = cursor.fetchone()
                if not fila:
                    raise ValueError(f"Producto con id {pid} no encontrado.")
                nombre_bd, precio_bd, stock_bd, activo_bd = fila
                if not activo_bd:
                    raise ValueError(
                        f'El producto "{nombre_bd}" está dado de baja y no se puede vender.'
                    )
                if stock_bd < cantidad:
                    raise ValueError(
                        f'Stock insuficiente para "{nombre_bd}". Disponible: {stock_bd}.'
                    )

                precio_unit = round(float(precio_bd), 2)
                subtotal = round(precio_unit * cantidad, 2)
                total += subtotal

                detalles.append((pid, cantidad, precio_unit))
                items_ok.append(nombre_bd)

            total = round(total, 2)

            cursor.execute(
                "INSERT INTO pedidos (cliente_id, estado, total) VALUES (%s, 'pendiente', %s)",
                (cliente_id, total),
            )
            pedido_id = cursor.lastrowid

            cursor.executemany(
                "INSERT INTO detalle_pedido (pedido_id, producto_id, cantidad, precio_unitario) "
                "VALUES (%s, %s, %s, %s)",
                [(pedido_id, pid, cant, pu) for pid, cant, pu in detalles],
            )
            # ↑ cada INSERT dispara el trigger descontar_stock

            conn.commit()
            return {"pedido_id": pedido_id, "total": total, "items_ok": items_ok}
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            raise


def cambiar_estado_pedido(pedido_id: int, nuevo_estado: str) -> None:
    """nuevo_estado en: pendiente, confirmado, entregado, cancelado."""
    if nuevo_estado not in ("pendiente", "confirmado", "entregado", "cancelado"):
        raise ValueError("Estado inválido.")
    with _conexion() as (cursor, conn):
        try:
            conn.start_transaction()

            cursor.execute("SELECT estado FROM pedidos WHERE id=%s", (pedido_id,))
            fila = cursor.fetchone()
            if not fila:
                raise ValueError(f"Pedido #{pedido_id} no encontrado.")
            estado_actual = fila[0]
            if estado_actual == "cancelado":
                raise ValueError(f"El pedido #{pedido_id} ya está cancelado.")

            # Si se cancela, se devuelve el stock reservado
            if nuevo_estado == "cancelado" and estado_actual != "cancelado":
                cursor.execute(
                    "SELECT producto_id, cantidad FROM detalle_pedido WHERE pedido_id=%s", (pedido_id,)
                )
                for pid, cant in cursor.fetchall():
                    cursor.execute(
                        "UPDATE productos SET stock = stock + %s WHERE id = %s", (cant, pid)
                    )

            cursor.execute("UPDATE pedidos SET estado=%s WHERE id=%s", (nuevo_estado, pedido_id))
            conn.commit()
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            raise


def listar_pedidos(
    filtro_cliente: str = None,
    filtro_producto: str = None,
    fecha_desde: str = None,
    fecha_hasta: str = None,
    estado: str = None,
) -> list:
    f_cli = f"%{filtro_cliente.strip()}%" if filtro_cliente and filtro_cliente.strip() else None
    f_prod = f"%{filtro_producto.strip()}%" if filtro_producto and filtro_producto.strip() else None
    f_desde = _parse_fecha(fecha_desde)
    f_hasta = _parse_fecha(fecha_hasta)

    sql = """
        SELECT p.id, p.total, p.estado, p.creado_en,
               COUNT(d.id) AS items,
               c.nombre, c.telefono
        FROM pedidos p
        JOIN clientes c ON c.id = p.cliente_id
        LEFT JOIN detalle_pedido d ON d.pedido_id = p.id
        WHERE 1=1
    """
    params = []

    if f_cli:
        sql += " AND (c.nombre LIKE %s OR c.telefono LIKE %s)"
        params += [f_cli, f_cli]
    if f_prod:
        sql += (" AND p.id IN (SELECT DISTINCT dp.pedido_id FROM detalle_pedido dp "
                 "JOIN productos pr ON pr.id = dp.producto_id WHERE pr.nombre LIKE %s)")
        params.append(f_prod)
    if f_desde:
        sql += " AND DATE(p.creado_en) >= %s"
        params.append(f_desde)
    if f_hasta:
        sql += " AND DATE(p.creado_en) <= %s"
        params.append(f_hasta)
    if estado:
        sql += " AND p.estado = %s"
        params.append(estado)

    sql += " GROUP BY p.id ORDER BY p.creado_en DESC"

    with _conexion() as (cursor, _conn):
        cursor.execute(sql, tuple(params))
        return [
            {"id": r[0], "total": float(r[1]), "estado": r[2],
             "fecha": _fmt_fecha(r[3]), "items": r[4],
             "cliente_nombre": r[5] or "(sin nombre)", "cliente_telefono": r[6]}
            for r in cursor.fetchall()
        ]


def obtener_detalle_pedido(pedido_id: int) -> dict:
    with _conexion() as (cursor, _conn):
        cursor.execute(
            """
            SELECT p.id, p.cliente_id, c.nombre, c.telefono, p.total, p.estado, p.creado_en
            FROM pedidos p
            JOIN clientes c ON c.id = p.cliente_id
            WHERE p.id = %s
            """,
            (pedido_id,),
        )
        cab = cursor.fetchone()
        if not cab:
            return None

        cursor.execute(
            """
            SELECT d.producto_id, pr.nombre, d.precio_unitario, d.cantidad,
                   (d.precio_unitario * d.cantidad) AS subtotal
            FROM detalle_pedido d
            JOIN productos pr ON pr.id = d.producto_id
            WHERE d.pedido_id = %s
            ORDER BY d.id
            """,
            (pedido_id,),
        )
        items = [
            {"producto_id": r[0], "producto_nombre": r[1],
             "precio_unitario": float(r[2]), "cantidad": r[3], "subtotal": float(r[4])}
            for r in cursor.fetchall()
        ]
        return {
            "id": cab[0], "cliente_id": cab[1],
            "cliente_nombre": cab[2] or "(sin nombre)", "cliente_telefono": cab[3],
            "total": float(cab[4]), "estado": cab[5], "fecha": _fmt_fecha(cab[6]),
            "items": items,
        }


# ── MÉTRICAS / DASHBOARD ─────────────────────────────────────────────────────────

def resumen_negocio() -> dict:
    """Métricas para el dashboard del admin."""
    with _conexion() as (cursor, _conn):
        cursor.execute("SELECT COUNT(*), COALESCE(SUM(total), 0) FROM pedidos WHERE estado != 'cancelado'")
        fila = cursor.fetchone()
        total_pedidos = fila[0] or 0
        ingresos = round(float(fila[1] or 0), 2)

        cursor.execute("SELECT COUNT(*) FROM productos WHERE activo = TRUE")
        productos = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM clientes")
        clientes = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM productos WHERE activo = TRUE AND stock < 5")
        bajo_stock = cursor.fetchone()[0]

        ticket_promedio = round(ingresos / total_pedidos, 2) if total_pedidos > 0 else 0.0

        return {
            "total_pedidos": total_pedidos,
            "ingresos": ingresos,
            "productos": productos,
            "clientes": clientes,
            "ticket_promedio": ticket_promedio,
            "bajo_stock": bajo_stock,
        }


def estadisticas_ventas_7_dias() -> list:
    with _conexion() as (cursor, _conn):
        # INTERVAL 6 DAY + hoy = 7 días exactos (antes eran 8).
        sql = """
            SELECT DATE(creado_en) as dia, SUM(total) as total
            FROM pedidos
            WHERE estado != 'cancelado' AND creado_en >= DATE_SUB(CURDATE(), INTERVAL 6 DAY)
            GROUP BY dia
            ORDER BY dia ASC
        """
        cursor.execute(sql)
        return [{"dia": r[0].strftime("%d/%m"), "total": float(r[1])} for r in cursor.fetchall()]


def estadisticas_por_categoria() -> list:
    with _conexion() as (cursor, _conn):
        sql = """
            SELECT p.categoria, SUM(d.precio_unitario * d.cantidad) as total
            FROM detalle_pedido d
            JOIN productos p ON p.id = d.producto_id
            JOIN pedidos pe ON pe.id = d.pedido_id
            WHERE pe.estado != 'cancelado'
            GROUP BY p.categoria
            ORDER BY total DESC
        """
        cursor.execute(sql)
        return [{"categoria": r[0] or "Sin categoría", "total": float(r[1])} for r in cursor.fetchall()]


def productos_mas_vendidos(limit=5) -> list:
    with _conexion() as (cursor, _conn):
        sql = """
            SELECT pr.nombre, SUM(d.cantidad) as total_cant
            FROM detalle_pedido d
            JOIN pedidos pe ON pe.id = d.pedido_id
            JOIN productos pr ON pr.id = d.producto_id
            WHERE pe.estado != 'cancelado'
            GROUP BY d.producto_id, pr.nombre
            ORDER BY total_cant DESC
            LIMIT %s
        """
        cursor.execute(sql, (limit,))
        return [{"nombre": r[0], "cantidad": r[1]} for r in cursor.fetchall()]
