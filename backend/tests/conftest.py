import os

from cryptography.fernet import Fernet

os.environ.setdefault("JWT_SECRET", "test-secret-with-enough-entropy-for-hs256")
os.environ.setdefault("ENCRYPTION_KEY", Fernet.generate_key().decode())
os.environ.setdefault("ADMIN_EMAIL", "admin@example.com")
os.environ.setdefault("ADMIN_PASSWORD", "administrator-password")
