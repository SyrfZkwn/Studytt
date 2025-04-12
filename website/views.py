from flask import Blueprint, render_template

views = Blueprint('view', __name__)

@views.route('/')
def home():
    return render_template("home.html")