#!/usr/bin/env python3
"""Bounded OpenRouter tool-use evaluation. No shell execution or embedded credentials."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from data import default_window, write_json

ROOT=Path(__file__).resolve().parents[1]
TOOL_SCHEMAS=[
 {'type':'function','function':{'name':'wiki','description':'Run the bundled wikipedia-opportunity CLI. argv starts with discover, plan, run or reanalyze. Use --out under the supplied evaluation directory.','parameters':{'type':'object','properties':{'argv':{'type':'array','items':{'type':'string'}}},'required':['argv'],'additionalProperties':False}}},
 {'type':'function','function':{'name':'read_file','description':'Read SKILL.md, a reference, or an evaluation output JSON/Markdown.','parameters':{'type':'object','properties':{'path':{'type':'string'}},'required':['path'],'additionalProperties':False}}},
 {'type':'function','function':{'name':'write_json_file','description':'Write a research plan or criteria JSON in the evaluation directory.','parameters':{'type':'object','properties':{'path':{'type':'string'},'data':{'type':'object'}},'required':['path','data'],'additionalProperties':False}}}
]

class Harness:
    def __init__(self,out):
        self.out=out.resolve()
    def safe_path(self,value,write=False):
        p=(ROOT/value).resolve()
        allowed=[self.out] if write else [self.out,ROOT/'references']
        if not any(p==a or a in p.parents for a in allowed) and not (not write and p==ROOT/'SKILL.md'):
            raise ValueError('Path outside evaluation area')
        return p
    def call(self,name,args):
        if name=='read_file':
            p=self.safe_path(args['path'])
            if p.suffix not in ('.json','.md','.csv'): raise ValueError('Read text outputs only')
            return p.read_text()[:24000]
        if name=='write_json_file':
            p=self.safe_path(args['path'],True)
            if p.suffix!='.json' or p.exists(): raise ValueError('Use a new JSON filename')
            write_json(p,args['data']); return {'written':str(p)}
        if name!='wiki': raise ValueError('Unknown tool')
        argv=args['argv']
        if not argv or argv[0] not in ('discover','plan','run','reanalyze'): raise ValueError('Invalid command')
        from wiki_interest import parser
        try:
            parsed=parser().parse_args(argv)
        except SystemExit as e:
            raise ValueError('Invalid CLI arguments') from e
        if Path(parsed.cache).resolve() != (ROOT/'.cache').resolve() or parsed.refresh:
            raise ValueError('Evaluation controls cache; no refresh')
        for name in ('out','config','run','criteria'):
            value=getattr(parsed,name,None)
            if value: self.safe_path(value,write=True)
        proc=subprocess.run([sys.executable,str(ROOT/'scripts/wiki_interest.py'),*argv],cwd=ROOT,capture_output=True,text=True,timeout=600)
        return {'exit_code':proc.returncode,'stdout':proc.stdout[-18000:],'stderr':proc.stderr[-3000:]}

def request(key,model,messages,max_tokens):
    body={'model':model,'messages':messages,'tools':TOOL_SCHEMAS,'tool_choice':'auto','max_tokens':max_tokens,'temperature':0}
    req=Request('https://openrouter.ai/api/v1/chat/completions',data=json.dumps(body).encode(),
                headers={'Authorization':'Bearer '+key,'Content-Type':'application/json','X-Title':'Wikipedia Opportunity Skill Evaluation'})
    for attempt in range(3):
        try:
            with urlopen(req,timeout=120) as r: return json.load(r)
        except HTTPError as e:
            if e.code not in (429,502,503) or attempt==2: raise RuntimeError(f'OpenRouter HTTP {e.code}; check model availability/account limits') from None
            time.sleep(2**attempt)
    raise RuntimeError('Retry limit')

def evaluate_outputs(out, transcript, finals):
    reports=sorted(out.rglob('report.pdf'))
    runs=[]
    for path in out.rglob('analysis.json'):
        folder=path.parent
        if all((folder/name).is_file() for name in ('snapshot.json','provenance.json','report.pdf')):
            runs.append({'folder':folder, 'analysis':json.loads(path.read_text()),
                         'snapshot':json.loads((folder/'snapshot.json').read_text()),
                         'provenance':json.loads((folder/'provenance.json').read_text())})
    pairs=[(first,second) for first in runs for second in runs
           if second['provenance'].get('parent_run')
           and Path(second['provenance']['parent_run']).resolve()==first['folder'].resolve()]
    expected_start,expected_end=default_window()
    def unchanged_except_criteria(first,second):
        before=dict(first['snapshot']); after=dict(second['snapshot'])
        old=dict(before.pop('config',{})); new=dict(after.pop('config',{}))
        old_criteria=dict(old.pop('criteria',{})); new_criteria=dict(new.pop('criteria',{}))
        return before==after and old==new and {k:v for k,v in new_criteria.items() if k!='min_growth_pct'}=={k:v for k,v in old_criteria.items() if k!='min_growth_pct'}
    def successful_reanalysis(entry):
        if entry.get('tool')!='wiki' or entry.get('result',{}).get('exit_code')!=0:
            return False
        try:
            return json.loads(entry['arguments'])['argv'][0]=='reanalyze'
        except (ValueError, KeyError, IndexError, TypeError):
            return False
    from pypdf import PdfReader
    checks={'two_finals':len(finals)==2 and all(isinstance(f,str) and f.strip() for f in finals),
            'two_reports':bool(pairs) and len(reports)>=2,
            'single_page_reports':bool(reports) and all(len(PdfReader(p).pages)==1 for p in reports),
            'exact_period':any(all(run['analysis'].get(k)==v for run in pair for k,v in (('start',expected_start),('end',expected_end))) for pair in pairs),
            'followup_criteria':any(second['analysis'].get('criteria',{}).get('min_growth_pct')==30 for _,second in pairs),
            'followup_same_observations':any(unchanged_except_criteria(first,second) for first,second in pairs),
            'followup_no_network':any(second['provenance'].get('current_run',{}).get('operation')=='reanalyze'
                                      and second['provenance']['current_run'].get('http_requests')==0 for _,second in pairs),
            'coherent_pair':any(first['analysis'].get('start')==second['analysis'].get('start')==expected_start
                                and first['analysis'].get('end')==second['analysis'].get('end')==expected_end
                                and first['analysis'].get('criteria',{}).get('min_growth_pct')==10
                                and second['analysis'].get('criteria',{}).get('min_growth_pct')==30
                                and unchanged_except_criteria(first,second)
                                and first['provenance'].get('source_acquisition')==second['provenance'].get('source_acquisition')
                                and second['provenance'].get('current_run',{}).get('operation')=='reanalyze'
                                and second['provenance'].get('current_run',{}).get('http_requests')==0
                                for first,second in pairs),
            'followup_used_reanalyze':any(successful_reanalysis(x) for x in transcript)}
    return checks

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--model',required=True,help='Explicit authorized OpenRouter model ID supporting tools')
    p.add_argument('--out',required=True,help='Empty folder under work/evaluation/')
    p.add_argument('--max-turns',type=int,default=18)
    args=p.parse_args()
    key=os.environ.get('OPENROUTER_API_KEY')
    if not key: p.error('OPENROUTER_API_KEY is not set. No model call made.')
    out=(ROOT/args.out).resolve(); base=ROOT/'work/evaluation'
    if base not in out.parents: p.error('--out must be under work/evaluation/')
    if out.exists() and any(out.iterdir()): p.error('Use an empty evaluation folder')
    out.mkdir(parents=True,exist_ok=True)
    harness=Harness(out)
    messages=[{'role':'system','content':(ROOT/'SKILL.md').read_text()+'\nYou have wiki/read_file/write_json_file tools. Use them instead of shell. Setup is already complete. All new plans and outputs must be under '+str(out)+'. Do not modify skill code. Finish only after reading generated analysis. Do not claim visual PDF inspection: this harness has no image viewer.'},
              {'role':'user','content':'Ми думаємо додати курс з астрономії. Досліди останні два повні роки в українській Wikipedia, оціни надійність зростання та підготуй PDF. Можна використати загальну статтю як початковий вузький проксі; поясни обмеження.'}]
    transcript=[]; finals=[]; followup=False; started=time.time()
    for turn in range(min(args.max_turns,30)):
        response=request(key,args.model,messages,3000)
        msg=response['choices'][0]['message']
        # Keep only assistant protocol fields; providers may add unrelated fields.
        msg={k:v for k,v in msg.items() if k in ('role','content','tool_calls')}
        messages.append(msg)
        transcript.append({'turn':turn,'model':response.get('model'),'usage':response.get('usage'),'message':msg})
        write_json(out/'transcript.json',transcript)
        calls=msg.get('tool_calls',[])
        if not calls:
            finals.append(msg.get('content'))
            if not followup:
                messages.append({'role':'user','content':'Тепер підвищ мінімальне зростання до 30%. Повтори висновок і PDF на тих самих даних без мережі. Покажи, що змінилося.'})
                followup=True; continue
            break
        for call in calls:
            try: result=harness.call(call['function']['name'],json.loads(call['function']['arguments']))
            except Exception as e: result={'error':str(e)}
            messages.append({'role':'tool','tool_call_id':call['id'],'content':json.dumps(result,ensure_ascii=False)})
            transcript.append({'tool':call['function']['name'],'arguments':call['function']['arguments'],'result':result})
            write_json(out/'transcript.json',transcript)
    checks=evaluate_outputs(out,transcript,finals)
    summary={'requested_model':args.model,'actual_models':sorted({x['model'] for x in transcript if x.get('model')}),
             'elapsed_seconds':round(time.time()-started,2),'checks':checks,'finals':finals,
             'status':'automated_checks_passed_needs_semantic_review' if all(checks.values()) else 'failed',
             'review_required':'Inspect numerical grounding, proxy caveats, recommendations and PDF rendering; tool success alone is insufficient.'}
    write_json(out/'summary.json',summary); print(json.dumps(summary,ensure_ascii=False,indent=2))
    return 0 if all(checks.values()) else 1

if __name__=='__main__': sys.exit(main())
