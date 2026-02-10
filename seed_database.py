"""
Database Seeder for AI Blog
============================
Populates the database with sample data for development and testing.

Usage: python seed_database.py
"""

import psycopg2
from config import Config
from datetime import datetime, timedelta
import random
from werkzeug.security import generate_password_hash

# Database connection
def get_connection():
    return psycopg2.connect(
        host=Config.DB_HOST,
        port=Config.DB_PORT,
        database=Config.DB_NAME,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD
    )

# ============================================
# Sample Data
# ============================================

SAMPLE_USERS = [
    {
        "username": "admin",
        "email": "admin@aiblog.com",
        "password": "admin123",
        "is_admin": True,
        "is_active": True,
        "email_notifications": True
    },
    {
        "username": "johndoe",
        "email": "john@example.com",
        "password": "password123",
        "is_admin": False,
        "is_active": True,
        "email_notifications": True
    },
    {
        "username": "janedoe",
        "email": "jane@example.com",
        "password": "password123",
        "is_admin": False,
        "is_active": True,
        "email_notifications": False
    },
    {
        "username": "techwriter",
        "email": "tech@example.com",
        "password": "password123",
        "is_admin": False,
        "is_active": True,
        "email_notifications": True
    }
]

# Posts for each AI tool
SAMPLE_POSTS = {
    "chatgpt": [
        {
            "title": "Getting Started with ChatGPT: A Comprehensive Beginner's Guide",
            "content": """
<h2>Introduction to ChatGPT</h2>
<p>ChatGPT is a powerful AI language model developed by OpenAI that has revolutionized how we interact with artificial intelligence. Whether you're looking to boost your productivity, learn new concepts, or simply explore the possibilities of AI, this guide will help you get started.</p>

<h2>Key Features of ChatGPT</h2>
<ul>
    <li><strong>Natural Language Understanding:</strong> ChatGPT can understand and respond to complex queries in natural language</li>
    <li><strong>Code Generation:</strong> Generate, debug, and explain code in multiple programming languages</li>
    <li><strong>Creative Writing:</strong> Help with stories, poems, scripts, and other creative content</li>
    <li><strong>Language Translation:</strong> Translate text between numerous languages</li>
    <li><strong>Research Assistant:</strong> Summarize articles, explain concepts, and answer questions</li>
</ul>

<h2>Best Practices for Prompting</h2>
<p>The key to getting great results from ChatGPT is crafting effective prompts. Here are some tips:</p>

<h3>Be Specific</h3>
<p>Instead of asking "Tell me about Python," try "Explain Python list comprehensions with three practical examples for data processing."</p>

<h3>Provide Context</h3>
<p>Give ChatGPT the background information it needs to give you a relevant answer.</p>

<h3>Use Examples</h3>
<p>Show ChatGPT what you want by providing examples of the output format you're looking for.</p>

<pre><code>Example prompt:
"Write a Python function that takes a list of numbers and returns 
the sum of all even numbers. Include error handling and docstrings."</code></pre>

<h2>Common Use Cases</h2>
<ol>
    <li>Writing and editing emails</li>
    <li>Debugging code</li>
    <li>Learning new topics</li>
    <li>Brainstorming ideas</li>
    <li>Creating outlines and drafts</li>
</ol>

<h2>Conclusion</h2>
<p>ChatGPT is a versatile tool that can significantly enhance your productivity. Start with simple prompts and gradually explore more complex interactions as you become comfortable with the platform.</p>
""",
            "excerpt": "Learn how to effectively use ChatGPT with this comprehensive beginner's guide covering key features, prompting strategies, and common use cases."
        },
        {
            "title": "10 Advanced ChatGPT Prompting Techniques for Power Users",
            "content": """
<h2>Taking Your ChatGPT Skills to the Next Level</h2>
<p>Once you've mastered the basics, these advanced techniques will help you unlock ChatGPT's full potential.</p>

<h2>1. Chain of Thought Prompting</h2>
<p>Ask ChatGPT to explain its reasoning step by step:</p>
<pre><code>"Solve this problem step by step, showing your reasoning at each stage..."</code></pre>

<h2>2. Role-Based Prompting</h2>
<p>Assign ChatGPT a specific role or persona:</p>
<pre><code>"Act as a senior software architect and review this code for potential issues..."</code></pre>

<h2>3. Few-Shot Learning</h2>
<p>Provide examples of the input-output format you want:</p>
<pre><code>Input: "happy" → Output: "joyful, elated, cheerful"
Input: "sad" → Output: "melancholy, dejected, gloomy"
Input: "angry" → Output: </code></pre>

<h2>4. Constraint-Based Prompting</h2>
<p>Set specific constraints for the output:</p>
<pre><code>"Explain quantum computing in exactly 100 words, suitable for a 10-year-old."</code></pre>

<h2>5. Iterative Refinement</h2>
<p>Build on previous responses to refine results:</p>
<ul>
    <li>Start with a broad request</li>
    <li>Ask for modifications based on the output</li>
    <li>Continue refining until satisfied</li>
</ul>

<h2>6. Template Filling</h2>
<p>Provide a template for ChatGPT to complete:</p>
<pre><code>Fill in this template:
Product: [NAME]
Target Audience: [AUDIENCE]
Key Benefits: [3 BENEFITS]
Call to Action: [CTA]</code></pre>

<h2>7. Socratic Method</h2>
<p>Ask ChatGPT to help you learn through questions rather than direct answers.</p>

<h2>8. Multi-Perspective Analysis</h2>
<p>Request analysis from multiple viewpoints:</p>
<pre><code>"Analyze this business decision from the perspectives of: 
1) A financial analyst
2) A customer
3) An employee"</code></pre>

<h2>9. Output Formatting</h2>
<p>Specify exact output formats like JSON, markdown tables, or bullet points.</p>

<h2>10. Meta-Prompting</h2>
<p>Ask ChatGPT to help you write better prompts:</p>
<pre><code>"Help me write a better prompt for generating marketing copy for a SaaS product."</code></pre>

<h2>Conclusion</h2>
<p>Mastering these techniques will dramatically improve your results with ChatGPT. Practice regularly and experiment with combining different approaches.</p>
""",
            "excerpt": "Discover 10 advanced prompting techniques including chain of thought, role-based prompting, and few-shot learning to become a ChatGPT power user."
        }
    ],
    "claude": [
        {
            "title": "Why Claude is Perfect for Long-Form Content Analysis",
            "content": """
<h2>Claude's Extended Context Window Advantage</h2>
<p>Anthropic's Claude stands out in the AI assistant landscape with its impressive context window, making it ideal for analyzing lengthy documents, codebases, and research papers.</p>

<h2>What Makes Claude Different</h2>
<p>Claude's key differentiators include:</p>
<ul>
    <li><strong>200K Token Context:</strong> Analyze entire books or large codebases in a single conversation</li>
    <li><strong>Constitutional AI:</strong> Built with safety and helpfulness as core principles</li>
    <li><strong>Nuanced Reasoning:</strong> Excellent at handling complex, multi-step problems</li>
    <li><strong>Honest Uncertainty:</strong> Claude acknowledges when it's unsure rather than making things up</li>
</ul>

<h2>Best Use Cases for Claude</h2>

<h3>Document Analysis</h3>
<p>Upload lengthy documents and ask Claude to:</p>
<ul>
    <li>Summarize key points</li>
    <li>Extract specific information</li>
    <li>Compare multiple documents</li>
    <li>Identify inconsistencies or gaps</li>
</ul>

<h3>Code Review</h3>
<p>Claude excels at reviewing large codebases:</p>
<pre><code>Prompt: "Review this entire repository for:
1. Security vulnerabilities
2. Performance bottlenecks  
3. Code style inconsistencies
4. Missing error handling"</code></pre>

<h3>Research Synthesis</h3>
<p>Combine insights from multiple research papers into coherent summaries and analyses.</p>

<h2>Tips for Working with Claude</h2>
<ol>
    <li>Provide clear context about your goals</li>
    <li>Break complex tasks into subtasks</li>
    <li>Ask for reasoning and citations</li>
    <li>Use Claude's ability to maintain context across long conversations</li>
</ol>

<h2>Claude vs ChatGPT</h2>
<p>While both are excellent, Claude particularly shines when you need:</p>
<ul>
    <li>Analysis of very long documents</li>
    <li>Careful, nuanced responses</li>
    <li>Tasks requiring sustained context</li>
</ul>

<h2>Conclusion</h2>
<p>Claude's extended context window and thoughtful design make it an invaluable tool for anyone working with large amounts of text or code.</p>
""",
            "excerpt": "Explore why Claude's 200K token context window and thoughtful design make it the ideal choice for analyzing lengthy documents, codebases, and research papers."
        },
        {
            "title": "Claude's Artifacts Feature: A Game-Changer for Developers",
            "content": """
<h2>Introduction to Claude Artifacts</h2>
<p>Claude's Artifacts feature allows you to create, view, and iterate on code, documents, and visualizations in a dedicated workspace alongside your conversation.</p>

<h2>What Are Artifacts?</h2>
<p>Artifacts are standalone pieces of content that Claude can create:</p>
<ul>
    <li><strong>Code:</strong> Complete, runnable applications</li>
    <li><strong>Documents:</strong> Markdown, HTML, or plain text</li>
    <li><strong>Diagrams:</strong> SVG visualizations and charts</li>
    <li><strong>React Components:</strong> Interactive UI components</li>
</ul>

<h2>Creating Your First Artifact</h2>
<p>Simply ask Claude to create something substantial:</p>
<pre><code>"Create a React component for a todo list with add, complete, and delete functionality."</code></pre>

<h2>Key Benefits</h2>

<h3>1. Visual Preview</h3>
<p>See your code rendered in real-time without leaving the conversation.</p>

<h3>2. Easy Iteration</h3>
<p>Request changes and watch the artifact update instantly:</p>
<pre><code>"Add dark mode support to this component"
"Include a search/filter feature"
"Add animations for adding/removing items"</code></pre>

<h3>3. Export Ready</h3>
<p>Copy code directly to your project or download as files.</p>

<h2>Best Practices</h2>
<ol>
    <li>Start with clear requirements</li>
    <li>Iterate incrementally</li>
    <li>Test the preview before copying</li>
    <li>Ask for explanations of complex parts</li>
</ol>

<h2>Example Workflow</h2>
<pre><code>1. "Create a dashboard component with 3 stat cards"
2. "Add a line chart showing weekly data"
3. "Make it responsive for mobile"
4. "Add loading states and error handling"
5. "Convert to TypeScript with proper types"</code></pre>

<h2>Limitations to Know</h2>
<ul>
    <li>No backend/API connections in preview</li>
    <li>Limited to client-side code</li>
    <li>Some complex libraries may not render</li>
</ul>

<h2>Conclusion</h2>
<p>Artifacts transform Claude from a text-based assistant into a visual development partner, dramatically speeding up prototyping and development workflows.</p>
""",
            "excerpt": "Learn how Claude's Artifacts feature enables real-time code preview, instant iteration, and visual development directly in your AI conversation."
        }
    ],
    "gemini": [
        {
            "title": "Exploring Gemini's Multimodal Capabilities",
            "content": """
<h2>What Makes Gemini Truly Multimodal</h2>
<p>Google's Gemini was built from the ground up to understand and process multiple types of input: text, images, audio, video, and code. This native multimodality sets it apart from models that had image capabilities added later.</p>

<h2>Image Understanding</h2>
<p>Gemini excels at visual tasks:</p>
<ul>
    <li><strong>Image Description:</strong> Detailed descriptions of photos and graphics</li>
    <li><strong>Text Extraction:</strong> Reading text from images (OCR)</li>
    <li><strong>Chart Analysis:</strong> Interpreting graphs and visualizations</li>
    <li><strong>Object Detection:</strong> Identifying items in images</li>
</ul>

<h2>Practical Applications</h2>

<h3>Document Processing</h3>
<p>Upload receipts, forms, or handwritten notes and have Gemini extract and organize the information.</p>

<h3>Visual Q&A</h3>
<pre><code>Upload an image and ask:
- "What's wrong with this code screenshot?"
- "Identify the plants in this garden photo"
- "What does this error message mean?"</code></pre>

<h3>Creative Tasks</h3>
<ul>
    <li>Describe art styles and influences</li>
    <li>Generate captions for social media</li>
    <li>Analyze design compositions</li>
</ul>

<h2>Video Understanding</h2>
<p>Gemini can process video content to:</p>
<ul>
    <li>Summarize key points</li>
    <li>Answer questions about specific moments</li>
    <li>Transcribe and translate</li>
    <li>Identify objects and actions</li>
</ul>

<h2>Integration with Google Ecosystem</h2>
<p>Gemini works seamlessly with:</p>
<ul>
    <li>Google Workspace (Docs, Sheets, Slides)</li>
    <li>Google Cloud services</li>
    <li>Android devices</li>
</ul>

<h2>Tips for Best Results</h2>
<ol>
    <li>Provide high-quality images when possible</li>
    <li>Be specific about what you want analyzed</li>
    <li>Combine text and image inputs for context</li>
    <li>Use follow-up questions to dive deeper</li>
</ol>

<h2>Conclusion</h2>
<p>Gemini's native multimodal design opens up possibilities that text-only AI simply can't match. From analyzing documents to understanding videos, it's a powerful tool for visual workflows.</p>
""",
            "excerpt": "Discover how Gemini's native multimodal capabilities enable powerful image, video, and document understanding that transforms visual workflows."
        }
    ],
    "midjourney": [
        {
            "title": "Mastering Midjourney: From Prompts to Stunning Art",
            "content": """
<h2>The Art of AI Image Generation</h2>
<p>Midjourney has emerged as one of the most powerful AI art generators, capable of creating stunning visuals from text descriptions. This guide will help you master the art of prompting.</p>

<h2>Understanding Midjourney Prompts</h2>
<p>A Midjourney prompt consists of:</p>
<ul>
    <li><strong>Subject:</strong> What you want to create</li>
    <li><strong>Style:</strong> Artistic style or medium</li>
    <li><strong>Mood:</strong> Atmosphere and feeling</li>
    <li><strong>Parameters:</strong> Technical settings</li>
</ul>

<h2>Essential Parameters</h2>

<h3>Aspect Ratio (--ar)</h3>
<pre><code>--ar 16:9  (Widescreen)
--ar 9:16  (Portrait/Mobile)
--ar 1:1   (Square)
--ar 2:3   (Classic photo)</code></pre>

<h3>Stylization (--stylize or --s)</h3>
<pre><code>--s 0    (Minimal artistic interpretation)
--s 100  (Default)
--s 1000 (Maximum artistic freedom)</code></pre>

<h3>Chaos (--chaos)</h3>
<pre><code>--chaos 0   (Consistent results)
--chaos 100 (Maximum variation)</code></pre>

<h2>Prompt Structure Tips</h2>

<h3>Be Specific</h3>
<pre><code>❌ "A castle"
✅ "A medieval Gothic castle on a misty mountain, 
    dramatic sunset lighting, detailed stonework"</code></pre>

<h3>Use Art References</h3>
<pre><code>"Portrait in the style of Rembrandt, 
 dramatic chiaroscuro lighting, oil painting"</code></pre>

<h3>Describe Lighting</h3>
<ul>
    <li>Golden hour</li>
    <li>Dramatic rim lighting</li>
    <li>Soft diffused light</li>
    <li>Neon cyberpunk glow</li>
</ul>

<h2>Popular Style Keywords</h2>
<ul>
    <li><strong>Photorealistic:</strong> hyperrealistic, 8K, detailed</li>
    <li><strong>Artistic:</strong> watercolor, oil painting, sketch</li>
    <li><strong>Digital:</strong> 3D render, octane render, unreal engine</li>
    <li><strong>Vintage:</strong> film grain, polaroid, retro</li>
</ul>

<h2>Advanced Techniques</h2>

<h3>Image Prompting</h3>
<p>Use an existing image as a reference by uploading it and adding your prompt.</p>

<h3>Multi-Prompt Weighting</h3>
<pre><code>"cat::2 astronaut::1" (Cat is twice as important)</code></pre>

<h3>Negative Prompting</h3>
<pre><code>"beautiful landscape --no people, buildings"</code></pre>

<h2>Conclusion</h2>
<p>Midjourney rewards experimentation. Start with simple prompts, learn from the results, and gradually incorporate more advanced techniques.</p>
""",
            "excerpt": "Learn to create stunning AI art with Midjourney through effective prompting, essential parameters, and advanced techniques like multi-prompt weighting."
        },
        {
            "title": "Midjourney v6: What's New and How to Use It",
            "content": """
<h2>The Evolution of Midjourney</h2>
<p>Midjourney v6 represents a massive leap forward in AI image generation, with dramatically improved photorealism, text rendering, and prompt understanding.</p>

<h2>Key Improvements in v6</h2>

<h3>1. Text Rendering</h3>
<p>For the first time, Midjourney can reliably render text in images:</p>
<pre><code>"A neon sign that says 'OPEN 24 HOURS' in a rainy city"</code></pre>
<p>Use quotation marks around the text you want rendered.</p>

<h3>2. Enhanced Photorealism</h3>
<p>V6 produces images that are often indistinguishable from photographs:</p>
<ul>
    <li>Better skin textures and details</li>
    <li>More realistic lighting and shadows</li>
    <li>Improved material rendering</li>
</ul>

<h3>3. Better Prompt Following</h3>
<p>V6 understands more nuanced prompts and follows instructions more accurately.</p>

<h3>4. Coherent Scenes</h3>
<p>Complex scenes with multiple elements are more coherent and logical.</p>

<h2>Changed Parameters</h2>

<h3>Style Raw</h3>
<pre><code>--style raw (Less Midjourney aesthetic, more literal)</code></pre>

<h3>New Stylize Range</h3>
<pre><code>--stylize ranges from 0 to 1000 (default 100)</code></pre>

<h2>Prompting Differences</h2>

<h3>More Natural Language</h3>
<p>V6 understands conversational prompts better:</p>
<pre><code>V5: "woman, red dress, fashion photography, studio lighting"
V6: "A fashion photograph of a woman in an elegant red dress, 
     professional studio lighting"</code></pre>

<h3>Longer Prompts Work Better</h3>
<p>V6 can handle and benefit from more detailed descriptions.</p>

<h2>Tips for v6</h2>
<ol>
    <li>Write more naturally, less like keywords</li>
    <li>Be more specific about what you want</li>
    <li>Use --style raw for photorealism</li>
    <li>Experiment with lower stylize values</li>
</ol>

<h2>When to Use v5 vs v6</h2>
<ul>
    <li><strong>Use v6:</strong> Photorealism, text in images, complex scenes</li>
    <li><strong>Use v5:</strong> Artistic styles, when you prefer the v5 aesthetic</li>
</ul>

<h2>Conclusion</h2>
<p>Midjourney v6 is a significant upgrade that opens new creative possibilities, especially for photorealistic images and text rendering. Take time to relearn prompting for best results.</p>
""",
            "excerpt": "Explore Midjourney v6's groundbreaking features including text rendering, enhanced photorealism, and improved prompt understanding with updated prompting strategies."
        }
    ],
    "github-copilot": [
        {
            "title": "Supercharge Your Coding with GitHub Copilot",
            "content": """
<h2>Your AI Pair Programmer</h2>
<p>GitHub Copilot is an AI-powered code completion tool that suggests entire lines or blocks of code as you type. It's like having an experienced developer looking over your shoulder, ready to help.</p>

<h2>Getting Started</h2>

<h3>Installation</h3>
<ol>
    <li>Subscribe to GitHub Copilot</li>
    <li>Install the extension in VS Code or your IDE</li>
    <li>Sign in with your GitHub account</li>
    <li>Start coding!</li>
</ol>

<h2>Key Features</h2>

<h3>Code Completion</h3>
<p>Copilot suggests code as you type:</p>
<pre><code>def calculate_fibonacci(n):
    # Copilot will suggest the implementation
    </code></pre>

<h3>Comment-to-Code</h3>
<p>Write a comment describing what you want:</p>
<pre><code># Function to fetch user data from API and cache it
# Copilot generates the complete function</code></pre>

<h3>Test Generation</h3>
<p>Copilot can generate unit tests for your functions.</p>

<h3>Documentation</h3>
<p>Generate docstrings and comments for existing code.</p>

<h2>Tips for Better Suggestions</h2>

<h3>1. Write Clear Comments</h3>
<pre><code># Parse CSV file and return list of dictionaries
# Handle missing values by replacing with None
# Skip header row</code></pre>

<h3>2. Use Descriptive Names</h3>
<pre><code># Good: user_authentication_service
# Bad: uas</code></pre>

<h3>3. Provide Context</h3>
<p>Open related files so Copilot understands your codebase.</p>

<h3>4. Accept Partially</h3>
<p>Use Ctrl+Right to accept suggestions word by word.</p>

<h2>Keyboard Shortcuts</h2>
<ul>
    <li><strong>Tab:</strong> Accept suggestion</li>
    <li><strong>Esc:</strong> Dismiss suggestion</li>
    <li><strong>Alt+]:</strong> Next suggestion</li>
    <li><strong>Alt+[:</strong> Previous suggestion</li>
    <li><strong>Ctrl+Enter:</strong> Open Copilot panel</li>
</ul>

<h2>Best Practices</h2>
<ol>
    <li>Always review suggestions before accepting</li>
    <li>Test generated code thoroughly</li>
    <li>Don't rely on Copilot for security-critical code</li>
    <li>Use it to learn patterns and approaches</li>
</ol>

<h2>Conclusion</h2>
<p>GitHub Copilot is a powerful productivity tool that can significantly speed up your development workflow. Use it wisely as an assistant, not a replacement for understanding your code.</p>
""",
            "excerpt": "Learn to boost your coding productivity with GitHub Copilot's AI-powered code completion, comment-to-code generation, and smart suggestions."
        },
        {
            "title": "GitHub Copilot Chat: Beyond Code Completion",
            "content": """
<h2>Conversational AI in Your IDE</h2>
<p>GitHub Copilot Chat brings the power of conversational AI directly into your development environment, allowing you to ask questions, get explanations, and receive coding help through natural language.</p>

<h2>What Copilot Chat Can Do</h2>

<h3>Explain Code</h3>
<p>Select code and ask:</p>
<pre><code>/explain
"What does this regex pattern do?"
"Why is this function using recursion?"</code></pre>

<h3>Fix Bugs</h3>
<pre><code>/fix
"Why am I getting a null pointer exception?"
"Debug this function"</code></pre>

<h3>Write Tests</h3>
<pre><code>/tests
"Generate unit tests for this class"
"Write integration tests for the API"</code></pre>

<h3>Generate Documentation</h3>
<pre><code>/doc
"Add JSDoc comments to this file"
"Generate README documentation"</code></pre>

<h2>Slash Commands</h2>
<ul>
    <li><strong>/explain:</strong> Explain selected code</li>
    <li><strong>/fix:</strong> Propose fixes for issues</li>
    <li><strong>/tests:</strong> Generate tests</li>
    <li><strong>/doc:</strong> Generate documentation</li>
    <li><strong>/optimize:</strong> Suggest optimizations</li>
    <li><strong>/clear:</strong> Clear chat history</li>
</ul>

<h2>Context-Aware Conversations</h2>
<p>Copilot Chat understands:</p>
<ul>
    <li>Your current file</li>
    <li>Selected code</li>
    <li>Error messages in the terminal</li>
    <li>Your project structure</li>
</ul>

<h2>Example Workflows</h2>

<h3>Debugging</h3>
<pre><code>1. "I'm getting this error: [paste error]"
2. "Can you explain why this might happen?"
3. "Show me how to fix it"
4. "Are there edge cases I should handle?"</code></pre>

<h3>Learning</h3>
<pre><code>1. "What design pattern is used here?"
2. "What are the pros and cons?"
3. "Show me an alternative approach"</code></pre>

<h3>Refactoring</h3>
<pre><code>1. "How can I make this more readable?"
2. "Convert this to TypeScript"
3. "Add proper error handling"</code></pre>

<h2>Tips for Effective Use</h2>
<ol>
    <li>Select relevant code before asking</li>
    <li>Be specific about what you need</li>
    <li>Use follow-up questions to refine answers</li>
    <li>Reference specific files or functions</li>
</ol>

<h2>Privacy Considerations</h2>
<p>Be aware that your code and questions are sent to GitHub's servers. Review your organization's policies for sensitive projects.</p>

<h2>Conclusion</h2>
<p>Copilot Chat transforms your IDE into an interactive learning and development environment. It's particularly valuable for understanding unfamiliar codebases and getting unstuck quickly.</p>
""",
            "excerpt": "Discover how GitHub Copilot Chat brings conversational AI to your IDE with code explanations, debugging help, test generation, and natural language coding assistance."
        }
    ]
}

