"""Fixed private-evaluation Apple artifact. No account headers, alternate URL or redirects."""
import asyncio
import gzip
import hashlib
from io import BytesIO
import struct
from .apple_transport import OwnedHttpSession,TransportBlocked
from .private_session_store import _private_bytes,_write_new

URL='https://secure-appldnld.apple.com/itunes12/041-56365-20210413-79A5AC6D-6B0A-46EC-B399-5A381183E3BE/iTunes12.8.3.dmg'
OFFSET=184678769
LENGTH=3471595
PAYLOAD_SHA='8a6c068c95036326eb2d2885fa60912ed0f7229d0939ae92934a70a3bb6cf025'
LIBRARY_SHA='2eafc3c79c7f41a8afbfbeaaf23ee5dab5ad5bda55ec8e54dbc0ddf1d20ce630'
MEMBER='System/Library/PrivateFrameworks/CoreADI.framework/Versions/A/CoreADI'

def extract(payload):
    if len(payload)!=LENGTH or hashlib.sha256(payload).hexdigest()!=PAYLOAD_SHA:
        raise TransportBlocked('artifact_source_digest_mismatch')
    with gzip.GzipFile(fileobj=BytesIO(payload)) as gz:data=gz.read(32*1024*1024+1)
    if len(data)>32*1024*1024:raise TransportBlocked('artifact_source_too_large')
    pos=0;fat=None
    while pos+76<=len(data):
        h=data[pos:pos+76]
        if h[:6]!=b'070707':raise TransportBlocked('artifact_source_invalid')
        names=int(h[59:65],8);size=int(h[65:76],8)
        start=pos+76;end=start+names;stop=end+size
        if not 0<names<=4096 or size<0 or stop>len(data) or data[end-1]!=0:raise TransportBlocked('artifact_source_invalid')
        name=data[start:end-1].decode('utf-8').removeprefix('./')
        if name==MEMBER and size:
            if fat is not None:raise TransportBlocked('artifact_source_invalid')
            fat=data[end:stop]
        pos=stop
        if name=='TRAILER!!!':break
    if fat is None or fat[:4]!=b'\xca\xfe\xba\xbe':raise TransportBlocked('artifact_source_invalid')
    count=struct.unpack_from('>I',fat,4)[0]
    if not 0<count<=16 or 8+count*20>len(fat):raise TransportBlocked('artifact_source_invalid')
    slices=[]
    for n in range(count):
        cpu,sub,offset,size,align=struct.unpack_from('>IIIII',fat,8+n*20)
        if cpu==0x01000007:
            if not 0<size<=16*1024*1024 or offset+size>len(fat):raise TransportBlocked('artifact_source_invalid')
            slices.append(fat[offset:offset+size])
    if len(slices)!=1 or hashlib.sha256(slices[0]).hexdigest()!=LIBRARY_SHA:
        raise TransportBlocked('artifact_digest_mismatch')
    return slices[0]

async def ensure(path,*,private_evaluation=False,local_consent=False):
    if private_evaluation is not True and local_consent is not True:raise TransportBlocked('native_consent_required')
    if path.exists() or path.is_symlink():
        value=await asyncio.to_thread(_private_bytes,path,16*1024*1024)
        if hashlib.sha256(value).hexdigest()!=LIBRARY_SHA:raise TransportBlocked('artifact_digest_mismatch')
        return
    http=OwnedHttpSession(profile='mac_artifact',timeout=60)
    try:
        response=await http.request('GET',URL,headers={'Range':f'bytes={OFFSET}-{OFFSET+LENGTH-1}','Accept-Encoding':'identity'})
        import re
        headers={key.lower():value for key,value in response.headers.items()}
        if headers.get('content-encoding','identity').lower()!='identity':raise TransportBlocked('artifact_encoding_blocked')
        content_range=headers.get('content-range','')
        match=re.fullmatch(f'bytes {OFFSET}-{OFFSET+LENGTH-1}/([0-9]+)',content_range)
        if response.status_code!=206 or match is None or int(match[1])<OFFSET+LENGTH:
            raise TransportBlocked('artifact_range_invalid')
        library=await asyncio.to_thread(extract,response.content)
        await asyncio.to_thread(_write_new,path,library)
    finally:await http.close()
