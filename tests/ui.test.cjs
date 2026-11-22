const {test}=require("node:test");
const assert=require("node:assert/strict");
const fs=require("node:fs");
const path=require("node:path");
const {JSDOM}=require("jsdom");
const root=path.resolve(__dirname,"../retrace/rootfs/app/retrace/static");
const html=fs.readFileSync(path.join(root,"index.html"),"utf8");
const script=fs.readFileSync(path.join(root,"app.js"),"utf8");
const flush=()=>new Promise(resolve=>setImmediate(resolve));
async function setup(options={}){
  const data={channel:"edge",csrf:"synthetic-csrf",health:{status:"ok"},setup:{locations_connected:options.connected??true,discovery_session_saved:false,shared_auth:!!options.shared},auth:options.auth||{phase:"idle"},recovery:{phase:"idle"},
    items:[{id:"a",name:"Fixture A",enabled:!!options.enabled,report:null},{id:"b",name:"Fixture B",enabled:false,report:null}]};
  const dom=new JSDOM(html,{url:"https://ha.example.invalid/api/hassio_ingress/synthetic/",runScripts:"outside-only"});
  const window=dom.window,requests=[];
  let tick;
  window.setInterval=callback=>{tick=callback;return 1;};
  window.fetch=async(url,init={})=>{
    const body=init.body?JSON.parse(init.body):null;
    requests.push({url,body,headers:init.headers});
    let result=data,ok=true;
    if(options.onRequest){
      const override=await options.onRequest({url,body,data});
      if(override!==undefined)return {ok:override.ok??true,json:async()=>JSON.parse(JSON.stringify(override.result))};
    }
    if(url==="ui/login"){
      data.auth={phase:"working"};result=data.auth;
    }else if(url==="ui/factor"){
      if(!Number.isInteger(body.method)){ok=false;result={message:"Synthetic method must be an integer"};}
      else {data.auth={phase:"working"};result=data.auth;}
    }else if(url==="ui/select"){
      if(options.failSave){ok=false;result={message:"Fixture save failure"};}
      else {for(const item of data.items)item.enabled=body.ids.includes(item.id);result={saved:true,selected_count:body.ids.length};}
    }else if(url==="ui/rotate-pairing"){
      result={revoked:true,message:"Previous read access revoked."};
    }else if(url==="ui/recovery"){
      data.recovery={phase:"input",kind:"verification_code",label:"SMS verification code",secret:true,choices:[]};
      result=data.recovery;
    }else if(url==="ui/refresh"){
      data.items.find(item=>item.id===body.id).refresh={status:"queued"};
      result={status:"queued",message:"Refresh queued for this item."};
    }
    return {ok,json:async()=>JSON.parse(JSON.stringify(result))};
  };
  window.eval(script);await flush();
  return {window,document:window.document,data,requests,refresh:()=>tick(),close:()=>dom.window.close()};
}
function submit(env,id){env.document.getElementById(id).dispatchEvent(new env.window.Event("submit",{bubbles:true,cancelable:true}));}

