"""Tests for the hardened vote submission pipeline (batch submit, edit, audit)."""
import pytest
import database as db


def _create_matchup(seed_data):
    """Helper: create a chatgpt-vs-claude matchup, return matchup_id."""
    return db.create_matchup(
        seed_data['post_chatgpt_id'],
        seed_data['post_claude_id']
    )


def _get_tools(matchup_id):
    """Helper: return (tool_a, tool_b) for a matchup."""
    m = db.get_matchup(matchup_id)
    return m['tool_a'], m['tool_b']


def _make_votes(categories, tool_id):
    """Helper: build vote dicts for given categories all pointing to same tool."""
    return [{'category': cat, 'winner_tool': tool_id} for cat in categories]


# ============== Batch Submit Tests ==============

class TestBatchSubmitVotes:

    def test_submit_all_categories(self, db_conn, seed_data):
        mid = _create_matchup(seed_data)
        tool_a, _ = _get_tools(mid)
        votes = _make_votes(db.VOTE_CATEGORIES, tool_a)

        result = db.batch_submit_votes(
            seed_data['user_premium_id'], mid, votes, True)

        assert result['success'] is True
        assert result['status_code'] == 201
        assert len(result['vote_ids']) == 5
        assert result['edit_window_expires_at'] is not None

    def test_submit_partial_categories(self, db_conn, seed_data):
        mid = _create_matchup(seed_data)
        tool_a, _ = _get_tools(mid)
        cats = ['writing_quality', 'accuracy', 'overall']
        votes = _make_votes(cats, tool_a)

        result = db.batch_submit_votes(
            seed_data['user_premium_id'], mid, votes, True)

        assert result['success'] is True
        assert result['status_code'] == 201
        assert len(result['vote_ids']) == 3

        # Only those 3 categories in DB
        db_votes = db.get_user_votes_for_matchup(seed_data['user_premium_id'], mid)
        assert len(db_votes) == 3
        assert set(v['category'] for v in db_votes) == set(cats)

    def test_free_user_rejected(self, db_conn, seed_data):
        mid = _create_matchup(seed_data)
        tool_a, _ = _get_tools(mid)
        votes = _make_votes(['overall'], tool_a)

        result = db.batch_submit_votes(
            seed_data['user_free_id'], mid, votes, True)

        assert result['success'] is False
        assert result['error']['code'] == 'PREMIUM_REQUIRED'
        assert result['status_code'] == 403

    def test_nonexistent_matchup(self, db_conn, seed_data):
        votes = [{'category': 'overall', 'winner_tool': 1}]
        result = db.batch_submit_votes(
            seed_data['user_premium_id'], 999999, votes, True)

        assert result['success'] is False
        assert result['error']['code'] == 'MATCHUP_NOT_FOUND'

    def test_archived_matchup(self, db_conn, seed_data):
        mid = _create_matchup(seed_data)
        tool_a, _ = _get_tools(mid)
        with db_conn.cursor() as cur:
            cur.execute("UPDATE matchups SET status = 'archived' WHERE matchup_id = %s",
                        (mid,))

        result = db.batch_submit_votes(
            seed_data['user_premium_id'], mid,
            _make_votes(['overall'], tool_a), True)

        assert result['success'] is False
        assert result['error']['code'] == 'MATCHUP_INACTIVE'

    def test_invalid_category(self, db_conn, seed_data):
        mid = _create_matchup(seed_data)
        tool_a, _ = _get_tools(mid)
        votes = [{'category': 'nonexistent', 'winner_tool': tool_a}]

        result = db.batch_submit_votes(
            seed_data['user_premium_id'], mid, votes, True)

        assert result['success'] is False
        assert result['error']['code'] == 'INVALID_CATEGORY'

    def test_duplicate_category_in_batch(self, db_conn, seed_data):
        mid = _create_matchup(seed_data)
        tool_a, _ = _get_tools(mid)
        votes = [
            {'category': 'overall', 'winner_tool': tool_a},
            {'category': 'overall', 'winner_tool': tool_a},
        ]

        result = db.batch_submit_votes(
            seed_data['user_premium_id'], mid, votes, True)

        assert result['success'] is False
        assert result['error']['code'] == 'DUPLICATE_CATEGORY'

    def test_invalid_winner_tool(self, db_conn, seed_data):
        mid = _create_matchup(seed_data)
        gemini_id = seed_data['tool_gemini_id']
        votes = [{'category': 'overall', 'winner_tool': gemini_id}]

        result = db.batch_submit_votes(
            seed_data['user_premium_id'], mid, votes, True)

        assert result['success'] is False
        assert result['error']['code'] == 'INVALID_WINNER'

    def test_empty_votes_rejected(self, db_conn, seed_data):
        mid = _create_matchup(seed_data)
        result = db.batch_submit_votes(
            seed_data['user_premium_id'], mid, [], True)

        assert result['success'] is False
        assert result['error']['code'] == 'INVALID_PAYLOAD'

    def test_too_many_votes_rejected(self, db_conn, seed_data):
        mid = _create_matchup(seed_data)
        tool_a, _ = _get_tools(mid)
        votes = _make_votes(db.VOTE_CATEGORIES, tool_a)
        votes.append({'category': 'overall', 'winner_tool': tool_a})  # 6 total

        result = db.batch_submit_votes(
            seed_data['user_premium_id'], mid, votes, True)

        assert result['success'] is False
        assert result['error']['code'] == 'INVALID_PAYLOAD'

    def test_idempotent_identical_resubmit(self, db_conn, seed_data):
        mid = _create_matchup(seed_data)
        tool_a, _ = _get_tools(mid)
        votes = _make_votes(['overall', 'accuracy'], tool_a)

        first = db.batch_submit_votes(
            seed_data['user_premium_id'], mid, votes, True)
        assert first['success'] is True
        assert first['status_code'] == 201

        second = db.batch_submit_votes(
            seed_data['user_premium_id'], mid, votes, True)
        assert second['success'] is True
        assert second['status_code'] == 200  # Idempotent

    def test_different_resubmit_suggests_patch(self, db_conn, seed_data):
        mid = _create_matchup(seed_data)
        tool_a, tool_b = _get_tools(mid)

        first = db.batch_submit_votes(
            seed_data['user_premium_id'], mid,
            _make_votes(['overall'], tool_a), True)
        assert first['success'] is True

        second = db.batch_submit_votes(
            seed_data['user_premium_id'], mid,
            _make_votes(['overall'], tool_b), True)
        assert second['success'] is False
        assert second['error']['code'] == 'EXISTING_VOTES_USE_PATCH'

    def test_locked_votes_rejected(self, db_conn, seed_data):
        mid = _create_matchup(seed_data)
        tool_a, _ = _get_tools(mid)

        db.batch_submit_votes(
            seed_data['user_premium_id'], mid,
            _make_votes(['overall'], tool_a), True)

        with db_conn.cursor() as cur:
            cur.execute(
                "UPDATE votes SET locked = TRUE WHERE user_id = %s AND matchup_id = %s",
                (seed_data['user_premium_id'], mid))

        result = db.batch_submit_votes(
            seed_data['user_premium_id'], mid,
            _make_votes(['overall'], tool_a), True)

        assert result['success'] is False
        assert result['error']['code'] == 'VOTE_LOCKED'

    def test_rate_limit_enforced(self, db_conn, seed_data):
        """49 existing votes + batch of 2 should exceed the 50 limit."""
        mid = _create_matchup(seed_data)
        tool_a, _ = _get_tools(mid)

        # Create 49 fake votes directly in DB
        with db_conn.cursor() as cur:
            # Create extra matchups to get 49 distinct category votes
            # We need multiple matchups since max 5 categories per matchup
            for i in range(10):  # 10 matchups * 5 categories = 50 capacity
                cur.execute("""
                    INSERT INTO Post (Title, Content, Category, tool_id)
                    VALUES (%s, %s, 'Tech', %s) RETURNING postid
                """, (f'RateTest A {i}', f'content a {i}', seed_data['tool_chatgpt_id']))
                pa = cur.fetchone()[0]
                cur.execute("""
                    INSERT INTO Post (Title, Content, Category, tool_id)
                    VALUES (%s, %s, 'Tech', %s) RETURNING postid
                """, (f'RateTest B {i}', f'content b {i}', seed_data['tool_claude_id']))
                pb = cur.fetchone()[0]
                cur.execute("""
                    INSERT INTO matchups (post_a_id, post_b_id, tool_a, tool_b, position_seed)
                    VALUES (%s, %s, %s, %s, 0) RETURNING matchup_id
                """, (pa, pb,
                      min(seed_data['tool_chatgpt_id'], seed_data['tool_claude_id']),
                      max(seed_data['tool_chatgpt_id'], seed_data['tool_claude_id'])))
                extra_mid = cur.fetchone()[0]
                # Insert up to 5 votes per matchup, but stop at 49 total
                cats_to_use = list(db.VOTE_CATEGORIES)
                for cat in cats_to_use:
                    cur.execute("SELECT COUNT(*) FROM votes WHERE user_id = %s AND voted_at > CURRENT_TIMESTAMP - INTERVAL '24 hours'",
                                (seed_data['user_premium_id'],))
                    if cur.fetchone()[0] >= 49:
                        break
                    cur.execute("""
                        INSERT INTO votes (user_id, matchup_id, category, winner_tool, position_a_was_left)
                        VALUES (%s, %s, %s, %s, TRUE)
                    """, (seed_data['user_premium_id'], extra_mid, cat,
                          min(seed_data['tool_chatgpt_id'], seed_data['tool_claude_id'])))

        # Now try to submit 2 more (should exceed 50)
        result = db.batch_submit_votes(
            seed_data['user_premium_id'], mid,
            _make_votes(['overall', 'accuracy'], tool_a), True)

        assert result['success'] is False
        assert result['error']['code'] == 'RATE_LIMITED'
        assert result['error']['details']['limit'] == 50

    def test_rollback_on_failure_no_partial_inserts(self, db_conn, seed_data):
        """If validation fails, no votes should be inserted."""
        mid = _create_matchup(seed_data)
        gemini_id = seed_data['tool_gemini_id']
        # First vote valid, second has invalid winner
        tool_a, _ = _get_tools(mid)
        votes = [
            {'category': 'overall', 'winner_tool': tool_a},
            {'category': 'accuracy', 'winner_tool': gemini_id},  # invalid
        ]

        result = db.batch_submit_votes(
            seed_data['user_premium_id'], mid, votes, True)

        assert result['success'] is False
        # No votes should exist
        db_votes = db.get_user_votes_for_matchup(seed_data['user_premium_id'], mid)
        assert len(db_votes) == 0

    def test_audit_events_logged(self, db_conn, seed_data):
        mid = _create_matchup(seed_data)
        tool_a, _ = _get_tools(mid)
        votes = _make_votes(['overall', 'accuracy'], tool_a)

        db.batch_submit_votes(
            seed_data['user_premium_id'], mid, votes, True,
            metadata={'ip': '127.0.0.1'})

        with db_conn.cursor() as cur:
            cur.execute("""
                SELECT event_type, categories, error_code
                FROM vote_events
                WHERE user_id = %s AND matchup_id = %s AND event_type = 'submit'
                ORDER BY created_at DESC LIMIT 1
            """, (seed_data['user_premium_id'], mid))
            row = cur.fetchone()
            assert row is not None
            assert row[0] == 'submit'
            assert 'overall' in row[1]
            assert row[2] is None  # no error


