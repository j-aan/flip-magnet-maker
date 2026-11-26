"""
flipmagnet.py - make 2- or 3-image lenticular FLIP prints (fridge magnets).

Commands
--------
  pitchtest   print this first, put the lens on it, find your REAL LPI
  build       align the images, interlace them, write print-ready PNGs

Examples
--------
  python flipmagnet.py pitchtest --lpi 60 --dpi 720
  python flipmagnet.py build 1.png 2.jpg --lpi 60 --dpi 720 --size 2

Lens direction
--------------
Default is HORIZONTAL ridges: you tilt the magnet up/down to flip.
Both eyes see the same frame, so there is less ghosting. When you laminate,
the lens ridges must run the same way as the strips on the print
(left-to-right). Use --direction vertical for left/right tilting.

Print rules
-----------
- Print at 100% / "actual size", NO "fit to page", best quality, glossy paper.
- --dpi should be your printer's native resolution: Epson 720, Canon/HP 600.
  The PNG has that DPI written inside it.
"""
import argparse
import math
import os
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

SHEETS_IN = {"a4": (8.27, 11.69), "letter": (8.5, 11.0), "4x6": (4.0, 6.0)}


# ---------------------------------------------------------------- helpers
def load_rgb(path):
    im = Image.open(path).convert("RGB")
    return np.array(im)


