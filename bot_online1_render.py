"""Bot Telegram ONLINE1. Chạy bằng Python 3, không cần cài thư viện."""
import json
import os
import re
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

# Số tiền tính theo nghìn đồng, giống báo cáo.
TIERS = (
    (10_000, 588), (5_000, 288), (2_000, 188), (1_000, 128),
    (500, 88), (300, 68), (200, 58), (100, 38), (50, 18), (0, 8),
)
USAGE = (
    "Nhập: /check tài_khoản nạp_tháng cược_thực_tháng\n"
    "Ví dụ: /check tram96 1,400 6,972\n"
    "Số tiền tính theo nghìn đồng. Dấu chấm hoặc phẩy dùng để phân cách hàng nghìn."
)


def parse_amount(value):
    if not re.fullmatch(r"[0-9]{1,15}|[0-9]{1,3}(?:,[0-9]{3}){1,4}|[0-9]{1,3}(?:\.[0-9]{3}){1,4}", value):
        raise ValueError("Số tiền phải là số nguyên không âm theo đơn vị nghìn đồng.")
    return int(value.replace(",", "").replace(".", ""))


def eligible_code(deposit, wager):
    for minimum, code in TIERS:
        if deposit >= minimum and (minimum < 1_000 or wager >= 4 * deposit):
            return code


def reply_to(message):
    if message.get("chat", {}).get("type") != "private":
        return None
    parts = message.get("text", "").split()
    if not parts:
        return None
    command = parts[0].split("@", 1)[0].lower()
    if command in ("/start", "/help"):
        return USAGE
    if command != "/check":
        return None
    if len(parts) != 4:
        return USAGE

    _, account, raw_deposit, raw_wager = parts
    if len(account) > 100:
        return "Tên tài khoản quá dài."
    try:
        deposit = parse_amount(raw_deposit)
        wager = parse_amount(raw_wager)
    except ValueError as error:
        return str(error)

    code = eligible_code(deposit, wager)
    rounds = f"{wager / deposit:.2f}" if deposit else "— (tổng nạp bằng 0)"
    return (
        f"ONLINE1 | {account}\n"
        f"Nạp tháng: {deposit:,}K\nCược thực tháng: {wager:,}K\n"
        f"Vòng cược: {rounds}\nĐủ điều kiện nhận code {code}K.\nGiờ cấp code: 19h (giờ Việt Nam)."
    )


def telegram(token, method, **params):
    request = Request(
        f"https://api.telegram.org/bot{token}/{method}",
        data=json.dumps(params).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urlopen(request, timeout=40) as response:
        result = json.load(response)
    return result["result"]


def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not re.fullmatch(r"[0-9]+:[A-Za-z0-9_-]+", token):
        raise SystemExit("Token BotFather không đúng định dạng.")
    offset = 0
    print("Bot đang chạy. Gửi /start trong chat riêng với bot.")
    while True:
        try:
            updates = telegram(token, "getUpdates", offset=offset, timeout=25, allowed_updates=["message"])
            for update in updates:
                message = update.get("message", {})
                reply = reply_to(message)
                if reply:
                    try:
                        telegram(token, "sendMessage", chat_id=message["chat"]["id"], text=reply)
                    except HTTPError as error:
                        if error.code not in (400, 403):
                            raise
                        print(f"Không gửi được phản hồi (HTTP {error.code}).")
                offset = update["update_id"] + 1
        except HTTPError as error:
            if error.code in (401, 404):
                raise SystemExit("Telegram từ chối token. Kiểm tra lại token BotFather.")
            if error.code == 409:
                raise SystemExit("Bot đang chạy ở nơi khác hoặc còn webhook. Dừng bản cũ hoặc gỡ webhook rồi thử lại.")
            print(f"Telegram trả lỗi HTTP {error.code}. Đang thử lại.")
            time.sleep(5)
        except (URLError, TimeoutError):
            print("Mất kết nối với Telegram. Đang thử lại.")
            time.sleep(5)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nĐã dừng bot.")
