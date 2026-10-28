"""Build the PSG Appreciation 2026 slideshow video.

Photos are matched to groups by filename prefix (see GROUPS), e.g.
"IFD12.jpg" or "Amazing Race3.jpg", and play in filename-number order.

Usage: python3 build.py [--photo-seconds 4] [--out out/PSG_Appreciation_2026.mp4]
"""
import argparse
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

# (title, subtitle, [(filename prefix, caption shown on the photo)])
GROUPS = [
    ("amRead", "", [("amRead", "")]),
    ("ChineseRead", "", [("ChineseRead", "")]),
    ("MarComm & Events", "", [
        ("Amazing Race", "Amazing Race"),
        ("Donation Drive", "Donation Drive"),
        ("My Shopping Partner @ Queenstown", "My Shopping Partner @ Queenstown"),
        ("Parent's Day", "Parents' Day"),
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
OPEN_SECONDS = 5.0
CLOSE_SECONDS = 7.0
EXTS = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp", ".bmp", ".tif", ".tiff"}

FONT_DIR = Path("/usr/share/fonts/opentype/inter")
F_BOLD = str(FONT_DIR / "InterDisplay-Bold.otf")
F_SEMI = str(FONT_DIR / "InterDisplay-SemiBold.otf")
F_LIGHT = str(FONT_DIR / "InterDisplay-Light.otf")

NAVY = (16, 24, 52)
PLUM = (58, 28, 84)
GOLD = (240, 196, 92)
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


def gradient_bg(seed):
    rnd = random.Random(seed)
    img = Image.new("RGB", (CW, CH))
    px = ImageDraw.Draw(img)
    for y in range(CH):
        t = y / CH
        c = tuple(int(NAVY[i] * (1 - t) + PLUM[i] * t) for i in range(3))
        px.line([(0, y), (CW, y)], fill=c)
    # Soft bokeh lights
    glow = Image.new("RGB", (CW, CH), (0, 0, 0))
    g = ImageDraw.Draw(glow)
    palette = [GOLD, (255, 140, 170), (120, 190, 255), (255, 220, 160)]
    for _ in range(26):
        r = rnd.randint(60, 260)
        x, y = rnd.randint(0, CW), rnd.randint(0, CH)
        col = tuple(int(v * rnd.uniform(.25, .55)) for v in rnd.choice(palette))
        g.ellipse([x - r, y - r, x + r, y + r], fill=col)
    glow = glow.filter(ImageFilter.GaussianBlur(40))
    img = Image.fromarray(np.minimum(np.asarray(img, "uint16") + np.asarray(glow, "uint16"), 255).astype("uint8"))
    # Confetti
    d = ImageDraw.Draw(img)
    conf = [GOLD, (255, 120, 150), (110, 200, 255), (150, 230, 160), WHITE]
    for _ in range(90):
        x, y = rnd.randint(0, CW), rnd.randint(0, CH)
        if abs(x - CW / 2) < CW * .46 and abs(y - CH / 2) < CH * .27:
            continue  # keep the text area clear
        w, h = rnd.randint(14, 34), rnd.randint(30, 60)
        ang = rnd.uniform(0, math.pi)
        pts = [(-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)]
        pts = [(x + px_ * math.cos(ang) - py * math.sin(ang), y + px_ * math.sin(ang) + py * math.cos(ang))
               for px_, py in pts]
        d.polygon(pts, fill=rnd.choice(conf))
    return img


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
    img = gradient_bg(seed)
    d = ImageDraw.Draw(img)
    f_eye = ImageFont.truetype(F_SEMI, 92)
    f_title = fit_font(d, title, F_BOLD, 330, CW * .82)
    f_sub = ImageFont.truetype(F_LIGHT, 120)
    cy = CH / 2 + 60
    centered(d, cy - 300, eyebrow.upper(), f_eye, GOLD, tracking=28)
    centered(d, cy + 60, title, f_title, WHITE)
    d.rounded_rectangle([CW / 2 - 180, cy + 150, CW / 2 + 180, cy + 162], 6, fill=GOLD)
    if subtitle:
        centered(d, cy + 330, subtitle, f_sub, (230, 225, 245))
    img.save(dst, quality=95)


def make_caption(text, dst):
    """A transparent 1080p overlay with a small pill label, bottom left."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    f = ImageFont.truetype(F_SEMI, 40)
    tw = d.textlength(text, font=f)
    x, y = 56, H - 56 - 76
    d.rounded_rectangle([x, y, x + tw + 64, y + 76], 38, fill=(16, 24, 52, 200))
    d.rounded_rectangle([x + 22, y + 30, x + 38, y + 46], 8, fill=GOLD)
    d.text((x + 50, y + 38), text, font=f, fill=WHITE, anchor="lm")
    img.save(dst)


def render_clip(still, out, seconds, variant, caption=None):
    """Slow Ken Burns zoom/pan over a still image, with an optional caption on top."""
    n = int(round(seconds * FPS))
    zin = variant % 2 == 0
    z0, z1 = (1.0, 1.12) if zin else (1.12, 1.0)
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
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)

    # Timeline of (still, on-screen seconds, transition in, caption overlay)
    timeline = []
    make_card(WORK / "stills" / "000_open.jpg", "Celebrating a wonderful year together",
              "PSG Appreciation 2026", "", seed=1)
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
        make_card(card, "PSG 2026", title, sub, seed=10 + gi)
        timeline.append((card, CARD_SECONDS, "fadeblack", None))
        for pi, (src, cap) in enumerate(photos, 1):
            used.add(src)
            dst = WORK / "stills" / f"{gi}_{pi:03d}.jpg"
            jobs.append((src, dst))
            timeline.append((dst, args.photo_seconds, "fade", cap))
    for p in sorted(Path(args.photos).rglob("*")):
        if p.is_file() and p.suffix.lower() in EXTS and p not in used:
            print(f"WARNING: not matched to any group, skipped: {p.name}")

    close = WORK / "stills" / "999_close.jpg"
    make_card(close, "PSG 2026", "Thank You", "for your time, effort and heart this year", seed=99)
    timeline.append((close, CLOSE_SECONDS, "fadeblack", None))

    with ThreadPoolExecutor(4) as ex:
        list(ex.map(lambda j: compose_photo(*j), jobs))
    print(f"Prepared {len(jobs)} photos")

    # Each clip holds its on-screen time plus the crossfade overlap
    clips = []
    for i, (still, secs, trans, cap) in enumerate(timeline):
        clips.append((still, WORK / "clips" / f"{i:04d}.mp4", secs + XFADE, trans, i, cap))
    with ThreadPoolExecutor(4) as ex:
        list(ex.map(lambda c: render_clip(c[0], c[1], c[2], c[4], c[5]), clips))
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
