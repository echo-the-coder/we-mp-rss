"""
飞书图片卡片发送测试
测试流程: 获取 token → 上传图片 → 发送带图卡片
"""
import os
import sys
import time

# 确保项目根目录在 path 中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.config import cfg
from core.notice.feishu import (
    _get_tenant_access_token,
    _upload_image,
    send_feishu_image_card,
)

# 从配置读取
notice_cfg = cfg.get("notice", {}) or {}
feishu_app_cfg = notice_cfg.get("feishu_app", {}) or {}

app_id = feishu_app_cfg.get("app_id", "")
app_secret = feishu_app_cfg.get("app_secret", "")
chat_id = feishu_app_cfg.get("chat_id", "")

print(f"app_id:     {app_id[:8]}***" if app_id else "app_id:     未配置")
print(f"app_secret: {app_secret[:4]}***" if app_secret else "app_secret: 未配置")
print(f"chat_id:    {chat_id}" if chat_id else "chat_id:    未配置")

if not all([app_id, app_secret, chat_id]):
    print("\n❌ 飞书应用配置不完整，请检查 config.yaml 中的 notice.feishu_app")
    sys.exit(1)

# 测试用图片：优先用二维码，没有就生成一张测试图
test_image = "./static/wx_qrcode.png"
if not os.path.exists(test_image):
    print(f"\n⚠️  {test_image} 不存在，生成测试图片...")
    # 生成一张简单的 1x1 白色 PNG 作为测试
    import base64
    os.makedirs("./static", exist_ok=True)
    # 最小的有效 PNG 文件
    minimal_png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="
    )
    with open(test_image, "wb") as f:
        f.write(minimal_png)
    print(f"   已生成测试图片: {test_image}")

print("\n--- 步骤 1: 获取 tenant_access_token ---")
try:
    token = _get_tenant_access_token(app_id, app_secret)
    print(f"✅ 获取成功: {token[:16]}...")
except Exception as e:
    print(f"❌ 失败: {e}")
    sys.exit(1)

print("\n--- 步骤 2: 上传图片 ---")
try:
    image_key = _upload_image(token, test_image)
    print(f"✅ 上传成功: image_key={image_key}")
except Exception as e:
    print(f"❌ 失败: {e}")
    sys.exit(1)

print("\n--- 步骤 3: 发送带图卡片 ---")
try:
    text = f"- 服务名：测试\n- 发送时间： {time.strftime('%Y-%m-%d %H:%M:%S')}"
    send_feishu_image_card(
        app_id, app_secret, chat_id,
        "WeRSS 飞书图片测试",
        text,
        test_image
    )
    print("\n🎉 全部完成！请检查飞书群是否收到带二维码图片的卡片消息")
except Exception as e:
    print(f"❌ 失败: {e}")
    sys.exit(1)
