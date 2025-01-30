from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, SubmitField, BooleanField
from wtforms.validators import DataRequired, Length
from app.models import User

class EditProfileForm(FlaskForm):
    username = StringField('Username', validators=[
        DataRequired(),
        Length(min=3, max=64, message='Username must be between 3 and 64 characters')
    ])
    submit = SubmitField('Save Changes')

    def __init__(self, original_username=None, *args, **kwargs):
        super(EditProfileForm, self).__init__(*args, **kwargs)
        self.original_username = original_username

    def validate_username(self, username):
        if username.data != self.original_username:
            user = User.query.filter_by(username=username.data).first()
            if user is not None:
                raise ValidationError('Please use a different username.')

class TicketForm(FlaskForm):
    title = StringField('Title', validators=[
        DataRequired(),
        Length(min=5, max=100, message='Title must be between 5 and 100 characters')
    ])
    description = TextAreaField('Description', validators=[
        DataRequired(),
        Length(min=10, message='Description must be at least 10 characters')
    ])
    priority = SelectField('Priority', 
        choices=[('Low', 'Low'), ('Medium', 'Medium'), ('High', 'High')],
        validators=[DataRequired()]
    )
    category = SelectField('Category',
        choices=[
            ('General', 'General'),
            ('Technical', 'Technical'),
            ('Account', 'Account'),
            ('Billing', 'Billing'),
            ('Feature Request', 'Feature Request')
        ],
        validators=[DataRequired()]
    )
    submit = SubmitField('Create Ticket')

class UpdateTicketForm(FlaskForm):
    status = SelectField('Status', 
        choices=[
            ('Open', 'Open'),
            ('In Progress', 'In Progress'),
            ('On Hold', 'On Hold'),
            ('Closed', 'Closed')
        ],
        validators=[DataRequired()]
    )
    assignee = SelectField('Assign To', coerce=int)  # Will be populated with staff users
    submit = SubmitField('Update Ticket')

class TicketCommentForm(FlaskForm):
    content = TextAreaField('Comment', validators=[
        DataRequired(),
        Length(min=2, message='Comment must be at least 2 characters')
    ])
    is_internal = BooleanField('Internal Note (Staff Only)')
    submit = SubmitField('Add Comment')

class ChatForm(FlaskForm):
    message = TextAreaField('Message', validators=[
        DataRequired(),
        Length(min=2, max=500, message='Message must be between 2 and 500 characters')
    ])
    submit = SubmitField('Send') 