SAMPLE_COMMENTS = [
    "Great article! This really helped me understand the topic better.",
    "Thanks for sharing these tips. I've been using this tool for months and learned something new!",
    "Very informative. Would love to see more content like this.",
    "This is exactly what I was looking for. Bookmarked!",
    "The examples are really helpful. Can you do a follow-up on advanced techniques?",
    "I tried the approach you mentioned and it worked perfectly. Thanks!",
    "Clear and concise explanation. Perfect for beginners.",
    "Been struggling with this for days. Your guide solved my problem in minutes!",
]

# More detailed comments for thorough testing of admin user detail view
DETAILED_TEST_COMMENTS = {
    "johndoe": [
        {"content": "This is my first comment on this blog. Really enjoying the content!", "is_spam": False},
        {"content": "I've been using ChatGPT for 6 months now and this guide covers everything I wish I knew when starting.", "is_spam": False},
        {"content": "Quick question - does this approach work with the API as well, or just the web interface?", "is_spam": False},
        {"content": "Following up on my previous comment - I figured it out! Thanks for the clear explanations.", "is_spam": False},
        {"content": "Would love to see a comparison between Claude and ChatGPT for coding tasks.", "is_spam": False},
        {"content": "The code examples are super helpful. Already implemented the fibonacci function in my project.", "is_spam": False},
        {"content": "One small correction: in the section about prompting, you might want to mention temperature settings.", "is_spam": False},
        {"content": "Shared this with my team - we're all learning together now!", "is_spam": False},
    ],
    "janedoe": [
        {"content": "As a designer, I find the Midjourney tips especially useful. Great work!", "is_spam": False},
        {"content": "The artifact feature in Claude has completely changed my workflow.", "is_spam": False},
        {"content": "I appreciate how you break down complex topics into digestible pieces.", "is_spam": False},
        {"content": "Has anyone tried combining multiple AI tools for a single project? Would love to hear experiences.", "is_spam": False},
        {"content": "This helped me explain AI concepts to my non-technical colleagues. Thank you!", "is_spam": False},
    ],
    "techwriter": [
        {"content": "From a technical writing perspective, these AI tools have transformed my documentation process.", "is_spam": False},
        {"content": "The multimodal capabilities section was particularly insightful. Looking forward to more content!", "is_spam": False},
        {"content": "I use GitHub Copilot daily and can confirm these tips really improve the suggestions.", "is_spam": False},
        {"content": "Just discovered this blog today. Already bookmarked several articles!", "is_spam": False},
        {"content": "Pro tip for others: combining Copilot with Copilot Chat is a game changer for code reviews.", "is_spam": False},
        {"content": "The v6 Midjourney guide was timely - I was just about to upgrade. Perfect timing!", "is_spam": False},
        {"content": "Could you cover how to use AI tools for API documentation in a future post?", "is_spam": False},
        {"content": "Minor feedback: some code blocks could use syntax highlighting for readability.", "is_spam": False},
        {"content": "This community is amazing. Love how helpful everyone is in the comments!", "is_spam": False},
        {"content": "Been recommending this blog to all my developer friends.", "is_spam": False},
    ]
}

