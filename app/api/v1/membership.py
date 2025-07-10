from typing import List, Optional
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Depends, status
import stripe
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies.database import get_db_session
from db.crud.membership import MembershipCrud
from db.crud.user import UsersCrud
from db.tables.user import UserRole
from db.tables.membership import MembershipPlan, MembershipStatus
from schemas.membership import (
    CreateMembershipSchema,
    OutMembershipSchema,
    PaginatedMembershipSchema
)
from schemas.user import OutUserSchema
from api.v1.authentication import get_current_active_user
from core.config import settings

router = APIRouter(
    prefix="/memberships",
    tags=["Memberships"],
)

# Stripe configuration (in production, use environment variables)
stripe.api_key = "sk_test_..."  # Replace with your Stripe secret key

# Membership pricing
MEMBERSHIP_PRICES = {
    MembershipPlan.BASIC: 9.99,
    MembershipPlan.PREMIUM: 19.99,
    MembershipPlan.PROFESSIONAL: 29.99
}


class CreatePaymentIntentSchema(BaseModel):
    plan_type: MembershipPlan


class PaymentConfirmationSchema(BaseModel):
    payment_intent_id: str
    plan_type: MembershipPlan


def require_candidate_role(current_user: OutUserSchema = Depends(get_current_active_user)) -> OutUserSchema:
    """Require user to be a candidate."""
    if current_user.role != UserRole.CANDIDATE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only candidates can purchase memberships"
        )
    return current_user


@router.post("/create-payment-intent")
async def create_payment_intent(
    payment_data: CreatePaymentIntentSchema,
    current_user: OutUserSchema = Depends(require_candidate_role),
    db: AsyncSession = Depends(get_db_session)
):
    """Create a Stripe payment intent for membership subscription."""
    try:
        # Check if user already has an active membership
        membership_crud = MembershipCrud(db)
        active_membership = await membership_crud.get_active_membership_by_user_id(current_user.id)
        
        if active_membership:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You already have an active membership"
            )
        
        # Get price for the plan
        amount = MEMBERSHIP_PRICES.get(payment_data.plan_type)
        if not amount:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid membership plan"
            )
        
        # Create payment intent
        intent = stripe.PaymentIntent.create(
            amount=int(amount * 100),  # Amount in cents
            currency='usd',
            metadata={
                'user_id': current_user.id,
                'plan_type': payment_data.plan_type.value,
                'user_email': current_user.email
            }
        )
        
        return {
            "client_secret": intent.client_secret,
            "amount": amount,
            "currency": "usd"
        }
        
    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Stripe error: {str(e)}"
        )


@router.post("/confirm-payment", response_model=OutMembershipSchema)
async def confirm_payment(
    payment_data: PaymentConfirmationSchema,
    db: AsyncSession = Depends(get_db_session),
    current_user: OutUserSchema = Depends(require_candidate_role)
):
    """Confirm payment and activate membership."""
    try:
        # Verify payment intent
        intent = stripe.PaymentIntent.retrieve(payment_data.payment_intent_id)
        
        if intent.status != 'succeeded':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Payment not completed"
            )
        
        # Verify the payment belongs to this user
        if str(current_user.id) != intent.metadata.get('user_id'):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Payment does not belong to current user"
            )
        
        # Create membership
        membership_crud = MembershipCrud(db)
        user_crud = UsersCrud(db)
        
        start_date = datetime.utcnow()
        renewal_date = start_date + timedelta(days=30)  # 30-day subscription
        
        membership_data = {
            "user_id": current_user.id,
            "plan_type": payment_data.plan_type,
            "status": MembershipStatus.ACTIVE,
            "price": MEMBERSHIP_PRICES[payment_data.plan_type],
            "start_date": start_date,
            "renewal_date": renewal_date,
            "stripe_payment_intent_id": payment_data.payment_intent_id
        }
        
        membership = await membership_crud.create(membership_data)
        
        # Activate user account
        await user_crud.activate_user(current_user.id)
        
        await membership_crud.commit_session()
        
        return OutMembershipSchema.model_validate(membership)
        
    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Stripe error: {str(e)}"
        )


