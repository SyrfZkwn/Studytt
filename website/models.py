from . import db 
from flask_login import UserMixin
from sqlalchemy.sql import func 

class Note(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100))
    code = db.Column(db.String(100))
    chapter = db.Column(db.String(100))
    description = db.Column(db.Text)
    date = db.Column(db.DateTime(timezone=True), default=func.now())
    file_path = db.Column(db.String(255))
    publisher = db.Column(db.String, db.ForeignKey('user.id'))

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True)
    password = db.Column(db.String(150))
    username = db.Column(db.String(150))
    file = db.Column(db.LargeBinary)
    notes = db.relationship('Note')