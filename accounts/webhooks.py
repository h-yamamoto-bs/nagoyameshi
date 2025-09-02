from __future__ import annotations

import json
from datetime import datetime, timezone as dt_timezone

import stripe
from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone as dj_timezone

from .models import Subscription

stripe.api_key = settings.STRIPE_API_SECRET_KEY


def _update_local_subscription_from_event(data_object: dict) -> None:
    """Apply changes from Stripe subscription object to local Subscription row."""
    sub_id = data_object.get('id')
    customer_id = data_object.get('customer')
    status = data_object.get('status')  # active, canceled, trialing, past_due, etc.
    cancel_at_period_end = bool(data_object.get('cancel_at_period_end', False))
    current_period_end = data_object.get('current_period_end')
    canceled_at = data_object.get('canceled_at')

    sub_model = None
    if sub_id:
        sub_model = Subscription.objects.filter(stripe_subscription_id=sub_id).first()
    if not sub_model and customer_id:
        sub_model = Subscription.objects.filter(stripe_customer_id=customer_id).first()

    if not sub_model:
        return

    updated = False

    # Save IDs if missing
    if customer_id and not sub_model.stripe_customer_id:
        sub_model.stripe_customer_id = customer_id
        updated = True
    if sub_id and not sub_model.stripe_subscription_id:
        sub_model.stripe_subscription_id = sub_id
        updated = True

    # Determine end_date
    end_date = sub_model.end_date
    if cancel_at_period_end and current_period_end:
        end_date = datetime.fromtimestamp(current_period_end, tz=dt_timezone.utc).date()
    if status == 'canceled' and canceled_at:
        end_date = datetime.fromtimestamp(canceled_at, tz=dt_timezone.utc).date()

    if end_date != sub_model.end_date:
        sub_model.end_date = end_date
        updated = True

    # is_active flag
    # 決済が成功してStripeのSubscriptionがactiveになっている場合のみ有効とする。
    # incomplete/trialing/past_due等は有効化しない。
    today = dj_timezone.localdate()
    new_active = (status == 'active') and not (end_date and end_date < today)

    if new_active != sub_model.is_active:
        sub_model.is_active = new_active
        updated = True

    if updated:
        sub_model.save()


@csrf_exempt
def stripe_webhook(request):
    """Stripe webhook endpoint to keep local subscription in sync.
    Handles subscription.updated/deleted to save end_date and active state.
    """
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    webhook_secret = getattr(settings, 'STRIPE_WEBHOOK_SECRET', None)

    try:
        if webhook_secret and sig_header:
            event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
        else:
            event = json.loads(payload.decode('utf-8') or '{}')
    except Exception:
        return HttpResponse(status=400)

    event_type = event.get('type')
    data_object = event.get('data', {}).get('object', {})

    if event_type in ('customer.subscription.updated', 'customer.subscription.deleted'):
        try:
            _update_local_subscription_from_event(data_object)
        except Exception:
            # Fail silently to avoid 5xx retries storm
            pass

    return HttpResponse(status=200)
