"""Opt-in line-image experiments. Not enabled in the application OCR pipeline.

Every transform returns a new RGB image; no source crop is saved or overwritten.
Square padding is deliberately experimental: aspect preservation can reduce the
effective text height seen by a model pretrained with a square stretch.
"""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageOps

from preprocessing.image_preprocessor import preprocess_image

VARIANTS = {
    'original': 'RGB decode, unchanged cached processor square resize',
    'existing': 'Existing page preprocessing: median3, autocontrast cutoff1, contrast1.15, max2400',
    'contrast': 'Grayscale and autocontrast cutoff0; no denoising or clipping of histogram tails',
    'clahe': 'Grayscale local CLAHE clipLimit1.5 tileGrid8x2; no threshold or denoise',
    'denoise': 'Grayscale bilateral filter diameter5 sigmaColor15 sigmaSpace2; retain gray strokes',
    'deskew': 'Grayscale projection deskew within +/-3deg step0.5, >=5% gain, expanded white canvas',
    'threshold': 'Grayscale global Otsu binarization; experimental only',
    'aspect': 'Grayscale Lanczos fit into white 384x384 canvas, aspect ratio preserved',
    'margin': 'RGB white border max(2, round(height*0.05)) on every side; no crop or denoise',
}


def estimate_line_skew(image: Image.Image) -> tuple[float, float]:
    """Return Pillow correction angle and projection-score gain, not writing slant.

    This heuristic can confuse handwriting slant with baseline skew. It is a
    guarded experimental candidate, never an automatic production default.
    """
    gray = image.convert('L')
    gray.thumbnail((600, 600), Image.Resampling.LANCZOS)
    foreground = np.asarray(gray) < 160
    if foreground.sum() < 30 or min(gray.size) < 8:
        return 0.0, 0.0
    mask = Image.fromarray((foreground * 255).astype('uint8'))

    def score(angle):
        rotated = mask.rotate(angle, resample=Image.Resampling.NEAREST, expand=True, fillcolor=0)
        counts = (np.asarray(rotated) > 0).sum(axis=1).astype(float)
        return float(np.square(counts).sum())

    initial = score(0)
    angle = max(np.arange(-3, 3.01, .5), key=score)
    gain = score(angle) / max(1, initial) - 1
    return (float(angle), float(gain)) if abs(angle) >= .5 and gain >= .05 else (0.0, float(gain))


def prepare_line_image(image: Image.Image, variant: str) -> Image.Image:
    if variant not in VARIANTS:
        raise ValueError(f'Unknown preprocessing variant: {variant}')
    rgb = ImageOps.exif_transpose(image).convert('RGB')
    if variant == 'original':
        return rgb
    if variant == 'existing':
        return preprocess_image(rgb).convert('RGB')
    if variant == 'margin':
        return ImageOps.expand(rgb, border=max(2, round(rgb.height * .05)), fill='white')
    gray = rgb.convert('L')
    if variant == 'contrast':
        result = ImageOps.autocontrast(gray, cutoff=0)
    elif variant == 'clahe':
        import cv2
        result = Image.fromarray(cv2.createCLAHE(clipLimit=1.5, tileGridSize=(8, 2)).apply(np.asarray(gray)))
    elif variant == 'denoise':
        import cv2
        result = Image.fromarray(cv2.bilateralFilter(np.asarray(gray), 5, 15, 2))
    elif variant == 'deskew':
        angle, _ = estimate_line_skew(gray)
        result = gray.rotate(angle, resample=Image.Resampling.BICUBIC,
                             expand=True, fillcolor=255) if angle else gray
    elif variant == 'threshold':
        import cv2
        _, pixels = cv2.threshold(np.asarray(gray), 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        result = Image.fromarray(pixels)
    else:
        result = ImageOps.pad(gray, (384, 384), method=Image.Resampling.LANCZOS, color=255)
    return result.convert('RGB')


def image_diagnostics(image: Image.Image) -> dict:
    """Descriptive signals, not calibrated blur/lighting or clipping diagnoses."""
    import cv2
    gray = np.asarray(image.convert('L'))
    ink = gray < 160
    edge = np.concatenate((ink[:2].ravel(), ink[-2:].ravel(), ink[:, :2].ravel(), ink[:, -2:].ravel()))
    background_tiles = [float(np.percentile(tile, 90)) for tile in np.array_split(gray, 4, axis=1)]
    return {
        'width': image.width, 'height': image.height, 'aspect_ratio': image.width / image.height,
        'laplacian_variance': float(cv2.Laplacian(gray, cv2.CV_64F).var()),
        'p05': float(np.percentile(gray, 5)), 'p95': float(np.percentile(gray, 95)),
        'dark_pixel_fraction': float(ink.mean()), 'edge_dark_pixels': int(edge.sum()),
        'background_p90_range_across_four_tiles': max(background_tiles) - min(background_tiles),
        'exif_orientation': image.getexif().get(274),
        'channels_identical': image.mode != 'RGB' or bool(np.array_equal(np.asarray(image)[:, :, 0], np.asarray(image)[:, :, 1]) and np.array_equal(np.asarray(image)[:, :, 1], np.asarray(image)[:, :, 2])),
    }