test("save gives exact count and leaves no unsaved changes",async()=>{
  const env=await setup();try{
    const check=env.document.querySelector("#choices input");check.checked=true;check.dispatchEvent(new env.window.Event("change"));
    assert.match(env.document.getElementById("selection-state").textContent,/Unsaved/);
    submit(env,"selection");await flush();
    assert.match(env.document.getElementById("selection-feedback").textContent,/Saved: 1 item tracked/);
    assert.equal(env.document.getElementById("selection-feedback").dataset.kind,"success");
    assert.equal(env.document.getElementById("save-selection").disabled,true);
    assert.equal(env.requests.filter(request=>request.url==="ui/select").length,1);
  }finally{env.close();}
});
test("failed save retains edits and gives an error instead of Saved",async()=>{
  const env=await setup({failSave:true});try{
    const check=env.document.querySelector("#choices input");check.checked=true;check.dispatchEvent(new env.window.Event("change"));
    submit(env,"selection");await flush();
    assert.equal(env.document.getElementById("selection-feedback").textContent,"Fixture save failure");
    assert.equal(env.document.getElementById("selection-feedback").dataset.kind,"error");
    assert.equal(env.document.getElementById("save-selection").disabled,false);
    assert.equal(env.document.querySelector("#choices input").checked,true);
  }finally{env.close();}
});
test("background refresh preserves a partially typed SMS code",async()=>{
  const env=await setup();try{
    env.data.recovery={phase:"input",kind:"verification_code",label:"SMS verification code",secret:true,choices:[]};
    await env.refresh();
    const input=env.document.querySelector("#recovery input");input.value="000123";
    await env.refresh();
    assert.equal(env.document.querySelector("#recovery input"),input);
    assert.equal(input.value,"000123");
  }finally{env.close();}
});
test("discovery sends email and password together and clears the password field",async()=>{
  const env=await setup();try{
    const form=env.document.getElementById("discovery-start");
    form.elements.namedItem("email").value="fixture@example.invalid";
    form.elements.namedItem("password").value="synthetic-test-password";
    env.document.getElementById("consent").checked=true;
    submit(env,"discovery-start");await flush();
    const calls=env.requests.filter(request=>request.url==="ui/recovery");
    assert.equal(calls.length,1);
    assert.deepEqual(calls[0].body.credentials,{email:"fixture@example.invalid",password:"synthetic-test-password"});
    assert.equal(calls[0].headers["X-CSRF-Token"],"synthetic-csrf");
    assert.equal(form.elements.namedItem("password").value,"");
    assert.equal(env.document.querySelector("#recovery input").autocomplete,"one-time-code");
    assert.equal(env.document.body.textContent.includes("synthetic-test-password"),false);
  }finally{env.close();}
});
test("valid saved discovery session does not ask for credentials",async()=>{
  const env=await setup();try{
    env.data.setup.discovery_session_saved=true;await env.refresh();
    assert.equal(env.document.getElementById("discovery-credentials").hidden,true);
    env.document.getElementById("consent").checked=true;
    submit(env,"discovery-start");await flush();
    const call=env.requests.find(request=>request.url==="ui/recovery");
    assert.equal(call.body.credentials,undefined);
    assert.equal(call.body.fresh_login,undefined);
  }finally{env.close();}
});
test("per-item refresh queues only the clicked item and shows progress",async()=>{
  const env=await setup({enabled:true});try{
    env.document.querySelector("[data-refresh]").click();await flush();
    const calls=env.requests.filter(request=>request.url==="ui/refresh");
    assert.equal(calls.length,1);assert.equal(calls[0].body.id,"a");
    assert.match(env.document.getElementById("refresh-status-a").textContent,/Queued for the next available worker/);
    assert.equal(env.document.querySelector("[data-refresh]").disabled,true);
    assert.match(env.document.querySelector(".item-status").textContent,/Queued/);
    assert.equal(env.document.getElementById("app-title").textContent,"Retrace Edge");
  }finally{env.close();}
});

test("same-name items have descriptive secondary labels",async()=>{
  const env=await setup();try{
    env.data.items[0]={...env.data.items[0],name:"iPhone",model:"iPhone17,2",model_name:"iPhone 16 Pro Max",paired_at:"2024-01-02"};
    env.data.items[1]={...env.data.items[1],name:"iPhone",model:"iPhone18,2",model_name:"iPhone 17 Pro Max",paired_at:"2025-03-04"};
    await env.refresh();
    const details=[...env.document.querySelectorAll("#choices small")].map(node=>node.textContent);
    assert.match(details[0],/iPhone 16 Pro Max.*Paired 2024-01-02.*ID a/);
    assert.match(details[1],/iPhone 17 Pro Max.*Paired 2025-03-04.*ID b/);
    assert.equal(env.document.querySelectorAll("#choices input").length,2);
  }finally{env.close();}
});
test("legacy channel labels are shown as Edge",async()=>{
  const env=await setup();try{
    env.data.channel="beta";await env.refresh();
    assert.equal(env.document.getElementById("app-title").textContent,"Retrace Edge");
  }finally{env.close();}
});

