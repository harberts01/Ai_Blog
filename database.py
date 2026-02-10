"""
Database Module
Handles all database connections and operations
"""
import os
import time as _time
import logging
import psycopg2
import psycopg2.extras
from psycopg2.extras import RealDictCursor
from datetime import datetime as _datetime
from config import Config

# Configure logging - never log sensitive data like passwords or connection strings
logger = logging.getLogger(__name__)


def get_connection():
    """Create and return a database connection"""
    try:
        # Check if DATABASE_URL is set (Dokploy/Heroku style)
        database_url = os.environ.get('DATABASE_URL')
        
        if database_url:
            # Some providers use postgres:// but psycopg2 needs postgresql://
            if database_url.startswith('postgres://'):
                database_url = database_url.replace('postgres://', 'postgresql://', 1)
            
            # SSL mode: require for external connections, disable for internal Docker networks
            ssl_mode = os.environ.get('DB_SSL_MODE', 'prefer')
            conn = psycopg2.connect(database_url, sslmode=ssl_mode)
        else:
            # Local/VPS development with individual env vars
            ssl_mode = os.environ.get('DB_SSL_MODE', 'prefer')
            conn = psycopg2.connect(
                host=Config.DB_HOST,
                port=Config.DB_PORT,
                database=Config.DB_NAME,
                user=Config.DB_USER,
                password=Config.DB_PASSWORD,
                sslmode=ssl_mode
            )
        return conn
    except psycopg2.Error as e:
        # Log error without exposing connection details
        logger.error(f'Database connection failed: {type(e).__name__}')
        return None


# Global connection for backward compatibility
conn = get_connection()

if conn:
    logger.info('Database connection established.')
else:
    logger.warning('Database connection could not be established.')


# ============== AI Tools ==============

def get_all_tools():
    """Fetch all AI tools"""
    connection = get_connection()
    if not connection:
        return []
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT tool_id, name, slug, description, icon_url FROM AITool ORDER BY name")
            return [
                {
                    'id': row[0], 
                    'name': row[1], 
                    'slug': row[2], 
                    'description': row[3],
                    'icon_url': row[4]
                } 
                for row in cursor.fetchall()
            ]
    finally:
        connection.close()


def get_tool_by_slug(slug):
    """Fetch a single AI tool by slug"""
    connection = get_connection()
    if not connection:
        return None
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT tool_id, name, slug, description, icon_url, api_provider FROM AITool WHERE slug = %s", 
                (slug,)
            )
            row = cursor.fetchone()
            if row:
                return {
                    'id': row[0], 
                    'name': row[1], 
                    'slug': row[2], 
                    'description': row[3],
                    'icon_url': row[4],
                    'api_provider': row[5]
                }
    finally:
        connection.close()
    return None


def get_tool_by_id(tool_id):
    """Fetch a single AI tool by ID"""
    connection = get_connection()
    if not connection:
        return None
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT tool_id, name, slug, description, icon_url FROM AITool WHERE tool_id = %s", 
                (tool_id,)
            )
            row = cursor.fetchone()
            if row:
                return {
                    'id': row[0], 
                    'name': row[1], 
                    'slug': row[2], 
                    'description': row[3],
                    'icon_url': row[4]
                }
    finally:
        connection.close()
    return None


# ============== Posts ==============

POSTS_PER_PAGE = 12  # Default pagination size


def search_posts(query, page=1, per_page=POSTS_PER_PAGE):
    """Search posts using PostgreSQL full-text search"""
    connection = get_connection()
    if not connection:
        return [], 0
    try:
        offset = (page - 1) * per_page
        # Escape special characters and prepare search query
        search_query = ' & '.join(query.split())  # Convert spaces to AND
        
        with connection.cursor() as cursor:
            # Get total count of matching posts
            cursor.execute("""
                SELECT COUNT(*) FROM Post 
                WHERE to_tsvector('english', Title || ' ' || Content) @@ plainto_tsquery('english', %s)
            """, (query,))
            total = cursor.fetchone()[0]
            
            # Get paginated search results with ranking
            cursor.execute("""
                SELECT p.postid, p.Title, p.Content, p.Category, p.CreatedAt, p.tool_id,
                       t.name as tool_name, t.slug as tool_slug,
                       ts_rank(to_tsvector('english', p.Title || ' ' || p.Content), 
                               plainto_tsquery('english', %s)) as rank
                FROM Post p
                LEFT JOIN AITool t ON p.tool_id = t.tool_id
                WHERE to_tsvector('english', p.Title || ' ' || p.Content) @@ plainto_tsquery('english', %s)
                ORDER BY rank DESC, p.CreatedAt DESC
                LIMIT %s OFFSET %s
            """, (query, query, per_page, offset))
            posts = [
                {
                    'id': row[0], 
                    'title': row[1], 
                    'content': row[2], 
                    'category': row[3],
                    'created_at': row[4],
                    'tool_id': row[5],
                    'tool_name': row[6],
                    'tool_slug': row[7]
                } 
                for row in cursor.fetchall()
            ]
            return posts, total
    finally:
        connection.close()


def get_all_posts(page=1, per_page=POSTS_PER_PAGE):
    """Fetch paginated blog posts with tool information"""
    connection = get_connection()
    if not connection:
        return [], 0
    try:
        offset = (page - 1) * per_page
        with connection.cursor() as cursor:
            # Get total count
            cursor.execute("SELECT COUNT(*) FROM Post")
            total = cursor.fetchone()[0]
            
            # Get paginated posts
            cursor.execute("""
                SELECT p.postid, p.Title, p.Content, p.Category, p.CreatedAt, p.tool_id,
                       t.name as tool_name, t.slug as tool_slug
                FROM Post p
                LEFT JOIN AITool t ON p.tool_id = t.tool_id
                ORDER BY p.CreatedAt DESC
                LIMIT %s OFFSET %s
            """, (per_page, offset))
            posts = [
                {
                    'id': row[0], 
                    'title': row[1], 
                    'content': row[2], 
                    'category': row[3],
                    'created_at': row[4],
                    'tool_id': row[5],
                    'tool_name': row[6],
                    'tool_slug': row[7]
                } 
                for row in cursor.fetchall()
            ]
            return posts, total
    finally:
        connection.close()


def get_posts_by_tool(tool_id, page=1, per_page=POSTS_PER_PAGE):
    """Fetch paginated posts for a specific AI tool"""
    connection = get_connection()
    if not connection:
        return [], 0
    try:
        offset = (page - 1) * per_page
        with connection.cursor() as cursor:
            # Get total count for this tool
            cursor.execute("SELECT COUNT(*) FROM Post WHERE tool_id = %s", (tool_id,))
            total = cursor.fetchone()[0]
            
            # Get paginated posts
            cursor.execute("""
                SELECT p.postid, p.Title, p.Content, p.Category, p.CreatedAt, p.tool_id,
                       t.name as tool_name, t.slug as tool_slug
                FROM Post p
                LEFT JOIN AITool t ON p.tool_id = t.tool_id
                WHERE p.tool_id = %s
                ORDER BY p.CreatedAt DESC
                LIMIT %s OFFSET %s
            """, (tool_id, per_page, offset))
            posts = [
                {
                    'id': row[0], 
                    'title': row[1], 
                    'content': row[2], 
                    'category': row[3],
                    'created_at': row[4],
                    'tool_id': row[5],
                    'tool_name': row[6],
                    'tool_slug': row[7]
                } 
                for row in cursor.fetchall()
            ]
            return posts, total
    finally:
        connection.close()


def get_post_by_id(post_id):
    """Fetch a single post by ID"""
    connection = get_connection()
    if not connection:
        return None
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT p.postid, p.Title, p.Content, p.Category, p.CreatedAt, p.tool_id,
                       t.name as tool_name, t.slug as tool_slug
                FROM Post p
                LEFT JOIN AITool t ON p.tool_id = t.tool_id
                WHERE p.postid = %s
            """, (post_id,))
            row = cursor.fetchone()
            if row:
                return {
                    'id': row[0], 
                    'title': row[1], 
                    'content': row[2], 
                    'category': row[3],
                    'created_at': row[4],
                    'tool_id': row[5],
                    'tool_name': row[6],
                    'tool_slug': row[7]
                }
    finally:
        connection.close()
    return None


def get_posts_by_category(category, page=1, per_page=POSTS_PER_PAGE):
    """Fetch paginated posts for a specific category"""
    connection = get_connection()
    if not connection:
        return [], 0
    try:
        offset = (page - 1) * per_page
        with connection.cursor() as cursor:
            # Get total count for this category
            cursor.execute("SELECT COUNT(*) FROM Post WHERE Category = %s", (category,))
            total = cursor.fetchone()[0]
            
            # Get paginated posts
            cursor.execute("""
                SELECT p.postid, p.Title, p.Content, p.Category, p.CreatedAt, p.tool_id,
                       t.name as tool_name, t.slug as tool_slug
                FROM Post p
                LEFT JOIN AITool t ON p.tool_id = t.tool_id
                WHERE p.Category = %s
                ORDER BY p.CreatedAt DESC
                LIMIT %s OFFSET %s
            """, (category, per_page, offset))
            posts = [
                {
                    'id': row[0], 
                    'title': row[1], 
                    'content': row[2], 
                    'category': row[3],
                    'created_at': row[4],
                    'tool_id': row[5],
                    'tool_name': row[6],
                    'tool_slug': row[7]
                } 
                for row in cursor.fetchall()
            ]
            return posts, total
    finally:
        connection.close()


def get_categories_with_counts():
    """Get all categories with their distinct tool counts (for comparison feature)"""
    connection = get_connection()
    if not connection:
        return []
    try:
        with connection.cursor() as cursor:
            # Count distinct tools per category, not just posts
            # This enables filtering for categories that can be compared (2+ different tools)
            cursor.execute("""
                SELECT Category, COUNT(DISTINCT tool_id) as count
                FROM Post
                WHERE tool_id IS NOT NULL
                GROUP BY Category
                ORDER BY count DESC
            """)
            return [{'name': row[0], 'count': row[1]} for row in cursor.fetchall()]
    finally:
        connection.close()


def get_post_count():
    """Get total number of posts"""
    connection = get_connection()
    if not connection:
        return 0
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM Post")
            return cursor.fetchone()[0]
    finally:
        connection.close()


def get_recent_posts(limit=5):
    """Get the most recent posts"""
    connection = get_connection()
    if not connection:
        return []
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT p.postid, p.Title, p.Category, p.CreatedAt, t.name as tool_name, t.slug as tool_slug
                FROM Post p
                LEFT JOIN AITool t ON p.tool_id = t.tool_id
                ORDER BY p.CreatedAt DESC
                LIMIT %s
            """, (limit,))
            return [
                {
                    'id': row[0],
                    'title': row[1],
                    'category': row[2],
                    'created_at': row[3],
                    'tool_name': row[4],
                    'tool_slug': row[5]
                }
                for row in cursor.fetchall()
            ]
    finally:
        connection.close()


def insert_post(title, content, category, tool_id=None):
    """Insert a new blog post and return the post ID"""
    connection = get_connection()
    if not connection:
        return None
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO Post (Title, Content, Category, tool_id) VALUES (%s, %s, %s, %s) RETURNING postid",
                (title, content, category, tool_id)
            )
            post_id = cursor.fetchone()[0]
            connection.commit()
            return post_id
    except Exception as e:
        print(f"Error inserting post: {e}")
        return None
    finally:
        connection.close()


def get_last_post_date_for_tool(tool_id):
    """Get the date of the most recent post for a specific tool"""
    connection = get_connection()
    if not connection:
        return None
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT CreatedAt FROM Post 
                WHERE tool_id = %s 
                ORDER BY CreatedAt DESC 
                LIMIT 1
            """, (tool_id,))
            row = cursor.fetchone()
            return row[0] if row else None
    finally:
        connection.close()


def get_recent_posts_by_tool(tool_id, days=21):
    """Fetch posts from the last N days for a specific tool to avoid repetition"""
    connection = get_connection()
    if not connection:
        return []
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT p.postid, p.Title, p.Content, p.Category, p.CreatedAt
                FROM Post p
                WHERE p.tool_id = %s 
                AND p.CreatedAt >= CURRENT_DATE - INTERVAL '%s days'
                ORDER BY p.CreatedAt DESC
            """, (tool_id, days))
            return [
                {
                    'id': row[0], 
                    'title': row[1], 
                    'content': row[2], 
                    'category': row[3],
                    'created_at': row[4]
                } 
                for row in cursor.fetchall()
            ]
    finally:
        connection.close()


def get_recent_categories_by_tool(tool_id, days=7):
    """Fetch categories used in the last N days for a specific tool"""
    connection = get_connection()
    if not connection:
        return []
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT DISTINCT p.Category
                FROM Post p
                WHERE p.tool_id = %s 
                AND p.CreatedAt >= CURRENT_DATE - INTERVAL '%s days'
            """, (tool_id, days))
            return [row[0] for row in cursor.fetchall()]
    finally:
        connection.close()


# ============== Users ==============

def get_user_by_email(email):
    """Fetch user by email"""
    connection = get_connection()
    if not connection:
        return None
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT user_id, email, password_hash, username, is_active FROM Users WHERE email = %s",
                (email,)
            )
            row = cursor.fetchone()
            if row:
                return {
                    'id': row[0],
                    'email': row[1],
                    'password_hash': row[2],
                    'username': row[3],
                    'is_active': row[4]
                }
    finally:
        connection.close()
    return None


def get_user_by_id(user_id):
    """Fetch user by ID"""
    connection = get_connection()
    if not connection:
        return None
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT user_id, email, password_hash, username, is_active, email_notifications, is_admin FROM Users WHERE user_id = %s",
                (user_id,)
            )
            row = cursor.fetchone()
            if row:
                return {
                    'id': row[0],
                    'email': row[1],
                    'password_hash': row[2],
                    'username': row[3],
                    'is_active': row[4],
                    'email_notifications': row[5] if row[5] is not None else True,
                    'is_admin': row[6] if row[6] is not None else False
                }
    finally:
        connection.close()
    return None


def update_user_email_preferences(user_id, email_notifications):
    """Update user email notification preferences"""
    connection = get_connection()
    if not connection:
        return False
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE Users SET email_notifications = %s WHERE user_id = %s",
                (email_notifications, user_id)
            )
            connection.commit()
            return cursor.rowcount > 0
    except Exception as e:
        print(f"Error updating email preferences: {e}")
        return False
    finally:
        connection.close()


def update_user_profile(user_id, username=None, email=None):
    """Update user profile information (username and/or email)"""
    connection = get_connection()
    if not connection:
        return {'success': False, 'error': 'Database connection failed'}
    try:
        with connection.cursor() as cursor:
            # Build dynamic update query
            updates = []
            params = []
            
            if username is not None:
                # Check if username is taken by another user
                cursor.execute(
                    "SELECT user_id FROM Users WHERE username = %s AND user_id != %s",
                    (username, user_id)
                )
                if cursor.fetchone():
                    return {'success': False, 'error': 'Username is already taken'}
                updates.append("username = %s")
                params.append(username)
            
            if email is not None:
                # Check if email is taken by another user
                cursor.execute(
                    "SELECT user_id FROM Users WHERE email = %s AND user_id != %s",
                    (email, user_id)
                )
                if cursor.fetchone():
                    return {'success': False, 'error': 'Email is already in use'}
                updates.append("email = %s")
                params.append(email)
            
            if not updates:
                return {'success': False, 'error': 'No fields to update'}
            
            params.append(user_id)
            query = f"UPDATE Users SET {', '.join(updates)} WHERE user_id = %s"
            cursor.execute(query, params)
            connection.commit()
            
            return {'success': True}
    except Exception as e:
        logger.error(f"Error updating user profile: {e}")
        return {'success': False, 'error': 'Failed to update profile'}
    finally:
        connection.close()


def update_user_password(user_id, new_password_hash):
    """Update user's password"""
    connection = get_connection()
    if not connection:
        return False
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE Users SET password_hash = %s WHERE user_id = %s",
                (new_password_hash, user_id)
            )
            connection.commit()
            return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Error updating password: {e}")
        return False
    finally:
        connection.close()


def get_user_full_profile(user_id):
    """Get complete user profile including stats"""
    connection = get_connection()
    if not connection:
        return None
    try:
        with connection.cursor() as cursor:
            # Get user info
            cursor.execute("""
                SELECT user_id, email, username, is_active, is_admin, 
                       email_notifications, created_at
                FROM Users WHERE user_id = %s
            """, (user_id,))
            row = cursor.fetchone()
            if not row:
                return None
            
            user = {
                'id': row[0],
                'email': row[1],
                'username': row[2],
                'is_active': row[3],
                'is_admin': row[4],
                'email_notifications': row[5],
                'created_at': row[6]
            }
            
            # Get stats
            cursor.execute("SELECT COUNT(*) FROM Comment WHERE user_id = %s", (user_id,))
            user['comment_count'] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM Bookmark WHERE user_id = %s", (user_id,))
            user['bookmark_count'] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM Subscription WHERE user_id = %s", (user_id,))
            user['subscription_count'] = cursor.fetchone()[0]
            
            return user
    finally:
        connection.close()


def delete_user_account(user_id):
    """Delete a user account and all associated data"""
    connection = get_connection()
    if not connection:
        return False
    try:
        with connection.cursor() as cursor:
            # Delete user (cascades to comments, bookmarks, subscriptions, notifications)
            cursor.execute("DELETE FROM Users WHERE user_id = %s", (user_id,))
            connection.commit()
            return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Error deleting user account: {e}")
        return False
    finally:
        connection.close()


def create_user(email, password_hash, username):
    """Create a new user"""
    connection = get_connection()
    if not connection:
        return None
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO Users (email, password_hash, username) VALUES (%s, %s, %s) RETURNING user_id",
                (email, password_hash, username)
            )
            row = cursor.fetchone()
            connection.commit()
            return row[0] if row else None
    except Exception as e:
        print(f"Error creating user: {e}")
        return None
    finally:
        connection.close()


# ============== Subscriptions ==============

def get_user_subscriptions(user_id):
    """Get all subscriptions for a user"""
    connection = get_connection()
    if not connection:
        return []
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT t.tool_id, t.name, t.slug, t.description, t.icon_url, s.subscribed_at
                FROM Subscription s
                JOIN AITool t ON s.tool_id = t.tool_id
                WHERE s.user_id = %s
                ORDER BY t.name
            """, (user_id,))
            return [
                {
                    'tool_id': row[0],
                    'name': row[1],
                    'slug': row[2],
                    'description': row[3],
                    'icon_url': row[4],
                    'subscribed_at': row[5]
                }
                for row in cursor.fetchall()
            ]
    finally:
        connection.close()


def get_subscribed_tool_ids(user_id):
    """Get list of tool IDs that a user is subscribed to"""
    connection = get_connection()
    if not connection:
        return []
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT tool_id FROM Subscription WHERE user_id = %s
            """, (user_id,))
            return [row[0] for row in cursor.fetchall()]
    finally:
        connection.close()


