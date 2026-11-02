#!/usr/bin/env python3
"""Небольшие опыты Linux: только собственные процессы и временные файлы."""
import argparse, ctypes, json, mmap, os, resource, select, signal, socket, stat, struct, sys, tempfile, time
from pathlib import Path

def line(k,v): print(f'{k}: {v}',flush=True)
def read_all(fd):
    out=[]
    while True:
        v=os.read(fd,4096)
        if not v: return b''.join(out)
        out.append(v)
def lab01():
    line('byteorder',sys.byteorder); line('pointer_bytes',struct.calcsize('P'));line('page_size',os.sysconf('SC_PAGE_SIZE'))
    line('integer_0x12345678_le',struct.pack('<I',0x12345678).hex(' '));line('integer_0x12345678_be',struct.pack('>I',0x12345678).hex(' '))
    a=ctypes.create_string_buffer(b'ABC');line('own_buffer_virtual_address',hex(ctypes.addressof(a)));line('own_buffer',a.raw.hex(' '))
def lab02():
    with tempfile.TemporaryDirectory(prefix='linux-book-') as d:
        f=os.open(str(Path(d)/'message'),os.O_CREAT|os.O_EXCL|os.O_RDWR,0o600)
        line('fd',f);line('written',os.write(f,b'Linux\n'));line('offset',os.lseek(f,0,os.SEEK_CUR));os.lseek(f,0,os.SEEK_SET);line('read',repr(os.read(f,99)));os.close(f)
def lab03():
    r,w=os.pipe();p=os.fork()
    if p==0:
        os.close(r);os.dup2(w,1);os.close(w)
        os.execve(sys.executable,[sys.executable,'-c','import os;print("child pid=%s token=%s"%(os.getpid(),os.environ["LAB_TOKEN"]))'],dict(os.environ,LAB_TOKEN='from-parent'))
    os.close(w);out=read_all(r);os.close(r);_,s=os.waitpid(p,0)
    line('parent_pid',os.getpid());line('fork_returned_child_pid',p);line('child_output',out.decode().strip());line('child_exit',os.waitstatus_to_exitcode(s))
def lab04():
    with tempfile.TemporaryDirectory(prefix='linux-book-') as d:
        p=Path(d)/'letters';p.write_bytes(b'ABCDEFGH');a=os.open(p,os.O_RDONLY);b=os.dup(a);c=os.open(p,os.O_RDONLY)
        line('a_reads',os.read(a,2).decode());line('dup_b_reads',os.read(b,2).decode());line('new_open_c_reads',os.read(c,2).decode());line('offsets',[os.lseek(i,0,os.SEEK_CUR) for i in [a,b,c]])
        for i in [a,b,c]: os.close(i)
def lab05():
    m=mmap.mmap(-1,mmap.PAGESIZE,flags=mmap.MAP_PRIVATE|mmap.MAP_ANONYMOUS);m[0:1]=b'A';r,w=os.pipe();p=os.fork()
    if p==0:
        os.close(r);m[0:1]=b'B';os.write(w,m[0:1]);os.close(w);os._exit(0)
    os.close(w);line('child_value',read_all(r).decode());os.close(r);os.waitpid(p,0);line('parent_value',m[0:1].decode());m.close()
def lab06():
    with tempfile.TemporaryDirectory(prefix='linux-book-') as d:
        a=Path(d)/'a';b=Path(d)/'b';s=Path(d)/'shortcut';a.write_bytes(b'old');os.link(a,b);s.symlink_to('a');fd=os.open(a,os.O_RDONLY)
        line('same_inode',a.stat().st_ino==b.stat().st_ino);line('hard_links_before',a.stat().st_nlink);a.unlink();line('hard_links_after',b.stat().st_nlink);line('symlink_target_exists',s.exists());b.unlink();line('open_after_unlink',os.read(fd,20).decode());line('fd_links',os.fstat(fd).st_nlink);os.close(fd)
def lab07():
    with tempfile.TemporaryDirectory(prefix='linux-book-') as d:
        q=Path(d);target=q/'config';tmp=q/'config.new';target.write_bytes(b'old\n');old=os.open(target,os.O_RDONLY)
        try:
            fd=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            try:
                data=memoryview(b'new\n');written=0
                while written<len(data):
                    progress=os.write(fd,data[written:])
                    if progress<=0: raise RuntimeError('write made no progress before publication')
                    written+=progress
                os.fsync(fd)
            finally: os.close(fd)
            os.replace(tmp,target)
            directory=os.open(q,os.O_RDONLY|os.O_DIRECTORY)
            try: os.fsync(directory)
            finally: os.close(directory)
            line('read_old_descriptor',os.read(old,99).decode().strip());line('read_new_path',target.read_text().strip())
        finally: os.close(old)
def lab08():
    with tempfile.TemporaryDirectory(prefix='linux-book-') as d:
        p=Path(d)/'private';saved=os.umask(0o027)
        try: f=os.open(p,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o666);os.close(f)
        finally: os.umask(saved)
        s=p.stat();line('requested_mode','0666');line('umask','0027');line('actual_mode',oct(stat.S_IMODE(s.st_mode)));line('owner_uid',s.st_uid);line('our_effective_uid',os.geteuid());line('groups',os.getgroups())
