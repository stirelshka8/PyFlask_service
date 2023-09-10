from flask import Flask, render_template, flash, redirect, request, url_for, session
from flask_login import login_required, current_user, LoginManager, login_user
from forms import RegisterForm, ArticleForm, UpdateUserInfoForm, CommentForm
from db_manager import db, Articles, User, Comment, DeletedArticles
from flask_principal import Principal, Permission, RoleNeed
from flask_paginate import Pagination, get_page_args
from passlib.hash import sha256_crypt
from flask_ckeditor import CKEditor
from flask_migrate import Migrate
from flask_session import Session
from sqlalchemy import desc, func
from dotenv import load_dotenv
import datetime
import markdown
import redis
import os

dotenv_path = os.path.join(os.path.dirname(__file__), '.env')

if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)
else:
    exit('[STOP SYSTEM STARTUP] >> Не обнаружен файл переменных окружения ".env". \n'
         'Файл должен располагаться на одном уровне с "app.py".')

admin_permission = Permission(RoleNeed("admin"))

app = Flask(__name__)
login_manager = LoginManager()
login_manager.init_app(app)
ckeditor = CKEditor(app)
principal = Principal(app)
migrate = Migrate(app, db)

app.secret_key = os.environ.get('SECRET')

if (os.environ.get('DB_TYPE')).lower() == 'sqlite':
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///myflaskblog.db'
elif (os.environ.get('DB_TYPE')).lower() == 'postgresql':
    pass
elif (os.environ.get('DB_TYPE')).lower() == 'mysql':
    pass
else:
    exit('[DB ERROR] >> Неверно указаны настройки базы данных!')

db.init_app(app)

if (os.environ.get('SESSION_TYPE')).lower() == 'redis':
    app.config['SESSION_TYPE'] = 'redis'
    app.config['SESSION_PERMANENT'] = True
    app.config['SESSION_USE_SIGNER'] = True
    app.config['SESSION_KEY_PREFIX'] = 'flpy_'
    app.config['SESSION_REDIS'] = redis.StrictRedis(
        host=os.environ.get('REDIS_HOST'),
        port=os.environ.get('REDIS_PORT'),
        db=os.environ.get('REDIS_DB'),
        password=os.environ.get('REDIS_PASS')
    )
    app.config['PERMANENT_SESSION_LIFETIME'] = datetime.timedelta(hours=1)
elif (os.environ.get('SESSION_TYPE')).lower() == 'file':
    app.config['SESSION_TYPE'] = 'filesystem'
else:
    exit('[SESSION ERROR] >> Неверно указаны настройки сессии!')

Session(app)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, user_id)


@login_manager.unauthorized_handler
def unauthorized():
    flash('Доступ разрешен только авторизованным!', 'danger')
    return render_template('home.html')


@app.route('/')
def index():
    return render_template('home.html')


@app.route('/favicon.ico')
def favicon():
    return url_for('static', filename='image/favicon.ico')


