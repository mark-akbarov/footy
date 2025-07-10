import logging
from typing import Optional

import stripe
from fastapi import HTTPException
from starlette import status
from stripe.checkout import Session
from asyncer import asyncify
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings

stripe.api_key = settings.STRIPE_API_KEY



async def create_payment_intent(
    amount: int,
    currency: str = "USD",
):
    """
    :param amount: in cents
    :param currency: defaults to USD
    :return:
    """
    intent: dict = await asyncify(stripe.PaymentIntent.create)(
        amount=amount,
        currency=currency,
    )
    return intent


async def get_checkout_items(price: int):
    items = [
        {
            'price_data': {
                'currency': 'usd',
                'product_data': {
                    'name': 'Subscription',
                },
                'unit_amount': price,
            },
            'quantity': 1,
        }
    ]

    return items


async def create_stripe_checkout_session(
    items: list,
    customer_email: str,
    ride_id: int,
    ride_hash: Optional[str] = None,
) -> Session:
    ui_mode = 'embedded'
    mode = 'payment'
    return_url = settings.STRIPE_RETURN_URL + '?session_id={CHECKOUT_SESSION_ID}'
    session = await asyncify(stripe.checkout.Session.create)(
        ui_mode=ui_mode,
        line_items=items,
        mode=mode,
        return_url=return_url,
        customer_email=customer_email,
        metadata={
            'environment': str(settings.ENVIRONMENT.value),
            'ride_id': ride_id,
            'ride_hash': ride_hash
        },
        payment_method_types=['card']
    )
    return session


async def cancel_payment_intent(payment_intent_id: str):
    try:
        intent = stripe.PaymentIntent.retrieve(payment_intent_id)
        stripe.Refund.create(payment_intent=intent)
        return "succeeded"
    except stripe.error.StripeError as e:
        logging.exception(f"Stripe error: {e}")
        return "failed", e.json_body
