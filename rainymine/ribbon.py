"""Readable native ribbon commands: wrapped captions without elision."""
from PySide6.QtCore import Qt, QSize, QRect, QEvent
from PySide6.QtGui import QIcon, QPainter, QPalette
from PySide6.QtWidgets import QToolButton, QStyle, QStyleOptionToolButton, QSizePolicy


class RibbonButton(QToolButton):
    """Keep the full action text for localization, search and accessibility.

    Qt's text-under-icon toolbutton can elide even explicit multiline captions.
    Paint a native button with an icon beside a measured, word-wrapped caption.
    Width grows for translations rather than shrinking the font or clipping text.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('ribbonCommand')
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setIconSize(QSize(24, 24))

    def caption(self):
        return ' '.join(self.text().split())

    def caption_rect(self):
        return QRect(42, 6, self.width()-50, self.height()-12)

    def caption_bounds(self, width=None):
        return self.fontMetrics().boundingRect(
            QRect(0, 0, (width or self.width())-50, 1000),
            Qt.TextFlag.TextWordWrap, self.caption())

    def fit_caption(self):
        if not self.text():
            return
        width = 176
        longest = max(self.fontMetrics().horizontalAdvance(word)
                      for word in self.caption().split())
        width = max(width, longest+54)
        while self.caption_bounds(width).height() > self.fontMetrics().lineSpacing()*2:
            width += 12
        height = max(54, self.fontMetrics().lineSpacing()*2+16)
        self.setFixedSize(width, height)
        self.setAccessibleName(self.caption())
        self.setToolTip(self.caption())
        self.updateGeometry()
        self.update()

    def setText(self, text):
        super().setText(text)
        self.fit_caption()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() in (QEvent.Type.FontChange, QEvent.Type.StyleChange):
            self.fit_caption()

    def paintEvent(self, event):
        option = QStyleOptionToolButton()
        self.initStyleOption(option)
        option.text = ''
        option.icon = QIcon()
        painter = QPainter(self)
        self.style().drawComplexControl(QStyle.ComplexControl.CC_ToolButton,
                                       option, painter, self)
        mode = QIcon.Mode.Normal if self.isEnabled() else QIcon.Mode.Disabled
        self.icon().paint(painter, QRect(10, (self.height()-24)//2, 24, 24),
                          Qt.AlignmentFlag.AlignCenter, mode)
        group = QPalette.ColorGroup.Active if self.isEnabled() else QPalette.ColorGroup.Disabled
        painter.setPen(self.palette().color(group, QPalette.ColorRole.ButtonText))
        painter.setFont(self.font())
        painter.drawText(self.caption_rect(),
                         Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter |
                         Qt.TextFlag.TextWordWrap, self.caption())
