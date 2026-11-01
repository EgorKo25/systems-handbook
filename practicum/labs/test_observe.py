import importlib.util
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import socketserver
import threading
import time
import unittest

spec=importlib.util.spec_from_file_location('study_observe',Path(__file__).with_name('observe.py'))
probe=importlib.util.module_from_spec(spec);spec.loader.exec_module(probe)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path=='/redirect':
            self.send_response(302);self.send_header('Location','/healthz');self.send_header('Content-Length','0');self.end_headers();return
        code=200 if self.path in ('/healthz','/delayed200') else 503
        body=b'{"status":"ok"}'
        self.send_response(code);self.send_header('Content-Length',str(len(body)));self.end_headers()
        if self.path.startswith('/delayed'):
            self.wfile.flush()
            time.sleep(.12)
            self.server.body_write_started[self.path]=time.perf_counter()
        try:
            self.wfile.write(body)
        except OSError:
            pass
        finally:
            if self.path.startswith('/delayed'):
                self.server.body_events[self.path].set()
    def log_message(self,*args):pass


class BrokenResponse(socketserver.BaseRequestHandler):
    def handle(self):
        self.request.settimeout(2)
        request=self.request.recv(4096)
        if b'/bad-status' in request:
            response=b'not an HTTP status line\r\n\r\n'
        elif b'/short-length' in request:
            response=b'HTTP/1.1 200 OK\r\nContent-Length: 10\r\nConnection: close\r\n\r\nabc'
        else:
            response=b'HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\nConnection: close\r\n\r\n3\r\nab'
        self.request.sendall(response)


class ProbeChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        cls.server.body_write_started={}
        cls.server.body_events={path:threading.Event() for path in ('/delayed200','/delayed503')}
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
        cls.base='http://127.0.0.1:'+str(cls.server.server_address[1])
        cls.broken=socketserver.ThreadingTCPServer(('127.0.0.1',0),BrokenResponse)
        cls.broken.daemon_threads=True
        cls.broken_thread=threading.Thread(target=cls.broken.serve_forever,daemon=True);cls.broken_thread.start()
        cls.broken_base='http://127.0.0.1:'+str(cls.broken.server_address[1])
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join()
        cls.broken.shutdown();cls.broken.server_close();cls.broken_thread.join()
    def test_known_percentiles_and_empty_successes(self):
        self.assertEqual(probe.percentile([5,1,3,2,4],50),3)
        self.assertEqual(probe.percentile([5,1,3,2,4],99),5)
        self.assertIsNone(probe.percentile([],99))
    def test_real_http_success_count_and_throughput(self):
        result=probe.observe(self.base+'/healthz',count=7,concurrency=2)
        self.assertEqual(result['requests'],7);self.assertEqual(result['errors'],0)
        self.assertEqual(result['statuses'],{'200':7})
        self.assertGreater(result['successful_per_second'],0)
        self.assertLessEqual(result['success_latency_ms']['50'],result['success_latency_ms']['99'])
    def test_http_error_is_not_fast_success(self):
        result=probe.observe(self.base+'/failure',count=3,concurrency=1)
        self.assertEqual(result['errors'],3);self.assertEqual(result['statuses'],{'503':3})
        self.assertEqual(result['successful_per_second'],0)
        self.assertIsNone(result['success_latency_ms']['99'])
    def test_explicit_expected_http_failure_code(self):
        result=probe.observe(self.base+'/failure',count=2,expected=503)
        self.assertEqual(result['errors'],0)
    def test_redirect_does_not_silently_become_health_success(self):
        result=probe.observe(self.base+'/redirect',count=2)
        self.assertEqual(result['errors'],2);self.assertEqual(result['statuses'],{'302':2})
    def test_expected_200_and_503_both_wait_for_the_delayed_body(self):
        for path,expected in (('/delayed200',200),('/delayed503',503)):
            with self.subTest(status=expected):
                row=probe.request(self.base+path,timeout=3,expected=expected)
                finished=time.perf_counter()
                self.assertTrue(self.server.body_events[path].wait(3))
                self.assertTrue(row['ok'])
                self.assertEqual(row['body_bytes_read'],len(b'{"status":"ok"}'))
                # Assert causal order, not a fragile fixed millisecond threshold.
                self.assertGreaterEqual(finished,self.server.body_write_started[path])
    def test_broken_chunked_200_is_error_and_full_series_survives(self):
        result=probe.observe(self.broken_base+'/bad-chunk',count=4,concurrency=2)
        self.assertEqual(result['requests'],4)
        self.assertEqual(result['errors'],4)
        self.assertEqual(result['statuses'],{'200':4})
        self.assertEqual(result['failure_kinds'],{'protocol-error':4})
        self.assertEqual(result['successful_per_second'],0)
        self.assertIsNone(result['success_latency_ms']['99'])
    def test_short_content_length_200_is_not_success(self):
        result=probe.observe(self.broken_base+'/short-length',count=2)
        self.assertEqual(result['requests'],2)
        self.assertEqual(result['errors'],2)
        self.assertEqual(result['statuses'],{'200':2})
        self.assertEqual(result['failure_kinds'],{'protocol-error':2})
    def test_bad_status_line_also_returns_a_counted_protocol_failure(self):
        result=probe.observe(self.broken_base+'/bad-status',count=3)
        self.assertEqual(result['requests'],3)
        self.assertEqual(result['errors'],3)
        self.assertEqual(result['statuses'],{'protocol-error':3})
        self.assertEqual(result['failure_kinds'],{'protocol-error':3})
    def test_invalid_input_never_becomes_a_request(self):
        for value in ('file:///etc/passwd','http://user:password@127.0.0.1/'):
            with self.assertRaises(ValueError):probe.observe(value)
        for kwargs in ({'count':0},{'concurrency':33},{'timeout':0},{'expected':0}):
            with self.assertRaises(ValueError):probe.observe(self.base,**kwargs)


if __name__=='__main__':unittest.main()