@router.get("/my-membership", response_model=OutMembershipSchema)
async def get_my_membership(
    db: AsyncSession = Depends(get_db_session),
    current_user: OutUserSchema = Depends(require_candidate_role)
):
    """Get current user's active membership."""
    membership_crud = MembershipCrud(db)
    membership = await membership_crud.get_active_membership_by_user_id(current_user.id)
    
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active membership found"
        )
    
    return OutMembershipSchema.model_validate(membership)


@router.get("/history", response_model=List[OutMembershipSchema])
async def get_membership_history(
    db: AsyncSession = Depends(get_db_session),
    current_user: OutUserSchema = Depends(require_candidate_role)
):
    """Get membership history for current user."""
    membership_crud = MembershipCrud(db)
    memberships = await membership_crud.get_memberships_by_user_id(current_user.id)
    
    return [OutMembershipSchema.model_validate(m) for m in memberships]


@router.post("/upgrade")
async def upgrade_membership(
    new_plan: CreatePaymentIntentSchema,
    db: AsyncSession = Depends(get_db_session),
    current_user: OutUserSchema = Depends(require_candidate_role)
):
    """Upgrade membership plan."""
    membership_crud = MembershipCrud(db)
    
    # Get current membership
    current_membership = await membership_crud.get_active_membership_by_user_id(current_user.id)
    if not current_membership:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active membership to upgrade"
        )
    
    # Check if new plan is actually an upgrade
    current_plan_value = list(MembershipPlan).index(current_membership.plan_type)
    new_plan_value = list(MembershipPlan).index(new_plan.plan_type)
    
    if new_plan_value <= current_plan_value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New plan must be higher tier than current plan"
        )
    
    # Calculate pro-rated amount
    days_remaining = (current_membership.renewal_date - datetime.utcnow()).days
    new_price = MEMBERSHIP_PRICES[new_plan.plan_type]
    current_price = float(current_membership.price)
    
    # Simple pro-ration calculation
    daily_current = current_price / 30
    daily_new = new_price / 30
    upgrade_amount = (daily_new - daily_current) * days_remaining
    
    try:
        # Create payment intent for upgrade
        intent = stripe.PaymentIntent.create(
            amount=int(upgrade_amount * 100),  # Amount in cents
            currency='usd',
            metadata={
                'user_id': current_user.id,
                'plan_type': new_plan.plan_type.value,
                'upgrade': 'true',
                'current_membership_id': current_membership.id
            }
        )
        
        return {
            "client_secret": intent.client_secret,
            "amount": upgrade_amount,
            "currency": "usd",
            "message": "Complete payment to upgrade your membership"
        }
        
    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Stripe error: {str(e)}"
        )


@router.get("/plans")
async def get_membership_plans():
    """Get available membership plans and pricing."""
    return {
        "plans": [
            {
                "plan": MembershipPlan.BASIC,
                "price": MEMBERSHIP_PRICES[MembershipPlan.BASIC],
                "features": [
                    "Apply to unlimited positions",
                    "Basic profile visibility",
                    "Email notifications"
                ]
            },
            {
                "plan": MembershipPlan.PREMIUM,
                "price": MEMBERSHIP_PRICES[MembershipPlan.PREMIUM],
                "features": [
                    "All Basic features",
                    "Priority in search results",
                    "Direct messaging with teams",
                    "Application tracking"
                ]
            },
            {
                "plan": MembershipPlan.PROFESSIONAL,
                "price": MEMBERSHIP_PRICES[MembershipPlan.PROFESSIONAL],
                "features": [
                    "All Premium features",
                    "Featured profile highlighting",
                    "Career consultation",
                    "Resume review service"
                ]
            }
        ]
    } 