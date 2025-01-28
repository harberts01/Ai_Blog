import requests #provides a way to send HTTP requests to a web server
import db 
import os #a way to interact with the operating system
import re #regular expression matching operations
import schedule 
import time 
import threading #provides a way to run multiple threads (tasks) while the main thread is running
from flask import Flask, render_template, request
from openai import OpenAI

app = Flask(__name__)

API_KEY = os.environ["OPENAI_API_KEY"]

client = OpenAI(api_key=API_KEY)

def get_db_connection():
    return db.conn

@app.route("/")
def home():
    posts = fetch_posts()
    return render_template("index.html", posts=posts)

#TODO: create a route for the read more button that will display the full blog post
   

#TODO: Create a function that inserts comments into the database
def insert_comment(data):
    conn = get_db_connection()
    with conn.cursor() as cursor:
        postid = data.get("postid")
        content = data.get("comment")
        if not postid or not content:
            raise ValueError("Missing postid or content in the form data")

        sql = "INSERT INTO Comment (postid, content) VALUES (%s, %s)"
        cursor.execute(sql, (postid, content))
        db.conn.commit()

#TODO: Create a function for like/dislike functionality

#TODO: Create a function that retreives the comments from the database and associates them with the blog post they belong to



def insert_blog_post(data):
   conn = get_db_connection()
   with conn.cursor() as cursor:

    columns = ', '.join(data.keys())
    placeholders = ', '.join(['?'] * len(data))
    sql = f"INSERT INTO Post ({columns}) VALUES ({placeholders})"
    
    cursor.execute(sql, tuple(data.values()))
    
    db.conn.commit()
 

def fetch_posts():
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute("SELECT Title, Content, Category, Tags FROM Post")
        rows = cursor.fetchall()
        posts = []
        for row in rows:
            posts.append({
                "title": row[0],
                "content": row[1],
                "category": row[2],
                # "tags": row[3].split(",")
            })
    
    
    return posts


def generate_post():
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute("SELECT CATEGORY FROM Post WHERE POSTID = (SELECT MAX(POSTID) FROM Post)")
        previous_category = cursor.fetchall()
        cursor.execute("SELECT Title FROM Post")
        previous_titles = [title[0] for title in cursor.fetchall()]

    
    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "user",
                "content": "Generate a blog post with the following details:\n"
                           f"- Title: A brief and catchy title for the blog post. Must be a different title from {previous_titles}\n"
                           "- Content: A detailed and informative content for the blog post, formatted in HTML minus metadata.\n"
                           f"- Category: A relevant category for the blog post. Must be a different category from {previous_category}\n"
                        #    "- Tags: A list of comma-separated tags related to the blog post.\n"
                           "The generated blog post should be in the following format:\n"
                           "Title: [Title]\n"
                           "Content: [Content]\n"
                           "Category: [Category]\n"
                        #    "Tags: [Tag1, Tag2, Tag3, ...]"
            }
        ]
    )
    response = completion.choices[0].message.content

    lines = response.split("\n")
    data = {}
    content_lines = []
    for line in lines:
        if line.startswith("Title:"):
            data["title"] = line[len("Title:"):].strip()
        elif line.startswith("Content:"):
            content_lines.append(line[len("Content:"):].strip())
        elif line.startswith("Category:"):
            data["category"] = line[len("Category:"):].strip()
        elif content_lines:
            content_lines.append(line.strip())
        # elif line.startswith("Tags:"):
        #     data["tags"] = [tag.strip() for tag in line[len("Tags:"):].strip().split(",")]

    content = "\n".join(content_lines)

    
    match = re.search(r'(<.*?>.*<\/.*?>)', content, re.DOTALL)
    if match:
        data["content"] = match.group(1)
    else:
        data["content"] = content

    
    if not data["title"] or not data["content"] or not data["category"]:
        print("Generated post contains NULL values. Skipping database insertion.")
    else:
        
        insert_blog_post(data)

    return response

#Schedule the generation of a blog post every 5 minutes:
schedule.every(1).minute.do(generate_post)

scheduler_active = False

def run_scheduler():
    while scheduler_active == True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == "__main__":
    scheduler_thread = threading.Thread(target=run_scheduler)
    scheduler_thread.start()
    app.run(debug=True)
    
    