import requests
import db
import os
from flask import Flask, render_template, request
from openai import OpenAI

app = Flask(__name__)
url = "https://api.openai.com/v1/chat/completions"
API_KEY = os.environ["OPENAI_API_KEY"]

client = OpenAI(api_key=API_KEY)

@app.route("/")
def home():
    posts = fetch_posts()
    generated_post = generate_post()
    print(generated_post)
    return render_template("index.html", posts=posts)

@app.route("/submit", methods=["POST"])
def submit():
    # Capture form data
    title = request.form.get("title")
    content = request.form.get("content")
    category = request.form.get("category")
    tags = request.form.get("tags").split(",")  # Assuming tags are comma-separated

    # Assign input data to the data dictionary
    data = {
        "title": title,
        "content": content,
        "category": category,
        "tags": tags
    }

    # Insert the data into the database
    insert_blog_post(data)

    return render_template("index.html", posts=fetch_posts())

def insert_blog_post(data):
    cursor = db.conn.cursor()
    
    # Dynamically build the SQL query
    columns = ', '.join(data.keys())
    placeholders = ', '.join(['?'] * len(data))
    sql = f"INSERT INTO Post ({columns}) VALUES ({placeholders})"
    
    # Execute the query with the data values
    cursor.execute(sql, tuple(data.values()))
    
    db.conn.commit()
    db.conn.close()

def fetch_posts():
    cursor = db.conn.cursor()
    cursor.execute("SELECT Title, Content, Category, Tags FROM Post")
    rows = cursor.fetchall()
    posts = []
    for row in rows:
        posts.append({
            "title": row[0],
            "content": row[1],
            "category": row[2],
            "tags": row[3].split(",")  # Assuming tags are stored as comma-separated values
        })
    
    return posts

# @app.route("/generate_post")
def generate_post():
    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "user",
                "content": "Generate a blog post with the following details:\n"
                           "- Title: A brief and catchy title for the blog post.\n"
                           "- Content: A detailed and informative content for the blog post.\n"
                           "- Category: A relevant category for the blog post.\n"
                           "- Tags: A list of comma-separated tags related to the blog post.\n"
                           "The generated blog post should be in the following format:\n"
                           "Title: [Title]\n"
                           "Content: [Content]\n"
                           "Category: [Category]\n"
                           "Tags: [Tag1, Tag2, Tag3, ...]"
            }
        ]
    )
    response = completion.choices[0].message['content']
    return response

if __name__ == "__main__":
    app.run(debug=True)