"""
AI Blog Application
A secure, modern blog platform featuring content from top AI tools
"""
import os
import re
import html
import schedule
import time
import threading
import requests
from functools import wraps
from datetime import datetime

from flask import (
    Flask, render_template, request, redirect, 
    url_for, flash, session, abort, jsonify
)
from werkzeug.security import generate_password_hash, check_password_hash

from config import Config
import database as db

# ============== App Setup ==============

app = Flask(__name__)
app.config.from_object(Config)
app.secret_key = Config.SECRET_KEY

# ============== AI Provider Clients ==============

# OpenAI Client
openai_client = None
if Config.OPENAI_API_KEY:
    from openai import OpenAI
    openai_client = OpenAI(api_key=Config.OPENAI_API_KEY)

# Anthropic Client
anthropic_client = None
if Config.ANTHROPIC_API_KEY:
    try:
        from anthropic import Anthropic
        anthropic_client = Anthropic(api_key=Config.ANTHROPIC_API_KEY)
    except ImportError:
        print("Warning: anthropic package not installed. Run: pip install anthropic")

# Google Gemini Client
gemini_model = None
if Config.GOOGLE_API_KEY:
    try:
        import google.generativeai as genai
        genai.configure(api_key=Config.GOOGLE_API_KEY)
        gemini_model = genai.GenerativeModel('gemini-1.5-pro')
    except ImportError:
        print("Warning: google-generativeai package not installed. Run: pip install google-generativeai")

# Together AI Client (for Llama)
together_client = None
if Config.TOGETHER_API_KEY:
    try:
        from together import Together
        together_client = Together(api_key=Config.TOGETHER_API_KEY)
    except ImportError:
        print("Warning: together package not installed. Run: pip install together")

# Mistral Client
mistral_client = None
if Config.MISTRAL_API_KEY:
    try:
        from mistralai import Mistral
        mistral_client = Mistral(api_key=Config.MISTRAL_API_KEY)
    except ImportError:
        print("Warning: mistralai package not installed. Run: pip install mistralai")


# ============== Security Helpers ==============

def sanitize_input(text):
    """Sanitize user input to prevent XSS"""
    if text is None:
        return None
    return html.escape(str(text).strip())


def validate_email(email):
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def login_required(f):
    """Decorator to require login for routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function


def get_current_user():
    """Get the current logged-in user"""
    if 'user_id' in session:
        return db.get_user_by_id(session['user_id'])
    return None


# ============== Context Processors ==============

@app.context_processor
def inject_globals():
    """Inject global variables into all templates"""
    return {
        'current_user': get_current_user(),
        'ai_tools': db.get_all_tools(),
        'current_year': datetime.now().year
    }


# ============== Public Routes ==============

@app.route("/")
def home():
    """Home page showing all recent posts"""
    posts = db.get_all_posts()
    tools = db.get_all_tools()
    return render_template("index.html", posts=posts, tools=tools)


@app.route("/tool/<slug>")
def tool_page(slug):
    """Page for a specific AI tool showing its posts"""
    tool = db.get_tool_by_slug(slug)
    if not tool:
        abort(404)
    
    posts = db.get_posts_by_tool(tool['id'])
    user = get_current_user()
    is_subscribed = False
    
    if user:
        is_subscribed = db.is_subscribed(user['id'], tool['id'])
    
    return render_template("tool.html", tool=tool, posts=posts, is_subscribed=is_subscribed)


@app.route("/post/<int:post_id>")
def post(post_id):
    """Individual blog post page"""
    post_data = db.get_post_by_id(post_id)
    if not post_data:
        abort(404)
    
    comments = db.get_comments_by_post(post_id)
    return render_template("post.html", post=post_data, comments=comments)


@app.route("/post/<int:post_id>/comment", methods=["POST"])
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
            session['user_id'] = user_id
            flash('Account created successfully! Welcome!', 'success')
            return redirect(url_for('home'))
        else:
            flash('An error occurred. Please try again.', 'error')
    
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
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
            
            session['user_id'] = user['id']
            session.permanent = True
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
    session.clear()
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


@app.route("/my-feed")
@login_required
def my_feed():
    """Show posts from subscribed tools"""
    user = get_current_user()
    posts = db.get_subscribed_posts(user['id'])
    subscriptions = db.get_user_subscriptions(user['id'])
    
    return render_template("feed.html", posts=posts, subscriptions=subscriptions)


@app.route("/subscriptions")
@login_required
def subscriptions():
    """Manage subscriptions page"""
    user = get_current_user()
    all_tools = db.get_all_tools()
    user_subs = db.get_user_subscriptions(user['id'])
    subscribed_ids = [sub['tool_id'] for sub in user_subs]
    
    return render_template("subscriptions.html", tools=all_tools, subscribed_ids=subscribed_ids)


# ============== AI Content Generation ==============

# Categories that appeal to human readers
BLOG_CATEGORIES = [
    "Technology & Innovation",
    "Productivity & Efficiency",
    "Creative Arts & Design",
    "Business & Entrepreneurship",
    "Science & Discovery",
    "Health & Wellness",
    "Education & Learning",
    "Entertainment & Culture",
    "Environment & Sustainability",
    "Personal Development",
    "Future Trends",
    "How-To Guides",
    "Industry News",
    "Opinion & Analysis",
    "Case Studies"
]


def build_prompt(tool_name, style, recent_titles, available_categories):
    """Build the system and user prompts for content generation"""
    system_prompt = f"""You are {tool_name}, an AI writing engaging blog posts for a diverse human audience.
