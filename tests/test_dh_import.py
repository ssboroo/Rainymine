import base64,csv,hashlib,io,tempfile,unittest,zlib
from copy import deepcopy
from pathlib import Path
from rainymine.dh_import import scan_sources,project_from_bundle,source_bytes,source_page,options,measurement
from rainymine.core import save_project,load_project


class DhImportTests(unittest.TestCase):
    def fixtures(self,folder):
        root=Path(folder)
        def write(name,fields,rows):
            with (root/name).open('w',encoding='utf-8-sig',newline='') as f:
                w=csv.writer(f);w.writerow(fields);w.writerows(rows)
        write('dh_collar.csv',['id','companyholeid','easting','northing','elevation','maxdepth','azimuth','dip','datum','projection','zone','height_datum'],[['42','MN-01',400000,6500000,100,10,360,-90,'GDA94','UTM',51,'EGM96']])
        write('dh_assay.csv',['companyholeid','fromdepth','todepth','attributecolumn','attributevalue','units','dsc'],[['MN-01',0,1,'Au','-0.1','PPM','LDL'],['MN-01',1,2,'Au','0','PPM',''],['MN-01',2,3,'Au','0.5','PPM',''],['MN-01',0,1,'Fe','25','PCT',''],['MN-01',3,4,'Au','NULL','PPM','']])
        write('dh_assay_pivoted.csv',['companyholeid','fromdepth','todepth','Au_PPM'],[['MN-01',0,1,-.1],['MN-01',1,2,0],['MN-01',2,3,.5]])
        write('dh_geology.csv',['collarid','fromdepth','todepth','attributecolumn','attributevalue','mrtdetailid'],[['42',0,5,'Lith1_Code','ORE',1],['42',5,10,'Lith1_Code','WASTE',2]])
        for kind in ['alteration','event','geotech','hyperspectral','recovery','specgrav']:
            (root/('dh_'+kind+'.csv')).write_text('aid,collarid,attributevalue\nNo data found\n',encoding='utf-8')
        return sorted(root.glob('dh_*.csv'))
    def test_archive_byte_exact_portable_and_core_projection(self):
        with tempfile.TemporaryDirectory() as folder:
            paths=self.fixtures(folder);bundle=scan_sources(paths);p,r=project_from_bundle(bundle,('dh_assay.csv','Au','PPM'),'Lith1_Code')
            self.assertEqual(r['collars'],1);self.assertEqual(r['active_assays'],2);self.assertEqual(r['active_lithology'],2);self.assertEqual(p.surveys,[])
            self.assertEqual(p.crs_code,'EPSG:28351');self.assertEqual(p.grade_unit,'ppm');self.assertEqual(p.collars[0].azimuth,0)
            self.assertEqual([a.grade for a in p.assays],[0,.5]);self.assertEqual(r['measurement_counts']['below_detection_excluded'],1)
            self.assertEqual(sum(f['empty_marker'] for f in bundle['files'].values()),6)
            output=Path(folder)/'project.rmine';save_project(output,p);restored=load_project(output)
            for path in paths:self.assertEqual(source_bytes(restored.workspace['dh_bundle'],path.name),path.read_bytes())
            self.assertEqual(source_page(bundle,'dh_hyperspectral.csv'),[])
    def test_half_detection_explicit_and_sources_not_doubled(self):
        with tempfile.TemporaryDirectory() as folder:
            b=scan_sources(self.fixtures(folder));before=deepcopy(b);p,r=project_from_bundle(b,('dh_assay.csv','Au','PPM'),policy='half_limit')
            self.assertEqual([a.grade for a in p.assays],[.05,0,.5]);self.assertEqual(b,before)
            iron,r=project_from_bundle(b,('dh_assay.csv','Fe','PCT'));self.assertEqual(iron.grade_unit,'%');self.assertEqual([a.grade for a in iron.assays],[25])
            self.assertIn(('dh_assay_pivoted.csv','Au','PPM'),options(b)['channels'])
    def test_ragged_comments_retained_and_paginated_without_becoming_lithology(self):
        with tempfile.TemporaryDirectory() as folder:
            paths=self.fixtures(folder);path=Path(folder)/'dh_geology.csv'
            with path.open('a',encoding='utf-8') as f:f.write('42,0,5,Comments,unquoted,comma,99\n')
            b=scan_sources(paths);p,r=project_from_bundle(b,lithology_column='Lith1_Code')
            self.assertEqual(len(p.lithology),2);self.assertEqual(len(r['source_parse_issues']),1)
            page=source_page(b,'dh_geology.csv',page=1,size=2);self.assertIn('_extra_columns',page[0]);self.assertIn('_parse_issue',page[0])
            self.assertEqual(source_bytes(b,'dh_geology.csv'),path.read_bytes())
    def test_overlapping_assays_all_held_out_and_orphan_reported(self):
        with tempfile.TemporaryDirectory() as folder:
            paths=self.fixtures(folder);path=Path(folder)/'dh_assay.csv'
            with path.open('a',encoding='utf-8') as f:f.write('MN-01,1.5,2.5,Au,1,PPM,\nUNKNOWN,4,5,Au,1,PPM,\n')
            p,r=project_from_bundle(scan_sources(paths),('dh_assay.csv','Au','PPM'))
            self.assertEqual(p.assays,[]);self.assertEqual(len(r['issues']),4)
    def test_mixed_crs_and_duplicate_collars_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            paths=self.fixtures(folder);path=Path(folder)/'dh_collar.csv'
            with path.open('a',encoding='utf-8') as f:f.write('43,MN-02,400000,6500000,100,10,0,-90,GDA94,UTM,50,EGM96\n')
            with self.assertRaisesRegex(ValueError,'өөр CRS'):project_from_bundle(scan_sources(paths))
    def test_large_long_table_does_not_hit_scientific_row_limit(self):
        with tempfile.TemporaryDirectory() as folder:
            paths=self.fixtures(folder);path=Path(folder)/'dh_geochemistry.csv'
            with path.open('w',encoding='utf-8') as f:
                f.write('collarid,attributecolumn,attributevalue\n')
                for i in range(100001):f.write('42,Cu,<1\n')
            b=scan_sources(paths+[path]);p,r=project_from_bundle(b)
            self.assertEqual(b['files']['dh_geochemistry.csv']['rows'],100001);self.assertEqual(p.assays,[])
            self.assertEqual(source_page(b,path.name,page=500,size=200)[0]['attributevalue'],'<1')
    def test_cancel_and_corrupt_or_oversized_archive_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            paths=self.fixtures(folder)
            with self.assertRaises(RuntimeError):scan_sources(paths,lambda:True)
            b=scan_sources(paths);b['files']['dh_collar.csv']['sha256']='0'*64
            with self.assertRaisesRegex(ValueError,'SHA256'):source_bytes(b,'dh_collar.csv')
    def test_numeric_qualifiers_missing_and_zero(self):
        self.assertEqual(measurement('<1','','exclude'),(None,'below_detection_excluded'))
        self.assertEqual(measurement('<1','','half_limit'),(.5,'below_detection_half_limit'))
        self.assertEqual(measurement('0','','exclude'),(0.,'measured'))
        self.assertEqual(measurement('NULL','','exclude'),(None,'missing'))
        self.assertEqual(measurement('>5','','half_limit'),(None,'upper_censored'))

    def test_existing_csv_import_routes_dh_files_to_bundle_dialog(self):
        from unittest.mock import Mock
        from rainymine.workbench import Workbench
        window=Mock()
        Workbench.import_data(window,'assays','/data/dh_assay.csv')
        window.dh_import_dialog.assert_called_once_with('/data')
        window.guard.assert_not_called()

    def test_pivot_unit_conflict_cannot_silently_relabel_percent_as_ppm(self):
        with tempfile.TemporaryDirectory() as folder:
            paths=self.fixtures(folder);path=Path(folder)/'dh_assay_pivoted.csv'
            path.write_text('companyholeid,fromdepth,todepth,Fe_PPM\nMN-01,0,1,25\n',encoding='utf-8')
            bundle=scan_sources(paths);self.assertEqual(options(bundle)['pivot_unit_conflicts'][0]['column'],'Fe_PPM')
            self.assertNotIn(('dh_assay_pivoted.csv','Fe','PPM'),options(bundle)['channels'])
            with self.assertRaisesRegex(ValueError,'unit'):project_from_bundle(bundle,('dh_assay_pivoted.csv','Fe','PPM'))
