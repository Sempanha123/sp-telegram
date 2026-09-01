from __future__ import annotations

import base64
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

private=Ed25519PrivateKey.generate()
private_raw=private.private_bytes(serialization.Encoding.Raw,serialization.PrivateFormat.Raw,serialization.NoEncryption())
public_raw=private.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)
print("SERVER LICENSE_SIGNING_PRIVATE_KEY_B64="+base64.b64encode(private_raw).decode())
print("DESKTOP SP_LICENSE_PUBLIC_KEY_B64="+base64.b64encode(public_raw).decode())
print("Store the private value only in the license server secret environment. Never commit it to the desktop repository.")
