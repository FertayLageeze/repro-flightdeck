import json
import pytest
from flightdeck.core import ContractError
from flightdeck.policies import JevPolicy,OllamaPolicy,action_space,RulePolicy


def initial():
    return {'task':'test','metric':'accuracy','executed':False,'exit_code':None,'artifact':{'path':'p.csv','columns':{'id':'id','prediction':'prediction'}},'candidates':[],'verification':None,'failure':None}


def response(confidence=.9):
    return {'model':'jev-fixture','answers':{'next_action':{'type':'choice','choice':'execute','probabilities':{'execute':.9,'stop':.1},'confidence':confidence}},'usage':{'input_tokens':12}}


def test_jev_wire_contract(monkeypatch):
    monkeypatch.setenv('TYPESAFE_API_KEY','fixture')
    def transport(url,body,key):
        assert url=='https://api.typesafe.ai/v1/systemone' and key=='fixture'
        assert body['questions']['next_action']['type']=='choice'
        assert set(body['questions']['next_action']['criteria'])=={'stop','execute'}
        return response()
    action,meta=JevPolicy(transport=transport).decide(initial())
    assert action=={'action':'execute'} and meta['confidence']==.9


def test_no_key_no_fake_success(monkeypatch):
    monkeypatch.delenv('TYPESAFE_API_KEY',raising=False)
    with pytest.raises(ContractError):JevPolicy()


def test_low_confidence_abstains_or_escalates(monkeypatch):
    monkeypatch.setenv('TYPESAFE_API_KEY','fixture')
    assert JevPolicy(transport=lambda *a:response(.2)).decide(initial())[0]['action']=='stop'
    action,meta=JevPolicy(transport=lambda *a:response(.2),fallback=RulePolicy()).decide(initial())
    assert action['action']=='execute' and 'fallback' in meta


@pytest.mark.parametrize('mutation',['unknown','nan','sum','mismatch','choice'])
def test_invalid_jev_distribution_rejected(monkeypatch,mutation):
    monkeypatch.setenv('TYPESAFE_API_KEY','fixture')
    result=response();answer=result['answers']['next_action']
    if mutation=='unknown':answer['choice']='shell'
    if mutation=='nan':answer['confidence']=float('nan')
    if mutation=='sum':answer['probabilities']['execute']=.8
    if mutation=='mismatch':answer['probabilities']['unexpected']=0
    if mutation=='choice':answer['choice']='stop'
    with pytest.raises(ContractError):JevPolicy(transport=lambda *a:result).decide(initial())


def test_ollama_structured_output():
    def transport(url,body):
        assert url.startswith('http://127.0.0.1:11434/') and body['stream'] is False
        assert 'execute' in body['format']['properties']['choice']['enum']
        return {'message':{'content':json.dumps({'choice':'execute'})},'model':'fixture'}
    assert OllamaPolicy('fixture',transport).decide(initial())[0]['action']=='execute'


def test_ambiguous_recovery_stops():
    state=initial();state.update(executed=True,exit_code=0,failure='missing',candidates=[{'path':'a.csv','columns':['id','prediction']},{'path':'b.csv','columns':['id','prediction']}])
    assert RulePolicy().decide(state)[0]['action']=='stop'


def test_terminal_state_cannot_bind_scored_result():
    state=initial();state.update(executed=True,exit_code=0,verification={'passed':False})
    assert list(action_space(state))==['stop']
