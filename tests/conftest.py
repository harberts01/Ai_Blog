"""
Test fixtures for Compare & Vote feature testing.

Uses monkeypatching to mock database.get_connection() so tests run against
a test database with per-test transaction rollback. This ensures tests
never affect the production database and don't interfere with each other.

Requires TEST_DATABASE_URL environment variable or falls back to
individual DB env vars with DB_NAME=ai_blog_test.
"""
import os
import pytest
import psycopg2


def get_test_connection():
    """Create a connection to the test database"""
    database_url = os.environ.get('TEST_DATABASE_URL')

    if database_url:
        if database_url.startswith('postgres://'):
            database_url = database_url.replace('postgres://', 'postgresql://', 1)
        return psycopg2.connect(database_url)

    # Fall back to individual env vars with test database name
    return psycopg2.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        port=os.environ.get('DB_PORT', '5432'),
        database=os.environ.get('TEST_DB_NAME', 'ai_blog'),
        user=os.environ.get('DB_USER', 'postgres'),
        password=os.environ.get('DB_PASSWORD', ''),
    )


@pytest.fixture(scope='session')
def db_schema():
    """
    Session-scoped: set up the test database schema once.
    Reads schema.sql and the matchups migration, executes them.
    """
    conn = get_test_connection()
    conn.autocommit = True
    try:
        with conn.cursor() as cursor:
            # Read and execute the base schema
            schema_path = os.path.join(os.path.dirname(__file__), '..', 'schema.sql')
            with open(schema_path, 'r', encoding='utf-8') as f:
                cursor.execute(f.read())

            # Execute migrations in order (those that add tables/functions we need)
            migrations_dir = os.path.join(os.path.dirname(__file__), '..', 'migrations')
            migration_files = [
                '002_add_premium_subscriptions.sql',
                '003a_insert_plans.sql',
                '003d_timestamp_trigger.sql',
                '006_add_matchups_votes.sql',
                '007_add_vote_events.sql',
                '008_add_tool_stats.sql',
                '009_add_h2h_stats.sql',
                '010_add_user_vote_stats.sql',
            ]
            for mf in migration_files:
                path = os.path.join(migrations_dir, mf)
                if os.path.exists(path):
                    with open(path, 'r', encoding='utf-8') as f:
                        cursor.execute(f.read())

        yield conn
    finally:
        conn.close()


@pytest.fixture(scope='session')
def seed_data(db_schema):
    """
    Session-scoped: insert seed data and return known IDs.
    Uses the connection from db_schema which has autocommit=True.
    """
    conn = db_schema
    ids = {}
    with conn.cursor() as cursor:
        # Ensure tools exist (schema.sql inserts them via ON CONFLICT DO NOTHING)
        cursor.execute("SELECT tool_id, slug FROM AITool ORDER BY tool_id")
        for row in cursor.fetchall():
            ids[f'tool_{row[1]}_id'] = row[0]

        # Create test users
        cursor.execute("""
            INSERT INTO Users (email, password_hash, username)
            VALUES ('premium@test.com', 'hash123', 'PremiumUser')
            ON CONFLICT (email) DO UPDATE SET username = EXCLUDED.username
            RETURNING user_id
        """)
        ids['user_premium_id'] = cursor.fetchone()[0]

        cursor.execute("""
            INSERT INTO Users (email, password_hash, username)
            VALUES ('free@test.com', 'hash456', 'FreeUser')
            ON CONFLICT (email) DO UPDATE SET username = EXCLUDED.username
            RETURNING user_id
        """)
        ids['user_free_id'] = cursor.fetchone()[0]

        # Ensure a premium plan exists, then give premium user a subscription
        cursor.execute("""
            INSERT INTO SubscriptionPlan (name, display_name, description, price_cents, interval)
            VALUES ('premium_monthly', 'Premium Monthly', 'Premium plan', 999, 'month')
            ON CONFLICT (name) DO NOTHING
        """)
        cursor.execute("SELECT plan_id FROM SubscriptionPlan WHERE name = 'premium_monthly' LIMIT 1")
        plan_row = cursor.fetchone()
        if plan_row:
            premium_plan_id = plan_row[0]
            cursor.execute("""
                INSERT INTO UserSubscription (user_id, plan_id, status, current_period_end)
                VALUES (%s, %s, 'active', CURRENT_TIMESTAMP + INTERVAL '30 days')
                ON CONFLICT (user_id) DO UPDATE SET
                    plan_id = EXCLUDED.plan_id,
                    status = 'active',
                    current_period_end = CURRENT_TIMESTAMP + INTERVAL '30 days'
            """, (ids['user_premium_id'], premium_plan_id))

        # Create test posts from different tools
        for slug in ['chatgpt', 'claude', 'gemini', 'llama', 'grok']:
            tool_id = ids.get(f'tool_{slug}_id')
            if tool_id:
                cursor.execute("""
                    INSERT INTO Post (Title, Content, Category, tool_id)
                    VALUES (%s, %s, 'Technology', %s)
                    ON CONFLICT DO NOTHING
                    RETURNING postid
                """, (f'Test Post by {slug}', f'Content from {slug}', tool_id))
                row = cursor.fetchone()
                if row:
                    ids[f'post_{slug}_id'] = row[0]

        # If posts already existed, fetch them
        if 'post_chatgpt_id' not in ids:
            cursor.execute("""
                SELECT p.postid, t.slug FROM Post p
                JOIN AITool t ON p.tool_id = t.tool_id
                WHERE t.slug IN ('chatgpt', 'claude', 'gemini', 'llama', 'grok')
                ORDER BY p.postid
            """)
            for row in cursor.fetchall():
                key = f'post_{row[1]}_id'
                if key not in ids:
                    ids[key] = row[0]

        # Create a test prompt
        cursor.execute("""
            INSERT INTO prompts (title, content)
            VALUES ('Test Prompt', 'Write about technology')
            RETURNING prompt_id
        """)
        ids['prompt_id'] = cursor.fetchone()[0]

    return ids


