from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from app.models import User
from app.forms import LoginForm, RegistrationForm, ResetPasswordRequestForm, ResetPasswordForm
from werkzeug.urls import url_parse
import json

bp = Blueprint('auth', __name__)

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.home'))
    
    form = LoginForm()
    if form.validate_on_submit():
        try:
            # Try to sign in with Supabase
            response = current_app.supabase.auth.sign_in_with_password({
                "email": form.email.data,
                "password": form.password.data
            })
            
            # Get user data from response
            user_data = response.user
            
            # Get or create user in our database
            user = User.query.filter_by(email=user_data.email).first()
            if not user:
                user = User(
                    id=user_data.id,
                    email=user_data.email,
                    username=user_data.email.split('@')[0],  # Default username from email
                    role='customer'  # Default role
                )
                db.session.add(user)
                db.session.commit()
            
            # Update last sign in
            user.last_sign_in_at = user_data.last_sign_in_at
            db.session.commit()
            
            # Log in the user
            login_user(user, remember=form.remember_me.data)
            
            # Redirect to next page or home
            next_page = request.args.get('next')
            if not next_page or url_parse(next_page).netloc != '':
                next_page = url_for('main.home')
            return redirect(next_page)
            
        except Exception as e:
            flash('Invalid email or password', 'danger')
            print(f"Login error: {str(e)}")
            return render_template('auth/login.html', form=form)
    
    return render_template('auth/login.html', form=form)

@bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.home'))
    
    form = RegistrationForm()
    if form.validate_on_submit():
        try:
            # Try to sign up with Supabase
            response = current_app.supabase.auth.sign_up({
                "email": form.email.data,
                "password": form.password.data,
                "options": {
                    "data": {
                        "username": form.username.data
                    }
                }
            })
            
            # Get user data from response
            user_data = response.user
            
            # Create user in our database
            user = User(
                id=user_data.id,
                email=user_data.email,
                username=form.username.data,
                role='customer'  # Default role
            )
            db.session.add(user)
            db.session.commit()
            
            flash('Registration successful! Please check your email to verify your account.', 'success')
            return redirect(url_for('auth.login'))
            
        except Exception as e:
            flash('Registration failed. Please try again.', 'danger')
            print(f"Registration error: {str(e)}")
            return render_template('auth/register.html', form=form)
    
    return render_template('auth/register.html', form=form)

@bp.route('/logout')
@login_required
def logout():
    try:
        # Sign out from Supabase
        current_app.supabase.auth.sign_out()
    except Exception as e:
        print(f"Supabase logout error: {str(e)}")
    
    # Sign out from Flask-Login
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('main.home'))

@bp.route('/profile')
@login_required
def profile():
    return render_template('auth/profile.html')

@bp.route('/reset_password_request', methods=['GET', 'POST'])
def reset_password_request():
    if current_user.is_authenticated:
        return redirect(url_for('main.home'))
    
    form = ResetPasswordRequestForm()
    if form.validate_on_submit():
        try:
            # Request password reset from Supabase
            current_app.supabase.auth.reset_password_email(form.email.data)
            flash('Check your email for instructions to reset your password.', 'info')
            return redirect(url_for('auth.login'))
        except Exception as e:
            print(f"Password reset request error: {str(e)}")
            flash('Error sending password reset email.', 'danger')
    
    return render_template('auth/reset_password_request.html', form=form)

@bp.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('main.home'))
    
    form = ResetPasswordForm()
    if form.validate_on_submit():
        try:
            # Update password in Supabase
            current_app.supabase.auth.update_user({
                "password": form.password.data
            })
            flash('Your password has been reset.', 'success')
            return redirect(url_for('auth.login'))
        except Exception as e:
            print(f"Password reset error: {str(e)}")
            flash('Error resetting password.', 'danger')
    
    return render_template('auth/reset_password.html', form=form)

# Create a profile template
@bp.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    form = EditProfileForm()
    if form.validate_on_submit():
        try:
            current_user.username = form.username.data
            db.session.commit()
            flash('Your profile has been updated.', 'success')
            return redirect(url_for('auth.profile'))
        except Exception as e:
            flash('Error updating profile.', 'danger')
            print(f"Profile update error: {str(e)}")
    elif request.method == 'GET':
        form.username.data = current_user.username
    
    return render_template('auth/edit_profile.html', form=form) 