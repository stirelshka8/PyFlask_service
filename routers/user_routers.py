from flask import render_template, flash, redirect, request, url_for, session, Blueprint, jsonify
from forms import RegisterForm, ArticleForm, UpdateUserPass, UpdateUser
from db_manager import db, Articles, User, DeletedArticles, Role, get_user_messages, get_user_contacts, \
    get_user_by_username, Message, save_message, NewMessageNotification, add_contact
from flask_login import login_required, current_user, login_user
from flask_paginate import Pagination
from passlib.hash import sha256_crypt
from datetime import datetime
import secrets
import os

user_blueprint = Blueprint('user', __name__)


@user_blueprint.route('/logout')
@login_required
def logout():
    session.clear()
    flash('Вы вышли из системы', 'success')
    return redirect(url_for('index'))


@user_blueprint.route('/user/<string:username>')
@login_required
def user(username):
    users = User.query.filter_by(username=username).first()

    if users:
        author_articles = Articles.query.filter_by(author=users).all()
        total_author_articles = len(author_articles)
        total_author_likes = sum(article.likes for article in author_articles)

        if hasattr(users, 'registration_date'):
            registration_date = users.registration_date.strftime('%Y-%m-%d')
        else:
            registration_date = "Дата регистрации не найдена"

        total_rejected_articles = Articles.query.filter_by(author=users, status='отклонена').count()

        total_deleted_articles = DeletedArticles.query.filter_by(user=users).count()

        user_info = users.user_information

        return render_template('user.html', user=users, author_articles=author_articles,
                               total_author_articles=total_author_articles, total_author_likes=total_author_likes,
                               registration_date=registration_date, total_rejected_articles=total_rejected_articles,
                               total_deleted_articles=total_deleted_articles, user_info=user_info)

    else:
        flash('Пользователь не найден', 'danger')
        return redirect(url_for('moderate'))


@user_blueprint.route('/register', methods=['GET', 'POST'])
def register():
    if (os.environ.get('REGISTER_OFF')).lower() == 'false':
        form = RegisterForm(request.form)
        if request.method == 'POST' and form.validate():
            name = form.name.data
            email = form.email.data
            username = form.username.data
            password = sha256_crypt.hash(str(form.password.data))

            existing_user = User.query.filter_by(username=username).first()
            existing_email = User.query.filter_by(email=email).first()

            if existing_user:
                flash('Пользователь с таким именем уже существует.', 'danger')
                return redirect(url_for('user.register'))

            if existing_email:
                flash('Пользователь с таким email уже существует.', 'danger')
                return redirect(url_for('register'))

            new_user = User(name=name, email=email, username=username, password=password)

            user_role = Role.query.filter_by(name='USER').first()
            if user_role:
                new_user.roles.append(user_role)

            new_user.token = secrets.token_hex(16)

            db.session.add(new_user)
            db.session.commit()

            flash('Теперь вы зарегистрированы и можете войти. Добро пожаловать в BlogIt!!', 'success')

            return redirect(url_for('index'))

        return render_template('register.html', form=form)
    else:
        return render_template('register_off.html', img=f'/static/image/stop.png')


@user_blueprint.route('/login', methods=['GET', 'POST'])
def login():
    # TODO: Добавить функцию отключения входа для пользователей, кроме админов
    if request.method == 'POST':
        username = request.form['username']
        password_candidate = request.form['password']

        users = User.query.filter_by(username=username).first()

        if users and sha256_crypt.verify(password_candidate, users.password):
            session['logged_in'] = True
            session['username'] = username

            if users.has_role('super_admin'):
                session['is_super_admin'] = True
            elif users.has_role('admin'):
                session['is_admin'] = True
            elif users.has_role('moder'):
                session['is_moder'] = True
            else:
                session['is_super_admin'] = False
                session['is_admin'] = False
                session['is_moder'] = False
                session['is_user'] = True

            login_user(users)

            deleted_articles = DeletedArticles.query.filter_by(user=users, notified=False).all()

            if deleted_articles:
                flash(
                    f'Внимание! У вас были удалены статьи.'
                    f' Было удалено статей со статусом "отклонена" - {len(deleted_articles)}.',
                    'warning')

                for article in deleted_articles:
                    article.notified = True
                db.session.commit()
            else:
                flash('Вы успешно авторизовались', 'success')

            return redirect(url_for('user.dashboard'))
        else:
            flash('Неверное имя пользователя или пароль', 'danger')
            return render_template('login.html')

    return render_template('login.html')


@user_blueprint.route('/update_user_info', methods=['GET', 'POST'])
@login_required
def update_user_info():
    if request.method == 'POST':

        form = UpdateUser(request.form)

        if form.validate():
            current_user.name = form.name.data
            current_user.user_information = form.user_information.data

            db.session.commit()
            flash('Информация о пользователе успешно обновлена.', 'success')
        else:
            flash(f'Ошибка при обновлении информации о пользователе.', 'danger')

        return redirect(url_for('user.dashboard'))

    users = User.query.filter_by(username=session['username']).first()

    return render_template('edit_info.html', user=users)


@user_blueprint.route('/update_pass', methods=['GET', 'POST'])
@login_required
def update_pass():
    if request.method == 'POST':

        form = UpdateUserPass(request.form)

        if form.new_password.data and form.validate():
            current_user.password = sha256_crypt.hash(str(form.new_password.data))

            db.session.commit()
            flash('Пароль именён!.', 'success')
        else:
            flash('Ошибка смены пароля!.', 'danger')

        return redirect(url_for('user.dashboard'))

    users = User.query.filter_by(username=session['username']).first()

    return render_template('edit_pass.html', user=users)


