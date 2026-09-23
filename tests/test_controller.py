import csv
import json
from pathlib import Path
import sys
import pytest

from flightdeck.core import Controller,ContractError,audit_run,contained,verify_predictions
from flightdeck.policies import RulePolicy
from flightdeck.report import render


def csvfile(path,fields,rows):
    with path.open("w",newline="",encoding="utf-8") as f:
        w=csv.writer(f);w.writerow(fields);w.writerows(rows)
    return path


@pytest.fixture
def card(tmp_path):
    folder=tmp_path/"card";folder.mkdir()
    csvfile(folder/"truth.csv",["id","target"],[("a","1"),("b","0")])
    (folder/"experiment.py").write_text("from pathlib import Path\nPath('export.csv').write_text('sample_id,y_pred\\na,1\\nb,0\\n',encoding='utf-8')\n",encoding="utf-8")
    manifest={"id":"test","title":"Test","scope":"test fixture","source":"https://example.org/paper","inputs":["experiment.py"],"command":["{python}","experiment.py"],"truth":"truth.csv","metric":"accuracy","acceptance":{"min":1,"max":1},"artifact":{"path":"expected.csv","columns":{"id":"id","prediction":"prediction"}},"timeout_seconds":5}
    path=folder/"manifest.json";path.write_text(json.dumps(manifest),encoding="utf-8")
    return path


def test_recovery_and_strict_baseline(card,tmp_path):
    strict=Controller(card,tmp_path/"strict",RulePolicy(strict=True)).run()
    fixed=Controller(card,tmp_path/"fixed",RulePolicy()).run()
    assert strict["status"]=="unresolved"
    assert fixed["status"]=="verified"
    assert fixed["result"]["value"]==1
    assert [e for e in fixed["events"] if e["kind"]=="binding_repair"]
    assert audit_run(tmp_path/"fixed")["integrity"]=="valid"
    assert str(tmp_path) not in json.dumps(fixed)
    assert str(tmp_path).replace('\\','\\\\') not in json.dumps(fixed)
    assert 'Users' not in json.dumps(fixed)


def test_wrong_predictions_do_not_pass(card,tmp_path):
    (card.parent/"experiment.py").write_text("from pathlib import Path\nPath('export.csv').write_text('sample_id,y_pred\\na,0\\nb,1\\n',encoding='utf-8')\n",encoding="utf-8")
    result=Controller(card,tmp_path/"bad",RulePolicy()).run()
    assert result["status"]=="unresolved" and result["result"]["value"]==0


def test_successful_exit_is_not_evidence(card,tmp_path):
    (card.parent/"experiment.py").write_text("print('SUCCESS accuracy=1.0')",encoding="utf-8")
    result=Controller(card,tmp_path/"fake",RulePolicy(),max_steps=5).run()
    assert result["status"]!="verified" and result["result"] is None


def test_failed_exit_rejects_artifact(card,tmp_path):
    with (card.parent/"experiment.py").open("a") as f:f.write("raise SystemExit(1)\n")
    result=Controller(card,tmp_path/"exit",RulePolicy()).run()
    assert result["status"]=="unresolved" and result["result"] is None


def test_worker_cannot_change_frozen_protocol(card,tmp_path):
    (card.parent/"experiment.py").write_text("from pathlib import Path\nPath('../truth.csv').write_text('id,target\\na,0\\nb,1\\n')",encoding="utf-8")
    result=Controller(card,tmp_path/"tamper",RulePolicy()).run()
    assert result["status"]=="integrity_failed"


def test_trace_artifact_and_source_tampering_detected(card,tmp_path):
    run=tmp_path/"run";Controller(card,run,RulePolicy()).run()
    artifact=run/"workspace/export.csv";original=artifact.read_bytes()
    artifact.write_text('sample_id,y_pred\na,0\nb,1\n',encoding='utf-8')
    with pytest.raises(ContractError):audit_run(run)
    artifact.write_bytes(original)
    source=run/"workspace/experiment.py";source.write_text("# edited",encoding="utf-8")
    with pytest.raises(ContractError,match="Source/input"):audit_run(run)


