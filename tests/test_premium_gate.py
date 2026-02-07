"""Tests for the premium gating layer (Phase 1 / Step 4)."""
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


# ============== premium_required Decorator ==============

class TestPremiumRequiredDecorator:
    """Tests for the premium_required decorator on API routes."""

    def test_unauthenticated_api_gets_401(self, client, db_conn, seed_data):
        matchup_id = _create_matchup(seed_data)
        resp = client.get(f'/api/matchups/{matchup_id}/results')
        assert resp.status_code == 401
        data = resp.get_json()
        assert data['error']['code'] == 'AUTH_REQUIRED'

    def test_free_user_api_gets_403(self, client, db_conn, seed_data):
        matchup_id = _create_matchup(seed_data)
        _login(client, seed_data['user_free_id'])
        resp = client.get(f'/api/matchups/{matchup_id}/results')
        assert resp.status_code == 403
        data = resp.get_json()
        assert data['error']['code'] == 'PREMIUM_REQUIRED'
        assert data['error']['upgrade_url'] == '/pricing'

    def test_premium_user_allowed_through(self, client, db_conn, seed_data):
        matchup_id = _create_matchup(seed_data)
        matchup = db.get_matchup(matchup_id)
        _login(client, seed_data['user_premium_id'])
        # Must vote first so results endpoint returns 200
        db.cast_vote(
            seed_data['user_premium_id'], matchup_id,
            'overall', matchup['tool_a']
        )
        resp = client.get(f'/api/matchups/{matchup_id}/results')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True

    def test_free_user_post_votes_gets_403(self, client, db_conn, seed_data):
        matchup_id = _create_matchup(seed_data)
        _login(client, seed_data['user_free_id'])
        resp = client.post(
            f'/api/matchups/{matchup_id}/votes',
            json={'votes': [{'category': 'overall', 'winner': 'left'}]}
        )
        assert resp.status_code == 403
        data = resp.get_json()
        assert data['error']['code'] == 'PREMIUM_REQUIRED'

    def test_free_user_patch_votes_gets_403(self, client, db_conn, seed_data):
        matchup_id = _create_matchup(seed_data)
        _login(client, seed_data['user_free_id'])
        resp = client.patch(
            f'/api/matchups/{matchup_id}/votes',
            json={'votes': [{'category': 'overall', 'winner': 'left'}]}
        )
        assert resp.status_code == 403
        data = resp.get_json()
        assert data['error']['code'] == 'PREMIUM_REQUIRED'


# ============== get_active_matchups_for_post ==============

class TestGetActiveMatchupsForPost:
    """Tests for the database function get_active_matchups_for_post."""

    def test_returns_matchup_for_post_a(self, db_conn, seed_data):
        matchup_id = _create_matchup(seed_data)
        results = db.get_active_matchups_for_post(seed_data['post_chatgpt_id'])
        assert any(m['matchup_id'] == matchup_id for m in results)

    def test_returns_matchup_for_post_b(self, db_conn, seed_data):
        matchup_id = _create_matchup(seed_data)
        results = db.get_active_matchups_for_post(seed_data['post_claude_id'])
        assert any(m['matchup_id'] == matchup_id for m in results)

    def test_returns_opposing_tool_info(self, db_conn, seed_data):
        _create_matchup(seed_data)
        results = db.get_active_matchups_for_post(seed_data['post_chatgpt_id'])
        assert len(results) >= 1
        assert results[0]['opposing_tool_name'] is not None
        assert results[0]['opposing_tool_slug'] is not None

    def test_excludes_archived_matchups(self, db_conn, seed_data):
        matchup_id = _create_matchup(seed_data)
        with db_conn.cursor() as cur:
            cur.execute(
                "UPDATE matchups SET status = 'archived' WHERE matchup_id = %s",
                (matchup_id,)
            )
        results = db.get_active_matchups_for_post(seed_data['post_chatgpt_id'])
        assert not any(m['matchup_id'] == matchup_id for m in results)

    def test_empty_for_unmatched_post(self, db_conn, seed_data):
        results = db.get_active_matchups_for_post(999999)
        assert results == []


# ============== Blog Post Compare Banner ==============

class TestBlogPostCompareBanner:
    """Tests for the compare banner on blog post pages."""

    def test_banner_shown_when_matchup_exists(self, client, db_conn, seed_data):
        _create_matchup(seed_data)
        # Log in so we can see full post content (banner is inside can_view_full block)
        _login(client, seed_data['user_premium_id'])
        resp = client.get(f'/post/{seed_data["post_chatgpt_id"]}')
        assert resp.status_code == 200
        assert b'compare-banner' in resp.data

    def test_no_banner_when_no_matchup(self, client, db_conn, seed_data):
        _login(client, seed_data['user_premium_id'])
        resp = client.get(f'/post/{seed_data["post_chatgpt_id"]}')
        assert resp.status_code == 200
        assert b'compare-banner' not in resp.data


# ============== Compare View Free User Experience ==============

class TestCompareViewFreeUser:
    """Tests for the compare view with a free (non-premium) user."""

    def test_free_user_sees_disabled_voting(self, client, db_conn, seed_data):
        matchup_id = _create_matchup(seed_data)
        _login(client, seed_data['user_free_id'])
        resp = client.get(f'/compare/{matchup_id}')
        assert resp.status_code == 200
        assert b'voting-panel-disabled' in resp.data
        assert b'bi-lock-fill' in resp.data

    def test_free_user_sees_upgrade_cta(self, client, db_conn, seed_data):
        matchup_id = _create_matchup(seed_data)
        _login(client, seed_data['user_free_id'])
        resp = client.get(f'/compare/{matchup_id}')
        assert resp.status_code == 200
        assert b'Upgrade to Vote' in resp.data

    def test_free_user_sees_blurred_teaser(self, client, db_conn, seed_data):
        matchup_id = _create_matchup(seed_data)
        _login(client, seed_data['user_free_id'])
        resp = client.get(f'/compare/{matchup_id}')
        assert resp.status_code == 200
        assert b'blurred-teaser' in resp.data
        assert b'See How the Community Voted' in resp.data

    def test_free_user_sees_upgrade_modal(self, client, db_conn, seed_data):
        matchup_id = _create_matchup(seed_data)
        _login(client, seed_data['user_free_id'])
        resp = client.get(f'/compare/{matchup_id}')
        assert resp.status_code == 200
        assert b'upgradeModal' in resp.data
        assert b'Unlock Compare' in resp.data

    def test_premium_user_no_disabled_panel(self, client, db_conn, seed_data):
        matchup_id = _create_matchup(seed_data)
        _login(client, seed_data['user_premium_id'])
        resp = client.get(f'/compare/{matchup_id}')
        assert resp.status_code == 200
        # The CSS class name appears in the stylesheet for all users,
        # but the actual HTML element should only render for free users
        assert b'id="voting-panel-disabled"' not in resp.data
        assert b'Upgrade to Vote' not in resp.data
