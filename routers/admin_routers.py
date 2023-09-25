from flask import render_template, flash, redirect, request, url_for, Blueprint
from flask_login import login_required, current_user
from db_manager import db, Articles, DeletedArticles
from flask_paginate import Pagination
from forms import ArticleForm

admin_blueprint = Blueprint('admin', __name__)


@admin_blueprint.route('/moderate', methods=['GET', 'POST'])
@login_required
def moderate():

    if current_user.has_role('moder') or current_user.has_role('admin'):
        per_page = 12
        page = request.args.get('page', 1, type=int)

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
