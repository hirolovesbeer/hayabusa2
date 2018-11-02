import json
import linecache
import os
import subprocess
import threading
import time
import uuid
from datetime import datetime

from flask import render_template, request, jsonify, \
    redirect, url_for, session
from flask_login import login_required, current_user

from app import db, webui
from app.base.forms import UpdatePasswordForm
from app.home import blueprint
from hayabusa.errors import unexpected_error, HayabusaError, \
    RESTResultWaitTimeout


@blueprint.route('/settings')
@login_required
def settings():
    notice = session.pop('notice', None)
    error = session.pop('error', None)
    form = UpdatePasswordForm()
    return render_template('settings.html', form=form,
                           notice=notice, error=error)


@blueprint.route('/update_password', methods=['POST'])
@login_required
def update_password():
    old_password = request.form['old_password']
    new_password = request.form['new_password']
    if (not old_password) or (not new_password):
        session['error'] = 'Old Password and New Password are required'
    else:
        if current_user.password != old_password:
            session['error'] = 'Password Mismatch: wrong old password'
        else:
            try:
                current_user.password = new_password
                db.session.commit()
                session['notice'] = 'Changed your password'
            except Exception as e:
                webui.logger.error('DB Error: %s', e)
                session['error'] = \
                    'Error: Could not update the user information'
                db.session.rollback()
    return redirect(url_for('home_blueprint.settings'))


@blueprint.route('/log_search')
@login_required
def log_search():
    match = session.get('log-search-match', '')
    count = session.get('log-search-count', False)
    sum = session.get('log-search-sum', False)
    exact = session.get('log-search-exact', False)
    end_date = datetime.now().strftime('%Y-%m-%d %H:%M')
    return render_template('log_search.html', end_date=end_date, match=match,
                           count=count, sum=sum, exact=exact)


@blueprint.route('/search_queries')
@login_required
def search_queries():
    return render_template('search_queries.html')


@blueprint.route('/charts')
@login_required
def charts():
    queries = webui.query_data.get(current_user.username, [])
    return render_template('charts.html', queries=queries)


@blueprint.route('/queries', methods=['POST'])
@login_required
def queries():
    name = request.form['name']
    if not name:
        error = {'error': 'Name field is required.'}
        return jsonify(error)
    match = request.form['match']

    if request.form.get('exact'):
        exact = True
    else:
        exact = False

    user = current_user.username
    query_id = str(uuid.uuid1())
    data = {'query_id': query_id, 'name': name, 'match': match, 'exact': exact}
    with webui.query_data_lock:
        user_data = webui.query_data.get(user)
        if user_data:
            if len(webui.query_data[user]) == webui.max_search_queries:
                error = {'error': "Max Search Queries Reached: %s" %
                                  webui.max_search_queries}
                return jsonify(error)
            for query in webui.query_data[user]:
                if query['name'] == name:
                    error = {'error': "'%s' already exists." % name}
                    return jsonify(error)
            webui.query_data[user] = user_data + [data]
        else:
            webui.query_data[user] = [data]
    webui.logger.debug('added search query: user: %s, data: %s', user, data)
    return jsonify(data)


@blueprint.route('/queries/<query_id>', methods=['DELETE'])
@login_required
def delete_query(query_id):
    ok_status = {'status': 'ok'}
    not_found = {'error': 'Query Not Found: %s' % query_id}
    user = current_user.username
    with webui.count_data_lock:
        if webui.count_data.get(query_id):
            webui.logger.debug('deleting search query results: '
                               'user: %s, query_id: %s', user, query_id)
            del webui.count_data[query_id]
    with webui.query_data_lock:
        user_data = webui.query_data.get(user)
        if user_data:
            for i, v in enumerate(user_data):
                if v['query_id'] == query_id:
                    webui.logger.debug('deleting search query:'
                                       ' user: %s, data: %s', user, v)
                    del user_data[i]
                    webui.query_data[user] = user_data
                    return jsonify(ok_status)
    return jsonify(not_found)


@blueprint.route('/query_table_data')
@login_required
def query_table_data():
    user = current_user.username
    data = webui.query_data.get(user, [])
    return jsonify(data)


@blueprint.route('/query_chart_data')
@login_required
def query_chart_data():
    user = current_user.username
    user_data = webui.query_data.get(user)
    res = {}
    if user_data:
        for meta in user_data:
            query_id = meta['query_id']
            data = webui.count_data.get(query_id, [])
            res[query_id] = {'meta': meta, 'data': data}
    return jsonify(res)


@blueprint.route('/search', methods=['POST'])
@login_required
def search():
    try:
        time_period = request.form['time_period']
        match = request.form['match']

        if request.form.get('count'):
            count = True
        else:
            count = False
        if request.form.get('sum'):
            sum = True
        else:
            sum = False
        if request.form.get('exact'):
            exact = True
        else:
            exact = False
        session['log-search-match'] = match
        session['log-search-count'] = count
        session['log-search-sum'] = sum
        session['log-search-exact'] = exact

        try:
            start_time, end_time = time_period.split(' - ')
        except ValueError:
            raise HayabusaError('Invalid Time Period: %s' % time_period)

        request_id = post_request(current_user, match, start_time, end_time,
                                  count, sum, exact)
    except HayabusaError as e:
        webui.logger.error('error: %s', e)
        return jsonify({'error': str(e)})
    except Exception as e:
        unexpected_error(webui.logger, 'search', e)
        return jsonify({'error': 'Internal Server Error'})

    return jsonify({'id': request_id})


