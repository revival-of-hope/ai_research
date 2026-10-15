import secrets

from cryptography.fernet import Fernet


print(f"JWT_SECRET={secrets.token_urlsafe(48)}")
print(f"ENCRYPTION_KEY={Fernet.generate_key().decode()}")
