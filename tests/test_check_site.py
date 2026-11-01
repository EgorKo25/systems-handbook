"""Regression fixtures for failures invisible in a root-only link smoke test."""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_site.py"
spec = importlib.util.spec_from_file_location("check_site", SCRIPT)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class CheckSiteTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)

    def tearDown(self):
        self.directory.cleanup()

    def put(self, name, source):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")

    def errors(self):
        checker = module.SiteChecker(self.root)
        checker.check()
        return "\n".join(checker.errors)

    def test_query_encoded_fragment_and_directory_index(self):
        self.put("index.html", '<a href="chapter/?mode=read#%D1%81%D0%B5%D1%82%D1%8C">Read</a>')
        self.put("chapter/index.html", '<h1 id="сеть">Сеть</h1><a href="../index.html">Back</a><pre>/home/alice/data and http://localhost are examples</pre>')
        self.assertEqual(self.errors(), "")
        self.put("chapter/index.html", '<h1 id="other">Wrong chapter</h1>')
        self.assertIn("missing anchor 'сеть'", self.errors())

    def test_project_absolute_and_machine_urls_fail_but_source_link_is_ok(self):
        self.put("index.html", '<a href="/linux/index.html">Broken under project base</a><a href="file:///home/alice/book.html">Private</a><a href="http://localhost:8766/">Dev server</a><a href="https://www.postgresql.org/docs/">Source</a>')
        errors = self.errors()
        self.assertIn("absolute path", errors)
        self.assertEqual(errors.count("machine-specific URL"), 2)
        self.assertNotIn("postgresql.org", errors)

    def test_dynamic_command_glossary_and_search_targets(self):
        commands = [{"name": "ip", "purpose": "Explain", "syntax": "ip", "volume": "missing", "chapter": "network", "flags": []}, {"name": "ps", "purpose": "Processes", "syntax": "ps", "volume": "linux", "chapter": "removed-chapter", "flags": []}]
        terms = [{"term": "Socket", "definition": "Endpoint", "volume": "linux", "anchor": "gone"}]
        self.put("linux/index.html", '<h1 id="chapter">Linux</h1>' + ''.join('<script type="application/json" id="'+key+'">'+json.dumps(value)+'</script>' for key, value in {"book-data": [{"id": "chapter"}], "glossary-data": [], "command-reference-data": [], "library-glossary-data": [], "flag-comparison-data": []}.items()))
        self.put("index.html", '<script type="application/json" id="command-reference-data">'+json.dumps(commands)+'</script><script type="application/json" id="library-glossary-data">'+json.dumps(terms)+'</script><script>window.BOOK_SEARCH=[{"url":"index.html#missing"}];</script>')
        errors = self.errors()
        self.assertIn("unknown volume 'missing'", errors)
        self.assertIn("missing target linux/index.html#removed-chapter", errors)
        self.assertIn("missing target linux/index.html#gone", errors)
        self.assertIn("BOOK_SEARCH: missing anchor 'missing'", errors)

    def test_duplicate_ids_bad_json_external_css_and_runtime_network(self):
        self.put("index.html", '<h1 id="same">A</h1><h2 id="same">B</h2><script type="application/json">{broken}</script><link rel="stylesheet" href="style.css"><script>fetch("data.json")</script>')
        self.put("style.css", '@import "https://example.net/font.css"; body{background:url(missing.png)}')
        errors = self.errors()
        for expected in ("duplicate HTML ID", "invalid embedded JSON", "external active resource", "missing local file", "runtime network API"):
            self.assertIn(expected, errors)

    def test_fragment_sources_and_nested_export_do_not_mask_a_broken_reading_page(self):
        self.put('index.html', '<h1>Library</h1>')
        self.put('newbook/sources/01.html', '<a href="../linux/index.html#later">fragment</a>')
        self.put('_site/index.html', '<a href="old-missing.html">previous artifact</a>')
        self.assertEqual(self.errors(), '')
        self.put('newbook/index.html', '<a href="missing.html">broken real page</a>')
        self.assertIn('missing.html', self.errors())
        # A self-contained exported directory still validates its own contents.
        checker = module.SiteChecker(self.root/'_site')
        checker.check()
        self.assertTrue(any('old-missing.html' in error for error in checker.errors))

    def test_explicit_fragment_routes_are_separate_from_dom_anchors(self):
        self.put('index.html', '<a href="lab/?mode=read#race">Race</a><a href="lab/#scenario">Selector</a><a href="lab/#heading">Heading</a>')
        self.put('lab/index.html', '<h1 id="heading">Lab</h1><select id="scenario" data-fragment-routes="option-values"><optgroup label="Models"><option value="race">Race</option><option value="cas">CAS</option></optgroup></select>')
        checker = module.SiteChecker(self.root)
        self.assertTrue(checker.check(), checker.errors)
        page = checker.pages[self.root/'lab/index.html']
        self.assertEqual(page.fragment_routes, ['race', 'cas'])
        self.assertNotIn('race', page.ids)
        self.assertIn('scenario', page.ids)

    def test_normal_select_does_not_implicitly_allow_fragments(self):
        self.put('index.html', '<select id="scenario"><option value="race">Race</option></select><a href="#race">Wrong</a>')
        self.assertIn("missing anchor 'race'", self.errors())

    def test_declared_routes_do_not_allow_typo_case_path_or_encoded_state(self):
        self.put('index.html', '<select id="scenario" data-fragment-routes="option-values"><option value="race">Race</option></select>' + ''.join('<a href="#'+s+'">Wrong</a>' for s in ['rcae', 'Race', 'race/next', 'race?step=1', '%72ace', 'race:~:text=state']))
        errors = self.errors()
        self.assertEqual(errors.count('missing anchor'), 6, errors)
        # A real ID still has normal decoded-anchor/text-fragment semantics.
        self.put('index.html', '<h1 id="сеть">Network</h1><a href="#%D1%81%D0%B5%D1%82%D1%8C:~:text=Network">Heading</a>')
        self.assertEqual(self.errors(), '')

    def test_fragment_route_duplicates_across_options_and_selectors_fail(self):
        for selects in [
            '<select id="s" data-fragment-routes="option-values"><option value="race">One</option><option value="race">Two</option></select>',
            '<select id="a" data-fragment-routes="option-values"><option value="race">One</option></select><select id="b" data-fragment-routes="option-values"><option value="race">Two</option></select>',
        ]:
            with self.subTest(selects=selects):
                self.put('index.html', selects)
                self.assertIn("duplicate declared fragment route 'race'", self.errors())

    def test_fragment_routes_must_not_collide_with_ids_or_named_anchors(self):
        for anchor in ['<h1 id="race">Title</h1>', '<a name="race">Legacy</a>']:
            with self.subTest(anchor=anchor):
                self.put('index.html', anchor + '<select id="scenario" data-fragment-routes="option-values"><option value="race">Race</option></select>')
                self.assertIn("declared fragment route 'race' collides", self.errors())

    def test_fragment_route_marker_has_a_narrow_validated_contract(self):
        cases = [
            ('<div data-fragment-routes="option-values"><option value="race">Wrong</option></div>', 'requires a select'),
            ('<select id="s" data-fragment-routes="anything"><option value="race">Wrong</option></select>', 'invalid fragment route selector'),
            ('<select data-fragment-routes="option-values"><option value="race">Wrong</option></select>', 'invalid fragment route selector'),
            ('<select id="s" multiple data-fragment-routes="option-values"><option value="race">Wrong</option></select>', 'invalid fragment route selector'),
            ('<select id="s" data-fragment-routes="option-values" data-fragment-routes="option-values"><option value="race">Wrong</option></select>', 'invalid fragment route selector'),
            ('<select id="s" data-fragment-routes="option-values"></select>', 'has no options'),
            ('<select id="s" data-fragment-routes="option-values"><option value="race">Unclosed', 'unclosed fragment route selector'),
            ('<select id="s" data-fragment-routes="option-values"><select id="nested"><option value="race">Wrong</option></select></select>', 'nested select'),
            ('<select><select id="s" data-fragment-routes="option-values"><option value="race">Wrong</option></select></select>', 'invalid fragment route selector'),
        ]
        for html, expected in cases:
            with self.subTest(html=html):
                self.put('index.html', html)
                self.assertIn(expected, self.errors())

    def test_fragment_route_options_require_one_literal_unreserved_value(self):
        for option in ['<option>race</option>', '<option value="">Empty</option>', '<option value=" race">Space</option>', '<option value="race/next">Path</option>', '<option value="%72ace">Encoded</option>', '<option value="race#next">Hash</option>', '<option value="race" value="cas">Duplicate</option>']:
            with self.subTest(option=option):
                self.put('index.html', '<select id="s" data-fragment-routes="option-values">'+option+'</select>')
                self.assertIn('option requires one explicit nonempty unreserved value', self.errors())

    def test_fragment_routes_are_page_local_and_bad_files_still_fail(self):
        self.put('index.html', '<a href="lab/index.html#race">Good</a><a href="#race">Wrong page</a><a href="missing.html#race">Missing</a>')
        self.put('lab/index.html', '<select id="s" data-fragment-routes="option-values"><option value="race">Race</option></select>')
        errors = self.errors()
        self.assertEqual(errors.count('missing anchor'), 1, errors)
        self.assertEqual(errors.count('missing local file'), 1, errors)

    def test_escaped_option_attribute_and_implicit_option_end_are_parsed(self):
        self.put('index.html', '<select id="s" data-fragment-routes="option-values"><option value="r&#97;ce">Race<option value="cas">CAS</select><a href="#race">Race</a><a href="#cas">CAS</a>')
        self.assertEqual(self.errors(), '')

    def test_real_coordination_routes_validate_without_hidden_anchor_elements(self):
        lab = Path(__file__).resolve().parents[1]/'operating-systems/labs/coordination'
        for filename in ['index.html', 'lab.css', 'lab.js', 'models.js']:
            self.put('operating-systems/labs/coordination/'+filename, (lab/filename).read_text(encoding='utf-8'))
        page = module.Page(lab/'index.html')
        page.feed((lab/'index.html').read_text(encoding='utf-8'))
        page.close()
        self.put('index.html', ''.join('<a href="operating-systems/labs/coordination/?mode=read#'+route+'">'+route+'</a>' for route in page.fragment_routes))
        # Only the declared lab's existing return link needs this reader stub.
        data = {'book-data': [{'id': 'os-14-interleavings'}], 'glossary-data': [], 'command-reference-data': [], 'library-glossary-data': [], 'flag-comparison-data': []}
        self.put('operating-systems/index.html', '<h1 id="os-14-interleavings">Reader dependency</h1>' + ''.join('<script type="application/json" id="'+key+'">'+json.dumps(value)+'</script>' for key, value in data.items()))
        checker = module.SiteChecker(self.root, node_check=bool(shutil.which('node')))
        self.assertTrue(checker.check(), checker.errors)
        checked_lab = checker.pages[self.root/'operating-systems/labs/coordination/index.html']
        self.assertEqual(len(checked_lab.fragment_routes), 13)
        self.assertFalse(set(checked_lab.fragment_routes) & set(checked_lab.ids))
        if shutil.which('node'):
            self.assertEqual(checker.checked_js, 2)


