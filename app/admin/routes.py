from flask import render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user
from functools import wraps
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired, Email
from flask_wtf.csrf import generate_csrf, validate_csrf
from app.admin import bp
from app.models import User, Organization, Invitation, SubscriptionPlan, Subscription, SubscriptionFeedback
from app import db
from datetime import datetime, timedelta
import uuid
import stripe

def get_stripe():
    """Get Stripe instance with current configuration"""
    if not hasattr(get_stripe, 'stripe_instance'):
        stripe.api_key = current_app.config.get('STRIPE_SECRET_KEY')
        if not stripe.api_key or stripe.api_key == 'your-stripe-secret-key':
            raise ValueError('Invalid Stripe secret key. Please check your configuration.')
        get_stripe.stripe_instance = stripe
    return get_stripe.stripe_instance

class CreateOrganizationForm(FlaskForm):
    name = StringField('Organization Name', validators=[DataRequired()])
    domain = StringField('Email Domain', validators=[DataRequired()])
    submit = SubmitField('Create Organization')

class InviteUserForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    role = StringField('Role', validators=[DataRequired()])
    submit = SubmitField('Send Invitation')

def admin_required(f):
    """Decorator to require admin access"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_admin:
            flash('You need to be an admin to access this page.', 'danger')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function

@bp.route('/organizations')
@login_required
@admin_required
def organizations():
    """List all organizations (super admin only)"""
    orgs = Organization.query.all()
    return render_template('admin/organizations.html', organizations=orgs)

@bp.route('/organization/create', methods=['GET', 'POST'])
@login_required
def create_organization():
    """Create a new organization"""
    form = CreateOrganizationForm()
    
    if form.validate_on_submit():
        name = form.name.data
        domain = form.domain.data
        
        if Organization.query.filter_by(domain=domain).first():
            flash('Domain already registered.', 'danger')
            return redirect(url_for('admin.create_organization'))
        
        try:
            # Get the Free plan
            free_plan = SubscriptionPlan.query.filter_by(name='Free').first()
            if not free_plan:
                flash('Unable to create organization: Free plan not found.', 'danger')
                return redirect(url_for('admin.create_organization'))

            # Create the organization with Free plan
            org = Organization(
                name=name, 
                domain=domain,
                subscription_plan_id=free_plan.id
            )
            db.session.add(org)
            
            # Need to flush to get the organization ID
            db.session.flush()
            
            # Create initial subscription
            subscription = Subscription(
                organization_id=org.id,
                plan_id=free_plan.id,
                status='active',
                start_date=datetime.utcnow(),
                next_billing_date=datetime.utcnow() + timedelta(days=30)  # Set next billing date to 30 days from now
            )
            db.session.add(subscription)
            
            # Need to flush to get the subscription ID
            db.session.flush()
            
            # Now we can safely set the current subscription
            org.current_subscription_id = subscription.id
            
            # Set user's organization and make them an admin
            current_user.organization = org
            current_user.role = 'admin'
            
            db.session.commit()
            flash(f'Organization {name} created successfully with Free plan!', 'success')
            return redirect(url_for('admin.manage_organization'))
        except Exception as e:
            db.session.rollback()
            flash('An error occurred while creating the organization. Please try again.', 'danger')
            return redirect(url_for('admin.create_organization'))
    
    return render_template('admin/create_organization.html', form=form)

@bp.route('/manage')
@login_required
@admin_required
def manage_organization():
    org = current_user.organization
    if not org:
        flash('You need to be part of an organization to manage it.', 'warning')
        return redirect(url_for('main.index'))
    
    # Detailed debug logging
    current_app.logger.info("\n=== Organization Debug Info ===")
    current_app.logger.info(f"Organization ID: {org.id}")
    current_app.logger.info(f"Organization Name: {org.name}")
    current_app.logger.info(f"Organization Domain: {org.domain}")
    current_app.logger.info(f"Subscription Plan ID: {org.subscription_plan_id}")
    current_app.logger.info(f"Current Subscription ID: {org.current_subscription_id}")
    
    # Get all subscriptions for this org
    all_subs = Subscription.query.filter_by(organization_id=org.id).all()
    current_app.logger.info("\n=== All Subscriptions ===")
    for sub in all_subs:
        current_app.logger.info(f"Subscription ID: {sub.id}")
        current_app.logger.info(f"Status: {sub.status}")
        current_app.logger.info(f"Plan ID: {sub.plan_id}")
        current_app.logger.info(f"Start Date: {sub.start_date}")
        current_app.logger.info(f"End Date: {sub.end_date}")
        current_app.logger.info(f"Next Billing Date: {sub.next_billing_date}")
        current_app.logger.info("---")
    
    # Fix missing current subscription
    if not org.current_subscription_id:
        # Find the most recent active subscription
        active_sub = Subscription.query.filter_by(
            organization_id=org.id,
            status='active',
            plan_id=org.subscription_plan_id
        ).order_by(Subscription.start_date.desc()).first()
        
        if active_sub:
            org.current_subscription_id = active_sub.id
            db.session.commit()
            current_app.logger.info(f"Fixed missing current_subscription_id. Set to: {active_sub.id}")
    
    if org.subscription_plan:
        current_app.logger.info("\n=== Current Plan ===")
        current_app.logger.info(f"Plan Name: {org.subscription_plan.name}")
        current_app.logger.info(f"Plan Price: ${org.subscription_plan.price}/month")
        current_app.logger.info(f"Team Size Limit: {org.subscription_plan.team_size_limit}")
    
    if org.current_subscription:
        current_app.logger.info("\n=== Current Subscription ===")
        current_app.logger.info(f"Status: {org.current_subscription.status}")
        current_app.logger.info(f"Start Date: {org.current_subscription.start_date}")
        current_app.logger.info(f"End Date: {org.current_subscription.end_date}")
        current_app.logger.info(f"Next Billing: {org.current_subscription.next_billing_date}")
    
    current_app.logger.info("\n=== End Debug Info ===\n")
    
    # Get subscription plans
    subscription_plans = SubscriptionPlan.query.filter_by(is_active=True).all()
    
    # Check and enforce member limit
    if org.subscription_plan:
        member_limit = org.subscription_plan.team_size_limit
        members = User.query.filter_by(organization_id=org.id).order_by(User.created_at.desc()).all()
        if len(members) > member_limit:
            # Get the excess members (newest members first, excluding admins)
            excess_count = len(members) - member_limit
            removed_count = 0
            for member in members:
                if removed_count >= excess_count:
                    break
                if member.role != 'admin':
                    member.organization_id = None
                    member.role = 'user'
                    removed_count += 1
            
            db.session.commit()
            flash(f'{removed_count} members were removed as they exceed your plan\'s limit of {member_limit} members.', 'warning')
            # Refresh members list after removal
            members = User.query.filter_by(organization_id=org.id).order_by(User.created_at.desc()).all()
    else:
        members = User.query.filter_by(organization_id=org.id).order_by(User.created_at.desc()).all()
    
    pending_invites = Invitation.query.filter_by(
        organization_id=org.id,
        accepted=False
    ).filter(
        Invitation.expires_at > datetime.utcnow()
    ).all()
    
    form = FlaskForm()  # Create an empty form for CSRF protection
    
    return render_template('admin/manage_organization.html', 
                         organization=org,
                         members=members,
                         pending_invites=pending_invites,
                         subscription_plans=subscription_plans,
                         stripe_public_key=current_app.config['STRIPE_PUBLIC_KEY'],
                         current_time=datetime.utcnow(),
                         form=form)

@bp.route('/change_plan/<int:plan_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def change_plan(plan_id):
    org = current_user.organization
    if not org:
        flash('You need to be part of an organization to manage subscriptions.', 'warning')
        return redirect(url_for('main.index'))
    
    plan = SubscriptionPlan.query.get_or_404(plan_id)
    
    # Check if the organization has enough seats for the new plan
    if org.active_users_count > plan.team_size_limit:
        flash(f'Cannot downgrade to {plan.name} plan. You have {org.active_users_count} active users, but the plan only allows {plan.team_size_limit}.', 'danger')
        return redirect(url_for('admin.manage_organization'))
    
    # For GET requests (coming from payment success), verify CSRF token from query param
    if request.method == 'GET':
        token = request.args.get('csrf_token')
        if not token or not validate_csrf(token):
            flash('Invalid request.', 'danger')
            return redirect(url_for('admin.manage_organization'))
    
    try:
        # Create new subscription
        subscription = Subscription(
            organization_id=org.id,
            plan_id=plan.id,
            status='active',
            start_date=datetime.utcnow(),
            next_billing_date=datetime.utcnow() + timedelta(days=30)  # Set next billing date to 30 days from now
        )
        db.session.add(subscription)
        
        # Update organization's subscription
        org.subscription_plan_id = plan.id
        org.current_subscription_id = subscription.id
        
        db.session.commit()
        flash(f'Successfully switched to {plan.name} plan.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error changing subscription plan: {str(e)}', 'danger')
    
    return redirect(url_for('admin.manage_organization'))

@bp.route('/organization/invite', methods=['GET', 'POST'])
@login_required
def invite_user():
    """Invite a user to the organization"""
    if not current_user.is_organization_admin:
        flash('Admin access required.', 'danger')
        return redirect(url_for('main.index'))
    
    form = InviteUserForm()
    
    if request.method == 'GET':
        return render_template('admin/invite_user.html', form=form)
    
    if form.validate_on_submit():
        email = form.email.data
        role = form.role.data
        
        if role not in ['user', 'staff', 'admin']:
            flash('Invalid role specified.', 'danger')
            return redirect(url_for('admin.manage_organization'))
        
        try:
            # Check if user is already a member of the organization
            existing_user = User.query.filter_by(
                email=email,
                organization_id=current_user.organization_id
            ).first()
            
            if existing_user:
                flash('This user is already a member of your organization.', 'warning')
                return redirect(url_for('admin.manage_organization'))
            
            # Check if there's a pending invitation that hasn't expired
            existing_invite = Invitation.query.filter_by(
                email=email,
                organization_id=current_user.organization_id,
                accepted=False
            ).filter(
                Invitation.expires_at > datetime.utcnow()
            ).first()
            
            if existing_invite:
                flash('An active invitation already exists for this email.', 'warning')
                return redirect(url_for('admin.manage_organization'))
            
            # Delete any expired invitations for this email
            expired_invites = Invitation.query.filter_by(
                email=email,
                organization_id=current_user.organization_id
            ).filter(
                (Invitation.expires_at <= datetime.utcnow()) | 
                (Invitation.accepted == True)
            ).all()
            
            for invite in expired_invites:
                db.session.delete(invite)
            
            # Create new invitation
            token = str(uuid.uuid4())
            expires_at = datetime.utcnow() + timedelta(days=7)
            
            invitation = Invitation(
                email=email,
                organization_id=current_user.organization_id,
                token=token,
                expires_at=expires_at,
                is_admin_invite=(role in ['admin', 'staff'])  # Both admin and staff get admin privileges
            )
            
            db.session.add(invitation)
            db.session.commit()
            
            # Show the invitation token to the admin
            flash(f'Invitation sent to {email}. Token: {token}', 'success')
            return redirect(url_for('admin.manage_organization'))
            
        except Exception as e:
            db.session.rollback()
            flash('An error occurred while sending the invitation. Please try again.', 'danger')
            return redirect(url_for('admin.manage_organization'))
    
    return render_template('admin/invite_user.html', form=form)

@bp.route('/organization/members/<int:user_id>/remove', methods=['POST'])
@login_required
def remove_member(user_id):
    """Remove a member from the organization"""
    if not current_user.is_organization_admin:
        flash('Admin access required.', 'danger')
        return redirect(url_for('main.index'))
    
    try:
        user = User.query.get_or_404(user_id)
        
        # Don't allow removing yourself
        if user.id == current_user.id:
            flash('You cannot remove yourself from the organization.', 'danger')
            return redirect(url_for('admin.manage_organization'))
            
        # Check if user is in the same organization
        if user.organization_id != current_user.organization_id:
            flash('User not in your organization.', 'danger')
            return redirect(url_for('admin.manage_organization'))
        
        # Remove user from organization
        user.organization_id = None
        user.role = 'user'  # Reset role to default
        db.session.commit()
        
        flash('Member has been removed from the organization.', 'success')
        return redirect(url_for('admin.manage_organization'))
    except Exception as e:
        db.session.rollback()
        flash('An error occurred while removing the member.', 'danger')
        return redirect(url_for('admin.manage_organization'))

@bp.route('/organization/members/<int:user_id>/role', methods=['GET', 'POST'])
@login_required
def update_member_role(user_id):
    """Update a member's role"""
    if not current_user.is_organization_admin:
        flash('Admin access required.', 'danger')
        return redirect(url_for('main.index'))
    
    if request.method == 'GET':
        return redirect(url_for('admin.manage_organization'))
    
    try:
        user = User.query.get_or_404(user_id)
        if user.organization_id != current_user.organization_id:
            flash('User not in your organization.', 'danger')
            return redirect(url_for('admin.manage_organization'))
        
        # Don't allow changing your own role
        if user.id == current_user.id:
            flash('You cannot change your own role.', 'danger')
            return redirect(url_for('admin.manage_organization'))
            
        # Don't allow changing other admin roles
        if user.role == 'admin':
            flash('You cannot modify another admin\'s role.', 'danger')
            return redirect(url_for('admin.manage_organization'))
        
        role = request.form.get('role')
        if role not in ['user', 'staff', 'admin']:
            flash('Invalid role specified.', 'danger')
            return redirect(url_for('admin.manage_organization'))
        
        user.role = role
        db.session.commit()
        
        flash('User role updated successfully.', 'success')
        return redirect(url_for('admin.manage_organization'))
    except Exception as e:
        db.session.rollback()
        flash('An error occurred while updating the role.', 'danger')
        return redirect(url_for('admin.manage_organization'))

