"""
模拟微信授权过期场景，测试完整通知链路
跳过 WX_API，直接调用 sys_notice 发送带图片的通知
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.config import cfg
from jobs.notice import sys_notice

QR_CODE_PATH = "./static/wx_qrcode.png"

# 如果没有真实二维码，生成一张测试用的二维码图片
if not os.path.exists(QR_CODE_PATH):
    try:
        import qrcode
        img = qrcode.make("https://weixin.qq.com/test-auth")
        img.save(QR_CODE_PATH)
        print(f"已生成测试二维码: {QR_CODE_PATH}")
    except ImportError:
        # 没有 qrcode 库，用一张纯色 PNG 代替
        import base64
        os.makedirs("./static", exist_ok=True)
        # 100x100 红色 PNG
        minimal_png = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="
        )
        with open(QR_CODE_PATH, "wb") as f:
            f.write(minimal_png)
        print(f"已生成占位图片: {QR_CODE_PATH}")

# 模拟 failauth.py 中 CallBackNotice 的逻辑
text = f"- 服务名：{cfg.get('server.name', 'we-mp-rss')}\n"
text += f"- 发送时间： {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}"
text += f"\n- 请使用微信扫描二维码进行授权"

title = str(cfg.get("server.code_title", "WeRss授权过期,扫码授权"))

print(f"\n模拟发送授权过期通知:")
print(f"  标题: {title}")
print(f"  内容: {text}")
print(f"  图片: {QR_CODE_PATH}")
print()

sys_notice(text, title, image_path=QR_CODE_PATH)

print("\n✅ 通知已发送，请检查飞书群消息")
