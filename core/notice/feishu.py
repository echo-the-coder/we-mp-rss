import requests
import json


def send_feishu_message(webhook_url, title, text):
    """
    发送飞书 Markdown 格式消息（通过 Webhook）

    参数:
    - webhook_url: 飞书机器人 Webhook 地址
    - title: 消息标题
    - text: Markdown 格式内容
    """
    headers = {'Content-Type': 'application/json'}
    data = {
        "msg_type": "interactive",
        "card": {
            "config": {
                "wide_screen_mode": True,
                "enable_forward": True
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "content": text,
                        "tag": "lark_md"
                    }
                }
            ],
            "header": {
                "template": "blue",
                "title": {
                    "content": title,
                    "tag": "plain_text"
                }
            }
        }
    }
    try:
        response = requests.post(
            url=webhook_url,
            headers=headers,
            data=json.dumps(data)
        )
        print(response.text)
    except Exception as e:
        print('飞书通知发送失败', e)


# ========== 飞书应用 API 方式（支持发送图片） ==========

def _get_tenant_access_token(app_id, app_secret):
    """
    获取飞书 tenant_access_token
    """
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    resp = requests.post(url, json={
        "app_id": app_id,
        "app_secret": app_secret
    })
    result = resp.json()
    if result.get("code") != 0:
        raise Exception(f"获取 tenant_access_token 失败: {result.get('msg')}")
    return result["tenant_access_token"]


def _upload_image(token, image_path):
    """
    上传图片到飞书，返回 image_key

    参数:
    - token: tenant_access_token
    - image_path: 本地图片文件路径
    """
    url = "https://open.feishu.cn/open-apis/im/v1/images"
    headers = {"Authorization": f"Bearer {token}"}
    with open(image_path, "rb") as f:
        resp = requests.post(
            url,
            headers=headers,
            data={"image_type": "message"},
            files={"image": f}
        )
    result = resp.json()
    if result.get("code") != 0:
        raise Exception(f"飞书图片上传失败: {result.get('msg')}")
    return result["data"]["image_key"]


def _send_card_with_image(token, chat_id, title, text, image_key):
    """
    通过飞书 API 发送带图片的卡片消息到群

    参数:
    - token: tenant_access_token
    - chat_id: 群聊 ID
    - title: 卡片标题
    - text: 文本内容（lark_md 格式）
    - image_key: 飞书图片 key
    """
    url = "https://open.feishu.cn/open-apis/im/v1/messages"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    card = {
        "config": {
            "wide_screen_mode": True,
            "enable_forward": True
        },
        "header": {
            "template": "red",
            "title": {
                "content": title,
                "tag": "plain_text"
            }
        },
        "elements": [
            {
                "tag": "div",
                "text": {
                    "content": text,
                    "tag": "lark_md"
                }
            },
            {
                "tag": "img",
                "img_key": image_key,
                "alt": {
                    "tag": "plain_text",
                    "content": "微信授权二维码"
                },
                "mode": "fit_horizontal",
                "preview": True
            },
            {
                "tag": "note",
                "elements": [
                    {
                        "tag": "plain_text",
                        "content": "请使用微信扫描上方二维码进行授权"
                    }
                ]
            }
        ]
    }
    data = {
        "receive_id": chat_id,
        "msg_type": "interactive",
        "content": json.dumps(card)
    }
    resp = requests.post(
        f"{url}?receive_id_type=chat_id",
        headers=headers,
        json=data
    )
    result = resp.json()
    if result.get("code") != 0:
        raise Exception(f"飞书消息发送失败: {result.get('msg')}")
    print(f"飞书图片卡片发送成功: chat_id={chat_id}")


def send_feishu_image_card(app_id, app_secret, chat_id, title, text, image_path):
    """
    通过飞书应用 API 发送带二维码图片的卡片消息

    完整流程: 获取 token → 上传图片 → 发送卡片

    参数:
    - app_id: 飞书应用 App ID
    - app_secret: 飞书应用 App Secret
    - chat_id: 目标群聊 ID
    - title: 卡片标题
    - text: 文本内容
    - image_path: 二维码图片本地路径
    """
    try:
        token = _get_tenant_access_token(app_id, app_secret)
        image_key = _upload_image(token, image_path)
        _send_card_with_image(token, chat_id, title, text, image_key)
    except Exception as e:
        print(f"飞书图片卡片发送失败: {e}")
