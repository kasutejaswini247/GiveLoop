const CATS=["Books","Clothes","School Supplies","Electronics","Furniture","Toys","Kitchen Items","Household Items","Medical Support Items","Other"];
const CONDS=["New","Like New","Good","Usable"];
const ICON={"Books":"📚","Clothes":"👕","School Supplies":"🎒","Electronics":"💻","Furniture":"🪑","Toys":"🧸","Kitchen Items":"🍳","Household Items":"🏠","Medical Support Items":"🩺","Other":"🎁"};
let user=null;
const $=s=>document.querySelector(s);
const esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const opts=(list,sel,all)=>(all?`<option value="">${all}</option>`:"")+list.map(o=>`<option ${o==sel?"selected":""}>${o}</option>`).join("");
const pill=s=>`<span class="pill ${String(s).toLowerCase()}">${esc(s)}</span>`;
const fmt=d=>(d||"").slice(0,10);

async function api(url,method="GET",body){
  const r=await fetch(url,{method,headers:{"Content-Type":"application/json"},body:body?JSON.stringify(body):undefined});
  let d={};try{d=await r.json()}catch(e){}
  if(!r.ok)throw new Error(d.error||"Something went wrong.");
  return d;
}
function toast(m,bad){const t=$("#toast");t.textContent=m;t.className="show"+(bad?" bad":"");clearTimeout(t.h);t.h=setTimeout(()=>t.className="",3200)}
async function act(fn,after){try{const d=await fn();if(d&&d.message)toast(d.message);if(after)await after(d)}catch(e){toast(e.message,true)}}
function go(h){location.hash=h}

function life(status){
  const steps=["Available","Requested","Accepted","Matched","Completed"];
  const i=steps.indexOf(status);
  return `<div class="life">${steps.map((s,k)=>`<span class="${k<=i?"on":""}">${s}</span>`).join("→")}</div>`;
}
function renderNav(){
  const a=(h,t,c="")=>`<a href="#${h}" class="${c}" onclick="$('#nav').classList.remove('open')">${t}</a>`;
  let h=a("home","Home")+a("how","How It Works")+a("browse","Browse Donations")+a("needs","Active Needs")+a("about","About");
  if(user){h+=a(user.role=="admin"?"admin":"dashboard","Dashboard")+`<a href="#" onclick="logout();return false">Logout (${esc(user.name.split(" ")[0])})</a>`}
  else h+=a("login","Login")+a("register","Register","cta");
  $("#nav").innerHTML=h;
}
async function logout(){await api("/api/logout","POST");user=null;renderNav();go("home");toast("You have been logged out.")}
function need(roles){
  if(!user){toast("Please log in first.",true);go("login");return false}
  if(roles&&!roles.includes(user.role)){toast("You are not allowed to open that page.",true);go("home");return false}
  return true;
}

/* ---------- pages ---------- */
const steps=()=>`<div class="grid">${[["List What You Have","Donors add useful items they no longer need."],["Tell Us What Is Needed","Recipients and organizations post their requirements."],["Smart Matching","GiveLoop compares donations with real needs."],["Complete the GiveLoop","Connect, donate and give the item a new purpose."]].map((s,i)=>`<div class="card step"><div class="num">${i+1}</div><h3>${s[0]}</h3><p class="meta">${s[1]}</p></div>`).join("")}</div>
<div class="flow" style="margin-top:22px"><b>DONATE</b><span class="arrow">→</span><b>MATCH</b><span class="arrow">→</span><b>CONNECT</b><span class="arrow">→</span><b>COMPLETE</b></div>`;

