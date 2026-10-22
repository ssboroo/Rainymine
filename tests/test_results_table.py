import unittest
from PySide6.QtCore import Qt,QModelIndex
from PySide6.QtWidgets import QApplication,QAbstractItemView
from rainymine.results_table import ResultTableModel,ResultsDialog


class LazyResults(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])

    def test_rows_are_read_on_demand_and_values_preserved(self):
        class Rows:
            def __len__(self):return 1000000
            def __getitem__(self,index):
                if not 0<=index<1000000:raise IndexError(index)
                return {'id':index,'grade':None if index else 0}
        rows=Rows();model=ResultTableModel(['id','grade'],rows)
        self.assertIs(model.rows,rows);self.assertEqual(model.rowCount(),1000000)
        self.assertEqual(model.data(model.index(999999,0)),'999999')
        self.assertEqual(model.data(model.index(0,1)),'0')
        self.assertEqual(model.data(model.index(999999,1)),'')
        self.assertEqual(model.rowCount(model.index(0,0)),0)
        self.assertIsNone(model.data(QModelIndex()))
        self.assertFalse(model.flags(model.index(0,0)) & Qt.ItemFlag.ItemIsEditable)

    def test_dialog_uses_lazy_model_and_export_signal(self):
        dialog=ResultsDialog(None,['id','grade'],[{'id':1,'grade':0},{'id':2,'grade':None}],'Result')
        self.addCleanup(dialog.close)
        self.assertIs(dialog.table.model(),dialog.model)
        self.assertEqual(dialog.table.editTriggers(),QAbstractItemView.EditTrigger.NoEditTriggers)
        self.assertEqual(dialog.model.headerData(1,Qt.Orientation.Horizontal),'grade')
        called=[];dialog.box.accepted.connect(lambda:called.append(True))
        from PySide6.QtWidgets import QDialogButtonBox
        dialog.box.button(QDialogButtonBox.StandardButton.Save).click()
        self.assertEqual(called,[True])
