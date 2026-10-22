"""Fact-only laboratory diagnostics; never invent a lab batch or rejection."""
import math
import numpy as np


def quality_advice(rows):
    issues=[]
    for r in rows:
        if not r.get('passed',False):
            issues.append({'row':r.get('row'),'sample_id':r.get('sample_id',''),'lab':r.get('lab') or 'Тодорхойгүй',
                           'batch':r.get('batch') or 'Тодорхойгүй','type':r['type'],'statistic':r.get('statistic'),
                           'action':'Лабораторийн эх бүртгэл, CRM/хязгаарыг нягталж дахин шинжлүүлэх эсэхийг мэргэжилтэн шийднэ.'})
    standard=[r for r in rows if r['type']=='standard'];duplicates=[r for r in rows if r['type']=='duplicate']
    return {'issues':issues,'text':f'QA/QC: {len(rows)} мөр; CRM {len(standard)}; duplicate {len(duplicates)}; тохируулсан босго давсан {len(issues)} мөр.\n'+
            '\n'.join(f"Мөр {r['row']}, {r['type']}, лаборатори {r['lab']}, багц {r['batch']}, statistic={r['statistic']}" for r in issues[:30])+
            '\nShewhart нь баталгаат SD-тай CRM-д хамаарна. Duplicate mean–absolute difference нь precision diagnostic; Thompson–Howarth загварын calibration автоматаар баталгаажаагүй.'}


def show_quality_charts(parent,rows):
    from PySide6.QtWidgets import QDialog,QVBoxLayout
    from PySide6.QtCharts import QChart,QChartView,QScatterSeries,QLineSeries
    from PySide6.QtGui import QColor
    crm=[r for r in rows if r['type']=='standard' and r.get('statistic') is not None]
    if crm:
        dialog=QDialog(parent);dialog.setWindowTitle('Shewhart CRM — certified SD');dialog.resize(900,550);layout=QVBoxLayout(dialog);chart=QChart();series=QScatterSeries();series.setName('CRM Z')
        for i,r in enumerate(crm,1):series.append(i,float(r['statistic']))
        chart.addSeries(series)
        for level in (-3,-2,0,2,3):
            line=QLineSeries();line.setName(str(level)+' SD');line.append(1,level);line.append(max(2,len(crm)),level);line.setColor(QColor('#b95a45') if abs(level)==3 else QColor('#99adb8'));chart.addSeries(line)
        chart.createDefaultAxes();layout.addWidget(QChartView(chart));dialog.exec()
    pairs=[r for r in rows if r['type']=='duplicate' and r.get('measured') is not None and r.get('expected') is not None]
    if pairs:parent.chart('Duplicate precision diagnostic — not a calibrated Thompson–Howarth model',
                          [{'pair_mean':(r['measured']+r['expected'])/2,'absolute_difference':abs(r['measured']-r['expected'])} for r in pairs],
                          'pair_mean','absolute_difference')
