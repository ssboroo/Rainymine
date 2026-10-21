"""Native desktop workspace: consistent controls, command search and focus mode."""
from PySide6.QtCore import Qt,QSize,QTimer
from PySide6.QtGui import QAction,QKeySequence,QFont,QShortcut,QColor,QBrush
from PySide6.QtWidgets import (QWidget,QHBoxLayout,QLabel,QToolBar,QToolButton,QPushButton,
    QDockWidget,QHeaderView,QDialog,QVBoxLayout,QLineEdit,QListWidget,QListWidgetItem,
    QSizePolicy,QTabWidget,QApplication,QTreeWidgetItem,QTableWidget,QTableWidgetItem,QAbstractItemView,QScrollArea,QComboBox,QMenu)
from .advanced import AdvancedWorkbench
from .icons import icon,brand_icon,semantic_icon
from .theme import STYLE


class CommandPalette(QDialog):
    def __init__(self,parent,entries):
        super().__init__(parent);self.entries=entries;self.setWindowTitle('Үйлдэл хайх');self.resize(580,440)
        layout=QVBoxLayout(self);self.search=QLineEdit();self.search.setPlaceholderText('Нэрээр хайх…  жишээ: импорт, блок, RBF')
        self.search.setAccessibleName('Үйлдэл хайх');layout.addWidget(self.search)
        self.results=QListWidget();self.results.setAccessibleName('Олдсон үйлдлүүд');layout.addWidget(self.results)
        hint=QLabel('↑ ↓ Сонгох    Enter Ажиллуулах    Esc Хаах');hint.setObjectName('muted');layout.addWidget(hint)
        self.search.textChanged.connect(self.filter);self.search.returnPressed.connect(self.launch)
        self.results.itemActivated.connect(self.launch)
        self.down=QShortcut(QKeySequence('Down'),self.search);self.down.activated.connect(self.results.setFocus)
        self.filter('');self.search.setFocus()
    def filter(self,text):
        self.results.clear()
        for i,(title,callback,enabled) in enumerate(self.entries):
            if enabled and text.casefold() in title.casefold():
                item=QListWidgetItem(title);item.setData(Qt.ItemDataRole.UserRole,i);self.results.addItem(item)
        if self.results.count():self.results.setCurrentRow(0)
    def launch(self,*args):
        item=self.results.currentItem()
        if item:
            callback=self.entries[item.data(Qt.ItemDataRole.UserRole)][1]
            self.accept();QTimer.singleShot(0,callback)


