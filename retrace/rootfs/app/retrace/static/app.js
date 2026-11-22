"use strict";
let providerTouched=false;
let csrf="", snapshot=null, loginMethod=null, busy=false, selectionDirty=false;
let forceDiscoveryLogin=false, reconnecting=false, recoveryKey="";
let refreshing=false, emailHint="", authKey="", factorKey="", factorPhase="idle", layoutShared=null, activeFeedback=null;
const itemFeedback=new Map();
const $=id=>document.getElementById(id);
const itemCount=n=>n+" item"+(n===1?"":"s");
const text=(tag,value)=>{const node=document.createElement(tag);node.textContent=value;return node;};
function setFeedback(id,message,kind="info"){
  const box=$(id);if(!box)return;
  box.textContent=message;box.dataset.kind=kind;box.hidden=!message;
}
function notice(message,kind="info",target=activeFeedback){
  // Action feedback belongs to its control, never a duplicate banner on other tabs.
  setFeedback("message",target?"":message,kind);
  if(target){
    setFeedback(target,message,kind);
    if(target.startsWith("refresh-status-")){
      const id=target.slice("refresh-status-".length);
      itemFeedback.set(id,{message,kind,status:snapshot?.items.find(item=>item.id===id)?.refresh?.status});
    }
  }
}
function statusBadge(id,label,kind="info"){
  const node=$(id);if(node.textContent!==label)node.textContent=label;
  node.dataset.kind=kind;
}
function renderStatus(data){
  const auth=data.auth?.phase,flow=data.recovery?.phase,health=data.health||{};
  const selected=data.items.filter(item=>item.enabled);
  const setupBlocked=auth==="failed"&&data.auth?.error==="setup_required";
  const pending=["working","choose_method","verification_code"].includes(auth);
  statusBadge("account-badge",pending?(auth==="working"?"Account: connecting":"Account: verification needed"):
    setupBlocked?"Account: setup required":auth==="failed"?"Account: sign-in needs attention":data.setup?.locations_connected?"Account: connected":"Account: not connected",
    setupBlocked?"error":pending?"info":auth==="failed"?"error":data.setup?.locations_connected?"success":"info");
  const recoveryIssue=["failed","expired","timed_out"].includes(flow);
  statusBadge("keys-badge",flow==="working"?"Item keys: recovering":flow==="input"?"Item keys: unlock needed":recoveryIssue?"Item keys: recovery needs attention":
    data.items.length?"Item keys: ready":"Item keys: not recovered",recoveryIssue?"error":flow==="input"?"warning":data.items.length&&flow!=="working"?"success":"info");
  statusBadge("tracking-badge","Tracking: "+itemCount(selected.length),selected.length?"success":"info");
  let label="Checks: waiting",kind="info";
  if(health.error_code==="rate_limited"){label="Checks: paused by Apple";kind="warning";}
  else if(health.status==="reauth_required"){label="Checks: reconnect needed";kind="error";}
  else if(health.status==="setup_required"||setupBlocked){label="Checks: setup needs attention";kind="error";}
  else if(auth==="failed"){label="Status: sign-in needs attention";kind="error";}
  else if(recoveryIssue){label="Status: recovery needs attention";kind="error";}
  else if(["error","partial_results"].includes(health.status)||health.items_failed>0){label="Checks: needs attention";kind="error";}
  else if(!selected.length)label="Checks: choose tracked items";
  else if(health.status==="polling")label="Checks: refreshing";
  else if(health.status==="searching")label="Checks: searching for sightings";
  else if(health.status==="no_reports")label="Checks: no sightings yet";
  else if(health.status==="ok"){label="Checks: completed";kind="success";}
  statusBadge("checks-badge",label,kind);
}

