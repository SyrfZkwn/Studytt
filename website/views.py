from flask import Blueprint, render_template, current_app, request, flash, redirect, url_for
from flask_login import login_required, current_user
from flask_wtf import FlaskForm
from wtforms import FileField, SubmitField, StringField, TextAreaField
from werkzeug.utils import secure_filename
import os
from wtforms.validators import InputRequired, DataRequired
from .models import Note, Question
from . import db
from wtforms.widgets import TextArea

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
    posts = current_user.notes
    return render_template("profile.html", user=current_user, follower_count=follower_count, following_count=following_count, posts=posts)

@views.route('/saved')
@login_required
def saved():
    follower_count = current_user.follower_count()
    following_count = current_user.following_count()
    saved_posts = current_user.saved
    return render_template("saved.html", user=current_user, follower_count=follower_count, following_count=following_count, saved_posts=saved_posts)

@views.route('/post/<int:post_id>')
@login_required
def post_detail(post_id):
    post = Note.query.get_or_404(post_id)
    return render_template("post_detail.html", post=post)

@views.route('/chat')
@login_required
def chat():
    followers = current_user.followers.all()
    following = current_user.followed.all()
    return render_template("chat.html", user=current_user, followers=followers, following=following)


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
