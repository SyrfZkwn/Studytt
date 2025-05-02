from flask import Blueprint, render_template, current_app, request, flash, redirect, url_for, session 
from flask_login import login_required, current_user
from flask_wtf import FlaskForm
from wtforms import FileField, SubmitField, StringField, TextAreaField
from werkzeug.utils import secure_filename
import os
from wtforms.validators import InputRequired, DataRequired
from .models import Note, ChatMessage, User, Question, Rating
from . import db
from wtforms.widgets import TextArea
from flask import Flask, render_template, request, redirect, url_for
from flask_socketio import SocketIO, join_room, leave_room, send
from . import socketio
from string import ascii_uppercase
import random

views = Blueprint('views', __name__)

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
    # Handle both cases - query object or list
    posts = current_user.notes.all() if hasattr(current_user.notes, 'all') else current_user.notes
    notes_count = len(posts)
    
    return render_template("profile.html", user=current_user, 
                          follower_count=follower_count, 
                          following_count=following_count, 
                          posts=posts,
                          notes_count=notes_count)

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
    if request.method == 'POST':
        rating_value = int(request.form.get("rating"))
    
        if post.publisher == current_user.id:
            flash("You can't rate your own post!", category="error")
            return redirect(url_for('views.post_detail', post_id=post_id))
        
        existing = Rating.query.filter_by(rater_id=current_user.id, note_id=post_id).first()
        if existing:
            existing.value = rating_value
        else:
            new_rating = Rating(rater_id=current_user.id, note_id=post_id, value=rating_value)
            db.session.add(new_rating)

        post_author = User.query.get(post.publisher)
        post_author.points += rating_value

        db.session.commit()
        flash(f"Thanks for rating! {rating_value} point(s) given to {post_author.username}", category="success")
        return redirect(url_for('views.post_detail', post_id=post_id))
    
    return render_template("post_detail.html", post=post)

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
        if "image_profile" not in request.files:
            flash("No file part", "error")
            return redirect(request.url)
        file = request.files["image_profile"]
        if file.filename == "":
            flash("No selected file", "error")
            return redirect(request.url)
        if file:
            random_hex = secrets.token_hex(8)
            _, f_ext = os.path.splitext(file.filename)
            picture_fn = random_hex + f_ext
            picture_path = os.path.join(current_app.root_path, "static/profile_pics", picture_fn)

            # Resize image to 125x125 pixels
            output_size = (125, 125)
            i = Image.open(file)
            i.thumbnail(output_size)
            i.save(picture_path)

            current_user.image_profile = picture_fn
            db.session.commit()
            flash("Your profile picture has been updated!", "success")
            return redirect(url_for("views.profile"))
    image_file = url_for('static', filename='profile_pics/' + current_user.image_profile)
    return render_template('edit_profile.html', title='edit_profile')
