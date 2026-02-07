"""
AI Blog Application
A secure, modern blog platform featuring content from top AI tools

This is the main Flask application file. It has been refactored to use
separate modules for better maintainability:

- config.py      : Application configuration
- database.py    : Database operations
- auth.py        : Authentication helpers
- utils.py       : Utility functions
- ai_generators.py : AI content generation
"""
import os
import re
import logging
import threading
from datetime import datetime, timedelta
from urllib.parse import urlparse, urljoin

from flask import (
    Flask, render_template, request, redirect, 
    url_for, flash, session, abort, jsonify
)

# Configure secure logging (no sensitive data)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)


def is_safe_url(target):
    """Validate redirect URL to prevent open redirect attacks"""
    if not target:
        return False
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and ref_url.netloc == test_url.netloc
from werkzeug.security import generate_password_hash, check_password_hash
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from config import Config
import database as db
from auth import login_required, admin_required, premium_required, get_current_user, login_user, logout_user
from utils import sanitize_input, validate_email
import ai_generators


# ============== App Setup ==============

app = Flask(__name__)
app.config.from_object(Config)
app.secret_key = Config.SECRET_KEY


# ============== Security Setup ==============

# CSRF Protection
csrf = CSRFProtect(app)

# Rate Limiting
limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=["1000 per day", "200 per hour"],
    storage_uri="memory://"
)


@app.after_request
def add_security_headers(response):
    """Add security headers to all responses"""
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com https://cdn.jsdelivr.net; "
        "img-src 'self' data: https:; "
        "connect-src 'self' https://cdn.jsdelivr.net; "
        "frame-ancestors 'self';"
    )
    return response


# ============== Context Processors ==============

@app.context_processor
def inject_globals():
    """Inject global variables into all templates"""
    user = get_current_user()
    is_premium = False
    free_posts_remaining = 0
    
    if user:
        is_premium = db.is_user_premium(user['id'])
        if not is_premium:
            views_this_month = db.get_user_free_post_views_this_month(user['id'])
            free_posts_remaining = max(0, Config.FREE_POSTS_PER_MONTH - views_this_month)
    
    return {
        'current_user': user,
        'ai_tools': db.get_all_tools(),
        'current_year': datetime.now().year,
        'now': datetime.now(),
        'is_premium': is_premium,
        'free_posts_remaining': free_posts_remaining,
        'FREE_POSTS_PER_MONTH': Config.FREE_POSTS_PER_MONTH,
        'FREE_POST_DELAY_DAYS': Config.FREE_POST_DELAY_DAYS
    }


# ============== Template Filters ==============

@app.template_filter('reading_time')
def reading_time_filter(content):
    """Calculate estimated reading time for content"""
    if not content:
        return "1 min read"
    text = re.sub(r'<[^>]+>', '', content)
    word_count = len(text.split())
    minutes = max(1, round(word_count / 200))
    return f"{minutes} min read"


@app.template_filter('word_count')
def word_count_filter(content):
    """Count words in content"""
    if not content:
        return 0
    text = re.sub(r'<[^>]+>', '', content)
    return len(text.split())


# ============== Public Routes ==============

@app.route("/")
def home():
    """Home page showing all recent posts"""
    page = request.args.get('page', 1, type=int)
    per_page = 9
    posts, total = db.get_all_posts(page=page, per_page=per_page)
    tools = db.get_all_tools()
    total_pages = (total + per_page - 1) // per_page
    
    return render_template(
        "index.html", 
        posts=posts, 
        tools=tools,
        page=page,
        total_pages=total_pages,
        total_posts=total
    )


@app.route("/tool/<slug>")
def tool_page(slug):
    """Page for a specific AI tool showing its posts"""
    tool = db.get_tool_by_slug(slug)
    if not tool:
        abort(404)
    
    page = request.args.get('page', 1, type=int)
    per_page = 12
    posts, total = db.get_posts_by_tool(tool['id'], page=page, per_page=per_page)
    total_pages = (total + per_page - 1) // per_page
    
    user = get_current_user()
    is_subscribed = False
    if user:
        is_subscribed = db.is_subscribed(user['id'], tool['id'])
    
    return render_template(
        "tool.html", 
        tool=tool, 
        posts=posts, 
        is_subscribed=is_subscribed,
        page=page,
        total_pages=total_pages,
        total_posts=total
    )


@app.route("/search")
def search():
    """Search posts"""
    query = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)
    per_page = 12
    
    if not query:
        return render_template("search.html", posts=[], query="", page=1, total_pages=0, total_posts=0)
    
    posts, total = db.search_posts(query, page=page, per_page=per_page)
    total_pages = (total + per_page - 1) // per_page
    
    return render_template(
        "search.html",
        posts=posts,
        query=query,
        page=page,
        total_pages=total_pages,
        total_posts=total
    )


@app.route("/post/<int:post_id>")
def post(post_id):
    """Individual blog post page"""
    post_data = db.get_post_by_id(post_id)
    if not post_data:
        abort(404)
    
    comments = db.get_comments_by_post(post_id)
    
    # Check if user has bookmarked this post
    is_bookmarked = False
    user = get_current_user()
    is_premium = False
    can_view_full = True
    limit_reason = None
    free_posts_remaining = 5
    
    if user:
        is_bookmarked = db.is_bookmarked(user['id'], post_id)
        is_premium = db.is_user_premium(user['id'])
        
        if not is_premium:
            # Check if user can view this post
            can_view, reason = db.can_user_view_post(
                user['id'], 
                post_id, 
                post_data['created_at'],
                free_post_limit=Config.FREE_POSTS_PER_MONTH,
                delay_days=Config.FREE_POST_DELAY_DAYS
            )
            
            if can_view and reason == 'within_limit':
                # Record the view if it's a new view within their limit
                if not db.has_user_viewed_post(user['id'], post_id):
                    db.record_free_post_view(user['id'], post_id)
            
            can_view_full = can_view
            limit_reason = reason
            views_this_month = db.get_user_free_post_views_this_month(user['id'])
            free_posts_remaining = max(0, Config.FREE_POSTS_PER_MONTH - views_this_month)
    else:
        # Anonymous users get limited preview
        from datetime import datetime, timedelta
        delay_threshold = datetime.now() - timedelta(days=Config.FREE_POST_DELAY_DAYS)
        if post_data['created_at'] >= delay_threshold:
            can_view_full = False
            limit_reason = 'not_logged_in'
    
    active_matchups = db.get_active_matchups_for_post(post_id)
    tool_rank_badges = db.get_tool_rank_badges()

    return render_template("post.html",
                          post=post_data,
                          comments=comments,
                          is_bookmarked=is_bookmarked,
                          is_premium=is_premium,
                          can_view_full=can_view_full,
                          limit_reason=limit_reason,
                          free_posts_remaining=free_posts_remaining,
                          active_matchups=active_matchups,
                          tool_rank_badges=tool_rank_badges)


@app.route("/post/<int:post_id>/comment", methods=["POST"])
@limiter.limit("10 per minute")
def add_comment(post_id):
    """Add a comment to a post"""
    content = sanitize_input(request.form.get('content'))
    parent_id = request.form.get('parent_id', type=int)
    
    if not content or len(content) < 3:
        flash('Comment must be at least 3 characters.', 'error')
        return redirect(url_for('post', post_id=post_id))
    
    if len(content) > 1000:
        flash('Comment must be less than 1000 characters.', 'error')
        return redirect(url_for('post', post_id=post_id))
    
    user = get_current_user()
    user_id = user['id'] if user else None
    
    db.insert_comment(post_id, content, user_id=user_id, parent_id=parent_id)
    flash('Comment added successfully!', 'success')
    return redirect(url_for('post', post_id=post_id))


# ============== Authentication Routes ==============

@app.route("/register", methods=["GET", "POST"])
@limiter.limit("3 per hour")
def register():
    """User registration"""
    if get_current_user():
        return redirect(url_for('home'))
    
    if request.method == "POST":
        email = sanitize_input(request.form.get('email'))
        username = sanitize_input(request.form.get('username'))
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        errors = []
        
        if not email or not validate_email(email):
            errors.append('Please enter a valid email address.')
        
        if not username or len(username) < 3:
            errors.append('Username must be at least 3 characters.')
        
        if not password or len(password) < 8:
            errors.append('Password must be at least 8 characters.')
        elif not any(c.isupper() for c in password):
            errors.append('Password must contain at least one uppercase letter.')
        elif not any(c.islower() for c in password):
            errors.append('Password must contain at least one lowercase letter.')
        elif not any(c.isdigit() for c in password):
            errors.append('Password must contain at least one number.')
        
        if password != confirm_password:
            errors.append('Passwords do not match.')
        
        if db.get_user_by_email(email):
            errors.append('An account with this email already exists.')
        
        if errors:
            for error in errors:
                flash(error, 'error')
            return render_template("register.html")
        
        password_hash = generate_password_hash(password)
        user_id = db.create_user(email, password_hash, username)
        
        if user_id:
            login_user(user_id)
            flash('Account created successfully! Welcome!', 'success')
            return redirect(url_for('home'))
        else:
            flash('An error occurred. Please try again.', 'error')
    
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
@limiter.limit("20 per minute")
def login():
    """User login"""
    if get_current_user():
        return redirect(url_for('home'))
    
    if request.method == "POST":
        email = sanitize_input(request.form.get('email'))
        password = request.form.get('password')
        
        user = db.get_user_by_email(email)
        
        if user and check_password_hash(user['password_hash'], password):
            if not user['is_active']:
                logger.warning(f"Login attempt for deactivated account: {email}")
                flash('Your account has been deactivated.', 'error')
                return render_template("login.html")
            
            login_user(user['id'])
            logger.info(f"Successful login for user_id: {user['id']}")
            flash(f'Welcome back, {user["username"]}!', 'success')
            
            # Validate redirect URL to prevent open redirect attacks
            next_page = request.args.get('next')
            if next_page and is_safe_url(next_page):
                return redirect(next_page)
            return redirect(url_for('my_feed'))
        else:
            # Log failed attempt (don't log the password!)
            logger.warning(f"Failed login attempt for email: {email}")
            flash('Invalid email or password.', 'error')
    
    return render_template("login.html")


