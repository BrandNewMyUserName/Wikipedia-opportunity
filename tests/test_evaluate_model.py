import copy
import json

from reportlab.pdfgen.canvas import Canvas

from data import write_json
from evaluate_model import evaluate_outputs


def test_evaluation_requires_correct_period_and_unchanged_offline_followup(tmp_path, monkeypatch):
    monkeypatch.setattr('evaluate_model.default_window', lambda: ('2024-09-01', '2026-08-31'))
    first=tmp_path/'first'; second=tmp_path/'second'
    for folder in (first,second):
        folder.mkdir()
        pdf=Canvas(str(folder/'report.pdf')); pdf.drawString(50,700,'Report'); pdf.save()
    snapshot={'schema_version':1, 'source_retrieval_window':['t1','t2'],
              'config':{'start':'2024-09-01','end':'2026-08-31','series':[], 'criteria':{'min_growth_pct':10}},
              'series':[{'daily':{'2026-08-01':42}}]}
    updated=copy.deepcopy(snapshot)
    updated['config']['criteria']={'min_growth_pct':30}
    write_json(first/'snapshot.json',snapshot)
    write_json(second/'snapshot.json',updated)
    write_json(first/'analysis.json',{'start':'2024-09-01','end':'2026-08-31','criteria':{'min_growth_pct':10}})
    write_json(second/'analysis.json',{'start':'2024-09-01','end':'2026-08-31','criteria':{'min_growth_pct':30}})
    write_json(first/'provenance.json',{'source_acquisition':{'cache_hits':0,'http_requests':4},
                                        'current_run':{'operation':'run','http_requests':4}})
    write_json(second/'provenance.json',{'parent_run':str(first.resolve()),
                                          'source_acquisition':{'cache_hits':0,'http_requests':4},
                                          'current_run':{'operation':'reanalyze','http_requests':0}})
    trace=[{'tool':'wiki','arguments':json.dumps({'argv':['reanalyze']}),
            'result':{'exit_code':0}}]
    assert all(evaluate_outputs(tmp_path,trace,['initial','followup']).values())

    wrong=json.loads((first/'analysis.json').read_text())
    wrong['start']='2024-01-01'; wrong['end']='2025-12-31'
    write_json(first/'analysis.json',wrong)
    checks=evaluate_outputs(tmp_path,trace,['initial','followup'])
    assert not checks['exact_period'] and not checks['coherent_pair']

    write_json(first/'analysis.json',{'start':'2024-09-01','end':'2026-08-31','criteria':{'min_growth_pct':10}})
    changed=copy.deepcopy(updated); changed['series'][0]['daily']['2026-08-01']=43
    write_json(second/'snapshot.json',changed)
    checks=evaluate_outputs(tmp_path,trace,['initial','followup'])
    assert not checks['followup_same_observations'] and not checks['coherent_pair']
