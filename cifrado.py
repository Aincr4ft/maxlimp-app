import hashlib
import hmac
import os
import secrets

ITERACIONES = 100_000


def cifrar_contrasena(password: str) -> str:
    """
    Genera un hash seguro usando PBKDF2-HMAC-SHA256 con un salt aleatorio único.
    Formato: pbkdf2:sha256:<iteraciones>:<salt_hex>:<hash_hex>
    """
    salt = secrets.token_bytes(16)
    hash_bytes = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, ITERACIONES)
    return f"pbkdf2:sha256:{ITERACIONES}:{salt.hex()}:{hash_bytes.hex()}"


def verificar_contrasena(password_ingresado: str, hash_guardado: str) -> bool:
    """
    Verifica una contraseña contra el hash almacenado.
    Soporta hashes PBKDF2 modernos y hashes legacy SHA-256 planos para compatibilidad.
    """
    if not hash_guardado or not password_ingresado:
        return False

    if hash_guardado.startswith("pbkdf2:sha256:"):
        partes = hash_guardado.split(":")
        if len(partes) != 5:
            return False
        _, _, iters_str, salt_hex, hash_hex = partes
        try:
            salt = bytes.fromhex(salt_hex)
            iters = int(iters_str)
            calc_hash = hashlib.pbkdf2_hmac("sha256", password_ingresado.encode("utf-8"), salt, iters)
            return hmac.compare_digest(calc_hash.hex(), hash_hex)
        except (ValueError, TypeError):
            return False

    # Compatibilidad con hashes antiguos SHA-256 plano (64 caracteres)
    legacy_hash = hashlib.sha256(password_ingresado.encode("utf-8")).hexdigest()
    return hmac.compare_digest(legacy_hash, hash_guardado)


def es_hash_legacy(hash_guardado: str) -> bool:
    """Indica si el hash almacenado usa el formato antiguo y necesita actualizarse."""
    return not (hash_guardado and hash_guardado.startswith("pbkdf2:"))

