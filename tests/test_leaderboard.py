"""Tests for the Global Leaderboard (Phase 2 / Step 1)."""
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


# ============== Recompute Aggregation ==============

class TestRecomputeToolStats:
    """Tests for the recompute_tool_stats() aggregation function."""

    def test_basic_aggregation(self, db_conn, seed_data):
        mid = _create_matchup(seed_data)
        matchup = db.get_matchup(mid)
        _cast_and_lock(db_conn, seed_data['user_premium_id'], mid,
                       db.VOTE_CATEGORIES, matchup['tool_a'])

        result = db.recompute_tool_stats()
        assert result is not None
        assert result['tools_updated'] > 0

        above, below = db.get_tool_stats_for_leaderboard('overall', min_votes=0)
        all_tools = above + below
        tool_a_stats = next((t for t in all_tools if t['tool_id'] == matchup['tool_a']), None)
        assert tool_a_stats is not None
        assert tool_a_stats['total_wins'] >= 1
        assert tool_a_stats['total_votes'] >= 1

    def test_locked_only_counting(self, db_conn, seed_data):
        mid = _create_matchup(seed_data)
        matchup = db.get_matchup(mid)
        # Cast but do NOT lock
        db.cast_vote(seed_data['user_premium_id'], mid, 'overall', matchup['tool_a'])

        result = db.recompute_tool_stats()
        assert result is not None

        above, below = db.get_tool_stats_for_leaderboard('overall', min_votes=0)
        all_tools = above + below
        tool_a_stats = next((t for t in all_tools if t['tool_id'] == matchup['tool_a']), None)
        assert tool_a_stats is not None
        assert tool_a_stats['total_votes'] == 0

    def test_active_matchup_only(self, db_conn, seed_data):
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

        result = db.recompute_tool_stats()
        above, below = db.get_tool_stats_for_leaderboard('overall', min_votes=0)
        all_tools = above + below
        tool_a_stats = next((t for t in all_tools if t['tool_id'] == matchup['tool_a']), None)
        assert tool_a_stats['total_votes'] == 0

    def test_pending_tools_get_zero_rows(self, db_conn, seed_data):
        db.recompute_tool_stats()
        above, below = db.get_tool_stats_for_leaderboard('overall', min_votes=0)
        all_tools = above + below
        # Grok is pending (set by migration 006)
        grok_stats = next((t for t in all_tools if t['slug'] == 'grok'), None)
        assert grok_stats is not None
        assert grok_stats['total_votes'] == 0

    def test_trend_stable_with_few_votes(self, db_conn, seed_data):
        mid = _create_matchup(seed_data)
        matchup = db.get_matchup(mid)
        _cast_and_lock(db_conn, seed_data['user_premium_id'], mid,
                       ['overall'], matchup['tool_a'])

        db.recompute_tool_stats()
        above, below = db.get_tool_stats_for_leaderboard('overall', min_votes=0)
        all_tools = above + below
        for tool in all_tools:
            assert tool['trend'] in ('up', 'down', 'stable')


# ============== Leaderboard API ==============

class TestLeaderboardAPI:
    """Tests for GET /api/dashboard/leaderboard."""

    def test_premium_gets_200(self, client, db_conn, seed_data):
        db.recompute_tool_stats()
        _login(client, seed_data['user_premium_id'])
        resp = client.get('/api/dashboard/leaderboard')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        assert 'leaderboard' in data
        assert 'below_threshold' in data

    def test_sorting_by_win_rate(self, client, db_conn, seed_data):
        mid = _create_matchup(seed_data)
        matchup = db.get_matchup(mid)
        _cast_and_lock(db_conn, seed_data['user_premium_id'], mid,
                       db.VOTE_CATEGORIES, matchup['tool_a'])
        db.recompute_tool_stats()

        _login(client, seed_data['user_premium_id'])
        resp = client.get('/api/dashboard/leaderboard?min_votes=0')
        data = resp.get_json()
        rates = [t['win_rate'] for t in data['leaderboard']]
        assert rates == sorted(rates, reverse=True)

    def test_category_switching(self, client, db_conn, seed_data):
        mid = _create_matchup(seed_data)
        matchup = db.get_matchup(mid)
        _cast_and_lock(db_conn, seed_data['user_premium_id'], mid,
                       db.VOTE_CATEGORIES, matchup['tool_a'])
        db.recompute_tool_stats()

        _login(client, seed_data['user_premium_id'])
        for cat in db.VOTE_CATEGORIES:
            resp = client.get(f'/api/dashboard/leaderboard?category={cat}&min_votes=0')
            assert resp.status_code == 200
            data = resp.get_json()
            assert data['category'] == cat

    def test_invalid_category_returns_400(self, client, db_conn, seed_data):
        _login(client, seed_data['user_premium_id'])
        resp = client.get('/api/dashboard/leaderboard?category=invalid_cat')
        assert resp.status_code == 400
        data = resp.get_json()
        assert data['error']['code'] == 'INVALID_CATEGORY'

    def test_min_votes_threshold(self, client, db_conn, seed_data):
        mid = _create_matchup(seed_data)
        matchup = db.get_matchup(mid)
        _cast_and_lock(db_conn, seed_data['user_premium_id'], mid,
                       ['overall'], matchup['tool_a'])
        db.recompute_tool_stats()

        _login(client, seed_data['user_premium_id'])
        resp = client.get('/api/dashboard/leaderboard?min_votes=100')
        data = resp.get_json()
        assert len(data['leaderboard']) == 0
        assert len(data['below_threshold']) > 0

    def test_ties_ranking(self, client, db_conn, seed_data):
        db.recompute_tool_stats()
        _login(client, seed_data['user_premium_id'])
        resp = client.get('/api/dashboard/leaderboard?min_votes=0')
        data = resp.get_json()
        if len(data['leaderboard']) > 1:
            # All at 0.0 win rate should share rank 1
            tied = [t for t in data['leaderboard'] if t['win_rate'] == 0.0]
            if len(tied) > 1:
                ranks = [t['rank'] for t in tied]
                assert all(r == ranks[0] for r in ranks)

    def test_confidence_badges(self, client, db_conn, seed_data):
        db.recompute_tool_stats()
        _login(client, seed_data['user_premium_id'])
        resp = client.get('/api/dashboard/leaderboard?min_votes=0')
        data = resp.get_json()
        for tool in data['leaderboard']:
            assert tool['confidence'] in ('high', 'medium', 'low')

    def test_computed_at_present(self, client, db_conn, seed_data):
        db.recompute_tool_stats()
        _login(client, seed_data['user_premium_id'])
        resp = client.get('/api/dashboard/leaderboard?min_votes=0')
        data = resp.get_json()
        assert data.get('computed_at') is not None


