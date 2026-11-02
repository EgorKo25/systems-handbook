"""Subprocess-mock boundaries only: no credentials, network, gh executable or VM."""
import contextlib,io,json,subprocess,sys,unittest
from pathlib import Path
from unittest.mock import call,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'vm'))
import lab as L

def response(code=200,body=b'{"ok":true}',rc=0):
 return subprocess.CompletedProcess([],rc,b'HTTP/2.0 '+str(code).encode()+b' status\r\nX-Own: fixture\r\n\r\n'+body)
def empty(rc=1):return subprocess.CompletedProcess([],rc,b'')

class ApiRetryTests(unittest.TestCase):
 def setUp(self):
  self.api=object.__new__(L.GitHub);self.api.repo='own/private-fixture';self.api.branch='main';self.api.prefix='repos/'+self.api.repo;self.api.gh='own-fake-gh-never-execute';self.path=self.api.prefix+'/releases/17/assets?per_page=100&page=1'
 def execute(self,answers,method='GET',data=None,missing=False):
  stack=contextlib.ExitStack();self.addCleanup(stack.close)
  self.run=stack.enter_context(patch.object(L.subprocess,'run',side_effect=answers));self.sleep=stack.enter_context(patch.object(L.time,'sleep'))
  self.out=stack.enter_context(contextlib.redirect_stdout(io.StringIO()));self.err=stack.enter_context(contextlib.redirect_stderr(io.StringIO()))
  return self.api.api(method,self.path,data=data,missing=missing)
 def attempts(self,count,delays):
  self.assertEqual(self.run.call_count,count);self.assertEqual(self.sleep.call_args_list,[call(d)for d in delays])
  for c in self.run.call_args_list:
   args,=c.args;self.assertEqual(args[:4],[self.api.gh,'api','--hostname','github.com']);self.assertEqual(c.kwargs['stdout'],subprocess.PIPE);self.assertEqual(c.kwargs['stderr'],subprocess.DEVNULL)
  self.assertEqual(self.out.getvalue(),'');self.assertEqual(self.err.getvalue(),'')
 def test_immediate_success_no_delay(self):
  self.assertEqual(self.execute([response()]),{'ok':True});self.attempts(1,[])
 def test_success_after_empty_transport_failure(self):
  self.assertEqual(self.execute([empty(),response()]),{'ok':True});self.attempts(2,[1]);self.assertEqual(self.run.call_args_list[0],self.run.call_args_list[1])
 def test_success_on_third_with_exact_delays(self):
  self.assertEqual(self.execute([empty(2),empty(-15),response(body=b'[]')]),[]);self.attempts(3,[1,2]);self.assertTrue(all(c==self.run.call_args_list[0]for c in self.run.call_args_list))
 def test_exhaustion_exactly_three_no_last_sleep(self):
  with self.assertRaisesRegex(L.Error,'did not return an HTTP status'):self.execute([empty(),empty(),empty(),response()])
  self.attempts(3,[1,2])
 def test_mutations_one_attempt_even_with_no_response(self):
  for method in ['POST','PUT','PATCH','DELETE']:
   with self.subTest(method=method):
    with self.assertRaisesRegex(L.Error,'did not return an HTTP status'):self.execute([empty(),response()],method,{'own':'body'})
    self.attempts(1,[]);self.assertEqual(self.run.call_args.kwargs['input'],L.dump({'own':'body'}))
 def test_other_methods_not_normalized_into_retry(self):
  for method in ['HEAD','OPTIONS','get']:
   with self.subTest(method=method):
    with self.assertRaises(L.Error):self.execute([empty(),response()],method)
    self.attempts(1,[])
 def test_any_HTTP_status_prevents_retry_on_nonzero_exit(self):
  for code in [200,301,401,403,404,409,429,500,502,503]:
   with self.subTest(code=code):
    with self.assertRaises(L.HTTP)as caught:self.execute([response(code=code,rc=1),response()])
    self.assertEqual(caught.exception.status,code);self.attempts(1,[])
 def test_HTTP_error_zero_exit_not_retried(self):
  for code in [302,404,429,500]:
   with self.subTest(code=code):
    with self.assertRaises(L.HTTP):self.execute([response(code=code),response()])
    self.attempts(1,[])
 def test_missing_404_behavior_preserved(self):
  self.assertIsNone(self.execute([response(code=404,rc=1)],missing=True));self.attempts(1,[])
 def test_zero_exit_empty_or_malformed_stdout_not_retried(self):
  for raw in [b'',b'not HTTP',b'HTTP/2.0 nope\n\n{}',b'prefix\nHTTP/2.0 200\n\n{}']:
   with self.subTest(raw=raw):
    with self.assertRaisesRegex(L.Error,'did not return an HTTP status'):self.execute([subprocess.CompletedProcess([],0,raw),response()])
    self.attempts(1,[])
 def test_nonempty_failed_protocol_output_not_retried(self):
  for raw in [b' ',b'not HTTP',b'HTTP/2.0 nope\n\n{}',b'prefix\nHTTP/2.0 503\n\n{}']:
   with self.subTest(raw=raw):
    with self.assertRaisesRegex(L.Error,'did not return an HTTP status'):self.execute([subprocess.CompletedProcess([],1,raw),response()])
    self.attempts(1,[])
 def test_invalid_JSON_no_retry(self):
  with self.assertRaises(json.JSONDecodeError):self.execute([response(body=b'{broken'),response()])
  self.attempts(1,[])
 def test_oversize_body_no_retry(self):
  with self.assertRaisesRegex(L.Error,'Oversize API response'):self.execute([response(body=b'x'*(4*1024**2)),response()])
  self.attempts(1,[])
 def test_transport_then_HTTP_error_does_not_consume_third(self):
  with self.assertRaises(L.HTTP):self.execute([empty(),response(code=503,rc=1),response()])
  self.attempts(2,[1])
 def test_transport_then_invalid_JSON_stops(self):
  with self.assertRaises(json.JSONDecodeError):self.execute([empty(),response(body=b'bad'),response()])
  self.attempts(2,[1])
 def test_zero_exit_without_status_stops_after_prior_failure(self):
  with self.assertRaises(L.Error):self.execute([empty(),empty(0),response()])
  self.attempts(2,[1])
 def test_spawn_exception_previous_behavior_preserved(self):
  with self.assertRaises(OSError):self.execute([OSError('own injected spawn failure')])
  self.attempts(1,[])
 def test_existing_success_body_semantics_preserved(self):
  for body,expected in [(b'',None),(b' \n',None),(b'null',None),(b'[]',[]),(b'42',42)]:
   with self.subTest(body=body):self.assertEqual(self.execute([response(body=body)]),expected);self.attempts(1,[])

if __name__=='__main__':unittest.main(verbosity=2)
