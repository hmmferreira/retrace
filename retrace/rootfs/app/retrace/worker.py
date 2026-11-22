"""Single-flight polling; passwords discarded after authentication."""
import asyncio
from datetime import datetime, timezone, timedelta
import math
import os
import sys
import json
import time
from .storage import atomic_json, read_json, token_only
from .progress import safe_progress


AUTH_ERRORS={"authentication_failed","authentication_network_error","verification_rejected",
    "verification_not_accepted","verification_rate_limited","code_request_failed",
    "invalid_verification_code","session_save_failed","discovery_handoff_failed",
    "setup_required","sign_in_expired","apple_signin_refused","credentials_rejected",
    "authentication_protocol_error","authentication_state_error"}

class AuthenticationError(RuntimeError):
    """Stable public code only; never keep the underlying SDK exception/message."""
    def __init__(self,code,stage,*,retry_factor=False):
        self.code=code if code in AUTH_ERRORS else "authentication_failed"
        self.stage=stage
        self.retry_factor=retry_factor
        super().__init__(self.code)

def _auth_classification(error,stage):
    from .apple_transport import TransportBlocked,VerificationFailure
    if stage=="session_save":return "session_save_failed",False,"storage"
    if stage=="discovery_handoff":return "discovery_handoff_failed",False,"handoff"
    if isinstance(error,VerificationFailure):
        code=("verification_rate_limited" if error.status==429 else
              "verification_not_accepted" if error.stage=="submit" else "code_request_failed")
        return code,True,"verification_refused"
    # Some SDKs expose an explicit invalid-code type. The currently pinned one
    # does not; never infer a wrong code by matching an exception's prose/name.
    from findmy import errors as sdk_errors
    invalid_types=tuple(value for name in ("InvalidCodeError","InvalidVerificationCodeError")
        if isinstance((value:=getattr(sdk_errors,name,None)),type) and issubclass(value,Exception))
    if invalid_types and isinstance(error,invalid_types):
        return "invalid_verification_code",True,"verification_code_rejected"
    if isinstance(error,TransportBlocked):
        if error.code=="request_failed":return "authentication_network_error",False,"network"
        setup={"artifact_unavailable","artifact_digest_mismatch","artifact_review_required","reviewed_artifact_required",
            "isolated_provisioning_worker_required","worker_boundary_unavailable","explicit_new_identity_required",
            "signing_identity_missing","signing_identity_invalid"}
        if error.code in setup:return "setup_required",False,"setup"
        return ("code_request_failed" if stage=="2fa_request" else "verification_rejected" if stage=="2fa_submit" else "authentication_failed"),False,"transport_blocked"
    import aiohttp
    if isinstance(error,(TimeoutError,OSError,aiohttp.ClientError)):
        return "authentication_network_error",False,"network"
    unavailable=getattr(sdk_errors,"AppleServiceUnavailableError",None)
    if isinstance(unavailable,type) and isinstance(error,unavailable):
        return "verification_rate_limited" if getattr(error,"status_code",None)==429 else "authentication_network_error",False,"service_unavailable"
    refused=getattr(sdk_errors,"GrandSlamRefusedError",None)
    if isinstance(refused,type) and isinstance(error,refused):
        if getattr(error,"step",None)=="init":return "apple_signin_refused",False,"apple_refused"
        if getattr(error,"step",None)=="complete":return "credentials_rejected",False,"credentials_refused"
        return "authentication_protocol_error",False,"protocol"
    for name,code,kind in (("InvalidCredentialsError","credentials_rejected","credentials_refused"),
                           ("UnhandledProtocolError","authentication_protocol_error","protocol"),
                           ("InvalidStateError","authentication_state_error","state")):
        cls=getattr(sdk_errors,name,None)
        if isinstance(cls,type) and isinstance(error,cls):
            # A factor refusal must not be presented as a wrong account password.
            if name in {"InvalidCredentialsError","UnhandledProtocolError"} and stage in {"2fa_request","2fa_submit"}:
                code="code_request_failed" if stage=="2fa_request" else "verification_rejected"
            return code,False,kind
    code=getattr(error,"code",None)
    if isinstance(code,str) and code in {"artifact_unavailable","artifact_digest_mismatch","artifact_review_required","reviewed_artifact_required",
                "isolated_provisioning_worker_required","worker_boundary_unavailable","explicit_new_identity_required",
                "native_consent_required","native_consent_invalid","signing_identity_missing","signing_identity_invalid","native_worker_failed","signing_failed","provisioning_failed","provisioning_request_failed","provisioning_endpoints_changed","provisioning_timeout"}:
        return "setup_required",False,"setup"
    return ("verification_rejected" if stage=="2fa_submit" else "code_request_failed" if stage=="2fa_request" else "authentication_failed"),False,"unclassified"

