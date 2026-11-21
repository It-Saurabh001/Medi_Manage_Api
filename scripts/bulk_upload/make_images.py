"""Generate 7 generic product images (one per dosage_form) as PNG, pure Python (no Pillow needed).

    python scripts/bulk_upload/make_images.py

Writes scripts/bulk_upload/images/<dosage_form>.png. These are our own drawings, so there is
no copyright issue, and they never show a wrong brand/strength (they are generic per form).
"""
import math
import struct
import zlib
from pathlib import Path

SIZE = 400
OUT_DIR = Path(__file__).resolve().parent / "images"


class Canvas:
    def __init__(self, size, bg):
        self.size = size
        self.px = [[list(bg) for _ in range(size)] for _ in range(size)]

    def fill(self, sdf, color, box=None, alpha=1.0):
        """Paint pixels where the signed distance sdf(x, y) < 0, anti-aliased over 1px."""
        x0, y0, x1, y1 = box or (0, 0, self.size, self.size)
        x0, y0 = max(0, int(x0)), max(0, int(y0))
        x1, y1 = min(self.size, int(x1) + 1), min(self.size, int(y1) + 1)
        for y in range(y0, y1):
            row = self.px[y]
            for x in range(x0, x1):
                d = sdf(x + 0.5, y + 0.5)
                cov = min(1.0, max(0.0, 0.5 - d)) * alpha
                if cov > 0:
                    p = row[x]
                    for i in range(3):
                        p[i] = round(p[i] * (1 - cov) + color[i] * cov)

    def save_png(self, path):
        raw = b"".join(b"\x00" + bytes(c for p in row for c in p) for row in self.px)
        def chunk(tag, data):
            return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        png = (b"\x89PNG\r\n\x1a\n"
               + chunk(b"IHDR", struct.pack(">IIBBBBB", self.size, self.size, 8, 2, 0, 0, 0))
               + chunk(b"IDAT", zlib.compress(raw, 9))
               + chunk(b"IEND", b""))
        path.write_bytes(png)


# ---------- signed distance helpers ----------
def circle(cx, cy, r):
    return lambda x, y: math.hypot(x - cx, y - cy) - r


def rrect(cx, cy, w, h, r, angle=0.0):
    """Rounded rectangle centred at (cx, cy), optionally rotated by angle (degrees)."""
    ca, sa = math.cos(math.radians(-angle)), math.sin(math.radians(-angle))
    hw, hh = w / 2 - r, h / 2 - r

    def sdf(x, y):
        dx, dy = x - cx, y - cy
        lx, ly = dx * ca - dy * sa, dx * sa + dy * ca
        qx, qy = abs(lx) - hw, abs(ly) - hh
        return math.hypot(max(qx, 0), max(qy, 0)) + min(max(qx, qy), 0) - r
    return sdf


def intersect(a, b):
    return lambda x, y: max(a(x, y), b(x, y))


def half_plane(cx, cy, angle, keep_left=True):
    """Points on one side of a line through (cx, cy) perpendicular to `angle` (degrees)."""
    ca, sa = math.cos(math.radians(angle)), math.sin(math.radians(angle))
    sign = 1 if keep_left else -1
    return lambda x, y: sign * ((x - cx) * ca + (y - cy) * sa)


def shadow(c, sdf, box):
    c.fill(lambda x, y: sdf(x - 6, y - 10) - 2, (0, 0, 0), box=(box[0], box[1], box[2] + 14, box[3] + 16), alpha=0.10)


def base(bg, ring):
    c = Canvas(SIZE, bg)
    c.fill(circle(200, 200, 170), ring)
    return c


# ---------- one drawing per dosage form ----------
def tablet():
    c = base((235, 244, 255), (214, 232, 252))
    for cx, cy, r in ((165, 215, 82), (265, 150, 58)):
        s = circle(cx, cy, r)
        bx = (cx - r - 2, cy - r - 2, cx + r + 2, cy + r + 2)
        shadow(c, s, bx)
        c.fill(s, (255, 255, 255), bx)
        c.fill(circle(cx, cy, r - 8), (244, 247, 251), bx)
        c.fill(rrect(cx, cy, r * 1.4, 6, 3), (196, 206, 220), bx)
    return c


