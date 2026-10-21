"""Native 2026 workspace: live layers, viewport modes, block grid and local assistant."""
from pathlib import Path
import sys
from PySide6.QtCore import Qt, QSize, QAbstractTableModel, QModelIndex
from PySide6.QtGui import QColor, QIcon
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QDockWidget, QTabWidget, QSplitter, QTableView, QAbstractItemView, QHeaderView,
    QTreeWidgetItem, QToolButton, QButtonGroup, QScrollArea, QGroupBox)
from .advanced import AdvancedWorkbench
from .workbench import icon
from .theme import THEME


class BlockTableModel(QAbstractTableModel):
    """Lazy grid: never duplicate a large block model into millions of Qt items."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.blocks = []
        self.unit = ''
        self.maximum = 1.0

    def set_blocks(self, blocks, unit, maximum=1):
        self.beginResetModel()
        self.blocks = blocks
        self.unit = unit
        self.maximum = max(float(maximum), 1e-12)
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.blocks)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else 7

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal:
                return ['Дугаар', 'Зүүн (м)', 'Хойд (м)', 'Өндөр (м)',
                        'Агуулга (' + self.unit + ')', 'Нягт (т/м³)', 'Чулуулаг'][section]
            return str(section + 1)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self.blocks):
            return None
        block = self.blocks[index.row()]
        column = index.column()
        if role == Qt.ItemDataRole.DisplayRole:
            if column == 0:
                return str(index.row() + 1)
            value = block.get(('x', 'y', 'z', 'grade', 'density', 'lithology')[column - 1])
            if value is None and column == 6:
                value = block.get('domain')
            if value is None:
                return '—'
            return f'{value:,.3f}' if isinstance(value, (int, float)) else str(value)
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return int(Qt.AlignmentFlag.AlignVCenter | (Qt.AlignmentFlag.AlignLeft if column == 6 else Qt.AlignmentFlag.AlignRight))
        if role == Qt.ItemDataRole.BackgroundRole and column == 4 and block.get('grade') is not None:
            ratio = min(1., max(0., block['grade'] / self.maximum))
            return QColor.fromHsvF((1 - ratio) * .60, .27 + ratio * .16, 1.)
        if role == Qt.ItemDataRole.ToolTipRole:
            return 'Төслийн бодит блокийн өгөгдөл. — нь мэдээлэл байхгүйг заана.'


TEXT = {
    'Survey': 'Замнал', 'Стандарт /\nBlank / Dup': 'Хяналтын\nсорьц',
    'String /\nPolygon': 'Шугам /\nОлон өнцөгт', 'Breakline\nTIN': 'Тасралтын\nшугам',
    'Mesh\nшалгах': 'Тор\nшалгах', 'Блок модель\nүүсгэх': 'Блок загвар\nүүсгэх',
    'Домэйн\nPolygon': 'Домэйны\nхүрээ', 'Variogram\nба fit': 'Вариограмм\nтохируулах',
    'Cross-\nvalidation': 'Хөндлөн\nшалгалт', 'External\nBenchmark': 'Гадаад\nхарьцуулалт',
    'Fault\nPlane': 'Хагарлын\nхавтгай', 'Density /\nCutoff': 'Нягт /\nЗаагийн агуулга',
    'Ил уурхайн\nBench': 'Ил уурхайн\nмөргөцөг', 'Capacity\nSchedule': 'Хүчин чадлын\nхуваарь',
    'Хоёр\nviewport': 'Хос\nхарагдац', 'Local AI\nТуслах': 'Хиймэл оюуны\nтуслах',
    'RBF implicit\nгадарга': 'RBF хүдрийн\nгадарга', 'Pit\nоновчлол': 'Ил уурхайн\nоновчлол',
    'Geobank / SQL\nунших': 'Өгөгдлийн сан\nунших', 'CRS\nхөрвүүлэх': 'Координат\nхөрвүүлэх',
}


class WorkspaceWorkbench(AdvancedWorkbench):
    def __init__(self):
        self._workspace_ready = False
        self._table_sync = False
        super().__init__()
        self.setStyleSheet(THEME)
        self.setMinimumSize(1180, 740)
        screen = QApplication.primaryScreen()
        available = screen.availableGeometry() if screen else None
        self.resize(min(1600, max(1180, available.width()-24)) if available else 1600,
                    min(980, max(740, available.height()-24)) if available else 980)
        for scene in (self.scene, self.secondary):
            scene.renderer.SetBackground(.82, .90, .95)
            scene.renderer.SetBackground2(.97, .99, 1.)
            scene.renderer.GradientBackgroundOn()
        self._workspace_ready = True
        self.support.show()
        self.resizeDocks([self.layer_dock, self.support], [255, 320], Qt.Orientation.Horizontal)
        self.workspace_split.setSizes([570, 190])
        self.refresh_workspace()
        root = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[1]))
        self.setWindowIcon(QIcon(str(root / 'assets/rainymine-brand.svg')))

    def build_ui(self):
        super().build_ui()
        self.build_ribbon()
        # Reuse every existing layer/section control instead of replacing behavior.
        original = [dock for dock in self.findChildren(QDockWidget) if dock not in (self.layer_dock, self.support)]
        project_dock, section_dock, table_dock = original[:3]
        self.project_pages = QTabWidget()
        layer_panel = self.layer_dock.widget()
        layer_panel.setParent(None)
        self.project_pages.addTab(layer_panel, 'Давхаргууд')
        for dock, title in ((project_dock, 'Цооногууд'), (section_dock, 'Огтлол')):
            panel = dock.widget()
            panel.setParent(None)
            dock.setWidget(QWidget())
            dock.hide()
            self.removeDockWidget(dock)
            self.project_pages.addTab(panel, title)
        self.layer_dock.setWidget(self.project_pages)
        self.layer_dock.setWindowTitle('ТӨСЛИЙН ДАВХАРГУУД')
        self.layer_dock.setMinimumWidth(245)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.layer_dock)
        self.layer_list.setHeaderLabels(['Давхарга', 'Элемент'])
        self.layer_list.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.layer_list.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        # The bottom data grid belongs under the viewport, between the two sidebars.
        self.table.setParent(None)
        table_dock.setWidget(QWidget())
        table_dock.hide()
        self.removeDockWidget(table_dock)
        layout = self.centralWidget().layout()
        while layout.count():
            item = layout.takeAt(0)
            if item.widget() is not None and item.widget() is not self.split:
                item.widget().hide()
            if item.layout() is not None:
                for i in range(item.layout().count()):
                    widget = item.layout().itemAt(i).widget()
                    if widget is not None:
                        widget.hide()
        layout.setContentsMargins(5, 4, 5, 4)
        layout.setSpacing(4)
        viewbar = QWidget()
        row = QHBoxLayout(viewbar)
        row.setContentsMargins(3, 0, 3, 2)
        self.view_group = QButtonGroup(self)
        self.view_group.setExclusive(True)
        self.view_buttons = {}
        for mode, title in (('iso', 'Гурван хэмжээст'), ('section', 'Огтлол'), ('top', 'Төлөвлөгөө')):
            button = QToolButton()
            button.setText(title)
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, name=mode: self.change_workspace_view(name))
            self.view_group.addButton(button)
            self.view_buttons[mode] = button
            row.addWidget(button)
        self.view_buttons['iso'].setChecked(True)
        row.addStretch()
        self.workspace_title = QLabel()
        self.workspace_title.setObjectName('workspaceTitle')
        row.addWidget(self.workspace_title)
        layout.addWidget(viewbar)
        self.workspace_split = QSplitter(Qt.Orientation.Vertical)
        self.workspace_split.addWidget(self.split)
        self.data_tabs = QTabWidget()
        self.block_table = QTableView()
        self.block_model = BlockTableModel(self.block_table)
        self.block_table.setModel(self.block_model)
        self.block_table.setAlternatingRowColors(True)
        self.block_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.block_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.block_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.block_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.block_table.verticalHeader().hide()
        self.block_table.clicked.connect(self.block_row_selected)
        self.data_tabs.addTab(self.block_table, 'Блок загвар')
        self.data_tabs.addTab(self.table, 'Цооногийн өгөгдөл')
        self.workspace_split.addWidget(self.data_tabs)
        self.workspace_split.setStretchFactor(0, 4)
        self.workspace_split.setStretchFactor(1, 1)
        self.data_tabs.setMinimumHeight(120)
        layout.addWidget(self.workspace_split, 1)
        # The right panel reuses the bounded local-AI worker and reviewed help.
        help_panel = self.support.widget()
        help_panel.setParent(None)
        self.assistant_tabs = QTabWidget()
        self.assistant_tabs.addTab(help_panel, 'Тусламж')
        self.project_summary = QLabel()
        self.project_summary.setWordWrap(True)
        self.project_summary.setTextFormat(Qt.TextFormat.PlainText)
        self.project_summary.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.project_summary.setMargin(15)
        self.assistant_tabs.addTab(self.project_summary, 'Төсөл')
        self.support.setWidget(self.assistant_tabs)
        self.support.setWindowTitle('ХИЙМЭЛ ОЮУНЫ ТУСЛАХ')
        self.support.setMinimumWidth(295)
        self.support.setMaximumWidth(420)
        self.support.append('Ажлаа эхлүүлэх', '① Өгөгдөл оруулах\nАмсар, замнал, сорьц, гадаргын мэдээллээ импортлоно.\n\n② Тохиргоо хийх\nКоординат, огтлол, блок загварын параметрээ шалгана.\n\n③ Алдаа засах\nАсуултаа бичих эсвэл шалгасан зааврыг шууд сонгоно.')
        self.support.show()

    def build_ribbon(self):
        # Integrate advanced tools into the six categories shown in the reference.
        advanced = self.ribbon.widget(7)
        extra_groups = {}
        for button in list(advanced.findChildren(QToolButton)):
            label = button.text()
            target = 4 if label.startswith('Pit') else 1 if label.startswith(('Excel', 'Geobank')) else 2
            if target not in extra_groups:
                group = QGroupBox('Нэмэлт хэрэгсэл')
                QHBoxLayout(group).setContentsMargins(3, 0, 3, 18)
                self.ribbon.widget(target).layout().insertWidget(0, group)
                extra_groups[target] = group
            extra_groups[target].layout().addWidget(button)
        navigation = self.ribbon.widget(6)
        group = QGroupBox('Давхарга ба огтлол')
        QHBoxLayout(group).setContentsMargins(3, 0, 3, 18)
        for button in list(navigation.findChildren(QToolButton)):
            group.layout().addWidget(button)
        self.ribbon.widget(5).layout().insertWidget(0, group)
        self.ribbon.removeTab(7)
        self.ribbon.removeTab(6)
        advanced.deleteLater()
        navigation.deleteLater()
        names = ['Төсөл', 'Өрөмдлөг', 'Геологи', 'Блок загвар', 'Уурхайн төлөвлөлт', 'Харагдац']
        for index, name in enumerate(names):
            self.ribbon.setTabText(index, name)
        old = self.ribbon.widget(0)
        page = QWidget()
        row = QHBoxLayout(page)
        row.setContentsMargins(5, 3, 5, 3)
        actions = [('Шинэ', 'file', self.new), ('Нээх', 'folder', self.open), ('Хадгалах', 'save', self.save),
                   ('Оруулах', 'import', lambda: self.import_data('collars')),
                   ('Гаргах', 'export', self.export_blocks), ('Давхарга', 'layers', self.toggle_layers),
                   ('Огтлол', 'section', self.open_section_controls), ('Хэмжих', 'measure', lambda: self.measure.setChecked(not self.measure.isChecked())),
                   ('Хайх', 'search', self.focus_search), ('Шилжүүлэх', 'pan', self.pan_view),
                   ('Эргүүлэх', 'rotate', self.rotate_view), ('Томруулах', 'zoom', self.zoom_view),
                   ('Сонгох', 'pick', lambda: self.measure.setChecked(False)), ('Тохиргоо', 'gear', self.settings)]
        for title, kind, callback in actions:
            button = QToolButton()
            button.setText(title)
            button.setIcon(icon(kind))
            button.setIconSize(QSize(27, 27))
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            button.setMinimumWidth(66)
            button.clicked.connect(lambda checked=False, fn=callback: fn())
            row.addWidget(button)
        row.addStretch()
        self.ribbon.removeTab(0)
        self.ribbon.insertTab(0, page, 'Төсөл')
        old.deleteLater()
        for button in self.ribbon.findChildren(QToolButton):
            button.setText(TEXT.get(button.text(), button.text()))
        for group in self.ribbon.findChildren(QGroupBox):
            group.setTitle({'DTM / Solid': 'Гадарга / Биет', 'Загварын prototype': 'Туршилтын загвар'}.get(group.title(), group.title()))
        # Horizontal scrolling retains every tool on narrow screens.
        for index in range(self.ribbon.count()):
            content = self.ribbon.widget(index)
            content.setObjectName('ribbonPage')
            content.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            label = self.ribbon.tabText(index)
            self.ribbon.removeTab(index)
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            scroll.setWidget(content)
            self.ribbon.insertTab(index, scroll, label)
        self.ribbon.setIconSize(QSize(21, 21))
        for index, kind in enumerate(('folder', 'holes', 'layers', 'cube', 'pit', 'surface')):
            self.ribbon.setTabIcon(index, icon(kind))
        self.ribbon.setCurrentIndex(0)
        self.ribbon.setMinimumHeight(132)
        self.ribbon.setMaximumHeight(132)

    def focus_search(self):
        self.layer_dock.show()
        self.project_pages.setCurrentIndex(1)
        self.search.setFocus()

    def open_section_controls(self):
        self.layer_dock.show()
        self.project_pages.setCurrentIndex(2)
        self.change_workspace_view('section')

    def change_workspace_view(self, mode):
        self.slab.setChecked(mode == 'section')
        self.scene.view('north' if mode == 'section' else mode)
        self.view_buttons[mode].setChecked(True)

    def pan_view(self):
        values = self.params('Камерын шилжилт — метр', {'Зүүн': 0., 'Хойд': 0., 'Өндөр': 0.})
        if values is None:
            return
        def run():
            offset = [float(values[key]) for key in ('Зүүн', 'Хойд', 'Өндөр')]
            if not all(__import__('math').isfinite(value) for value in offset):
                raise ValueError('Шилжилт төгсгөлөг тоо байна.')
            camera = self.scene.renderer.GetActiveCamera()
            camera.SetPosition(*[a+b for a, b in zip(camera.GetPosition(), offset)])
            camera.SetFocalPoint(*[a+b for a, b in zip(camera.GetFocalPoint(), offset)])
            self.scene.renderer.ResetCameraClippingRange()
            self.scene.window.Render()
        self.guard(run)

    def rotate_view(self):
        self.scene.renderer.GetActiveCamera().Azimuth(15)
        self.scene.window.Render()

    def zoom_view(self):
        self.scene.renderer.GetActiveCamera().Dolly(1.2)
        self.scene.renderer.ResetCameraClippingRange()
        self.scene.window.Render()

    def layer_selected(self, item, *args):
        if item is None or item.data(0, Qt.ItemDataRole.UserRole) is None:
            return
        super().layer_selected(item, *args)

    def refresh_layers(self):
        if not hasattr(self, 'layer_list'):
            return
        self.updating_layers = True
        self.layer_list.clear()
        groups = {}
        for title in ('Төслийн өгөгдөл', 'Цооногууд', 'Блок загвар', 'Геометр ба уурхайн загвар'):
            group = QTreeWidgetItem([title, ''])
            self.layer_list.addTopLevelItem(group)
            groups[title] = group
        current = None
        for key, actor in self.scene.actors.items():
            if key == 'selected':
                continue
            name = 'Цооногууд' if key in ('holes', 'collars') else 'Блок загвар' if key == 'blocks' else 'Төслийн өгөгдөл' if key == 'surface' else 'Геометр ба уурхайн загвар'
            source = self.scene.sources.get(key)
            item = QTreeWidgetItem([self.layer_name(key), str(source.GetNumberOfCells() if source else 0)])
            item.setData(0, Qt.ItemDataRole.UserRole, key)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(0, Qt.CheckState.Checked if actor.GetVisibility() else Qt.CheckState.Unchecked)
            groups[name].addChild(item)
            if key == self.active_layer:
                current = item
        self.layer_list.expandAll()
        self.layer_list.setCurrentItem(current or next((g.child(0) for g in groups.values() if g.childCount()), None))
        self.updating_layers = False
        self.layer_selected(self.layer_list.currentItem())

    def refresh(self):
        super().refresh()
        if self._workspace_ready:
            self.refresh_workspace()

    def refresh_workspace(self):
        blocks = self.project.workspace.get('block_model', {}).get('blocks', [])
        self._table_sync = True
        self.block_model.set_blocks(blocks, self.project.grade_unit, self.scene.grade_max)
        self._table_sync = False
        self.workspace_title.setText(self.project.name)
        self.data_tabs.setTabText(0, f'Блок загвар · {len(blocks):,}')
        self.project_summary.setText(f'{self.project.name}\n\n{len(self.project.collars):,} цооног\n{len(self.project.assays):,} сорьц\n{len(blocks):,} блок\n\nКоординат: {self.project.crs_code or "Локал метр"}\nАгуулгын нэгж: {self.project.grade_unit}\n\nТөслийн мэдээлэл энэ самбарт локал харагдана. AI модельд төслийн өгөгдөл дамжуулахгүй.\n\nRAINY STUDIO · 90220101')

    def block_row_selected(self, index):
        if self._table_sync or not index.isValid():
            return
        block = self.block_model.blocks[index.row()]
        self.picked_info.setText(f'Блок #{index.row()}\nX {block["x"]:,.2f}  Y {block["y"]:,.2f}\nZ {block["z"]:,.2f}\nАгуулга: {block.get("grade")} {self.project.grade_unit}')
        self.active_layer = 'blocks'
        self.refresh_layers()

    def on_click(self, obj, event):
        super().on_click(obj, event)
        if not hasattr(self, 'block_table') or self.measure_mode:
            return
        import vtk
        x, y = self.vtk.GetEventPosition()
        picker = vtk.vtkCellPicker()
        picker.SetTolerance(.008)
        if picker.Pick(x, y, 0, self.scene.renderer):
            info = self.scene.identify(picker.GetActor(), picker.GetCellId())
            if info and 'block_index' in info:
                row = info['block_index']
                if row < self.block_model.rowCount():
                    self.block_table.selectRow(row)
                    self.block_table.scrollTo(self.block_model.index(row, 0))
