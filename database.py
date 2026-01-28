"""
Database Module
Handles all database connections and operations
"""
import psycopg2
from psycopg2.extras import RealDictCursor
from config import Config


def get_connection():
    """Create and return a database connection"""
    try:
        conn = psycopg2.connect(
            host=Config.DB_HOST,
            port=Config.DB_PORT,
            database=Config.DB_NAME,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD
        )
        return conn
    except psycopg2.Error as e:
        print(f'Database connection failed: {e}')
        return None


# Global connection for backward compatibility
conn = get_connection()

if conn:
    print('Database connection established.')
else:
    print('Warning: Database connection could not be established.')


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


def insert_post(title, content, category, tool_id=None):
    """Insert a new blog post"""
    connection = get_connection()
    if not connection:
        return False
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO Post (Title, Content, Category, tool_id) VALUES (%s, %s, %s, %s)",
                (title, content, category, tool_id)
            )
            connection.commit()
            return True
    except Exception as e:
        print(f"Error inserting post: {e}")
        return False
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
                "SELECT user_id, email, password_hash, username, is_active FROM Users WHERE user_id = %s",
                (user_id,)
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
    """Get all comments for a post"""
    connection = get_connection()
    if not connection:
        return []
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT commentid, content, CreatedAt FROM Comment WHERE postid = %s ORDER BY CreatedAt DESC",
                (post_id,)
            )
            return [
                {'id': row[0], 'content': row[1], 'created_at': row[2]}
                for row in cursor.fetchall()
            ]
    finally:
        connection.close()


def insert_comment(post_id, content):
    """Insert a new comment"""
    connection = get_connection()
    if not connection:
        return False
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO Comment (postid, content) VALUES (%s, %s)",
                (post_id, content)
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
