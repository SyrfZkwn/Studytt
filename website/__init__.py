from flask import Flask, request
from flask_sqlalchemy import SQLAlchemy
from os import path
from flask_login import LoginManager, current_user
from flask_socketio import SocketIO
from sqlalchemy import event
from sqlalchemy.engine import Engine
import sqlite3
from flask_migrate import Migrate
from datetime import datetime
import pytz
from website.admin import init_admin
from itsdangerous import URLSafeTimedSerializer
from .extensions import db, mail, migrate, socketio

DB_NAME = "database.db"

def get_local_time():
    local_tz = pytz.timezone('Asia/Singapore')
    return datetime.now(local_tz)

def time_ago(value):
    if isinstance(value, datetime):
        # Ensure the value is timezone-aware, using Asia/Singapore timezone if not already
        if value.tzinfo is None:
            local_tz = pytz.timezone('Asia/Singapore')
            value = local_tz.localize(value)  # Localize naive datetime to Singapore timezone

        # Get the current time in Asia/Singapore timezone as a timezone-aware object
        now = get_local_time()

        # Calculate the time difference
        delta = now - value
        days = delta.days
        if days > 0:
            return f"{days} day{'s' if days > 1 else ''} ago"
        else:
            hours = delta.seconds // 3600
            if hours > 0:
                return f"{hours} hour{'s' if hours > 1 else ''} ago"
            minutes = (delta.seconds % 3600) // 60
            if minutes > 0:
                return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
            return "Just now"
    return value



def create_app():
    app = Flask(__name__, template_folder='templates')
    app.config['SECRET_KEY'] = 'dua tiga kucing berlari'
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_NAME}'
    app.config['UPLOAD_FOLDER'] = 'static/notes'
    app.config['PDF_PREVIEW_FOLDER'] = 'static/pdf_preview'
    app.jinja_env.filters['time_ago'] = time_ago

    db.init_app(app)
    socketio.init_app(app, cors_allowed_origins="*")


    from .views import views
    from .auth import auth
    from .models import User, Note, ChatMessage, Question, Answer, Comment, Reply

    app.register_blueprint(views, url_prefix='/')
    app.register_blueprint(auth, url_prefix='/')

    create_database(app)

    migrate.init_app(app, db)

    login_manager = LoginManager()
    login_manager.login_view = 'auth.login'
    login_manager.login_message = "You must be signed in to view that page."
    login_manager.login_message_category = "error"
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(id):
        return User.query.get(int(id))

    @app.context_processor
    def inject_request():
        return dict(request=request)
    
    @app.context_processor
    def inject_unread_notifications():
        from .models import Notification
        if current_user.is_authenticated:
            count = Notification.query.filter_by(notified_user_id=current_user.id, is_read=False).count()
            return dict(total_unread_notifications=count)
        return dict(total_unread_notifications=0)
    
    app.config['MAIL_SERVER'] = 'smtp.gmail.com'
    app.config['MAIL_USERNAME'] = 'studytt518@gmail.com'
    app.config['MAIL_PASSWORD'] = 'pxsp emts vske moyo'
    app.config['MAIL_PORT'] = 465
    app.config['MAIL_USE_TLS'] = False
    app.config['MAIL_USE_SSL'] = True
    app.config['MAIL_BACKEND'] = 'smtp'

    global s
    s = URLSafeTimedSerializer(app.config['SECRET_KEY'])

    mail.init_app(app)

    # Initialize flask-admin
    init_admin(app, db, User, Note, ChatMessage, Question, Answer, Comment, Reply)

    return app

def create_database(app):
    if not path.exists('website/' + DB_NAME):
        with app.app_context():
            db.create_all()
        print('Created Database!')
    else:
        print('Database already existed!')

@event.listens_for(Engine, "connect")
def enable_sqlite_fk_constraints(dbapi_connection, connection_record):
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.close()