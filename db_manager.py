from flask_sqlalchemy import SQLAlchemy
from passlib.hash import sha256_crypt
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    email = db.Column(db.String(100), unique=True)
    username = db.Column(db.String(30), unique=True)
    password = db.Column(db.String(100))
    token = db.Column(db.String(100))
    user_information = db.Column(db.String(300))
    articles = db.relationship('Articles', backref='author')
    roles = db.relationship('Role', secondary='user_roles')
    registration_date = db.Column(db.DateTime, default=datetime.utcnow)

    def is_active(self):
        return True

    def has_role(self, role_name):
        related_roles = self.roles
        return any(role.name == role_name for role in related_roles)


class Role(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True)
    description = db.Column(db.String(255))


class UserRoles(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'))
    role_id = db.Column(db.Integer, db.ForeignKey('role.id', ondelete='CASCADE'))


class Articles(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255))
    body = db.Column(db.Text)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'))  # Reference to the User table
    date_created = db.Column(db.DateTime, default=db.func.current_timestamp())
    likes = db.Column(db.Integer, default=0)
    status = db.Column(db.String(50), default='ожидает модерации')
    likes_users = db.relationship('User', secondary='article_likes', back_populates='liked_articles')
    comments = db.relationship('Comment', backref='article', lazy='dynamic')

    @property
    def comments_count(self):
        return self.comments.count()


class ArticleLikes(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'))
    article_id = db.Column(db.Integer, db.ForeignKey('articles.id', ondelete='CASCADE'))


class DeletedArticles(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    article_id = db.Column(db.Integer, db.ForeignKey('articles.id'), nullable=False)
    article = db.relationship('Articles', foreign_keys=[article_id])
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User', foreign_keys=[user_id])
    deleted_at = db.Column(db.DateTime, default=datetime.utcnow)
    notified = db.Column(db.Boolean, default=False)


User.liked_articles = db.relationship('Articles', secondary='article_likes', back_populates='likes_users')


class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.Text, nullable=False)
    date_created = db.Column(db.DateTime, default=datetime.utcnow)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    article_id = db.Column(db.Integer, db.ForeignKey('articles.id'), nullable=False)
    author = db.relationship('User', backref='comments')


def create_user(name, email, username, password):
    hashed_password = sha256_crypt.hash(password)
    new_user = User(name=name, email=email, username=username, password=hashed_password)
    db.session.add(new_user)
    db.session.commit()


def get_user_by_username(username):
    return User.query.filter_by(username=username).first()
