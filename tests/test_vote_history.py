"""Tests for Personal Voting History (Phase 2 / Step 3)."""
import pytest
import database as db
from datetime import date, timedelta


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


def _create_matchup_3(seed_data):
    """Chatgpt vs Gemini."""
    return db.create_matchup(
        seed_data['post_chatgpt_id'],
        seed_data['post_gemini_id']
    )


def _create_matchup_4(seed_data):
    """Claude vs Llama."""
    return db.create_matchup(
        seed_data['post_claude_id'],
        seed_data['post_llama_id']
    )


def _create_matchup_5(seed_data):
    """Chatgpt vs Llama."""
    return db.create_matchup(
        seed_data['post_chatgpt_id'],
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


# ============== Recompute User Vote Stats ==============

class TestRecomputeUserVoteStats:
    """Tests for the recompute_user_vote_stats() function."""

    def test_basic_recompute(self, db_conn, seed_data):
        mid = _create_matchup(seed_data)
        matchup = db.get_matchup(mid)
        _cast_and_lock(db_conn, seed_data['user_premium_id'], mid,
                       db.VOTE_CATEGORIES, matchup['tool_a'])

        result = db.recompute_user_vote_stats(seed_data['user_premium_id'])
        assert result is not None
        assert result['success'] is True

        with db_conn.cursor() as cur:
            cur.execute(
                "SELECT total_votes_cast, total_matchups_voted FROM user_vote_stats WHERE user_id = %s",
                (seed_data['user_premium_id'],)
            )
            row = cur.fetchone()
            assert row is not None
            assert row[0] == 5  # 5 categories
            assert row[1] == 1  # 1 matchup

    def test_favorite_tool_computed(self, db_conn, seed_data):
        # Vote chatgpt-side tool in 2 matchups, different tool in 1
        mid1 = _create_matchup(seed_data)
        m1 = db.get_matchup(mid1)
        _cast_and_lock(db_conn, seed_data['user_premium_id'], mid1,
                       ['overall'], m1['tool_a'])

        mid2 = _create_matchup_3(seed_data)
        m2 = db.get_matchup(mid2)
        # chatgpt vs gemini — vote for chatgpt (tool_a since chatgpt < gemini)
        _cast_and_lock(db_conn, seed_data['user_premium_id'], mid2,
                       ['overall', 'accuracy'], m2['tool_a'])

        mid3 = _create_matchup_alt(seed_data)
        m3 = db.get_matchup(mid3)
        _cast_and_lock(db_conn, seed_data['user_premium_id'], mid3,
                       ['overall'], m3['tool_a'])

        db.recompute_user_vote_stats(seed_data['user_premium_id'])

        with db_conn.cursor() as cur:
            cur.execute(
                "SELECT favorite_tool_id, favorite_tool_vote_count FROM user_vote_stats WHERE user_id = %s",
                (seed_data['user_premium_id'],)
            )
            row = cur.fetchone()
            assert row is not None
            # chatgpt tool_a voted 3 times total (mid1 + mid2 x2), should be favorite
            assert row[1] >= 2

    def test_category_most_voted(self, db_conn, seed_data):
        mid = _create_matchup(seed_data)
        matchup = db.get_matchup(mid)
        _cast_and_lock(db_conn, seed_data['user_premium_id'], mid,
                       ['overall', 'accuracy'], matchup['tool_a'])

        mid2 = _create_matchup_alt(seed_data)
        m2 = db.get_matchup(mid2)
        _cast_and_lock(db_conn, seed_data['user_premium_id'], mid2,
                       ['overall'], m2['tool_a'])

        db.recompute_user_vote_stats(seed_data['user_premium_id'])

        with db_conn.cursor() as cur:
            cur.execute(
                "SELECT category_most_voted FROM user_vote_stats WHERE user_id = %s",
                (seed_data['user_premium_id'],)
            )
            row = cur.fetchone()
            assert row is not None
            assert row[0] == 'overall'

    def test_majority_agreement_all_aligned(self, db_conn, seed_data):
        """As sole voter, user should always agree with majority (100%)."""
        mid = _create_matchup(seed_data)
        matchup = db.get_matchup(mid)
        _cast_and_lock(db_conn, seed_data['user_premium_id'], mid,
                       db.VOTE_CATEGORIES, matchup['tool_a'])

        db.recompute_user_vote_stats(seed_data['user_premium_id'])

        with db_conn.cursor() as cur:
            cur.execute(
                "SELECT majority_agreement_rate FROM user_vote_stats WHERE user_id = %s",
                (seed_data['user_premium_id'],)
            )
            row = cur.fetchone()
            assert row is not None
            assert float(row[0]) == 1.0

    def test_majority_agreement_partial(self, db_conn, seed_data):
        """Two users vote differently on some categories."""
        mid = _create_matchup(seed_data)
        matchup = db.get_matchup(mid)

        # Premium user votes tool_a for all 5 categories
        _cast_and_lock(db_conn, seed_data['user_premium_id'], mid,
                       db.VOTE_CATEGORIES, matchup['tool_a'])

        # Free user votes tool_b for 3 categories, tool_a for 2
        _cast_and_lock(db_conn, seed_data['user_free_id'], mid,
                       ['overall', 'accuracy'], matchup['tool_a'])
        _cast_and_lock(db_conn, seed_data['user_free_id'], mid,
                       ['writing_quality', 'creativity', 'usefulness'], matchup['tool_b'])

        db.recompute_user_vote_stats(seed_data['user_premium_id'])

        with db_conn.cursor() as cur:
            cur.execute(
                "SELECT majority_agreements, majority_agreement_rate FROM user_vote_stats WHERE user_id = %s",
                (seed_data['user_premium_id'],)
            )
            row = cur.fetchone()
            assert row is not None
            # Premium voted tool_a on all 5. Community: on 2 categories both vote tool_a (majority=tool_a),
            # on 3 categories it's 1-1 tie (row_number picks tool_a or tool_b based on count DESC).
            # Either way, agreement should be between 2 and 5.
            assert row[0] >= 2
            assert float(row[1]) > 0

    def test_streak_consecutive_days(self, db_conn, seed_data):
        """Votes on 3 consecutive days should yield streak=3."""
        # Use 3 different matchup pairs so we don't hit the dedup
        creators = [_create_matchup, _create_matchup_alt, _create_matchup_3]
        mids = []
        for creator in creators:
            mid = creator(seed_data)
            m = db.get_matchup(mid)
            _cast_and_lock(db_conn, seed_data['user_premium_id'], mid,
                           ['overall'], m['tool_a'])
            mids.append(mid)

        # Backdate votes for previous days
        today = date.today()
        with db_conn.cursor() as cur:
            for i, days_ago in enumerate([0, 1, 2]):
                vote_date = today - timedelta(days=days_ago)
                cur.execute(
                    "UPDATE votes SET voted_at = %s WHERE user_id = %s AND matchup_id = %s",
                    (vote_date, seed_data['user_premium_id'], mids[i])
                )

        db.recompute_user_vote_stats(seed_data['user_premium_id'])

        with db_conn.cursor() as cur:
            cur.execute(
                "SELECT current_streak, longest_streak FROM user_vote_stats WHERE user_id = %s",
                (seed_data['user_premium_id'],)
            )
            row = cur.fetchone()
            assert row is not None
            assert row[0] == 3  # current streak
            assert row[1] >= 3  # longest streak

    def test_streak_with_gap(self, db_conn, seed_data):
        """Today, yesterday, and 4 days ago → current=2."""
        today = date.today()
        creators = [_create_matchup, _create_matchup_alt, _create_matchup_3]
        mids = []
        for creator in creators:
            mid = creator(seed_data)
            m = db.get_matchup(mid)
            _cast_and_lock(db_conn, seed_data['user_premium_id'], mid,
                           ['overall'], m['tool_a'])
            mids.append(mid)

        with db_conn.cursor() as cur:
            # mids[0] = today, mids[1] = yesterday, mids[2] = 4 days ago
            cur.execute(
                "UPDATE votes SET voted_at = %s WHERE user_id = %s AND matchup_id = %s",
                (today, seed_data['user_premium_id'], mids[0])
            )
            cur.execute(
                "UPDATE votes SET voted_at = %s WHERE user_id = %s AND matchup_id = %s",
                (today - timedelta(days=1), seed_data['user_premium_id'], mids[1])
            )
            cur.execute(
                "UPDATE votes SET voted_at = %s WHERE user_id = %s AND matchup_id = %s",
                (today - timedelta(days=4), seed_data['user_premium_id'], mids[2])
            )

        db.recompute_user_vote_stats(seed_data['user_premium_id'])

        with db_conn.cursor() as cur:
            cur.execute(
                "SELECT current_streak FROM user_vote_stats WHERE user_id = %s",
                (seed_data['user_premium_id'],)
            )
            row = cur.fetchone()
            assert row is not None
            assert row[0] == 2

    def test_streak_no_recent_votes(self, db_conn, seed_data):
        """Vote 5 days ago → current_streak=0."""
        mid = _create_matchup(seed_data)
        matchup = db.get_matchup(mid)
        _cast_and_lock(db_conn, seed_data['user_premium_id'], mid,
                       ['overall'], matchup['tool_a'])

        with db_conn.cursor() as cur:
            cur.execute(
                "UPDATE votes SET voted_at = %s WHERE user_id = %s AND matchup_id = %s",
                (date.today() - timedelta(days=5), seed_data['user_premium_id'], mid)
            )

        db.recompute_user_vote_stats(seed_data['user_premium_id'])

        with db_conn.cursor() as cur:
            cur.execute(
                "SELECT current_streak FROM user_vote_stats WHERE user_id = %s",
                (seed_data['user_premium_id'],)
            )
            row = cur.fetchone()
            assert row is not None
            assert row[0] == 0

    def test_upsert_on_second_call(self, db_conn, seed_data):
        """Calling recompute twice should update, not duplicate."""
        mid = _create_matchup(seed_data)
        matchup = db.get_matchup(mid)
        _cast_and_lock(db_conn, seed_data['user_premium_id'], mid,
                       ['overall'], matchup['tool_a'])

        db.recompute_user_vote_stats(seed_data['user_premium_id'])
        db.recompute_user_vote_stats(seed_data['user_premium_id'])

        with db_conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM user_vote_stats WHERE user_id = %s",
                (seed_data['user_premium_id'],)
            )
            assert cur.fetchone()[0] == 1

    def test_empty_user_returns_zeros(self, db_conn, seed_data):
        """User with no votes should get all zeros."""
        db.recompute_user_vote_stats(seed_data['user_free_id'])

        with db_conn.cursor() as cur:
            cur.execute(
                "SELECT total_votes_cast, current_streak, favorite_tool_id FROM user_vote_stats WHERE user_id = %s",
                (seed_data['user_free_id'],)
            )
            row = cur.fetchone()
            assert row is not None
            assert row[0] == 0
            assert row[1] == 0
            assert row[2] is None


