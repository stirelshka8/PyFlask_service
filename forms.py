from wtforms import Form, StringField, PasswordField, validators, TextAreaField
from wtforms.validators import DataRequired
from flask_wtf import FlaskForm


class RegisterForm(Form):
    name = StringField('Имя', [
        validators.Length(min=5, max=40, message='Имя должно быть от 5 до 40 символов')])
    username = StringField('Имя пользователя', [
        validators.Length(min=7, max=30, message='Имя пользователя должно быть от 7 до 30 символов')])
    email = StringField('Email', [
        validators.Length(min=7, max=35),
        validators.Email(message='Некорректный адрес электронной почты')])
    password = PasswordField('Пароль', [
        validators.DataRequired(),
        validators.Length(min=7, max=20),
        validators.EqualTo('confirm', message='Пароли не совпадают')])
    confirm = PasswordField('Подтверждение пароля')


class ArticleForm(FlaskForm):
    title = StringField('title', validators=[DataRequired()])
    body = TextAreaField('body', validators=[DataRequired()])