@app.route("/logout")
def logout():
    """User logout"""
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('home'))


@app.route("/forgot-password", methods=["GET", "POST"])
@limiter.limit("5 per hour")
def forgot_password():
    """Request password reset"""
    if get_current_user():
        return redirect(url_for('home'))

    if request.method == "POST":
        email = sanitize_input(request.form.get('email'))
        user = db.get_user_by_email(email)

        if user:
            # Generate reset token (valid for 1 hour)
            import secrets
            token = secrets.token_urlsafe(32)
            expires_at = datetime.now() + timedelta(hours=1)

            # Store token in database
            db.create_password_reset_token(user['id'], token, expires_at)

            # Send email with reset link
            reset_url = url_for('reset_password', token=token, _external=True)
            import email_utils
            email_utils.send_password_reset_email(app, user['email'], user['username'], reset_url)

            logger.info(f"Password reset requested for user_id: {user['id']}")

        # Always show success message (don't reveal if email exists)
        flash('If an account exists with that email, you will receive a password reset link shortly.', 'info')
        return redirect(url_for('login'))

    return render_template("forgot_password.html")


@app.route("/reset-password/<token>", methods=["GET", "POST"])
@limiter.limit("5 per hour")
def reset_password(token):
    """Reset password with token"""
    if get_current_user():
        return redirect(url_for('home'))

    # Verify token
    user_id = db.verify_password_reset_token(token)
    if not user_id:
        flash('Invalid or expired reset link.', 'error')
        return redirect(url_for('forgot_password'))

    if request.method == "POST":
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        if not password or len(password) < 8:
            flash('Password must be at least 8 characters.', 'error')
            return render_template("reset_password.html")

        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template("reset_password.html")

        # Update password
        password_hash = generate_password_hash(password)
        db.update_user_password(user_id, password_hash)

        # Delete used token
        db.delete_password_reset_token(token)

        logger.info(f"Password reset successful for user_id: {user_id}")
        flash('Your password has been reset! You can now log in.', 'success')
        return redirect(url_for('login'))

    return render_template("reset_password.html")


# ============== Subscription Routes ==============

@app.route("/subscribe/<int:tool_id>", methods=["POST"])
@login_required
def subscribe(tool_id):
    """Subscribe to an AI tool"""
    user = get_current_user()
    tool = db.get_tool_by_id(tool_id)
    
    if not tool:
        abort(404)
    
    if db.is_subscribed(user['id'], tool_id):
        flash(f'You are already subscribed to {tool["name"]}.', 'info')
    else:
        db.add_subscription(user['id'], tool_id)
        flash(f'Successfully subscribed to {tool["name"]}!', 'success')
    
    return redirect(url_for('tool_page', slug=tool['slug']))


@app.route("/unsubscribe/<int:tool_id>", methods=["POST"])
@login_required
def unsubscribe(tool_id):
    """Unsubscribe from an AI tool"""
    user = get_current_user()
    tool = db.get_tool_by_id(tool_id)
    
    if not tool:
        abort(404)
    
    db.remove_subscription(user['id'], tool_id)
    flash(f'Unsubscribed from {tool["name"]}.', 'info')
    
    return redirect(url_for('tool_page', slug=tool['slug']))


@app.route("/subscriptions")
@login_required
def subscriptions():
    """User subscriptions management page"""
    user = get_current_user()
    all_tools = db.get_all_tools()
    subscribed_ids = db.get_subscribed_tool_ids(user['id'])
    
    return render_template(
        "subscriptions.html", 
        tools=all_tools, 
        subscribed_ids=subscribed_ids
    )


@app.route("/update-email-preferences", methods=["POST"])
@login_required
def update_email_preferences():
    """Update user email notification preferences"""
    user = get_current_user()
    
    # Checkbox value: present = True, absent = False
    email_notifications = request.form.get('email_notifications') == 'on'
    
    db.update_user_email_preferences(user['id'], email_notifications)
    
    if email_notifications:
        flash('Email notifications enabled.', 'success')
    else:
        flash('Email notifications disabled.', 'info')
    
    # Redirect back to referring page (account or subscriptions)
    next_page = request.form.get('next') or request.referrer or url_for('subscriptions')
    return redirect(next_page)


# ============== Account Management ==============

@app.route("/account")
@login_required
def account():
    """User account settings page"""
    user = get_current_user()
    profile = db.get_user_full_profile(user['id'])
    return render_template("account.html", profile=profile)


@app.route("/account/update-profile", methods=["POST"])
@login_required
def update_profile():
    """Update user profile (username/email)"""
    user = get_current_user()
    
    username = sanitize_input(request.form.get('username', '').strip())
    email = request.form.get('email', '').strip().lower()
    
    # Validate inputs
    errors = []
    
    if username and len(username) < 3:
        errors.append('Username must be at least 3 characters')
    if username and len(username) > 50:
        errors.append('Username must be less than 50 characters')
    if username and not re.match(r'^[a-zA-Z0-9_]+$', username):
        errors.append('Username can only contain letters, numbers, and underscores')
    
    if email and not validate_email(email):
        errors.append('Please enter a valid email address')
    
    if errors:
        for error in errors:
            flash(error, 'danger')
        return redirect(url_for('account'))
    
    # Only update fields that changed
    current_username = user['username']
    current_email = user['email']
    
    update_username = username if username and username != current_username else None
    update_email = email if email and email != current_email else None
    
    if not update_username and not update_email:
        flash('No changes detected', 'info')
        return redirect(url_for('account'))
    
    result = db.update_user_profile(user['id'], username=update_username, email=update_email)
    
    if result['success']:
        flash('Profile updated successfully!', 'success')
        # Update session with new info
        if update_username:
            session['username'] = update_username
    else:
        flash(result.get('error', 'Failed to update profile'), 'danger')
    
    return redirect(url_for('account'))


@app.route("/account/change-password", methods=["POST"])
@login_required
def change_password():
    """Change user password"""
    user = get_current_user()
    
    current_password = request.form.get('current_password', '')
    new_password = request.form.get('new_password', '')
    confirm_password = request.form.get('confirm_password', '')
    
    # Get full user with password hash
    full_user = db.get_user_by_email(user['email'])
    if not full_user:
        flash('User not found', 'danger')
        return redirect(url_for('account'))
    
    # Verify current password
    if not check_password_hash(full_user['password_hash'], current_password):
        flash('Current password is incorrect', 'danger')
        return redirect(url_for('account'))
    
    # Validate new password
    if len(new_password) < 8:
        flash('New password must be at least 8 characters', 'danger')
        return redirect(url_for('account'))
    
    # Check password strength
    has_upper = any(c.isupper() for c in new_password)
    has_lower = any(c.islower() for c in new_password)
    has_digit = any(c.isdigit() for c in new_password)
    
    if not (has_upper and has_lower and has_digit):
        flash('Password must contain uppercase, lowercase, and a number', 'danger')
        return redirect(url_for('account'))
    
    if new_password != confirm_password:
        flash('New passwords do not match', 'danger')
        return redirect(url_for('account'))
    
    if current_password == new_password:
        flash('New password must be different from current password', 'danger')
        return redirect(url_for('account'))
    
    # Update password
    new_hash = generate_password_hash(new_password)
    if db.update_user_password(user['id'], new_hash):
        logger.info(f"Password changed for user: {user['email']}")
        flash('Password changed successfully!', 'success')
    else:
        flash('Failed to change password', 'danger')
    
    return redirect(url_for('account'))


@app.route("/account/delete", methods=["POST"])
@login_required
def delete_account():
    """Delete user account"""
    user = get_current_user()
    
    # Require password confirmation
    password = request.form.get('password', '')
    confirm_text = request.form.get('confirm_delete', '')
    
    if confirm_text != 'DELETE':
        flash('Please type DELETE to confirm account deletion', 'danger')
        return redirect(url_for('account'))
    
    # Verify password
    full_user = db.get_user_by_email(user['email'])
    if not full_user or not check_password_hash(full_user['password_hash'], password):
        flash('Incorrect password', 'danger')
        return redirect(url_for('account'))
    
    # Delete account
    if db.delete_user_account(user['id']):
        logger.info(f"Account deleted: {user['email']}")
        logout_user()
        flash('Your account has been deleted. We\'re sorry to see you go!', 'info')
        return redirect(url_for('home'))
    else:
        flash('Failed to delete account', 'danger')
        return redirect(url_for('account'))


# ============== Subscription & Payments ==============