def add_subscription(user_id, tool_id):
    """Add a subscription for a user"""
    connection = get_connection()
    if not connection:
        return False
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO Subscription (user_id, tool_id) VALUES (%s, %s)",
                (user_id, tool_id)
            )
            connection.commit()
            return True
    except Exception as e:
        print(f"Error adding subscription: {e}")
        return False
    finally:
        connection.close()


def remove_subscription(user_id, tool_id):
    """Remove a subscription for a user"""
    connection = get_connection()
    if not connection:
        return False
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM Subscription WHERE user_id = %s AND tool_id = %s",
                (user_id, tool_id)
            )
            connection.commit()
            return True
    except Exception as e:
        print(f"Error removing subscription: {e}")
        return False
    finally:
        connection.close()


def is_subscribed(user_id, tool_id):
    """Check if user is subscribed to a tool"""
    connection = get_connection()
    if not connection:
        return False
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT 1 FROM Subscription WHERE user_id = %s AND tool_id = %s",
                (user_id, tool_id)
            )
            return cursor.fetchone() is not None
    finally:
        connection.close()


def get_subscriber_emails_by_tool(tool_id):
    """Get email addresses of all users subscribed to a tool (for notifications)"""
    connection = get_connection()
    if not connection:
        return []
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT u.email
                FROM Users u
                JOIN Subscription s ON u.user_id = s.user_id
                WHERE s.tool_id = %s AND u.email_notifications = TRUE
            """, (tool_id,))
            return [row[0] for row in cursor.fetchall()]
    finally:
        connection.close()


def get_subscribed_posts(user_id, page=1, per_page=POSTS_PER_PAGE):
    """Get paginated posts from tools the user is subscribed to"""
    connection = get_connection()
    if not connection:
        return [], 0
    try:
        offset = (page - 1) * per_page
        with connection.cursor() as cursor:
            # Get total count
            cursor.execute("""
                SELECT COUNT(*)
                FROM Post p
                JOIN Subscription s ON p.tool_id = s.tool_id
                WHERE s.user_id = %s
            """, (user_id,))
            total = cursor.fetchone()[0]
            
            # Get paginated posts
            cursor.execute("""
                SELECT p.postid, p.Title, p.Content, p.Category, p.CreatedAt, p.tool_id,
                       t.name as tool_name, t.slug as tool_slug
                FROM Post p
                JOIN AITool t ON p.tool_id = t.tool_id
                JOIN Subscription s ON t.tool_id = s.tool_id
                WHERE s.user_id = %s
                ORDER BY p.CreatedAt DESC
                LIMIT %s OFFSET %s
            """, (user_id, per_page, offset))
            posts = [
                {
                    'id': row[0], 
                    'title': row[1], 
                    'content': row[2], 
                    'category': row[3],
                    'created_at': row[4],
                    'tool_id': row[5],
                    'tool_name': row[6],
                    'tool_slug': row[7]
                } 
                for row in cursor.fetchall()
            ]
            return posts, total
    finally:
        connection.close()


# ============== Comments ==============

def get_comments_by_post(post_id):
    """Get all comments for a post with user info and threading structure"""
    connection = get_connection()
    if not connection:
        return []
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT c.commentid, c.content, c.CreatedAt, c.parent_id, c.user_id,
                       u.username
                FROM Comment c
                LEFT JOIN Users u ON c.user_id = u.user_id
                WHERE c.postid = %s AND c.is_spam = FALSE
                ORDER BY c.CreatedAt ASC
            """, (post_id,))
            
            comments = []
            for row in cursor.fetchall():
                comments.append({
                    'id': row[0],
                    'content': row[1],
                    'created_at': row[2],
                    'parent_id': row[3],
                    'user_id': row[4],
                    'username': row[5] or 'Anonymous',
                    'replies': []
                })
            
            # Build threaded structure
            comment_map = {c['id']: c for c in comments}
            root_comments = []
            
            for comment in comments:
                if comment['parent_id'] is None:
                    root_comments.append(comment)
                else:
                    parent = comment_map.get(comment['parent_id'])
                    if parent:
                        parent['replies'].append(comment)
            
            return root_comments
    finally:
        connection.close()


def get_comments_by_user(user_id, limit=50):
    """Get all comments by a specific user with post info"""
    connection = get_connection()
    if not connection:
        return []
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT c.commentid, c.content, c.CreatedAt, c.is_spam,
                       p.postid, p.Title
                FROM Comment c
                JOIN Post p ON c.postid = p.postid
                WHERE c.user_id = %s
                ORDER BY c.CreatedAt DESC
                LIMIT %s
            """, (user_id, limit))
            
            return [
                {
                    'id': row[0],
                    'content': row[1],
                    'created_at': row[2],
                    'is_spam': row[3],
                    'post_id': row[4],
                    'post_title': row[5]
                }
                for row in cursor.fetchall()
            ]
    finally:
        connection.close()


def insert_comment(post_id, content, user_id=None, parent_id=None):
    """Insert a new comment or reply"""
    connection = get_connection()
    if not connection:
        return False
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO Comment (postid, content, user_id, parent_id) VALUES (%s, %s, %s, %s)",
                (post_id, content, user_id, parent_id)
            )
            connection.commit()
            return True
    except Exception as e:
        print(f"Error inserting comment: {e}")
        return False
    finally:
        connection.close()


def delete_old_spam_comments(days=30):
    """Delete spam comments older than specified number of days"""
    connection = get_connection()
    if not connection:
        return 0
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM Comment WHERE is_spam = TRUE AND CreatedAt < CURRENT_DATE - INTERVAL '%s days'",
                (days,)
            )
            deleted_count = cursor.rowcount
            connection.commit()
            print(f"Deleted {deleted_count} spam comments older than {days} days")
            return deleted_count
    except Exception as e:
        print(f"Error deleting spam comments: {e}")
        return 0
    finally:
        connection.close()


# ============== Bookmarks ==============

def add_bookmark(user_id, post_id):
    """Add a bookmark for a user"""
    connection = get_connection()
    if not connection:
        return False
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO Bookmark (user_id, post_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                (user_id, post_id)
            )
            connection.commit()
            return True
    except Exception as e:
        print(f"Error adding bookmark: {e}")
        return False
    finally:
        connection.close()


def remove_bookmark(user_id, post_id):
    """Remove a bookmark for a user"""
    connection = get_connection()
    if not connection:
        return False
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM Bookmark WHERE user_id = %s AND post_id = %s",
                (user_id, post_id)
            )
            connection.commit()
            return True
    except Exception as e:
        print(f"Error removing bookmark: {e}")
        return False
    finally:
        connection.close()


def is_bookmarked(user_id, post_id):
    """Check if a post is bookmarked by a user"""
    connection = get_connection()
    if not connection:
        return False
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT 1 FROM Bookmark WHERE user_id = %s AND post_id = %s",
                (user_id, post_id)
            )
            return cursor.fetchone() is not None
    finally:
        connection.close()


def get_user_bookmarks(user_id, page=1, per_page=POSTS_PER_PAGE):
    """Get all bookmarked posts for a user with pagination"""
    connection = get_connection()
    if not connection:
        return [], 0
    try:
        offset = (page - 1) * per_page
        with connection.cursor() as cursor:
            # Get total count
            cursor.execute(
                "SELECT COUNT(*) FROM Bookmark WHERE user_id = %s",
                (user_id,)
            )
            total = cursor.fetchone()[0]
            
            # Get paginated bookmarks
            cursor.execute("""
                SELECT p.postid, p.Title, p.Content, p.Category, p.CreatedAt, p.tool_id,
                       t.name as tool_name, t.slug as tool_slug, b.created_at as bookmarked_at
                FROM Bookmark b
                JOIN Post p ON b.post_id = p.postid
                LEFT JOIN AITool t ON p.tool_id = t.tool_id
                WHERE b.user_id = %s
                ORDER BY b.created_at DESC
                LIMIT %s OFFSET %s
            """, (user_id, per_page, offset))
            posts = [
                {
                    'id': row[0],
                    'title': row[1],
                    'content': row[2],
                    'category': row[3],
                    'created_at': row[4],
                    'tool_id': row[5],
                    'tool_name': row[6],
                    'tool_slug': row[7],
                    'bookmarked_at': row[8]
                }
                for row in cursor.fetchall()
            ]
            return posts, total
    finally:
        connection.close()


def get_bookmarked_post_ids(user_id):
    """Get list of post IDs bookmarked by a user (for checking multiple posts)"""
    connection = get_connection()
    if not connection:
        return set()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT post_id FROM Bookmark WHERE user_id = %s",
                (user_id,)
            )
            return {row[0] for row in cursor.fetchall()}
    finally:
        connection.close()


# ============== API Usage Tracking ==============

# Estimated costs per 1K tokens (input/output) - Updated Jan 2026
API_COSTS = {
    'openai': {
        'gpt-4o': {'input': 0.0025, 'output': 0.010},
        'gpt-4o-mini': {'input': 0.00015, 'output': 0.0006},
        'gpt-4-turbo': {'input': 0.01, 'output': 0.03},
    },
    'anthropic': {
        'claude-3-5-sonnet-20241022': {'input': 0.003, 'output': 0.015},
        'claude-3-opus-20240229': {'input': 0.015, 'output': 0.075},
        'claude-3-haiku-20240307': {'input': 0.00025, 'output': 0.00125},
    },
    'google': {
        'gemini-1.5-pro': {'input': 0.00125, 'output': 0.005},
        'gemini-1.5-flash': {'input': 0.000075, 'output': 0.0003},
    },
    'together': {
        'meta-llama/Meta-Llama-3.1-405B-Instruct-Turbo': {'input': 0.005, 'output': 0.015},
        'meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo': {'input': 0.00088, 'output': 0.00088},
    },
    'xai': {
        'grok-2-latest': {'input': 0.002, 'output': 0.010},
        'grok-2': {'input': 0.002, 'output': 0.010},
    },
    'jasper': {
        'jasper': {'input': 0.01, 'output': 0.01},  # Jasper uses credit-based pricing, estimate
    }
}


def calculate_api_cost(provider, model, input_tokens, output_tokens):
    """Calculate estimated cost for an API call"""
    provider_costs = API_COSTS.get(provider, {})
    model_costs = provider_costs.get(model, {'input': 0.01, 'output': 0.01})  # Default fallback
    
    input_cost = (input_tokens / 1000) * model_costs['input']
    output_cost = (output_tokens / 1000) * model_costs['output']
    
    return round(input_cost + output_cost, 6)


def log_api_usage(tool_id, provider, model, input_tokens=0, output_tokens=0, success=True, error_message=None):
    """Log an API usage record"""
    connection = get_connection()
    if not connection:
        return None
    try:
        estimated_cost = calculate_api_cost(provider, model, input_tokens, output_tokens)
        with connection.cursor() as cursor:
            cursor.execute("""
                INSERT INTO APIUsage (tool_id, provider, model, input_tokens, output_tokens, estimated_cost, success, error_message)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING usage_id
            """, (tool_id, provider, model, input_tokens, output_tokens, estimated_cost, success, error_message))
            usage_id = cursor.fetchone()[0]
            connection.commit()
            return usage_id
    except Exception as e:
        print(f"Error logging API usage: {e}")
        return None
    finally:
        connection.close()


def get_api_usage_stats(days=30):
    """Get API usage statistics for the specified period"""
    # Default structure to return if no data or connection error
    default_stats = {
        'per_tool': [],
        'totals': {
            'total_requests': 0,
            'total_input_tokens': 0,
            'total_output_tokens': 0,
            'total_cost': 0.0,
            'failed_requests': 0
        },
        'daily': [],
        'period_days': days
    }
    
    connection = get_connection()
    if not connection:
        return default_stats
    try:
        with connection.cursor() as cursor:
            # Usage per tool
            cursor.execute("""
                SELECT t.name, t.slug, 
                       COUNT(a.usage_id) as requests,
                       COALESCE(SUM(a.input_tokens), 0) as total_input_tokens,
                       COALESCE(SUM(a.output_tokens), 0) as total_output_tokens,
                       COALESCE(SUM(a.estimated_cost), 0) as total_cost,
                       COUNT(CASE WHEN a.success = FALSE THEN 1 END) as failed_requests
                FROM AITool t
                LEFT JOIN APIUsage a ON t.tool_id = a.tool_id 
                    AND a.created_at >= CURRENT_DATE - INTERVAL '%s days'
                GROUP BY t.tool_id, t.name, t.slug
                ORDER BY total_cost DESC
            """, (days,))
            usage_per_tool = [
                {
                    'name': row[0],
                    'slug': row[1],
                    'requests': int(row[2]) if row[2] else 0,
                    'input_tokens': int(row[3]) if row[3] else 0,
                    'output_tokens': int(row[4]) if row[4] else 0,
                    'total_cost': float(row[5]) if row[5] else 0.0,
                    'failed_requests': int(row[6]) if row[6] else 0
                }
                for row in cursor.fetchall()
            ]
            
            # Total stats
            cursor.execute("""
                SELECT COUNT(*) as total_requests,
                       COALESCE(SUM(input_tokens), 0) as total_input_tokens,
                       COALESCE(SUM(output_tokens), 0) as total_output_tokens,
                       COALESCE(SUM(estimated_cost), 0) as total_cost,
                       COUNT(CASE WHEN success = FALSE THEN 1 END) as failed_requests
                FROM APIUsage
                WHERE created_at >= CURRENT_DATE - INTERVAL '%s days'
            """, (days,))
            row = cursor.fetchone()
            totals = {
                'total_requests': int(row[0]) if row[0] else 0,
                'total_input_tokens': int(row[1]) if row[1] else 0,
                'total_output_tokens': int(row[2]) if row[2] else 0,
                'total_cost': float(row[3]) if row[3] else 0.0,
                'failed_requests': int(row[4]) if row[4] else 0
            }
            
            # Daily usage for chart
            cursor.execute("""
                SELECT DATE(created_at) as date, 
                       COUNT(*) as requests,
                       COALESCE(SUM(estimated_cost), 0) as cost
                FROM APIUsage
                WHERE created_at >= CURRENT_DATE - INTERVAL '%s days'
                GROUP BY DATE(created_at)
                ORDER BY date
            """, (days,))
            daily_usage = [
                {'date': row[0].strftime('%Y-%m-%d'), 'requests': row[1], 'cost': float(row[2])}
                for row in cursor.fetchall()
            ]
            
            return {
                'per_tool': usage_per_tool,
                'totals': totals,
                'daily': daily_usage,
                'period_days': days
            }
    except Exception as e:
        print(f"Error getting API usage stats: {e}")
        return default_stats
    finally:
        connection.close()


def get_api_errors(days=30, page=1, per_page=50):
    """Get recent API errors with details for admin review"""
    connection = get_connection()
    if not connection:
        return [], 0
    try:
        offset = (page - 1) * per_page
        with connection.cursor() as cursor:
            # Get total count of errors
            cursor.execute("""
                SELECT COUNT(*) FROM APIUsage 
                WHERE success = FALSE 
                  AND created_at >= CURRENT_DATE - INTERVAL '%s days'
            """, (days,))
            total = cursor.fetchone()[0]
            
            # Get paginated error details
            cursor.execute("""
                SELECT a.usage_id, a.provider, a.model, a.error_message, a.created_at,
                       t.name as tool_name, t.slug as tool_slug
                FROM APIUsage a
                LEFT JOIN AITool t ON a.tool_id = t.tool_id
                WHERE a.success = FALSE
                  AND a.created_at >= CURRENT_DATE - INTERVAL '%s days'
                ORDER BY a.created_at DESC
                LIMIT %s OFFSET %s
            """, (days, per_page, offset))
            errors = [
                {
                    'id': row[0],
                    'provider': row[1],
                    'model': row[2],
                    'error_message': row[3],
                    'created_at': row[4],
                    'tool_name': row[5],
                    'tool_slug': row[6]
                }
                for row in cursor.fetchall()
            ]
            return errors, total
    except Exception as e:
        print(f"Error getting API errors: {e}")
        return [], 0
    finally:
        connection.close()


def get_api_error_summary(days=30):
    """Get summary of API errors grouped by provider and error type"""
    connection = get_connection()
    if not connection:
        return []
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT a.provider, t.name as tool_name, t.slug as tool_slug,
                       COUNT(*) as error_count,
                       MAX(a.created_at) as last_error,
                       array_agg(DISTINCT LEFT(a.error_message, 100)) as sample_errors
                FROM APIUsage a
                LEFT JOIN AITool t ON a.tool_id = t.tool_id
                WHERE a.success = FALSE
                  AND a.created_at >= CURRENT_DATE - INTERVAL '%s days'
                GROUP BY a.provider, t.name, t.slug
                ORDER BY error_count DESC
            """, (days,))
            return [
                {
                    'provider': row[0],
                    'tool_name': row[1],
                    'tool_slug': row[2],
                    'error_count': row[3],
                    'last_error': row[4],
                    'sample_errors': row[5][:3] if row[5] else []  # Keep top 3 unique errors
                }
                for row in cursor.fetchall()
            ]
    except Exception as e:
        print(f"Error getting API error summary: {e}")
        return []
    finally:
        connection.close()


# ============== Admin Functions ==============

