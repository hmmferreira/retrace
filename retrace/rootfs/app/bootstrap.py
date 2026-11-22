"""Prepare private state, drop root, and start the explicitly selected runtime."""
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from retrace.private_data import prepare_private_root
from retrace.shared_runtime import read_options,configure_runtime,RuntimeBlocked,owned_session_available,publish_runtime_options


def main():
    os.umask(0o077)
    options=read_options()
    root=Path('/data/retrace')
    prepare_private_root(root,1000 if os.geteuid()==0 else None,1000)
    publish_runtime_options(root,options,uid=1000 if os.geteuid()==0 else None,gid=1000)
    if os.geteuid()==0:
        os.setgroups([]);os.setgid(1000);os.setuid(1000)
    os.environ['XDG_CONFIG_HOME']=str(root/'config')
    (root/'config').mkdir(exist_ok=True,mode=0o700)
    mode=configure_runtime(options)
    if mode=='legacy' and owned_session_available(root):
        raise RuntimeBlocked('owned_runtime_required')
    children=[]
    def stop(signum=None,frame=None,*,exit_code=0):
        for child in children:
            if child.poll() is None:child.terminate()
        for child in children:
            try:child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                child.kill();child.wait(timeout=5)
        raise SystemExit(exit_code)
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    if mode=='legacy':
        state=root/'anisette';state.mkdir(exist_ok=True,mode=0o700)
        children.append(subprocess.Popen(['/opt/anisette-v3-server','--host','127.0.0.1','--adi-path',str(root/'config'/'anisette-v3')],
            cwd=state,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
            env={key:os.environ[key] for key in ('PATH','LANG','LC_ALL','SSL_CERT_FILE','SSL_CERT_DIR','XDG_CONFIG_HOME') if key in os.environ}))
    children.append(subprocess.Popen([sys.executable,'-m','retrace.server']))
    while all(child.poll() is None for child in children):time.sleep(1)
    stop(exit_code=1)

if __name__=='__main__':
    try:main()
    except Exception as error:
        code=getattr(error,'code','startup_failed')
        if not isinstance(code,str) or len(code)>80 or not all(c.islower() or c=='_' for c in code):code='startup_failed'
        print('Retrace startup blocked: '+code,flush=True)
        raise SystemExit(1)
