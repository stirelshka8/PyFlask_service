from wtforms import Form, StringField, PasswordField, validators


class RegisterForm(Form):
    name = StringField('Имя', [validators.Length(min=5, max=40)])
    username = StringField('Имя пользователя', [validators.Length(min=7, max=30)])
    email = StringField('Email', [validators.Length(min=7, max=35)])
    password = PasswordField('Пароль', [
        validators.DataRequired(),
        validators.EqualTo('confirm', message='Пароли не совпадают')
    ])
    confirm = PasswordField('Подтверждение пароля')
