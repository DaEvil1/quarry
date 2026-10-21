"""Draw Quarry's app icons (a cut stone on the dark nav colour) with the standard library only.

Run from frontend/: python scripts/make_icons.py. Writes public/favicon.svg and public/icons/*.png.
"""

import struct
import zlib
from pathlib import Path

BG = (0x1D, 0x21, 0x28)
# facets: light top, dark left, main right (the cockpit's dark-theme accent and two shades of it)
FACETS = [
    ((0xA9, 0xBB, 0xFA), [(0.30, 0.30), (0.62, 0.22), (0.80, 0.45), (0.50, 0.46)]),
    ((0x4F, 0x69, 0xD6), [(0.30, 0.30), (0.50, 0.46), (0.36, 0.80), (0.20, 0.55)]),
    ((0x7C, 0x96, 0xF5), [(0.50, 0.46), (0.80, 0.45), (0.70, 0.76), (0.36, 0.80)]),
]
OUT = Path(__file__).resolve().parent.parent / "public"


def inside(x, y, poly):
    hit = False
    for i in range(len(poly)):
        (x1, y1), (x2, y2) = poly[i], poly[i - 1]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            hit = not hit
    return hit


def in_rounded(x, y, r):
    cx = min(max(x, r), 1 - r)
    cy = min(max(y, r), 1 - r)
    return (x - cx) ** 2 + (y - cy) ** 2 <= r * r


def render(size, *, rounded, scale):
    ss = 4
    facets = [(c, [(0.5 + (px - 0.5) * scale, 0.5 + (py - 0.5) * scale) for px, py in p]) for c, p in FACETS]
    rows = []
    for j in range(size):
        row = bytearray([0])
        for i in range(size):
            acc = [0, 0, 0, 0]
            for sj in range(ss):
                for si in range(ss):
                    x, y = (i + (si + 0.5) / ss) / size, (j + (sj + 0.5) / ss) / size
                    if rounded and not in_rounded(x, y, 0.22):
                        continue
                    col = BG
                    for c, poly in facets:
                        if inside(x, y, poly):
                            col = c
                            break
                    acc[0] += col[0]; acc[1] += col[1]; acc[2] += col[2]; acc[3] += 255
            n = ss * ss
            a = acc[3] // n
            rgb = [acc[k] // max(1, acc[3] // 255) for k in range(3)] if a else [0, 0, 0]
            row += bytes(rgb + [a])
        rows.append(bytes(row))
    raw = zlib.compress(b"".join(rows), 9)

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", raw) + chunk(b"IEND", b""))


def svg():
    polys = "".join(
        f'<polygon fill="#{c[0]:02x}{c[1]:02x}{c[2]:02x}" points="'
        + " ".join(f"{x * 64:g},{y * 64:g}" for x, y in p) + '"/>'
        for c, p in FACETS)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
            f'<rect width="64" height="64" rx="14" fill="#1d2128"/>{polys}</svg>\n')


if __name__ == "__main__":
    (OUT / "icons").mkdir(parents=True, exist_ok=True)
    (OUT / "favicon.svg").write_text(svg())
    (OUT / "icons" / "icon-192.png").write_bytes(render(192, rounded=True, scale=1.0))
    (OUT / "icons" / "icon-512.png").write_bytes(render(512, rounded=True, scale=1.0))
    # maskable: full-bleed background, stone inside the 80% safe zone
    (OUT / "icons" / "maskable-512.png").write_bytes(render(512, rounded=False, scale=0.72))
    print("icons written to", OUT)
