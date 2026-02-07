"""
Authentication Module
Handles user authentication, session management, and access control
"""
from functools import wraps
from flask import session, redirect, url_for, flash, request, jsonify
import database as db


def login_required(f):
    """
    Decorator to require login for routes.
    
    Redirects unauthenticated users to login page with a return URL.
    
    Usage:
        @app.route('/protected')
        @login_required
        def protected_route():
            ...
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function


def get_current_user():
    """
    Get the current logged-in user from session.
    
    Returns:
        User dict if logged in, None otherwise
    """
    if 'user_id' in session:
        return db.get_user_by_id(session['user_id'])
    return None


def login_user(user_id, permanent=True):
    """
    Log in a user by setting session data.
    
    Regenerates session to prevent session fixation attacks.
    
    Args:
        user_id: The user's database ID
        permanent: Whether the session should persist
    """
    # Clear any existing session data first (prevents session fixation)
    session.clear()
    
    # Set new session data
    session['user_id'] = user_id
    session.permanent = permanent
    session.modified = True


def logout_user():
    """
    Log out the current user by clearing session.
    """
    session.clear()


def admin_required(f):
    """
    Decorator to require admin access for routes.
    
    Redirects non-admin users to home page with error message.
    
    Usage:
        @app.route('/admin')
        @admin_required
        def admin_route():
            ...
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login', next=request.url))
        
        user = db.get_user_by_id(session['user_id'])
        if not user or not user.get('is_admin'):
            flash('You do not have permission to access this page.', 'error')
            return redirect(url_for('home'))
        
        return f(*args, **kwargs)
    return decorated_function


def premium_required(f):
    """
    Decorator to require premium subscription for routes.

    For API routes (/api/*): returns JSON 401/403 with structured error.
    For page routes: flashes warning and redirects to pricing page.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            if request.path.startswith('/api/'):
                return jsonify({
                    'error': {
                        'code': 'AUTH_REQUIRED',
                        'message': 'Authentication required.',
                        'details': {}
                    }
                }), 401
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login', next=request.url))

        if not db.is_user_premium(session['user_id']):
            if request.path.startswith('/api/'):
                return jsonify({
                    'error': {
                        'code': 'PREMIUM_REQUIRED',
                        'message': 'This feature requires a premium subscription.',
                        'details': {},
                        'upgrade_url': '/pricing'
                    }
                }), 403
            flash('Premium subscription required.', 'warning')
            return redirect(url_for('pricing'))

        return f(*args, **kwargs)
    return decorated_function


def is_authenticated():
    """
    Check if a user is currently authenticated.
    
    Returns:
        True if user is logged in, False otherwise
    """
    return 'user_id' in session
