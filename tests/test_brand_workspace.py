"""Reference design integration: tool reachability, reversible locale and geometry identity."""
from copy import deepcopy
import unittest
from PySide6.QtCore import Qt
from tests import test_workspace
from tests.test_scene import NoRenderWindow
from rainymine.i18n import tr, set_language
from rainymine.scene import Scene
from rainymine.core import demo
from rainymine.estimation import make_blocks


class BrandWorkspaceTests(test_workspace.WorkspaceLayoutTests):
    def tearDown(self):
        set_language('mn', persist=False)

    def test_every_original_tool_is_reachable_in_catalog(self):
        window=self.make_window()
        sources=set(window.tool_catalog)
        for title in ('RBF хүдрийн\nгадарга','Ил уурхайн\nоновчлол','Excel\nимпорт',
                      'STL\nимпорт','STL\nэкспорт','Өгөгдлийн сан\nунших',
                      'Хөндлөн\nшалгалт','Гадаад\nхарьцуулалт','Хагарлын\nхавтгай',
                      'MILP\nОновчлол','Зам /\nТээвэр','X / Y / Z\nзүсэлт'):
            self.assertIn(title,sources)
        self.assertGreaterEqual(len(window.tool_entries()),50)
        self.assertTrue(all(not button.icon().isNull() for button in window.tool_catalog.values()))

    def test_locale_roundtrip_never_changes_project_or_numeric_values(self):
        window=self.make_window();before=deepcopy(window.project)
        original=window.ribbon.tabText(0)
        window.set_language('en',persist=False)
        self.assertEqual(window.ribbon.tabText(0),'Project')
        self.assertEqual(window.ribbon.tabText(3),'Block model')
        self.assertEqual(window.block_model.headerData(1,Qt.Orientation.Horizontal),'Easting (m)')
        self.assertEqual(window.project,before)
        self.assertEqual(len(window.tool_entries()),len(window.tool_catalog))
        window.set_language('mn',persist=False)
        self.assertEqual(window.ribbon.tabText(0),original)
        self.assertEqual(window.block_model.headerData(1,Qt.Orientation.Horizontal),'Зүүн (м)')
        self.assertEqual(window.project,before)

    def test_block_selection_updates_inspector_with_actual_values(self):
        window=self.make_window();window.block_row_selected(window.block_model.index(0,0))
        block=window.block_model.blocks[0]
        self.assertEqual(window.inspector_values['x'].text(),f'{block["x"]:,.3f}')
        self.assertEqual(window.inspector_values['density'].text(),'—')
        window.toggle_coordinate_grid(False);window.display_buttons['Тор'].setChecked(False)
        window.refresh()
        self.assertFalse(window.scene.coordinate_grid.GetVisibility())

    def test_language_refresh_keeps_user_names_and_conversation(self):
        window=self.make_window()
        window.project.name='Төсөл'
        h=window.project.collars[0]
        window.project.workspace.setdefault('strings',[]).append(
            {'name':'Гадарга','closed':False,'points':[[h.x,h.y,h.z],[h.x+10,h.y+10,h.z]]})
        window.support.append('User','Keep this customer conversation.')
        original=window.support.chat.toPlainText()
        window.set_language('en',persist=False);window.refresh()
        self.assertEqual(window.brand_project.text(),'Төсөл')
        self.assertIn('drillholes',window.project_summary.text())
        self.assertEqual(window.support.chat.toPlainText(),original)
        found=[]
        for i in range(window.layer_list.topLevelItemCount()):
            group=window.layer_list.topLevelItem(i)
            for j in range(group.childCount()):
                item=group.child(j)
                if item.data(0,Qt.ItemDataRole.UserRole)=='string_0':found.append(item.text(0))
        self.assertEqual(found,['Гадарга'])

    def test_small_window_keeps_inspector_inside_the_sidebar(self):
        window=self.make_window();window.resize(1080,740);window.show();self.app.processEvents()
        value=window.inspector_values['dimensions']
        point=value.mapTo(window.support.widget(), value.rect().bottomLeft())
        self.assertLessEqual(point.y(),window.support.widget().height())
        self.assertTrue(window.help_scroller.widgetResizable())
        self.assertEqual(window.scene.coordinate_grid.GetXAxisLabelVisibility(),0)
        self.assertIn('E:',window.scene.coordinate_text.GetInput())

    def test_cutaway_retains_selected_only_label_policy(self):
        window=self.make_window();window.toggle_labels(False)
        for value in (False,True):
            window.toggle_cutaway(value)
            for label in window.scene.labels:
                if label.GetInput()!=window.scene.selected_hole:
                    self.assertFalse(label.GetVisibility())


