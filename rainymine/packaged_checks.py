"""Exercise offline dependency data and project I/O inside the frozen executable."""
from pathlib import Path
from tempfile import TemporaryDirectory
from .core import Project,Collar,save_project,load_project
from .data_tools import transform_project
from .geometry import write_dxf,read_dxf
from .estimation import Estimator,estimate_model
from .planning import optimize_schedule,haul_route,haul_capacity
from .benchmark import compare_reference

def verify(project):
    p=transform_project(Project(collars=[Collar('CONTROL',105,0,100,10)]),'EPSG:4326','EPSG:32648')
    assert abs(p.collars[0].x-500000)<1e-5
    with TemporaryDirectory() as folder:
        root=Path(folder);save_project(root/'蒙古.rmine',project);restored=load_project(root/'蒙古.rmine')
        assert len(restored.workspace['block_model']['blocks'])==len(project.workspace['block_model']['blocks'])
        geometry={'strings':[{'name':'TEST','closed':True,'points':[[0,0,0],[10,0,0],[10,10,0],[0,10,0]]}]}
        write_dxf(root/'roundtrip.dxf',geometry);result,_=read_dxf(root/'roundtrip.dxf');assert len(result['strings'])==1
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
