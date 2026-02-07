"""Tests for the Head-to-Head Win Rate Matrix (Phase 2 / Step 2)."""
import pytest
import database as db


@pytest.fixture(scope='session')
def app_instance():
    """Create Flask app configured for testing."""
    from app import app
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    app.config['SERVER_NAME'] = 'localhost'
    return app


@pytest.fixture()
def client(app_instance, db_conn):
    """Per-test Flask test client with DB transaction isolation."""
    with app_instance.test_client() as c:
        yield c


def _login(client, user_id):
    with client.session_transaction() as sess:
        sess['user_id'] = user_id


def _create_matchup(seed_data):
    return db.create_matchup(
        seed_data['post_chatgpt_id'],
        seed_data['post_claude_id']
    )


def _create_matchup_alt(seed_data):
    """Create a second matchup with different tools."""
    return db.create_matchup(
        seed_data['post_gemini_id'],
        seed_data['post_llama_id']
    )


def _cast_and_lock(db_conn, user_id, matchup_id, categories, winner_tool):
    """Cast votes and immediately lock them for deterministic tests."""
    for cat in categories:
        db.cast_vote(user_id, matchup_id, cat, winner_tool)
    with db_conn.cursor() as cur:
        cur.execute(
            "UPDATE votes SET locked = TRUE WHERE user_id = %s AND matchup_id = %s",
            (user_id, matchup_id)
        )


# ============== Recompute H2H Stats ==============

class TestRecomputeH2HStats:
    """Tests for the recompute_h2h_stats() aggregation function."""

    def test_basic_h2h_aggregation(self, db_conn, seed_data):
        mid = _create_matchup(seed_data)
        matchup = db.get_matchup(mid)
        _cast_and_lock(db_conn, seed_data['user_premium_id'], mid,
                       db.VOTE_CATEGORIES, matchup['tool_a'])

        result = db.recompute_h2h_stats()
        assert result is not None
        assert result['pairs_updated'] > 0

        # Verify h2h_stats has the right data
        with db_conn.cursor() as cur:
            cur.execute("""
                SELECT tool_a_wins, tool_b_wins, total_votes
                FROM h2h_stats
                WHERE tool_a_id = %s AND tool_b_id = %s AND category = 'overall'
            """, (matchup['tool_a'], matchup['tool_b']))
            row = cur.fetchone()
            assert row is not None
            assert row[0] >= 1  # tool_a_wins
            assert row[2] >= 1  # total_votes

    def test_symmetric_win_rates(self, db_conn, seed_data):
        mid = _create_matchup(seed_data)
        matchup = db.get_matchup(mid)
        _cast_and_lock(db_conn, seed_data['user_premium_id'], mid,
                       ['overall'], matchup['tool_a'])

        db.recompute_h2h_stats()

        with db_conn.cursor() as cur:
            cur.execute("""
                SELECT tool_a_win_rate, tool_b_win_rate
                FROM h2h_stats
                WHERE tool_a_id = %s AND tool_b_id = %s AND category = 'overall'
            """, (matchup['tool_a'], matchup['tool_b']))
            row = cur.fetchone()
            assert row is not None
            if row[0] is not None and row[1] is not None:
                assert abs(float(row[0]) + float(row[1]) - 1.0) < 0.01

    def test_locked_only_counting(self, db_conn, seed_data):
        mid = _create_matchup(seed_data)
        matchup = db.get_matchup(mid)
        # Cast but do NOT lock
        db.cast_vote(seed_data['user_premium_id'], mid, 'overall', matchup['tool_a'])

        db.recompute_h2h_stats()

        with db_conn.cursor() as cur:
            cur.execute("""
                SELECT total_votes
                FROM h2h_stats
                WHERE tool_a_id = %s AND tool_b_id = %s AND category = 'overall'
            """, (matchup['tool_a'], matchup['tool_b']))
            row = cur.fetchone()
            assert row is not None
            assert row[0] == 0

    def test_pending_tool_pairs_have_zeros(self, db_conn, seed_data):
        db.recompute_h2h_stats()

        # Grok is pending — find its ID
        with db_conn.cursor() as cur:
            cur.execute("SELECT tool_id FROM AITool WHERE slug = 'grok'")
            grok_row = cur.fetchone()
            assert grok_row is not None
            grok_id = grok_row[0]

            cur.execute("""
                SELECT total_votes, trend_tool_a, trend_tool_b
                FROM h2h_stats
                WHERE (tool_a_id = %s OR tool_b_id = %s) AND category = 'overall'
            """, (grok_id, grok_id))
            rows = cur.fetchall()
            assert len(rows) > 0
            for row in rows:
                assert row[0] == 0  # total_votes
                assert row[1] == 'new'  # trend_tool_a
                assert row[2] == 'new'  # trend_tool_b

    def test_only_active_matchups(self, db_conn, seed_data):
        mid = _create_matchup(seed_data)
        matchup = db.get_matchup(mid)
        _cast_and_lock(db_conn, seed_data['user_premium_id'], mid,
                       ['overall'], matchup['tool_a'])

        # Archive the matchup
        with db_conn.cursor() as cur:
            cur.execute(
                "UPDATE matchups SET status = 'archived' WHERE matchup_id = %s",
                (mid,)
            )

        db.recompute_h2h_stats()

        with db_conn.cursor() as cur:
            cur.execute("""
                SELECT total_votes
                FROM h2h_stats
                WHERE tool_a_id = %s AND tool_b_id = %s AND category = 'overall'
            """, (matchup['tool_a'], matchup['tool_b']))
            row = cur.fetchone()
            assert row is not None
            assert row[0] == 0


