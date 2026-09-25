import copy
from pypdf import PdfReader
from analysis import analyze
from report import render
from test_analysis import series, config

def test_one_page_unicode_report(tmp_path):
    a=analyze({'config':config(),'series':[series()]}); render(a,tmp_path)
    doc=PdfReader(tmp_path/'report.pdf')
    assert len(doc.pages)==1
    text=doc.pages[0].extract_text()
    assert 'Астрономія' in text and '54,900' in text and '+50.4%' in text
    assert (tmp_path/'trend.png').stat().st_size>10000
    assert len((tmp_path/'monthly.csv').read_text().splitlines())==25

def test_six_series_one_page(tmp_path):
    ss=[]
    for i in range(6):
        s=series(); s['id']=f'audience-{i}'; ss.append(s)
    a=analyze({'config':config(),'series':ss}); render(a,tmp_path)
    assert len(PdfReader(tmp_path/'report.pdf').pages)==1

def test_revised_growth_criterion_appears_in_both_reports(tmp_path):
    snapshot={'config':config(),'series':[series()]}
    first=tmp_path/'first'; second=tmp_path/'second'
    first.mkdir(); second.mkdir()
    render(analyze(snapshot),first)
    render(analyze(snapshot,{'min_growth_pct':30}),second)
    assert 'Minimum raw growth criterion: 10%.' in (first/'report.md').read_text()
    assert 'Minimum raw growth criterion: 30%.' in (second/'report.md').read_text()
    assert 'Applied minimum raw growth criterion: 10%.' in PdfReader(first/'report.pdf').pages[0].extract_text()
    assert 'Applied minimum raw growth criterion: 30%.' in PdfReader(second/'report.pdf').pages[0].extract_text()
