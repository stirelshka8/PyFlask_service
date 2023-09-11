from flask import render_template, flash, redirect, request, url_for, session, Blueprint
from db_manager import db, Articles, Comment, DeletedArticles
from flask_login import login_required, current_user
from flask_paginate import Pagination, get_page_args
from forms import ArticleForm, CommentForm
from sqlalchemy import desc, func
import markdown

article_blueprint = Blueprint('article', __name__)


@article_blueprint.route('/delete_article/<int:id>/', methods=['POST'])
@login_required
def delete_article(id):
    article = Articles.query.get_or_404(id)
    if current_user != article.author:
        flash('Вы не имеете права удалять эту статью.', 'danger')
    else:
        deleted_article = DeletedArticles(user=current_user, article=article)
        db.session.add(deleted_article)

        Comment.query.filter_by(article_id=id).delete()
        db.session.delete(article)
        db.session.commit()
        flash('Статья успешно удалена.', 'success')

    return redirect(url_for('user.dashboard'))


@article_blueprint.route('/edit_article/<int:id>/', methods=['GET', 'POST'])
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


@article_blueprint.route('/article/<int:id>/')
@login_required
def display_article(id):
    article = db.session.get(Articles, id)
    title = article.title
    body = markdown.markdown(article.body)
    author = article.author.username
    date_created = article.date_created

    page = request.args.get('page', type=int, default=1)
    per_page = 10
    comments = Comment.query.filter_by(article_id=id).order_by(Comment.date_created.desc()).paginate(page=page,
                                                                                                     per_page=per_page,
                                                                                                     error_out=False)
    admins = session['is_admin']

    if article:
        return render_template('article.html',
                               title=title,
                               body=body,
                               author=author,
                               date_created=date_created,
                               current_user=current_user,
                               admins=admins,
                               article=article,
                               comments=comments.items,
                               pagination=comments,
                               form=ArticleForm())  # Add this line
    else:
        flash('Статья не найдена', 'danger')
        return redirect(url_for('articles'))


@article_blueprint.route('/articles')
def articles():
    page, per_page, offset = get_page_args(page_parameter='page',
                                           per_page_parameter='per_page')

    articles_list = (Articles.query
                     .filter(Articles.status == 'опубликована')
                     .order_by(Articles.date_created.desc())
                     .paginate(page=page, per_page=per_page, error_out=False))

    top_likes_articles = Articles.query.order_by(desc(Articles.likes)).limit(1).all()
    top_comments_articles = (
        db.session.query(Articles, func.count(Comment.id).label('comment_count'))
        .outerjoin(Comment)
        .group_by(Articles.id)
        .order_by(desc('comment_count'))
        .limit(1)
        .all()
    )

    total_comments_dict = {}

    for article in articles_list.items:
        total_comments = Comment.query.filter_by(article_id=article.id).count()
        total_comments_dict[article.id] = total_comments

    total_articles = articles_list.total

    pagination = Pagination(page=page, per_page=per_page, total=articles_list.total,
                            css_framework='bootstrap4')

    return render_template('articles.html',
                           articles_list=articles_list,
                           total_articles=total_articles,
                           total_comments_dict=total_comments_dict,
                           pagination=pagination,
                           top_likes_articles=top_likes_articles,
                           top_comments_articles=top_comments_articles)


@article_blueprint.route('/delete_rejected_articles', methods=['POST'])
@login_required
def delete_rejected_articles():
    if current_user.has_role('admin'):
        count_deleted_articles = Articles.query.filter_by(status='отклонена').delete()

        if count_deleted_articles > 0:
            db.session.commit()
            flash(f'Успешно удалено {count_deleted_articles} статей со статусом "отклонена".', 'success')
        else:
            flash('Нет статей со статусом "отклонена" для удаления.', 'info')

        return redirect(url_for('admin.moderate'))
    else:
        flash('У вас нет прав доступа к этой странице.', 'danger')
        return redirect(url_for('index'))


@article_blueprint.route('/add_comment/<int:id>', methods=['GET', 'POST'])
@login_required
def add_comment(id):
    form = CommentForm()

    if form.validate_on_submit():
        body = form.body.data
        article_id = form.article_id.data

        comment = Comment(body=body, author=current_user, article_id=article_id)  # Передайте идентификатор статьи
        db.session.add(comment)
        db.session.commit()

        flash('Комментарий добавлен', 'success')
        return redirect(url_for('article.display_article', id=id))

    return render_template('add_comment.html', form=form)


@article_blueprint.route('/delete_comment/<int:comment_id>', methods=['POST'])
@login_required
def delete_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    article = Articles.query.get_or_404(comment.article_id)
    author = article.author

    if current_user.id == comment.author_id and current_user.id == author.id and not session['is_admin']:
        flash('У Вас нет доступа для удаления данного комментария!', 'danger')
    else:
        db.session.delete(comment)
        db.session.commit()
        flash('Комментарий удален', 'success')

    return redirect(url_for('article.display_article', id=comment.article_id))


@article_blueprint.route('/like_article/<int:id>/', methods=['POST'])
@login_required
def like_article(id):
    article = Articles.query.get_or_404(id)

    if current_user in article.likes_users:
        article.likes -= 1
        article.likes_users.remove(current_user)
        flash('Пометка удалена.', 'info')
    else:
        article.likes += 1
        article.likes_users.append(current_user)
        flash('Статья помечена как понравившаяся.', 'success')

    db.session.commit()

    return redirect(url_for('article.display_article', id=id))
