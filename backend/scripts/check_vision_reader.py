"""Try the configured reader once, on a picture made here (no child's photo is sent).

    python -m scripts.check_vision_reader                     # the reader in VISION_PROVIDER
    python -m scripts.check_vision_reader --provider openai   # or name one: gemini | openai

It draws a small multiple-choice question with option 2 circled, asks the reader to transcribe it
(the same blind prompt as for real papers) and prints what came back, how long it took and how many
tokens it used. Use it after changing a key or a model name. The key itself is never printed.
Exit status 0 when the reader answered, 1 when it did not.
"""

import argparse
import sys

from PIL import Image, ImageDraw, ImageFont

from app.config import get_settings
from app.knowledge_tracing.application.grading.pipeline import part_specs
from app.knowledge_tracing.application.grading.types import KeyPart, VisionError
from app.knowledge_tracing.application.photo_crops import encode_png
from app.knowledge_tracing.infrastructure.vision.factory import (
    VisionNotConfigured,
    create_vision_provider,
)


def sample_picture():
    """"Which number is bigger than 7?  1. 5   2. 9   3. 6" with option 2 circled in pencil."""
    import numpy as np

    image = Image.new("RGB", (900, 260), "white")
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("arial.ttf", 38)
    except OSError:
        font = ImageFont.load_default()
    draw.text((30, 30), "7. Which number is bigger than 7?", fill="black", font=font)
    for number, (x, value) in enumerate(((120, "5"), (420, "9"), (720, "6")), start=1):
        draw.text((x, 150), f"{number}.  {value}", fill="black", font=font)
    draw.ellipse((395, 135, 545, 215), outline=(60, 60, 70), width=5)  # the child's circle
    return np.array(image)[:, :, ::-1].copy()  # PIL is RGB, the encoder wants BGR


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--provider", help="mock | gemini | openai (default: VISION_PROVIDER)")
    args = parser.parse_args()

    settings = get_settings()
    try:
        provider = create_vision_provider(settings, args.provider)
    except VisionNotConfigured as error:
        print(f"NOT READY: {error}")
        return 1

    key = [KeyPart(1, "choice", ("2",), option_labels=("1", "2", "3"))]  # never sent: only the options
    print(f"reader: {provider.name} / {getattr(provider, 'model', '?')}")
    try:
        reading, info = provider.read_item(encode_png(sample_picture()), part_specs(key), "si")
    except VisionError as error:
        print(f"FAILED: {error.code}: {error}")
        for warning in sorted(getattr(provider, "warnings", set())):
            print(f"warning: {warning}")
        return 1

    part = reading.parts[0]
    print(f"read: answer={part.answer!r} blank={part.blank} confidence={part.confidence}")
    print(f"took {info.latency_ms} ms, {info.tokens_in} tokens in, {info.tokens_out} tokens out")
    print("expected answer: 2 (the circled option)")
    for warning in sorted(getattr(provider, "warnings", set())):
        print(f"warning: {warning}")
    return 0 if part.answer.strip() in {"2", "(2)", "ii"} else 1


if __name__ == "__main__":
    sys.exit(main())
