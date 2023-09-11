from flask import render_template, flash, redirect, request, url_for, session, Blueprint
from flask_login import login_required, current_user, login_user
from forms import RegisterForm, ArticleForm, UpdateUserInfoForm
from db_manager import db, Articles, User, DeletedArticles
from flask_paginate import Pagination
from passlib.hash import sha256_crypt

user_blueprint = Blueprint('user', __name__)


@user_blueprint.route('/logout')
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

        return render_template('user.html', user=users, author_articles=author_articles,
                               total_author_articles=total_author_articles, total_author_likes=total_author_likes,
                               registration_date=registration_date, total_rejected_articles=total_rejected_articles,
                               total_deleted_articles=total_deleted_articles)

    else:
        flash('Пользователь не найден', 'danger')
        return redirect(url_for('moderate'))


@user_blueprint.route('/register', methods=['GET', 'POST'])
def register():
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
            return redirect(url_for('register'))

        if existing_email:
            flash('Пользователь с таким email уже существует.', 'danger')
            return redirect(url_for('register'))

        new_user = User(name=name, email=email, username=username, password=password)

        db.session.add(new_user)
        db.session.commit()

        flash('Теперь вы зарегистрированы и можете войти. Добро пожаловать в BlogIt!!', 'success')

        return redirect(url_for('index'))

    return render_template('register.html', form=form)


@user_blueprint.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password_candidate = request.form['password']

        users = User.query.filter_by(username=username).first()

        if users and sha256_crypt.verify(password_candidate, users.password):
            session['logged_in'] = True
            session['username'] = username

            if users.has_role('admin'):
                session['is_admin'] = True
            else:
                session['is_admin'] = False

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


@user_blueprint.route('/update_user_info', methods=['POST'])
@login_required
def update_user_info():
    form = UpdateUserInfoForm(request.form)
    if form.validate():
        current_user.name = form.name.data
        if form.new_password.data:
            current_user.password = sha256_crypt.hash(str(form.new_password.data))

        db.session.commit()
        flash('Информация о пользователе успешно обновлена.', 'success')
    else:
        flash('Ошибка при обновлении информации о пользователе.', 'danger')
    return redirect(url_for('dashboard'))


@user_blueprint.route('/dashboard', methods=['GET', 'POST'])
@login_required
def dashboard():
    per_page = 12
    page = request.args.get('page', 1, type=int)

    if 'logged_in' in session:

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
            return redirect(url_for('dashboard'))

        users = User.query.filter_by(username=session['username']).first()

        user_articles = (Articles.query
                         .filter_by(author=current_user)
                         .order_by(Articles.date_created.desc())
                         .paginate(page=page, per_page=per_page))

        total_articles = user_articles.total

        pagination = Pagination(page=page, per_page=per_page, total=total_articles, css_framework='bootstrap4')

        return render_template('dashboard.html', user=users, user_articles=user_articles,
                               total_articles=total_articles, pagination=pagination, form=form)
    else:
        flash('Вы не аутентифицированны!', 'danger')
        return redirect(url_for('login'))
