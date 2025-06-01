from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView
from flask_login import current_user
from flask import redirect, url_for

class AdminModelView(ModelView):
    def is_accessible(self):
        return current_user.is_authenticated and current_user.email == "Studytt@Admin"

    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for('auth.login'))

def init_admin(app, db, User, Note):
    admin = Admin(app, name='Studyyt Admin', template_mode='bootstrap3')
    admin.add_view(AdminModelView(User, db.session))
    admin.add_view(AdminModelView(Note, db.session))