# ============================================
# Seeder Functions
# ============================================

def clear_data(cursor):
    """Clear existing data from all tables."""
    print("🗑️  Clearing existing data...")
    cursor.execute("DELETE FROM Vote")
    cursor.execute("DELETE FROM ComparisonPost")
    cursor.execute("DELETE FROM Comparison")
    cursor.execute("DELETE FROM Bookmark")
    cursor.execute("DELETE FROM Comment")
    cursor.execute("DELETE FROM ToolFollow")
    cursor.execute("DELETE FROM Post")
    cursor.execute("DELETE FROM Users")
    print("   Data cleared.")

def seed_users(cursor):
    """Insert sample users."""
    print("👤 Seeding users...")
    user_ids = []
    
    for user in SAMPLE_USERS:
        cursor.execute("""
            INSERT INTO Users (username, email, password_hash, is_admin, is_active, email_notifications, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING user_id
        """, (
            user["username"],
            user["email"],
            generate_password_hash(user["password"]),
            user["is_admin"],
            user["is_active"],
            user["email_notifications"],
            datetime.now() - timedelta(days=random.randint(10, 60))
        ))
        user_id = cursor.fetchone()[0]
        user_ids.append(user_id)
        print(f"   Created user: {user['username']} (ID: {user_id})")
    
    return user_ids