@app.route("/pricing")
def pricing():
    """Display pricing/subscription plans"""
    plans = db.get_all_subscription_plans()
    user = get_current_user()
    
    current_subscription = None
    if user:
        current_subscription = db.get_user_subscription(user['id'])
    
    return render_template("pricing.html", 
                          plans=plans,
                          current_subscription=current_subscription,
                          stripe_publishable_key=Config.STRIPE_PUBLISHABLE_KEY)


@app.route("/checkout/<plan_type>")
@login_required
def checkout_plan(plan_type):
    """Start subscription checkout process"""
    import stripe_utils
    
    user = get_current_user()
    
    # Validate plan type
    if plan_type not in ['monthly', 'annual']:
        flash('Invalid subscription plan', 'danger')
        return redirect(url_for('pricing'))
    
    # Get price ID based on plan type
    if plan_type == 'monthly':
        price_id = Config.STRIPE_PRICE_MONTHLY
    else:
        price_id = Config.STRIPE_PRICE_ANNUAL
    
    if not price_id:
        flash('Subscription plans are not configured. Please try again later.', 'danger')
        return redirect(url_for('pricing'))
    
    try:
        # Create checkout session
        user_data = {
            'user_id': user['id'],
            'email': user['email'],
            'username': user['username'],
            'stripe_customer_id': db.get_user_by_email(user['email']).get('stripe_customer_id')
        }
        
        success_url = url_for('checkout_success', _external=True)
        cancel_url = url_for('checkout_cancel', _external=True)
        
        session = stripe_utils.create_checkout_session(
            user_data, price_id, success_url, cancel_url
        )
        
        return redirect(session.url)
        
    except Exception as e:
        logger.error(f"Checkout error: {e}")
        flash('Unable to start checkout. Please try again.', 'danger')
        return redirect(url_for('pricing'))


@app.route("/checkout/success")
@login_required
def checkout_success():
    """Handle successful checkout - provisions subscription from Stripe session"""
    import stripe_utils
    
    session_id = request.args.get('session_id')
    user = get_current_user()
    subscription_activated = False
    
    # Always try to provision the subscription from the checkout session
    # This ensures subscription is activated even if webhook is delayed/fails
    if session_id:
        try:
            checkout_session = stripe_utils.stripe.checkout.Session.retrieve(
                session_id,
                expand=['subscription', 'customer']
            )
            
            logger.info(f"Checkout session retrieved for user {user['id']}: payment_status={checkout_session.payment_status}, subscription={checkout_session.subscription}")
            
            # Check for paid OR successful subscription (handles both regular payments and trials)
            if checkout_session.payment_status in ['paid', 'no_payment_required'] and checkout_session.subscription:
                stripe_sub = checkout_session.subscription
                stripe_customer_id = checkout_session.customer.id if hasattr(checkout_session.customer, 'id') else checkout_session.customer
                
                # Update user's stripe customer ID
                db.update_user_stripe_customer_id(user['id'], stripe_customer_id)
                
                # Get the subscription details if it's just an ID string
                if isinstance(stripe_sub, str):
                    stripe_sub = stripe_utils.stripe.Subscription.retrieve(stripe_sub)
                
                # Check existing subscription - only skip if already active with SAME stripe subscription
                existing_sub = db.get_user_subscription(user['id'])
                should_update = True
                
                if existing_sub:
                    # Update if: no stripe sub ID, different stripe sub ID, not active, or is free plan
                    if (existing_sub.get('stripe_subscription_id') == stripe_sub.id 
                        and existing_sub.get('status') == 'active'
                        and existing_sub.get('plan_name') not in ['free', None]):
                        should_update = False
                        logger.info(f"User {user['id']} already has active premium subscription {stripe_sub.id}")
                
                if should_update:
                    # Determine plan based on interval
                    plan_name = 'premium_monthly'
                    if stripe_sub.items.data[0].price.recurring.interval == 'year':
                        plan_name = 'premium_annual'
                    
                    plan = db.get_subscription_plan_by_name(plan_name)
                    if plan:
                        from datetime import datetime
                        success = db.upsert_user_subscription(
                            user_id=user['id'],
                            plan_id=plan['plan_id'],
                            stripe_subscription_id=stripe_sub.id,
                            stripe_customer_id=stripe_customer_id,
                            status=stripe_sub.status,  # Use actual Stripe status
                            current_period_start=datetime.fromtimestamp(stripe_sub.current_period_start),
                            current_period_end=datetime.fromtimestamp(stripe_sub.current_period_end)
                        )
                        if success:
                            subscription_activated = True
                            logger.info(f"✅ Subscription provisioned for user {user['id']}: {plan_name} (status: {stripe_sub.status})")
                        else:
                            logger.error(f"Failed to upsert subscription for user {user['id']}")
                    else:
                        logger.error(f"Plan not found: {plan_name}")
                else:
                    subscription_activated = True  # Already active
            else:
                logger.warning(f"Checkout session for user {user['id']} not ready: payment_status={checkout_session.payment_status}")
                
        except Exception as e:
            logger.error(f"Error provisioning subscription from checkout for user {user['id']}: {e}", exc_info=True)
    
    return render_template("checkout_success.html", session_id=session_id, subscription_activated=subscription_activated)


@app.route("/checkout/cancel")
@login_required
def checkout_cancel():
    """Handle cancelled checkout"""
    flash('Checkout was cancelled. No charges were made.', 'info')
    return redirect(url_for('pricing'))


@app.route("/account/billing")
@login_required
def billing():
    """User billing/subscription management"""
    import stripe_utils
    
    user = get_current_user()
    subscription = db.get_user_subscription(user['id'])
    payment_history = db.get_user_payment_history(user['id'])
    
    # Generate portal link if user has a subscription
    portal_url = None
    if subscription and subscription.get('stripe_customer_id'):
        try:
            portal_session = stripe_utils.create_billing_portal_session(
                subscription['stripe_customer_id'],
                url_for('billing', _external=True)
            )
            portal_url = portal_session.url
        except Exception as e:
            logger.error(f"Failed to create billing portal session: {e}")
    
    return render_template("billing.html",
                          subscription=subscription,
                          payment_history=payment_history,
                          portal_url=portal_url)


@app.route("/account/cancel-subscription", methods=["POST"])
@login_required
def cancel_subscription():
    """Cancel user's subscription at period end"""
    import stripe_utils
    
    user = get_current_user()
    subscription = db.get_user_subscription(user['id'])
    
    if not subscription or not subscription.get('stripe_subscription_id'):
        flash('No active subscription found.', 'error')
        return redirect(url_for('billing'))
    
    try:
        # Cancel at period end (user keeps access until then)
        stripe_utils.cancel_subscription(subscription['stripe_subscription_id'], at_period_end=True)
        
        # Update local database
        db.update_user_subscription_cancel_at_period_end(user['id'], True)
        
        flash('Your subscription has been cancelled. You will have access until the end of your billing period.', 'success')
        logger.info(f"User {user['id']} cancelled subscription {subscription['stripe_subscription_id']}")
    except Exception as e:
        logger.error(f"Failed to cancel subscription for user {user['id']}: {e}")
        flash('Failed to cancel subscription. Please try again or contact support.', 'error')
    
    return redirect(url_for('billing'))


@app.route("/account/reactivate-subscription", methods=["POST"])
@login_required
def reactivate_subscription():
    """Reactivate a subscription that was set to cancel"""
    import stripe_utils
    
    user = get_current_user()
    subscription = db.get_user_subscription(user['id'])
    
    if not subscription or not subscription.get('stripe_subscription_id'):
        flash('No subscription found to reactivate.', 'error')
        return redirect(url_for('billing'))
    
    try:
        # Reactivate subscription
        stripe_utils.reactivate_subscription(subscription['stripe_subscription_id'])
        
        # Update local database
        db.update_user_subscription_cancel_at_period_end(user['id'], False)
        
        flash('Your subscription has been reactivated! You will continue to be billed.', 'success')
        logger.info(f"User {user['id']} reactivated subscription {subscription['stripe_subscription_id']}")
    except Exception as e:
        logger.error(f"Failed to reactivate subscription for user {user['id']}: {e}")
        flash('Failed to reactivate subscription. Please try again or contact support.', 'error')
    
    return redirect(url_for('billing'))


@app.route("/webhooks/stripe", methods=["POST"])
@csrf.exempt  # Stripe webhooks don't use CSRF tokens
@limiter.exempt
def stripe_webhook():
    """Handle Stripe webhook events"""
    import stripe_utils
    
    payload = request.get_data()
    sig_header = request.headers.get('Stripe-Signature')
    
    if not sig_header:
        return jsonify({'error': 'No signature'}), 400
    
    try:
        event = stripe_utils.construct_webhook_event(payload, sig_header)
    except ValueError as e:
        logger.error(f"Invalid webhook payload: {e}")
        return jsonify({'error': 'Invalid payload'}), 400
    except Exception as e:
        logger.error(f"Webhook signature verification failed: {e}")
        return jsonify({'error': 'Invalid signature'}), 400
    
    # Process the event
    try:
        stripe_utils.process_webhook_event(event)
    except Exception as e:
        logger.error(f"Webhook processing error: {e}")
        # Still return 200 to acknowledge receipt
    
    return jsonify({'status': 'received'}), 200


