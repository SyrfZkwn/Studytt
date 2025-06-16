from flask import Blueprint, render_template, current_app, request, flash, redirect, url_for, session, abort
from flask_login import login_required, current_user
from flask_wtf import FlaskForm
from wtforms import FileField, SubmitField, StringField, TextAreaField
from flask_wtf.file import FileSize
from werkzeug.utils import secure_filename
import os
from wtforms.validators import InputRequired, DataRequired
from .models import Note, ChatMessage, User, Question, Rating, Answer, Comment, CommentVote, Reply, Notification, ReplyVote, Report
from . import db
from wtforms.widgets import TextArea
from flask import Flask, render_template, request, redirect, url_for
from flask_socketio import SocketIO, join_room, leave_room, send, emit 
from flask_socketio import SocketIO, join_room, leave_room, send, emit
from . import socketio
from string import ascii_uppercase
import random
import secrets
import os
from PIL import Image
from sqlalchemy.sql import func
import bleach
import re
from sqlalchemy import or_, and_
import random
from string import ascii_uppercase
from datetime import datetime
from . import db, socketio
from werkzeug.security import check_password_hash, generate_password_hash


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
import uuid
from .views_utils import clean, super_clean, find_mentions, generate_pdf_preview, shorten, recommend_posts, suggest_profiles
from werkzeug.security import check_password_hash, generate_password_hash

views = Blueprint('views', __name__, template_folder='../templates')

class UploadFileForm(FlaskForm):
    file = FileField("File", validators=[InputRequired(), FileSize(max_size=15 * 1024 * 1024, message="File must be 15MB or less.")])
    submit = SubmitField("Upload")
    description = TextAreaField("description") 

@views.route('/home')
@login_required
def home():
    followed_ids = [user.id for user in current_user.followed]  # Get IDs of users current_user is following

    notes = Note.query.all()
    featured_notes = Note.query.filter(Note.publisher.in_(followed_ids)).all()  # Get posts by followed users

    recommended_profiles = suggest_profiles(current_user.id)  # Function from views_utils.py

    # Exclude current user and followed users from random_profiles
    random_profiles = User.query.filter(
        User.id != current_user.id,
        ~User.id.in_(followed_ids)
    ).all()
    
    return render_template("home.html", user=current_user, notes=notes, recommended_profiles=recommended_profiles,
                           random_profiles=random_profiles, featured_notes=featured_notes)


rooms = {}

def generate_unique_code(length):
    while True:
        code = ''.join(random.choice(ascii_uppercase) for _ in range(length))
        if code not in rooms:
            break
    return code

def generate_room_code(user1_id, user2_id):
    # Generate a consistent room code for two user IDs
    sorted_ids = sorted([str(user1_id), str(user2_id)])
    return f"room_{sorted_ids[0]}_{sorted_ids[1]}"

def generate_unique_code(length):
    while True:
        code = ""
        for _ in range(length):
            code += random.choice(ascii_uppercase)
        
        if code not in rooms:
            break
    
    return code

@views.route('/chat')
@login_required
def chat_home():
    # Show chat list of followed users
    followed_users = current_user.followed.all()
    chat_data = []

    for user in followed_users:
        last_message = ChatMessage.query.filter(
            ((ChatMessage.sender_id == current_user.id) & (ChatMessage.receiver_id == user.id)) |
            ((ChatMessage.sender_id == user.id) & (ChatMessage.receiver_id == current_user.id))
        ).order_by(ChatMessage.date.desc()).first()

        print(f"[DEBUG] User: {user.username}, Last Message: {last_message.content if last_message else 'None'}")

        chat_data.append({
            "user": user,
            "last_message": last_message.content if last_message else "",
            "timestamp": last_message.date if last_message else None
        })


    return render_template("chat.html", chat_data=chat_data)


@views.route('/chat/<int:user_id>')
@login_required
def chat_room(user_id):
    # Check if user_id is followed by current_user
    user = User.query.get_or_404(user_id)
    if not current_user.is_following(user):
        flash("You can only chat with users you follow.", "error")
        return redirect(url_for('views.chat_home'))
    
    messages = ChatMessage.query.filter(
        ((ChatMessage.sender_id == current_user.id) & (ChatMessage.receiver_id == user_id)) |
        ((ChatMessage.sender_id == user_id) & (ChatMessage.receiver_id == current_user.id))
    ).order_by(ChatMessage.date.asc()).all()

    return render_template("room.html", messages=messages, chat_with=user)

@socketio.on('send_message')
def handle_send_message(data):
    sender_id = current_user.id
    receiver_id = data['receiver_id']
    content = data['content']

    # Save message to DB
    message = ChatMessage(sender_id=sender_id, receiver_id=receiver_id, content=content)
    db.session.add(message)
    db.session.commit()

    room = f"user_{receiver_id}"
    emit('receive_message', {
        'sender_id': sender_id,
        'content': content,
        'date': message.date.strftime('%Y-%m-%d %H:%M')
    }, room=room)

    # Optional: send a notification to receiver
    emit('notification', {
        'notified_user_id': receiver_id,
        'notifier_id': sender_id,
        'type': 'chat',
        'message': f"New message from {current_user.username}"
    }, room=room)