test("incomplete key search is distinguished from no sighting",async()=>{
  const env=await setup({enabled:true});try{
    env.data.health.status="searching";
    env.data.items[0].refresh={status:"searching"};await env.refresh();
    assert.match(env.document.getElementById("health").textContent,/searching remaining/);
    assert.match(env.document.querySelector(".item-status").textContent,/older key search will continue/);
    assert.equal(env.document.querySelector("[data-refresh]").disabled,false);
  }finally{env.close();}
});

test("pairing renewal requires explicit confirmation and never displays tokens",async()=>{
  const env=await setup();try{
    const form=env.document.getElementById("pairing-security");
    form.dispatchEvent(new env.window.Event("submit",{cancelable:true}));await flush();
    assert.equal(env.requests.filter(call=>call.url==="ui/rotate-pairing").length,0);
    env.document.getElementById("pairing-consent").checked=true;
    form.dispatchEvent(new env.window.Event("submit",{cancelable:true}));await flush();await flush();
    const calls=env.requests.filter(call=>call.url==="ui/rotate-pairing");
    assert.equal(calls.length,1);assert.deepEqual(calls[0].body,{confirm:true});
    assert.match(env.document.getElementById("pairing-status").textContent,/revoked/);
    assert.equal(env.document.getElementById("pairing-consent").checked,false);
  }finally{env.close();}
});

test("shared authentication uses the main form and device-unlock prompt",async()=>{
  const env=await setup();try{
    env.data.setup.shared_auth=true;env.data.auth={phase:"working"};
    env.data.recovery={phase:"input",kind:"device_unlock",choices:[{value:"opaque",label:"Synthetic phone · iPhone"}]};
    await env.refresh();
    assert.equal(env.document.getElementById("discovery-credentials").hidden,true);
    assert.equal(env.document.getElementById("discover").hidden,true);
    assert.match(env.document.getElementById("auth-explanation").textContent,/One Apple sign-in/);
    const passcode=env.document.querySelector("#recovery input");
    assert.equal(passcode.type,"password");passcode.value="synthetic-unlock";
    await env.refresh();assert.equal(passcode.value,"synthetic-unlock");
    submit(env,"recovery");await flush();
    const request=env.requests.find(request=>request.url==="ui/recovery");
    assert.deepEqual(request.body,{action:"answer",choice:"opaque",passcode:"synthetic-unlock"});
    assert.equal(passcode.value,"");
    assert.equal(env.document.body.textContent.includes("synthetic-unlock"),false);
  }finally{env.close();}
});


test("expired shared verification reopens the main sign-in with an explicit reason",async()=>{
  const env=await setup();try{
    env.data.setup.shared_auth=true;env.data.auth={phase:"failed",error:"sign_in_expired"};
    env.data.recovery={phase:"expired"};
    await env.refresh();
    assert.equal(env.document.getElementById("login").hidden,false);
    assert.equal(env.document.getElementById("factor").hidden,true);
    assert.match(env.document.getElementById("login-status").textContent,/verification step expired/);
    assert.match(env.document.getElementById("recovery-status").textContent,/saved tracked items are kept/);
    assert.equal(env.document.getElementById("discovery-credentials").hidden,true);
  }finally{env.close();}
});


test("shared account consent is inside the unified form before Connect and missing consent retains password",async()=>{
  const env=await setup({shared:true,connected:false});try{
    const form=env.document.getElementById("login"),consent=env.document.getElementById("consent"),button=env.document.getElementById("connect-account");
    assert.equal(consent.closest("form"),form);
    assert.ok(consent.compareDocumentPosition(button)&env.window.Node.DOCUMENT_POSITION_FOLLOWING);
    assert.equal(env.document.getElementById("discovery-step").hidden,true);
    assert.equal(env.document.getElementById("discovery-controls").closest("article"),env.document.getElementById("account-step"));
    assert.match(env.document.getElementById("auth-explanation").textContent,/encrypted Find My item keys.*unlock passcode/);
    form.elements.namedItem("email").value="fixture@example.invalid";
    form.elements.namedItem("password").value="synthetic-password";
    submit(env,"login");await flush();
    assert.equal(env.requests.filter(call=>call.url==="ui/login").length,0);
    assert.equal(form.elements.namedItem("password").value,"synthetic-password");
    const feedback=env.document.getElementById("login-status");
    assert.equal(feedback.hidden,false);assert.equal(feedback.dataset.kind,"error");
    assert.match(feedback.textContent,/Allow encrypted item-key recovery/);
    assert.equal(feedback.getAttribute("aria-live"),"polite");
  }finally{env.close();}
});