def get_admin_statistics():
    """Get comprehensive statistics for admin dashboard"""
    connection = get_connection()
    if not connection:
        return {}
    try:
        stats = {}
        with connection.cursor() as cursor:
            # Total posts
            cursor.execute("SELECT COUNT(*) FROM Post")
            stats['total_posts'] = cursor.fetchone()[0]
            
            # Posts this week
            cursor.execute("SELECT COUNT(*) FROM Post WHERE CreatedAt >= CURRENT_DATE - INTERVAL '7 days'")
            stats['posts_this_week'] = cursor.fetchone()[0]
            
            # Posts this month
            cursor.execute("SELECT COUNT(*) FROM Post WHERE CreatedAt >= CURRENT_DATE - INTERVAL '30 days'")
            stats['posts_this_month'] = cursor.fetchone()[0]
            
            # Total users
            cursor.execute("SELECT COUNT(*) FROM Users")
            stats['total_users'] = cursor.fetchone()[0]
            
            # Users this week
            cursor.execute("SELECT COUNT(*) FROM Users WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'")
            stats['new_users_this_week'] = cursor.fetchone()[0]
            
            # Total comments
            cursor.execute("SELECT COUNT(*) FROM Comment")
            stats['total_comments'] = cursor.fetchone()[0]
            
            # Comments this week
            cursor.execute("SELECT COUNT(*) FROM Comment WHERE CreatedAt >= CURRENT_DATE - INTERVAL '7 days'")
            stats['comments_this_week'] = cursor.fetchone()[0]
            
            # Spam comments pending
            cursor.execute("SELECT COUNT(*) FROM Comment WHERE is_spam = TRUE")
            stats['spam_comments'] = cursor.fetchone()[0]
            
            # Total subscriptions
            cursor.execute("SELECT COUNT(*) FROM Subscription")
            stats['total_subscriptions'] = cursor.fetchone()[0]
            
            # Total bookmarks
            cursor.execute("SELECT COUNT(*) FROM Bookmark")
            stats['total_bookmarks'] = cursor.fetchone()[0]
            
            # Posts per tool
            cursor.execute("""
                SELECT t.name, t.slug, COUNT(p.postid) as count
                FROM AITool t
                LEFT JOIN Post p ON t.tool_id = p.tool_id
                GROUP BY t.tool_id, t.name, t.slug
                ORDER BY count DESC
            """)
            stats['posts_per_tool'] = [{'name': row[0], 'slug': row[1], 'count': row[2]} for row in cursor.fetchall()]
            
            # Recent posts (last 10)
            cursor.execute("""
                SELECT p.postid, p.Title, p.Category, p.CreatedAt, t.name
                FROM Post p
                LEFT JOIN AITool t ON p.tool_id = t.tool_id
                ORDER BY p.CreatedAt DESC
                LIMIT 10
            """)
            stats['recent_posts'] = [
                {
                    'id': row[0],
                    'title': row[1],
                    'category': row[2],
                    'created_at': row[3],
                    'tool_name': row[4]
                }
                for row in cursor.fetchall()
            ]
            
            # Recent users (last 10)
            cursor.execute("""
                SELECT user_id, username, email, created_at, is_admin
                FROM Users
                ORDER BY created_at DESC
                LIMIT 10
            """)
            stats['recent_users'] = [
                {
                    'id': row[0],
                    'username': row[1],
                    'email': row[2],
                    'created_at': row[3],
                    'is_admin': row[4]
                }
                for row in cursor.fetchall()
            ]
            
            # Posts per day (last 30 days for chart)
            cursor.execute("""
                SELECT DATE(CreatedAt) as date, COUNT(*) as count
                FROM Post
                WHERE CreatedAt >= CURRENT_DATE - INTERVAL '30 days'
                GROUP BY DATE(CreatedAt)
                ORDER BY date
            """)
            stats['posts_per_day'] = [{'date': str(row[0]), 'count': row[1]} for row in cursor.fetchall()]
            
        return stats
    finally:
        connection.close()


def get_all_users(page=1, per_page=20):
    """Get paginated list of all users for admin"""
    connection = get_connection()
    if not connection:
        return [], 0
    try:
        offset = (page - 1) * per_page
        with connection.cursor() as cursor:
            # Get total count
            cursor.execute("SELECT COUNT(*) FROM Users")
            total = cursor.fetchone()[0]
            
            # Get users
            cursor.execute("""
                SELECT user_id, username, email, is_active, is_admin, email_notifications, created_at
                FROM Users
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
            """, (per_page, offset))
            
            users = [
                {
                    'id': row[0],
                    'username': row[1],
                    'email': row[2],
                    'is_active': row[3],
                    'is_admin': row[4],
                    'email_notifications': row[5],
                    'created_at': row[6]
                }
                for row in cursor.fetchall()
            ]
            
            return users, total
    finally:
        connection.close()


def get_spam_comments(page=1, per_page=20):
    """Get paginated spam comments for moderation"""
    connection = get_connection()
    if not connection:
        return [], 0
    try:
        offset = (page - 1) * per_page
        with connection.cursor() as cursor:
            # Get total count
            cursor.execute("SELECT COUNT(*) FROM Comment WHERE is_spam = TRUE")
            total = cursor.fetchone()[0]
            
            # Get comments
            cursor.execute("""
                SELECT c.commentid, c.content, c.CreatedAt, c.postid, p.Title, u.username
                FROM Comment c
                LEFT JOIN Post p ON c.postid = p.postid
                LEFT JOIN Users u ON c.user_id = u.user_id
                WHERE c.is_spam = TRUE
                ORDER BY c.CreatedAt DESC
                LIMIT %s OFFSET %s
            """, (per_page, offset))
            
            comments = [
                {
                    'id': row[0],
                    'content': row[1],
                    'created_at': row[2],
                    'post_id': row[3],
                    'post_title': row[4],
                    'username': row[5] or 'Anonymous'
                }
                for row in cursor.fetchall()
            ]
            
            return comments, total
    finally:
        connection.close()


def mark_comment_not_spam(comment_id):
    """Mark a comment as not spam"""
    connection = get_connection()
    if not connection:
        return False
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE Comment SET is_spam = FALSE WHERE commentid = %s",
                (comment_id,)
            )
            connection.commit()
            return cursor.rowcount > 0
    finally:
        connection.close()


def delete_comment(comment_id):
    """Delete a comment"""
    connection = get_connection()
    if not connection:
        return False
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM Comment WHERE commentid = %s",
                (comment_id,)
            )
            connection.commit()
            return cursor.rowcount > 0
    finally:
        connection.close()


def toggle_user_admin(user_id, is_admin):
    """Toggle admin status for a user"""
    connection = get_connection()
    if not connection:
        return False
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE Users SET is_admin = %s WHERE user_id = %s",
                (is_admin, user_id)
            )
            connection.commit()
            return cursor.rowcount > 0
    finally:
        connection.close()


def toggle_user_active(user_id, is_active):
    """Toggle active status for a user"""
    connection = get_connection()
    if not connection:
        return False
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE Users SET is_active = %s WHERE user_id = %s",
                (is_active, user_id)
            )
            connection.commit()
            return cursor.rowcount > 0
    finally:
        connection.close()


# ============== Matchups & Votes ==============

VOTE_CATEGORIES = ('writing_quality', 'accuracy', 'creativity', 'usefulness', 'overall')
VOTE_LOCK_MINUTES = 5
DAILY_VOTE_LIMIT = 50

# Structured error codes for vote pipeline
VOTE_ERROR_STATUS = {
    'AUTH_REQUIRED': 401,
    'PREMIUM_REQUIRED': 403,
    'MATCHUP_NOT_FOUND': 404,
    'MATCHUP_INACTIVE': 409,
    'INVALID_PAYLOAD': 400,
    'DUPLICATE_CATEGORY': 400,
    'INVALID_CATEGORY': 400,
    'INVALID_WINNER': 400,
    'VOTE_LOCKED': 409,
    'RATE_LIMITED': 429,
    'EXISTING_VOTES_USE_PATCH': 409,
    'NEW_VOTE_VIA_PATCH': 400,
    'DUPLICATE_VOTE': 409,
    'FREE_LIMIT_REACHED': 403,
}


def _make_vote_error(code, message=None, details=None):
    """Build a structured error response dict for the vote pipeline."""
    status_code = VOTE_ERROR_STATUS.get(code, 500)
    return {
        'success': False,
        'status_code': status_code,
        'error': {
            'code': code,
            'message': message or code.replace('_', ' ').title(),
            'details': details or {}
        }
    }


def _log_vote_event(cursor, event_type, user_id, matchup_id, categories=None,
                    error_code=None, metadata=None):
    """Append a row to the vote_events audit table (call within an existing transaction)."""
    cursor.execute("""
        INSERT INTO vote_events (event_type, user_id, matchup_id, categories,
                                 error_code, metadata)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (event_type, user_id, matchup_id, categories,
          error_code, psycopg2.extras.Json(metadata or {})))


def get_user_vote_count_24h(user_id):
    """Count votes cast by user in the last 24 hours (for rate limiting)."""
    connection = get_connection()
    if not connection:
        return 0
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT COUNT(*) FROM votes
                WHERE user_id = %s
                  AND voted_at > CURRENT_TIMESTAMP - INTERVAL '24 hours'
            """, (user_id,))
            return cursor.fetchone()[0]
    except Exception:
        return 0
    finally:
        connection.close()


def create_matchup(post_a_id, post_b_id, prompt_id=None):
    """
    Create a new matchup between two posts from different AI tools.

    Enforces:
    - Posts must exist and belong to different, active AI tools
    - Canonical ordering (tool_a < tool_b by ID) applied automatically
    - No duplicate matchup for the same post pair

    Returns matchup_id if successful, None on failure.
    """
    if post_a_id == post_b_id:
        logger.warning("Cannot create matchup: same post for both sides")
        return None

    connection = get_connection()
    if not connection:
        return None
    try:
        with connection.cursor() as cursor:
            # Fetch both posts with their tool info
            cursor.execute("""
                SELECT p.postid, p.tool_id, t.status
                FROM Post p
                JOIN AITool t ON p.tool_id = t.tool_id
                WHERE p.postid IN (%s, %s)
            """, (post_a_id, post_b_id))
            rows = cursor.fetchall()

            if len(rows) != 2:
                logger.warning("Cannot create matchup: one or both posts not found")
                return None

            post_map = {row[0]: {'tool_id': row[1], 'status': row[2]} for row in rows}

            tool_a_id = post_map[post_a_id]['tool_id']
            tool_b_id = post_map[post_b_id]['tool_id']

            if tool_a_id == tool_b_id:
                logger.warning("Cannot create matchup: both posts from same tool")
                return None

            # Check both tools are active
            for pid in [post_a_id, post_b_id]:
                if post_map[pid]['status'] != 'active':
                    logger.warning(f"Cannot create matchup: tool for post {pid} is not active")
                    return None

            # Canonical ordering: ensure tool_a < tool_b by ID
            if tool_a_id < tool_b_id:
                final_post_a, final_post_b = post_a_id, post_b_id
                final_tool_a, final_tool_b = tool_a_id, tool_b_id
            else:
                final_post_a, final_post_b = post_b_id, post_a_id
                final_tool_a, final_tool_b = tool_b_id, tool_a_id

            import random
            position_seed = random.randint(0, 2**31 - 1)

            cursor.execute("""
                INSERT INTO matchups (post_a_id, post_b_id, tool_a, tool_b, prompt_id, position_seed)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING matchup_id
            """, (final_post_a, final_post_b, final_tool_a, final_tool_b, prompt_id, position_seed))

            matchup_id = cursor.fetchone()[0]
            connection.commit()
            return matchup_id
    except Exception as e:
        try:
            connection.rollback()
        except Exception:
            pass
        if 'unique' in str(e).lower() or 'duplicate' in str(e).lower():
            logger.info(f"Matchup already exists for posts {post_a_id} and {post_b_id}")
        else:
            logger.error(f"Error creating matchup: {e}")
        return None
    finally:
        connection.close()


def generate_missing_matchups():
    """
    Generate all missing matchups between posts from different active AI tools.

    Uses a single SQL INSERT with ON CONFLICT DO NOTHING for efficiency.
    Returns the number of newly created matchups.
    """
    connection = get_connection()
    if not connection:
        return 0
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                INSERT INTO matchups (post_a_id, post_b_id, tool_a, tool_b, position_seed, status)
                SELECT
                    CASE WHEN pa.tool_id < pb.tool_id THEN pa.postid ELSE pb.postid END,
                    CASE WHEN pa.tool_id < pb.tool_id THEN pb.postid ELSE pa.postid END,
                    LEAST(pa.tool_id, pb.tool_id),
                    GREATEST(pa.tool_id, pb.tool_id),
                    floor(random() * 2147483647)::int,
                    'active'
                FROM Post pa
                JOIN AITool ta ON pa.tool_id = ta.tool_id
                JOIN Post pb ON pa.postid < pb.postid
                JOIN AITool tb ON pb.tool_id = tb.tool_id
                WHERE ta.status = 'active'
                  AND tb.status = 'active'
                  AND pa.tool_id != pb.tool_id
                ON CONFLICT (post_a_id, post_b_id) DO NOTHING
            """)
            created_count = cursor.rowcount
            connection.commit()
            logger.info(f"Generated {created_count} new matchups")
            return created_count
    except Exception as e:
        try:
            connection.rollback()
        except Exception:
            pass
        logger.error(f"Error generating matchups: {e}")
        return 0
    finally:
        connection.close()


def get_matchup(matchup_id):
    """Get a matchup with full post and tool details"""
    connection = get_connection()
    if not connection:
        return None
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT m.matchup_id, m.post_a_id, m.post_b_id, m.tool_a, m.tool_b,
                       m.prompt_id, m.position_seed, m.status, m.created_at,
                       pa.Title, pa.Content, pa.Category,
                       pb.Title, pb.Content, pb.Category,
                       ta.name, ta.slug, ta.icon_url,
                       tb.name, tb.slug, tb.icon_url
                FROM matchups m
                JOIN Post pa ON m.post_a_id = pa.postid
                JOIN Post pb ON m.post_b_id = pb.postid
                JOIN AITool ta ON m.tool_a = ta.tool_id
                JOIN AITool tb ON m.tool_b = tb.tool_id
                WHERE m.matchup_id = %s
            """, (matchup_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return {
                'matchup_id': row[0],
                'post_a_id': row[1], 'post_b_id': row[2],
                'tool_a': row[3], 'tool_b': row[4],
                'prompt_id': row[5], 'position_seed': row[6],
                'status': row[7], 'created_at': row[8],
                'title_a': row[9], 'content_a': row[10], 'category_a': row[11],
                'title_b': row[12], 'content_b': row[13], 'category_b': row[14],
                'tool_a_name': row[15], 'tool_a_slug': row[16], 'tool_a_icon': row[17],
                'tool_b_name': row[18], 'tool_b_slug': row[19], 'tool_b_icon': row[20]
            }
    finally:
        connection.close()


def get_matchup_by_posts(post_a_id, post_b_id):
    """Find an existing matchup between two posts (order-independent)"""
    connection = get_connection()
    if not connection:
        return None
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT matchup_id FROM matchups
                WHERE (post_a_id = %s AND post_b_id = %s)
                   OR (post_a_id = %s AND post_b_id = %s)
            """, (post_a_id, post_b_id, post_b_id, post_a_id))
            row = cursor.fetchone()
            if row:
                return get_matchup(row[0])
            return None
    finally:
        connection.close()


def get_active_matchups_for_post(post_id):
    """Get all active matchups that include this post, with opposing tool info."""
    connection = get_connection()
    if not connection:
        return []
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT m.matchup_id,
                       CASE WHEN m.post_a_id = %s THEN tb.name ELSE ta.name END,
                       CASE WHEN m.post_a_id = %s THEN tb.slug ELSE ta.slug END
                FROM matchups m
                JOIN AITool ta ON m.tool_a = ta.tool_id
                JOIN AITool tb ON m.tool_b = tb.tool_id
                WHERE (m.post_a_id = %s OR m.post_b_id = %s)
                  AND m.status = 'active'
                ORDER BY m.created_at DESC
            """, (post_id, post_id, post_id, post_id))
            return [
                {
                    'matchup_id': row[0],
                    'opposing_tool_name': row[1],
                    'opposing_tool_slug': row[2]
                }
                for row in cursor.fetchall()
            ]
    except Exception:
        return []
    finally:
        connection.close()


def cast_vote(user_id, matchup_id, category, winner_tool_id):
    """
    Cast or update a vote on a matchup.

    Enforces:
    - User must have premium subscription
    - Matchup must exist and be active
    - Category must be valid
    - winner_tool_id must be one of the two tools in the matchup
    - Cannot change a locked vote

    Returns dict with 'success', 'vote_id', and 'error' keys.
    """
    if category not in VOTE_CATEGORIES:
        return {'success': False, 'vote_id': None, 'error': f'Invalid category: {category}'}

    if not is_user_premium(user_id):
        return {'success': False, 'vote_id': None, 'error': 'Premium subscription required to vote'}

    connection = get_connection()
    if not connection:
        return {'success': False, 'vote_id': None, 'error': 'Database connection failed'}
    try:
        with connection.cursor() as cursor:
            # Get matchup details and validate
            cursor.execute("""
                SELECT matchup_id, tool_a, tool_b, position_seed, status
                FROM matchups WHERE matchup_id = %s
            """, (matchup_id,))
            matchup = cursor.fetchone()

            if not matchup:
                return {'success': False, 'vote_id': None, 'error': 'Matchup not found'}

            if matchup[4] != 'active':
                return {'success': False, 'vote_id': None, 'error': 'Matchup is not active'}

            tool_a, tool_b = matchup[1], matchup[2]
            position_seed = matchup[3]

            if winner_tool_id not in (tool_a, tool_b):
                return {'success': False, 'vote_id': None, 'error': 'Winner must be one of the matchup tools'}

            # Check if existing vote is locked
            cursor.execute("""
                SELECT vote_id, locked FROM votes
                WHERE user_id = %s AND matchup_id = %s AND category = %s
            """, (user_id, matchup_id, category))
            existing = cursor.fetchone()

            if existing and existing[1]:
                return {'success': False, 'vote_id': existing[0], 'error': 'Vote is locked and cannot be changed'}

            # Determine position_a_was_left from position_seed and user_id
            position_a_was_left = ((position_seed + user_id) % 2 == 0)

            # Upsert vote — only updates if not locked
            cursor.execute("""
                INSERT INTO votes (user_id, matchup_id, category, winner_tool, voted_at, position_a_was_left)
                VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP, %s)
                ON CONFLICT (user_id, matchup_id, category)
                DO UPDATE SET winner_tool = EXCLUDED.winner_tool,
                              voted_at = CURRENT_TIMESTAMP,
                              position_a_was_left = EXCLUDED.position_a_was_left
                WHERE votes.locked = FALSE
                RETURNING vote_id
            """, (user_id, matchup_id, category, winner_tool_id, position_a_was_left))

            result = cursor.fetchone()
            if not result:
                return {'success': False, 'vote_id': None, 'error': 'Vote is locked and cannot be changed'}

            connection.commit()
            return {'success': True, 'vote_id': result[0], 'error': None}
    except Exception as e:
        try:
            connection.rollback()
        except Exception:
            pass
        logger.error(f"Error casting vote: {e}")
        return {'success': False, 'vote_id': None, 'error': 'An unexpected error occurred'}
    finally:
        connection.close()


def get_user_votes_for_matchup(user_id, matchup_id):
    """Get all of a user's votes for a specific matchup"""
    connection = get_connection()
    if not connection:
        return []
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT vote_id, category, winner_tool, voted_at, locked, position_a_was_left
                FROM votes
                WHERE user_id = %s AND matchup_id = %s
                ORDER BY category
            """, (user_id, matchup_id))
            return [
                {
                    'vote_id': row[0],
                    'category': row[1],
                    'winner_tool': row[2],
                    'voted_at': row[3],
                    'locked': row[4],
                    'position_a_was_left': row[5]
                }
                for row in cursor.fetchall()
            ]
    finally:
        connection.close()


def get_matchup_vote_counts(matchup_id):
    """Get vote counts per category and tool for a matchup"""
    connection = get_connection()
    if not connection:
        return {}
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT category, winner_tool, COUNT(*) as count
                FROM votes
                WHERE matchup_id = %s
                GROUP BY category, winner_tool
                ORDER BY category, winner_tool
            """, (matchup_id,))
            results = {}
            for row in cursor.fetchall():
                cat = row[0]
                if cat not in results:
                    results[cat] = {}
                results[cat][row[1]] = row[2]
            return results
    finally:
        connection.close()


