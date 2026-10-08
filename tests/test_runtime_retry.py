from types import SimpleNamespace
import pytest
from runtime_service import transform

def fake(replies):
    calls=[]
    def create(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=next(replies)))])
    return SimpleNamespace(model='test',client=SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))),calls

def payload():
    return {'mode':'arguments','schema':{'type':'object','properties':{'old':{'type':'string'},'new':{'type':'string'}},'required':['old','new'],'additionalProperties':False},'evidence':[{'capability':'source.read','output':{'ok':True,'value':{'content':'original source'}}}]}

def test_invalid_json_and_unmatched_patch_are_retried_before_return():
    client,calls=fake(iter(['not JSON','{"old":"absent","new":"replacement"}','{"old":"original","new":"replacement"}']))
    assert transform(payload(),client)=={'resolved':{'old':'original','new':'replacement'}}
    assert len(calls)==3

def test_retry_limit_is_three_total_attempts():
    client,calls=fake(iter(['not JSON']*4))
    with pytest.raises(ValueError): transform(payload(),client)
    assert len(calls)==3


def test_nested_execution_status():
    from run_live_solution import execution_status
    assert execution_status({'execution':{'status':'error'}})=='error'
    assert execution_status({'execution':{'status':'success'}})=='success'
    assert execution_status({'status':'running'})=='running'

def test_patch_must_match_source_not_only_diff():
    from runtime_service import validate_arguments
    data=payload()
    data['evidence'].append({'capability':'evidence.read','output':{'ok':True,'value':{'content':'diff-only fragment'}}})
    with pytest.raises(ValueError):
        validate_arguments({'old':'diff-only','new':'changed'},data['schema'],data['evidence'])
