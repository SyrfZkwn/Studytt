from flask import Blueprint, render_template, current_app
from flask_login import login_required, current_user
from flask_wtf import FlaskForm
from wtforms import FileField, SubmitField, StringField, DateField
from werkzeug.utils import secure_filename
import os
from wtforms.validators import InputRequired

class UploadFileForm(FlaskForm):
    subject = StringField("Subject", validators=[InputRequired()])
    chapter = StringField("Chapter", validators=[InputRequired()])
    date = DateField("Date", validators=[InputRequired()])
    publisher = StringField("Publisher", validators=[InputRequired()])
    file = FileField("File", validators=[InputRequired()])
    submit = SubmitField("Upload File")

views = Blueprint('views', __name__)

@views.route('/home')
@login_required
def home():
    return render_template("home.html", user=current_user)

@views.route('/post', methods=['GET', 'POST'])
def post():
    form = UploadFileForm()
    if form.validate_on_submit():
        file = form.file.data
        file.save(os.path.join(os.path.abspath(os.path.dirname(__file__)),current_app.config['UPLOAD_FOLDER'],secure_filename(file.filename)))
        return "File has been uploaded."
    return render_template("post.html", form=form)