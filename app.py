from flask import Flask, render_template, flash, url_for
from flask_principal import Principal, Permission, RoleNeed
from routers.articles_routers import article_blueprint
from routers.admin_routers import admin_blueprint
from routers.user_routers import user_blueprint
from flask_login import LoginManager
from flask_ckeditor import CKEditor
from flask_migrate import Migrate
from flask_session import Session
from db_manager import db, User
from dotenv import load_dotenv
import datetime
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

# Registering routes ----------------------
app.register_blueprint(article_blueprint)
app.register_blueprint(admin_blueprint)
app.register_blueprint(user_blueprint)
# -----------------------------------------

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


@app.route('/')
def index():
    return render_template('home.html')


@app.route('/favicon.ico')
def favicon():
    return url_for('static', filename='image/favicon.ico')


@app.route('/about')
def about():
    return render_template('about.html')


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, user_id)


@login_manager.unauthorized_handler
def unauthorized():
    flash('Доступ разрешен только авторизованным!', 'danger')
    return render_template('home.html')


if __name__ == '__main__':
    app.run(debug=True, host="192.168.1.10")