test("accepted main sign-in clears password and shows pending feedback beside the form",async()=>{
  let release;
  const gate=new Promise(resolve=>{release=resolve;});
  const env=await setup({shared:true,connected:false,onRequest:async({url,data})=>{
    if(url!=="ui/login")return;
    await gate;data.auth={phase:"working"};return {result:data.auth};
  }});try{
    const form=env.document.getElementById("login");
    form.elements.namedItem("email").value="fixture@example.invalid";form.elements.namedItem("password").value="synthetic-password";
    env.document.getElementById("consent").checked=true;
    submit(env,"login");await flush();
    assert.equal(form.elements.namedItem("password").value,"");
    assert.equal(env.document.getElementById("login-status").dataset.kind,"working");
    assert.match(env.document.getElementById("login-status").textContent,/Connecting your Apple account/);
    assert.equal(form.nextElementSibling.id,"login-status");
    assert.equal(env.requests.find(call=>call.url==="ui/login").body.discovery_consent,true);
    release();await flush();await flush();
  }finally{release();env.close();}
});

test("factor method selection and typed code survive asynchronous snapshot polling",async()=>{
  const methods=[{value:0,label:"Trusted device"},{value:1,label:"SMS"}];
  const env=await setup({shared:true,connected:false,auth:{phase:"choose_method",methods}});try{
    const select=env.document.querySelector("#factor select");select.value="1";
    env.data.health.last_poll="2026-11-20T12:00:00Z";await env.refresh();
    assert.equal(env.document.querySelector("#factor select"),select);assert.equal(select.value,"1");
    submit(env,"factor");await flush();await flush();
    assert.equal(env.requests.find(call=>call.url==="ui/factor").body.method,1);
    env.data.auth={phase:"verification_code",method:1};await env.refresh();
    const code=env.document.querySelector("#factor input");code.value="000123";
    await env.refresh();
    assert.equal(env.document.querySelector("#factor input"),code);assert.equal(code.value,"000123");
    env.data.auth={phase:"verification_code",method:1,error:"verification_not_accepted"};await env.refresh();
    assert.equal(env.document.querySelector("#factor input"),code);assert.equal(code.value,"000123");
    assert.match(env.document.getElementById("factor-status").textContent,/did not accept.*sign-in may also have expired/);
    submit(env,"factor");await flush();await flush();
    const submissions=env.requests.filter(call=>call.url==="ui/factor");
    assert.deepEqual(submissions[1].body,{method:1,code:"000123"});assert.equal(code.value,"");
  }finally{env.close();}
});

test("reloaded verification step submits the server method rather than null",async()=>{
  const env=await setup({shared:true,connected:false,auth:{phase:"verification_code",method:1}});try{
    const code=env.document.querySelector("#factor input");code.value="000321";
    submit(env,"factor");await flush();await flush();
    const call=env.requests.find(call=>call.url==="ui/factor");
    assert.deepEqual(call.body,{method:1,code:"000321"});
    assert.equal(env.document.getElementById("factor-status").getAttribute("role"),"status");
    assert.equal(env.document.getElementById("login").hidden,true);
  }finally{env.close();}
});

