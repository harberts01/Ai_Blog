"""
Seed matchups for all valid post pairs (posts from different AI tools).
Run once in production to generate all possible matchups.

Usage: python seed_matchups.py
"""
from itertools import combinations
from database import get_connection, create_matchup


def get_all_post_ids_with_tools():
    """Fetch all post IDs grouped by tool_id."""
    connection = get_connection()
    if not connection:
        print("ERROR: Could not connect to database")
        return []
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT p.postid, p.tool_id, t.name, p.Category
                FROM Post p
                JOIN AITool t ON p.tool_id = t.tool_id
                WHERE t.status = 'active'
                ORDER BY p.tool_id, p.postid
            """)
            return cursor.fetchall()
    finally:
        connection.close()


def main():
    posts = get_all_post_ids_with_tools()
    if not posts:
        print("No posts found.")
        return

    print(f"Found {len(posts)} posts:")
    for post_id, tool_id, tool_name, category in posts:
        print(f"  Post {post_id} — {tool_name} (tool_id={tool_id}, category={category})")

    created = 0
    skipped = 0

    for (id_a, tool_a, name_a, cat_a), (id_b, tool_b, name_b, cat_b) in combinations(posts, 2):
        if tool_a == tool_b:
            continue  # skip same-tool pairs
        if cat_a != cat_b:
            continue  # skip different-category pairs

        matchup_id = create_matchup(id_a, id_b)
        if matchup_id:
            print(f"  Created matchup {matchup_id}: Post {id_a} ({name_a}) vs Post {id_b} ({name_b}) [{cat_a}]")
            created += 1
        else:
            skipped += 1

    print(f"\nDone! Created {created} matchups, skipped {skipped} (duplicates or invalid).")


if __name__ == "__main__":
    main()
