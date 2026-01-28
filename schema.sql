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
    content TEXT NOT NULL,
    CreatedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_spam BOOLEAN DEFAULT FALSE
);

-- ============== Indexes for Performance ==============
CREATE INDEX IF NOT EXISTS idx_post_tool_id ON Post(tool_id);
CREATE INDEX IF NOT EXISTS idx_post_created_at ON Post(CreatedAt);
CREATE INDEX IF NOT EXISTS idx_subscription_user_id ON Subscription(user_id);
CREATE INDEX IF NOT EXISTS idx_subscription_tool_id ON Subscription(tool_id);
CREATE INDEX IF NOT EXISTS idx_comment_postid ON Comment(postid);
CREATE INDEX IF NOT EXISTS idx_users_email ON Users(email);

-- ============== Sample AI Tools Data ==============
INSERT INTO AITool (name, slug, description, icon_url, api_provider) VALUES
    ('ChatGPT (GPT-4o)', 'chatgpt', 'OpenAI''s most advanced language model', '/static/icons/chatgpt.png', 'openai'),
    ('Claude 3.5 Sonnet', 'claude', 'Anthropic''s thoughtful AI assistant', '/static/icons/claude.png', 'anthropic'),
    ('Gemini 1.5 Pro', 'gemini', 'Google''s multimodal AI model', '/static/icons/gemini.png', 'google'),
    ('Llama 3.1 405B', 'llama', 'Meta''s open-source large language model', '/static/icons/llama.png', 'together'),
    ('Mistral Large 2', 'mistral', 'European AI with multilingual capabilities', '/static/icons/mistral.png', 'mistral'),
    ('Jasper', 'jasper', 'AI-powered marketing content platform', '/static/icons/jasper.png', 'jasper')
ON CONFLICT (slug) DO NOTHING;
