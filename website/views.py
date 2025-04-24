from flask import Blueprint, render_template, current_app, request, flash, redirect, url_for
from flask_login import login_required, current_user
from flask_wtf import FlaskForm
from wtforms import FileField, SubmitField
from werkzeug.utils import secure_filename
import os
from wtforms.validators import InputRequired
from .models import Note
from . import db

views = Blueprint('views', __name__)

class UploadFileForm(FlaskForm):
    file = FileField("File", validators=[InputRequired()])
    submit = SubmitField("Upload")

@views.route('/home')
@login_required
def home():
    return render_template("home.html", user=current_user)

@views.route('/post', methods=['GET', 'POST'])
@login_required
def post():
    form = UploadFileForm()

    if request.method == 'POST':
        title = request.form.get('title')
        code = request.form.get('code')
        chapter = request.form.get('chapter')
        description = request.form.get('description')

        if form.validate_on_submit():
            file = form.file.data
            file.save(os.path.join(os.path.abspath(os.path.dirname(__file__)),current_app.config['UPLOAD_FOLDER'],secure_filename(file.filename)))

        new_note = Note(
            title=title,
            chapter=chapter,
            code=code,
            description=description,
            publisher=current_user.id
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
    return render_template("profile.html", user=current_user, follower_count=follower_count, following_count=following_count)

@views.route('/saved')
@login_required
def saved(): return render_template("saved.html", user=current_user)