# general python imports
import datetime
import os
import re
import urllib
from flask import (Flask, redirect, render_template,
                   request, Response, url_for)
from flask.ext.script import Manager
from flask.ext.basicauth import BasicAuth
from flask.ext.bootstrap import Bootstrap
import markdown2
from flask.ext.sqlalchemy import SQLAlchemy, BaseQuery
from flask.ext.migrate import Migrate, MigrateCommand
from sqlalchemy_searchable import SearchQueryMixin
from sqlalchemy_utils.types import TSVectorType
from sqlalchemy_searchable import make_searchable
from sqlalchemy import desc
from flask.ext.wtf import Form
from wtforms import StringField, SubmitField
from wtforms.validators import Required, Length
from flask.ext.pagedown import PageDown
from flask.ext.pagedown.fields import PageDownField

# Config and a bit of intitialization

app = Flask(__name__)
app.config.from_envvar('FTZM_CFG')
pagedown = PageDown(app)
bootstrap = Bootstrap(app)
basic_auth = BasicAuth(app)
basedir = os.path.abspath(os.path.dirname(__file__))
db = SQLAlchemy(app)
migrate = Migrate(app, db)
manager = Manager(app)
manager.add_command('db', MigrateCommand)
make_searchable()


class ArticleQuery(BaseQuery, SearchQueryMixin):
    pass


class Article(db.Model):
    query_class = ArticleQuery
    __tablename__ = 'article'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.Unicode(255))
    abstract = db.Column(db.Text)
    slug = db.Column(db.Unicode(255), unique=True)
    content = db.Column(db.UnicodeText)  # are these text things right
    content_html = db.Column(db.Text)
    timestamp = db.Column(db.DateTime)
    search_vector = db.Column(TSVectorType('title', 'content', 'abstract'))

    @staticmethod
    def on_changed_content(target, value, oldvalue, initiator):
        target.content_html = markdown2.markdown(value,
                                                 extras=["fenced-code-blocks"])

    @staticmethod
    def on_changed_title(target, value, oldvalue, initiator):
        target.slug = re.sub('[^\w]+', '-', value.lower())

    def __init__(self, **kwargs):
        super(Article, self).__init__(**kwargs)
        self.timestamp = datetime.datetime.now()

db.configure_mappers()
db.Model.metadata.create_all(db.session.connection())
# calls this on change
db.event.listen(Article.content, 'set', Article.on_changed_content)
# calls this on change
db.event.listen(Article.title, 'set', Article.on_changed_title)

# If the database is totally empty it doesn;t run for some reason.
# load in python shell, run the first two db commands above, then create an
# article object, add+commit and the app will run as normal. maybe put the
# creation of a
# dummy in here to help that: it could be deleted later and save headaches.
# at any rate, troubleshoot it.


# Initialization code


@app.template_filter('clean_querystring')
def clean_querystring(request_args, *keys_to_remove, **new_values):
    querystring = dict((key, value) for key, value in request_args.items())
    for key in keys_to_remove:
        querystring.pop(key, None)
    querystring.update(new_values)
    return urllib.urlencode(querystring)


@app.errorhandler(404)
def not_found(exc):
    return Response('<h3>Not Found</h3>'), 404


class CreateForm(Form):
    title = StringField('Title', validators=[Length(1, 255)])
    abstract = PageDownField('Abstract', validators=[Required()])
    content = PageDownField("Body", validators=[Required()])
    submit = SubmitField('Publish Article')


class DeleteForm(Form):
    submit = SubmitField('Delete Article')


@app.route('/', methods=["GET", "POST"])
def index():
    year = datetime.date.today().year
    search = request.form.get('search')
    order = request.form.get('order')
    if order == "asc":
        query_order = Article.timestamp
    else:
        query_order = desc(Article.timestamp)
    if not search:
        query = Article.query.order_by(query_order).all()
    else:
        query = Article.query.search(search).order_by(query_order).all()
        # add order by timestamp
    return render_template('index.html', query=query, order=order,
                           search=search, year=year)


@app.route('/<slug>')
def article(slug):
    article = Article.query.filter_by(slug=slug).first_or_404()
    return render_template('article.html', article=article)


@app.route('/create', methods=['GET', 'POST'])
@basic_auth.required
def create():
    form = CreateForm()
    if form.validate_on_submit():
        article = Article(title=form.title.data, abstract=form.abstract.data,
                          content=form.content.data)
        db.session.add(article)
        return redirect(url_for('index'))
    return render_template('create.html', form=form)


@app.route('/edit/<slug>', methods=['GET', 'POST'])
@basic_auth.required
def edit(slug):
    article = Article.query.filter_by(slug=slug).first_or_404()
    form = CreateForm()
    delete_form = DeleteForm()
    if form.validate_on_submit():
        article.content = form.content.data
        article.title = form.title.data
        article.abstract = form.abstract.data
        db.session.add(article)
        return redirect(url_for('article', slug=article.slug))
    if delete_form.validate_on_submit():
        db.session.delete(article)
        return redirect(url_for('index'))
    form.title.data = article.title
    form.abstract.data = article.abstract
    form.content.data = article.content
    return render_template('edit.html', form=form, delete_form=delete_form)


@app.route('/portfolio')
def portfolio():
    return render_template('portfolio.html')


@app.route('/about')
def about():
    return render_template('about.html')


@app.route('/contact')
def contact():
    return render_template('contact.html')

@app.route('/feed.xml')
def feed():
    query = Article.query.order_by(desc(Article.timestamp)).all()
    return render_template('feed.xml', query=query)

# app run stuff

def main():
    manager.run()

if __name__ == '__main__':
    main()
