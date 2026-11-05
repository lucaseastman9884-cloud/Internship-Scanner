"""Draw the app icons (P7): a magnifying glass over three rising bars. Original, no logos.

Standard library only (zlib PNG writer), so it adds no dependency. Run once after a design change:
    python scripts/make_icons.py
"""
from __future__ import annotations

import math
import struct
import zlib
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "site" / "icons"
NAVY = (31, 58, 95)
WHITE = (255, 255, 255)
GOLD = (242, 178, 51)
SAMPLES = 3  # 3×3 samples per pixel for smooth edges


def _shape(x: float, y: float, maskable: bool):
    """Colour at a point in the unit square, or None for transparent."""
    if not maskable:
        # Rounded square, corner radius 0.18.
        r = 0.18
        dx, dy = max(r - x, 0, x - (1 - r)), max(r - y, 0, y - (1 - r))
        if dx * dx + dy * dy > r * r:
            return None
    # The maskable icon keeps its drawing inside the central 80% safe zone.
    s = 0.66 if maskable else 0.86
    u, v = (x - 0.5) / s + 0.5, (y - 0.5) / s + 0.5
    cx, cy, ring_r, ring_w = 0.43, 0.43, 0.27, 0.06
    d = math.hypot(u - cx, v - cy)
    # Handle: a thick segment from the ring toward the bottom right.
    ax, ay = cx + ring_r * 0.72, cy + ring_r * 0.72
    bx, by = 0.86, 0.86
    t = max(0.0, min(1.0, ((u - ax) * (bx - ax) + (v - ay) * (by - ay)) / ((bx - ax) ** 2 + (by - ay) ** 2)))
    if math.hypot(u - (ax + t * (bx - ax)), v - (ay + t * (by - ay))) < 0.055:
        return WHITE
    if abs(d - ring_r) < ring_w / 2:
        return WHITE
    if d < ring_r - ring_w / 2:
        # Three bars inside the lens, rising left to right.
        for i, h in enumerate((0.12, 0.2, 0.28)):
            left = 0.29 + i * 0.1
            if left <= u <= left + 0.07 and 0.57 - h <= v <= 0.57:
                return GOLD
    return NAVY


def _png(size: int, maskable: bool) -> bytes:
    rows = []
    n = SAMPLES
    for py in range(size):
        row = bytearray([0])  # filter type 0
        for px in range(size):
            acc = [0, 0, 0, 0]
            for sy in range(n):
                for sx in range(n):
                    c = _shape((px + (sx + 0.5) / n) / size, (py + (sy + 0.5) / n) / size, maskable)
                    if c:
                        acc[0] += c[0]; acc[1] += c[1]; acc[2] += c[2]; acc[3] += 255
            cover = acc[3] / 255
            if cover:
                row += bytes([round(acc[0] / cover), round(acc[1] / cover), round(acc[2] / cover), round(acc[3] / (n * n))])
            else:
                row += b"\0\0\0\0"
        rows.append(bytes(row))

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    header = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)  # 8-bit RGBA
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(b"".join(rows), 9)) + chunk(b"IEND", b"")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, size, maskable in (("icon-192.png", 192, False), ("icon-512.png", 512, False), ("maskable-512.png", 512, True)):
        (OUT / name).write_bytes(_png(size, maskable))
        print(f"wrote {OUT / name}")


if __name__ == "__main__":
    main()
