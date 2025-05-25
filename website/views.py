from flask import Blueprint, render_template, current_app, request, flash, redirect, url_for, session, abort
from flask_login import login_required, current_user
from flask_wtf import FlaskForm
from wtforms import FileField, SubmitField, StringField, TextAreaField
from werkzeug.utils import secure_filename
import os
from wtforms.validators import InputRequired, DataRequired
from .models import Note, ChatMessage, User, Question, Rating, Answer, Comment, CommentVote, Reply, Notification
from . import db
from wtforms.widgets import TextArea
from flask import Flask, render_template, request, redirect, url_for
from flask_socketio import SocketIO, join_room, leave_room, send
from . import socketio
from string import ascii_uppercase
import random
import secrets
import os
from PIL import Image
from sqlalchemy.sql import func
import bleach
import re

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

views = Blueprint('views', __name__, template_folder='../templates')


class UploadFileForm(FlaskForm):
        file = FileField("File", validators=[InputRequired()])
        submit = SubmitField("Upload")
        description = TextAreaField("description") 

@views.route('/home')
@login_required
def home():
        notes = Note.query.all()
        return render_template("home.html", user=current_user, notes=notes)

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
    return render_template("chat.html", followed_users=followed_users)

@views.route('/chat/<int:user_id>')
@login_required
def chat_room(user_id):
    # Check if user_id is followed by current_user
    user = User.query.get_or_404(user_id)
    if not current_user.is_following(user):
        flash("You can only chat with users you follow.", "error")
        return redirect(url_for('views.chat_home'))

    room_code = generate_room_code(current_user.id, user_id)
    if room_code not in rooms:
        rooms[room_code] = {"members": 0, "messages": []}

    session["room"] = room_code
    session["name"] = current_user.username
    session["chat_with"] = user.username

    return render_template("room.html", code=room_code, messages=rooms[room_code]["messages"], chat_with=user)

@socketio.on("message")
def message(data):
    room = session.get("room")
    name = session.get("name")
    
    if not room or room not in rooms:
        return 
    
    content = {
        "name": name,
        "message": data["data"]
    }
    
    send(content, to=room)
    rooms[room]["messages"].append(content)

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
        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename).replace('\\', '/')
        absolute_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), file_path)
        file.save(absolute_path)

        new_note = Note(
            title=title,
            chapter=chapter,
            code=code,
            description=clean_description,
            publisher=current_user.id,
            file_path=file_path
        )

        db.session.add(new_note)
        db.session.commit()

        flash('Note posted!', category='success')
        return redirect(url_for('views.home'))
        
    return render_template("post.html", form=form)

@views.route('/profile')
@login_required
def profile():
        follower_count = current_user.follower_count()
        following_count = current_user.following_count()
        points = current_user.points
        posts = current_user.notes.all() if hasattr(current_user.notes, 'all') else current_user.notes
        notes_count = len(posts)
        
        return render_template("profile.html", user=current_user, follower_count=follower_count, following_count=following_count, posts=posts, notes_count=notes_count, points=points)

@views.route('/profile/<int:user_id>')
@login_required
def user_profile(user_id):
        user = User.query.get_or_404(user_id)
        follower_count = user.follower_count()
        following_count = user.following_count()
        points = user.points
        posts = user.notes.all() if hasattr(user.notes, 'all') else user.notes
        notes_count = len(posts)
        is_following = current_user.is_following(user)
        return render_template("profile.html", user=user, follower_count=follower_count, following_count=following_count, posts=posts, notes_count=notes_count, points=points, is_following=is_following)

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

@views.route('/saved')
@login_required
def saved():
        follower_count = current_user.follower_count()
        following_count = current_user.following_count()
        # Don't call .all() on current_user.saved since it's already a list
        saved_posts = current_user.saved
        # Get the notes count (be careful here - use .all() if it's a query, but not if it's already a list)
        notes_count = len(current_user.notes.all()) if hasattr(current_user.notes, 'all') else len(current_user.notes)
        
        return render_template("saved.html", user=current_user, 
                            follower_count=follower_count, 
                            following_count=following_count, 
                            saved_posts=saved_posts,
                            notes_count=notes_count)


