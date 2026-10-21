"""Prepare pinned, SHA256-verified Windows AI assets for packaging."""
import argparse
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from rainymine.local_engine import (download_verified,extract_runtime,RUNTIME_TAG,RUNTIME_URL,RUNTIME_SHA,
                                   MODEL_URL,MODEL_NAME,MODEL_SHA,MODEL_BYTES)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--model',action='store_true');args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]/'ai'
    archive=download_verified(RUNTIME_URL,root/'downloads'/f'{RUNTIME_TAG}.zip',RUNTIME_SHA,200_000_000)
    engine=extract_runtime(archive,root/'runtime');print('Verified Windows CPU engine:',engine)
    if args.model:
        model=download_verified(MODEL_URL,root/'models'/MODEL_NAME,MODEL_SHA,MODEL_BYTES+1024)
        print('Verified GGUF model:',model)

if __name__=='__main__':main()