@socketio.on("connect")
def connect():
    room = session.get("room")
    name = session.get("name")
    
    if not room or not name:
        return
    
    if room not in rooms:
        return
    
    join_room(room)
    send({"name": "System", "message": f"{name} has joined the room"}, to=room)
    rooms[room]["members"] += 1

@socketio.on("disconnect")
def disconnect():
    room = session.get("room")
    name = session.get("name")
    leave_room(room)

    if room in rooms:
        rooms[room]["members"] -= 1
        if rooms[room]["members"] <= 0:
            del rooms[room]
    
    send({"name": name, "message": "has left the room"}, to=room)



@socketio.on('connect')
def on_connect():
    if current_user.is_authenticated:
        room = f"user_{current_user.id}"
        join_room(room)

@views.route('/post', methods=['GET', 'POST'])
@login_required
def post():
    form = UploadFileForm()

    if request.method == 'POST' and form.validate_on_submit():
        title = request.form.get('title')
        code = request.form.get('code')
        chapter = request.form.get('chapter')

        raw_description = form.description.data
        clean_description = clean(raw_description)
        file = form.file.data
        filename = secure_filename(file.filename)

        ext = os.path.splitext(filename)[1].lower()
        ALLOWED_EXTENSIONS = {'.pdf', '.jpg', '.jpeg', '.png', '.gif', '.webp'}

        if ext not in ALLOWED_EXTENSIONS:
            flash("Only PDF and image files are allowed.", category="error")
            return render_template("post.html", form=form)

        unique_filename = f"{uuid.uuid4().hex}_{filename}"
        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_filename).replace('\\', '/')
        absolute_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), file_path)
        preview_path = None
        file.save(absolute_path)

      

        # Generate preview if it's a PDF
        if unique_filename.lower().endswith('.pdf'):
            preview_filename = unique_filename.rsplit('.', 1)[0] + '_preview.jpg'
            preview_path = os.path.join(current_app.config['PDF_PREVIEW_FOLDER'], preview_filename).replace('\\', '/')
            generate_pdf_preview(file_path, preview_path)

        new_note = Note(
            title=title,
            chapter=chapter,
            code=code,
            description=clean_description,
            publisher=current_user.id,
            file_path=file_path,
            preview_path=preview_path
        )
        db.session.add(new_note)
        db.session.commit()

        usernames = find_mentions(clean_description) #mention user
        for username in usernames:
            user = User.query.filter(func.lower(User.username) == username.lower()).first()
            if user and user.id != current_user.id:
                new_notification = Notification(
                notified_user_id=user.id,
                notifier_id = current_user.id,
                type='mention',
                message=f"You were mentioned in description <b>'{title} {code} | {chapter}'</b>.",
                post_id = new_note.id
                )
            db.session.add(new_notification)
            db.session.commit()

        flash('Note posted!', category='success')
        return redirect(url_for('views.home'))
    
    else:
        for field, errors in form.errors.items():
            for error in errors:
                if 'file size' in error.lower():
                    flash('Maximum file size is only 15MB', category='error')
                else:
                    flash(error, category='error')
        
    return render_template("post.html", form=form)

@views.route('/profile')
@login_required
def profile():
    show_posts = int(request.args.get('show_posts', 1)) # will show posts by default
    show_saved = int(request.args.get('show_saved', 0))

    follower_count = current_user.follower_count()
    following_count = current_user.following_count()
    points = current_user.points
    posts = current_user.notes
    points_ratios = sum(n.rating_ratio for n in posts)
    notes_count = len(posts)
    saved_posts = current_user.saved
    
    return render_template("profile.html", 
        user=current_user, 
        follower_count=follower_count, 
        following_count=following_count, 
        posts=posts, 
        notes_count=notes_count,
        points_ratios = points_ratios, 
        saved_posts=saved_posts,
        points=points,
        show_saved=show_saved,
        show_posts=show_posts
    )

@views.route('/profile/<int:user_id>')
@login_required
def user_profile(user_id):
    show_posts = 1 
    show_saved = 0

    user = User.query.get_or_404(user_id)
    follower_count = user.follower_count()
    following_count = user.following_count()
    points = user.points
    posts = user.notes
    points_ratios = sum(n.rating_ratio for n in posts)
    notes_count = len(posts)
    is_following = current_user.is_following(user)

    return render_template("profile.html",
        user=user,
        follower_count=follower_count,
        following_count=following_count,
        posts=posts,
        points_ratios = points_ratios, 
        notes_count=notes_count,
        points=points,
        is_following=is_following,
        show_posts=show_posts,
        show_saved=show_saved
    )

