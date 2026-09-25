import json
from types import SimpleNamespace
import pytest
from data import Client, DataError, write_json
from wiki_interest import execute, plan
from evaluate_model import Harness
import wiki_interest
from test_analysis import config, series

def test_reanalysis_no_network_and_integrity(tmp_path,monkeypatch):
    src=tmp_path/'original'; src.mkdir()
    snapshot={'schema_version':1,'config':config(),'series':[series()]}
    write_json(src/'snapshot.json',snapshot)
    write_json(src/'provenance.json',{'schema_version':1, 'snapshot_sha256':Client.digest(snapshot),
                                      'cache_hits':3, 'http_requests':4, 'sources':[]})
    def forbidden(*a,**kw): raise AssertionError('network must not run')
    monkeypatch.setattr(Client,'get',forbidden)
    criteria=tmp_path/'criteria.json'; write_json(criteria,{'min_growth_pct':90})
    args=SimpleNamespace(command='reanalyze',cache=str(tmp_path/'cache'),offline=False,refresh=False,
                         run=str(src),out=str(tmp_path/'new'),criteria=str(criteria))
    result=execute(args)
    assert result['http_requests']==0 and result['research_order']==[]
    provenance=json.loads((tmp_path/'new'/'provenance.json').read_text())
    assert provenance['schema_version']==2
    assert provenance['source_acquisition']=={'cache_hits':3,'http_requests':4}
    assert provenance['current_run']=={'operation':'reanalyze','cache_hits':0,'http_requests':0}
    assert 'http_requests' not in provenance and 'cache_hits' not in provenance
    args.run=str(tmp_path/'new'); args.out=str(tmp_path/'new-again'); args.criteria=None
    execute(args)
    repeated=json.loads((tmp_path/'new-again'/'provenance.json').read_text())
    assert repeated['source_acquisition']==provenance['source_acquisition']
    assert repeated['current_run']['http_requests']==0
    args.run=str(src)
    snapshot['series'][0]['articles'][0]['daily']['2024-01-01']=1
    write_json(src/'snapshot.json',snapshot); args.out=str(tmp_path/'tampered')
    with pytest.raises(DataError,match='hash mismatch'): execute(args)

def test_run_provenance_separates_source_and_current_counters(tmp_path,monkeypatch):
    planned=config(); planned['series']=[{key:value for key,value in planned['series'][0].items()
                                          if key!='project_totals'}]
    plan_path=tmp_path/'plan.json'; write_json(plan_path,planned)
    snapshot={'schema_version':1,'created_at':'2026-09-25T00:00:00+00:00',
              'config':planned,'series':[series()]}
    def fake_collect(client, config):
        client.hits=3; client.requests=4
        return snapshot
    monkeypatch.setattr(wiki_interest,'collect',fake_collect)
    args=SimpleNamespace(command='run',cache=str(tmp_path/'cache'),offline=False,refresh=False,
                         config=str(plan_path),out=str(tmp_path/'run'))
    execute(args)
    provenance=json.loads((tmp_path/'run'/'provenance.json').read_text())
    assert provenance['source_acquisition']=={'cache_hits':3,'http_requests':4}
    assert provenance['current_run']=={'operation':'run','cache_hits':3,'http_requests':4}

def test_plan_maps_and_saves_provenance(tmp_path,monkeypatch):
    client=Client(tmp_path/'cache'); monkeypatch.setattr(client,'entities',lambda ids:{'Q333':{'sitelinks':{'ukwiki':{'title':'Астрономія'}}}})
    args=SimpleNamespace(qids=['Q333'],languages=['uk'],question='Astronomy?',start='2023-01-01',end='2024-12-31',out=str(tmp_path/'plan.json'))
    result=plan(client,args)
    assert result['series'][0]['articles'][0]['title']=='Астрономія'
    assert (tmp_path/'plan.mapping.json').exists()
    args.languages=['pl']; args.out=str(tmp_path/'missing.json')
    with pytest.raises(DataError,match='Missing sitelinks'): plan(client,args)
    assert not (tmp_path/'missing.json').exists()

def test_harness_blocks_outside_writes(tmp_path):
    h=Harness(tmp_path/'eval')
    with pytest.raises(ValueError): h.call('write_json_file',{'path':'SKILL.md','data':{}})
    with pytest.raises(ValueError): h.call('wiki',{'argv':['run','--config','/tmp/other.json','--out','/tmp/out']})
    with pytest.raises(ValueError): h.call('wiki',{'argv':['run','--cache','/tmp/out']})


def test_harness_blocks_equals_path_bypass(tmp_path):
    h=Harness(tmp_path/'eval')
    with pytest.raises(ValueError): h.call('wiki',{'argv':['run','--config=/tmp/input.json','--out=/tmp/out']})
    with pytest.raises(ValueError): h.call('wiki',{'argv':['discover','--query=x','--cache=/tmp/elsewhere']})
