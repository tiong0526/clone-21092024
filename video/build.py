"""Build the PSG Appreciation 2026 slideshow video.

Photos are matched to groups by filename prefix (see GROUPS), e.g.
"IFD12.jpg" or "Amazing Race3.jpg", and play in filename-number order.

Usage: python3 build.py [--photo-seconds 4] [--out out/PSG_Appreciation_2026.mp4]
"""
import argparse
import hashlib
import math
import random
import re
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

try:
    import pillow_heif
    pillow_heif.register_heif_opener()
except ImportError:
    pass

ROOT = Path(__file__).resolve().parent.parent
PHOTOS = ROOT / "photos"
HERE = Path(__file__).resolve().parent
WORK = HERE / "work"
CACHE = HERE / "cache"  # rendered clips, reused when nothing about them changed
COVER = HERE / "assets" / "opening.webp"

# (title, subtitle, [(filename prefix, caption shown on the photo)])
GROUPS = [
    ("amRead", "", [("amRead", "")]),
    ("ChineseRead", "", [("ChineseRead", "")]),
    ("MarComm & Events", "", [
        ("Amazing Race", "Amazing Race"),
        ("Donation Drive", "Donation Drive"),
        ("My Shopping Partner @ Queenstown", "My Shopping Partner @ Queenstown"),
        ("Parent's Day", "Parent\u2019s Day"),
        ("Teachers' Day Appreciation", "Teachers\u2019 Day Appreciation"),
        ("Terrarium Workshop", "Terrarium Workshop"),
    ]),
    ("Fathers' Group", "", [("Fathers Group", "")]),
    ("International Friendship Day", "IFD", [("IFD", "")]),
    ("Junior Achievement", "JA", [("JA", "")]),
]

W, H = 1920, 1080
CW, CH = 3840, 2160  # stills are rendered at 4K so the slow zoom stays smooth
FPS = 30
XFADE = 0.8
CARD_SECONDS = 4.0
OPEN_SECONDS = 8.0
CLOSE_SECONDS = 7.0
EXTS = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp", ".bmp", ".tif", ".tiff"}

FONT_DIR = Path("/usr/share/fonts/opentype/inter")
F_SEMI = str(FONT_DIR / "InterDisplay-SemiBold.otf")
F_SERIF = str(HERE / "assets" / "fonts" / "DMSerifDisplay-Regular.woff")

# Palette taken from the "Thank You, QtPSG!" cover
CREAM = (251, 246, 236)
INK = (14, 74, 85)  # dark teal used for titles
TEAL = (31, 111, 107)
TEAL_LT = (52, 146, 136)
GOLD = (236, 176, 64)
CORAL = (240, 132, 110)
WHITE = (255, 255, 255)


def run(cmd):
    subprocess.run(cmd, check=True)


def event_of(path):
    """'Amazing Race12.jpg' -> 'amazing race' (curly apostrophes normalised)."""
    stem = path.stem.replace("\u2019", "'")
    return re.sub(r"[\s._-]*[\d.]+$", "", stem).strip().lower()


def natural_key(path):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", path.name)]


def list_photos(root, prefix):
    files = [p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in EXTS
             and event_of(p) == prefix.lower()]
    return sorted(files, key=natural_key)


