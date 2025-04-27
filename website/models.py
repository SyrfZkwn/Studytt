from . import db 
from flask_login import UserMixin
from sqlalchemy.sql import func 

followers = db.Table('followers',
    db.Column('follower_id', db.Integer, db.ForeignKey('user.id')),
    db.Column('followed_id', db.Integer, db.ForeignKey('user.id'))
)

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

    followed = db.relationship(
        'User', secondary=followers,
        primaryjoin=(followers.c.follower_id == id),
        secondaryjoin=(followers.c.followed_id == id),
        backref=db.backref('followers', lazy='dynamic'), lazy='dynamic')

    def follow(self, user):
        if not self.is_following(user):
            self.followed.append(user)

    def unfollow(self, user):
        if self.is_following(user):
            self.followed.remove(user)

    def is_following(self, user):
        return self.followed.filter(
            followers.c.followed_id == user.id).count() > 0

    def follower_count(self):
        return self.followers.count()

    def following_count(self):
        return self.followed.count()