def get_matchup_total_votes(matchup_id):
    """Get total number of individual votes cast on a matchup (across all categories/users)"""
    connection = get_connection()
    if not connection:
        return 0
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM votes WHERE matchup_id = %s", (matchup_id,))
            return cursor.fetchone()[0]
    finally:
        connection.close()


def batch_submit_votes(user_id, matchup_id, votes, position_a_is_left, metadata=None):
    """
    Atomically submit a batch of votes for a matchup.

    All votes succeed or all fail. Validates every constraint before inserting.

    Args:
        user_id: int
        matchup_id: int
        votes: list of {'category': str, 'winner_tool': int}
        position_a_is_left: bool
        metadata: optional dict for audit log (ip, read_time_seconds, etc.)

    Returns dict with 'success', 'status_code', and either 'vote_ids'+'edit_window_expires_at'
    or 'error' with 'code', 'message', 'details'.
    """
    # --- Fast validation (no DB) ---
    if not votes or len(votes) > len(VOTE_CATEGORIES):
        return _make_vote_error('INVALID_PAYLOAD',
                                f'Submit between 1 and {len(VOTE_CATEGORIES)} category votes.')

    categories = [v['category'] for v in votes]
    seen = set()
    for cat in categories:
        if cat in seen:
            return _make_vote_error('DUPLICATE_CATEGORY',
                                    f'Duplicate category in submission: {cat}.',
                                    {'category': cat})
        seen.add(cat)

    for v in votes:
        if v['category'] not in VOTE_CATEGORIES:
            return _make_vote_error('INVALID_CATEGORY',
                                    f"Invalid category: {v['category']}.",
                                    {'category': v['category']})
        if v.get('winner_tool') is None:
            return _make_vote_error('INVALID_WINNER',
                                    'Winner must be one of the tools in this matchup.')

    # --- DB transaction ---
    connection = get_connection()
    if not connection:
        return _make_vote_error('MATCHUP_NOT_FOUND', 'Database connection failed.')
    try:
        with connection.cursor() as cursor:
            # Premium check (inline, same connection)
            cursor.execute("""
                SELECT EXISTS(
                    SELECT 1 FROM UserSubscription us
                    JOIN SubscriptionPlan sp ON us.plan_id = sp.plan_id
                    WHERE us.user_id = %s
                      AND us.status IN ('active', 'trialing')
                      AND sp.name != 'free'
                      AND (us.current_period_end IS NULL
                           OR us.current_period_end > CURRENT_TIMESTAMP)
                )
            """, (user_id,))
            is_premium_user = cursor.fetchone()[0]
            if not is_premium_user:
                # Bootstrap free voting: allow limited votes for free users
                from config import Config
                if Config.BOOTSTRAP_FREE_VOTING_ENABLED:
                    # Check if user already voted on THIS matchup (doesn't count as new)
                    cursor.execute("""
                        SELECT COUNT(*) FROM votes
                        WHERE user_id = %s AND matchup_id = %s
                    """, (user_id, matchup_id))
                    already_voted_this = cursor.fetchone()[0] > 0

                    if not already_voted_this:
                        # Count distinct matchups voted this ISO week
                        cursor.execute("""
                            SELECT COUNT(DISTINCT matchup_id)
                            FROM votes
                            WHERE user_id = %s
                              AND voted_at >= date_trunc('week', CURRENT_TIMESTAMP)
                        """, (user_id,))
                        free_used = cursor.fetchone()[0]

                        if free_used >= Config.BOOTSTRAP_FREE_VOTES_PER_WEEK:
                            cat_str = ','.join(categories)
                            _log_vote_event(cursor, 'reject', user_id, matchup_id, cat_str,
                                            'FREE_LIMIT_REACHED', metadata)
                            connection.commit()
                            # Calculate next Monday 00:00 UTC for reset time
                            cursor.execute("""
                                SELECT date_trunc('week', CURRENT_TIMESTAMP) + INTERVAL '7 days'
                            """)
                            resets_at = cursor.fetchone()[0].isoformat() + 'Z'
                            return _make_vote_error('FREE_LIMIT_REACHED',
                                                    'You have used all your free comparisons this week.',
                                                    {'used': free_used,
                                                     'limit': Config.BOOTSTRAP_FREE_VOTES_PER_WEEK,
                                                     'resets_at': resets_at})
                    # Free user within limit — proceed to vote
                else:
                    cat_str = ','.join(categories)
                    _log_vote_event(cursor, 'reject', user_id, matchup_id, cat_str,
                                    'PREMIUM_REQUIRED', metadata)
                    connection.commit()
                    return _make_vote_error('PREMIUM_REQUIRED',
                                            'Voting requires a premium subscription.')

            # Matchup validation
            cursor.execute("""
                SELECT matchup_id, tool_a, tool_b, status
                FROM matchups WHERE matchup_id = %s
            """, (matchup_id,))
            matchup = cursor.fetchone()
            if not matchup:
                cat_str = ','.join(categories)
                _log_vote_event(cursor, 'reject', user_id, None, cat_str,
                                'MATCHUP_NOT_FOUND', metadata)
                connection.commit()
                return _make_vote_error('MATCHUP_NOT_FOUND', 'Matchup not found.')

            tool_a, tool_b = matchup[1], matchup[2]
            if matchup[3] != 'active':
                cat_str = ','.join(categories)
                _log_vote_event(cursor, 'reject', user_id, matchup_id, cat_str,
                                'MATCHUP_INACTIVE', metadata)
                connection.commit()
                return _make_vote_error('MATCHUP_INACTIVE',
                                        'This matchup is no longer accepting votes.')

            # Winner validation
            for v in votes:
                if v['winner_tool'] not in (tool_a, tool_b):
                    cat_str = ','.join(categories)
                    _log_vote_event(cursor, 'reject', user_id, matchup_id, cat_str,
                                    'INVALID_WINNER', metadata)
                    connection.commit()
                    return _make_vote_error('INVALID_WINNER',
                                            'Winner must be one of the tools in this matchup.',
                                            {'category': v['category'],
                                             'provided_tool_id': v['winner_tool']})

            # Rate limit check (reads from votes table)
            cursor.execute("""
                SELECT COUNT(*) FROM votes
                WHERE user_id = %s
                  AND voted_at > CURRENT_TIMESTAMP - INTERVAL '24 hours'
            """, (user_id,))
            current_count = cursor.fetchone()[0]
            if current_count + len(votes) > DAILY_VOTE_LIMIT:
                cat_str = ','.join(categories)
                _log_vote_event(cursor, 'reject', user_id, matchup_id, cat_str,
                                'RATE_LIMITED', metadata)
                connection.commit()
                return _make_vote_error('RATE_LIMITED',
                                        'Daily vote limit reached. Try again tomorrow.',
                                        {'limit': DAILY_VOTE_LIMIT,
                                         'current': current_count,
                                         'requested': len(votes)})

            # Check existing votes (with row lock)
            cursor.execute("""
                SELECT vote_id, category, winner_tool, locked
                FROM votes
                WHERE user_id = %s AND matchup_id = %s AND category = ANY(%s)
                FOR UPDATE
            """, (user_id, matchup_id, categories))
            existing = {row[1]: {'vote_id': row[0], 'winner_tool': row[2], 'locked': row[3]}
                        for row in cursor.fetchall()}

            if existing:
                # Check for locked votes
                for cat, ev in existing.items():
                    if ev['locked']:
                        cat_str = ','.join(categories)
                        _log_vote_event(cursor, 'reject', user_id, matchup_id, cat_str,
                                        'VOTE_LOCKED', metadata)
                        connection.commit()
                        return _make_vote_error('VOTE_LOCKED',
                                                'One or more votes are locked and cannot be changed.',
                                                {'locked_category': cat})

                # Build a map of submitted winners by category
                submitted = {v['category']: v['winner_tool'] for v in votes}

                # Check if any existing votes differ
                has_different = False
                for cat, ev in existing.items():
                    if cat in submitted and submitted[cat] != ev['winner_tool']:
                        has_different = True
                        break

                if has_different:
                    cat_str = ','.join(categories)
                    _log_vote_event(cursor, 'reject', user_id, matchup_id, cat_str,
                                    'EXISTING_VOTES_USE_PATCH', metadata)
                    connection.commit()
                    return _make_vote_error('EXISTING_VOTES_USE_PATCH',
                                            'Votes already exist for this matchup. Use PATCH to edit.')

                # All existing match → check if all submitted already exist (full idempotent)
                all_idempotent = all(cat in existing for cat in submitted)
                if all_idempotent:
                    cat_str = ','.join(categories)
                    _log_vote_event(cursor, 'submit', user_id, matchup_id, cat_str,
                                    None, metadata)
                    connection.commit()
                    return {
                        'success': True,
                        'status_code': 200,
                        'vote_ids': [existing[cat]['vote_id'] for cat in submitted],
                        'edit_window_expires_at': None
                    }

            # Insert new votes (only categories not already existing)
            vote_ids = []
            new_categories = []
            for v in votes:
                if v['category'] in existing:
                    vote_ids.append(existing[v['category']]['vote_id'])
                    continue
                cursor.execute("""
                    INSERT INTO votes (user_id, matchup_id, category, winner_tool,
                                       voted_at, position_a_was_left)
                    VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP, %s)
                    RETURNING vote_id
                """, (user_id, matchup_id, v['category'], v['winner_tool'],
                      position_a_is_left))
                vote_ids.append(cursor.fetchone()[0])
                new_categories.append(v['category'])

            # Get the edit window expiry
            cursor.execute("SELECT CURRENT_TIMESTAMP + INTERVAL '1 minute' * %s",
                           (VOTE_LOCK_MINUTES,))
            expires_at = cursor.fetchone()[0]

            cat_str = ','.join(categories)
            _log_vote_event(cursor, 'submit', user_id, matchup_id, cat_str,
                            None, metadata)
            connection.commit()

            return {
                'success': True,
                'status_code': 201,
                'vote_ids': vote_ids,
                'edit_window_expires_at': expires_at.isoformat()
            }

    except psycopg2.errors.UniqueViolation:
        try:
            connection.rollback()
        except Exception:
            pass
        return _make_vote_error('DUPLICATE_VOTE',
                                'You have already voted on this category for this matchup.')
    except Exception as e:
        try:
            connection.rollback()
        except Exception:
            pass
        logger.error(f"Error in batch_submit_votes: {e}")
        return _make_vote_error('INVALID_PAYLOAD', 'An unexpected error occurred.')
    finally:
        connection.close()


def batch_edit_votes(user_id, matchup_id, votes, position_a_is_left, metadata=None):
    """
    Atomically edit existing votes within the lock window.

    All edits succeed or all fail. Rejects new categories (must use POST).
    Real-time lock check: expires votes on the spot if > 5 minutes old.

    Args:
        user_id: int
        matchup_id: int
        votes: list of {'category': str, 'winner_tool': int}
        position_a_is_left: bool
        metadata: optional dict for audit log

    Returns same shape as batch_submit_votes.
    """
    # --- Fast validation (no DB) ---
    if not votes or len(votes) > len(VOTE_CATEGORIES):
        return _make_vote_error('INVALID_PAYLOAD',
                                f'Submit between 1 and {len(VOTE_CATEGORIES)} category votes.')

    categories = [v['category'] for v in votes]
    seen = set()
    for cat in categories:
        if cat in seen:
            return _make_vote_error('DUPLICATE_CATEGORY',
                                    f'Duplicate category in submission: {cat}.',
                                    {'category': cat})
        seen.add(cat)

    for v in votes:
        if v['category'] not in VOTE_CATEGORIES:
            return _make_vote_error('INVALID_CATEGORY',
                                    f"Invalid category: {v['category']}.",
                                    {'category': v['category']})
        if v.get('winner_tool') is None:
            return _make_vote_error('INVALID_WINNER',
                                    'Winner must be one of the tools in this matchup.')

    # --- DB transaction ---
    connection = get_connection()
    if not connection:
        return _make_vote_error('MATCHUP_NOT_FOUND', 'Database connection failed.')
    try:
        with connection.cursor() as cursor:
            # Premium check (inline)
            cursor.execute("""
                SELECT EXISTS(
                    SELECT 1 FROM UserSubscription us
                    JOIN SubscriptionPlan sp ON us.plan_id = sp.plan_id
                    WHERE us.user_id = %s
                      AND us.status IN ('active', 'trialing')
                      AND sp.name != 'free'
                      AND (us.current_period_end IS NULL
                           OR us.current_period_end > CURRENT_TIMESTAMP)
                )
            """, (user_id,))
            is_premium_user = cursor.fetchone()[0]
            if not is_premium_user:
                # Bootstrap: allow edits for free users who already voted on this matchup
                from config import Config
                if Config.BOOTSTRAP_FREE_VOTING_ENABLED:
                    cursor.execute("""
                        SELECT COUNT(*) FROM votes
                        WHERE user_id = %s AND matchup_id = %s
                    """, (user_id, matchup_id))
                    if cursor.fetchone()[0] == 0:
                        # No existing votes — can't edit what doesn't exist
                        cat_str = ','.join(categories)
                        _log_vote_event(cursor, 'reject', user_id, matchup_id, cat_str,
                                        'PREMIUM_REQUIRED', metadata)
                        connection.commit()
                        return _make_vote_error('PREMIUM_REQUIRED',
                                                'Voting requires a premium subscription.')
                    # Has existing votes on this matchup — allow edit
                else:
                    cat_str = ','.join(categories)
                    _log_vote_event(cursor, 'reject', user_id, matchup_id, cat_str,
                                    'PREMIUM_REQUIRED', metadata)
                    connection.commit()
                    return _make_vote_error('PREMIUM_REQUIRED',
                                            'Voting requires a premium subscription.')

            # Matchup validation
            cursor.execute("""
                SELECT matchup_id, tool_a, tool_b, status
                FROM matchups WHERE matchup_id = %s
            """, (matchup_id,))
            matchup = cursor.fetchone()
            if not matchup:
                cat_str = ','.join(categories)
                _log_vote_event(cursor, 'reject', user_id, None, cat_str,
                                'MATCHUP_NOT_FOUND', metadata)
                connection.commit()
                return _make_vote_error('MATCHUP_NOT_FOUND', 'Matchup not found.')

            tool_a, tool_b = matchup[1], matchup[2]
            if matchup[3] != 'active':
                cat_str = ','.join(categories)
                _log_vote_event(cursor, 'reject', user_id, matchup_id, cat_str,
                                'MATCHUP_INACTIVE', metadata)
                connection.commit()
                return _make_vote_error('MATCHUP_INACTIVE',
                                        'This matchup is no longer accepting votes.')

            # Winner validation
            for v in votes:
                if v['winner_tool'] not in (tool_a, tool_b):
                    cat_str = ','.join(categories)
                    _log_vote_event(cursor, 'reject', user_id, matchup_id, cat_str,
                                    'INVALID_WINNER', metadata)
                    connection.commit()
                    return _make_vote_error('INVALID_WINNER',
                                            'Winner must be one of the tools in this matchup.',
                                            {'category': v['category'],
                                             'provided_tool_id': v['winner_tool']})

            # No rate limit check for edits (they're free)

            # Fetch existing votes with row lock + elapsed seconds computed in SQL
            cursor.execute("""
                SELECT vote_id, category, winner_tool, locked,
                       EXTRACT(EPOCH FROM (LOCALTIMESTAMP - voted_at)) as elapsed_sec
                FROM votes
                WHERE user_id = %s AND matchup_id = %s AND category = ANY(%s)
                FOR UPDATE
            """, (user_id, matchup_id, categories))
            existing = {row[1]: {'vote_id': row[0], 'winner_tool': row[2],
                                 'locked': row[3], 'elapsed_sec': row[4]}
                        for row in cursor.fetchall()}

            # All submitted categories must already have votes
            for cat in categories:
                if cat not in existing:
                    cat_str = ','.join(categories)
                    _log_vote_event(cursor, 'reject', user_id, matchup_id, cat_str,
                                    'NEW_VOTE_VIA_PATCH', metadata)
                    connection.commit()
                    return _make_vote_error('NEW_VOTE_VIA_PATCH',
                                            'Cannot add new categories via PATCH. Use POST for initial votes.',
                                            {'category': cat})

            # Real-time lock check + opportunistic locking
            for cat, ev in existing.items():
                if ev['locked'] or ev['elapsed_sec'] > VOTE_LOCK_MINUTES * 60:
                    # Opportunistically lock if not already
                    if not ev['locked']:
                        cursor.execute(
                            "UPDATE votes SET locked = TRUE WHERE vote_id = %s",
                            (ev['vote_id'],))
                        _log_vote_event(cursor, 'lock', user_id, matchup_id, cat,
                                        None, metadata)
                    cat_str = ','.join(categories)
                    _log_vote_event(cursor, 'reject', user_id, matchup_id, cat_str,
                                    'VOTE_LOCKED', metadata)
                    connection.commit()
                    return _make_vote_error('VOTE_LOCKED',
                                            'One or more votes are locked and cannot be changed.',
                                            {'locked_category': cat})

            # Apply edits
            submitted = {v['category']: v['winner_tool'] for v in votes}
            vote_ids = []
            edited_categories = []

            all_same = all(submitted[cat] == existing[cat]['winner_tool'] for cat in categories)
            if all_same:
                # Idempotent no-op
                cat_str = ','.join(categories)
                _log_vote_event(cursor, 'edit', user_id, matchup_id, cat_str,
                                None, metadata)
                connection.commit()
                return {
                    'success': True,
                    'status_code': 200,
                    'vote_ids': [existing[cat]['vote_id'] for cat in categories],
                    'edit_window_expires_at': None
                }

            for cat in categories:
                ev = existing[cat]
                if submitted[cat] == ev['winner_tool']:
                    vote_ids.append(ev['vote_id'])
                    continue
                # Update the vote
                cursor.execute("""
                    UPDATE votes
                    SET winner_tool = %s, voted_at = CURRENT_TIMESTAMP,
                        position_a_was_left = %s
                    WHERE vote_id = %s AND locked = FALSE
                    RETURNING vote_id
                """, (submitted[cat], position_a_is_left, ev['vote_id']))
                result = cursor.fetchone()
                if not result:
                    # Race condition: locked between our check and update
                    connection.rollback()
                    return _make_vote_error('VOTE_LOCKED',
                                            'Vote was locked during edit.',
                                            {'category': cat})
                vote_ids.append(result[0])
                edited_categories.append(cat)

            # Get new edit window expiry
            cursor.execute("SELECT CURRENT_TIMESTAMP + INTERVAL '1 minute' * %s",
                           (VOTE_LOCK_MINUTES,))
            expires_at = cursor.fetchone()[0]

            cat_str = ','.join(categories)
            _log_vote_event(cursor, 'edit', user_id, matchup_id, cat_str,
                            None, metadata)
            connection.commit()

            return {
                'success': True,
                'status_code': 200,
                'vote_ids': vote_ids,
                'edit_window_expires_at': expires_at.isoformat()
            }

    except Exception as e:
        try:
            connection.rollback()
        except Exception:
            pass
        logger.error(f"Error in batch_edit_votes: {e}")
        return _make_vote_error('INVALID_PAYLOAD', 'An unexpected error occurred.')
    finally:
        connection.close()


