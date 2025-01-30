from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, SubmitField
from wtforms.validators import DataRequired, Length

class TicketForm(FlaskForm):
    title = StringField('Title', validators=[DataRequired(), Length(min=1, max=100)])
    description = TextAreaField('Description', validators=[DataRequired()])
    priority = SelectField('Priority', choices=[
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High')
    ], validators=[DataRequired()])
    category = SelectField('Category', choices=[
        ('general', 'General'),
        ('technical', 'Technical'),
        ('billing', 'Billing'),
        ('feature_request', 'Feature Request'),
        ('bug_report', 'Bug Report')
    ], validators=[DataRequired()])
    submit = SubmitField('Submit')

class ResponseForm(FlaskForm):
    content = TextAreaField('Response', validators=[DataRequired()])
    submit = SubmitField('Submit Response') 