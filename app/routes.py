from flask import Blueprint, render_template, flash, redirect, url_for, request, current_app
from flask_login import login_required, current_user
from flask_wtf.csrf import csrf_exempt
from app.models import Organization, Subscription
from app import db
import stripe
import logging
from datetime import datetime

bp = Blueprint('main', __name__)

@bp.route('/admin/webhook', methods=['POST'])
@csrf_exempt
def stripe_webhook():
    payload = request.get_data()
    sig_header = request.headers.get('Stripe-Signature')
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, current_app.config['STRIPE_WEBHOOK_SECRET']
        )
        logging.debug(f"Received Stripe webhook event: {event.type}")
    except ValueError as e:
        logging.error(f"Invalid payload: {str(e)}")
        return 'Invalid payload', 400
    except stripe.error.SignatureVerificationError as e:
        logging.error(f"Invalid signature: {str(e)}")
        return 'Invalid signature', 400

    if event.type == 'customer.subscription.updated':
        subscription = event.data.object
        org = Organization.query.filter_by(stripe_customer_id=subscription.customer).first()
        if org:
            org.stripe_subscription_id = subscription.id
            db.session.commit()
            logging.info(f"Updated subscription ID for organization {org.id}")
    
    elif event.type == 'customer.subscription.deleted':
        subscription = event.data.object
        org = Organization.query.filter_by(stripe_customer_id=subscription.customer).first()
        if org:
            # Update the subscription end date
            sub = Subscription.query.filter_by(organization_id=org.id).order_by(Subscription.id.desc()).first()
            if sub:
                sub.end_date = datetime.fromtimestamp(subscription.current_period_end)
                db.session.commit()
                logging.info(f"Updated subscription end date for organization {org.id}")

    return '', 200 
