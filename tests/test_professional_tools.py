import math
import tempfile
from pathlib import Path
from copy import deepcopy
import unittest
import numpy as np
from rainymine.cad import boolean_mesh,repair_mesh,transform_geometry,SnapIndex
from rainymine.formats import read_surpac,write_surpac,read_surpac_dtm,read_shapefile,las_preview,read_dem
from rainymine.mine_design import spiral_ramp,drill_ring,tunnel_network,stope_boxes
from rainymine.advanced_estimation import indicator_kriging,estimate_passes,blend_schedule
from rainymine.estimation import make_blocks,gamma_model,fit_variogram
from rainymine.geometry import mesh_report


def cube(position=(0,0,0)):
    import manifold3d as md
    output=md.Manifold.cube([2,2,2]).translate(position).to_mesh64()
    return {'name':'Cube','vertices':np.asarray(output.vert_properties)[:,:3].tolist(),'faces':np.asarray(output.tri_verts).tolist()}


class CadTools(unittest.TestCase):
    def test_boolean_analytic_volume_at_utm(self):
        a=cube((500000,5300000,1400));b=cube((500001,5300000,1400));before=deepcopy(a)
        for operation,expected in [('union',12),('intersection',4),('difference',4)]:
            mesh,report=boolean_mesh(a,b,operation)
            self.assertAlmostEqual(report['volume_m3'],expected);self.assertEqual(mesh_report(mesh)['open_edges'],0)
        self.assertEqual(a,before)
        self.assertIsNone(boolean_mesh(a,cube((500010,5300000,1400)),'intersection')[0])
        broken=cube();broken['faces']=broken['faces'][:-1]
        with self.assertRaises(ValueError):boolean_mesh(broken,b,'union')
    def test_repair_hole_and_transform(self):
        mesh=cube();mesh['faces']=mesh['faces'][:-2]
        fixed,report=repair_mesh(mesh,1e-8,3)
        self.assertGreater(report['before']['open_edges'],0);self.assertEqual(report['after']['open_edges'],0)
        moved=transform_geometry(fixed,[100,200,300],scale=[2,2,2])
        np.testing.assert_allclose(np.asarray(moved['vertices']).mean(axis=0),np.asarray(fixed['vertices']).mean(axis=0)+[100,200,300])
        self.assertAlmostEqual(abs(mesh_report(moved)['signed_volume_m3']),64)
    def test_exact_vertex_and_segment_snap(self):
        snap=SnapIndex([[500000,5300000,0],[500010,5300000,0]],[[0,1]])
        result=snap.nearest([500005,5300001,0],1.1)
        self.assertEqual(result['kind'],'segment');self.assertEqual(result['point'],[500005,5300000,0])
        self.assertIsNone(snap.nearest([500005,5300010,0],1))


class ExternalFormats(unittest.TestCase):
    def test_surpac_str_and_ascii_dtm(self):
        strings=[{'name':'triangle','points':[[500000,5300000,1],[500010,5300000,1],[500000,5300010,1]],'closed':True,'descriptions':[['A'],['B'],['C'],['A']]}]
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);path=root/'mesh.str';write_surpac(path,strings);read=read_surpac(path)
            self.assertEqual(read['strings'][0]['points'],strings[0]['points']);self.assertTrue(read['strings'][0]['closed']);self.assertEqual(read['strings'][0]['descriptions'][0],['A'])
            dtm=root/'mesh.dtm';dtm.write_text('mesh.str,\n0,0,0,0,END\nOBJECT,1\nTRISOLATION,1\n1,1,2,3\nEND\n')
            self.assertEqual(read_surpac_dtm(dtm)['faces'],[[0,1,2]])
            dtm.write_text('../mesh.str,\n')
            with self.assertRaises(ValueError):read_surpac_dtm(dtm)
    def test_shp_z_and_attributes_crs(self):
        import shapefile
        from pyproj import CRS
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'line.shp'
            with shapefile.Writer(str(path),shapeType=shapefile.POLYLINEZ) as writer:
                writer.field('NAME','C');writer.linez([[[500000,5300000,10],[500010,5300010,20]]]);writer.record('TEST')
            path.with_suffix('.prj').write_text(CRS.from_epsg(32648).to_wkt())
            result=read_shapefile(path);self.assertEqual(result['crs'],'EPSG:32648');self.assertEqual(result['strings'][0]['points'][1],[500010,5300010,20]);self.assertEqual(result['attributes'][0]['NAME'],'TEST')
    def test_las_laz_streaming_source_ids_and_filters(self):
        import laspy
        from pyproj import CRS
        with tempfile.TemporaryDirectory() as directory:
            header=laspy.LasHeader(point_format=3,version='1.2');header.offsets=[500000,5300000,1000];header.scales=[.001]*3;header.add_crs(CRS.from_epsg(32648))
            data=laspy.LasData(header);data.x=500000+np.arange(100)*.01;data.y=np.full(100,5300000.);data.z=np.full(100,1400.);data.intensity=np.arange(100,dtype=np.uint16);data.classification=np.arange(100,dtype=np.uint8)%3
            for extension in ('las','laz'):
                path=Path(directory)/('points.'+extension);data.write(path);result=las_preview(path,10,classes=[2],chunk_size=13)
                np.testing.assert_array_equal(result['source_index'],[20,50,80]);self.assertEqual(result['crs'],'EPSG:32648');self.assertEqual(result['source_points'],100)
                np.testing.assert_allclose(result['xyz'][:,0],500000+np.array([20,50,80])*.01,atol=1e-8)
    def test_geotiff_pixel_centres_and_nodata(self):
        import rasterio
        from rasterio.transform import from_origin
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'dem.tif';values=np.arange(16,dtype=np.float32).reshape(4,4);values[0,0]=-9999
            with rasterio.open(path,'w',driver='GTiff',width=4,height=4,count=1,dtype='float32',crs='EPSG:32648',transform=from_origin(500000,5300040,10,10),nodata=-9999) as dataset:dataset.write(values,1)
            mesh,metadata=read_dem(path);self.assertEqual(len(mesh['vertices']),15);self.assertEqual(len(mesh['faces']),16);self.assertEqual(metadata['crs'],'EPSG:32648')
            self.assertEqual(mesh['vertices'][0],[500015,5300035,1]);self.assertNotIn(-9999,[v[2] for v in mesh['vertices']])


