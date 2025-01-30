from flask import current_app
from flask_mail import Message
from app import mail
from threading import Thread
import traceback
import logging
import sys

# Set up logging
logging.basicConfig(
    filename='email_debug.log',
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
# Also log to console
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.DEBUG)
logging.getLogger().addHandler(console_handler)

def send_async_email(app, msg):
    try:
        with app.app_context():
            logging.info(f"Attempting to send email to: {msg.recipients}")
            logging.info(f"Using SMTP server: {app.config['MAIL_SERVER']}:{app.config['MAIL_PORT']}")
            logging.info(f"SSL: {app.config['MAIL_USE_SSL']}, TLS: {app.config['MAIL_USE_TLS']}")
            logging.info(f"Username: {app.config['MAIL_USERNAME']}")
            logging.info(f"Password length: {len(app.config['MAIL_PASSWORD'])}")
            mail.send(msg)
            logging.info("Email sent successfully!")
    except Exception as e:
        logging.error(f"Error sending email: {str(e)}")
        logging.error("Traceback:")
        logging.error(traceback.format_exc())
        # Re-raise the exception to ensure it's not silently caught
        raise

def send_email(subject, sender, recipients, text_body, html_body):
    try:
        logging.info(f"\nPreparing to send email:")
        logging.info(f"Subject: {subject}")
        logging.info(f"From: {sender}")
        logging.info(f"To: {recipients}")
        msg = Message(subject, sender=sender, recipients=recipients)
        msg.body = text_body
        msg.html = html_body
        Thread(target=send_async_email, args=(current_app._get_current_object(), msg)).start()
        logging.info("Email thread started")
    except Exception as e:
        logging.error(f"Error preparing email: {str(e)}")
        logging.error("Traceback:")
        logging.error(traceback.format_exc())
        # Re-raise the exception to ensure it's not silently caught
        raise

def send_password_reset_email(user_email, reset_url):
    send_email(
        'Reset Your Password',
        sender=current_app.config['MAIL_DEFAULT_SENDER'],
        recipients=[user_email],
        text_body=f'''To reset your password, visit the following link:

{reset_url}

If you did not request a password reset, simply ignore this email and no changes will be made.

Best regards,
The QHelpDesk Team''',
        html_body=f'''
<p>To reset your password, click on the following link:</p>
<p><a href="{reset_url}">Reset Password</a></p>
<p>If you did not request a password reset, simply ignore this email and no changes will be made.</p>
<p>Best regards,<br>The QHelpDesk Team</p>
'''
    ) 