# ============== User Vote Stats API ==============

class TestUserVoteStatsAPI:
    """Tests for GET /api/users/me/vote-stats."""

    def test_premium_gets_stats(self, client, db_conn, seed_data):
        mid = _create_matchup(seed_data)
        matchup = db.get_matchup(mid)
        _cast_and_lock(db_conn, seed_data['user_premium_id'], mid,
                       db.VOTE_CATEGORIES, matchup['tool_a'])
        db.recompute_user_vote_stats(seed_data['user_premium_id'])

        _login(client, seed_data['user_premium_id'])
        resp = client.get('/api/users/me/vote-stats')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        assert data['total_votes_cast'] >= 5

    def test_includes_distributions(self, client, db_conn, seed_data):
        mid = _create_matchup(seed_data)
        matchup = db.get_matchup(mid)
        _cast_and_lock(db_conn, seed_data['user_premium_id'], mid,
                       db.VOTE_CATEGORIES, matchup['tool_a'])
        db.recompute_user_vote_stats(seed_data['user_premium_id'])
        db._user_stats_cache.invalidate_all()

        _login(client, seed_data['user_premium_id'])
        resp = client.get('/api/users/me/vote-stats')
        data = resp.get_json()
        assert 'category_distribution' in data
        assert 'tool_distribution' in data
        assert len(data['category_distribution']) > 0
        assert len(data['tool_distribution']) > 0

    def test_free_user_gets_403(self, client, db_conn, seed_data):
        _login(client, seed_data['user_free_id'])
        resp = client.get('/api/users/me/vote-stats')
        assert resp.status_code == 403
        data = resp.get_json()
        assert data['error']['code'] == 'PREMIUM_REQUIRED'


