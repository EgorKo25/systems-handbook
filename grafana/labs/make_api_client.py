#!/usr/bin/env python3
"""Create private curl header config from a token read without echo or argv/history."""
import argparse,getpass,json,os
from pathlib import Path
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('private_directory',type=Path);a=p.parse_args();directory=a.private_directory.resolve()
 if not directory.is_dir():p.error('initialize your private persistent lab first')
 if directory.stat().st_mode & 0o077:p.error('private directory must have no group/other permission bits')
 token=getpass.getpass('Service account token (hidden): ')
 if not token or not token.isascii() or any(c.isspace() or ord(c)<33 or ord(c)==127 for c in token):p.error('expected nonempty ASCII token without whitespace/control characters')
 path=directory/'api.curl'
 fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
 with os.fdopen(fd,'w') as f:f.write('header = '+json.dumps('Authorization: Bearer '+token)+'\n')
 print('Created private/api.curl with mode0600; token was not printed. Existing file is never overwritten.')
