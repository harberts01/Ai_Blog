-- =====================================================
-- AI Blog: Add Notifications Table
-- Run this directly in PostgreSQL (pgAdmin, psql, or Dokploy console)
-- =====================================================

-- Create the Notification table
CREATE TABLE IF NOT EXISTS Notification (
    notification_id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES Users(user_id) ON DELETE CASCADE,
    type VARCHAR(50) NOT NULL,
    title VARCHAR(255) NOT NULL,
    message TEXT,
    link VARCHAR(500),
    tool_id INTEGER REFERENCES AITool(tool_id) ON DELETE SET NULL,
    post_id INTEGER REFERENCES Post(postid) ON DELETE SET NULL,
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_notification_user_id ON Notification(user_id);
CREATE INDEX IF NOT EXISTS idx_notification_is_read ON Notification(user_id, is_read);
CREATE INDEX IF NOT EXISTS idx_notification_created_at ON Notification(created_at);

-- Verify table was created
SELECT 'Notification table created successfully!' AS status;
SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'notification';