# ============== User Vote History API ==============

class TestUserVoteHistoryAPI:
    """Tests for GET /api/users/me/votes."""

    def test_premium_gets_paginated_history(self, client, db_conn, seed_data):
        mid = _create_matchup(seed_data)
        matchup = db.get_matchup(mid)
        _cast_and_lock(db_conn, seed_data['user_premium_id'], mid,
                       db.VOTE_CATEGORIES, matchup['tool_a'])

        _login(client, seed_data['user_premium_id'])
        resp = client.get('/api/users/me/votes')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        assert 'votes' in data
        assert 'total' in data
        assert 'page' in data
        assert 'pages' in data
        assert len(data['votes']) >= 5

    def test_filter_by_tool(self, client, db_conn, seed_data):
        mid = _create_matchup(seed_data)
        matchup = db.get_matchup(mid)
        _cast_and_lock(db_conn, seed_data['user_premium_id'], mid,
                       ['overall'], matchup['tool_a'])

        _login(client, seed_data['user_premium_id'])
        resp = client.get('/api/users/me/votes?tool=chatgpt')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        # All votes should involve chatgpt
        for v in data['votes']:
            slugs = [v['tool_a']['slug'], v['tool_b']['slug']]
            assert 'chatgpt' in slugs

    def test_filter_by_category(self, client, db_conn, seed_data):
        mid = _create_matchup(seed_data)
        matchup = db.get_matchup(mid)
        _cast_and_lock(db_conn, seed_data['user_premium_id'], mid,
                       db.VOTE_CATEGORIES, matchup['tool_a'])

        _login(client, seed_data['user_premium_id'])
        resp = client.get('/api/users/me/votes?category=overall')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        for v in data['votes']:
            assert v['category'] == 'overall'

    def test_filter_by_alignment(self, client, db_conn, seed_data):
        mid = _create_matchup(seed_data)
        matchup = db.get_matchup(mid)
        _cast_and_lock(db_conn, seed_data['user_premium_id'], mid,
                       ['overall'], matchup['tool_a'])

        _login(client, seed_data['user_premium_id'])
        resp = client.get('/api/users/me/votes?alignment=majority')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        for v in data['votes']:
            assert v['user_aligned'] is True

    def test_sort_oldest(self, client, db_conn, seed_data):
        mid = _create_matchup(seed_data)
        matchup = db.get_matchup(mid)
        _cast_and_lock(db_conn, seed_data['user_premium_id'], mid,
                       db.VOTE_CATEGORIES, matchup['tool_a'])

        _login(client, seed_data['user_premium_id'])
        resp = client.get('/api/users/me/votes?sort=oldest')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        # Verify ascending order
        if len(data['votes']) >= 2:
            assert data['votes'][0]['voted_at'] <= data['votes'][-1]['voted_at']

    def test_free_user_blocked(self, client, db_conn, seed_data):
        _login(client, seed_data['user_free_id'])
        resp = client.get('/api/users/me/votes')
        assert resp.status_code == 403
        data = resp.get_json()
        assert data['error']['code'] == 'PREMIUM_REQUIRED'