def lock_expired_votes():
    """
    Lock votes older than VOTE_LOCK_MINUTES.
    Intended to be called by a background/cron job.

    Returns number of votes locked, or 0 on failure.
    """
    connection = get_connection()
    if not connection:
        return 0
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                UPDATE votes
                SET locked = TRUE
                WHERE locked = FALSE
                  AND voted_at < CURRENT_TIMESTAMP - INTERVAL '1 minute' * %s
            """, (VOTE_LOCK_MINUTES,))
            count = cursor.rowcount
            connection.commit()
            return count
    except Exception as e:
        try:
            connection.rollback()
        except Exception:
            pass
        logger.error(f"Error locking expired votes: {e}")
        return 0
    finally:
        connection.close()


# ============== Leaderboard Cache & Aggregation ==============

class _LeaderboardCache:
    """Simple in-memory cache with TTL for leaderboard API responses."""

    def __init__(self, ttl_seconds=300):
        self._store = {}
        self._ttl = ttl_seconds

    def get(self, key):
        entry = self._store.get(key)
        if entry is None:
            return None
        if _time.time() - entry['ts'] > self._ttl:
            del self._store[key]
            return None
        return entry['data'], _time.time() - entry['ts']

    def set(self, key, data):
        self._store[key] = {'data': data, 'ts': _time.time()}

    def invalidate_all(self):
        self._store.clear()


_leaderboard_cache = _LeaderboardCache(ttl_seconds=300)


def recompute_tool_stats():
    """
    Recompute the tool_stats summary table from raw vote data.

    Uses a single optimized query with conditional aggregation for
    all-time, 7-day, and previous-7-day windows. Upserts results.
    Returns {'tools_updated': int, 'duration_ms': int} or None on error.
    """
    start = _time.time()
    log_id = log_cron_start('recompute_tool_stats')

    connection = get_connection()
    if not connection:
        log_cron_failure(log_id, 'Could not get database connection')
        return None
    try:
        with connection.cursor() as cursor:
            # Single query: CROSS JOIN tools × categories, LEFT JOIN aggregated votes
            cursor.execute("""
                WITH tool_categories AS (
                    SELECT t.tool_id, t.status, cat.category
                    FROM AITool t
                    CROSS JOIN (VALUES
                        ('writing_quality'),('accuracy'),('creativity'),
                        ('usefulness'),('overall')
                    ) AS cat(category)
                    WHERE t.status IN ('active', 'pending')
                ),
                vote_agg AS (
                    SELECT
                        t.tool_id,
                        v.category,
                        COUNT(*) AS total_votes,
                        SUM(CASE WHEN v.winner_tool = t.tool_id THEN 1 ELSE 0 END) AS total_wins,
                        SUM(CASE WHEN v.voted_at > NOW() - INTERVAL '7 days' THEN 1 ELSE 0 END) AS votes_last_7d,
                        SUM(CASE WHEN v.voted_at > NOW() - INTERVAL '7 days'
                                      AND v.winner_tool = t.tool_id THEN 1 ELSE 0 END) AS wins_last_7d,
                        SUM(CASE WHEN v.voted_at BETWEEN NOW() - INTERVAL '14 days'
                                      AND NOW() - INTERVAL '7 days' THEN 1 ELSE 0 END) AS votes_prev_7d,
                        SUM(CASE WHEN v.voted_at BETWEEN NOW() - INTERVAL '14 days'
                                      AND NOW() - INTERVAL '7 days'
                                      AND v.winner_tool = t.tool_id THEN 1 ELSE 0 END) AS wins_prev_7d
                    FROM AITool t
                    JOIN matchups m ON (m.tool_a = t.tool_id OR m.tool_b = t.tool_id)
                    JOIN votes v ON v.matchup_id = m.matchup_id
                    WHERE t.status = 'active'
                      AND v.locked = TRUE
                      AND m.status = 'active'
                    GROUP BY t.tool_id, v.category
                )
                SELECT tc.tool_id, tc.status, tc.category,
                       COALESCE(va.total_votes, 0),
                       COALESCE(va.total_wins, 0),
                       COALESCE(va.votes_last_7d, 0),
                       COALESCE(va.wins_last_7d, 0),
                       COALESCE(va.votes_prev_7d, 0),
                       COALESCE(va.wins_prev_7d, 0)
                FROM tool_categories tc
                LEFT JOIN vote_agg va ON tc.tool_id = va.tool_id AND tc.category = va.category
            """)
            rows = cursor.fetchall()

            tools_updated = 0
            for row in rows:
                (tool_id, status, category,
                 total_votes, total_wins,
                 votes_last_7d, wins_last_7d,
                 votes_prev_7d, wins_prev_7d) = row

                win_rate = round(total_wins / total_votes, 4) if total_votes > 0 else None
                win_rate_7d = round(wins_last_7d / votes_last_7d, 4) if votes_last_7d > 0 else None
                win_rate_prev_7d = round(wins_prev_7d / votes_prev_7d, 4) if votes_prev_7d > 0 else None

                # Trend logic
                if votes_last_7d < 5 or votes_prev_7d < 5:
                    trend = 'stable'
                elif win_rate_7d is not None and win_rate_prev_7d is not None:
                    delta = win_rate_7d - win_rate_prev_7d
                    if delta > 0.05:
                        trend = 'up'
                    elif delta < -0.05:
                        trend = 'down'
                    else:
                        trend = 'stable'
                else:
                    trend = 'stable'

                cursor.execute("""
                    INSERT INTO tool_stats
                        (tool_id, category, total_votes, total_wins, win_rate,
                         wins_last_7d, votes_last_7d, win_rate_7d,
                         wins_prev_7d, votes_prev_7d, win_rate_prev_7d,
                         trend, computed_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                    ON CONFLICT (tool_id, category) DO UPDATE SET
                        total_votes = EXCLUDED.total_votes,
                        total_wins = EXCLUDED.total_wins,
                        win_rate = EXCLUDED.win_rate,
                        wins_last_7d = EXCLUDED.wins_last_7d,
                        votes_last_7d = EXCLUDED.votes_last_7d,
                        win_rate_7d = EXCLUDED.win_rate_7d,
                        wins_prev_7d = EXCLUDED.wins_prev_7d,
                        votes_prev_7d = EXCLUDED.votes_prev_7d,
                        win_rate_prev_7d = EXCLUDED.win_rate_prev_7d,
                        trend = EXCLUDED.trend,
                        computed_at = EXCLUDED.computed_at
                """, (tool_id, category, total_votes, total_wins, win_rate,
                      wins_last_7d, votes_last_7d, win_rate_7d,
                      wins_prev_7d, votes_prev_7d, win_rate_prev_7d,
                      trend))
                tools_updated += 1

            connection.commit()

        duration_ms = int((_time.time() - start) * 1000)
        _leaderboard_cache.invalidate_all()
        log_cron_complete(log_id, details={'tools_updated': tools_updated, 'duration_ms': duration_ms})
        return {'tools_updated': tools_updated, 'duration_ms': duration_ms}
    except Exception as e:
        try:
            connection.rollback()
        except Exception:
            pass
        logger.error(f"Error recomputing tool stats: {e}")
        log_cron_failure(log_id, str(e))
        return None
    finally:
        connection.close()


def get_tool_stats_for_leaderboard(category, min_votes=30):
    """
    Get tool stats for the leaderboard, split into above/below threshold.

    Returns (above_threshold_list, below_threshold_list).
    Each item is a dict with tool_id, name, slug, status, total_votes,
    total_wins, win_rate, votes_last_7d, win_rate_7d, trend, computed_at.
    """
    connection = get_connection()
    if not connection:
        return [], []
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT ts.tool_id, t.name, t.slug, t.status,
                       ts.total_votes, ts.total_wins, ts.win_rate,
                       ts.votes_last_7d, ts.win_rate_7d,
                       ts.wins_last_7d, ts.votes_prev_7d, ts.win_rate_prev_7d,
                       ts.trend, ts.computed_at
                FROM tool_stats ts
                JOIN AITool t ON ts.tool_id = t.tool_id
                WHERE ts.category = %s
                ORDER BY ts.win_rate DESC NULLS LAST, ts.total_votes DESC
            """, (category,))
            rows = cursor.fetchall()

        above = []
        below = []
        for row in rows:
            item = {
                'tool_id': row[0],
                'name': row[1],
                'slug': row[2],
                'status': row[3],
                'total_votes': row[4],
                'total_wins': row[5],
                'win_rate': float(row[6]) if row[6] is not None else 0.0,
                'votes_last_7d': row[7],
                'win_rate_7d': float(row[8]) if row[8] is not None else 0.0,
                'wins_last_7d': row[9],
                'votes_prev_7d': row[10],
                'win_rate_prev_7d': float(row[11]) if row[11] is not None else 0.0,
                'trend': row[12],
                'computed_at': row[13].isoformat() if row[13] else None,
            }
            if item['total_votes'] >= min_votes and item['status'] == 'active':
                above.append(item)
            else:
                below.append(item)
        return above, below
    except Exception as e:
        try:
            connection.rollback()
        except Exception:
            pass
        logger.error(f"Error getting tool stats for leaderboard: {e}")
        return [], []
    finally:
        connection.close()


def get_tool_category_breakdown(tool_id):
    """
    Get all 5 category stats for a single tool.
    Returns {category: {'win_rate': float, 'trend': str}}.
    """
    connection = get_connection()
    if not connection:
        return {}
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT category, win_rate, trend
                FROM tool_stats
                WHERE tool_id = %s
            """, (tool_id,))
            rows = cursor.fetchall()
        return {
            row[0]: {
                'win_rate': float(row[1]) if row[1] is not None else 0.0,
                'trend': row[2],
            }
            for row in rows
        }
    except Exception as e:
        try:
            connection.rollback()
        except Exception:
            pass
        logger.error(f"Error getting tool category breakdown: {e}")
        return {}
    finally:
        connection.close()


def get_tool_rank_badges(min_votes=30):
    """
    Find which tools are #1 in each category (with enough votes).
    Returns {tool_id: [{'category': str, 'category_display': str}]}.
    """
    display_names = {
        'writing_quality': 'Writing Quality',
        'accuracy': 'Accuracy',
        'creativity': 'Creativity',
        'usefulness': 'Usefulness',
        'overall': 'Overall',
    }
    connection = get_connection()
    if not connection:
        return {}
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT DISTINCT ON (ts.category) ts.category, ts.tool_id
                FROM tool_stats ts
                JOIN AITool t ON ts.tool_id = t.tool_id
                WHERE t.status = 'active'
                  AND ts.total_votes >= %s
                  AND ts.win_rate IS NOT NULL
                ORDER BY ts.category, ts.win_rate DESC, ts.total_votes DESC
            """, (min_votes,))
            rows = cursor.fetchall()

        badges = {}
        for row in rows:
            cat, tool_id = row[0], row[1]
            if tool_id not in badges:
                badges[tool_id] = []
            badges[tool_id].append({
                'category': cat,
                'category_display': display_names.get(cat, cat),
            })
        return badges
    except Exception as e:
        try:
            connection.rollback()
        except Exception:
            pass
        logger.error(f"Error getting tool rank badges: {e}")
        return {}
    finally:
        connection.close()


# ============== Head-to-Head Stats ==============

def recompute_h2h_stats():
    """
    Recompute the h2h_stats summary table from raw vote data.

    Generates all pair/category combos, aggregates locked votes from active
    matchups, computes win rates, trends, and confidence, then upserts.
    Returns {'pairs_updated': int, 'duration_ms': int} or None on error.
    """
    start = _time.time()
    log_id = log_cron_start('recompute_h2h_stats')

    connection = get_connection()
    if not connection:
        log_cron_failure(log_id, 'Could not get database connection')
        return None
    try:
        with connection.cursor() as cursor:
            # Get all active+pending tools
            cursor.execute("""
                SELECT tool_id, status FROM AITool
                WHERE status IN ('active', 'pending')
                ORDER BY tool_id
            """)
            tools = cursor.fetchall()

            # Generate all pair/category combos (canonical: tool_a_id < tool_b_id)
            all_combos = {}
            for i, (tid_a, status_a) in enumerate(tools):
                for tid_b, status_b in tools[i + 1:]:
                    has_pending = (status_a == 'pending' or status_b == 'pending')
                    for cat in VOTE_CATEGORIES:
                        all_combos[(tid_a, tid_b, cat)] = {
                            'has_pending': has_pending,
                            'total_votes': 0, 'tool_a_wins': 0, 'tool_b_wins': 0,
                            'total_votes_7d': 0, 'tool_a_wins_7d': 0, 'tool_b_wins_7d': 0,
                            'total_votes_prev_7d': 0, 'tool_a_wins_prev_7d': 0, 'tool_b_wins_prev_7d': 0,
                        }

            # Aggregate vote data
            cursor.execute("""
                SELECT
                    m.tool_a AS tool_a_id, m.tool_b AS tool_b_id, v.category,
                    COUNT(*) AS total_votes,
                    SUM(CASE WHEN v.winner_tool = m.tool_a THEN 1 ELSE 0 END) AS tool_a_wins,
                    SUM(CASE WHEN v.winner_tool = m.tool_b THEN 1 ELSE 0 END) AS tool_b_wins,
                    SUM(CASE WHEN v.voted_at > NOW() - INTERVAL '7 days' THEN 1 ELSE 0 END) AS total_votes_7d,
                    SUM(CASE WHEN v.voted_at > NOW() - INTERVAL '7 days'
                                  AND v.winner_tool = m.tool_a THEN 1 ELSE 0 END) AS tool_a_wins_7d,
                    SUM(CASE WHEN v.voted_at > NOW() - INTERVAL '7 days'
                                  AND v.winner_tool = m.tool_b THEN 1 ELSE 0 END) AS tool_b_wins_7d,
                    SUM(CASE WHEN v.voted_at BETWEEN NOW() - INTERVAL '14 days'
                                  AND NOW() - INTERVAL '7 days' THEN 1 ELSE 0 END) AS total_votes_prev_7d,
                    SUM(CASE WHEN v.voted_at BETWEEN NOW() - INTERVAL '14 days'
                                  AND NOW() - INTERVAL '7 days'
                                  AND v.winner_tool = m.tool_a THEN 1 ELSE 0 END) AS tool_a_wins_prev_7d,
                    SUM(CASE WHEN v.voted_at BETWEEN NOW() - INTERVAL '14 days'
                                  AND NOW() - INTERVAL '7 days'
                                  AND v.winner_tool = m.tool_b THEN 1 ELSE 0 END) AS tool_b_wins_prev_7d
                FROM matchups m
                JOIN votes v ON v.matchup_id = m.matchup_id
                WHERE m.status = 'active' AND v.locked = TRUE
                GROUP BY m.tool_a, m.tool_b, v.category
            """)
            for row in cursor.fetchall():
                key = (row[0], row[1], row[2])
                if key in all_combos:
                    all_combos[key].update({
                        'total_votes': row[3], 'tool_a_wins': row[4], 'tool_b_wins': row[5],
                        'total_votes_7d': row[6], 'tool_a_wins_7d': row[7], 'tool_b_wins_7d': row[8],
                        'total_votes_prev_7d': row[9], 'tool_a_wins_prev_7d': row[10], 'tool_b_wins_prev_7d': row[11],
                    })

            # Upsert all combos
            pairs_updated = 0
            for (tid_a, tid_b, cat), d in all_combos.items():
                tv = d['total_votes']
                a_wr = round(d['tool_a_wins'] / tv, 4) if tv > 0 else None
                b_wr = round(d['tool_b_wins'] / tv, 4) if tv > 0 else None

                # Confidence
                if tv >= 100:
                    confidence = 'high'
                elif tv >= 30:
                    confidence = 'medium'
                else:
                    confidence = 'low'

                # Trends
                if d['has_pending']:
                    trend_a = 'new'
                    trend_b = 'new'
                else:
                    tv_7d = d['total_votes_7d']
                    tv_prev = d['total_votes_prev_7d']
                    # Tool A trend
                    if tv_7d < 5 or tv_prev < 5:
                        trend_a = 'stable'
                        trend_b = 'stable'
                    else:
                        a_wr_7d = d['tool_a_wins_7d'] / tv_7d if tv_7d > 0 else 0
                        a_wr_prev = d['tool_a_wins_prev_7d'] / tv_prev if tv_prev > 0 else 0
                        delta_a = a_wr_7d - a_wr_prev
                        if delta_a > 0.05:
                            trend_a = 'up'
                        elif delta_a < -0.05:
                            trend_a = 'down'
                        else:
                            trend_a = 'stable'
                        # Tool B trend is opposite
                        if delta_a < -0.05:
                            trend_b = 'up'
                        elif delta_a > 0.05:
                            trend_b = 'down'
                        else:
                            trend_b = 'stable'

                cursor.execute("""
                    INSERT INTO h2h_stats
                        (tool_a_id, tool_b_id, category, total_votes,
                         tool_a_wins, tool_b_wins, tool_a_win_rate, tool_b_win_rate,
                         total_votes_7d, tool_a_wins_7d, tool_b_wins_7d,
                         total_votes_prev_7d, tool_a_wins_prev_7d, tool_b_wins_prev_7d,
                         trend_tool_a, trend_tool_b, confidence, computed_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                    ON CONFLICT (tool_a_id, tool_b_id, category) DO UPDATE SET
                        total_votes = EXCLUDED.total_votes,
                        tool_a_wins = EXCLUDED.tool_a_wins,
                        tool_b_wins = EXCLUDED.tool_b_wins,
                        tool_a_win_rate = EXCLUDED.tool_a_win_rate,
                        tool_b_win_rate = EXCLUDED.tool_b_win_rate,
                        total_votes_7d = EXCLUDED.total_votes_7d,
                        tool_a_wins_7d = EXCLUDED.tool_a_wins_7d,
                        tool_b_wins_7d = EXCLUDED.tool_b_wins_7d,
                        total_votes_prev_7d = EXCLUDED.total_votes_prev_7d,
                        tool_a_wins_prev_7d = EXCLUDED.tool_a_wins_prev_7d,
                        tool_b_wins_prev_7d = EXCLUDED.tool_b_wins_prev_7d,
                        trend_tool_a = EXCLUDED.trend_tool_a,
                        trend_tool_b = EXCLUDED.trend_tool_b,
                        confidence = EXCLUDED.confidence,
                        computed_at = EXCLUDED.computed_at
                """, (tid_a, tid_b, cat, tv,
                      d['tool_a_wins'], d['tool_b_wins'], a_wr, b_wr,
                      d['total_votes_7d'], d['tool_a_wins_7d'], d['tool_b_wins_7d'],
                      d['total_votes_prev_7d'], d['tool_a_wins_prev_7d'], d['tool_b_wins_prev_7d'],
                      trend_a, trend_b, confidence))
                pairs_updated += 1

            connection.commit()

        duration_ms = int((_time.time() - start) * 1000)
        _leaderboard_cache.invalidate_all()
        log_cron_complete(log_id, details={'pairs_updated': pairs_updated, 'duration_ms': duration_ms})
        return {'pairs_updated': pairs_updated, 'duration_ms': duration_ms}
    except Exception as e:
        try:
            connection.rollback()
        except Exception:
            pass
        logger.error(f"Error recomputing h2h stats: {e}")
        log_cron_failure(log_id, str(e))
        return None
    finally:
        connection.close()


