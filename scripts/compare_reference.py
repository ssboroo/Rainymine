"""Numerical comparison CLI; outputs JSON, never certifies a deposit."""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from rainymine.core import load_project
from rainymine.benchmark import compare_reference, write_comparison_report

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('project');parser.add_argument('reference')
    parser.add_argument('--coordinate-tolerance',type=float,default=.01)
    parser.add_argument('--grade-absolute',type=float,default=.001)
    parser.add_argument('--grade-relative',type=float,default=.01)
    parser.add_argument('--density',type=float,help='Explicit fallback t/m3; no density is inferred')
    parser.add_argument('--geometry-relative',type=float,default=1e-6)
    parser.add_argument('--output',help='Standalone .html or machine-readable .json report')
    args=parser.parse_args();project=load_project(args.project)
    if not project.workspace.get('block_model'):parser.error('Project has no block model')
    result=compare_reference(project.workspace['block_model'],args.reference,args.coordinate_tolerance,args.grade_absolute,args.grade_relative,project.grade_unit,args.density,args.geometry_relative)
    if args.output:write_comparison_report(args.output,result)
    print(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False))
    return 0 if result['numerical_pass'] else 1

if __name__=='__main__':raise SystemExit(main())
