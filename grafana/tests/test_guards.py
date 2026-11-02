#!/usr/bin/env python3
"""Execute literal chapter02 Bash with private command stubs; no download/install/server."""
import html,os,re,subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def literal(name):
 s=(ROOT/'sources/grafana-02-install.html').read_text()
 return html.unescape(re.search(r'<pre id="'+name+r'"><code>(.*?)</code></pre>',s,re.S).group(1))
class Guards(unittest.TestCase):
 def setup_tree(self,tmp,mode):
  root=Path(tmp);stub=root/'stubs';stub.mkdir();events=root/'events'
  def tool(name,text):
   p=stub/name;p.write_text('#!/bin/bash\n'+text);p.chmod(0o755)
  tool('curl','printf "curl\\n" >> "$EVENTS"\n[ "$MODE" != curl-failure ]\n')
  tool('sha256sum','cat >/dev/null\nprintf "hash\\n" >> "$EVENTS"\n[ "$MODE" != hash-failure ]\n')
  tool('tar','printf "tar\\n" >> "$EVENTS"\nmkdir -p "$GRAFANA_HOME/bin"\nprintf \'#!/bin/bash\\nprintf "exec\\\\n" >> "$EVENTS"\\n\' > "$GRAFANA_HOME/bin/grafana"\nchmod +x "$GRAFANA_HOME/bin/grafana"\n')
  env={**os.environ,'HOME':str(root),'PATH':str(stub)+':'+os.environ['PATH'],'EVENTS':str(events),'MODE':mode}
  return root,events,env
 def download(self,mode,existing=False):
  with tempfile.TemporaryDirectory() as tmp:
   root,events,env=self.setup_tree(tmp,mode)
   if existing:(root/'handbook/grafana/releases/grafana-13.3.0').mkdir(parents=True)
   c=subprocess.run(['bash','-c',literal('grafana-download-guard')],env=env,capture_output=True,text=True,timeout=10)
   return c.returncode,events.read_text().splitlines() if events.exists() else []
 def test_curl_failure_no_hash_tar_execution(self):
  code,events=self.download('curl-failure');self.assertNotEqual(code,0);self.assertEqual(events,['curl'])
 def test_hash_failure_no_tar_execution(self):
  code,events=self.download('hash-failure');self.assertNotEqual(code,0);self.assertEqual(events,['curl','hash'])
 def test_existing_release_no_download(self):
  code,events=self.download('ok',True);self.assertNotEqual(code,0);self.assertEqual(events,[])
 def test_stub_success_reaches_version(self):
  code,events=self.download('ok');self.assertEqual(code,0);self.assertEqual(events,['curl','hash','tar','exec'])
 def test_rejected_init_never_starts_old_state(self):
  with tempfile.TemporaryDirectory() as tmp:
   root,events,env=self.setup_tree(tmp,'ok');work=root/'state-root';state=work/'state';state.mkdir(parents=True);sentinel=state/'old-key';sentinel.write_bytes(b'preserve-old-state')
   home=root/'release';(home/'bin').mkdir(parents=True);binary=home/'bin/grafana';binary.write_text('#!/bin/bash\nprintf "exec\\n" >> "$EVENTS"\n');binary.chmod(0o755)
   env.update(GRAFANA_WORK=str(work),GRAFANA_HOME=str(home))
   c=subprocess.run(['bash','-c',literal('grafana-new-state-guard')],cwd=ROOT/'labs',env=env,capture_output=True,text=True,timeout=10)
   self.assertNotEqual(c.returncode,0);self.assertFalse(events.exists());self.assertEqual(sentinel.read_bytes(),b'preserve-old-state');self.assertEqual(list(state.iterdir()),[sentinel])
if __name__=='__main__':unittest.main()
