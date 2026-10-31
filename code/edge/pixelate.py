"""Pixelates regions of a frame in coarse blocks, which, unlike a light blur, cannot be undone."""

from collections.abc import Iterable

from PIL import Image

from frame import Box

BLOCK = 16  # pixels per block side: a face 80 pixels wide becomes five blocks


def pixelate(image: Image.Image, regions: Iterable[Box], block: int = BLOCK) -> Image.Image:
    result = image.copy()
    for x0, y0, x1, y1 in regions:
        x0, y0 = max(0, x0), max(0, y0)
        x1, y1 = min(image.width, x1), min(image.height, y1)
        if x0 >= x1 or y0 >= y1:
            continue
        region = result.crop((x0, y0, x1, y1))
        coarse = region.resize((max(1, region.width // block), max(1, region.height // block)), Image.Resampling.BOX)
        result.paste(coarse.resize(region.size, Image.Resampling.NEAREST), (x0, y0))
    return result