class AppleWorker:
    def __init__(self, store, *, account_factory=None, session_writer=None, authenticated=None, session_available=None):
        self.store = store
        self.account_factory=account_factory
        self.session_writer=session_writer
        self.authenticated=authenticated
        self.session_available=session_available or (lambda:read_json(self.store.root/"account.json") is not None)
        self.lock = asyncio.Lock()
        self.poll_lock = asyncio.Lock()
        self.pending = None
        self.owner = None
        self.methods = []
        self.auth_task = None
        self.failures = 0
        self.wake = asyncio.Event()
        self.last_attempt = None
        self.query_slots = asyncio.Semaphore(self.CONCURRENCY)
        self.inventory_busy=False
        self.active_items = set()
        self.item_attempts = {}
        self.manual_tasks = {}

    def request_poll(self):
        self.wake.set()

    def _session(self, account):
        atomic_json(self.store.root / "account.json", token_only(account))

    @staticmethod
    def _method_kind(method):
        from findmy.reports.twofactor import SmsSecondFactorMethod,TrustedDeviceSecondFactorMethod
        if isinstance(method,SmsSecondFactorMethod):return "sms"
        if isinstance(method,TrustedDeviceSecondFactorMethod):return "trusted_device"
        return "unknown"

    def _method_choices(self):
        return [{"value":n,"label":"SMS" if self._method_kind(method)=="sms" else
                 "Trusted device" if self._method_kind(method)=="trusted_device" else "Verification method"}
                for n,method in enumerate(self.methods)]

    @staticmethod
    def _auth_event(stage,event,*,method=None,error=None,kind=None,status=None,reason=None,step=None,apple_step=None,apple_code=None,fault=None,component=None,line=None,provider=None):
        if stage not in {"login","2fa_request","2fa_submit","session_save","discovery_handoff"}:return
        if event not in {"started","completed","failed","cancelled"}:return
        value={"stage":stage,"event":event}
        if isinstance(provider,str) and provider in {"apple_music","macos"}:value["provider"]=provider
        if isinstance(method,str) and method in {"sms","trusted_device","unknown"}:value["method"]=method
        if isinstance(error,str) and error in AUTH_ERRORS:value["error"]=error
        if isinstance(kind,str) and kind in {"storage","handoff","verification_refused","verification_code_rejected","network","setup","transport_blocked","service_unavailable","unclassified","apple_refused","credentials_refused","protocol","state"}:value["kind"]=kind
        if type(status) is int and status in {400,401,403,429,500,502,503,504}:value["status"]=status
        if isinstance(reason,str) and reason in {"destination_blocked","request_failed","transport_closed","transport_options_blocked",
                       "dns_destination_blocked","redirect_blocked","response_invalid","response_too_large",
                       "explicit_new_identity_required","signing_identity_missing","signing_identity_invalid",
                       "artifact_unavailable","artifact_digest_mismatch","artifact_review_required","reviewed_artifact_required",
                       "isolated_provisioning_worker_required","worker_boundary_unavailable"}:value["reason"]=reason
        if isinstance(step,str) and step in {"account_setup","apple_signin","verification_methods"}:value["step"]=step
        if isinstance(apple_step,str) and apple_step in {"init","complete"}:value["apple_step"]=apple_step
        if type(apple_code) is int and -1000000<=apple_code<=1000000:value["apple_code"]=apple_code
        if isinstance(fault,str) and fault in {"attribute_error","type_error","key_error","value_error","runtime_error","other"}:value["fault"]=fault
        if isinstance(component,str) and component in {"account_protocol","account_factory","owned_transport","offline_signer","native_worker","worker"}:
            value["component"]=component
            if type(line) is int and 0<line<100000:value["line"]=line
        # Bounded structured print deliberately survives global SDK logging disable.
        # No caller can supply owner/email/phone/code/token, body or exception text.
        print("Retrace auth: "+json.dumps(value,separators=(",",":")),flush=True)

    async def _auth_step(self,stage,operation,*,method=None,context=None):
        self._auth_event(stage,"started",method=method,provider=context.get("provider") if isinstance(context,dict) else None)
        try:result=await operation()
        except asyncio.CancelledError:
            self._auth_event(stage,"cancelled",method=method)
            raise
        except Exception as error:
            code,retry,kind=_auth_classification(error,stage)
            details={}
            from findmy import errors as sdk_errors
            refused=getattr(sdk_errors,"GrandSlamRefusedError",None)
            if isinstance(refused,type) and isinstance(error,refused):
                details={"apple_step":getattr(error,"step",None),"apple_code":getattr(error,"ec",None)}
            if kind in {"unclassified","protocol","state"}:
                details["fault"]=next((label for cls,label in ((AttributeError,"attribute_error"),(TypeError,"type_error"),(KeyError,"key_error"),(ValueError,"value_error"),(RuntimeError,"runtime_error")) if isinstance(error,cls)),"other")
                origins={"findmy.reports.account":"account_protocol","retrace.shared_runtime":"account_factory",
                         "retrace.owned_protocol":"account_factory","retrace.apple_transport":"owned_transport",
                         "retrace.offline_signer":"offline_signer","retrace.native_worker":"native_worker","retrace.worker":"worker"}
                frame=error.__traceback__
                while frame is not None:
                    origin=origins.get(frame.tb_frame.f_globals.get("__name__"))
                    if origin:details.update(component=origin,line=frame.tb_lineno)
                    frame=frame.tb_next
            self._auth_event(stage,"failed",method=method,error=code,kind=kind,
                status=getattr(error,"status",getattr(error,"status_code",None)),reason=getattr(error,"code",None),
                step=context.get("step") if isinstance(context,dict) else None,**details)
            raise AuthenticationError(code,stage,retry_factor=retry) from None
        self._auth_event(stage,"completed",method=method)
        return result

    async def _complete_signin(self,*,method=None):
        account=self.pending
        async def save():
            if self.session_writer is None:await asyncio.to_thread(self._session,account)
            else:await self.session_writer(account)
        await self._auth_step("session_save",save,method=method)
        if self.authenticated is not None:
            await self._auth_step("discovery_handoff",lambda:self.authenticated(self.owner,account),method=method)
            # The callback explicitly takes ownership until discovery completes.
            self.pending=None
        await self._clear_pending()
        self.store.health["status"]="ready"
        self.request_poll()
        return {"phase":"complete"}

    async def _clear_pending(self):
        account=self.pending
        self.pending, self.owner, self.methods = None, None, []
        if account is not None:
            if hasattr(account,"_password"):account._password=None
            try:
                async with asyncio.timeout(10):await account.close()
            except Exception:pass
        if self.auth_task and self.auth_task is not asyncio.current_task():
            self.auth_task.cancel()
        self.auth_task = None

    async def _expire(self):
        await asyncio.sleep(600)
        async with self.lock:
            await self._clear_pending()

    async def login(self, owner, email, password, *, provider=None,native_consent=False):
        from findmy import AsyncAppleAccount, LocalAnisetteProvider, LoginState
        async with self.lock:
            if self.pending:
                raise ValueError("Finish or cancel the current sign-in")
            context={"step":"account_setup","provider":provider or "apple_music"}
            async def start():
                async with asyncio.timeout(90):
                    account = (await self.account_factory(provider,**({"native_consent":True} if native_consent else {})) if provider is not None and self.account_factory is not None else
                               await self.account_factory() if self.account_factory is not None else
                               AsyncAppleAccount(LocalAnisetteProvider(libs_path=str(self.store.root / "ani_libs.bin"))))
                self.pending, self.owner = account, owner
                self.auth_task = asyncio.create_task(self._expire())
                async with asyncio.timeout(90):
                    context["step"]="apple_signin"
                    state=await account.login(email,password)
                    if state==LoginState.REQUIRE_2FA:
                        context["step"]="verification_methods"
                        self.methods=list(await account.get_2fa_methods())
                        return {"phase":"choose_method","methods":self._method_choices()}
                    if state!=LoginState.LOGGED_IN:raise ValueError("Authentication incomplete")
                    return None
            try:
                result=await self._auth_step("login",start,context=context)
                return result if result is not None else await self._complete_signin()
            except BaseException:
                await self._clear_pending()
                raise

    async def factor(self, owner, index, code=None):
        from findmy import LoginState
        stage="2fa_request" if code is None else "2fa_submit"
        async with self.lock:
            if not self.pending or self.owner!=owner:
                raise AuthenticationError("sign_in_expired",stage)
            if type(index) is not int or index<0 or index>=len(self.methods):
                raise ValueError("Invalid verification method")
            method=self.methods[index];kind=self._method_kind(method)
            try:
                async def verify():
                    async with asyncio.timeout(90):
                        if code is None:await method.request()
                        else:
                            await method.submit(code)
                            if self.pending.login_state!=LoginState.LOGGED_IN:
                                raise ValueError("Verification incomplete")
                await self._auth_step(stage,verify,method=kind)
                if code is None:return {"phase":"verification_code","method":index}
                return await self._complete_signin(method=kind)
            except AuthenticationError as error:
                # A known HTTP refusal has not advanced the SDK challenge. Keep
                # it for an explicit human retry, never automatically resend a
                # factor/code. Ambiguous submit/network outcomes are torn down.
                active=self.pending is not None and self.pending.login_state==LoginState.REQUIRE_2FA
                if active and (error.retry_factor or (code is None and error.code in {
                        "code_request_failed","authentication_network_error","verification_rate_limited"})):
                    if code is not None:
                        return {"phase":"verification_code","method":index,"error":error.code}
                    return {"phase":"choose_method","methods":self._method_choices(),"error":error.code}
                await self._clear_pending()
                raise
            except BaseException:
                await self._clear_pending()
                raise

    async def cancel(self, owner):
        async with self.lock:
            if self.owner and self.owner != owner:
                raise ValueError("Sign-in belongs to another user")
            await self._clear_pending()

    CONCURRENCY = 2
    START_SPACING = 1.0
    ITEM_TIMEOUT = 120
    ALLOWED_ERRORS = {"apple_empty_response","authentication_required","poll_failed","item_timeout","rate_limited","setup_required"}

    MANUAL_INTERVAL = 60

    def request_refresh(self, item_id):
        if self.inventory_busy:
            return {"status":"discovery_busy","message":"Item discovery is saving keys. Try refresh again when it finishes."}
        if item_id not in self.store.items or not self.store.items[item_id].get("enabled"):
            raise ValueError("Choose a tracked item")
        if self.pending:
            return {"status":"signing_in","message":"Finish account sign-in first."}
        if not self.session_available():
            return {"status":"reauth_required","message":"Connect the location account first."}
        until=read_json(self.store.root/"request-cooldown.json",{}).get("until",0)
        if until>time.time():
            return {"status":"paused","retry_after":math.ceil(until-time.time()),
                    "message":"Apple requested a pause. Refresh will be available after the pause."}
        if item_id in self.active_items:
            return {"status":"refreshing","message":"This item is already refreshing."}
        task=self.manual_tasks.get(item_id)
        if task and not task.done():
            return {"status":"queued","message":"This item is already queued."}
        remaining=self.MANUAL_INTERVAL-(time.monotonic()-self.item_attempts.get(item_id,-math.inf))
        if remaining>0:
            return {"status":"cooldown","retry_after":math.ceil(remaining),
                    "message":"This item was checked recently. Try again in "+str(math.ceil(remaining))+" seconds."}
        self.store.item_health[item_id]={"status":"queued"}
        task=asyncio.create_task(self._manual_refresh(item_id))
        self.manual_tasks[item_id]=task
        task.add_done_callback(lambda completed: self.manual_tasks.pop(item_id,None)
                               if self.manual_tasks.get(item_id) is completed else None)
        return {"status":"queued","message":"Refresh queued for this item. It will use the next available worker."}

    async def _manual_refresh(self, item_id):
        try:
            result=await self._query_item(item_id)
            if result.get("ok") and self.store.items.get(item_id,{}).get("enabled"):
                self._accept_report(item_id,result.get("report"))
        except asyncio.CancelledError:
            raise
        except Exception:
            self.store.item_health[item_id]={"status":"error","error":"poll_failed"}

    async def close(self):
        tasks=list(self.manual_tasks.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks,return_exceptions=True)

    async def _query_item(self, item_id):
        # Automatic and manual requests share the same two slots. Semaphore
        # waiters are served before an automatic worker can take another item.
        async with self.query_slots:
            if not self.store.items.get(item_id,{}).get("enabled"):
                return {"ok":True,"report":None}
            previous=self.item_attempts.get(item_id)
            if previous is not None and time.monotonic()-previous<self.MANUAL_INTERVAL:
                return {"ok":True,"report":None,"skipped":True}
            self.item_attempts[item_id]=time.monotonic()
            self.active_items.add(item_id)
            self.store.item_health[item_id]={"status":"refreshing"}
            try:
                result=await self._query_process(item_id)
                self.store.item_health[item_id]={
                    "status":("updated" if result.get("report") else "searching" if result.get("search_pending") else "no_report") if result.get("ok") else "error",
                    "checked_at":datetime.now(timezone.utc).isoformat(),
                    "error":result.get("error"),"progress":safe_progress(result.get("progress"))}
                return result
            except asyncio.CancelledError:
                self.store.item_health[item_id]={"status":"cancelled"}
                raise
            except Exception:
                self.store.item_health[item_id]={"status":"error","error":"poll_failed",
                    "checked_at":datetime.now(timezone.utc).isoformat()}
                return {"ok":False,"error":"poll_failed"}
            finally:
                self.active_items.discard(item_id)

    async def _query_process(self, item_id):
        from .reporting_runtime import report_launch
        default_command,env=report_launch(self.store.root)
        command=getattr(self,"_item_command",default_command)
        progress_path=self.store.root/"progress"/(item_id+".json")
        progress_path.unlink(missing_ok=True)
        process=await asyncio.create_subprocess_exec(*command,
            stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,env=env)
        try:
            try:
                output,_=await asyncio.wait_for(
                    process.communicate(json.dumps({"id":item_id}).encode()),
                    timeout=self.ITEM_TIMEOUT)
            except TimeoutError:
                process.kill()
                await process.communicate()
                progress=safe_progress(read_json(progress_path,{}))
                print("Retrace query timeout: "+json.dumps(progress),flush=True)
                return {"ok":False,"error":"item_timeout","progress":progress}
            if process.returncode or len(output)>8192:
                return {"ok":False,"error":"poll_failed"}
            result=json.loads(output)
            if not isinstance(result,dict) or not isinstance(result.get("ok"),bool):
                return {"ok":False,"error":"poll_failed"}
            if result.get("error") not in self.ALLOWED_ERRORS and not result["ok"]:
                return {"ok":False,"error":"poll_failed"}
            from .progress import safe_query_diagnostic
            diagnostic=safe_query_diagnostic(result.get("diagnostic"))
            if diagnostic:
                result["diagnostic"]=diagnostic
                print("Retrace query diagnostic: "+json.dumps(diagnostic),flush=True)
            progress=safe_progress(read_json(progress_path,{}))
            if progress:
                result["progress"]=progress
                print("Retrace query completed: "+json.dumps(progress),flush=True)
            return result
        finally:
            if process.returncode is None:
                process.kill()
                await process.communicate()

    def _accept_report(self,key,report):
        if not isinstance(report,dict):
            return False
        try:
            lat,lon,accuracy=report["latitude"],report["longitude"],report["accuracy"]
            if not all(isinstance(v,(int,float)) and math.isfinite(v) for v in (lat,lon,accuracy)):
                return False
            if not (-90<=lat<=90 and -180<=lon<=180 and accuracy>=0):
                return False
            timestamp=datetime.fromisoformat(report["timestamp"])
            if timestamp.tzinfo is None or timestamp>datetime.now(timezone.utc)+timedelta(minutes=5):
                return False
            previous=self.store.reports.get(key)
            if previous and timestamp<datetime.fromisoformat(previous["timestamp"]):
                return False
            updated={**self.store.reports,key:{"latitude":lat,"longitude":lon,"accuracy":accuracy,
                                     "timestamp":timestamp.astimezone(timezone.utc).isoformat()}}
            atomic_json(self.store.root/"reports.json",updated)
            self.store.reports=updated
            return True
        except (KeyError,TypeError,ValueError):
            return False

    def _summary(self,event):
        allowed=("status","selected_count","reports_received","items_with_locations",
                 "items_completed","items_failed","error_code")
        print("Retrace "+event+": "+json.dumps(
            {key:self.store.health.get(key) for key in allowed}),flush=True)

    async def poll(self):
        if self.poll_lock.locked():
            return
        async with self.poll_lock:
            await self._poll()

    async def _poll(self):
        if self.pending:
            return
        selected={key:item for key,item in self.store.items.items() if item["enabled"]}
        if not self.session_available():
            self.store.health["status"]="reauth_required"
            return
        if not selected:
            self.store.health["status"]="select_items"
            return
        self.last_attempt=time.monotonic()
        self.store.health.update(status="polling",last_attempt=datetime.now(timezone.utc).isoformat(),
            selected_count=len(selected),reports_received=0,items_completed=0,items_failed=0,
            items_with_locations=sum(key in self.store.reports for key in selected),
            error_code=None,next_poll=datetime.fromtimestamp(time.time()+900,timezone.utc).isoformat())
        self._summary("poll started")
        failures=[]
        searches=[]
        queue=asyncio.Queue()
        for key in selected:
            queue.put_nowait(key)
        start_lock=asyncio.Lock()
        next_start=0.0
        stop=asyncio.Event()

        async def update_items():
            nonlocal next_start
            while not queue.empty() and not stop.is_set():
                key=queue.get_nowait()
                if self.pending or not self.store.items.get(key,{}).get("enabled"):
                    continue
                # Stagger process starts rather than bursting all devices at Apple.
                async with start_lock:
                    await asyncio.sleep(max(0,next_start-time.monotonic()))
                    next_start=time.monotonic()+self.START_SPACING
                if stop.is_set() or self.pending:
                    return
                try:
                    result=await self._query_item(key)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    result={"ok":False,"error":"poll_failed"}
                if result.get("search_pending"):
                    searches.append(key)
                if not result["ok"]:
                    error=result.get("error","poll_failed")
                    failures.append(error)
                    self.store.health["items_failed"]+=1
                    self.store.health["error_code"]=error
                    if error in ("authentication_required","rate_limited","setup_required"):
                        stop.set()
                elif self.store.items.get(key,{}).get("enabled") and self._accept_report(key,result.get("report")):
                    self.store.health["reports_received"]+=1
                self.store.health["items_completed"]+=1
                self.store.health["items_with_locations"]=sum(k in self.store.reports for k in selected)
                self._summary("item completed")

        # Only two live workers; each publishes before taking another device.
        async with asyncio.TaskGroup() as group:
            for _ in range(min(self.CONCURRENCY,len(selected))):
                group.create_task(update_items())
        received=self.store.health["reports_received"]
        if "setup_required" in failures:
            status="setup_required"
        elif "authentication_required" in failures:
            status="reauth_required"
        elif received:
            status="partial_results" if failures else "searching" if searches else "ok"
        else:
            status="error" if failures else "searching" if searches else "no_reports"
        self.failures=self.failures+1 if failures else 0
        self.store.health.update(status=status,items_searching=len(searches),last_poll=datetime.now(timezone.utc).isoformat())
        self._summary("poll completed")

    async def run(self):
        while True:
            self.wake.clear()
            remaining=0 if self.last_attempt is None else max(0,self.last_attempt+900-time.monotonic())
            if not remaining:
                try:
                    await self.poll()
                except asyncio.CancelledError:
                    raise
                except Exception:
                    self.failures+=1
                    self.store.health.update(status="error",error_code="poll_failed")
                    self._summary("poll failed")
                remaining=min(3600,900*2**min(self.failures,2))
            self.store.health["next_poll"]=datetime.fromtimestamp(time.time()+remaining,timezone.utc).isoformat()
            try:
                await asyncio.wait_for(self.wake.wait(),timeout=remaining)
            except TimeoutError:
                pass
