// QA: run the page's own line-up core on real images and check against references.
const fs = require("fs"), path = require("path"), { PNG } = require("pngjs"), jpeg = require("jpeg-js");
const src = fs.readFileSync(process.argv[2], "utf8");
const a = src.indexOf("// ALIGN-CORE-START"), b = src.indexOf("// ALIGN-CORE-END");
if (a < 0 || b < 0) { console.error("core markers not found"); process.exit(2); }
const AlignCore = new Function(src.slice(a, b) + "\nreturn AlignCore;")();
const load = f => { const buf = fs.readFileSync(f); const im = /\.png$/i.test(f) ? PNG.sync.read(buf) : jpeg.decode(buf, { useTArray: true });
  return { data: im.data, width: im.width, height: im.height }; };
const IMG = process.argv[3];
// references from the Python SIFT script, converted to centre-based form
const cases = [
  { name: "1 + 2 (same scene, gag swap)", ref: "1.png", mov: "2.jpg", expect: { s: 1.0318, dx: -0.4, dy: 0.1 }, tolS: .01, tolD: 6, mustPass: true },
  { name: "1 + 3 (cartoon vs real photo)", ref: "1.png", mov: "3.jpg", expect: { s: 1.4104, dx: 100.7, dy: -223.8 }, tolS: .03, tolD: 25, mustPass: false },
];
(async () => {
  let cv = null;
  try { cv = require("@techstark/opencv-js"); const t0 = Date.now(); while (!(cv.Mat && cv.ORB)) { if (Date.now() - t0 > 60000) throw 0; await new Promise(r => setTimeout(r, 100)); } } catch (e) { cv = null; }
  let fails = 0;
  for (const c of cases) {
    const R = load(path.join(IMG, c.ref)), M = load(path.join(IMG, c.mov));
    console.log(`\n== ${c.name}`);
    const exQ = AlignCore.quality(R, M, { ...c.expect, rot: 0 });
    const wrong = AlignCore.quality(R, M, { ...c.expect, rot: 0, dx: c.expect.dx + 60, dy: c.expect.dy + 40 });
    console.log(`  reference transform quality ${exQ.toFixed(3)} (${AlignCore.verdict(exQ)}), deliberately wrong ${wrong.toFixed(3)} (${AlignCore.verdict(wrong)})`);
    for (const eng of ["js", "opencv"]) {
      if (eng === "opencv" && !cv) { console.log("  opencv: not available"); continue; }
      const t0 = Date.now();
      const r = eng === "js" ? AlignCore.jsAlign(R, M) : AlignCore.cvAlign(cv, R, M);
      const ms = Date.now() - t0;
      if (r.fail) { console.log(`  ${eng}: no match ${JSON.stringify(r.tried)}`); if (c.mustPass && eng === "js") fails++; continue; }
      const q = AlignCore.quality(R, M, r);
      const ok = Math.abs(r.s - c.expect.s) <= c.tolS && Math.abs(r.dx - c.expect.dx) <= c.tolD && Math.abs(r.dy - c.expect.dy) <= c.tolD;
      console.log(`  ${eng.padEnd(6)} s=${r.s.toFixed(4)} rot=${r.rot.toFixed(2)} dx=${r.dx.toFixed(1)} dy=${r.dy.toFixed(1)} quality=${q.toFixed(3)} ${AlignCore.verdict(q)} ` +
        `${r.inliers ? `inliers=${r.inliers}/${r.matches} err=${r.err.toFixed(2)}px ` : ""}${ms}ms  -> ${ok ? "MATCHES REFERENCE" : "OFF FROM REFERENCE"}`);
      if (c.mustPass && !ok) fails++;
    }
  }
  console.log(fails ? `\nQA FAILED (${fails})` : "\nQA PASSED");
  process.exit(fails ? 1 : 0);
})();
