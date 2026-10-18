// Real mouse input: place shapes on the big editor paper. Usage: node editor-shapes-test.mjs <port> <url> <out.png>
import fs from "node:fs";
const [port, url, out] = process.argv.slice(2);
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
const js = async (expr) => (await send("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true })).result.result.value;
const rect = (sel) => js(`(() => { const r = document.querySelector(${JSON.stringify(sel)}).getBoundingClientRect(); return {x: r.x, y: r.y, w: r.width, h: r.height}; })()`);
const mouse = (type, x, y, buttons = 1) => send("Input.dispatchMouseEvent", { type, x, y, button: "left", buttons, clickCount: 1, pointerType: "mouse" });
const click = async (x, y) => { await mouse("mouseMoved", x, y, 0); await mouse("mousePressed", x, y); await mouse("mouseReleased", x, y, 0); };
const clickSel = async (sel) => { const r = await rect(sel); await click(r.x + r.w / 2, r.y + r.h / 2); };
await send("Runtime.enable");
await send("Emulation.setDeviceMetricsOverride", { width: 1680, height: 1300, deviceScaleFactor: 1, mobile: false });
await send("Page.navigate", { url });
await sleep(5000);
await js(`window.scrollTo(0, 260)`); await sleep(300);
await clickSel('#tb-shapes [data-shape="circle"]');
await sleep(200);
const banner = await js(`document.getElementById("editor-status").textContent`);
const ed = await rect("#editor");
await mouse("mouseMoved", ed.x + ed.w * 0.25, ed.y + 250, 0);
await mouse("mousePressed", ed.x + ed.w * 0.25, ed.y + 250);
for (let i = 1; i <= 6; i++) await mouse("mouseMoved", ed.x + ed.w * (0.25 + 0.05 * i), ed.y + 250 + 6 * i);
await mouse("mouseReleased", ed.x + ed.w * 0.55, ed.y + 286, 0);
await sleep(300);
await clickSel('#tb-shapes [data-shape="check"]');
await click(ed.x + ed.w * 0.8, ed.y + 330);
await sleep(300);
await send("Input.dispatchKeyEvent", { type: "keyDown", key: "Escape", code: "Escape", windowsVirtualKeyCode: 27 });
await sleep(2500);
const result = await js(`JSON.stringify({ banner: ${JSON.stringify(banner)}, stored: Object.values(JSON.parse(localStorage.getItem("handwriter:v3")||"{}").shapes||{}).flat().map(s => s.type),
  editorSvg: document.getElementById("editor-shapes").children.length, placingAfterEsc: !document.getElementById("editor-place").hidden,
  hint: document.getElementById("shape-hint").textContent })`);
console.log("RESULT", result);
// after Esc, typing must work again
await clickSel("#editor"); await send("Input.insertText", { text: " typed-after" }); await sleep(300);
console.log("TYPING", await js(`document.getElementById("editor").textContent.includes("typed-after")`));
const shot = await send("Page.captureScreenshot", { format: "png" });
fs.writeFileSync(out, Buffer.from(shot.result.data, "base64"));
console.log("LOGS", JSON.stringify(logs));
ws.close();