COORDINATION_ROUTES_ADAPTER = r'''
'use strict';
// Execute the real lab with synthetic DOM/storage; no browser, kernel or network.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const root=process.argv[2],declared=JSON.parse(process.argv[3]);
const html=fs.readFileSync(path.join(root,'index.html'),'utf8');
const block=html.match(/<select\b(?=[^>]*\bid="scenario")[^>]*>([\s\S]*?)<\/select>/);
assert.ok(block,'actual scenario selector exists');
assert.match(block[0],/\bdata-fragment-routes="option-values"/);
assert.equal((html.match(/\bdata-fragment-routes=/g)||[]).length,1);
const options=[...block[1].matchAll(/<option\b[^>]*\bvalue="([^"]+)"/g)].map(x=>x[1]);
const expected=['race','inheritance','cas','aba','publication','wakeup','deadlock','backpressure','signals','readiness','access','budget','bytes'];
assert.deepEqual(options,expected);assert.equal(new Set(options).size,13);assert.deepEqual(declared,options);
const KEY='systems-handbook.os.coordination.v1';
const original=fs.readFileSync(path.join(root,'lab.js'),'utf8');
const probe='let state={version:1';assert.equal(original.split(probe).length,2);
// Read only the real closure's supported-key list; all routing/rendering is unchanged.
const source=original.replace(probe,'window.__supportedRoutes=Object.keys(scenarios);'+probe);
function make(hash='',seed=null){
 const ids=[...html.matchAll(/\bid="([^"]+)"/g)].map(x=>x[1]),nodes=new Map(),events={};
 function element(){return {value:'',textContent:'',disabled:false,hidden:false,children:[],events:{},replaceChildren(...c){this.children=c;},append(...c){this.children.push(...c);},addEventListener(n,fn){this.events[n]=fn;}};}
 for(const id of ids)nodes.set(id,element());
 const writes=new Map([['foreign.notes','leave alone']]);if(seed!==null)writes.set(KEY,seed);
 const url=new URL('https://example.invalid/lab/index.html');url.hash=hash;
 const ctx={document:{getElementById(id){assert.ok(nodes.has(id),'missing actual HTML ID '+id);return nodes.get(id);},createElement:element,documentElement:{style:{setProperty(){}}}},location:url,localStorage:{getItem(k){assert.equal(k,KEY);return writes.has(k)?writes.get(k):null;},setItem(k,v){assert.equal(k,KEY);writes.set(k,v);}},confirm:()=>false,addEventListener(name,fn){(events[name]??=[]).push(fn);}};
 ctx.window=ctx;vm.createContext(ctx);vm.runInContext(fs.readFileSync(path.join(root,'models.js'),'utf8'),ctx);vm.runInContext(source,ctx);
 assert.deepEqual(Array.from(ctx.__supportedRoutes),options);
 return {ctx,nodes,writes,fire(id,event='change',value){if(value!==undefined)nodes.get(id).value=value;assert.equal(typeof nodes.get(id).events[event],'function',id+':'+event);nodes.get(id).events[event]();},hash(value){ctx.location.hash=value;assert.equal(events.hashchange.length,1);events.hashchange[0]();},snapshot(){return JSON.stringify([nodes.get('scenario').value,nodes.get('assumptions').textContent,nodes.get('step-title').textContent,nodes.get('explanation').textContent,nodes.get('position').textContent,nodes.get('state').children.map(x=>x.textContent)]);}};
}
let boot=0,changes=0,dropdown=0,rejected=0;
for(const route of options){
 const seed=JSON.stringify({version:1,scenario:route==='race'?'bytes':'race',history:['retained'],positions:{},variants:{}});
 const t=make('#'+route,seed);assert.equal(t.nodes.get('scenario').value,route);assert.ok(t.nodes.get('assumptions').textContent);assert.ok(t.nodes.get('step-title').textContent);assert.equal(t.nodes.get('history').children.length,1);assert.equal(JSON.parse(t.writes.get(KEY)).scenario,route);boot++;
 const bySelect=make();bySelect.fire('scenario','change',route);assert.equal(bySelect.ctx.location.hash,'#'+route);bySelect.hash(bySelect.ctx.location.hash);assert.equal(bySelect.snapshot(),make('#'+route).snapshot());dropdown++;
 const live=make('#bytes');live.hash('#'+route);assert.equal(live.nodes.get('scenario').value,route);assert.equal(live.snapshot(),make('#'+route).snapshot());changes++;
 // Real navigation advances the chosen model, retains its position, and returns.
 live.fire('next','click');const next=live.snapshot();live.hash(route==='bytes'?'#race':'#bytes');live.hash('#'+route);assert.equal(live.snapshot(),next);assert.equal(live.writes.get('foreign.notes'),'leave alone');
}
for(const hash of ['#missing','#Race','#race/next','#race?step=1','#%72ace','#race:~:text=state','#constructor','#__proto__']){
 const booted=make(hash);assert.equal(booted.nodes.get('scenario').value,'race');
 const t=make('#bytes'),before=t.snapshot(),saved=t.writes.get(KEY);t.hash(hash);assert.equal(t.snapshot(),before);assert.equal(t.writes.get(KEY),saved);rejected++;
}
console.log(JSON.stringify({status:'PASS',declared:options.length,bootstrap:boot,hashchange:changes,selector:dropdown,rejected,scope:'actual models/lab adapter with read-only key-list probe in minimal DOM; not a real browser'}));
'''


