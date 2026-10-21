import base64
import json
from pathlib import Path
import tempfile
import unittest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from rainymine.licensing import LicenseManager, StateStore, TRIAL_SECONDS, canonical


class LicensingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.now = 1800000000
        self.key = Ed25519PrivateKey.generate()
        public = self.key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        self.manager = LicenseManager(StateStore(Path(self.temp.name), False), {'test': base64.b64encode(public).decode()}, 'device', lambda: self.now)

    def document(self, **changes):
        payload = {'schema': 1, 'product': 'RAINYMINE', 'key_id': 'test', 'license_id': '123', 'customer': 'Туршилтын хэрэглэгч', 'device_id': 'device', 'not_before': self.now, 'expires_at': self.now + 86400}
        payload.update(changes)
        return {'payload': payload, 'signature': base64.b64encode(self.key.sign(canonical(payload))).decode()}

    def activation(self, document):
        path = Path(self.temp.name) / 'incoming.rainylic'
        path.write_text(json.dumps(document), encoding='utf-8')
        return self.manager.activate(path)

    def test_explicit_start_and_exact_seven_day_boundary(self):
        self.assertEqual(self.manager.status().kind, 'not_started')
        self.assertFalse((self.manager.store.root / 'trial.dat').exists())
        self.assertTrue(self.manager.status(True).allowed)
        self.now += TRIAL_SECONDS - 1
        self.assertTrue(self.manager.status().allowed)
        self.now += 1
        self.assertEqual(self.manager.status().kind, 'expired')
        self.assertFalse(self.manager.status().allowed)

    def test_restarting_and_repeated_start_do_not_extend_trial(self):
        self.manager.status(True)
        self.now += TRIAL_SECONDS
        other = LicenseManager(self.manager.store, self.manager.keys, 'device', lambda: self.now)
        self.assertFalse(other.status(True).allowed)

    def test_clock_rollback_fails_closed(self):
        self.manager.status(True)
        self.now += 86400
        self.manager.status()
        self.now -= 3600
        self.assertEqual(self.manager.status().kind, 'error')
        self.now += 3600
        self.assertTrue(self.manager.status().allowed)

    def test_corrupt_state_does_not_restart(self):
        self.manager.status(True)
        (self.manager.store.root / 'trial.dat').write_bytes(b'broken')
        self.assertFalse(self.manager.status(True).allowed)

    def test_valid_signed_activation_and_expiry(self):
        self.assertEqual(self.activation(self.document()).kind, 'licensed')
        self.now += 86400
        self.assertFalse(self.manager.status().allowed)

    def test_tampered_customer_and_wrong_key_rejected(self):
        document = self.document()
        document['payload']['customer'] = 'Changed'
        with self.assertRaisesRegex(ValueError, 'гарын үсэг'):
            self.activation(document)
        self.manager.keys = {}
        with self.assertRaisesRegex(ValueError, 'түлхүүр'):
            self.activation(self.document())

    def test_other_device_and_future_license_rejected(self):
        with self.assertRaisesRegex(ValueError, 'төхөөрөмж'):
            self.activation(self.document(device_id='other'))
        with self.assertRaisesRegex(ValueError, 'хугацаа'):
            self.activation(self.document(not_before=self.now + 10))

    def test_invalid_dates_and_oversize_rejected(self):
        document = self.document()
        document['payload']['expires_at'] = 'forever'
        with self.assertRaisesRegex(ValueError, 'огноо'):
            self.activation(document)
        path = Path(self.temp.name) / 'huge.rainylic'
        path.write_bytes(b'x' * 40000)
        with self.assertRaisesRegex(ValueError, 'том'):
            self.manager.activate(path)

    def test_license_renewal_after_trial_expired(self):
        self.manager.status(True)
        self.now += TRIAL_SECONDS
        self.assertFalse(self.manager.status().allowed)
        self.assertTrue(self.activation(self.document()).allowed)

    def test_one_surviving_anchor_restores_original_start(self):
        class MemoryStore:
            root = Path(self.temp.name)
            states = [{'schema': 1, 'device': 'device', 'started': self.now - TRIAL_SECONDS, 'last_seen': self.now}]
            def read(inner): return inner.states
            def write(inner, state): inner.states = [state]
        self.manager.store = MemoryStore()
        self.assertEqual(self.manager.status(True).kind, 'expired')
