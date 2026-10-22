"""Independent row-level feasibility checks, separate from solver matrices."""
import math
from .core import finite


def audit_blend_schedule(tasks,rows,mining_capacity,processing_capacity,periods,minimum_grade,maximum_grade,discount=0.):
    finite(mining_capacity,processing_capacity,minimum_grade,maximum_grade,discount)
    if min(mining_capacity,processing_capacity)<=0 or not 0<=minimum_grade<=maximum_grade or not 0<=discount<1 or type(periods) is not int or periods<1:
        raise ValueError('Audit параметр буруу.')
    source={task['id']:task for task in tasks}
    if len(source)!=len(tasks):raise ValueError('Source ID давхардсан.')
    for task in tasks:
        finite(task['tonnes'],task['process_tonnes'],task['grade'],task['value'])
        if task['tonnes']<=0 or not 0<=task['process_tonnes']<=task['tonnes'] or task['grade']<0 or any(p not in source for p in task.get('predecessors',[])):
            raise ValueError('Source task буруу.')
    errors=[];selected={};by_period={p:[] for p in range(1,periods+1)}
    for row in rows:
        key=row.get('id');period=row.get('period')
        if key not in source:errors.append('unknown_task');continue
        if key in selected:errors.append('duplicate_task');continue
        if type(period) is not int or period not in by_period:errors.append('invalid_period');continue
        task=source[key]
        if any(row.get(k)!=task[k] for k in ('tonnes','process_tonnes','grade','value')):
            errors.append('task_values_changed')
        selected[key]=period;by_period[period].append(task)
    report=[];npv=0.
    for key,period in selected.items():
        if any(parent not in selected or selected[parent]>=period for parent in source[key].get('predecessors',[])):
            errors.append('precedence_violation')
    for period,chosen in by_period.items():
        mined=math.fsum(t['tonnes'] for t in chosen);feed=math.fsum(t['process_tonnes'] for t in chosen)
        metal=math.fsum(t['process_tonnes']*t['grade'] for t in chosen)
        tolerance=1e-6
        if mined>mining_capacity+tolerance:errors.append('mining_capacity')
        if feed>processing_capacity+tolerance:errors.append('processing_capacity')
        # Evaluate mass inequalities, including empty periods, without division.
        if metal<minimum_grade*feed-tolerance or metal>maximum_grade*feed+tolerance:errors.append('feed_grade')
        npv+=math.fsum(t['value'] for t in chosen)/(1+discount)**(period-1)
        report.append({'period':period,'mined_tonnes':mined,'feed_tonnes':feed,'feed_grade':metal/feed if feed else None})
    return {'passed':not errors,'violations':sorted(set(errors)),'periods':report,'npv':npv,
            'source_tasks':len(tasks),'scheduled_tasks':len(selected),
            'scope':'same-period processing; no stockpile; feasibility only',
            'independent_engineering_review':False}