@views.route('/post/<int:post_id>', methods=['POST', 'GET'])
@login_required
def post_detail(post_id):
    post = Note.query.get_or_404(post_id)
    post_author = User.query.get(post.publisher)

    ratings = post.ratings  # List of Rating objects
    ratings_count = len(ratings)
    total_points = sum(r.value for r in ratings)

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
                post_author.points -= existing.value
                existing.value = rating_value

                new_notification = Notification(
                    notified_user_id=post.publisher,
                    notifier_id = current_user.id,
                    type='rating',
                        message=f"Changed the rating on <b>'{post.title} {post.code} | {post.chapter}'</b> to <b>{rating_value} point(s)!</b>"
                    )
                db.session.add(new_notification)
            else:
                new_rating = Rating(rater_id=current_user.id, note_id=post_id, value=rating_value)
                db.session.add(new_rating)

                new_notification = Notification(
                    notified_user_id=post.publisher,
                    notifier_id = current_user.id,
                    type='rating',
                        message=f"Rated your post <b>'{post.title} {post.code} | {post.chapter}'</b> with <b>{rating_value} point(s)!</b>"
                    )
                db.session.add(new_notification)

            post_author.points += rating_value

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
                    short_comment = super_clean_comment_body[:20] + '...' if len(super_clean_comment_body) > 20 else super_clean_comment_body
                    new_notification = Notification(
                        notified_user_id=post.publisher,
                        notifier_id = current_user.id,
                        type='comment',
                            message=f"Commented '{short_comment}' on your post <b>'{post.title} {post.code} | {post.chapter}'</b>."
                        )
                    db.session.add(new_notification)
                db.session.commit()
                flash('Comment posted!', category='success')
            else:
                flash('Comment cannot be empty.', category='error')

            return redirect(url_for('views.post_detail', post_id=post_id))

        

    comments = Comment.query.filter_by(note_id=post_id).all()
    
    return render_template("post_detail.html", post=post, ratings_count=ratings_count, total_points=total_points, comments=comments)

@views.route('/delete_comment/<int:comment_id>', methods=['POST'])
@login_required
def delete_comment (comment_id):
    comment = Comment.query.get_or_404(comment_id)
    post_id = comment.note_id

    if comment.user_id != current_user.id:
        flash ('You can only delete your own comments.', 'error')
        return redirect(url_for('views.post_detail', post_id = post_id))
    

    db.session.delete(comment)
    db.session.commit()
    flash('Comment deleted!', 'success')

    return redirect(url_for('views.post_detail', post_id = post_id))

@views.route('/vote_comment/<int:comment_id>', methods=['POST'])
@login_required
def vote_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    vote_value = int(request.form.get('vote'))  # should be 1 or -1

    existing_vote = CommentVote.query.filter_by(user_id=current_user.id, comment_id=comment_id).first()

    if existing_vote:
        if existing_vote.value == vote_value:
            db.session.delete(existing_vote)  # toggle vote (undo)
        else:
            existing_vote.value = vote_value  # switch vote
    else:
        new_vote = CommentVote(user_id=current_user.id, comment_id=comment_id, value=vote_value)
        db.session.add(new_vote)

    db.session.commit()
    return redirect(request.referrer or url_for('views.home'))

@views.route('/comment/<int:comment_id>/reply', methods=['POST'])
@login_required
def reply_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    reply_body = request.form.get('reply_body')
    clean_reply_body = clean(reply_body)

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
    short_reply = super_clean_reply_body[:20] + '...' if len(super_clean_reply_body) > 20 else super_clean_reply_body
    if comment.user.id != current_user.id:
        new_notification = Notification(
            notified_user_id=comment.user.id,
            notifier_id = current_user.id,
            type='reply',
            message=f"replied '{short_reply}' to your comment in post <b>'{comment.note.title} {comment.note.code} | {comment.note.chapter}'</b>."
            )
        db.session.add(new_notification)
    db.session.commit()
    flash("Reply posted!", "success")
    return redirect(url_for('views.post_detail', post_id=comment.note_id))

@views.route('/delete_reply/<int:reply_id>', methods=['POST'])
@login_required
def delete_reply (reply_id):
    reply = Reply.query.get_or_404(reply_id)
    post_id = reply.comment.note_id

    if reply.user_id != current_user.id:
        flash ('You can only delete your own comments.', 'error')
        return redirect(url_for('views.post_detail', post_id = post_id))
    

    db.session.delete(reply)
    db.session.commit()
    flash('Reply deleted!', 'success')

    return redirect(url_for('views.post_detail', post_id = post_id))

@views.route('/save_post/<int:post_id>', methods=['POST'])
@login_required
def save_post(post_id):
        post = Note.query.get_or_404(post_id)
        if post not in current_user.saved:
            current_user.saved.append(post)
            db.session.commit()
            flash('Post saved successfully!', 'success')
        else:
            flash('Post already saved.', 'info')
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

        flash('Question posted!', category='success')
        return redirect(url_for('views.qna'))
    
    questions = Question.query.all()
    return render_template("qna.html", user=current_user, questions=questions)

import secrets
from PIL import Image

@views.route("/edit_profile", methods=["GET", "POST"])
@login_required
def edit_profile():
        if request.method == "POST":
            username = request.form.get("username")
            biography = request.form.get("biography")

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

                    # Make sure the directory exists
                    profile_pics_folder = os.path.join(current_app.root_path, "static", "profile_pics")
                    os.makedirs(profile_pics_folder, exist_ok=True)

                    picture_path = os.path.join(profile_pics_folder, picture_fn)

                    # Resize image to 125x125 pixels
                    output_size = (125, 125)
                    i = Image.open(file)
                    i.thumbnail(output_size)
                    i.save(picture_path)

                    current_user.image_profile = picture_fn

            db.session.commit()
            flash("Your profile has been updated!", "success")
            return redirect(url_for("views.profile"))

        image_file = url_for('static', filename='profile_pics/' + current_user.image_profile)
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
            post.description = form.description.data

            db.session.commit()

            flash('Note Edited!', category='success')
            return redirect(url_for('views.post_detail', post_id=post.id))
            
        return render_template("post_edit.html", form=form, post=post)