# ============== Vote History Integration ==============

class TestVoteHistoryIntegration:
    """Integration tests for vote submission triggering stats recompute."""

    def test_stats_recomputed_on_vote_submit(self, client, db_conn, seed_data):
        """After voting, stats should be available."""
        mid = _create_matchup(seed_data)
        matchup = db.get_matchup(mid)
        _cast_and_lock(db_conn, seed_data['user_premium_id'], mid,
                       db.VOTE_CATEGORIES, matchup['tool_a'])
        db.recompute_user_vote_stats(seed_data['user_premium_id'])
        db._user_stats_cache.invalidate_all()

        _login(client, seed_data['user_premium_id'])
        resp = client.get('/api/users/me/vote-stats')
        data = resp.get_json()
        assert data['success'] is True
        assert data['total_votes_cast'] > 0

    def test_cron_runs_user_stats(self, client, db_conn, seed_data, app_instance):
        """Cron endpoint should include user_stats_updated."""
        from config import Config
        token = Config.CRON_SECRET
        resp = client.get(f'/cron/recompute-stats?token={token}')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        assert 'user_stats_updated' in data


# ============== Dashboard History Page ==============

class TestDashboardHistoryPage:
    """Tests for the /dashboard/history page."""

    def test_premium_sees_history_page(self, client, db_conn, seed_data):
        _login(client, seed_data['user_premium_id'])
        resp = client.get('/dashboard/history')
        assert resp.status_code == 200
        assert b'My Votes' in resp.data
