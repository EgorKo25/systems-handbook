"""Create a new persistent Go compiler/runtime stand; never reset an existing one."""
import argparse, hashlib, json, os, shlex, shutil, subprocess
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--go',required=True,type=Path);p.add_argument('--root',required=True,type=Path)
a=p.parse_args();root=a.root.expanduser().absolute();go=a.go.expanduser().resolve()
if root.exists() or root.is_symlink():p.error('root already exists; preserved. Resume with its env.sh or choose another root')
if not go.is_file():p.error('--go must name an existing executable bin/go')
env={k:v for k,v in os.environ.items() if not k.startswith(('GO','CGO')) and k not in ('BASH_ENV','ENV')}
env.update(GOENV='off',GOTOOLCHAIN='local',GOWORK='off',GOTELEMETRY='off',GOPROXY='off',GOSUMDB='off')
v=subprocess.run([str(go),'version'],env=env,capture_output=True,text=True,timeout=10)
if v.returncode or v.stdout.strip()!='go version go1.27.3 linux/amd64':p.error('this profile requires existing Go1.27.3 linux/amd64; no download attempted')
here=Path(__file__).resolve().parent
root.parent.mkdir(parents=True,exist_ok=True);root.mkdir()
shutil.copytree(here/'fixtures',root/'projects')
shutil.copytree(here.parent/'service',root/'service',ignore=shutil.ignore_patterns('dist','.lab-cache','__pycache__'))
shutil.copy2(here/'handler_bench_test.go',root/'service/internal/httpapp/handler_bench_test.go')
for d in ('out','reports','cache/build','cache/modules','cache/gopath','tmp','work'): (root/d).mkdir(parents=True,exist_ok=True)
settings=dict(GO=str(go),LABROOT=str(root),GOCACHE=str(root/'cache/build'),GOMODCACHE=str(root/'cache/modules'),GOPATH=str(root/'cache/gopath'),TMPDIR=str(root/'tmp'),GOTMPDIR=str(root/'tmp'),GOENV='off',GOTOOLCHAIN='local',GOWORK='off',GOTELEMETRY='off',GOPROXY='off',GOSUMDB='off',GOFLAGS='',GOOS='linux',GOARCH='amd64',GOAMD64='v1',GOEXPERIMENT='',CGO_ENABLED='0',GOMAXPROCS='2',GODEBUG='',GOGC='100',GOMEMLIMIT='off',CGO_CFLAGS='-O2 -g',CGO_CPPFLAGS='',CGO_CXXFLAGS='-O2 -g',CGO_LDFLAGS='-O2 -g')
(root/'env.json').write_text(json.dumps(settings,indent=2)+'\n')
(root/'env.sh').write_text('# Source only your own newly created file.\nunset BASH_ENV ENV\n'+''.join('export '+k+'='+shlex.quote(v)+'\n' for k,v in settings.items())+'export PATH='+shlex.quote(str(go.parent))+':"$PATH"\n')
manifest={str(f.relative_to(root)):hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(root.rglob('*')) if f.is_file()}
(root/'prepared.json').write_text(json.dumps({'format':1,'toolchain':v.stdout.strip(),'source_files':manifest},indent=2)+'\n')
print(root/'env.sh')