class ConnectionProxy:
    """
    Wraps a psycopg2 connection with savepoint-based commit/rollback.

    Database functions call commit() on success and rollback() on error.
    This proxy translates those into savepoint operations so that:
    - commit() preserves changes within the test transaction
    - rollback() recovers from errors without losing prior work
    - close() is a no-op (the real connection stays open for the test)
    """

    def __init__(self, real_conn):
        object.__setattr__(self, '_real_conn', real_conn)
        object.__setattr__(self, '_sp_id', 0)
        # Create initial savepoint
        with real_conn.cursor() as cur:
            cur.execute("SAVEPOINT proxy_sp_0")

    def close(self):
        pass

    def commit(self):
        rc = object.__getattribute__(self, '_real_conn')
        sp_id = object.__getattribute__(self, '_sp_id')
        next_id = sp_id + 1
        object.__setattr__(self, '_sp_id', next_id)
        with rc.cursor() as cur:
            cur.execute(f"RELEASE SAVEPOINT proxy_sp_{sp_id}")
            cur.execute(f"SAVEPOINT proxy_sp_{next_id}")

    def rollback(self):
        rc = object.__getattribute__(self, '_real_conn')
        sp_id = object.__getattribute__(self, '_sp_id')
        with rc.cursor() as cur:
            cur.execute(f"ROLLBACK TO SAVEPOINT proxy_sp_{sp_id}")

    def __getattr__(self, name):
        return getattr(object.__getattribute__(self, '_real_conn'), name)

    def __setattr__(self, name, value):
        if name in ('_real_conn', '_sp_id'):
            object.__setattr__(self, name, value)
        else:
            setattr(object.__getattribute__(self, '_real_conn'), name, value)


@pytest.fixture()
def db_conn(db_schema, monkeypatch):
    """
    Per-test fixture: provides a connection wrapped in a transaction
    that gets rolled back after each test. Also monkeypatches
    database.get_connection so that all database functions use this
    test connection instead of creating their own.
    """
    conn = get_test_connection()
    conn.autocommit = False

    # Wrap in proxy with savepoint-based commit/rollback
    proxy = ConnectionProxy(conn)

    import database
    monkeypatch.setattr(database, 'get_connection', lambda: proxy)

    yield conn

    # Roll back all changes from this test
    try:
        conn.rollback()
    except Exception:
        pass
    finally:
        conn.close()
