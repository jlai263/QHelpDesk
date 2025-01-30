from flask import render_template, flash, redirect, url_for, request, jsonify
from flask_login import current_user, login_required
from app.main import bp
from app import db
from openai import OpenAI
import os
from datetime import datetime
from app.models import User, Invitation, Organization, Ticket

client = OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))

@bp.route('/')
def index():
    if not current_user.is_authenticated:
        return render_template('main/landing.html')
    
    # Get user's organization
    org = current_user.organization
    if not org:
        # Get pending invitations for the user
        try:
            pending_invites = Invitation.query.filter_by(
                email=current_user.email,
                accepted=False
            ).filter(
                Invitation.expires_at > datetime.utcnow()
            ).all()
        except Exception as e:
            print(f"Error fetching invitations: {str(e)}")
            pending_invites = []
        
        # If user has no organization, show landing page with options
        return render_template('main/landing.html', 
                             show_org_options=True,
                             pending_invites=pending_invites,
                             message="You are not currently a member of any organization. Please join one or create your own.")
    
    # Prepare stats based on user role
    if current_user.is_admin or current_user.role == 'staff':
        # Admin/Staff stats - they can see all tickets
        org_tickets = Ticket.query.filter_by(organization_id=org.id)
        stats = {
            'total_tickets': org_tickets.count(),
            'open_tickets': org_tickets.filter_by(status='open').count(),
            'high_priority': org_tickets.filter_by(priority='high').count(),
            'team_members': User.query.filter_by(organization_id=org.id).count()
        }
        
        # Calculate support overview stats
        total_closed = org_tickets.filter_by(status='closed').count()
        total_tickets = org_tickets.count()
        resolution_rate = (total_closed / total_tickets * 100) if total_tickets > 0 else 0
        
        resolved_today = org_tickets.filter(
            Ticket.status == 'closed',
            Ticket.updated_at >= datetime.utcnow().date()
        ).count()
        
        # Calculate average response time for tickets with first response
        tickets_with_response = org_tickets.filter(Ticket.first_response_time.isnot(None)).all()
        if tickets_with_response:
            total_response_time = sum(
                (ticket.first_response_time - ticket.created_at).total_seconds() 
                for ticket in tickets_with_response
            )
            avg_response_time = total_response_time / len(tickets_with_response)
            avg_response_hours = round(avg_response_time / 3600, 1)  # Convert to hours
        else:
            avg_response_hours = 0
        
        support_stats = {
            'avg_response_time': f"{avg_response_hours}h",
            'resolved_today': resolved_today,
            'resolution_rate': f"{round(resolution_rate, 1)}%"
        }
        
        recent_tickets = org_tickets.order_by(Ticket.created_at.desc()).limit(5).all()
        return render_template('main/dashboard.html', stats=stats, support_stats=support_stats, recent_tickets=recent_tickets)
    else:
        # Regular user stats - using submitter_id instead of user_id
        stats = {
            'open_tickets': Ticket.query.filter_by(submitter_id=current_user.id, status='open').count(),
            'in_progress_tickets': Ticket.query.filter_by(submitter_id=current_user.id, status='in_progress').count(),
            'closed_tickets': Ticket.query.filter_by(submitter_id=current_user.id, status='closed').count()
        }
        recent_tickets = Ticket.query.filter_by(submitter_id=current_user.id).order_by(Ticket.created_at.desc()).limit(5).all()
        return render_template('main/user_dashboard.html', stats=stats, recent_tickets=recent_tickets)

@bp.route('/landing')
@login_required
def landing():
    # Get pending invitations for the user
    try:
        pending_invites = Invitation.query.filter_by(
            email=current_user.email,
            accepted=False  # Only get invitations that haven't been accepted
        ).filter(
            Invitation.expires_at > datetime.utcnow()
        ).all()
    except Exception as e:
        print(f"Error fetching invitations: {str(e)}")
        pending_invites = []
    
    # Always show organization options if user has no organization
    show_org_options = not current_user.organization
    message = "You are not currently a member of any organization. Please join one or create your own."
    
    return render_template('main/landing.html', 
                         pending_invites=pending_invites,
                         show_org_options=show_org_options,
                         message=message)

@bp.route('/dashboard')
@login_required
def dashboard():
    if not current_user.organization:
        flash('Please join or create an organization first.', 'warning')
        return redirect(url_for('main.landing'))
    
    # Get organization stats based on user role
    if current_user.is_admin or current_user.role == 'staff':
        # Admin/Staff stats - they can see all tickets
        org_tickets = Ticket.query.filter_by(organization_id=current_user.organization_id)
        stats = {
            'total_tickets': org_tickets.count(),
            'open_tickets': org_tickets.filter_by(status='open').count(),
            'high_priority': org_tickets.filter_by(priority='high').count(),
            'team_members': User.query.filter_by(organization_id=current_user.organization_id).count()
        }
        
        # Calculate support overview stats
        total_closed = org_tickets.filter_by(status='closed').count()
        total_tickets = org_tickets.count()
        resolution_rate = (total_closed / total_tickets * 100) if total_tickets > 0 else 0
        
        resolved_today = org_tickets.filter(
            Ticket.status == 'closed',
            Ticket.updated_at >= datetime.utcnow().date()
        ).count()
        
        # Calculate average response time for tickets with first response
        tickets_with_response = org_tickets.filter(Ticket.first_response_time.isnot(None)).all()
        if tickets_with_response:
            total_response_time = sum(
                (ticket.first_response_time - ticket.created_at).total_seconds() 
                for ticket in tickets_with_response
            )
            avg_response_time = total_response_time / len(tickets_with_response)
            avg_response_hours = round(avg_response_time / 3600, 1)  # Convert to hours
        else:
            avg_response_hours = 0
        
        support_stats = {
            'avg_response_time': f"{avg_response_hours}h",
            'resolved_today': resolved_today,
            'resolution_rate': f"{round(resolution_rate, 1)}%"
        }
        
        return render_template('main/dashboard.html', stats=stats, support_stats=support_stats)
    else:
        # Regular user stats
        user_tickets = Ticket.query.filter_by(submitter_id=current_user.id)
        stats = {
            'total_tickets': user_tickets.count(),
            'open_tickets': user_tickets.filter_by(status='open').count(),
            'in_progress_tickets': user_tickets.filter_by(status='in_progress').count()
        }
        return render_template('main/user_dashboard.html', stats=stats)

