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

    def test_rotated_blocks_and_slices_follow_grid_axes(self):
        import numpy as np
        from rainymine.estimation import make_blocks
        from rainymine.spatial import search_basis
        p=demo();bounds=[500000,5300000,1200,500010,5300020,1230]
        angles=[35,-25,15];basis=search_basis(*angles);pivot=np.array(bounds[:3])
        blocks=make_blocks(bounds,[10,20,30],grid_angles=angles)
        blocks[0]['grade']=2
        p.workspace['block_model']={'blocks':blocks,'bounds':bounds,'grid_angles':angles,'grid_origin':bounds[:3]}
        for mode,expected in [('blocks',6),('slices',3)]:
            p.workspace['block_display']=mode;scene=Scene(NoRenderWindow());scene.load(p)
            poly=scene.sources['blocks'];self.assertEqual(poly.GetNumberOfCells(),expected)
            for i in range(poly.GetNumberOfPoints()):
                world=np.array(poly.GetPoint(i))+scene.origin
                grid=pivot+(world-pivot)@basis
                self.assertTrue(np.all(grid>=np.array(bounds[:3])-1e-7))
                self.assertTrue(np.all(grid<=np.array(bounds[3:])+1e-7))
            self.assertAlmostEqual(poly.GetCellData().GetScalars().GetRange()[0],2)

if __name__=='__main__':unittest.main()
