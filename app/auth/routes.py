from flask import render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, current_user, login_required
from urllib.parse import urlparse
from app.auth import bp
from app.auth.forms import LoginForm, RegistrationForm, ChangePasswordForm, ForgotPasswordForm, ResetPasswordForm
from app.models import User
from app import db
from app.email import send_password_reset_email
import jwt
from datetime import datetime, timedelta
from flask import current_app

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user is None or not user.check_password(form.password.data):
            flash('Invalid email or password')
            return redirect(url_for('auth.login'))
        login_user(user, remember=form.remember_me.data)
        next_page = request.args.get('next')
        if not next_page or urlparse(next_page).netloc != '':
            next_page = url_for('main.index')
        return redirect(next_page)
    return render_template('auth/login.html', title='Sign In', form=form)

@bp.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('main.index'))

@bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(username=form.username.data, email=form.email.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('Congratulations, you are now a registered user!')
        return redirect(url_for('auth.login'))
    return render_template('auth/register.html', title='Register', form=form)

@bp.route('/profile')
@login_required
def profile():
    return render_template('auth/profile.html', title='Profile', user=current_user)

@bp.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if current_user.check_password(form.current_password.data):
            current_user.set_password(form.new_password.data)
            db.session.commit()
            flash('Your password has been updated.', 'success')
            return redirect(url_for('auth.profile'))
        else:
            flash('Invalid current password.', 'danger')
    return render_template('auth/change_password.html', title='Change Password', form=form)

@bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    form = ForgotPasswordForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            # Generate reset token
            token = jwt.encode(
                {
                    'reset_password': user.id,
                    'exp': datetime.utcnow() + timedelta(minutes=30)
                },
                current_app.config['SECRET_KEY'],
                algorithm='HS256'
            )
            
            # Send reset email
            reset_url = url_for('auth.reset_password', token=token, _external=True)
            send_password_reset_email(user.email, reset_url)
            
            flash('Check your email for instructions to reset your password.', 'info')
            return redirect(url_for('auth.login'))
    return render_template('auth/forgot_password.html', title='Reset Password', form=form)

@bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    try:
        token_data = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])
        user_id = token_data['reset_password']
        user = User.query.get(user_id)
    except:
        flash('Invalid or expired reset link.', 'danger')
        return redirect(url_for('auth.forgot_password'))
    
    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)
        db.session.commit()
        flash('Your password has been reset.', 'success')
        return redirect(url_for('auth.login'))
    return render_template('auth/reset_password.html', form=form) 