@views.route('/follow/<int:user_id>', methods=['POST'])
@login_required
def follow(user_id):
    user = User.query.get_or_404(user_id)
    if user == current_user:
        flash("You cannot follow yourself.", "error")
        return redirect(url_for('views.user_profile', user_id=user_id))
    if not current_user.is_following(user):
        current_user.follow(user)
        new_notification = Notification(
            notified_user_id=user.id,
            notifier_id = current_user.id,
            type='follow',
            message=f"has started following you."
            )
        db.session.add(new_notification)
        db.session.commit()
        flash(f"You are now following {user.username}", "success")
    return redirect(url_for('views.user_profile', user_id=user_id))

@views.route('/unfollow/<int:user_id>', methods=['POST'])
@login_required
def unfollow(user_id):
    user = User.query.get_or_404(user_id)
    if user == current_user:
        flash("You cannot unfollow yourself.", "error")
        return redirect(url_for('views.user_profile', user_id=user_id))
    if current_user.is_following(user):
        current_user.unfollow(user)
        db.session.commit()
        flash(f"You have unfollowed {user.username}", "success")
    return redirect(url_for('views.user_profile', user_id=user_id))

@views.route('/post/<int:post_id>', methods=['POST', 'GET'])
@login_required
def post_detail(post_id):
    post = Note.query.get(post_id)
    post_author = User.query.get(post.publisher)
    if not post:
        flash("The post you're looking for doesn't exist.", "error")
        return redirect(url_for('views.deleted_post'))

    if request.method == 'POST':
        # If the rating form was submitted
        if "rating" in request.form:
            try:
                rating_value = int(request.form.get("rating"))
            except (ValueError, TypeError):
                flash("Invalid rating submitted.", category="error")
                return redirect(url_for('views.post_detail', post_id=post_id))

            if post.publisher == current_user.id:
                flash("You can't rate your own post!", category="error")
                return redirect(url_for('views.post_detail', post_id=post_id))
            
            existing = Rating.query.filter_by(rater_id=current_user.id, note_id=post_id).first()
            if existing:
                existing.value = rating_value

                new_notification = Notification(
                    notified_user_id=post.publisher,
                    notifier_id = current_user.id,
                    type='rating',
                    message=f"Changed the rating on <b>'{post.title} {post.code} | {post.chapter}'</b> to <b>{rating_value} point(s)!</b>",
                    post_id = post_id
                    )
                db.session.add(new_notification)
            else:
                new_rating = Rating(rater_id=current_user.id, note_id=post_id, value=rating_value)
                db.session.add(new_rating)

                new_notification = Notification(
                    notified_user_id=post.publisher,
                    notifier_id = current_user.id,
                    type='rating',
                    message=f"Rated your post <b>'{post.title} {post.code} | {post.chapter}'</b> with <b>{rating_value} point(s)!</b>",
                    post_id = post_id
                    )
                db.session.add(new_notification)

            db.session.commit()

            flash(f"Thanks for rating! {rating_value} point(s) given to {post_author.username}", category="success")
            return redirect(url_for('views.post_detail', post_id=post_id))

        # If the comment form was submitted
        elif "comment_body" in request.form:
            comment_body = request.form.get('comment_body')
            clean_comment_body = clean(comment_body)
            if clean_comment_body and clean_comment_body.strip():
                new_comment = Comment(
                    body=clean_comment_body,
                    commenter_id=current_user.id,
                    note_id=post_id  # Make sure you're associating with the correct post
                )
                db.session.add(new_comment)

                if post.publisher != current_user.id:
                    super_clean_comment_body = super_clean(comment_body)
                    short_comment = shorten(super_clean_comment_body)
                    new_notification = Notification(
                        notified_user_id=post.publisher,
                        notifier_id = current_user.id,
                        type='comment',
                        message=f"Commented '{short_comment}' on your post <b>'{post.title} {post.code} | {post.chapter}'</b>.",
                        post_id = post_id
                        )
                    db.session.add(new_notification)

                usernames = find_mentions(clean_comment_body) #mention user
                for username in usernames:
                    user = User.query.filter(func.lower(User.username) == username.lower()).first()
                    if user and user.id != current_user.id:
                        new_notification = Notification(
                        notified_user_id=user.id,
                        notifier_id = current_user.id,
                        type='mention',
                        message=f"You were mentioned in a comment in <b>'{post.title} {post.code} | {post.chapter}'</b>.",
                        post_id = post_id
                        )
                        db.session.add(new_notification)
                db.session.commit()

                comments = Comment.query.filter_by(note_id=post_id).all()

                if comments:
                    total_replies = sum(len(comment.replies) for comment in post.comments)
                    post.total_comments = len(post.comments) + total_replies
                else:
                    post.total_comments = 0

                db.session.commit()
                flash('Comment posted!', category='success')
            else:
                flash('Comment cannot be empty.', category='error')

            return redirect(url_for('views.post_detail', post_id=post_id))
        
    comments = Comment.query.filter_by(note_id=post_id).all()

    ratings = post.ratings  # List of Rating objects
    ratings_count = len(ratings)
    total_points = sum(r.value for r in ratings)
    post.total_points = total_points

    if ratings_count == 0:
        post.rating_ratio = 0.0
    else:
        post.rating_ratio = round(total_points / ratings_count, 1)

    notes = post_author.notes
    post_author.points = sum(n.total_points for n in notes)

    db.session.commit()
    
    return render_template("post_detail.html", post=post, ratings_count=ratings_count, total_points=total_points, comments=comments)

