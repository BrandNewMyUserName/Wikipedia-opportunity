import io
import json
from urllib.error import HTTPError
import pytest
import data
from data import Client, DataError

def response(obj):
    return io.BytesIO(json.dumps(obj).encode())

def test_cache_offline_integrity(tmp_path,monkeypatch):
    monkeypatch.setattr(data,'urlopen',lambda *a,**kw:response({'items':[{'views':1}]}))
    c=Client(tmp_path); expected=c.get('https://example.org/a')
    c=Client(tmp_path,offline=True)
    assert c.get('https://example.org/a')==expected and c.requests==0
    with pytest.raises(DataError,match='Offline cache miss'): c.get('https://example.org/b')
    path=next(tmp_path.glob('*.json')); d=json.loads(path.read_text()); d['data']={}; path.write_text(json.dumps(d))
    with pytest.raises(DataError,match='Corrupt cache'): c.get('https://example.org/a')

def test_429_retry_and_404_missing(tmp_path,monkeypatch):
    calls=[]
    def fetch(*args,**kwargs):
        calls.append(1)
        if len(calls)<3: raise HTTPError('url',429,'rate',{'Retry-After':'0'},None)
        return response({'items':[]})
    monkeypatch.setattr(data,'urlopen',fetch); monkeypatch.setattr(data.time,'sleep',lambda _:None)
    c=Client(tmp_path); assert c.get('https://example.org/rate')=={'items':[]}; assert c.requests==3
    def missing(*a,**kw): raise HTTPError('url',404,'missing',{},None)
    monkeypatch.setattr(data,'urlopen',missing)
    assert c.get('https://example.org/missing',missing_ok=True)['missing']
    with pytest.raises(DataError,match='HTTP 404'): c.get('https://example.org/strict')

def test_retry_budget(tmp_path,monkeypatch):
    def fail(*a,**kw): raise HTTPError('url',503,'down',{},None)
    monkeypatch.setattr(data,'urlopen',fail); monkeypatch.setattr(data.time,'sleep',lambda _:None)
    c=Client(tmp_path)
    with pytest.raises(DataError,match='Retries exhausted'): c.get('https://example.org/down')
    assert c.requests==4

def test_unicode_and_reserved_title_encoding(tmp_path,monkeypatch):
    urls=[]
    def fetch(url,**kw): urls.append(url); return {'items':[]}
    c=Client(tmp_path); monkeypatch.setattr(c,'get',fetch)
    c.series('uk','А / B?','2024-01-01','2024-01-31')
    assert '%D0%90_%2F_B%3F' in urls[0]

@pytest.mark.parametrize('page',[{'missing':True}, {'ns':0,'title':'X','pageprops':{'disambiguation':''}},
                                 {'ns':0,'title':'X','pageprops':{'wikibase_item':'Q2'}}])
def test_semantic_validation(page,tmp_path,monkeypatch):
    c=Client(tmp_path); monkeypatch.setattr(c,'api',lambda *a,**kw:{'query':{'pages':[page]}})
    with pytest.raises(DataError): c.validate_article('uk',{'title':'X','qid':'Q1'},'2024-01-01')

def test_range_batch_overlap_and_offline(tmp_path,monkeypatch):
    requests=[]
    def fetch(req,**kwargs):
        requests.append(req.full_url)
        start,end=req.full_url.rsplit('/',2)[1:]
        rows=[{'timestamp':d.replace('-','')+'00','views':5} for d in data.days(
            start[:4]+'-'+start[4:6]+'-'+start[6:8],end[:4]+'-'+end[4:6]+'-'+end[6:8])]
        return response({'items':rows})
    monkeypatch.setattr(data,'urlopen',fetch)
    c=Client(tmp_path)
    a=c.series('uk','Астрономія','2023-01-01','2023-12-31')
    assert len(a)==365 and len(requests)==1
    c=Client(tmp_path)
    b=c.series('uk','Астрономія','2023-06-01','2024-02-29')
    assert len(requests)==2 and requests[-1].endswith('/2024010100/2024022900')
    c=Client(tmp_path,offline=True)
    assert c.series('uk','Астрономія','2023-06-01','2024-02-29')==b and c.requests==0
    c=Client(tmp_path,refresh=True)
    c.series('uk','Астрономія','2023-06-01','2024-02-29')
    assert len(requests)==3 and requests[-1].endswith('/2023060100/2024022900')

def test_range_rejects_unexpected_dates(tmp_path,monkeypatch):
    monkeypatch.setattr(data,'urlopen',lambda *a,**kw:response({'items':[{'timestamp':'2025010100','views':3}]}))
    with pytest.raises(DataError,match='Out-of-window'):
        Client(tmp_path).series('uk','X','2023-01-01','2023-12-31')