@app.route("/feed")
@login_required
def my_feed():
    """Personalized feed based on subscriptions"""
    user = get_current_user()
    subscriptions = db.get_user_subscriptions(user['id'])
    
    page = request.args.get('page', 1, type=int)
    per_page = 12
    posts, total = db.get_subscribed_posts(user['id'], page=page, per_page=per_page)
    total_pages = (total + per_page - 1) // per_page
    
    return render_template(
        "feed.html", 
        posts=posts, 
        subscriptions=subscriptions,
        page=page,
        total_pages=total_pages,
        total_posts=total
    )


# ============== Bookmark Routes ==============

@app.route("/bookmark/<int:post_id>", methods=["POST"])
@login_required
def bookmark_post(post_id):
    """Bookmark a post"""
    user = get_current_user()
    post = db.get_post_by_id(post_id)
    
    if not post:
        abort(404)
    
    if db.is_bookmarked(user['id'], post_id):
        flash('Post already bookmarked.', 'info')
    else:
        db.add_bookmark(user['id'], post_id)
        flash('Post bookmarked!', 'success')
    
    # Return to the page they came from
    return redirect(request.referrer or url_for('post', post_id=post_id))


@app.route("/unbookmark/<int:post_id>", methods=["POST"])
@login_required
def unbookmark_post(post_id):
    """Remove a bookmark"""
    user = get_current_user()
    
    db.remove_bookmark(user['id'], post_id)
    flash('Bookmark removed.', 'info')
    
    return redirect(request.referrer or url_for('bookmarks'))


@app.route("/bookmarks")
@login_required
def bookmarks():
    """View all bookmarked posts"""
    user = get_current_user()
    
    page = request.args.get('page', 1, type=int)
    per_page = 12
    posts, total = db.get_user_bookmarks(user['id'], page=page, per_page=per_page)
    total_pages = (total + per_page - 1) // per_page
    
    return render_template(
        "bookmarks.html",
        posts=posts,
        page=page,
        total_pages=total_pages,
        total_posts=total
    )


# ============== Admin Routes ==============

@app.route("/admin")
@admin_required
def admin_dashboard():
    """Admin dashboard with statistics and overview"""
    stats = db.get_admin_statistics()
    api_usage = db.get_api_usage_stats(days=30)
    cron_stats = db.get_cron_stats()
    recent_cron_logs = db.get_cron_logs(limit=10)
    return render_template("admin/dashboard.html", 
                          stats=stats, 
                          api_usage=api_usage,
                          cron_stats=cron_stats,
                          recent_cron_logs=recent_cron_logs)


@app.route("/admin/cron-logs")
@admin_required
def admin_cron_logs():
    """Admin page to view cron job execution logs"""
    job_type = request.args.get('type')
    limit = request.args.get('limit', 50, type=int)
    
    logs = db.get_cron_logs(limit=limit, job_type=job_type)
    cron_stats = db.get_cron_stats()
    
    return render_template(
        "admin/cron_logs.html",
        logs=logs,
        cron_stats=cron_stats,
        job_type=job_type,
        limit=limit
    )


@app.route("/admin/api-errors")
@admin_required
def admin_api_errors():
    """Admin page to view API error logs"""
    page = request.args.get('page', 1, type=int)
    days = request.args.get('days', 30, type=int)
    per_page = 50
    
    errors, total = db.get_api_errors(days=days, page=page, per_page=per_page)
    error_summary = db.get_api_error_summary(days=days)
    total_pages = (total + per_page - 1) // per_page
    
    return render_template(
        "admin/api_errors.html",
        errors=errors,
        error_summary=error_summary,
        page=page,
        total_pages=total_pages,
        total_errors=total,
        days=days
    )


@app.route("/admin/users")
@admin_required
def admin_users():
    """Admin user management page"""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    users, total = db.get_all_users(page=page, per_page=per_page)
    total_pages = (total + per_page - 1) // per_page
    
    return render_template(
        "admin/users.html",
        users=users,
        page=page,
        total_pages=total_pages,
        total_users=total
    )


@app.route("/admin/users/<int:user_id>/toggle-admin", methods=["POST"])
@admin_required
def admin_toggle_admin(user_id):
    """Toggle admin status for a user"""
    current_user = get_current_user()
    
    # Prevent self-demotion
    if current_user['id'] == user_id:
        flash('You cannot change your own admin status.', 'error')
        return redirect(url_for('admin_users'))
    
    user = db.get_user_by_id(user_id)
    if user:
        new_status = not user.get('is_admin', False)
        db.toggle_user_admin(user_id, new_status)
        action = "promoted to" if new_status else "demoted from"
        flash(f'{user["username"]} {action} admin.', 'success')
    
    return redirect(url_for('admin_users'))


@app.route("/admin/users/<int:user_id>/toggle-active", methods=["POST"])
@admin_required
def admin_toggle_active(user_id):
    """Toggle active status for a user"""
    current_user = get_current_user()
    
    # Prevent self-deactivation
    if current_user['id'] == user_id:
        flash('You cannot deactivate your own account.', 'error')
        return redirect(url_for('admin_users'))
    
    user = db.get_user_by_id(user_id)
    if user:
        new_status = not user.get('is_active', True)
        db.toggle_user_active(user_id, new_status)
        action = "activated" if new_status else "deactivated"
        flash(f'{user["username"]} account {action}.', 'success')
    
    return redirect(url_for('admin_users'))


@app.route("/admin/users/<int:user_id>")
@admin_required
def admin_view_user(user_id):
    """Admin view user details with comments"""
    user = db.get_user_by_id(user_id)
    if not user:
        flash('User not found.', 'error')
        return redirect(url_for('admin_users'))

    comments = db.get_comments_by_user(user_id, limit=50)
    subscriptions = db.get_user_subscriptions(user_id)
    bookmarks = db.get_user_bookmarks(user_id)
    premium_subscription = db.get_user_subscription(user_id)  # Get premium subscription status
    is_premium = db.is_user_premium(user_id)

    return render_template(
        "admin/user_detail.html",
        user=user,
        comments=comments,
        subscriptions=subscriptions,
        bookmarks=bookmarks,
        premium_subscription=premium_subscription,
        is_premium=is_premium
    )


@app.route("/admin/comments")
@admin_required
def admin_comments():
    """Admin comment moderation page"""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    comments, total = db.get_spam_comments(page=page, per_page=per_page)
    total_pages = (total + per_page - 1) // per_page
    
    return render_template(
        "admin/comments.html",
        comments=comments,
        page=page,
        total_pages=total_pages,
        total_comments=total
    )


@app.route("/admin/comments/<int:comment_id>/approve", methods=["POST"])
@admin_required
def admin_approve_comment(comment_id):
    """Mark a comment as not spam"""
    db.mark_comment_not_spam(comment_id)
    flash('Comment approved.', 'success')
    return redirect(url_for('admin_comments'))


@app.route("/admin/comments/<int:comment_id>/delete", methods=["POST"])
@admin_required
def admin_delete_comment(comment_id):
    """Delete a comment"""
    db.delete_comment(comment_id)
    flash('Comment deleted.', 'success')
    return redirect(url_for('admin_comments'))


@app.route("/admin/generate-posts", methods=["POST"])
@admin_required
def admin_generate_posts():
    """Manually trigger post generation for all tools"""
    import threading
    
    def generate_async():
        ai_generators.generate_all_posts(app=app)
    
    thread = threading.Thread(target=generate_async, daemon=True)
    thread.start()
    
    flash('Post generation started in background. Check back in a few minutes.', 'info')
    return redirect(url_for('admin_dashboard'))


@app.route("/admin/generate-posts/<tool_slug>", methods=["POST"])
@admin_required
def admin_generate_single_post(tool_slug):
    """Manually trigger post generation for a specific tool"""
    import threading
    
    def generate_async():
        ai_generators.generate_post_for_tool(tool_slug, app=app)
    
    thread = threading.Thread(target=generate_async, daemon=True)
    thread.start()
    
    flash(f'Post generation for {tool_slug} started. Check back in a few minutes.', 'info')
    return redirect(url_for('admin_dashboard'))


