#!/usr/bin/env python3
"""Настоящая справка выбранных CLI и безопасный upload dry-run без сервера.
Не проверяет каждую форму всей справки и не подтверждает серверные права.
"""
import argparse, json, os, re, runpy, shlex, subprocess, sys, tempfile
from pathlib import Path
sys.dont_write_bytecode=True

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--jf',required=True);ap.add_argument('--oras',required=True);ap.add_argument('--report',type=Path);a=ap.parse_args()
    volume=Path(__file__).resolve().parents[2]
    commands=runpy.run_path(str(volume/'sources/reference.py'))['COMMANDS']
    report={'date':'2026-11-01','scope':'actual pinned help, selected aliases and native no-server upload dry-run; not Artifactory','commands':[]}
    with tempfile.TemporaryDirectory(prefix='artifactory-grammar-') as td:
        root=Path(td);env={k:v for k,v in os.environ.items() if not k.startswith('JFROG_')}
        env.update(HOME=td,JFROG_CLI_HOME_DIR=str(root/'config'),JFROG_CLI_TEMP_DIR=str(root/'state'),CI='true',
          JFROG_CLI_REPORT_USAGE='false',JFROG_CLI_OFFER_CONFIG='false',JFROG_CLI_AVOID_NEW_VERSION_WARNING='true',JFROG_CLI_LOG_LEVEL='ERROR')
        def run(argv,ok=True,stdin=None):
            p=subprocess.run(argv,cwd=root,env=env,text=True,input=stdin,capture_output=True,timeout=30)
            assert (p.returncode==0)==ok,(argv[1:3],p.returncode,p.stderr[-400:])
            return p
        assert run([a.jf,'--version']).stdout.strip()=='jf version 2.129.0'
        assert re.search(r'Version:\s+1\.3\.6(?:\s|$)',run([a.oras,'version']).stdout)
        curl=run(['curl','--help','all']).stdout
        for card in commands:
            words=shlex.split(card['name']);exe=a.jf if words[0]=='jf' else a.oras if words[0]=='oras' else None
            if not exe:continue
            p=run([exe,*words[1:],'--help']);helptext=p.stdout+p.stderr
            forms=[]
            for flag in card['flags']:
                for form in re.findall(r'(?<!\w)--?[A-Za-z][A-Za-z0-9-]*',flag['flag']):
                    text=curl if card['name']=='jf rt curl' and form!='--server-id' else helptext
                    assert re.search(r'(?<![A-Za-z0-9-])'+re.escape(form)+r'(?![A-Za-z0-9-])',text),(card['name'],form)
                    forms.append(form)
            for alias in card['aliases']:
                run([exe,*shlex.split(alias)[1:],'--help'])
            report['commands'].append({'name':card['name'],'selected_flag_forms':forms,'aliases_help_accepted':card['aliases']})
        run([a.jf,'config','add','unreachable','--url=http://127.0.0.1:1','--user=fixture','--access-token-stdin','--interactive=false'],stdin='dummy-not-a-secret')
        folder=root/'input/tree';folder.mkdir(parents=True);(folder/'item.txt').write_text('own candidate\n')
        flat=run([a.jf,'rt','upload','input/tree/item.txt','generic-candidates/test/','--server-id=unreachable','--dry-run','--flat=true','--fail-no-op=true','--detailed-summary'])
        tree=run([a.jf,'rt','upload','input/tree/item.txt','generic-candidates/test/','--server-id=unreachable','--dry-run','--flat=false','--fail-no-op=true','--detailed-summary'])
        flat_target=json.loads(flat.stdout)['files'][0]['target'].split('/artifactory/',1)[1]
        tree_target=json.loads(tree.stdout)['files'][0]['target'].split('/artifactory/',1)[1]
        assert flat_target=='generic-candidates/test/item.txt'
        assert tree_target=='generic-candidates/test/input/tree/item.txt'
        literal=run([a.jf,'rt','upload','input/tree/absent','generic-candidates/test/','--server-id=unreachable','--dry-run','--fail-no-op=true'],ok=False)
        assert literal.returncode==1
        # The no-op code is real and distinct from an HTTP or credential failure.
        missing=run([a.jf,'rt','upload','input/tree/missing*','generic-candidates/test/','--server-id=unreachable','--dry-run','--flat=true','--fail-no-op=true'],ok=False)
        assert missing.returncode==2,(missing.returncode,missing.stderr[-1000:],missing.stdout[-1000:])
        report['dry_run']={'same_input':'one authored file under input/tree','flat_true_exit':flat.returncode,'flat_false_exit':tree.returncode,
                          'flat_true_target':flat_target,'flat_false_target':tree_target,'literal_absent_exit':literal.returncode,'empty_glob_with_fail_no_op_exit':missing.returncode,'destination':'explicitly unreachable loopback port; no server acceptance'}
        for argv in [[a.jf,'--server-id=unreachable','rt','ping'],[a.jf,'rt','--server-id=unreachable','ping']]:run(argv,ok=False)
        report['bad_server_id_placement_rejected']=2
    report['commands_passed']=len(report['commands']);report['selected_flag_forms_checked']=sum(len(c['selected_flag_forms']) for c in report['commands'])
    data=json.dumps(report,ensure_ascii=False,indent=2)+'\n'
    if a.report:a.report.write_text(data)
    print(data)
if __name__=='__main__':main()
