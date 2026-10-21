import csv,gzip,io,json,sqlite3,tempfile,unittest,zipfile,hashlib
from pathlib import Path
from copy import deepcopy
import numpy as np
import pyarrow.parquet as pq
from rainymine.core import Project,Collar,Survey,Assay,Lithology
from rainymine.estimation import make_blocks
from rainymine.open_exchange import write_omf,write_geopackage,read_geopackage,write_exchange_bundle,contract
from rainymine.spatial import model_basis


def fixture():
    p=Project(collars=[Collar('Монгол-01',500000.000123,5300000.000234,1400,10)],surveys=[Survey('Монгол-01',0,0,-90)],assays=[Assay('Монгол-01',0,10,.75)],lithology=[Lithology('Монгол-01',0,10,'ORE')])
    p.crs_code='EPSG:32648';p.grade_unit='%';p.surface=[[500000,5300000,1400],[500010,5300010,1401],[500020,5300000,1402]]
    bounds=[500000,5300000,1400,500015,5300020,1410];angles=[35,-10,15]
    blocks=make_blocks(bounds,[10,10,10],grid_angles=angles)
    blocks[0]['grade']=0.;blocks[1]['grade']=None
    p.workspace={'block_model':{'bounds':bounds,'size':[10,10,10],'grid_origin':bounds[:3],'grid_angles':angles,'blocks':blocks},
                 'strings':[{'name':'Монгол хил','closed':True,'points':[[500000,5300000,1400],[500020,5300000,1401],[500020,5300020,1402]]}],
                 'meshes':[{'name':'UTM','vertices':[[500000.000123,5300000,1400],[500010,5300000,1401],[500010,5300010,1402]],'faces':[[0,1,2]]}]}
    return p


