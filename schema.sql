-- PostgreSQL Schema for AI Blog
-- Run this script to create the database and tables

-- Create database (run separately as postgres superuser if needed)
-- CREATE DATABASE ai_blog;

-- Connect to ai_blog database before running the rest

-- ============== AI Tools Table ==============
CREATE TABLE IF NOT EXISTS AITool (
    tool_id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    icon_url VARCHAR(500),
    api_provider VARCHAR(50)
);

-- ============== Users Table ==============
CREATE TABLE IF NOT EXISTS Users (
    user_id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    username VARCHAR(100) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    is_admin BOOLEAN DEFAULT FALSE,
    email_notifications BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============== Posts Table ==============
CREATE TABLE IF NOT EXISTS Post (
    postid SERIAL PRIMARY KEY,
    Title VARCHAR(500) NOT NULL,
    Content TEXT,
    Category VARCHAR(100),
    CreatedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    tool_id INTEGER REFERENCES AITool(tool_id)
);

-- ============== Subscriptions Table ==============
CREATE TABLE IF NOT EXISTS Subscription (
    subscription_id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES Users(user_id) ON DELETE CASCADE,
    tool_id INTEGER NOT NULL REFERENCES AITool(tool_id) ON DELETE CASCADE,
    subscribed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, tool_id)
);

-- ============== Comments Table ==============
CREATE TABLE IF NOT EXISTS Comment (
    commentid SERIAL PRIMARY KEY,
    postid INTEGER NOT NULL REFERENCES Post(postid) ON DELETE CASCADE,
    user_id INTEGER REFERENCES Users(user_id) ON DELETE SET NULL,
    parent_id INTEGER REFERENCES Comment(commentid) ON DELETE CASCADE,
    content TEXT NOT NULL,
    CreatedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_spam BOOLEAN DEFAULT FALSE
);

-- ============== Bookmarks Table ==============
CREATE TABLE IF NOT EXISTS Bookmark (
    bookmark_id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES Users(user_id) ON DELETE CASCADE,
    post_id INTEGER NOT NULL REFERENCES Post(postid) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, post_id)
);

-- ============== AI Comparison Tables ==============
CREATE TABLE IF NOT EXISTS Comparison (
    comparison_id SERIAL PRIMARY KEY,
    topic VARCHAR(500) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ComparisonPost (
    id SERIAL PRIMARY KEY,
    comparison_id INTEGER NOT NULL REFERENCES Comparison(comparison_id) ON DELETE CASCADE,
    post_id INTEGER NOT NULL REFERENCES Post(postid) ON DELETE CASCADE,
    UNIQUE(comparison_id, post_id)
);

CREATE TABLE IF NOT EXISTS Vote (
    vote_id SERIAL PRIMARY KEY,
    comparison_id INTEGER NOT NULL REFERENCES Comparison(comparison_id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES Users(user_id) ON DELETE SET NULL,
    post_id INTEGER NOT NULL REFERENCES Post(postid) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(comparison_id, user_id)
);

-- ============== In-App Notifications Table ==============
CREATE TABLE IF NOT EXISTS Notification (
    notification_id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES Users(user_id) ON DELETE CASCADE,
    type VARCHAR(50) NOT NULL,  -- 'new_post', 'comment_reply', 'system', etc.
    title VARCHAR(255) NOT NULL,
    message TEXT,
    link VARCHAR(500),  -- URL to navigate to when clicked
    tool_id INTEGER REFERENCES AITool(tool_id) ON DELETE SET NULL,
    post_id INTEGER REFERENCES Post(postid) ON DELETE SET NULL,
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_notification_user_id ON Notification(user_id);
CREATE INDEX IF NOT EXISTS idx_notification_is_read ON Notification(user_id, is_read);
CREATE INDEX IF NOT EXISTS idx_notification_created_at ON Notification(created_at);

-- ============== Indexes for Performance ==============
CREATE INDEX IF NOT EXISTS idx_post_tool_id ON Post(tool_id);
CREATE INDEX IF NOT EXISTS idx_post_created_at ON Post(CreatedAt);
CREATE INDEX IF NOT EXISTS idx_subscription_user_id ON Subscription(user_id);
CREATE INDEX IF NOT EXISTS idx_subscription_tool_id ON Subscription(tool_id);
CREATE INDEX IF NOT EXISTS idx_comment_postid ON Comment(postid);
CREATE INDEX IF NOT EXISTS idx_users_email ON Users(email);

-- ============== API Usage Tracking ==============
CREATE TABLE IF NOT EXISTS APIUsage (
    usage_id SERIAL PRIMARY KEY,
    tool_id INTEGER REFERENCES AITool(tool_id),
    provider VARCHAR(50) NOT NULL,
    model VARCHAR(100) NOT NULL,
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    estimated_cost DECIMAL(10, 6) DEFAULT 0,
    success BOOLEAN DEFAULT TRUE,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_api_usage_tool_id ON APIUsage(tool_id);
CREATE INDEX IF NOT EXISTS idx_api_usage_created_at ON APIUsage(created_at);

-- ============== Sample AI Tools Data ==============
INSERT INTO AITool (name, slug, description, icon_url, api_provider) VALUES
    ('ChatGPT (GPT-4o)', 'chatgpt', 'OpenAI''s most advanced language model', '/static/icons/chatgpt.png', 'openai'),
    ('Claude 3.5 Sonnet', 'claude', 'Anthropic''s thoughtful AI assistant', '/static/icons/claude.png', 'anthropic'),
    ('Gemini 1.5 Pro', 'gemini', 'Google''s multimodal AI model', '/static/icons/gemini.png', 'google'),
    ('Llama 3.1 405B', 'llama', 'Meta''s open-source large language model (Coming Soon)', '/static/icons/llama.png', 'together'),
    ('Grok 3', 'grok', 'xAI''s witty truth-seeking AI', '/static/icons/grok.png', 'xai')
ON CONFLICT (slug) DO NOTHING;