@app.route('/about')
def about():
    return render_template('about.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('Вы вышли из системы', 'success')
    return redirect(url_for('index'))


@app.route('/moderate', methods=['GET', 'POST'])
@login_required
def moderate():
    if current_user.has_role('admin'):
        per_page = 12
        page = request.args.get('page', 1, type=int)

        if 'logged_in' in session:
            form = ArticleForm()

            if request.method == 'POST':
                article_id = request.form.get('article_id')
                new_status = request.form.get('new_status')

                article = Articles.query.get(article_id)
                if article:
                    article.status = new_status

                    if new_status == 'отклонена':
                        rejection_comment = request.form.get('rejection_comment')
                        article.rejection_comment = rejection_comment

                        deleted_article = DeletedArticles(user=article.author, article=article)
                        db.session.add(deleted_article)

                    db.session.commit()
                    flash(f'Статус статьи с ID {article_id} обновлен на "{new_status}".', 'success')
                else:
                    flash(f'Статья с ID {article_id} не найдена.', 'danger')

            user_articles = (Articles.query
                             .filter_by(status='ожидает модерации')
                             .order_by(Articles.date_created.desc())
                             .paginate(page=page, per_page=per_page))

            total_articles = user_articles.total

            pagination = Pagination(page=page, per_page=per_page, total=total_articles, css_framework='bootstrap4')

            return render_template('moderate.html', user=current_user, user_articles=user_articles,
                                   total_articles=total_articles, pagination=pagination, form=form)
        else:
            flash('У вас нет прав доступа к этой странице.', 'danger')
            return redirect(url_for('index'))


@app.route('/user/<string:username>')
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


@app.route('/delete_rejected_articles', methods=['POST'])
@login_required
def delete_rejected_articles():
    if current_user.has_role('admin'):
        count_deleted_articles = Articles.query.filter_by(status='отклонена').delete()

        if count_deleted_articles > 0:
            db.session.commit()
            flash(f'Успешно удалено {count_deleted_articles} статей со статусом "отклонена".', 'success')
        else:
            flash('Нет статей со статусом "отклонена" для удаления.', 'info')

        return redirect(url_for('moderate'))
    else:
        flash('У вас нет прав доступа к этой странице.', 'danger')
        return redirect(url_for('index'))


@app.route('/articles')
def articles():
    page, per_page, offset = get_page_args(page_parameter='page',
                                           per_page_parameter='per_page')

    articles_list = (Articles.query
                     .filter(Articles.status == 'опубликована')
                     .order_by(Articles.date_created.desc())
                     .paginate(page=page, per_page=per_page, error_out=False))

    top_likes_articles = Articles.query.order_by(desc(Articles.likes)).limit(1).all()
    top_comments_articles = (
        db.session.query(Articles, func.count(Comment.id).label('comment_count'))
        .outerjoin(Comment)
        .group_by(Articles.id)
        .order_by(desc('comment_count'))
        .limit(1)
        .all()
    )

    total_comments_dict = {}

    for article in articles_list.items:
        total_comments = Comment.query.filter_by(article_id=article.id).count()
        total_comments_dict[article.id] = total_comments

    total_articles = articles_list.total

    pagination = Pagination(page=page, per_page=per_page, total=articles_list.total,
                            css_framework='bootstrap4')

    return render_template('articles.html',
                           articles_list=articles_list,
                           total_articles=total_articles,
                           total_comments_dict=total_comments_dict,
                           pagination=pagination,
                           top_likes_articles=top_likes_articles,
                           top_comments_articles=top_comments_articles)


@app.route('/article/<int:id>/')
@login_required
def display_article(id):
    article = db.session.get(Articles, id)
    title = article.title
    body = markdown.markdown(article.body)
    author = article.author.username
    date_created = article.date_created

    page = request.args.get('page', type=int, default=1)
    per_page = 10
    comments = Comment.query.filter_by(article_id=id).order_by(Comment.date_created.desc()).paginate(page=page,
                                                                                                     per_page=per_page,
                                                                                                     error_out=False)
    admins = session['is_admin']

    if article:
        return render_template('article.html',
                               title=title,
                               body=body,
                               author=author,
                               date_created=date_created,
                               current_user=current_user,
                               admins=admins,
                               article=article,
                               comments=comments.items,
                               pagination=comments,
                               form=ArticleForm())  # Add this line
    else:
        flash('Статья не найдена', 'danger')
        return redirect(url_for('articles'))


@app.route('/edit_article/<int:id>/', methods=['GET', 'POST'])
@login_required
def edit_article(id):
    article = Articles.query.get_or_404(id)
    if current_user != article.author:
        flash('Вы не имеете права редактировать эту статью.', 'danger')
        return redirect(url_for('dashboard'))

    form = ArticleForm(obj=article)

    if request.method == 'POST':
        article.title = request.form['title']
        article.body = request.form['body']
        db.session.commit()
        flash('Статья успешно отредактирована.', 'success')
        return redirect(url_for('dashboard'))

    return render_template('edit_article.html', form=form, article=article)


@app.route('/delete_article/<int:id>/', methods=['POST'])
@login_required
def delete_article(id):
    article = Articles.query.get_or_404(id)
    if current_user != article.author:
        flash('Вы не имеете права удалять эту статью.', 'danger')
    else:
        deleted_article = DeletedArticles(user=current_user, article=article)
        db.session.add(deleted_article)

        Comment.query.filter_by(article_id=id).delete()
        db.session.delete(article)
        db.session.commit()
        flash('Статья успешно удалена.', 'success')

    return redirect(url_for('dashboard'))


@app.route('/register', methods=['GET', 'POST'])
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


@app.route('/login', methods=['GET', 'POST'])
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

            return redirect(url_for('dashboard'))
        else:
            flash('Неверное имя пользователя или пароль', 'danger')
            return render_template('login.html')

    return render_template('login.html')


@app.route('/update_user_info', methods=['POST'])
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


@app.route('/dashboard', methods=['GET', 'POST'])
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


@app.route('/add_comment/<int:id>', methods=['GET', 'POST'])
@login_required
def add_comment(id):
    form = CommentForm()

    if form.validate_on_submit():
        body = form.body.data
        article_id = form.article_id.data

        comment = Comment(body=body, author=current_user, article_id=article_id)  # Передайте идентификатор статьи
        db.session.add(comment)
        db.session.commit()

        flash('Комментарий добавлен', 'success')
        return redirect(url_for('display_article', id=id))

    return render_template('add_comment.html', form=form)


@app.route('/delete_comment/<int:comment_id>', methods=['POST'])
@login_required
def delete_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    article = Articles.query.get_or_404(comment.article_id)
    author = article.author

    print(session['is_admin'])

    if current_user.id == comment.author_id and current_user.id == author.id and not session['is_admin']:
        flash('У Вас нет доступа для удаления данного комментария!', 'danger')
    else:
        db.session.delete(comment)
        db.session.commit()
        flash('Комментарий удален', 'success')

    return redirect(url_for('display_article', id=comment.article_id))


@app.route('/like_article/<int:id>/', methods=['POST'])
@login_required
def like_article(id):
    article = Articles.query.get_or_404(id)

    if current_user in article.likes_users:
        article.likes -= 1
        article.likes_users.remove(current_user)
        flash('Пометка удалена.', 'info')
    else:
        article.likes += 1
        article.likes_users.append(current_user)
        flash('Статья помечена как понравившаяся.', 'success')

    db.session.commit()

    return redirect(url_for('display_article', id=id))


if __name__ == '__main__':
    app.run(debug=True)