@bp.route('/organization/invite/<token>/resend', methods=['POST'])
@login_required
def resend_invite(token):
    """Resend an expired invitation"""
    if not current_user.is_organization_admin:
        flash('Admin access required.', 'danger')
        return redirect(url_for('main.index'))
    
    try:    
        invitation = Invitation.query.filter_by(token=token).first_or_404()
        if invitation.organization_id != current_user.organization_id:
            flash('Invalid invitation.', 'danger')
            return redirect(url_for('admin.manage_organization'))
        
        invitation.expires_at = datetime.utcnow() + timedelta(days=7)
        db.session.commit()
        
        # TODO: Send invitation email
        flash('Invitation resent successfully.', 'success')
        return redirect(url_for('admin.manage_organization'))
    except Exception as e:
        flash('An error occurred while resending the invitation.', 'danger')
        return redirect(url_for('admin.manage_organization'))

@bp.route('/organization/invite/<token>/cancel', methods=['POST'])
@login_required
def cancel_invite(token):
    """Cancel a pending invitation"""
    if not current_user.is_organization_admin:
        flash('Admin access required.', 'danger')
        return redirect(url_for('main.index'))
    
    try:
        invitation = Invitation.query.filter_by(token=token).first_or_404()
        if invitation.organization_id != current_user.organization_id:
            flash('Invalid invitation.', 'danger')
            return redirect(url_for('admin.manage_organization'))
        
        db.session.delete(invitation)
        db.session.commit()
        
        flash('Invitation cancelled successfully.', 'success')
        return redirect(url_for('admin.manage_organization'))
    except Exception as e:
        db.session.rollback()
        flash('An error occurred while cancelling the invitation.', 'danger')
        return redirect(url_for('admin.manage_organization'))

