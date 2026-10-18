// Screenshot each shape *while it is being dragged* on the editor paper. Usage: node drag-preview-test.mjs <port> <url> <outdir>
import fs from "node:fs";
const [port, url, outdir] = process.argv.slice(2);
const targets = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
const ws = new WebSocket(targets.find((t) => t.type === "page").webSocketDebuggerUrl);
await new Promise((r) => ws.addEventListener("open", r, { once: true }));
let id = 0; const pending = new Map(); const logs = [];
ws.addEventListener("message", (e) => {
  const m = JSON.parse(e.data);
  if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); }
  if (m.method === "Runtime.exceptionThrown") logs.push("EXC " + (m.params.exceptionDetails.exception?.description || m.params.exceptionDetails.text));
});
const send = (method, params = {}) => new Promise((r) => { pending.set(++id, r); ws.send(JSON.stringify({ id, method, params })); });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const js = async (expr) => (await send("Runtime.evaluate", { expression: expr, returnByValue: true })).result.result.value;
const rect = (sel) => js(`(() => { const r = document.querySelector(${JSON.stringify(sel)}).getBoundingClientRect(); return {x: r.x, y: r.y, w: r.width, h: r.height}; })()`);
const mouse = (type, x, y, buttons = 1) => send("Input.dispatchMouseEvent", { type, x, y, button: "left", buttons, clickCount: 1, pointerType: "mouse" });
await send("Runtime.enable");
await send("Emulation.setDeviceMetricsOverride", { width: 1680, height: 1300, deviceScaleFactor: 1, mobile: false });
await send("Page.navigate", { url });
await sleep(5000);
await js(`localStorage.clear(); window.scrollTo(0, 260)`); await sleep(300);
const shapes = ["circle", "box", "underline", "arrow", "check", "cross", "star", "scribble", "highlight"];
const frames = [];
for (const [i, t] of shapes.entries()) {
  const b = await rect(`#tb-shapes [data-shape="${t}"]`);
  await mouse("mouseMoved", b.x + b.w / 2, b.y + b.h / 2, 0); await mouse("mousePressed", b.x + b.w / 2, b.y + b.h / 2); await mouse("mouseReleased", b.x + b.w / 2, b.y + b.h / 2, 0);
  const ed = await rect("#editor");
  const x0 = ed.x + 120 + (i % 3) * 230, y0 = ed.y + 120 + Math.floor(i / 3) * 120;
  await mouse("mouseMoved", x0, y0, 0); await mouse("mousePressed", x0, y0);
  for (let k = 1; k <= 5; k++) await mouse("mouseMoved", x0 + 30 * k, y0 + (t === "underline" ? 2 : 10 * k));
  await sleep(150);
  const shot = await send("Page.captureScreenshot", { format: "png", clip: { x: x0 - 30, y: y0 - 30 + await js("scrollY"), width: 220, height: 110, scale: 1 } });
  frames.push(`${t}: ${await js(`document.getElementById("editor-draft").innerHTML.slice(0, 18)`)}`);
  fs.writeFileSync(`${outdir}/drag-${t}.png`, Buffer.from(shot.result.data, "base64"));
  await mouse("mouseReleased", x0 + 150, y0 + 50, 0);
  await sleep(200);
}
console.log(frames.join("\n"));
console.log("stored", await js(`Object.values(JSON.parse(localStorage.getItem("handwriter:v3")||"{}").shapes||{}).flat().length`), "LOGS", JSON.stringify(logs));
ws.close();