# ============== Batch Edit Tests ==============

class TestBatchEditVotes:

    def test_edit_within_window(self, db_conn, seed_data):
        mid = _create_matchup(seed_data)
        tool_a, tool_b = _get_tools(mid)

        db.batch_submit_votes(
            seed_data['user_premium_id'], mid,
            _make_votes(['overall'], tool_a), True)

        result = db.batch_edit_votes(
            seed_data['user_premium_id'], mid,
            _make_votes(['overall'], tool_b), True)

        assert result['success'] is True
        assert result['status_code'] == 200

        # Verify winner changed
        votes = db.get_user_votes_for_matchup(seed_data['user_premium_id'], mid)
        overall = [v for v in votes if v['category'] == 'overall'][0]
        assert overall['winner_tool'] == tool_b

    def test_edit_resets_voted_at(self, db_conn, seed_data):
        mid = _create_matchup(seed_data)
        tool_a, tool_b = _get_tools(mid)

        db.batch_submit_votes(
            seed_data['user_premium_id'], mid,
            _make_votes(['overall'], tool_a), True)

        # Backdate the vote slightly
        with db_conn.cursor() as cur:
            cur.execute("""
                UPDATE votes SET voted_at = CURRENT_TIMESTAMP - INTERVAL '2 minutes'
                WHERE user_id = %s AND matchup_id = %s
            """, (seed_data['user_premium_id'], mid))

        result = db.batch_edit_votes(
            seed_data['user_premium_id'], mid,
            _make_votes(['overall'], tool_b), True)

        assert result['success'] is True
        assert result['edit_window_expires_at'] is not None

    def test_edit_locked_vote_rejected(self, db_conn, seed_data):
        mid = _create_matchup(seed_data)
        tool_a, tool_b = _get_tools(mid)

        db.batch_submit_votes(
            seed_data['user_premium_id'], mid,
            _make_votes(['overall'], tool_a), True)

        with db_conn.cursor() as cur:
            cur.execute(
                "UPDATE votes SET locked = TRUE WHERE user_id = %s AND matchup_id = %s",
                (seed_data['user_premium_id'], mid))

        result = db.batch_edit_votes(
            seed_data['user_premium_id'], mid,
            _make_votes(['overall'], tool_b), True)

        assert result['success'] is False
        assert result['error']['code'] == 'VOTE_LOCKED'

    def test_realtime_lock_expired_vote(self, db_conn, seed_data):
        """Vote older than 5 minutes should be auto-locked even if job hasn't run."""
        mid = _create_matchup(seed_data)
        tool_a, tool_b = _get_tools(mid)

        db.batch_submit_votes(
            seed_data['user_premium_id'], mid,
            _make_votes(['overall'], tool_a), True)

        # Backdate vote to 10 minutes ago (past lock window)
        with db_conn.cursor() as cur:
            cur.execute("""
                UPDATE votes SET voted_at = CURRENT_TIMESTAMP - INTERVAL '10 minutes'
                WHERE user_id = %s AND matchup_id = %s
            """, (seed_data['user_premium_id'], mid))

        result = db.batch_edit_votes(
            seed_data['user_premium_id'], mid,
            _make_votes(['overall'], tool_b), True)

        assert result['success'] is False
        assert result['error']['code'] == 'VOTE_LOCKED'

        # Verify vote was opportunistically locked
        votes = db.get_user_votes_for_matchup(seed_data['user_premium_id'], mid)
        assert votes[0]['locked'] is True

    def test_new_category_via_patch_rejected(self, db_conn, seed_data):
        mid = _create_matchup(seed_data)
        tool_a, _ = _get_tools(mid)

        # Submit only 'overall'
        db.batch_submit_votes(
            seed_data['user_premium_id'], mid,
            _make_votes(['overall'], tool_a), True)

        # Try to PATCH with 'accuracy' (never voted on)
        result = db.batch_edit_votes(
            seed_data['user_premium_id'], mid,
            _make_votes(['accuracy'], tool_a), True)

        assert result['success'] is False
        assert result['error']['code'] == 'NEW_VOTE_VIA_PATCH'

    def test_idempotent_edit(self, db_conn, seed_data):
        mid = _create_matchup(seed_data)
        tool_a, _ = _get_tools(mid)

        db.batch_submit_votes(
            seed_data['user_premium_id'], mid,
            _make_votes(['overall'], tool_a), True)

        # PATCH with same winner
        result = db.batch_edit_votes(
            seed_data['user_premium_id'], mid,
            _make_votes(['overall'], tool_a), True)

        assert result['success'] is True
        assert result['status_code'] == 200

    def test_edit_does_not_count_rate_limit(self, db_conn, seed_data):
        """Edits should work even if daily vote count is at limit."""
        mid = _create_matchup(seed_data)
        tool_a, tool_b = _get_tools(mid)

        db.batch_submit_votes(
            seed_data['user_premium_id'], mid,
            _make_votes(['overall'], tool_a), True)

        # Fake 50 votes in the last 24h (at limit)
        with db_conn.cursor() as cur:
            for i in range(10):
                cur.execute("""
                    INSERT INTO Post (Title, Content, Category, tool_id)
                    VALUES (%s, %s, 'Tech', %s) RETURNING postid
                """, (f'EditRate A {i}', f'c {i}', seed_data['tool_chatgpt_id']))
                pa = cur.fetchone()[0]
                cur.execute("""
                    INSERT INTO Post (Title, Content, Category, tool_id)
                    VALUES (%s, %s, 'Tech', %s) RETURNING postid
                """, (f'EditRate B {i}', f'c {i}', seed_data['tool_claude_id']))
                pb = cur.fetchone()[0]
                cur.execute("""
                    INSERT INTO matchups (post_a_id, post_b_id, tool_a, tool_b, position_seed)
                    VALUES (%s, %s, %s, %s, 0) RETURNING matchup_id
                """, (pa, pb,
                      min(seed_data['tool_chatgpt_id'], seed_data['tool_claude_id']),
                      max(seed_data['tool_chatgpt_id'], seed_data['tool_claude_id'])))
                extra_mid = cur.fetchone()[0]
                for cat in db.VOTE_CATEGORIES:
                    cur.execute("SELECT COUNT(*) FROM votes WHERE user_id = %s AND voted_at > CURRENT_TIMESTAMP - INTERVAL '24 hours'",
                                (seed_data['user_premium_id'],))
                    if cur.fetchone()[0] >= 50:
                        break
                    cur.execute("""
                        INSERT INTO votes (user_id, matchup_id, category, winner_tool, position_a_was_left)
                        VALUES (%s, %s, %s, %s, TRUE)
                    """, (seed_data['user_premium_id'], extra_mid, cat,
                          min(seed_data['tool_chatgpt_id'], seed_data['tool_claude_id'])))

        # Edit should still work (no rate limit on edits)
        result = db.batch_edit_votes(
            seed_data['user_premium_id'], mid,
            _make_votes(['overall'], tool_b), True)

        assert result['success'] is True

    def test_audit_events_edit(self, db_conn, seed_data):
        mid = _create_matchup(seed_data)
        tool_a, tool_b = _get_tools(mid)

        db.batch_submit_votes(
            seed_data['user_premium_id'], mid,
            _make_votes(['overall'], tool_a), True)

        db.batch_edit_votes(
            seed_data['user_premium_id'], mid,
            _make_votes(['overall'], tool_b), True)

        with db_conn.cursor() as cur:
            cur.execute("""
                SELECT event_type FROM vote_events
                WHERE user_id = %s AND matchup_id = %s
                ORDER BY created_at
            """, (seed_data['user_premium_id'], mid))
            types = [row[0] for row in cur.fetchall()]
            assert 'submit' in types
            assert 'edit' in types
