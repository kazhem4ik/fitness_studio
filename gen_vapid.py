from cryptography.hazmat.primitives.asymmetric.ec import generate_private_key, SECP256R1
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat, PrivateFormat, NoEncryption
import base64

private_key = generate_private_key(SECP256R1())

# Public key: uncompressed point (65 bytes)
pub_bytes = private_key.public_key().public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)
pub_b64 = base64.urlsafe_b64encode(pub_bytes).rstrip(b'=').decode()

# Private key: DER -> extract raw 32-byte scalar (last 32 bytes of the private key number)
priv_num = private_key.private_numbers().private_value
priv_bytes = priv_num.to_bytes(32, 'big')
priv_b64 = base64.urlsafe_b64encode(priv_bytes).rstrip(b'=').decode()

print("PUBLIC:", pub_b64)
print("PRIVATE:", priv_b64)
print()
print("Len public bytes:", len(pub_bytes), "(should be 65)")
print("Len private bytes:", len(priv_bytes), "(should be 32)")
