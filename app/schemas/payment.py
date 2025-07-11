from .base import BaseSchema


class CustomerRequest(BaseSchema):
    email: str
    name: str = None


class SubscriptionRequest(BaseSchema):
    customer_id: str
    price_id: str
    trial_period_days: int = 0


class UpdateSubscriptionRequest(BaseSchema):
    subscription_id: str
    new_price_id: str
