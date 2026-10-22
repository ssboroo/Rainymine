"""Read-only report grids: visible cells only, with unchanged source export."""
import reprlib
from PySide6.QtCore import QAbstractTableModel,QModelIndex,Qt
from PySide6.QtWidgets import QDialog,QVBoxLayout,QTableView,QDialogButtonBox,QHeaderView,QAbstractItemView


class ReportModel(QAbstractTableModel):
    def __init__(self,rows,columns,parent=None):
        super().__init__(parent);self.rows=rows;self.columns=columns
    def rowCount(self,parent=QModelIndex()):return 0 if parent.isValid() else len(self.rows)
    def columnCount(self,parent=QModelIndex()):return 0 if parent.isValid() else len(self.columns)
    def headerData(self,section,orientation,role=Qt.ItemDataRole.DisplayRole):
        if role==Qt.ItemDataRole.DisplayRole:return self.columns[section] if orientation==Qt.Orientation.Horizontal else str(section+1)
    def data(self,index,role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not 0<=index.row()<len(self.rows) or not 0<=index.column()<len(self.columns):return None
        value=self.rows[index.row()].get(self.columns[index.column()])
        if role in (Qt.ItemDataRole.DisplayRole,Qt.ItemDataRole.ToolTipRole):
            text='—' if value is None else reprlib.repr(value) if isinstance(value,(list,dict,tuple,set)) else str(value)
            maximum=4096 if role==Qt.ItemDataRole.ToolTipRole else 512
            return text if len(text)<=maximum else text[:maximum]+'…'
        if role==Qt.ItemDataRole.TextAlignmentRole:return int(Qt.AlignmentFlag.AlignVCenter | (Qt.AlignmentFlag.AlignRight if isinstance(value,(int,float)) else Qt.AlignmentFlag.AlignLeft))


class ReportDialog(QDialog):
    def __init__(self,parent,columns,rows,title):
        super().__init__(parent);self.setWindowTitle(title);self.resize(1050,600)
        layout=QVBoxLayout(self);self.table=QTableView(self);self.model=ReportModel(rows,columns,self);self.table.setModel(self.model)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers);self.table.setAlternatingRowColors(True)
        self.table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        header=self.table.horizontalHeader();header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive);header.setMinimumSectionSize(100);header.setDefaultSectionSize(155)
        self.table.verticalHeader().setDefaultSectionSize(28);layout.addWidget(self.table)
        self.box=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel)
        self.box.button(QDialogButtonBox.StandardButton.Save).setText('CSV экспорт');self.box.button(QDialogButtonBox.StandardButton.Cancel).setText('Хаах')
        self.box.rejected.connect(self.reject);layout.addWidget(self.box)
