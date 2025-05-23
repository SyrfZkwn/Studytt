from . import db 
from flask_login import UserMixin
from sqlalchemy.sql import func
from datetime import datetime, timezone
import pytz

def get_local_time():
    local_tz = pytz.timezone('Asia/Singapore')
    return datetime.now(local_tz)

followers = db.Table('followers',
    db.Column('follower_id', db.Integer, db.ForeignKey('user.id')),
    db.Column('followed_id', db.Integer, db.ForeignKey('user.id'))
)

saved_posts = db.Table('saved_posts',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id')),
    db.Column('note_id', db.Integer, db.ForeignKey('note.id'))
)

class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.Text)
    body = db.Column(db.Text)
    date = db.Column(db.DateTime(timezone=True), default=get_local_time)
    publisher = db.Column(db.Integer, db.ForeignKey('user.id'))
    answers = db.relationship('Answer', backref='question', lazy=True)
    


class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)  # Can be null for room messages
    room_code = db.Column(db.String(10), nullable=True)  # For room-based messages
    message = db.Column(db.Text)
    date = db.Column(db.DateTime(timezone=True), default=get_local_time)

class Note(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(50))
    code = db.Column(db.String(10))
    chapter = db.Column(db.String(30))
    description = db.Column(db.Text)
    date = db.Column(db.DateTime(timezone=True), default=get_local_time)
    file_path = db.Column(db.String(255))
    publisher = db.Column(db.Integer, db.ForeignKey('user.id'))
    comments = db.relationship('Comment', backref='note', cascade='all, delete', lazy=True)
    ratings = db.relationship('Rating', backref='note', cascade='all, delete', passive_deletes=True)

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True)
    password = db.Column(db.String(150))
    username = db.Column(db.String(150))
    biography = db.Column(db.Text, nullable=True)       # New field for biography
    image_profile = db.Column(db.String(20), nullable=False, default='default.jpg')
    file = db.Column(db.LargeBinary)
    points = db.Column(db.Integer, default=0)
    notes = db.relationship('Note', backref='user', lazy=True)
    saved = db.relationship('Note', secondary=saved_posts, backref='saved_by')
    questions = db.relationship('Question', backref='user', lazy=True)


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

class Rating(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    rater_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    note_id = db.Column(db.Integer, db.ForeignKey('note.id', ondelete='CASCADE'), nullable=False)
    value = db.Column(db.Integer, nullable=False)

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.Text, nullable=False)
    date_posted = db.Column(db.DateTime(timezone=True), default=get_local_time)
    note_id = db.Column(db.Integer, db.ForeignKey('note.id'), nullable=False)
    commenter_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    user = db.relationship('User', backref='comments', lazy=True)
    votes = db.relationship('CommentVote', backref='comment', lazy=True, cascade="all, delete-orphan")
    replies = db.relationship('Reply',backref='comment',lazy=True,cascade='all, delete-orphan',passive_deletes=True)

class CommentVote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    comment_id = db.Column(db.Integer, db.ForeignKey('comment.id', ondelete='CASCADE'), nullable=False)
    value = db.Column(db.Integer, nullable=False)  # +1 = upvote, -1 = downvote

    __table_args__ = (db.UniqueConstraint('user_id', 'comment_id', name='unique_comment_vote'),)

class Reply(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.Text, nullable=False)
    date_posted = db.Column(db.DateTime(timezone=True), default=get_local_time)
    comment_id = db.Column(db.Integer, db.ForeignKey('comment.id', ondelete='CASCADE'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    user = db.relationship('User', backref='replies', lazy=True)

class Answer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.Text, nullable=False)
    date_posted = db.Column(db.DateTime(timezone=True), default=get_local_time)
    question_id = db.Column(db.Integer, db.ForeignKey('question.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    is_pinned = db.Column(db.Boolean, default=False)
    user = db.relationship('User', backref=db.backref('user_answers', lazy=True))

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    notified_user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    notifier_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    type = db.Column(db.String(20))
    message = db.Column(db.Text)
    is_read = db.Column(db.Boolean, default=False)
    timestamp = db.Column(db.DateTime(timezone=True), default=get_local_time)

    notifier = db.relationship('User', foreign_keys=[notifier_id], backref='notifications_sent')
    notified_user = db.relationship('User', foreign_keys=[notified_user_id], backref='notifications_received')