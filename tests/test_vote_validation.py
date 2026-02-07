"""Tests for vote casting, locking, and retrieval logic."""
import pytest
import database as db


def _create_test_matchup(seed_data):
    """Helper: create a matchup between chatgpt and claude posts."""
    return db.create_matchup(
        seed_data['post_chatgpt_id'],
        seed_data['post_claude_id']
    )


def _get_matchup_tools(matchup_id):
    """Helper: return (tool_a, tool_b) for a matchup."""
    matchup = db.get_matchup(matchup_id)
    return matchup['tool_a'], matchup['tool_b']


class TestCastVote:
    """Tests for the cast_vote function."""

    def test_premium_user_can_vote(self, db_conn, seed_data):
        """Premium user voting on valid matchup/category should succeed"""
        matchup_id = _create_test_matchup(seed_data)
        tool_a, tool_b = _get_matchup_tools(matchup_id)

        result = db.cast_vote(
            seed_data['user_premium_id'], matchup_id, 'overall', tool_a
        )
        assert result['success'] is True
        assert result['vote_id'] is not None
        assert result['error'] is None

    def test_free_user_rejected(self, db_conn, seed_data):
        """Free-tier user should get premium-required error"""
        matchup_id = _create_test_matchup(seed_data)
        tool_a, _ = _get_matchup_tools(matchup_id)

        result = db.cast_vote(
            seed_data['user_free_id'], matchup_id, 'overall', tool_a
        )
        assert result['success'] is False
        assert 'Premium' in result['error'] or 'premium' in result['error']

    def test_invalid_category_rejected(self, db_conn, seed_data):
        """An invalid category should be rejected"""
        matchup_id = _create_test_matchup(seed_data)
        tool_a, _ = _get_matchup_tools(matchup_id)

        result = db.cast_vote(
            seed_data['user_premium_id'], matchup_id, 'invalid_thing', tool_a
        )
        assert result['success'] is False
        assert 'category' in result['error'].lower()

    def test_all_valid_categories_accepted(self, db_conn, seed_data):
        """Each of the 5 valid categories should work"""
        matchup_id = _create_test_matchup(seed_data)
        tool_a, _ = _get_matchup_tools(matchup_id)

        for category in db.VOTE_CATEGORIES:
            result = db.cast_vote(
                seed_data['user_premium_id'], matchup_id, category, tool_a
            )
            assert result['success'] is True, f"Failed for category: {category}"

    def test_winner_must_be_matchup_tool(self, db_conn, seed_data):
        """Voting for a tool not in the matchup should fail"""
        matchup_id = _create_test_matchup(seed_data)
        # Use gemini which is not in the chatgpt-vs-claude matchup
        gemini_tool_id = seed_data['tool_gemini_id']

        result = db.cast_vote(
            seed_data['user_premium_id'], matchup_id, 'overall', gemini_tool_id
        )
        assert result['success'] is False
        assert 'matchup tools' in result['error'].lower() or 'Winner' in result['error']

    def test_nonexistent_matchup_rejected(self, db_conn, seed_data):
        """Matchup ID 999999 should fail"""
        result = db.cast_vote(
            seed_data['user_premium_id'], 999999, 'overall',
            seed_data['tool_chatgpt_id']
        )
        assert result['success'] is False
        assert 'not found' in result['error'].lower()

    def test_archived_matchup_rejected(self, db_conn, seed_data):
        """Matchup with status='archived' should fail"""
        matchup_id = _create_test_matchup(seed_data)
        tool_a, _ = _get_matchup_tools(matchup_id)

        # Archive the matchup
        with db_conn.cursor() as cursor:
            cursor.execute(
                "UPDATE matchups SET status = 'archived' WHERE matchup_id = %s",
                (matchup_id,)
            )

        result = db.cast_vote(
            seed_data['user_premium_id'], matchup_id, 'overall', tool_a
        )
        assert result['success'] is False
        assert 'not active' in result['error'].lower()

    def test_upsert_updates_unlocked_vote(self, db_conn, seed_data):
        """Second vote for same user/matchup/category should update the winner"""
        matchup_id = _create_test_matchup(seed_data)
        tool_a, tool_b = _get_matchup_tools(matchup_id)

        # First vote for tool_a
        result1 = db.cast_vote(
            seed_data['user_premium_id'], matchup_id, 'overall', tool_a
        )
        assert result1['success'] is True

        # Change vote to tool_b (within lock window)
        result2 = db.cast_vote(
            seed_data['user_premium_id'], matchup_id, 'overall', tool_b
        )
        assert result2['success'] is True

        # Verify the vote was updated
        votes = db.get_user_votes_for_matchup(seed_data['user_premium_id'], matchup_id)
        overall_vote = [v for v in votes if v['category'] == 'overall'][0]
        assert overall_vote['winner_tool'] == tool_b

    def test_locked_vote_cannot_change(self, db_conn, seed_data):
        """Vote with locked=TRUE should return lock error"""
        matchup_id = _create_test_matchup(seed_data)
        tool_a, tool_b = _get_matchup_tools(matchup_id)

        # Cast initial vote
        result = db.cast_vote(
            seed_data['user_premium_id'], matchup_id, 'overall', tool_a
        )
        assert result['success'] is True

        # Manually lock the vote
        with db_conn.cursor() as cursor:
            cursor.execute(
                "UPDATE votes SET locked = TRUE WHERE vote_id = %s",
                (result['vote_id'],)
            )

        # Try to change the locked vote
        result2 = db.cast_vote(
            seed_data['user_premium_id'], matchup_id, 'overall', tool_b
        )
        assert result2['success'] is False
        assert 'locked' in result2['error'].lower()

    def test_position_a_was_left_recorded(self, db_conn, seed_data):
        """Vote should record position_a_was_left based on position_seed + user_id"""
        matchup_id = _create_test_matchup(seed_data)
        tool_a, _ = _get_matchup_tools(matchup_id)

        db.cast_vote(
            seed_data['user_premium_id'], matchup_id, 'overall', tool_a
        )

        votes = db.get_user_votes_for_matchup(seed_data['user_premium_id'], matchup_id)
        assert len(votes) == 1
        assert votes[0]['position_a_was_left'] is not None
        assert isinstance(votes[0]['position_a_was_left'], bool)

    def test_returns_vote_id_on_success(self, db_conn, seed_data):
        """Successful vote should return dict with integer vote_id"""
        matchup_id = _create_test_matchup(seed_data)
        tool_a, _ = _get_matchup_tools(matchup_id)

        result = db.cast_vote(
            seed_data['user_premium_id'], matchup_id, 'overall', tool_a
        )
        assert result['success'] is True
        assert isinstance(result['vote_id'], int)