async function api(path,data){
  const response=await fetch(path,{method:data?"POST":"GET",headers:data?{"Content-Type":"application/json","X-CSRF-Token":csrf}:{},body:data?JSON.stringify(data):undefined,cache:"no-store",credentials:"same-origin"});
  const result=await response.json();
  if(!response.ok)throw Error(result.message||"The request failed. Your saved choices have not been changed.");
  return result;
}
async function action(fn,pending="Working…",success,target=null){
  if(busy)return;
  busy=true;activeFeedback=target;notice(pending,"working",target);updateButtons();
  try{const result=await fn();if(success)notice(typeof success==="function"?success(result):success,"success");
    else if(result?.phase)notice(result.phase==="input"?"Apple needs the information shown in the discovery step.":result.phase==="complete"?"Discovery complete. Choose items and save your tracking choices.":result.phase==="failed"?"Discovery failed. Try the saved session or sign in again.":"Discovery: "+result.phase,result.phase==="complete"?"success":result.phase==="failed"?"error":"info");
    await refresh();}
  catch(error){notice(error.message,"error");}
  finally{busy=false;activeFeedback=null;updateButtons();}
}
function updateButtons(){
  for(const button of document.querySelectorAll("form button"))button.disabled=busy||!snapshot||!csrf;
  for(const form of document.querySelectorAll("form")){
    const scoped=busy&&(form.getAttribute("aria-describedby")||"").split(" ").includes(activeFeedback);
    const authPending=snapshot?.setup?.shared_auth&&snapshot.auth?.phase==="working"&&["login","factor"].includes(form.id);
    form.setAttribute("aria-busy",String(Boolean(scoped||authPending)));
  }
  if(snapshot?.setup?.shared_auth&&snapshot.auth?.phase==="working"){
    for(const button of document.querySelectorAll("#login button,#factor button"))button.disabled=true;
  }
  $("save-selection").disabled=busy||!selectionDirty;
  $("cancel-login").disabled=busy;$("cancel-recovery").disabled=busy;
  for(const button of document.querySelectorAll("[data-refresh]")){
    const state=snapshot?.items.find(item=>item.id===button.dataset.refresh)?.refresh?.status;
    button.disabled=busy||state==="queued"||state==="refreshing";
    button.setAttribute("aria-busy",String(state==="queued"||state==="refreshing"||(busy&&activeFeedback==="refresh-status-"+button.dataset.refresh)));
  }
}
function ago(value){if(!value)return "No sighting yet";const seconds=Math.max(0,Math.floor((Date.now()-Date.parse(value))/1000));return seconds<60?"Just now":seconds<3600?Math.floor(seconds/60)+" minutes ago":seconds<86400?Math.floor(seconds/3600)+" hours ago":Math.floor(seconds/86400)+" days ago";}
const errors={"setup_required":"Secure runtime setup needs attention.","rate_limited":"Apple requested a pause.","apple_empty_response":"Apple returned an empty response.","authentication_required":"Reconnect location access.","poll_failed":"Refresh failed.","item_timeout":"This item exceeded its query time limit."};
function description(item){
  const parts=[];
  if(item.apple_name&&item.apple_name!==item.name)parts.push(item.apple_name);
  if(item.model_name||item.model)parts.push(item.model_name||item.model);
  if(item.paired_at)parts.push("Paired "+item.paired_at);
  parts.push("ID "+item.id.slice(0,8));
  return parts.join(" · ");
}
function configureLayout(shared){
  if(layoutShared===shared)return;
  layoutShared=shared;
  const login=$("login"),discovery=$("discovery-start"),consent=$("recovery-consent");
  if(shared){
    login.insertBefore(consent,$("connect-account"));
    $("account-step").insertBefore($("auth-explanation"),login);
    $("account-step").append($("discovery-controls"));
  }else{
    discovery.insertBefore(consent,$("discover"));
    $("setup").insertBefore($("auth-explanation"),$("setup").firstChild);
    $("discovery-step").append($("discovery-controls"));
    $("auth-explanation").textContent="Location access reads sightings on a schedule. Item discovery unlocks encrypted item keys using a separate client. These two private sessions are reused while valid.";
    $("consent-label").textContent="I allow this installation to join my iCloud Keychain trust circle to recover my item keys.";
    $("discovery-description").textContent="Discovery unlocks item keys separately from refreshing locations. Apple may request an SMS code and a trusted device's unlock passcode. Later discovery attempts reuse the saved session.";
    $("discover").hidden=false;
  }
  $("discovery-step").hidden=shared;discovery.hidden=shared;$("recovery-heading").hidden=!shared;
  $("account-title").textContent=shared?"1. Connect Apple account and discover items":"1. Location access";
  $("account-description").textContent=shared?"Sign in once, verify with Apple, then choose a trusted device if asked. Your password, verification code and device passcode are not saved.":"Connect once so this app can fetch sightings. Your password is discarded after sign-in. Reconnect only when Apple expires the session.";
  $("connect-account").textContent=shared?"Connect Apple account":"Connect location access";
  $("reconnect").textContent=shared?"Reconnect Apple account":"Reconnect location access";
  $("selection-title").textContent=shared?"2. Choose tracked items":"3. Choose tracked items";
  $("consent").setAttribute("aria-required",String(shared));
}
function render(data){
  snapshot=data;csrf=data.csrf;
  $("app-title").textContent="Retrace"+(data.channel==="stable"?"":" Edge");
  document.title=$("app-title").textContent;
  $("health").textContent=({"ok":"Tracking","searching":"Tracking; searching remaining items","partial_results":"Some items need attention","no_reports":"No reports returned","reauth_required":"Connect location access","setup_required":"Secure runtime setup required","select_items":"Choose tracked items","polling":"Refreshing","error":"Refresh needs attention","starting":"Starting","ready":"Ready"})[data.health.status]||"Checking";
  renderStatus(data);
  const selected=data.items.filter(item=>item.enabled), known=selected.filter(item=>item.report).length, health=data.health;
  $("poll-summary").textContent=selected.length+" tracked · "+known+" with a saved location · Scheduled check: "+(health.last_poll?ago(health.last_poll):"not completed")+" · Checked "+(health.items_completed??0)+"/"+selected.length+(health.error_code?" · "+(errors[health.error_code]||"Refresh needs attention."):"");
  const cards=$("cards");cards.replaceChildren();
  if(!selected.length)cards.append(text("p","Choose items in Setup, then save your tracking choices."));
  for(const item of selected){
    const card=text("article","");card.append(text("h2",item.name));const detail=text("p",description(item));detail.className="item-description";card.append(detail);const dl=text("dl",""),report=item.report;
    for(const [label,value] of [["Last sighting",ago(report?.timestamp)],["Last checked",item.refresh?.checked_at?ago(item.refresh.checked_at):"Not checked yet"],["Reported at",report?new Date(report.timestamp).toLocaleString():"Not reported"],["Accuracy",report?Math.round(report.accuracy)+" m":"Not reported"]])dl.append(text("dt",label),text("dd",value));
    card.append(dl);
    const state=item.refresh||{}, status=text("p",({"queued":"Queued for the next available worker…","refreshing":"Asking Apple for this item…","updated":"Latest available report checked.","searching":"Recent keys checked. The older key search will continue on the next refresh.","no_report":"Check finished: Apple returned no sighting for this item.","cancelled":"Refresh cancelled."})[state.status]||(state.status==="error"?(errors[state.error]||"Refresh failed. Try again later."):""));
    status.id="refresh-status-"+item.id;status.className="item-status inline-feedback";status.setAttribute("role","status");status.setAttribute("aria-live","polite");status.setAttribute("aria-atomic","true");
    const local=itemFeedback.get(item.id);
    if(local&&local.status===state.status){status.textContent=local.message;status.dataset.kind=local.kind;}
    else itemFeedback.delete(item.id);
    status.hidden=!status.textContent;
    const button=text("button",state.status==="queued"?"Refresh queued":state.status==="refreshing"?"Refreshing…":"Refresh this item");button.dataset.refresh=item.id;
    button.onclick=()=>action(async()=>{
      const result=await api("ui/refresh",{id:item.id});
      const kind=["error","setup_required"].includes(result.status)?"error":["paused","cooldown","reauth_required","discovery_busy","signing_in"].includes(result.status)?"info":"success";
      notice((result.message||"Refresh request completed.")+(result.status==="paused"?" Try again in "+Math.ceil(result.retry_after/60)+" minutes.":""),kind);
    },"Queueing this item's refresh…",null,status.id);
    button.setAttribute("aria-describedby",status.id);
    card.append(button,status);cards.append(card);
  }
  if(!selectionDirty){
    const choices=$("choices");choices.replaceChildren();
    for(const item of data.items){
      const label=text("label","");label.className="check";
      const check=document.createElement("input");check.type="checkbox";check.value=item.id;check.checked=item.enabled;
      check.onchange=()=>{selectionDirty=true;$("selection-state").textContent="Unsaved changes";$("selection-count").textContent=choices.querySelectorAll("input:checked").length+" selected";updateButtons();};
      const copy=text("span","");copy.className="item-label";
      copy.append(text("span",item.name));const detail=text("small",description(item));detail.className="item-description";copy.append(detail);
      label.append(check,copy);choices.append(label);
    }
    if(!data.items.length)choices.append(text("p",data.setup?.shared_auth?"Connect your Apple account and recover item keys above first.":"Discover items in step 2 first."));
    $("selection-count").textContent=selected.length+" selected";
  }
  const shared=Boolean(data.setup?.shared_auth);
  configureLayout(shared);
  $("provider-controls").hidden=!shared;
  const providerSelect=$("authentication-provider");
  if(!providerTouched&&data.setup?.default_authentication_provider)providerSelect.value=data.setup.default_authentication_provider;
  providerSelect.querySelector('option[value="apple_music"]').disabled=data.setup?.authentication_providers?.find(p=>p.id==="apple_music")?.available===false;
  configureNativeConsent(data);
  $("provider-current").textContent=data.setup?.locations_connected?"Current connection provider: "+(data.setup?.authentication_provider==="macos"?"macOS":"Apple Music"):"No saved connection yet";
  const macAvailable=Boolean(data.setup?.authentication_providers?.find(p=>p.id==="macos")?.available);
  const macOption=$("authentication-provider").querySelector('option[value="macos"]');
  macOption.disabled=!macAvailable;
  macOption.textContent=macAvailable?(data.channel==="stable"?"macOS provider":"macOS provider (experimental)"):"macOS provider (unavailable)";
  $("provider-help").textContent=macAvailable?"Both use your Apple account and Apple verification. Switching provider creates a separate device identity and needs a new sign-in; the previous provider's saved connection is kept. No automatic fallback.":"Both providers use your Apple account and Apple verification. The experimental macOS provider is not enabled in this build. Your current connection is kept.";
  if(data.channel==='stable')$("provider-help").textContent="This release uses the macOS provider. Apple Music remains available in Edge for development.";
  const providerPending=["working","choose_method","verification_code"].includes(data.auth?.phase);
  $("authentication-provider").disabled=providerPending;
  const connected=Boolean(data.setup?.locations_connected);
  $("location-state").textContent=connected?"Connected":"Not connected";
  $("login").hidden=connected&&!reconnecting;$("reconnect").hidden=!connected;
  if(shared){
    $("auth-explanation").textContent="One Apple sign-in connects location access and recovers the encrypted Find My item keys needed for tracking. Apple may request a verification code, then the unlock passcode of a trusted device to approve access to those keys. The device passcode is separate from your Apple password.";
    $("discovery-description").textContent="Discovery starts after the main Apple sign-in. Choose a trusted device below and enter its unlock passcode if requested. Later discovery may need main-account reauthentication because location tokens cannot unlock Keychain recovery.";
    $("consent-label").textContent="I allow this installation to recover my encrypted Find My item keys using my authenticated account and a trusted device's unlock passcode.";
    const key=JSON.stringify(data.auth||{});
    if(key!==authKey)showFactor(data.auth||{phase:"idle"});
    const underway=["choose_method","verification_code","working"].includes(data.auth?.phase);
    const needsLogin=data.auth?.phase==="failed"||["expired","failed"].includes(data.recovery?.phase);
    if(underway){$("login").hidden=true;$("reconnect").hidden=true;}
    else if(needsLogin){reconnecting=true;$("login").hidden=false;}
  }
  const saved=Boolean(data.setup?.discovery_session_saved);
  $("discovery-state").textContent=saved?"Session saved":"First discovery";
  $("discovery-credentials").hidden=saved&&!forceDiscoveryLogin;
  for(const input of $("discovery-credentials").querySelectorAll("input"))input.required=!$("discovery-credentials").hidden;
  $("discovery-signin").hidden=!saved||forceDiscoveryLogin;
  $("discover").textContent=saved&&!forceDiscoveryLogin?"Discover using saved session":"Sign in and discover items";
  if(shared){
    $("discovery-credentials").hidden=true;
    for(const input of $("discovery-credentials").querySelectorAll("input"))input.required=false;
    $("discovery-signin").hidden=true;
    $("discover").hidden=true;
    $("discovery-state").textContent="Shared Apple sign-in";
  }
  renderRecovery(data.recovery);
  updateButtons();
}
function renderRecovery(flow){
  const messages={"idle":"","working":"Contacting Apple. Keep this page open…","complete":"Discovery complete. Choose items below and save your tracking choices.","failed":"Discovery did not finish. Try the saved session again, or choose Sign in again if Apple expired it.","timed_out":"Apple did not respond in time. Try again.","expired":"Discovery expired. Start it again.","cancelled":"Discovery cancelled.","busy":"Another user is completing discovery."};
  const sharedErrors={"authentication_required":"Reconnect using the main Apple sign-in to authorize item discovery. Location tokens alone cannot unlock item keys.","timed_out":"Apple did not respond in time. Reconnect using the main Apple sign-in to try discovery again.","no_recovery_devices":"Apple returned no recoverable trusted devices. Check your account's Keychain setup before reconnecting.","discovery_failed":"Item discovery could not finish. Reconnect using the main Apple sign-in to try again."};
  const key=JSON.stringify(flow||{});if(key===recoveryKey)return;recoveryKey=key;
  const message=snapshot?.setup?.shared_auth?(flow?.phase==="expired"?"Item discovery expired. Reconnect using the main Apple sign-in; your saved tracked items are kept.":flow?.phase==="failed"?(sharedErrors[flow.error]||sharedErrors.discovery_failed):messages[flow?.phase]??""):messages[flow?.phase]??"";
  setFeedback("recovery-status",message,["failed","expired","timed_out"].includes(flow?.phase)?"error":flow?.phase==="complete"?"success":flow?.phase==="working"?"working":"info");
  const form=$("recovery");form.replaceChildren();form.hidden=flow?.phase!=="input";if(form.hidden)return;
  if(flow.kind==="device_unlock"){
    const select=document.createElement("select");select.name="choice";
    for(const choice of flow.choices||[]){const option=text("option",choice.label);option.value=choice.value;select.append(option);}
    const device=text("label","Trusted device");device.append(select);
    const passcode=document.createElement("input");passcode.type="password";passcode.autocomplete="off";passcode.maxLength=512;passcode.required=true;
    const label=text("label","Unlock passcode for the selected device");label.append(passcode);
    form.append(text("p","Your Apple account is already signed in. Use this device's unlock passcode to recover encrypted item keys. It is not saved and failed attempts are not retried automatically."),device,label,text("button","Unlock item keys"));
    form.onsubmit=event=>{event.preventDefault();if(busy)return;const value=passcode.value;passcode.value="";action(()=>api("ui/recovery",{action:"answer",choice:select.value,passcode:value}),"Recovering item keys…",null,"recovery-status");};
    return;
  }
  const label=text("label",flow.label);let input;
  if(flow.kind==="recovery_device"){
    input=document.createElement("select");
    for(const choice of flow.choices){const option=text("option",choice.label);option.value=choice.value;input.append(option);}
    form.append(text("p","Choose a device whose unlock passcode you know. This is not your Apple account password."));
  }else{
    input=document.createElement("input");input.type=flow.secret?"password":flow.kind==="email"?"email":"text";
    input.autocomplete=flow.kind==="password"?"current-password":flow.kind==="email"?"username":flow.kind==="verification_code"?"one-time-code":"off";
    input.inputMode=flow.kind==="verification_code"?"numeric":"text";input.maxLength=512;input.required=true;
    if(flow.kind==="email")input.value=emailHint;
    if(flow.kind==="verification_code")form.append(text("p","Enter the SMS code sent for this discovery attempt, not a separate trusted-device approval code."));
  }
  input.name="response";label.append(input);form.append(label,text("button",flow.kind==="verification_code"?"Verify SMS code":flow.kind==="device_passcode"?"Unlock item keys":"Continue"));
  form.onsubmit=event=>{event.preventDefault();if(busy)return;const value=input.value;input.value="";action(()=>api("ui/recovery",{action:"answer",value}),"Verifying with Apple…",null,"recovery-status");};
}
async function refresh(){if(refreshing)return;refreshing=true;try{render(await api("v1/snapshot"));}catch(error){$("health").textContent="App unavailable";statusBadge("checks-badge","Checks: app unavailable","error");notice(error.message,"error");}finally{refreshing=false;}}
document.querySelectorAll("[data-tab]").forEach(button=>button.onclick=()=>{setFeedback("message","");for(const id of ["overview","setup"])$(id).hidden=id!==button.dataset.tab;document.querySelectorAll("[data-tab]").forEach(other=>other.setAttribute("aria-selected",String(other===button)));});
function configureNativeConsent(data){
  const required=Boolean(data?.setup?.shared_auth&&data.setup.native_component_consent_required&&$("authentication-provider").value==="macos");
  $("native-component-notice").hidden=!required;
  $("native-component-consent").required=required;
}
$("authentication-provider").onchange=()=>{providerTouched=true;configureNativeConsent(snapshot);};
$("login").onsubmit=event=>{
  event.preventDefault();if(busy)return;
  if(!snapshot||!csrf){notice("Account status is still loading. Try again shortly.","info","login-status");return;}
  if(snapshot?.setup?.shared_auth&&!$("consent").checked){
    notice("Allow encrypted item-key recovery before connecting your Apple account.","error","login-status");$("consent").focus();return;
  }
  if(snapshot?.setup?.native_component_consent_required&&$("authentication-provider").value==="macos"&&!$("native-component-consent").checked){
    notice("Review the Apple component notice and allow local acquisition before connecting.","error","login-status");$("native-component-consent").focus();return;
  }
  const form=event.target;
  if(!form.checkValidity()){notice("Enter your Apple account email and password before connecting.","error","login-status");form.reportValidity();return;}
  const email=form.elements.namedItem("email").value,password=form.elements.namedItem("password").value;
  emailHint=email;$("discovery-email").value=email;
  form.elements.namedItem("password").value="";
  action(async()=>showFactor(await api("ui/login",{email,password,...(snapshot?.setup?.shared_auth?{discovery_consent:true,provider:$("authentication-provider").value,native_component_consent:$("native-component-consent").checked}:{})})),"Connecting your Apple account…",null,"login-status");
};
function showFactor(result){
  result=result||{phase:"idle"};authKey=JSON.stringify(result);
  const form=$("factor"),shared=Boolean(snapshot?.setup?.shared_auth);
  const reasons={
    "apple_signin_refused":"Apple declined to start sign-in for this account or device before checking the password. Wait before retrying; repeatedly reconnecting may not help.",
    "credentials_rejected":"Apple did not accept the sign-in credentials. Check the account email and password before retrying.",
    "authentication_protocol_error":"Apple’s sign-in response could not be processed. Retrace’s app log records the failure stage without your credentials.",
    "authentication_state_error":"The sign-in sequence could not continue. Cancel sign-in, then reconnect using the account form.",
    "authentication_failed":"Sign-in stopped unexpectedly. Retrace’s app log records the failure stage without your credentials.",
    "sign_in_expired":"The verification step expired. Sign in again using the Apple account form above.",
    "session_expired":"The saved session expired. Reconnect using the Apple account form above.",
    "session_save_failed":"Your account session could not be saved securely. Check app storage before signing in again.",
    "setup_required":"Secure account setup is incomplete. Open the app’s Configuration tab and check first-time setup before retrying. This is a local setup problem, not a rejected Apple password.",
    "verification_not_accepted":"Apple did not accept that verification attempt. Check that you are using the code from the selected method, then try again. Your sign-in may also have expired.",
    "invalid_verification_code":"Apple did not accept that verification attempt. Check the code from the selected method and try again.",
    "verification_rate_limited":"Apple asked you to wait before trying verification again. Do not repeatedly request or submit codes.",
    "code_request_failed":"Apple did not accept the code request. Choose a verification method and try again, or restart sign-in.",
    "authentication_network_error":"The authentication request could not complete. Check the connection and try again.",
    "verification_rejected":"Verification could not finish safely. Restart sign-in using the Apple account form above.",
    "discovery_handoff_failed":"Apple sign-in finished, but item discovery could not start. Reconnect your account to try discovery again."
  };
  const promptPhase=["choose_method","verification_code"].includes(result.phase);
  if(Number.isInteger(result.method)&&result.method>=0)loginMethod=result.method;
  if(promptPhase){
    setFeedback("login-status","");
    const effectiveMethod=Number.isInteger(result.method)&&result.method>=0?result.method:loginMethod;
    const key=JSON.stringify({phase:result.phase,method:result.phase==="verification_code"?effectiveMethod:null,methods:result.phase==="choose_method"?result.methods:undefined});
    if(key!==factorKey){
      const selected=form.querySelector("select")?.value;
      factorKey=key;form.replaceChildren();
      if(result.phase==="choose_method"){
        const select=document.createElement("select");select.name="method";
        for(const method of result.methods||[]){const option=text("option",method.label);option.value=method.value;select.append(option);}
        if(selected!==undefined&&[...select.options].some(option=>option.value===selected))select.value=selected;
        const label=text("label","How should Apple send your verification code?");label.append(select);form.append(label,text("button","Send verification code"));
        form.onsubmit=event=>{
          event.preventDefault();if(busy)return;
          const method=Number(select.value);
          if(!Number.isInteger(method)||method<0){notice("Choose a verification method first.","error","factor-status");return;}
          loginMethod=method;
          action(async()=>showFactor(await api("ui/factor",{method})),"Requesting your verification code…",null,"factor-status");
        };
      }else if(Number.isInteger(effectiveMethod)&&effectiveMethod>=0){
        // Method comes from server state, so a reloaded page never sends null or
        // silently switches an SMS verification attempt to a different method.
        loginMethod=effectiveMethod;
        const code=document.createElement("input");code.name="code";code.type="password";code.inputMode="numeric";code.autocomplete="one-time-code";code.maxLength=8;code.required=true;
        const label=text("label","Code from the selected verification method");label.append(code);form.append(label,text("button","Verify code"));
        form.onsubmit=event=>{
          event.preventDefault();if(busy)return;
          const method=loginMethod;
          if(!Number.isInteger(method)||method<0){notice("This verification step is unavailable. Restart Apple sign-in.","error","factor-status");return;}
          if(!/^\d{4,8}$/.test(code.value)){notice("Enter the 4–8 digit code from your selected verification method.","error","factor-status");code.focus();return;}
          const value=code.value;code.value="";
          action(async()=>showFactor(await api("ui/factor",{method,code:value})),"Verifying your code with Apple…",null,"factor-status");
        };
      }
    }
    factorPhase=result.phase;form.hidden=!form.children.length;
    if(result.phase==="verification_code"&&(!Number.isInteger(effectiveMethod)||effectiveMethod<0)){
      notice("This verification step is unavailable. Restart Apple sign-in using the form above.","error","factor-status");return;
    }
    notice(result.error?(reasons[result.error]||"Apple could not complete this verification step. Try again or restart sign-in."):result.phase==="choose_method"?"Choose how Apple should send your verification code.":"Code requested. Enter the code received through your selected method.",result.error?"error":"info","factor-status");
    return;
  }
  if(result.phase==="working"){
    notice("Apple sign-in is running. Progress will update here.","working",factorPhase==="choose_method"||factorPhase==="verification_code"?"factor-status":"login-status");
    return;
  }
  factorPhase=result.phase;factorKey="";loginMethod=null;form.replaceChildren();form.hidden=true;setFeedback("factor-status","");
  if(result.phase==="complete"){
    reconnecting=false;
    notice(shared?"Apple account connected.":"Location access connected. Next, discover or choose your items.","success","login-status");
  }else if(result.phase==="failed"){
    notice(reasons[result.error]||"Apple sign-in could not finish. Reconnect using the account form above.","error","login-status");
  }else if(result.phase==="cancelled")notice("Apple sign-in cancelled.","info","login-status");
}
$("reconnect").onclick=()=>{reconnecting=true;$("login").hidden=false;$("login").elements.namedItem("email").focus();};
$("discovery-signin").onclick=()=>{forceDiscoveryLogin=true;$("discovery-credentials").hidden=false;for(const input of $("discovery-credentials").querySelectorAll("input"))input.required=true;$("discovery-email").focus();$("discover").textContent="Sign in and discover items";};
$("discovery-start").onsubmit=event=>{
  event.preventDefault();if(busy)return;
  if(!$("consent").checked){notice("Read and accept the item-key recovery consent first.","error","recovery-status");return;}
  const form=event.target,data={action:"start",consent:true};
  if(!$("discovery-credentials").hidden){data.credentials={email:form.elements.namedItem("email").value,password:form.elements.namedItem("password").value};emailHint=form.elements.namedItem("email").value;form.elements.namedItem("password").value="";data.fresh_login=forceDiscoveryLogin;}
  action(()=>api("ui/recovery",data),"Discovering items. Apple may request an SMS code or a trusted-device passcode…",null,"recovery-status");
};
$("selection").onsubmit=event=>{
  event.preventDefault();
  action(async()=>{
    const ids=[...$("choices").querySelectorAll("input:checked")].map(check=>check.value);
    const result=await api("ui/select",{ids});selectionDirty=false;
    $("selection-state").textContent=itemCount(result.selected_count)+" saved";
    return result;
  },"Saving tracking choices…",result=>"Saved: "+itemCount(result.selected_count)+" tracked. Location checks run separately; each item shows its refresh progress.","selection-feedback");
};
$("cancel-recovery").onclick=()=>action(()=>api("ui/recovery",{action:"cancel"}),"Cancelling discovery…","Discovery cancelled.","recovery-status");
$("cancel-login").onclick=()=>action(async()=>{await api("ui/cancel",{});$("factor").hidden=true;},"Cancelling sign-in…","Apple sign-in cancelled.","login-status");
$("pairing-security").onsubmit=event=>{
  event.preventDefault();
  if(!$("pairing-consent").checked){notice("Confirm that existing read-only access should be revoked.","error","pairing-status");return;}
  action(async()=>{const result=await api("ui/rotate-pairing",{confirm:true});$("pairing-consent").checked=false;return result;},"Revoking old location-read access…",result=>result.message,"pairing-status");
};
refresh();setInterval(refresh,5000);
