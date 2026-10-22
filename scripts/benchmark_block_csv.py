"""Reproducible synthetic CPU import timing; no rendering or SLA certification."""
import argparse
import csv
import json
from pathlib import Path
import platform
import sys
import tempfile
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from rainymine.block_csv import read_block_csv,KEYS


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--blocks',type=int,default=50000)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    if not 1<=args.blocks<=50000:parser.error('--blocks must be 1..50000')
    with tempfile.TemporaryDirectory() as directory:
        path=Path(directory)/'blocks.csv'
        with path.open('w',newline='') as stream:
            writer=csv.writer(stream);writer.writerow(KEYS)
            for i in range(args.blocks):writer.writerow([500005+(i%100)*10,5300005+(i//100)*10,1005,10,10,10,1])
        started=time.perf_counter()
        model,report=read_block_csv(path,dict(zip(KEYS,KEYS)),'EPSG:32648','ppm',geometry={'origin':[500000,5300000,1000],'parent_size':[10,10,10],'angles':[90,0,0]})
        elapsed=time.perf_counter()-started
        import numpy,pyproj
        result={'operation':'explicit parent geometry CSV import','blocks':len(model['blocks']),
                'elapsed_seconds':round(elapsed,3),'bytes':path.stat().st_size,'source_sha256':report['sha256'],
                'python':platform.python_version(),'system':platform.system(),'numpy':numpy.__version__,'pyproj':pyproj.__version__,
                'scope':'synthetic CPU import only; not GPU FPS, not real mine acceptance'}
        text=json.dumps(result,indent=2)+'\n'
        if args.output:args.output.write_text(text,encoding='utf-8')
        print(text,end='')

if __name__=='__main__':main()
