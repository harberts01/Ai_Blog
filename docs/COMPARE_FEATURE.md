# Compare Feature Documentation

## Overview

The **Compare Feature** allows users to compare blog posts written by different AI tools (ChatGPT, Claude, Gemini, etc.) on similar topics. This enables users to evaluate writing styles, analyze content metrics, and vote for their favorite AI-generated content.

---

## Use Cases

### UC-01: Browse Available Comparisons
**Actor:** Any User (Guest or Registered)  
**Description:** Users can view the compare landing page to see available categories and recent comparisons.

**Flow:**
1. User navigates to `/compare`
2. System displays categories with 2+ posts from different AI tools
3. System shows recent comparisons (up to 5)
4. User can select a category or view a recent comparison

---

### UC-02: Create Category-Based Comparison
**Actor:** Any User (Guest or Registered)  
**Description:** Users can generate a comparison by selecting a content category.

**Flow:**
1. User selects a category from the compare page (e.g., "Technology & Innovation")
2. System retrieves one post per AI tool for that category
3. System creates a new comparison record
4. User is redirected to the comparison view page

**Preconditions:**
- Category must have posts from at least 2 different AI tools

---

### UC-03: View Side-by-Side Comparison
**Actor:** Any User (Guest or Registered)  
**Description:** Users can view a detailed side-by-side comparison of AI-generated posts.

**Flow:**
1. User accesses a comparison via `/compare/<comparison_id>`
2. System displays posts in a responsive grid layout
3. Each post card shows:
   - AI tool name
   - Writing style metrics
   - Post title and category
   - Scrollable content preview
   - Link to full post
4. If votes exist, system displays current voting results with percentages

---

### UC-04: Vote for Favorite AI Writer
**Actor:** Registered User (Logged In)  
**Description:** Authenticated users can cast a vote for their preferred AI-written post.

**Flow:**
1. User views a comparison while logged in
2. User clicks "Vote" button on their preferred post
3. System records the vote (or updates existing vote)
4. System displays confirmation message
5. Voting results are updated in real-time

**Preconditions:**
- User must be logged in
- Post must be part of the comparison

**Business Rules:**
- Users can only have one vote per comparison
- Users can change their vote at any time
- Votes are recorded with timestamps

---

## Acceptance Criteria

### Compare Landing Page (`/compare`)

| ID | Criterion | Priority |
|----|-----------|----------|
| AC-01 | Page displays all categories that have 2+ posts from different AI tools | Must Have |
| AC-02 | Each category button shows the count of available posts | Must Have |
| AC-03 | Categories with fewer than 2 posts are hidden | Must Have |
| AC-04 | Recent comparisons section shows up to 5 most recent comparisons | Should Have |
| AC-05 | Each recent comparison displays topic, date, and post count | Should Have |
| AC-06 | "How It Works" section explains the 3-step process | Should Have |
| AC-07 | Page is accessible to both guests and logged-in users | Must Have |

### Comparison View Page (`/compare/<id>`)

| ID | Criterion | Priority |
|----|-----------|----------|
| AC-08 | Page displays posts in responsive grid (adapts to number of posts) | Must Have |
| AC-09 | Each post card displays the AI tool name prominently | Must Have |
| AC-10 | Style metrics are calculated and displayed for each post: | Must Have |
|    | - Word count | |
|    | - Average words per sentence | |
|    | - Vocabulary richness (%) | |
|    | - Reading level (grade) | |
| AC-11 | Post content is displayed in a scrollable preview (max 400px height) | Must Have |
| AC-12 | Each post has a "Read Full Post" link | Must Have |
| AC-13 | Breadcrumb navigation shows path back to compare page | Should Have |
| AC-14 | Page header shows topic name and total vote count | Should Have |

### Voting System

| ID | Criterion | Priority |
|----|-----------|----------|
| AC-15 | Vote button is only visible to logged-in users | Must Have |
| AC-16 | Guests see a prompt to log in to vote | Must Have |
| AC-17 | User's current vote is visually highlighted (border + "Your Vote" badge) | Must Have |
| AC-18 | User can change their vote by clicking a different post | Should Have |
| AC-19 | Voting results show ranking with percentages | Must Have |
| AC-20 | Leading post displays trophy icon | Should Have |
| AC-21 | Progress bars visualize vote distribution | Should Have |
| AC-22 | Vote counts update after each vote submission | Must Have |
| AC-23 | CSRF protection is enforced on vote submission | Must Have |

