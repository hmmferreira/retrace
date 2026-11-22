"""Private worker entry point. Native stdout/stderr are never a control channel."""
import base64
from io import BytesIO
import json
import os
from pathlib import Path
import struct
import sys
import sysconfig

MAX_REQUEST=128*1024*1024
MAX_REPLY=24*1024*1024
MAX_ARTIFACT=64*1024*1024
MAX_STATE=16*1024*1024
MAX_FIELD=1024*1024


def _binary(value,limit):
    if not isinstance(value,str) or not 0<len(value)<=4*((limit+2)//3):raise ValueError()
    result=base64.b64decode(value,validate=True)
    if not 0<len(result)<=limit:raise ValueError()
    return result

def _encoded(value):return base64.b64encode(value).decode("ascii")

def _read():
    header=sys.stdin.buffer.read(4)
    if not header:return None
    if len(header)!=4:raise ValueError()
    size=struct.unpack("!I",header)[0]
    if not 0<size<=MAX_REQUEST:raise ValueError()
    body=sys.stdin.buffer.read(size)
    if len(body)!=size:raise ValueError()
    value=json.loads(body)
    if not isinstance(value,dict):raise ValueError()
    return value

def main():
    control=int(sys.argv[1])
    output=os.fdopen(control,"wb",buffering=0)
    def send(value):
        data=json.dumps(value,separators=(",",":")).encode()
        if not 0<len(data)<=MAX_REPLY:raise ValueError()
        output.write(struct.pack("!I",len(data)));output.write(data)
    try:
        # -I -S omits environment paths, user site and executable .pth files.
        code=Path(__file__).resolve().parent
        public=[code,"/lib","/lib64","/usr/lib","/usr/local/lib","/etc/ld.so.cache","/etc/localtime","/dev/urandom"]
        for key in ("stdlib","platstdlib","purelib","platlib"):
            value=sysconfig.get_paths().get(key)
            if value:
                public.append(value)
                if value not in sys.path:sys.path.append(value)
        sys.path.insert(0,str(code))
        from native_sandbox import restrict_worker
        boundary=restrict_worker(public)
        send({"ok":True,"ready":True,"boundary":boundary})
    except BaseException:
        send({"ok":False,"error":"worker_boundary_unavailable"})
        return
    # No third-party implementation imports, native loads or input processing
    # happen until the OS boundary above is successfully active.
    provider=None;engine=None;session=None;mode=None;phase="new"
    try:
        while True:
            request=_read()
            if request is None:return
            command=request.get("command")
            if command=="mac_prepare" and phase=="new":
                from macos_child import create
                engine=create(_binary(request.get("artifact"),MAX_ARTIFACT),request.get("host_uuid"),request.get("saved"))
                phase="mac"
                send({"ok":True,"phase":engine.phase})
            elif command=="mac_begin" and phase=="mac":
                cpim=engine.begin(_binary(request.get("spim"),MAX_FIELD),consent=request.get("consent"))
                send({"ok":True,"cpim":_encoded(cpim)})
            elif command=="mac_finish" and phase=="mac":
                saved=engine.finish(_binary(request.get("ptm"),MAX_FIELD),_binary(request.get("tk"),MAX_FIELD),request.get("routing"))
                send({"ok":True,"saved":saved});return
            elif command=="mac_headers" and phase=="mac":
                headers,saved=engine.headers()
                send({"ok":True,"headers":headers,"saved":saved});return
            elif command=="prepare" and phase=="new":
                from anisette import Anisette
                from anisette._ani_provider import AnisetteProvider
                class NoProvisioning:
                    adi=None
                    def provision(self,*args,**kwargs):raise RuntimeError()
                def no_download():raise RuntimeError()
                libraries=_binary(request.get("artifact"),MAX_ARTIFACT)
                mode=request.get("mode")
                files=[BytesIO(libraries)]
                if mode=="signing":files.insert(0,BytesIO(_binary(request.get("state"),MAX_STATE)))
                elif mode!="provisioning":raise ValueError()
                config=None
                if request.get("device") is not None:
                    device=request["device"]
                    if mode!="provisioning" or not isinstance(device,dict) or set(device)!={"uid","devid","client_info"} or any(
                        not isinstance(value,str) or not value or len(value)>1024
                        or any(ord(c)<32 or ord(c)>126 for c in value) for value in device.values()):raise ValueError()
                    from anisette._device import AnisetteDeviceConfig
                    config=AnisetteDeviceConfig.default()
                    config.unique_device_id=device["devid"].upper()
                    config.local_user_uuid=device["uid"]
                    config.server_friendly_description=device["client_info"]
                provider=AnisetteProvider.load(*files,fs_fallback=no_download,default_device_config=config)
                provider._provisioning_session=NoProvisioning()
                engine=Anisette(provider)
                if mode=="signing":
                    if not engine.is_provisioned:raise ValueError()
                    send({"ok":True,"state":snapshot(provider)})
                    phase="signing"
                else:
                    if engine.is_provisioned:raise ValueError()
                    device=provider.device
                    send({"ok":True,"identity":{"X-Mme-Device-Id":device.unique_device_identifier,
                        "X-MMe-Client-Info":device.server_friendly_description,"X-Apple-I-MD-LU":base64.b64encode(device.local_user_uuid.encode()).decode("ascii")}})
                    phase="prepared"
            elif command=="begin" and phase=="prepared":
                session=provider.adi.start_provisioning((1<<64)-2,_binary(request.get("spim"),MAX_FIELD))
                send({"ok":True,"cpim":_encoded(bytes(session.cpim))});phase="begun"
            elif command=="finish" and phase=="begun":
                provider.adi.end_provisioning(session.session,_binary(request.get("ptm"),MAX_FIELD),_binary(request.get("tk"),MAX_FIELD))
                if not engine.is_provisioned:raise ValueError()
                send({"ok":True,"state":snapshot(provider)});return
            elif command=="identity_check" and phase=="signing":
                expected=request.get("expected")
                if not isinstance(expected,dict) or set(expected)!={"uid","devid","client_info"} or any(
                    not isinstance(v,str) or not v or len(v)>1024 or any(ord(c)<32 or ord(c)>126 for c in v)
                    for v in expected.values()):raise ValueError()
                device=provider.device
                send({"ok":True,"checks":{
                    "device_id_matches":device.unique_device_identifier==expected["devid"].upper(),
                    "local_user_matches":device.local_user_uuid==expected["uid"],
                    "client_info_matches":device.server_friendly_description==expected["client_info"]}})
            elif command=="headers" and phase=="signing":
                if not engine.is_provisioned:raise ValueError()
                headers=engine.get_data()
                send({"ok":True,"headers":{key:headers[key] for key in ("X-Apple-I-MD","X-Apple-I-MD-M")},"state":snapshot(provider)})
            else:raise ValueError()
    except BaseException as error:
        # Fixed public component labels and line numbers only; no exception prose.
        detail={}
        frame=error.__traceback__
        allowed={'macos_child.py','macos_memory.py','adi_run.py','harness.py','stubs.py','macho.py'}
        while frame is not None:
            name=Path(frame.tb_frame.f_code.co_filename).name
            if name in allowed:detail={'component':name,'line':frame.tb_lineno}
            frame=frame.tb_next
        try:send({"ok":False,"error":"native_worker_failed",**detail})
        except BaseException:pass

def snapshot(provider):
    value=BytesIO();provider.save(value,exclude=["libs"])
    state=value.getvalue()
    if not 0<len(state)<=MAX_STATE:raise ValueError()
    return _encoded(state)

if __name__=="__main__":main()
