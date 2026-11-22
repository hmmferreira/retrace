"""App-owned credential destinations and asynchronous HTTP; experimental only.

This constrains traffic using this transport. It is not a sandbox against
malicious Python code opening its own sockets; OS egress isolation is separate.
"""
import asyncio
import hashlib
import ipaddress
import json
import math
from pathlib import Path
import plistlib
import re
import socket
import ssl
from urllib.parse import urlsplit
import aiohttp
import certifi

class TransportBlocked(RuntimeError):
    """Codes contain no URL, headers, body or upstream exception text."""
    def __init__(self,code="destination_blocked"):
        super().__init__(code)
        self.code=code

class VerificationFailure(TransportBlocked):
    """Known factor HTTP refusal, without response text or verification inputs."""
    def __init__(self,stage,status):
        if stage not in ("request","submit") or status not in (400,401,403,429):
            raise TransportBlocked("request_failed")
        self.status=status
        self.stage=stage
        super().__init__("verification_rate_limited" if status==429 else
            "verification_not_accepted" if stage=="submit" else "verification_request_rejected")

VERIFICATION_ROUTES={
    ("PUT","/auth/verify/phone"):"request",
    ("GET","/auth/verify/trusteddevice"):"request",
    ("POST","/auth/verify/phone/securitycode"):"submit",
    ("GET","/grandslam/GsService2/validate"):"submit",
}

ACCOUNT_PATHS={
    "gsa.apple.com":frozenset({"/grandslam/GsService2","/grandslam/GsService2/validate","/auth","/auth/verify/phone","/auth/verify/phone/securitycode","/auth/verify/trusteddevice"}),
    "gsas.apple.com":frozenset({"/grandslam/GsService2/postdata"}),
    "setup.icloud.com":frozenset({"/setup/iosbuddy/loginDelegates"}),
    "gateway.icloud.com":frozenset({"/findmyservice/v2/fetch","/acsnservice/fetch"}),
}
CLOUDKIT_PATHS=frozenset({"/setup/setup/ck/v1/ckAppInit","/ckcoderouter/api/client/code/invoke"}|{
    "/ckdatabase/api/client/"+path for path in ("zone/retrieve","zone/sync","record/retrieve","record/sync")})
PROVISIONING_ROUTES=frozenset({
    ("GET","/grandslam/GsService2/lookup"),
    ("POST","/grandslam/MidService/startMachineProvisioning"),
    ("POST","/grandslam/MidService/finishMachineProvisioning"),
})
ARTIFACT_URL="https://apps.mzstatic.com/content/android-apple-music-apk/applemusic.apk"

ESCROW_PATHS=frozenset("/escrowproxy/api/"+path for path in ("get_records","get_club_cert","srp_init","recover"))

def validate_destination(profile,method,url):
    if profile not in ("account","cloudkit","escrow","provisioning","artifact","mac_artifact") or method not in ("GET","POST","PUT"):
        raise TransportBlocked()
    if not isinstance(url,str) or any(ord(c)<=32 or ord(c)>=127 for c in url) or any(c in url for c in "\\#"):
        raise TransportBlocked()
    try:
        parsed=urlsplit(url)
        host=parsed.hostname
        if (parsed.scheme!="https" or not host or parsed.username is not None or parsed.password is not None
                or parsed.port not in (None,443) or parsed.netloc.endswith(":")
                or "%" in parsed.netloc or "%" in parsed.path or parsed.fragment
                or ("?" in url and not parsed.query)):
            raise TransportBlocked()
        if parsed.query and not (profile=="cloudkit" and parsed.path=="/setup/setup/ck/v1/ckAppInit"
            and parsed.query in ("container=com.apple.icloud.searchparty","container=com.apple.security.keychain")):
            raise TransportBlocked()
        if profile=="mac_artifact":
            from .macos_artifact import URL
            allowed=method=="GET" and url==URL
        elif profile=="artifact":
            allowed=method=="GET" and url==ARTIFACT_URL
        elif profile=="account":
            allowed=parsed.path in ACCOUNT_PATHS.get(host,()) and (method!="PUT" or (host=="gsa.apple.com" and parsed.path=="/auth/verify/phone"))
        elif profile=="cloudkit":
            allowed=host=="gateway.icloud.com" and parsed.path in CLOUDKIT_PATHS and method=="POST"
        elif profile=="provisioning":
            allowed=host=="gsa.apple.com" and (method,parsed.path) in PROVISIONING_ROUTES
        else:
            allowed=bool(re.fullmatch(r"p[1-9][0-9]{0,4}-escrowproxy\.icloud\.com",host)) and parsed.path in ESCROW_PATHS and method=="POST"
        if not allowed: raise TransportBlocked()
    except (ValueError,AttributeError):
        raise TransportBlocked() from None
    return host

