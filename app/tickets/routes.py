from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app.tickets import bp
from app.models import Ticket, TicketResponse, User
from app.tickets.forms import TicketForm, ResponseForm
from app import db
from openai import OpenAI
import os
from datetime import datetime, timedelta

client = OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))

def get_ai_suggestion(title, description):
    print(f"Attempting to get AI suggestion for title: {title}")  # Debug print
    try:
        print(f"OpenAI API Key: {os.environ.get('OPENAI_API_KEY')[:10]}...")  # Debug print (first 10 chars only)
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful IT support assistant. Provide a brief, helpful suggestion for troubleshooting the following computer issue. Be specific and practical."},
                {"role": "user", "content": f"Issue Title: {title}\nDescription: {description}"}
            ],
            max_tokens=200,
            temperature=0.7
        )
        suggestion = response.choices[0].message.content
        print(f"AI Suggestion successfully generated: {suggestion}")  # Debug print
        return suggestion
    except Exception as e:
        print(f"OpenAI API error details: {str(e)}")  # Debug print
        return "Unable to generate AI suggestion at this time."

def require_organization(f):
    """Decorator to require organization membership"""
    def decorated_function(*args, **kwargs):
        if not current_user.organization:
            flash('You need to be a member of an organization to access tickets.', 'warning')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

@bp.route('/')
@login_required
@require_organization
def index():
    # Filter tickets based on user role
    if current_user.is_admin or current_user.role == 'staff':
        # Admin/Staff can see all tickets in their organization
        tickets = Ticket.query.filter_by(organization_id=current_user.organization_id).all()
    else:
        # Regular users can only see their own tickets
        tickets = Ticket.query.filter_by(
            organization_id=current_user.organization_id,
            submitter_id=current_user.id
        ).all()
    
    return render_template('tickets/index.html', title='Tickets', tickets=tickets)

@bp.route('/create', methods=['GET', 'POST'])
@login_required
@require_organization
def create():
    form = TicketForm()
    if form.validate_on_submit():
        # Get AI suggestion if possible
        ai_suggestion = get_ai_suggestion(form.title.data, form.description.data)
        
        # Get available staff members (staff and admins)
        staff_members = User.query.filter(
            User.organization_id == current_user.organization_id,
            User.role.in_(['staff', 'admin']),
            User.is_active == True
        ).all()
        
        # Implement round-robin assignment
        assignee = None
        if staff_members:
            # Get the last assigned ticket
            last_ticket = Ticket.query.filter_by(
                organization_id=current_user.organization_id
            ).order_by(Ticket.created_at.desc()).first()
            
            if last_ticket and last_ticket.assignee_id:
                # Find the next staff member in the rotation
                current_idx = next(
                    (i for i, staff in enumerate(staff_members) 
                     if staff.id == last_ticket.assignee_id), -1
                )
                next_idx = (current_idx + 1) % len(staff_members)
                assignee = staff_members[next_idx]
            else:
                # If no last ticket or it had no assignee, start with the first staff member
                assignee = staff_members[0]
        
        ticket = Ticket(
            title=form.title.data,
            description=form.description.data,
            priority=form.priority.data,
            category=form.category.data,
            submitter_id=current_user.id,
            organization_id=current_user.organization_id,
            assignee_id=assignee.id if assignee else None,
            ai_suggestion=ai_suggestion
        )
        
        db.session.add(ticket)
        db.session.commit()
        
        flash(f'Ticket created and assigned to {assignee.username if assignee else "unassigned"}!', 'success')
        return redirect(url_for('tickets.view', id=ticket.id))
    
    return render_template('tickets/create.html', title='Create Ticket', form=form)

@bp.route('/<int:id>')
@login_required
@require_organization
def view(id):
    ticket = Ticket.query.get_or_404(id)
    
    # Ensure user can only view tickets from their organization
    if ticket.organization_id != current_user.organization_id:
        flash('You do not have permission to view this ticket.', 'danger')
        return redirect(url_for('tickets.index'))
    
    # Regular users can only view their own tickets
    if not (current_user.is_admin or current_user.role == 'staff'):
        if ticket.submitter_id != current_user.id:
            flash('You do not have permission to view this ticket.', 'danger')
            return redirect(url_for('tickets.index'))
    
    form = ResponseForm()
    return render_template('tickets/view.html', title=f'Ticket #{id}', ticket=ticket, form=form)

@bp.route('/<int:id>/update', methods=['POST'])
@login_required
@require_organization
def update(id):
    ticket = Ticket.query.get_or_404(id)
    # Ensure user can only update tickets from their organization
    if ticket.organization_id != current_user.organization_id:
        flash('You do not have permission to update this ticket.', 'danger')
        return redirect(url_for('tickets.index'))
    
    if not current_user.is_staff:
        flash('You do not have permission to update ticket status.', 'danger')
        return redirect(url_for('tickets.view', id=id))
    
    status = request.form.get('status')
    if status in ['open', 'in_progress', 'on_hold', 'closed']:
        ticket.status = status
        db.session.commit()
        flash('Ticket status has been updated.', 'success')
    return redirect(url_for('tickets.view', id=id))

