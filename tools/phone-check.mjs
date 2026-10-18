// Emulates a phone-sized viewport over CDP, reports horizontal overflow and saves a screenshot.
// Usage: node phone-check.mjs <cdp-port> <url> <out.png> [width] [height]
import fs from "node:fs";
const [port, url, out, width = "390", height = "900", before = ""] = process.argv.slice(2);
const errors = [];
const targets = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
const page = targets.find((t) => t.type === "page");
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((r) => ws.addEventListener("open", r, { once: true }));
let id = 0;
const pending = new Map();
ws.addEventListener("message", (e) => {
  const msg = JSON.parse(e.data);
  if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id); }
  if (msg.method === "Runtime.exceptionThrown") errors.push(msg.params.exceptionDetails.exception?.description || msg.params.exceptionDetails.text);
  if (msg.method === "Runtime.consoleAPICalled" && msg.params.type === "log" && String(msg.params.args[0]?.value).startsWith("RESULT")) console.log(msg.params.args[0].value);
  if (msg.method === "Runtime.consoleAPICalled" && msg.params.type === "error") errors.push(msg.params.args.map((a) => a.value ?? a.description).join(" "));
});
const send = (method, params = {}) => new Promise((r) => { pending.set(++id, r); ws.send(JSON.stringify({ id, method, params })); });
await send("Runtime.enable");
await send("Emulation.setDeviceMetricsOverride", { width: +width, height: +height, deviceScaleFactor: +width < 800 ? 2 : 1, mobile: +width < 800 });
await send("Network.setCacheDisabled", { cacheDisabled: true });
await send("Page.navigate", { url });
await new Promise((r) => setTimeout(r, 6000));
const res = await send("Runtime.evaluate", {
  returnByValue: true,
  expression: `(() => { const d = document.documentElement; const wide = [...document.querySelectorAll('body *')].filter(el => el.getBoundingClientRect().right > d.clientWidth + 1).slice(0, 8).map(el => el.tagName + (el.id ? '#' + el.id : '') + '.' + el.className + ' right=' + Math.round(el.getBoundingClientRect().right)); return { clientWidth: d.clientWidth, scrollWidth: d.scrollWidth, wide }; })()`,
});
console.log(JSON.stringify({ ...res.result.result.value, errors }, null, 1));
if (before) { const code = before.endsWith(".js") ? fs.readFileSync(before, "utf8") : before; await send("Runtime.evaluate", { expression: code }); await new Promise((r) => setTimeout(r, before.endsWith(".js") ? 8000 : 1500)); }
const shot = await send("Page.captureScreenshot", { format: "png" });
fs.writeFileSync(out, Buffer.from(shot.result.data, "base64"));
ws.close();