class PublicResolver(aiohttp.abc.AbstractResolver):
    def __init__(self):
        self._delegate=aiohttp.resolver.DefaultResolver()
    async def resolve(self,host,port=0,family=socket.AF_INET):
        values=await self._delegate.resolve(host,port,family)
        try:
            if not values or any(not ipaddress.ip_address(value["host"]).is_global for value in values):
                raise TransportBlocked("dns_destination_blocked")
        except ValueError:
            raise TransportBlocked("dns_destination_blocked") from None
        return values
    async def close(self):
        await self._delegate.close()

def trust_context():
    root=Path(__file__).with_name("trust")/"apple-root-ca.pem"
    try:
        pem=root.read_text()
        fingerprint=hashlib.sha256(ssl.PEM_cert_to_DER_cert(pem)).hexdigest()
    except (OSError,ValueError):
        raise TransportBlocked("trust_store_invalid") from None
    if fingerprint!="b0b1730ecbc7ff4505142c49f1295e6eda6bcaed7e2c68c5be91b5a11001f024":
        raise TransportBlocked("trust_store_invalid")
    context=ssl.create_default_context(cafile=certifi.where())
    context.minimum_version=ssl.TLSVersion.TLSv1_2
    context.load_verify_locations(cadata=pem)
    return context

class Response:
    __slots__=("status_code","_body","headers")
    def __init__(self,status,body,headers):
        self.status_code,self._body,self.headers=status,body,headers
    @property
    def content(self): return self._body
    @property
    def ok(self): return 200<=self.status_code<300
    def text(self): return self._body.decode("utf-8")
    def json(self): return json.loads(self._body)
    def plist(self):
        # No external DTD/entity loading; fail rather than expand entities.
        if b"<!ENTITY" in self._body.upper(): raise TransportBlocked("response_invalid")
        value=plistlib.loads(self._body)
        if not isinstance(value,dict): raise TransportBlocked("response_invalid")
        return value
    def __repr__(self): return "<AppleResponse redacted>"