class CoordinationFragmentRoutesTests(unittest.TestCase):
    def run_adapter(self, lab):
        page = module.Page(lab/'index.html')
        page.feed((lab/'index.html').read_text(encoding='utf-8'))
        page.close()
        result = subprocess.run([shutil.which('node'), '-', str(lab), json.dumps(page.fragment_routes)], input=COORDINATION_ROUTES_ADAPTER, text=True, capture_output=True)
        return page, result

    @unittest.skipUnless(shutil.which('node'), 'Node.js is required for the real lab adapter regression')
    def test_actual_declared_lab_routes_match_bootstrap_hashchange_and_selector(self):
        lab = Path(__file__).resolve().parents[1]/'operating-systems/labs/coordination'
        page, result = self.run_adapter(lab)
        self.assertEqual(page.parse_errors, [])
        self.assertEqual(len(page.fragment_routes), 13)
        self.assertFalse(set(page.fragment_routes) & set(page.ids))
        self.assertEqual(result.returncode, 0, result.stdout+'\n'+result.stderr)
        proof = json.loads(result.stdout)
        self.assertEqual(proof['status'], 'PASS')
        self.assertEqual((proof['bootstrap'], proof['hashchange'], proof['selector']), (13, 13, 13))
        self.assertEqual(proof['rejected'], 8)

    @unittest.skipUnless(shutil.which('node'), 'Node.js is required for the real lab adapter regression')
    def test_adapter_regression_rejects_stale_extra_duplicate_and_missing_routes(self):
        original = Path(__file__).resolve().parents[1]/'operating-systems/labs/coordination'
        html = (original/'index.html').read_text(encoding='utf-8')
        js = (original/'lab.js').read_text(encoding='utf-8')
        changes = [
            ('stale option', html.replace('value="cas"', 'value="phantom"'), js),
            ('extra option', html.replace('<option value="cas">', '<option value="phantom">Phantom</option><option value="cas">'), js),
            ('duplicate option', html.replace('value="cas"', 'value="race"'), js),
            ('missing option', html.replace('<option value="cas">CAS и повтор</option>', ''), js),
            ('handler key drift', html, js.replace('\ncas:{name:', '\ncasRemoved:{name:')),
        ]
        for name, changed_html, changed_js in changes:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                lab = Path(directory)
                for filename in ['models.js']:
                    shutil.copyfile(original/filename, lab/filename)
                (lab/'index.html').write_text(changed_html, encoding='utf-8')
                (lab/'lab.js').write_text(changed_js, encoding='utf-8')
                _, result = self.run_adapter(lab)
                self.assertNotEqual(result.returncode, 0, name+' escaped the actual-adapter contract')
                self.assertIn('AssertionError', result.stderr)


if __name__ == "__main__":
    unittest.main()
