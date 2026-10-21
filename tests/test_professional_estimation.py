"""Analytical controls for experimental anisotropic and block-support workflows."""
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
import numpy as np
from rainymine.core import demo, save_project, load_project
from rainymine.estimation import Estimator, make_blocks, estimate_model, tonnage_grade
from rainymine.spatial import search_basis
from rainymine.planning import tasks_from_blocks


class ProfessionalEstimationTests(unittest.TestCase):
    def test_anisotropic_two_sample_analytic_weights(self):
        samples=[{'hole_id':'E','xyz':[1,0,0],'grade':2}, {'hole_id':'N','xyz':[0,1,0],'grade':10}]
        params={'method':'kriging','minimum':2,'neighbors':2,'radii':[10,10,10],
                'variogram_ranges':[10,1,1], 'nugget':0,'partial_sill':1}
        # gamma(E)=0.1495, gamma(N)=gamma(E-N)=1;
        # w_E=.5+(1-.1495)/2=.92525; w_N=.07475.
        result=Estimator(samples,params).predict([0,0,0])
        self.assertAlmostEqual(result['grade'],2.598)
        isotropic=Estimator(samples,dict(params,variogram_ranges=[10,10,10])).predict([0,0,0])
        self.assertAlmostEqual(isotropic['grade'],6)
        basis=search_basis(30,-25,15);origin=np.array([500000,5300000,1300])
        rotated=[dict(s,xyz=(np.array(s['xyz'])@basis.T+origin).tolist()) for s in samples]
        rotated_result=Estimator(rotated,dict(params,variogram_angles=[30,-25,15])).predict(origin)
        self.assertAlmostEqual(result['grade'],rotated_result['grade'],places=8)
        self.assertAlmostEqual(result['variance'],rotated_result['variance'],places=8)
        for ranges in ([1,0,1],[1,2],[1,float('nan'),1]):
            with self.assertRaises(ValueError):Estimator(samples,dict(params,variogram_ranges=ranges))

    def test_discrete_block_kriging_analytic_variance(self):
        samples=[{'hole_id':'A','xyz':[-1,0,0],'grade':0}, {'hole_id':'B','xyz':[1,0,0],'grade':2}]
        est=Estimator(samples,{'method':'kriging','minimum':2,'neighbors':2,'range_m':10})
        point=est.predict([0,0,0]);block=est.predict([0,0,0],support_offsets=[[-.5,0,0],[.5,0,0]])
        self.assertAlmostEqual(point['variance'],.151)
        # Mean sample/block gamma=.149125; mu=.001125; within-block gamma=.07475.
        self.assertAlmostEqual(block['variance'],.0755)
        self.assertAlmostEqual(block['grade'],1)
        for support in ([], [[0,0]], [[float('inf'),0,0]], [[0,0,0]]*65):
            with self.assertRaises(ValueError):est.predict([0,0,0],support_offsets=support)

    def test_top_cut_and_hole_constraints_preserve_source(self):
        samples=[{'hole_id':'A','xyz':[1,0,0],'grade':100},
                 {'hole_id':'A','xyz':[2,0,0],'grade':5},
                 {'hole_id':'B','xyz':[3,0,0],'grade':2}]
        original=deepcopy(samples)
        params={'minimum':2,'neighbors':2,'max_per_hole':1,'minimum_holes':2,'top_cut':10}
        est=Estimator(samples,params)
        self.assertEqual(est.capped_count,1)
        self.assertAlmostEqual(est.predict([0,0,0])['grade'],9.2)
        self.assertIsNone(est.predict([0,0,0],exclude_hole='B')['grade'])
        self.assertEqual(samples,original)
        with self.assertRaises(ValueError):Estimator(samples,dict(params,top_cut=-1))

    def test_rotated_grid_volume_and_model_roundtrip(self):
        bounds=[500000,5300000,1100,500004,5300002,1102]
        blocks=make_blocks(bounds,[2,2,2],grid_angles=[0,0,0])
        self.assertEqual(len(blocks),2)
        self.assertAlmostEqual(blocks[0]['x'],499999)
        self.assertAlmostEqual(blocks[0]['y'],5300001)
        self.assertAlmostEqual(sum(b['dx']*b['dy']*b['dz'] for b in blocks),16)
        p=demo();params={'method':'kriging','minimum':2,'neighbors':4,'radii':[1000,1000,1000],
                         'grid_angles':[35,-10,15],'variogram_ranges':[300,200,100],
                         'discretization':[2,2,2],'composite_length':20,'top_cut':2}
        model=estimate_model(p,[500000,5300000,1200,500040,5300040,1240],[20,20,20],params)
        self.assertTrue(all(b['grade'] is not None for b in model['blocks']))
        self.assertIn('block average',model['support'])
        p.workspace['block_model']=model
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'rotated.rmine';save_project(path,p);restored=load_project(path)
            self.assertEqual(restored.workspace['block_model'],model)
        self.assertEqual(tonnage_grade(model,2.5,[0])[0]['volume_m3'],64000)
        params['grid_angles'][0]=90
        self.assertEqual(model['params']['grid_angles'][0],35)
        with self.assertRaises(ValueError):tasks_from_blocks(model,2.5,.5)
        with self.assertRaises(ValueError):estimate_model(p,bounds,[2,2,2],dict(params,discretization=[5,1,1]))

    def test_cancel_does_not_replace_existing_model(self):
        p=demo();p.workspace['block_model']={'blocks':[],'sentinel':True}
        with self.assertRaises(RuntimeError):
            estimate_model(p,[500000,5300000,1200,500040,5300040,1240],[20,20,20],
                           {'minimum':2,'neighbors':4},cancel=lambda:True)
        self.assertEqual(p.workspace['block_model'],{'blocks':[],'sentinel':True})


if __name__=='__main__':unittest.main()
