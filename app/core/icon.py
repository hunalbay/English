"""Program simgesi (sistem tepsisi ve Windows .ico dosyası aynı çizimden üretilir)."""

from __future__ import annotations

BACKGROUND = "#2f5fd0"


def draw_icon(size: int = 64):  # noqa: ANN201 (PIL.Image döner; PIL isteğe bağlı bağımlılık)
    """Mavi zemin üzerine beyaz "EM" harfleri. Pillow gerektirir."""
    from PIL import Image, ImageDraw

    scale = size / 64
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((0, 0, size - 1, size - 1), radius=round(12 * scale), fill=BACKGROUND)

    def s(points):  # noqa: ANN001, ANN202
        return [(round(x * scale), round(y * scale)) for x, y in points]

    draw.rectangle(s([(10, 16), (18, 48)]), fill="white")
    for y in (16, 29, 42):
        draw.rectangle(s([(10, y), (30, y + 6)]), fill="white")
    draw.polygon(s([(35, 48), (35, 16), (42, 16), (46, 30), (50, 16), (57, 16), (57, 48),
                    (51, 48), (51, 28), (48, 40), (44, 40), (41, 28), (41, 48)]), fill="white")
    return image


def write_ico(path) -> None:  # noqa: ANN001
    """Windows için çok boyutlu .ico dosyası yazar."""
    image = draw_icon(256)
    image.save(path, format="ICO", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
