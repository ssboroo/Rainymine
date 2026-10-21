import unittest
from rainymine.estimation import Estimator, cross_validate

class AdditionalEstimators(unittest.TestCase):
    def samples(self):
        return [{'hole_id':str(i),'xyz':[x,0,0],'grade':g} for i,(x,g) in enumerate([(0,2),(2,6)])]
    def params(self,method,**extra):
        return dict(method=method,minimum=1,neighbors=2,radii=[100,100,100],nugget=0,partial_sill=1,range_m=10,**extra)
    def test_nearest_and_exact(self):
        est=Estimator(self.samples(),self.params('nearest'))
        self.assertEqual(est.predict([1.8,0,0])['grade'],6)
        self.assertEqual(est.predict([0,0,0])['status'],'exact_sample')
    def test_sk_analytic_single_sample(self):
        est=Estimator(self.samples()[:1],self.params('simple_kriging',known_mean=4))
        # spherical correlation at h/r=0.5 is 0.3125.
        r=est.predict([5,0,0])
        self.assertAlmostEqual(r['grade'],4+0.3125*(2-4))
        self.assertAlmostEqual(r['variance'],1-0.3125**2)
        self.assertEqual(est.predict([0,0,0])['variance'],0)
    def test_sk_far_support_returns_known_mean(self):
        est=Estimator(self.samples(),self.params('simple_kriging',known_mean=4))
        r=est.predict([20,0,0])
        self.assertAlmostEqual(r['grade'],4)
        self.assertAlmostEqual(r['variance'],1)
    def test_sk_requires_mean(self):
        with self.assertRaises(ValueError):Estimator(self.samples(),self.params('simple_kriging'))
    def test_no_support_and_cross_validation(self):
        est=Estimator(self.samples(),self.params('nearest'))
        self.assertIsNone(est.predict([1000,0,0])['grade'])
        result=cross_validate(self.samples(),self.params('nearest'))
        self.assertEqual(result['predicted'],2)
        self.assertAlmostEqual(result['rmse'],4)
