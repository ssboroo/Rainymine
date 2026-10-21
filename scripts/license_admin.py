"""Owner-only offline license issuer. Run on a secure machine, never ship private keys."""
import argparse
import base64
import getpass
import json
from pathlib import Path
import re
import sys
import time
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from rainymine.licensing import atomic_bytes, canonical


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    init = sub.add_parser('init')
    init.add_argument('--private-key', type=Path, required=True)
    init.add_argument('--public-keys', type=Path, required=True)
    init.add_argument('--key-id', required=True)
    issue = sub.add_parser('issue')
    issue.add_argument('--private-key', type=Path, required=True)
    issue.add_argument('--key-id', required=True)
    issue.add_argument('--customer', required=True)
    issue.add_argument('--device', required=True)
    issue.add_argument('--days', type=int, required=True)
    issue.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    if args.private_key.resolve().is_relative_to(repo):
        parser.error('Keep the private signing key outside the repository/build directory.')
    if not args.key_id or len(args.key_id) > 256:
        parser.error('Invalid key ID')
    password = getpass.getpass('Private key password (not stored): ').encode()
    if len(password) < 12:
        parser.error('Use a password of at least 12 characters.')
    if args.command == 'init':
        if args.private_key.exists():
            parser.error('Private key already exists; refusing overwrite.')
        keys = json.loads(args.public_keys.read_text()) if args.public_keys.exists() else {}
        if args.key_id in keys:
            parser.error('Key ID already exists; choose a new rotation ID.')
        if password != getpass.getpass('Repeat password: ').encode():
            parser.error('Passwords differ')
        private = Ed25519PrivateKey.generate()
        encoded = private.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.BestAvailableEncryption(password))
        # Exclusive creation, restrictive file mode; no private key is printed.
        args.private_key.parent.mkdir(parents=True, exist_ok=True)
        import os
        fd = os.open(args.private_key, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'wb') as output:
            output.write(encoded)
        public = private.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        keys[args.key_id] = base64.b64encode(public).decode()
        atomic_bytes(args.public_keys, canonical(keys))
        print('Created encrypted owner key. Commit only the public key registry; rebuild before issuing licenses.')
    else:
        if not re.fullmatch('[a-f0-9]{64}', args.device) or not 1 <= args.days <= 36500 or not 1 <= len(args.customer) <= 256:
            parser.error('Invalid device, duration or customer')
        if args.output.exists():
            parser.error('Output exists; refusing overwrite.')
        key = serialization.load_pem_private_key(args.private_key.read_bytes(), password=password)
        if not isinstance(key, Ed25519PrivateKey):
            parser.error('Expected an Ed25519 private key')
        now = int(time.time())
        payload = {'schema': 1, 'product': 'RAINYMINE', 'key_id': args.key_id,
                   'license_id': str(uuid.uuid4()), 'customer': args.customer,
                   'device_id': args.device, 'not_before': now, 'expires_at': now + args.days * 86400}
        document = {'payload': payload, 'signature': base64.b64encode(key.sign(canonical(payload))).decode()}
        atomic_bytes(args.output, canonical(document))
        print('Signed device license created:', args.output)


if __name__ == '__main__':
    main()