def get_h2h_matrix(category):
    """
    Get the full head-to-head matrix data for a category.

    Returns {
        'tools': [{'tool_id', 'name', 'slug', 'status'}, ...],
        'cells': [{'tool_a_id', 'tool_b_id', 'tool_a_win_rate', ...}, ...],
        'computed_at': str
    }
    """
    connection = get_connection()
    if not connection:
        return None
    try:
        with connection.cursor() as cursor:
            # Get tools ordered by slug
            cursor.execute("""
                SELECT tool_id, name, slug, status
                FROM AITool
                WHERE status IN ('active', 'pending')
                ORDER BY slug
            """)
            tools = []
            for row in cursor.fetchall():
                tools.append({
                    'tool_id': row[0], 'name': row[1],
                    'slug': row[2], 'status': row[3],
                })

            # Get h2h data for this category
            cursor.execute("""
                SELECT h.tool_a_id, h.tool_b_id,
                       h.tool_a_win_rate, h.tool_b_win_rate,
                       h.total_votes, h.confidence,
                       h.trend_tool_a, h.trend_tool_b,
                       h.computed_at,
                       ta.status AS status_a, tb.status AS status_b
                FROM h2h_stats h
                JOIN AITool ta ON h.tool_a_id = ta.tool_id
                JOIN AITool tb ON h.tool_b_id = tb.tool_id
                WHERE h.category = %s
                ORDER BY h.tool_a_id, h.tool_b_id
            """, (category,))

            cells = []
            computed_at = None
            for row in cursor.fetchall():
                cell = {
                    'tool_a_id': row[0], 'tool_b_id': row[1],
                    'tool_a_win_rate': float(row[2]) if row[2] is not None else None,
                    'tool_b_win_rate': float(row[3]) if row[3] is not None else None,
                    'total_votes': row[4], 'confidence': row[5],
                    'trend_tool_a': row[6], 'trend_tool_b': row[7],
                }
                if row[9] == 'pending' or row[10] == 'pending':
                    cell['pending'] = True
                if row[8] and computed_at is None:
                    computed_at = row[8].isoformat() if hasattr(row[8], 'isoformat') else str(row[8])
                cells.append(cell)

        return {
            'tools': tools,
            'cells': cells,
            'computed_at': computed_at,
        }
    except Exception as e:
        try:
            connection.rollback()
        except Exception:
            pass
        logger.error(f"Error getting h2h matrix: {e}")
        return None
    finally:
        connection.close()


def get_h2h_pair_detail(tool_a_id, tool_b_id):
    """
    Get detailed head-to-head data for a specific tool pair.

    Returns {
        'categories': [...],
        'recent_matchups': [...],
        'total_matchups': int
    }
    """
    connection = get_connection()
    if not connection:
        return None
    try:
        with connection.cursor() as cursor:
            # All 5 category rows
            cursor.execute("""
                SELECT category, tool_a_win_rate, tool_b_win_rate,
                       total_votes, confidence, trend_tool_a, trend_tool_b
                FROM h2h_stats
                WHERE tool_a_id = %s AND tool_b_id = %s
                ORDER BY category
            """, (tool_a_id, tool_b_id))
            categories = []
            for row in cursor.fetchall():
                categories.append({
                    'category': row[0],
                    'tool_a_win_rate': float(row[1]) if row[1] is not None else None,
                    'tool_b_win_rate': float(row[2]) if row[2] is not None else None,
                    'total_votes': row[3],
                    'confidence': row[4],
                    'trend_tool_a': row[5],
                    'trend_tool_b': row[6],
                })

            # Total matchups count
            cursor.execute("""
                SELECT COUNT(*) FROM matchups
                WHERE tool_a = %s AND tool_b = %s AND status = 'active'
            """, (tool_a_id, tool_b_id))
            total_matchups = cursor.fetchone()[0]

            # 5 most recent active matchups
            cursor.execute("""
                SELECT m.matchup_id, m.created_at,
                       (SELECT COUNT(*) FROM votes v WHERE v.matchup_id = m.matchup_id AND v.locked = TRUE) AS vote_count
                FROM matchups m
                WHERE m.tool_a = %s AND m.tool_b = %s AND m.status = 'active'
                ORDER BY m.created_at DESC
                LIMIT 5
            """, (tool_a_id, tool_b_id))
            recent_matchups = []
            for row in cursor.fetchall():
                recent_matchups.append({
                    'matchup_id': row[0],
                    'created_at': row[1].isoformat() if hasattr(row[1], 'isoformat') else str(row[1]),
                    'total_votes': row[2],
                })

        return {
            'categories': categories,
            'recent_matchups': recent_matchups,
            'total_matchups': total_matchups,
        }
    except Exception as e:
        try:
            connection.rollback()
        except Exception:
            pass
        logger.error(f"Error getting h2h pair detail: {e}")
        return None
    finally:
        connection.close()


# ============== Personal Voting History (Phase 2, Step 3) ==============

_user_stats_cache = _LeaderboardCache(ttl_seconds=300)


def recompute_user_vote_stats(user_id):
    """
    Recompute the user_vote_stats row for a single user.

    Called after vote submission and by cron for stale rows.
    Returns {'success': True} or None on error.
    """
    connection = get_connection()
    if not connection:
        return None
    try:
        with connection.cursor() as cursor:
            # 1. Totals
            cursor.execute("""
                SELECT COUNT(*), COUNT(DISTINCT matchup_id)
                FROM votes WHERE user_id = %s AND locked = TRUE
            """, (user_id,))
            total_votes, total_matchups = cursor.fetchone()

            # 2. Majority agreement
            # For each (matchup_id, category), find community majority winner,
            # then count how often this user's vote matches.
            cursor.execute("""
                WITH community AS (
                    SELECT matchup_id, category, winner_tool,
                           COUNT(*) AS cnt,
                           ROW_NUMBER() OVER (
                               PARTITION BY matchup_id, category
                               ORDER BY COUNT(*) DESC
                           ) AS rn
                    FROM votes
                    WHERE locked = TRUE
                    GROUP BY matchup_id, category, winner_tool
                ),
                majority AS (
                    SELECT matchup_id, category, winner_tool
                    FROM community WHERE rn = 1
                ),
                user_votes AS (
                    SELECT matchup_id, category, winner_tool
                    FROM votes
                    WHERE user_id = %s AND locked = TRUE
                )
                SELECT COUNT(*) FROM user_votes uv
                JOIN majority m ON uv.matchup_id = m.matchup_id
                    AND uv.category = m.category
                    AND uv.winner_tool = m.winner_tool
            """, (user_id,))
            majority_agreements = cursor.fetchone()[0]

            majority_rate = None
            if total_votes > 0:
                majority_rate = round(majority_agreements / total_votes, 4)

            # 3. Favorite tool
            cursor.execute("""
                SELECT winner_tool, COUNT(*) AS cnt
                FROM votes WHERE user_id = %s AND locked = TRUE
                GROUP BY winner_tool ORDER BY cnt DESC LIMIT 1
            """, (user_id,))
            fav_row = cursor.fetchone()
            favorite_tool_id = fav_row[0] if fav_row else None
            favorite_tool_count = fav_row[1] if fav_row else 0

            # 4. Category most voted
            cursor.execute("""
                SELECT category, COUNT(*) AS cnt
                FROM votes WHERE user_id = %s AND locked = TRUE
                GROUP BY category ORDER BY cnt DESC LIMIT 1
            """, (user_id,))
            cat_row = cursor.fetchone()
            category_most_voted = cat_row[0] if cat_row else None

            # 5. Streaks — get distinct vote dates
            cursor.execute("""
                SELECT DISTINCT DATE(voted_at) AS vote_date
                FROM votes WHERE user_id = %s AND locked = TRUE
                ORDER BY vote_date DESC
            """, (user_id,))
            dates = [r[0] for r in cursor.fetchall()]

            current_streak = 0
            longest_streak = 0
            if dates:
                from datetime import date as _date, timedelta as _td
                today = _date.today()
                # Current streak: starts if most recent vote is today or yesterday
                if dates[0] >= today - _td(days=1):
                    current_streak = 1
                    for i in range(1, len(dates)):
                        if dates[i] == dates[i - 1] - _td(days=1):
                            current_streak += 1
                        else:
                            break

                # Longest streak
                run = 1
                for i in range(1, len(dates)):
                    if dates[i] == dates[i - 1] - _td(days=1):
                        run += 1
                    else:
                        if run > longest_streak:
                            longest_streak = run
                        run = 1
                if run > longest_streak:
                    longest_streak = run

            # 6. Last voted
            cursor.execute("""
                SELECT MAX(voted_at) FROM votes
                WHERE user_id = %s AND locked = TRUE
            """, (user_id,))
            last_voted_at = cursor.fetchone()[0]

            # 7. Upsert
            cursor.execute("""
                INSERT INTO user_vote_stats (
                    user_id, total_votes_cast, total_matchups_voted,
                    majority_agreements, majority_agreement_rate,
                    favorite_tool_id, favorite_tool_vote_count,
                    category_most_voted, current_streak, longest_streak,
                    last_voted_at, computed_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (user_id) DO UPDATE SET
                    total_votes_cast = EXCLUDED.total_votes_cast,
                    total_matchups_voted = EXCLUDED.total_matchups_voted,
                    majority_agreements = EXCLUDED.majority_agreements,
                    majority_agreement_rate = EXCLUDED.majority_agreement_rate,
                    favorite_tool_id = EXCLUDED.favorite_tool_id,
                    favorite_tool_vote_count = EXCLUDED.favorite_tool_vote_count,
                    category_most_voted = EXCLUDED.category_most_voted,
                    current_streak = EXCLUDED.current_streak,
                    longest_streak = EXCLUDED.longest_streak,
                    last_voted_at = EXCLUDED.last_voted_at,
                    computed_at = CURRENT_TIMESTAMP
            """, (user_id, total_votes, total_matchups,
                  majority_agreements, majority_rate,
                  favorite_tool_id, favorite_tool_count,
                  category_most_voted, current_streak, longest_streak,
                  last_voted_at))
            connection.commit()

            # 8. Invalidate cache for this user
            _user_stats_cache._store.pop(('user_stats', user_id), None)

            return {'success': True}
    except Exception as e:
        try:
            connection.rollback()
        except Exception:
            pass
        logger.error(f"Error recomputing user vote stats for user {user_id}: {e}")
        return None
    finally:
        connection.close()


def get_user_vote_stats(user_id):
    """
    Get cached user vote stats with category and tool distributions.

    Returns full stats dict or None if no stats exist.
    """
    cached = _user_stats_cache.get(('user_stats', user_id))
    if cached is not None:
        data, age = cached
        data['cached'] = True
        data['cache_age_seconds'] = round(age, 1)
        return data

    connection = get_connection()
    if not connection:
        return None
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT uvs.total_votes_cast, uvs.total_matchups_voted,
                       uvs.majority_agreements, uvs.majority_agreement_rate,
                       uvs.favorite_tool_id, uvs.favorite_tool_vote_count,
                       uvs.category_most_voted, uvs.current_streak,
                       uvs.longest_streak, uvs.last_voted_at, uvs.computed_at,
                       t.name AS favorite_tool_name, t.slug AS favorite_tool_slug
                FROM user_vote_stats uvs
                LEFT JOIN AITool t ON uvs.favorite_tool_id = t.tool_id
                WHERE uvs.user_id = %s
            """, (user_id,))
            row = cursor.fetchone()
            if not row:
                return None

            stats = {
                'success': True,
                'total_votes_cast': row[0],
                'total_matchups_voted': row[1],
                'majority_agreements': row[2],
                'majority_agreement_rate': float(row[3]) if row[3] is not None else None,
                'favorite_tool': {
                    'tool_id': row[4],
                    'name': row[11],
                    'slug': row[12],
                    'vote_count': row[5],
                } if row[4] else None,
                'category_most_voted': row[6],
                'current_streak': row[7],
                'longest_streak': row[8],
                'last_voted_at': row[9].isoformat() if row[9] else None,
                'computed_at': row[10].isoformat() if row[10] else None,
                'cached': False,
            }

            # Category distribution
            cursor.execute("""
                SELECT category, COUNT(*) AS cnt
                FROM votes WHERE user_id = %s AND locked = TRUE
                GROUP BY category ORDER BY cnt DESC
            """, (user_id,))
            stats['category_distribution'] = [
                {'category': r[0], 'count': r[1]} for r in cursor.fetchall()
            ]

            # Tool distribution (tools the user voted FOR)
            cursor.execute("""
                SELECT t.name, t.slug, COUNT(*) AS cnt
                FROM votes v
                JOIN AITool t ON v.winner_tool = t.tool_id
                WHERE v.user_id = %s AND v.locked = TRUE
                GROUP BY t.name, t.slug ORDER BY cnt DESC
            """, (user_id,))
            stats['tool_distribution'] = [
                {'name': r[0], 'slug': r[1], 'count': r[2]} for r in cursor.fetchall()
            ]

            _user_stats_cache.set(('user_stats', user_id), stats)
            return stats
    except Exception as e:
        try:
            connection.rollback()
        except Exception:
            pass
        logger.error(f"Error getting user vote stats: {e}")
        return None
    finally:
        connection.close()


def get_user_vote_history(user_id, page=1, limit=20, tool_slug=None,
                          category=None, alignment=None, sort='newest'):
    """
    Get paginated, filterable vote history for a user.

    Returns {'votes': [...], 'total': int, 'page': int, 'pages': int} or None.
    """
    connection = get_connection()
    if not connection:
        return None
    try:
        with connection.cursor() as cursor:
            # Build WHERE clauses
            conditions = ["v.user_id = %s", "v.locked = TRUE"]
            params = [user_id]

            if category:
                conditions.append("v.category = %s")
                params.append(category)

            if tool_slug:
                # Filter by tool involved in the matchup (either side)
                conditions.append("""
                    (ta.slug = %s OR tb.slug = %s)
                """)
                params.extend([tool_slug, tool_slug])

            where_clause = " AND ".join(conditions)
            order = "v.voted_at DESC" if sort == 'newest' else "v.voted_at ASC"

            # Main query
            base_query = """
                FROM votes v
                JOIN matchups m ON v.matchup_id = m.matchup_id
                JOIN AITool ta ON m.tool_a = ta.tool_id
                JOIN AITool tb ON m.tool_b = tb.tool_id
                JOIN AITool tw ON v.winner_tool = tw.tool_id
                WHERE {where}
            """.format(where=where_clause)

            # Get total count (before alignment filter)
            cursor.execute(f"SELECT COUNT(*) {base_query}", params)
            total_before_alignment = cursor.fetchone()[0]

            # Fetch all matching votes (we need them for alignment annotation)
            offset = (page - 1) * limit
            cursor.execute(f"""
                SELECT v.vote_id, v.matchup_id, v.category, v.winner_tool,
                       v.voted_at,
                       m.tool_a, m.tool_b,
                       ta.name AS tool_a_name, ta.slug AS tool_a_slug,
                       tb.name AS tool_b_name, tb.slug AS tool_b_slug,
                       tw.name AS winner_name, tw.slug AS winner_slug
                {base_query}
                ORDER BY {order}
            """, params)
            all_votes = cursor.fetchall()

            # Get community majority for each (matchup_id, category) in the result set
            matchup_cats = set()
            for row in all_votes:
                matchup_cats.add((row[1], row[2]))  # matchup_id, category

            community_majority = {}
            if matchup_cats:
                # Batch fetch
                for mc_id, mc_cat in matchup_cats:
                    cursor.execute("""
                        SELECT winner_tool, COUNT(*) AS cnt
                        FROM votes
                        WHERE matchup_id = %s AND category = %s AND locked = TRUE
                        GROUP BY winner_tool ORDER BY cnt DESC LIMIT 1
                    """, (mc_id, mc_cat))
                    maj_row = cursor.fetchone()
                    if maj_row:
                        community_majority[(mc_id, mc_cat)] = maj_row[0]

            # Also get community vote counts per (matchup_id, category)
            community_counts = {}
            if matchup_cats:
                for mc_id, mc_cat in matchup_cats:
                    cursor.execute("""
                        SELECT winner_tool, COUNT(*) AS cnt
                        FROM votes
                        WHERE matchup_id = %s AND category = %s AND locked = TRUE
                        GROUP BY winner_tool
                    """, (mc_id, mc_cat))
                    counts = {}
                    total_community = 0
                    for r in cursor.fetchall():
                        counts[r[0]] = r[1]
                        total_community += r[1]
                    community_counts[(mc_id, mc_cat)] = {
                        'counts': counts, 'total': total_community
                    }

            # Annotate votes
            annotated = []
            for row in all_votes:
                matchup_id = row[1]
                cat = row[2]
                winner_tool = row[3]

                maj_winner = community_majority.get((matchup_id, cat))
                user_aligned = (winner_tool == maj_winner) if maj_winner else True

                cc = community_counts.get((matchup_id, cat), {'counts': {}, 'total': 0})
                tool_a_id = row[5]
                tool_b_id = row[6]
                tool_a_votes = cc['counts'].get(tool_a_id, 0)
                tool_b_votes = cc['counts'].get(tool_b_id, 0)
                total_cv = cc['total']
                tool_a_pct = round(tool_a_votes / total_cv * 100, 1) if total_cv > 0 else 0
                tool_b_pct = round(tool_b_votes / total_cv * 100, 1) if total_cv > 0 else 0

                annotated.append({
                    'vote_id': row[0],
                    'matchup_id': matchup_id,
                    'category': cat,
                    'winner_tool_id': winner_tool,
                    'winner_name': row[11],
                    'winner_slug': row[12],
                    'voted_at': row[4].isoformat() if row[4] else None,
                    'tool_a': {'id': tool_a_id, 'name': row[7], 'slug': row[8]},
                    'tool_b': {'id': tool_b_id, 'name': row[9], 'slug': row[10]},
                    'community': {
                        'tool_a_votes': tool_a_votes,
                        'tool_b_votes': tool_b_votes,
                        'tool_a_pct': tool_a_pct,
                        'tool_b_pct': tool_b_pct,
                        'total_votes': total_cv,
                    },
                    'user_aligned': user_aligned,
                })

            # Apply alignment filter if specified
            if alignment == 'majority':
                annotated = [v for v in annotated if v['user_aligned']]
            elif alignment == 'minority':
                annotated = [v for v in annotated if not v['user_aligned']]

            total = len(annotated) if alignment else total_before_alignment
            # Paginate
            if alignment:
                page_votes = annotated[(page - 1) * limit: page * limit]
            else:
                page_votes = annotated[offset: offset + limit]

            pages = max(1, (total + limit - 1) // limit)

            return {
                'success': True,
                'votes': page_votes,
                'total': total,
                'page': page,
                'pages': pages,
            }
    except Exception as e:
        try:
            connection.rollback()
        except Exception:
            pass
        logger.error(f"Error getting user vote history: {e}")
        return None
    finally:
        connection.close()


def recompute_stale_user_stats():
    """
    Cron function: find users with votes newer than their last computation
    and recompute their stats.

    Returns {'users_updated': int, 'duration_ms': int} or None on error.
    """
    start = _time.time()
    log_id = log_cron_start('recompute_user_vote_stats')

    connection = get_connection()
    if not connection:
        log_cron_failure(log_id, 'Could not get database connection')
        return None
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT DISTINCT v.user_id FROM votes v
                LEFT JOIN user_vote_stats uvs ON v.user_id = uvs.user_id
                WHERE uvs.computed_at IS NULL OR v.voted_at > uvs.computed_at
            """)
            stale_users = [r[0] for r in cursor.fetchall()]
        connection.close()

        updated = 0
        for uid in stale_users:
            result = recompute_user_vote_stats(uid)
            if result:
                updated += 1

        duration_ms = round((_time.time() - start) * 1000)
        log_cron_complete(log_id, details={
            'users_updated': updated,
            'duration_ms': duration_ms,
        })
        return {'users_updated': updated, 'duration_ms': duration_ms}
    except Exception as e:
        try:
            connection.rollback()
        except Exception:
            pass
        log_cron_failure(log_id, str(e))
        logger.error(f"Error recomputing stale user stats: {e}")
        return None
    finally:
        try:
            connection.close()
        except Exception:
            pass


