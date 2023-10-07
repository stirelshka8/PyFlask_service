from flask import Flask, render_template, flash, send_from_directory, redirect, url_for, request

from db_manager import db, User, get_user_by_username, add_contact, Message
from flask_principal import Principal, Permission, RoleNeed
from routers.articles_routers import article_blueprint
from flask_login import login_required, current_user
from routers.admin_routers import admin_blueprint
from routers.user_routers import user_blueprint
from flask_socketio import SocketIO, emit
from flask_login import LoginManager
from flask_ckeditor import CKEditor
from flask_migrate import Migrate
from flask_session import Session
from dotenv import load_dotenv
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
socketio = SocketIO(app)
login_manager = LoginManager()

# Registering routes ----------------------
app.register_blueprint(article_blueprint)
app.register_blueprint(admin_blueprint)
app.register_blueprint(user_blueprint)
# -----------------------------------------

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
    app.config['SESSION_KEY_PREFIX'] = os.environ.get('SESSION_KEY_PREFIX')
    app.config['SESSION_REDIS'] = redis.StrictRedis(
        host=os.environ.get('REDIS_HOST'),
        port=os.environ.get('REDIS_PORT'),
        db=os.environ.get('REDIS_DB'),
        password=os.environ.get('REDIS_PASS')
    )
    app.config['PERMANENT_SESSION_LIFETIME'] = int(os.environ.get('SESSION_LIFETIME'))
elif (os.environ.get('SESSION_TYPE')).lower() == 'file':
    app.config['SESSION_TYPE'] = 'filesystem'
else:
    exit('[SESSION ERROR] >> Неверно указаны настройки сессии!')

Session(app)


def get_unread_message_count(user):
    # Получите количество непрочитанных сообщений для данного пользователя
    try:
        unread_message_count = Message.query.filter_by(recipient_id=current_user.id, is_read=False).count()
    except AttributeError:
        unread_message_count = 0

    return unread_message_count


@app.route('/')
def index():
    return render_template('home.html')


@app.route('/favicon.ico')
def fav():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'image/fav.ico')


@app.route('/about')
def about():
    return render_template('about.html')


def count_message():
    if current_user.is_authenticated:  # Проверьте, аутентифицирован ли текущий пользователь
        unread_message_count = get_unread_message_count(current_user)  # Передайте текущего пользователя в функцию
    else:
        unread_message_count = 0  # Если пользователь не аутентифицирован, установите счетчик непрочитанных сообщений
        # в 0

    return {'get_unread_message_count': get_unread_message_count(current_user)}


@app.context_processor
def inject_data():
    return count_message()


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, user_id)


@login_manager.unauthorized_handler
def unauthorized():
    flash('Доступ разрешен только авторизованным!', 'danger')
    return render_template('login.html')


@app.route('/chat')
@login_required
def chat():
    return render_template('chat.html')


# Define a chat event handler
@socketio.on('message')
def handle_message(data):
    try:
        message = data['message']
        sender = current_user.username
        emit('message', {'message': message, 'sender': sender}, broadcast=True)
    except KeyError:
        pass


@app.route('/add_contact', methods=['GET', 'POST'])
@login_required
def add_contact_page():
    if request.method == 'POST':
        contact_username = request.form['contact_username']
        contact = get_user_by_username(contact_username)
        if contact:
            user = current_user
            add_contact(user, contact)
            flash(f'{contact_username} добавлен в адресную книгу', 'success')
        else:
            flash('Пользователь не найден', 'danger')
    return render_template('add_contact.html')




if __name__ == '__main__':
    app.run(debug=True, host="192.168.1.10")
    # app.run(debug=True)