@views.route('/delete_comment/<int:comment_id>', methods=['POST'])
@login_required
def delete_comment (comment_id):
    comment = Comment.query.get_or_404(comment_id)
    post_id = comment.note_id
    post = Note.query.get_or_404(post_id)

    if comment.commenter_id != current_user.id:
        flash ('You can only delete your own comments.', 'error')
        return redirect(url_for('views.post_detail', post_id = post_id))

    db.session.delete(comment)
    db.session.commit()

    total_replies = sum(len(comment.replies) for comment in post.comments)
    post.total_comments = len(post.comments) + total_replies
    db.session.commit()

    flash('Comment deleted!', 'success')
    return redirect(url_for('views.post_detail', post_id = post_id))

@views.route('/vote_comment/<int:comment_id>', methods=['POST'])
@login_required
def vote_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    vote_value = int(request.form.get('vote'))  # should be 1 or -1

    existing_vote = CommentVote.query.filter_by(voter_id=current_user.id, comment_id=comment_id).first()

    if existing_vote:
        if existing_vote.value == vote_value:
            db.session.delete(existing_vote)  # toggle vote (undo)
        else:
            existing_vote.value = vote_value  # switch vote
    else:
        new_vote = CommentVote(voter_id=current_user.id, comment_id=comment_id, value=vote_value)
        db.session.add(new_vote)

    db.session.commit()
    return redirect(request.referrer or url_for('views.home'))

@views.route('/vote_reply/<int:reply_id>', methods=['POST'])
@login_required
def vote_reply(reply_id):
    reply = Reply.query.get_or_404(reply_id)
    vote_value = int(request.form.get('vote'))  # should be 1 or -1

    existing_vote = ReplyVote.query.filter_by(voter_id=current_user.id, reply_id=reply_id).first()

    if existing_vote:
        if existing_vote.value == vote_value:
            db.session.delete(existing_vote)  # toggle vote (undo)
        else:
            existing_vote.value = vote_value  # switch vote
    else:
        new_vote = ReplyVote(voter_id=current_user.id, reply_id=reply_id, value=vote_value)
        db.session.add(new_vote)

    db.session.commit()
    return redirect(request.referrer or url_for('views.home'))

@views.route('/comment/<int:comment_id>/reply', methods=['POST'])
@login_required
def reply_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    reply_body = request.form.get('reply_body')
    clean_reply_body = clean(reply_body)
    post_id = comment.note_id
    post = Note.query.get_or_404(post_id)

    if not clean_reply_body or not clean_reply_body.strip():
        flash("Reply cannot be empty.", "error")
        return redirect(url_for('views.post_detail', post_id=comment.note_id))

    new_reply = Reply(
        body=clean_reply_body,
        comment_id=comment_id,
        user_id=current_user.id
    )
    db.session.add(new_reply)

    super_clean_reply_body = super_clean(reply_body)
    short_reply = shorten(super_clean_reply_body)
        
    if comment.commenter_id != current_user.id:
        new_notification = Notification(
            notified_user_id=comment.commenter_id,
            notifier_id = current_user.id,
            type='reply',
            message=f"replied '{short_reply}' to your comment in post <b>'{comment.note.title} {comment.note.code} | {comment.note.chapter}'</b>.",
            post_id = comment.note.id
            )
        db.session.add(new_notification)

    # Detect @mentions
    usernames = find_mentions(clean_reply_body)
    for username in usernames:
        user = User.query.filter(func.lower(User.username) == username.lower()).first()
        if user and user.id != current_user.id and comment.commenter_id != user.id:
            new_notification = Notification(
            notified_user_id=user.id,
            notifier_id = current_user.id,
            type='mention',
            message=f"You were mentioned in a reply in <b>'{comment.note.title} {comment.note.code} | {comment.note.chapter}'</b>.",
            post_id = comment.note.id
            )
            db.session.add(new_notification)

    replies = Reply.query.filter_by(comment_id=comment_id).all()

    if comment:
        total_replies = sum(len(comment.replies) for comment in post.comments)
        post.total_comments = len(post.comments) + total_replies
    else:
        post.total_comments = 0

    db.session.commit()
    flash("Reply posted!", "success")
    return redirect(url_for('views.post_detail', post_id=comment.note_id))

