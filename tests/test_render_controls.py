import unittest
from copy import deepcopy
import tempfile
from pathlib import Path
import numpy as np
from rainymine.core import Project,save_project,load_project
from rainymine.estimation import make_blocks
from rainymine.scene import Scene
from rainymine.render_controls import options,validate_camera,capture_camera,restore_camera
from rainymine.large_view import preview_polydata,interaction_lod


class SilentWindow:
    def __init__(self):
        import vtk
        self.window=vtk.vtkRenderWindow()
    def AddRenderer(self,r):self.window.AddRenderer(r)
    def GetInteractor(self):return None
    def Render(self):pass


def fixture():
    p=Project();blocks=make_blocks([500000,5300000,1000,500020,5300020,1020],[10]*3)
    for i,b in enumerate(blocks):b['grade']=None if i==0 else float(i)
    p.workspace['block_model']={'blocks':blocks,'bounds':[500000,5300000,1000,500020,5300020,1020],'size':[10]*3}
    p.workspace['block_display']='all';return p


class RenderTests(unittest.TestCase):
    def test_world_camera_roundtrip_survives_origin_change_and_file(self):
        p=fixture();scene=Scene(SilentWindow());scene.load(p);view=capture_camera(scene)
        p.workspace['camera_bookmarks']={'View':view}
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'view.rmine';save_project(path,p);loaded=load_project(path)
            scene.origin=tuple(np.array(scene.origin)+[100,20,30]);restore_camera(scene,loaded.workspace['camera_bookmarks']['View'])
            restored=capture_camera(scene)
            for key in ('position','focal_point','view_up'):np.testing.assert_allclose(restored[key],view[key])
            self.assertEqual(restored['parallel_scale'],view['parallel_scale'])
    def test_bad_render_recipes_and_degenerate_cameras_rejected(self):
        for value in ({'profile':'unknown'},{'clip_bounds':[0,0,0,0,1,1]},{'scalar_range':[2,1]},{'show_null_blocks':1}):
            with self.assertRaises(ValueError):options({'render_options':value})
        scene=Scene(SilentWindow());scene.load(fixture());view=capture_camera(scene);view['focal_point']=view['position']
        with self.assertRaises(ValueError):validate_camera(view)
    def test_clip_planes_keep_ids_and_do_not_change_source_or_grades(self):
        p=fixture();p.workspace['render_options']={'clip_bounds':[500001,5300001,1001,500019,5300019,1019],'profile':'quality','scalar_range':[0,10]}
        before=deepcopy(p.to_dict());scene=Scene(SilentWindow());scene.load(p);mapper=scene.actors['blocks'].GetMapper()
        self.assertEqual(mapper.GetNumberOfClippingPlanes(),6);self.assertEqual(mapper.GetScalarRange(),(0,10));self.assertTrue(scene.actors['blocks'].GetProperty().GetEdgeVisibility())
        self.assertIn('block_index',scene.sources['blocks'].GetCellData().GetArrayName(1));self.assertEqual(p.to_dict(),before)
        p.workspace['render_options']['clip_bounds']=None;scene.apply_render_controls();self.assertEqual(mapper.GetNumberOfClippingPlanes(),0)
    def test_null_visible_is_nan_and_selection_has_true_rotated_geometry(self):
        p=fixture();p.workspace['render_options']={'show_null_blocks':True};scene=Scene(SilentWindow());scene.load(p)
        self.assertTrue(np.isnan(scene.sources['blocks'].GetCellData().GetScalars().GetTuple1(0)))
        self.assertEqual(scene.identify(scene.actors['blocks'],0)['block_index'],0)
        self.assertEqual(scene.highlight_blocks([0,1],maximum=1),1);actor=scene.block_highlight
        self.assertFalse(actor.GetPickable());self.assertEqual(actor.GetMapper().GetInput().GetNumberOfPoints(),8)
        scene.highlight_blocks([]);self.assertIsNone(scene.block_highlight)
    def test_lod_budget_keeps_original_ids_scalars_and_sizes(self):
        n=100001;payload={'kind':'blocks','xyz':np.column_stack((np.arange(n),np.zeros(n),np.zeros(n))), 'sizes':np.ones((n,3)),'grade':np.arange(n,dtype=float),'source_index':np.arange(n,dtype=np.int64)*3}
        poly,_=preview_polydata(payload);lod=interaction_lod(poly,1000);out=lod.GetOutput();self.assertLessEqual(out.GetNumberOfPoints(),1000)
        for i in range(out.GetNumberOfPoints()):
            source=out.GetPointData().GetArray('source_index').GetTuple1(i);value=out.GetPointData().GetScalars().GetTuple1(i)
            self.assertEqual(source,value*3);self.assertEqual(out.GetPointData().GetArray('size').GetTuple3(i),(1.,1.,1.))
        self.assertEqual(poly.GetNumberOfPoints(),n)
