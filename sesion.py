# este archivo guarda quién está logueado en este momento
# usamos el patrón Singleton para que solo exista una sesión activa a la vez

class Sesion:
    _instancia = None

    def __init__(self, usuario_id: int, nombre: str, rol: str):
        self.usuario_id = usuario_id
        self.nombre = nombre
        self.rol = rol  # 'admin' o 'vendedor'

    @classmethod
    def crear(cls, usuario_id, nombre, rol):
        cls._instancia = cls(usuario_id, nombre, rol)
        return cls._instancia

    @classmethod
    def obtener(cls):
        return cls._instancia

    def es_admin(self) -> bool:
        return self.rol == 'admin'

    @classmethod
    def cerrar(cls):
        cls._instancia = None
