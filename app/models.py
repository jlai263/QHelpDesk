from app import db, login
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
import uuid
import re
from sqlalchemy.orm import relationship
from sqlalchemy import event

class Organization(db.Model):
    __tablename__ = 'organizations'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), index=True)
    domain = db.Column(db.String(120), index=True, unique=True)
    stripe_subscription_id = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    subscription_plan_id = db.Column(db.Integer, db.ForeignKey('subscription_plans.id', name='fk_org_subscription_plan'))
    current_subscription_id = db.Column(db.Integer, db.ForeignKey('subscriptions.id', name='fk_org_current_subscription'))
    
    # Relationships
    users = db.relationship('User', backref='organization', lazy='dynamic')
    invitations = db.relationship('Invitation', back_populates='organization', lazy='dynamic')
    current_subscription = db.relationship('Subscription', foreign_keys=[current_subscription_id])
    subscription_plan = db.relationship('SubscriptionPlan', back_populates='organizations')
    tickets = db.relationship('Ticket', back_populates='organization')
    subscriptions = db.relationship('Subscription', backref='organization', 
                                  primaryjoin="Organization.id==Subscription.organization_id",
                                  lazy='dynamic')
    subscription_feedbacks = db.relationship('SubscriptionFeedback', back_populates='organization')

    def __repr__(self):
        return f'<Organization {self.name}>'
    
    def is_valid_email(self, email):
        """Check if email matches organization domain"""
        if not self.domain:
            return True  # If no domain set, accept any email
        return email.lower().endswith('@' + self.domain.lower())

    @property
    def active_users_count(self):
        """Count of active users in the organization"""
        return User.query.filter_by(
            organization_id=self.id,
            is_active=True
        ).count()

    @property
    def can_add_user(self):
        if not self.subscription_plan:
            return False
        return self.active_users_count < self.subscription_plan.team_size_limit

    @property
    def remaining_seats(self):
        if not self.subscription_plan:
            return 0
        return max(0, self.subscription_plan.team_size_limit - self.active_users_count)

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True)
    email = db.Column(db.String(120), index=True, unique=True)
    password_hash = db.Column(db.String(128))
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    last_sign_in_at = db.Column(db.DateTime(timezone=True))
    role = db.Column(db.String(20), default='user', nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    
    # Organization relationship
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'))
    
    # Relationships
    tickets = db.relationship('Ticket', 
                            foreign_keys='Ticket.submitter_id',
                            backref=db.backref('submitter', lazy='joined'),
                            lazy='dynamic',
                            overlaps="submitted_tickets,author")
    assigned_tickets = db.relationship('Ticket',
                                     foreign_keys='Ticket.assignee_id',
                                     backref=db.backref('assignee', lazy='joined'),
                                     lazy='dynamic')
    comments = db.relationship('TicketComment', backref='user', lazy='dynamic')
    responses = db.relationship('TicketResponse', back_populates='user')

    @property
    def is_admin(self):
        return self.role == 'admin'

    @property
    def is_staff(self):
        return self.role in ['staff', 'admin']

    def __repr__(self):
        return f'<User {self.username}>'

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_organization_admin(self):
        """Check if user is an admin of their organization"""
        return self.is_admin and self.organization_id is not None

class Ticket(db.Model):
    __tablename__ = 'tickets'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='open')  # open, in_progress, closed
    priority = db.Column(db.String(20), default='medium')  # low, medium, high
    category = db.Column(db.String(50), nullable=False, default='General')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    due_date = db.Column(db.DateTime(timezone=True))
    submitter_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    assignee_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    first_response_time = db.Column(db.DateTime)
    last_response_by_staff = db.Column(db.DateTime)
    last_updated_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    ai_suggestion = db.Column(db.Text)
    
    # Organization relationship
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'))
    organization = relationship('Organization', back_populates='tickets')

    # Relationships
    comments = relationship('TicketComment', backref='ticket',
                             cascade='all, delete-orphan',
                             lazy='dynamic')
    responses = relationship('TicketResponse', backref='ticket', lazy='dynamic')
    last_updated_by = relationship('User', foreign_keys=[last_updated_by_id])

    @property
    def status_class(self):
        status_classes = {
            'open': 'primary',
            'in_progress': 'warning',
            'on_hold': 'info',
            'closed': 'success'
        }
        return status_classes.get(self.status.lower(), 'secondary')

    @property
    def priority_class(self):
        priority_classes = {
            'low': 'success',
            'medium': 'warning',
            'high': 'danger'
        }
        return priority_classes.get(self.priority.lower(), 'secondary')

    def __repr__(self):
        return f'<Ticket {self.id}: {self.title}>'

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'status': self.status,
            'priority': self.priority,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'assignee_id': self.assignee_id,
            'submitter_id': self.submitter_id
        }

    def needs_response(self):
        """Check if ticket needs a response from staff"""
        if not self.last_response_by_staff:
            return True
        if self.last_updated_by_id and self.last_updated_by_id != self.assignee_id:
            return True
        return False

    def is_overdue(self):
        """Check if ticket is overdue (open for more than 24 hours)"""
        if self.status != 'open':
            return False
        return datetime.utcnow() - self.created_at > timedelta(hours=24)

