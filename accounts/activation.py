from django.core import signing
from django.utils import timezone
from django.conf import settings
from django.core.mail import send_mail
from django.urls import reverse

DEFAULT_TIMEOUT = getattr(settings, 'ACCOUNT_ACTIVATION_TIMEOUT', 60*60*24)  # 24h
SIGNER = signing.TimestampSigner()


def generate_activation_token(user):
    value = str(user.pk)
    return SIGNER.sign(value)


def validate_activation_token(token):
    try:
        original = SIGNER.unsign(token, max_age=DEFAULT_TIMEOUT)
        return int(original)
    except signing.BadSignature:
        return None
    except signing.SignatureExpired:
        return None
    except Exception:
        return None


def send_activation_mail(request, user, token):
    activate_url = request.build_absolute_uri(
        reverse('accounts:activate', kwargs={'token': token})
    )
    subject = '[NagoyaMeshi] アカウント有効化のご案内'
    body = (
        f"{user.email} 様\n\n"
        f"以下のリンクをクリックしてアカウントを有効化してください。\n"
        f"(24時間以内に有効化してください)\n\n{activate_url}\n\n"
        "心当たりがない場合は本メールを破棄してください。\n"
        "NagoyaMeshi サポート"
    )
    send_mail(subject, body, getattr(settings, 'DEFAULT_FROM_EMAIL', None), [user.email])
