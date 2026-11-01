"""Source/trace contract checks for author A only; no common build or writes."""
from html.parser import HTMLParser
import importlib.util
import json
from pathlib import Path
import re
import sys
import unittest

sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
IDS=['os-01-purpose','os-02-kernel-model','os-03-program-process-thread',
     'os-05-syscalls-exceptions','os-06-process-lifecycle','os-07-context-switch',
     'os-08-scheduling','os-09-multiprocessor-scheduling',
     'os-29-boot-services-shutdown','os-30-cpu-observation','os-34-lifecycle-failures']

def load(name):
    spec=importlib.util.spec_from_file_location('source_'+name,ROOT/'sources'/(name+'.py'))
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

class SourceChecks(unittest.TestCase):
    def test_owned_source_headers_and_explicit_unique_anchors(self):
        ids=[]
        for name in IDS:
            s=(ROOT/'sources'/(name+'.html')).read_text()
            self.assertRegex(s,r'^<header><h1>.+?</h1><p>.+?</p></header>')
            self.assertNotRegex(s,r'<article\b|<footer\b|<h2>')
            ids.extend(re.findall(r'\bid="([^"]+)"',s))
        self.assertEqual(len(ids),len(set(ids)))

    def test_diagram_edges_states_fields_and_insertion_markers(self):
        diagrams=load('diagrams_execution').DIAGRAMS
        self.assertEqual(len({d['id'] for d in diagrams}),len(diagrams))
        for d in diagrams:
            self.assertIn(d['chapter'],IDS)
            self.assertEqual((ROOT/'sources'/(d['chapter']+'.html')).read_text().count(d['insert_before']),1)
            nodes={n['id'] for n in d['nodes']};edges={e['id'] for e in d['edges']}
            for edge in d['edges']:
                self.assertIn(edge['from'],nodes);self.assertIn(edge['to'],nodes)
            for step in d['steps']:
                self.assertEqual(set(step['states']),nodes)
                self.assertLessEqual(set(step['focus']),nodes)
                self.assertLessEqual(set(step['active']),edges)
                self.assertTrue(step['fields'])
                for field in step['fields']:
                    self.assertTrue(all(field.get(k) for k in ['name','before','after','why']))

    def test_shared_trace_calculations_and_no_reset_instruction(self):
        trace=json.loads((ROOT/'labs/trace-contract.json').read_text())
        address=int(trace['memory']['user_buffer_va'],16);size=trace['memory']['page_size_bytes']
        self.assertEqual(address//size,int(trace['memory']['vpn'],16))
        self.assertEqual(address%size,int(trace['memory']['offset'],16))
        self.assertEqual(int(trace['memory']['pfn'],16)*size+address%size,int(trace['memory']['user_buffer_pa'],16))
        self.assertEqual(int.from_bytes(bytes.fromhex(trace['file']['before_hex']),'little'),42)
        self.assertEqual(int.from_bytes(bytes.fromhex(trace['file']['after_hex']),'little'),43)
        self.assertEqual(trace['file']['rewrite_offset'],0)
        self.assertNotIn('record.bin',''.join((ROOT/'sources'/(name+'.html')).read_text() for name in IDS))

    def test_reference_does_not_replace_shared_command_names(self):
        ref=load('reference_execution')
        self.assertEqual(ref.COMMANDS,[])
        self.assertTrue(all(isinstance(x,tuple) and len(x)==2 and all(isinstance(v,str) and v for v in x) for x in ref.GLOSSARY))
        keys=[t.casefold() for t,d in ref.GLOSSARY]
        self.assertEqual(len(keys),len(set(keys)))

    def test_balanced_html_and_local_reader_anchors(self):
        void={'link','meta','img','br','hr','input','source','wbr'}
        class Balanced(HTMLParser):
            def __init__(self):super().__init__();self.stack=[]
            def handle_starttag(self,tag,attrs):
                if tag not in void:self.stack.append(tag)
            def handle_endtag(self,tag):
                if not self.stack or self.stack.pop()!=tag:raise AssertionError('Unbalanced closing tag '+tag)
        known={p.stem for p in (ROOT/'sources').glob('*.html')}
        for p in (ROOT/'sources').glob('*.html'):
            known.update(re.findall(r'\bid="([^\"]+)"',p.read_text()))
        for name in IDS:
            source=(ROOT/'sources'/(name+'.html')).read_text();parser=Balanced();parser.feed(source)
            self.assertEqual(parser.stack,[],name)
            for target in re.findall(r'href="#([^\"]+)"',source):self.assertIn(target,known,(name,target))

    def test_local_assets_and_links_to_already_published_books(self):
        for name in IDS:
            s=(ROOT/'sources'/(name+'.html')).read_text()
            for href in re.findall(r'(?:href|src)="([^"]+)"',s):
                if href.startswith('labs/'):
                    self.assertTrue((ROOT/href.split('#')[0]).is_file(),href)
                elif href.startswith('../') and '#' in href:
                    path,anchor=href.split('#',1)
                    page=(ROOT/path).read_text()
                    self.assertIn('id="'+anchor+'"',page,href)

if __name__=='__main__':unittest.main()
