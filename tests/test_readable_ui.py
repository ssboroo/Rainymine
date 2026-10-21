"""Visible captions and overflow on small screens, both locales and larger fonts."""
import unittest
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from tests.test_workspace import WorkspaceLayoutTests
from rainymine.ribbon import RibbonButton
from rainymine.theme import apply_light_palette


class ReadableWorkspaceTests(WorkspaceLayoutTests):
    def test_all_captions_fit_and_last_command_can_be_scrolled_into_view(self):
        window = self.make_window()
        window.show()
        if window.ribbon_collapsed:
            window.collapse_ribbon()
        for locale in ('mn', 'en'):
            window.set_language(locale, persist=False)
            for width, height in ((960, 640), (1280, 720), (1600, 900)):
                window.resize(width, height)
                for index in range(window.ribbon.count()):
                    window.ribbon.setCurrentIndex(index)
                    self.app.processEvents()
                    scroll = window.ribbon.widget(index)
                    buttons = scroll.findChildren(RibbonButton)
                    self.assertTrue(buttons)
                    for button in buttons:
                        self.assertLessEqual(button.caption_bounds().height(), button.caption_rect().height(), button.text())
                        self.assertGreaterEqual(button.caption_rect().width(), max(button.fontMetrics().horizontalAdvance(word) for word in button.caption().split()))
                        self.assertEqual(button.accessibleName(), button.caption())
                        self.assertLessEqual(button.mapTo(scroll.widget(), button.rect().bottomLeft()).y(), scroll.viewport().height())
                    last = max(buttons, key=lambda b: b.mapTo(scroll.widget(), b.rect().bottomRight()).x())
                    scroll.ensureWidgetVisible(last, 0, 0)
                    self.app.processEvents()
                    self.assertLessEqual(last.mapTo(scroll.viewport(), last.rect().bottomRight()).x(), scroll.viewport().width())
                    self.assertGreaterEqual(last.mapTo(scroll.viewport(), last.rect().topLeft()).x(), 0)

    def test_larger_font_keeps_full_caption_and_native_click(self):
        button = RibbonButton()
        font = QFont(self.app.font())
        font.setPixelSize(20)
        button.setFont(font)
        button.setText('Хөндлөн шалгалт / Cross-validation')
        button.show()
        self.app.processEvents()
        self.addCleanup(button.close)
        self.assertLessEqual(button.caption_bounds().height(), button.caption_rect().height())
        clicked=[]
        button.clicked.connect(lambda: clicked.append(True))
        QTest.mouseClick(button, Qt.MouseButton.LeftButton)
        self.assertEqual(clicked,[True])

    def test_light_palette_replaces_inherited_dark_text_pairs(self):
        original=self.app.palette()
        self.addCleanup(lambda: self.app.setPalette(original))
        dark=QPalette();dark.setColor(QPalette.ColorRole.Text,QColor('white'))
        self.app.setPalette(dark)
        apply_light_palette(self.app)
        palette=self.app.palette()
        self.assertLess(palette.color(QPalette.ColorRole.Text).lightness(),80)
        self.assertGreater(palette.color(QPalette.ColorRole.Base).lightness(),240)

    def test_block_columns_keep_readable_width_and_scroll(self):
        window=self.make_window();window.resize(960,640);window.show();self.app.processEvents()
        self.assertTrue(all(window.block_table.columnWidth(i)>=105 for i in range(1,7)))
        self.assertGreater(window.block_table.horizontalScrollBar().maximum(),0)