class OwnedHttpSession:
    MAX_BODY=8*1024*1024
    def __init__(self,*,profile="account",timeout=30,verify_tls=True):
        if profile not in ("account","cloudkit","escrow","provisioning","artifact","mac_artifact") or verify_tls is not True:
            raise TransportBlocked("transport_options_blocked")
        if not isinstance(timeout,(int,float)) or isinstance(timeout,bool) or not math.isfinite(timeout) or not 0<timeout<=90:
            raise TransportBlocked("transport_options_blocked")
        self.profile,self.timeout=profile,timeout
        self._ssl=trust_context()
        self._sessions={}
        self._resolvers=[]
        self._closed=False
    async def _session(self,host):
        if host not in self._sessions:
            resolver=PublicResolver()
            self._resolvers.append(resolver)
            connector=aiohttp.TCPConnector(resolver=resolver,force_close=host=="gsa.apple.com")
            self._sessions[host]=aiohttp.ClientSession(connector=connector,
                timeout=aiohttp.ClientTimeout(total=self.timeout),trust_env=False,
                cookie_jar=aiohttp.DummyCookieJar())
        return self._sessions[host]
    async def request(self,method,url,**kwargs):
        if self.profile=="artifact":raise TransportBlocked("artifact_stream_required")
        if self._closed: raise TransportBlocked("transport_closed")
        host=validate_destination(self.profile,method,url)
        if set(kwargs)-{"auth","headers","data","json","auto_retry"}:
            raise TransportBlocked("transport_options_blocked")
        if self.profile=='mac_artifact':
            from .macos_artifact import OFFSET,LENGTH
            if set(kwargs)!={'headers'} or kwargs['headers']!={'Range':f'bytes={OFFSET}-{OFFSET+LENGTH-1}','Accept-Encoding':'identity'}:
                raise TransportBlocked('transport_options_blocked')
        headers=kwargs.get("headers") or {}
        if not hasattr(headers,"items") or any(
            not isinstance(key,str) or not re.fullmatch(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+",key)
            or key.lower() in ("host","proxy-authorization","proxy-connection")
            or not isinstance(value,str) or any(c in value for c in "\r\n\x00")
            for key,value in headers.items()):
            raise TransportBlocked("transport_options_blocked")
        # No invisible retries of authentication or device-passcode exchanges.
        kwargs.pop("auto_retry",None)
        auth=kwargs.get("auth")
        if isinstance(auth,tuple):
            try: kwargs["auth"]=aiohttp.BasicAuth(*auth)
            except (TypeError,ValueError):
                raise TransportBlocked("transport_options_blocked") from None
        try:
            session=await self._session(host)
            async with session.request(method,url,allow_redirects=False,ssl=self._ssl,**kwargs) as response:
                if 300<=response.status<400: raise TransportBlocked("redirect_blocked")
                stage=VERIFICATION_ROUTES.get((method,urlsplit(url).path)) if self.profile=="account" and host=="gsa.apple.com" else None
                if stage is not None and response.status in (400,401,403,429):
                    raise VerificationFailure(stage,response.status)
                body=bytearray()
                async for chunk in response.content.iter_chunked(65536):
                    if len(body)+len(chunk)>self.MAX_BODY: raise TransportBlocked("response_too_large")
                    body.extend(chunk)
                return Response(response.status,bytes(body),dict(response.headers))
        except (aiohttp.ClientError,TimeoutError,OSError,ValueError,TypeError):
            raise TransportBlocked("request_failed") from None
    async def artifact_chunks(self,url,*,max_bytes):
        """Unauthenticated bounded vendor stream; account response limits unchanged."""
        if self._closed:raise TransportBlocked("transport_closed")
        if self.profile!="artifact" or type(max_bytes) is not int or not 0<max_bytes<=200*1024*1024:
            raise TransportBlocked("transport_options_blocked")
        host=validate_destination("artifact","GET",url)
        try:
            session=await self._session(host)
            async with session.request("GET",url,allow_redirects=False,ssl=self._ssl,auto_decompress=False,
                headers={"Accept":"application/vnd.android.package-archive","Accept-Encoding":"identity"}) as response:
                if 300<=response.status<400:raise TransportBlocked("redirect_blocked")
                if response.status!=200:raise TransportBlocked("artifact_download_failed")
                if response.headers.get("Content-Encoding","identity").lower()!="identity":
                    raise TransportBlocked("artifact_encoding_blocked")
                length=response.headers.get("Content-Length")
                if length is not None and (not length.isdecimal() or not 0<int(length)<=max_bytes):
                    raise TransportBlocked("response_too_large")
                received=0
                async for chunk in response.content.iter_chunked(65536):
                    received+=len(chunk)
                    if received>max_bytes:raise TransportBlocked("response_too_large")
                    yield chunk
                if received==0:raise TransportBlocked("artifact_download_failed")
        except (aiohttp.ClientError,TimeoutError,OSError,ValueError,TypeError):
            raise TransportBlocked("artifact_download_failed") from None

    async def get(self,url,**kwargs): return await self.request("GET",url,**kwargs)
    async def post(self,url,**kwargs): return await self.request("POST",url,**kwargs)
    async def close(self):
        self._closed=True
        sessions,self._sessions=self._sessions,{}
        await asyncio.gather(*(value.close() for value in sessions.values()),return_exceptions=True)
        resolvers,self._resolvers=self._resolvers,[]
        await asyncio.gather(*(value.close() for value in resolvers),return_exceptions=True)
