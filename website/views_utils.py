import os
from .models import Note, ChatMessage, User, Question, Rating, Answer, Comment, CommentVote, Reply, Notification, ReplyVote, saved_posts
from . import db
import os
import bleach
import re
from sqlalchemy import or_, func
from pdf2image import convert_from_path
from collections import Counter
import random

def clean(html):
    allowed_tags = ['b', 'i', 'u', 'em', 'strong', 'strike', 'strikethrough', 'p', 'br', 'ul', 'ol', 'li', 'a']
    allowed_attrs = {
        'a': ['href', 'title', 'target']
    }

    # Clean the HTML using bleach
    cleaned = bleach.clean(html, tags=allowed_tags, attributes=allowed_attrs, strip=True)

    # Collapse any more than 2 consecutive <br> tags into just 2 <br> tags
    cleaned = re.sub(r'(<br\s*/?>\s*){3,}', '<br><br>', cleaned)

    return cleaned

def super_clean(html):
    # Strip all HTML tags and attributes
    text_only = bleach.clean(html, tags=[], attributes={}, strip=True)

    # Optionally collapse excessive whitespace or newlines
    text_only = re.sub(r'\s+', ' ', text_only).strip()

    return text_only

def find_mentions(text):
    # Find mentions in text
    return re.findall(r'@([\w.]+)', text)

def generate_pdf_preview(pdf_rel_path, preview_rel_path):
    # Generate PDF preview image
    base_dir = os.path.abspath(os.path.dirname(__file__))

    abs_pdf_path = os.path.join(base_dir, pdf_rel_path)
    abs_preview_path = os.path.join(base_dir, preview_rel_path)

    pages = convert_from_path(abs_pdf_path, first_page=1, last_page=1)
    os.makedirs(os.path.dirname(abs_preview_path), exist_ok=True)
    pages[0].save(abs_preview_path, 'JPEG')

def shorten(text, length=20):
    # Create short text for notifications
    return text[:length] + '...' if len(text) > length else text

def extract_keywords(title):
    # Extract words and remove common stopwords
    stopwords = {"of", "the", "and", "in", "on", "for", "to", "with", "i", "ii", "iii", 
        "iv", "v", "vi", "vii", "viii", "ix", "x", "introduction", 
        "principles", "fundamentals", "basics", "foundation", 
        "concepts", "theory", "methods", "techniques", "overview",
        "study", "studies", "approach", "approaches",
        "essential", "elements", "analysis", "application", "applications",
    }
    words = re.findall(r'\b[a-zA-Z]+\b', title.lower())
    return [word for word in words if word not in stopwords]

def get_user_keywords(user_id):
    # Get titles of highly rated notes
    rated_titles = db.session.query(Note.title).join(Rating).filter(
        Rating.rater_id == user_id,
        Rating.value >= 4
    ).all()

    # Get titles of saved notes
    saved_titles = db.session.query(Note.title).join(
        saved_posts, Note.id == saved_posts.c.note_id
    ).filter(
        saved_posts.c.user_id == user_id
    ).all()

    # Merge and flatten titles
    all_titles = [title for (title,) in rated_titles + saved_titles]

    # Extract keywords
    keywords = [kw for title in all_titles for kw in extract_keywords(title)]
    keyword_counts = Counter(keywords)

    # Return top 3 keywords
    return [kw for kw, _ in keyword_counts.most_common(3)]

def recommend_posts(user_id, limit=20):
    top_keywords = get_user_keywords(user_id)

    if not top_keywords:
        return []  # Return trending posts or fallback

    # Build OR conditions for keyword matching
    conditions = [Note.title.ilike(f"%{kw}%") for kw in top_keywords]

    # Subqueries to exclude saved and rated posts
    user = User.query.get(user_id)
    saved_ids = [note.id for note in user.saved]

    # Get note IDs rated by user
    rated_note_ids = db.session.query(Rating.note_id).filter_by(rater_id=user_id).all()
    rated_ids = [r[0] for r in rated_note_ids]

    # Fetch posts that match keywords, not by user, and not saved or rated
    posts = Note.query.filter(
        or_(*conditions),
        Note.publisher != user_id,
        ~Note.id.in_(saved_ids),
        ~Note.id.in_(rated_ids)
    ).order_by(func.random()).limit(limit).all()

    return posts

def suggest_profiles(user_id, limit=5):
    user = User.query.get(user_id)
    if not user:
        return []

    followed_ids = {u.id for u in user.followed}
    user_keywords = set(get_user_keywords(user_id))

    # Get users not followed and not the current user
    other_users = User.query.filter(
        User.id != user_id,
        ~User.id.in_(followed_ids)
    ).all()

    keyword_matches = []
    no_keyword_users = []

    for other_user in other_users:
        note_titles = [note.title for note in other_user.notes]
        keywords = set(
            kw for title in note_titles for kw in extract_keywords(title)
        )

        overlap = user_keywords & keywords
        if overlap:
            keyword_matches.append((other_user, len(overlap)))
        else:
            no_keyword_users.append(other_user)

    # Sort by most overlap
    keyword_matches.sort(key=lambda x: x[1], reverse=True)

    # Extract just the user objects
    suggestions = [user for user, _ in keyword_matches]

    # If not enough, fill with random users from those without overlap
    if len(suggestions) < limit:
        remaining_needed = limit - len(suggestions)
        random.shuffle(no_keyword_users)
        suggestions += no_keyword_users[:remaining_needed]

    return suggestions[:limit]