def lab09():
    r,w=os.pipe()
    try: p=os.fork()
    except BaseException:
        os.close(r);os.close(w);raise
    if p==0:
        os.close(r)
        try:
            signal.pthread_sigmask(signal.SIG_BLOCK,{signal.SIGUSR1})
            os.write(w,b'ready\n');v=signal.sigwait({signal.SIGUSR1})
            os.write(w,f'received={v}\n'.encode())
        except BaseException: os.close(w);os._exit(1)
        os.close(w);os._exit(0)
    os.close(w);reaped=False;deadline=time.monotonic()+5.0
    def receive_line(stage):
        buf=bytearray()
        while not buf.endswith(b'\n'):
            remaining=deadline-time.monotonic()
            if remaining<=0 or not select.select([r],[],[],remaining)[0]:
                raise TimeoutError(f'timeout waiting for {stage}')
            chunk=os.read(r,1)
            if not chunk: raise EOFError(f'EOF before complete {stage}: {bytes(buf)!r}')
            buf.extend(chunk)
            if len(buf)>64: raise RuntimeError(f'oversized {stage} marker')
        return bytes(buf)
    try:
        ready=receive_line('ready')
        if ready!=b'ready\n': raise RuntimeError(f'invalid ready marker: {ready!r}')
        line('child',ready.decode().strip());os.kill(p,signal.SIGUSR1)
        received=receive_line('received')
        if received!=f'received={signal.SIGUSR1}\n'.encode():
            raise RuntimeError(f'invalid received marker: {received!r}')
        line('child',received.decode().strip())
        while True:
            child,status=os.waitpid(p,os.WNOHANG)
            if child==p: reaped=True;break
            remaining=deadline-time.monotonic()
            if remaining<=0: raise TimeoutError('timeout waiting for own child exit')
            time.sleep(min(0.01,remaining))
        result=os.waitstatus_to_exitcode(status);line('exit',result)
        if result!=0: raise RuntimeError(f'own child failed: {result}')
    finally:
        os.close(r)
        if not reaped:
            try: os.kill(p,signal.SIGKILL)
            except ProcessLookupError: pass
            os.waitpid(p,0)
def lab10():
    r,w=os.pipe();p=os.fork()
    if p==0:
        os.close(r);os.write(w,b'one\ntwo\n');os.close(w);os._exit(0)
    os.close(w);data=read_all(r);os.close(r);os.waitpid(p,0);line('bytes_before_eof',repr(data));line('line_count',len(data.splitlines()))
def lab11():
    a,b=socket.socketpair();a.sendall(b'hello');a.shutdown(socket.SHUT_WR);parts=[]
    while True:
        v=b.recv(2)
        if not v: break
        parts.append(v.decode())
    line('recv_with_size_2',parts);line('complete_message',''.join(parts));a.close();b.close()
def lab12():
    r,w=os.pipe2(os.O_NONBLOCK|os.O_CLOEXEC);e=select.epoll();e.register(r,select.EPOLLIN);os.write(w,b'XYZ');line('ready_before',[(fd,ev) for fd,ev in e.poll(0)]);line('first_read',os.read(r,1).decode());line('ready_still',bool(e.poll(0)));line('remaining',os.read(r,99).decode())
    try: os.read(r,99)
    except BlockingIOError: line('empty_nonblocking_read','EAGAIN')
    os.close(w);line('after_writer_close',[(fd,ev) for fd,ev in e.poll(0)]);line('eof',repr(os.read(r,99)));e.close();os.close(r)
def lab13():
    wanted={'Name','State','Pid','PPid','Threads','VmSize','VmRSS','voluntary_ctxt_switches','nonvoluntary_ctxt_switches'}
    for linev in Path('/proc/self/status').read_text().splitlines():
        if linev.split(':',1)[0] in wanted: print(linev)
    line('own_cgroup',Path('/proc/self/cgroup').read_text().strip())
    for name in ['pid','mnt','net','user']:
        line('namespace_'+name,os.readlink('/proc/self/ns/'+name))
    for name in ['cpu','memory','io']:
        p=Path('/proc/pressure')/name
        if p.exists(): line('psi_'+name,p.read_text().strip().replace('\n',' | '))
def lab14():
    a=time.monotonic();b=time.process_time();v=0
    for i in range(500000): v=(v+i)%1000003
    line('calculation_check',v);line('work_elapsed_seconds',round(time.monotonic()-a,6));line('work_cpu_seconds',round(time.process_time()-b,6))
    a=time.monotonic();b=time.process_time();time.sleep(0.04);line('sleep_elapsed_seconds',round(time.monotonic()-a,6));line('sleep_cpu_seconds',round(time.process_time()-b,6))
LABS={f'{i:02d}':globals()[f'lab{i:02d}'] for i in range(1,15)}
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('number',choices=list(LABS)+['all']);a=p.parse_args()
    for n in LABS if a.number=='all' else [a.number]:
        print('\nОпыт '+n,flush=True);LABS[n]()