@bp.route('/accept_invite/<token>', methods=['POST'])
@login_required
def accept_invite(token):
    invitation = Invitation.query.filter_by(token=token).first_or_404()
    
    if invitation.is_expired():
        flash('This invitation has expired.', 'danger')
        return redirect(url_for('main.index'))
    
    if invitation.email != current_user.email:
        flash('This invitation is not for your email address.', 'danger')
        return redirect(url_for('main.index'))
    
    # Update user's organization and role
    current_user.organization_id = invitation.organization_id
    if invitation.is_admin_invite:
        current_user.role = 'admin'
    else:
        current_user.role = 'user'
    
    # Delete the invitation after accepting
    db.session.delete(invitation)
    db.session.commit()
    
    flash('You have successfully joined the organization!', 'success')
    return redirect(url_for('main.index'))

@bp.route('/decline_invite/<token>', methods=['POST'])
@login_required
def decline_invite(token):
    invitation = Invitation.query.filter_by(token=token).first_or_404()
    
    if invitation.email != current_user.email:
        flash('This invitation is not for your email address.', 'danger')
        return redirect(url_for('main.index'))
    
    db.session.delete(invitation)
    db.session.commit()
    
    flash('Invitation declined.', 'info')
    return redirect(url_for('main.index'))

@bp.route('/join_with_token', methods=['POST'])
@login_required
def join_with_token():
    token = request.form.get('token')
    if not token:
        flash('Please provide an invitation token.', 'danger')
        return redirect(url_for('main.index'))
    
    invitation = Invitation.query.filter_by(token=token).first()
    if not invitation:
        flash('Invalid invitation token.', 'danger')
        return redirect(url_for('main.index'))
    
    if invitation.is_expired():
        flash('This invitation has expired.', 'danger')
        return redirect(url_for('main.index'))
    
    if invitation.email != current_user.email:
        flash('This invitation is not for your email address.', 'danger')
        return redirect(url_for('main.index'))
    
    # Update user's organization and role
    current_user.organization_id = invitation.organization_id
    if invitation.is_admin_invite:
        current_user.role = 'admin'
    else:
        current_user.role = 'user'
    
    # Delete the invitation after accepting
    db.session.delete(invitation)
    db.session.commit()
    
    flash('You have successfully joined the organization!', 'success')
    return redirect(url_for('main.index'))

@bp.route('/ai_chat')
@login_required
def ai_chat():
    return render_template('ai_chat.html', title='AI Chat')

@bp.route('/ai_chat/message', methods=['POST'])
@login_required
def ai_chat_message():
    try:
        # Verify request is AJAX
        if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({"response": "Invalid request method"}), 400

        # Debug print the raw request data
        print("Request data:", request.data)
        print("Request content type:", request.content_type)
        
        # Get and validate the JSON data
        if not request.is_json:
            print("Error: Request is not JSON")
            return jsonify({"response": "Invalid content type. Please send JSON data."}), 400
            
        data = request.get_json()
        print("Parsed JSON data:", data)  # Debug print
        
        if not data:
            print("Error: No JSON data in request")
            return jsonify({"response": "No data provided"}), 400
            
        user_message = data.get('message')
        if not user_message:
            print("Error: No message in JSON data")
            return jsonify({"response": "No message provided"}), 400
            
        print(f"Processing message: {user_message}")  # Debug print
        print(f"Using OpenAI API Key: {os.environ.get('OPENAI_API_KEY')[:5]}...")  # Debug print (first 5 chars only)
        
        # Make the API call
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful IT support assistant. Provide specific and practical solutions for technical issues."},
                {"role": "user", "content": user_message}
            ],
            max_tokens=150,
            temperature=0.7
        )
        
        # Validate the API response
        if not response.choices:
            print("Error: No choices in OpenAI response")
            return jsonify({"response": "I apologize, but I couldn't generate a response. Please try again."}), 500
            
        ai_response = response.choices[0].message.content
        print(f"Success! AI Response: {ai_response}")  # Debug print
        
        # Return response with proper headers
        return jsonify({
            "response": ai_response
        }), 200, {
            'Content-Type': 'application/json',
            'Cache-Control': 'no-cache, no-store, must-revalidate'
        }
        
    except ValueError as e:
        print(f"JSON parsing error: {str(e)}")
        return jsonify({"response": "Invalid JSON format"}), 400
    except Exception as e:
        error_msg = str(e)
        print(f"Error details: {error_msg}")  # Debug print
        
        if "api_key" in error_msg.lower():
            return jsonify({"response": "API key configuration error. Please contact support."}), 500
        elif "rate limit" in error_msg.lower():
            return jsonify({"response": "Too many requests. Please try again in a moment."}), 429
        else:
            return jsonify({"response": "I apologize, but I encountered an error. Please try again later."}), 500

@bp.route('/help')
@login_required
def help():
    return render_template('main/help.html', title='Help & Support') 