async function home(){
  const s=await api("/api/stats");
  const boxes=[["Donations",s.donations],["Active Needs",s.needs],["Successful Matches",s.matches],["Completed Donations",s.completed]];
  $("#app").innerHTML=`
  <section class="hero"><div class="hero-in"><div>
    <h1>Give What You Have.<br>Complete What Someone Needs.</h1>
    <p class="sub">GiveLoop intelligently connects useful donations with people and organizations that need them.</p>
    <a class="btn" href="#donate">Donate an Item</a><a class="btn alt" href="#needs">Find What You Need</a>
    <p class="meta"><b>GiveLoop does not simply list donations. It intelligently connects available resources with real-world needs.</b></p></div>
    <div class="flow"><div class="node"><span>🤲</span>Donor</div><span class="arrow">→</span><div class="node" style="background:var(--sage)"><span>🔄</span><b>GiveLoop</b><div class="meta">Smart match</div></div><span class="arrow">→</span><div class="node"><span>🏫</span>Recipient</div></div>
  </div></section>
  <div class="wrap"><div class="grid">${boxes.map(b=>`<div class="card stat"><div class="n">${b[1]}</div>${b[0]}</div>`).join("")}</div></div>
  <div class="band"><div class="wrap"><h2 class="center">How GiveLoop Works</h2>${steps()}</div></div>
  <div class="wrap"><h2 class="center">Why GiveLoop?</h2><div class="grid">${[["♻️","Reduce Waste","Keep usable items out of landfills."],["🎯","Reach the Right People","Connect donations with actual requirements."],["⏱️","Save Time","Find suitable matches instead of searching manually."],["🌱","Create Impact","Turn unused resources into meaningful support."]].map(c=>`<div class="card center"><div style="font-size:2rem">${c[0]}</div><h3>${c[1]}</h3><p class="meta">${c[2]}</p></div>`).join("")}</div></div>`;
}
function how(){$("#app").innerHTML=`<div class="wrap"><h2 class="center">How GiveLoop Works</h2><p class="center sub">Donate → Match → Connect → Complete</p>${steps()}<h3 class="center" style="margin-top:34px">Donation lifecycle</h3><div class="center">${life("Completed")}</div><p class="center meta">Smart score (0–100): category 30 · item similarity 25 · location 20 · condition 10 · quantity 10 · urgency 5</p></div>`}
function about(){$("#app").innerHTML=`<div class="wrap"><h2>About GiveLoop</h2><div class="card"><p>Many people hold usable items they no longer need, while schools, NGOs and families need exactly those items. They rarely find each other.</p><p><b>GiveLoop does not simply list donations. It intelligently connects available resources with real-world needs.</b> Donors list items, recipients post requirements, and GiveLoop scores every pair so the best matches rise to the top, including partial matches where several donors together fulfil one requirement.</p><p class="meta">Where Giving Meets Need.</p></div></div>`}

async function needs(){
  const rows=await api("/api/requirements");
  $("#app").innerHTML=`<div class="wrap"><h2>Active Needs</h2><p class="sub">What people and organizations need right now.</p><div class="grid">${rows.map(r=>`<div class="card"><p>${pill(r.urgency)} <span class="meta">${r.urgency=="High"?"URGENT NEED":"NEED"}</span></p><h3>${r.quantity_needed} ${esc(r.item_name)}</h3><p class="meta">Needed by: <b>${esc(r.recipient_name)}</b><br>Area: ${esc(r.area)}<br>Purpose: ${esc(r.purpose||"—")}</p><div class="bar"><i style="width:${Math.min(100,r.fulfilled*100/r.quantity_needed)}%"></i></div><p class="meta">${r.fulfilled} of ${r.quantity_needed} fulfilled</p><a class="btn sm" href="#browse?q=${encodeURIComponent(r.item_name)}">Find Matching Donations</a></div>`).join("")||'<div class="empty">No active needs right now.</div>'}</div></div>`;
}