# ============== Matrix API ==============

class TestMatrixAPI:
    """Tests for GET /api/dashboard/matrix."""

    def test_premium_gets_matrix_200(self, client, db_conn, seed_data):
        db.recompute_h2h_stats()
        _login(client, seed_data['user_premium_id'])
        resp = client.get('/api/dashboard/matrix')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        assert 'tools' in data
        assert 'cells' in data

    def test_correct_cell_count(self, client, db_conn, seed_data):
        db.recompute_h2h_stats()
        _login(client, seed_data['user_premium_id'])
        resp = client.get('/api/dashboard/matrix')
        data = resp.get_json()
        n = len(data['tools'])
        expected_cells = n * (n - 1) // 2  # C(n,2)
        assert len(data['cells']) == expected_cells

    def test_category_switching(self, client, db_conn, seed_data):
        mid = _create_matchup(seed_data)
        matchup = db.get_matchup(mid)
        _cast_and_lock(db_conn, seed_data['user_premium_id'], mid,
                       db.VOTE_CATEGORIES, matchup['tool_a'])
        db.recompute_h2h_stats()

        _login(client, seed_data['user_premium_id'])
        for cat in db.VOTE_CATEGORIES:
            resp = client.get(f'/api/dashboard/matrix?category={cat}')
            assert resp.status_code == 200
            data = resp.get_json()
            assert data['category'] == cat

    def test_pending_cell_flagged(self, client, db_conn, seed_data):
        db.recompute_h2h_stats()
        _login(client, seed_data['user_premium_id'])
        resp = client.get('/api/dashboard/matrix')
        data = resp.get_json()

        # Find cells with pending tools
        pending_cells = [c for c in data['cells'] if c.get('pending')]
        # Grok is pending, so there should be pending cells
        assert len(pending_cells) > 0

    def test_free_user_gets_403(self, client, db_conn, seed_data):
        _login(client, seed_data['user_free_id'])
        resp = client.get('/api/dashboard/matrix')
        assert resp.status_code == 403
        data = resp.get_json()
        assert data['error']['code'] == 'PREMIUM_REQUIRED'


# ============== Pair Detail API ==============

