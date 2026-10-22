"""Native stereonet view and vector PDF export."""
import math
from PySide6.QtCore import Qt,QRectF
from PySide6.QtGui import QPainterPath,QPen,QColor,QPdfWriter,QPageSize,QPainter
from PySide6.QtWidgets import QDialog,QVBoxLayout,QLabel,QPushButton,QGraphicsScene,QGraphicsView,QFileDialog


def show_histogram(parent,rows):
    from PySide6.QtCharts import QChart,QChartView,QBarSeries,QBarSet,QBarCategoryAxis
    dialog=QDialog(parent);dialog.setWindowTitle('Агуулгын histogram — support m');dialog.resize(950,600);layout=QVBoxLayout(dialog)
    chart=QChart();series=QBarSeries();values=QBarSet('Support m');values.append([r['support_m'] for r in rows]);series.append(values);chart.addSeries(series)
    axis=QBarCategoryAxis();axis.append([f'{r["from_grade"]:.2g}–{r["to_grade"]:.2g}' for r in rows]);axis.setLabelsAngle(-50);chart.addAxis(axis,Qt.AlignmentFlag.AlignBottom);series.attachAxis(axis);chart.createDefaultAxes()
    layout.addWidget(QChartView(chart));dialog.exec()


def show_stereonet(parent,report):
    dialog=QDialog(parent);dialog.setWindowTitle(report['projection']+' stereonet — screening');dialog.resize(760,820);layout=QVBoxLayout(dialog)
    scene=QGraphicsScene(0,0,700,700);view=QGraphicsView(scene);view.setRenderHint(QPainter.RenderHint.Antialiasing);layout.addWidget(view)
    pen=QPen(QColor('#bacbd4'));scene.addEllipse(70,70,560,560,QPen(QColor('#19364c')))
    for dip in (15,30,45,60,75):
        radius=(math.sqrt(2)*math.sin(math.radians(dip)/2) if report['projection']=='Schmidt' else math.tan(math.radians(dip)/2))*280
        scene.addEllipse(350-radius,350-radius,2*radius,2*radius,pen)
    for angle in range(0,360,30):
        r=math.radians(angle);scene.addLine(350,350,350+280*math.sin(r),350-280*math.cos(r),pen)
    for text,x,y in [('N',345,40),('E',650,342),('S',345,650),('W',35,342)]:scene.addText(text).setPos(x,y)
    screening={r['index']:r for r in report['plane_checks']}
    for pole in report['poles']:
        flag=screening.get(pole['index'],{});color=QColor('#b94e39') if flag.get('planar_screen') or flag.get('flexural_toppling_screen') else QColor('#008b92')
        x,y=350+pole['x']*280,350-pole['y']*280;item=scene.addEllipse(x-3,y-3,6,6,QPen(color),color);item.setToolTip(str(pole))
    scene.addText(report['projection']+' — geometric screening only').setPos(150,5)
    scene.addText('Angular rings • no factor of safety / engineering approval').setPos(110,675)
    label=QLabel('Lower-hemisphere poles; circles are angular-distance rings, not a full Wulff great-circle grid.\n'+report['scope']);label.setWordWrap(True);layout.addWidget(label)
    button=QPushButton('Вектор PDF хадгалах');layout.addWidget(button)
    def save():
        path,_=QFileDialog.getSaveFileName(dialog,'Stereonet PDF','Stereonet.pdf','PDF (*.pdf)')
        if not path:return
        writer=QPdfWriter(path);writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4));painter=QPainter(writer)
        try:scene.render(painter,QRectF(0,0,writer.width(),writer.width()),scene.sceneRect())
        finally:painter.end()
    button.clicked.connect(save);dialog.exec()
