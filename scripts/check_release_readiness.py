"""Fail closed on unconfigured commercial-release prerequisites; preview is explicit."""
import argparse
import base64
import json
from pathlib import Path


def check(root):
    root=Path(root)
    config=json.loads((root/'release/config.json').read_text(encoding='utf-8'))
    keys=json.loads((root/'assets/license-public-keys.json').read_text(encoding='utf-8'))
    failures=[]
    if not isinstance(keys,dict) or not keys:failures.append('Owner Ed25519 public keys are not configured')
    elif any(not isinstance(k,str) or not k or not isinstance(v,str) for k,v in keys.items()):failures.append('Invalid license key registry')
    else:
        try:
            if any(len(base64.b64decode(v,validate=True))!=32 for v in keys.values()):raise ValueError()
        except (ValueError,TypeError):failures.append('Invalid Ed25519 public key encoding')
    expected={'code_signing':'configured','owner_distribution_license':'approved',
              'independent_deposit_validation':'completed','physical_windows_device_validation':'completed',
              'license_signing_key':'configured'}
    for key,value in expected.items():
        if config.get(key)!=value:failures.append(key+': '+str(config.get(key)))
    # This validates declared readiness, not the truth of a reviewer statement.
    return {'production_ready':not failures,'blockers':failures,
            'scope':'Configuration preflight only; certificate trust, reviewer evidence and hardware reports require separate verification'}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument('--production',action='store_true')
    args=parser.parse_args();result=check(args.root)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    raise SystemExit(1 if args.production and not result['production_ready'] else 0)
