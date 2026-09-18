import hashlib

# convierte la contraseña a un código irreversible antes de guardarla
def cifrar_contrasena(password: str) -> str:
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

# cuando alguien inicia sesión, ciframos lo que escribió y lo comparamos
def verificar_contrasena(password_ingresado: str, hash_guardado: str) -> bool:
    return cifrar_contrasena(password_ingresado) == hash_guardado