@bp.route('/create-checkout-session', methods=['POST'])
@login_required
@admin_required
def create_checkout_session():
    try:
        # Initialize Stripe with the current secret key
        stripe_instance = get_stripe()
        
        data = request.get_json()
        plan_name = data.get('planName')
        plan_price = float(data.get('planPrice'))
        plan_id = int(data.get('planId'))
        
        # Create Stripe Checkout Session
        success_url = url_for('admin.payment_success', plan_id=plan_id, _external=True)
        cancel_url = url_for('admin.manage_organization', _external=True)
        
        checkout_session = stripe_instance.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'unit_amount': int(plan_price * 100),  # Convert to cents
                    'product_data': {
                        'name': f'{plan_name} Plan',
                        'description': f'Monthly subscription for {plan_name} Plan'
                    },
                    'recurring': {
                        'interval': 'month'
                    }
                },
                'quantity': 1,
            }],
            mode='subscription',
            success_url=success_url,
            cancel_url=cancel_url,
            client_reference_id=str(current_user.organization_id),
            metadata={
                'plan_id': plan_id,
                'organization_id': current_user.organization_id
            }
        )
        
        return jsonify({'id': checkout_session.id})
        
    except Exception as e:
        print(f"Stripe Error: {str(e)}")  # Add logging for debugging
        return jsonify({'error': str(e)}), 403