def get_tools(cursor):
    """Get all AI tools from database."""
    cursor.execute("SELECT tool_id, slug FROM AITool")
    return {row[1]: row[0] for row in cursor.fetchall()}

def seed_posts(cursor, tools):
    """Insert sample posts."""
    print("📝 Seeding posts...")
    post_ids = []
    
    for tool_slug, posts in SAMPLE_POSTS.items():
        if tool_slug not in tools:
            print(f"   ⚠️  Tool '{tool_slug}' not found, skipping...")
            continue
            
        tool_id = tools[tool_slug]
        
        for i, post in enumerate(posts):
            # Truncate title and excerpt to fit database constraints
            title = post["title"][:100]
            excerpt = post["excerpt"][:100]
            
            cursor.execute("""
                INSERT INTO Post (tool_id, Title, Content, Category)
                VALUES (%s, %s, %s, %s)
                RETURNING postid
            """, (
                tool_id,
                title,
                post["content"],
                excerpt
            ))
            post_id = cursor.fetchone()[0]
            post_ids.append(post_id)
            print(f"   Created post: {title[:50]}... (ID: {post_id})")
    
    return post_ids

def seed_comments(cursor, post_ids, user_ids):
    """Insert sample comments with detailed test data for admin user detail view."""
    print("💬 Seeding comments...")
    
    # Create a mapping of usernames to user_ids
    cursor.execute("SELECT user_id, username FROM Users")
    user_map = {row[1]: row[0] for row in cursor.fetchall()}
    
    comment_count = 0
    
    # First, add detailed comments for specific users (for testing admin user detail view)
    for username, comments in DETAILED_TEST_COMMENTS.items():
        if username not in user_map:
            continue
            
        user_id = user_map[username]
        
        # Distribute comments across different posts
        for i, comment_data in enumerate(comments):
            post_id = post_ids[i % len(post_ids)]  # Cycle through posts
            
            # Vary the timestamps for realistic testing
            days_ago = random.randint(0, 30)
            
            cursor.execute("""
                INSERT INTO Comment (postid, user_id, content, is_spam, parent_id, CreatedAt)
                VALUES (%s, %s, %s, %s, %s, NOW() - INTERVAL '%s days')
            """, (
                post_id,
                user_id,
                comment_data["content"],
                comment_data["is_spam"],
                None,
                days_ago
            ))
            comment_count += 1
    
    # Also add some random comments using the simple SAMPLE_COMMENTS list
    commenter_ids = [uid for uid in user_ids if uid != user_map.get('admin')]
    
    for post_id in post_ids:
        num_extra_comments = random.randint(1, 3)
        
        for _ in range(num_extra_comments):
            user_id = random.choice(commenter_ids)
            content = random.choice(SAMPLE_COMMENTS)
            days_ago = random.randint(0, 45)
            
            cursor.execute("""
                INSERT INTO Comment (postid, user_id, content, is_spam, parent_id, CreatedAt)
                VALUES (%s, %s, %s, %s, %s, NOW() - INTERVAL '%s days')
            """, (
                post_id,
                user_id,
                content,
                False,
                None,
                days_ago
            ))
            comment_count += 1
    
    print(f"   Created {comment_count} comments across {len(post_ids)} posts")

