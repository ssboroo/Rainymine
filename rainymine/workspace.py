"""Native 2026 workspace: live layers, viewport modes, block grid and local assistant."""
from pathlib import Path
import sys
from PySide6.QtCore import Qt, QSize, QAbstractTableModel, QModelIndex, QSettings, QTimer
from PySide6.QtGui import QColor, QIcon, QAction
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QDockWidget, QTabWidget, QSplitter, QTableView, QAbstractItemView, QHeaderView,
    QTreeWidgetItem, QToolButton, QButtonGroup, QScrollArea, QGroupBox, QToolBar,
    QComboBox, QDialog, QListWidget, QListWidgetItem, QLineEdit, QFormLayout,
    QPushButton, QSizePolicy, QMenu)
from .advanced import AdvancedWorkbench
from .workbench import icon
from .theme import THEME
from .icons import brand_icon, semantic_icon
from .presentation import CommandPalette
from .i18n import tr, language, set_language, UiLocalizer


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
                return tr(['Дугаар', 'Зүүн (м)', 'Хойд (м)', 'Өндөр (м)',
                        'Агуулга (' + self.unit + ')', 'Нягт (т/м³)', 'Чулуулаг'][section])
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
        self.labels_visible = False
        self.ribbon_collapsed = False
        self.focus_active = False
        self._table_sync = False
        super().__init__()
        self.setStyleSheet(THEME)
        self.setMinimumSize(1080, 720)
        screen = QApplication.primaryScreen()
        available = screen.availableGeometry() if screen else None
        self.resize(min(1600, max(1180, available.width()-24)) if available else 1600,
                    min(980, max(740, available.height()-24)) if available else 980)
        for scene in (self.scene, self.secondary):
            scene.renderer.SetBackground(.82, .90, .95)
            scene.renderer.SetBackground2(.97, .99, 1.)
            scene.renderer.GradientBackgroundOn()
        for scene in (self.scene, self.secondary):
            scene.configure_presentation()
        self._workspace_ready = True
        self.support.show()
        self.resizeDocks([self.layer_dock, self.support], [235, 285], Qt.Orientation.Horizontal)
        self.workspace_split.setSizes([570, 190])
        self.refresh_workspace()
        root = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[1]))
        self.title_label.setProperty('userText', True)
        self.setWindowIcon(brand_icon())
        self.tool_catalog = {b.property('commandSource'): b for i in range(self.ribbon.count()) for b in self.ribbon.widget(i).findChildren(QToolButton) if b.property('commandSource')}
        self.polish_controls()
        self.update_labels()
        if self.project.name.startswith('ЖИШЭЭ'):
            self.display_buttons['Тасалж харах'].setChecked(True)
            self.toggle_cutaway(True)
        self.localizer = UiLocalizer(self)
        self.set_language(QSettings('Rainy Studio', 'RAINYMINE').value('ui/language', 'mn'), persist=False)

    def enrich_demo(self):
        super().enrich_demo()
        if self.project.name.startswith('ЖИШЭЭ'):
            from .domains import fault_patch
            model = self.project.workspace['block_model']
            self.project.workspace['block_display'] = 'blocks'
            self.layer_checks['surface'].setChecked(True)
            bounds = model['bounds']
            fault = {'name': 'DEMO F1', 'point': [(bounds[i]+bounds[i+3])/2 for i in range(3)],
                     'normal': [1., .35, .15]}
            self.project.workspace.setdefault('meshes', []).append(fault_patch(fault, 240))
            # This plane is a visual example, not a fault constraint on estimated grades.

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
        self.layer_dock.setWindowTitle('Төслийн өгөгдөл')
        self.layer_dock.setMinimumWidth(215)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.layer_dock)
        self.layer_list.setHeaderLabels(['Давхарга', 'Элемент'])
        self.layer_list.header().setStretchLastSection(False)
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
        for mode, title in (('iso', '3D'), ('section', 'Огтлол'), ('top', 'Төлөвлөгөө')):
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
        self.help_scroller = QScrollArea()
        self.help_scroller.setWidgetResizable(True)
        self.help_scroller.setMinimumHeight(100)
        self.help_scroller.setWidget(help_panel)
        self.assistant_tabs.addTab(self.help_scroller, 'Тусламж')
        self.project_summary = QLabel()
        self.project_summary.setWordWrap(True)
        self.project_summary.setTextFormat(Qt.TextFormat.PlainText)
        self.project_summary.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.project_summary.setMargin(15)
        self.assistant_tabs.addTab(self.project_summary, 'Төсөл')
        self.support.setWidget(self.assistant_tabs)
        self.support.setWindowTitle('Локал туслах')
        self.support.setMinimumWidth(270)
        self.support.setMaximumWidth(420)
        note = help_panel.layout().itemAt(0).widget()
        note.setToolTip(note.text())
        note.setText('Программ ашиглах, тохируулах, алдаа засах локал туслах.')
        help_panel.layout().setContentsMargins(8,6,8,6)
        help_panel.layout().setSpacing(3)
        self.support.cancel_button.setText('Зогсоох')
        self.support.cancel_button.setToolTip('Зогсоох / Санах ой чөлөөлөх')
        self.support.status.setText('Шууд заавар сонгох эсвэл асуултаа бичнэ үү.')
        self.support.chat.setHtml("""
        <table cellspacing="4" cellpadding="2">
        <tr><td valign="top" style="color:#00b7b1;font-size:20px">①</td><td><b>Өгөгдөл оруулах</b><br/><span style="color:#647b91">Цооног, гадарга, сорьцын мэдээллээ импортлоно.</span></td></tr>
        <tr><td valign="top" style="color:#00b7b1;font-size:20px">②</td><td><b>Тохиргоо хийх</b><br/><span style="color:#647b91">Координат, блок загварын параметрээ шалгана.</span></td></tr>
        <tr><td valign="top" style="color:#00b7b1;font-size:20px">③</td><td><b>Алдаа засах</b><br/><span style="color:#647b91">Асуултаа бичих эсвэл шууд заавар сонгоно.</span></td></tr>
        </table>""")
        self.support.show()

        self.build_brand_controls()
        self.build_inspector()
        self.build_view_tools()

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
            button.setProperty('commandSource', button.text())
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
        for title in ('Төслийн өгөгдөл', 'Цооногууд', 'Блок загвар', 'Геометр / Уурхай'):
            group = QTreeWidgetItem([tr(title), ''])
            self.layer_list.addTopLevelItem(group)
            groups[title] = group
        current = None
        for key, actor in self.scene.actors.items():
            if key == 'selected':
                continue
            name = 'Цооногууд' if key in ('holes', 'collars') else 'Блок загвар' if key == 'blocks' else 'Төслийн өгөгдөл' if key == 'surface' else 'Геометр / Уурхай'
            source = self.scene.sources.get(key)
            display_name = tr(self.layer_name(key)) if key in ('holes','collars','surface','blocks') else self.layer_name(key)
            item = QTreeWidgetItem([display_name, str(source.GetNumberOfCells() if source else 0)])
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
        self.workspace_title.setText(tr(f'{len(blocks):,} блок'))
        self.brand_project.setText(self.project.name)
        self.brand_project.setToolTip(self.project.name)
        self.update_labels()
        self.apply_view_preferences()
        if hasattr(self, 'localizer'):
            self.localizer.apply(self)
        self.data_tabs.setTabText(0, tr(f'Блок загвар · {len(blocks):,}'))
        self.project_summary.setText(f'{self.project.name}\n\n{len(self.project.collars):,} цооног\n{len(self.project.assays):,} сорьц\n{len(blocks):,} блок\n\nКоординат: {self.project.crs_code or "Локал метр"}\nАгуулгын нэгж: {self.project.grade_unit}\n\nТөслийн мэдээлэл энэ самбарт локал харагдана. AI модельд төслийн өгөгдөл дамжуулахгүй.\n\nRAINY STUDIO · 90220101')
        if language()=='en':self.update_english_summary()

    def block_row_selected(self, index):
        if self._table_sync or not index.isValid():
            return
        block = self.block_model.blocks[index.row()]
        self.picked_info.setText(f'Блок #{index.row()}\nX {block["x"]:,.2f}  Y {block["y"]:,.2f}\nZ {block["z"]:,.2f}\nАгуулга: {block.get("grade")} {self.project.grade_unit}')
        self.active_layer = 'blocks'
        self.refresh_layers()
        self.show_block_properties(index.row())

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
                    self.show_block_properties(row)
                    self.block_table.selectRow(row)
                    self.block_table.scrollTo(self.block_model.index(row, 0))


    def build_brand_controls(self):
        """Retain main's branded masthead, keyboard tools and manual guide."""
        self.masthead = QToolBar('RAINYMINE', self)
        self.masthead.setObjectName('masthead')
        self.masthead.setMovable(False)
        panel = QWidget()
        panel.setObjectName('mastheadPanel')
        row = QHBoxLayout(panel)
        row.setContentsMargins(10, 5, 10, 5)
        logo = QLabel()
        logo.setPixmap(brand_icon().pixmap(30, 30))
        row.addWidget(logo)
        name = QLabel('RAINY<span style="color:#00a8ad">MINE</span>')
        name.setObjectName('wordmark')
        row.addWidget(name)
        year = QLabel('2026')
        year.setObjectName('projectTitle')
        row.addWidget(year)
        self.brand_project = QLabel()
        self.brand_project.setTextFormat(Qt.TextFormat.PlainText)
        self.brand_project.setProperty('userText', True)
        self.brand_project.setObjectName('projectTitle')
        self.brand_project.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        row.addWidget(self.brand_project, 1)
        search = QPushButton('Үйлдэл хайх · Ctrl K')
        search.setObjectName('commandSearch')
        search.setIcon(icon('search'))
        search.clicked.connect(self.command_palette)
        row.addWidget(search)
        self.language_combo = QComboBox()
        self.language_combo.setObjectName('languageSelector')
        self.language_combo.setAccessibleName('Language / Хэл')
        self.language_combo.addItem('Монгол', 'mn');self.language_combo.addItem('English', 'en')
        self.language_combo.activated.connect(lambda index: self.set_language(self.language_combo.itemData(index)))
        row.addWidget(self.language_combo)
        all_tools = QPushButton('Бүх хэрэгсэл')
        all_tools.setIcon(icon('grid'));all_tools.clicked.connect(self.open_tool_library)
        row.addWidget(all_tools)
        badge = QLabel('ОФФЛАЙН')
        badge.setObjectName('offlineBadge')
        row.addWidget(badge)
        panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.masthead.addWidget(panel)
        ribbon_bar = next(bar for bar in self.findChildren(QToolBar) if bar.windowTitle() == 'Ribbon')
        self.insertToolBar(ribbon_bar, self.masthead)
        self.insertToolBarBreak(ribbon_bar)
        self.ribbon.tabBarDoubleClicked.connect(lambda index: self.collapse_ribbon())
        self.ribbon.tabBar().setToolTip('Ctrl+F1: хэрэгслийн мөр хураах / дэлгэх')
        label_button = QToolButton()
        label_button.setText('Шошго')
        label_button.setIcon(icon('label'))
        label_button.setCheckable(True)
        label_button.toggled.connect(self.toggle_labels)
        self.view_buttons['iso'].parentWidget().layout().insertWidget(3, label_button)
        self.labels_button = label_button
        self.panels_menu = self.menuBar().addMenu('Самбарууд')
        for dock in (self.layer_dock, self.support):
            self.panels_menu.addAction(dock.toggleViewAction())
        self.action(self.panels_menu, 'Бүх хэрэгсэл', self.open_tool_library, 'Ctrl+Shift+P')
        self.data_action = QAction('Өгөгдлийн хүснэгт', self)
        self.data_action.setCheckable(True)
        self.data_action.setChecked(True)
        self.data_action.toggled.connect(self.data_tabs.setVisible)
        self.panels_menu.addAction(self.data_action)
        self.action(self.panels_menu, 'Үйлдэл хайх', self.command_palette, 'Ctrl+K')
        self.action(self.panels_menu, 'Хэрэгслийн мөр хураах / дэлгэх', self.collapse_ribbon, 'Ctrl+F1')
        self.action(self.panels_menu, '3D төвлөрсөн горим', self.focus_workspace, 'F10')
        guide = QWidget()
        guide_layout = QVBoxLayout(guide)
        for title, description, callback in (
            ('① Өгөгдөл оруулах', 'Амсар, замнал, сорьцын CSV мэдээллээ импортлоно.', lambda: self.import_data('collars')),
            ('② Загвар тохируулах', 'Блокийн хэмжээ, домэйн, үнэлгээний параметрээ тохируулна.', self.block_dialog),
            ('③ Чанар шалгах', 'Сорьцын бүрхэлт, интервалын алдааг шалгана.', self.qaqc)):
            button = QPushButton(title)
            button.clicked.connect(lambda checked=False, fn=callback: fn())
            guide_layout.addWidget(button)
            note = QLabel(description)
            note.setWordWrap(True)
            guide_layout.addWidget(note)
        guide_layout.addStretch()
        self.assistant_tabs.addTab(guide, 'Эхлэх')

    def polish_controls(self):
        for button in self.findChildren(QToolButton):
            title = button.text().replace('\n', ' ').strip()
            if title:
                button.setAccessibleName(title)
                if not button.toolTip():
                    button.setToolTip(title)
                button.setIcon(semantic_icon(button.text(), button.icon()))
        self.workspace_title.setTextFormat(Qt.TextFormat.PlainText)
        self.search.setClearButtonEnabled(True)
        self.search.setAccessibleName('Цооногийн нэрээр хайх')
        self.search.addAction(icon('search'), self.search.ActionPosition.LeadingPosition)

    def update_labels(self):
        for scene in (getattr(self, 'scene', None), getattr(self, 'secondary', None)):
            if scene:
                visible = scene.actors.get('holes') and scene.actors['holes'].GetVisibility() and scene.section is None
                for label in scene.labels:
                    label.SetVisibility(bool(visible and (self.labels_visible or label.GetInput() == scene.selected_hole)))
                    label.GetTextProperty().SetOrientation(0)
                scene.window.Render()

    def toggle_labels(self, value):
        self.labels_visible = value
        self.update_labels()

    def show_hole(self, name):
        super().show_hole(name)
        if self._workspace_ready:
            self.update_labels()

    def update_section(self, *args):
        super().update_section(*args)
        if self._workspace_ready:
            self.update_labels()

    def change_layer(self, key, changes):
        super().change_layer(key, changes)
        if self._workspace_ready:
            self.update_labels()

    def collapse_ribbon(self):
        self.ribbon_collapsed = not self.ribbon_collapsed
        self.ribbon.setFixedHeight(36 if self.ribbon_collapsed else 132)

    def focus_workspace(self):
        items = (self.layer_dock, self.support, self.data_tabs, self.ribbon)
        if not self.focus_active:
            self._focus_visibility = [not item.isHidden() for item in items]
            for item in items:
                item.hide()
        else:
            for item, visible in zip(items, self._focus_visibility):
                item.setVisible(visible)
        self.focus_active = not self.focus_active

    def command_palette(self):
        entries = []
        seen = set()
        for button in self.ribbon.findChildren(QToolButton):
            title = button.text().replace('\n', ' ').strip()
            if title and title not in seen:
                seen.add(title)
                entries.append((title, button.click, button.isEnabled()))
        for action in self.findChildren(QAction):
            title = action.text().replace('&', '').strip()
            if title and title not in seen and not action.isSeparator():
                seen.add(title)
                entries.append((title, action.trigger, action.isEnabled()))
        CommandPalette(self, entries).exec()

    def createPopupMenu(self):
        menu = QMenu(self)
        for dock in (self.layer_dock, self.support):
            menu.addAction(dock.toggleViewAction())
        menu.addAction(self.data_action)
        return menu

    def build_inspector(self):
        # The assistant remains live; the inspector uses the same selected block as the grid.
        panel = QWidget()
        layout = QVBoxLayout(panel);layout.setContentsMargins(0,0,0,0)
        layout.addWidget(self.assistant_tabs, 3)
        group = QGroupBox('Сонгосон блокийн шинж')
        group.setObjectName('blockInspector')
        self.inspector_form = QFormLayout(group)
        self.inspector_form.setContentsMargins(10,22,10,8)
        self.inspector_form.setVerticalSpacing(3)
        self.inspector_values = {}
        for key, title in (('index','Дугаар'),('x','Зүүн (м)'),('y','Хойд (м)'),
                           ('z','Өндөр (м)'),('grade','Агуулга'),('density','Нягт (т/м³)'),
                           ('domain','Домэйн'),('dimensions','Тор')):
            value = QLabel('—');value.setTextFormat(Qt.TextFormat.PlainText)
            value.setProperty('userText', True);value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self.inspector_values[key] = value
            self.inspector_form.addRow(title, value)
        layout.addWidget(group, 1)
        self.support.setWidget(panel)

    def show_block_properties(self, row):
        if not 0 <= row < self.block_model.rowCount():
            return
        block = self.block_model.blocks[row]
        fields = dict(block, index=row+1,
                      dimensions=' × '.join(f'{block.get(k, 0):g}' for k in ('dx','dy','dz'))+' m')
        for key, label in self.inspector_values.items():
            value = fields.get(key)
            label.setText('—' if value is None else f'{value:,.3f}' if isinstance(value,(int,float)) and key!='index' else str(value))

    def build_view_tools(self):
        bar = self.view_buttons['iso'].parentWidget().layout()
        self.display_buttons = {}
        for text, kind, callback in (
            ('Тор', 'grid', self.toggle_coordinate_grid),
            ('Тасалж харах', 'section', self.toggle_cutaway),
            ('Блокийн ирмэг', 'cube', self.toggle_block_edges),
            ('Камер сэргээх', 'expand', lambda value=False: self.scene.reset())):
            button = QToolButton();button.setText(text);button.setToolTip(text)
            button.setIcon(icon(kind));button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
            button.setCheckable(text != 'Камер сэргээх')
            button.setChecked(text in ('Тор','Блокийн ирмэг'))
            button.clicked.connect(callback)
            bar.insertWidget(bar.count()-1, button)
            self.display_buttons[text] = button
            self.action(self.panels_menu, text, button.click)
        self.status_contact = QLabel('RAINY STUDIO · 90220101')
        self.statusBar().addPermanentWidget(self.status_contact)

    def toggle_coordinate_grid(self, value):
        for scene in (self.scene,self.secondary):
            if scene and scene.coordinate_grid:
                scene.coordinate_grid.SetVisibility(value)
                if scene.coordinate_text:scene.coordinate_text.SetVisibility(value)
                scene.window.Render()

    def toggle_cutaway(self, value):
        for scene in (self.scene,self.secondary):
            if scene:scene.set_cutaway(value)
        self.update_labels()

    def toggle_block_edges(self, value):
        for scene in (self.scene,self.secondary):
            if scene and 'blocks' in scene.actors:
                scene.actors['blocks'].GetProperty().SetEdgeVisibility(value);scene.window.Render()

    def tool_entries(self):
        entries = [];seen=set()
        for index in range(self.ribbon.count()):
            category = self.ribbon.tabText(index)
            for button in self.ribbon.widget(index).findChildren(QToolButton):
                title = button.text().replace('\n',' ').strip()
                if title and title not in seen:
                    entries.append((category, title, button.click, button.isEnabled(), button.icon()))
                    seen.add(title)
        return entries

    def open_tool_library(self):
        dialog = QDialog(self);dialog.setWindowTitle(tr('Бүх хэрэгсэл'));dialog.resize(760,620)
        layout = QVBoxLayout(dialog)
        search = QLineEdit();search.setPlaceholderText(tr('Үйлдэл хайх'));layout.addWidget(search)
        tools = QListWidget();layout.addWidget(tools,1)
        entries = self.tool_entries()
        for index,(category,title,callback,enabled,tool_icon) in enumerate(entries):
            item = QListWidgetItem(tool_icon, category+'  /  '+title)
            item.setData(Qt.ItemDataRole.UserRole,index)
            if not enabled:item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
            tools.addItem(item)
        def filter_items(query):
            for i in range(tools.count()):
                tools.item(i).setHidden(query.casefold() not in tools.item(i).text().casefold())
        search.textChanged.connect(filter_items)
        def launch(item):
            callback=entries[item.data(Qt.ItemDataRole.UserRole)][2]
            dialog.accept();QTimer.singleShot(0,callback)
        tools.itemActivated.connect(launch)
        dialog.exec()

    def set_language(self, code, persist=True):
        if code not in ('mn','en'):code='mn'
        set_language(code, self, persist=persist)
        from .support_knowledge import TOPICS
        from .support_knowledge_en import localize
        for index,topic in enumerate(TOPICS,1):self.support.manual.setItemText(index,localize(topic,code)['title'])
        self.support.manual.setItemText(0,tr('Зааврыг шууд үзэх — модель шаардахгүй'))
        self.language_combo.setCurrentIndex(self.language_combo.findData(code))
        self.block_model.headerDataChanged.emit(Qt.Orientation.Horizontal,0,6)
        self.refresh_layers()
        if self._workspace_ready:self.refresh_workspace()
        # The initial reviewed guide is static; user conversations are never rewritten.
        if not getattr(self.support, '_conversation_started', False):
            self.support.chat.setPlainText(
                'Welcome to RAINYMINE.\n\n1. Import collars → surveys → assays.\n2. Check coordinates and units before estimation.\n3. Use All tools or Ctrl+K to find any command.\n\nLocal assistant: application support only. No project data is sent to a cloud service.'
                if code=='en' else
                'RAINYMINE-д тавтай морил.\n\n1. Амсар → замнал → сорьц дарааллаар импортлоно.\n2. Үнэлгээний өмнө координат, нэгжээ шалгана.\n3. Бүх хэрэгсэл эсвэл Ctrl+K-ээр хэрэгслээ хайна.\n\nЛокал туслах зөвхөн программын заавар өгнө. Төслийн өгөгдлийг үүлэн үйлчилгээ рүү илгээхгүй.')
        if code=='en':
            blocks=self.project.workspace.get('block_model',{}).get('blocks',[])
            self.project_summary.setText(f'{self.project.name}\n\n{len(self.project.collars):,} drillholes\n{len(self.project.assays):,} assays\n{len(blocks):,} blocks\n\nCRS: {self.project.crs_code or "Local metres"}\nGrade unit: {self.project.grade_unit}\n\nProject data stays local and is never passed to the assistant model.\n\nRAINY STUDIO · 90220101')
        for scene in (self.scene,self.secondary):
            if scene:
                scene.legend.SetTitle(('Grade ' if code=='en' else 'Агуулга ')+self.project.grade_unit)
                scene.window.Render()

    def apply_view_preferences(self):
        if not hasattr(self, 'display_buttons'):
            return
        grid = self.display_buttons['Тор'].isChecked()
        edges = self.display_buttons['Блокийн ирмэг'].isChecked()
        for scene in (self.scene, self.secondary):
            if not scene:continue
            if scene.coordinate_grid:scene.coordinate_grid.SetVisibility(grid)
            if scene.coordinate_text:scene.coordinate_text.SetVisibility(grid)
            if 'blocks' in scene.actors:scene.actors['blocks'].GetProperty().SetEdgeVisibility(edges)

    def layer_selected(self, item, *args):
        if item is None or item.data(0, Qt.ItemDataRole.UserRole) is None:
            return
        super().layer_selected(item, *args)

    def update_english_summary(self):
        blocks=self.project.workspace.get('block_model',{}).get('blocks',[])
        self.project_summary.setText(f'{self.project.name}\n\n{len(self.project.collars):,} drillholes\n{len(self.project.assays):,} assays\n{len(blocks):,} blocks\n\nCRS: {self.project.crs_code or "Local metres"}\nGrade unit: {self.project.grade_unit}\n\nProject data stays local. The assistant receives no project data.\n\nRAINY STUDIO · 90220101')
