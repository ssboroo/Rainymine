import gc
import unittest
import numpy as np
from rainymine.optimization import nested_pits

class RoadmapTests(unittest.TestCase):
    def model(self):
        return {'blocks':[dict(i=0,j=0,k=0,x=0.,y=0.,z=0.,dx=1.,dy=1.,dz=1.,grade=10.)]}

    def test_rf_break_even_and_base_price(self):
        progress=[]
        report=nested_pits(self.model(),1,1,1,2,1,rf_start=.1,rf_end=.5,rf_step=.2,
                           progress=lambda a,b:progress.append((a,b)))
        rows=report['scenarios']
        self.assertEqual([r['selected_blocks'] for r in rows],[0,0,1])
        self.assertAlmostEqual(rows[-1]['net_value'],2.)
        self.assertAlmostEqual(rows[-1]['base_price_net_value'],7.)
        self.assertEqual(rows[-1]['added_indices'],[0])
        self.assertEqual(progress[-1],(3,3))
        self.assertTrue(report['all_nested'])
        self.assertFalse(report['engineering_review'])

    def test_bounds_and_cancellation(self):
        for kwargs in ({'rf_step':0},{'rf_start':2,'rf_end':1},{'rf_step':.001}):
            with self.assertRaises(ValueError):nested_pits(self.model(),1,1,1,2,1,**kwargs)
        with self.assertRaises(RuntimeError):nested_pits(self.model(),1,1,1,2,1,cancel=lambda:True)

    def test_vtk_buffers_survive_payload(self):
        from rainymine.large_view import preview_polydata
        payload=dict(xyz=np.array([[1.,2.,3.],[4.,5.,6.]]),sizes=np.ones((2,3)),
                     grade=np.array([.2,.8]),source_index=np.array([7,9]),kind='blocks')
        poly,origin=preview_polydata(payload)
        del payload;gc.collect()
        self.assertEqual(poly.GetPointData().GetArray('source_index').GetValue(1),9)
        self.assertAlmostEqual(poly.GetPointData().GetScalars().GetValue(1),.8,places=6)
        self.assertTrue(np.allclose(np.array(poly.GetPoint(0))+origin,[1,2,3]))
