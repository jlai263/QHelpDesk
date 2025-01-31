from flask import Blueprint

bp = Blueprint('admin', __name__)

from app.admin import routes

# Register the webhook route at the blueprint level
bp.add_url_rule('/webhook', 'webhook', routes.stripe_webhook, methods=['POST'])
bp.add_url_rule('/admin/webhook', 'admin_webhook', routes.stripe_webhook, methods=['POST']) 