@bp.route('/payment/success')
@login_required
@admin_required
def payment_success():
    plan_id = request.args.get('plan_id')
    if not plan_id:
        flash('Invalid payment confirmation.', 'danger')
        return redirect(url_for('admin.manage_organization'))
    
    try:
        # Get the plan
        plan = SubscriptionPlan.query.get(plan_id)
        if not plan:
            flash('Invalid plan selected.', 'danger')
            return redirect(url_for('admin.manage_organization'))
        
        org = current_user.organization
        if not org:
            flash('No organization found.', 'danger')
            return redirect(url_for('admin.manage_organization'))
        
        current_plan = org.subscription_plan
        current_subscription = org.current_subscription
        stripe_instance = get_stripe()

        def create_stripe_event_log(event_type, description, metadata=None):
            """Helper function to log events to Stripe"""
            try:
                event_data = {
                    'object': {
                        'customer': org.stripe_customer_id,
                        'description': description,
                        'metadata': metadata or {},
                        'livemode': False,  # Since we're in test mode
                    }
                }

                # Add specific data based on event type
                if event_type == 'checkout.session.completed':
                    event_data['object'].update({
                        'mode': 'subscription',
                        'payment_status': 'paid',
                    })
                elif event_type.startswith('customer.subscription'):
                    event_data['object'].update({
                        'status': metadata.get('status', 'active'),
                        'current_period_end': metadata.get('effective_date'),
                        'cancel_at_period_end': metadata.get('action') == 'schedule_downgrade',
                        'cancel_at': metadata.get('effective_date'),
                    })
                elif event_type.startswith('invoice'):
                    event_data['object'].update({
                        'status': 'paid',
                        'amount_paid': metadata.get('amount', 0),
                        'billing_reason': metadata.get('action', 'subscription_update'),
                    })

                # Create the event with enhanced visibility
                stripe_instance.Event.create(
                    type=event_type,
                    data=event_data
                )
            except Exception as e:
                print(f"Error logging Stripe event: {str(e)}")

        # Handle different subscription scenarios
        if current_subscription:
            if current_subscription.status == 'cancelled':
                # Reactivating a cancelled subscription with the same plan
                if current_plan and current_plan.id == plan.id:
                    if org.stripe_subscription_id:
                        try:
                            # Reactivate in Stripe first
                            stripe_sub = stripe_instance.Subscription.modify(
                                org.stripe_subscription_id,
                                cancel_at_period_end=False,
                                billing_cycle_anchor='unchanged',
                                proration_behavior='none',
                                metadata={
                                    'action': 'reactivate',
                                    'organization_id': str(org.id),
                                    'plan_name': plan.name,
                                    'previous_status': 'cancelled'
                                }
                            )
                            # Log the reactivation event
                            create_stripe_event_log(
                                'subscription.reactivated',
                                f'Subscription reactivated for {org.name}',
                                {
                                    'organization_id': str(org.id),
                                    'plan_name': plan.name,
                                    'next_billing_date': stripe_sub.current_period_end
                                }
                            )
                            current_subscription.next_billing_date = datetime.fromtimestamp(stripe_sub.current_period_end)
                        except Exception as e:
                            print(f"Stripe reactivation error: {str(e)}")
                            flash('Error syncing with payment system. Please contact support.', 'danger')
                            return redirect(url_for('admin.manage_organization'))
                    
                    current_subscription.status = 'active'
                    current_subscription.end_date = None
                    flash(f'Your {plan.name} subscription has been reactivated. You will be charged on your next billing date: {current_subscription.next_billing_date.strftime("%B %d, %Y")}.', 'success')
            
            elif current_subscription.status == 'scheduled_downgrade':
                if current_plan.price < plan.price:
                    # Reverting a scheduled downgrade (going back to higher tier)
                    if org.stripe_subscription_id:
                        try:
                            stripe_sub = stripe_instance.Subscription.modify(
                                org.stripe_subscription_id,
                                cancel_at_period_end=False,
                                items=[{'price': current_plan.stripe_price_id}],
                                billing_cycle_anchor='unchanged',
                                proration_behavior='none',
                                metadata={
                                    'action': 'revert_downgrade',
                                    'organization_id': str(org.id),
                                    'plan_name': current_plan.name,
                                    'previous_status': 'scheduled_downgrade'
                                }
                            )
                            # Log the revert event
                            create_stripe_event_log(
                                'subscription.downgrade_reverted',
                                f'Scheduled downgrade reverted for {org.name}',
                                {
                                    'organization_id': str(org.id),
                                    'plan_name': current_plan.name,
                                    'next_billing_date': stripe_sub.current_period_end
                                }
                            )
                            current_subscription.next_billing_date = datetime.fromtimestamp(stripe_sub.current_period_end)
                        except Exception as e:
                            print(f"Stripe revert error: {str(e)}")
                            flash('Error syncing with payment system. Please contact support.', 'danger')
                            return redirect(url_for('admin.manage_organization'))
                    
                    # Delete any scheduled subscriptions
                    scheduled_sub = Subscription.query.filter_by(
                        organization_id=org.id,
                        status='scheduled'
                    ).first()
                    if scheduled_sub:
                        db.session.delete(scheduled_sub)
                    
                    current_subscription.status = 'active'
                    current_subscription.end_date = None
                    flash(f'Your scheduled downgrade has been cancelled. You will keep your {current_plan.name} plan.', 'success')
            
            else:  # Active subscription
                if current_plan:
                    if plan.price < current_plan.price:
                        # Downgrading to a cheaper plan
                        if org.stripe_subscription_id:
                            try:
                                # Schedule the downgrade in Stripe
                                stripe_sub = stripe_instance.Subscription.modify(
                                    org.stripe_subscription_id,
                                    cancel_at_period_end=True,
                                    proration_behavior='none',
                                    metadata={
                                        'action': 'schedule_downgrade',
                                        'organization_id': str(org.id),
                                        'current_plan': current_plan.name,
                                        'new_plan': plan.name,
                                        'downgrade_date': datetime.fromtimestamp(stripe_sub.current_period_end).strftime('%Y-%m-%d')
                                    }
                                )
                                # Log the downgrade scheduling event
                                create_stripe_event_log(
                                    'subscription.downgrade_scheduled',
                                    f'Subscription downgrade scheduled for {org.name}',
                                    {
                                        'organization_id': str(org.id),
                                        'from_plan': current_plan.name,
                                        'to_plan': plan.name,
                                        'effective_date': stripe_sub.current_period_end
                                    }
                                )
                                next_billing_date = datetime.fromtimestamp(stripe_sub.current_period_end)
                            except Exception as e:
                                print(f"Stripe downgrade error: {str(e)}")
                                flash('Error syncing with payment system. Please contact support.', 'danger')
                                return redirect(url_for('admin.manage_organization'))
                        else:
                            next_billing_date = current_subscription.next_billing_date
                        
                        # Create new subscription that starts at the next billing date
                        new_subscription = Subscription(
                            organization_id=org.id,
                            plan_id=plan.id,
                            status='scheduled',
                            start_date=next_billing_date,
                            next_billing_date=next_billing_date + timedelta(days=30)
                        )
                        db.session.add(new_subscription)
                        
                        # Mark current subscription as scheduled to end
                        current_subscription.status = 'scheduled_downgrade'
                        current_subscription.end_date = next_billing_date
                        
                        flash(f'Your subscription will be downgraded to the {plan.name} plan on {next_billing_date.strftime("%B %d, %Y")}. '
                              f'You will keep your {current_plan.name} features until then. '
                              f'You can revert this change anytime before {next_billing_date.strftime("%B %d, %Y")}.', 'info')
                    else:
                        # Upgrading to a more expensive plan - apply immediately with proration
                        if org.stripe_subscription_id:
                            try:
                                # Upgrade in Stripe immediately with proration
                                stripe_sub = stripe_instance.Subscription.modify(
                                    org.stripe_subscription_id,
                                    items=[{'price': plan.stripe_price_id}],
                                    proration_behavior='always_invoice',
                                    billing_cycle_anchor='unchanged',
                                    metadata={
                                        'action': 'upgrade',
                                        'organization_id': str(org.id),
                                        'previous_plan': current_plan.name,
                                        'new_plan': plan.name,
                                        'upgrade_date': datetime.utcnow().strftime('%Y-%m-%d')
                                    }
                                )
                                # Log the upgrade event
                                create_stripe_event_log(
                                    'subscription.upgraded',
                                    f'Subscription upgraded for {org.name}',
                                    {
                                        'organization_id': str(org.id),
                                        'from_plan': current_plan.name,
                                        'to_plan': plan.name,
                                        'proration_date': datetime.utcnow().timestamp()
                                    }
                                )
                                next_billing_date = datetime.fromtimestamp(stripe_sub.current_period_end)
                            except Exception as e:
                                print(f"Stripe upgrade error: {str(e)}")
                                flash('Error syncing with payment system. Please contact support.', 'danger')
                                return redirect(url_for('admin.manage_organization'))
                        else:
                            next_billing_date = datetime.utcnow() + timedelta(days=30)
                        
                        current_subscription.status = 'cancelled'
                        current_subscription.end_date = datetime.utcnow()
        
        # Create new subscription
                        new_subscription = Subscription(
            organization_id=org.id,
            plan_id=plan.id,
            status='active',
            start_date=datetime.utcnow(),
                            next_billing_date=next_billing_date
        )
                        db.session.add(new_subscription)
                        org.current_subscription_id = new_subscription.id
        
                        flash(f'Successfully upgraded to the {plan.name} plan! You will be charged a prorated amount for the upgrade.', 'success')
        
        # Update organization's plan
        org.subscription_plan_id = plan.id
        db.session.commit()
        
        # When upgrading, add invoice.paid event
        create_stripe_event_log(
            'invoice.paid',
            f'Upgrade proration invoice paid for {org.name}',
            {
                'organization_id': str(org.id),
                'from_plan': current_plan.name,
                'to_plan': plan.name,
                'amount': plan.price - current_plan.price
            }
        )
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error processing payment: {str(e)}', 'danger')
    
    return redirect(url_for('admin.manage_organization'))