class MineTools(unittest.TestCase):
    def test_spiral_every_segment_slope_and_width(self):
        mesh,line,report=spiral_ramp([500000,5300000],1400,1420,80,12,10,20,4)
        points=np.array(line['points']);delta=np.diff(points,axis=0);slopes=delta[:,2]/np.linalg.norm(delta[:,:2],axis=1)
        np.testing.assert_allclose(slopes,.1,atol=1e-8);self.assertAlmostEqual(points[-1,2],1420)
        vertices=np.array(mesh['vertices']);np.testing.assert_allclose(np.linalg.norm(vertices[::2]-vertices[1::2],axis=1),12,atol=1e-8)
        self.assertAlmostEqual(report['horizontal_length_m'],200)
    def test_tunnel_union_and_ring_geometry(self):
        mesh=tunnel_network([[0,0,0],[20,0,0],[20,20,0]],4,4)
        self.assertAlmostEqual(mesh_report(mesh)['signed_volume_m3'],624)
        holes=drill_ring([0,0,0],90,0,-60,60,7,20)
        self.assertEqual(len(holes),7)
        for h in holes:self.assertAlmostEqual(math.dist(*h['points']),20)
        np.testing.assert_allclose(holes[3]['points'][1],[20,0,0],atol=1e-8)
    def test_stope_boxes_nonoverlap_analytic_optimum(self):
        blocks=make_blocks([0,0,0,40,10,10],[10,10,10])
        for b in blocks:b['grade']=2
        result=stope_boxes({'blocks':blocks,'bounds':[0,0,0,40,10,10]},[2,1,1],1,10,2)
        self.assertTrue(result['optimal']);self.assertEqual(result['objective'],72000)
        selected=[i for s in result['selected'] for i in s['block_indices']];self.assertEqual(len(selected),len(set(selected)))


class EstimationTools(unittest.TestCase):
    def test_indicator_bounds_and_expanding_pass(self):
        samples=[{'hole_id':'A','xyz':[-10,0,0],'grade':0}, {'hole_id':'B','xyz':[10,0,0],'grade':2}]
        params={'minimum':2,'neighbors':2,'radii':[20,20,20],'range_m':100}
        result=indicator_kriging(samples,[0,0,0],1,params);self.assertAlmostEqual(result['probability'],.5);self.assertIsNone(result['grade'])
        rows,counts=estimate_passes(samples,[{'x':0,'y':0,'z':0}],[{**params,'radii':[1,1,1]},params])
        self.assertEqual(rows[0]['estimation_pass'],2);self.assertEqual(counts[0]['estimated'],0);self.assertAlmostEqual(rows[0]['grade'],1)
    def test_variogram_families_analytic_fit(self):
        for model in ('spherical','exponential','gaussian'):
            rows=[{'distance':float(x),'semivariance':float(gamma_model(x,.1,1.2,100,model)),'pairs':50} for x in np.linspace(10,200,20)]
            result=fit_variogram(rows,model)
            self.assertTrue(result['converged']);self.assertAlmostEqual(result['range_m'],100,places=3)
    def test_joint_feed_grade_and_precedence(self):
        tasks=[{'id':'W','tonnes':10,'process_tonnes':0,'grade':0,'value':-5,'predecessors':[]},
               {'id':'L','tonnes':50,'process_tonnes':50,'grade':1,'value':50,'predecessors':['W']},
               {'id':'H','tonnes':50,'process_tonnes':50,'grade':3,'value':50,'predecessors':['W']}]
        result=blend_schedule(tasks,100,100,2,2,2)
        self.assertTrue(result['optimal']);self.assertAlmostEqual(result['npv'],95)
        self.assertEqual(next(r['period'] for r in result['rows'] if r['id']=='W'),1)
        self.assertAlmostEqual(result['periods'][1]['feed_grade'],2)
        bad=deepcopy(tasks);bad[0]['predecessors']=['L']
        with self.assertRaises(ValueError):blend_schedule(bad,100,100,2,2,2)


