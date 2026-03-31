import secrets
from uuid import uuid4

def generate_csrf_token(length=32):
    return str(secrets.token_urlsafe(length))

def generate_uuid_token():
    return str(uuid4())