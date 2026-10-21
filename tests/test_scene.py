import unittest
import vtk
from rainymine.core import demo
from rainymine.scene import Scene

class NoRenderWindow:
    def __init__(self):self.window=vtk.vtkRenderWindow()
    def AddRenderer(self,r):self.window.AddRenderer(r)
    def GetInteractor(self):return None
    def Render(self):pass

class SceneTests(unittest.TestCase):
    def test_geometry_and_slab_clipping(self):
        scene=Scene(NoRenderWindow());scene.load(demo())
        self.assertGreater(scene.sources['holes'].GetNumberOfCells(),500)
        self.assertGreater(scene.sources['surface'].GetNumberOfPolys(),50)
        scene.set_section((90,0,80));mapper=scene.actors['holes'].GetMapper();mapper.Update();poly=mapper.GetInput()
        self.assertGreater(poly.GetNumberOfCells(),0)
        for i in range(poly.GetNumberOfPoints()):self.assertLessEqual(abs(poly.GetPoint(i)[0]),40.0001)
        scene.set_section(None);self.assertEqual(scene.actors['holes'].GetMapper().GetInput().GetNumberOfCells(),scene.sources['holes'].GetNumberOfCells())
    def test_large_coordinates_shifted(self):
        scene=Scene(NoRenderWindow());p=demo();scene.load(p)
        self.assertLess(max(abs(x) for x in scene.sources['holes'].GetBounds()),1000)
        xyz=scene.local((p.collars[0].x,p.collars[0].y,p.collars[0].z))
        for a,b,c in zip(xyz,scene.origin,(p.collars[0].x,p.collars[0].y,p.collars[0].z)):self.assertAlmostEqual(a+b,c)

if __name__=='__main__':unittest.main()
