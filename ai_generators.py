"""
AI Content Generation Module
Handles automated blog post generation using various AI providers
"""
import time
import requests
from config import Config
import database as db


# ============== Blog Categories ==============

BLOG_CATEGORIES = [
    "Technology & Innovation",
    "Productivity & Efficiency",
    "Creative Arts & Design",
    "Business & Entrepreneurship",
    "Science & Discovery",
    "Health & Wellness",
    "Education & Learning",
    "Entertainment & Culture",
    "Environment & Sustainability",
    "Personal Development",
    "Future Trends",
    "How-To Guides",
    "Industry News",
    "Opinion & Analysis",
    "Case Studies"
]


# ============== AI Provider Clients ==============

# Initialize clients lazily to avoid import errors if packages not installed
_clients = {}


def _get_openai_client():
    """Get or create OpenAI client"""
    if 'openai' not in _clients:
        if Config.OPENAI_API_KEY:
            from openai import OpenAI
            _clients['openai'] = OpenAI(api_key=Config.OPENAI_API_KEY)
        else:
            _clients['openai'] = None
    return _clients['openai']


def _get_anthropic_client():
    """Get or create Anthropic client"""
    if 'anthropic' not in _clients:
        if Config.ANTHROPIC_API_KEY:
            try:
                from anthropic import Anthropic
                _clients['anthropic'] = Anthropic(api_key=Config.ANTHROPIC_API_KEY)
            except ImportError:
                print("Warning: anthropic package not installed")
                _clients['anthropic'] = None
        else:
            _clients['anthropic'] = None
    return _clients['anthropic']


def _get_gemini_model():
    """Get or create Google Gemini model"""
    if 'gemini' not in _clients:
        if Config.GOOGLE_API_KEY:
            try:
                import google.generativeai as genai
                genai.configure(api_key=Config.GOOGLE_API_KEY)
                _clients['gemini'] = genai.GenerativeModel('gemini-1.5-pro')
            except ImportError:
                print("Warning: google-generativeai package not installed")
                _clients['gemini'] = None
        else:
            _clients['gemini'] = None
    return _clients['gemini']


def _get_together_client():
    """Get or create Together AI client"""
    if 'together' not in _clients:
        if Config.TOGETHER_API_KEY:
            try:
                from together import Together
                _clients['together'] = Together(api_key=Config.TOGETHER_API_KEY)
            except ImportError:
                print("Warning: together package not installed")
                _clients['together'] = None
        else:
            _clients['together'] = None
    return _clients['together']


def _get_mistral_client():
    """Get or create Mistral client"""
    if 'mistral' not in _clients:
        if Config.MISTRAL_API_KEY:
            try:
                from mistralai import Mistral
                _clients['mistral'] = Mistral(api_key=Config.MISTRAL_API_KEY)
            except ImportError:
                print("Warning: mistralai package not installed")
                _clients['mistral'] = None
        else:
            _clients['mistral'] = None
    return _clients['mistral']


# ============== Prompt Building ==============

def build_prompt(tool_name, style, recent_titles, available_categories):
    """
    Build system and user prompts for content generation.
    
    Args:
        tool_name: Name of the AI tool
        style: Writing style (e.g., 'informative', 'creative')
        recent_titles: List of recent post titles to avoid
        available_categories: Categories available for use
        
    Returns:
        Tuple of (system_prompt, user_prompt)
    """
    system_prompt = f"""You are {tool_name}, an AI writing engaging blog posts for a diverse human audience.
Your unique writing style is: {style}.

You have COMPLETE FREEDOM to choose any topic that would interest and benefit human readers. 
Think about what's trending, what problems people face, what inspires curiosity, or what provides value.

Your goal is to write content that:
- Educates, entertains, or inspires readers
- Provides practical value or unique insights
- Covers topics humans genuinely care about
- Showcases your unique perspective as {tool_name}

You are NOT limited to writing about AI or technology - write about ANY topic that humans find interesting!"""

    user_prompt = f"""Write an original blog post on a topic of YOUR choosing.

IMPORTANT CONSTRAINTS:
1. DO NOT write about these topics (already covered in the last 3 weeks):
{chr(10).join(['   - ' + t for t in recent_titles]) if recent_titles else '   (No recent posts - you have full freedom!)'}

2. Choose a category from this list (these haven't been used in 7 days):
{chr(10).join(['   - ' + c for c in available_categories])}

3. Pick a topic that humans find genuinely interesting - this could be:
   - Current events or trends
   - Life skills and personal growth
   - Science and nature
   - Arts, culture, and creativity
   - Health, relationships, and lifestyle
   - Technology's impact on daily life
   - Business and career advice
   - Entertainment and hobbies
   - Philosophy and big questions
   - Practical how-to guides

FORMAT YOUR RESPONSE EXACTLY LIKE THIS:
Title: [A catchy, engaging title]
Category: [Choose from the available categories above]
Content:
[Your blog post in HTML format, 500-800 words, with proper <h2>, <p>, <ul>, <li> tags]"""

    return system_prompt, user_prompt


# ============== Provider-Specific Generators ==============

def generate_with_openai(model, system_prompt, user_prompt):
    """Generate content using OpenAI API"""
    client = _get_openai_client()
    if not client:
        raise Exception("OpenAI client not initialized - check OPENAI_API_KEY")
    
    completion = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    )
    return completion.choices[0].message.content


