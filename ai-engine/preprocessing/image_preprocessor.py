from __future__ import annotations

from PIL import Image, ImageEnhance, ImageFilter, ImageOps


def preprocess_image(
    image: Image.Image,
    *,
    max_dimension: int = 2400,
) -> Image.Image:
    """Apply non-destructive orientation, denoising, contrast, and size corrections."""
    corrected = ImageOps.exif_transpose(image).convert("L")
    corrected = corrected.filter(ImageFilter.MedianFilter(size=3))
    corrected = ImageOps.autocontrast(corrected, cutoff=1)
    corrected = ImageEnhance.Contrast(corrected).enhance(1.15)
    corrected.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
    return corrected