async function browse(){
  const p=new URLSearchParams((location.hash.split("?")[1])||"");
  $("#app").innerHTML=`<div class="wrap"><h2>Browse Donations</h2><div class="filters"><input id="fq" placeholder="Search item name…" value="${esc(p.get("q")||"")}"><select id="fc">${opts(CATS,"","All categories")}</select><input id="fl" placeholder="Location"><select id="fo">${opts(CONDS,"","Any condition")}</select></div><div id="list" class="grid"></div></div>`;
  const load=async()=>{
    const qs=new URLSearchParams({q:$("#fq").value,category:$("#fc").value,location:$("#fl").value,condition:$("#fo").value});
    const rows=await api("/api/donations?"+qs);
    $("#list").innerHTML=rows.map(d=>`<div class="card"><div class="thumb">${d.image?`<img src="${esc(d.image)}" alt="" onerror="this.parentNode.textContent='${ICON[d.category]||"🎁"}'">`:ICON[d.category]||"🎁"}</div><h3>${esc(d.item_name)}</h3><p class="meta">${esc(d.category)} · Qty ${d.quantity} · ${esc(d.condition)}<br>📍 ${esc(d.area)}<br>Availability: ${pill(d.status)}</p><button class="btn sm" onclick="findMatch()">Find Match</button>${user&&user.role=="recipient"&&d.status=="Available"?`<button class="btn sm alt" onclick="reqDon(${d.id})">Request</button>`:""}</div>`).join("")||'<div class="empty">No donations found.</div>';
  };
  ["fq","fl"].forEach(i=>$("#"+i).addEventListener("input",load));["fc","fo"].forEach(i=>$("#"+i).addEventListener("change",load));
  load();
}
function findMatch(){if(!user){toast("Please log in to see smart matches.",true);return go("login")}go(user.role=="admin"?"admin":"matches")}
function reqDon(id,rid){act(()=>api("/api/requests","POST",{donation_id:id,requirement_id:rid}),()=>route())}

function authForm(kind){
  const reg=kind=="register";
  $("#app").innerHTML=`<div class="wrap"><form class="card" id="f"><h2>${reg?"Create your account":"Welcome back"}</h2>
  ${reg?`<label>Full Name</label><input name="name" required>`:""}<label>Username</label><input name="username" required>
  <label>Password</label><input name="password" type="password" required>
  ${reg?`<div class="two"><div><label>Phone Number</label><input name="phone" required></div><div><label>Area / Location</label><input name="area" required></div></div><label>User Role</label><select name="role"><option value="donor">Donor</option><option value="recipient">Recipient</option></select>`:""}
  <p><button class="btn">${reg?"Register":"Login"}</button><a class="btn alt" href="#${reg?"login":"register"}">${reg?"I have an account":"Create Account"}</a></p>
  ${reg?"":'<p class="meta">Demo: admin/admin123 · donor rahul/demo123 · recipient education/demo123</p>'}</form></div>`;
  $("#f").onsubmit=e=>{e.preventDefault();const b=Object.fromEntries(new FormData(e.target));
    act(()=>api(reg?"/api/register":"/api/login","POST",b),d=>{if(reg)go("login");else{user=d.user;renderNav();toast("Welcome, "+user.name+"!");go(user.role=="admin"?"admin":"dashboard")}})};
}
const login=()=>authForm("login"),register=()=>authForm("register");

function itemForm(kind){
  const don=kind=="donate";if(!need([don?"donor":"recipient"]))return;
  $("#app").innerHTML=`<div class="wrap"><form class="card" id="f"><h2>${don?"Donate an Item":"Create Requirement"}</h2>
  <label>${don?"Item Name":"Required Item"}</label><input name="item_name" required placeholder="e.g. School Bags">
  <div class="two"><div><label>Category</label><select name="category">${opts(CATS)}</select></div>
  <div><label>${don?"Quantity":"Quantity Needed"}</label><input name="${don?"quantity":"quantity_needed"}" type="number" min="1" required></div>
  <div><label>${don?"Condition":"Minimum Condition Required"}</label><select name="${don?"condition":"condition_required"}">${opts(CONDS,"Good")}</select></div>
  <div><label>Area / Location</label><input name="area" required placeholder="e.g. Hyderabad"></div></div>
  ${don?`<label>Image URL (optional)</label><input name="image" type="url"><label>Purpose / Notes</label><input name="notes">`:`<label>Urgency</label><select name="urgency">${opts(["Low","Medium","High"],"Medium")}</select><label>Purpose</label><input name="purpose">`}
  <label>Description</label><textarea name="description" rows="3"></textarea>
  <p><button class="btn">${don?"Add Donation":"Post Requirement"}</button><a class="btn alt" href="#dashboard">Cancel</a></p></form></div>`;
  $("#f").onsubmit=e=>{e.preventDefault();act(()=>api(don?"/api/donations":"/api/requirements","POST",Object.fromEntries(new FormData(e.target))),()=>go(don?"matches":"matches"))};
}
const donate=()=>itemForm("donate"),createNeed=()=>itemForm("need");

