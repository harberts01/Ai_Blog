"""
Stripe Integration Module
Handles all Stripe payment processing for subscriptions
"""
import stripe
from config import Config
from datetime import datetime
import database as db

# Initialize Stripe
stripe.api_key = Config.STRIPE_SECRET_KEY


def get_or_create_customer(user):
    """
    Get existing Stripe customer or create new one.
    
    Args:
        user: Dict with user_id, email, username, stripe_customer_id
        
    Returns:
        Stripe Customer object
    """
    # Check if user already has a Stripe customer ID
    if user.get('stripe_customer_id'):
        try:
            customer = stripe.Customer.retrieve(user['stripe_customer_id'])
            if not customer.get('deleted'):
                return customer
        except stripe.error.InvalidRequestError:
            pass  # Customer doesn't exist, create new one
    
    # Create new customer
    customer = stripe.Customer.create(
        email=user['email'],
        name=user.get('username', ''),
        metadata={
            'user_id': str(user['user_id']),
            'username': user.get('username', '')
        }
    )
    
    # Save customer ID to database
    db.update_user_stripe_customer_id(user['user_id'], customer.id)
    
    return customer


def create_checkout_session(user, price_id, success_url, cancel_url):
    """
    Create a Stripe Checkout session for subscription.
    
    This redirects users to Stripe's hosted payment page.
    No payment data touches your server.
    
    Args:
        user: Dict with user info
        price_id: Stripe Price ID (e.g., 'price_xxx')
        success_url: URL to redirect after successful payment
        cancel_url: URL to redirect if user cancels
        
    Returns:
        Stripe Checkout Session
    """
    customer = get_or_create_customer(user)
    
    session_params = {
        'customer': customer.id,
        'payment_method_types': ['card'],
        'line_items': [{
            'price': price_id,
            'quantity': 1,
        }],
        'mode': 'subscription',
        'success_url': success_url + '?session_id={CHECKOUT_SESSION_ID}',
        'cancel_url': cancel_url,
        'metadata': {
            'user_id': str(user['user_id'])
        },
        'subscription_data': {
            'metadata': {
                'user_id': str(user['user_id'])
            }
        },
        'allow_promotion_codes': True,  # Allow discount codes
    }
    
    # Add trial period if configured
    trial_days = Config.TRIAL_DAYS
    if trial_days and trial_days > 0:
        session_params['subscription_data']['trial_period_days'] = trial_days
    
    return stripe.checkout.Session.create(**session_params)


def create_billing_portal_session(customer_id, return_url):
    """
    Create a Stripe Customer Portal session.
    
    Allows customers to manage their subscription (cancel, update payment, etc.)
    without you building those UIs.
    
    Args:
        customer_id: Stripe Customer ID
        return_url: URL to return to after portal session
        
    Returns:
        Stripe BillingPortal Session
    """
    return stripe.billing_portal.Session.create(
        customer=customer_id,
        return_url=return_url,
    )


def get_subscription(subscription_id):
    """Retrieve a Stripe subscription"""
    try:
        return stripe.Subscription.retrieve(subscription_id)
    except stripe.error.InvalidRequestError:
        return None


def cancel_subscription(subscription_id, at_period_end=True):
    """
    Cancel a subscription.
    
    Args:
        subscription_id: Stripe Subscription ID
        at_period_end: If True, cancel at end of billing period (default).
                      If False, cancel immediately.
    """
    if at_period_end:
        return stripe.Subscription.modify(
            subscription_id,
            cancel_at_period_end=True
        )
    else:
        return stripe.Subscription.cancel(subscription_id)


def reactivate_subscription(subscription_id):
    """Reactivate a subscription that was set to cancel at period end"""
    return stripe.Subscription.modify(
        subscription_id,
        cancel_at_period_end=False
    )


def construct_webhook_event(payload, sig_header):
    """
    Construct and verify a Stripe webhook event.
    
    Args:
        payload: Raw request body
        sig_header: Stripe-Signature header value
        
    Returns:
        Stripe Event object
        
    Raises:
        ValueError: If signature verification fails
    """
    return stripe.Webhook.construct_event(
        payload,
        sig_header,
        Config.STRIPE_WEBHOOK_SECRET
    )


# ============== Webhook Event Handlers ==============

def handle_checkout_completed(event):
    """
    Handle successful checkout session completion.
    Called when user completes payment on Stripe Checkout.
    """
    session = event['data']['object']
    user_id = int(session['metadata'].get('user_id', 0))
    customer_id = session.get('customer')
    subscription_id = session.get('subscription')
    
    if not user_id or not subscription_id:
        print(f"⚠️ Checkout completed but missing user_id or subscription_id")
        return
    
    # Get subscription details from Stripe
    subscription = stripe.Subscription.retrieve(subscription_id)
    price_id = subscription['items']['data'][0]['price']['id']
    
    # Find matching plan in database
    plan = db.get_plan_by_stripe_price_id(price_id)
    if not plan:
        print(f"⚠️ No plan found for price_id: {price_id}")
        return
    
    # Update user's stripe customer ID
    db.update_user_stripe_customer_id(user_id, customer_id)
    
    # Create or update user subscription
    db.upsert_user_subscription(
        user_id=user_id,
        plan_id=plan['plan_id'],
        stripe_customer_id=customer_id,
        stripe_subscription_id=subscription_id,
        status=subscription['status'],
        current_period_start=datetime.fromtimestamp(subscription['current_period_start']),
        current_period_end=datetime.fromtimestamp(subscription['current_period_end']),
        trial_end=datetime.fromtimestamp(subscription['trial_end']) if subscription.get('trial_end') else None
    )
    
    print(f"✅ Subscription activated for user {user_id}: {plan['display_name']}")
    
    # Send welcome notification
    db.create_notification(
        user_id=user_id,
        notification_type='system',
        title='Welcome to Premium! 🎉',
        message=f"Your {plan['display_name']} subscription is now active. Enjoy unlimited access!",
        link='/account'
    )


