"""RAINYMINE 2026 light workspace palette, shared by native dialogs."""
THEME = '''
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