@app.route("/admin/sync-subscription/<int:user_id>", methods=["POST"])
@admin_required
def admin_sync_subscription(user_id):
    """Manually sync a user's subscription from Stripe to database"""
    import stripe
    from datetime import datetime
    from config import Config

    # Initialize Stripe
    stripe.api_key = Config.STRIPE_SECRET_KEY

    try:
        user = db.get_user_by_id(user_id)
        if not user:
            return jsonify({'success': False, 'error': 'User not found'}), 404

        # Get Stripe customer ID
        stripe_customer_id = user.get('stripe_customer_id')
        if not stripe_customer_id:
            # Try to find by email
            customers = stripe.Customer.list(email=user['email'], limit=1)
            if customers.data:
                stripe_customer_id = customers.data[0].id
                db.update_user_stripe_customer_id(user_id, stripe_customer_id)
            else:
                return jsonify({'success': False, 'error': 'No Stripe customer found for this user'}), 404

        # Get active subscriptions from Stripe
        logger.info(f"Fetching Stripe subscriptions for customer: {stripe_customer_id}")
        subscriptions = stripe.Subscription.list(
            customer=stripe_customer_id,
            status='all',
            limit=10
        )
        logger.info(f"Subscriptions type: {type(subscriptions)}, has data: {hasattr(subscriptions, 'data')}")

        # Find active subscription ID
        active_sub_id = None
        for sub in subscriptions.data:
            # Access status using getattr to handle both dict and object
            status = getattr(sub, 'status', None) or sub.get('status') if isinstance(sub, dict) else sub.status
            sub_id = getattr(sub, 'id', None) or sub.get('id') if isinstance(sub, dict) else sub.id

            if status in ['active', 'trialing']:
                active_sub_id = sub_id
                break

        if not active_sub_id:
            return jsonify({'success': False, 'error': 'No active subscription found in Stripe'}), 404

        # Retrieve the full subscription object WITHOUT expand (to get all standard fields)
        logger.info(f"Retrieving full subscription object: {active_sub_id}")
        active_sub = stripe.Subscription.retrieve(active_sub_id)

        logger.info(f"Retrieved subscription - has current_period_start: {active_sub.get('current_period_start', 'MISSING')}")

        # Access interval from plan (since subscription object has 'plan' field)
        interval = active_sub.get('plan', {}).get('interval', 'month')
        plan_name = 'premium_annual' if interval == 'year' else 'premium_monthly'

        # Get plan from database
        plan = db.get_subscription_plan_by_name(plan_name)
        if not plan:
            return jsonify({'success': False, 'error': f'Plan {plan_name} not found in database'}), 404

        # Get period fields with fallback to billing_cycle_anchor or start_date
        period_start = active_sub.get('current_period_start') or active_sub.get('billing_cycle_anchor') or active_sub.get('start_date')
        period_end = active_sub.get('current_period_end')

        if not period_start:
            return jsonify({'success': False, 'error': f'Missing period start in subscription. Available fields: {list(active_sub.keys())}'}), 500

        # If period_end doesn't exist, calculate it based on interval
        if not period_end:
            if interval == 'year':
                # Add 365 days worth of seconds
                period_end = period_start + (365 * 24 * 60 * 60)
            else:  # month
                # Add 30 days worth of seconds (approximation)
                period_end = period_start + (30 * 24 * 60 * 60)
            logger.info(f"Calculated period_end from interval {interval}: {datetime.fromtimestamp(period_end)}")

        # Update subscription
        success = db.upsert_user_subscription(
            user_id=user_id,
            plan_id=plan['plan_id'],
            stripe_subscription_id=active_sub['id'],
            stripe_customer_id=stripe_customer_id,
            status=active_sub['status'],
            current_period_start=datetime.fromtimestamp(period_start),
            current_period_end=datetime.fromtimestamp(period_end)
        )

        if success:
            # Verify subscription was created correctly
            sub_check = db.get_user_subscription(user_id)
            is_premium = db.is_user_premium(user_id)

            logger.info(f"✅ Admin synced subscription for user {user_id}: {plan_name} (status: {active_sub.status})")
            logger.info(f"Verification - Subscription in DB: plan={sub_check.get('plan_name') if sub_check else 'None'}, status={sub_check.get('status') if sub_check else 'None'}, is_premium={is_premium}")

            return jsonify({
                'success': True,
                'message': f'Subscription synced successfully',
                'plan': plan_name,
                'status': active_sub.status,
                'is_premium': is_premium,
                'db_plan': sub_check.get('plan_name') if sub_check else None,
                'period_end': sub_check.get('current_period_end').isoformat() if sub_check and sub_check.get('current_period_end') else None
            })
        else:
            return jsonify({'success': False, 'error': 'Failed to update subscription in database'}), 500

    except Exception as e:
        logger.error(f"Error syncing subscription for user {user_id}: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route("/admin/check-subscription/<int:user_id>")
@admin_required
def admin_check_subscription(user_id):
    """Diagnostic endpoint to check subscription status"""
    try:
        user = db.get_user_by_id(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404

        # Get subscription from database
        subscription = db.get_user_subscription(user_id)
        is_premium = db.is_user_premium(user_id)

        # Get all plans for reference
        connection = db.get_connection()
        all_plans = []
        if connection:
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT plan_id, name, display_name FROM SubscriptionPlan")
                    all_plans = [{'plan_id': row[0], 'name': row[1], 'display_name': row[2]} for row in cursor.fetchall()]
            finally:
                connection.close()

        return jsonify({
            'user_id': user_id,
            'username': user['username'],
            'email': user['email'],
            'is_premium': is_premium,
            'subscription': {
                'plan_id': subscription.get('plan_id') if subscription else None,
                'plan_name': subscription.get('plan_name') if subscription else None,
                'status': subscription.get('status') if subscription else None,
                'current_period_end': subscription.get('current_period_end').isoformat() if subscription and subscription.get('current_period_end') else None,
                'stripe_subscription_id': subscription.get('stripe_subscription_id') if subscription else None,
            } if subscription else None,
            'available_plans': all_plans
        })
    except Exception as e:
        logger.error(f"Error checking subscription for user {user_id}: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


# ============== Cron Endpoints (for external scheduler like Dokploy) ==============

@app.route("/cron/generate-posts")
@limiter.exempt
def cron_generate_posts():
    """Cron endpoint for scheduled post generation (called by Dokploy)"""
    token = request.args.get('token')
    if not token or token != Config.CRON_SECRET:
        logger.warning("Unauthorized cron attempt")
        abort(403)
    
    # Log cron job start
    log_id = db.log_cron_start('generate_posts')
    
    try:
        logger.info("Cron: Starting post generation...")
        posts_count = ai_generators.generate_all_posts(app=app)
        logger.info("Cron: Post generation complete")
        
        # Log successful completion
        db.log_cron_complete(log_id, posts_generated=posts_count if posts_count else 0)
        
        return jsonify({'success': True, 'message': 'Post generation complete', 'posts_generated': posts_count})
    except Exception as e:
        # Log failure
        error_msg = str(e)
        logger.error(f"Cron job failed: {error_msg}")
        db.log_cron_failure(log_id, error_msg)
        return jsonify({'success': False, 'error': error_msg}), 500


@app.route("/cron/cleanup")
@limiter.exempt
def cron_cleanup():
    """Cron endpoint for scheduled cleanup tasks (called by Dokploy)"""
    token = request.args.get('token')
    if not token or token != Config.CRON_SECRET:
        logger.warning("Unauthorized cron attempt")
        abort(403)
    
    # Log cron job start
    log_id = db.log_cron_start('cleanup')
    
    try:
        logger.info("Cron: Running cleanup tasks...")
        
        # Cleanup spam comments older than configured days
        spam_deleted = db.delete_old_spam_comments(days=Config.SPAM_MAX_AGE_DAYS)
        logger.info(f"Cron: Deleted {spam_deleted} old spam comments (>{Config.SPAM_MAX_AGE_DAYS} days old)")
        
        # Cleanup old notifications
        notif_deleted = db.delete_old_notifications(Config.NOTIFICATIONS_MAX_AGE_DAYS)
        logger.info(f"Cron: Deleted {notif_deleted} old notifications")
        
        # Log successful completion
        db.log_cron_complete(
            log_id, 
            spam_deleted=spam_deleted, 
            notifications_deleted=notif_deleted,
            details={'spam_max_age_days': Config.SPAM_MAX_AGE_DAYS, 'notif_max_age_days': Config.NOTIFICATIONS_MAX_AGE_DAYS}
        )
        
        return jsonify({
            'success': True,
            'spam_deleted': spam_deleted,
            'notifications_deleted': notif_deleted
        })
    except Exception as e:
        # Log failure
        error_msg = str(e)
        logger.error(f"Cron cleanup failed: {error_msg}")
        db.log_cron_failure(log_id, error_msg)
        return jsonify({'success': False, 'error': error_msg}), 500


@app.route("/cron/recompute-stats")
@limiter.exempt
def cron_recompute_stats():
    """Cron endpoint for recomputing tool leaderboard stats"""
    token = request.args.get('token')
    if not token or token != Config.CRON_SECRET:
        logger.warning("Unauthorized cron attempt for recompute-stats")
        abort(403)

    try:
        logger.info("Cron: Recomputing tool stats...")
        result = db.recompute_tool_stats()
        h2h_result = db.recompute_h2h_stats()
        user_stats_result = db.recompute_stale_user_stats()
        if result:
            logger.info(f"Cron: Tool stats recomputed — {result['tools_updated']} rows in {result['duration_ms']}ms")
            if h2h_result:
                logger.info(f"Cron: H2H stats recomputed — {h2h_result['pairs_updated']} pairs in {h2h_result['duration_ms']}ms")
            if user_stats_result:
                logger.info(f"Cron: User vote stats recomputed — {user_stats_result['users_updated']} users in {user_stats_result['duration_ms']}ms")
            response = {'success': True, **result}
            if h2h_result:
                response['h2h_pairs_updated'] = h2h_result['pairs_updated']
                response['h2h_duration_ms'] = h2h_result['duration_ms']
            if user_stats_result:
                response['user_stats_updated'] = user_stats_result['users_updated']
            return jsonify(response)
        return jsonify({'success': False, 'error': 'Recomputation returned None'}), 500
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Cron recompute-stats failed: {error_msg}")
        return jsonify({'success': False, 'error': error_msg}), 500


# ============== Error Handlers ==============

@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404


@app.errorhandler(500)
def server_error(e):
    return render_template('500.html'), 500


# ============== Content Metrics Helper ==============

def calculate_content_metrics(content):
    """Calculate style metrics for content"""
    import re
    from html import unescape

    # Strip HTML tags
    text = re.sub(r'<[^>]+>', '', content)
    text = unescape(text)

    words = text.split()
    word_count = len(words)

    sentences = re.split(r'[.!?]+', text)
    sentence_count = len([s for s in sentences if s.strip()])

    avg_words_per_sentence = word_count / sentence_count if sentence_count > 0 else 0

    paragraphs = [p for p in text.split('\n\n') if p.strip()]
    paragraph_count = len(paragraphs) or 1

    unique_words = len(set(w.lower() for w in words))
    vocab_richness = (unique_words / word_count * 100) if word_count > 0 else 0

    syllable_estimate = sum(1 for word in words for char in word if char.lower() in 'aeiou')
    avg_syllables = syllable_estimate / word_count if word_count > 0 else 0
    reading_level = round(0.39 * avg_words_per_sentence + 11.8 * avg_syllables - 15.59, 1)
    reading_level = max(0, min(18, reading_level))

    return {
        'word_count': word_count,
        'sentence_count': sentence_count,
        'paragraph_count': paragraph_count,
        'avg_words_per_sentence': round(avg_words_per_sentence, 1),
        'vocab_richness': round(vocab_richness, 1),
        'reading_level': reading_level
    }


# ============== Dashboard Routes ==============

@app.route("/dashboard")
def dashboard():
    """Compare & Vote Dashboard — leaderboard and analytics"""
    return render_template("dashboard.html")


@app.route("/api/dashboard/leaderboard")
@premium_required
def api_dashboard_leaderboard():
    """API: Get leaderboard data for a category (premium only)"""
    category = request.args.get('category', 'overall')
    min_votes = request.args.get('min_votes', 30, type=int)

    if category not in db.VOTE_CATEGORIES:
        return jsonify({
            'error': {
                'code': 'INVALID_CATEGORY',
                'message': f'Invalid category. Must be one of: {", ".join(db.VOTE_CATEGORIES)}',
                'details': {}
            }
        }), 400

    # Check cache
    cache_key = (category, min_votes)
    cached = db._leaderboard_cache.get(cache_key)
    if cached is not None:
        data, age = cached
        data['cached'] = True
        data['cache_age_seconds'] = round(age, 1)
        return jsonify(data)

    above, below = db.get_tool_stats_for_leaderboard(category, min_votes)

    # Build leaderboard with competition ranking
    leaderboard = []
    rank = 1
    for i, tool in enumerate(above):
        if i > 0 and tool['win_rate'] != above[i - 1]['win_rate']:
            rank = i + 1

        # Confidence badge
        tv = tool['total_votes']
        if tv >= 100:
            confidence = 'high'
        elif tv >= 30:
            confidence = 'medium'
        else:
            confidence = 'low'

        # Trend delta
        if tool['win_rate_7d'] is not None and tool['win_rate_prev_7d'] is not None and tool['votes_last_7d'] >= 5:
            delta_val = (tool['win_rate_7d'] - tool['win_rate_prev_7d']) * 100
            trend_delta = f"{delta_val:+.1f}%"
        else:
            trend_delta = None

        # Category breakdown
        breakdown = db.get_tool_category_breakdown(tool['tool_id'])

        leaderboard.append({
            'rank': rank,
            'tool_id': tool['tool_id'],
            'tool_name': tool['name'],
            'tool_slug': tool['slug'],
            'total_votes': tool['total_votes'],
            'total_wins': tool['total_wins'],
            'win_rate': tool['win_rate'],
            'win_rate_display': f"{tool['win_rate'] * 100:.1f}%",
            'votes_last_7d': tool['votes_last_7d'],
            'win_rate_7d': tool['win_rate_7d'],
            'trend': tool['trend'],
            'trend_delta': trend_delta,
            'confidence': confidence,
            'category_breakdown': breakdown,
        })

    # Below threshold
    below_list = []
    for tool in below:
        entry = {
            'tool_id': tool['tool_id'],
            'tool_name': tool['name'],
            'tool_slug': tool['slug'],
            'status': tool['status'],
            'total_votes': tool['total_votes'],
        }
        if tool['status'] == 'pending':
            entry['message'] = 'Pending release'
        else:
            entry['message'] = f"{tool['total_votes']} votes so far"
        below_list.append(entry)

    computed_at = above[0]['computed_at'] if above else (below[0]['computed_at'] if below else None)

    response_data = {
        'success': True,
        'category': category,
        'min_votes': min_votes,
        'computed_at': computed_at,
        'leaderboard': leaderboard,
        'below_threshold': below_list,
        'cached': False,
        'cache_age_seconds': 0,
    }

    db._leaderboard_cache.set(cache_key, response_data)
    return jsonify(response_data)


@app.route("/api/dashboard/leaderboard/teaser")
def api_dashboard_leaderboard_teaser():
    """API: Get limited leaderboard teaser (no auth required)"""
    above, _ = db.get_tool_stats_for_leaderboard('overall', min_votes=0)

    teaser = []
    for tool in above[:2]:
        wr = tool['win_rate']
        # Round to nearest 5%
        rounded = round(wr * 20) * 5
        teaser.append({
            'tool_name': tool['name'],
            'tool_slug': tool['slug'],
            'win_rate_rounded': rounded,
        })

    return jsonify({
        'success': True,
        'teaser': teaser,
    })


@app.route("/api/dashboard/matrix")
@premium_required
def api_dashboard_matrix():
    """API: Get head-to-head matrix data for a category (premium only)"""
    category = request.args.get('category', 'overall')

    if category not in db.VOTE_CATEGORIES:
        return jsonify({
            'error': {
                'code': 'INVALID_CATEGORY',
                'message': f'Invalid category. Must be one of: {", ".join(db.VOTE_CATEGORIES)}',
                'details': {}
            }
        }), 400

    # Check cache
    cache_key = ('matrix', category)
    cached = db._leaderboard_cache.get(cache_key)
    if cached is not None:
        data, age = cached
        data['cached'] = True
        data['cache_age_seconds'] = round(age, 1)
        return jsonify(data)

    matrix_data = db.get_h2h_matrix(category)
    if matrix_data is None:
        return jsonify({'success': False, 'error': 'Failed to load matrix data'}), 500

    response_data = {
        'success': True,
        'category': category,
        'tools': matrix_data['tools'],
        'cells': matrix_data['cells'],
        'computed_at': matrix_data['computed_at'],
        'cached': False,
        'cache_age_seconds': 0,
    }

    db._leaderboard_cache.set(cache_key, response_data)
    return jsonify(response_data)


@app.route("/api/dashboard/matrix/pair/<slug_a>/<slug_b>")
@premium_required
def api_dashboard_matrix_pair(slug_a, slug_b):
    """API: Get detailed head-to-head data for a specific tool pair (premium only)"""
    tool_a = db.get_tool_by_slug(slug_a)
    tool_b = db.get_tool_by_slug(slug_b)

    if not tool_a or not tool_b:
        return jsonify({
            'error': {
                'code': 'TOOL_NOT_FOUND',
                'message': 'One or both tools not found',
                'details': {}
            }
        }), 404

    if tool_a['id'] == tool_b['id']:
        return jsonify({
            'error': {
                'code': 'SAME_TOOL',
                'message': 'Cannot compare a tool with itself',
                'details': {}
            }
        }), 400

    # Canonical ordering by integer ID
    id_a, id_b = tool_a['id'], tool_b['id']
    canonical_a_id = min(id_a, id_b)
    canonical_b_id = max(id_a, id_b)

    # Check cache
    cache_key = ('h2h_pair', canonical_a_id, canonical_b_id)
    cached = db._leaderboard_cache.get(cache_key)
    if cached is not None:
        data, age = cached
        data['cached'] = True
        data['cache_age_seconds'] = round(age, 1)
        return jsonify(data)

    detail = db.get_h2h_pair_detail(canonical_a_id, canonical_b_id)
    if detail is None:
        return jsonify({'success': False, 'error': 'Failed to load pair detail'}), 500

    # Determine which tool info is A and B in canonical order
    if tool_a['id'] == canonical_a_id:
        info_a, info_b = tool_a, tool_b
    else:
        info_a, info_b = tool_b, tool_a

    # Check user votes on recent matchups
    user_id = session.get('user_id')
    for matchup in detail['recent_matchups']:
        matchup['user_has_voted'] = False
        if user_id:
            votes = db.get_user_votes_for_matchup(user_id, matchup['matchup_id'])
            if votes:
                matchup['user_has_voted'] = True

    response_data = {
        'success': True,
        'tool_a': {'tool_id': info_a['id'], 'name': info_a['name'], 'slug': info_a['slug']},
        'tool_b': {'tool_id': info_b['id'], 'name': info_b['name'], 'slug': info_b['slug']},
        'categories': detail['categories'],
        'recent_matchups': detail['recent_matchups'],
        'total_matchups': detail['total_matchups'],
        'cached': False,
        'cache_age_seconds': 0,
    }

    db._leaderboard_cache.set(cache_key, response_data)
    return jsonify(response_data)


@app.route("/dashboard/history")
@premium_required
def dashboard_history():
    """Personal Voting History page (premium only)"""
    return render_template("dashboard_history.html")


@app.route("/api/users/me/vote-stats")
@premium_required
def api_user_vote_stats():
    """API: Get personal vote stats for the current user (premium only)"""
    user = get_current_user()
    stats = db.get_user_vote_stats(user['id'])
    if stats is None:
        return jsonify({'success': True, 'empty': True})
    return jsonify(stats)


@app.route("/api/users/me/votes")
@premium_required
def api_user_vote_history():
    """API: Get paginated personal vote history (premium only)"""
    user = get_current_user()
    page = request.args.get('page', 1, type=int)
    limit = min(request.args.get('limit', 20, type=int), 50)
    tool_slug = request.args.get('tool')
    category = request.args.get('category')
    alignment = request.args.get('alignment')
    sort = request.args.get('sort', 'newest')

    if category and category not in db.VOTE_CATEGORIES:
        return jsonify({'error': {
            'code': 'INVALID_CATEGORY',
            'message': f'Invalid category. Must be one of: {", ".join(db.VOTE_CATEGORIES)}',
            'details': {}
        }}), 400

    if alignment and alignment not in ('majority', 'minority'):
        return jsonify({'error': {
            'code': 'INVALID_ALIGNMENT',
            'message': 'Alignment must be "majority" or "minority".',
            'details': {}
        }}), 400

    if sort not in ('newest', 'oldest'):
        return jsonify({'error': {
            'code': 'INVALID_SORT',
            'message': 'Sort must be "newest" or "oldest".',
            'details': {}
        }}), 400

    result = db.get_user_vote_history(
        user['id'], page=page, limit=limit,
        tool_slug=tool_slug, category=category,
        alignment=alignment, sort=sort
    )
    if result is None:
        return jsonify({'success': False, 'error': 'Failed to load vote history'}), 500
    return jsonify(result)


@app.route("/dashboard/tools/<slug>")
def dashboard_tool_detail(slug):
    """Placeholder for tool detail page (Phase 3)"""
    tool = db.get_tool_by_slug(slug)
    if not tool:
        abort(404)
    return render_template("dashboard.html", placeholder_tool=tool)


# ============== Compare & Vote Routes ==============

@app.route("/compare")
def compare_page():
    """Matchup listing page — browse active matchups"""
    page = request.args.get('page', 1, type=int)
    matchups, total = db.get_active_matchups(page=page, per_page=12)
    total_pages = (total + 11) // 12
    return render_template(
        "compare.html",
        matchups=matchups,
        page=page,
        total_pages=total_pages,
        total=total
    )


@app.route("/compare/<int:matchup_id>")
def view_matchup(matchup_id):
    """Compare view — blind side-by-side post comparison with voting"""
    matchup = db.get_matchup(matchup_id)
    if not matchup or matchup['status'] != 'active':
        abort(404)

    user = get_current_user()
    user_id = user['id'] if user else 0
    is_premium = db.is_user_premium(user_id) if user else False

    # Determine left/right position assignment
    position_a_is_left = ((matchup['position_seed'] + user_id) % 2 == 0)

    # Assign posts to left/right based on position
    if position_a_is_left:
        left_post = {
            'id': matchup['post_a_id'], 'title': matchup['title_a'],
            'content': matchup['content_a'], 'category': matchup['category_a'],
            'side': 'a'
        }
        right_post = {
            'id': matchup['post_b_id'], 'title': matchup['title_b'],
            'content': matchup['content_b'], 'category': matchup['category_b'],
            'side': 'b'
        }
    else:
        left_post = {
            'id': matchup['post_b_id'], 'title': matchup['title_b'],
            'content': matchup['content_b'], 'category': matchup['category_b'],
            'side': 'b'
        }
        right_post = {
            'id': matchup['post_a_id'], 'title': matchup['title_a'],
            'content': matchup['content_a'], 'category': matchup['category_a'],
            'side': 'a'
        }

    # Calculate content metrics
    left_post['metrics'] = calculate_content_metrics(left_post['content'] or '')
    right_post['metrics'] = calculate_content_metrics(right_post['content'] or '')

    # Get user's existing votes and determine view state
    user_votes = []
    has_voted = False
    votes_locked = False
    earliest_vote_time = None
    if user:
        user_votes = db.get_user_votes_for_matchup(user_id, matchup_id)
        has_voted = len(user_votes) > 0
        if has_voted:
            votes_locked = user_votes[0]['locked']
            earliest_vote_time = min(v['voted_at'] for v in user_votes)

    # Build results data (only if user has voted AND is premium)
    results = None
    if has_voted and is_premium:
        vote_counts = db.get_matchup_vote_counts(matchup_id)
        results = {}
        for cat in db.VOTE_CATEGORIES:
            cat_counts = vote_counts.get(cat, {})
            tool_a_count = cat_counts.get(matchup['tool_a'], 0)
            tool_b_count = cat_counts.get(matchup['tool_b'], 0)
            cat_total = tool_a_count + tool_b_count
            results[cat] = {
                'tool_a_votes': tool_a_count,
                'tool_b_votes': tool_b_count,
                'tool_a_pct': round(tool_a_count / cat_total * 100) if cat_total > 0 else 0,
                'tool_b_pct': round(tool_b_count / cat_total * 100) if cat_total > 0 else 0,
                'total': cat_total
            }

    total_vote_count = db.get_matchup_total_votes(matchup_id)

    # Map user_votes to left/right for template
    user_vote_map = {}
    for v in user_votes:
        if v['winner_tool'] == matchup['tool_a']:
            winner_side = 'left' if position_a_is_left else 'right'
        else:
            winner_side = 'right' if position_a_is_left else 'left'
        user_vote_map[v['category']] = winner_side

    return render_template(
        "comparison.html",
        matchup=matchup,
        left_post=left_post,
        right_post=right_post,
        position_a_is_left=position_a_is_left,
        is_premium=is_premium,
        has_voted=has_voted,
        votes_locked=votes_locked,
        user_vote_map=user_vote_map,
        results=results,
        total_vote_count=total_vote_count,
        earliest_vote_time=earliest_vote_time.isoformat() if earliest_vote_time else None,
        vote_lock_minutes=db.VOTE_LOCK_MINUTES,
        vote_categories=db.VOTE_CATEGORIES
    )


def _format_vote_results(matchup, vote_counts):
    """Format vote counts into the standard results dict for API responses."""
    results = {}
    for cat in db.VOTE_CATEGORIES:
        cat_counts = vote_counts.get(cat, {})
        tool_a_count = cat_counts.get(matchup['tool_a'], 0)
        tool_b_count = cat_counts.get(matchup['tool_b'], 0)
        cat_total = tool_a_count + tool_b_count
        results[cat] = {
            'tool_a_name': matchup['tool_a_name'],
            'tool_b_name': matchup['tool_b_name'],
            'tool_a_votes': tool_a_count,
            'tool_b_votes': tool_b_count,
            'tool_a_pct': round(tool_a_count / cat_total * 100) if cat_total > 0 else 0,
            'tool_b_pct': round(tool_b_count / cat_total * 100) if cat_total > 0 else 0,
        }
    return results


def _map_votes_left_right(data_votes, matchup, position_a_is_left):
    """Map left/right winner sides to tool IDs. Returns (mapped_votes, error_response)."""
    mapped = []
    for v in data_votes:
        category = v.get('category')
        winner_side = v.get('winner')
        if winner_side not in ('left', 'right'):
            return None, (jsonify({'error': {
                'code': 'INVALID_WINNER',
                'message': f'Invalid winner side for {category}. Must be "left" or "right".',
                'details': {'category': category}
            }}), 400)
        if winner_side == 'left':
            winner_tool = matchup['tool_a'] if position_a_is_left else matchup['tool_b']
        else:
            winner_tool = matchup['tool_b'] if position_a_is_left else matchup['tool_a']
        mapped.append({'category': category, 'winner_tool': winner_tool})
    return mapped, None


@app.route("/api/matchups/<int:matchup_id>/votes", methods=["POST"])
@premium_required
@limiter.limit("30 per minute")
def api_batch_vote_matchup(matchup_id):
    """API: Submit a batch of votes on a matchup (atomic)."""
    user = get_current_user()
    data = request.get_json()
    if not data or 'votes' not in data or not isinstance(data['votes'], list):
        return jsonify({'error': {
            'code': 'INVALID_PAYLOAD',
            'message': 'Request must contain a votes array.',
            'details': {}
        }}), 400

    matchup = db.get_matchup(matchup_id)
    if not matchup:
        return jsonify({'error': {
            'code': 'MATCHUP_NOT_FOUND',
            'message': 'Matchup not found.',
            'details': {}
        }}), 404

    position_a_is_left = ((matchup['position_seed'] + user['id']) % 2 == 0)
    mapped_votes, err = _map_votes_left_right(data['votes'], matchup, position_a_is_left)
    if err:
        return err

    meta = {
        'ip': request.remote_addr,
        'read_time_seconds': data.get('read_time_seconds'),
        'batch_size': len(mapped_votes)
    }

    result = db.batch_submit_votes(
        user['id'], matchup_id, mapped_votes, position_a_is_left, meta)

    if not result['success']:
        return jsonify({'error': result['error']}), result['status_code']

    try:
        db.recompute_user_vote_stats(user['id'])
    except Exception:
        logger.warning(f"Failed to recompute user stats for user {user['id']}")

    vote_counts = db.get_matchup_vote_counts(matchup_id)
    results = _format_vote_results(matchup, vote_counts)

    return jsonify({
        'success': True,
        'vote_count': len(result['vote_ids']),
        'edit_window_expires_at': result.get('edit_window_expires_at'),
        'results': results,
        'tool_a_name': matchup['tool_a_name'],
        'tool_b_name': matchup['tool_b_name'],
        'tool_a_icon': matchup['tool_a_icon'],
        'tool_b_icon': matchup['tool_b_icon'],
        'position_a_is_left': position_a_is_left
    }), result['status_code']


@app.route("/api/matchups/<int:matchup_id>/votes", methods=["PATCH"])
@premium_required
@limiter.limit("30 per minute")
def api_batch_edit_votes(matchup_id):
    """API: Edit existing votes within the lock window (atomic)."""
    user = get_current_user()
    data = request.get_json()
    if not data or 'votes' not in data or not isinstance(data['votes'], list):
        return jsonify({'error': {
            'code': 'INVALID_PAYLOAD',
            'message': 'Request must contain a votes array.',
            'details': {}
        }}), 400

    matchup = db.get_matchup(matchup_id)
    if not matchup:
        return jsonify({'error': {
            'code': 'MATCHUP_NOT_FOUND',
            'message': 'Matchup not found.',
            'details': {}
        }}), 404

    position_a_is_left = ((matchup['position_seed'] + user['id']) % 2 == 0)
    mapped_votes, err = _map_votes_left_right(data['votes'], matchup, position_a_is_left)
    if err:
        return err

    meta = {
        'ip': request.remote_addr,
        'read_time_seconds': data.get('read_time_seconds'),
        'batch_size': len(mapped_votes)
    }

    result = db.batch_edit_votes(
        user['id'], matchup_id, mapped_votes, position_a_is_left, meta)

    if not result['success']:
        return jsonify({'error': result['error']}), result['status_code']

    try:
        db.recompute_user_vote_stats(user['id'])
    except Exception:
        logger.warning(f"Failed to recompute user stats for user {user['id']}")

    vote_counts = db.get_matchup_vote_counts(matchup_id)
    results = _format_vote_results(matchup, vote_counts)

    return jsonify({
        'success': True,
        'vote_count': len(result['vote_ids']),
        'edit_window_expires_at': result.get('edit_window_expires_at'),
        'results': results,
        'tool_a_name': matchup['tool_a_name'],
        'tool_b_name': matchup['tool_b_name'],
        'tool_a_icon': matchup['tool_a_icon'],
        'tool_b_icon': matchup['tool_b_icon'],
        'position_a_is_left': position_a_is_left
    }), 200


@app.route("/api/matchups/<int:matchup_id>/results")
@premium_required
def api_matchup_results(matchup_id):
    """API: Get matchup results (only if user has voted)"""
    user = get_current_user()
    matchup = db.get_matchup(matchup_id)
    if not matchup:
        return jsonify({'success': False, 'error': 'Matchup not found'}), 404

    user_votes = db.get_user_votes_for_matchup(user['id'], matchup_id)
    if not user_votes:
        return jsonify({'success': False, 'error': 'You must vote before viewing results'}), 403

    vote_counts = db.get_matchup_vote_counts(matchup_id)
    results = _format_vote_results(matchup, vote_counts)

    return jsonify({
        'success': True,
        'results': results,
        'tool_a_name': matchup['tool_a_name'],
        'tool_b_name': matchup['tool_b_name'],
        'tool_a_icon': matchup['tool_a_icon'],
        'tool_b_icon': matchup['tool_b_icon'],
        'total_votes': db.get_matchup_total_votes(matchup_id)
    })


# ============== API Routes ==============

@app.route("/api/tools")
def api_tools():
    """API endpoint to get all AI tools"""
    tools = db.get_all_tools()
    return jsonify({
        'success': True,
        'data': tools,
        'count': len(tools)
    })


@app.route("/api/tools/<slug>")
def api_tool_by_slug(slug):
    """API endpoint to get a single tool by slug"""
    tool = db.get_tool_by_slug(slug)
    if not tool:
        return jsonify({'success': False, 'error': 'Tool not found'}), 404
    return jsonify({
        'success': True,
        'data': tool
    })


@app.route("/api/posts")
def api_posts():
    """API endpoint to get paginated posts"""
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 12, type=int), 50)  # Max 50 per page
    tool_id = request.args.get('tool_id', type=int)
    category = request.args.get('category')
    search = request.args.get('q')
    
    if search:
        posts, total = db.search_posts(search, page=page, per_page=per_page)
    elif tool_id:
        posts, total = db.get_posts_by_tool(tool_id, page=page, per_page=per_page)
    elif category:
        posts, total = db.get_posts_by_category(category, page=page, per_page=per_page)
    else:
        posts, total = db.get_all_posts(page=page, per_page=per_page)
    
    total_pages = (total + per_page - 1) // per_page
    
    return jsonify({
        'success': True,
        'data': posts,
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total': total,
            'total_pages': total_pages,
            'has_next': page < total_pages,
            'has_prev': page > 1
        }
    })


