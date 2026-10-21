"""Exercise offline dependency data and project I/O inside the frozen executable."""
from pathlib import Path
from tempfile import TemporaryDirectory
from .core import Project,Collar,save_project,load_project
from .data_tools import transform_project
from .geometry import write_dxf,read_dxf
from .estimation import Estimator

def verify(project):
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
    from PySide6.QtCharts import QChart,QChartView,QScatterSeries
    chart=QChart();series=QScatterSeries();series.append(0,1);chart.addSeries(series);chart.createDefaultAxes();view=QChartView(chart);view.resize(200,100);view.show();view.close()
    return [implicit,envelope]
