import json
from copy import deepcopy
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from rainymine.agent_commands import validate_plan,parse_command,execute_plan,AuditJournal
from rainymine.core import demo


class CommandTests(unittest.TestCase):
    def test_allowlist_blocks_code_paths_approval_and_ambiguous_language(self):
        for tool in ('delete','approve_resource','python','sql','save_project'):
            with self.assertRaises(ValueError):validate_plan({'version':1,'steps':[{'tool':tool,'params':{}}]})
        for question in ('эх сорьцыг устга','ангиллыг батал','IDW биш SK','execute python','IDW or NN'):
            with self.assertRaises(ValueError):parse_command(question)
        with self.assertRaises(ValueError):validate_plan({'version':1,'steps':[{'tool':'estimate_blocks','params':{'method':'idw','path':'x'}}]})
        with self.assertRaises(ValueError):validate_plan({'version':1,'steps':[{'tool':'composite','params':{'length':True}}]})

    def test_real_composites_and_estimation_are_detached_atomic_and_cancellable(self):
        from rainymine.estimation import estimate_model
        p=demo();p.workspace['block_model']=estimate_model(p,[499950,5299950,1100,500450,5300400,1500],[250,225,200],{'method':'idw','minimum':2,'neighbors':8,'radii':[220,220,130],'composite_length':10})
        p.workspace['block_model']['blocks'][0].update(density=2.7,domain='Оксид')
        before=p.to_dict();plan=parse_command('5 метрээр композит хийгээд IDW бод');progress=[]
        result=execute_plan(p,plan,'cmd1',progress=lambda a,b:progress.append((a,b)))
        self.assertEqual(p.to_dict(),before);self.assertTrue(result['changed']);candidate=result['candidate']
        self.assertEqual(candidate.workspace['block_model']['params']['composite_length'],5)
        self.assertEqual(candidate.workspace['block_model']['blocks'][0]['density'],2.7)
        self.assertEqual(candidate.workspace['block_model']['blocks'][0]['domain'],'Оксид')
        self.assertGreater(len(candidate.workspace['ai_composites']['samples']),0)
        self.assertEqual(candidate.assays,p.assays);self.assertEqual(candidate.workspace['ai_command_receipts'][-1]['id'],'cmd1')
        self.assertEqual(progress[-1],(200,200))
        with self.assertRaises(RuntimeError):execute_plan(p,plan,cancel=lambda:True)
        bad=deepcopy(plan);bad['steps'][1]['params']['method']='kriging'
        with self.assertRaises(ValueError):execute_plan(p,bad)
        self.assertEqual(p.to_dict(),before)
        p.workspace['block_model']['blocks'][0]['resource_class']='Indicated'
        with self.assertRaises(ValueError):execute_plan(p,plan)

    def test_no_rules_are_invented_and_audit_survives_undo(self):
        p=demo()
        with self.assertRaises(ValueError):execute_plan(p,parse_command('Ангиллын санал гарга'))
        result=execute_plan(p,parse_command('Төслийг шалга'));self.assertFalse(result['changed'])
        with tempfile.TemporaryDirectory() as folder:
            journal=AuditJournal(Path(folder)/'journal.jsonl');journal.append('c','started',plan=parse_command('Төслийг шалга'));journal.append('c','cancelled')
            self.assertEqual([r['event'] for r in journal.tail()],['started','cancelled'])
            self.assertEqual(len(journal.tail(1)),1)


class AgentIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tests.test_workspace import WorkspaceLayoutTests
        WorkspaceLayoutTests.setUpClass();cls.app=WorkspaceLayoutTests.app
    def make_window(self):
        from tests.test_workspace import WorkspaceLayoutTests
        return WorkspaceLayoutTests.make_window(self)
    def pump(self,condition,timeout=20):
        from PySide6.QtTest import QTest
        deadline=time.monotonic()+timeout
        while not condition() and time.monotonic()<deadline:self.app.processEvents();QTest.qWait(5)
        self.assertTrue(condition(),'Background command did not finish')

    def test_chat_execution_has_one_undo_redo_and_durable_receipts(self):
        w=self.make_window();before=w.project.to_dict();old=len(w.history.undo_items)
        with tempfile.TemporaryDirectory() as folder,patch('rainymine.local_engine.data_root',return_value=Path(folder)/'ai'):
            w.support.mode.setCurrentIndex(2);w.support.question.setText('5 метрээр композит хий');w.support.ask()
            self.pump(lambda:not w.support.busy())
            self.assertIn('ai_composites',w.project.workspace);self.assertEqual(len(w.history.undo_items),old+1)
            self.assertTrue(w.history.undo_items[-1][0].startswith('AI:'))
            command_id=w.project.workspace['ai_command_receipts'][-1]['id'];w.undo();self.assertEqual(w.project.to_dict(),before)
            w.redo();self.assertIn('ai_composites',w.project.workspace)
            events=[r['event'] for r in AuditJournal().tail() if r['id']==command_id]
            self.assertEqual(events,['requested','started','prepared','completed','undo_requested','undone','redo_requested','redone'])

    def test_local_model_plan_is_validated_before_any_application_command(self):
        w=self.make_window();before=w.project.to_dict();messages=[]
        class Engine:
            def __init__(self,*args):pass
            def start(self,cancel):pass
            def complete(self,prompt,max_tokens):
                messages.append(prompt)
                return json.dumps({'version':1,'steps':[{'tool':'composite','params':{'length':7}}]})
            def stop(self):pass
        with tempfile.TemporaryDirectory() as folder,patch('rainymine.local_engine.data_root',return_value=Path(folder)/'ai'),patch('rainymine.local_engine.LocalEngine',Engine):
            engine=Path(folder)/'engine';model=Path(folder)/'model';engine.touch();model.touch()
            w.support.engine_path=str(engine);w.support.model_path=str(model);w.support.mode.setCurrentIndex(2)
            w.support.question.setText('prepare regular samples for my project');w.support.ask();self.pump(lambda:not w.support.busy())
            self.assertEqual(w.project.workspace['ai_composites']['length_m'],7)
            self.assertEqual(w.project.assays, __import__('rainymine.core',fromlist=['Project']).Project.from_dict(before).assays)
            self.assertEqual(len(messages),1);self.assertNotIn(str(before['collars'][0]['x']),messages[0][0]['content'])
            w.support.engine=Engine()
            with patch.object(w.support.engine,'complete',return_value=json.dumps({'version':1,'steps':[{'tool':'approve_resource','params':{}}]})):
                current=w.project.to_dict();w.support.question.setText('please handle the project');w.support.ask();self.pump(lambda:not w.support.busy())
                self.assertEqual(w.project.to_dict(),current)
                self.assertTrue(any(r['event']=='planning_failed' for r in AuditJournal().tail()))

    def test_failed_calculation_records_failure_without_undo_or_mutation(self):
        w=self.make_window();before=w.project.to_dict();old=len(w.history.undo_items)
        with tempfile.TemporaryDirectory() as folder,patch('rainymine.local_engine.data_root',return_value=Path(folder)/'ai'),patch('rainymine.background.QMessageBox.warning'):
            w.support.mode.setCurrentIndex(2);w.support.question.setText('OK бод');w.support.ask();self.pump(lambda:not w.support.busy())
            self.assertEqual(w.project.to_dict(),before);self.assertEqual(len(w.history.undo_items),old)
            self.assertEqual(AuditJournal().tail()[-1]['event'],'failed')

    def test_cancelled_worker_and_stale_result_never_apply(self):
        w=self.make_window();before=w.project;events=[];applied=[]
        def operation(cancel,progress):
            while not cancel():time.sleep(.002)
            return 'discard'
        task=w.launch_task('cancel test',operation,applied.append,True,on_event=lambda state,**kw:events.append(state));task.cancel.set()
        self.pump(lambda:not w._engineering_tasks);self.assertEqual(events,['cancelled']);self.assertFalse(applied);self.assertIs(w.project,before)
        events=[]
        def delayed(cancel):time.sleep(.03);return 1
        with patch('rainymine.background.QMessageBox.information'):
            w.launch_task('stale',delayed,applied.append,on_event=lambda state,**kw:events.append(state));w.project=deepcopy(w.project)
            self.pump(lambda:not w._engineering_tasks)
        self.assertEqual(events,['stale']);self.assertFalse(applied)
