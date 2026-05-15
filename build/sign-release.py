#!/usr/bin/env python3
"""
Sign a release artifact (.dmg or .exe) with the Ed25519 update key.

Reads the private key from either:
  - the UPDATE_SIGNING_KEY environment variable (used in GitHub Actions), or
  - build/.update-signing-key (used on Nathan's laptop)

Prints the base64-encoded signature on stdout. This goes into the
appcast.xml entry's sparkle:edSignature attribute.

Usage:
    python build/sign-release.py dist/Bitaxe-Baller-Mac.dmg

Exit codes:
    0 — signature on stdout
    1 — usage / I/O error
    2 — key not found
"""

import base64
import os
import sys

try:
    from nacl.signing import SigningKey
except ImportError:
    sys.stderr.write("PyNaCl is not installed. pip install pynacl\n")
    sys.exit(1)


KEY_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".update-signing-key")


def load_key() -> SigningKey:
    env_key = os.environ.get("UPDATE_SIGNING_KEY", "").strip()
    if env_key:
        return SigningKey(base64.b64decode(env_key))
    if os.path.exists(KEY_PATH):
        with open(KEY_PATH) as f:
            return SigningKey(base64.b64decode(f.read().strip()))
    sys.stderr.write(
        f"No signing key. Set UPDATE_SIGNING_KEY in the env, or run\n"
        f"  python build/gen-update-keypair.py\n"
        f"to create one at {KEY_PATH}.\n"
    )
    sys.exit(2)


def main() -> int:
    if len(sys.argv) != 2:
        sys.stderr.write("usage: sign-release.py <path-to-artifact>\n")
        return 1
    artifact = sys.argv[1]
    if not os.path.isfile(artifact):
        sys.stderr.write(f"not a file: {artifact}\n")
        return 1

    sk = load_key()
    with open(artifact, "rb") as f:
        sig = sk.sign(f.read()).signature
    print(base64.b64encode(sig).decode("ascii"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
