const $=id=>document.getElementById(id);let id=null,timer=null;
function draw(d){$("card").hidden=false;$("status").textContent=d.status;$("details").textContent=JSON.stringify(d,null,2);$("handoff").hidden=d.status!=="waiting_human";$("resume").hidden=d.status!=="waiting_human";}
async function poll(){if(!id)return;const d=await fetch(`/v1/tasks/${id}`).then(r=>r.json());draw(d);if(!["succeeded","failed","cancelled"].includes(d.status))timer=setTimeout(poll,1200);}
$("run").onclick=async()=>{const prompt=$("prompt").value.trim();if(prompt.length<3)return alert("أدخل مهمة واضحة.");const d=await fetch("/v1/tasks",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({prompt,budget_usd:Number($("budget").value)})}).then(r=>r.json());id=d.id;draw(d);poll();};
$("resume").onclick=async()=>{const d=await fetch(`/v1/tasks/${id}/resume`,{method:"POST"}).then(r=>r.json());draw(d);poll();};
