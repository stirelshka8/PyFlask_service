from flask import Flask, render_template, flash, redirect, request, url_for, session
from flask_login import LoginManager, login_required
from flask_paginate import Pagination, get_page_args
from forms import RegisterForm, ArticleForm
from db_manager import db, Articles, User
from passlib.hash import sha256_crypt
from flask_ckeditor import CKEditor

app = Flask(__name__)
login_manager = LoginManager()
login_manager.init_app(app)
ckeditor = CKEditor(app)


app.secret_key = 'Secret145'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///myflaskblog.db'
db.init_app(app)

with app.app_context():
    db.create_all()


@login_manager.user_loader
def load_user(user_id):
    return db.session.query(User).get(user_id)



@login_manager.unauthorized_handler
def unauthorized():
    flash('Доступ разрешен только авторизованным!', 'danger')
    return redirect(url_for('login'))


@app.route('/')
def index():
    return render_template('home.html')


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

    pagination = Pagination(page=page, per_page=per_page, total=articles_list.total,
                            css_framework='bootstrap4')

    return render_template('articles.html', articles_list=articles_list, pagination=pagination)


#TODO Исправить ошибку при который авторизированный пользователь не может получить доступ
@app.route('/article/<int:id>/')
@login_required
def display_article(id):
    print(session)
    article = Articles.query.get(id)
    if article:
        return render_template('article.html', article=article)
    else:
        flash('Статья не найдена', 'danger')
        return redirect(url_for('articles'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm(request.form)
    if request.method == 'POST' and form.validate():
        name = form.name.data
        email = form.email.data
        username = form.username.data
        password = sha256_crypt.hash(str(form.password.data))

        # Check if a user with the same username or email already exists
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
            print(session)
            session['logged_in'] = True
            session['username'] = username
            print(session)
            app.logger.debug('Authentication successful')  # Добавьте логирование
            flash('Вы успешно авторизовались', 'success')
            return redirect(url_for('dashboard'))
        else:
            app.logger.debug('Authentication failed')  # Добавьте логирование
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
        user_articles = (Articles.query.filter_by(author=user)
                         .order_by(Articles.date_created.desc()).paginate(page=page, per_page=per_page))

        pagination = Pagination(page=page, per_page=per_page, total=user_articles.total, css_framework='bootstrap4')

        return render_template('dashboard.html', user=user, user_articles=user_articles, pagination=pagination,
                               form=form)
    else:
        flash('Вы не аутентифицированны!', 'danger')
        return redirect(url_for('login'))


if __name__ == '__main__':
    app.run(debug=True)