@bp.route('/webhook', methods=['POST'])
@bp.route('/admin/webhook', methods=['POST'])
def stripe_webhook():
    """Handle Stripe webhook events"""
    payload = request.get_data()
    sig_header = request.headers.get('Stripe-Signature')
    
    try:
        print("Received webhook event")  # Debug logging
        
        # Initialize Stripe with the current secret key
        stripe_instance = get_stripe()
        
        # Verify webhook signature
        event = stripe.Webhook.construct_event(
            payload, sig_header, current_app.config['STRIPE_WEBHOOK_SECRET']
        )
        
        print(f"Webhook event type: {event.type}")  # Debug logging
        
        # Handle the event
        if event.type == 'checkout.session.completed':
            session = event.data.object
            print(f"Processing completed checkout session: {session.id}")  # Debug logging
            
            # Get the organization and plan IDs from metadata
            org_id = session.metadata.get('organization_id')
            plan_id = session.metadata.get('plan_id')
            
            print(f"Organization ID: {org_id}, Plan ID: {plan_id}")  # Debug logging
            
            if org_id and plan_id:
                org = Organization.query.get(org_id)
                plan = SubscriptionPlan.query.get(plan_id)
                
                if org and plan:
                    print(f"Updating subscription for org {org.name} to plan {plan.name}")  # Debug logging
                    
                    # Update the organization's subscription
                    if org.current_subscription:
                        org.current_subscription.status = 'cancelled'
                        org.current_subscription.end_date = datetime.utcnow()
                    
                    # Create new subscription
                    subscription = Subscription(
                        organization_id=org.id,
                        plan_id=plan.id,
                        status='active',
                        start_date=datetime.utcnow(),
                        next_billing_date=datetime.utcnow() + timedelta(days=30)
                    )
                    db.session.add(subscription)
                    
                    # Update organization's subscription
                    org.subscription_plan_id = plan.id
                    org.current_subscription_id = subscription.id
                    
                    db.session.commit()
                    print("Successfully updated subscription")  # Debug logging
        
        return jsonify({'status': 'success'}), 200
        
    except Exception as e:
        print(f'Stripe webhook error: {str(e)}')
        return jsonify({'error': str(e)}), 400

