import unittest
import tempfile
from pathlib import Path
from rainymine.core import Project,Collar,demo,save_project,load_project
from rainymine.viewing import styled_project,named_section
from rainymine.estimation import make_blocks
from rainymine.scene import Scene
from test_scene import NoRenderWindow

class DisplayStateTests(unittest.TestCase):
    def test_named_sections_styles_survive_save_and_do_not_mutate_source(self):
        original=Project(collars=[Collar('A',0,0,0,100)])
        p=styled_project(original,'holes',{'visible':False,'opacity':.25,'representation':'wireframe','color':[1,0,0]})
        p=named_section(p,'Хойд', [90,20,50]);p=named_section(p,'Хойд',[45,30,60])
        self.assertNotIn('layer_styles',original.workspace);self.assertEqual(len(p.workspace['sections']),1)
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'display.rmine';save_project(path,p);self.assertEqual(load_project(path).workspace,p.workspace)
    def test_invalid_settings_are_rejected(self):
        p=Project()
        for change in ({'opacity':2},{'opacity':float('nan')},{'visible':'false'},{'color':[1,2,0]},{'representation':'unknown'}):
            with self.assertRaises(ValueError):styled_project(p,'holes',change)
        for name,values in [('',[0,0,10]),('A',[360,0,10]),('A',[0,0,0])]:
            with self.assertRaises(ValueError):named_section(p,name,values)
    def test_scene_style_reversion_and_scalar_visibility(self):
        p=demo();p=styled_project(p,'holes',{'opacity':.3,'color':[1,0,0],'representation':'wireframe'})
        scene=Scene(NoRenderWindow());scene.load(p);a=scene.actors['holes']
        self.assertAlmostEqual(a.GetProperty().GetOpacity(),.3);self.assertEqual(a.GetMapper().GetScalarVisibility(),0)
        p=styled_project(p,'holes',{'color':None});scene.project=p;scene.apply_styles();self.assertEqual(a.GetMapper().GetScalarVisibility(),1)
        scene.project=styled_project(p,'holes',{'visible':False});scene.apply_styles();scene.select(p.collars[0].hole_id);self.assertFalse(scene.actors['selected'].GetVisibility())
    def test_pick_identity_survives_clipping(self):
        scene=Scene(NoRenderWindow());scene.load(demo());scene.set_section((90,0,100));mapper=scene.actors['holes'].GetMapper();mapper.Update()
        self.assertGreater(mapper.GetInput().GetNumberOfCells(),0)
        result=scene.identify(scene.actors['holes'],0);self.assertIn(result['hole_id'],[h.hole_id for h in scene.project.collars])
        self.assertIsNone(scene.identify(scene.actors['holes'],-1))
    def test_selected_hole_respects_slab_and_remains_selectable(self):
        p=demo();scene=Scene(NoRenderWindow());scene.load(p);scene.select(p.collars[0].hole_id);scene.set_section((90,0,100))
        actor=scene.actors['selected'];actor.GetMapper().Update();poly=actor.GetMapper().GetInput()
        for i in range(poly.GetNumberOfPoints()):self.assertLessEqual(abs(poly.GetPoint(i)[0]),50.0001)
        self.assertEqual(scene.selected_hole,p.collars[0].hole_id);self.assertEqual(actor.GetPickable(),0)
    def test_clipping_pipeline_survives_python_collection(self):
        import gc
        scene=Scene(NoRenderWindow());scene.load(demo());scene.set_section((90,0,100));gc.collect()
        mapper=scene.actors['holes'].GetMapper();mapper.Update();self.assertGreater(mapper.GetInput().GetNumberOfCells(),0)
    def test_color_legend_tracks_all_scalar_layers(self):
        p=Project();blocks=make_blocks([0,0,0,20,20,20],[10,10,10])
        for b in blocks:b['grade']=1.
        p.workspace['block_model']={'blocks':blocks,'bounds':[0,0,0,20,20,20],'size':[10,10,10]}
        scene=Scene(NoRenderWindow());scene.load(p);scene.visible('holes',False);self.assertTrue(scene.legend.GetVisibility())
        scene.visible('blocks',False);self.assertFalse(scene.legend.GetVisibility())
    def test_block_indices_and_shifted_slices(self):
        p=Project();blocks=make_blocks([0,0,0,20,20,20],[10,10,10])
        for i,b in enumerate(blocks):b['grade']=float(i)
        p.workspace['block_model']={'blocks':blocks,'bounds':[0,0,0,20,20,20],'size':[10,10,10]};p.workspace['block_slice_positions']=[5,5,5]
        scene=Scene(NoRenderWindow());scene.load(p);poly=scene.sources['blocks'];info=scene.identify(scene.actors['blocks'],0)
        self.assertEqual(info['grade'],blocks[info['block_index']]['grade']);self.assertEqual(poly.GetCellData().GetArray('block_index').GetNumberOfTuples(),poly.GetNumberOfCells())
        # All three planes now intersect the lower block rather than being fixed at model midpoints.
        self.assertEqual(info['block_index'],0)
        p.workspace['block_slice_positions']=[21,5,5]
        with self.assertRaises(ValueError):p.validate()

if __name__=='__main__':unittest.main()
