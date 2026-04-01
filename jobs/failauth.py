from core.print import print_warning
from driver.base import WX_API
from core.config import cfg
from jobs.notice import sys_notice
from driver.success import Success
from driver.qrcode_utils import is_qr_image_valid
import time

QR_CODE_PATH = "./static/wx_qrcode.png"

def send_wx_code(title:str="",url:str=""):
    if cfg.get("server.send_code",False):
        WX_API.GetCode(Notice=CallBackNotice,CallBack=Success)
    pass
def CallBackNotice(data=None,ext_data=None):
        if data is not None:
            print_warning(data)
            return
        text=f"- 服务名：{cfg.get('server.name','')}\n"
        text+=f"- 发送时间： {time.strftime('%Y-%m-%d %H:%M:%S',time.localtime(time.time()))}"
        has_qr_file = WX_API.GetHasCode() and is_qr_image_valid(QR_CODE_PATH)

        if has_qr_file:
            text += f"\n- 请使用微信扫描二维码进行授权"
            sys_notice(
                text,
                str(cfg.get("server.code_title", "WeRss授权过期,扫码授权")),
                image_path=QR_CODE_PATH
            )
            return

        print_warning("二维码图片无效，降级发送文本提醒")
        text += f"\n- 二维码图片生成异常，请打开 Web UI 手动刷新扫码授权二维码"
        sys_notice(
            text,
            str(cfg.get("server.code_title", "WeRss授权过期,扫码授权")),
            image_path=""
        )