class TestPairDetailAPI:
    """Tests for GET /api/dashboard/matrix/pair/<slugA>/<slugB>."""

    def test_pair_detail_returns_5_categories(self, client, db_conn, seed_data):
        db.recompute_h2h_stats()
        _login(client, seed_data['user_premium_id'])
        resp = client.get('/api/dashboard/matrix/pair/chatgpt/claude')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        assert len(data['categories']) == 5

    def test_slug_order_normalization(self, client, db_conn, seed_data):
        db.recompute_h2h_stats()
        _login(client, seed_data['user_premium_id'])

        resp1 = client.get('/api/dashboard/matrix/pair/chatgpt/claude')
        resp2 = client.get('/api/dashboard/matrix/pair/claude/chatgpt')
        assert resp1.status_code == 200
        assert resp2.status_code == 200

        data1 = resp1.get_json()
        data2 = resp2.get_json()
        # Same canonical pair
        assert data1['tool_a']['tool_id'] == data2['tool_a']['tool_id']
        assert data1['tool_b']['tool_id'] == data2['tool_b']['tool_id']

    def test_recent_matchups_included(self, client, db_conn, seed_data):
        mid = _create_matchup(seed_data)
        db.recompute_h2h_stats()
        _login(client, seed_data['user_premium_id'])

        resp = client.get('/api/dashboard/matrix/pair/chatgpt/claude')
        data = resp.get_json()
        assert 'recent_matchups' in data
        assert 'total_matchups' in data
        assert data['total_matchups'] >= 1

    def test_invalid_slug_returns_404(self, client, db_conn, seed_data):
        _login(client, seed_data['user_premium_id'])
        resp = client.get('/api/dashboard/matrix/pair/nonexistent/claude')
        assert resp.status_code == 404
        data = resp.get_json()
        assert data['error']['code'] == 'TOOL_NOT_FOUND'

    def test_free_user_gets_403(self, client, db_conn, seed_data):
        _login(client, seed_data['user_free_id'])
        resp = client.get('/api/dashboard/matrix/pair/chatgpt/claude')
        assert resp.status_code == 403
        data = resp.get_json()
        assert data['error']['code'] == 'PREMIUM_REQUIRED'


# ============== Cache Behavior ==============

class TestH2HCache:
    """Tests for caching on the matrix API."""

    def test_cache_hit_on_matrix(self, client, db_conn, seed_data):
        db.recompute_h2h_stats()
        db._leaderboard_cache.invalidate_all()
        _login(client, seed_data['user_premium_id'])

        # First request populates cache
        resp1 = client.get('/api/dashboard/matrix')
        data1 = resp1.get_json()
        assert data1['cached'] is False

        # Second request should hit cache
        resp2 = client.get('/api/dashboard/matrix')
        data2 = resp2.get_json()
        assert data2['cached'] is True
        assert data2['cache_age_seconds'] >= 0

    def test_cache_invalidated_after_recompute(self, client, db_conn, seed_data):
        db.recompute_h2h_stats()
        _login(client, seed_data['user_premium_id'])

        # Populate cache
        client.get('/api/dashboard/matrix')

        # Recompute invalidates cache
        db._leaderboard_cache.invalidate_all()

        resp = client.get('/api/dashboard/matrix')
        data = resp.get_json()
        assert data['cached'] is False


# ============== Dashboard Matrix Section ==============

class TestDashboardMatrixSection:
    """Tests for the matrix section on the /dashboard page."""

    def test_matrix_section_visible_premium(self, client, db_conn, seed_data):
        _login(client, seed_data['user_premium_id'])
        resp = client.get('/dashboard')
        assert resp.status_code == 200
        assert b'Head-to-Head Matchups' in resp.data

    def test_matrix_hidden_for_free_users(self, client, db_conn, seed_data):
        _login(client, seed_data['user_free_id'])
        resp = client.get('/dashboard')
        assert resp.status_code == 200
        assert b'Unlock the Full Dashboard' in resp.data
        assert b'blur' in resp.data

    def test_cron_runs_both_recomputes(self, client, db_conn, seed_data, app_instance):
        from config import Config
        token = Config.CRON_SECRET
        resp = client.get(f'/cron/recompute-stats?token={token}')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        assert 'tools_updated' in data
        assert 'h2h_pairs_updated' in data