class TicketComment(db.Model):
    __tablename__ = 'ticket_comments'
    
    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey('tickets.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    content = db.Column(db.Text, nullable=False)
    is_internal = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, index=True, default=datetime.utcnow)

    def __repr__(self):
        return f'<Comment {self.id} on Ticket {self.ticket_id}>'

class TicketResponse(db.Model):
    __tablename__ = 'ticket_responses'
    
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text)
    created_at = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    ticket_id = db.Column(db.Integer, db.ForeignKey('tickets.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    user = relationship('User', back_populates='responses')

    def __repr__(self):
        return f'<TicketResponse {self.id}>'

class Invitation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), nullable=False)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'))
    token = db.Column(db.String(100), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)
    is_admin_invite = db.Column(db.Boolean, default=False)
    accepted = db.Column(db.Boolean, default=False)
    accepted_at = db.Column(db.DateTime)
    
    # Relationship
    organization = db.relationship('Organization', back_populates='invitations')
    
    def is_expired(self):
        return datetime.utcnow() > self.expires_at

class SubscriptionPlan(db.Model):
    __tablename__ = 'subscription_plans'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True, nullable=False)
    price = db.Column(db.Float, nullable=False)
    team_size_limit = db.Column(db.Integer, nullable=False)
    description = db.Column(db.String(256))
    features = db.Column(db.JSON)  # Store features as JSON array
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    organizations = db.relationship('Organization', back_populates='subscription_plan', lazy='dynamic')

    def __repr__(self):
        return f'<SubscriptionPlan {self.name}>'

class Subscription(db.Model):
    __tablename__ = 'subscriptions'
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id', name='fk_subscription_org'))
    plan_id = db.Column(db.Integer, db.ForeignKey('subscription_plans.id', name='fk_subscription_plan'))
    status = db.Column(db.String(20), default='active')  # active, cancelled, expired
    start_date = db.Column(db.DateTime, default=datetime.utcnow)
    end_date = db.Column(db.DateTime)
    last_billing_date = db.Column(db.DateTime)
    next_billing_date = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<Subscription {self.organization_id}:{self.plan_id}>'

    @property
    def is_active(self):
        return (self.status == 'active' and 
                (self.end_date is None or self.end_date > datetime.utcnow()))

class SubscriptionFeedback(db.Model):
    __tablename__ = 'subscription_feedbacks'
    
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    feedback = db.Column(db.Text, nullable=False)
    reason = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    organization = db.relationship('Organization', back_populates='subscription_feedbacks')

@login.user_loader
def load_user(id):
    return User.query.get(int(id)) 