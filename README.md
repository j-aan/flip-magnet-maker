# Flip Magnet Maker

Make lenticular **flip** prints (fridge magnets, cards) from 2 or 3 pictures, right in the browser.
Pick the lens LPI, printer, size and flip direction, line the pictures up, and save print-ready PNGs.

**Use it:** https://j-aan.github.io/flip-magnet-maker/

Everything runs in your browser. Pictures are never uploaded.

## What it does

- **Flip direction:** *Walk past* (lens ridges top to bottom, changes as people pass) or *Tilt* (ridges left to right, tip it up/down, less ghosting).
- **Lens LPI:** type the number from your pitch test, decimals allowed (e.g. `59.87`).
- **Printer:** Epson 720 DPI, Canon / HP / Brother 600 DPI, or any DPI.
- **Size:** 2×2, 2×3, 3×2, 3×3, 2.5×3.5 in, or custom. Optional bleed + crop marks.
- **Full sheet:** A4, Letter or 4×6 photo paper, filled with copies.
- **Auto line-up:** a built-in engine plus OpenCV (downloaded on first use). A QA report says PASS / WARN / FAIL with the numbers behind it. *Check* scores your manual slider settings.
- **Pitch test:** prints bars at ±0.6 LPI around your lens value to find the real LPI.
- Saved PNGs carry the print DPI, so "actual size / 100%" prints at the right size.

## How to print

1. Print the **pitch test** on the same printer and paper. Lay the lens on it, ridges along the lines. The bar that looks one solid colour and flips evenly is your real LPI.
2. Type that LPI in, then save the magnet or sheet. Print at **100% / actual size**, glossy photo paper, best quality.
3. Let the ink dry about an hour. Line the lens ridges up with the strips, press it down from one edge.
4. Stick on magnet sheet, cut on the crop marks.

## Files

| Path | What |
|---|---|
| `src/flip-magnet.html` | The page source (also published as a claude.ai artifact) |
| `index.html` | Stand-alone site, built from the source: `python build.py` |
| `python/flipmagnet.py` | Same tool as a command-line script (SIFT line-up, `--patch` to fix a spot) |
| `qa/` | Automated tests |

## QA

Two tests, run them after any change (pictures are not in the repo; point them at your own folder with `1.png`, `2.jpg`, `3.jpg`):

```
python build.py
cd qa && npm install
node qa_align.js ../index.html <image-folder>     # line-up engines vs reference numbers
node qa_browser.js ../index.html <image-folder>   # headless Chrome: add pictures, Auto line-up,
                                                  # check verdicts, download all 3 PNGs, check size + DPI
```

`qa_browser.js` uses Chrome at the default Windows path; set `CHROME_PATH` to use another browser.

The reference numbers in `qa_align.js` come from the Python script's SIFT line-up of the original test pictures.
For other pictures, change the `cases` list.
