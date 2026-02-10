-- Close all matchups where the two posts belong to different categories.
-- Vote history is preserved; only the status is changed.

-- Preview what will be affected:
SELECT m.matchup_id, m.status,
       pa.postid AS post_a, pa.Category AS cat_a, ta.name AS tool_a,
       pb.postid AS post_b, pb.Category AS cat_b, tb.name AS tool_b
FROM matchups m
JOIN Post pa ON m.post_a_id = pa.postid
JOIN Post pb ON m.post_b_id = pb.postid
JOIN AITool ta ON m.tool_a = ta.tool_id
JOIN AITool tb ON m.tool_b = tb.tool_id
WHERE pa.Category != pb.Category
ORDER BY m.matchup_id;

-- Close the cross-category matchups:
UPDATE matchups
SET status = 'closed', updated_at = CURRENT_TIMESTAMP
WHERE matchup_id IN (
    SELECT m.matchup_id
    FROM matchups m
    JOIN Post pa ON m.post_a_id = pa.postid
    JOIN Post pb ON m.post_b_id = pb.postid
    WHERE pa.Category != pb.Category
      AND m.status != 'closed'
);