class PresentationWorkbench(AdvancedWorkbench):
    def __init__(self):
        self.presentation_ready=False;self.ribbon_collapsed=False;self.focus_active=False;self.labels_visible=False
        super().__init__();self.setStyleSheet(STYLE);self.setWindowIcon(brand_icon())
        self.setMinimumSize(1024,720);self.presentation_ready=True
        self.polish_controls();self.polish_data()
        QTimer.singleShot(0,self.balance_docks)

    def build_ui(self):
        super().build_ui();self.ribbon.setObjectName('ribbon');self.ribbon.setFixedHeight(134)
        self.ribbon.tabBar().setToolTip('Табыг давхар дарж хэрэгслийн мөрийг хураана / дэлгэнэ · Ctrl+F1')
        self.ribbon.tabBarDoubleClicked.connect(lambda index:self.collapse_ribbon())
        docks=self.findChildren(QDockWidget);self.project_dock=docks[0];self.section_dock=docks[1];self.data_dock=docks[2]
        self.project_dock.setWindowTitle('Цооногууд');self.section_dock.setWindowTitle('Огтлол');self.data_dock.setWindowTitle('Өгөгдлийн хүснэгт')
        self.layer_dock.setWindowTitle('Давхаргууд');self.layer_dock.setMinimumWidth(245)
        self.project_dock.setMinimumWidth(235);self.section_dock.setMinimumWidth(235)
        self.tabifyDockWidget(self.project_dock,self.section_dock);self.project_dock.raise_()
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea,self.layer_dock)
        self.tabifyDockWidget(self.project_dock,self.layer_dock);self.layer_dock.raise_()
        self.setTabPosition(Qt.DockWidgetArea.LeftDockWidgetArea,QTabWidget.TabPosition.South)
        for check in self.layer_checks.values():check.hide()
        self.stats.setMinimumHeight(62);self.info.setObjectName('selectionInfo');self.picked_info.setObjectName('pickedInfo')
        self.search.setClearButtonEnabled(True);self.search.setAccessibleName('Цооногийн нэрээр хайх')
        self.search.setPlaceholderText('Цооног хайх…');self.search.addAction(icon('search'),QLineEdit.ActionPosition.LeadingPosition)
        self.tree.setAlternatingRowColors(True);self.tree.setRootIsDecorated(False)
        self.tree.header().setStretchLastSection(False)
        self.tree.header().setSectionResizeMode(0,QHeaderView.ResizeMode.Stretch)
        self.tree.header().setSectionResizeMode(1,QHeaderView.ResizeMode.ResizeToContents)
        self.layer_list.setRootIsDecorated(True);self.layer_list.setAlternatingRowColors(False)
        self.layer_list.setIndentation(12);self.layer_list.setIconSize(QSize(14,14))
        self.layer_list.header().setStretchLastSection(False)
        self.layer_list.header().setSectionResizeMode(0,QHeaderView.ResizeMode.Stretch)
        self.layer_list.header().setSectionResizeMode(1,QHeaderView.ResizeMode.Fixed);self.layer_list.setColumnWidth(1,55)
        self.layer_list.setHeaderLabels(['Төслийн өгөгдөл','Тоо'])
        self.opacity.setAccessibleName('Давхаргын тунгалагшил');self.representation.setAccessibleName('Давхаргын дүрслэл')
        self.opacity_value=QLabel('100%');self.opacity_value.setObjectName('opacityValue')
        self.opacity.valueChanged.connect(lambda n:self.opacity_value.setText(f'{n}%'))
        self.layer_dock.widget().layout().insertWidget(2,self.opacity_value)
        self.measure_label.setObjectName('muted');self.table.verticalHeader().setDefaultSectionSize(31)
        self.table.horizontalHeader().setMinimumSectionSize(80);self.table.setShowGrid(False)
        self.table.setAccessibleName('Цооногийн координат ба замналын хүснэгт')
        self.data_tabs=QTabWidget();self.block_table=QTableWidget();self.block_table.setColumnCount(6)
        self.block_table.setHorizontalHeaderLabels(['Блок','Зүүн, м','Хойд, м','Өндөр, м','Агуулга','Variance'])
        self.block_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.block_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.block_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.block_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.block_table.verticalHeader().setDefaultSectionSize(29);self.block_table.setShowGrid(False)
        self.block_table.itemSelectionChanged.connect(self.select_block_row)
        self.block_page=0;block_panel=QWidget();block_layout=QVBoxLayout(block_panel);block_layout.setContentsMargins(0,0,0,0);block_layout.setSpacing(0);block_layout.addWidget(self.block_table)
        pager=QHBoxLayout();self.page_caption=QLabel();self.page_caption.setObjectName('muted');pager.addWidget(self.page_caption);pager.addStretch()
        self.previous_page=QToolButton();self.previous_page.setText('Өмнөх');self.previous_page.clicked.connect(lambda:self.render_block_page(self.block_page-1));pager.addWidget(self.previous_page)
        self.next_page=QToolButton();self.next_page.setText('Дараах');self.next_page.clicked.connect(lambda:self.render_block_page(self.block_page+1));pager.addWidget(self.next_page);block_layout.addLayout(pager)
        self.data_tabs.addTab(block_panel,'Блок загвар');self.data_tabs.addTab(self.table,'Цооногууд');self.data_dock.setWidget(self.data_tabs)
        # Masthead owns the existing live project title; no duplicate project state.
        self.masthead=QToolBar('RAINYMINE');self.masthead.setObjectName('masthead');self.masthead.setMovable(False)
        panel=QWidget();panel.setObjectName('mastheadPanel');row=QHBoxLayout(panel);row.setContentsMargins(12,8,12,8);row.setSpacing(10)
        logo=QLabel();logo.setPixmap(brand_icon().pixmap(32,32));row.addWidget(logo)
        wordmark=QLabel('RAINYMINE');wordmark.setObjectName('wordmark');row.addWidget(wordmark)
        year=QLabel('2026');year.setObjectName('projectTitle');row.addWidget(year)
        self.title_label.setObjectName('projectTitle');self.title_label.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Preferred);row.addWidget(self.title_label,1)
        search=QPushButton('Үйлдэл хайх     Ctrl K');search.setObjectName('commandSearch');search.setIcon(icon('search'));search.clicked.connect(self.command_palette);row.addWidget(search)
        for name,kind,callback in [('Төсөл нээх','folder',self.open),('Хадгалах · Ctrl+S','save',self.save)]:
            b=QToolButton();b.setObjectName('mastheadAction');b.setIcon(icon(kind));b.setIconSize(QSize(20,20));b.setToolTip(name);b.setAccessibleName(name);b.clicked.connect(lambda checked=False,cb=callback:cb());row.addWidget(b)
        badge=QLabel('ОФФЛАЙН');badge.setObjectName('offlineBadge');row.addWidget(badge)
        panel.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Preferred);self.masthead.addWidget(panel)
        ribbon_bar=next(bar for bar in self.findChildren(QToolBar) if bar.windowTitle()=='Ribbon')
        self.insertToolBar(ribbon_bar,self.masthead);self.insertToolBarBreak(ribbon_bar)
        # Compact camera commands stay next to the viewport at every ribbon tab.
        header=self.centralWidget().layout().itemAt(0).layout()
        brand=self.findChild(QLabel,'brand');brand.setText('3D ажлын орчин');brand.setObjectName('viewportTitle')
        for i in range(header.count()):
            w=header.itemAt(i).widget()
            if isinstance(w,QLabel) and 'ОФФЛАЙН' in w.text():w.hide()
        for title,mode in [('3D','iso'),('Дээрээс','top'),('Урдаас','north')]:
            b=QToolButton();b.setText(title);b.setToolTip('Камер · '+title);b.clicked.connect(lambda checked=False,m=mode:self.scene.view(m));header.addWidget(b)
        b=QToolButton();b.setIcon(icon('pick'));b.setToolTip('Загварыг төвлөрүүлэх');b.setAccessibleName('Загварыг төвлөрүүлэх');b.clicked.connect(lambda:self.scene.reset());header.addWidget(b)
        self.labels_button=QToolButton();self.labels_button.setIcon(icon('label'));self.labels_button.setText('Шошго');self.labels_button.setCheckable(True)
        self.labels_button.toggled.connect(self.toggle_labels);self.labels_button.setToolTip('Бүх цооногийн нэрийг харуулах / нуух');header.addWidget(self.labels_button)
        self.centralWidget().layout().setContentsMargins(8,6,8,6)
        footer=self.centralWidget().layout().itemAt(2).widget()
        if isinstance(footer,QLabel):footer.setText('Эргүүлэх: зүүн товч   ·   Томруулах: дугуй   ·   Зөөх: Shift + зүүн');footer.setObjectName('viewportHint')
        self.coordinates.setFont(QFont('Consolas',9))
        panels=self.menuBar().addMenu('Самбарууд')
        for dock in (self.project_dock,self.section_dock,self.layer_dock,self.data_dock):panels.addAction(dock.toggleViewAction())
        self.action(panels,'Хэрэгслийн мөр хураах / дэлгэх',self.collapse_ribbon,'Ctrl+F1')
        self.action(panels,'3D төвлөрсөн горим',self.focus_workspace,'F10')
        self.action(panels,'Үйлдэл хайх',self.command_palette,'Ctrl+K')
        self.build_guide(panels)

    def build_guide(self,panels):
        self.guide_dock=QDockWidget('RAINYMINE ТУСЛАХ',self);self.guide_dock.setMinimumWidth(225)
        tabs=QTabWidget();help_page=QWidget();layout=QVBoxLayout(help_page);layout.setContentsMargins(12,12,12,12);layout.setSpacing(14)
        for number,title,description,callback in [
            ('1','Өгөгдөл оруулах','Амсар, замнал, сорьц болон гадаргын мэдээллээ импортлоно.',lambda:self.import_data('collars')),
            ('2','Загвар тохируулах','Блокийн хэмжээ, домэйн болон үнэлгээний параметрээ тохируулна.',self.block_dialog),
            ('3','Чанар шалгах','Сорьцын бүрхэлт, интервал болон анхдагч өгөгдлийн алдааг шалгана.',self.qaqc)]:
            row=QHBoxLayout();badge=QLabel(number);badge.setObjectName('guideNumber');badge.setFixedSize(24,24);badge.setAlignment(Qt.AlignmentFlag.AlignCenter);row.addWidget(badge)
            title_button=QPushButton(title);title_button.clicked.connect(lambda checked=False,cb=callback:cb());row.addWidget(title_button,1);layout.addLayout(row)
            text=QLabel(description);text.setWordWrap(True);text.setObjectName('muted');layout.addWidget(text)
        layout.addStretch();note=QLabel('Оффлайн заавар • Дээрх товчнууд хэрэгслийг нээнэ.');note.setWordWrap(True);note.setObjectName('muted');layout.addWidget(note)
        ask=QPushButton('Тусламж / үйлдэл хайх…');ask.setIcon(icon('search'));ask.clicked.connect(self.command_palette);layout.addWidget(ask)
        tabs.addTab(help_page,'Тусламж');project_page=QWidget();project_layout=QVBoxLayout(project_page)
        self.project_summary=QLabel();self.project_summary.setWordWrap(True);self.project_summary.setTextFormat(Qt.TextFormat.PlainText);project_layout.addWidget(self.project_summary);project_layout.addStretch();tabs.addTab(project_page,'Төсөл')
        # Preserve the real local support engine merged on main while presenting
        # it inside the user's requested right-hand assistant panel.
        support_panel=self.support.widget();support_panel.setParent(None);self.support.setWidget(QWidget())
        self.support.setup_button.setText('AI бэлтгэх');self.support.setup_button.setToolTip('Анх тохируулах · 1.28 GB')
        self.support.files_button.setText('Файл…');self.support.cancel_button.setText('Зогсоох')
        self.support.manual.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon);self.support.manual.setMinimumContentsLength(10)
        ai_scroll=QScrollArea();ai_scroll.setWidgetResizable(True);ai_scroll.setWidget(support_panel)
        tabs.addTab(ai_scroll,'Local AI');self.guide_tabs=tabs
        for button in self.ribbon.findChildren(QToolButton):
            if 'Local AI' in button.text():
                button.clicked.disconnect();button.clicked.connect(self.show_ai_guide)
        self.guide_dock.setWidget(tabs);self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea,self.guide_dock);panels.addAction(self.guide_dock.toggleViewAction())

    def show_ai_guide(self):self.guide_dock.show();self.guide_tabs.setCurrentIndex(2)

    def createPopupMenu(self):
        menu=QMenu(self)
        for dock in (self.layer_dock,self.project_dock,self.section_dock,self.guide_dock,self.data_dock):
            menu.addAction(dock.toggleViewAction())
        return menu

    def polish_controls(self):
        for button in self.findChildren(QToolButton):
            text=button.text()
            if text:
                label=text.replace('\n',' ');button.setAccessibleName(label)
                if not button.toolTip():button.setToolTip(label)
                if button.objectName()!='mastheadAction':button.setIcon(semantic_icon(text,button.icon()))
                if self.ribbon.isAncestorOf(button):button.setMinimumWidth(72);button.setIconSize(QSize(27,27))
        self.measure.setIcon(icon('pick'));self.representation.setToolTip('Сонгосон давхаргын геометрийн харагдац')

    def balance_docks(self):
        self.resizeDocks([self.layer_dock,self.guide_dock],[250,225],Qt.Orientation.Horizontal)
        self.resizeDocks([self.data_dock],[210],Qt.Orientation.Vertical)

    def refresh(self):
        super().refresh()
        if self.presentation_ready:self.polish_data()

    def polish_data(self):
        count=len(self.project.collars);depth=sum(h.depth for h in self.project.collars)
        self.stats.setText(f'<span style="font-size:22px;color:#202f40;font-weight:600">{count:,}</span>'
            f'<span style="color:#5c6d7f"> цооног</span> &nbsp; '
            f'<span style="font-size:16px;color:#117b79;font-weight:600">{depth:,.0f} м</span>'
            f'<br><span style="color:#5c6d7f">{len(self.project.assays):,} сорьц &nbsp; · &nbsp; {len(self.project.surveys):,} замналын хэмжилт</span>')
        self.title_label.setToolTip(self.project.name)
        self.project_summary.setText(f'{self.project.name}\n\n{count:,} цооног\n{len(self.project.assays):,} сорьц\n\nCRS: {self.project.crs_code or self.project.crs}\nАгуулгын нэгж: {self.project.grade_unit}')
        self.render_block_page(0)
        for row in range(self.table.rowCount()):
            for col in range(1,self.table.columnCount()):
                item=self.table.item(row,col)
                if item:item.setTextAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter)
        for scene in (self.scene,self.secondary):
            if scene:
                scene.renderer.SetBackground(.985,.991,.995);scene.renderer.GradientBackgroundOff()
                scene.legend.GetLabelTextProperty().SetFontSize(11)
        self.update_labels()

    def render_block_page(self,page):
        blocks=self.project.workspace.get('block_model',{}).get('blocks',[])
        self.block_page=max(0,min(page,max(0,(len(blocks)-1)//1000)));start=self.block_page*1000;page_blocks=blocks[start:start+1000]
        self.page_caption.setText(f'{start+1 if blocks else 0:,}–{start+len(page_blocks):,} / {len(blocks):,}')
        self.previous_page.setEnabled(self.block_page>0);self.next_page.setEnabled(start+1000<len(blocks))
        self.block_table.blockSignals(True);self.block_table.setRowCount(len(page_blocks));self.block_table.setUpdatesEnabled(False)
        self.block_table.setHorizontalHeaderLabels(['Блок','Зүүн, м','Хойд, м','Өндөр, м','Агуулга '+self.project.grade_unit,'Variance'])
        for row,block in enumerate(page_blocks):
            values=[start+row,block['x'],block['y'],block['z'],block.get('grade'),block.get('variance')]
            for column,value in enumerate(values):
                text='—' if value is None else str(value) if column==0 else f'{value:,.2f}' if column<4 else f'{value:.3f}'
                item=QTableWidgetItem(text);item.setTextAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter)
                if column==4 and value is not None:
                    rgb=[0.,0.,0.];self.scene.lut.GetColor(value,rgb);color=QColor.fromRgbF(*rgb);color.setAlphaF(.24);item.setBackground(QBrush(color))
                self.block_table.setItem(row,column,item)
        self.block_table.setUpdatesEnabled(True);self.block_table.blockSignals(False)
        if not blocks:self.data_tabs.setCurrentIndex(1)

    def select_block_row(self):
        row=self.block_table.currentRow()
        if row<0:return
        row+=self.block_page*1000;blocks=self.project.workspace.get('block_model',{}).get('blocks',[])
        if 0<=row<len(blocks):
            b=blocks[row];self.picked_info.setText(f"Блок #{row}\nX {b['x']:,.2f}  Y {b['y']:,.2f}\nZ {b['z']:,.2f}\nАгуулга: {b.get('grade')} {self.project.grade_unit}\nVariance: {b.get('variance')}\n{b.get('status','')}")

    def refresh_layers(self):
        super().refresh_layers()
        previous=self.layer_list.blockSignals(True)
        items=[self.layer_list.takeTopLevelItem(0) for _ in range(self.layer_list.topLevelItemCount())]
        groups={}
        for item in items:
            key=item.data(0,Qt.ItemDataRole.UserRole)
            if key in ('holes','collars'):category='Цооногууд'
            elif key=='surface':category='Гадарга'
            elif key=='blocks':category='Блок загвар'
            elif key.startswith('mesh') and self.project.workspace.get('meshes',[])[int(key.split('_')[1])].get('role') in ('pit','optimized_pit','drive'):category='Уурхайн загвар'
            else:category='Геологи'
            if category not in groups:
                group=QTreeWidgetItem([category,'']);group.setIcon(0,icon('folder'));groups[category]=group;self.layer_list.addTopLevelItem(group)
            groups[category].addChild(item)
            item.setIcon(0,icon('holes' if key=='holes' else 'surface' if key=='surface' else 'cube' if key.startswith('mesh') or key=='blocks' else 'pick'))
            item.setToolTip(0,item.text(0));item.setTextAlignment(1,Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter)
        self.layer_list.expandAll()
        if items:self.layer_list.setCurrentItem(next((item for item in items if item.data(0,Qt.ItemDataRole.UserRole)==self.active_layer),items[0]))
        self.layer_list.blockSignals(previous)

    def layer_selected(self,item,*args):
        if item and item.data(0,Qt.ItemDataRole.UserRole) is not None:super().layer_selected(item,*args)

    def update_labels(self):
        for scene in (getattr(self,'scene',None),getattr(self,'secondary',None)):
            if scene:
                visible=scene.actors.get('holes') and scene.actors['holes'].GetVisibility() and scene.section is None
                for label in scene.labels:
                    label.SetVisibility(bool(visible and (self.labels_visible or label.GetInput()==scene.selected_hole)))
                    label.GetTextProperty().SetOrientation(0)
                scene.window.Render()

    def toggle_labels(self,value):self.labels_visible=value;self.update_labels()
    def show_hole(self,name):
        super().show_hole(name)
        if self.presentation_ready:self.update_labels()
    def update_section(self,*args):
        super().update_section(*args)
        if self.presentation_ready:self.update_labels()
    def change_layer(self,key,changes):
        super().change_layer(key,changes)
        if self.presentation_ready:self.update_labels()
    def collapse_ribbon(self):
        self.ribbon_collapsed=not self.ribbon_collapsed;self.ribbon.setFixedHeight(36 if self.ribbon_collapsed else 134)
    def focus_workspace(self):
        docks=(self.project_dock,self.section_dock,self.layer_dock,self.data_dock,self.guide_dock)
        if not self.focus_active:
            self.focus_visibility=[not d.isHidden() for d in docks];self.focus_ribbon_visible=not self.ribbon.isHidden()
            for dock in docks:dock.hide()
            self.ribbon.hide()
        else:
            for dock,visible in zip(docks,self.focus_visibility):dock.setVisible(visible)
            self.ribbon.setVisible(self.focus_ribbon_visible);self.layer_dock.raise_()
        self.focus_active=not self.focus_active
    def command_palette(self):
        entries=[];seen=set()
        for button in self.ribbon.findChildren(QToolButton):
            title=button.text().replace('\n',' ').strip()
            if title and title not in seen:
                seen.add(title);entries.append((title,button.click,button.isEnabled()))
        for action in self.findChildren(QAction):
            title=action.text().replace('&','').strip()
            if title and title not in seen and not action.isSeparator():
                seen.add(title);entries.append((title,action.trigger,action.isEnabled()))
        CommandPalette(self,entries).exec()
