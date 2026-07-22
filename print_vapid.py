from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
import base64
import os

with open("private_key.pem", "rb") as f:
    private_key = serialization.load_pem_private_key(f.read(), password=None)
    
with open("public_key.pem", "rb") as f:
    public_key = serialization.load_pem_public_key(f.read())
    
priv_bytes = private_key.private_numbers().private_value.to_bytes(32, 'big')
priv_b64 = base64.urlsafe_b64encode(priv_bytes).decode('utf-8').rstrip('=')

pub_numbers = public_key.public_numbers()
pub_bytes = b'\x04' + pub_numbers.x.to_bytes(32, 'big') + pub_numbers.y.to_bytes(32, 'big')
pub_b64 = base64.urlsafe_b64encode(pub_bytes).decode('utf-8').rstrip('=')

print("PRIVATE:", priv_b64)
print("PUBLIC:", pub_b64)