Your unique writing style is: {style}.

You have COMPLETE FREEDOM to choose any topic that would interest and benefit human readers. 
Think about what's trending, what problems people face, what inspires curiosity, or what provides value.

Your goal is to write content that:
- Educates, entertains, or inspires readers
- Provides practical value or unique insights
- Covers topics humans genuinely care about
- Showcases your unique perspective as {tool_name}

You are NOT limited to writing about AI or technology - write about ANY topic that humans find interesting!"""

    user_prompt = f"""Write an original blog post on a topic of YOUR choosing.

IMPORTANT CONSTRAINTS:
1. DO NOT write about these topics (already covered in the last 3 weeks):
{chr(10).join(['   - ' + t for t in recent_titles]) if recent_titles else '   (No recent posts - you have full freedom!)'}

2. Choose a category from this list (these haven't been used in 7 days):
{chr(10).join(['   - ' + c for c in available_categories])}

3. Pick a topic that humans find genuinely interesting - this could be:
   - Current events or trends
   - Life skills and personal growth
   - Science and nature
   - Arts, culture, and creativity
   - Health, relationships, and lifestyle
   - Technology's impact on daily life
   - Business and career advice
   - Entertainment and hobbies
   - Philosophy and big questions
   - Practical how-to guides

FORMAT YOUR RESPONSE EXACTLY LIKE THIS:
Title: [A catchy, engaging title]
Category: [Choose from the available categories above]
Content:
[Your blog post in HTML format, 500-800 words, with proper <h2>, <p>, <ul>, <li> tags]"""

    return system_prompt, user_prompt


def generate_with_openai(model, system_prompt, user_prompt):
    """Generate content using OpenAI API"""
    if not openai_client:
        raise Exception("OpenAI client not initialized - check OPENAI_API_KEY")
    
    completion = openai_client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    )
    return completion.choices[0].message.content


def generate_with_anthropic(model, system_prompt, user_prompt):
    """Generate content using Anthropic Claude API"""
    if not anthropic_client:
        raise Exception("Anthropic client not initialized - check ANTHROPIC_API_KEY")
    
    message = anthropic_client.messages.create(
        model=model,
        max_tokens=4096,
        system=system_prompt,
        messages=[
            {"role": "user", "content": user_prompt}
        ]
    )
    return message.content[0].text


def generate_with_google(model, system_prompt, user_prompt):
    """Generate content using Google Gemini API"""
    if not gemini_model:
        raise Exception("Gemini client not initialized - check GOOGLE_API_KEY")
    
    full_prompt = f"{system_prompt}\n\n{user_prompt}"
    response = gemini_model.generate_content(full_prompt)
    return response.text


def generate_with_together(model, system_prompt, user_prompt):
    """Generate content using Together AI (Llama) API"""
    if not together_client:
        raise Exception("Together client not initialized - check TOGETHER_API_KEY")
    
    response = together_client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    )
    return response.choices[0].message.content


def generate_with_mistral(model, system_prompt, user_prompt):
    """Generate content using Mistral AI API"""
    if not mistral_client:
        raise Exception("Mistral client not initialized - check MISTRAL_API_KEY")
    
    response = mistral_client.chat.complete(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    )
    return response.choices[0].message.content


def generate_with_jasper(system_prompt, user_prompt):
    """Generate content using Jasper AI API"""
    if not Config.JASPER_API_KEY:
        raise Exception("Jasper API key not configured - check JASPER_API_KEY")
    
    # Jasper uses a REST API
    headers = {
        "Authorization": f"Bearer {Config.JASPER_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "inputs": {
            "command": f"{system_prompt}\n\n{user_prompt}"
        }
    }
    
    response = requests.post(
        "https://api.jasper.ai/v1/command",
        headers=headers,
        json=payload
    )
    
    if response.status_code == 200:
        return response.json().get("output", "")
    else:
        raise Exception(f"Jasper API error: {response.status_code} - {response.text}")


# Provider dispatch map
PROVIDER_GENERATORS = {
    'openai': generate_with_openai,
    'anthropic': generate_with_anthropic,
    'google': generate_with_google,
    'together': generate_with_together,
    'mistral': generate_with_mistral,
}


def generate_post_for_tool(tool_slug):
    """Generate a blog post using a specific AI tool's native API"""
    tool = db.get_tool_by_slug(tool_slug)
    if not tool:
        print(f"Tool not found: {tool_slug}")
        return None
    
    tool_config = Config.AI_TOOLS.get(tool_slug, {})
    provider = tool_config.get('provider', 'openai')
    model = tool_config.get('model', 'gpt-4o')
    style = tool_config.get('prompt_style', 'informative')
    
    # Get posts from the last 3 weeks to avoid repetition
    recent_posts = db.get_recent_posts_by_tool(tool['id'], days=21)
    recent_titles = [p['title'] for p in recent_posts]
    
    # Get categories used in the last 7 days to ensure variety
    recent_categories = db.get_recent_categories_by_tool(tool['id'], days=7)
    available_categories = [cat for cat in BLOG_CATEGORIES if cat not in recent_categories]
    
    # If all categories were used recently, allow all
    if not available_categories:
        available_categories = BLOG_CATEGORIES
    
    # Build prompts
    system_prompt, user_prompt = build_prompt(
        tool['name'], style, recent_titles, available_categories
    )
    
    try:
        # Generate content using the appropriate provider
        if provider == 'jasper':
            response = generate_with_jasper(system_prompt, user_prompt)
        elif provider in PROVIDER_GENERATORS:
            generator = PROVIDER_GENERATORS[provider]
            response = generator(model, system_prompt, user_prompt)
        else:
            raise Exception(f"Unknown provider: {provider}")
        
        # Parse the response
        lines = response.split('\n')
        data = {'tool_id': tool['id']}
        content_lines = []
        in_content = False
        
        for line in lines:
            if line.startswith('Title:'):
                data['title'] = line[6:].strip()
            elif line.startswith('Category:'):
                data['category'] = line[9:].strip()
            elif line.startswith('Content:'):
                in_content = True
                content_lines.append(line[8:].strip())
            elif in_content:
                content_lines.append(line)
        
        data['content'] = '\n'.join(content_lines).strip()
        
        if data.get('title') and data.get('content') and data.get('category'):
            db.insert_post(
                data['title'], 
                data['content'], 
                data['category'], 
                data['tool_id']
            )
            print(f"✅ Generated post by {tool['name']} ({provider}): {data['title']} [{data['category']}]")
            return data
        else:
            print(f"❌ Failed to parse response for {tool['name']}")
            return None
            
    except Exception as e:
        print(f"❌ Error generating post with {tool['name']} ({provider}): {e}")
        return None
        
        data['content'] = '\n'.join(content_lines).strip()
        
        if data.get('title') and data.get('content') and data.get('category'):
            db.insert_post(
                data['title'], 
                data['content'], 
                data['category'], 
                data['tool_id']
            )
            print(f"Generated post by {tool['name']}: {data['title']} [{data['category']}]")
            return data
        else:
            print(f"Failed to parse response for {tool['name']}")
            return None
            
    except Exception as e:
        print(f"Error generating post: {e}")
        return None


def generate_all_posts():
    """Generate posts for all AI tools"""
    for tool_slug in Config.AI_TOOLS.keys():
        generate_post_for_tool(tool_slug)
        time.sleep(2)  # Rate limiting between API calls


# Schedule daily post generation
schedule.every(24).hours.do(generate_all_posts)

# Schedule spam comment cleanup every 30 days
def cleanup_spam_comments():
    """Delete spam comments older than 30 days"""
    print("Running scheduled spam comment cleanup...")
    deleted = db.delete_old_spam_comments(days=30)
    print(f"Spam cleanup complete. Deleted {deleted} comments.")

schedule.every(30).days.do(cleanup_spam_comments)

scheduler_active = False


def run_scheduler():
    """Run the scheduler in background"""
    while scheduler_active:
        schedule.run_pending()
        time.sleep(60)


# ============== Error Handlers ==============

@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404


@app.errorhandler(500)
def server_error(e):
    return render_template('500.html'), 500


# ============== API Routes (for future use) ==============

@app.route("/api/tools")
def api_tools():
    """API endpoint to get all tools"""
    tools = db.get_all_tools()
    return jsonify(tools)


@app.route("/api/posts/<int:tool_id>")
def api_posts_by_tool(tool_id):
    """API endpoint to get posts by tool"""
    posts = db.get_posts_by_tool(tool_id)
    return jsonify(posts)


# ============== Main ==============

if __name__ == "__main__":
    scheduler_active = True
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()
    
    print("🚀 AI Blog is starting...")
    print("📝 Scheduler active - will generate posts every 24 hours")
    print("🗑️  Spam cleanup scheduled - will delete old spam comments every 30 days")
    print("🌐 Visit http://127.0.0.1:5000")
    
    app.run(debug=True)
