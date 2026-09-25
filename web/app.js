const $ = (id) => document.getElementById(id);
let id = null;
let timer = null;
let screenTimer = null;
let lastStatus = null;
let tasks = JSON.parse(localStorage.getItem("agi.tasks") || "[]");
const terminal = ["succeeded", "failed", "cancelled"];

function statusLabel(status) {
  return ({
    queued: "في قائمة الانتظار",
    running: "ينفّذ الآن",
    waiting_human: "بانتظار تدخلك",
    succeeded: "اكتملت المهمة",
    failed: "توقفت المهمة",
    cancelled: "أُلغيت المهمة"
  })[status] || status;
}

function saveTasks() {
  localStorage.setItem("agi.tasks", JSON.stringify(tasks.slice(-30)));
}

function renderHistory() {
  const box = $("historyList");
  if (!tasks.length) {
    box.innerHTML = '<div class="empty">لا توجد مهام محلية حتى الآن.</div>';
  } else {
    box.innerHTML = tasks.slice().reverse().map(t =>
      '<button class="list-item" data-task-id="' + t.id + '"><span><strong>' +
      escapeHtml(t.prompt.slice(0, 54)) + '</strong><br><span class="muted">' +
      escapeHtml(t.createdAt) + '</span></span><span class="status-pill ' +
      (t.status === "succeeded" ? "ok" : t.status === "waiting_human" ? "wait" : t.status === "failed" ? "bad" : "wait") +
      '">' + escapeHtml(statusLabel(t.status)) + '</span></button>'
    ).join("");
  }
  $("taskCount").textContent = String(tasks.length);
  $("usageTotal").textContent = "$" + tasks.reduce((a,t)=>a+Number(t.spent_usd||0),0).toFixed(2);
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#039;"}[c]));
}

function setView(name) {
  document.querySelectorAll(".view").forEach(v => v.classList.remove("active"));
  const target = $(name);
  if (target) target.classList.add("active");
  document.querySelectorAll(".nav button").forEach(b => b.classList.toggle("active", b.dataset.view === name));
}

function attachRuntimeView() {
  $("runtimeCard").classList.remove("hidden");
  $("runtimeCard").scrollIntoView({behavior:"smooth", block:"start"});
}

function syncTaskRecord(d) {
  const i = tasks.findIndex(t => t.id === d.id);
  const record = {id:d.id,prompt:$("prompt").value.trim(),status:d.status,spent_usd:d.spent_usd||0,createdAt:new Date().toLocaleString("ar")};
  if (i >= 0) tasks[i] = {...tasks[i], ...record};
  else tasks.push(record);
  saveTasks();
  renderHistory();
}

function draw(d) {
  attachRuntimeView();
  $("status").textContent = statusLabel(d.status);
  const waiting = d.status === "waiting_human";
  const active = d.status === "running" || d.status === "queued";
  $("dot").style.background = d.status === "succeeded" ? "#35d07f" : d.status === "failed" ? "#ff6577" : waiting ? "#ffb84d" : "#4da3ff";
  $("dot").style.boxShadow = "0 0 14px " + $("dot").style.background;
  const steps = Math.max(Number(d.steps || 0), 0);
  $("timeline").innerHTML = steps
    ? Array.from({length: Math.min(steps, 12)}, (_, i) =>
      '<div class="step"><span class="num">' + (i+1) + '</span><div><strong>جولة تنفيذ ' +
      (i+1) + '</strong><br><small>قراءة الحالة، تنفيذ الإجراء، ثم التحقق</small></div></div>'
    ).join("")
    : '<div class="step"><span class="num">•</span><div><strong>تهيئة المتصفح</strong><br><small>إنشاء جلسة معزولة للمهمة</small></div></div>';

  $("handoff").classList.toggle("hidden", !waiting);
  $("humanControls").classList.toggle("hidden", !waiting);
  $("resume").classList.toggle("hidden", !waiting);

  const reason = d.handoff_reason;
  $("handoffText").textContent =
    reason === "authentication" ? "أكمل تسجيل الدخول أو رمز التحقق في جلسة المتصفح، ثم اضغط متابعة." :
    reason === "human_verification" ? "أكمل التحقق البشري المطلوب، ثم اضغط متابعة." :
    "يلزم إجراء بشري قبل الاستمرار.";

  $("result").classList.toggle("hidden", !d.result && !d.error);
  $("result").classList.toggle("error", Boolean(d.error) && !d.result);
  if (d.result || d.error) $("result").textContent = d.result || d.error;

  $("activitySession").textContent = active || waiting ? "نشطة" : d.status === "succeeded" ? "أغلقت" : "متوقفة";
  $("activityCost").textContent = "$" + Number(d.spent_usd||0).toFixed(4);
  $("lastEvent").textContent = d.error ? d.error : d.result ? "اكتملت المهمة وتم استلام النتيجة." : "الجولة الحالية: " + String(d.steps||0);

  syncTaskRecord(d);
  if (active || waiting) startScreen(); else { clearTimeout(screenTimer); screenTimer = null; }
  if (d.status !== lastStatus && d.status === "succeeded") {
    setView("tasksView");
  }
  lastStatus = d.status;
}

