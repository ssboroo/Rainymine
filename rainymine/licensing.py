"""Seven-day offline evaluation and Ed25519-signed device licenses.

Local trial anchors deter accidental resets/clock rollback, not a hostile administrator.
No private signing key, network call, project data or payment handling belongs here.
"""
import base64
import getpass
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import sys
import tempfile
import time
from dataclasses import dataclass

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

TRIAL_SECONDS = 7 * 24 * 60 * 60
MAX_LICENSE_BYTES = 32768


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode('utf-8')


def device_id():
    identity = platform.node()
    if sys.platform == 'win32':
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\Microsoft\Cryptography', 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as key:
            identity = winreg.QueryValueEx(key, 'MachineGuid')[0]
    return hashlib.sha256(('RAINYMINE-v1|' + identity + '|' + getpass.getuser()).encode()).hexdigest()


def _protect(data, decrypt=False):
    if sys.platform != 'win32':
        return data  # Developer/source tests only; Windows distribution uses DPAPI.
    import ctypes
    from ctypes import wintypes

    class Blob(ctypes.Structure):
        _fields_ = [('cbData', wintypes.DWORD), ('pbData', ctypes.POINTER(ctypes.c_ubyte))]
    buffer = ctypes.create_string_buffer(data)
    source = Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    output = Blob()
    crypt = ctypes.WinDLL('crypt32', use_last_error=True)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    fn = crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    fn.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    fn.restype = wintypes.BOOL
    if not fn(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(output)):
        raise OSError(ctypes.get_last_error(), 'Лицензийн хамгаалсан төлөвийг уншиж/хадгалж чадсангүй.')
    try:
        return ctypes.string_at(output.pbData, output.cbData)
    finally:
        kernel.LocalFree(output.pbData)


def atomic_bytes(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.license-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


class StateStore:
    """Two per-user anchors; deleting just one does not restart the trial."""
    def __init__(self, root=None, use_registry=None):
        self.root = Path(root) if root is not None else Path(os.environ.get('LOCALAPPDATA', str(Path.home() / '.local/share'))) / 'Rainymine' / 'licensing'
        self.registry = sys.platform == 'win32' if use_registry is None else use_registry

    def read(self):
        blobs = []
        path = self.root / 'trial.dat'
        if path.exists():
            if path.stat().st_size > MAX_LICENSE_BYTES:
                raise ValueError('Лицензийн төлөв гэмтсэн.')
            blobs.append(path.read_bytes())
        if self.registry:
            import winreg
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Rainymine\Licensing') as key:
                    value, kind = winreg.QueryValueEx(key, 'TrialState')
                    if kind != winreg.REG_BINARY or len(value) > MAX_LICENSE_BYTES:
                        raise ValueError('Лицензийн бүртгэл гэмтсэн.')
                    blobs.append(value)
            except FileNotFoundError:
                pass
        return [json.loads(_protect(blob, decrypt=True)) for blob in blobs]

    def write(self, state):
        blob = _protect(canonical(state))
        atomic_bytes(self.root / 'trial.dat', blob)
        if self.registry:
            import winreg
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r'Software\Rainymine\Licensing') as key:
                winreg.SetValueEx(key, 'TrialState', 0, winreg.REG_BINARY, blob)


@dataclass(frozen=True)
class Status:
    allowed: bool
    kind: str
    message: str
    expires: float | None = None


def verify_license(document, keys, device, now):
    if not isinstance(document, dict) or set(document) != {'payload', 'signature'}:
        raise ValueError('Лицензийн файлын бүтэц буруу.')
    payload = document['payload']
    required = {'schema', 'product', 'key_id', 'license_id', 'customer', 'device_id', 'not_before', 'expires_at'}
    if not isinstance(payload, dict) or set(payload) != required:
        raise ValueError('Лицензийн талбарууд буруу.')
    for field in ('key_id', 'license_id', 'customer', 'device_id'):
        if not isinstance(payload[field], str) or not 1 <= len(payload[field]) <= 256:
            raise ValueError('Лицензийн мэдээлэл буруу.')
    for field in ('not_before', 'expires_at'):
        if type(payload[field]) not in (int, float) or not math.isfinite(payload[field]):
            raise ValueError('Лицензийн огноо буруу.')
    if payload['schema'] != 1 or payload['product'] != 'RAINYMINE' or payload['device_id'] != device:
        raise ValueError('Энэ төхөөрөмжийн RAINYMINE лиценз биш.')
    if not payload['not_before'] <= now < payload['expires_at']:
        raise ValueError('Лицензийн хугацаа эхлээгүй эсвэл дууссан.')
    if payload['key_id'] not in keys:
        raise ValueError('Лиценз олгогчийн нийтийн түлхүүр тохируулагдаагүй.')
    try:
        key = Ed25519PublicKey.from_public_bytes(base64.b64decode(keys[payload['key_id']], validate=True))
        key.verify(base64.b64decode(document['signature'], validate=True), canonical(payload))
    except (InvalidSignature, ValueError, TypeError) as exc:
        raise ValueError('Лицензийн тоон гарын үсэг хүчингүй.') from exc
    return payload