def capsule():
    c = base((255, 240, 240), (252, 222, 222))
    body = rrect(200, 200, 270, 104, 52, angle=-35)
    box = (70, 70, 330, 330)
    shadow(c, body, box)
    c.fill(intersect(body, half_plane(200, 200, -35, True)), (255, 255, 255), box)
    c.fill(intersect(body, half_plane(200, 200, -35, False)), (220, 60, 70), box)
    c.fill(rrect(250, 146, 60, 12, 6, angle=-35), (255, 255, 255), box, alpha=0.45)
    return c


def syrup():
    c = base((255, 246, 232), (252, 233, 205))
    body = rrect(200, 245, 150, 190, 30)
    shadow(c, body, (120, 145, 280, 345))
    c.fill(rrect(200, 132, 64, 50, 10), (170, 92, 30))        # neck
    c.fill(rrect(200, 102, 84, 40, 8), (245, 245, 245))       # cap
    c.fill(body, (190, 104, 32), (120, 145, 280, 345))        # amber bottle
    c.fill(rrect(200, 250, 116, 90, 10), (255, 255, 255))     # label
    c.fill(rrect(200, 235, 70, 12, 6), (230, 120, 60))
    c.fill(rrect(200, 262, 50, 10, 5), (210, 210, 210))
    return c


def injection():
    c = base((234, 250, 250), (210, 240, 240))
    glass = rrect(200, 235, 120, 190, 22)
    shadow(c, glass, (135, 135, 265, 335))
    c.fill(rrect(200, 118, 96, 44, 8), (240, 120, 60))        # flip-off cap
    c.fill(rrect(200, 146, 84, 22, 4), (180, 186, 194))       # crimp
    c.fill(glass, (224, 240, 246), (135, 135, 265, 335))
    c.fill(rrect(200, 268, 104, 110, 18), (120, 190, 220))    # liquid
    c.fill(rrect(200, 225, 104, 44, 6), (255, 255, 255))      # label
    c.fill(rrect(168, 230, 10, 130, 5), (255, 255, 255), alpha=0.45)
    return c


def ointment():
    c = base((240, 248, 236), (222, 239, 214))
    tube = rrect(205, 200, 230, 96, 24, angle=-30)
    shadow(c, tube, (70, 80, 340, 320))
    c.fill(tube, (250, 250, 250), (70, 80, 340, 320))
    c.fill(rrect(205, 200, 120, 60, 10, angle=-30), (90, 170, 90), (70, 80, 340, 320))
    c.fill(rrect(310, 140, 30, 110, 4, angle=-30), (215, 220, 215))   # crimped end
    c.fill(rrect(98, 262, 60, 54, 10, angle=-30), (60, 130, 70))      # cap
    return c


def drops():
    c = base((238, 242, 255), (219, 226, 252))
    body = rrect(170, 250, 110, 150, 22)
    shadow(c, body, (110, 170, 230, 330))
    c.fill(rrect(170, 168, 70, 30, 8), (255, 255, 255))       # shoulder
    c.fill(rrect(170, 136, 26, 50, 10), (255, 255, 255))      # nozzle
    c.fill(body, (255, 255, 255), (110, 170, 230, 330))
    c.fill(rrect(170, 255, 84, 70, 10), (90, 110, 220))       # label
    # falling drop: stacked circles shrinking upward = teardrop
    for i in range(30):
        t = i / 29
        c.fill(circle(282, 250 - t * 52, 30 * (1 - t) + 1.5), (80, 140, 230), (240, 180, 320, 285))
    c.fill(circle(272, 252, 7), (255, 255, 255), alpha=0.6)
    return c


def other():
    c = base((236, 250, 242), (212, 241, 224))
    disc = circle(200, 200, 112)
    shadow(c, disc, (86, 86, 314, 314))
    c.fill(disc, (255, 255, 255), (86, 86, 314, 314))
    c.fill(rrect(200, 200, 150, 48, 10), (40, 170, 100))
    c.fill(rrect(200, 200, 48, 150, 10), (40, 170, 100))
    return c


DRAWINGS = {"Tablet": tablet, "Capsule": capsule, "Syrup": syrup, "Injection": injection,
            "Ointment": ointment, "Drops": drops, "Other": other}


def main():
    OUT_DIR.mkdir(exist_ok=True)
    for name, draw in DRAWINGS.items():
        path = OUT_DIR / f"{name.lower()}.png"
        draw().save_png(path)
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