async function dashboard(){
  if(!need(["donor","recipient"]))return;
  if(user.role=="admin")return go("admin");
  const [d,reqs]=await Promise.all([api("/api/dashboard"),api("/api/requests")]);
  const don=user.role=="donor";
  const rows=d.items.map(i=>don?`<tr><td>${esc(i.item_name)}</td><td>${esc(i.category)}</td><td>${i.quantity}</td><td>${esc(i.condition)}</td><td>${esc(i.area)}</td><td>${pill(i.status)}</td><td>${fmt(i.created_at)}</td></tr>`
    :`<tr><td>${esc(i.item_name)}</td><td>${esc(i.category)}</td><td>${i.fulfilled} / ${i.quantity_needed}</td><td>${esc(i.condition_required)}</td><td>${esc(i.area)}</td><td>${pill(i.urgency)}</td><td>${pill(i.status)}</td><td>${fmt(i.created_at)}</td></tr>`).join("");
  const rr=reqs.map(r=>`<tr><td>${esc(r.item_name)} (${r.quantity})</td><td>${esc(don?r.recipient_name:r.donor_name)}</td><td>${pill(r.status)}${life(r.status=="Requested"?"Requested":r.status=="Accepted"?"Accepted":r.status=="Completed"?"Completed":"")}</td><td>${don&&r.status=="Requested"?`<button class="btn sm" onclick="decide(${r.id},'accept')">Accept</button><button class="btn sm red" onclick="decide(${r.id},'reject')">Reject</button>`:""}${r.status=="Accepted"?`<button class="btn sm" onclick="finish(${r.donation_id})">Mark Completed</button>`:""}</td></tr>`).join("");
  $("#app").innerHTML=`<div class="wrap"><h2>Welcome back, ${esc(user.name)}</h2><p class="sub">${don?"Your donations, matched with real needs.":"Your requirements, matched with real donations."}</p>
  <div class="grid">${d.stats.map(s=>`<div class="card stat"><div class="n">${s[1]}</div>${s[0]}</div>`).join("")}</div>
  <p style="margin-top:18px">${don?'<a class="btn" href="#donate">+ Donate an Item</a>':'<a class="btn" href="#create-need">+ Create Requirement</a>'}<a class="btn alt" href="#matches">View Matches</a><a class="btn alt" href="#" onclick="document.getElementById('mine').scrollIntoView({behavior:'smooth'});return false">${don?"My Donations":"My Requirements"}</a></p>
  <h3 id="mine" style="margin-top:26px">${don?"My Donations":"My Requirements"}</h3><div class="table-wrap">${rows?`<table><tr>${don?"<th>Item<th>Category<th>Quantity<th>Condition<th>Area<th>Status<th>Date":"<th>Item<th>Category<th>Fulfilled<th>Condition<th>Area<th>Urgency<th>Status<th>Date"}</tr>${rows}</table>`:'<div class="empty">Nothing here yet.</div>'}</div>
  <h3>${don?"Donation Requests":"My Requests"}</h3><div class="table-wrap">${rr?`<table><tr><th>Item<th>${don?"Requested by":"Donor"}<th>Status<th>Action</tr>${rr}</table>`:'<div class="empty">No requests yet.</div>'}</div></div>`;
}
const decide=(id,w)=>act(()=>api(`/api/requests/${id}/${w}`,"PUT"),()=>route());
const finish=id=>act(()=>api(`/api/donations/${id}/complete`,"PUT"),()=>route());

