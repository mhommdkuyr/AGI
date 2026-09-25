const $ = (id) => document.getElementById(id);
let id = null;
let timer = null;
let screenTimer = null;
let lastStatus = null;

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

function draw(d) {
  $("card").classList.remove("hidden");
  $("status").textContent = statusLabel(d.status);
  $("dot").style.background = d.status === "succeeded" ? "#35d07f" :
    d.status === "failed" ? "#ff6577" : d.status === "waiting_human" ? "#ffb84d" : "#4da3ff";
  $("dot").style.boxShadow = "0 0 14px " + $("dot").style.background;

  const steps = Math.max(Number(d.steps || 0), 0);
  $("timeline").innerHTML = steps
    ? Array.from({length: Math.min(steps, 8)}, (_, i) =>
        '<div class="step"><span class="num">' + (i + 1) +
        '</span><div><strong>جولة تنفيذ</strong><br><small>مراقبة الصفحة واتخاذ الإجراء التالي</small></div></div>'
      ).join("")
    : '<div class="step"><span class="num">•</span><div><strong>تهيئة المتصفح</strong><br><small>إنشاء جلسة معزولة للمهمة</small></div></div>';

  const waiting = d.status === "waiting_human";
  $("handoff").classList.toggle("hidden", !waiting);
  $("resume").classList.toggle("hidden", !waiting);

  if (d.handoff_reason === "authentication") {
    $("handoffText").textContent = "أكمل تسجيل الدخول أو رمز التحقق في جلسة المتصفح، ثم اضغط متابعة.";
  } else if (d.handoff_reason === "human_verification") {
    $("handoffText").textContent = "أكمل التحقق البشري المطلوب، ثم اضغط متابعة.";
  } else if (d.handoff_reason) {
    $("handoffText").textContent = "يلزم إجراء بشري قبل الاستمرار.";
  }

  if (d.result) {
    $("result").classList.remove("hidden");
    $("result").textContent = d.result;
  } else {
    $("result").classList.add("hidden");
  }

  if (d.error) {
    $("result").classList.remove("hidden");
    $("result").classList.add("error");
    $("result").textContent = d.error;
  } else {
    $("result").classList.remove("error");
  }

  if (d.status !== lastStatus && d.status === "running") {
    startScreen();
  }
  lastStatus = d.status;
}

async function poll() {
  if (!id) return;
  try {
    const response = await fetch('/v1/tasks/' + id, {cache: "no-store"});
    const data = await response.json();
    draw(data);
    if (!terminal.includes(data.status)) timer = setTimeout(poll, 900);
  } catch (_) {
    timer = setTimeout(poll, 1800);
  }
}

async function refreshScreen() {
  if (!id) return;
  const image = $("screen");
  try {
    const response = await fetch('/v1/tasks/' + id + '/screen?t=' + Date.now(), {cache: "no-store"});
    if (!response.ok) throw new Error();
    const blob = await response.blob();
    image.src = URL.createObjectURL(blob);
    $("screenEmpty").classList.add("hidden");
  } catch (_) {}
  screenTimer = setTimeout(refreshScreen, 900);
}

function startScreen() {
  clearTimeout(screenTimer);
  refreshScreen();
}

$("run").onclick = async () => {
  const prompt = $("prompt").value.trim();
  if (prompt.length < 3) return alert("اكتب مهمة واضحة.");
  $("run").disabled = true;
  $("run").textContent = "جاري بدء المهمة…";
  try {
    const response = await fetch("/v1/tasks", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({prompt, budget_usd: Number($("budget").value)})
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "تعذر إنشاء المهمة");
    id = data.id;
    draw(data);
    startScreen();
    poll();
  } catch (error) {
    alert(error.message);
  } finally {
    $("run").disabled = false;
    $("run").textContent = "بدء التنفيذ ↗";
  }
};

$("resume").onclick = async () => {
  if (!id) return;
  $("resume").disabled = true;
  $("resume").textContent = "جاري الاستئناف…";
  try {
    const response = await fetch('/v1/tasks/' + id + '/resume', {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({confirmed: true})
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "تعذر الاستئناف");
    draw(data);
    poll();
  } catch (error) {
    alert(error.message);
  } finally {
    $("resume").disabled = false;
    $("resume").textContent = "متابعة المهمة";
  }
};

$("cancel").onclick = async () => {
  if (!id) return;
  await fetch('/v1/tasks/' + id + '/cancel', {method: "POST"});
  poll();
};