def test_no_output_overwrite(card,tmp_path):
    out=tmp_path/"existing";out.mkdir()
    with pytest.raises(ContractError):Controller(card,out,RulePolicy())


def test_timeout(card,tmp_path):
    manifest=json.loads(card.read_text());manifest["timeout_seconds"]=.1;card.write_text(json.dumps(manifest))
    (card.parent/"experiment.py").write_text("import time\ntime.sleep(2)")
    result=Controller(card,tmp_path/"timeout",RulePolicy()).run()
    assert result["status"]=="unresolved" and result["result"] is None


@pytest.mark.parametrize("rows",[[('a',1)], [('a',1),('a',0)], [('a',1),('b',0),('c',1)], [('',1),('b',0)]])
def test_id_contract(tmp_path,rows):
    truth=csvfile(tmp_path/'truth.csv',['id','target'],[('a',1),('b',0)])
    predicted=csvfile(tmp_path/'pred.csv',['id','prediction'],rows)
    with pytest.raises(ContractError):verify_predictions(truth,predicted,{'id':'id','prediction':'prediction'},'accuracy',{'min':0,'max':1})


@pytest.mark.parametrize("value",['nan','inf','-inf','-1','1','0'])
def test_invalid_probabilities(tmp_path,value):
    truth=csvfile(tmp_path/'truth.csv',['id','target'],[('a',1)])
    predicted=csvfile(tmp_path/'pred.csv',['id','probability'],[('a',value)])
    with pytest.raises(ContractError):verify_predictions(truth,predicted,{'id':'id','probability':'probability'},'nll',{'min':0,'max':1})


def test_nll_and_rmse_independent_values(tmp_path):
    import math
    truth=csvfile(tmp_path/'truth.csv',['id','target'],[('a',1),('b',0)])
    predicted=csvfile(tmp_path/'pred.csv',['id','p'],[('b',.2),('a',.8)])
    result=verify_predictions(truth,predicted,{'id':'id','probability':'p'},'nll',{'min':0,'max':1})
    assert result['value']==pytest.approx(-math.log(.8))
    result=verify_predictions(truth,predicted,{'id':'id','prediction':'p'},'rmse',{'min':0,'max':1})
    assert result['value']==pytest.approx(.2)


def test_interval_order_and_coverage(tmp_path):
    truth=csvfile(tmp_path/'truth.csv',['id','target'],[('a',1),('b',0)])
    predicted=csvfile(tmp_path/'pred.csv',['id','lower','upper'],[('a',1,2),('b',2,3)])
    columns={'id':'id','lower':'lower','upper':'upper'}
    assert verify_predictions(truth,predicted,columns,'coverage',{'min':0,'max':1})['value']==.5
    csvfile(predicted,['id','lower','upper'],[('a',2,1),('b',2,3)])
    with pytest.raises(ContractError):verify_predictions(truth,predicted,columns,'coverage',{'min':0,'max':1})


def test_path_traversal_and_report_injection(tmp_path):
    with pytest.raises(ContractError):contained(tmp_path,'../escape.csv')
    with pytest.raises(ContractError):contained(tmp_path,str(tmp_path.resolve()))
    output=tmp_path/'report.html';render({'title':'</script><script>alert(1)</script>'},output)
    assert '</script><script>alert(1)' not in output.read_text(encoding='utf-8')


def test_unknown_action_and_budget(card,tmp_path):
    class BadPolicy:
        name='adversarial fixture'
        def decide(self,state):return {'action':'change_acceptance','min':0},{'live_model':False}
    result=Controller(card,tmp_path/'badpolicy',BadPolicy(),max_steps=3).run()
    assert result['status']=='budget_exhausted' and result['result'] is None


def test_secret_environment_not_forwarded(card,tmp_path,monkeypatch):
    monkeypatch.setenv('TYPESAFE_API_KEY','test-secret-not-real')
    with (card.parent/'experiment.py').open('a') as f:f.write("import os\nassert 'TYPESAFE_API_KEY' not in os.environ\n")
    assert Controller(card,tmp_path/'env',RulePolicy()).run()['status']=='verified'
