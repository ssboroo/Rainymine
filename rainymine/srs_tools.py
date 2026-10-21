"""Auditable SRS additions. Metres, project grade units and explicit support weights."""
import math
from scipy.optimize import linprog
from .core import finite, composite_assays


def lithology_composites(project, length=5):
    """Restart fixed-length bins at each logged lithology boundary; exclude unlogged rock.

    Assay support is intersected with each bin. Missing assay is never zero grade.
    """
    project.validate();finite(length)
    if length <= 0:raise ValueError('Композитын урт эерэг байна.')
    from .core import Project, Collar, Assay, composite_assays, MAX_ROWS
    if sum(math.ceil((r.to_m-r.from_m)/length) for r in project.lithology)>MAX_ROWS:
        raise ValueError('Композитын тоо хэт их.')
    assays={}
    for a in project.assays:assays.setdefault(a.hole_id,[]).append(a)
    result=[]
    for rock in project.lithology:
        # Translate this domain to zero, reusing the established support calculation.
        interval=rock.to_m-rock.from_m
        clipped=[Assay('domain',max(a.from_m,rock.from_m)-rock.from_m,
                       min(a.to_m,rock.to_m)-rock.from_m,a.grade)
                 for a in assays.get(rock.hole_id,[]) if a.to_m>rock.from_m and a.from_m<rock.to_m]
        domain=Project(collars=[Collar('domain',0,0,0,interval)],assays=clipped,grade_unit=project.grade_unit)
        for row in composite_assays(domain,length):
            result.append({**row,'hole_id':rock.hole_id,'from_m':row['from_m']+rock.from_m,
                           'to_m':row['to_m']+rock.from_m,'lithology':rock.rock})
    return result


def swath_rows(samples, model, axis='X', width=50, origin=0):
    """Length-weighted samples vs volume-weighted blocks in half-open centre bins.

    These are different supports, a diagnostic rather than an accuracy certificate.
    No-data bins are retained, and unestimated block volume is reported separately.
    """
    finite(width,origin)
    if axis not in 'XYZ' or len(axis)!=1 or width<=0:raise ValueError('Тэнхлэг / swath өргөн буруу.')
    index='XYZ'.index(axis);key=axis.lower();bins={}
    def bucket(coordinate):
        finite(coordinate);i=math.floor((coordinate-origin)/width)
        return bins.setdefault(i,{'sample_support_m':0.,'sample_sum':0.,'sample_count':0,
                                 'estimated_volume_m3':0.,'block_sum':0.,'block_count':0,'unestimated_volume_m3':0.})
    for s in samples:
        grade=s['grade'];weight=s['support_m'];finite(grade,weight)
        if weight<=0:raise ValueError('Сорьцын support эерэг байна.')
        b=bucket(s['xyz'][index]);b['sample_support_m']+=weight;b['sample_sum']+=weight*grade;b['sample_count']+=1
    for block in model['blocks']:
        sizes=[block[k] for k in ('dx','dy','dz')];finite(*sizes)
        if min(sizes)<=0:raise ValueError('Блокийн хэмжээ эерэг байна.')
        volume=math.prod(sizes);b=bucket(block[key]);b['block_count']+=1
        grade=block.get('grade')
        if grade is None:b['unestimated_volume_m3']+=volume
        else:
            finite(grade);b['estimated_volume_m3']+=volume;b['block_sum']+=volume*grade
    result=[]
    for i,b in sorted(bins.items()):
        sample=b['sample_sum']/b['sample_support_m'] if b['sample_support_m'] else None
        block=b['block_sum']/b['estimated_volume_m3'] if b['estimated_volume_m3'] else None
        result.append({'axis':axis,'from_m':origin+i*width,'to_m':origin+(i+1)*width,
                       'sample_grade':sample,'block_grade':block,
                       'difference':block-sample if block is not None and sample is not None else None,
                       **{k:v for k,v in b.items() if k not in ('sample_sum','block_sum')}})
    return result


def blend_materials(materials, target_tonnes, minimum_grade, maximum_grade):
    """Minimum-cost single-period divisible-feed LP. No precedence/mining schedule.

    Each feed has id, available tonnes, grade and cost per tonne. Grade units must
    match; costs must use one currency. Bounds and two weighted grade constraints
    are enforced by HiGHS. Infeasibility never produces a partial blend.
    """
    finite(target_tonnes,minimum_grade,maximum_grade)
    if target_tonnes<=0 or not 0<=minimum_grade<=maximum_grade:raise ValueError('Хольцын тонн / агуулгын хязгаар буруу.')
    if not materials or len(materials)>10000:raise ValueError('1–10000 материал оруулна.')
    ids=set();grades=[];costs=[];bounds=[]
    for m in materials:
        name=m['id']
        if not isinstance(name,str) or not name.strip() or name in ids:raise ValueError('Материалын ID хоосон / давхардсан.')
        ids.add(name);available=m['tonnes'];grade=m['grade'];cost=m['cost_per_tonne'];finite(available,grade,cost)
        if min(available,grade,cost)<0:raise ValueError('Материалын утга сөрөг байж болохгүй.')
        grades.append(grade);costs.append(cost);bounds.append((0,available))
    solution=linprog(costs,A_ub=[grades,[-g for g in grades]],
                        b_ub=[maximum_grade*target_tonnes,-minimum_grade*target_tonnes],
                        A_eq=[[1.]*len(materials)],b_eq=[target_tonnes],bounds=bounds,method='highs')
    if not solution.success:
        if solution.status==2:return {'feasible':False,'rows':[],'reason':'infeasible_capacity_or_grade'}
        raise ValueError('LP шийдэл олдсонгүй: '+solution.message)
    amounts=solution.x;tonnes=float(sum(amounts));grade=float(sum(x*g for x,g in zip(amounts,grades))/tonnes)
    tolerance=1e-7*max(1.,target_tonnes)
    if abs(tonnes-target_tonnes)>tolerance or any(x< -tolerance or x>b[1]+tolerance for x,b in zip(amounts,bounds)) or not minimum_grade-1e-7<=grade<=maximum_grade+1e-7:
        raise ValueError('LP үр дүнгийн үлдэгдэл зөвшөөрөгдөх хэмжээнээс их.')
    return {'feasible':True,'tonnes':tonnes,'grade':grade,'total_cost':float(solution.fun),
            'algorithm':'HiGHS continuous linear programming; single-period feed only',
            'rows':[{'id':m['id'],'tonnes':max(0.,float(x)),'grade':m['grade'],'cost_per_tonne':m['cost_per_tonne']}
                    for m,x in zip(materials,amounts)]}


def survey_doglegs(project, threshold=10):
    """True 3D tangent dogleg severity; azimuth wrap is handled by vectors."""
    from .core import direction,dot
    finite(threshold)
    if threshold<0:raise ValueError('Dogleg босго сөрөг байж болохгүй.')
    project.validate();groups={};rows=[]
    for station in project.surveys:groups.setdefault(station.hole_id,[]).append(station)
    for hole,stations in sorted(groups.items()):
        stations.sort(key=lambda s:s.depth)
        for a,b in zip(stations,stations[1:]):
            angle=math.degrees(math.acos(max(-1.,min(1.,dot(direction(a.azimuth,a.dip),direction(b.azimuth,b.dip))))))
            severity=angle*30/(b.depth-a.depth)
            rows.append({'hole_id':hole,'from_m':a.depth,'to_m':b.depth,'dogleg_degrees':angle,
                         'degrees_per_30m':severity,'flagged':severity>threshold})
    return rows
