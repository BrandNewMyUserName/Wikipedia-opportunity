from pathlib import Path
import re
import yaml

def test_skill_spec_and_relative_references():
    root=Path(__file__).resolve().parents[1]
    text=(root/'SKILL.md').read_text()
    meta=yaml.safe_load(text.split('---',2)[1])
    assert meta['name']==root.name and re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*',meta['name'])
    assert 1<=len(meta['name'])<=64 and 1<=len(meta['description'])<=1024
    for link in re.findall(r'\]\(([^)]+)\)',text):
        if not link.startswith('http'): assert (root/link).is_file()
    assert len(text.splitlines())<500
