import os
import tempfile
import unittest

try:
    from PIL import Image
except ImportError:
    Image = None

try:
    import qrcode
except ImportError:
    qrcode = None

from driver.qrcode_utils import is_qr_image_valid


class TestQrCodeUtils(unittest.TestCase):
    @unittest.skipUnless(Image is not None, "Pillow is required")
    def test_white_image_is_invalid(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = os.path.join(tmp_dir, "white.png")
            Image.new("RGB", (300, 300), "white").save(path, "PNG")
            self.assertFalse(is_qr_image_valid(path))

    @unittest.skipUnless(Image is not None, "Pillow is required")
    def test_transparent_image_is_invalid(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = os.path.join(tmp_dir, "transparent.png")
            Image.new("RGBA", (300, 300), (255, 255, 255, 0)).save(path, "PNG")
            self.assertFalse(is_qr_image_valid(path))

    @unittest.skipUnless(Image is not None and qrcode is not None, "Pillow and qrcode are required")
    def test_real_qrcode_is_valid(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = os.path.join(tmp_dir, "qrcode.png")
            img = qrcode.make("https://mp.weixin.qq.com/")
            img.save(path)
            self.assertTrue(is_qr_image_valid(path))


if __name__ == "__main__":
    unittest.main()