@user_blueprint.route('/dashboard', methods=['GET', 'POST'])
@login_required
def dashboard():
    per_page = 12
    page = request.args.get('page', 1, type=int)

    form = ArticleForm()

    if request.method == 'POST' and form.validate():
        title = form.title.data
        body = form.body.data
        author = current_user
        status = 'ожидает модерации'

        new_article = Articles(title=title, body=body, author=author, status=status)
        db.session.add(new_article)
        db.session.commit()

        flash('Статья успешно добавлена и ожидает модерации.', 'success')
        return redirect(url_for('user.dashboard'))

    users = User.query.filter_by(username=session['username']).first()
    try:
        role = str(users.get_roles()[0]).upper()
    except IndexError:
        role = 'USER'

    user_articles = (Articles.query
                     .filter_by(author=current_user)
                     .order_by(Articles.date_created.desc())
                     .paginate(page=page, per_page=per_page))

    total_articles = user_articles.total

    pagination = Pagination(page=page, per_page=per_page, total=total_articles, css_framework='bootstrap4')

    return render_template('dashboard.html', user=users, role=role, user_articles=user_articles,
                           total_articles=total_articles, pagination=pagination, form=form)


@user_blueprint.route('/send_message', methods=['POST'])
@login_required
def send_message_route():
    recipient_username = request.json.get('recipient_username')
    message_text = request.json.get('message_text')

    recipient = get_user_by_username(recipient_username)

    if recipient:
        save_message(current_user, recipient, message_text)
        timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')

        # Создайте оповещение о новом сообщении
        new_notification = NewMessageNotification(user_id=recipient.id, sender_username=current_user.username)
        db.session.add(new_notification)
        db.session.commit()

        return jsonify({'timestamp': timestamp}), 201
    else:
        return jsonify({'error': 'Получатель не найден'}), 400


@user_blueprint.route('/messages')
@login_required
def messages():
    received_messages, sent_messages = get_user_messages(current_user)
    address_book = get_user_contacts(current_user)

    # Получите все оповещения о новых сообщениях для текущего пользователя
    new_notifications = NewMessageNotification.query.filter_by(user_id=current_user.id, is_read=False).all()

    # Помечайте все непрочитанные уведомления как прочитанные
    for notification in new_notifications:
        notification.is_read = True
        db.session.commit()

    # Получите список пользователей из адресной книги
    address_book_users = [contact.username for contact in address_book]

    return render_template('messages.html',
                           received_messages=received_messages,
                           sent_messages=sent_messages,
                           address_book=address_book,
                           new_notifications=new_notifications,
                           address_book_users=address_book_users)


@user_blueprint.route('/get_messages/<recipient_username>', methods=['GET'])
@login_required
def get_messages(recipient_username):
    recipient = get_user_by_username(recipient_username)
    if not recipient:
        return jsonify({'error': 'Пользователь не найден'}), 404

    # Извлеките все сообщения между текущим пользователем и получателем
    messages = Message.query.filter(
        ((Message.sender == recipient) & (Message.recipient == current_user)) |
        ((Message.sender == current_user) & (Message.recipient == recipient))
    ).order_by(Message.timestamp).all()

    # Пометьте все непрочитанные сообщения как прочитанные
    for message in messages:
        if not message.is_read and message.recipient == current_user:
            message.is_read = True
            db.session.commit()

    formatted_messages = [{'sender': message.sender.username,
                           'message_text': message.message_text,
                           'timestamp': message.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                           'is_read': message.is_read}
                          for message in messages]

    return jsonify({'messages': formatted_messages})


@user_blueprint.route('/mark_as_read/<notification_id>', methods=['POST'])
@login_required
def mark_as_read(notification_id):
    notification = NewMessageNotification.query.get(notification_id)

    if notification and notification.user_id == current_user.id:
        notification.is_read = True
        db.session.commit()

        return jsonify({'success': True}), 200
    else:
        return jsonify({'error': 'Уведомление не найдено'}), 404


@user_blueprint.route('/add_to_address_book', methods=['POST'])
@login_required
def add_to_address_book():
    if request.method == 'POST':
        username = request.json.get('username')
        user_to_add = User.query.filter_by(username=username).first()

        if user_to_add:
            if user_to_add != current_user:  # Проверьте, что пользователь не пытается добавить себя в контакты
                add_contact(current_user, user_to_add)
                flash(f'Пользователь {username} добавлен в адресную книгу.', 'success')
            else:
                flash('Вы не можете добавить себя в адресную книгу.', 'danger')
        else:
            flash('Пользователь не найден.', 'danger')

        return jsonify({'success': True}), 200

    return render_template('add_contact.html')


@user_blueprint.route('/ignore_notification/<notification_id>', methods=['POST'])
@login_required
def ignore_notification(notification_id):
    notification = NewMessageNotification.query.get(notification_id)

    if notification and notification.user_id == current_user.id:
        db.session.delete(notification)
        db.session.commit()

        return jsonify({'success': True}), 200
    else:
        return jsonify({'error': 'Уведомление не найдено'}), 404


@user_blueprint.route('/read_message/<recipient_username>', methods=['GET'])
@login_required
def read_message(recipient_username):
    recipient = get_user_by_username(recipient_username)
    if not recipient:
        return jsonify({'error': 'Пользователь не найден'}), 404

    messages = Message.query.filter(
        (Message.sender == recipient and Message.recipient == current_user) &
        (Message.is_read == False)  # Учитывайте только непрочитанные сообщения
    ).all()

    for message in messages:
        message.is_read = True  # Установите статус сообщения как прочитанное
        db.session.commit()

    return jsonify({'success': True}), 200


