"""Exercise offline dependency data and project I/O inside the frozen executable."""
from pathlib import Path
from tempfile import TemporaryDirectory
from .core import Project,Collar,save_project,load_project
from .data_tools import transform_project
from .geometry import write_dxf,read_dxf
from .estimation import Estimator

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
    from PySide6.QtCharts import QChart,QChartView,QScatterSeries
    chart=QChart();series=QScatterSeries();series.append(0,1);chart.addSeries(series);chart.createDefaultAxes();view=QChartView(chart);view.resize(200,100);view.show();view.close()
