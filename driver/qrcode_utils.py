import os


def is_qr_image_valid(
    image_path: str,
    min_file_size: int = 365,
    min_dimension: int = 50,
    min_non_white_ratio: float = 0.01,
    min_dark_ratio: float = 0.005,
    min_opaque_ratio: float = 0.7,
) -> bool:
    """
    校验二维码图片是否有效，避免发送空白或透明图。
    """
    if not image_path or not os.path.exists(image_path):
        return False
    if os.path.getsize(image_path) < min_file_size:
        return False

    try:
        from PIL import Image
        with Image.open(image_path) as img:
            rgba = img.convert("RGBA")
    except Exception:
        return False

    width, height = rgba.size
    if width < min_dimension or height < min_dimension:
        return False

    total_pixels = width * height
    if total_pixels <= 0:
        return False

    alpha = rgba.getchannel("A")
    alpha_hist = alpha.histogram()
    opaque_pixels = total_pixels - alpha_hist[0]
    opaque_ratio = opaque_pixels / float(total_pixels)
    if opaque_ratio < min_opaque_ratio:
        return False

    white_bg = Image.new("RGB", rgba.size, "white")
    white_bg.paste(rgba, mask=alpha)
    gray = white_bg.convert("L")
    gray_hist = gray.histogram()

    white_pixels = sum(gray_hist[245:256])
    dark_pixels = sum(gray_hist[0:80])
    non_white_ratio = (total_pixels - white_pixels) / float(total_pixels)
    dark_ratio = dark_pixels / float(total_pixels)

    if non_white_ratio < min_non_white_ratio:
        return False
    if dark_ratio < min_dark_ratio:
        return False

    return True
