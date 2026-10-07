from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
ASSET_DIR = ROOT / "assets"
ICON_OUTPUT = ASSET_DIR / "saferide.ico"
MARK_SIZES = (32, 48, 96, 256)

NAVY = "#0b1220"
BLUE = "#2563eb"
BLUE_LIGHT = "#60a5fa"
WHITE = "#f8fafc"
GREEN = "#22c55e"


def draw_mark(size: int) -> Image.Image:
    """Render the SafeRide shield-and-helmet mark at icon quality."""
    scale = 4
    canvas = size * scale
    ratio = canvas / 256

    def box(values: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
        return tuple(round(value * ratio) for value in values)  # type: ignore[return-value]

    def points(values: list[tuple[int, int]]) -> list[tuple[int, int]]:
        return [(round(x * ratio), round(y * ratio)) for x, y in values]

    def width(value: int) -> int:
        return max(1, round(value * ratio))

    image = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    # The dark tile keeps the mark readable in Explorer, the taskbar and both
    # light and dark Windows themes.
    draw.rounded_rectangle(box((10, 10, 246, 246)), radius=width(52), fill=NAVY)

    # Shield: safety. The asymmetric helmet inside it supplies the ride cue.
    shield = [(128, 31), (216, 68), (207, 145), (181, 194), (128, 229),
              (75, 194), (49, 145), (40, 68)]
    draw.polygon(points(shield), fill=BLUE)
    draw.line(points(shield + [shield[0]]), fill=BLUE_LIGHT, width=width(5), joint="curve")

    # Motorcycle helmet profile. Broad shapes survive all the way down to the
    # 16 px ICO layer, unlike lettering or thin line art.
    draw.pieslice(box((66, 69, 190, 193)), start=180, end=360, fill=WHITE)
    draw.polygon(points([(66, 130), (180, 130), (209, 151), (203, 181),
                         (169, 181), (158, 164), (66, 164)]), fill=WHITE)
    draw.rounded_rectangle(box((112, 103, 188, 132)), radius=width(11), fill=NAVY)
    draw.polygon(points([(178, 108), (203, 125), (184, 132)]), fill=BLUE_LIGHT)
    draw.rounded_rectangle(box((161, 166, 198, 176)), radius=width(5), fill=NAVY)

    # This green point matches SafeRide's live safe state.
    draw.ellipse(box((72, 139, 92, 159)), fill=GREEN)

    return image.resize((size, size), Image.Resampling.LANCZOS)


def main() -> None:
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    generated = {size: draw_mark(size) for size in MARK_SIZES}
    for size, image in generated.items():
        image.save(ASSET_DIR / f"saferide-mark-{size}.png", optimize=True)

    generated[256].save(
        ICON_OUTPUT,
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    print(ICON_OUTPUT)
    for size in MARK_SIZES:
        print(ASSET_DIR / f"saferide-mark-{size}.png")


if __name__ == "__main__":
    main()