@views.route('/delete_reply/<int:reply_id>', methods=['POST'])
@login_required
def delete_reply (reply_id):
    reply = Reply.query.get_or_404(reply_id)
    post_id = reply.comment.note_id
    post = Note.query.get_or_404(post_id)

    if reply.user_id != current_user.id:
        flash ('You can only delete your own replies.', 'error')
        return redirect(url_for('views.post_detail', post_id = post_id))
    

    db.session.delete(reply)
    db.session.commit()
    flash('Reply deleted!', 'success')

    total_replies = sum(len(comment.replies) for comment in post.comments)
    post.total_comments = len(post.comments) + total_replies
    db.session.commit()

    return redirect(url_for('views.post_detail', post_id = post_id))

@views.route('/save_post/<int:post_id>', methods=['POST'])
@login_required
def save_post(post_id):
        post = Note.query.get_or_404(post_id)
        if post not in current_user.saved:
            current_user.saved.append(post)
            flash('Post saved!', 'success')
        else:
            current_user.saved.remove(post)
            flash('Post unsaved!', 'success')
        db.session.commit()
        return redirect(url_for('views.post_detail', post_id=post_id))

@views.route('/qna', methods=['GET', 'POST'])
@login_required
def qna():

    if request.method == 'POST':
        title = request.form.get('title')
        body = request.form.get('body')
        clean_body = clean(body)

        new_question = Question(
            title=title,
            body=clean_body,
            publisher=current_user.id
        )

        db.session.add(new_question)
        db.session.commit()

        usernames = find_mentions(clean_body) #mention user
        for username in usernames:
            user = User.query.filter(func.lower(User.username) == username.lower()).first()
            if user and user.id != current_user.id:
                new_notification = Notification(
                notified_user_id=user.id,
                notifier_id = current_user.id,
                type='mention_question',
                message=f"You were mentioned in question <b>'{title}'</b>.",
                post_id = new_question.id
                )
                db.session.add(new_notification)
            db.session.commit()

        flash('Question posted!', category='success')
        return redirect(url_for('views.qna'))
    
    questions = Question.query.all()
    return render_template("qna.html", user=current_user, questions=questions)

@views.route('/qna/<int:question_id>', methods=['GET', 'POST'])
@login_required
def qna_details(question_id):

    question = Question.query.get_or_404(question_id)
    
    return render_template("qna_details.html", user=current_user, question=question)

@views.route('/add-answer/<int:question_id>', methods=['POST'])
@login_required
def add_answer (question_id):
    question = Question.query.get_or_404(question_id)
    
    if request.method == 'POST':
        answer_body = request.form.get('answer_body')
        clean_answer_body = clean(answer_body)

        new_answer= Answer(
            body=clean_answer_body,
            question_id=question.id,
            user_id=current_user.id
        )

        db.session.add(new_answer)

        super_clean_answer_body = super_clean(answer_body)
        short_answer_body = shorten(super_clean_answer_body)
        if question.publisher != current_user.id:
            new_notification = Notification(
                notified_user_id=question.user.id,
                notifier_id = current_user.id,
                type='answer',
                post_id = question.id,
                message=f"Answered '{short_answer_body}' to your question <b>'{question.title}'</b>.",
                )
            db.session.add(new_notification)

        db.session.commit()
        flash('Answer added!', 'success')

        usernames = find_mentions(clean_answer_body) #mention user
        for username in usernames:
            user = User.query.filter(func.lower(User.username) == username.lower()).first()
            if user and user.id != current_user.id:
                new_notification = Notification(
                notified_user_id=user.id,
                notifier_id = current_user.id,
                type='mention_answer',
                message=f"You were mentioned in an answer in <b>'{question.title}'</b>.",
                post_id = question.id
                )
                db.session.add(new_notification)
            db.session.commit()

    else:
        flash('Please enter a comment.', 'error')

    return redirect(url_for('views.qna_details', user=current_user, question=question, question_id=question_id))

@views.route('/delete-answer/<int:answer_id>', methods=['POST'])
@login_required
def delete_answer (answer_id):
    answer = Answer.query.get_or_404(answer_id)
    question = answer.question
    question_id = answer.question_id

    if answer.user_id != current_user.id:
        flash ('You can only delete your own comments.', 'error')
        return redirect(url_for('views.qna_details', user=current_user, question=question, question_id=question_id))

    db.session.delete(answer)
    db.session.commit()
    flash('Answer deleted!', 'success')

    return redirect(url_for('views.qna_details', user=current_user, question=question, question_id=question_id))

