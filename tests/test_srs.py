import math
import unittest
from rainymine.core import Collar, Survey, Assay, Lithology, Project, Trajectory
from rainymine.srs_tools import lithology_composites, swath_rows, blend_materials


class DesurveyMethods(unittest.TestCase):
    def test_straight_and_quarter_circle(self):
        for method in ('minimum_curvature','balanced_tangential','radius_of_curvature'):
            t=Trajectory(Collar('A',0,0,0,100,90,0),[],method)
            self.assertAlmostEqual(t.at(100)[0],100)
        h=Collar('A',0,0,0,100)
        surveys=[Survey('A',0,0,0),Survey('A',100,0,-90)]
        balanced=Trajectory(h,surveys,'balanced_tangential').at(100)
        radius=Trajectory(h,surveys,'radius_of_curvature').at(100)
        self.assertAlmostEqual(balanced[1],50);self.assertAlmostEqual(balanced[2],-50)
        self.assertAlmostEqual(radius[1],200/math.pi);self.assertAlmostEqual(radius[2],-200/math.pi)

    def test_wrap_station_continuity_and_validation(self):
        h=Collar('A',0,0,0,150)
        for method in ('balanced_tangential','radius_of_curvature'):
            t=Trajectory(h,[Survey('A',0,359,-45),Survey('A',100,1,-65)],method)
            self.assertLess(abs(t.at(100)[0]),1)
            self.assertLess(math.dist(t.at(100-1e-7),t.at(100+1e-7)),1e-5)
            self.assertEqual(t.at(0),(0.,0.,0.))
        with self.assertRaises(ValueError):Trajectory(h,[],'invalid')


class SupportDiagnostics(unittest.TestCase):
    def test_lithology_boundary_and_missing_assay(self):
        p=Project(collars=[Collar('A',0,0,0,10)],assays=[Assay('A',0,2,1),Assay('A',4,10,3)],
                  lithology=[Lithology('A',0,3,'A'),Lithology('A',3,8,'B')])
        rows=lithology_composites(p,5)
        self.assertEqual([(r['from_m'],r['to_m']) for r in rows],[(0,3),(3,8)])
        self.assertEqual(rows[0]['grade'],1);self.assertAlmostEqual(rows[0]['coverage'],2/3)
        self.assertEqual(rows[1]['support_m'],4);self.assertEqual(rows[1]['grade'],3)

    def test_swath_weighting_no_data_negative_bins(self):
        samples=[{'xyz':[-1,0,0],'grade':2.,'support_m':1.}, {'xyz':[-2,0,0],'grade':4.,'support_m':3.}]
        blocks=[{'x':-1,'dx':1,'dy':1,'dz':1,'grade':1}, {'x':-2,'dx':3,'dy':1,'dz':1,'grade':5},
                {'x':10,'dx':2,'dy':1,'dz':1,'grade':None}]
        rows=swath_rows(samples,{'blocks':blocks},width=10)
        self.assertEqual(rows[0]['from_m'],-10);self.assertEqual(rows[0]['sample_grade'],3.5)
        self.assertEqual(rows[0]['block_grade'],4);self.assertEqual(rows[0]['difference'],.5)
        self.assertEqual(rows[1]['from_m'],10);self.assertIsNone(rows[1]['block_grade'])
        self.assertEqual(rows[1]['unestimated_volume_m3'],2)
        with self.assertRaises(ValueError):swath_rows([],{'blocks':[]},axis='XY')


class BlendTests(unittest.TestCase):
    def feeds(self):return [{'id':'low','tonnes':100,'grade':1,'cost_per_tonne':1},
                            {'id':'high','tonnes':100,'grade':3,'cost_per_tonne':5}]
    def test_analytic_minimum_cost(self):
        r=blend_materials(self.feeds(),100,2,2.5)
        self.assertTrue(r['feasible']);self.assertAlmostEqual(r['grade'],2)
        self.assertAlmostEqual(r['rows'][0]['tonnes'],50);self.assertAlmostEqual(r['total_cost'],300)
    def test_infeasibility_never_partial(self):
        for amount,grade in [(201,2),(100,4)]:
            r=blend_materials(self.feeds(),amount,grade,grade)
            self.assertFalse(r['feasible']);self.assertEqual(r['rows'],[])
    def test_bad_values_and_duplicate_ids(self):
        with self.assertRaises(ValueError):blend_materials(self.feeds()*2,100,1,3)
        with self.assertRaises(ValueError):blend_materials(self.feeds(),float('nan'),1,3)
        with self.assertRaises(ValueError):blend_materials(self.feeds(),100,3,1)

class SurveyChecks(unittest.TestCase):
    def test_vector_dogleg_wrap_and_vertical(self):
        from rainymine.srs_tools import survey_doglegs
        p=Project(collars=[Collar('A',0,0,0,60)],surveys=[Survey('A',0,359,0),Survey('A',30,1,0),Survey('A',60,1,-90)])
        rows=survey_doglegs(p,10)
        self.assertAlmostEqual(rows[0]['degrees_per_30m'],2);self.assertFalse(rows[0]['flagged'])
        self.assertAlmostEqual(rows[1]['degrees_per_30m'],90);self.assertTrue(rows[1]['flagged'])

    def test_export_selected_method_preserves_project(self):
        import csv,tempfile
        from pathlib import Path
        from copy import deepcopy
        from rainymine.core import export_trajectories
        p=Project(collars=[Collar('A',0,0,0,100)],surveys=[Survey('A',0,0,0),Survey('A',100,0,-90)])
        before=deepcopy(p)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'trace.csv';export_trajectories(path,p,'balanced_tangential')
            with path.open(encoding='utf-8-sig') as f:rows=list(csv.DictReader(f))
            self.assertAlmostEqual(float(rows[-1]['y']),50)
        self.assertEqual(p,before)
