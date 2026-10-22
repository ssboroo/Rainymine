"""CAD/GIS dig-line exports with source CRS and separate unknown polygons."""
from pathlib import Path
import json
import shutil
import tempfile


def export_diglines(rows,destination,crs):
    import ezdxf
    import shapefile
    from pyproj import CRS
    from shapely.geometry import Polygon
    from shapely.geometry.polygon import orient
    reference=CRS.from_user_input(crs)
    if not reference.is_projected or any(abs(a.unit_conversion_factor-1)>1e-9 for a in reference.axis_info[:2]):raise ValueError('Explicit projected metre CRS required')
    destination=Path(destination)
    if destination.exists():raise ValueError('Dig-line destination exists')
    stage=Path(tempfile.mkdtemp(prefix='.diglines-',dir=destination.parent))
    try:
        doc=ezdxf.new();doc.units=6;msp=doc.modelspace()
        with shapefile.Writer(str(stage/'diglines'),shapeType=shapefile.POLYGONZ,encoding='utf-8') as writer:
            writer.field('kind','C',20);writer.field('area_m2','F',20,4);writer.field('z_m','F',20,4)
            for row in rows:
                poly=orient(Polygon([p[:2] for p in row['outer']],[[p[:2] for p in r] for r in row['holes']]),sign=-1.)
                rings=[list(poly.exterior.coords)]+[list(r.coords) for r in poly.interiors]
                writer.polyz([[[x,y,row['elevation']] for x,y in ring] for ring in rings]);writer.record(row['kind'],row['area_m2'],row['elevation'])
                for ring in rings:msp.add_lwpolyline(ring,close=True,dxfattribs={'layer':row['kind'],'elevation':row['elevation']})
        doc.saveas(stage/'diglines.dxf');(stage/'diglines.prj').write_text(reference.to_wkt(version='WKT1_ESRI'));(stage/'diglines.cpg').write_text('UTF-8')
        metadata={'crs':reference.to_string(),'units':'metres','polygons':len(rows),'unknown_is_separate':True,'holes_preserved':True,'scope':'block-based material boundaries for professional review; not excavator guidance certification'}
        (stage/'metadata.json').write_text(json.dumps(metadata,indent=2));stage.rename(destination)
        return {'path':str(destination),**metadata}
    except BaseException:shutil.rmtree(stage,ignore_errors=True);raise