class ContactAndPreview(unittest.TestCase):
    def test_contact_plane_and_fault_barrier(self):
        from rainymine.implicit_domains import contact_surface
        from rainymine.domains import fault_zone
        rows=[{'x':x,'y':y,'z':z,'value':x-5} for x in (0,10) for y in (0,3,7,10) for z in (0,10)]
        faults=[{'name':'F','point':[0,5,0],'normal':[0,1,0]}]
        mesh,report=contact_surface(rows,[0,0,0,10,10,10],11,faults=faults)
        self.assertEqual(len(report['fault_zone_counts']),2)
        for face in mesh['faces']:
            self.assertEqual(len({fault_zone(mesh['vertices'][i],faults) for i in face}),1)
            for i in face:self.assertAlmostEqual(mesh['vertices'][i][0],5,places=5)
    def test_gpu_preview_native_arrays_and_source_identity(self):
        from rainymine.large_view import parquet_preview,preview_polydata
        from rainymine.block_store import write_block_parquet
        model={'blocks':make_blocks([500000,5300000,1400,500100,5300010,1410],[10,10,10]),'bounds':[500000,5300000,1400,500100,5300010,1410]}
        for i,b in enumerate(model['blocks']):b['grade']=i
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'model.parquet';write_block_parquet(path,model,'EPSG:32648','%');payload=parquet_preview(path,maximum=4,cutoff=2)
            self.assertLessEqual(len(payload['xyz']),4);poly,origin=preview_polydata(payload)
            self.assertEqual(poly.GetPoints().GetData().GetDataTypeAsString(),'float')
            identifiers=poly.GetPointData().GetArray('source_index')
            for i in range(poly.GetNumberOfPoints()):
                index=identifiers.GetValue(i);np.testing.assert_allclose(np.array(poly.GetPoint(i))+origin,[model['blocks'][index][k] for k in 'xyz'],atol=1e-7)

class LidarExport(unittest.TestCase):
    def test_laz_filter_preserves_native_records_and_atomic_cancel(self):
        import laspy
        from pyproj import CRS
        from rainymine.formats import filter_las
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);header=laspy.LasHeader(point_format=3,version='1.2');header.add_crs(CRS.from_epsg(32648));header.offsets=[500000,5300000,1400];header.scales=[.001]*3
            data=laspy.LasData(header);data.x=500000+np.arange(10);data.y=np.full(10,5300000.);data.z=np.full(10,1400.);data.intensity=np.arange(10,dtype=np.uint16);data.red=np.arange(10,dtype=np.uint16)*10
            source=root/'in.las';target=root/'out.laz';data.write(source)
            report=filter_las(source,target,[500002,5300000,1400,500005,5300000,1400]);out=laspy.read(target)
            self.assertEqual(report['written_points'],4);np.testing.assert_array_equal(out.intensity,[2,3,4,5]);np.testing.assert_array_equal(out.red,[20,30,40,50]);self.assertEqual(out.header.parse_crs().to_epsg(),32648)
            before=target.read_bytes()
            with self.assertRaises(RuntimeError):filter_las(source,target,cancel=lambda:True)
            self.assertEqual(target.read_bytes(),before)
            with self.assertRaises(ValueError):filter_las(source,source)

class LithologyControls(unittest.TestCase):
    def test_logged_controls_only_and_no_invented_outside(self):
        from rainymine.core import Project,Collar,Lithology
        from rainymine.implicit_domains import lithology_constraints
        project=Project(collars=[Collar('A',500000,5300000,100,30)],lithology=[Lithology('A',0,10,'ORE'),Lithology('A',15,25,'HOST')])
        controls=lithology_constraints(project,'ORE',5)
        self.assertEqual(len(controls),4);self.assertEqual([r['value'] for r in controls],[1,1,-1,-1])
        self.assertAlmostEqual(controls[0]['z'],97.5);self.assertAlmostEqual(controls[2]['z'],82.5)
        with self.assertRaises(ValueError):lithology_constraints(project,'MISSING')

class LargeRayPicking(unittest.TestCase):
    def test_oriented_boxes_pick_original_id_and_reject_parallel_miss(self):
        from rainymine.large_view import pick_blocks_ray
        payload={'xyz':np.array([[500000,5300000,1400],[500020,5300000,1400]]),'sizes':np.full((2,3),10.),'source_index':np.array([100,200]),'grid_angles':[35,-10,15]}
        result=pick_blocks_ray([500000,5300000,1450],[0,0,-1],payload)
        self.assertEqual(result['source_index'],100)
        self.assertIsNone(pick_blocks_ray([500100,5300100,1450],[0,0,-1],payload))
