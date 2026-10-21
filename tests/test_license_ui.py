import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
import tempfile
import unittest
from PySide6.QtWidgets import QApplication, QDialog
from rainymine.licensing import LicenseManager, StateStore, TRIAL_SECONDS
from rainymine.license_ui import LicenseDialog


class LicenseDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_expired_dialog_cannot_accept_and_preserves_save(self):
        with tempfile.TemporaryDirectory() as directory:
            now = [1800000000]
            manager = LicenseManager(StateStore(Path(directory), False), {}, 'device', lambda: now[0])
            manager.status(True)
            now[0] += TRIAL_SECONDS
            saved = []
            dialog = LicenseDialog(manager, save_callback=lambda: saved.append(True))
            self.assertFalse(dialog.proceed.isEnabled())
            dialog.accept()
            self.assertNotEqual(dialog.result(), QDialog.DialogCode.Accepted)
            from PySide6.QtWidgets import QPushButton
            next(button for button in dialog.findChildren(QPushButton) if button.text() == 'Одоогийн төслөө хадгалах…').click()
            self.assertEqual(saved, [True])
            dialog.close()

    def test_start_button_enables_trial_without_restarting_it(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = LicenseManager(StateStore(Path(directory), False), {}, 'device', lambda: 1800000000)
            dialog = LicenseDialog(manager)
            self.assertFalse(dialog.proceed.isEnabled())
            dialog.start.click()
            self.assertTrue(dialog.proceed.isEnabled())
            self.assertTrue(dialog.start.isHidden())
            dialog.accept()
            self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)
