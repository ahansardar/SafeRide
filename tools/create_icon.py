from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "assets" / "saferide.ico"


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGBA", (256, 256), "#2563eb")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((18, 18, 238, 238), radius=34, outline="#0f172a", width=12)
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/seguisb.ttf", 92)
    except OSError:
        font = ImageFont.load_default()
    text = "SR"
    box = draw.textbbox((0, 0), text, font=font)
    x = (256 - (box[2] - box[0])) / 2
    y = (256 - (box[3] - box[1])) / 2 - box[1]
    draw.text((x, y), text, fill="white", font=font)
    image.save(OUTPUT, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print(OUTPUT)


if __name__ == "__main__":
    main()