def seed_subscriptions(cursor, user_ids, tools):
    """Create subscriptions for users."""
    print("🔔 Seeding subscriptions...")
    
    tool_ids = list(tools.values())
    
    for user_id in user_ids[1:]:  # Skip admin
        # Each user subscribes to 2-4 random tools
        num_subs = random.randint(2, 4)
        subscribed_tools = random.sample(tool_ids, min(num_subs, len(tool_ids)))
        
        for tool_id in subscribed_tools:
            cursor.execute("""
                INSERT INTO ToolFollow (user_id, tool_id)
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING
            """, (user_id, tool_id))
    
    print(f"   Created subscriptions for {len(user_ids) - 1} users")

def seed_bookmarks(cursor, user_ids, post_ids):
    """Create bookmarks for users."""
    print("🔖 Seeding bookmarks...")
    
    for user_id in user_ids[1:]:  # Skip admin
        # Each user bookmarks 1-3 random posts
        num_bookmarks = random.randint(1, 3)
        bookmarked_posts = random.sample(post_ids, min(num_bookmarks, len(post_ids)))
        
        for post_id in bookmarked_posts:
            cursor.execute("""
                INSERT INTO Bookmark (user_id, post_id)
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING
            """, (user_id, post_id))
    
    print(f"   Created bookmarks for {len(user_ids) - 1} users")