test("selection and manual refresh errors remain beside their own actions after polling",async()=>{
  const env=await setup({enabled:true,failSave:true,onRequest:async({url})=>{
    if(url==="ui/refresh")return {ok:false,result:{message:"Synthetic refresh rejected"}};
  }});try{
    const check=env.document.querySelector("#choices input");check.checked=false;check.dispatchEvent(new env.window.Event("change"));
    submit(env,"selection");await flush();
    const selection=env.document.getElementById("selection-feedback");
    assert.equal(selection.dataset.kind,"error");assert.match(selection.textContent,/Fixture save failure/);
    assert.equal(selection.closest(".save-bar"),env.document.getElementById("save-selection").parentElement);
    env.document.querySelector("[data-refresh]").click();await flush();
    let status=env.document.getElementById("refresh-status-a");
    assert.equal(status.dataset.kind,"error");assert.match(status.textContent,/Synthetic refresh rejected/);
    await env.refresh();status=env.document.getElementById("refresh-status-a");
    assert.match(status.textContent,/Synthetic refresh rejected/);
    assert.equal(env.document.querySelector("[data-refresh]").nextElementSibling,status);
  }finally{env.close();}
});

test("legacy discovery keeps its separate connection and consent",async()=>{
  const env=await setup();try{
    assert.equal(env.document.getElementById("discovery-step").hidden,false);
    assert.equal(env.document.getElementById("consent").closest("form").id,"discovery-start");
    assert.match(env.document.getElementById("account-title").textContent,/Location access/);
    assert.equal(env.document.getElementById("discovery-controls").closest("article").id,"discovery-step");
  }finally{env.close();}
});


test("missing server method cannot submit a verification code",async()=>{
  const env=await setup({shared:true,connected:false,auth:{phase:"verification_code"}});try{
    assert.equal(env.document.getElementById("factor").hidden,true);
    assert.match(env.document.getElementById("factor-status").textContent,/Restart Apple sign-in/);
    submit(env,"factor");await flush();
    assert.equal(env.requests.filter(call=>call.url==="ui/factor").length,0);
  }finally{env.close();}
});

test("code request refusal keeps selected method and places feedback next to Send",async()=>{
  const methods=[{value:0,label:"Trusted device"},{value:1,label:"SMS"}];
  const env=await setup({shared:true,connected:false,auth:{phase:"choose_method",methods}});try{
    const select=env.document.querySelector("#factor select");select.value="1";
    env.data.auth={phase:"choose_method",methods,error:"code_request_failed"};await env.refresh();
    assert.equal(env.document.querySelector("#factor select"),select);assert.equal(select.value,"1");
    const feedback=env.document.getElementById("factor-status");
    assert.equal(feedback.dataset.kind,"error");assert.match(feedback.textContent,/did not accept the code request/);
    assert.equal(env.document.getElementById("factor").nextElementSibling,feedback);
    assert.equal(env.requests.filter(call=>call.url==="ui/factor").length,0);
  }finally{env.close();}
});

test("selection pending and success feedback stay in the mobile save bar",async()=>{
  let release;const gate=new Promise(resolve=>{release=resolve;});
  const env=await setup({onRequest:async({url,body,data})=>{
    if(url!=="ui/select")return;
    await gate;for(const item of data.items)item.enabled=body.ids.includes(item.id);
    return {result:{saved:true,selected_count:body.ids.length}};
  }});try{
    const check=env.document.querySelector("#choices input");check.checked=true;check.dispatchEvent(new env.window.Event("change"));
    submit(env,"selection");await flush();
    const feedback=env.document.getElementById("selection-feedback");
    assert.equal(feedback.dataset.kind,"working");assert.match(feedback.textContent,/Saving tracking choices/);
    assert.equal(env.document.getElementById("selection").getAttribute("aria-busy"),"true");
    release();await flush();await flush();
    assert.equal(feedback.dataset.kind,"success");assert.match(feedback.textContent,/Saved: 1 item tracked/);
    assert.equal(feedback.closest(".save-bar"),env.document.getElementById("save-selection").parentElement);
  }finally{release();env.close();}
});


test("setup completion stays local across tabs and polling; overview badges show current stages",async()=>{
  const env=await setup({shared:true,enabled:true,auth:{phase:"complete"}});try{
    env.document.querySelector('[data-tab="setup"]').click();
    assert.equal(env.document.getElementById('message').hidden,true);
    assert.match(env.document.getElementById('login-status').textContent,/Apple account connected/);
    env.document.querySelector('[data-tab="overview"]').click();
    assert.equal(env.document.getElementById('setup').hidden,true);
    assert.equal(env.document.getElementById('message').hidden,true);
    await env.refresh();
    assert.equal(env.document.getElementById('message').hidden,true);
    assert.equal(env.document.getElementById('account-badge').textContent,'Account: connected');
    assert.equal(env.document.getElementById('keys-badge').textContent,'Item keys: ready');
    assert.equal(env.document.getElementById('tracking-badge').textContent,'Tracking: 1 item');
    assert.equal(env.document.getElementById('checks-badge').textContent,'Checks: completed');
    assert.doesNotMatch(env.document.getElementById('overview').textContent,/Continue with encrypted item-key recovery/);
  }finally{env.close();}
});

