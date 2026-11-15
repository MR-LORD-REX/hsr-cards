"""Image compositing primitives shared by card families."""
from PIL import Image, ImageOps


def paste_icon(canvas: Image.Image, icon: Image.Image | None, box):
    """Fit and center a borrowed icon inside a pixel (left, top, right, bottom) box.

    Alpha-composite into the RGBA canvas in place using Lanczos resizing; preserve
    aspect ratio and leave the input icon unchanged. None is a no-op; image/mode
    errors propagate. No files or provider resources are opened.
    """
    if icon is None:
        return
    left, top, right, bottom = [int(value) for value in box]
    size = (max(1, right - left), max(1, bottom - top))
    working = ImageOps.contain(icon.convert("RGBA"), size, Image.Resampling.LANCZOS)
    x = left + (size[0] - working.width) // 2
    y = top + (size[1] - working.height) // 2
    canvas.alpha_composite(working, (x, y))
