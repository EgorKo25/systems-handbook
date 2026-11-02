#!/usr/bin/env python3
"""Fixture transport only: own loopback receiver/curl, no Grafana or real tokens.
getpass is controlled in-process; this tests serialization/validation, not PTY echo
or validity of these fixture tokens for Grafana authentication.
"""
import contextlib,http.server,io,os,runpy,shutil,stat,subprocess,sys,tempfile,threading,unittest
from pathlib import Path
from unittest.mock import patch

HELPER=Path(__file__).resolve().parents[1]/'labs/make_api_client.py'

def invoke(directory,token):
 stdout=io.StringIO();stderr=io.StringIO();creation=[];real_open=os.open
 def traced_open(path,flags,mode=0o777,*args,**kwargs):
  if Path(path).name=='api.curl':creation.append((flags,mode))
  return real_open(path,flags,mode,*args,**kwargs)
 with patch.object(sys,'argv',[str(HELPER),str(directory)]),patch('getpass.getpass',return_value=token) as getter,patch('os.open',side_effect=traced_open),contextlib.redirect_stdout(stdout),contextlib.redirect_stderr(stderr):
  try:runpy.run_path(str(HELPER),run_name='__main__');outcome=0
  except SystemExit as error:outcome=error.code
  except FileExistsError:outcome='FileExistsError'
 return outcome,getter.call_count,stdout.getvalue(),creation

class APIClient(unittest.TestCase):
 def test_valid_config_curl_roundtrip_and_permissions(self):
  if not shutil.which('curl'):self.skipTest('curl unavailable: real transport not tested')
  received=[]
  class Receiver(http.server.BaseHTTPRequestHandler):
   def log_message(self,*args):pass
   def do_GET(self):
    received.append(self.headers.get('Authorization'))
    self.send_response(200);self.end_headers();self.wfile.write(b'own-loopback-fixture-ok')
  server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Receiver)
  thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
  old_umask=os.umask(0)
  try:
   with tempfile.TemporaryDirectory(prefix='grafana-api-client-') as tmp:
    for index,token in enumerate(['fixture-token-01','fixture"quote\\slash']):
     with self.subTest(case=index):
      directory=Path(tmp)/str(index);directory.mkdir(mode=0o700)
      result,calls,stdout,creation=invoke(directory,token);path=directory/'api.curl'
      self.assertEqual(result,0);self.assertEqual(calls,1);self.assertNotIn(token,stdout)
      self.assertEqual(stat.S_IMODE(directory.stat().st_mode),0o700)
      self.assertEqual(stat.S_IMODE(path.stat().st_mode),0o600)
      self.assertEqual(len(creation),1);flags,mode=creation[0]
      self.assertTrue(flags&os.O_EXCL);self.assertTrue(flags&os.O_CREAT);self.assertEqual(mode,0o600)
      before=len(received)
      command=['curl','--config',str(path),'--fail-with-body','--silent','--show-error',f'http://127.0.0.1:{server.server_port}/own-fixture']
      response=subprocess.run(command,capture_output=True,text=True,timeout=10)
      self.assertEqual(response.returncode,0,response.stderr)
      self.assertEqual(response.stdout,'own-loopback-fixture-ok');self.assertEqual(len(received),before+1)
      # HTTP headers.get returns the value, not the name followed by the value.
      self.assertEqual(received[-1],'Bearer '+token)
  finally:
   os.umask(old_umask);server.shutdown();server.server_close();thread.join(timeout=3)

 def test_37_negative_ascii_inputs_and_non_ascii(self):
  ascii_inputs=['',' ','a b','\t\n']+['fixture'+chr(code)+'token' for code in [*range(32),127]]
  self.assertEqual(len(ascii_inputs),37)
  with tempfile.TemporaryDirectory(prefix='grafana-api-client-invalid-') as tmp:
   for index,token in enumerate([*ascii_inputs,'fixture-тест']):
    with self.subTest(case=index):
     directory=Path(tmp)/str(index);directory.mkdir(mode=0o700)
     result,calls,stdout,creation=invoke(directory,token)
     self.assertEqual(result,2);self.assertEqual(calls,1);self.assertEqual(creation,[])
     self.assertEqual(list(directory.iterdir()),[])

 def test_existing_file_exclusive_refusal_preserves_bytes_and_metadata(self):
  with tempfile.TemporaryDirectory(prefix='grafana-api-client-existing-') as tmp:
   directory=Path(tmp)/'private';directory.mkdir(mode=0o700)
   result,_,_,_=invoke(directory,'fixture-original');self.assertEqual(result,0)
   path=directory/'api.curl';before=(path.read_bytes(),path.stat().st_mtime_ns,path.stat().st_mode)
   result,_,_,_=invoke(directory,'fixture-replacement')
   self.assertEqual(result,'FileExistsError')
   self.assertEqual((path.read_bytes(),path.stat().st_mtime_ns,path.stat().st_mode),before)

 def test_open_private_rejected_before_token_read(self):
  with tempfile.TemporaryDirectory(prefix='grafana-api-client-open-') as tmp:
   directory=Path(tmp)/'private';directory.mkdir();directory.chmod(0o770)
   result,calls,_,creation=invoke(directory,'fixture-token')
   self.assertEqual(result,2);self.assertEqual(calls,0);self.assertEqual(creation,[])
   self.assertEqual(list(directory.iterdir()),[])

 def test_missing_private_rejected_before_token_read(self):
  with tempfile.TemporaryDirectory(prefix='grafana-api-client-missing-') as tmp:
   directory=Path(tmp)/'missing'
   result,calls,_,creation=invoke(directory,'fixture-token')
   self.assertEqual(result,2);self.assertEqual(calls,0);self.assertEqual(creation,[])
   self.assertFalse(directory.exists())

if __name__=='__main__':unittest.main()
