(async () => {
  const $ = (id) => document.getElementById(id);
  const wait = (ms) => new Promise((r) => setTimeout(r, ms));
  const ed = $("editor");
  const caretAtEnd = () => { ed.focus(); const r = document.createRange(); r.selectNodeContents(ed); r.collapse(false); getSelection().removeAllRanges(); getSelection().addRange(r); };
  ed.innerHTML = "<p>Table test:</p><p><br></p>";
  caretAtEnd();
  $("tb-table").dispatchEvent(new MouseEvent("mousedown", { bubbles: true }));
  $("tb-table").click();
  document.querySelectorAll("#tp-grid button")[8 * 1 + 2].click();          // 2 rows x 3 columns
  const td = ed.querySelector("td"); td.textContent = "A1";
  const r = document.createRange(); r.selectNodeContents(td); getSelection().removeAllRanges(); getSelection().addRange(r);
  document.dispatchEvent(new Event("selectionchange"));
  await wait(100);
  const tableBarShown = !$("table-bar").hidden;
  document.querySelector('[data-table="row-below"]').click();
  caretAtEnd();
  $("tb-math").dispatchEvent(new MouseEvent("mousedown", { bubbles: true }));
  $("tb-math").click();
  $("math-input").value = "\\frac{a+1}{b} = x^{2} \\Rightarrow \\sqrt{y}";
  $("math-input").dispatchEvent(new Event("input"));
  const mathPreview = $("math-preview").innerHTML;
  $("math-dialog").close("ok");
  await wait(1500);
  document.querySelector('[data-shape="circle"]').click();
  const img = $("preview-img").getBoundingClientRect();
  const at = (fx, fy) => ({ clientX: img.left + img.width * fx, clientY: img.top + img.height * fy, bubbles: true, button: 0, pointerId: 1 });
  $("preview-frame").dispatchEvent(new PointerEvent("pointerdown", at(0.1, 0.07)));
  $("preview-frame").dispatchEvent(new PointerEvent("pointermove", at(0.45, 0.12)));
  $("preview-frame").dispatchEvent(new PointerEvent("pointerup", at(0.45, 0.12)));
  document.querySelector('[data-shape="check"]').click();
  $("preview-frame").dispatchEvent(new PointerEvent("pointerdown", at(0.8, 0.2)));
  $("preview-frame").dispatchEvent(new PointerEvent("pointerup", at(0.8, 0.2)));
  await wait(2500);
  window.__result = { tableBarShown, rows: ed.querySelectorAll("tr").length, cols: ed.querySelector("tr").children.length,
    math: ed.querySelector("[data-tex]")?.dataset.tex, mathPreview: mathPreview.slice(0, 120),
    shapeCount: $("shape-count").textContent, status: $("status").textContent };
  console.log("RESULT " + JSON.stringify(window.__result));
})();
