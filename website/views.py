from flask import Blueprint, render_template, current_app, request, flash, redirect, url_for, session, abort
from flask_login import login_required, current_user
from flask_wtf import FlaskForm
from wtforms import FileField, SubmitField, StringField, TextAreaField
from werkzeug.utils import secure_filename
import os
from wtforms.validators import InputRequired, DataRequired
from .models import Note, ChatMessage, User, Question, Rating, Answer
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

def generate_unique_code(length):
    while True:
        code = ""
        for _ in range(length):
            code += random.choice(ascii_uppercase)
        
        if code not in rooms:
            break
    
    return code

@views.route("/chat", methods=["POST", "GET"])
def chat_home():
    session.clear()
    if request.method == "POST":
        name = request.form.get("name")
        code = request.form.get("code")
        join = request.form.get("join", False)
        create = request.form.get("create", False)

        if not name:
            return render_template("chat.html", error="Please enter a name.", code=code, name=name)

        if join != False and not code:
            return render_template("chat.html", error="Please enter a room code.", code=code, name=name)
        
        room = code
        if create != False:
            room = generate_unique_code(4)
            rooms[room] = {"members": 0, "messages": []}
        elif code not in rooms:
            return render_template("chat.html", error="Room does not exist.", code=code, name=name)
        
        session["room"] = room
        session["name"] = name
        return redirect(url_for("views.room"))

    return render_template("chat.html")

@views.route("/room")
def room():
    room = session.get("room")
    if room is None or session.get("name") is None or room not in rooms:
        return redirect(url_for("views.chat_home"))  # Fixed redirect

    return render_template("room.html", code=room, messages=rooms[room]["messages"])

@socketio.on("message")
def message(data):
    room = session.get("room")
    name = session.get("name")
    
    print(f"Message received: {data}")
    print(f"Session room: {room}, name: {name}")
    
    if not room or room not in rooms:
        print(f"Room {room} not found or not in session")
        return 
    
    content = {
        "name": name,
        "message": data["data"]
    }
    
    print(f"Sending message to room {room}: {content}")
    send(content, to=room)
    rooms[room]["messages"].append(content)

@socketio.on("connect")
def connect():
    room = session.get("room")
    name = session.get("name")
    
    print(f"Socket connected. Session data: room={room}, name={name}")
    
    if not room or not name:
        print("No room or name in session")
        return
    
    if room not in rooms:
        print(f"Room {room} not found")
        return
    
    join_room(room)
    print(f"{name} joined room {room}")
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
    print(f"{name} has left the room {room}")


@views.route('/post', methods=['GET', 'POST'])
@login_required
def post():
    form = UploadFileForm()

    if request.method == 'POST':
        title = request.form.get('title')
        code = request.form.get('code')
        chapter = request.form.get('chapter')

        if form.validate_on_submit():
            description = form.description.data
            file = form.file.data
            filename = secure_filename(file.filename)
            file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename).replace('\\', '/')
            absolute_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), file_path)
            file.save(absolute_path)

            new_note = Note(
                title=title,
                chapter=chapter,
                code=code,
                description=description,
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
        db.session.commit()
        flash(f"You are now following {user.username}.", "success")
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
        flash(f"You have unfollowed {user.username}.", "success")
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
    if request.method == 'POST':
        rating_value = int(request.form.get("rating"))
    
        if post.publisher == current_user.id:
            flash("You can't rate your own post!", category="error")
            return redirect(url_for('views.post_detail', post_id=post_id))
        
        existing = Rating.query.filter_by(rater_id=current_user.id, note_id=post_id).first()
        if existing:
            post_author.points -= existing.value
            existing.value = rating_value
        else:
            new_rating = Rating(rater_id=current_user.id, note_id=post_id, value=rating_value)
            db.session.add(new_rating)

        post_author.points += rating_value

        db.session.commit()
        flash(f"Thanks for rating! {rating_value} point(s) given to {post_author.username}", category="success")
        return redirect(url_for('views.post_detail', post_id=post_id))
    
    return render_template("post_detail.html", post=post)

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

        new_question = Question(
            title=title,
            body=body,
            publisher=current_user.id
        )

        db.session.add(new_question)
        db.session.commit()

        flash('Question posted!', category='success')
        return redirect(url_for('views.qna'))
    
    question = Question.query.all()
    return render_template("qna.html", user=current_user, question=question)

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
                flash('File not found, but note deleted!', category='error')
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
        db.session.commit()
        flash('Comment added!', 'success')
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


@views.route('/pin_answer<int:answer_id>', methods=['POST'])
@login_required
def pin_answer(answer_id):
    answer = Answer.query.get_or_404(answer_id)
    Question= answer.question

    if Question.publisher != (current_user.id):
        flash('You can only pin answers to your own questions.', 'error')
        return redirect(url_for('views.qna'))
    

    Answer.query.filter_by(question_id=answer_id, is_pinned=True).update({'is_pinned': False})
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