class OpenExchange(unittest.TestCase):
    def test_omf_official_schema_required_arrays_and_rotated_leaf_geometry(self):
        p=fixture();before=deepcopy(p);model=p.workspace['block_model'];basis=model_basis(model)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'Монгол.omf';report=write_omf(path,p)
            with zipfile.ZipFile(path) as z:
                self.assertEqual(z.comment,b'Open Mining Format 2.0-beta.1');index=json.loads(gzip.decompress(z.read('index.json.gz')))
                self.assertEqual(index['units'],'m');self.assertIn('UTM zone 48N',index['coordinate_reference_system'])
                element=next(e for e in index['elements'] if e['geometry']['type']=='BlockModel');g=element['geometry'];self.assertEqual(g['subblocks']['type'],'Freeform')
                table=pq.read_table(io.BytesIO(z.read(g['subblocks']['subblocks']['filename'])));self.assertTrue(all(not f.nullable for f in table.schema));self.assertEqual(str(table.schema.field('parent_u').type),'uint32');physical=pq.ParquetFile(io.BytesIO(z.read(g['subblocks']['subblocks']['filename']))).schema;self.assertEqual(physical.column(0).physical_type,'INT32');rows=table.to_pylist()
                for row,block in zip(rows,model['blocks']):
                    parent=np.array([row['parent_'+a] for a in 'uvw']);low=np.array([row['corner_min_'+a] for a in 'uvw']);high=np.array([row['corner_max_'+a] for a in 'uvw'])
                    center=np.array(index['origin'])+np.array(g['orient']['origin'])+(parent+(low+high)/2)*model['size']@basis.T
                    np.testing.assert_allclose(center,[block[k] for k in 'xyz'],atol=1e-8,rtol=0);np.testing.assert_allclose((high-low)*model['size'],[block[k] for k in ('dx','dy','dz')],atol=1e-8)
                attr=next(a for a in element['attributes'] if a['name']=='grade');values=pq.read_table(io.BytesIO(z.read(attr['data']['values']['filename']))).column('number').to_pylist()
                self.assertEqual(values[:2],[0.,None]);self.assertEqual(attr['units'],'%');self.assertEqual(report['format'],'OMF 2.0-beta.1')
        self.assertEqual(p,before)
    def test_sparse_subblocks_keep_real_sizes_ids_and_nulls(self):
        p=fixture();m=p.workspace['block_model'];b=m['blocks'][0];basis=model_basis(m);leaf=deepcopy(b)
        leaf.update(dict(zip('xyz',(np.array([b[k] for k in 'xyz'])-basis[:,0]*2.5).tolist())));leaf['dx']=5;leaf['block_id']='0:child';leaf['subblock_level']=1;m['blocks']=[leaf]
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'sparse.omf';write_omf(path,p)
            with zipfile.ZipFile(path) as z:
                index=json.loads(gzip.decompress(z.read('index.json.gz')));e=next(e for e in index['elements'] if e['geometry']['type']=='BlockModel');ref=e['geometry']['subblocks']['subblocks'];self.assertEqual(ref['item_count'],1)
                row=pq.read_table(io.BytesIO(z.read(ref['filename']))).to_pylist()[0];self.assertAlmostEqual(row['corner_max_u']-row['corner_min_u'],.5)
                self.assertIn('block_id',[a['name'] for a in e['attributes']])
    def test_reject_overlap_unknown_crs_and_atomic_cancel(self):
        p=fixture();p.workspace['block_model']['blocks'].append(deepcopy(p.workspace['block_model']['blocks'][0]))
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'existing.omf';path.write_bytes(b'previous')
            with self.assertRaisesRegex(ValueError,'давхардсан'):write_omf(path,p)
            self.assertEqual(path.read_bytes(),b'previous')
            with self.assertRaises(RuntimeError):write_omf(path,fixture(),lambda:True)
            self.assertEqual(path.read_bytes(),b'previous')
        p=fixture();p.crs_code=''
        with self.assertRaises(ValueError):contract(p)
        p.crs_code='EPSG:4326'
        with self.assertRaises(ValueError):contract(p)
    def test_geopackage_ogc_tables_crs_and_3d_layers(self):
        import fiona
        p=fixture()
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'Монгол.gpkg';report=write_geopackage(path,p)
            with sqlite3.connect(path) as db:
                self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0],'ok')
                self.assertEqual(db.execute('PRAGMA application_id').fetchone()[0],0x47504b47)
                self.assertTrue(all(r[0]==1 for r in db.execute('SELECT z FROM gpkg_geometry_columns')))
                metadata=json.loads(db.execute('SELECT metadata_json FROM rainymine_exchange').fetchone()[0]);self.assertEqual(metadata['grade_unit'],'%')
            with fiona.open(path,layer='collars') as source:
                self.assertEqual(source.crs.to_epsg(),32648);row=next(iter(source));self.assertEqual(tuple(row['geometry']['coordinates']),(500000.000123,5300000.000234,1400.))
            data=read_geopackage(path,'polygons');self.assertTrue(data['strings'][0]['closed']);self.assertFalse(data['z_assumed_zero']);self.assertEqual(data['strings'][0]['points'],p.workspace['strings'][0]['points'])
            self.assertEqual(len(read_geopackage(path,'collars')['points']),1);self.assertFalse(report['blocks_exported'])
    def test_gpkg_holes_and_atomic_cancel(self):
        import fiona
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'holes.gpkg'
            with fiona.open(path,'w',driver='GPKG',crs='EPSG:32648',schema={'geometry':'Polygon','properties':{'name':'str'}}) as f:
                f.write({'geometry':{'type':'Polygon','coordinates':[[[0,0],[10,0],[10,10],[0,0]],[[1,1],[2,1],[2,2],[1,1]]]},'properties':{'name':'hole'}})
            data=read_geopackage(path,'holes');self.assertTrue(data['z_assumed_zero']);self.assertEqual([s['ring_role'] for s in data['strings']],['exterior','hole'])
            old=path.read_bytes()
            with self.assertRaises(RuntimeError):write_geopackage(path,fixture(),lambda:True)
            self.assertEqual(path.read_bytes(),old)
    def test_csv_bundle_precision_nulls_metadata_and_hashes(self):
        p=fixture()
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'export.zip';write_exchange_bundle(path,p)
            with zipfile.ZipFile(path) as z:
                manifest=json.loads(z.read('manifest.json'));self.assertEqual(manifest['crs'],'EPSG:32648');self.assertEqual(manifest['block_model']['grid_angles'],[35,-10,15])
                for name,entry in manifest['files'].items():self.assertEqual(hashlib.sha256(z.read(name)).hexdigest(),entry['sha256'])
                rows=list(csv.DictReader(io.StringIO(z.read('blocks.csv').decode('utf-8-sig'))));self.assertEqual(rows[0]['grade'],'0');self.assertEqual(rows[1]['grade'],'')
                collars=list(csv.DictReader(io.StringIO(z.read('collars.csv').decode('utf-8-sig'))));self.assertEqual(float(collars[0]['x']),p.collars[0].x)
                from rainymine.geometry import read_obj
                obj=Path(folder)/'mesh.obj';obj.write_bytes(z.read('mesh-0001.obj'));self.assertEqual(read_obj(obj)['vertices'],p.workspace['meshes'][0]['vertices'])
                self.assertIn('structure.csv',z.namelist());self.assertIn('geotech.csv',z.namelist())
