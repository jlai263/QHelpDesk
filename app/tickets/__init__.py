from flask import Blueprint

bp = Blueprint('tickets', __name__)

from app.tickets import routes
