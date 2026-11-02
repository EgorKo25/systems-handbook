#!/usr/bin/env python3
"""Explicit actions on an owned persistent loopback Vault laboratory. No reset."""
import argparse, base64, contextlib, json, os, pathlib, shlex, signal, socket, ssl, subprocess, sys, time, urllib.error, urllib.request
HERE=pathlib.Path(__file__).resolve().parent
os.umask(0o077)

def save(path,data):
    path.write_text(data if isinstance(data,str) else json.dumps(data,indent=2)+'\n'); path.chmod(0o600)

def settings(root): return json.loads((root/'stand.json').read_text())
def tls(root): return ssl.create_default_context(cafile=str(root/'tls/ca.crt'))
def request(root,path,body=None,token=None,method=None):
    cfg=settings(root); data=None if body is None else json.dumps(body).encode()
    headers={'Content-Type':'application/json'}
    if token: headers['X-Vault-Token']=token
    req=urllib.request.Request(f"https://127.0.0.1:{cfg['port']}/v1/{path}",data,headers,method=method)
    try:
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),urllib.request.HTTPSHandler(context=tls(root)))
        with opener.open(req,timeout=10) as r:
            b=r.read(); return r.status,json.loads(b) if b else {}
    except urllib.error.HTTPError as e:
        return e.code,json.loads(e.read())

def binary(root): return settings(root)['vault']
def operator(root): return (root/'private/operator.token').read_text().strip()
def cli(root,args,token=None,want=0,json_output=False):
    env={k:v for k,v in os.environ.items() if not k.startswith('VAULT_')}; env.update(VAULT_ADDR=f"https://127.0.0.1:{settings(root)['port']}",VAULT_CACERT=str(root/'tls/ca.crt'),VAULT_CONFIG_PATH=str(root/'client.hcl'))
    env.pop('VAULT_NAMESPACE',None); env.pop('VAULT_SKIP_VERIFY',None)
    env['VAULT_TOKEN']=operator(root) if token is None else token
    # No command output containing a credential is emitted to the caller's log.
    r=subprocess.run([binary(root),*args],env=env,cwd=root,text=True,capture_output=True)
    if r.returncode!=want:
        raise RuntimeError(f"vault {' '.join(args[:2])}: expected exit {want}, received {r.returncode}; inspect privately")
    return json.loads(r.stdout) if json_output else r

def ensure_own_process(root):
    pid=int((root/'server.pid').read_text())
    cmd=pathlib.Path(f'/proc/{pid}/cmdline').read_bytes().split(b'\0')
    if str(root/'server.hcl').encode() not in cmd or pathlib.Path(f'/proc/{pid}/cwd').resolve()!=root:
        raise RuntimeError('PID identity differs; refusing to signal')
    return pid