class TestLockExpiredVotes:
    """Tests for the lock_expired_votes function."""

    def test_locks_old_votes(self, db_conn, seed_data):
        """Votes older than VOTE_LOCK_MINUTES should be locked"""
        matchup_id = _create_test_matchup(seed_data)
        tool_a, _ = _get_matchup_tools(matchup_id)

        db.cast_vote(
            seed_data['user_premium_id'], matchup_id, 'overall', tool_a
        )

        # Backdate the vote to 10 minutes ago
        with db_conn.cursor() as cursor:
            cursor.execute("""
                UPDATE votes SET voted_at = CURRENT_TIMESTAMP - INTERVAL '10 minutes'
                WHERE user_id = %s AND matchup_id = %s
            """, (seed_data['user_premium_id'], matchup_id))

        locked_count = db.lock_expired_votes()
        assert locked_count >= 1

        # Verify vote is now locked
        votes = db.get_user_votes_for_matchup(seed_data['user_premium_id'], matchup_id)
        assert votes[0]['locked'] is True

    def test_does_not_lock_recent_votes(self, db_conn, seed_data):
        """Votes within the lock window should remain unlocked"""
        matchup_id = _create_test_matchup(seed_data)
        tool_a, _ = _get_matchup_tools(matchup_id)

        db.cast_vote(
            seed_data['user_premium_id'], matchup_id, 'overall', tool_a
        )

        # Don't backdate — vote was just created
        locked_count = db.lock_expired_votes()
        # This specific vote should not have been locked
        votes = db.get_user_votes_for_matchup(seed_data['user_premium_id'], matchup_id)
        assert votes[0]['locked'] is False

    def test_already_locked_unaffected(self, db_conn, seed_data):
        """Already-locked votes should not cause errors"""
        matchup_id = _create_test_matchup(seed_data)
        tool_a, _ = _get_matchup_tools(matchup_id)

        db.cast_vote(
            seed_data['user_premium_id'], matchup_id, 'overall', tool_a
        )

        # Lock it manually
        with db_conn.cursor() as cursor:
            cursor.execute("""
                UPDATE votes SET locked = TRUE
                WHERE user_id = %s AND matchup_id = %s
            """, (seed_data['user_premium_id'], matchup_id))

        # Running lock_expired_votes should not error
        count = db.lock_expired_votes()
        assert isinstance(count, int)


class TestGetUserVotesForMatchup:
    """Tests for the get_user_votes_for_matchup function."""

    def test_returns_all_category_votes(self, db_conn, seed_data):
        """Should return votes across all categories for a user/matchup"""
        matchup_id = _create_test_matchup(seed_data)
        tool_a, _ = _get_matchup_tools(matchup_id)

        for category in db.VOTE_CATEGORIES:
            db.cast_vote(
                seed_data['user_premium_id'], matchup_id, category, tool_a
            )

        votes = db.get_user_votes_for_matchup(seed_data['user_premium_id'], matchup_id)
        assert len(votes) == len(db.VOTE_CATEGORIES)
        categories_returned = {v['category'] for v in votes}
        assert categories_returned == set(db.VOTE_CATEGORIES)

    def test_empty_for_no_votes(self, db_conn, seed_data):
        """User with no votes should get empty list"""
        matchup_id = _create_test_matchup(seed_data)
        votes = db.get_user_votes_for_matchup(seed_data['user_premium_id'], matchup_id)
        assert votes == []


class TestGetMatchupVoteCounts:
    """Tests for the get_matchup_vote_counts function."""

    def test_aggregates_correctly(self, db_conn, seed_data):
        """Should return counts grouped by category and tool"""
        matchup_id = _create_test_matchup(seed_data)
        tool_a, _ = _get_matchup_tools(matchup_id)

        db.cast_vote(
            seed_data['user_premium_id'], matchup_id, 'overall', tool_a
        )

        counts = db.get_matchup_vote_counts(matchup_id)
        assert 'overall' in counts
        assert tool_a in counts['overall']
        assert counts['overall'][tool_a] == 1

    def test_empty_for_no_votes(self, db_conn, seed_data):
        """Should return empty dict when no votes exist"""
        matchup_id = _create_test_matchup(seed_data)
        counts = db.get_matchup_vote_counts(matchup_id)
        assert counts == {}
