"""
Database Module
Handles all database connections and operations
"""
import os
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
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


# ============== AI Comparison Functions ==============

def get_posts_by_category_for_comparison(category):
    """Get posts from different AI tools for the same category"""
    connection = get_connection()
    if not connection:
        return []
    try:
        with connection.cursor() as cursor:
            # Get one post per tool for the given category
            cursor.execute("""
                SELECT DISTINCT ON (p.tool_id)
                    p.postid, p.Title, p.Content, p.Category, p.CreatedAt, p.tool_id,
                    t.name as tool_name, t.slug as tool_slug
                FROM Post p
                LEFT JOIN AITool t ON p.tool_id = t.tool_id
                WHERE p.Category = %s
                ORDER BY p.tool_id, p.CreatedAt DESC
            """, (category,))
            return [
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
    finally:
        connection.close()


def get_random_comparison_posts(limit=3):
    """Get random posts from different AI tools for comparison"""
    connection = get_connection()
    if not connection:
        return []
    try:
        with connection.cursor() as cursor:
            # Get one random recent post per tool
            cursor.execute("""
                SELECT DISTINCT ON (p.tool_id)
                    p.postid, p.Title, p.Content, p.Category, p.CreatedAt, p.tool_id,
                    t.name as tool_name, t.slug as tool_slug
                FROM Post p
                LEFT JOIN AITool t ON p.tool_id = t.tool_id
                WHERE p.CreatedAt >= CURRENT_DATE - INTERVAL '30 days'
                ORDER BY p.tool_id, RANDOM()
                LIMIT %s
            """, (limit,))
            return [
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
    finally:
        connection.close()


def create_comparison(topic, post_ids):
    """Create a new comparison with selected posts"""
    connection = get_connection()
    if not connection:
        return None
    try:
        with connection.cursor() as cursor:
            # Create comparison
            cursor.execute(
                "INSERT INTO Comparison (topic) VALUES (%s) RETURNING comparison_id",
                (topic,)
            )
            comparison_id = cursor.fetchone()[0]
            
            # Add posts to comparison
            for post_id in post_ids:
                cursor.execute(
                    "INSERT INTO ComparisonPost (comparison_id, post_id) VALUES (%s, %s)",
                    (comparison_id, post_id)
                )
            
            connection.commit()
            return comparison_id
    except Exception as e:
        print(f"Error creating comparison: {e}")
        return None
    finally:
        connection.close()


def get_comparison_by_id(comparison_id):
    """Get comparison details with posts"""
    connection = get_connection()
    if not connection:
        return None
    try:
        with connection.cursor() as cursor:
            # Get comparison info
            cursor.execute(
                "SELECT comparison_id, topic, created_at FROM Comparison WHERE comparison_id = %s",
                (comparison_id,)
            )
            row = cursor.fetchone()
            if not row:
                return None
            
            comparison = {
                'id': row[0],
                'topic': row[1],
                'created_at': row[2],
                'posts': []
            }
            
            # Get posts in comparison
            cursor.execute("""
                SELECT p.postid, p.Title, p.Content, p.Category, p.CreatedAt, p.tool_id,
                       t.name as tool_name, t.slug as tool_slug
                FROM ComparisonPost cp
                JOIN Post p ON cp.post_id = p.postid
                LEFT JOIN AITool t ON p.tool_id = t.tool_id
                WHERE cp.comparison_id = %s
            """, (comparison_id,))
            
            for row in cursor.fetchall():
                comparison['posts'].append({
                    'id': row[0],
                    'title': row[1],
                    'content': row[2],
                    'category': row[3],
                    'created_at': row[4],
                    'tool_id': row[5],
                    'tool_name': row[6],
                    'tool_slug': row[7]
                })
            
            return comparison
    finally:
        connection.close()


def add_vote(comparison_id, user_id, post_id):
    """Add or update a vote for a comparison"""
    connection = get_connection()
    if not connection:
        return False
    try:
        with connection.cursor() as cursor:
            # Upsert vote
            cursor.execute("""
                INSERT INTO Vote (comparison_id, user_id, post_id)
                VALUES (%s, %s, %s)
                ON CONFLICT (comparison_id, user_id) 
                DO UPDATE SET post_id = %s, created_at = CURRENT_TIMESTAMP
            """, (comparison_id, user_id, post_id, post_id))
            connection.commit()
            return True
    except Exception as e:
        print(f"Error adding vote: {e}")
        return False
    finally:
        connection.close()


def get_vote_counts(comparison_id):
    """Get vote counts for each post in a comparison"""
    connection = get_connection()
    if not connection:
        return {}
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT post_id, COUNT(*) as votes
                FROM Vote
                WHERE comparison_id = %s
                GROUP BY post_id
            """, (comparison_id,))
            return {row[0]: row[1] for row in cursor.fetchall()}
    finally:
        connection.close()


def get_user_vote(comparison_id, user_id):
    """Get the user's vote for a comparison"""
    connection = get_connection()
    if not connection:
        return None
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT post_id FROM Vote WHERE comparison_id = %s AND user_id = %s",
                (comparison_id, user_id)
            )
            row = cursor.fetchone()
            return row[0] if row else None
    finally:
        connection.close()


def get_recent_comparisons(limit=10):
    """Get recent comparisons"""
    connection = get_connection()
    if not connection:
        return []
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT c.comparison_id, c.topic, c.created_at, COUNT(cp.id) as post_count
                FROM Comparison c
                LEFT JOIN ComparisonPost cp ON c.comparison_id = cp.comparison_id
                GROUP BY c.comparison_id
                ORDER BY c.created_at DESC
                LIMIT %s
            """, (limit,))
            return [
                {
                    'id': row[0],
                    'topic': row[1],
                    'created_at': row[2],
                    'post_count': row[3]
                }
                for row in cursor.fetchall()
            ]
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