@app.route("/api/posts/<int:post_id>")
def api_post_by_id(post_id):
    """API endpoint to get a single post by ID"""
    post = db.get_post_by_id(post_id)
    if not post:
        return jsonify({'success': False, 'error': 'Post not found'}), 404
    
    comments = db.get_comments_by_post(post_id)
    
    return jsonify({
        'success': True,
        'data': {
            **post,
            'comments': comments,
            'comment_count': len(comments)
        }
    })


@app.route("/api/posts/<int:tool_id>/by-tool")
def api_posts_by_tool(tool_id):
    """API endpoint to get posts by tool ID (legacy endpoint)"""
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 12, type=int), 50)
    posts, total = db.get_posts_by_tool(tool_id, page=page, per_page=per_page)
    
    return jsonify({
        'success': True,
        'data': posts,
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total': total,
            'total_pages': (total + per_page - 1) // per_page
        }
    })


@app.route("/api/categories")
def api_categories():
    """API endpoint to get all categories with post counts"""
    categories = db.get_categories_with_counts()
    return jsonify({
        'success': True,
        'data': categories
    })


@app.route("/api/stats")
def api_stats():
    """API endpoint to get public statistics"""
    stats = {
        'total_posts': db.get_post_count(),
        'total_tools': len(db.get_all_tools()),
        'recent_posts': db.get_recent_posts(limit=5)
    }
    return jsonify({
        'success': True,
        'data': stats
    })


