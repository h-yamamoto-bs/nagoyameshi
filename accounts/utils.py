from __future__ import annotations

from datetime import datetime, timezone as dt_timezone
import stripe
from django.conf import settings
from django.utils import timezone as dj_timezone
from .models import Subscription

# Ensure API key (safe to set multiple times)
stripe.api_key = settings.STRIPE_API_SECRET_KEY


def sync_subscription_from_stripe(user) -> None:
    """Fetch latest Stripe Subscription and sync local Subscription model.
    - Updates: stripe_customer_id, end_date, is_active
    - Handles cancel_at_period_end and canceled status.
    - No-op on errors.
    """
    try:
        if not user or not getattr(user, 'is_authenticated', False):
            return
        try:
            sub_model = user.subscription
        except Subscription.DoesNotExist:
            return
        sub_id = getattr(sub_model, 'stripe_subscription_id', None)
        if not sub_id:
            return

        try:
            s = stripe.Subscription.retrieve(sub_id)
        except Exception:
            return

        status = getattr(s, 'status', None)  # active, canceled, trialing, past_due, etc.
        cancel_at_period_end = bool(getattr(s, 'cancel_at_period_end', False))
        current_period_end = getattr(s, 'current_period_end', None)
        canceled_at = getattr(s, 'canceled_at', None)
        customer_id = getattr(s, 'customer', None)

        updated_fields = []

        # customer_id補完
        if customer_id and customer_id != sub_model.stripe_customer_id:
            sub_model.stripe_customer_id = customer_id
            updated_fields.append('stripe_customer_id')

        # 終了日の決定
        end_date = sub_model.end_date
        if cancel_at_period_end and current_period_end:
            end_date = datetime.fromtimestamp(current_period_end, tz=dt_timezone.utc).date()
        if status == 'canceled' and canceled_at:
            end_date = datetime.fromtimestamp(canceled_at, tz=dt_timezone.utc).date()

        if end_date != sub_model.end_date:
            sub_model.end_date = end_date
            updated_fields.append('end_date')

        # 有効/無効
        today = dj_timezone.localdate()
        new_is_active = sub_model.is_active
        if status == 'canceled':
            new_is_active = False
        else:
            new_is_active = True
            if end_date and end_date < today:
                new_is_active = False

        if new_is_active != sub_model.is_active:
            sub_model.is_active = new_is_active
            updated_fields.append('is_active')

        if updated_fields:
            sub_model.save(update_fields=updated_fields)
    except Exception:
        # Fail silently
        return
