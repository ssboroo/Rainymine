"""GUI-thread apply for locally planned AI commands; no arbitrary model code."""
import json
from pathlib import Path
import re
from uuid import uuid4
from .agent_commands import AuditJournal,FORBIDDEN,parse_command,validate_plan,execute_plan


def run_question(window,question,dock):
    if re.search(FORBIDDEN,question):raise ValueError('AI cannot approve resources, delete source data or execute code')
    if window.computing or window._engineering_tasks:raise ValueError('Finish or cancel the active calculation first')
    source=window.project;journal=AuditJournal();command_id=uuid4().hex
    journal.append(command_id,'requested',question=question)
    def work(worker):
        worker.progress.emit('Зөвшөөрөгдсөн командын төлөвлөгөө…')
        try:plan=parse_command(question)
        except ValueError:
            if not Path(dock.engine_path).is_file() or not Path(dock.model_path).is_file():raise
            from .local_engine import LocalEngine
            if dock.engine is None:dock.engine=LocalEngine(dock.engine_path,dock.model_path)
            dock.engine.start(worker.cancelled.is_set)
            system=('Return JSON only, version 1 steps (max 6), each {"tool":...,"params":...}. '
                    'Allowed: validate_project {}, composite {"length":5,"minimum_coverage":1}, '
                    'estimate_blocks {"method":"nearest|idw|kriging|simple_kriging"}, qaqc_summary {}, classification_proposal {}. '
                    'Use existing application geometry/search/variogram/rules only. Never invent configuration. '
                    'Never approve, delete, import, export, save files, run Python/SQL/shell, change licensing, or use network tools. '
                    'For unsupported/ambiguous requests return {"unsupported":true}. No project data is included in this prompt.')
            plan=validate_plan(json.loads(dock.engine.complete([{'role':'system','content':system},{'role':'user','content':question}],max_tokens=512)))
        if worker.cancelled.is_set():raise RuntimeError('AI plan cancelled')
        return plan
    def planned(plan):
        if source is not window.project:
            journal.append(command_id,'stale');dock.append('AI','Төсөл өөрчлөгдсөн. Дахин ажиллуулна уу.');return
        journal.append(command_id,'started',plan=plan)
        dock.append('AI — төлөвлөгөө',json.dumps(plan,ensure_ascii=False,indent=2))
        def operation(cancel,progress):return execute_plan(source,plan,command_id,cancel,progress)
        def apply(result):
            # Fail closed if the durable intent cannot be recorded before mutation.
            journal.append(command_id,'prepared',changed=result['changed'])
            if result['changed']:
                result['candidate'].workspace['ai_command_receipts'][-1]['status']='applied'
                window.commit(result['candidate'])
            dock.append('AI — үр дүн',json.dumps(result['results'],ensure_ascii=False,indent=2))
            dock.status.setText('Дууслаа · өөрчлөлтийг Ctrl+Z-ээр буцаана.' if result['changed'] else 'Дууслаа · төсөл өөрчлөгдөөгүй.')
        def event(state,**details):
            if state=='completed' and any(s['tool'] in ('composite','estimate_blocks','classification_proposal') for s in plan['steps']) and window.history.undo_items:
                _,snapshot=window.history.undo_items[-1];window.history.undo_items[-1]=('AI:'+command_id,snapshot)
            try:journal.append(command_id,state,**details)
            except OSError as exc:dock.append('Audit',f'Бүртгэл бичихэд алдаа: {exc}')
        task=window.launch_task('AI команд — background / Undo',operation,apply,with_progress=True,on_event=event)
        dock._agent_task=task;dock.ask_button.setEnabled(False)
        def finished():dock._agent_task=None;dock.ask_button.setEnabled(True)
        task.worker.finished.connect(finished)
    worker_holder={}
    def audited_plan(plan):
        if dock.worker and dock.worker.cancelled.is_set():return
        worker_holder['planned']=True
        if window.guard(lambda:planned(plan)) is False:journal.append(command_id,'planning_failed',error='Plan could not start')
    dock.start_worker(work,audited_plan)
    worker=dock.worker
    worker.failure.connect(lambda message:journal.append(command_id,'planning_failed',error=message))
    def finished_plan():
        if worker.cancelled.is_set() and not worker_holder.get('planned'):journal.append(command_id,'cancelled',phase='planning')
    worker.finished.connect(finished_plan)
