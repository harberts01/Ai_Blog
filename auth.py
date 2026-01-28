"""
Authentication Module
Handles user authentication, session management, and access control
"""
from functools import wraps
from flask import session, redirect, url_for, flash, request
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
    
    Args:
        user_id: The user's database ID
        permanent: Whether the session should persist
    """
    session['user_id'] = user_id
    session.permanent = permanent


def logout_user():
    """
    Log out the current user by clearing session.
    """
    session.clear()


def is_authenticated():
    """
    Check if a user is currently authenticated.
    
    Returns:
        True if user is logged in, False otherwise
    """
    return 'user_id' in session