@bp.route('/<int:id>/delete', methods=['POST'])
@login_required
@require_organization
def delete(id):
    ticket = Ticket.query.get_or_404(id)
    # Ensure user can only delete tickets from their organization
    if ticket.organization_id != current_user.organization_id:
        flash('You do not have permission to delete this ticket.', 'danger')
        return redirect(url_for('tickets.index'))
    
    if not (current_user.is_staff or current_user.id == ticket.submitter_id):
        flash('You do not have permission to delete this ticket.', 'danger')
        return redirect(url_for('tickets.view', id=id))
    
    db.session.delete(ticket)
    db.session.commit()
    flash('Ticket has been deleted.', 'success')
    return redirect(url_for('tickets.index'))

@bp.route('/<int:id>/response', methods=['POST'])
@login_required
@require_organization
def add_response(id):
    ticket = Ticket.query.get_or_404(id)
    # Ensure user can only respond to tickets from their organization
    if ticket.organization_id != current_user.organization_id:
        flash('You do not have permission to respond to this ticket.', 'danger')
        return redirect(url_for('tickets.index'))
    
    form = ResponseForm()
    if form.validate_on_submit():
        response = TicketResponse(
            content=form.content.data,
            ticket_id=ticket.id,
            user_id=current_user.id
        )
        
        # Update ticket response tracking for staff responses
        if current_user.is_staff:
            # Set first response time if not set
            if not ticket.first_response_time:
                ticket.first_response_time = datetime.utcnow()
            # Update last response by staff
            ticket.last_response_by_staff = datetime.utcnow()
            ticket.last_updated_by_id = current_user.id
        
        db.session.add(response)
        db.session.commit()
        flash('Your response has been added.', 'success')
    return redirect(url_for('tickets.view', id=id))

@bp.route('/<int:id>/chat', methods=['POST'])
@login_required
def chat(id):
    ticket = Ticket.query.get_or_404(id)
    data = request.get_json()
    user_message = data.get('message')
    
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful IT support assistant. Provide specific and practical solutions for the following computer issue."},
                {"role": "user", "content": f"Ticket Title: {ticket.title}\nDescription: {ticket.description}\nUser Question: {user_message}"}
            ],
            max_tokens=200,
            temperature=0.7
        )
        ai_response = response.choices[0].message.content
        return jsonify({"response": ai_response})
    except Exception as e:
        print(f"OpenAI API error in chat: {str(e)}")
        return jsonify({"response": "I apologize, but I encountered an error. Please try again later."}), 500

@bp.route('/filter')
@login_required
@require_organization
def filter_tickets():
    filters = request.args.getlist('filters')
    
    # Base query - restrict to organization
    if current_user.is_admin or current_user.role == 'staff':
        # Admin/Staff can see all tickets in their organization
        query = Ticket.query.filter_by(organization_id=current_user.organization_id)
    else:
        # Regular users can only see their own tickets
        query = Ticket.query.filter_by(
            organization_id=current_user.organization_id,
            submitter_id=current_user.id
        )
    
    if not filters:
        # If no filters are active, return all tickets (based on user role)
        tickets = query.order_by(Ticket.created_at.desc()).all()
    else:
        for filter_type in filters:
            if filter_type == 'assigned_to_me':
                query = query.filter_by(assignee_id=current_user.id)
            elif filter_type == 'high_priority':
                query = query.filter_by(priority='high')
            elif filter_type == 'needs_response':
                # Get all tickets that have no responses from staff/admin
                query = query.filter(
                    Ticket.status == 'open'  # Only show open tickets
                ).outerjoin(
                    TicketResponse,  # Join with responses
                    (TicketResponse.ticket_id == Ticket.id) & 
                    (TicketResponse.user_id.in_(  # Where response is from staff/admin
                        db.session.query(User.id).filter(
                            User.organization_id == current_user.organization_id,
                            User.role.in_(['staff', 'admin'])
                        )
                    ))
                ).group_by(Ticket.id).having(
                    db.func.count(TicketResponse.id) == 0  # No staff responses found
                )
            elif filter_type == 'overdue':
                # Show tickets that have been open for more than 24 hours
                twenty_four_hours_ago = datetime.utcnow() - timedelta(hours=24)
                query = query.filter(
                    Ticket.status == 'open',
                    Ticket.created_at <= twenty_four_hours_ago
                )
        tickets = query.order_by(Ticket.created_at.desc()).all()
    
    return jsonify({
        'tickets': [{
            'id': ticket.id,
            'title': ticket.title,
            'status': ticket.status,
            'priority': ticket.priority,
            'created_at': ticket.created_at.isoformat(),
            'status_class': ticket.status_class,
            'priority_class': ticket.priority_class,
            'assignee': ticket.assignee.username if ticket.assignee else None
        } for ticket in tickets]
    }) 