// Drives the page with real (trusted) mouse input over CDP, like a person would.
// Usage: node real-input.mjs <cdp-port> <url>
const [port, url] = process.argv.slice(2);
const targets = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
const ws = new WebSocket(targets.find((t) => t.type === "page").webSocketDebuggerUrl);
await new Promise((r) => ws.addEventListener("open", r, { once: true }));
let id = 0; const pending = new Map(); const logs = [];
ws.addEventListener("message", (e) => {
  const m = JSON.parse(e.data);
  if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); }
  if (m.method === "Runtime.exceptionThrown") logs.push("EXC " + (m.params.exceptionDetails.exception?.description || m.params.exceptionDetails.text));
  if (m.method === "Runtime.consoleAPICalled") logs.push(m.params.type + " " + m.params.args.map((a) => a.value ?? a.description).join(" "));
});
const send = (method, params = {}) => new Promise((r) => { pending.set(++id, r); ws.send(JSON.stringify({ id, method, params })); });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const js = async (expr) => (await send("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true })).result.result.value;
const rect = (sel) => js(`(() => { const r = document.querySelector(${JSON.stringify(sel)}).getBoundingClientRect(); return {x: r.x, y: r.y, w: r.width, h: r.height}; })()`);
const mouse = (type, x, y, extra = {}) => send("Input.dispatchMouseEvent", { type, x, y, button: "left", buttons: type === "mouseReleased" ? 0 : 1, clickCount: 1, pointerType: "mouse", ...extra });
async function click(x, y) { await mouse("mouseMoved", x, y, { buttons: 0 }); await mouse("mousePressed", x, y); await mouse("mouseReleased", x, y); }
async function clickSel(sel) { await js(`document.querySelector(${JSON.stringify(sel)}).scrollIntoView({block: "center"})`); await sleep(200); const r = await rect(sel); await click(r.x + r.w / 2, r.y + r.h / 2); }

await send("Runtime.enable");
await send("Emulation.setDeviceMetricsOverride", { width: 1680, height: 1300, deviceScaleFactor: 1, mobile: false });
await send("Page.navigate", { url });
await sleep(5000);

// 1) Shapes: pick circle, drag on the preview, then pick tick and click.
await clickSel('[data-shape="circle"]');
await js(`document.getElementById("preview-frame").scrollIntoView({block: "center"})`); await sleep(300);
let f = await rect("#preview-img");
await mouse("mouseMoved", f.x + f.w * 0.1, f.y + f.h * 0.07, { buttons: 0 });
await mouse("mousePressed", f.x + f.w * 0.1, f.y + f.h * 0.07);
for (let i = 1; i <= 5; i++) await mouse("mouseMoved", f.x + f.w * (0.1 + 0.07 * i), f.y + f.h * (0.07 + 0.01 * i));
await mouse("mouseReleased", f.x + f.w * 0.45, f.y + f.h * 0.12);
await sleep(300);
await clickSel('[data-shape="check"]');
f = await rect("#preview-img");
await click(f.x + f.w * 0.8, f.y + f.h * 0.3);
await sleep(2500);
console.log("SHAPES", await js(`JSON.stringify({count: document.getElementById("shape-count").textContent, placing: document.getElementById("preview-frame").classList.contains("placing"), status: document.getElementById("status").textContent})`));

// 2) Text colour: select a word in the editor, then use the toolbar colour.
await js(`(() => { const ed = document.getElementById("editor"); const t = ed.querySelector("li b")?.firstChild || ed.querySelector("p").firstChild; const r = document.createRange(); r.selectNodeContents(t); const s = getSelection(); s.removeAllRanges(); s.addRange(r); ed.focus(); })()`);
await clickSel(".tb-color");   // opening the native picker moves focus away from the editor
await sleep(300);
await send("Input.dispatchKeyEvent", { type: "keyDown", key: "Escape", code: "Escape", windowsVirtualKeyCode: 27 });
await js(`(() => { const c = document.getElementById("tb-color"); c.value = "#a3202b"; c.dispatchEvent(new Event("input", {bubbles: true})); c.dispatchEvent(new Event("change", {bubbles: true})); })()`);
await sleep(300);
console.log("COLOR", await js(`(() => { const hits = [...document.getElementById("editor").querySelectorAll("[style*=color], font[color]")].map(e => e.outerHTML.slice(0, 90)); return JSON.stringify(hits); })()`));
console.log("LOGS", JSON.stringify(logs));
ws.close();
