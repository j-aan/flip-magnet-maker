// End-to-end QA in headless Chrome: load the page, add real pictures, Auto line-up,
// read the QA verdict, build the magnet + sheet + pitch test, screenshot results.
const puppeteer = require("puppeteer-core"), path = require("path"), fs = require("fs");
const PAGE = process.argv[2], IMG = process.argv[3], OUT = process.argv[4] || "shots";
fs.mkdirSync(OUT, { recursive: true });
const sleep = ms => new Promise(r => setTimeout(r, ms));
(async () => {
  const browser = await puppeteer.launch({ executablePath: process.env.CHROME_PATH || "C:/Program Files/Google/Chrome/Application/chrome.exe", headless: true, args: ["--allow-file-access-from-files"] });
  const page = await browser.newPage(); await page.setViewport({ width: 1280, height: 1400 });
  const DL = path.resolve(OUT, "downloads"); fs.rmSync(DL, { recursive: true, force: true }); fs.mkdirSync(DL, { recursive: true });
  await (await page.target().createCDPSession()).send("Page.setDownloadBehavior", { behavior: "allow", downloadPath: DL });
  const errors = []; page.on("pageerror", e => errors.push("pageerror: " + e.message));
  page.on("console", m => { if (m.type() === "error") errors.push("console: " + m.text()); });
  await page.goto(require("url").pathToFileURL(path.resolve(PAGE)).href, { waitUntil: "networkidle2" });
  const pickInto = async (slot, file) => {
    const [fc] = await Promise.all([page.waitForFileChooser(), page.evaluate(i => document.querySelectorAll("#slots .slot")[i].click(), slot)]);
    await fc.accept([path.join(IMG, file)]); await sleep(800);
  };
  let fails = 0;
  for (const [second, expectV] of [["2.jpg", "PASS"], ["3.jpg", "WARN"]]) {
    console.log(`\n== Browser: 1.png + ${second}`);
    await pickInto(0, "1.png"); await pickInto(1, second);
    const t0 = Date.now();
    await page.evaluate(() => [...document.querySelectorAll("#aligns button")].find(b => b.textContent === "Auto line-up").click());
    await page.waitForFunction(() => document.querySelector("#aligns .qa-box .pill"), { timeout: 120000 });
    const qa = await page.evaluate(() => ({
      verdict: document.querySelector("#aligns .qa-box .pill").textContent,
      msg: document.querySelector("#aligns .qa-head span:last-child").textContent,
      rows: [...document.querySelectorAll("#aligns table.qa tr")].map(tr => tr.children[0].textContent + ": " + tr.children[1].textContent)
    }));
    console.log(`  verdict ${qa.verdict} in ${((Date.now() - t0) / 1000).toFixed(1)} s - ${qa.msg}`); qa.rows.forEach(r => console.log("   " + r));
    if (qa.verdict !== expectV) { console.log(`  EXPECTED ${expectV}`); fails++; }
    await sleep(500);
    const tag = second.replace(".jpg", "");
    await (await page.$(".stage")).screenshot({ path: path.join(OUT, `overlay_1_${tag}.png`) });
    // build + download each print file, then check pixel size and embedded DPI
    for (const id of ["b-one", "b-sheet", "b-pitch"]) {
      for (const f of fs.readdirSync(DL)) fs.rmSync(path.join(DL, f), { force: true });
      const before = new Set();
      await page.click("#" + id);
      await page.waitForFunction(() => !document.querySelector("#status").textContent.startsWith("Building"), { timeout: 120000 });
      const st = await page.evaluate(() => ({ s: document.querySelector("#status").textContent, cls: document.querySelector("#status").className }));
      let file = null;
      for (let k = 0; k < 100 && !file; k++) { await sleep(200); file = fs.readdirSync(DL).find(f => !before.has(f) && f.endsWith(".png")); }
      if (!file) { console.log(`  ${id}: ${st.s} - NO FILE DOWNLOADED`); fails++; continue; }
      await sleep(500);
      const buf = fs.readFileSync(path.join(DL, file));
      const w = buf.readUInt32BE(16), h = buf.readUInt32BE(20), ph = buf.indexOf("pHYs");
      const dpiX = ph > 0 ? Math.round(buf.readUInt32BE(ph + 4) * .0254) : 0;
      const expectW = { "b-one": 1818, "b-sheet": 5954, "b-pitch": 5328 }[id];
      const ok = dpiX === 720 && w === expectW && !st.cls.includes("err");
      console.log(`  ${id}: ${file} ${w}x${h} px, ${dpiX} DPI, ${(buf.length / 1048576).toFixed(1)} MB ${ok ? "OK" : "WRONG"}`);
      if (!ok) fails++;
    }
  }
  await page.screenshot({ path: path.join(OUT, "page.png"), fullPage: false });
  console.log(errors.length ? "\nPage errors:\n  " + errors.join("\n  ") : "\nNo page errors.");
  if (errors.length) fails++;
  await browser.close();
  console.log(fails ? `BROWSER QA FAILED (${fails})` : "BROWSER QA PASSED");
  process.exit(fails ? 1 : 0);
})().catch(e => { console.error(e); process.exit(1); });