@blueprint.route('/status/<request_id>', methods=['GET'])
@login_required
def status(request_id):
    webui.logger.debug('status check: %s', request_id)
    try:
        data = webui.rest_client.status(current_user.username,
                                        current_user.api_password, request_id)
    except HayabusaError as e:
        data = {'error': str(e)}
    except Exception as e:
        unexpected_error(webui.logger, 'status', e)
        data = {'error': 'Internal Server Error'}
    return jsonify(data)


@blueprint.route('/draw')
@login_required
def draw_empty():
    try:
        draw = int(request.args.get('draw'))
    except Exception as e:
        webui.logger.error('Invalid Parameters: %s, %s', request.args, e)
        return jsonify({'error': 'Bad Request'})
    return jsonify({'draw': draw, 'data': [], 'recordsTotal': 0,
                    'recordsFiltered': 0})


@blueprint.route('/draw/<request_id>')
@login_required
def draw_request(request_id):
    try:
        draw = int(request.args.get('draw'))
        start = int(request.args.get('start'))
        length = int(request.args.get('length'))
        search_value = request.args.get('search[value]')
    except Exception as e:
        webui.logger.error('Invalid Parameters: %s, %s', request.args, e)
        return jsonify({'error': 'Bad Request'})

    webui.logger.debug('%s - draw: %s, start: %s, length: %s,'
                       ' search_value: %s',
                       request_id, draw, start, length, search_value)

    user = current_user.username
    tmp_file_base = webui.tmp_file_path(user, request_id)
    tmp_file_stdout = tmp_file_base + '.stdout'
    tmp_file_meta = tmp_file_base + '.meta'

    # --------------------------------------
    # wait for a long time to get the result
    while True:
        if os.path.exists(tmp_file_stdout) and os.path.exists(tmp_file_meta):
            break
        else:
            time.sleep(0.1)
    # --------------------------------------

    webui.logger.debug('loading: %s', tmp_file_stdout)
    with open(tmp_file_meta) as f:
        meta_info = json.load(f)
        num_lines = meta_info['lines']
        meta_user = meta_info['user']

    if user != meta_user:
        message = 'Permission Denied for Request: %s' % request_id
        return jsonify({'error': message})

    new_data = []
    # get necessary lines to draw the DataTable
    for num in range(start+1, start+length+1):
        line = linecache.getline(tmp_file_stdout, num)
        new_data.append([line])
    linecache.clearcache()
    res = {'draw': draw, 'data': new_data,
           'recordsTotal': num_lines,
           'recordsFiltered': num_lines, 'meta': meta_info}
    return jsonify(res)


# ============== General Functions ==============


def post_request(user, match, start_time, end_time, count, sum, exact):
    receiver, host, port = webui.rest_client.listen_random_port()
    request_id = webui.rest_client.search_base(user.username,
                                               user.api_password,
                                               match, start_time, end_time,
                                               count, sum, exact, host, port)
    th = threading.Thread(target=receive_result,
                          args=(receiver, user.username, request_id))
    th.setDaemon(True)
    th.start()
    return request_id


def receive_result(receiver, user, request_id):
    try:
        receive_result_main(receiver, user, request_id)
    except Exception as e:
        webui.logger.error('Error: %s', e)


def receive_result_main(receiver, user, request_id):
    file_name_base = webui.tmp_file_path(user, request_id)
    stdout_file = file_name_base + '.stdout'
    meta_file = file_name_base + '.meta'

    try:
        data = webui.rest_client.receive_data(receiver)
        stdout = data['stdout']
        stderr = data['stderr']
        exit_status = data['exit_status']
    except RESTResultWaitTimeout as e:
        webui.logger.error('%s: %s, %s', e, user, request_id)
        stdout = ''
        stderr = 'Error: Wait Result Timeout'
        exit_status = 1

    create_result_files(user, stdout_file, meta_file, stdout, stderr,
                        exit_status)


def create_result_files(user, stdout_file, meta_file, stdout, stderr,
                        exit_status):
    with open(stdout_file, mode='w') as f:
        f.write(stdout)

    remove_empty_lines(stdout_file)

    num_lines = count_lines(stdout_file)

    meta_info = {'user': user, 'lines': num_lines, 'exit_status': exit_status,
                 'stderr': stderr}
    webui.logger.debug('meta info: %s', meta_info)
    with open(meta_file, mode='w') as f:
        json.dump(meta_info, f)


def remove_empty_lines(file):
    args = ['sed', '-i', '/^$/d', file]
    exec_command(args)


def count_lines(file):
    args = ['wc', '-l', file]
    res = exec_command(args)
    return int(res.stdout.split()[0])


def exec_command(args):
    cmd = ' '.join(args)
    error_message = 'Could not execute command: %s' % cmd
    webui.logger.debug('[command] excuting command: %s', cmd)
    try:
        res = subprocess.run(args,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE,
                             encoding='utf-8')
    except Exception as e:
        webui.logger.error('Error: %s', e)
        raise HayabusaError(error_message)
    webui.logger.debug('[command] %s - exit status: %s', cmd, res.returncode)
    if res.returncode != 0:
        webui.logger.error("Error: stderr: '%s', stdout: '%s'",
                           res.stderr, res.stdout)
        raise HayabusaError(error_message)
    return res
