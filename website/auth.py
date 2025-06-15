from flask import Blueprint, render_template, request, flash, redirect, url_for
from .models import User
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, login_required, logout_user, current_user
from sqlalchemy.sql import func
from flask_mailman import EmailMessage
from .extensions import db, mail
from .email_utils import generate_verification_token, confirm_verification_token
from flask_mailman import EmailMessage
from .extensions import db, mail
from .email_utils import generate_verification_token, confirm_verification_token, confirm_reset_token, generate_reset_token


auth = Blueprint('auth', __name__)

@auth.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        # Special admin login check
        if email == "studytt518@gmail.com" and password == "~Qwerty1234567":
            # Create a dummy User object for admin
            admin_user = User()
            admin_user.id = 0
            admin_user.email = "studytt518@gmail.com"
            admin_user.username = "Admin"
            login_user(admin_user, remember=True)
            return redirect(url_for('views.home'))

        user = User.query.filter_by(email=email).first()
        if user:
            if not user.verified:
                flash('Please verify your email before logging in.', category='error')
                return render_template("signup.html", show_resend_link=True)
            
            if user.banned:
                flash('Your account has been suspended. Please contact support.', category='error')
                return render_template("login.html")

            if check_password_hash(user.password, password):
                login_user(user, remember=True)
                return redirect(url_for('views.home'))
            else:
                flash('Incorrect password, try again.', category='error')
        else:
            flash('An account with that email does not exists.', category='error')

    return render_template("login.html")

@auth.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully', category='success')
    return redirect(url_for('auth.login'))

@auth.route('/', methods=['GET', 'POST'])
def sign_up():
    if request.method == 'POST':
        email = request.form.get('email').strip().lower()
        username = request.form.get('username').strip()
        password1 = request.form.get('password1')
        password2 = request.form.get('password2')

        # Validate form data first
        if len(username) < 3:
            flash('Username must be at least 3 characters long.', category='error')
            return render_template("signup.html")
        if len(email) < 4:
            flash('Email must be at least 4 characters long.', category='error')
            return render_template("signup.html")
        if password1 != password2:
            flash('Passwords do not match.', category='error')
            return render_template("signup.html")
        if len(password1) < 7:
            flash('Password must be at least 7 characters.', category='error')
            return render_template("signup.html")

        # Check for existing username
        existing_user = User.query.filter(func.lower(User.username) == username.lower()).first()
        if existing_user:
            flash('Username is unavailable. Choose another one.', category='error')
            return render_template("signup.html")
        
        banned_user = User.query.filter(func.lower(User.email) == email.lower(), User.banned == True).first()
        if banned_user:
            flash('Cannot create account with this email address.', category='error')
            return render_template("signup.html")

        # Check for existing verified email
        existing_email = User.query.filter(func.lower(User.email) == email).first()
        if existing_email:

            
            if existing_email.verified:
                flash('An account with that email already exists.', category='error')
                return render_template("signup.html", show_resend_link=False)
            else:
                flash('Email already registered but not verified. Please check your email or resend the verification link.', category='error')
                existing_email.username = username
                existing_email.password = generate_password_hash(password1, method='pbkdf2:sha256')
                db.session.commit()

                # Send verification email
                token = generate_verification_token(email)
                verify_url = url_for('auth.verify_email', token=token, _external=True)
                html = render_template('verify_email.html', verify_url=verify_url)
                subject = "Please verify your email"

                msg = EmailMessage(
                    subject=subject,
                    from_email="studytt518@gmail.com",
                    to=[email],
                    body=html
                )
                msg.content_subtype = 'html'
                msg.send()

                return render_template("signup.html", show_resend_link=True)
        else:
            # Create user
            new_user = User(
                email=email,
                username=username,
                password=generate_password_hash(password1, method='pbkdf2:sha256'),
                verified=False
            )
            db.session.add(new_user)

        db.session.commit()

        # Send verification email
        token = generate_verification_token(email)
        verify_url = url_for('auth.verify_email', token=token, _external=True)
        html = render_template('verify_email.html', verify_url=verify_url)
        subject = "Please verify your email"

        msg = EmailMessage(
            subject=subject,
            from_email="studytt518@gmail.com",
            to=[email],
            body=html
        )
        msg.content_subtype = 'html'
        msg.send()

        flash('A verification email has been sent to your email address.', category='success')
        return render_template('signup.html', show_resend_link=True)

    return render_template("signup.html")

@auth.route('/verify/<token>')
def verify_email(token):
    email = confirm_verification_token(token)
    if not email:
        flash('The verification link is invalid or has expired.', category='error')
        return redirect(url_for('auth.sign_up'))

    user = User.query.filter_by(email=email).first()
    if user:
        if user.verified:
            flash('Account already verified. Please login.', category='error')
        else:
            user.verified = True
            db.session.commit()
            flash('Your email has been verified. You can now log in.', category='success')
    else:
        flash('No account found with this email.', category='error')

    return redirect(url_for('auth.login'))

@auth.route('/resend-email', methods=['POST'])
def resend_email():
    email = request.form.get('resend_email')
    user = User.query.filter_by(email=email).first()

    if user:
        if user.verified:
            flash('Your email is already verified.', category='error')
        else:
            token = generate_verification_token(email)
            verify_url = url_for('auth.verify_email', token=token, _external=True)
            html = render_template('verify_email.html', verify_url=verify_url)
            subject = "Please verify your email"

            msg = EmailMessage(
                subject=subject,
                from_email="studytt518@gmail.com",
                to=[email],
                body=html
            )
            msg.content_subtype = 'html'
            msg.send()

            flash('Verification email resent. Check your inbox (or spam).', category='success')
    else:
        flash('No account found with that email.', category='error')

    return render_template('signup.html', show_resend_link=True)

@auth.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()

        if user:
            

            if not user.verified:
                flash('Your email is not verified.', category='error')
                return render_template("signup.html", show_resend_link=True)
            
            else:
                token = generate_reset_token(user.email)
                reset_url = url_for('auth.reset_password', token=token, _external=True)
                html = render_template('reset_email.html', reset_url=reset_url)
                subject = "Reset Your Password"

                msg = EmailMessage(
                    subject=subject,
                    from_email="studytt518@gmail.com",
                    to=[email],
                    body=html
                )
                msg.content_subtype = 'html'
                msg.send()
                flash('A password reset link has been sent to your email.', 'success')

            
            
        else:
            flash('No account found with that email.', category='error')
        return redirect(url_for('auth.forgot_password'))

    return render_template('forgot_password.html')

@auth.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    email = confirm_reset_token(token)
    if not email:
        flash('The reset link is invalid or expired.', category='error')
        return redirect(url_for('auth.forgot_password'))

    user = User.query.filter_by(email=email).first()
    if request.method == 'POST':
        new_password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        if new_password != confirm_password:
            flash('Passwords do not match.', category='error')
            return render_template('reset_password.html')
        if len(new_password) < 7:
            flash('Password must be at least 7 characters.', category='error')
            return render_template("reset_password.html")


        user.password = generate_password_hash(new_password, method='pbkdf2:sha256')
        db.session.commit()
        flash('Your password has been updated. You can now log in.', category='success')
        return redirect(url_for('auth.login'))

    return render_template('reset_password.html')