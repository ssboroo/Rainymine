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


# Combined workspace style; legacy presentation retains STYLE.
"""RAINYMINE 2026 light workspace palette, shared by native dialogs."""
THEME = STYLE + '''
QWidget {font-family:"Segoe UI";font-size:12px;color:#101c2c;}
QWidget#ribbonPage {background:#f9fcfe;}
QMainWindow,QDialog {background:#f4f8fb;}
QMenuBar {background:#f9fcfe;border-bottom:1px solid #d9e6ee;padding:3px;color:#162b43;}
QMenuBar::item {padding:5px 10px;border-radius:4px;}
QMenuBar::item:selected,QMenu::item:selected {background:#dcf6f5;color:#007f84;}
QMenu {background:white;border:1px solid #cbdde8;padding:5px;}
QToolBar {background:#f9fcfe;border:0;spacing:3px;padding:0;}
QToolButton {background:transparent;border:1px solid transparent;border-radius:5px;padding:5px;color:#172b45;}
QToolButton:hover {background:#e5f7f8;border-color:#a8dddf;}
QToolButton:checked {background:#d8f6f4;border-color:#19c6b3;color:#007e81;}
QPushButton {background:#ffffff;border:1px solid #cbdde8;border-radius:5px;padding:7px 11px;}
QPushButton:hover {background:#e7f9f8;border-color:#19c6b3;}
QPushButton:disabled,QToolButton:disabled {color:#9aa6b2;background:#edf3f7;}
QTabWidget::pane {border:1px solid #d0e2ed;background:#f9fcfe;border-radius:5px;}
QTabBar::tab {background:#eaf3f8;color:#334a66;padding:8px 13px;border:0;border-bottom:2px solid transparent;}
QTabBar::tab:selected {background:#ffffff;color:#009ba3;border-bottom:2px solid #19c6b3;}
QTabBar::tab:hover {background:#e1f6f7;}
QGroupBox {border:0;border-right:1px solid #d9e7ef;padding:0 5px;margin-top:0;}
QGroupBox::title {subcontrol-origin:padding;subcontrol-position:bottom center;color:#7b8fa2;padding:1px;}
QDockWidget {background:#f8fcfe;}
QDockWidget::title {background:#eaf3f8;color:#101c2c;border-bottom:1px solid #d3e4ed;padding:8px;font-weight:600;}
QTreeWidget,QTableView,QTextEdit {background:#ffffff;alternate-background-color:#f2f8fc;border:1px solid #d4e4ee;border-radius:3px;gridline-color:#e1ecf3;selection-background-color:#d8f4f2;selection-color:#102c40;}
QTreeWidget::item {padding:4px 0;}
QHeaderView::section {background:#edf5fa;border:0;border-right:1px solid #d4e4ee;border-bottom:1px solid #d4e4ee;padding:6px;color:#344c64;}
QLineEdit,QDoubleSpinBox,QSpinBox,QComboBox {background:#fff;border:1px solid #c8dce8;border-radius:4px;padding:6px;selection-background-color:#c9f0ee;}
QLineEdit:focus,QComboBox:focus {border-color:#19c6b3;}
QCheckBox {padding:3px;spacing:5px;}
QCheckBox::indicator {width:13px;height:13px;border:1px solid #9aaec1;border-radius:3px;background:#fff;}
QCheckBox::indicator:checked {background:#19c6b3;border-color:#00a49f;}
QStatusBar {background:#edf5f9;border-top:1px solid #d1e2ec;color:#5e7489;}
QLabel#brand {font-size:17px;font-weight:700;color:#101c2c;}
QLabel#muted {color:#73899a;}
QLabel#workspaceTitle {font-size:12px;font-weight:600;color:#203a55;}
QScrollArea {border:0;background:transparent;}
QScrollBar:vertical {background:#edf5f9;width:9px;}
QScrollBar::handle:vertical {background:#becfda;min-height:28px;border-radius:4px;}
QScrollBar:horizontal {background:#edf5f9;height:9px;}
QScrollBar::handle:horizontal {background:#becfda;min-width:28px;border-radius:4px;}
QSplitter::handle {background:#e3edf4;}
QProgressBar {border:1px solid #c4e1e8;background:#edf7fa;border-radius:5px;text-align:center;}
QProgressBar::chunk {background:#19c6b3;border-radius:4px;}
'''

THEME += '''
QGroupBox#blockInspector {border:1px solid #d4e4ee;border-radius:4px;margin:2px 0 0 0;padding:0;background:white;}
QGroupBox#blockInspector::title {subcontrol-origin:margin;subcontrol-position:top left;left:10px;top:5px;font-weight:600;color:#101c2c;}
QGroupBox#blockInspector QLabel {font-size:11px;min-height:16px;}
'''

# Explicit foregrounds and measured controls keep Windows dark-mode palettes
# from turning text white on our light scientific workspace.
THEME += '''
QWidget {font-size:13px;color:#172b40;}
QLabel,QAbstractItemView {color:#172b40;}
QLabel#muted {color:#52697a;}
QLineEdit,QTextEdit,QPlainTextEdit,QSpinBox,QDoubleSpinBox,QComboBox {
    color:#172b40;background:#ffffff;selection-color:#ffffff;selection-background-color:#00777b;
}
QTreeWidget,QTableView,QTableWidget,QListWidget {color:#172b40;}
QHeaderView::section {color:#294257;font-size:12px;padding:8px;}
QToolButton#ribbonCommand {padding:0;color:#172b40;text-align:left;}
QToolButton#ribbonCommand:hover {background:#e2f3f2;border-color:#9acbc8;}
QToolButton#ribbonCommand:checked {background:#d2efeb;color:#123e43;}
QToolButton#ribbonCommand:disabled {color:#657789;}
QGroupBox#ribbonGroup {border:0;border-right:1px solid #ccdce5;padding:0;margin:0;}
QGroupBox#ribbonGroup::title {color:#425e72;font-size:11px;padding:3px 6px;}
QScrollBar:horizontal {height:14px;}
QScrollBar:vertical {width:12px;}
QTabBar::tab {padding:8px 10px;}
QStatusBar {font-size:11px;color:#425e72;}
QLabel#selectionInfo,QLabel#pickedInfo {color:#294257;}
QGroupBox#blockInspector QLabel {font-size:12px;min-height:18px;}
'''


def apply_light_palette(app):
    """Define all text/background pairs, including disabled and inactive windows."""
    from PySide6.QtGui import QColor, QPalette
    palette = QPalette()
    roles = {
        QPalette.ColorRole.Window: '#f4f8fb',
        QPalette.ColorRole.WindowText: '#172b40',
        QPalette.ColorRole.Base: '#ffffff',
        QPalette.ColorRole.AlternateBase: '#f2f8fc',
        QPalette.ColorRole.Text: '#172b40',
        QPalette.ColorRole.Button: '#f9fcfe',
        QPalette.ColorRole.ButtonText: '#172b40',
        QPalette.ColorRole.ToolTipBase: '#101c2c',
        QPalette.ColorRole.ToolTipText: '#ffffff',
        QPalette.ColorRole.Highlight: '#00777b',
        QPalette.ColorRole.HighlightedText: '#ffffff',
        QPalette.ColorRole.PlaceholderText: '#5c6d7f',
        QPalette.ColorRole.Link: '#006d74',
        QPalette.ColorRole.BrightText: '#ffffff',
    }
    for role, color in roles.items():
        palette.setColor(role, QColor(color))
    for role in (QPalette.ColorRole.WindowText, QPalette.ColorRole.Text,
                 QPalette.ColorRole.ButtonText):
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor('#657789'))
    app.setPalette(palette)