@views.route('/pin_answer/<int:answer_id>', methods=['POST'])
@login_required
def pin_answer(answer_id):
    answer = Answer.query.get_or_404(answer_id)
    question = answer.question
    question_id = answer.question_id

    if question.publisher != current_user.id:
        flash('You can only pin answers to your own questions.', 'error')
        return redirect(url_for('views.qna_details', user=current_user, question=question, question_id=question_id))

    # Unpin any previously pinned answers for the same question
    Answer.query.filter_by(question_id=question.id, is_pinned=True).update({'is_pinned': False})
    
    # Pin the selected answer
    answer.is_pinned = True

    new_notification = Notification(
        notified_user_id=answer.user_id,
        notifier_id = current_user.id,
        type='pin',
        post_id = question.id,
        message=f"Pinned your answer in question <b>'{question.title}'</b>.",
        )
    db.session.add(new_notification)

    db.session.commit()

    flash('Answer pinned!', 'success')
    return redirect(url_for('views.qna_details', user=current_user, question=question, question_id=question_id))

@views.route('/unpin_answer/<int:answer_id>', methods=['POST'])
@login_required
def unpin_answer(answer_id):
    answer = Answer.query.get_or_404(answer_id)
    question = answer.question
    question_id = answer.question_id

    if question.publisher != current_user.id:
        flash('You can only unpin answers to your own questions.', 'error')
        return redirect(url_for('views.qna_details', user=current_user, question=question, question_id=question_id))
    

    answer.is_pinned = False
    db.session.commit()

    flash('Answer unpinned!', 'success')
    return redirect(url_for('views.qna_details', user=current_user, question=question, question_id=question_id))

import secrets
from PIL import Image, ImageOps


@views.route("/edit_profile", methods=["GET", "POST"])
@login_required
def edit_profile():
    if request.method == "POST":
        username = request.form.get("username")
        biography = clean(request.form.get("biography"))

        if username:
            current_user.username = username
        if biography:
            current_user.biography = biography

        if "image_profile" in request.files:
            file = request.files["image_profile"]
            if file and file.filename != "":
                random_hex = secrets.token_hex(8)
                _, f_ext = os.path.splitext(file.filename)
                picture_fn = random_hex + f_ext

                profile_pics_folder = os.path.join(current_app.root_path, "static", "profile_pics")
                os.makedirs(profile_pics_folder, exist_ok=True)

                picture_path = os.path.join(profile_pics_folder, picture_fn)

                # DELETE OLD PROFILE PICTURE IF IT'S NOT THE DEFAULT ONE
                old_picture = current_user.image_profile
                if old_picture != "default.jpg":
                    old_picture_path = os.path.join(profile_pics_folder, old_picture)
                    if os.path.exists(old_picture_path):
                        try:
                            os.remove(old_picture_path)
                        except Exception as e:
                            print(f"Error deleting old profile picture: {e}")

                # RESIZE & SAVE NEW PICTURE
                output_size = (125, 125)
                i = Image.open(file)
                i = ImageOps.fit(i, output_size, Image.Resampling.LANCZOS)
                i.save(picture_path)

                current_user.image_profile = picture_fn

        db.session.commit()
        flash("Your profile has been updated!", "success")
        return redirect(url_for("views.profile"))

    image_file = url_for('static', filename='profile_pics/' + (current_user.image_profile if current_user.image_profile else 'default.jpg'))
    return render_template('edit_profile.html', title='edit_profile')

@views.route('/edit/<int:post_id>', methods=['GET', 'POST'])
@login_required
def post_edit(post_id):
        post = Note.query.get_or_404(post_id)
        if post.publisher != current_user.id:
            abort(403)

        form = UploadFileForm()

        if request.method == 'POST':
            post.title = request.form.get('title')
            post.code = request.form.get('code')
            post.chapter = request.form.get('chapter')
            post.description = clean(form.description.data)

            db.session.commit()

            flash('Note Edited!', category='success')
            return redirect(url_for('views.post_detail', post_id=post.id))
            
        return render_template("post_edit.html", form=form, post=post)

@views.route("/delete/<int:post_id>", methods=['POST'])
@login_required
def delete_post(post_id):
    post = Note.query.get_or_404(post_id)

    if post.publisher != current_user.id:
        abort(403)

    for rating in post.ratings:
        post_author = User.query.get(post.publisher)
        post_author.points -= rating.value

    if post.file_path:
        try:
            file_path = os.path.join(current_app.root_path, post.file_path)
            if os.path.exists(file_path):
                os.remove(file_path)
            else:
                flash('File not found, but post deleted!', category='error')
            if post.file_path.endswith('.pdf'):
                preview_path = os.path.join(current_app.root_path, post.preview_path)
                os.remove(preview_path)
        except Exception as e:
            flash(f"Failed to delete file: {e}", category='error')

    db.session.delete(post)
    db.session.commit()
    flash('Note Deleted!', category='success')
    return redirect(url_for('views.home'))

