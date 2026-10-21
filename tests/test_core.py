import csv
import math
import tempfile
import unittest
from dataclasses import asdict,replace
from pathlib import Path
from rainymine.core import *

class GeometryTests(unittest.TestCase):
    def test_vertical_and_cardinal_axes(self):
        for az,dip,expected in [(0,-90,(10,20,-70)),(0,0,(10,120,30)),(90,0,(110,20,30)),(180,0,(10,-80,30)),(270,0,(-90,20,30))]:
            t=Trajectory(Collar('A',10,20,30,100,az,dip),[])
            for a,b in zip(t.at(100),expected):self.assertAlmostEqual(a,b,places=8)
    def test_quarter_circle_analytic(self):
        h=Collar('A',0,0,0,100,0,0);t=Trajectory(h,[Survey('A',0,0,0),Survey('A',100,0,-90)]);r=200/math.pi
        self.assertAlmostEqual(t.at(100)[1],r,places=8);self.assertAlmostEqual(t.at(100)[2],-r,places=8)
        self.assertAlmostEqual(t.at(50)[1],r*math.sin(math.pi/4),places=8)
        self.assertAlmostEqual(t.at(50)[2],-r*(1-math.cos(math.pi/4)),places=8)
    def test_wraparound_and_tail(self):
        h=Collar('A',0,0,0,150,0,-45);t=Trajectory(h,[Survey('A',0,359,-45),Survey('A',100,1,-45)])
        self.assertLess(abs(t.at(100)[0]),.1)
        for a,b,c in zip(t.at(100),t.at(150),direction(1,-45)):self.assertAlmostEqual(b-a,50*c)
    def test_station_continuity(self):
        t=Trajectory(Collar('A',1e6,5e6,1400,200),[Survey('A',0,0,-60),Survey('A',100,60,-70),Survey('A',200,120,-80)])
        self.assertLess(math.dist(t.at(100-1e-7),t.at(100+1e-7)),1e-6)
        with self.assertRaises(ValueError):t.at(201)
    def test_sampling_includes_stations(self):
        t=Trajectory(Collar('A',0,0,0,110),[Survey('A',0,0,-90),Survey('A',37,20,-75)])
        depths=[d for d,p in t.sample(10,97,9)];self.assertIn(37,depths);self.assertEqual(depths[0],10);self.assertEqual(depths[-1],97)

class DataTests(unittest.TestCase):
    def project(self):return Project(collars=[Collar('A',0,0,10,100)])
    def test_validation_rejects_bad_values(self):
        h=self.project().collars[0]
        for bad in [replace(h,x=float('nan')),replace(h,depth=-1),replace(h,azimuth=360),replace(h,dip=1),replace(h,x=True)]:
            with self.assertRaises(ValueError):Project(collars=[bad]).validate()
        with self.assertRaises(ValueError):Project(collars=[h,h]).validate()
    def test_interval_errors(self):
        for assays in [[Assay('B',0,1,1)],[Assay('A',99,101,1)],[Assay('A',1,10,1),Assay('A',9,20,2)],[Assay('A',1,2,101)]]:
            with self.assertRaises(ValueError):Project(collars=self.project().collars,assays=assays).validate()
    def test_survey_errors(self):
        for surveys in [[Survey('A',2,0,-90)],[Survey('A',0,0,-90),Survey('A',0,10,-80)],[Survey('B',0,0,-90)]]:
            with self.assertRaises(ValueError):Project(collars=self.project().collars,surveys=surveys).validate()
    def test_roundtrip(self):
        p=demo()
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/'Монгол нэр.rmine';save_project(f,p);self.assertEqual(load_project(f).to_dict(),p.to_dict())
            f=Path(d)/'trace.csv';export_trajectories(f,p)
            with f.open(encoding='utf-8-sig') as stream:self.assertGreater(len(list(csv.DictReader(stream))),20)
            f=Path(d)/'collar.csv';write_records(f,[asdict(h) for h in p.collars],tuple(Collar.__dataclass_fields__));self.assertEqual(read_collars(f),p.collars)
    def test_invalid_save_preserves_old_file(self):
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/'a.rmine';save_project(f,self.project());before=f.read_bytes()
            with self.assertRaises(ValueError):save_project(f,Project(collars=[Collar('A',float('nan'),0,0,1)]))
            self.assertEqual(f.read_bytes(),before)
    def test_bad_csv(self):
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/'a.csv';f.write_text('hole_id,x\nA,0',encoding='utf-8')
            with self.assertRaises(ValueError):read_collars(f)
            f.write_text('x,y,z\nnan,0,0',encoding='utf-8')
            with self.assertRaises(ValueError):read_surface(f)
    def test_oversized_save_preserves_old_file(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/'a.rmine';save_project(f,self.project());before=f.read_bytes()
            with patch('rainymine.core.MAX_FILE',100):
                with self.assertRaises(ValueError):save_project(f,self.project())
            self.assertEqual(f.read_bytes(),before)
    def test_unknown_format(self):
        with self.assertRaises(ValueError):Project.from_dict({'format':'other'})
    def test_surface_duplicate(self):
        with self.assertRaises(ValueError):Project(surface=[[0,0,1],[0,0,2],[1,1,1]]).validate()
    def test_collinear_surface(self):
        with self.assertRaises(ValueError):Project(surface=[[0,0,1],[1,1,2],[2,2,3]]).validate()
    def test_composite_support_and_gaps(self):
        p=self.project();p.assays=[Assay('A',0,2,1),Assay('A',2,5,3),Assay('A',7,10,4)];rows=composite_assays(p,5)
        self.assertAlmostEqual(rows[0]['grade'],2.2);self.assertEqual(rows[0]['coverage'],1)
        self.assertEqual(rows[1]['grade'],4);self.assertAlmostEqual(rows[1]['coverage'],.6);self.assertEqual(len(rows),2)
    def test_bad_composite_length(self):
        for length in (0,-1,float('nan'),.00001):
            with self.assertRaises(ValueError):composite_assays(self.project(),length)

if __name__=='__main__':unittest.main()