@views.route("/delete/<int:post_id>", methods=['POST'])
@login_required
def delete(post_id):
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
        except Exception as e:
            flash(f"Failed to delete file: {e}", category='error')

    db.session.delete(post)
    db.session.commit()
    flash('Note Deleted!', category='success')
    return redirect(url_for('views.home'))

@views.route('/add-answer/<int:question_id>', methods=['POST'])
@login_required
def add_answer (question_id):
    question = Question.query.get_or_404(question_id)
    
    if request.method == 'POST':
        answer_body = request.form.get('answer_body')

        new_answer= Answer(
            body=answer_body,
            question_id=question.id,
            user_id=current_user.id
        )

        db.session.add(new_answer)

        super_clean_answer_body = super_clean(answer_body)
        short_answer_body = super_clean_answer_body[:20] + '...' if len(super_clean_answer_body) > 20 else super_clean_answer_body
        if question.publisher != current_user.id:
            new_notification = Notification(
                notified_user_id=question.user.id,
                notifier_id = current_user.id,
                type='reply',
                message=f"Answered '{short_answer_body}' to your question <b>'{question.title}'</b>."
                )
            db.session.add(new_notification)

        db.session.commit()
        flash('Answer added!', 'success')
    else:
        flash('Please enter a comment.', 'error')

    return redirect(url_for('views.qna'))

@views.route('/delete-answer/<int:answer_id>', methods=['POST'])
@login_required
def delete_answer (answer_id):
    answer = Answer.query.get_or_404(answer_id)

    if answer.user_id != current_user.id:
        flash ('You can only delete your own comments.', 'error')
        return redirect(url_for('views.qna'))
    

    db.session.delete(answer)
    db.session.commit()
    flash('Comment deleted!', 'success')

    return redirect(url_for('views.qna'))

@views.route('/notification')
@login_required
def notification():
    unread_notifications = Notification.query.filter_by(notified_user_id=current_user.id, is_read=False).order_by(Notification.timestamp.desc()).all()
    read_notifications = Notification.query.filter_by(notified_user_id=current_user.id, is_read=True).order_by(Notification.timestamp.desc()).all()
    total_unread_notifications = len(unread_notifications)
    return render_template("notification.html", user=current_user, unread_notifications=unread_notifications, read_notifications=read_notifications, total_unread_notifications=total_unread_notifications)

@views.route('/notifications/read/<int:notification_id>')
@login_required
def read_notification(notification_id):
    notification = Notification.query.get_or_404(notification_id)

    if notification.notified_user_id != current_user.id:
        abort(403)
    notification.is_read = True
    db.session.commit()
    return redirect(url_for('views.notification'))

@views.route('/notifications/unread/<int:notification_id>')
@login_required
def unread_notification(notification_id):
    notification = Notification.query.get_or_404(notification_id)
    if notification.notified_user_id != current_user.id:
        abort(403)
    notification.is_read = False
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

@views.route('/pin_answer<int:answer_id>', methods=['POST'])
@login_required
def pin_answer(answer_id):
    answer = Answer.query.get_or_404(answer_id)
    question = answer.question

    if question.publisher != current_user.id:
        flash('You can only pin answers to your own questions.', 'error')
        return redirect(url_for('views.qna'))

    # Unpin any previously pinned answers for the same question
    Answer.query.filter_by(question_id=question.id, is_pinned=True).update({'is_pinned': False})
    
    # Pin the selected answer
    answer.is_pinned = True
    db.session.commit()

    flash('Answer pinned!', 'success')
    return redirect(url_for('views.qna'))

@views.route('/unpin_answer<int:answer_id>', methods=['POST'])
@login_required
def unpin_answer(answer_id):
    answer = Answer.query.get_or_404(answer_id)
    Question= answer.question

    if Question.publisher != (current_user.id):
        flash('You can only unpin answers to your own questions.', 'error')
        return redirect(url_for('views.qna'))
    

    answer.is_pinned = False
    db.session.commit()

    flash('Answer unpinned!', 'success')
    return redirect(url_for('views.qna'))

@views.route('/search')
def search():
    query = request.args.get('q', '')

    users = User.query.filter(User.username.ilike(f"%{query}%")).all()
    notes = Note.query.filter(
        (Note.title.ilike(f"%{query}%")) | 
        (Note.code.ilike(f"%{query}%")) |
        (Note.chapter.ilike(f"%{query}%")) 
    ).all()

    return render_template("search_results.html", users=users, notes=notes, query=query)