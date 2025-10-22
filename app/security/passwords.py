from passlib.context import CryptContext


_password_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    return _password_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return _password_context.verify(plain_password, hashed_password)
