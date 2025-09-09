from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone


def send_safe_mail(subject: str, body: str, to_list: list[str], fail_silently: bool = True) -> bool:
    """Wrap send_mail with exception handling.
    Returns True if queued successfully, False otherwise.
    """
    if not to_list:
        return False
    try:
        send_mail(subject, body, getattr(settings, 'DEFAULT_FROM_EMAIL', None), to_list, fail_silently=False)
        return True
    except Exception:
        if not fail_silently:
            raise
        return False


def build_reservation_mail(user, shop, reserve_date, people: int) -> tuple[str, str]:
    subject = '[NagoyaMeshi] ご予約を受け付けました'
    body = (
        f"{user.email} 様\n\n"
        f"以下の内容で予約を受け付けました。\n\n"
        f"店舗: {shop.name}\n"
        f"住所: {shop.address}\n"
        f"予約日: {reserve_date.strftime('%Y-%m-%d')}\n"
        f"人数: {people} 名\n"
        f"受付時刻: {timezone.now().strftime('%Y-%m-%d %H:%M')}\n\n"
        "このメールに心当たりがない場合は破棄してください。\n"
        "NagoyaMeshi サポート"
    )
    return subject, body


def send_reservation_mail(user, shop, reserve_date, people: int) -> bool:
    try:
        subject, body = build_reservation_mail(user, shop, reserve_date, people)
        return send_safe_mail(subject, body, [user.email])
    except Exception:
        return False
