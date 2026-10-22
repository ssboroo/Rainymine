"""Read-only result views without one Qt item allocation per data cell."""
from PySide6.QtCore import Qt,QAbstractTableModel,QModelIndex
from PySide6.QtWidgets import QDialog,QVBoxLayout,QTableView,QDialogButtonBox,QHeaderView,QAbstractItemView


class ResultTableModel(QAbstractTableModel):
    def __init__(self,columns,rows,parent=None):
        super().__init__(parent);self.columns=list(columns);self.rows=rows

    def rowCount(self,parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self,parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.columns)

    def data(self,index,role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not 0<=index.row()<len(self.rows) or not 0<=index.column()<len(self.columns):return None
        if role in (Qt.ItemDataRole.DisplayRole,Qt.ItemDataRole.ToolTipRole):
            value=self.rows[index.row()].get(self.columns[index.column()])
            return '' if value is None else str(value)
        return None

    def headerData(self,section,orientation,role=Qt.ItemDataRole.DisplayRole):
        if role!=Qt.ItemDataRole.DisplayRole:return None
        if orientation==Qt.Orientation.Horizontal:
            return self.columns[section] if 0<=section<len(self.columns) else None
        return str(section+1)


class ResultsDialog(QDialog):
    def __init__(self,parent,columns,rows,title):
        super().__init__(parent);self.setWindowTitle(title);self.resize(980,520)
        layout=QVBoxLayout(self);self.table=QTableView(self)
        self.model=ResultTableModel(columns,rows,self);self.table.setModel(self.model)
        self.table.setAlternatingRowColors(True);self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setDefaultSectionSize(150)
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        self.table.verticalHeader().setDefaultSectionSize(26)
        layout.addWidget(self.table)
        self.box=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel)
        self.box.button(QDialogButtonBox.StandardButton.Save).setText('CSV экспорт')
        self.box.button(QDialogButtonBox.StandardButton.Cancel).setText('Хаах')
        self.box.rejected.connect(self.reject);layout.addWidget(self.box)
