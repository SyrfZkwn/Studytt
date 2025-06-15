from flask_admin import Admin, AdminIndexView, expose
from flask_admin.contrib.sqla import ModelView
from flask_admin.actions import action
from flask_login import current_user
from flask import redirect, url_for, flash
from markupsafe import Markup

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
    column_list = ('id', 'username', 'email', 'verified', 'banned', 'ban_actions', 'points', 'theme_preference')
    column_searchable_list = ('username', 'email')
    column_filters = ('verified', 'banned', 'theme_preference')
    form_columns = ('username', 'email', 'biography', 'verified', 'banned', 'ban_reason', 'points', 'theme_preference')
    column_sortable_list = ('id', 'username', 'email', 'points')
    form_excluded_columns = ['notes', 'saved', 'questions', 'user_comments', 'user_ratings', 
                           'followed', 'followers', 'sent_messages', 'received_messages',
                           'notifications_sent', 'notifications_received', 'user_replies',
                           'user_answers', 'reports_made', 'file', 'password']
    page_size = 50

    can_create = False
    can_edit = False
    can_delete = True
    
    def _ban_actions_formatter(self, context, model, name):
        if model.banned:
            return Markup(f'''
                <span class="label label-danger">BANNED</span><br>
                <small>{model.ban_reason or "No reason"}</small><br>
                <form method="post" action="/admin/unban_user/{model.id}" style="display:inline; margin-top:5px;">
                    <button type="submit" class="btn btn-xs btn-success">Unban</button>
                </form> 
            ''')
        else:
            return Markup(f'''
                <span class="label label-success">Active</span><br>
                <form method="post" action="/admin/ban_user/{model.id}" style="display:inline;">
                    <input type="text" name="ban_reason" placeholder="Ban reason" style="width:100px; margin-bottom:2px;"><br>
                    <button type="submit" class="btn btn-xs btn-danger">Ban</button>
                </form>
            ''')
    
    column_formatters = {
        'ban_actions': _ban_actions_formatter
    }


    
    

    # Store db reference - we'll set this in init_admin
    _db = None
    
    @action('ban', 'Ban Selected Users', 'Are you sure you want to ban selected users?')
    def action_ban(self, ids):
        try:
            from .models import get_local_time
            # Import User model here to avoid circular imports
            from .models import User
            
            query = User.query.filter(User.id.in_(ids))
            count = 0
            for user in query.all():
                if not user.banned:
                    user.banned = True
                    user.ban_reason = "Banned by admin (bulk action)"
                    user.banned_at = get_local_time()
                    count += 1
            
            # Use the db session that's available to the model
            User.query.session.commit()
            flash(f'Successfully banned {count} users.', 'success')
        except Exception as ex:
            if not self.handle_view_exception(ex):
                raise
            flash('Failed to ban users. {}'.format(str(ex)), 'error')

    @action('unban', 'Unban Selected Users', 'Are you sure you want to unban selected users?')
    def action_unban(self, ids):
        try:
            # Import User model here to avoid circular imports
            from .models import User
            
            query = User.query.filter(User.id.in_(ids))
            count = 0
            for user in query.all():
                if user.banned:
                    user.banned = False
                    user.ban_reason = None
                    user.banned_at = None
                    count += 1
            
            # Use the db session that's available to the model
            User.query.session.commit()
            flash(f'Successfully unbanned {count} users.', 'success')
        except Exception as ex:
            if not self.handle_view_exception(ex):
                raise
            flash('Failed to unban users. {}'.format(str(ex)), 'error')

# Keep all your existing admin classes unchanged
class NoteAdmin(AdminModelView):
    column_list = ('id', 'title', 'code', 'chapter', 'publisher', 'date', 'total_points', 'rating_ratio')
    column_searchable_list = ('title', 'code', 'chapter')
    column_filters = ('code', 'chapter', 'date')
    form_columns = ('title', 'code', 'chapter', 'description', 'publisher')
    column_sortable_list = ('id', 'title', 'date', 'total_points', 'rating_ratio')
    page_size = 50

class ChatMessageAdmin(AdminModelView):
    column_list = ('id', 'sender_id', 'receiver_id', 'content', 'date')
    column_searchable_list = ('content',)
    column_filters = ('date',)
    form_columns = ('sender_id', 'receiver_id', 'content')
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
    
    def _status_formatter(view, context, model, name):
        if model.status == 'pending':
            return Markup(f'<span class="label label-warning">{model.status}</span>')
        elif model.status == 'reviewed':
            return Markup(f'<span class="label label-success">{model.status}</span>')
        elif model.status == 'dismissed':
            return Markup(f'<span class="label label-danger">{model.status}</span>')
        return model.status
    
    column_formatters = {
        'status': _status_formatter
    }

def init_admin(app, db, User, Note, ChatMessage, Question, Answer, Comment, Reply, Report):
    admin = Admin(
        app, 
        name='StudyTT Admin',
        template_mode='bootstrap3',
        index_view=CustomAdminIndexView(),
        base_template='admin/my_master.html'
    )
    
    admin.add_view(UserAdmin(User, db.session, name='Users'))
    admin.add_view(NoteAdmin(Note, db.session, name='Notes'))
    admin.add_view(ChatMessageAdmin(ChatMessage, db.session, name='Chat Messages'))
    admin.add_view(QuestionAdmin(Question, db.session, name='Questions'))
    admin.add_view(AnswerAdmin(Answer, db.session, name='Answers'))
    admin.add_view(CommentAdmin(Comment, db.session, name='Comments'))
    admin.add_view(ReplyAdmin(Reply, db.session, name='Replies'))
    admin.add_view(ReportAdmin(Report, db.session, name='Reports'))
    
    from flask_admin.base import MenuLink
    admin.add_link(MenuLink(name='Back to Site', url='/home'))
    admin.add_link(MenuLink(name='Logout', url='/logout'))
    
    return admin