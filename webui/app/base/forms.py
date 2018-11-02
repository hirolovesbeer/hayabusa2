from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField


class LoginForm(FlaskForm):
    username = StringField('User Name', id='username_login')
    password = PasswordField('Password', id='pwd_login')


class CreateAccountForm(FlaskForm):
    username = StringField('User Name', id='username_create')
    password = PasswordField('Password', id='pwd_create')
    api_password = PasswordField('API Password', id='api_pwd_create')


class AdminModifyAccountForm(FlaskForm):
    password = PasswordField('Password', id='pwd_modify')
    api_password = PasswordField('API Password', id='api_pwd_modify')


class UpdatePasswordForm(FlaskForm):
    old_password = PasswordField('Old Password', id='old_pwd_update')
    new_password = PasswordField('New Password', id='new_pwd_update')