# ============== Premium Gate ==============

class TestLeaderboardPremiumGate:
    """Tests for premium gating on the leaderboard API."""

    def test_free_user_gets_403(self, client, db_conn, seed_data):
        _login(client, seed_data['user_free_id'])
        resp = client.get('/api/dashboard/leaderboard')
        assert resp.status_code == 403
        data = resp.get_json()
        assert data['error']['code'] == 'PREMIUM_REQUIRED'

    def test_unauthenticated_gets_401(self, client, db_conn, seed_data):
        resp = client.get('/api/dashboard/leaderboard')
        assert resp.status_code == 401
        data = resp.get_json()
        assert data['error']['code'] == 'AUTH_REQUIRED'


# ============== Teaser Endpoint ==============

class TestLeaderboardTeaser:
    """Tests for GET /api/dashboard/leaderboard/teaser."""

    def test_teaser_no_auth_required(self, client, db_conn, seed_data):
        db.recompute_tool_stats()
        resp = client.get('/api/dashboard/leaderboard/teaser')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        assert 'teaser' in data

    def test_teaser_max_two_tools(self, client, db_conn, seed_data):
        db.recompute_tool_stats()
        resp = client.get('/api/dashboard/leaderboard/teaser')
        data = resp.get_json()
        assert len(data['teaser']) <= 2

    def test_teaser_has_rounded_win_rate(self, client, db_conn, seed_data):
        db.recompute_tool_stats()
        resp = client.get('/api/dashboard/leaderboard/teaser')
        data = resp.get_json()
        for t in data['teaser']:
            assert 'win_rate_rounded' in t
            assert isinstance(t['win_rate_rounded'], int)


# ============== Cache Behavior ==============

class TestLeaderboardCache:
    """Tests for the in-memory leaderboard cache."""

    def test_cache_hit_returns_cached_flag(self, client, db_conn, seed_data):
        db.recompute_tool_stats()
        db._leaderboard_cache.invalidate_all()
        _login(client, seed_data['user_premium_id'])

        # First request populates cache
        resp1 = client.get('/api/dashboard/leaderboard?min_votes=0')
        data1 = resp1.get_json()
        assert data1['cached'] is False

        # Second request should hit cache
        resp2 = client.get('/api/dashboard/leaderboard?min_votes=0')
        data2 = resp2.get_json()
        assert data2['cached'] is True
        assert data2['cache_age_seconds'] >= 0

    def test_cache_invalidated_after_recompute(self, client, db_conn, seed_data):
        db.recompute_tool_stats()
        _login(client, seed_data['user_premium_id'])

        # Populate cache
        client.get('/api/dashboard/leaderboard?min_votes=0')

        # Recompute invalidates cache
        db._leaderboard_cache.invalidate_all()

        resp = client.get('/api/dashboard/leaderboard?min_votes=0')
        data = resp.get_json()
        assert data['cached'] is False


# ============== Dashboard Page ==============

class TestDashboardPage:
    """Tests for the /dashboard page route."""

    def test_premium_user_sees_dashboard(self, client, db_conn, seed_data):
        _login(client, seed_data['user_premium_id'])
        resp = client.get('/dashboard')
        assert resp.status_code == 200
        assert b'Compare & Vote Dashboard' in resp.data

    def test_free_user_sees_blurred_gate(self, client, db_conn, seed_data):
        _login(client, seed_data['user_free_id'])
        resp = client.get('/dashboard')
        assert resp.status_code == 200
        assert b'Unlock the Full Dashboard' in resp.data
        assert b'blur' in resp.data

    def test_anonymous_can_access(self, client, db_conn, seed_data):
        resp = client.get('/dashboard')
        assert resp.status_code == 200
        assert b'Compare & Vote Dashboard' in resp.data