def get_active_matchups(page=1, per_page=12):
    """Get paginated active matchups with tool info"""
    connection = get_connection()
    if not connection:
        return [], 0
    try:
        offset = (page - 1) * per_page
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM matchups WHERE status = 'active'")
            total = cursor.fetchone()[0]

            cursor.execute("""
                SELECT m.matchup_id, m.post_a_id, m.post_b_id,
                       m.tool_a, m.tool_b, m.status, m.created_at,
                       ta.name, ta.slug,
                       tb.name, tb.slug,
                       pa.Title, pb.Title,
                       pa.Category
                FROM matchups m
                JOIN AITool ta ON m.tool_a = ta.tool_id
                JOIN AITool tb ON m.tool_b = tb.tool_id
                JOIN Post pa ON m.post_a_id = pa.postid
                JOIN Post pb ON m.post_b_id = pb.postid
                WHERE m.status = 'active'
                ORDER BY m.created_at DESC
                LIMIT %s OFFSET %s
            """, (per_page, offset))
            matchups = [
                {
                    'matchup_id': row[0],
                    'post_a_id': row[1], 'post_b_id': row[2],
                    'tool_a': row[3], 'tool_b': row[4],
                    'status': row[5], 'created_at': row[6],
                    'tool_a_name': row[7], 'tool_a_slug': row[8],
                    'tool_b_name': row[9], 'tool_b_slug': row[10],
                    'title_a': row[11], 'title_b': row[12],
                    'category': row[13]
                }
                for row in cursor.fetchall()
            ]
            return matchups, total
    finally:
        connection.close()


# ============================================
# Engagement Bootstrap Functions
# ============================================

_featured_matchup_cache = _LeaderboardCache(ttl_seconds=600)  # 10-minute TTL


def get_featured_matchup():
    """
    Get a single featured matchup for the homepage widget.
    Priority: pinned > trending (most votes in 24h) > underserved (fewest total votes).
    Returns dict or None.
    """
    connection = get_connection()
    if not connection:
        return None
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT m.matchup_id, m.post_a_id, m.post_b_id,
                       m.pinned,
                       ta.name AS tool_a_name, tb.name AS tool_b_name,
                       ta.slug AS tool_a_slug, tb.slug AS tool_b_slug,
                       pa.Title AS title_a,
                       LEFT(REGEXP_REPLACE(pa.Content, '<[^>]+>', '', 'g'), 250) AS preview_a,
                       pb.Title AS title_b,
                       LEFT(REGEXP_REPLACE(pb.Content, '<[^>]+>', '', 'g'), 250) AS preview_b,
                       COALESCE(vc.cnt, 0) AS total_votes,
                       COALESCE(rc.cnt, 0) AS recent_votes
                FROM matchups m
                JOIN AITool ta ON m.tool_a = ta.tool_id
                JOIN AITool tb ON m.tool_b = tb.tool_id
                JOIN Post pa ON m.post_a_id = pa.postid
                JOIN Post pb ON m.post_b_id = pb.postid
                LEFT JOIN (
                    SELECT matchup_id, COUNT(*) AS cnt
                    FROM votes GROUP BY matchup_id
                ) vc ON vc.matchup_id = m.matchup_id
                LEFT JOIN (
                    SELECT matchup_id, COUNT(*) AS cnt
                    FROM votes
                    WHERE voted_at > CURRENT_TIMESTAMP - INTERVAL '24 hours'
                    GROUP BY matchup_id
                ) rc ON rc.matchup_id = m.matchup_id
                WHERE m.status = 'active'
                ORDER BY
                    m.pinned DESC NULLS LAST,
                    COALESCE(rc.cnt, 0) DESC,
                    COALESCE(vc.cnt, 0) ASC
                LIMIT 1
            """)
            row = cursor.fetchone()
            if not row:
                return None
            return {
                'matchup_id': row[0],
                'post_a_id': row[1], 'post_b_id': row[2],
                'pinned': row[3],
                'tool_a_name': row[4], 'tool_b_name': row[5],
                'tool_a_slug': row[6], 'tool_b_slug': row[7],
                'title_a': row[8], 'preview_a': row[9],
                'title_b': row[10], 'preview_b': row[11],
                'total_votes': row[12], 'recent_votes': row[13]
            }
    except Exception as e:
        logger.error(f"Error getting featured matchup: {e}")
        return None
    finally:
        connection.close()


def get_free_votes_this_week(user_id):
    """Count distinct matchups a user has voted on this ISO week (Mon-Sun)."""
    connection = get_connection()
    if not connection:
        return 0
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT COUNT(DISTINCT matchup_id)
                FROM votes
                WHERE user_id = %s
                  AND voted_at >= date_trunc('week', CURRENT_TIMESTAMP)
            """, (user_id,))
            return cursor.fetchone()[0]
    except Exception:
        return 0
    finally:
        connection.close()


def toggle_matchup_pin(matchup_id):
    """Toggle the pinned flag on a matchup. Returns new pinned value or None."""
    connection = get_connection()
    if not connection:
        return None
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                UPDATE matchups SET pinned = NOT COALESCE(pinned, FALSE)
                WHERE matchup_id = %s
                RETURNING pinned
            """, (matchup_id,))
            row = cursor.fetchone()
            connection.commit()
            if row:
                _featured_matchup_cache.invalidate_all()
                return row[0]
            return None
    except Exception as e:
        connection.rollback()
        logger.error(f"Error toggling matchup pin: {e}")
        return None
    finally:
        connection.close()


def update_matchup_status(matchup_id, status):
    """Update matchup status. Returns True on success."""
    valid_statuses = ('active', 'closed', 'draft')
    if status not in valid_statuses:
        return False
    connection = get_connection()
    if not connection:
        return False
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                UPDATE matchups SET status = %s WHERE matchup_id = %s
            """, (status, matchup_id))
            connection.commit()
            return cursor.rowcount > 0
    except Exception as e:
        connection.rollback()
        logger.error(f"Error updating matchup status: {e}")
        return False
    finally:
        connection.close()


def get_matchup_overview_stats():
    """Get overview stats for admin matchup management."""
    connection = get_connection()
    if not connection:
        return {}
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT
                    COUNT(*) FILTER (WHERE status = 'active') AS active_count,
                    COUNT(*) FILTER (WHERE status = 'closed') AS closed_count,
                    COUNT(*) FILTER (WHERE pinned = TRUE AND status = 'active') AS pinned_count,
                    COUNT(*) AS total_count
                FROM matchups
            """)
            row = cursor.fetchone()
            cursor.execute("SELECT COUNT(*) FROM votes")
            total_votes = cursor.fetchone()[0]
            cursor.execute("""
                SELECT COUNT(*) FROM votes
                WHERE voted_at >= CURRENT_DATE
            """)
            votes_today = cursor.fetchone()[0]
            return {
                'active': row[0], 'closed': row[1],
                'pinned': row[2], 'total': row[3],
                'total_votes': total_votes,
                'votes_today': votes_today
            }
    except Exception as e:
        logger.error(f"Error getting matchup stats: {e}")
        return {}
    finally:
        connection.close()


def track_event(event_name, user_id=None, session_id=None, matchup_id=None, properties=None):
    """Insert an analytics event into the analytics_events table."""
    connection = get_connection()
    if not connection:
        return False
    try:
        import json as _json
        with connection.cursor() as cursor:
            cursor.execute("""
                INSERT INTO analytics_events (event_name, user_id, session_id, matchup_id, properties)
                VALUES (%s, %s, %s, %s, %s)
            """, (event_name, user_id, session_id, matchup_id,
                  _json.dumps(properties) if properties else '{}'))
            connection.commit()
            return True
    except Exception as e:
        try:
            connection.rollback()
        except Exception:
            pass
        logger.error(f"Error tracking event '{event_name}': {e}")
        return False
    finally:
        connection.close()


# ============================================
# In-App Notification Functions
# ============================================

def create_notification(user_id, notification_type, title, message=None, link=None, tool_id=None, post_id=None):
    """
    Create a new in-app notification for a user
    
    Args:
        user_id: Target user's ID
        notification_type: Type of notification ('new_post', 'comment_reply', 'system', etc.)
        title: Notification title (max 255 chars)
        message: Optional detailed message
        link: Optional URL to navigate to when clicked
        tool_id: Optional related AI tool ID
        post_id: Optional related post ID
    
    Returns:
        notification_id if successful, None otherwise
    """
    connection = get_connection()
    if not connection:
        return None
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                INSERT INTO Notification (user_id, type, title, message, link, tool_id, post_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING notification_id
            """, (user_id, notification_type, title[:255], message, link, tool_id, post_id))
            connection.commit()
            return cursor.fetchone()[0]
    except Exception as e:
        logger.error(f"Error creating notification: {e}")
        return None
    finally:
        connection.close()


def create_bulk_notifications(user_ids, notification_type, title, message=None, link=None, tool_id=None, post_id=None):
    """
    Create notifications for multiple users at once (e.g., for new post notifications)
    
    Args:
        user_ids: List of user IDs to notify
        Other args same as create_notification
    
    Returns:
        Number of notifications created
    """
    if not user_ids:
        return 0
    
    connection = get_connection()
    if not connection:
        return 0
    try:
        with connection.cursor() as cursor:
            # Use executemany for bulk insert
            data = [(uid, notification_type, title[:255], message, link, tool_id, post_id) for uid in user_ids]
            cursor.executemany("""
                INSERT INTO Notification (user_id, type, title, message, link, tool_id, post_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, data)
            connection.commit()
            return len(user_ids)
    except Exception as e:
        logger.error(f"Error creating bulk notifications: {e}")
        return 0
    finally:
        connection.close()


def get_user_notifications(user_id, limit=50, unread_only=False):
    """
    Get notifications for a user
    
    Args:
        user_id: User's ID
        limit: Maximum number of notifications to return
        unread_only: If True, only return unread notifications
    
    Returns:
        List of notification dictionaries
    """
    connection = get_connection()
    if not connection:
        return []
    try:
        with connection.cursor() as cursor:
            query = """
                SELECT n.notification_id, n.type, n.title, n.message, n.link, 
                       n.tool_id, n.post_id, n.is_read, n.created_at,
                       t.name as tool_name, t.slug as tool_slug
                FROM Notification n
                LEFT JOIN AITool t ON n.tool_id = t.tool_id
                WHERE n.user_id = %s
            """
            if unread_only:
                query += " AND n.is_read = FALSE"
            query += " ORDER BY n.created_at DESC LIMIT %s"
            
            cursor.execute(query, (user_id, limit))
            return [
                {
                    'id': row[0],
                    'type': row[1],
                    'title': row[2],
                    'message': row[3],
                    'link': row[4],
                    'tool_id': row[5],
                    'post_id': row[6],
                    'is_read': row[7],
                    'created_at': row[8],
                    'tool_name': row[9],
                    'tool_slug': row[10]
                }
                for row in cursor.fetchall()
            ]
    finally:
        connection.close()


def get_unread_notification_count(user_id):
    """Get count of unread notifications for a user"""
    connection = get_connection()
    if not connection:
        return 0
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM Notification WHERE user_id = %s AND is_read = FALSE",
                (user_id,)
            )
            return cursor.fetchone()[0]
    finally:
        connection.close()


def mark_notification_read(notification_id, user_id):
    """Mark a single notification as read (verifies ownership)"""
    connection = get_connection()
    if not connection:
        return False
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                UPDATE Notification 
                SET is_read = TRUE 
                WHERE notification_id = %s AND user_id = %s
            """, (notification_id, user_id))
            connection.commit()
            return cursor.rowcount > 0
    finally:
        connection.close()


def mark_all_notifications_read(user_id):
    """Mark all notifications as read for a user"""
    connection = get_connection()
    if not connection:
        return 0
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE Notification SET is_read = TRUE WHERE user_id = %s AND is_read = FALSE",
                (user_id,)
            )
            connection.commit()
            return cursor.rowcount
    finally:
        connection.close()


def delete_old_notifications(days=30):
    """Delete notifications older than specified days"""
    connection = get_connection()
    if not connection:
        return 0
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                DELETE FROM Notification 
                WHERE created_at < NOW() - INTERVAL '%s days'
            """, (days,))
            connection.commit()
            return cursor.rowcount
    finally:
        connection.close()


def get_subscriber_user_ids_by_tool(tool_id):
    """Get user IDs (not emails) of all users subscribed to a tool (for in-app notifications)"""
    connection = get_connection()
    if not connection:
        return []
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT u.user_id
                FROM Users u
                JOIN Subscription s ON u.user_id = s.user_id
                WHERE s.tool_id = %s AND u.is_active = TRUE
            """, (tool_id,))
            return [row[0] for row in cursor.fetchall()]
    finally:
        connection.close()


def get_premium_subscriber_emails_by_tool(tool_id):
    """
    Get email addresses of premium users subscribed to a tool (for email notifications)
    
    Only returns emails of users who:
    - Have an active/trialing premium subscription
    - Are subscribed to the specified AI tool
    - Have email_notifications enabled
    - Have an active account
    
    Args:
        tool_id: The AI tool's ID
        
    Returns:
        List of email addresses
    """
    connection = get_connection()
    if not connection:
        return []
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT DISTINCT u.email
                FROM Users u
                JOIN Subscription s ON u.user_id = s.user_id
                JOIN UserSubscription us ON u.user_id = us.user_id
                JOIN SubscriptionPlan sp ON us.plan_id = sp.plan_id
                WHERE s.tool_id = %s 
                AND u.is_active = TRUE
                AND u.email_notifications = TRUE
                AND us.status IN ('active', 'trialing')
                AND sp.name != 'free'
                AND (us.current_period_end IS NULL OR us.current_period_end > NOW())
            """, (tool_id,))
            return [row[0] for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f"Error getting premium subscriber emails: {e}")
        return []
    finally:
        connection.close()


def get_premium_subscriber_user_ids_by_tool(tool_id):
    """
    Get user IDs of premium users subscribed to a tool (for in-app notifications)
    
    Only returns user IDs of users who:
    - Have an active/trialing premium subscription
    - Are subscribed to the specified AI tool
    - Have an active account
    
    Args:
        tool_id: The AI tool's ID
        
    Returns:
        List of user IDs
    """
    connection = get_connection()
    if not connection:
        return []
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT DISTINCT u.user_id
                FROM Users u
                JOIN Subscription s ON u.user_id = s.user_id
                JOIN UserSubscription us ON u.user_id = us.user_id
                JOIN SubscriptionPlan sp ON us.plan_id = sp.plan_id
                WHERE s.tool_id = %s 
                AND u.is_active = TRUE
                AND us.status IN ('active', 'trialing')
                AND sp.name != 'free'
                AND (us.current_period_end IS NULL OR us.current_period_end > NOW())
            """, (tool_id,))
            return [row[0] for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f"Error getting premium subscriber user IDs: {e}")
        return []
    finally:
        connection.close()


# ============== Premium Subscription Functions ==============

def get_all_subscription_plans():
    """Get all available subscription plans"""
    connection = get_connection()
    if not connection:
        return []
    try:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("""
                SELECT plan_id, name, display_name, description, price_cents, 
                       interval, interval_count, stripe_price_id,
                       features, is_active, created_at
                FROM SubscriptionPlan 
                WHERE is_active = TRUE
                ORDER BY price_cents ASC
            """)
            return cursor.fetchall()
    except Exception:
        return []
    finally:
        connection.close()


def get_plan_by_id(plan_id):
    """Get a subscription plan by ID"""
    connection = get_connection()
    if not connection:
        return None
    try:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("""
                SELECT plan_id, name, display_name, description, price_cents, 
                       interval, interval_count, stripe_price_id,
                       features, is_active, created_at
                FROM SubscriptionPlan 
                WHERE plan_id = %s
            """, (plan_id,))
            return cursor.fetchone()
    except Exception:
        return None
    finally:
        connection.close()


