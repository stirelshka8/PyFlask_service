from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from passlib.hash import sha256_crypt

db = SQLAlchemy()


class User(db.Model, UserMixin):  # Обновленная модель User с UserMixin
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    email = db.Column(db.String(100), unique=True)
    username = db.Column(db.String(30), unique=True)
    password = db.Column(db.String(100))
    articles = db.relationship('Articles', backref='author')  # Establish the relationship

    def is_active(self):
        return True  # Здесь вы можете реализовать логику проверки активности пользователя


class Articles(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255))
    body = db.Column(db.Text)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'))  # Reference to the User table
    date_created = db.Column(db.DateTime, default=db.func.current_timestamp())


def create_user(name, email, username, password):
    hashed_password = sha256_crypt.hash(password)
    new_user = User(name=name, email=email, username=username, password=hashed_password)
    db.session.add(new_user)
    db.session.commit()


def get_user_by_username(username):
    return User.query.filter_by(username=username).first()