def main():
    """Run the database seeder."""
    print("=" * 60)
    print("🌱 AI Blog Database Seeder")
    print("=" * 60)
    
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Clear existing data
        clear_data(cursor)
        
        # Get existing tools
        tools = get_tools(cursor)
        if not tools:
            print("❌ No AI tools found in database. Run schema.sql first.")
            return
        
        print(f"   Found {len(tools)} AI tools: {', '.join(tools.keys())}")
        
        # Seed data
        user_ids = seed_users(cursor)
        post_ids = seed_posts(cursor, tools)
        seed_comments(cursor, post_ids, user_ids)
        seed_subscriptions(cursor, user_ids, tools)
        seed_bookmarks(cursor, user_ids, post_ids)
        
        # Commit all changes
        conn.commit()
        
        print("\n" + "=" * 60)
        print("✅ Database seeded successfully!")
        print("=" * 60)
        print(f"\n📊 Summary:")
        print(f"   - {len(user_ids)} users created")
        print(f"   - {len(post_ids)} posts created")
        print(f"   - Comments, subscriptions, and bookmarks added")
        print(f"\n🔐 Login credentials:")
        print(f"   Admin: admin@aiblog.com / admin123")
        print(f"   User:  john@example.com / password123")
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ Error: {e}")
        raise
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    main()
