"""Bot Telegram ONLINE1. Chạy bằng Python 3, không cần cài thư viện."""
import json
import os
import re
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
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
    if message.get("chat", {}).get("type") not in ("private", "group", "supergroup"):
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


def replies_for(message):
    batch = ""
    for line in message.get("text", "").splitlines():
        reply = reply_to({**message, "text": line})
        if not reply:
            continue
        if batch and len(batch) + len(reply) + 2 > 3500:
            yield batch
            batch = ""
        batch = f"{batch}\n\n{reply}" if batch else reply
    if batch:
        yield batch


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
    token = os.environ["TELEGRAM_BOT_TOKEN"].strip()
    secret = os.environ["TELEGRAM_WEBHOOK_SECRET"].strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,256}", secret):
        raise SystemExit("TELEGRAM_WEBHOOK_SECRET chỉ dùng chữ, số, dấu - hoặc _.")
    public_url = os.environ["RENDER_EXTERNAL_URL"].rstrip("/")

    class WebhookHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200 if self.path == "/" else 404)
            self.end_headers()

        def do_POST(self):
            if self.path != "/telegram":
                self.send_error(404)
                return
            received = self.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
            if not hmac.compare_digest(received.encode(), secret.encode()):
                self.send_error(403)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 1_000_000:
                    raise ValueError
                update = json.loads(self.rfile.read(length))
                message = update.get("message", {})
                replies = list(replies_for(message))
            except (ValueError, AttributeError, TypeError):
                self.send_error(400)
                return
            for reply in replies:
                try:
                    telegram(token, "sendMessage", chat_id=message["chat"]["id"], text=reply)
                except HTTPError as error:
                    if error.code not in (400, 403):
                        self.send_error(502)
                        return
                except (URLError, TimeoutError):
                    self.send_error(502)
                    return
            self.send_response(200)
            self.end_headers()

    with ThreadingHTTPServer(("0.0.0.0", int(os.environ.get("PORT", "10000"))), WebhookHandler) as server:
        try:
            telegram(token, "setWebhook", url=f"{public_url}/telegram",
                     secret_token=secret, allowed_updates=["message"])
        except (HTTPError, URLError, TimeoutError):
            raise SystemExit("Đăng ký webhook thất bại. Kiểm tra token và kết nối Telegram.") from None
        print("Webhook Telegram đã đăng ký.")
        server.serve_forever()


if __name__ == "__main__":
    main()