def prepare(root,vault,port,cluster):
    if (root/'stand.json').exists(): raise RuntimeError('stand already exists; use status/start/unseal, never implicit reset')
    if root in (pathlib.Path('/'),pathlib.Path.home()): raise RuntimeError('dedicated root required')
    for n in (port,cluster):
        if not 1024<=n<=65535: raise RuntimeError('unprivileged port required')
        with socket.socket() as s: s.bind(('127.0.0.1',n))
    if port==cluster: raise RuntimeError('API and cluster ports must differ')
    root.mkdir(parents=True,exist_ok=True,mode=0o700); root.chmod(0o700)
    for d in ('private','tls','state','logs','snapshots'): (root/d).mkdir(mode=0o700,exist_ok=True)
    version=subprocess.run([str(vault),'version'],text=True,capture_output=True,check=True).stdout
    if not version.startswith('Vault v1.21.4 '): raise RuntimeError('this laboratory pins Vault v1.21.4')
    save(root/'stand.json',dict(vault=str(vault),port=port,cluster=cluster,version=version.strip()))
    def openssl(args): subprocess.run(['openssl',*args],check=True,capture_output=True,cwd=root/'tls')
    openssl(['req','-x509','-newkey','rsa:2048','-nodes','-keyout','ca.key','-out','ca.crt','-days','30','-subj','/CN=Handbook local CA','-addext','basicConstraints=critical,CA:TRUE','-addext','keyUsage=critical,keyCertSign,cRLSign'])
    openssl(['req','-newkey','rsa:2048','-nodes','-keyout','server.key','-out','server.csr','-subj','/CN=localhost'])
    save(root/'tls/server.ext','subjectAltName=IP:127.0.0.1,DNS:localhost\nbasicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature,keyEncipherment\nextendedKeyUsage=serverAuth\n')
    openssl(['x509','-req','-in','server.csr','-CA','ca.crt','-CAkey','ca.key','-CAcreateserial','-out','server.crt','-days','14','-extfile','server.ext'])
    save(root/'server.hcl',f'''ui = false
disable_mlock = true
api_addr = "https://127.0.0.1:{port}"
cluster_addr = "https://127.0.0.1:{cluster}"
listener "tcp" {{
  address = "127.0.0.1:{port}"
  cluster_address = "127.0.0.1:{cluster}"
  tls_cert_file = "{root}/tls/server.crt"
  tls_key_file = "{root}/tls/server.key"
  tls_min_version = "tls12"
}}
storage "raft" {{
  path = "{root}/state"
  node_id = "handbook-one"
}}
''')
    helper=root/'private/token-helper.sh'
    save(helper,'#!/bin/sh\ncase "$1" in\n  get|erase) exit 0 ;;\n  store) echo "Token storage disabled; use explicit private token files" >&2; exit 1 ;;\n  *) exit 1 ;;\nesac\n')
    helper.chmod(0o700)
    save(root/'client.hcl',f'token_helper = "{helper}"\n')
    save(root/'env.sh',f'unset VAULT_TOKEN VAULT_NAMESPACE VAULT_SKIP_VERIFY VAULT_CLIENT_CERT VAULT_CLIENT_KEY VAULT_AGENT_ADDR\nexport VAULT_ADDR=https://127.0.0.1:{port}\nexport VAULT_CACERT={shlex.quote(str(root/"tls/ca.crt"))}\nexport VAULT_CONFIG_PATH={shlex.quote(str(root/"client.hcl"))}\nexport PATH={shlex.quote(str(vault.parent))}:"$PATH"\n')
    print('Prepared private persistent stand; no server started')

