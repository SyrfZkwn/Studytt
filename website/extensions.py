from flask_sqlalchemy import SQLAlchemy
from flask_mailman import Mail
from flask_migrate import Migrate
from flask_socketio import SocketIO

db = SQLAlchemy()
mail = Mail()
migrate = Migrate()
socketio = SocketIO()