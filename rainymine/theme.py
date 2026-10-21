"""Native desktop design tokens. Scientific colours in the viewport are separate."""
COLORS={'ink':'#202f40','muted':'#5c6d7f','canvas':'#f4f6f8','surface':'#ffffff',
        'line':'#dce3e9','navy':'#101c2c','accent':'#008f92','selected':'#e0f2ef'}

STYLE='''
QWidget {font-family:"Segoe UI";font-size:12px;color:@ink;}
QMainWindow,QDialog {background:@canvas;}
QToolTip {background:@navy;color:white;border:0;padding:8px;}
QMenuBar {background:#edf3f6;color:@ink;padding:3px 8px;}
QMenuBar::item {padding:5px 9px;}
QMenuBar::item:selected {background:#dcecf0;border-radius:4px;}
QMenu {background:white;border:1px solid @line;padding:5px;}
QMenu::item {padding:7px 28px 7px 12px;}
QMenu::item:selected {background:@selected;color:#0d615f;border-radius:4px;}
QToolBar {border:0;background:@surface;spacing:4px;padding:0;}
QToolBar#masthead {background:#e9f0f4;border-bottom:1px solid #dce3e9;}
QWidget#mastheadPanel {background:#e9f0f4;}
QLabel#wordmark {color:#101c2c;font-size:17px;font-weight:700;}
QLabel#projectTitle {color:#42586b;font-size:12px;}
QLabel#offlineBadge {color:#087b7c;background:#d9f2ee;border-radius:4px;padding:5px 8px;font-size:10px;font-weight:600;}
QToolButton {border:1px solid transparent;border-radius:5px;background:transparent;padding:5px;color:@ink;}
QToolButton:hover {border-color:#b6d8d1;background:@selected;}
QToolButton:pressed,QToolButton:checked {background:#cce9e3;border-color:#7bbeb2;color:#0d615f;}
QToolButton:disabled {color:#8996a4;}
QToolButton:focus,QPushButton:focus,QLineEdit:focus,QComboBox:focus,QDoubleSpinBox:focus {border:1px solid @accent;}
QToolButton#mastheadAction {color:#101c2c;padding:7px;}
QToolButton#mastheadAction:hover {background:#d9eeec;border-color:#9bcac4;}
QPushButton#commandSearch {background:#f4f8fa;border:1px solid #cbd8e1;color:#42586b;padding:7px 12px;text-align:left;}
QPushButton#commandSearch:hover {background:#dcefeb;}
QTabWidget::pane {border:0;border-bottom:1px solid @line;background:white;}
QTabWidget#ribbon::pane {border-top:1px solid @line;}
QTabBar::tab {background:#edf1f5;color:@muted;border:0;padding:8px 11px;min-height:16px;}
QTabBar::tab:selected {background:white;color:#0d615f;border-top:2px solid @accent;padding-top:6px;font-weight:600;}
QTabBar::tab:hover:!selected {background:#e2e9ee;color:@ink;}
QTabBar {qproperty-drawBase:0;}
QGroupBox {border:0;border-right:1px solid @line;margin:0;padding:0 6px;}
QGroupBox::title {subcontrol-origin:padding;subcontrol-position:bottom center;color:@muted;font-size:10px;padding:1px 4px;}
QDockWidget {background:@surface;}
QDockWidget::title {background:#f7f9fb;border-bottom:1px solid @line;color:#42586b;padding:9px 10px;font-weight:600;}
QDockWidget::close-button,QDockWidget::float-button {border:0;padding:3px;}
QDockWidget::close-button:hover,QDockWidget::float-button:hover {background:#dfe8ed;border-radius:3px;}
QMainWindow::separator {background:@canvas;width:6px;height:6px;}
QMainWindow::separator:hover {background:#b6d8d1;}
QTreeWidget,QTableWidget,QListWidget {background:white;alternate-background-color:#f7f9fb;border:1px solid @line;border-radius:4px;gridline-color:#edf1f5;selection-background-color:@selected;selection-color:#0c5e5b;outline:0;}
QTreeWidget::item,QListWidget::item {padding:6px 3px;min-height:18px;border-bottom:1px solid #f0f3f6;}
QTreeWidget::item:selected,QListWidget::item:selected {background:@selected;color:#0c5e5b;}
QTreeWidget::item:hover,QListWidget::item:hover {background:#eef6f4;}
QTableWidget::item {padding:5px 8px;border:0;}
QTableWidget::item:selected {background:@selected;color:#0c5e5b;}
QHeaderView::section {background:#f2f5f8;color:#53687a;border:0;border-bottom:1px solid @line;padding:8px;font-size:11px;font-weight:600;}
QTableCornerButton::section {background:#f2f5f8;border:0;}
QLineEdit,QDoubleSpinBox,QComboBox {background:white;color:@ink;border:1px solid #ccd6df;border-radius:4px;padding:6px;min-height:18px;selection-background-color:@selected;selection-color:#0c5e5b;}
QComboBox::drop-down {width:18px;border:0;}
QComboBox QAbstractItemView {background:white;color:@ink;selection-background-color:@selected;selection-color:#0c5e5b;}
QPushButton {background:white;color:@ink;border:1px solid #ccd6df;border-radius:4px;padding:7px 10px;min-height:18px;}
QPushButton:hover {background:#edf7f4;border-color:#91c2b9;}
QPushButton:pressed,QPushButton:checked {background:#d8eee7;color:#0c5e5b;}
QPushButton:default {background:#087b7c;color:white;border-color:#087b7c;}
QPushButton:disabled {background:#f0f3f5;color:#8c99a5;}
QCheckBox {spacing:7px;padding:4px 0;}
QCheckBox::indicator {width:16px;height:16px;}
QSlider::groove:horizontal {height:4px;background:#dce6eb;border-radius:2px;}
QSlider::sub-page:horizontal {background:@accent;border-radius:2px;}
QSlider::handle:horizontal {background:@accent;width:13px;height:13px;margin:-5px 0;border:2px solid white;border-radius:8px;}
QScrollArea {border:0;background:white;}
QScrollBar:vertical {background:#f2f5f8;width:8px;margin:0;}
QScrollBar::handle:vertical {background:#c4d0d9;border-radius:4px;min-height:30px;}
QScrollBar::handle:vertical:hover {background:#95a8b7;}
QScrollBar:horizontal {background:#f2f5f8;height:8px;}
QScrollBar::handle:horizontal {background:#c4d0d9;border-radius:4px;min-width:30px;}
QScrollBar::add-line,QScrollBar::sub-line {width:0;height:0;}
QScrollBar::add-page,QScrollBar::sub-page {background:transparent;}
QStatusBar {background:#f7f9fb;color:@muted;border-top:1px solid @line;font-size:10px;}
QStatusBar::item {border:0;}
QLabel#viewportTitle {font-size:13px;font-weight:600;color:#314c5d;}
QLabel#viewportHint,QLabel#muted {font-size:11px;color:@muted;}
QLabel#selectionInfo {background:#f5f8fa;border:1px solid @line;border-radius:4px;padding:8px;color:#4b6274;font-size:11px;}
QLabel#pickedInfo {background:#eff7f5;border:1px solid #d0e8e0;border-radius:4px;padding:8px;color:#245e55;font-size:11px;}
QLabel#opacityValue {color:@muted;font-size:11px;}
QDialog QLabel {background:transparent;}
QProgressBar {background:#edf1f5;border:1px solid @line;border-radius:4px;text-align:center;}
QProgressBar::chunk {background:@accent;border-radius:3px;}
'''
for key,value in COLORS.items():STYLE=STYLE.replace('@'+key,value)

STYLE += "QLabel#guideNumber {color:#063a45;background:#00bdbb;border-radius:12px;font-size:13px;font-weight:600;}"
