#!/usr/bin/env python3
"""Real Go/JFrog CLI + own loopback protocol fixture + SQLite MODEL.

Never starts Artifactory. No server/edition/DB/permission/restore acceptance.
Requires prepared Go>=1.26, JFrog CLI2.129.0, OpenSSL; Python standard library.
All experiment writes go to a new TemporaryDirectory. Reports omit credentials,
absolute runtime paths, temporary keys and the user's account name.
"""
from pathlib import Path
import argparse, base64, contextlib, hashlib, http.server, json, os, shutil
import ssl, subprocess, sys, tempfile, threading, time, statistics
from urllib.parse import unquote

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from go_fixture import MODULE, VERSION, create, escape
from store_model import Store
from release_manifest import describe, verify

@contextlib.contextmanager
def endpoint(files, cert=None, key=None, auth=False):
    calls = []
    expected = 'Basic ' + base64.b64encode(b'fixture:dummy-not-a-secret').decode()
    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def do_GET(self):
            calls.append({'method':'GET', 'path':self.path, 'authorized':self.headers.get('Authorization') == expected})
            if self.path == '/artifactory/api/system/ping':
                self.send_response(200); self.end_headers(); self.wfile.write(b'OK'); return
            if self.path == '/artifactory/api/system/version':
                b = b'{"version":"7.161.20","revision":"fixture-only"}'
                self.send_response(200); self.send_header('Content-Type','application/json'); self.end_headers(); self.wfile.write(b); return
            prefix = '/artifactory/api/go/go-virtual/'
            if not self.path.startswith(prefix):
                self.send_error(404); return
            if auth and self.headers.get('Authorization') != expected:
                self.send_response(401); self.send_header('WWW-Authenticate','Basic realm="fixture"'); self.end_headers(); return
            from urllib.parse import unquote
            name = unquote(self.path[len(prefix):].split('?',1)[0])
            target = (files/name).resolve()
            if not target.is_relative_to(files.resolve()) or not target.is_file():
                self.send_error(404); return
            b = target.read_bytes()
            self.send_response(200); self.send_header('Content-Length',str(len(b))); self.end_headers(); self.wfile.write(b)
    s = http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler)
    if cert:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(cert,key)
        s.socket = ctx.wrap_socket(s.socket,server_side=True)
    thread = threading.Thread(target=s.serve_forever,daemon=True);thread.start()
    try: yield ('https' if cert else 'http')+'://127.0.0.1:'+str(s.server_port),calls
    finally:s.shutdown();s.server_close();thread.join()

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--go',required=True)
    ap.add_argument('--jf',required=True)
    ap.add_argument('--report',type=Path)
    a=ap.parse_args()
    go=str(Path(a.go).resolve()); jf=str(Path(a.jf).resolve())
    report={'date':'2026-11-01','scope':'native Go + native CLI; own protocol fixture and storage model; NOT Artifactory','checks':[]}
    def passed(name,**data):report['checks'].append(dict(name=name,passed=True,**data))
    with tempfile.TemporaryDirectory(prefix='artifactory-local-') as td:
        r=Path(td);(r/'home').mkdir();(r/'project').mkdir()
        env={k:v for k,v in os.environ.items() if not k.startswith(('GO','JFROG_'))}
        env.update(HOME=str(r/'home'),GOENV='off',GOFLAGS='',GOWORK='off',GOTOOLCHAIN='local',GOAUTH='off',
                   GOPATH=str(r/'gopath'),GOCACHE=str(r/'gocache'),GOMODCACHE=str(r/'gomodcache'),
                   GOPROXY='off',GOPRIVATE='example.invalid',GONOPROXY='none',GONOSUMDB='example.invalid',
                   GOSUMDB='sum.golang.org',CGO_ENABLED='0',PATH=str(Path(go).parent)+os.pathsep+os.environ.get('PATH',''),
                   JFROG_CLI_HOME_DIR=str(r/'jf-config'),JFROG_CLI_TEMP_DIR=str(r/'jf-state'),
                   JFROG_CLI_REPORT_USAGE='false',JFROG_CLI_OFFER_CONFIG='false',
                   JFROG_CLI_AVOID_NEW_VERSION_WARNING='true',JFROG_CLI_LOG_LEVEL='ERROR',CI='true')
        def run(argv,cwd=None,stdin=None,ok=True,extra=None):
            p=subprocess.run(argv,cwd=cwd or r,env=dict(env,**(extra or {})),input=stdin,text=True,capture_output=True,timeout=90)
            if (p.returncode==0)!=ok:
                raise AssertionError(str(argv[1:3])+': '+p.stderr.replace(str(r),'<temporary>')[:1600])
            return p
        report['go_version']=run([go,'version']).stdout.strip()
        report['cli_version']=run([jf,'--version']).stdout.strip()
        assert report['cli_version']=='jf version 2.129.0'
        passed('pinned CLI version and real Go')
        shutil.copytree(HERE/'module/checkdigit',r/'module')
        run([go,'test','./...'],r/'module');passed('own dependency source tests')
        create(r/'proxy')
        assert escape(MODULE)=='example.invalid/!build!lab/checkdigit'
        assert escape('example.invalid/Team/nested/v2')=='example.invalid/!team/nested/v2'
        passed('uppercase escape preserves slashes and major suffix')
        shutil.copytree(HERE/'service',r/'consumer')
        with endpoint(r/'proxy') as (url,calls):
            proxy=url+'/artifactory/api/go/go-virtual'
            run([go,'mod','tidy'],r/'consumer',extra={'GOPROXY':proxy})
            assert any('/!build!lab/checkdigit/@v/v1.0.0.zip' in unquote(x['path']).lower() for x in calls)
            tidy_calls=len(calls)
            run([go,'build','-trimpath','-ldflags=-X main.version=1.0.0','-o',str(r/'receipt'),'./cmd/receipt'],r/'consumer',extra={'GOPROXY':proxy})
            before=len(calls)
            run([go,'build','-trimpath','-ldflags=-X main.version=1.0.0','-o',str(r/'receipt'),'./cmd/receipt'],r/'consumer',extra={'GOPROXY':proxy})
            assert len(calls)==before
            output=json.loads(run([str(r/'receipt'),'AB']).stdout)
            assert output=={'order':'AB','digit':1,'version':'1.0.0'}
            passed('real Go cold fetch, repeated warm build without new requests, executable output',tidy_requests=tidy_calls,first_build_extra_requests=before-tidy_calls,http_requests=before)
            run([go,'mod','download',MODULE+'@'+VERSION],r/'consumer',extra={'GOPROXY':proxy,'GOMODCACHE':str(r/'clean-modcache')})
            assert len(calls)>before
            passed('new module cache requires actual protocol fetch')
            p=run([go,'mod','download',MODULE+'@'+VERSION],r/'consumer',extra={'GOPROXY':'off','GOMODCACHE':str(r/'missing-modcache')},ok=False)
            passed('cold cache cannot resolve with GOPROXY off',exit=p.returncode)
            run([jf,'config','add','fixture','--url='+url,'--user=fixture','--access-token-stdin','--interactive=false'],stdin='dummy-not-a-secret\n')
            p=run([jf,'rt','ping','--server-id=fixture']);assert 'OK' in p.stdout
            p=run([jf,'rt','curl','/api/system/ping','--server-id=fixture','--fail','--silent','--show-error']);assert p.stdout=='OK'
            passed('real jf rt ping and curl against explicit loopback MOCK, not Artifactory')
        for argv in [[jf,'--server-id=fixture','rt','ping'],[jf,'rt','--server-id=fixture','ping']]:
            run(argv,ok=False)
        passed('server-id is local, rejected before rt and before ping')
        run([jf,'go-config','--server-id-resolve=fixture','--repo-resolve=go-virtual','--server-id-deploy=fixture','--repo-deploy=go-local'],r/'consumer')
        cfg=(r/'consumer/.jfrog/projects/go.yaml').read_text()
        assert 'go-virtual' in cfg and 'go-local' in cfg and 'dummy-not-a-secret' not in cfg
        passed('native go-config persists repository IDs, not token')
        (r/'input.txt').write_bytes(b'own build input\n')
        run([jf,'rt','build-add-dependencies','receipt','1','input.txt'])
        info=json.loads(run([jf,'rt','build-publish','receipt','1','--server-id=fixture','--dry-run']).stdout)
        dep=info['modules'][0]['dependencies'][0]
        assert dep['sha1']==hashlib.sha1((r/'input.txt').read_bytes()).hexdigest()
        assert info['name']=='receipt' and info['number']=='1' and 'properties' not in info
        assert list((r/'jf-state').rglob('partials'))
        run([jf,'rt','bp','receipt','1','--server-id=fixture','--dry-run'])
        passed('native build-info collection and dry-run + bp alias; state under chosen directory',dependency_sha1=dep['sha1'])
        # TLS/netrc is a Go protocol experiment. Its server is our fixture only.
        run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-days','1','-subj','/CN=localhost',
             '-addext','subjectAltName=DNS:localhost,IP:127.0.0.1','-keyout',str(r/'fixture.key'),'-out',str(r/'fixture.crt')])
        netrc=r/'private.netrc';netrc.write_text('machine 127.0.0.1 login fixture password dummy-not-a-secret\n');netrc.chmod(0o600)
        with endpoint(r/'proxy',str(r/'fixture.crt'),str(r/'fixture.key'),True)as(url,calls):
            settings={'GOPROXY':url+'/artifactory/api/go/go-virtual','GOMODCACHE':str(r/'tls-cache'),
                      'SSL_CERT_FILE':str(r/'fixture.crt'),'NETRC':str(netrc),'GOAUTH':'netrc'}
            p=run([go,'mod','download',MODULE+'@'+VERSION],r/'consumer',extra=settings,ok=False)
            assert '401' in p.stderr
            passed('native Go netrc prefix without the nondefault port does not match pinned client URL')
            netrc.write_text('machine '+url.removeprefix('https://')+' login fixture password dummy-not-a-secret\n')
            run([go,'mod','download',MODULE+'@'+VERSION],r/'consumer',extra=settings)
            assert any(x['authorized'] for x in calls)
            passed('native Go HTTPS + scoped CA + netrc credentials',authored_dummy_credentials_only=True)
            settings.update(GOAUTH='off',GOMODCACHE=str(r/'unauth-cache'))
            p=run([go,'mod','download',MODULE+'@'+VERSION],r/'consumer',extra=settings,ok=False)
            assert '401' in p.stderr
            passed('without netrc authentication clean HTTPS client fails 401')
        binary=r/'receipt';document={'version':'1.0.0','toolchain':report['go_version'],'files':[describe(binary)]};verify(document,r)
        for malformed in [{'files':[]},{'version':'1.0.0','toolchain':'Go','files':[]},
                          dict(document,files=document['files']*2),dict(document,files=[dict(document['files'][0],size=True)]),
                          dict(document,files=[dict(document['files'][0],sha256='not-a-hash')])]:
            try:verify(malformed,r)
            except ValueError:pass
            else:raise AssertionError('malformed manifest accepted')
        passed('manifest rejects empty, missing metadata, duplicate names and malformed size/hash')
        outside=r/'outside';outside.mkdir();(outside/'receipt').symlink_to(binary)
        try:verify(document,outside)
        except ValueError:pass
        else:raise AssertionError('symlink accepted')
        (outside/'receipt').unlink();(outside/'receipt').write_bytes(b'changed')
        try:verify(document,outside)
        except ValueError:pass
        else:raise AssertionError('corruption accepted')
        passed('manifest rejects symlink and changed bytes; does not claim origin trust')
        model=Store(r/'model');data=b'one authored payload\n'
        model.put('candidates/receipt/1.0.0',data);model.copy('candidates/receipt/1.0.0','releases/receipt/1.0.0')
        before=model.stats();assert before['references']==2 and before['blob_files']==1
        model.delete('candidates/receipt/1.0.0');assert model.collect()==0
        passed('MODEL: two paths one blob; deleting one reference cannot reclaim live bytes',stats=before)
        model.close();shutil.copytree(r/'model',r/'backup')
        restored=Store(r/'backup');assert restored.read('releases/receipt/1.0.0')==data;restored.close()
        broken=r/'broken';shutil.copytree(r/'backup',broken)
        next((broken/'filestore').glob('*/*')).unlink()
        inconsistent=Store(broken)
        try:inconsistent.read('releases/receipt/1.0.0')
        except FileNotFoundError:pass
        else:raise AssertionError('DB-only recovery accepted')
        inconsistent.close();passed('MODEL: paired restore reads bytes; missing filestore is rejected')
        model=Store(r/'model');model.delete('releases/receipt/1.0.0');assert model.collect()==1;model.close()
        passed('MODEL: last reference removal makes blob collectable')
        samples=[]
        for _ in range(7):
            start=time.perf_counter();run([jf,'--version']);samples.append((time.perf_counter()-start)*1000)
        report['measurement']={'scope':'CLI process startup only; not server throughput/cache efficiency','runs':len(samples),'unit':'ms','median':round(statistics.median(samples),3),'minimum':round(min(samples),3),'maximum':round(max(samples),3)}
    report['checks_passed']=len(report['checks'])
    report['not_executed']=['Artifactory installation/license','real Router/Access/PostgreSQL/filestore','Go publish to real server','OCI push/pull','build-info publish/promotion to real server','RBAC/revocation','coherent Artifactory backup/restore','HA/replication/federation']
    if a.report:a.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