test("badges distinguish verification, key unlock, pending sightings, rate limits and real errors",async()=>{
  const env=await setup({shared:true,connected:false});try{
    env.data.auth={phase:'verification_code',method:0};env.data.recovery={phase:'input',kind:'device_unlock',choices:[]};await env.refresh();
    assert.match(env.document.getElementById('account-badge').textContent,/verification needed/);
    assert.match(env.document.getElementById('keys-badge').textContent,/unlock needed/);
    env.data.auth={phase:'idle'};env.data.setup.locations_connected=true;env.data.items[0].enabled=true;env.data.recovery={phase:'complete'};env.data.health={status:'searching'};await env.refresh();
    assert.equal(env.document.getElementById('checks-badge').textContent,'Checks: searching for sightings');
    assert.equal(env.document.getElementById('checks-badge').dataset.kind,'info');
    env.data.health={status:'error',error_code:'rate_limited'};await env.refresh();
    assert.equal(env.document.getElementById('checks-badge').textContent,'Checks: paused by Apple');
    assert.equal(env.document.getElementById('checks-badge').dataset.kind,'warning');
    env.data.health={status:'reauth_required'};await env.refresh();
    assert.equal(env.document.getElementById('checks-badge').textContent,'Checks: reconnect needed');
    assert.equal(env.document.getElementById('checks-badge').dataset.kind,'error');
    env.data.recovery={phase:'failed',error:'discovery_failed'};env.data.health={status:'ok'};await env.refresh();
    assert.match(env.document.getElementById('keys-badge').textContent,/needs attention/);
  }finally{env.close();}
});

test("unavailable app is shown as an issue and is not masked by switching tabs",async()=>{
  let unavailable=false;
  const env=await setup({onRequest:({url})=>unavailable&&url==='v1/snapshot'?{ok:false,result:{message:'Synthetic app unavailable'}}:undefined});try{
    unavailable=true;await env.refresh();
    assert.equal(env.document.getElementById('checks-badge').textContent,'Checks: app unavailable');
    env.document.querySelector('[data-tab="setup"]').click();
    assert.equal(env.document.getElementById('checks-badge').dataset.kind,'error');
    assert.equal(env.document.getElementById('message').hidden,true);
    unavailable=false;await env.refresh();
    assert.equal(env.document.getElementById('checks-badge').dataset.kind,'info');
  }finally{env.close();}
});

test("local setup failure explains Configuration instead of asking for another Apple sign-in",async()=>{
  const env=await setup({shared:true,connected:false,auth:{phase:"failed",error:"setup_required"}});try{
    assert.match(env.document.getElementById("login-status").textContent,/Configuration tab/);
    assert.match(env.document.getElementById("login-status").textContent,/not a rejected Apple password/);
    assert.equal(env.document.getElementById("account-badge").textContent,"Account: setup required");
    assert.equal(env.document.getElementById("checks-badge").textContent,"Checks: setup needs attention");
    assert.equal(env.document.getElementById("account-badge").dataset.kind,"error");
    env.data.setup.locations_connected=true;await env.refresh();
    assert.equal(env.document.getElementById("account-badge").dataset.kind,"error");
    assert.equal(env.document.getElementById("account-badge").textContent,"Account: setup required");
    assert.equal(env.document.getElementById("message").hidden,true);
  }finally{env.close();}
});