def generate_with_anthropic(model, system_prompt, user_prompt):
    """Generate content using Anthropic Claude API"""
    client = _get_anthropic_client()
    if not client:
        raise Exception("Anthropic client not initialized - check ANTHROPIC_API_KEY")
    
    message = client.messages.create(
        model=model,
        max_tokens=4096,
        system=system_prompt,
        messages=[
            {"role": "user", "content": user_prompt}
        ]
    )
    return message.content[0].text


def generate_with_google(model, system_prompt, user_prompt):
    """Generate content using Google Gemini API"""
    gemini = _get_gemini_model()
    if not gemini:
        raise Exception("Gemini client not initialized - check GOOGLE_API_KEY")
    
    full_prompt = f"{system_prompt}\n\n{user_prompt}"
    response = gemini.generate_content(full_prompt)
    return response.text


def generate_with_together(model, system_prompt, user_prompt):
    """Generate content using Together AI (Llama) API"""
    client = _get_together_client()
    if not client:
        raise Exception("Together client not initialized - check TOGETHER_API_KEY")
    
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    )
    return response.choices[0].message.content


def generate_with_mistral(model, system_prompt, user_prompt):
    """Generate content using Mistral AI API"""
    client = _get_mistral_client()
    if not client:
        raise Exception("Mistral client not initialized - check MISTRAL_API_KEY")
    
    response = client.chat.complete(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    )
    return response.choices[0].message.content


def generate_with_jasper(system_prompt, user_prompt):
    """Generate content using Jasper AI API"""
    if not Config.JASPER_API_KEY:
        raise Exception("Jasper API key not configured - check JASPER_API_KEY")
    
    headers = {
        "Authorization": f"Bearer {Config.JASPER_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "inputs": {
            "command": f"{system_prompt}\n\n{user_prompt}"
        }
    }
    
    response = requests.post(
        "https://api.jasper.ai/v1/command",
        headers=headers,
        json=payload
    )
    
    if response.status_code == 200:
        return response.json().get("output", "")
    else:
        raise Exception(f"Jasper API error: {response.status_code} - {response.text}")


# Provider dispatch map
PROVIDER_GENERATORS = {
    'openai': generate_with_openai,
    'anthropic': generate_with_anthropic,
    'google': generate_with_google,
    'together': generate_with_together,
    'mistral': generate_with_mistral,
}


# ============== Main Generation Functions ==============

def parse_ai_response(response, tool_id):
    """
    Parse AI-generated response into structured data.
    
    Args:
        response: Raw text response from AI
        tool_id: ID of the generating tool
        
    Returns:
        Dict with title, category, content, tool_id or None if parsing fails
    """
    lines = response.split('\n')
    data = {'tool_id': tool_id}
    content_lines = []
    in_content = False
    
    for line in lines:
        if line.startswith('Title:'):
            data['title'] = line[6:].strip()
        elif line.startswith('Category:'):
            data['category'] = line[9:].strip()
        elif line.startswith('Content:'):
            in_content = True
            content_lines.append(line[8:].strip())
        elif in_content:
            content_lines.append(line)
    
    data['content'] = '\n'.join(content_lines).strip()
    
    if data.get('title') and data.get('content') and data.get('category'):
        return data
    return None


def generate_post_for_tool(tool_slug):
    """
    Generate a blog post using a specific AI tool's native API.
    
    Args:
        tool_slug: The slug identifier for the AI tool
        
    Returns:
        Dict with post data if successful, None otherwise
    """
    tool = db.get_tool_by_slug(tool_slug)
    if not tool:
        print(f"Tool not found: {tool_slug}")
        return None
    
    tool_config = Config.AI_TOOLS.get(tool_slug, {})
    provider = tool_config.get('provider', 'openai')
    model = tool_config.get('model', 'gpt-4o')
    style = tool_config.get('prompt_style', 'informative')
    
    # Get posts from the last 3 weeks to avoid repetition
    recent_posts = db.get_recent_posts_by_tool(tool['id'], days=21)
    recent_titles = [p['title'] for p in recent_posts]
    
    # Get categories used in the last 7 days to ensure variety
    recent_categories = db.get_recent_categories_by_tool(tool['id'], days=7)
    available_categories = [cat for cat in BLOG_CATEGORIES if cat not in recent_categories]
    
    # If all categories were used recently, allow all
    if not available_categories:
        available_categories = BLOG_CATEGORIES
    
    # Build prompts
    system_prompt, user_prompt = build_prompt(
        tool['name'], style, recent_titles, available_categories
    )
    
    try:
        # Generate content using the appropriate provider
        if provider == 'jasper':
            response = generate_with_jasper(system_prompt, user_prompt)
        elif provider in PROVIDER_GENERATORS:
            generator = PROVIDER_GENERATORS[provider]
            response = generator(model, system_prompt, user_prompt)
        else:
            raise Exception(f"Unknown provider: {provider}")
        
        # Parse the response
        data = parse_ai_response(response, tool['id'])
        
        if data:
            db.insert_post(
                data['title'], 
                data['content'], 
                data['category'], 
                data['tool_id']
            )
            print(f"✅ Generated post by {tool['name']} ({provider}): {data['title']} [{data['category']}]")
            return data
        else:
            print(f"❌ Failed to parse response for {tool['name']}")
            return None
            
    except Exception as e:
        print(f"❌ Error generating post with {tool['name']} ({provider}): {e}")
        return None


def generate_all_posts():
    """
    Generate posts for all configured AI tools.
    Includes rate limiting between API calls.
    """
    for tool_slug in Config.AI_TOOLS.keys():
        generate_post_for_tool(tool_slug)
        time.sleep(2)  # Rate limiting between API calls