class LicenseManager:
    def __init__(self, store=None, keys=None, device=None, clock=time.time):
        self.store = store or StateStore()
        self.device = device or device_id()
        self.clock = clock
        if keys is None:
            root = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[1]))
            keys = json.loads((root / 'assets/license-public-keys.json').read_text(encoding='utf-8'))
        self.keys = keys

    def _state(self, now, start=False):
        states = self.store.read()
        if not states:
            if not start:
                return None
            states = [{'schema': 1, 'device': self.device, 'started': now, 'last_seen': now}]
        for state in states:
            if not isinstance(state, dict) or set(state) != {'schema', 'device', 'started', 'last_seen'}:
                raise ValueError('Туршилтын бүртгэл гэмтсэн. Дэмжлэгт хандана уу.')
            if state['schema'] != 1 or state['device'] != self.device:
                raise ValueError('Туршилтын бүртгэл энэ төхөөрөмжид тохирохгүй.')
            for field in ('started', 'last_seen'):
                if type(state[field]) not in (int, float) or not math.isfinite(state[field]) or state[field] < 0:
                    raise ValueError('Туршилтын огноо гэмтсэн.')
            if state['last_seen'] < state['started']:
                raise ValueError('Туршилтын огноо зөрсөн.')
        started = min(state['started'] for state in states)
        last = max(state['last_seen'] for state in states)
        if now + 120 < last or now < started:
            raise ValueError('Системийн цаг ухарсан байна. Огноо, цагаа засна уу.')
        state = {'schema': 1, 'device': self.device, 'started': started, 'last_seen': max(now, last)}
        self.store.write(state)
        return state

    def status(self, start_trial=False):
        try:
            now = self.clock()
            if type(now) not in (int, float) or not math.isfinite(now) or now < 0:
                raise ValueError('Системийн цаг буруу.')
            state = self._state(now, start_trial)
            license_path = self.store.root / 'license.rainylic'
            if license_path.exists():
                if license_path.stat().st_size > MAX_LICENSE_BYTES:
                    raise ValueError('Лицензийн файл хэт том.')
                payload = verify_license(json.loads(license_path.read_text(encoding='utf-8')), self.keys, self.device, now)
                if state is None:
                    self._state(now, True)
                return Status(True, 'licensed', 'Идэвхтэй лиценз: ' + payload['customer'], payload['expires_at'])
            if state is None:
                return Status(False, 'not_started', '7 хоногийн туршилтыг эхлүүлэх эсвэл лицензээ идэвхжүүлнэ үү.')
            expires = state['started'] + TRIAL_SECONDS
            if now >= expires:
                return Status(False, 'expired', '7 хоногийн туршилтын хугацаа дууссан. Лиценз идэвхжүүлнэ үү.', expires)
            hours = max(1, math.ceil((expires - now) / 3600))
            return Status(True, 'trial', f'Туршилтын лиценз — {hours} цаг үлдсэн.', expires)
        except (OSError, ValueError, TypeError, KeyError) as exc:
            return Status(False, 'error', str(exc))

    def activate(self, path):
        path = Path(path)
        if path.stat().st_size > MAX_LICENSE_BYTES:
            raise ValueError('Лицензийн файл хэт том.')
        document = json.loads(path.read_text(encoding='utf-8'))
        now = self.clock()
        verify_license(document, self.keys, self.device, now)
        self._state(now, True)
        atomic_bytes(self.store.root / 'license.rainylic', canonical(document))
        return self.status()