@views.route('/notification')
@login_required
def notification():
    unread_notifications = Notification.query.filter_by(notified_user_id=current_user.id, is_read=False).order_by(Notification.timestamp.desc()).all()
    read_notifications = Notification.query.filter_by(notified_user_id=current_user.id, is_read=True).order_by(Notification.timestamp.desc()).all()
    total_unread_notifications = len(unread_notifications)
    return render_template("notification.html", user=current_user, unread_notifications=unread_notifications, read_notifications=read_notifications, total_unread_notifications=total_unread_notifications)

@views.route('/notifications/go-to/<int:notification_id>')
@login_required
def go_to_notification(notification_id):
    notification = Notification.query.get_or_404(notification_id)

    if notification.notified_user_id != current_user.id:
        abort(403)
    notification.is_read = True
    db.session.commit()
    
    # Redirect based on type
    if notification.type == 'follow':
        return redirect(url_for('views.user_profile', user_id=notification.notifier_id))
    elif notification.type in ['mention', 'rating', 'comment', 'reply']:
        return redirect(url_for('views.post_detail', post_id=notification.post_id))
    elif notification.type in ['answer', 'pin', 'mention_question', 'mention_answer']:
        return redirect(url_for('views.qna_details', question_id = notification.post_id))
    elif notification.type in ['chat']:
        return redirect(url_for('views.chat_room', user_id=notification.notifier_id))
    else:
        flash("Notification type is unknown.", "error")
        return redirect(url_for('views.home'))  # fallback

@views.route('/notifications/read/<int:notification_id>')
@login_required
def read_notification(notification_id):
    notification = Notification.query.get_or_404(notification_id)

    if notification.notified_user_id != current_user.id:
        abort(403)
    notification.is_read = True
    db.session.commit()
    return redirect(url_for('views.notification'))

@views.route('/delete-notification/<int:notification_id>')
@login_required
def delete_notification (notification_id):
    notification = Notification.query.get_or_404(notification_id)

    if notification.notified_user_id != current_user.id:
        abort(403)

    db.session.delete(notification)
    db.session.commit()
    flash('Notification deleted!', 'success')

    return redirect(url_for('views.notification'))

@views.route('/notifications/read_all')
@login_required
def read_notification_all():
    notifications = Notification.query.filter_by(notified_user_id=current_user.id, is_read=False).all()

    if notifications:
        for n in notifications:
            n.is_read = True
        db.session.commit()
        flash('All notifications read!', 'success')
    else:
        flash('No notifications to read!', 'error')

    return redirect(url_for('views.notification'))

@views.route('/notifications/delete_all')
@login_required
def delete_all_notification():
    notifications = Notification.query.filter_by(notified_user_id=current_user.id, is_read=True).all()

    if notifications:
        for n in notifications:
            db.session.delete(n)

        db.session.commit()
        flash('All notifications deleted!', 'success')
    else:
        flash('No notifications to delete!', 'error')

    return redirect(url_for('views.notification'))

@views.route('/search')
@login_required
def search():
    query = request.args.get('q', '')
    post_search = int(request.args.get('post', 1)) # will search notes by default
    user_search = int(request.args.get('user', 0))

    users=[]
    notes=[]

    if user_search:
        users = User.query.filter(User.username.ilike(f"%{query}%"), User.id != current_user.id).all()

    if post_search:
        notes = Note.query.filter(
            (Note.title.ilike(f"%{query}%")) | 
            (Note.code.ilike(f"%{query}%")) |
            (Note.chapter.ilike(f"%{query}%")) 
        ).all()

    return render_template("search_results.html", users=users, notes=notes, query=query, post=post_search, user=user_search)

@views.route('/explore')
@login_required
def explore():
    notes = Note.query.all()

    recommended_notes = recommend_posts(current_user.id)
    recommended_profiles = suggest_profiles(current_user.id)
    # Get IDs of users current_user is following
    followed_ids = [user.id for user in current_user.followed]

    # Exclude current user and followed users from random_profiles
    random_profiles = User.query.filter(
        User.id != current_user.id,
        ~User.id.in_(followed_ids)
    ).all()

    return render_template("explore.html", current_user=current_user, notes=notes, recommended_notes = recommended_notes, 
                           recommended_profiles=recommended_profiles, random_profiles=random_profiles)

@views.route('/post_not_found')
def deleted_post():
    return render_template('post_deleted.html')

@views.route('/profile-followers/<int:user_id>')
@login_required
def profile_followers(user_id):
    show_followers = int(request.args.get('show_followers', 1)) # will show posts by default
    show_following = int(request.args.get('show_following', 0))

    user = User.query.get_or_404(user_id)
    follower_count = user.follower_count()
    following_count = user.following_count()
    points = user.points
    posts = user.notes
    followers = user.followers.all()
    following = user.followed.all()
    notes_count = len(posts)
    is_following = current_user.is_following(user)

    return render_template("followers.html", 
        user=user, 
        follower_count=follower_count, 
        following_count=following_count, 
        notes_count=notes_count, 
        points=points,
        show_followers=show_followers,
        show_following=show_following,
        is_following=is_following,
        followers=followers,
        following=following
    )

