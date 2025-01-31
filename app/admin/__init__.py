from flask import Blueprint

bp = Blueprint('admin', __name__)

from app.admin import routes

# Register the webhook routes
webhook_view = routes.stripe_webhook
webhook_view.is_exempt = True  # Mark the view as CSRF exempt

bp.add_url_rule('/webhook', 'webhook', webhook_view, methods=['POST'])
bp.add_url_rule('/admin/webhook', 'admin_webhook', webhook_view, methods=['POST']) 