### Content Metrics Calculation

| ID | Criterion | Priority |
|----|-----------|----------|
| AC-24 | Word count accurately counts words (excluding HTML tags) | Must Have |
| AC-25 | Sentence detection handles common punctuation (. ! ?) | Must Have |
| AC-26 | Vocabulary richness = unique words / total words × 100 | Must Have |
| AC-27 | Reading level uses standard readability formula | Should Have |

---

## Data Model

### Tables

#### Comparison
| Column | Type | Description |
|--------|------|-------------|
| comparison_id | SERIAL | Primary key |
| topic | VARCHAR(500) | Comparison topic/category name |
| created_at | TIMESTAMP | Creation timestamp |

#### ComparisonPost
| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL | Primary key |
| comparison_id | INTEGER | FK to Comparison |
| post_id | INTEGER | FK to Post |
| UNIQUE | | (comparison_id, post_id) |

#### Vote
| Column | Type | Description |
|--------|------|-------------|
| vote_id | SERIAL | Primary key |
| comparison_id | INTEGER | FK to Comparison |
| user_id | INTEGER | FK to Users (nullable) |
| post_id | INTEGER | FK to Post (the voted post) |
| created_at | TIMESTAMP | Vote timestamp |
| UNIQUE | | (comparison_id, user_id) |

---

## API Endpoints

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| GET | `/compare` | Compare landing page | No |
| GET | `/compare/category/<category>` | Create comparison by category | No |
| GET | `/compare/<comparison_id>` | View comparison details | No |
| POST | `/compare/<comparison_id>/vote/<post_id>` | Submit vote | Yes |

---

## Style Metrics Explained

| Metric | Description | Calculation |
|--------|-------------|-------------|
| **Words** | Total word count | `len(text.split())` |
| **Words/Sent** | Average words per sentence | `word_count / sentence_count` |
| **Vocab** | Vocabulary richness percentage | `unique_words / total_words × 100` |
| **Grade** | Reading level (US grade) | Flesch-Kincaid or similar formula |

---

## UI Components

### Post Comparison Card
```
┌─────────────────────────────────────┐
│ [AI Tool Name]           [Vote Btn] │
├─────────────────────────────────────┤
│ Words │ Words/Sent │ Vocab │ Grade  │  ← Metrics Bar
│  542  │    18.2    │  73%  │   8    │
├─────────────────────────────────────┤
│ Post Title                          │
│ [Category Badge]                    │
├─────────────────────────────────────┤
│                                     │
│     Post Content Preview            │  ← Scrollable (max 400px)
│     (Full HTML rendered)            │
│                                     │
├─────────────────────────────────────┤
│      [Read Full Post Button]        │
└─────────────────────────────────────┘
```

### Voting Results Display
```
┌─────────────────────────────────────┐
│ 🏆 Current Results                  │
├─────────────────────────────────────┤
│ 🥇 ChatGPT     45 votes (55.5%)    │
│ ████████████████████░░░░░░░░░░░░░░ │
│                                     │
│ 2  Claude      28 votes (34.6%)    │
│ ██████████████░░░░░░░░░░░░░░░░░░░░ │
│                                     │
│ 3  Gemini       8 votes (9.9%)     │
│ ████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ │
└─────────────────────────────────────┘
```

---

## Security Considerations

1. **CSRF Protection**: All vote submissions require valid CSRF token
2. **Authentication**: Voting requires logged-in user
3. **Vote Integrity**: Users limited to one vote per comparison (upsert logic)
4. **Input Validation**: Verify post belongs to comparison before accepting vote

---

## Future Enhancements

| Enhancement | Description | Priority |
|-------------|-------------|----------|
| Topic-based Comparisons | Compare posts on a specific topic (not just category) | Medium |
| AI vs AI Battles | Head-to-head matchups with tournament brackets | Low |
| Time-limited Voting | Set voting deadlines for comparisons | Low |
| Share Comparisons | Social sharing with results snapshot | Medium |
| Leaderboard | Global ranking of AI tools by vote count | Medium |
| Custom Comparisons | Let users select specific posts to compare | High |
| Export Results | Download comparison results as PDF/CSV | Low |

---

## Related Documentation

- [PRODUCT_DOCUMENTATION.md](PRODUCT_DOCUMENTATION.md) - Full product overview
- [FILE_STRUCTURE.md](FILE_STRUCTURE.md) - Project file organization
- [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) - Deployment instructions
