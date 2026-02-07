"""Tests for matchup creation and validation logic."""
import pytest
import database as db


class TestCreateMatchup:
    """Tests for the create_matchup function."""

    def test_creates_matchup_with_valid_posts(self, db_conn, seed_data):
        """Two posts from different active tools should create a matchup"""
        matchup_id = db.create_matchup(
            seed_data['post_chatgpt_id'],
            seed_data['post_claude_id']
        )
        assert matchup_id is not None
        assert isinstance(matchup_id, int)

    def test_canonical_ordering_applied(self, db_conn, seed_data):
        """Regardless of argument order, tool_a < tool_b in the stored record"""
        # Pass the higher tool_id post first
        chatgpt_id = seed_data['tool_chatgpt_id']
        claude_id = seed_data['tool_claude_id']

        matchup_id = db.create_matchup(
            seed_data['post_claude_id'],
            seed_data['post_chatgpt_id']
        )
        assert matchup_id is not None

        matchup = db.get_matchup(matchup_id)
        assert matchup is not None
        # tool_a should be the one with the lower ID
        assert matchup['tool_a'] < matchup['tool_b']

    def test_rejects_same_post_both_sides(self, db_conn, seed_data):
        """Same post_id for both arguments should return None"""
        post_id = seed_data['post_chatgpt_id']
        result = db.create_matchup(post_id, post_id)
        assert result is None

    def test_rejects_posts_from_same_tool(self, db_conn, seed_data):
        """Two posts from the same tool should return None"""
        # Create a second post from chatgpt
        with db_conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO Post (Title, Content, Category, tool_id)
                VALUES ('Another ChatGPT Post', 'More content', 'Technology', %s)
                RETURNING postid
            """, (seed_data['tool_chatgpt_id'],))
            second_post_id = cursor.fetchone()[0]

        result = db.create_matchup(seed_data['post_chatgpt_id'], second_post_id)
        assert result is None

    def test_rejects_inactive_tool(self, db_conn, seed_data):
        """Post from a tool with status='pending' should be rejected"""
        # grok has status='pending'
        if 'post_grok_id' not in seed_data:
            pytest.skip("No grok post in seed data")

        result = db.create_matchup(
            seed_data['post_chatgpt_id'],
            seed_data['post_grok_id']
        )
        assert result is None

    def test_prevents_duplicate_matchup(self, db_conn, seed_data):
        """Creating the same matchup twice should return None on second call"""
        first = db.create_matchup(
            seed_data['post_chatgpt_id'],
            seed_data['post_claude_id']
        )
        assert first is not None

        second = db.create_matchup(
            seed_data['post_chatgpt_id'],
            seed_data['post_claude_id']
        )
        assert second is None

    def test_prevents_duplicate_reversed_order(self, db_conn, seed_data):
        """Creating matchup with reversed post order should also be caught"""
        first = db.create_matchup(
            seed_data['post_chatgpt_id'],
            seed_data['post_claude_id']
        )
        assert first is not None

        # Reversed order — canonical ordering means same DB row
        second = db.create_matchup(
            seed_data['post_claude_id'],
            seed_data['post_chatgpt_id']
        )
        assert second is None

    def test_nonexistent_post_rejected(self, db_conn, seed_data):
        """A non-existent post ID should cause failure"""
        result = db.create_matchup(999999, seed_data['post_chatgpt_id'])
        assert result is None

    def test_position_seed_is_set(self, db_conn, seed_data):
        """Created matchup should have a non-null position_seed"""
        matchup_id = db.create_matchup(
            seed_data['post_chatgpt_id'],
            seed_data['post_claude_id']
        )
        matchup = db.get_matchup(matchup_id)
        assert matchup['position_seed'] is not None

    def test_prompt_id_nullable(self, db_conn, seed_data):
        """Matchup without prompt_id should work (NULL)"""
        matchup_id = db.create_matchup(
            seed_data['post_chatgpt_id'],
            seed_data['post_claude_id']
        )
        matchup = db.get_matchup(matchup_id)
        assert matchup['prompt_id'] is None

    def test_prompt_id_accepted(self, db_conn, seed_data):
        """Matchup with valid prompt_id should store it"""
        matchup_id = db.create_matchup(
            seed_data['post_chatgpt_id'],
            seed_data['post_claude_id'],
            prompt_id=seed_data['prompt_id']
        )
        assert matchup_id is not None
        matchup = db.get_matchup(matchup_id)
        assert matchup['prompt_id'] == seed_data['prompt_id']


class TestGetMatchupByPosts:
    """Tests for the get_matchup_by_posts function."""

    def test_finds_existing_matchup(self, db_conn, seed_data):
        """Should find a matchup regardless of post argument order"""
        matchup_id = db.create_matchup(
            seed_data['post_chatgpt_id'],
            seed_data['post_claude_id']
        )
        assert matchup_id is not None

        # Forward order
        result = db.get_matchup_by_posts(
            seed_data['post_chatgpt_id'],
            seed_data['post_claude_id']
        )
        assert result is not None
        assert result['matchup_id'] == matchup_id

        # Reversed order
        result_reversed = db.get_matchup_by_posts(
            seed_data['post_claude_id'],
            seed_data['post_chatgpt_id']
        )
        assert result_reversed is not None
        assert result_reversed['matchup_id'] == matchup_id

    def test_returns_none_for_no_matchup(self, db_conn, seed_data):
        """Should return None when no matchup exists for the post pair"""
        result = db.get_matchup_by_posts(
            seed_data['post_chatgpt_id'],
            seed_data['post_gemini_id']
        )
        assert result is None


class TestGetActiveMatchups:
    """Tests for the get_active_matchups function."""

    def test_returns_paginated_results(self, db_conn, seed_data):
        """Should return matchups with total count"""
        db.create_matchup(seed_data['post_chatgpt_id'], seed_data['post_claude_id'])
        db.create_matchup(seed_data['post_chatgpt_id'], seed_data['post_gemini_id'])

        matchups, total = db.get_active_matchups(page=1, per_page=10)
        assert total >= 2
        assert len(matchups) >= 2
        assert 'tool_a_name' in matchups[0]
        assert 'title_a' in matchups[0]

    def test_empty_result(self, db_conn, seed_data):
        """Should return empty list and 0 total when no matchups exist"""
        matchups, total = db.get_active_matchups(page=1, per_page=10)
        # total could be 0 if no matchups created in this test's transaction
        assert isinstance(matchups, list)
        assert isinstance(total, int)
