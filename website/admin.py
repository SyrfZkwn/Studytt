from flask_admin import Admin, AdminIndexView, expose
from flask_admin.contrib.sqla import ModelView
from flask_login import current_user
from flask import redirect, url_for

class CustomAdminIndexView(AdminIndexView):
    @expose('/')
    def index(self):
        if not (current_user.is_authenticated and current_user.email.lower() == "studytt518@gmail.com"):
            return redirect(url_for('auth.login'))
        
        # Get statistics for dashboard
        from .models import User, Note, Comment, ChatMessage, Question, Answer, Reply, Report
        
        user_count = User.query.count()
        note_count = Note.query.count()
        comment_count = Comment.query.count()
        chat_count = ChatMessage.query.count()
        question_count = Question.query.count()
        answer_count = Answer.query.count()
        reply_count = Reply.query.count()
        report_count = Report.query.filter_by(status='pending').count()
        
        # Recent activity (last 5 users, notes, etc.)
        recent_users = User.query.order_by(User.id.desc()).limit(5).all()
        recent_notes = Note.query.order_by(Note.date.desc()).limit(5).all()
        recent_reports = Report.query.filter_by(status='pending').order_by(Report.timestamp.desc()).limit(5).all()
        
        return self.render('admin/custom_index.html',
                         user_count=user_count,
                         note_count=note_count,
                         comment_count=comment_count,
                         chat_count=chat_count,
                         question_count=question_count,
                         answer_count=answer_count,
                         reply_count=reply_count,
                         report_count=report_count,
                         recent_users=recent_users,
                         recent_notes=recent_notes,
                         recent_reports=recent_reports)

class AdminModelView(ModelView):
    def is_accessible(self):
        return current_user.is_authenticated and current_user.email.lower() == "studytt518@gmail.com"

    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for('auth.login'))

class UserAdmin(AdminModelView):
    column_list = ('id', 'username', 'email', 'verified', 'points', 'theme_preference')
    column_searchable_list = ('username', 'email')
    column_filters = ('verified', 'theme_preference')
    form_columns = ('username', 'email', 'biography', 'verified', 'points', 'theme_preference')
    column_sortable_list = ('id', 'username', 'email', 'points')
    page_size = 50

class NoteAdmin(AdminModelView):
    column_list = ('id', 'title', 'code', 'chapter', 'publisher', 'date', 'total_points', 'rating_ratio')
    column_searchable_list = ('title', 'code', 'chapter')
    column_filters = ('code', 'chapter', 'date')
    form_columns = ('title', 'code', 'chapter', 'description', 'publisher')
    column_sortable_list = ('id', 'title', 'date', 'total_points', 'rating_ratio')
    page_size = 50

# In your admin.py, temporarily update the ChatMessageAdmin class:
class ChatMessageAdmin(AdminModelView):
    column_list = ('id', 'sender_id', 'receiver_id', 'content', 'date')  # Remove 'is_read'
    column_searchable_list = ('content',)
    column_filters = ('date',)  # Remove 'is_read' from filters
    form_columns = ('sender_id', 'receiver_id', 'content')  # Remove 'is_read'
    column_sortable_list = ('id', 'date')
    page_size = 50

class QuestionAdmin(AdminModelView):
    column_list = ('id', 'title', 'publisher', 'date')
    column_searchable_list = ('title', 'body')
    column_filters = ('date',)
    form_columns = ('title', 'body', 'publisher')
    column_sortable_list = ('id', 'title', 'date')
    page_size = 50

class AnswerAdmin(AdminModelView):
    column_list = ('id', 'question_id', 'user_id', 'is_pinned', 'date_posted')
    column_searchable_list = ('body',)
    column_filters = ('is_pinned', 'date_posted')
    form_columns = ('body', 'question_id', 'user_id', 'is_pinned')
    column_sortable_list = ('id', 'date_posted')
    page_size = 50

class CommentAdmin(AdminModelView):
    column_list = ('id', 'body', 'commenter_id', 'note_id', 'date_posted')
    column_searchable_list = ('body',)
    column_filters = ('date_posted',)
    form_columns = ('body', 'commenter_id', 'note_id')
    column_sortable_list = ('id', 'date_posted')
    page_size = 50

class ReplyAdmin(AdminModelView):
    column_list = ('id', 'body', 'user_id', 'comment_id', 'date_posted')
    column_searchable_list = ('body',)
    column_filters = ('date_posted',)
    form_columns = ('body', 'user_id', 'comment_id')
    column_sortable_list = ('id', 'date_posted')
    page_size = 50

class ReportAdmin(AdminModelView):
    column_list = ('id', 'reported_by', 'note_id', 'comment_id', 'reason', 'status', 'timestamp')
    column_searchable_list = ('reason',)
    column_filters = ('status', 'timestamp')
    form_columns = ('reported_by', 'note_id', 'comment_id', 'reason', 'status')
    column_sortable_list = ('id', 'timestamp', 'status')
    page_size = 50
    
    # Custom actions for reports
    def _status_formatter(view, context, model, name):
        if model.status == 'pending':
            return f'<span class="label label-warning">{model.status}</span>'
        elif model.status == 'reviewed':
            return f'<span class="label label-success">{model.status}</span>'
        elif model.status == 'dismissed':
            return f'<span class="label label-danger">{model.status}</span>'
        return model.status
    
    column_formatters = {
        'status': _status_formatter
    }

def init_admin(app, db, User, Note, ChatMessage, Question, Answer, Comment, Reply, Report):
    # Initialize admin with custom index view and styling
    admin = Admin(
        app, 
        name='StudyTT Admin',
        template_mode='bootstrap3',
        index_view=CustomAdminIndexView(),
        base_template='admin/my_master.html'  # This will use our custom template
    )
    
    # Add views with custom admin classes
    admin.add_view(UserAdmin(User, db.session, name='Users'))
    admin.add_view(NoteAdmin(Note, db.session, name='Notes'))
    admin.add_view(ChatMessageAdmin(ChatMessage, db.session, name='Chat Messages'))
    admin.add_view(QuestionAdmin(Question, db.session, name='Questions'))
    admin.add_view(AnswerAdmin(Answer, db.session, name='Answers'))
    admin.add_view(CommentAdmin(Comment, db.session, name='Comments'))
    admin.add_view(ReplyAdmin(Reply, db.session, name='Replies'))
    admin.add_view(ReportAdmin(Report, db.session, name='Reports'))
    
    # Add external links
    from flask_admin.base import MenuLink
    admin.add_link(MenuLink(name='Back to Site', url='/home'))
    admin.add_link(MenuLink(name='Logout', url='/logout'))
    
    return admin