@bp.route('/subscription/cancel', methods=['POST'])
@login_required
@admin_required
def cancel_subscription():
    try:
        org = current_user.organization
        if not org:
            return jsonify({'error': 'No organization found'}), 404

        # Check if there's an active subscription
        if not org.current_subscription:
            return jsonify({'error': 'No active subscription found. You may be on the free plan or your subscription has already been cancelled.'}), 400

        # Check subscription status
        if org.current_subscription.status == 'cancelled':
            return jsonify({'error': 'This subscription has already been cancelled.'}), 400

        # Since we don't have a Stripe subscription, just use current subscription end date or 30 days from now
        if org.current_subscription.next_billing_date:
            current_period_end = int(org.current_subscription.next_billing_date.timestamp())
        else:
            current_period_end = int((datetime.utcnow() + timedelta(days=30)).timestamp())

        # Update local subscription
        org.current_subscription.status = 'cancelled'
        org.current_subscription.end_date = datetime.fromtimestamp(current_period_end)

        # Cancel any other active subscriptions for this organization
        other_active_subs = Subscription.query.filter_by(
            organization_id=org.id,
            status='active'
        ).all()
        
        for sub in other_active_subs:
            sub.status = 'cancelled'
            sub.end_date = datetime.fromtimestamp(current_period_end)

        db.session.commit()

        return jsonify({
            'subscription': {
                'status': 'canceled',
                'current_period_end': current_period_end,
                'cancel_at_period_end': True
            }
        })

    except Exception as e:
        db.session.rollback()
        error_msg = str(e)
        print(f"Error cancelling subscription: {error_msg}")  # Log the error
        return jsonify({'error': f'Failed to cancel subscription: {error_msg}'}), 400

