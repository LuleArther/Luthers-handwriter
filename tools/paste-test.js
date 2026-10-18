(async () => {
  const ed = document.getElementById("editor");
  const wait = (ms) => new Promise((r) => setTimeout(r, ms));
  const paste = (data) => {
    ed.focus();
    const r = document.createRange(); r.selectNodeContents(ed); r.collapse(false);
    getSelection().removeAllRanges(); getSelection().addRange(r);
    const dt = new DataTransfer();
    for (const [k, v] of Object.entries(data)) dt.setData(k, v);
    ed.dispatchEvent(new ClipboardEvent("paste", { clipboardData: dt, bubbles: true, cancelable: true }));
  };
  ed.innerHTML = "<p><br></p>";
  paste({ "text/plain": `Step-by-Step Breakdown

Step 1: Plug the values into the formula
\\(A=1000\\left(1+\\frac{0.10}{4}\\right)^{4\\times 4}\\)
Step 2: Solve the fraction inside the parentheses
Divide the interest rate by the compounding frequency (\\(0.10 \\div 4 = 0.025\\)).
\\(A=1000(1+0.025)^{4\\times 4}\\)
\\(A=1000(1.025)^{4\\times 4}\\)
Step 3: Calculate the exponent
Multiply the number of years by the compounding frequency (\\(4 \\times 4 = 16\\) total
periods).` });
  const plainResult = ed.innerHTML;
  // KaTeX-style HTML as copied from many chat apps
  paste({ "text/html": '<p><strong>Step 4:</strong> Raise to the power</p><span class="katex-display"><span class="katex"><span class="katex-mathml"><math><semantics><mrow></mrow><annotation encoding="application/x-tex">A = 1000 \\times 1.4845 \\approx 1484.51</annotation></semantics></math></span><span class="katex-html">A = 1000 × 1.4845 ≈ 1484.51</span></span></span><script>alert(1)</script><img src="x" onerror="alert(2)">', "text/plain": "x" });
  await wait(2500);
  console.log("RESULT " + JSON.stringify({ maths: [...ed.querySelectorAll("[data-tex]")].map((m) => m.dataset.tex),
    centred: [...ed.querySelectorAll('p[style*="center"]')].length, bold: ed.querySelectorAll("b").length,
    scripts: ed.querySelectorAll("script, img").length, status: document.getElementById("status").textContent }));
})();