def font(px):
    for name in ("arialbd.ttf", "arial.ttf", "DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(name, px)
        except OSError:
            pass
    return ImageFont.load_default()


def align_to(ref, mov):
    """Warp `mov` so it lines up with `ref` (similarity transform: shift, scale,
    small rotation). Uses feature matching + RANSAC, so the parts that differ
    between the two images (the changed person) are ignored automatically."""
    g1 = cv2.cvtColor(ref, cv2.COLOR_RGB2GRAY)
    g2 = cv2.cvtColor(mov, cv2.COLOR_RGB2GRAY)
    sift = cv2.SIFT_create(8000)
    k1, d1 = sift.detectAndCompute(g1, None)
    k2, d2 = sift.detectAndCompute(g2, None)
    matches = cv2.BFMatcher().knnMatch(d2, d1, k=2)
    good = [m for m, n in matches if m.distance < 0.75 * n.distance]
    if len(good) < 20:
        sys.exit(f"Alignment failed: only {len(good)} matches. Are these the same scene?")
    src = np.float32([k2[m.queryIdx].pt for m in good])
    dst = np.float32([k1[m.trainIdx].pt for m in good])
    M, inl = cv2.estimateAffinePartial2D(src, dst, method=cv2.RANSAC,
                                         ransacReprojThreshold=2.0)
    h, w = ref.shape[:2]
    out = cv2.warpAffine(mov, M, (w, h), flags=cv2.INTER_LANCZOS4,
                         borderMode=cv2.BORDER_REPLICATE)
    # residual error on inliers, in pixels
    pts = cv2.transform(src[inl.ravel() == 1][None], M)[0]
    err = float(np.median(np.linalg.norm(pts - dst[inl.ravel() == 1], axis=1)))
    scale = math.hypot(M[0, 0], M[1, 0])
    angle = math.degrees(math.atan2(M[1, 0], M[0, 0]))
    print(f"  aligned: {int(inl.sum())}/{len(good)} matches kept, scale {scale:.4f}, "
          f"rotate {angle:+.2f} deg, shift ({M[0,2]:+.1f},{M[1,2]:+.1f}) px, "
          f"median error {err:.2f} px")
    return out


def crop_square(img, anchor):
    """Crop to the shape of the magnet. anchor: top / center / bottom."""
    h, w = img.shape[:2]
    s = min(h, w)
    x0 = (w - s) // 2
    if h > w:
        y0 = {"top": 0, "center": (h - s) // 2, "bottom": h - s}[anchor]
    else:
        y0 = 0
    return img[y0:y0 + s, x0:x0 + s]


def interlace(frames, lpi, dpi, direction):
    """Interleave frames into strips. Each lens (1/LPI inch) holds one strip of
    every frame. Works with non-integer pitches like 59.87 from the pitch test:
    every printer pixel row/column is given to the frame whose strip it falls in."""
    n = len(frames)
    h, w = frames[0].shape[:2]
    length = h if direction == "horizontal" else w
    pos = (np.arange(length) + 0.5) * lpi / dpi     # position in lens units
    which = (np.floor(pos * n) % n).astype(int)     # which frame owns this px
    # frames are flipped in order inside each lens: lens optics reverse the image
    which = (n - 1) - which
    out = np.empty_like(frames[0])
    for i, f in enumerate(frames):
        sel = which == i
        if direction == "horizontal":
            out[sel, :] = f[sel, :]
        else:
            out[:, sel] = f[:, sel]
    px_per_strip = dpi / (lpi * n)
    return out, px_per_strip


def add_bleed_and_marks(img, dpi, bleed_in, marks=True):
    """Pad with bleed (edge pixels stretched outward) plus a white margin with
    crop marks at the real magnet edge."""
    b = int(round(bleed_in * dpi))
    m = int(round(0.2 * dpi))                       # margin for marks
    padded = cv2.copyMakeBorder(img, b, b, b, b, cv2.BORDER_REPLICATE)
    canvas = Image.new("RGB", (padded.shape[1] + 2 * m, padded.shape[0] + 2 * m), "white")
    canvas.paste(Image.fromarray(padded), (m, m))
    if marks:
        d = ImageDraw.Draw(canvas)
        x0, y0 = m + b, m + b
        x1, y1 = x0 + img.shape[1], y0 + img.shape[0]
        L, g = int(0.15 * dpi), int(0.04 * dpi)
        lw = max(1, dpi // 300)
        for x in (x0, x1):
            d.line([(x, 0), (x, m - g)], fill="black", width=lw)
            d.line([(x, canvas.height - m + g), (x, canvas.height)], fill="black", width=lw)
        for y in (y0, y1):
            d.line([(0, y), (m - g, y)], fill="black", width=lw)
            d.line([(canvas.width - m + g, y), (canvas.width, y)], fill="black", width=lw)
    return canvas


def tile_sheet(tile, dpi, sheet, gap_in=0.15):
    sw, sh = (int(v * dpi) for v in SHEETS_IN[sheet])
    edge = int(0.25 * dpi)
    gap = int(gap_in * dpi)
    cols = max(1, (sw - 2 * edge + gap) // (tile.width + gap))
    rows = max(1, (sh - 2 * edge + gap) // (tile.height + gap))
    page = Image.new("RGB", (sw, sh), "white")
    ox = (sw - (cols * tile.width + (cols - 1) * gap)) // 2
    oy = (sh - (rows * tile.height + (rows - 1) * gap)) // 2
    for r in range(rows):
        for c in range(cols):
            page.paste(tile, (ox + c * (tile.width + gap), oy + r * (tile.height + gap)))
    return page, rows * cols


# ---------------------------------------------------------------- commands
def cmd_build(a):
    os.makedirs(a.out, exist_ok=True)
    n = len(a.images)
    if n not in (2, 3):
        sys.exit("Give 2 or 3 images.")
    print(f"Loading {n} images...")
    frames = [load_rgb(p) for p in a.images]

    if not a.no_align:
        print("Aligning to the first image...")
        frames = [frames[0]] + [align_to(frames[0], f) for f in frames[1:]]

    for spec in a.patch or []:
        # --patch FRAME:x0,y0,x1,y1  copies that box from frame 1 into FRAME
        fi, box = spec.split(":")
        x0, y0, x1, y1 = (int(v) for v in box.split(","))
        # feathered mask so the patch has no visible box edge
        h, w = frames[0].shape[:2]
        mask = np.zeros((h, w), np.float32)
        mask[y0:y1, x0:x1] = 1.0
        mask = cv2.GaussianBlur(mask, (0, 0), 6)[..., None]
        tgt = frames[int(fi) - 1].astype(np.float32)
        frames[int(fi) - 1] = (tgt * (1 - mask) + frames[0] * mask).astype(np.uint8)
        print(f"  patched frame {fi} box {box} from frame 1")

    frames = [crop_square(f, a.anchor) for f in frames]

    px = int(round(a.size * a.dpi))
    frames = [np.array(Image.fromarray(f).resize((px, px), Image.LANCZOS)) for f in frames]

    # aligned previews + flip GIF (what you should see when tilting)
    for i, f in enumerate(frames, 1):
        Image.fromarray(f).save(os.path.join(a.out, f"aligned_{i}.png"))
    gif = [Image.fromarray(f).resize((600, 600), Image.LANCZOS) for f in frames]
    gif[0].save(os.path.join(a.out, "preview_flip.gif"), save_all=True,
                append_images=gif[1:], duration=900, loop=0)

    inter, pps = interlace(frames, a.lpi, a.dpi, a.direction)
    if abs(pps - round(pps)) > 1e-6:
        print(f"  note: {pps:.3f} px per strip (not a whole number) - fine, but "
              f"a DPI that gives a whole number is a bit sharper.")
    tag = f"{a.size:g}in_{a.lpi:g}lpi_{a.dpi}dpi_{a.direction[0]}"
    single = add_bleed_and_marks(inter, a.dpi, a.bleed)
    p1 = os.path.join(a.out, f"magnet_{tag}.png")
    single.save(p1, dpi=(a.dpi, a.dpi))
    sheet, count = tile_sheet(single, a.dpi, a.sheet)
    p2 = os.path.join(a.out, f"sheet_{a.sheet}_{count}x_{tag}.png")
    sheet.save(p2, dpi=(a.dpi, a.dpi))

    print(f"\n{pps:g} px per strip, {n} frames, {a.lpi} LPI, {a.dpi} DPI")
    print(f"Single magnet : {p1}")
    print(f"Full sheet    : {p2}  ({count} magnets)")
    print(f"Flip preview  : {os.path.join(a.out, 'preview_flip.gif')}")
    print("Print at 100% / actual size. Strips run "
          + ("left-to-right: lay lens ridges left-to-right, tilt up/down."
             if a.direction == "horizontal" else
             "top-to-bottom: lay lens ridges top-to-bottom, tilt left/right."))


def cmd_pitchtest(a):
    """Bars at slightly different LPIs. Put the lens on top (ridges parallel to
    the lines). The bar that looks ONE solid colour along its whole length,
    and flips evenly black<->white when you tilt, is your real LPI.
    Wrong pitches show bands rolling along the bar."""
    os.makedirs(a.out, exist_ok=True)
    dpi, n = a.dpi, a.frames
    vals = np.round(np.arange(a.lpi - a.range, a.lpi + a.range + 1e-9, a.step), 3)
    bar_len, bar_t = int(6.0 * dpi), int(0.45 * dpi)
    label_w, gap, top = int(1.1 * dpi), int(0.08 * dpi), int(0.9 * dpi)
    W = label_w + bar_len + int(0.3 * dpi)
    H = top + len(vals) * (bar_t + gap) + int(0.2 * dpi)
    page = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(page)
    d.text((int(0.2 * dpi), int(0.12 * dpi)),
           f"PITCH TEST  {a.lpi:g} LPI nominal  {dpi} DPI  {n} frames  - print at 100%",
           fill="black", font=font(int(0.13 * dpi)))
    d.text((int(0.2 * dpi), int(0.4 * dpi)),
           "Lens ridges parallel to the lines. Winner = bar that looks ONE solid colour "
           "and flips evenly.", fill="black", font=font(int(0.095 * dpi)))
    y = top
    for v in vals:
        # one black strip per lens, 1/n of the lens wide (same math as interlace)
        pos = (np.arange(bar_len) + 0.5) * v / dpi
        row = np.where((np.floor(pos * n) % n) == 0, 0, 255).astype(np.uint8)
        bar = np.tile(row, (bar_t, 1))                 # vertical lines
        page.paste(Image.fromarray(bar).convert("RGB"), (label_w, y))
        d.rectangle([label_w - 2, y - 2, label_w + bar_len + 1, y + bar_t + 1],
                    outline=(150, 150, 150))
        d.text((int(0.2 * dpi), y + bar_t // 4), f"{v:.2f}", fill="black",
               font=font(int(0.16 * dpi)))
        y += bar_t + gap
    if a.direction == "horizontal":
        page = page.rotate(90, expand=True)            # lines now run left-to-right
    p = os.path.join(a.out, f"pitchtest_{a.lpi:g}lpi_{dpi}dpi_{a.direction[0]}.png")
    page.save(p, dpi=(dpi, dpi))
    print(f"Pitch test: {p}  ({page.width / dpi:.2f} x {page.height / dpi:.2f} in)")
    print("Print at 100% on the same paper + printer you will use for the magnets.")
    print("Then rebuild with --lpi <the winning number>.")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--lpi", type=float, default=60.0, help="lens LPI (use pitch-test result)")
    common.add_argument("--dpi", type=int, default=720, help="printer DPI: Epson 720, Canon/HP 600")
    common.add_argument("--direction", choices=["horizontal", "vertical"], default="horizontal",
                        help="lens ridge direction (horizontal = tilt up/down)")
    common.add_argument("--out", default="out", help="output folder")

    b = sub.add_parser("build", parents=[common], help="align + interlace images")
    b.add_argument("images", nargs="+", help="2 or 3 images; first one is the reference")
    b.add_argument("--size", type=float, default=2.0, help="magnet size in inches (square)")
    b.add_argument("--bleed", type=float, default=0.0625, help="bleed in inches")
    b.add_argument("--anchor", choices=["top", "center", "bottom"], default="bottom",
                   help="where to keep when cropping a tall image to square")
    b.add_argument("--sheet", choices=list(SHEETS_IN), default="a4")
    b.add_argument("--no-align", action="store_true")
    b.add_argument("--patch", action="append",
                   help="FRAME:x0,y0,x1,y1 copy a box from image 1 into FRAME "
                        "(coords of image 1, after alignment)")
    b.set_defaults(func=cmd_build)

    t = sub.add_parser("pitchtest", parents=[common], help="print a lens pitch test")
    t.add_argument("--frames", type=int, default=2)
    t.add_argument("--range", type=float, default=0.6, help="+/- LPI around nominal")
    t.add_argument("--step", type=float, default=0.1)
    t.set_defaults(func=cmd_pitchtest)

    a = ap.parse_args()
    a.func(a)


if __name__ == "__main__":
    main()