def start(root):
    if (root/'server.pid').exists():
        try: ensure_own_process(root); raise RuntimeError('owned server is already running')
        except FileNotFoundError: pass
    log=(root/'logs/server.log').open('ab')
    proc=subprocess.Popen([binary(root),'server','-config',str(root/'server.hcl')],cwd=root,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    log.close(); save(root/'server.pid',str(proc.pid)+'\n')
    for _ in range(100):
        if proc.poll() is not None: raise RuntimeError('server exited; inspect private logs/server.log')
        try:
            code,_=request(root,'sys/health')
            if code in (200,429,501,503): print('TLS listener ready; initialization/seal state still requires status'); return
        except (OSError,urllib.error.URLError): pass
        time.sleep(.1)
    raise RuntimeError('listener readiness timed out')

def unseal(root,source=None):
    source=source or root
    data=json.loads((source/'private/init.json').read_text())
    for share in data['unseal_keys_b64'][:2]:
        code,r=request(root,'sys/unseal',{'key':share})
        if code!=200: raise RuntimeError('unseal failed; stop')
    if r['sealed']: raise RuntimeError('threshold not reached; stop')
    for _ in range(100):
        code,_=request(root,'sys/health')
        if code==200: print('Unsealed; active node ready'); return
        time.sleep(.1)
    raise RuntimeError('active readiness timed out')

def initialize(root):
    _,r=request(root,'sys/init')
    if r['initialized']: raise RuntimeError('already initialized; use unseal; never initialize an existing store again')
    env={k:v for k,v in os.environ.items() if not k.startswith('VAULT_')}; env.update(VAULT_ADDR=f"https://127.0.0.1:{settings(root)['port']}",VAULT_CACERT=str(root/'tls/ca.crt'),VAULT_CONFIG_PATH=str(root/'client.hcl'))
    env.pop('VAULT_TOKEN',None); env.pop('VAULT_SKIP_VERIFY',None)
    out=subprocess.run([binary(root),'operator','init','-key-shares=3','-key-threshold=2','-format=json'],env=env,cwd=root,capture_output=True,text=True,check=True)
    data=json.loads(out.stdout); save(root/'private/init.json',data); unseal(root)
    initial=data['root_token']
    # A broad lab operator is time-bounded and orphaned before bootstrap root revoke.
    policy='path "*" { capabilities = ["create", "read", "update", "patch", "delete", "list", "sudo"] }'
    code,_=request(root,'sys/policies/acl/handbook-operator',{'policy':policy},initial,method='PUT')
    if code!=204: raise RuntimeError('operator policy failed')
    token=cli(root,['token','create','-orphan','-policy=handbook-operator','-ttl=8h','-explicit-max-ttl=24h','-format=json'],token=initial,json_output=True)['auth']['client_token']
    save(root/'private/operator.token',token+'\n')
    cli(root,['token','revoke','-self'],token=initial)
    code,_=request(root,'auth/token/lookup-self',token=initial)
    if code!=403: raise RuntimeError('bootstrap root revocation not confirmed')
    print('Initialized 3 shares / threshold 2; bootstrap root revoked; lab operator bounded to 24h')

def token(root,policy,ttl='10m'):
    return cli(root,['token','create',f'-policy={policy}',f'-ttl={ttl}','-format=json'],json_output=True)['auth']['client_token']

def provision(root):
    mounts=cli(root,['secrets','list','-format=json'],json_output=True)
    if 'secret/' not in mounts: cli(root,['secrets','enable','-path=secret','-version=2','kv'])
    for name in ('reader','writer','application'):
        cli(root,['policy','write',f'handbook-{name}',str(HERE/'policies'/f'{name}.hcl')])
    cli(root,['kv','put','-mount=secret','-cas=0','handbook/config','message=first'])
    cli(root,['kv','put','-mount=secret','handbook/forbidden','message=not-for-reader'])
    for name in ('reader','writer'): save(root/f'private/{name}.token',token(root,f'handbook-{name}')+'\n')
    audit=cli(root,['audit','list','-format=json'],json_output=True)
    if 'file/' not in audit: cli(root,['audit','enable','file','file_path=logs/audit.jsonl','mode=0600'])
    print('Provisioned KVv2, policies, short-lived test tokens, audit; no secret printed')

def test_tokens(root):
    for name in ('reader','writer'):
        save(root/f'private/{name}.token',token(root,f'handbook-{name}')+'\n')
    print('Fresh reader/writer tokens issued for 10m; KV state unchanged')

def checks(root):
    reader=(root/'private/reader.token').read_text().strip(); writer=(root/'private/writer.token').read_text().strip(); passed=[]
    def check(label,condition):
        if not condition: raise AssertionError(label)
        passed.append(label)
    r=cli(root,['kv','get','-mount=secret','-format=json','handbook/config'],token=reader,json_output=True)
    check('ACL read allowed',r['data']['data']['message']=='first')
    code,_=request(root,'secret/data/handbook/config',{'data':{'message':'forbidden'}},reader,method='POST'); check('ACL update denied HTTP403',code==403)
    code,_=request(root,'secret/data/handbook/forbidden',token=reader); check('explicit deny HTTP403',code==403)
    code,r=request(root,'secret/metadata/handbook',token=reader,method='LIST'); check('metadata LIST allowed',code==200 and 'config' in r['data']['keys'])
    code,_=request(root,'secret/data/handbook',token=reader,method='LIST'); check('data LIST denied',code==403)
    cli(root,['kv','put','-mount=secret','-cas=1','handbook/config','message=second'],token=writer)
    code,_=request(root,'secret/data/handbook/config',{'options':{'cas':1},'data':{'message':'stale'}},writer,method='POST'); check('stale CAS HTTP400',code==400)
    cli(root,['kv','patch','-mount=secret','-cas=2','handbook/config','added=yes'],token=writer)
    r=cli(root,['kv','get','-mount=secret','-format=json','handbook/config'],token=reader,json_output=True)
    check('PATCH retains field and increments version',r['data']['metadata']['version']==3 and r['data']['data']=={'message':'second','added':'yes'})
    cli(root,['kv','delete','-mount=secret','-versions=2','handbook/config'])
    code,_=request(root,'secret/data/handbook/config?version=2',token=reader); check('soft-deleted v2 absent HTTP404',code==404)
    cli(root,['kv','undelete','-mount=secret','-versions=2','handbook/config'])
    code,_=request(root,'secret/data/handbook/config?version=2',token=reader); check('undelete v2 HTTP200',code==200)
    cli(root,['kv','destroy','-mount=secret','-versions=2','handbook/config'])
    r=cli(root,['kv','metadata','get','-mount=secret','-format=json','handbook/config'],json_output=True)
    check('destroyed v2 irreversible flag',r['data']['versions']['2']['destroyed'] is True)
    short=token(root,'handbook-reader','3s'); code,_=request(root,'secret/data/handbook/config',token=short); check('TTL before expiry HTTP200',code==200)
    time.sleep(4); code,_=request(root,'secret/data/handbook/config',token=short); check('TTL after expiry HTTP403',code==403)
    revoke=token(root,'handbook-reader'); rc,_=request(root,'auth/token/revoke',{'token':revoke},operator(root)); assert rc==204; code,_=request(root,'secret/data/handbook/config',token=revoke); check('explicit token revoke HTTP403',code==403)
    save(root/'checks.json',dict(kind='native TLS Vault 1.21.4',checks=passed,passed=len(passed)))
    print(json.dumps(dict(passed=len(passed),checks=passed),ensure_ascii=False))

def approle(root):
    auth=cli(root,['auth','list','-format=json'],json_output=True)
    if 'approle/' not in auth: cli(root,['auth','enable','approle'])
    cli(root,['write','auth/approle/role/handbook','token_policies=handbook-application','token_ttl=5m','token_max_ttl=20m','secret_id_ttl=5m','secret_id_num_uses=1'])
    rid=cli(root,['read','-format=json','auth/approle/role/handbook/role-id'],json_output=True)['data']['role_id']
    wrapped=cli(root,['write','-wrap-ttl=60s','-f','-format=json','auth/approle/role/handbook/secret-id'],json_output=True)
    wtoken=wrapped['wrap_info']['token']; save(root/'private/wrapped-secret-id.json',wrapped)
    code,r=request(root,'sys/wrapping/lookup',{},wtoken); assert code==200
    assert r['data']['creation_path']=='auth/approle/role/handbook/secret-id'
    code,unwrapped=request(root,'sys/wrapping/unwrap',{},wtoken); assert code==200
    sid=unwrapped['data']['secret_id']; save(root/'private/role-id',rid+'\n'); save(root/'private/secret-id',sid+'\n')
    code,_=request(root,'sys/wrapping/unwrap',{},wtoken); assert code in (400,403)
    code,login=request(root,'auth/approle/login',dict(role_id=rid,secret_id=sid)); assert code==200
    save(root/'private/application.token',login['auth']['client_token']+'\n')
    code,_=request(root,'auth/approle/login',dict(role_id=rid,secret_id=sid)); assert code in (400,403)
    print('AppRole: wrapping creation_path checked; unwrap once; SecretID login once; second uses denied')

def pki(root):
    mounts=cli(root,['secrets','list','-format=json'],json_output=True)
    if any(name+'/' in mounts for name in ('pki-root','pki-int')):
        raise RuntimeError('PKI mount already exists; inspect both mounts instead of partially creating/replacing CA')
    for name in ('pki-root','pki-int'):
        cli(root,['secrets','enable',f'-path={name}','pki']); cli(root,['secrets','tune','-max-lease-ttl=8760h',name])
    ca=cli(root,['write','-format=json','pki-root/root/generate/internal','common_name=Handbook Lab Root','ttl=8760h'],json_output=True)
    save(root/'private/pki-root.json',ca)
    csr=cli(root,['write','-format=json','pki-int/intermediate/generate/internal','common_name=Handbook Lab Intermediate'],json_output=True)
    save(root/'private/intermediate.csr',csr['data']['csr'])
    signed=cli(root,['write','-format=json','pki-root/root/sign-intermediate',f'csr=@{root}/private/intermediate.csr','format=pem_bundle','ttl=720h'],json_output=True)
    save(root/'private/intermediate.pem',signed['data']['certificate'])
    cli(root,['write','pki-int/intermediate/set-signed',f'certificate=@{root}/private/intermediate.pem'])
    cli(root,['write','pki-int/roles/handbook','allowed_domains=lab.example.invalid','allow_subdomains=true','allow_bare_domains=false','allow_ip_sans=false','max_ttl=1h'])
    cert=cli(root,['write','-format=json','pki-int/issue/handbook','common_name=api.lab.example.invalid','ttl=10m'],json_output=True)
    save(root/'private/leaf.json',cert); save(root/'private/leaf.pem',cert['data']['certificate'])
    save(root/'private/leaf.key',cert['data']['private_key'])
    code,_=request(root,'pki-int/issue/handbook',dict(common_name='outside.example.invalid'),operator(root)); assert code==400
    cli(root,['write','pki-int/revoke','serial_number='+cert['data']['serial_number']])
    code,_=request(root,'pki-int/cert/crl'); assert code==200
    print('PKI: internal root → intermediate CSR → signed intermediate → leaf; outside SAN denied; revoked CRL fetched')

def agent(root):
    # A fresh SecretID is required: approle() deliberately consumed its first one.
    wrapped=cli(root,['write','-wrap-ttl=60s','-f','-format=json','auth/approle/role/handbook/secret-id'],json_output=True)
    w=wrapped['wrap_info']['token']
    code,meta=request(root,'sys/wrapping/lookup',{},w); assert code==200 and meta['data']['creation_path']=='auth/approle/role/handbook/secret-id'
    code,r=request(root,'sys/wrapping/unwrap',{},w); assert code==200
    save(root/'private/agent-secret-id',r['data']['secret_id']+'\n')
    save(root/'private/agent.hcl',f'''exit_after_auth = true
vault {{
  address = "https://127.0.0.1:{settings(root)['port']}"
  ca_cert = "{root}/tls/ca.crt"
}}
auto_auth {{
  method "approle" {{
    config = {{
      role_id_file_path = "{root}/private/role-id"
      secret_id_file_path = "{root}/private/agent-secret-id"
      remove_secret_id_file_after_reading = true
    }}
  }}
  sink "file" {{
    config = {{ path = "{root}/private/agent.token", mode = 0600 }}
  }}
}}
template {{
  contents = <<EOT
{{{{ with secret "secret/data/handbook/config" }}}}message={{{{ .Data.data.message }}}}{{{{ end }}}}
EOT
  destination = "{root}/private/rendered.env"
  perms = 0600
  error_on_missing_key = true
}}
''')
    # Agent logs stay private; they are not returned to CI.
    env={k:v for k,v in os.environ.items() if not k.startswith('VAULT_')}
    r=subprocess.run([binary(root),'agent','-config',str(root/'private/agent.hcl')],env=env,cwd=root,capture_output=True,timeout=30)
    save(root/'logs/agent.log',(r.stdout+r.stderr).decode(errors='replace'))
    if r.returncode: raise RuntimeError('Agent failed; inspect private logs/agent.log')
    assert (root/'private/rendered.env').read_text().strip()=='message=second'
    assert (root/'private/rendered.env').stat().st_mode & 0o777 == 0o600
    assert not (root/'private/agent-secret-id').exists()
    print('Agent native: fresh single-use AppRole login, template rendered 0600, consumed SecretID removed; one-shot mode')

def snapshot(root,name):
    if pathlib.Path(name).name!=name or not name.endswith('.snap'): raise RuntimeError('snapshot name must be a plain .snap basename')
    path=root/'snapshots'/name
    if path.exists(): raise RuntimeError('snapshot already exists; choose a new explicit name')
    cli(root,['operator','raft','snapshot','save',str(path)]); path.chmod(0o600)
    print('Snapshot saved; recovery not yet proven')

def restore(root,source,name):
    # This destructive operation is allowed only on a distinct newly prepared target.
    if root==source: raise RuntimeError('restore target must differ from source')
    if pathlib.Path(name).name!=name or not name.endswith('.snap'): raise RuntimeError('snapshot name must be a plain .snap basename')
    if (root/'private/operator.token').exists(): raise RuntimeError('target already initialized; prepare a fresh separate target')
    if (root/'restore-complete.json').exists(): raise RuntimeError('target already restored')
    snapshot=source/'snapshots'/name
    if not snapshot.is_file(): raise RuntimeError('source snapshot missing; target left uninitialized')
    # Fail before creating target credentials if source custody files are missing.
    source_init=json.loads((source/'private/init.json').read_text())
    if len(source_init.get('unseal_keys_b64',[]))<2: raise RuntimeError('source Shamir custody missing')
    source_operator=(source/'private/operator.token').read_text()
    code,health=request(root,'sys/init')
    if code!=200 or health.get('initialized') is not False:
        raise RuntimeError('target must be uninitialized; no force restore into existing state')
    initialize(root)
    cli(root,['operator','raft','snapshot','restore','-force',str(source/'snapshots'/name)])
    # CLI acceptance is asynchronous: wait for the imported state to seal the node.
    for _ in range(150):
        try:
            code,state=request(root,'sys/seal-status')
            if code==200 and state['sealed']: break
        except (OSError,urllib.error.URLError): pass
        time.sleep(.1)
    else: raise RuntimeError('accepted restore did not reach sealed state; inspect private server log')
    # Imported snapshot uses SOURCE barrier keys; the target's fresh shares are obsolete.
    unseal(root,source)
    save(root/'private/target-bootstrap-init-obsolete.json',(root/'private/init.json').read_text())
    save(root/'private/init.json',source_init)
    save(root/'private/operator.token',source_operator)
    save(root/'restore-imported.json',dict(source=str(source),snapshot=name,imported=True))
    code,_=request(root,'auth/token/lookup-self',token=source_operator.strip())
    if code!=200:
        raise RuntimeError('snapshot imported/unsealed, but current source operator is not valid in that snapshot; recover-operator on target, then verify-restore; do not import again')
    verify_restore(root)

def verify_restore(root):
    imported=json.loads((root/'restore-imported.json').read_text())
    restored=cli(root,['kv','get','-mount=secret','-format=json','handbook/config'],json_output=True)
    save(root/'restore-complete.json',dict(imported,restored_version=restored['data']['metadata']['version']))
    print('Separate restore accepted; compare value/version and external credentials with checkpoint')

def recover_operator(root):
    """Explicit single-owner Shamir lab ceremony, never an automatic login retry."""
    code,seal=request(root,'sys/seal-status')
    if code!=200 or seal.get('sealed') or seal.get('type')!='shamir':
        raise RuntimeError('recover-operator requires an unsealed Shamir laboratory')
    if (root/'private/operator.token').exists():
        code,_=request(root,'auth/token/lookup-self',token=operator(root))
        if code==200: raise RuntimeError('operator still valid; inspect/renew instead of generating root')
        if code!=403: raise RuntimeError('operator check inconclusive; no ceremony started')
    custody=json.loads((root/'private/init.json').read_text())
    shares=custody.get('unseal_keys_b64',[])
    code,status=request(root,'sys/generate-root/attempt')
    if code!=200 or status.get('started'): raise RuntimeError('root generation already active or status unavailable; no cancellation of another ceremony')
    required=status.get('required')
    if not isinstance(required,int) or required<1 or len(set(shares))<required:
        raise RuntimeError('insufficient distinct Shamir shares in private lab custody')
    record=root/'private'/f'operator-recovery-{time.time_ns()}.json'
    report={'kind':'explicit single-owner Shamir laboratory ceremony','root_revoked':False,'operator_saved':False}
    ephemeral=None; nonce=None
    try:
        code,attempt=request(root,'sys/generate-root/attempt',{})
        if code!=200: raise RuntimeError('root generation start failed')
        nonce=attempt['nonce'];otp=attempt['otp'];report['attempt']=attempt;save(record,report)
        if not nonce or len(otp.encode('ascii'))!=attempt['otp_length']:
            raise RuntimeError('invalid generation response; inspect private recovery record')
        for share in list(dict.fromkeys(shares))[:required]:
            code,result=request(root,'sys/generate-root/update',{'nonce':nonce,'key':share})
            if code!=200 or result.get('nonce')!=nonce: raise RuntimeError('root share submission failed')
        report['result']=result;save(record,report)
        encoded=result.get('encoded_token')
        if not result.get('complete') or not encoded: raise RuntimeError('root threshold not completed')
        raw=base64.b64decode(encoded+'='*(-len(encoded)%4),validate=True)
        pad=otp.encode('ascii')
        if len(raw)!=len(pad): raise RuntimeError('encoded token length mismatch; private recovery record retained')
        ephemeral=bytes(a^b for a,b in zip(raw,pad)).decode('ascii')
        # Private crash recovery only; the generated token is never stdout/argv.
        report['temporary_root']=ephemeral;save(record,report)
        policy='path "*" { capabilities = ["create", "read", "update", "patch", "delete", "list", "sudo"] }'
        code,_=request(root,'sys/policies/acl/handbook-operator',{'policy':policy},ephemeral,method='PUT')
        if code!=204: raise RuntimeError('operator policy recovery failed')
        code,created=request(root,'auth/token/create-orphan',{'policies':['handbook-operator'],'ttl':'8h','explicit_max_ttl':'24h','renewable':True},ephemeral)
        if code!=200: raise RuntimeError('bounded operator issue failed')
        fresh=created['auth']['client_token']
        pending=root/'private/operator.token.next';save(pending,fresh+'\n');pending.replace(root/'private/operator.token')
        code,lookup=request(root,'auth/token/lookup-self',token=fresh)
        if code!=200 or not lookup['data'].get('orphan') or lookup['data'].get('explicit_max_ttl')!=86400:
            raise RuntimeError('new operator verification failed')
        report.update(operator_saved=True,operator_ttl_seconds=lookup['data']['ttl'],operator_explicit_max_ttl_seconds=86400)
    finally:
        if ephemeral:
            code,_=request(root,'auth/token/revoke-self',{},ephemeral)
            check,_=request(root,'auth/token/lookup-self',token=ephemeral)
            report['root_revoked']=code==204 and check==403;save(record,report)
            if not report['root_revoked']: raise RuntimeError('temporary root revoke NOT confirmed; private recovery record requires immediate operator action')
        elif nonce:
            code,current=request(root,'sys/generate-root/attempt')
            if code==200 and current.get('started') and current.get('nonce')==nonce:
                cancel,_=request(root,'sys/generate-root/attempt',method='DELETE')
                report['own_incomplete_attempt_cancelled']=cancel==204;save(record,report)
    print('Recovered bounded orphan operator; temporary root revoked and HTTP403 confirmed; record private')

def measure(root,count):
    if count<10 or count>1000: raise RuntimeError('measurement count 10..1000')
    durations=[]; failures=0; t=operator(root)
    for _ in range(count):
        start=time.monotonic_ns(); code,_=request(root,'secret/data/handbook/config',token=t); durations.append((time.monotonic_ns()-start)/1e6); failures+=code!=200
    import math,statistics
    durations.sort(); report=dict(kind='sequential HTTPS KV read, fresh TLS connection per request',n=count,errors=failures,median_ms=statistics.median(durations),p95_ms=durations[math.ceil(.95*count)-1],p99_ms=durations[math.ceil(.99*count)-1],max_ms=max(durations),audit_enabled=True)
    save(root/'measure.json',report); print(json.dumps(report))

def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--root',type=pathlib.Path,required=True)
    sub=p.add_subparsers(dest='action',required=True)
    s=sub.add_parser('prepare'); s.add_argument('--vault',type=pathlib.Path,required=True); s.add_argument('--port',type=int,default=18200); s.add_argument('--cluster-port',type=int,default=18201)
    for act in ('start','init','unseal','provision','checks','approle','pki','agent','test-tokens','recover-operator','verify-restore','status','stop'): sub.add_parser(act)
    s=sub.add_parser('snapshot'); s.add_argument('--name',required=True)
    s=sub.add_parser('restore'); s.add_argument('--source',type=pathlib.Path,required=True); s.add_argument('--name',required=True)
    s=sub.add_parser('measure'); s.add_argument('--count',type=int,default=100)
    a=p.parse_args(); root=a.root.expanduser().resolve()
    if a.action=='prepare': prepare(root,a.vault.expanduser().resolve(),a.port,a.cluster_port)
    elif a.action=='start': start(root)
    elif a.action=='init': initialize(root)
    elif a.action=='unseal': unseal(root)
    elif a.action=='provision': provision(root)
    elif a.action=='checks': checks(root)
    elif a.action=='test-tokens': test_tokens(root)
    elif a.action=='recover-operator': recover_operator(root)
    elif a.action=='verify-restore': verify_restore(root)
    elif a.action=='approle': approle(root)
    elif a.action=='pki': pki(root)
    elif a.action=='agent': agent(root)
    elif a.action=='snapshot': snapshot(root,a.name)
    elif a.action=='restore': restore(root,a.source.expanduser().resolve(),a.name)
    elif a.action=='measure': measure(root,a.count)
    elif a.action=='status':
        code,r=request(root,'sys/health'); print(json.dumps({k:r.get(k) for k in ('initialized','sealed','standby','version') }|{'http':code}))
    elif a.action=='stop':
        pid=ensure_own_process(root); os.kill(pid,signal.SIGTERM)
        for _ in range(100):
            try:
                data=pathlib.Path(f'/proc/{pid}/stat').read_text()
                if data.split(') ',1)[1].startswith('Z'): break
            except FileNotFoundError: break
            time.sleep(.1)
        else: raise RuntimeError('stop timed out; no forced kill performed')
        (root/'server.pid').unlink(); print('Owned PID stopped; persistent state retained')
if __name__=='__main__':
    try: main()
    except Exception as e: print(f'STOP: {type(e).__name__}: {e}',file=sys.stderr); sys.exit(1)
