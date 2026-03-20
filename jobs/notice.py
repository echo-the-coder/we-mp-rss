from core.config import cfg
def sys_notice(text:str="",title:str="",tag:str='系统通知',type="",image_path:str=""):
    from core.notice import notice
    markdown_text = f"### {title} {type} {tag}\n{text}"
    notice_cfg = cfg.get('notice', {}) or {}
    webhook = notice_cfg.get('dingding', '')
    if len(webhook)>0:
        notice(webhook, title, markdown_text)

    # 飞书 Webhook 通知
    feishu_webhook = notice_cfg.get('feishu', '')
    if len(feishu_webhook) > 0:
        notice(feishu_webhook, title, markdown_text)

    # 飞书应用 API 通知（独立渠道，支持发送图片）
    feishu_app_cfg = notice_cfg.get('feishu_app', {}) or {}
    feishu_app_id = feishu_app_cfg.get('app_id', '')
    feishu_app_secret = feishu_app_cfg.get('app_secret', '')
    feishu_chat_id = feishu_app_cfg.get('chat_id', '')
    if all([feishu_app_id, feishu_app_secret, feishu_chat_id]):
        if image_path:
            from core.notice.feishu import send_feishu_image_card
            send_feishu_image_card(
                feishu_app_id, feishu_app_secret, feishu_chat_id,
                title, text, image_path
            )
        else:
            from core.notice.feishu import send_feishu_text_card
            send_feishu_text_card(
                feishu_app_id, feishu_app_secret, feishu_chat_id,
                title, text
            )

    wechat_webhook = notice_cfg.get('wechat', '')
    if len(wechat_webhook)>0:
        notice(wechat_webhook, title, markdown_text)
    custom_webhook = notice_cfg.get('custom', '')
    if len(custom_webhook)>0:
        notice(custom_webhook, title, markdown_text)
    bark_webhook = notice_cfg.get('bark', '')
    if len(bark_webhook)>0:
        notice(bark_webhook, title, markdown_text, notice_type='bark')
