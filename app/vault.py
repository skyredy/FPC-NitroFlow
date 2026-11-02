import base64
import json
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

class Vault:
    def __init__(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            pass
        else:
            with os.fdopen(descriptor, "wb") as output:
                output.write(AESGCM.generate_key(bit_length=256))
                output.flush()
                os.fsync(output.fileno())
        self.cipher = AESGCM(path.read_bytes())

    def seal(self, value, context):
        nonce = os.urandom(12)
        data = json.dumps(value, ensure_ascii=False).encode()
        return base64.b64encode(nonce + self.cipher.encrypt(nonce, data, context.encode())).decode()

    def open(self, value, context):
        data = base64.b64decode(value, validate=True)
        return json.loads(self.cipher.decrypt(data[:12], data[12:], context.encode()))
