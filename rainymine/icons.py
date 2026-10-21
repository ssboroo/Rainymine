"""Consistent native vector icons. No downloads or external icon fonts."""
from PySide6.QtCore import QByteArray,Qt
from PySide6.QtGui import QIcon,QPixmap,QPainter
from PySide6.QtSvg import QSvgRenderer

PATHS={
 'file':'<path d="M6 3h8l4 4v14H6zM14 3v5h4M9 12h6M9 16h6"/>',
 'folder':'<path d="M3 7V5h6l2 2h10v13H3zM3 10h18"/>',
 'save':'<path d="M4 3h14l3 3v15H3V3zM7 3v6h10V3M7 21v-8h10v8M14 5v2"/>',
 'plus':'<rect x="3" y="3" width="18" height="18" rx="3"/><path d="M12 7v10M7 12h10"/>',
 'upload':'<path d="M12 16V3m-4 4 4-4 4 4M4 15v6h16v-6"/>',
 'download':'<path d="M12 3v13m-4-4 4 4 4-4M4 16v5h16v-5"/>',
 'holes':'<circle cx="5" cy="4" r="2"/><circle cx="13" cy="4" r="2"/><path d="M5 6v4l7 11M13 6v6l6 9M19 3v9"/>',
 'grid':'<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M3 15h18M9 3v18M15 3v18"/>',
 'cube':'<path d="m12 2 9 5v10l-9 5-9-5V7zM3 7l9 5 9-5M12 12v10M7.5 4.5l9 5v10"/>',
 'surface':'<path d="m2 18 6-11 6 5 4-8 4 14-10 4zM2 18l12-6 8 6M8 7l4 15M18 4l-4 8"/>',
 'chart':'<path d="M4 3v17h17M7 15l4-5 4 3 5-8"/><circle cx="11" cy="10" r="1"/><circle cx="15" cy="13" r="1"/>',
 'pick':'<circle cx="12" cy="12" r="7"/><path d="M12 1v6M12 17v6M1 12h6M17 12h6"/>',
 'polygon':'<path d="m4 6 11-3 6 11-8 7-11-6z"/><circle cx="4" cy="6" r="1.5"/><circle cx="15" cy="3" r="1.5"/><circle cx="21" cy="14" r="1.5"/>',
 'undo':'<path d="m8 5-5 5 5 5M3 10h11a6 6 0 0 1 0 12"/>',
 'redo':'<path d="m16 5 5 5-5 5M21 10H10a6 6 0 0 0 0 12"/>',
 'pit':'<path d="M2 5h5v5h5v5h5v5h5M2 10h2v5h5v5h5"/>',
 'gear':'<path d="M3 6h18M3 12h18M3 18h18"/><circle cx="8" cy="6" r="2" fill="white"/><circle cx="16" cy="12" r="2" fill="white"/><circle cx="10" cy="18" r="2" fill="white"/>',
 'search':'<circle cx="10" cy="10" r="6"/><path d="m15 15 6 6"/>',
 'split':'<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M12 4v16"/>',
 'help':'<circle cx="12" cy="12" r="9"/><path d="M9 9a3 3 0 1 1 4 3c-1 .4-1 1-1 2M12 17h.01"/>',
 'label':'<path d="M3 4h8l10 10-7 7L3 10z"/><circle cx="7" cy="8" r="1"/>',
 'expand':'<path d="M8 3H3v5M16 3h5v5M21 16v5h-5M3 16v5h5"/>',
 'chevron':'<path d="m8 9 4 4 4-4"/>',
}

PATHS.update({
 'layers':'<path d="m2 7 10-5 10 5-10 5zM2 12l10 5 10-5M2 17l10 5 10-5"/>',
 'section':'<path d="M7 2 3 22h15l4-20zM3 14l19-7M14 1l-3 22"/>',
 'measure':'<path d="m3 18 15-15 4 4-15 15zM8 13l3 3M12 9l3 3M16 5l3 3"/>',
 'pan':'<path d="M8 13V5a2 2 0 0 1 4 0v7V3a2 2 0 0 1 4 0v9-6a2 2 0 0 1 4 0v10c0 5-4 7-8 7-3 0-4-2-6-5l-4-6q1-3 4-1l2 3"/>',
 'rotate':'<path d="M21 8A9 9 0 1 0 21 17M21 2v7h-7"/>',
 'zoom':'<circle cx="10" cy="10" r="6"/><path d="m15 15 6 6M7 10h6M10 7v6"/>'
})
PATHS['import']=PATHS['download']
PATHS['export']=PATHS['upload']

def icon(kind,color='#142a43'):
    svg='<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><g fill="none" stroke="'+color+'" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">'+PATHS.get(kind,PATHS['gear'])+'</g></svg>'
    pix=QPixmap(64,64);pix.fill(Qt.GlobalColor.transparent)
    painter=QPainter(pix);QSvgRenderer(QByteArray(svg.encode())).render(painter);painter.end()
    return QIcon(pix)

def semantic_icon(text,fallback):
    text=text.lower().replace('\n',' ')
    for words,kind in [(['экспорт','png зураг'],'download'),(['импорт','амсар','survey'],'upload'),
                       (['хадгалах'],'save'),(['нээх'],'folder'),(['шинэ төсөл'],'plus'),
                       (['сэргээх'],'redo'),(['буцаах'],'undo'),(['заавар'],'help'),
                       (['хоёр viewport'],'split'),(['тохиргоо'],'gear')]:
        if any(w in text for w in words):return icon(kind)
    return fallback

def brand_icon():
    from pathlib import Path
    import sys
    root = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[1]))
    return QIcon(str(root / 'assets' / 'rainymine-brand.svg'))