# ============== Legal Pages ==============

@app.route("/terms")
def terms():
    """Terms and Conditions page"""
    return render_template("legal/terms.html")


@app.route("/privacy")
def privacy():
    """Privacy Policy page"""
    return render_template("legal/privacy.html")


@app.route("/cookies")
def cookies():
    """Cookie Policy page"""
    return render_template("legal/cookies.html")


# ============== Notifications ==============

@app.route("/notifications")
@login_required
def notifications():
    """View all notifications for the current user"""
    user = get_current_user()
    notifications_list = db.get_user_notifications(user['id'], limit=100)
    unread_count = db.get_unread_notification_count(user['id'])
    return render_template("notifications.html", notifications=notifications_list, unread_count=unread_count)


@app.route("/notifications/unread-count")
@limiter.exempt
@login_required
def notifications_unread_count():
    """API endpoint to get unread notification count (for AJAX updates)"""
    user = get_current_user()
    count = db.get_unread_notification_count(user['id'])
    return jsonify({'count': count})


@app.route("/notifications/<int:notification_id>/read", methods=["POST"])
@login_required
def mark_notification_read(notification_id):
    """Mark a single notification as read"""
    user = get_current_user()
    success = db.mark_notification_read(notification_id, user['id'])
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': success})
    return redirect(url_for('notifications'))


