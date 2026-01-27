# AI Blog Platform - Deployment Guide

**Version:** 2.0.0  
**Last Updated:** January 24, 2026  
**Target Platform:** Hostinger Cloud Startup

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Local Preparation](#2-local-preparation)
3. [Hostinger Cloud Setup](#3-hostinger-cloud-setup)
4. [Database Setup](#4-database-setup)
5. [Application Deployment](#5-application-deployment)
6. [Secure API Key Configuration](#6-secure-api-key-configuration)
7. [Python Application Setup](#7-python-application-setup)
8. [SSL/HTTPS Configuration](#8-sslhttps-configuration)
9. [Monitoring & Maintenance](#9-monitoring--maintenance)
10. [Troubleshooting](#10-troubleshooting)

---

## 1. Prerequisites

### 1.1 Required Accounts

| Service                 | Purpose     | Sign Up URL                                 |
| ----------------------- | ----------- | ------------------------------------------- |
| Hostinger Cloud Startup | Web hosting | https://www.hostinger.com/cloud-hosting     |
| OpenAI                  | ChatGPT API | https://platform.openai.com/api-keys        |
| Anthropic               | Claude API  | https://console.anthropic.com/settings/keys |
| Google AI               | Gemini API  | https://aistudio.google.com/app/apikey      |
| Together AI             | Llama API   | https://api.together.xyz/settings/api-keys  |
| Mistral AI              | Mistral API | https://console.mistral.ai/api-keys         |
| Jasper AI               | Jasper API  | https://app.jasper.ai/settings/api          |

### 1.2 Hostinger Cloud Startup Features

| Feature            | Specification       |
| ------------------ | ------------------- |
| **RAM**            | 3 GB                |
| **CPU**            | 2 Cores             |
| **Storage**        | 200 GB NVMe SSD     |
| **Bandwidth**      | Unlimited           |
| **Websites**       | 300                 |
| **Free Domain**    | Yes (1 year)        |
| **Free SSL**       | Yes (Let's Encrypt) |
| **Daily Backups**  | Yes                 |
| **SSH Access**     | Yes                 |
| **Python Support** | Yes (via SSH)       |

### 1.3 Local Development Tools

- Git
- Python 3.12+
- SSH client (Windows Terminal, PuTTY, or built-in)

---

## 2. Local Preparation

### 2.1 Ensure `.gitignore` is Configured

Verify `.gitignore` in your project root includes:

```gitignore
# Environment & Secrets - NEVER COMMIT!
.env
*.env
.env.*
!.env.example

# Python
__pycache__/
*.py[cod]
.venv/
venv/
```

### 2.2 Verify No Secrets in Git History

```powershell
# Check if .env was ever committed
git log --all --full-history -- .env

# If found, rotate ALL your API keys immediately!
```

### 2.3 Prepare for MySQL Database

Hostinger Cloud uses MySQL. Update your `database.py` to support MySQL:

```python
# Install MySQL connector
# pip install mysql-connector-python
```

### 2.4 Push to Git Repository

```powershell
git add .
git commit -m "Prepare for Hostinger Cloud deployment"
git push origin main
```

---

## 3. Hostinger Cloud Setup

### 3.1 Access hPanel

1. Log into https://hpanel.hostinger.com
2. Select your Cloud Startup hosting plan
3. Note your **Server IP** and domain settings

### 3.2 Connect Your Domain

1. In hPanel, go to **Domains → yourdomain.com**
2. Point DNS to Hostinger nameservers:
   - `ns1.dns-parking.com`
   - `ns2.dns-parking.com`
3. Or update A record to your Cloud server IP

### 3.3 Enable SSH Access

1. Go to **Advanced → SSH Access**
2. Click **Enable**
3. Note your SSH credentials:
   - **Host:** your server IP or ssh.yourdomain.com
   - **Port:** 65002 (Hostinger's custom SSH port)
   - **Username:** Usually your hPanel username
   - **Password:** Your hPanel password (or set up SSH keys)

### 3.4 Connect via SSH

```powershell
# From Windows Terminal or PowerShell
ssh -p 65002 username@yourdomain.com

# Or using your server IP
ssh -p 65002 username@your-server-ip
```

### 3.5 Set Up SSH Keys (Recommended)

```powershell
# On your local machine, generate SSH key
ssh-keygen -t ed25519 -C "your-email@example.com"

# Copy public key
Get-Content ~/.ssh/id_ed25519.pub | clip
```

In hPanel:

1. Go to **Advanced → SSH Access → SSH Keys**
2. Click **Add SSH Key**
3. Paste your public key

---

## 4. Database Setup

### 4.1 Create MySQL Database

1. In hPanel, go to **Databases → MySQL Databases**
2. Create new database:
   - **Database name:** `aiblog_prod`
   - **Username:** `aiblog_user`
   - **Password:** Generate a strong password
3. Note the **MySQL hostname** (usually `localhost` or provided hostname)

### 4.2 Update Database Configuration

Create a MySQL-compatible version of your database module. Update `config.py`:

```python
# Database settings for MySQL
DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_NAME = os.environ.get('DB_NAME', 'aiblog_prod')
DB_USER = os.environ.get('DB_USER', 'aiblog_user')
DB_PASSWORD = os.environ.get('DB_PASSWORD', '')
```

### 4.3 Create Tables via phpMyAdmin

1. In hPanel, go to **Databases → phpMyAdmin**
2. Select your database
3. Run the following SQL:

```sql
-- Users Table
CREATE TABLE Users (
    user_id INT AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    username VARCHAR(100) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- AITool Table
CREATE TABLE AITool (
    tool_id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    slug VARCHAR(50) NOT NULL UNIQUE,
    description TEXT,
    icon_url VARCHAR(255),
    api_provider VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Post Table
CREATE TABLE Post (
    postid INT AUTO_INCREMENT PRIMARY KEY,
    Title VARCHAR(255) NOT NULL,
    Content TEXT NOT NULL,
    Category VARCHAR(100) NOT NULL,
    tool_id INT,
    CreatedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tool_id) REFERENCES AITool(tool_id)
);

-- Subscription Table
CREATE TABLE Subscription (
    subscription_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    tool_id INT NOT NULL,
    subscribed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES Users(user_id),
    FOREIGN KEY (tool_id) REFERENCES AITool(tool_id),
    UNIQUE KEY unique_subscription (user_id, tool_id)
);

-- Comment Table
CREATE TABLE Comment (
    commentid INT AUTO_INCREMENT PRIMARY KEY,
    postid INT NOT NULL,
    content TEXT NOT NULL,
    CreatedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (postid) REFERENCES Post(postid)
);

-- Insert AI Tools
INSERT INTO AITool (name, slug, description, icon_url, api_provider) VALUES
('ChatGPT (GPT-4o)', 'chatgpt', 'OpenAI''s flagship model - quick, well-researched drafts.', 'bi-chat-dots-fill', 'OpenAI'),
('Claude 3.5 Sonnet', 'claude', 'Anthropic''s advanced AI - nuanced, long-form content.', 'bi-cpu-fill', 'Anthropic'),
('Gemini 1.5 Pro', 'gemini', 'Google''s multimodal AI - data-driven research.', 'bi-google', 'Google'),
('Llama 3.1 405B', 'llama', 'Meta''s open-source powerhouse - technical content.', 'bi-code-slash', 'Meta'),
('Mistral Large 2', 'mistral', 'European AI excellence - fast and multilingual.', 'bi-wind', 'Mistral AI'),
('Jasper', 'jasper', 'Marketing AI specialist - brand-voice content.', 'bi-megaphone-fill', 'Jasper AI');
```

---

## 5. Application Deployment

### 5.1 Connect via SSH

```powershell
ssh -p 65002 username@yourdomain.com
```

### 5.2 Navigate to Web Root

```bash
# Hostinger's web root is typically:
cd ~/domains/yourdomain.com/public_html

# Or for main domain:
cd ~/public_html
```

### 5.3 Clone Your Repository

```bash
# Clone into a subdirectory
git clone https://github.com/yourusername/aiblog.git app
cd app
```

### 5.4 Set Up Python Virtual Environment

```bash
# Check available Python versions
python3 --version

# Create virtual environment
python3 -m venv .venv

# Activate virtual environment
source .venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt

# Install MySQL connector (for MySQL database)
pip install mysql-connector-python pymysql
```

---

## 6. Secure API Key Configuration

### 6.1 Create the `.env` File on Server

```bash
# Make sure you're in your app directory
cd ~/domains/yourdomain.com/public_html/app

# Create .env file
nano .env
```

### 6.2 Add Your Production Configuration

```env
# ============================================
# AI Blog Platform - Production Configuration
# ============================================

# Flask Settings
SECRET_KEY=paste-your-64-character-secret-key-here
FLASK_ENV=production
DEBUG=False

# MySQL Database (from hPanel)
DB_HOST=localhost
DB_NAME=u123456789_aiblog
DB_USER=u123456789_aiblog
DB_PASSWORD=your-database-password-here

# AI Provider API Keys
OPENAI_API_KEY=sk-prod-your-openai-key-here
ANTHROPIC_API_KEY=sk-ant-api03-your-anthropic-key-here
GOOGLE_API_KEY=AIza-your-google-key-here
TOGETHER_API_KEY=your-together-api-key-here
MISTRAL_API_KEY=your-mistral-api-key-here
JASPER_API_KEY=your-jasper-api-key-here
```

### 6.3 Generate a Secure SECRET_KEY

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

### 6.4 Secure the `.env` File (CRITICAL!)

```bash
# Set restrictive permissions
chmod 600 .env

# Verify permissions
ls -la .env
# Should show: -rw------- 1 username username
```

### 6.5 Add `.env` to `.htaccess` Protection

Create or edit `.htaccess` in your app directory:

```bash
nano .htaccess
```

Add:

```apache
# Protect sensitive files
<FilesMatch "^\.env$">
    Order allow,deny
    Deny from all
</FilesMatch>

<FilesMatch "^\.git">
    Order allow,deny
    Deny from all
</FilesMatch>
```

---

## 7. Python Application Setup

### 7.1 Create WSGI Entry Point

Hostinger Cloud uses Passenger for Python apps. Create `passenger_wsgi.py`:

```bash
nano passenger_wsgi.py
```

```python
import sys
import os

# Add your app to the path
INTERP = os.path.expanduser("~/domains/yourdomain.com/public_html/app/.venv/bin/python3")
if sys.executable != INTERP:
    os.execl(INTERP, INTERP, *sys.argv)

# Set the application directory
sys.path.insert(0, os.path.dirname(__file__))

# Load environment variables
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

# Import your Flask app
from app import app as application
```

### 7.2 Alternative: Create `app.cgi` for CGI Mode

If Passenger doesn't work, use CGI:

```bash
nano app.cgi
```

```python
#!/home/username/domains/yourdomain.com/public_html/app/.venv/bin/python3
import sys
import os

sys.path.insert(0, '/home/username/domains/yourdomain.com/public_html/app')
os.chdir('/home/username/domains/yourdomain.com/public_html/app')

from dotenv import load_dotenv
load_dotenv()

from wsgiref.handlers import CGIHandler
from app import app

CGIHandler().run(app)
```

Make it executable:

```bash
chmod +x app.cgi
```

### 7.3 Configure `.htaccess` for Flask

```bash
nano .htaccess
```

```apache
# Protect sensitive files
<FilesMatch "^\.env$">
    Order allow,deny
    Deny from all
</FilesMatch>

<FilesMatch "^\.git">
    Order allow,deny
    Deny from all
</FilesMatch>

# Enable Passenger (if supported)
PassengerEnabled On
PassengerAppRoot /home/username/domains/yourdomain.com/public_html/app
PassengerPython /home/username/domains/yourdomain.com/public_html/app/.venv/bin/python3

# Or use CGI fallback
# RewriteEngine On
# RewriteCond %{REQUEST_FILENAME} !-f
# RewriteRule ^(.*)$ app.cgi/$1 [L]
```

### 7.4 Setup via hPanel (Recommended Method)

1. In hPanel, go to **Advanced → Python**
2. Click **Create Application**
3. Configure:
   - **Python version:** 3.11 or 3.12
   - **Application root:** `/domains/yourdomain.com/public_html/app`
   - **Application URL:** Your domain
   - **Application startup file:** `app.py`
   - **Application entry point:** `app` (the Flask instance)
4. Click **Create**
5. Click **Run pip install** to install requirements.txt

### 7.5 Set Environment Variables in hPanel

1. In the Python app settings, find **Environment variables**
2. Add each variable:

| Variable            | Value               |
| ------------------- | ------------------- |
| `SECRET_KEY`        | your-64-char-secret |
| `DB_HOST`           | localhost           |
| `DB_NAME`           | u123456789_aiblog   |
| `DB_USER`           | u123456789_aiblog   |
| `DB_PASSWORD`       | your-db-password    |
| `OPENAI_API_KEY`    | sk-...              |
| `ANTHROPIC_API_KEY` | sk-ant-...          |
| `GOOGLE_API_KEY`    | AIza...             |
| `TOGETHER_API_KEY`  | ...                 |
| `MISTRAL_API_KEY`   | ...                 |
| `JASPER_API_KEY`    | ...                 |

3. Click **Restart** to apply changes

---

## 8. SSL/HTTPS Configuration

### 8.1 Enable Free SSL

1. In hPanel, go to **Security → SSL**
2. Select your domain
3. Click **Install** for Let's Encrypt SSL
4. Wait for certificate to be issued (usually 1-5 minutes)

### 8.2 Force HTTPS Redirect

Add to your `.htaccess`:

```apache
# Force HTTPS
RewriteEngine On
RewriteCond %{HTTPS} off
RewriteRule ^(.*)$ https://%{HTTP_HOST}%{REQUEST_URI} [L,R=301]
```

### 8.3 Verify SSL

Visit `https://yourdomain.com` and check for the padlock icon.

---

## 9. Monitoring & Maintenance

### 9.1 View Error Logs

```bash
# SSH into server
ssh -p 65002 username@yourdomain.com

# View error logs
tail -f ~/domains/yourdomain.com/logs/error.log

# View access logs
tail -f ~/domains/yourdomain.com/logs/access.log
```

### 9.2 Restart Python Application

In hPanel:

1. Go to **Advanced → Python**
2. Find your application
3. Click **Restart**

Or via SSH:

```bash
touch ~/domains/yourdomain.com/public_html/app/tmp/restart.txt
```

### 9.3 Update Application

```bash
# SSH into server
ssh -p 65002 username@yourdomain.com

# Navigate to app
cd ~/domains/yourdomain.com/public_html/app

# Pull latest changes
git pull origin main

# Activate virtual environment
source .venv/bin/activate

# Install any new dependencies
pip install -r requirements.txt

# Restart (via hPanel or touch restart.txt)
touch tmp/restart.txt
```

### 9.4 Database Backups

Hostinger Cloud includes automatic daily backups. To create manual backup:

1. Go to **Files → Backups**
2. Click **Generate new backup**
3. Or use phpMyAdmin to export database

### 9.5 Monitor API Usage

Set up billing alerts on each provider:

| Provider  | Usage Dashboard                              |
| --------- | -------------------------------------------- |
| OpenAI    | https://platform.openai.com/usage            |
| Anthropic | https://console.anthropic.com/settings/usage |
| Google    | https://console.cloud.google.com/billing     |
| Together  | https://api.together.xyz/settings/billing    |
| Mistral   | https://console.mistral.ai/usage             |

---

## 10. Troubleshooting

### 10.1 500 Internal Server Error

```bash
# Check error logs
tail -50 ~/domains/yourdomain.com/logs/error.log

# Verify Python path in passenger_wsgi.py
which python3

# Check file permissions
ls -la .env
chmod 600 .env
```

### 10.2 Database Connection Error

```bash
# Test database connection
source .venv/bin/activate
python3 -c "
import mysql.connector
conn = mysql.connector.connect(
    host='localhost',
    user='your_db_user',
    password='your_db_password',
    database='your_db_name'
)
print('Connected!' if conn.is_connected() else 'Failed')
"
```

### 10.3 Module Not Found Error

```bash
# Ensure virtual environment is activated
source .venv/bin/activate

# Reinstall requirements
pip install -r requirements.txt
```

### 10.4 Static Files Not Loading

Check `.htaccess` isn't blocking static folder:

```apache
# Allow static files
<Directory "static">
    Allow from all
</Directory>
```

### 10.5 Environment Variables Not Loading

1. Verify `.env` file exists and has correct permissions
2. Check hPanel Python app environment variables
3. Test loading:

```bash
source .venv/bin/activate
python3 -c "from dotenv import load_dotenv; load_dotenv(); import os; print(os.getenv('SECRET_KEY', 'NOT SET'))"
```

---

## Quick Reference

### SSH Connection

```powershell
ssh -p 65002 username@yourdomain.com
```

### File Locations

| Item          | Path                                              |
| ------------- | ------------------------------------------------- |
| Web Root      | `~/domains/yourdomain.com/public_html/`           |
| App Directory | `~/domains/yourdomain.com/public_html/app/`       |
| Error Logs    | `~/domains/yourdomain.com/logs/error.log`         |
| Python venv   | `~/domains/yourdomain.com/public_html/app/.venv/` |

### Key Commands

| Task          | Command                                           |
| ------------- | ------------------------------------------------- |
| Activate venv | `source .venv/bin/activate`                       |
| Install deps  | `pip install -r requirements.txt`                 |
| View logs     | `tail -f ~/domains/yourdomain.com/logs/error.log` |
| Restart app   | Via hPanel or `touch tmp/restart.txt`             |

---

## Security Checklist

- [ ] `.env` file has `600` permissions
- [ ] `.env` protected in `.htaccess`
- [ ] No secrets in git repository
- [ ] SSL/HTTPS enabled and forced
- [ ] Different API keys for dev/production
- [ ] API billing alerts configured
- [ ] Database password is strong
- [ ] `DEBUG=False` in production
- [ ] hPanel 2FA enabled

---

_Deployment Guide for AI Blog Platform on Hostinger Cloud Startup_  
_Last Updated: January 24, 2026_