@views.route('/toggle_theme', methods=['POST'])
@login_required
def toggle_theme():
    current_theme = getattr(current_user, 'theme_preference', 'light')
    new_theme = 'dark' if current_theme == 'light' else 'light'
    current_user.theme_preference = new_theme
    db.session.commit()
    return redirect(request.referrer or url_for('views.home'))


@views.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    if request.method == 'POST':
        # Handle theme preference
        if 'theme' in request.form:
            theme = request.form.get('theme', 'light')
            current_user.theme_preference = theme
            db.session.commit()
            flash('Theme updated successfully!', 'success')
            return redirect(url_for('views.settings'))
        
        # Handle password change
        elif 'new_password' in request.form:
            current_password = request.form.get('current_password')
            new_password = request.form.get('new_password')
            confirm_password = request.form.get('confirm_password')
            
            # Verify current password
            if not check_password_hash(current_user.password, current_password):
                flash('Current password is incorrect.', 'error')
                return redirect(url_for('views.settings'))
            
            # Check password confirmation
            if new_password != confirm_password:
                flash('New passwords do not match.', 'error')
                return redirect(url_for('views.settings'))
            
            # Check password length
            if len(new_password) < 7:
                flash('New password must be at least 7 characters long.', 'error')
                return redirect(url_for('views.settings'))
            
            # Update password
            current_user.password = generate_password_hash(new_password, method='pbkdf2:sha256')
            db.session.commit()
            flash('Password updated successfully!', 'success')
            return redirect(url_for('views.settings'))
    
    return render_template('settings.html')

@views.route('/report', methods=['GET', 'POST'])
@login_required
def report():
    if request.method == 'GET':
        note_id = request.args.get('note_id')
        comment_id = request.args.get('comment_id')
        return render_template('report_form.html', note_id=note_id, comment_id=comment_id)

    # POST method
    reason = request.form.get('reason')
    note_id = request.form.get('note_id')
    comment_id = request.form.get('comment_id')

    if not reason:
        flash("Please enter a reason for your report.", "warning")
        return redirect(request.referrer)

    # Check for duplicate reports
    existing = Report.query.filter_by(
        reported_by=current_user.id,
        note_id=note_id if note_id else None,
        comment_id=comment_id if comment_id else None
    ).first()

    if existing:
        flash("You've already reported this.", "info")
        return redirect(request.referrer)

    # Convert 'None' string to None for foreign keys
    note_id_val = None if not note_id or note_id == 'None' else note_id
    comment_id_val = None if not comment_id or comment_id == 'None' else comment_id

    report = Report(
        reported_by=current_user.id,
        note_id=note_id_val,
        comment_id=comment_id_val,
        reason=reason
    )
    db.session.add(report)
    db.session.commit()

    # Send email notification to admins
    admin_email = "studytt518@gmail.com"
    admin_user = User.query.filter(User.email.ilike(admin_email)).first()
    if admin_user:
        reporter = current_user.username
        reported_item = ""
        if note_id:
            reported_item = f"Post ID: {note_id} - {url_for('views.post_detail', post_id=note_id)}"
        elif comment_id:
            comment = Comment.query.get(comment_id)
            note_id_for_comment = comment.note_id if comment else None
            reported_item = f"Comment ID: {comment_id} - {url_for('views.post_detail', post_id=note_id_for_comment)}"
        message = f"New report submitted by {reporter}.\nReason: {reason}\nReported Content: {reported_item}"
        new_notification = Notification(
            notified_user_id=admin_user.id,
            notifier_id=current_user.id,
            type='report',
            message=message,
            post_id=note_id if note_id else note_id_for_comment
        )
        db.session.add(new_notification)
        db.session.commit()

    flash("Thank you. Your report has been submitted.", "success")
    return redirect(url_for('views.home'))


# Admin: view reports
@views.route('/admin/reports')
@login_required
def admin_reports():
    if not (current_user.is_authenticated and current_user.email and current_user.email.lower() == "studytt518@gmail.com"):
        return "Unauthorized", 403

    status_filter = request.args.get('status', 'pending')
    reports = Report.query.filter_by(status=status_filter).order_by(Report.timestamp.desc()).all()
    return render_template('admin_reports.html', reports=reports, status_filter=status_filter)


# Admin: update report status
@views.route('/admin/report/<int:report_id>/update', methods=['POST'])
@login_required
def update_report_status(report_id):
    if not (current_user.is_authenticated and current_user.email and current_user.email.lower() == "studytt518@gmail.com"):
        return "Unauthorized", 403

    report = Report.query.get_or_404(report_id)
    new_status = request.form.get('status')

    if new_status in ['reviewed', 'dismissed']:
        report.status = new_status
        db.session.commit()
        flash("Report status updated.", "success")
    else:
        flash("Invalid status.", "danger")

    return redirect(url_for('admin_reports'))