@bp.route('/api/subscription', methods=['GET'])
@login_required
@admin_required
def get_subscription():
    try:
        org = current_user.organization
        if not org:
            return jsonify({'error': 'No organization found'}), 404

        subscription_data = None
        if org.current_subscription:
            # Get Stripe subscription details if available
            stripe_instance = get_stripe()
            stripe_sub = None
            if org.stripe_subscription_id:
                try:
                    stripe_sub = stripe_instance.Subscription.retrieve(org.stripe_subscription_id)
                except Exception as e:
                    print(f"Error fetching Stripe subscription: {e}")

            subscription_data = {
                'status': org.current_subscription.status,
                'plan': {
                    'name': org.subscription_plan.name,
                    'description': org.subscription_plan.description,
                    'price': org.subscription_plan.price,
                    'features': org.subscription_plan.features
                },
                'current_period_end': int(org.current_subscription.next_billing_date.timestamp()) if org.current_subscription.next_billing_date else None,
                'cancel_at_period_end': stripe_sub.cancel_at_period_end if stripe_sub else False
            }

        return jsonify({
            'subscription': subscription_data
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 400

@bp.route('/fix_subscription')
@login_required
@admin_required
def fix_subscription():
    try:
        org = current_user.organization
        if not org:
            flash('No organization found.', 'danger')
            return redirect(url_for('admin.manage_organization'))
        
        # Find the active subscription
        active_sub = Subscription.query.filter_by(
            organization_id=org.id,
            status='active'
        ).first()
        
        if active_sub:
            # Link it to the organization
            org.current_subscription_id = active_sub.id
            db.session.commit()
            flash('Successfully fixed subscription link.', 'success')
        else:
            # If no active subscription found, create one for the current plan
            subscription = Subscription(
                organization_id=org.id,
                plan_id=org.subscription_plan_id,
                status='active',
                start_date=datetime.utcnow(),
                next_billing_date=datetime.utcnow() + timedelta(days=30)
            )
            db.session.add(subscription)
            db.session.flush()
            
            org.current_subscription_id = subscription.id
            db.session.commit()
            flash('Created and linked new subscription.', 'success')
        
        return redirect(url_for('admin.manage_organization'))
    except Exception as e:
        db.session.rollback()
        flash(f'Error fixing subscription: {str(e)}', 'danger')
        return redirect(url_for('admin.manage_organization'))

@bp.route('/resubscribe')
@login_required
@admin_required
def resubscribe():
    """Show the resubscribe page for cancelled subscriptions"""
    org = current_user.organization
    if not org:
        flash('You need to be part of an organization to manage subscriptions.', 'warning')
        return redirect(url_for('main.index'))
    
    if not org.current_subscription or org.current_subscription.status != 'cancelled':
        flash('This page is only available for cancelled subscriptions.', 'warning')
        return redirect(url_for('admin.manage_organization'))
    
    return render_template('admin/resubscribe.html', 
                         organization=org,
                         end_date=org.current_subscription.end_date,
                         days_remaining=((org.current_subscription.end_date - datetime.utcnow()).days))

@bp.route('/subscription/reactivate', methods=['POST'])
@login_required
@admin_required
def reactivate_subscription():
    """Reactivate a cancelled subscription"""
    try:
        org = current_user.organization
        if not org:
            flash('No organization found.', 'danger')
            return redirect(url_for('admin.manage_organization'))

        if not org.current_subscription:
            flash('No subscription found to reactivate.', 'danger')
            return redirect(url_for('admin.manage_organization'))

        if org.current_subscription.status != 'cancelled':
            flash('This subscription is not cancelled.', 'warning')
            return redirect(url_for('admin.manage_organization'))

        # Reactivate the subscription
        org.current_subscription.status = 'active'
        org.current_subscription.end_date = None  # Clear the end date
        db.session.commit()

        flash('Your subscription has been successfully reactivated!', 'success')
        return redirect(url_for('admin.manage_organization'))

    except Exception as e:
        db.session.rollback()
        flash(f'Error reactivating subscription: {str(e)}', 'danger')
        return redirect(url_for('admin.resubscribe')) 

@bp.route('/switch_plan', methods=['POST'])
@login_required
@admin_required
def switch_plan():
    plan_id = request.form.get('plan_id')
    if not plan_id:
        flash('Invalid plan selection.', 'danger')
        return redirect(url_for('admin.manage_organization'))
    
    try:
        # Get the plan
        plan = SubscriptionPlan.query.get(plan_id)
        if not plan:
            flash('Invalid plan selected.', 'danger')
            return redirect(url_for('admin.manage_organization'))
        
        org = current_user.organization
        if not org:
            flash('No organization found.', 'danger')
            return redirect(url_for('admin.manage_organization'))
        
        current_plan = org.subscription_plan
        current_subscription = org.current_subscription
        stripe_instance = get_stripe()

        def log_subscription_change(action, details):
            """Helper function to log subscription changes"""
            print(f"\n=== Subscription Change Log ===")
            print(f"Action: {action}")
            print(f"Organization: {org.name} (ID: {org.id})")
            print(f"Current Plan: {current_plan.name} (${current_plan.price}/month)")
            print(f"Target Plan: {plan.name} (${plan.price}/month)")
            print("Details:", details)
            print("==============================\n")

        if not current_subscription or not current_plan:
            # New subscription - redirect to Stripe payment
            return redirect(url_for('admin.payment_checkout', plan_id=plan_id))
        
        # Check if this is a downgrade (moving to a cheaper plan)
        is_downgrade = plan.price < current_plan.price
        
        if is_downgrade:
            # Handle downgrade - no payment needed, just schedule the change
            next_billing_date = current_subscription.next_billing_date or (datetime.utcnow() + timedelta(days=30))
            
            # Log initial state
            log_subscription_change("DOWNGRADE_STARTED", {
                "Current Status": current_subscription.status,
                "Current End Date": current_subscription.end_date,
                "Next Billing Date": next_billing_date
            })
            
            # Only try to modify Stripe subscription if it exists
            stripe_updated = False
            if hasattr(org, 'stripe_subscription_id') and org.stripe_subscription_id:
                try:
                    # Get the current subscription from Stripe
                    stripe_sub = stripe_instance.Subscription.retrieve(org.stripe_subscription_id)
                    
                    # Schedule the downgrade in Stripe by updating the subscription
                    stripe_sub = stripe_instance.Subscription.modify(
                        org.stripe_subscription_id,
                        cancel_at_period_end=True,
                        proration_behavior='none',
                        metadata={
                            'action': 'schedule_downgrade',
                            'organization_id': str(org.id),
                            'current_plan': current_plan.name,
                            'new_plan': plan.name,
                            'downgrade_date': datetime.fromtimestamp(stripe_sub.current_period_end).strftime('%Y-%m-%d')
                        }
                    )
                    
                    # Schedule the new subscription to start at period end
                    stripe_instance.SubscriptionSchedule.create(
                        customer=org.stripe_customer_id,
                        start_date=stripe_sub.current_period_end,
                        phases=[{
                            'items': [{'price': plan.stripe_price_id, 'quantity': 1}],
                            'start_date': stripe_sub.current_period_end
                        }]
                    )
                    
                    next_billing_date = datetime.fromtimestamp(stripe_sub.current_period_end)
                    stripe_updated = True
                    
                    log_subscription_change("STRIPE_UPDATED", {
                        "Subscription ID": org.stripe_subscription_id,
                        "Cancel At Period End": True,
                        "Period End": stripe_sub.current_period_end,
                        "New Next Billing Date": next_billing_date
                    })
                except Exception as e:
                    print(f"Stripe downgrade error: {str(e)}")
                    # Continue with local changes even if Stripe update fails
            
            # Create new subscription that starts at the next billing date
            new_subscription = Subscription(
                organization_id=org.id,
                plan_id=plan.id,
                status='scheduled',
                start_date=next_billing_date,
                next_billing_date=next_billing_date + timedelta(days=30)
            )
            db.session.add(new_subscription)
            
            # Mark current subscription as scheduled to end
            current_subscription.status = 'scheduled_downgrade'
            current_subscription.end_date = next_billing_date
            
            # Log database changes
            log_subscription_change("DATABASE_UPDATED", {
                "Current Subscription": {
                    "Status": current_subscription.status,
                    "End Date": current_subscription.end_date
                },
                "New Subscription": {
                    "Status": new_subscription.status,
                    "Start Date": new_subscription.start_date,
                    "Next Billing Date": new_subscription.next_billing_date
                }
            })
            
            try:
                db.session.commit()
                log_subscription_change("CHANGES_COMMITTED", {
                    "Success": True,
                    "Stripe Updated": stripe_updated,
                    "Database Updated": True
                })
            except Exception as e:
                db.session.rollback()
                log_subscription_change("COMMIT_FAILED", {
                    "Error": str(e)
                })
                raise
            
            flash(f'Your subscription will be downgraded to the {plan.name} plan on {next_billing_date.strftime("%B %d, %Y")}. '
                  f'You will keep your {current_plan.name} features until then. '
                  f'You can revert this change anytime before {next_billing_date.strftime("%B %d, %Y")}.', 'info')
            
            return redirect(url_for('admin.manage_organization'))
        else:
            # For upgrades, redirect to Stripe payment
            return redirect(url_for('admin.payment_checkout', plan_id=plan_id))
            
    except Exception as e:
        db.session.rollback()
        flash(f'Error switching plans: {str(e)}', 'danger')
        return redirect(url_for('admin.manage_organization'))

@bp.route('/cancel_downgrade', methods=['POST'])
@login_required
@admin_required
def cancel_downgrade():
    try:
        org = current_user.organization
        if not org:
            flash('No organization found.', 'danger')
            return redirect(url_for('admin.manage_organization'))

        current_subscription = org.current_subscription
        if not current_subscription or current_subscription.status != 'scheduled_downgrade':
            flash('No scheduled downgrade found.', 'warning')
            return redirect(url_for('admin.manage_organization'))

        # Delete the scheduled subscription
        scheduled_sub = Subscription.query.filter_by(
            organization_id=org.id,
            status='scheduled'
        ).first()
        if scheduled_sub:
            db.session.delete(scheduled_sub)

        # Update Stripe if we have a subscription ID
        if hasattr(org, 'stripe_subscription_id') and org.stripe_subscription_id:
            try:
                stripe_instance = get_stripe()
                # Cancel the scheduled cancellation in Stripe
                stripe_sub = stripe_instance.Subscription.modify(
                    org.stripe_subscription_id,
                    cancel_at_period_end=False,
                    metadata={
                        'action': 'cancel_downgrade',
                        'organization_id': str(org.id)
                    }
                )
                # Update our next billing date to match Stripe
                current_subscription.next_billing_date = datetime.fromtimestamp(stripe_sub.current_period_end)
                
                # Log the event in Stripe
                create_stripe_event_log(
                    'customer.subscription.updated',
                    f'Scheduled downgrade cancelled for {org.name}',
                    {
                        'organization_id': str(org.id),
                        'action': 'cancel_downgrade',
                        'status': 'active'
                    }
                )
            except Exception as e:
                print(f"Stripe cancel downgrade error: {str(e)}")
                # Continue with local changes even if Stripe update fails

        # Reactivate the current subscription
        current_subscription.status = 'active'
        current_subscription.end_date = None
        
        db.session.commit()
        flash('Your scheduled downgrade has been cancelled. You will keep your current plan.', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error cancelling downgrade: {str(e)}', 'danger')
    
    return redirect(url_for('admin.manage_organization')) 