def handle_subscription_updated(event):
    """Handle subscription updates (plan changes, renewals, etc.)"""
    subscription = event['data']['object']
    subscription_id = subscription['id']
    
    # Find user by subscription ID
    user_sub = db.get_user_subscription_by_stripe_id(subscription_id)
    if not user_sub:
        print(f"⚠️ No user found for subscription: {subscription_id}")
        return
    
    # Get new price/plan if changed
    price_id = subscription['items']['data'][0]['price']['id']
    plan = db.get_plan_by_stripe_price_id(price_id)
    
    # Update subscription in database
    db.update_user_subscription(
        user_id=user_sub['user_id'],
        plan_id=plan['plan_id'] if plan else user_sub['plan_id'],
        status=subscription['status'],
        current_period_start=datetime.fromtimestamp(subscription['current_period_start']),
        current_period_end=datetime.fromtimestamp(subscription['current_period_end']),
        cancel_at_period_end=subscription.get('cancel_at_period_end', False)
    )
    
    print(f"✅ Subscription updated for user {user_sub['user_id']}: {subscription['status']}")


def handle_subscription_deleted(event):
    """Handle subscription cancellation/deletion"""
    subscription = event['data']['object']
    subscription_id = subscription['id']
    
    # Find user by subscription ID
    user_sub = db.get_user_subscription_by_stripe_id(subscription_id)
    if not user_sub:
        return
    
    # Update subscription status to canceled
    db.update_user_subscription_status(
        user_id=user_sub['user_id'],
        status='canceled',
        canceled_at=datetime.now()
    )
    
    print(f"✅ Subscription canceled for user {user_sub['user_id']}")
    
    # Send notification
    db.create_notification(
        user_id=user_sub['user_id'],
        notification_type='system',
        title='Subscription Ended',
        message='Your premium subscription has ended. You can resubscribe anytime to regain full access.',
        link='/pricing'
    )


def handle_invoice_paid(event):
    """Record successful payment"""
    invoice = event['data']['object']
    customer_id = invoice.get('customer')
    
    # Find user by customer ID
    user = db.get_user_by_stripe_customer_id(customer_id)
    if not user:
        return
    
    # Record payment in history
    db.record_payment(
        user_id=user['user_id'],
        stripe_payment_intent_id=invoice.get('payment_intent'),
        stripe_invoice_id=invoice.get('id'),
        amount_cents=invoice.get('amount_paid', 0),
        currency=invoice.get('currency', 'usd'),
        status='succeeded',
        description=invoice.get('description') or 'Subscription payment',
        receipt_url=invoice.get('hosted_invoice_url')
    )
    
    print(f"✅ Payment recorded for user {user['user_id']}: ${invoice.get('amount_paid', 0) / 100:.2f}")


def handle_invoice_payment_failed(event):
    """Handle failed payment"""
    invoice = event['data']['object']
    customer_id = invoice.get('customer')
    
    user = db.get_user_by_stripe_customer_id(customer_id)
    if not user:
        return
    
    # Record failed payment
    db.record_payment(
        user_id=user['user_id'],
        stripe_payment_intent_id=invoice.get('payment_intent'),
        stripe_invoice_id=invoice.get('id'),
        amount_cents=invoice.get('amount_due', 0),
        currency=invoice.get('currency', 'usd'),
        status='failed',
        description='Payment failed'
    )
    
    # Notify user
    db.create_notification(
        user_id=user['user_id'],
        notification_type='system',
        title='Payment Failed',
        message='We couldn\'t process your payment. Please update your payment method to keep your premium access.',
        link='/account/billing'
    )
    
    print(f"⚠️ Payment failed for user {user['user_id']}")


# Webhook handler dispatch
WEBHOOK_HANDLERS = {
    'checkout.session.completed': handle_checkout_completed,
    'customer.subscription.updated': handle_subscription_updated,
    'customer.subscription.deleted': handle_subscription_deleted,
    'invoice.paid': handle_invoice_paid,
    'invoice.payment_failed': handle_invoice_payment_failed,
}


def process_webhook_event(event):
    """Process a Stripe webhook event"""
    event_type = event['type']
    handler = WEBHOOK_HANDLERS.get(event_type)
    
    if handler:
        try:
            handler(event)
            return True
        except Exception as e:
            print(f"❌ Error handling webhook {event_type}: {e}")
            return False
    else:
        print(f"ℹ️ Unhandled webhook event: {event_type}")
        return True