test("Apple pre-password refusal is explained even when an earlier location session exists",async()=>{
  const env=await setup({shared:true,connected:true,auth:{phase:"failed",error:"apple_signin_refused"}});try{
    assert.match(env.document.getElementById("login-status").textContent,/before checking the password/);
    assert.equal(env.document.getElementById("account-badge").textContent,"Account: sign-in needs attention");
    assert.equal(env.document.getElementById("account-badge").dataset.kind,"error");
    assert.equal(env.data.setup.locations_connected,true);
    assert.equal(env.document.getElementById("message").hidden,true);
  }finally{env.close();}
});

test("provider selector exposes candidate availability and locks during verification",async()=>{
  const env=await setup({shared:true,auth:{phase:"idle"}});try{
    const provider=env.document.getElementById("authentication-provider");
    assert.equal(env.document.getElementById("provider-controls").hidden,false);
    assert.equal(provider.value,"apple_music");
    assert.equal(provider.querySelector('option[value="macos"]').disabled,true);
    env.data.auth={phase:"verification_code",method:0};await env.refresh();
    assert.equal(provider.disabled,true);
  }finally{env.close();}
});


test("enabled Mac provider is selectable and sent explicitly without changing default",async()=>{
  const env=await setup({shared:true,auth:{phase:"idle"}});try{
    env.data.setup.authentication_providers=[{id:"apple_music",available:true},{id:"macos",available:true}];
    await env.refresh();
    const provider=env.document.getElementById("authentication-provider");
    assert.equal(provider.value,"apple_music");
    assert.equal(provider.querySelector('option[value="macos"]').disabled,false);
    provider.value="macos";
    env.document.querySelector('[name="email"]').value="fixture@example.invalid";
    env.document.querySelector('[name="password"]').value="synthetic-password";
    env.document.getElementById("consent").checked=true;
    env.document.getElementById("login").dispatchEvent(new env.window.Event("submit",{bubbles:true,cancelable:true}));
    await flush();
    assert.equal(env.requests.find(call=>call.url==="ui/login").body.provider,"macos");
  }finally{env.close();}
});

test("fresh stable selects macOS and requires local consent before clearing credentials",async()=>{
  const env=await setup({shared:true,connected:false,auth:{phase:"idle"}});try{
    env.data.channel="stable";
    env.data.setup.default_authentication_provider="macos";
    env.data.setup.native_component_consent_required=true;
    env.data.setup.authentication_providers=[{id:"apple_music",available:false},{id:"macos",available:true}];
    await env.refresh();
    assert.equal(env.document.getElementById("authentication-provider").value,"macos");
    assert.equal(env.document.getElementById("native-component-notice").hidden,false);
    const form=env.document.getElementById("login");
    form.elements.namedItem("email").value="fixture@example.invalid";
    form.elements.namedItem("password").value="synthetic-password";
    env.document.getElementById("consent").checked=true;
    submit(env,"login");await flush();
    assert.equal(form.elements.namedItem("password").value,"synthetic-password");
    assert.equal(env.requests.filter(r=>r.url==="ui/login").length,0);
    env.document.getElementById("native-component-consent").checked=true;
    submit(env,"login");await flush();
    assert.equal(env.requests.find(r=>r.url==="ui/login").body.native_component_consent,true);
  }finally{env.close();}
});

test("map navigation leaves ingress for native HA without external tile requests",async()=>{
  const env=await setup();try{
    const link=env.document.getElementById("open-native-map");
    assert.equal(link.getAttribute("href"),"/map");
    assert.equal(link.getAttribute("target"),"_top");
    assert.match(env.document.getElementById("native-map").textContent,/Hours to show/);
    assert.match(env.document.getElementById("native-map").textContent,/Stable and Edge/);
    assert.equal(env.document.querySelector("#map-preview"),null);
    assert.equal(env.document.querySelector('[src*="leaflet"], [href*="leaflet"]'),null);
    assert.doesNotMatch(script,/tile\.openstreetmap|L\.map\(/);
    env.document.querySelector('[data-tab="setup"]').click();
    env.document.querySelector('[data-tab="overview"]').click();
    await env.refresh();
    assert.equal(env.document.getElementById("overview").hidden,false);
    assert.equal(env.requests.every(request=>!request.url.startsWith("http")),true);
  }finally{env.close();}
});