class CutawayTests(unittest.TestCase):
    def test_cutaway_preserves_source_block_ids_and_restores_full_mesh(self):
        project=demo();bounds=[500000,5300000,1200,500040,5300040,1240]
        blocks=make_blocks(bounds,[10,10,10])
        for i,block in enumerate(blocks):block['grade']=i/len(blocks)
        project.workspace['block_model']={'blocks':blocks,'bounds':bounds,'size':[10]*3}
        project.workspace['block_display']='blocks'
        scene=Scene(NoRenderWindow());scene.load(project);scene.configure_presentation()
        source=scene.sources['blocks'];cells=source.GetNumberOfCells()
        self.assertEqual(cells,6*len(blocks))
        scene.set_cutaway(True)
        mapper=scene.actors['blocks'].GetMapper();mapper.Update()
        output=mapper.GetInput()
        self.assertLess(output.GetNumberOfCells(),cells)
        self.assertGreater(output.GetNumberOfCells(),0)
        for cell in range(output.GetNumberOfCells()):
            info=scene.identify(scene.actors['blocks'],cell)
            self.assertIn(info['block_index'],range(len(blocks)))
            self.assertEqual(info['grade'],blocks[info['block_index']]['grade'])
        self.assertEqual(source.GetNumberOfCells(),cells)
        scene.set_section((90,0,20));scene.set_cutaway(False);scene.set_section(None)
        mapper.Update();self.assertEqual(mapper.GetInput().GetNumberOfCells(),cells)
        self.assertEqual(project.workspace['block_model']['blocks'],blocks)

    def test_unknown_or_user_text_is_never_machine_translated(self):
        set_language('en',persist=False)
        self.assertEqual(tr('Customer deposit Өндөр-123'),'Customer deposit Өндөр-123')
        set_language('mn',persist=False)


class EnglishHelpTests(unittest.TestCase):
    def test_every_reviewed_topic_has_english_instructions(self):
        from rainymine.support_knowledge import TOPICS
        from rainymine.support_knowledge_en import HELP, localize
        from rainymine.local_support import render_selection
        import json
        self.assertEqual({t['id'] for t in TOPICS},set(HELP))
        for topic in TOPICS:
            english=localize(topic,'en')
            self.assertTrue(english['steps'])
            text,selected=render_selection(json.dumps({'topic_ids':[topic['id']]}),[topic],'en')
            self.assertEqual(selected,topic['id'])
            self.assertIn('Source: Rainymine help',text)
            self.assertNotRegex(text,'[А-Яа-яӨөҮү]')


class StartupContrastTests(unittest.TestCase):
    def test_dark_splash_preserves_the_light_upper_stratum(self):
        from PySide6.QtWidgets import QApplication
        from rainymine.startup import StartupScreen
        app=QApplication.instance() or QApplication([])
        splash=StartupScreen()
        self.addCleanup(splash.close)
        self.assertTrue(splash.artwork_loaded)
        image=splash.pixmap().toImage();w=image.width();h=image.height()
        light=0
        for y in range(int(h*.08),int(h*.24)):
            for x in range(int(w*.44),int(w*.56)):
                color=image.pixelColor(x,y)
                light += min(color.red(),color.green(),color.blue())>220
        self.assertGreater(light,50,'Dark background has erased the upper logo stratum')
