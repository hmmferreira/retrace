"""Pinned report-child startup; no inherited SDK paths or credential environment."""
import os
from pathlib import Path
import sys
from .shared_runtime import read_options,require_shared_backend,RuntimeBlocked

_SHARED_ENTRY="""import os,sys
from pathlib import Path
sys.path[:0]=['/opt/retrace-protocol','/app']
from retrace.shared_runtime import read_options,configure_runtime
options=read_options(Path(os.environ['RETRACE_DATA'])/'runtime-options.json')
if options['runtime_mode']!='shared':raise RuntimeError('shared_runtime_required')
configure_runtime(options)
from retrace.poll_item import main
main()
"""

def report_launch(root):
    env={key:os.environ[key] for key in ('PATH','LANG','LC_ALL','SSL_CERT_FILE','SSL_CERT_DIR','XDG_CONFIG_HOME') if key in os.environ}
    env['RETRACE_DATA']=str(root)
    mode=os.environ.get('RETRACE_RUNTIME_MODE','legacy')
    marker=Path(__file__).with_name('shared_backend.json')
    if mode=='shared':
        options=read_options(Path(root)/'runtime-options.json')
        if options['runtime_mode']!='shared':raise RuntimeBlocked('shared_runtime_required')
        require_shared_backend()
        # Explicit immutable paths select the pinned candidate; -I rejects any
        # arbitrary PYTHONPATH/user-site supplied to the outer web process.
        command=[sys.executable,'-I','-c',_SHARED_ENTRY]
        env['RETRACE_RUNTIME_MODE']='shared'
        env['RETRACE_PRIVATE_EVALUATION']='1' if options['private_evaluation'] else '0'
        env.pop('SSL_CERT_FILE',None);env.pop('SSL_CERT_DIR',None)
    elif mode=='legacy' and not marker.exists():
        command=[sys.executable,'-m','retrace.poll_item']
    else:raise RuntimeBlocked('shared_runtime_required')
    return command,env
