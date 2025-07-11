import os
import stripe
from fastapi import HTTPException, Request, APIRouter
from fastapi.responses import JSONResponse
from schemas.payment import UpdateSubscriptionRequest, CustomerRequest, SubscriptionRequest 
from dotenv import load_dotenv

load_dotenv()

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")



router = APIRouter(
    prefix="/payment",
)


@router.post("/create-customer")
async def create_customer(customer_request: CustomerRequest):
    try:
        customer = stripe.Customer.create(
            email=customer_request.email,
            name=customer_request.name
        )
        return {
            "customer_id": customer.id,
            "email": customer.email
        }
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/create-subscription")
async def create_subscription(subscription_request: SubscriptionRequest):
    try:
        subscription_params = {
            "customer": subscription_request.customer_id,
            "items": [{"price": subscription_request.price_id}],
            "payment_behavior": "default_incomplete",
            "payment_settings": {"save_default_payment_method": "on_subscription"},
            "expand": ["latest_invoice.payment_intent"],
        }
        
        # Add trial period if specified
        if subscription_request.trial_period_days > 0:
            subscription_params["trial_period_days"] = subscription_request.trial_period_days
        
        subscription = stripe.Subscription.create(**subscription_params)
        
        return {
            "subscription_id": subscription.id,
            "client_secret": subscription.latest_invoice.payment_intent.client_secret,
            "status": subscription.status
        }
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/subscription/{subscription_id}")
async def get_subscription(subscription_id: str):
    try:
        subscription = stripe.Subscription.retrieve(subscription_id)
        return {
            "subscription_id": subscription.id,
            "customer_id": subscription.customer,
            "status": subscription.status,
            "current_period_start": subscription.current_period_start,
            "current_period_end": subscription.current_period_end,
            "cancel_at_period_end": subscription.cancel_at_period_end
        }
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put("/update-subscription")
async def update_subscription(update_request: UpdateSubscriptionRequest):
    try:
        subscription = stripe.Subscription.retrieve(update_request.subscription_id)
        
        stripe.Subscription.modify(
            update_request.subscription_id,
            items=[{
                'id': subscription['items']['data'][0].id,
                'price': update_request.new_price_id,
            }]
        )
        
        return {"message": "Subscription updated successfully"}
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/cancel-subscription/{subscription_id}")
async def cancel_subscription(subscription_id: str, cancel_immediately: bool = False):
    try:
        if cancel_immediately:
            subscription = stripe.Subscription.delete(subscription_id)
        else:
            subscription = stripe.Subscription.modify(
                subscription_id,
                cancel_at_period_end=True
            )
        
        return {
            "subscription_id": subscription.id,
            "status": subscription.status,
            "canceled_at": subscription.canceled_at if cancel_immediately else None,
            "cancel_at_period_end": subscription.cancel_at_period_end
        }
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/resume-subscription/{subscription_id}")
async def resume_subscription(subscription_id: str):
    try:
        subscription = stripe.Subscription.modify(
            subscription_id,
            cancel_at_period_end=False
        )
        
        return {
            "subscription_id": subscription.id,
            "status": subscription.status,
            "cancel_at_period_end": subscription.cancel_at_period_end
        }
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/customer/{customer_id}/subscriptions")
async def get_customer_subscriptions(customer_id: str):
    try:
        subscriptions = stripe.Subscription.list(
            customer=customer_id,
            limit=10
        )
        
        return {
            "subscriptions": [
                {
                    "id": sub.id,
                    "status": sub.status,
                    "current_period_start": sub.current_period_start,
                    "current_period_end": sub.current_period_end,
                    "cancel_at_period_end": sub.cancel_at_period_end
                }
                for sub in subscriptions.data
            ]
        }
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get('stripe-signature')
    endpoint_secret = os.getenv("STRIPE_WEBHOOK_SECRET")
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")
    
    # Handle subscription-specific events
    if event['type'] == 'customer.subscription.created':
        subscription = event['data']['object']
        print(f"New subscription created: {subscription['id']}")
        # Add user to subscription in your database
        
    elif event['type'] == 'customer.subscription.updated':
        subscription = event['data']['object']
        print(f"Subscription updated: {subscription['id']}")
        # Update subscription status in your database
        
    elif event['type'] == 'customer.subscription.deleted':
        subscription = event['data']['object']
        print(f"Subscription canceled: {subscription['id']}")
        # Remove user access in your database
        
    elif event['type'] == 'invoice.payment_succeeded':
        invoice = event['data']['object']
        print(f"Subscription payment succeeded: {invoice['subscription']}")
        # Extend user access period
        
    elif event['type'] == 'invoice.payment_failed':
        invoice = event['data']['object']
        print(f"Subscription payment failed: {invoice['subscription']}")
        
    elif event['type'] == 'customer.subscription.trial_will_end':
        subscription = event['data']['object']
        # TODO: send notifs
        print(f"Trial ending soon: {subscription['id']}")
        
    else:
        print(f"Unhandled event type: {event['type']}")
    
    return JSONResponse(content={"status": "success"})


@router.get("/plans")
async def get_plans():
    try:
        prices = stripe.Price.list(
            active=True,
            type='recurring'
        )
        
        return {
            "plans": [
                {
                    "id": price.id,
                    "amount": price.unit_amount,
                    "currency": price.currency,
                    "interval": price.recurring.interval,
                    "interval_count": price.recurring.interval_count,
                    "product": price.product
                }
                for price in prices.data
            ]
        }
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=400, detail=str(e))

