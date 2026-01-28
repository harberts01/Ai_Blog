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
import re
import schedule
import threading
from datetime import datetime

from flask import (
    Flask, render_template, request, redirect, 
    url_for, flash, session, abort, jsonify
)
from werkzeug.security import generate_password_hash, check_password_hash
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from config import Config
import database as db
from auth import login_required, get_current_user, login_user, logout_user
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
    default_limits=["200 per day", "50 per hour"],
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
        "connect-src 'self'; "
        "frame-ancestors 'self';"
    )
    return response


# ============== Context Processors ==============

@app.context_processor
def inject_globals():
    """Inject global variables into all templates"""
    return {
        'current_user': get_current_user(),
        'ai_tools': db.get_all_tools(),
        'current_year': datetime.now().year
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
    per_page = 12
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
    return render_template("post.html", post=post_data, comments=comments)


@app.route("/post/<int:post_id>/comment", methods=["POST"])
@limiter.limit("10 per minute")
def add_comment(post_id):
    """Add a comment to a post"""
    content = sanitize_input(request.form.get('content'))
    
    if not content or len(content) < 3:
        flash('Comment must be at least 3 characters.', 'error')
        return redirect(url_for('post', post_id=post_id))
    
    if len(content) > 1000:
        flash('Comment must be less than 1000 characters.', 'error')
        return redirect(url_for('post', post_id=post_id))
    
    db.insert_comment(post_id, content)
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
@limiter.limit("5 per minute")
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
                flash('Your account has been deactivated.', 'error')
                return render_template("login.html")
            
            login_user(user['id'])
            flash(f'Welcome back, {user["username"]}!', 'success')
            
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            return redirect(url_for('home'))
        else:
            flash('Invalid email or password.', 'error')
    
    return render_template("login.html")


@app.route("/logout")
def logout():
    """User logout"""
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('home'))


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


# ============== Scheduled Tasks ==============

scheduler_active = False


def cleanup_spam_comments():
    """Delete spam comments older than 30 days"""
    print("Running scheduled spam comment cleanup...")
    deleted = db.delete_old_spam_comments(days=30)
    print(f"Spam cleanup complete. Deleted {deleted} comments.")


def run_scheduler():
    """Run the scheduler in background"""
    while scheduler_active:
        schedule.run_pending()
        import time
        time.sleep(60)


# ============== Error Handlers ==============

@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404


@app.errorhandler(500)
def server_error(e):
    return render_template('500.html'), 500


# ============== API Routes ==============

@app.route("/api/tools")
def api_tools():
    """API endpoint to get all tools"""
    tools = db.get_all_tools()
    return jsonify(tools)


@app.route("/api/posts/<int:tool_id>")
def api_posts_by_tool(tool_id):
    """API endpoint to get posts by tool"""
    posts, _ = db.get_posts_by_tool(tool_id)
    return jsonify(posts)


# ============== Main ==============

if __name__ == "__main__":
    # Setup scheduler
    schedule.every(24).hours.do(ai_generators.generate_all_posts)
    schedule.every(30).days.do(cleanup_spam_comments)
    
    scheduler_active = True
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()
    
    print("🚀 AI Blog is starting...")
    print("📝 Scheduler active - will generate posts every 24 hours")
    print("🗑️  Spam cleanup scheduled - will delete old spam comments every 30 days")
    print("🌐 Visit http://127.0.0.1:5000")
    
    app.run(debug=True)
