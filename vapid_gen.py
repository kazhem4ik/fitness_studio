import ecdsa
import base64

sk = ecdsa.SigningKey.generate(curve=ecdsa.NIST256p)
vk = sk.get_verifying_key()
private_key = base64.urlsafe_b64encode(sk.to_string()).decode('utf-8').rstrip('=')
public_key = base64.urlsafe_b64encode(b'\x04' + vk.to_string()).decode('utf-8').rstrip('=')
print('PRIVATE:', private_key)
print('PUBLIC:', public_key)
