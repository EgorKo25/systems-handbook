#!/usr/bin/env python3
"""Copy teaching inputs once. Never overwrite an existing reader directory."""
import argparse,json,os,shlex,shutil,subprocess,sys
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--go',required=True);p.add_argument('--root',required=True)
a=p.parse_args();go=Path(a.go).expanduser().absolute();root=Path(a.root).expanduser().absolute()
if not go.is_file() or not os.access(go,os.X_OK):p.error('--go must name an existing executable')
env=os.environ.copy();env.update(GOENV='off',GOTOOLCHAIN='local',GOWORK='off',GOTELEMETRY='off');env.pop('GOROOT',None)
r=subprocess.run([str(go),'version'],env=env,text=True,capture_output=True)
if r.returncode or r.stdout.strip()!='go version go1.27.3 linux/amd64':
 p.error('requires Go 1.27.3 linux/amd64; got '+repr(r.stdout+r.stderr))
if root.exists() or root.is_symlink():p.error('root already exists; preserve it and source its env.sh, or choose another NEW root')
here=Path(__file__).resolve().parent
if root==here or here in root.parents:p.error('choose a reader directory outside the distributed lab')
root.mkdir(parents=True)
try:
 shutil.copytree(here.parent/'service',root/'service',ignore=shutil.ignore_patterns('.git','dist','.lab-cache','__pycache__'))
 shutil.copytree(here/'fixtures',root/'fixtures')
 for d in ['cache/build','cache/modules','cache/gopath','tmp','out']:(root/d).mkdir(parents=True)
 values={'LAB':str(root),'HANDBOOK_GO':str(go),'GOENV':'off','GOTOOLCHAIN':'local','GOWORK':'off','GOFLAGS':'',
  'GO111MODULE':'on','GOCACHEPROG':'','GODEBUG':'','GOFIPS140':'off','GOTMPDIR':str(root/'tmp'),
  'GOCACHE':str(root/'cache/build'),'GOMODCACHE':str(root/'cache/modules'),'GOPATH':str(root/'cache/gopath'),
  'TMPDIR':str(root/'tmp'),'GOPROXY':'off','GOSUMDB':'off','GOTELEMETRY':'off','GOEXPERIMENT':'',
  'CGO_ENABLED':'0','GOOS':'linux','GOARCH':'amd64','GOAMD64':'v1','GOMAXPROCS':'2'}
 text="# Bash session for this reader-owned lab. No global Go settings.\nunset GOROOT\n"
 text+=''.join('export '+k+'='+shlex.quote(v)+'\n' for k,v in values.items())
 text+='export PATH='+shlex.quote(str(go.parent))+':"$PATH"\n'
 (root/'env.sh').write_text(text)
 (root/'.handbook-go-foundations.json').write_text(json.dumps({'format':1,'toolchain':r.stdout.strip(),'root':str(root)},indent=2)+'\n')
except Exception:
 print('Preparation stopped; preserve the partial directory for diagnosis; choose a new root after fixing the cause.',file=sys.stderr);raise
print('Prepared '+str(root));print('source '+shlex.quote(str(root/'env.sh')))
