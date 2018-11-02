from flask import render_template, request, abort, redirect, url_for, session
from flask_login import login_required, current_user

from app import db, webui
from app.admin import blueprint
from app.base.forms import CreateAccountForm, AdminModifyAccountForm
from app.base.models import User


@blueprint.before_request
def admin_required():
    name = current_user.username
    if name != 'admin':
        webui.logger.error('permission denied to access admin pages: %s',
                           name)
        abort(403)


@blueprint.route('/users', methods=['GET', 'POST'])
@login_required
def user_list():
    notice = session.pop('notice', None)
    error = session.pop('error', None)
    if 'create_account' in request.form:
        user = User(**request.form)
        webui.logger.debug('user: %s', user.username)
        if (not user.username) or (not user.password) or \
                (not user.api_password):
            error = 'User Name, Password, and API Password are required'
        else:
            existing_user = \
                User.query.filter_by(username=user.username).first()
            if existing_user:
                error = "'%s' already exists" % user.username
            else:
                try:
                    db.session.add(user)
                    db.session.commit()
                    session['notice'] = 'Created a user'
                    return redirect(url_for('admin_blueprint.user_list'))
                except Exception as e:
                    webui.logger.error('DB Error: %s', e)
                    error = 'Error: Could not create a user'
                    db.session.rollback()
    users = User.query.all()
    account_form = CreateAccountForm(request.form)
    return render_template('users.html', notice=notice, error=error,
                           users=users,
                           account_form=account_form)


@blueprint.route('/users/<user_id>/edit', methods=['GET'])
@login_required
def edit_user(user_id):
    notice = None
    target_user = User.query.filter_by(id=user_id).first()
    if not target_user:
        abort(404)
    users = User.query.all()
    modify_account_form = AdminModifyAccountForm(request.form)
    return render_template('users.html', notice=notice, users=users,
                           target_user=target_user,
                           account_form=modify_account_form)


@blueprint.route('/users/<user_id>/edit', methods=['POST'])
def modify_user(user_id):
    error = None
    target_user = User.query.filter_by(id=user_id).first()
    if not target_user:
        abort(404)
    password = request.form['password']
    api_password = request.form['api_password']
    if (not password) or (not api_password):
        error = 'Password and API Password are required'
        account_form = AdminModifyAccountForm()
    else:
        try:
            target_user.password = password
            target_user.api_password = api_password
            db.session.commit()
            session['notice'] = 'Updated the user information'
            return redirect(url_for('admin_blueprint.user_list'))
        except Exception as e:
            webui.logger.error('DB Error: %s', e)
            error = 'Error: Could not update the user information'
            db.session.rollback()
            account_form = AdminModifyAccountForm()
    users = User.query.all()
    return render_template('users.html', error=error, users=users,
                           target_user=target_user,
                           account_form=account_form)


@blueprint.route('/users/<user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    webui.logger.debug('deleting user id: %s', user_id)
    user = User.query.filter_by(id=user_id).first()
    if user:
        webui.logger.debug('deleting user: %s', user.username)
        try:
            db.session.delete(user)
            db.session.commit()
            session['notice'] = 'Deleted the user'
        except Exception as e:
            webui.logger.error('DB Error: %s', e)
            session['error'] = 'Error: Could not delete the user'
            db.session.rollback()
    else:
        abort(404)
    return redirect(url_for('admin_blueprint.user_list'))
