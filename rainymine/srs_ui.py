"""SRS analysis commands attached to the native workspace without changing project data."""
from PySide6.QtWidgets import QFileDialog, QMessageBox
from .core import export_trajectories, read_rows
from .srs_tools import lithology_composites, swath_rows, blend_materials
from .estimation import sample_support


class SrsTools:
    def build_srs_menu(self):
        menu=self.menuBar().addMenu('Шинжилгээ / SRS')
        for title,callback in [('Замналын арга / CSV…',self.desurvey_export),
                               ('Литологийн композит…',self.lithology_composite_report),
                               ('Swath X / Y / Z…',self.swath_report),
                               ('Survey огцом өөрчлөлт…',self.survey_dogleg_report),
                               ('Хүдэр холих LP…',self.blending_report)]:
            self.action(menu,title,callback)

    def desurvey_export(self):
        settings=self.params('Замнал экспорт — 3D үндсэн замнал minimum curvature хэвээр',
                             {'Арга':['minimum_curvature','balanced_tangential','radius_of_curvature']})
        if not settings:return
        path=self.destination('Замнал · '+settings['Арга'],'csv')
        if path:self.guard(lambda:export_trajectories(path,self.project,settings['Арга']))

    def lithology_composite_report(self):
        settings=self.params('Литологийн хилээр композитлох — логгүй чулуулаг орохгүй',{'Урт, м':5})
        if settings:self.guard(lambda:self.show_rows('Литологийн композит',lithology_composites(self.project,float(settings['Урт, м']))))

    def swath_report(self):
        def run():
            model=self.project.workspace.get('block_model')
            if not model:raise ValueError('Блок загвар үүсгэнэ үү.')
            settings=self.params('Swath — сорьцын урт / блокийн эзэлхүүнээр жинлэнэ',
                                 {'Тэнхлэг':['X','Y','Z'],'Өргөн, м':50,'Эхлэл, м':0,'Композит, м':5})
            if not settings:return
            rows=swath_rows(sample_support(self.project,float(settings['Композит, м'])),model,
                            settings['Тэнхлэг'],float(settings['Өргөн, м']),float(settings['Эхлэл, м']))
            self.swath_chart(rows,settings['Тэнхлэг'])
            self.show_rows('Swath — төвөөр ангилсан, өөр support-уудын харьцуулалт',rows)
        self.guard(run)

    def blending_report(self):
        path,_=QFileDialog.getOpenFileName(self,'CSV: hole_id, tonnes, grade, cost_per_tonne — нэгж ижил байна','','CSV (*.csv)')
        if not path:return
        def run():
            rows=read_rows(path,('hole_id','tonnes','grade','cost_per_tonne'))
            materials=[{'id':r['hole_id'],**{k:r[k] for k in ('tonnes','grade','cost_per_tonne')}} for r in rows]
            settings=self.params('Нэг үеийн feed LP — олборлолтын дарааллыг тооцохгүй',
                                 {'Зорилтот тонн':1000,'Доод агуулга':.5,'Дээд агуулга':1.})
            if not settings:return
            result=self.busy(lambda:blend_materials(materials,*[float(settings[k]) for k in ('Зорилтот тонн','Доод агуулга','Дээд агуулга')]))
            if not result['feasible']:
                QMessageBox.information(self,'Хольц боломжгүй','Нөөц тонн / агуулгын хязгаарт тохирох бүрэн хольц олдсонгүй.');return
            self.show_rows(f"Хольц · {result['tonnes']:,.2f} т · {result['grade']:.4f} {self.project.grade_unit} · зардал {result['total_cost']:,.2f}",result['rows'])
        self.guard(run)

    def swath_chart(self,rows,axis):
        from PySide6.QtCharts import QChart,QChartView,QLineSeries,QScatterSeries
        from PySide6.QtWidgets import QDialog,QVBoxLayout,QLabel
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QColor
        dialog=QDialog(self);dialog.setWindowTitle('Swath '+axis);dialog.resize(900,560)
        layout=QVBoxLayout(dialog);chart=QChart();chart.setTitle('Swath '+axis+' · '+self.project.grade_unit)
        for key,title,color in [('sample_grade','Сорьц · уртаар жинлэсэн','#008f92'),('block_grade','Блок · эзэлхүүнээр жинлэсэн','#bc784f')]:
            # Separate contiguous runs so gaps never become interpolated lines.
            run=None;previous=None;named=False
            points=QScatterSeries();points.setName(title);points.setColor(QColor(color));points.setMarkerSize(7)
            for row in rows:
                if row[key] is None:run=None;previous=None;continue
                if run is None or previous!=row['from_m']:
                    run=QLineSeries();run.setColor(QColor(color));chart.addSeries(run)
                x=(row['from_m']+row['to_m'])/2;run.append(x,row[key]);points.append(x,row[key]);previous=row['to_m']
            chart.addSeries(points)
        chart.createDefaultAxes()
        for a in chart.axes(Qt.Orientation.Horizontal):a.setTitleText(axis+' · м (блок / сорьцын төв)')
        for a in chart.axes(Qt.Orientation.Vertical):a.setTitleText(self.project.grade_unit)
        for series in chart.series():
            if isinstance(series,QLineSeries):
                for marker in chart.legend().markers(series):marker.setVisible(False)
        layout.addWidget(QChartView(chart));layout.addWidget(QLabel('Өөр support-уудын харьцуулалт. Хоосон интервалд шугам татахгүй. Хаахад CSV хүснэгт нээгдэнэ.'))
        dialog.exec()

    def survey_dogleg_report(self):
        from .srs_tools import survey_doglegs
        settings=self.params('Survey dogleg — алдааг автоматаар засахгүй',{'Босго, градус / 30 м':10})
        if settings:self.guard(lambda:self.show_rows('Survey dogleg',survey_doglegs(self.project,float(settings['Босго, градус / 30 м']))))