def compose_photo(src, dst):
    """Fit the photo onto a 4K canvas with a blurred, darkened copy behind it."""
    with Image.open(src) as im:
        im = ImageOps.exif_transpose(im).convert("RGB")
    bg = ImageOps.fit(im, (CW // 8, CH // 8), Image.LANCZOS)
    bg = bg.filter(ImageFilter.GaussianBlur(6)).resize((CW, CH), Image.LANCZOS)
    bg = Image.blend(bg, Image.new("RGB", (CW, CH), (0, 0, 0)), 0.45)
    ratio = im.width / im.height
    if abs(ratio - CW / CH) < 0.06:
        fg = ImageOps.fit(im, (CW, CH), Image.LANCZOS)
    else:
        fg = ImageOps.contain(im, (CW, CH), Image.LANCZOS)
    bg.paste(fg, ((CW - fg.width) // 2, (CH - fg.height) // 2))
    bg.save(dst, quality=93)


def leaf(layer, x, y, length, width, angle, color):
    """A paper-cut leaf with a lighter midrib, drawn onto an RGBA layer."""
    pts = []
    for i in range(41):
        t = i / 40
        pts.append((t * length, width / 2 * math.sin(math.pi * t) ** .8))
    pts += [(px_, -py) for px_, py in reversed(pts)]
    ca, sa = math.cos(angle), math.sin(angle)
    rot = [(x + px_ * ca - py * sa, y + px_ * sa + py * ca) for px_, py in pts]
    d = ImageDraw.Draw(layer)
    d.polygon(rot, fill=color + (255,))
    rib = tuple(min(255, c + 45) for c in color) + (255,)
    d.line([(x, y), (x + length * .92 * ca, y + length * .92 * sa)], fill=rib, width=max(3, int(width * .05)))


def flower(layer, x, y, r, petal, centre):
    d = ImageDraw.Draw(layer)
    for k in range(5):
        a = k * 2 * math.pi / 5
        px_, py = x + r * .55 * math.cos(a), y + r * .55 * math.sin(a)
        d.ellipse([px_ - r * .5, py - r * .5, px_ + r * .5, py + r * .5], fill=petal + (255,))
    d.ellipse([x - r * .22, y - r * .22, x + r * .22, y + r * .22], fill=centre + (255,))


def foliage(layer, rnd, cx, cy, spread, base_angle):
    """A cluster of leaves and flowers growing in from a corner."""
    colors = [TEAL, TEAL, TEAL_LT, GOLD, CORAL, (24, 92, 90)]
    for _ in range(16):
        ang = base_angle + rnd.uniform(-.9, .9)
        dist = rnd.uniform(0, spread * .55)
        x = cx + dist * math.cos(ang + rnd.uniform(-.6, .6))
        y = cy + dist * math.sin(ang + rnd.uniform(-.6, .6))
        ln = rnd.uniform(.28, .5) * spread
        leaf(layer, x, y, ln, ln * rnd.uniform(.32, .42), ang + rnd.uniform(-.5, .5), rnd.choice(colors))
    for _ in range(2):
        ang = base_angle + rnd.uniform(-.6, .6)
        dist = rnd.uniform(.2, .55) * spread
        flower(layer, cx + dist * math.cos(ang), cy + dist * math.sin(ang),
               rnd.uniform(.09, .13) * spread, rnd.choice([WHITE, CORAL]), GOLD)


def paper_bg(seed, keep_clear=None):
    """Cream paper with foliage in the corners; re-rolls the layout until no leaf
    touches the keep_clear box (left, top, right, bottom)."""
    for attempt in range(40):
        img, deco_alpha = _paper_bg(seed + attempt * 1000)
        if keep_clear is None or not deco_alpha.crop(tuple(int(v) for v in keep_clear)).getbbox():
            return img
    return img


def _paper_bg(seed):
    rnd = random.Random(seed)
    arr = np.full((CH, CW, 3), CREAM, dtype=np.float32)
    arr += np.random.default_rng(seed).normal(0, 2.2, (CH, CW, 1))  # paper grain
    img = Image.fromarray(arr.clip(0, 255).astype("uint8"))

    deco = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))
    spread = CH * .62
    foliage(deco, rnd, CW + 40, -40, spread, math.radians(135))       # top right
    foliage(deco, rnd, -40, CH + 40, spread, math.radians(-45))       # bottom left
    foliage(deco, rnd, -60, CH * .38, spread * .55, math.radians(10))  # left edge
    foliage(deco, rnd, CW + 60, CH * .8, spread * .6, math.radians(190))  # right edge
    # Soft drop shadow gives the paper-cut depth
    shadow = Image.new("RGBA", (CW, CH), (60, 50, 30, 0))
    shadow.putalpha(deco.getchannel("A").point(lambda a: a * .35).filter(ImageFilter.GaussianBlur(14)))
    img = img.convert("RGBA")
    img.alpha_composite(shadow, (10, 14))
    img.alpha_composite(deco)

    # Confetti: dashes, dots and the odd heart, kept clear of the text
    d = ImageDraw.Draw(img)
    for _ in range(46):
        x, y = rnd.randint(int(CW * .12), int(CW * .88)), rnd.randint(int(CH * .06), int(CH * .94))
        if abs(x - CW / 2) < CW * .36 and abs(y - CH / 2) < CH * .3:
            continue
        col = rnd.choice([TEAL_LT, GOLD, CORAL, GOLD])
        kind = rnd.random()
        if kind < .45:
            r = rnd.randint(12, 22)
            d.ellipse([x - r, y - r, x + r, y + r], fill=col)
        elif kind < .85:
            ang = rnd.uniform(0, math.pi)
            ln = rnd.randint(40, 70)
            d.line([(x, y), (x + ln * math.cos(ang), y + ln * math.sin(ang))], fill=col, width=18)
        else:
            heart(d, x, y, rnd.randint(30, 46), CORAL)
    return img.convert("RGB"), deco.getchannel("A")


def heart(d, x, y, s, color):
    d.ellipse([x - s, y - s * .6, x, y + s * .4], fill=color)
    d.ellipse([x, y - s * .6, x + s, y + s * .4], fill=color)
    d.polygon([(x - s * .97, y - s * .02), (x + s * .97, y - s * .02), (x, y + s * 1.05)], fill=color)


def centered(d, y, text, font, fill, tracking=0):
    if tracking:
        widths = [d.textlength(ch, font=font) for ch in text]
        total = sum(widths) + tracking * (len(text) - 1)
        x = (CW - total) / 2
        for ch, w in zip(text, widths):
            d.text((x, y), ch, font=font, fill=fill, anchor="ls")
            x += w + tracking
    else:
        d.text((CW / 2, y), text, font=font, fill=fill, anchor="ms")


def fit_font(d, text, path, size, max_w):
    while size > 60:
        f = ImageFont.truetype(path, size)
        if d.textlength(text, font=f) <= max_w:
            return f
        size -= 10
    return ImageFont.truetype(path, size)


def make_card(dst, eyebrow, title, subtitle, seed):
    probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    f_eye = ImageFont.truetype(F_SEMI, 80)
    f_title = fit_font(probe, title, F_SERIF, 380, CW * .66)
    f_sub = fit_font(probe, subtitle, F_SERIF, 140, CW * .6) if subtitle else None
    widest = max(probe.textlength(title, font=f_title),
                 probe.textlength(subtitle, font=f_sub) if subtitle else 0,
                 probe.textlength(eyebrow, font=f_eye) * 1.4)
    cy = CH / 2 if subtitle else CH / 2 + 110  # keep the text block visually centred
    pad = 120
    img = paper_bg(seed, (CW / 2 - widest / 2 - pad, cy - 420, CW / 2 + widest / 2 + pad, cy + 560))
    d = ImageDraw.Draw(img)
    centered(d, cy - 300, eyebrow.upper(), f_eye, TEAL, tracking=30)
    centered(d, cy + 110, title, f_title, INK)
    ly = cy + 250
    d.rounded_rectangle([CW / 2 - 420, ly - 4, CW / 2 - 90, ly + 4], 4, fill=GOLD)
    d.rounded_rectangle([CW / 2 + 90, ly - 4, CW / 2 + 420, ly + 4], 4, fill=GOLD)
    heart(d, CW / 2, ly - 18, 38, CORAL)
    if subtitle:
        centered(d, cy + 480, subtitle, f_sub, TEAL)
    img.save(dst, quality=95)


def make_cover(dst):
    with Image.open(COVER) as im:
        im = im.convert("RGB")
    ImageOps.fit(im, (CW, CH), Image.LANCZOS).save(dst, quality=95)


def make_caption(text, dst):
    """A transparent 1080p overlay with a small pill label, bottom left."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    f = ImageFont.truetype(F_SEMI, 40)
    tw = d.textlength(text, font=f)
    x, y = 56, H - 56 - 76
    d.rounded_rectangle([x, y, x + tw + 70, y + 76], 38, fill=INK + (225,))
    heart(d, x + 33, y + 34, 12, CORAL)
    d.text((x + 56, y + 38), text, font=f, fill=WHITE, anchor="lm")
    img.save(dst)


def render_clip(still, out, seconds, variant, caption=None, zoom=.12):
    """Slow Ken Burns zoom/pan over a still image, with an optional caption on top.

    Clips are cached by content, so a rebuild only renders what changed."""
    h = hashlib.sha1(still.read_bytes())
    if variant is None:  # derive the motion from the image so it is stable across rebuilds
        variant = int(h.hexdigest()[:8], 16)
    h.update(f"{seconds}|{variant}|{zoom}|{FPS}".encode())
    if caption:
        h.update(caption.read_bytes())
    cached = CACHE / f"{h.hexdigest()}.mp4"
    if cached.exists():
        shutil.copy(cached, out)
        return
    n = int(round(seconds * FPS))
    zin = variant % 2 == 0
    z0, z1 = (1.0, 1 + zoom) if zin else (1 + zoom, 1.0)
    pans = [(.5, .5, .5, .5), (.35, .5, .65, .5), (.65, .45, .35, .55), (.5, .35, .5, .65)]
    x0, y0, x1, y1 = pans[(variant // 2) % len(pans)]
    p = f"(on/{n - 1})"
    z = f"{z0}+({z1 - z0})*{p}"
    x = f"(iw-iw/zoom)*({x0}+({x1 - x0})*{p})"
    y = f"(ih-ih/zoom)*({y0}+({y1 - y0})*{p})"
    vf = f"zoompan=z='{z}':x='{x}':y='{y}':d={n}:s={W}x{H}:fps={FPS}"
    cmd = ["ffmpeg", "-v", "error", "-y", "-i", str(still)]
    if caption:
        cmd += ["-loop", "1", "-i", str(caption), "-filter_complex",
                f"[0:v]{vf}[bg];[bg][1:v]overlay=shortest=1,format=yuv420p"]
    else:
        cmd += ["-vf", vf + ",format=yuv420p"]
    run(cmd + ["-frames:v", str(n), "-c:v", "libx264", "-preset", "veryfast", "-crf", "15", str(out)])
    shutil.copy(out, cached)


def xfade_join(clips, out):
    """clips: list of (path, seconds, transition into this clip)."""
    if len(clips) == 1:
        shutil.copy(clips[0][0], out)
        return
    cmd = ["ffmpeg", "-v", "error", "-y"]
    for path, _, _ in clips:
        cmd += ["-i", str(path)]
    parts, prev, length = [], "0:v", clips[0][1]
    for i, (_, secs, trans) in enumerate(clips[1:], 1):
        off = length - XFADE
        label = f"v{i}"
        parts.append(f"[{prev}][{i}:v]xfade=transition={trans}:duration={XFADE}:offset={off:.3f}[{label}]")
        prev, length = label, off + secs
    cmd += ["-filter_complex", ";".join(parts), "-map", f"[{prev}]",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "15", "-pix_fmt", "yuv420p", str(out)]
    run(cmd)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--photo-seconds", type=float, default=4.0)
    ap.add_argument("--photos", default=str(PHOTOS))
    ap.add_argument("--out", default=str(HERE / "out" / "PSG_Appreciation_2026.mp4"))
    args = ap.parse_args()

    if WORK.exists():
        shutil.rmtree(WORK)
    (WORK / "stills").mkdir(parents=True)
    (WORK / "clips").mkdir()
    CACHE.mkdir(exist_ok=True)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)

    # Timeline of (still, on-screen seconds, transition in, caption overlay)
    timeline = []
    make_cover(WORK / "stills" / "000_open.jpg")
    timeline.append((WORK / "stills" / "000_open.jpg", OPEN_SECONDS, "fade", None))

    jobs = []
    used = set()
    for gi, (title, sub, events) in enumerate(GROUPS, 1):
        photos = []
        for ei, (prefix, caption) in enumerate(events):
            found = list_photos(Path(args.photos), prefix)
            cap = None
            if caption and found:
                cap = WORK / "stills" / f"{gi}_cap{ei}.png"
                make_caption(caption, cap)
            photos += [(p, cap) for p in found]
        print(f"{title}: {len(photos)} photos")
        if not photos:
            continue
        card = WORK / "stills" / f"{gi}_000_card.jpg"
        make_card(card, "QtPSG 2026", title, sub, seed=10 + gi)
        timeline.append((card, CARD_SECONDS, "fadewhite", None))
        for pi, (src, cap) in enumerate(photos, 1):
            used.add(src)
            dst = WORK / "stills" / f"{gi}_{pi:03d}.jpg"
            jobs.append((src, dst))
            timeline.append((dst, args.photo_seconds, "fade", cap))
    for p in sorted(Path(args.photos).rglob("*")):
        if p.is_file() and p.suffix.lower() in EXTS and p not in used:
            print(f"WARNING: not matched to any group, skipped: {p.name}")

    close = WORK / "stills" / "999_close.jpg"
    make_card(close, "QtPSG \u00b7 Building Stronger Families", "Thank You!",
              "for your time, effort and heart in 2026", seed=99)
    timeline.append((close, CLOSE_SECONDS, "fadewhite", None))

    with ThreadPoolExecutor(4) as ex:
        list(ex.map(lambda j: compose_photo(*j), jobs))
    print(f"Prepared {len(jobs)} photos")

    # Each clip holds its on-screen time plus the crossfade overlap
    clips = []
    for i, (still, secs, trans, cap) in enumerate(timeline):
        clips.append((still, WORK / "clips" / f"{i:04d}.mp4", secs + XFADE, trans, i, cap))
    zooms = {0: .05}  # the cover has text and faces near its edges, so barely zoom it
    with ThreadPoolExecutor(4) as ex:
        list(ex.map(lambda c: render_clip(c[0], c[1], c[2], None, c[5], zooms.get(c[4], .12)), clips))
    print(f"Rendered {len(clips)} clips")

    # Join in batches to keep each ffmpeg graph small, then join the batches
    batches, size = [], 20
    for b in range(0, len(clips), size):
        chunk = clips[b:b + size]
        out = WORK / f"batch_{b // size:02d}.mp4"
        xfade_join([(c[1], c[2], c[3]) for c in chunk], out)
        secs = sum(c[2] for c in chunk) - XFADE * (len(chunk) - 1)
        batches.append((out, secs, chunk[0][3]))
    silent = WORK / "silent.mp4"
    xfade_join(batches, silent)
    total = sum(b[1] for b in batches) - XFADE * (len(batches) - 1)

    music = WORK / "music.wav"
    run(["python3", str(HERE / "music.py"), f"{total:.2f}", str(music)])
    run(["ffmpeg", "-v", "error", "-y", "-i", str(silent), "-i", str(music),
         "-vf", f"fade=in:st=0:d=1.5,fade=out:st={total - 2.5:.2f}:d=2.5",
         "-c:v", "libx264", "-preset", "slow", "-crf", "20", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", args.out])
    print(f"Done: {args.out} ({total / 60:.1f} min)")


if __name__ == "__main__":
    main()