async function poll() {
  if (!id) return;
  try {
    const response = await fetch("/v1/tasks/" + id, {cache:"no-store"});
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "تعذر قراءة حالة المهمة");
    draw(data);
    if (!terminal.includes(data.status)) timer = setTimeout(poll, 900);
  } catch (_) {
    timer = setTimeout(poll, 1800);
  }
}

async function refreshScreen() {
  if (!id) return;
  try {
    const response = await fetch("/v1/tasks/" + id + "/screen?t=" + Date.now(), {cache:"no-store"});
    if (!response.ok) throw new Error();
    const blob = await response.blob();
    const old = $("screen").src;
    $("screen").src = URL.createObjectURL(blob);
    $("screenEmpty").classList.add("hidden");
    if (old && old.startsWith("blob:")) URL.revokeObjectURL(old);
  } catch (_) {}
  screenTimer = setTimeout(refreshScreen, 1000);
}

function startScreen() {
  clearTimeout(screenTimer);
  refreshScreen();
}

async function humanAction(action) {
  if (!id) return;
  try {
    const response = await fetch("/v1/tasks/" + id + "/human-input", {
      method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(action)
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "تعذر تنفيذ الإجراء");
    refreshScreen();
  } catch (error) { alert(error.message); }
}

$("screen").addEventListener("click", event => {
  if (!id || $("humanControls").classList.contains("hidden")) return;
  const rect = $("screen").getBoundingClientRect();
  humanAction({
    type:"click",
    x:Math.max(0,Math.min(1000,Math.round((event.clientX-rect.left)/rect.width*1000))),
    y:Math.max(0,Math.min(1000,Math.round((event.clientY-rect.top)/rect.height*1000)))
  });
});

$("humanSend").onclick = () => {
  const text = $("humanText").value.trim();
  if (!text) return;
  humanAction({type:"type",text});
  $("humanText").value = "";
};
$("humanText").addEventListener("keydown", e => { if (e.key === "Enter") { e.preventDefault(); $("humanSend").click(); }});
$("humanBack").onclick = () => humanAction({type:"back"});
$("humanForward").onclick = () => humanAction({type:"forward"});
$("humanScroll").onclick = () => humanAction({type:"scroll",x:500,y:500,delta:600});

$("run").onclick = async () => {
  const prompt = $("prompt").value.trim();
  if (prompt.length < 3) return alert("اكتب مهمة واضحة.");
  $("run").disabled = true; $("run").textContent = "جاري بدء المهمة…";
  try {
    const response = await fetch("/v1/tasks", {
      method:"POST", headers:{"Content-Type":"application/json"},
      body:JSON.stringify({prompt,budget_usd:Number($("budget").value),complexity:"normal"})
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "تعذر إنشاء المهمة");
    id = data.id;
    syncTaskRecord(data);
    draw(data);
    startScreen();
    poll();
  } catch (error) { alert(error.message); }
  finally { $("run").disabled=false; $("run").textContent="بدء التنفيذ ↗"; }
};

$("resume").onclick = async () => {
  if (!id) return;
  $("resume").disabled = true; $("resume").textContent = "جاري الاستئناف…";
  try {
    const response = await fetch("/v1/tasks/" + id + "/resume", {
      method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({confirmed:true})
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "تعذر الاستئناف");
    draw(data); poll();
  } catch (error) { alert(error.message); }
  finally { $("resume").disabled=false; $("resume").textContent="متابعة المهمة"; }
};

$("cancel").onclick = async () => {
  if (!id) return;
  await fetch("/v1/tasks/" + id + "/cancel", {method:"POST"});
  poll();
};

document.querySelectorAll(".nav button").forEach(button => {
  button.addEventListener("click", () => setView(button.dataset.view));
});

document.querySelectorAll(".quick").forEach(button => {
  button.addEventListener("click", () => {
    $("prompt").value = button.dataset.prompt;
    setView("homeView");
    $("prompt").focus();
  });
});

$("upgradeBtn").onclick = () => alert("الاشتراك المدفوع سيُفعّل بعد ربط مزود الدفع والكيان التجاري.");
$("menuBtn").onclick = () => setView("settingsView");
$("billingBtn").onclick = () => alert("الفوترة: الرصيد، الحدود، الفواتير، والعمولات ستظهر هنا.");

$("historyList").addEventListener("click", e => {
  const btn = e.target.closest("[data-task-id]");
  if (!btn) return;
  const found = tasks.find(t => t.id === btn.dataset.taskId);
  if (!found) return;
  $("prompt").value = found.prompt;
  id = found.id;
  setView("homeView");
  poll();
});

renderHistory();
