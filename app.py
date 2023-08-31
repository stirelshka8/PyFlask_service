from flask import Flask, render_template, flash, redirect, request, url_for, session, g
from flask_login import login_required, current_user, LoginManager, login_user
from flask_principal import Principal, Permission, RoleNeed, PermissionDenied
from flask_paginate import Pagination, get_page_args
from db_manager import db, Articles, User, Comment
from forms import RegisterForm, ArticleForm
from passlib.hash import sha256_crypt
from flask_ckeditor import CKEditor
from flask_session import Session
from dotenv import load_dotenv
import datetime
import markdown
import redis
import os

dotenv_path = os.path.join(os.path.dirname(__file__), '.env')

if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)

admin_permission = Permission(RoleNeed("admin"))

app = Flask(__name__)
login_manager = LoginManager()
login_manager.init_app(app)
ckeditor = CKEditor(app)
principal = Principal(app)

app.secret_key = os.environ.get('SECRET')

if (os.environ.get('DB_TYPE')).lower() == 'sqlite':
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///myflaskblog.db'
elif (os.environ.get('DB_TYPE')).lower() == 'postgresql':
    pass
elif (os.environ.get('DB_TYPE')).lower() == 'mysql':
    pass
else:
    exit('Неверно указаны настройки базы данных!')

db.init_app(app)

# Настройки для подключения к Redis
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
# Инициализация расширения сессий
Session(app)

with app.app_context():
    db.create_all()


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, user_id)


@app.route('/')
def index():
    return render_template('home.html')


@app.route('/stirelshka8')
@login_required
def admin_panel():
    if current_user.has_role('admin'):
        return "Добро пожаловать в панель администратора!"
    else:
        flash('У вас нет прав доступа к этой странице.', 'danger')
        return redirect(url_for('index'))

@app.route('/about')
def about():
    return render_template('about.html')


@app.route('/articles')
def articles():
    page, per_page, offset = get_page_args(page_parameter='page',
                                           per_page_parameter='per_page')

    articles_list = Articles.query.order_by(Articles.date_created.desc()).paginate(page=page,
                                                                                   per_page=per_page,
                                                                                   error_out=False)

    # Преобразование Markdown-текста статьи в HTML
    for article in articles_list.items:
        article.body = markdown.markdown(article.body)

    total_articles = articles_list.total

    pagination = Pagination(page=page, per_page=per_page, total=articles_list.total,
                            css_framework='bootstrap4')

    return render_template('articles.html',
                           articles_list=articles_list,
                           total_articles=total_articles,
                           pagination=pagination)


@app.route('/article/<int:id>/')
@login_required
def display_article(id):
    article = db.session.get(Articles, id)
    title = article.title
    body = markdown.markdown(article.body)
    author = article.author.username
    date_created = article.date_created

    # Get comments and paginate them
    page = request.args.get('page', type=int, default=1)
    per_page = 10  # Number of comments per page
    comments = Comment.query.filter_by(article_id=id).order_by(Comment.date_created.desc()).paginate(page=page,
                                                                                                     per_page=per_page,
                                                                                                     error_out=False)

    if article:
        return render_template('article.html',
                               title=title,
                               body=body,
                               author=author,
                               date_created=date_created,
                               current_user=current_user.username,
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

        # Add the new user to the database
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

        user = User.query.filter_by(username=username).first()

        if user and sha256_crypt.verify(password_candidate, user.password):
            # Authentication successful
            session['logged_in'] = True
            session['username'] = username

            if user.has_role('admin'):
                session['is_admin'] = True
            else:
                session['is_admin'] = False

            login_user(user)  # Войти в систему пользователем с помощью Flask-Login
            flash('Вы успешно авторизовались', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Неверное имя пользователя или пароль', 'danger')
            return render_template('login.html')

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('Вы вышли из системы', 'success')
    return redirect(url_for('index'))


@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    per_page = 12  # Number of articles per page
    page = request.args.get('page', 1, type=int)

    if 'logged_in' in session:
        form = ArticleForm()

        if request.method == 'POST':
            title = request.form['title']
            body = request.form['body']
            author = User.query.filter_by(username=session['username']).first()

            new_article = Articles(title=title, body=body, author=author)
            db.session.add(new_article)
            db.session.commit()

        user = User.query.filter_by(username=session['username']).first()
        user_articles = (Articles.query.filter_by(author_id=user.id)
                         .order_by(Articles.date_created.desc()).paginate(page=page, per_page=per_page))

        total_articles = user_articles.total

        pagination = Pagination(page=page, per_page=per_page, total=total_articles, css_framework='bootstrap4')

        return render_template('dashboard.html', user=user, user_articles=user_articles,
                               total_articles=total_articles, pagination=pagination, form=form)
    else:
        flash('Вы не аутентифицированны!', 'danger')
        return redirect(url_for('login'))


@app.route('/add_comment/<int:id>/', methods=['POST'])
@login_required
def add_comment(id):
    article = Articles.query.get_or_404(id)
    body = request.form.get('body')

    if body:
        new_comment = Comment(body=body, author=current_user, article_id=article.id)
        db.session.add(new_comment)
        db.session.commit()
        flash('Комментарий добавлен.', 'success')
    else:
        flash('Пустой комментарий нельзя добавить.', 'danger')

    return redirect(url_for('display_article', id=id))


@app.route('/like_article/<int:id>/', methods=['POST'])
@login_required
def like_article(id):
    article = Articles.query.get_or_404(id)

    # Check if the user has already liked the article
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
