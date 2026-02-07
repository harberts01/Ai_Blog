"""Tests for compare & vote route endpoints."""
import json
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
    """Set session user_id to simulate a logged-in user."""
    with client.session_transaction() as sess:
        sess['user_id'] = user_id


def _create_matchup(seed_data):
    """Helper: create a chatgpt-vs-claude matchup, return matchup_id."""
    return db.create_matchup(
        seed_data['post_chatgpt_id'],
        seed_data['post_claude_id']
    )


# ============== GET /compare ==============

class TestComparePage:
    """Tests for the matchup listing page."""

    def test_returns_200(self, client, db_conn, seed_data):
        resp = client.get('/compare')
        assert resp.status_code == 200

    def test_shows_matchups(self, client, db_conn, seed_data):
        _create_matchup(seed_data)
        resp = client.get('/compare')
        assert resp.status_code == 200
        assert b'Compare' in resp.data

    def test_pagination_param(self, client, db_conn, seed_data):
        _create_matchup(seed_data)
        resp = client.get('/compare?page=1')
        assert resp.status_code == 200

    def test_empty_page(self, client, db_conn, seed_data):
        resp = client.get('/compare?page=999')
        assert resp.status_code == 200


# ============== GET /compare/<matchup_id> ==============

class TestViewMatchup:
    """Tests for the compare view page."""

    def test_returns_200_for_valid_matchup(self, client, db_conn, seed_data):
        matchup_id = _create_matchup(seed_data)
        resp = client.get(f'/compare/{matchup_id}')
        assert resp.status_code == 200

    def test_404_for_nonexistent_matchup(self, client, db_conn, seed_data):
        resp = client.get('/compare/999999')
        assert resp.status_code == 404

    def test_404_for_archived_matchup(self, client, db_conn, seed_data):
        matchup_id = _create_matchup(seed_data)
        with db_conn.cursor() as cur:
            cur.execute(
                "UPDATE matchups SET status = 'archived' WHERE matchup_id = %s",
                (matchup_id,)
            )
        resp = client.get(f'/compare/{matchup_id}')
        assert resp.status_code == 404

    def test_shows_post_content_blind(self, client, db_conn, seed_data):
        matchup_id = _create_matchup(seed_data)
        resp = client.get(f'/compare/{matchup_id}')
        # Should contain post content but not tool names for non-voted user
        assert b'Post A' in resp.data or b'Post B' in resp.data

    def test_logged_in_premium_user(self, client, db_conn, seed_data):
        matchup_id = _create_matchup(seed_data)
        _login(client, seed_data['user_premium_id'])
        resp = client.get(f'/compare/{matchup_id}')
        assert resp.status_code == 200

    def test_anonymous_user_can_view(self, client, db_conn, seed_data):
        matchup_id = _create_matchup(seed_data)
        resp = client.get(f'/compare/{matchup_id}')
        assert resp.status_code == 200

    def test_shows_results_for_user_who_voted(self, client, db_conn, seed_data):
        matchup_id = _create_matchup(seed_data)
        matchup = db.get_matchup(matchup_id)
        _login(client, seed_data['user_premium_id'])

        # Cast a vote directly via DB function
        db.cast_vote(
            seed_data['user_premium_id'], matchup_id,
            'overall', matchup['tool_a']
        )

        resp = client.get(f'/compare/{matchup_id}')
        assert resp.status_code == 200


# ============== POST /api/matchups/<id>/votes ==============

