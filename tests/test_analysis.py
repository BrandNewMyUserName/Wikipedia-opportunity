import copy
import pytest
from analysis import assess, analyze, validate_config, DEFAULT_CRITERIA
from data import DataError, days, months

START, END = '2023-01-01','2024-12-31'

def series():
    return {'id':'uk','label':'Астрономія','language':'uk',
            'articles':[{'qid':'Q333','title':'Астрономія','url':'https://uk.wikipedia.org/wiki/Астрономія',
                         'warnings':[], 'daily':{d:100 if d<'2024' else 150 for d in days(START,END)}}],
            'project_totals':{m:1000000 for m in months(START,END)}}

def config():
    return {'schema_version':1,'question':'Astronomy growth?','start':START,'end':END,
            'series':[{k:v for k,v in series().items() if k!='project_totals'}]}

def test_sustained_growth_and_denominators():
    s=series(); r=assess(s,START,END,DEFAULT_CRITERIA)
    assert r['baseline_views']==36500 and r['latest_views']==54900
    assert r['growth_pct']==pytest.approx(50.41095890410959)
    assert r['signal']=='research_next' and r['positive_yoy_months']==12
    s['project_totals']={m:1000000 if m<'2024' else 2000000 for m in months(START,END)}
    r=assess(s,START,END,DEFAULT_CRITERIA)
    assert r['share_growth_pct']<0 and r['signal']=='no_clear_growth'

def test_missing_is_not_zero():
    s=series(); del s['articles'][0]['daily']['2024-03-02']
    r=assess(s,START,END,DEFAULT_CRITERIA)
    assert r['latest_views'] is None and r['growth_pct'] is None
    assert r['signal']=='insufficient_data'
    assert r['monthly'][14]['views'] is None

def test_recorded_zero_is_valid():
    s=series(); s['articles'][0]['daily']['2024-03-02']=0
    r=assess(s,START,END,DEFAULT_CRITERIA)
    assert r['latest_views']==54750 and r['coverage']==1

def test_spike_is_fragile():
    s=series(); s['articles'][0]['daily']['2024-03-02']=1000000
    r=assess(s,START,END,DEFAULT_CRITERIA)
    assert r['signal']=='fragile' and 'spike_concentration' in r['warnings']

def test_zero_baseline_no_infinite_growth():
    s=series()
    s['articles'][0]['daily']={d:0 if d<'2024' else 1 for d in days(START,END)}
    r=assess(s,START,END,DEFAULT_CRITERIA)
    assert r['growth_pct'] is None and r['signal']=='insufficient_data'

def test_basket_requires_all_members_each_day():
    s=series(); b=copy.deepcopy(s['articles'][0]); b['qid']='Q523'; b['title']='Sun'
    del b['daily']['2024-01-01']; s['articles'].append(b)
    assert assess(s,START,END,DEFAULT_CRITERIA)['signal']=='insufficient_data'

def test_non_equivalent_baskets_not_ranked():
    a,b=series(),series(); b['id']='cs'; b['articles'][0]['qid']='Q523'
    r=analyze({'config':config(),'series':[a,b]})
    assert not r['comparable_baskets'] and r['research_order']==[]

@pytest.mark.parametrize('change',[{'start':'2023-01-02'}, {'end':'2024-12-30'}, {'start':'2015-06-01'},
                                   {'end':'2099-12-31'}, {'start':'2024-01-01'}, {'criteria':{'min_positive_months':1.5}},
                                   {'criteria':{'bad':1}}, {'criteria':{'min_growth_pct':float('nan')}}])
def test_reject_bad_config(change):
    c=config(); c.update(change)
    with pytest.raises(DataError): validate_config(c)

def test_low_volume_and_move_downgrade():
    s=series(); s['articles'][0]['daily']={d:1 if d<'2024' else 2 for d in days(START,END)}
    assert assess(s,START,END,DEFAULT_CRITERIA)['signal']=='fragile'
    s=series(); s['articles'][0]['warnings']=['page_move_in_window']
    assert assess(s,START,END,DEFAULT_CRITERIA)['signal']=='fragile'

def test_denominator_missing_not_hidden():
    s=series(); del s['project_totals']['2024-03']
    r=assess(s,START,END,DEFAULT_CRITERIA)
    assert r['growth_pct'] is not None and r['share_growth_pct'] is None
    assert r['signal']=='insufficient_data'

def test_new_threshold_changes_decision():
    snap={'config':config(),'series':[series()]}
    assert analyze(snap)['research_order']==['uk']
    assert analyze(snap, {'min_growth_pct':100})['research_order']==[]
