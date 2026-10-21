"""Exercise offline dependency data and project I/O inside the frozen executable."""
from pathlib import Path
from tempfile import TemporaryDirectory
from .core import Project,Collar,save_project,load_project
from .data_tools import transform_project
from .geometry import write_dxf,read_dxf
from .estimation import Estimator,estimate_model
from .planning import optimize_schedule,haul_route,haul_capacity
from .benchmark import compare_reference

def verify_licensing():
    # Ephemeral test key only: never trusted by the application's public registry.
    import base64
    import json
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization
    from .licensing import LicenseManager, StateStore, TRIAL_SECONDS, canonical
    from .license_ui import LicenseDialog
    from PySide6.QtWidgets import QDialog
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    now = [1800000000]
    with TemporaryDirectory() as folder:
        manager = LicenseManager(StateStore(Path(folder), False), {'smoke': base64.b64encode(public).decode()}, 'smoke-device', lambda: now[0])
        assert manager.status().kind == 'not_started'
        assert manager.status(True).allowed
        now[0] += TRIAL_SECONDS
        assert not manager.status().allowed
        dialog = LicenseDialog(manager)
        assert not dialog.proceed.isEnabled()
        dialog.accept()
        assert dialog.result() != QDialog.DialogCode.Accepted
        dialog.close()
        payload = {'schema': 1, 'product': 'RAINYMINE', 'key_id': 'smoke', 'license_id': 'packaged-smoke', 'customer': 'Smoke', 'device_id': manager.device, 'not_before': now[0], 'expires_at': now[0] + 86400}
        path = Path(folder) / 'smoke.rainylic'
        path.write_text(json.dumps({'payload': payload, 'signature': base64.b64encode(private.sign(canonical(payload))).decode()}))
        assert manager.activate(path).kind == 'licensed'
        assert manager.status().allowed


def verify(project):
    verify_licensing()
    from .srs_tools import blend_materials,lithology_composites,swath_rows,survey_doglegs
    blend=blend_materials([{'id':'low','tonnes':100,'grade':1,'cost_per_tonne':1},
                           {'id':'high','tonnes':100,'grade':3,'cost_per_tonne':5}],100,2,2)
    assert blend['feasible'] and abs(blend['total_cost']-300)<1e-6
    assert lithology_composites(project,10)
    assert survey_doglegs(project)
    assert swath_rows([{'xyz':[0,0,0],'grade':2,'support_m':1}],{'blocks':[]})[0]['sample_grade']==2
    from .implicit import implicit_surface
    from .optimization import economic_pit,pit_mesh
    from .estimation import make_blocks
    from .exchange import xlsx_to_csv,read_stl,write_stl
    import sys
    if sys.platform=='win32':
        import pyodbc
        assert isinstance(pyodbc.drivers(),list)
    samples=[{'xyz':[500000+x,5300000+y,1200+z],'grade':x/100}
             for x in (0,100) for y in (0,100) for z in (0,100)]
    implicit,metadata=implicit_surface(samples,[500000,5300000,1200,500100,5300100,1300],.5,9)
    assert implicit['faces'] and metadata['sample_count']==8
    blocks=make_blocks([500200,5300000,1200,500220,5300020,1240],[20,20,20])
    for b in blocks:b['grade']=10 if b['k']==0 else 0
    pit=economic_pit({'blocks':blocks},2.7,100,.9,3,12)
    assert pit['selected_indices']==[0,1]
    envelope=pit_mesh({'blocks':blocks},pit['selected_indices'])
    p=transform_project(Project(collars=[Collar('CONTROL',105,0,100,10)]),'EPSG:4326','EPSG:32648')
    assert abs(p.collars[0].x-500000)<1e-5
    with TemporaryDirectory() as folder:
        root=Path(folder);save_project(root/'蒙古.rmine',project);restored=load_project(root/'蒙古.rmine')
        assert len(restored.workspace['block_model']['blocks'])==len(project.workspace['block_model']['blocks'])
        geometry={'strings':[{'name':'TEST','closed':True,'points':[[0,0,0],[10,0,0],[10,10,0],[0,10,0]]}]}
        write_dxf(root/'roundtrip.dxf',geometry);result,_=read_dxf(root/'roundtrip.dxf');assert len(result['strings'])==1
        write_stl(root/'implicit.stl',implicit);assert len(read_stl(root/'implicit.stl')['faces'])==len(implicit['faces'])
        from openpyxl import Workbook
        wb=Workbook();wb.active.append(['x','y','z']);wb.active.append([1,2,3]);wb.save(root/'values.xlsx');wb.close()
        xlsx_to_csv(root/'values.xlsx',root/'values.csv','Sheet');assert '1,2,3' in (root/'values.csv').read_text(encoding='utf-8-sig')
    samples=[{'hole_id':'A','xyz':[-1,0,0],'grade':0},{'hole_id':'B','xyz':[1,0,0],'grade':2}]
    r=Estimator(samples,{'method':'kriging','minimum':2,'neighbors':2}).predict([0,0,0]);assert abs(r['grade']-1)<1e-9
    advanced=estimate_model(project,[500000,5300000,1200,500040,5300040,1240],[20,20,20],
        {'method':'kriging','minimum':2,'neighbors':4,'radii':[1000,1000,1000],
         'variogram_ranges':[300,200,100],'variogram_angles':[35,-10,15],
         'grid_angles':[35,-10,15],'discretization':[2,2,2],'composite_length':20})
    assert all(b['grade'] is not None for b in advanced['blocks'])
    assert advanced['discretization']==[2,2,2]
    extension=estimate_model(project,[500000,5300000,1200,500040,5300040,1240],[40,40,40],
        {'minimum':1,'neighbors':4,'radii':[1000]*3,'composite_length':20,'subblock_levels':1,
         'faults':[{'name':'SMOKE','point':[500020,5300000,1200],'normal':[1,0,0]}]})
    assert len(extension['blocks'])==8
    optimized=optimize_schedule([{'id':'A','tonnes':1,'process_tonnes':1,'value':10,'predecessors':[]}],1,1,1)
    assert optimized['optimal'] and len(optimized['rows'])==1
    assert haul_capacity(haul_route([[0,0,0],[1000,0,0]],10),40,2,20,30,3,1,1,8,.8)['fleet_tonnes_per_shift']==3072
    with TemporaryDirectory() as folder:
        reference=Path(folder)/'reference.csv';reference.write_text('x,y,z,grade\n0,0,0,1\n')
        comparison=compare_reference({'blocks':[{'x':0,'y':0,'z':0,'grade':1}]},reference)
        assert comparison['numerical_pass'] and not comparison['independent_review_verified']
    from PySide6.QtCharts import QChart,QChartView,QScatterSeries
    chart=QChart();series=QScatterSeries();series.append(0,1);chart.addSeries(series);chart.createDefaultAxes();view=QChartView(chart);view.resize(200,100);view.show();view.close()

    from .local_support import answer,render_selection,candidates,OUT_OF_SCOPE
    from .local_engine import LocalEngine,default_paths
    assert render_selection('{"topic_ids":["import"]}',candidates('CSV импорт'))[1]=='import'
    import os
    model=os.environ.get('RAINYMINE_AI_SMOKE_MODEL')
    if model:
        engine=LocalEngine(default_paths()[0],model)
        try:
            engine.start()
            text,topic=answer('CSV импортын алдааг яаж засах вэ?',engine)
            assert topic=='import' and 'CSV UTF-8' in text
            assert answer('Rainymine ашиглаад хайрын шүлэг бич',engine)==(OUT_OF_SCOPE,None)
        finally:engine.stop()
    return [implicit,envelope]
