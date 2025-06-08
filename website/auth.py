from flask import Blueprint, render_template, request, flash, redirect, url_for
from .models import User
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, login_required, logout_user, current_user
from sqlalchemy.sql import func
from flask_mailman import EmailMessage
from .extensions import db, mail
from .email_utils import generate_verification_token, confirm_verification_token


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
            if check_password_hash(user.password, password):
                login_user(user, remember=True)
                return redirect(url_for('views.home'))
            else:
                flash('Incorrect password, try again.', category='error')
        else:
            flash('An account with that email already exists.', category='error')

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
            flash('Account already verified. Please login.', category='info')
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
            flash('Your email is already verified.', category='info')
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