def get_subscription_plan_by_name(name):
    """Get a subscription plan by name"""
    connection = get_connection()
    if not connection:
        return None
    try:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("""
                SELECT plan_id, name, display_name, description, price_cents, 
                       interval, interval_count, stripe_price_id,
                       features, is_active, created_at
                FROM SubscriptionPlan 
                WHERE name = %s
            """, (name,))
            return cursor.fetchone()
    except Exception:
        return None
    finally:
        connection.close()


def get_plan_by_stripe_price_id(price_id):
    """Get a subscription plan by Stripe price ID"""
    connection = get_connection()
    if not connection:
        return None
    try:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("""
                SELECT plan_id, name, display_name, description, price_cents, 
                       interval, interval_count, stripe_price_id,
                       features, is_active, created_at
                FROM SubscriptionPlan 
                WHERE stripe_price_id = %s
            """, (price_id,))
            return cursor.fetchone()
    except Exception:
        return None
    finally:
        connection.close()


def update_plan_stripe_price_id(plan_id, stripe_price_id):
    """Update Stripe price ID for a plan"""
    connection = get_connection()
    if not connection:
        return False
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                UPDATE SubscriptionPlan 
                SET stripe_price_id = %s 
                WHERE plan_id = %s
            """, (stripe_price_id, plan_id))
            connection.commit()
            return True
    except Exception:
        return False
    finally:
        connection.close()


def get_user_subscription(user_id):
    """Get a user's current subscription details"""
    connection = get_connection()
    if not connection:
        return None
    try:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("""
                SELECT us.*, sp.name as plan_name, sp.display_name,
                       sp.price_cents, sp.interval, sp.features
                FROM UserSubscription us
                JOIN SubscriptionPlan sp ON us.plan_id = sp.plan_id
                WHERE us.user_id = %s
            """, (user_id,))
            return cursor.fetchone()
    except Exception as e:
        print(f"Error getting user subscription: {e}")
        return None
    finally:
        connection.close()


def get_user_subscription_by_stripe_id(stripe_subscription_id):
    """Get user subscription by Stripe subscription ID"""
    connection = get_connection()
    if not connection:
        return None
    try:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("""
                SELECT us.*, sp.name as plan_name, sp.display_name
                FROM UserSubscription us
                JOIN SubscriptionPlan sp ON us.plan_id = sp.plan_id
                WHERE us.stripe_subscription_id = %s
            """, (stripe_subscription_id,))
            return cursor.fetchone()
    except Exception:
        return None
    finally:
        connection.close()


def upsert_user_subscription(user_id, plan_id, stripe_customer_id, stripe_subscription_id,
                              status, current_period_start, current_period_end, trial_end=None):
    """Create or update a user's subscription"""
    connection = get_connection()
    if not connection:
        return False
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                INSERT INTO UserSubscription (
                    user_id, plan_id, stripe_customer_id, stripe_subscription_id,
                    status, current_period_start, current_period_end, trial_end
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (user_id) DO UPDATE SET
                    plan_id = EXCLUDED.plan_id,
                    stripe_customer_id = EXCLUDED.stripe_customer_id,
                    stripe_subscription_id = EXCLUDED.stripe_subscription_id,
                    status = EXCLUDED.status,
                    current_period_start = EXCLUDED.current_period_start,
                    current_period_end = EXCLUDED.current_period_end,
                    trial_end = EXCLUDED.trial_end,
                    updated_at = NOW()
            """, (user_id, plan_id, stripe_customer_id, stripe_subscription_id,
                  status, current_period_start, current_period_end, trial_end))
            connection.commit()
            return True
    except Exception as e:
        logger.error(f"Error upserting subscription: {e}")
        return False
    finally:
        connection.close()


def update_user_subscription(user_id, plan_id=None, status=None, 
                              current_period_start=None, current_period_end=None,
                              cancel_at_period_end=None):
    """Update specific fields of a user's subscription"""
    connection = get_connection()
    if not connection:
        return False
    try:
        with connection.cursor() as cursor:
            updates = []
            params = []
            
            if plan_id is not None:
                updates.append("plan_id = %s")
                params.append(plan_id)
            if status is not None:
                updates.append("status = %s")
                params.append(status)
            if current_period_start is not None:
                updates.append("current_period_start = %s")
                params.append(current_period_start)
            if current_period_end is not None:
                updates.append("current_period_end = %s")
                params.append(current_period_end)
            if cancel_at_period_end is not None:
                updates.append("cancel_at_period_end = %s")
                params.append(cancel_at_period_end)
            
            if not updates:
                return False
                
            updates.append("updated_at = NOW()")
            params.append(user_id)
            
            cursor.execute(f"""
                UPDATE UserSubscription 
                SET {', '.join(updates)}
                WHERE user_id = %s
            """, params)
            connection.commit()
            return True
    except Exception:
        return False
    finally:
        connection.close()


def update_user_subscription_status(user_id, status, canceled_at=None):
    """Update subscription status and optionally set canceled_at"""
    connection = get_connection()
    if not connection:
        return False
    try:
        with connection.cursor() as cursor:
            if canceled_at:
                cursor.execute("""
                    UPDATE UserSubscription 
                    SET status = %s, canceled_at = %s, updated_at = NOW()
                    WHERE user_id = %s
                """, (status, canceled_at, user_id))
            else:
                cursor.execute("""
                    UPDATE UserSubscription 
                    SET status = %s, updated_at = NOW()
                    WHERE user_id = %s
                """, (status, user_id))
            connection.commit()
            return True
    except Exception:
        return False
    finally:
        connection.close()


def update_user_subscription_cancel_at_period_end(user_id, cancel_at_period_end):
    """Update cancel_at_period_end flag for a subscription"""
    connection = get_connection()
    if not connection:
        return False
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                UPDATE UserSubscription 
                SET cancel_at_period_end = %s, updated_at = NOW()
                WHERE user_id = %s
            """, (cancel_at_period_end, user_id))
            connection.commit()
            return True
    except Exception as e:
        print(f"Error updating cancel_at_period_end: {e}")
        return False
    finally:
        connection.close()


def is_user_premium(user_id):
    """Check if a user has an active premium subscription"""
    connection = get_connection()
    if not connection:
        return False
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT EXISTS(
                    SELECT 1 FROM UserSubscription us
                    JOIN SubscriptionPlan sp ON us.plan_id = sp.plan_id
                    WHERE us.user_id = %s 
                    AND us.status IN ('active', 'trialing')
                    AND sp.name != 'free'
                    AND (us.current_period_end IS NULL OR us.current_period_end > NOW())
                )
            """, (user_id,))
            return cursor.fetchone()[0]
    except Exception:
        return False
    finally:
        connection.close()


def update_user_stripe_customer_id(user_id, stripe_customer_id):
    """Update the Stripe customer ID for a user"""
    connection = get_connection()
    if not connection:
        return False
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                UPDATE Users 
                SET stripe_customer_id = %s 
                WHERE user_id = %s
            """, (stripe_customer_id, user_id))
            connection.commit()
            return True
    except Exception:
        return False
    finally:
        connection.close()


def get_user_by_stripe_customer_id(stripe_customer_id):
    """Get a user by their Stripe customer ID"""
    connection = get_connection()
    if not connection:
        return None
    try:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("""
                SELECT user_id, username, email, stripe_customer_id
                FROM Users 
                WHERE stripe_customer_id = %s
            """, (stripe_customer_id,))
            return cursor.fetchone()
    except Exception:
        return None
    finally:
        connection.close()


def record_payment(user_id, stripe_payment_intent_id, stripe_invoice_id,
                   amount_cents, currency, status, description=None, receipt_url=None):
    """Record a payment in payment history"""
    connection = get_connection()
    if not connection:
        return False
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                INSERT INTO PaymentHistory (
                    user_id, stripe_payment_intent_id, stripe_invoice_id,
                    amount_cents, currency, status, description, receipt_url
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (user_id, stripe_payment_intent_id, stripe_invoice_id,
                  amount_cents, currency, status, description, receipt_url))
            connection.commit()
            return True
    except Exception as e:
        logger.error(f"Error recording payment: {e}")
        return False
    finally:
        connection.close()


def get_user_payment_history(user_id, limit=20):
    """Get a user's payment history"""
    connection = get_connection()
    if not connection:
        return []
    try:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("""
                SELECT payment_id, stripe_payment_intent_id, stripe_invoice_id,
                       amount_cents, currency, status, description, receipt_url, created_at
                FROM PaymentHistory
                WHERE user_id = %s
                ORDER BY created_at DESC
                LIMIT %s
            """, (user_id, limit))
            return cursor.fetchall()
    except Exception:
        return []
    finally:
        connection.close()


# ============== Free Post View Tracking ==============

def get_user_free_post_views_this_month(user_id):
    """Get count of free post views for current month"""
    connection = get_connection()
    if not connection:
        return 0
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT COUNT(*) FROM FreePostView
                WHERE user_id = %s 
                AND viewed_at >= date_trunc('month', CURRENT_DATE)
            """, (user_id,))
            return cursor.fetchone()[0]
    except Exception:
        return 0
    finally:
        connection.close()


def record_free_post_view(user_id, post_id):
    """Record a free post view (for tracking limits)"""
    from datetime import datetime
    connection = get_connection()
    if not connection:
        return False
    try:
        month_year = datetime.now().strftime('%Y-%m')
        with connection.cursor() as cursor:
            # Check if already viewed this post this month
            cursor.execute("""
                SELECT 1 FROM FreePostView 
                WHERE user_id = %s AND post_id = %s AND month_year = %s
            """, (user_id, post_id, month_year))
            
            if cursor.fetchone():
                return True  # Already recorded
            
            # Insert new view record
            cursor.execute("""
                INSERT INTO FreePostView (user_id, post_id, month_year)
                VALUES (%s, %s, %s)
            """, (user_id, post_id, month_year))
            connection.commit()
            return True
    except Exception as e:
        logger.error(f"Error recording free post view: {e}")
        return False
    finally:
        connection.close()


def has_user_viewed_post(user_id, post_id):
    """Check if user has already viewed this post (for free tier)"""
    connection = get_connection()
    if not connection:
        return False
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT EXISTS(
                    SELECT 1 FROM FreePostView
                    WHERE user_id = %s AND post_id = %s
                )
            """, (user_id, post_id))
            return cursor.fetchone()[0]
    except Exception:
        return False
    finally:
        connection.close()


def can_user_view_post(user_id, post_id, post_created_at, free_post_limit=5, delay_days=14):
    """
    Check if user can view a post based on subscription status.
    
    Premium users: Can view all posts
    Free users: Can view posts older than delay_days OR within their monthly limit
    
    Returns: (can_view: bool, reason: str)
    """
    from datetime import datetime, timedelta
    
    # Check if user is premium
    if is_user_premium(user_id):
        return True, "premium"
    
    # Check if post is old enough for free tier
    delay_threshold = datetime.now() - timedelta(days=delay_days)
    if post_created_at < delay_threshold:
        return True, "post_old_enough"
    
    # Check if user already viewed this post
    if has_user_viewed_post(user_id, post_id):
        return True, "already_viewed"
    
    # Check free post limit
    views_this_month = get_user_free_post_views_this_month(user_id)
    if views_this_month < free_post_limit:
        return True, "within_limit"
    
    return False, "limit_reached"


def get_premium_stats():
    """Get premium subscription statistics for admin dashboard"""
    connection = get_connection()
    if not connection:
        return {}
    try:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            # Total premium users
            cursor.execute("""
                SELECT COUNT(*) as total_premium
                FROM UserSubscription us
                JOIN SubscriptionPlan sp ON us.plan_id = sp.plan_id
                WHERE us.status IN ('active', 'trialing')
                AND sp.name != 'free'
            """)
            total = cursor.fetchone()['total_premium']
            
            # Monthly vs Annual breakdown
            cursor.execute("""
                SELECT sp.name, COUNT(*) as count
                FROM UserSubscription us
                JOIN SubscriptionPlan sp ON us.plan_id = sp.plan_id
                WHERE us.status IN ('active', 'trialing')
                GROUP BY sp.name
            """)
            by_plan = {row['name']: row['count'] for row in cursor.fetchall()}
            
            # Revenue this month
            cursor.execute("""
                SELECT COALESCE(SUM(amount_cents), 0) as revenue
                FROM PaymentHistory
                WHERE status = 'succeeded'
                AND created_at >= date_trunc('month', CURRENT_DATE)
            """)
            monthly_revenue = cursor.fetchone()['revenue'] / 100
            
            return {
                'total_premium': total,
                'by_plan': by_plan,
                'monthly_revenue': monthly_revenue
            }
    except Exception:
        return {}
    finally:
        connection.close()


# ============== Cron Job Logging ==============

def log_cron_start(job_type):
    """Log the start of a cron job and return the log ID"""
    connection = get_connection()
    if not connection:
        return None
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                INSERT INTO cron_logs (job_type, status, started_at)
                VALUES (%s, 'started', CURRENT_TIMESTAMP)
                RETURNING log_id
            """, (job_type,))
            log_id = cursor.fetchone()[0]
            connection.commit()
            return log_id
    except Exception as e:
        logger.error(f"Failed to log cron start: {e}")
        return None
    finally:
        connection.close()


def log_cron_complete(log_id, posts_generated=0, spam_deleted=0, notifications_deleted=0, details=None):
    """Log the completion of a cron job"""
    connection = get_connection()
    if not connection or not log_id:
        return
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                UPDATE cron_logs
                SET status = 'completed',
                    completed_at = CURRENT_TIMESTAMP,
                    duration_seconds = EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - started_at))::INTEGER,
                    posts_generated = %s,
                    spam_deleted = %s,
                    notifications_deleted = %s,
                    details = %s
                WHERE log_id = %s
            """, (posts_generated, spam_deleted, notifications_deleted, 
                  psycopg2.extras.Json(details) if details else None, log_id))
            connection.commit()
    except Exception as e:
        logger.error(f"Failed to log cron completion: {e}")
    finally:
        connection.close()


def log_cron_failure(log_id, error_message):
    """Log the failure of a cron job"""
    connection = get_connection()
    if not connection or not log_id:
        return
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                UPDATE cron_logs
                SET status = 'failed',
                    completed_at = CURRENT_TIMESTAMP,
                    duration_seconds = EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - started_at))::INTEGER,
                    error_message = %s
                WHERE log_id = %s
            """, (error_message, log_id))
            connection.commit()
    except Exception as e:
        logger.error(f"Failed to log cron failure: {e}")
    finally:
        connection.close()


def get_cron_logs(limit=50, job_type=None):
    """Get recent cron job execution logs"""
    connection = get_connection()
    if not connection:
        return []
    try:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            if job_type:
                cursor.execute("""
                    SELECT log_id, job_type, status, started_at, completed_at,
                           duration_seconds, posts_generated, spam_deleted,
                           notifications_deleted, error_message, details
                    FROM cron_logs
                    WHERE job_type = %s
                    ORDER BY started_at DESC
                    LIMIT %s
                """, (job_type, limit))
            else:
                cursor.execute("""
                    SELECT log_id, job_type, status, started_at, completed_at,
                           duration_seconds, posts_generated, spam_deleted,
                           notifications_deleted, error_message, details
                    FROM cron_logs
                    ORDER BY started_at DESC
                    LIMIT %s
                """, (limit,))
            return cursor.fetchall()
    except Exception as e:
        logger.error(f"Failed to get cron logs: {e}")
        return []
    finally:
        connection.close()


def get_cron_stats():
    """Get statistics about cron job executions"""
    connection = get_connection()
    if not connection:
        return {}
    try:
        stats = {}
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            # Last successful execution per job type
            cursor.execute("""
                SELECT DISTINCT ON (job_type) 
                    job_type, started_at, completed_at, duration_seconds,
                    posts_generated, spam_deleted, notifications_deleted
                FROM cron_logs
                WHERE status = 'completed'
                ORDER BY job_type, started_at DESC
            """)
            last_runs = cursor.fetchall()
            stats['last_successful_runs'] = {row['job_type']: row for row in last_runs}
            
            # Count executions in last 7 days
            cursor.execute("""
                SELECT job_type, status, COUNT(*) as count
                FROM cron_logs
                WHERE started_at >= CURRENT_DATE - INTERVAL '7 days'
                GROUP BY job_type, status
                ORDER BY job_type, status
            """)
            recent_counts = cursor.fetchall()
            stats['recent_executions'] = recent_counts
            
            # Total executions
            cursor.execute("SELECT COUNT(*) as total FROM cron_logs")
            stats['total_executions'] = cursor.fetchone()['total']
            
            # Failed executions count
            cursor.execute("SELECT COUNT(*) as failed FROM cron_logs WHERE status = 'failed'")
            stats['failed_count'] = cursor.fetchone()['failed']
            
        return stats
    except Exception as e:
        logger.error(f"Failed to get cron stats: {e}")
        return {}
    finally:
        connection.close()


# ============== Password Reset Functions ==============

def create_password_reset_token(user_id, token, expires_at):
    """Create a password reset token"""
    connection = get_connection()
    if not connection:
        return False
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                INSERT INTO password_reset_tokens (user_id, token, expires_at)
                VALUES (%s, %s, %s)
            """, (user_id, token, expires_at))
            connection.commit()
            return True
    except Exception as e:
        logger.error(f"Failed to create password reset token: {e}")
        return False
    finally:
        connection.close()


def verify_password_reset_token(token):
    """Verify password reset token and return user_id if valid"""
    connection = get_connection()
    if not connection:
        return None
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT user_id, expires_at
                FROM password_reset_tokens
                WHERE token = %s
            """, (token,))
            result = cursor.fetchone()

            if result:
                user_id, expires_at = result
                # Check if token is expired
                from datetime import datetime
                if datetime.now() < expires_at:
                    return user_id
            return None
    except Exception as e:
        logger.error(f"Failed to verify password reset token: {e}")
        return None
    finally:
        connection.close()


def delete_password_reset_token(token):
    """Delete a password reset token after use"""
    connection = get_connection()
    if not connection:
        return False
    try:
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM password_reset_tokens WHERE token = %s", (token,))
            connection.commit()
            return True
    except Exception as e:
        logger.error(f"Failed to delete password reset token: {e}")
        return False
    finally:
        connection.close()


def update_user_password(user_id, password_hash):
    """Update user's password"""
    connection = get_connection()
    if not connection:
        return False
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                UPDATE Users
                SET password_hash = %s
                WHERE user_id = %s
            """, (password_hash, user_id))
            connection.commit()
            return True
    except Exception as e:
        logger.error(f"Failed to update user password: {e}")
        return False
    finally:
        connection.close()

