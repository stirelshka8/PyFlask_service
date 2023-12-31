from wtforms import Form, StringField, PasswordField, validators, TextAreaField, HiddenField, SubmitField
from wtforms.validators import DataRequired
from flask_wtf import FlaskForm


class RegisterForm(Form):
    name = StringField('Имя', [
        validators.Length(min=2, max=40, message='Имя должно быть от 2 до 40 символов')])
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


class UpdateUser(Form):
    name = StringField('Имя', [validators.Length(min=1, max=255)])
    user_information = StringField('Дополнительная информация', [validators.Length(min=1, max=300)])


class UpdateUserPass(Form):
    new_password = PasswordField('Новый пароль', [validators.Length(min=6, max=255)])
    confirm_password = PasswordField('Подтвердите новый пароль',
                                     [validators.EqualTo('new_password', message='Passwords must match')])


class ArticleForm(FlaskForm):
    title = StringField('title', validators=[DataRequired()])
    body = TextAreaField('body', validators=[DataRequired()])


class CommentForm(FlaskForm):
    body = TextAreaField('Комментарий', validators=[DataRequired()])
    article_id = HiddenField()
    submit = SubmitField('Добавить комментарий')
