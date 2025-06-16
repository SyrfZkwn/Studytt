from . import db 
from flask_login import UserMixin
from sqlalchemy.sql import func
from datetime import datetime, timezone
import pytz

def get_local_time():
    local_tz = pytz.timezone('Asia/Singapore')
    return datetime.now(local_tz)

followers = db.Table('followers',
    db.Column('follower_id', db.Integer, db.ForeignKey('user.id', ondelete='CASCADE')),
    db.Column('followed_id', db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'))
)

saved_posts = db.Table('saved_posts',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id', ondelete='CASCADE')),
    db.Column('note_id', db.Integer, db.ForeignKey('note.id', ondelete='CASCADE')),
    db.Column('date', db.DateTime(timezone=True), default=get_local_time)
)

class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    __tablename__ = 'question' 
    title = db.Column(db.Text)
    body = db.Column(db.Text)
    date = db.Column(db.DateTime(timezone=True), default=get_local_time)
    publisher = db.Column(db.Integer, db.ForeignKey('user.id', ondelete="CASCADE"))
    answers = db.relationship('Answer', backref='question', lazy=True, cascade="all, delete-orphan", passive_deletes=True)

# Update your ChatMessage model in models.py

class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'))
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'))
    content = db.Column(db.Text, nullable=False)
    date = db.Column(db.DateTime(timezone=True), default=get_local_time)
    is_read = db.Column(db.Boolean, default=False, nullable=False)  # Add this field
    sender = db.relationship('User', foreign_keys=[sender_id], backref=db.backref('sent_messages', cascade="all, delete-orphan", passive_deletes=True))
    receiver = db.relationship('User', foreign_keys=[receiver_id], backref=db.backref('received_messages', cascade="all, delete-orphan", passive_deletes=True))

class Note(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    __tablename__ = 'note'
    title = db.Column(db.String(50))
    code = db.Column(db.String(10))
    chapter = db.Column(db.String(100))
    description = db.Column(db.Text)
    date = db.Column(db.DateTime(timezone=True), default=get_local_time)
    file_path = db.Column(db.String(255))
    preview_path = db.Column(db.String(255), default=None)
    publisher = db.Column(db.Integer, db.ForeignKey('user.id', ondelete="CASCADE"))
    total_points = db.Column(db.Integer, default=0)
    rating_ratio = db.Column(db.Float, default=0.0)
    total_comments = db.Column(db.Integer, default=0)
    comments = db.relationship('Comment', backref='note', lazy=True, cascade="all, delete-orphan", passive_deletes=True)
    ratings = db.relationship('Rating', backref='note', cascade='all, delete-orphan', passive_deletes=True)

class User(db.Model, UserMixin):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True)
    password = db.Column(db.String(150))
    username = db.Column(db.String(150))
    biography = db.Column(db.Text, nullable=True, default='')
    image_profile = db.Column(db.String(255), nullable=False, default='default.jpg')
    points = db.Column(db.Integer, default=0)
    notes = db.relationship('Note', backref='user', lazy=True, cascade="all, delete-orphan", passive_deletes=True)
    saved = db.relationship('Note', secondary=saved_posts, backref='saved_by')
    questions = db.relationship('Question', backref='user', lazy=True, cascade="all, delete-orphan", passive_deletes=True)
    user_comments = db.relationship('Comment', backref='user', lazy=True, cascade="all, delete-orphan", passive_deletes=True)
    user_ratings = db.relationship('Rating', backref='user', lazy=True, cascade="all, delete-orphan", passive_deletes=True)
    verified = db.Column(db.Boolean, default=False)
    theme_preference = db.Column(db.String(50), default='light')
    banned = db.Column(db.Boolean, default=False, nullable=False)
    ban_reason = db.Column(db.Text, nullable=True)
    banned_at = db.Column(db.DateTime(timezone=True), nullable=True)

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
    rater_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    note_id = db.Column(db.Integer, db.ForeignKey('note.id', ondelete='CASCADE'), nullable=False)
    value = db.Column(db.Integer, nullable=False)
    date = db.Column(db.DateTime(timezone=True), default=get_local_time)

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.Text, nullable=False)
    date_posted = db.Column(db.DateTime(timezone=True), default=get_local_time)
    note_id = db.Column(db.Integer, db.ForeignKey('note.id', ondelete='CASCADE'), nullable=False)
    commenter_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    votes = db.relationship('CommentVote', backref='comment', lazy=True, cascade="all, delete-orphan", passive_deletes=True)
    replies = db.relationship('Reply', backref='comment', lazy=True, cascade='all, delete-orphan', passive_deletes=True)

class CommentVote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    voter_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    comment_id = db.Column(db.Integer, db.ForeignKey('comment.id', ondelete='CASCADE'), nullable=False)
    value = db.Column(db.Integer, nullable=False)  # +1 = upvote, -1 = downvote

    __table_args__ = (db.UniqueConstraint('voter_id', 'comment_id', name='unique_comment_vote'),)

class ReplyVote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    voter_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    reply_id = db.Column(db.Integer, db.ForeignKey('reply.id', ondelete='CASCADE'), nullable=False)
    value = db.Column(db.Integer, nullable=False)  # +1 = upvote, -1 = downvote

    __table_args__ = (db.UniqueConstraint('voter_id', 'reply_id', name='unique_reply_vote'),)

class Reply(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.Text, nullable=False)
    date_posted = db.Column(db.DateTime(timezone=True), default=get_local_time)
    comment_id = db.Column(db.Integer, db.ForeignKey('comment.id', ondelete='CASCADE'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    user = db.relationship('User', backref=db.backref('user_replies', cascade="all, delete-orphan", passive_deletes=True))
    votes = db.relationship('ReplyVote', backref='reply', lazy=True, cascade="all, delete-orphan", passive_deletes=True)

class Answer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.Text, nullable=False)
    date_posted = db.Column(db.DateTime(timezone=True), default=get_local_time)
    question_id = db.Column(db.Integer, db.ForeignKey('question.id', ondelete='CASCADE'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'))
    is_pinned = db.Column(db.Boolean, default=False)
    user = db.relationship('User', backref=db.backref('user_answers', cascade="all, delete-orphan", passive_deletes=True))

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    notified_user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'))
    notifier_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'))
    post_id = db.Column(db.Integer)
    type = db.Column(db.String(100))
    message = db.Column(db.Text)
    is_read = db.Column(db.Boolean, default=False)
    timestamp = db.Column(db.DateTime(timezone=True), default=get_local_time)

    notifier = db.relationship('User', foreign_keys=[notifier_id], backref=db.backref('notifications_sent', cascade="all, delete-orphan", passive_deletes=True))
    notified_user = db.relationship('User', foreign_keys=[notified_user_id], backref=db.backref('notifications_received', cascade="all, delete-orphan", passive_deletes=True))

class Report(db.Model):
    __tablename__ = 'report'

    id = db.Column(db.Integer, primary_key=True)
    reported_by = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    note_id = db.Column(db.Integer, db.ForeignKey('note.id', ondelete='CASCADE'), nullable=True)
    comment_id = db.Column(db.Integer, db.ForeignKey('comment.id', ondelete='CASCADE'), nullable=True)
    reason = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(100), default="pending")
    timestamp = db.Column(db.DateTime(timezone=True), default=get_local_time)

    reporter = db.relationship('User', backref=db.backref('reports_made', cascade="all, delete-orphan", passive_deletes=True))