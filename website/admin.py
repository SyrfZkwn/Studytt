from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView
from flask_login import current_user
from flask import redirect, url_for

class AdminModelView(ModelView):
    def is_accessible(self):
        return current_user.is_authenticated and current_user.email.lower() == "studytt518@gmail.com"

    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for('auth.login'))

class ReplyAdmin(AdminModelView):
    column_list = ('id', 'body', 'user_id', 'comment_id', 'date_posted')
    form_columns = ('body', 'user_id', 'comment_id')

class CommentAdmin(AdminModelView):
    column_list = ('id', 'body', 'commenter_id', 'note_id', 'date_posted')
    form_columns = ('body', 'commenter_id', 'note_id')

class ReportAdmin(AdminModelView):
    column_list = ('id', 'reported_by', 'note_id', 'comment_id', 'reason', 'status', 'timestamp')
    form_columns = ('reported_by', 'note_id', 'comment_id', 'reason', 'status')

def init_admin(app, db, User, Note, ChatMessage, Question, Answer, Comment, Reply, Report):
    admin = Admin(app, name='Studyyt Admin', template_mode='bootstrap3')
    admin.add_view(AdminModelView(User, db.session))
    admin.add_view(AdminModelView(Note, db.session))
    admin.add_view(AdminModelView(ChatMessage, db.session))
    admin.add_view(AdminModelView(Question, db.session))
    admin.add_view(AdminModelView(Answer, db.session))
    admin.add_view(CommentAdmin(Comment, db.session))  # Custom view for Comment
    admin.add_view(ReplyAdmin(Reply, db.session))      # Custom view for Reply
    admin.add_view(ReportAdmin(Report, db.session))    # Custom view for Report