async function matches(){
  if(!need(["donor","recipient"]))return;
  const gs=await api("/api/my-matches"),don=user.role=="donor";
  $("#app").innerHTML=`<div class="wrap"><h2>Smart Matches</h2><p class="sub">Ranked by GiveLoop's 0–100 match score. Only matches of 60% and above are shown.</p>
  ${gs.map(g=>`<div class="card" style="margin:18px 0"><h3>${esc(g.title)} <span class="meta">· ${esc(g.area)}</span> ${pill(g.status)}</h3>
  ${don?"":`<div class="bar"><i style="width:${Math.min(100,g.fulfilled*100/g.needed)}%"></i></div><p class="meta">${g.fulfilled} / ${g.needed} fulfilled ${g.status=="Fulfilled"?"· Requirement Fulfilled ✅":""}</p>`}
  <div class="grid">${g.matches.map(m=>`<div class="card match"><div class="score">${m.score}% MATCH</div><b>${esc(m.label)}</b><h3>${esc(m.item_name)}</h3>
  <p class="meta">${don?"Needed by":"Donor"}: ${esc(m.party)}<br>Donation Available: ${m.donation_qty} · Requirement: ${m.need_qty}<br>Category: ${esc(m.category)} · Area: ${esc(m.area)} · Condition: ${esc(m.condition)}</p>
  <p><b>${Math.min(m.donation_qty,m.need_qty)} of ${m.need_qty} required items available.</b></p><b class="meta">WHY THIS MATCH?</b><ul class="why">${m.why.map(w=>`<li>${esc(w)}</li>`).join("")}</ul>
  ${don?"":m.already_requested?'<span class="pill requested">Already requested</span>':m.donation_status!="Available"?'<span class="pill requested">Requested by someone</span>':`<button class="btn sm" onclick="reqDon(${m.donation_id},${m.requirement_id})">Request Donation</button>`}</div>`).join("")||'<div class="empty" style="grid-column:1/-1">No suitable matches found yet.</div>'}</div></div>`).join("")||`<div class="card empty">${don?"Add a donation":"Create a requirement"} to see smart matches.</div>`}</div>`;
}

const ADMIN_COLS={users:["id","name","username","phone","area","role"],donations:["id","item_name","category","quantity","condition","area","status","donor"],requirements:["id","item_name","category","quantity_needed","area","urgency","status","recipient"],matches:["id","donation","requirement","score","status"]};
async function admin(){
  if(!need(["admin"]))return;
  const st=await api("/api/admin/statistics");
  let h=`<div class="wrap"><h2>Admin Dashboard</h2><div class="grid">${Object.entries(st).map(([k,v])=>`<div class="card stat"><div class="n">${v}</div>${k}</div>`).join("")}</div>`;
  for(const t of Object.keys(ADMIN_COLS)){
    const {rows,statuses}=await api("/api/admin/"+t),cols=ADMIN_COLS[t];
    h+=`<h3 style="margin-top:26px;text-transform:capitalize">${t}</h3><div class="table-wrap">${rows.length?`<table><tr>${cols.map(c=>`<th>${c.replace("_"," ")}`).join("")}<th>Actions</tr>${rows.map(r=>`<tr>${cols.map(c=>`<td>${esc(r[c])}</td>`).join("")}<td>${statuses.length?`<select onchange="setStatus('${t}',${r.id},this.value)">${opts(statuses,r.status)}</select> `:""}${r.role=="admin"?"":`<button class="btn sm red" onclick="removeRec('${t}',${r.id})">Remove</button>`}</td></tr>`).join("")}</table>`:'<div class="empty">No records.</div>'}</div>`;
  }
  $("#app").innerHTML=h+"</div>";
}
const setStatus=(t,id,s)=>act(()=>api(`/api/admin/${t}/${id}/status`,"PUT",{status:s}),()=>route());
const removeRec=(t,id)=>{if(confirm("Are you sure you want to remove this record? This cannot be undone."))act(()=>api(`/api/admin/${t}/${id}`,"DELETE"),()=>route())};

/* ---------- router ---------- */
const routes={home,how,about,needs,browse,login,register,donate,"create-need":createNeed,dashboard,matches,admin};
async function route(){
  const h=(location.hash||"#home").slice(1).split("?")[0];
  document.querySelectorAll("nav a").forEach(a=>a.classList.toggle("on",a.getAttribute("href")=="#"+h));
  try{await (routes[h]||home)()}catch(e){toast(e.message,true)}
  window.scrollTo(0,0);
}
window.addEventListener("hashchange",route);
(async()=>{try{user=(await api("/api/me")).user}catch(e){}renderNav();route()})();
