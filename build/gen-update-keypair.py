#!/usr/bin/env python3
"""
Generate the Ed25519 keypair used to sign auto-update releases.

Run ONCE per project lifetime. After that:
  - The PRIVATE key lives at build/.update-signing-key (gitignored) and
    must also be backed up in 1Password — losing it permanently breaks
    auto-updates for every shipped client.
  - The PUBLIC key is printed to stdout. Paste it into app.py as
    UPDATE_SIGNING_PUBKEY so the running app can verify downloads.

This script refuses to overwrite an existing key file — if you really
need to rotate, delete the file manually first AND understand that every
old client will reject the next update because its baked-in public key
won't match the new signatures.
"""

import base64
import os
import sys

try:
    from nacl.signing import SigningKey
except ImportError:
    sys.stderr.write(
        "PyNaCl is not installed. Run: pip install pynacl\n"
        "(It's now in requirements.txt — `pip install -r requirements.txt` also works.)\n"
    )
    sys.exit(1)


KEY_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".update-signing-key")


def main() -> int:
    if os.path.exists(KEY_PATH):
        sys.stderr.write(
            f"Refusing to overwrite existing key at {KEY_PATH}.\n"
            f"If you really intend to rotate (this BREAKS auto-updates for every\n"
            f"already-shipped client), delete the file first.\n"
        )
        return 1

    sk = SigningKey.generate()
    private_b64 = base64.b64encode(bytes(sk)).decode("ascii")
    public_b64 = base64.b64encode(bytes(sk.verify_key)).decode("ascii")

    # 0600 — owner read/write only
    fd = os.open(KEY_PATH, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(private_b64 + "\n")

    print(f"Wrote private key to: {KEY_PATH}")
    print()
    print("PUBLIC KEY — paste into app.py as UPDATE_SIGNING_PUBKEY:")
    print(f'    UPDATE_SIGNING_PUBKEY = "{public_b64}"')
    print()
    print("CRITICAL next steps:")
    print("  1. Back up the private key in 1Password (it is NOT in git).")
    print("  2. Add the same private key as a GitHub Actions secret named")
    print("     UPDATE_SIGNING_KEY so the Windows build can sign too.")
    print("  3. Paste the public key line above into app.py.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