class TestApiBatchVoteMatchup:
    """Tests for the batch vote submission API (POST /votes)."""

    def test_requires_login(self, client, db_conn, seed_data):
        matchup_id = _create_matchup(seed_data)
        resp = client.post(
            f'/api/matchups/{matchup_id}/votes',
            json={'votes': [{'category': 'overall', 'winner': 'left'}]}
        )
        assert resp.status_code == 401
        data = resp.get_json()
        assert data['error']['code'] == 'AUTH_REQUIRED'

    def test_requires_premium(self, client, db_conn, seed_data):
        matchup_id = _create_matchup(seed_data)
        _login(client, seed_data['user_free_id'])
        resp = client.post(
            f'/api/matchups/{matchup_id}/votes',
            json={'votes': [{'category': 'overall', 'winner': 'left'}]}
        )
        assert resp.status_code == 403
        data = resp.get_json()
        assert data['error']['code'] == 'PREMIUM_REQUIRED'

    def test_premium_user_can_vote(self, client, db_conn, seed_data):
        matchup_id = _create_matchup(seed_data)
        _login(client, seed_data['user_premium_id'])
        resp = client.post(
            f'/api/matchups/{matchup_id}/votes',
            json={'votes': [{'category': 'overall', 'winner': 'left'}]}
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data['success'] is True
        assert data['vote_count'] == 1

    def test_vote_all_categories(self, client, db_conn, seed_data):
        matchup_id = _create_matchup(seed_data)
        _login(client, seed_data['user_premium_id'])
        votes = [{'category': cat, 'winner': 'left'} for cat in db.VOTE_CATEGORIES]
        resp = client.post(
            f'/api/matchups/{matchup_id}/votes',
            json={'votes': votes}
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data['success'] is True
        assert data['vote_count'] == 5

    def test_returns_results_and_edit_window(self, client, db_conn, seed_data):
        matchup_id = _create_matchup(seed_data)
        _login(client, seed_data['user_premium_id'])
        resp = client.post(
            f'/api/matchups/{matchup_id}/votes',
            json={'votes': [{'category': 'overall', 'winner': 'left'}]}
        )
        data = resp.get_json()
        assert 'results' in data
        assert 'tool_a_name' in data
        assert 'tool_b_name' in data
        assert 'position_a_is_left' in data
        assert 'edit_window_expires_at' in data

    def test_structured_error_format(self, client, db_conn, seed_data):
        matchup_id = _create_matchup(seed_data)
        _login(client, seed_data['user_free_id'])
        resp = client.post(
            f'/api/matchups/{matchup_id}/votes',
            json={'votes': [{'category': 'overall', 'winner': 'left'}]}
        )
        data = resp.get_json()
        assert 'error' in data
        assert 'code' in data['error']
        assert 'message' in data['error']
        assert 'details' in data['error']

    def test_404_for_nonexistent_matchup(self, client, db_conn, seed_data):
        _login(client, seed_data['user_premium_id'])
        resp = client.post(
            f'/api/matchups/999999/votes',
            json={'votes': [{'category': 'overall', 'winner': 'left'}]}
        )
        assert resp.status_code == 404

    def test_400_for_missing_votes(self, client, db_conn, seed_data):
        matchup_id = _create_matchup(seed_data)
        _login(client, seed_data['user_premium_id'])
        resp = client.post(
            f'/api/matchups/{matchup_id}/votes',
            json={}
        )
        assert resp.status_code == 400

    def test_400_for_invalid_winner_side(self, client, db_conn, seed_data):
        matchup_id = _create_matchup(seed_data)
        _login(client, seed_data['user_premium_id'])
        resp = client.post(
            f'/api/matchups/{matchup_id}/votes',
            json={'votes': [{'category': 'overall', 'winner': 'invalid'}]}
        )
        assert resp.status_code == 400

    def test_400_for_invalid_category(self, client, db_conn, seed_data):
        matchup_id = _create_matchup(seed_data)
        _login(client, seed_data['user_premium_id'])
        resp = client.post(
            f'/api/matchups/{matchup_id}/votes',
            json={'votes': [{'category': 'nonexistent', 'winner': 'left'}]}
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert data['error']['code'] == 'INVALID_CATEGORY'

    def test_vote_maps_left_right_correctly(self, client, db_conn, seed_data):
        matchup_id = _create_matchup(seed_data)
        matchup = db.get_matchup(matchup_id)
        _login(client, seed_data['user_premium_id'])

        resp = client.post(
            f'/api/matchups/{matchup_id}/votes',
            json={'votes': [{'category': 'overall', 'winner': 'left'}]}
        )
        assert resp.status_code == 201

        votes = db.get_user_votes_for_matchup(
            seed_data['user_premium_id'], matchup_id
        )
        assert len(votes) == 1
        assert votes[0]['winner_tool'] in (matchup['tool_a'], matchup['tool_b'])

    def test_archived_matchup_rejected(self, client, db_conn, seed_data):
        matchup_id = _create_matchup(seed_data)
        with db_conn.cursor() as cur:
            cur.execute(
                "UPDATE matchups SET status = 'archived' WHERE matchup_id = %s",
                (matchup_id,)
            )
        _login(client, seed_data['user_premium_id'])
        resp = client.post(
            f'/api/matchups/{matchup_id}/votes',
            json={'votes': [{'category': 'overall', 'winner': 'left'}]}
        )
        assert resp.status_code == 409
        data = resp.get_json()
        assert data['error']['code'] == 'MATCHUP_INACTIVE'


# ============== PATCH /api/matchups/<id>/votes ==============

class TestApiBatchEditVotes:
    """Tests for the batch vote edit API (PATCH /votes)."""

    def test_requires_login(self, client, db_conn, seed_data):
        matchup_id = _create_matchup(seed_data)
        resp = client.patch(
            f'/api/matchups/{matchup_id}/votes',
            json={'votes': [{'category': 'overall', 'winner': 'left'}]}
        )
        assert resp.status_code == 401
        data = resp.get_json()
        assert data['error']['code'] == 'AUTH_REQUIRED'

    def test_patch_success(self, client, db_conn, seed_data):
        matchup_id = _create_matchup(seed_data)
        _login(client, seed_data['user_premium_id'])

        # First submit
        client.post(
            f'/api/matchups/{matchup_id}/votes',
            json={'votes': [{'category': 'overall', 'winner': 'left'}]}
        )

        # Then edit
        resp = client.patch(
            f'/api/matchups/{matchup_id}/votes',
            json={'votes': [{'category': 'overall', 'winner': 'right'}]}
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True


# ============== GET /api/matchups/<id>/results ==============

class TestApiMatchupResults:
    """Tests for the results API endpoint."""

    def test_requires_login(self, client, db_conn, seed_data):
        matchup_id = _create_matchup(seed_data)
        resp = client.get(f'/api/matchups/{matchup_id}/results')
        assert resp.status_code == 401
        data = resp.get_json()
        assert data['error']['code'] == 'AUTH_REQUIRED'

    def test_403_for_free_user(self, client, db_conn, seed_data):
        matchup_id = _create_matchup(seed_data)
        _login(client, seed_data['user_free_id'])
        resp = client.get(f'/api/matchups/{matchup_id}/results')
        assert resp.status_code == 403
        data = resp.get_json()
        assert data['error']['code'] == 'PREMIUM_REQUIRED'
        assert data['error']['upgrade_url'] == '/pricing'

    def test_403_if_not_voted(self, client, db_conn, seed_data):
        matchup_id = _create_matchup(seed_data)
        _login(client, seed_data['user_premium_id'])
        resp = client.get(f'/api/matchups/{matchup_id}/results')
        assert resp.status_code == 403
        data = resp.get_json()
        assert data['success'] is False

    def test_returns_results_after_voting(self, client, db_conn, seed_data):
        matchup_id = _create_matchup(seed_data)
        matchup = db.get_matchup(matchup_id)
        _login(client, seed_data['user_premium_id'])

        # Cast a vote first
        db.cast_vote(
            seed_data['user_premium_id'], matchup_id,
            'overall', matchup['tool_a']
        )

        resp = client.get(f'/api/matchups/{matchup_id}/results')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        assert 'results' in data
        assert 'tool_a_name' in data
        assert 'tool_b_name' in data
        assert 'total_votes' in data

    def test_404_for_nonexistent_matchup(self, client, db_conn, seed_data):
        _login(client, seed_data['user_premium_id'])
        resp = client.get('/api/matchups/999999/results')
        assert resp.status_code == 404

    def test_results_include_all_categories(self, client, db_conn, seed_data):
        matchup_id = _create_matchup(seed_data)
        matchup = db.get_matchup(matchup_id)
        _login(client, seed_data['user_premium_id'])

        # Vote on all categories
        for cat in db.VOTE_CATEGORIES:
            db.cast_vote(
                seed_data['user_premium_id'], matchup_id,
                cat, matchup['tool_a']
            )

        resp = client.get(f'/api/matchups/{matchup_id}/results')
        data = resp.get_json()
        for cat in db.VOTE_CATEGORIES:
            assert cat in data['results']
            assert 'tool_a_votes' in data['results'][cat]
            assert 'tool_b_votes' in data['results'][cat]
            assert 'tool_a_pct' in data['results'][cat]
            assert 'tool_b_pct' in data['results'][cat]
