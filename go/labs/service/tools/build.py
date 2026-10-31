"""Explicit Go teaching build. No packages are installed and no go env -w is used."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]

def git(*args):
    env = {k:v for k,v in os.environ.items() if not k.startswith('GIT_')}
    env.update(GIT_CONFIG_GLOBAL=os.devnull,GIT_CONFIG_SYSTEM=os.devnull,GIT_CONFIG_NOSYSTEM='1',GIT_TERMINAL_PROMPT='0')
    return subprocess.check_output(['git','-c','core.fsmonitor=false',*args],cwd=ROOT,env=env,stderr=subprocess.DEVNULL,text=True).strip()

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--goos',default='linux',choices=['linux','windows'])
    parser.add_argument('--goarch',default='amd64',choices=['amd64','arm64'])
    parser.add_argument('--version',default='1.0.0')
    args=parser.parse_args()
    if not args.version or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-_+' for c in args.version):
        parser.error('version must be a nonempty simple release label')
    tool=os.environ.get('HANDBOOK_GO') or shutil.which('go')
    if not tool: parser.error('Go is not installed or HANDBOOK_GO is not set')
    out=ROOT/'dist'
    if out.is_symlink(): parser.error('dist cannot be a symlink')
    out.mkdir(exist_ok=True)
    name='handbook-service'+('.exe' if args.goos=='windows' else '')
    binary=out/name
    if binary.is_symlink(): parser.error('output cannot be a symlink')
    env=os.environ.copy()
    env.update(GOENV='off',GOTOOLCHAIN='local',GOWORK='off',GOFLAGS='',
               CGO_ENABLED='0',GOOS=args.goos,GOARCH=args.goarch,GOAMD64='v1',GOEXPERIMENT='',
               GOCACHE=str(ROOT/'.lab-cache/build'),GOPATH=str(ROOT/'.lab-cache/gopath'),
               GOMODCACHE=str(ROOT/'.lab-cache/modules'),GOPROXY='off',GOTELEMETRY='off')
    flags=['-mod=readonly','-trimpath','-buildvcs=false','-ldflags=-X main.Version='+args.version]
    subprocess.run([tool,'build',*flags,'-o',str(binary),'./cmd/handbook-service'],cwd=ROOT,env=env,check=True)
    data=binary.read_bytes()
    toolchain=subprocess.check_output([tool,'version'],env=env,text=True).strip()
    try:
        is_root=Path(git('rev-parse','--show-toplevel')).resolve()==ROOT
        revision=git('rev-parse','--verify','HEAD') if is_root else None
        dirty=bool(git('status','--porcelain','--untracked-files=normal')) if is_root else True
    except (subprocess.CalledProcessError,OSError): revision=None;dirty=True
    manifest={'format':1,'binary':name,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),
              'version':args.version,'toolchain':toolchain,'flags':flags,
              'target':{k:env[k] for k in ['GOOS','GOARCH','GOAMD64','CGO_ENABLED','GOEXPERIMENT']},
              'source_revision':revision,'source_dirty':dirty,
              'build_script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    target=out/'manifest.json'
    if target.is_symlink(): parser.error('manifest cannot be a symlink')
    with target.open('w',encoding='utf-8',newline='\n') as f: f.write(json.dumps(manifest,sort_keys=True,indent=2)+'\n')
    print(json.dumps(manifest,sort_keys=True))

if __name__=='__main__': main()