@app.route("/notifications/mark-all-read", methods=["POST"])
@login_required
def mark_all_notifications_read():
    """Mark all notifications as read"""
    user = get_current_user()
    count = db.mark_all_notifications_read(user['id'])
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True, 'marked_count': count})
    flash(f'Marked {count} notifications as read', 'success')
    return redirect(url_for('notifications'))


@app.route("/notifications/recent")
@limiter.exempt
@login_required  
def notifications_recent():
    """API endpoint to get recent notifications (for dropdown)"""
    user = get_current_user()
    notifications_list = db.get_user_notifications(user['id'], limit=10, unread_only=False)
    return jsonify({
        'notifications': [
            {
                'id': n['id'],
                'type': n['type'],
                'title': n['title'],
                'message': n['message'],
                'link': n['link'],
                'is_read': n['is_read'],
                'created_at': n['created_at'].isoformat() if n['created_at'] else None,
                'tool_name': n['tool_name'],
                'tool_slug': n['tool_slug']
            }
            for n in notifications_list
        ],
        'unread_count': db.get_unread_notification_count(user['id'])
    })


# ============== Main ==============

if __name__ == "__main__":
    print("🚀 AI Blog is starting...")
    print("📝 Using external scheduler (Dokploy) for cron jobs")
    print("   - POST generation: /cron/generate-posts?token=SECRET")
    print("   - Cleanup tasks:   /cron/cleanup?token=SECRET")
    
    # Use PORT from environment, default to 5000 locally
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    
    print(f"🌐 Starting on port {port}")
    
    app.run(host='0.0.0.0', port=port, debug=debug)
