from datetime import date
from flask import Flask, render_template, redirect, url_for, flash, request, abort
from flask_bootstrap import Bootstrap5
from flask_ckeditor import CKEditor
from flask_gravatar import Gravatar
from flask_login import UserMixin, login_user, LoginManager, current_user, logout_user, login_required
from flask_sqlalchemy import SQLAlchemy
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.orm import relationship
from forms import CreatePostForm, RegisterForm, LoginForm, CommentForm
import os


app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get("SECRET_KEY")
ckeditor = CKEditor(app)
Bootstrap5(app)


gravatar = Gravatar(app,
                    size=100,
                    rating='g',
                    default='retro',
                    force_default=False,
                    force_lower=False,
                    use_ssl=False,
                    base_url=None)



app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DB_URI", "sqlite:///posts.db")
db = SQLAlchemy()
db.init_app(app)

login_manager = LoginManager(app)
login_manager.init_app(app)


def notlogin(f):
    @wraps(f)
    def decorator_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return f(*args, **kwargs)
        else:
            return abort(404)
    return decorator_function

def admin_only(f):
    @wraps(f)
    def decorator_function(*args, **kwargs):
        try:
            if current_user.id !=1:
                return abort(403)
            else:
                return f(*args, **kwargs)
        except Exception:
            return abort(404)
    return decorator_function

def check_login(f):
    @wraps(f)
    def decorator_function(*args, **kwargs):
        try:
            if not current_user.is_authenticated:
                return redirect(url_for("login"))
            else:
                return f(*args, **kwargs)
        except Exception:
            return abort(404)
    return decorator_function



@login_manager.user_loader
def load_user(user_id):
    return db.get_or_404(User, user_id)



class BlogPost(db.Model):
    __tablename__ = "blog_posts"

    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    author = relationship("User", back_populates="posts")
    comments = relationship("Comments", back_populates="post")

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    #author = db.Column(db.String(250), nullable=False)
    img_url = db.Column(db.String(250), nullable=False)

class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(250), nullable=False)
    email = db.Column(db.String(250), nullable=False)
    password = db.Column(db.String(250), nullable=False)

    posts = relationship("BlogPost", back_populates="author")
    comments = relationship("Comments", back_populates="author")

class Comments(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    author = relationship("User", back_populates="comments")
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    body = db.Column(db.String(250), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey("blog_posts.id"))
    post = relationship("BlogPost", back_populates="comments")



with app.app_context():
    db.create_all()


@app.route('/register', methods=["POST", "GET"])
@notlogin
def register():
    form = RegisterForm()
    if request.method == "POST":
        username = form.name.data
        email = form.email.data
        password = form.password.data
        user = db.session.execute(db.select(User).where(User.name == username)).scalar()
        if user:
            flash("You have got account")
            return redirect(url_for("login"))
        else:
            password = generate_password_hash(password, salt_length=8)
            new_user = User(name=username, email=email, password=password)
            db.session.add(new_user)
            db.session.commit()
            login_user(new_user)
            return redirect(url_for("get_all_posts"))
    return render_template("register.html", form=form)


@app.route('/login', methods=["GET", "POST"])
@notlogin
def login():
    form = LoginForm()
    if request.method == "POST":
        email = form.email.data
        password = form.password.data
        user = db.session.execute(db.select(User).where(User.email == email)).scalar()
        if not user:
            return redirect(url_for("register"))
        elif check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for("get_all_posts"))
        else:
            return render_template("login.html", form=form)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route('/')
def get_all_posts():
    result = db.session.execute(db.select(BlogPost))
    posts = result.scalars().all()
    return render_template("index.html", all_posts=posts, logged_in=current_user.is_authenticated)


@app.route("/post/<int:post_id>", methods=["GET", "POST"])
@check_login
def show_post(post_id):
    post = db.get_or_404(BlogPost, post_id)
    form = CommentForm()
    if request.method == "POST":
        if form.validate_on_submit():
            body = form.body.data
            db.session.add(Comments(body=body, author=current_user, post=post))
            db.session.commit()
            return redirect(url_for("show_post", post_id=post_id))
        else:
            return abort(404)
    #comments = db.session.execute(db.select(Comments)).scalars().all()
    return render_template("post.html", post=post, logged_in=current_user.is_authenticated, form=form)


@app.route("/new-post", methods=["GET", "POST"])
@admin_only
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author=current_user,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form, logged_in=current_user.is_authenticated)


@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
@admin_only
def edit_post(post_id):
    post = db.get_or_404(BlogPost, post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.author = current_user
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))
    return render_template("make-post.html", form=edit_form, is_edit=True, logged_in=current_user.is_authenticated)


@app.route("/delete/<int:post_id>")
@admin_only
def delete_post(post_id):
    post_to_delete = db.get_or_404(BlogPost, post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


@app.route("/about")
def about():
    return render_template("about.html", logged_in=current_user.is_authenticated)


@app.route("/contact")
def contact():
    return render_template("contact.html", logged_in=current_user.is_authenticated)

@app.route("/chats")
def chatPage():
    return render_template("chat.html")


if __name__ == "__main__":
    app.run(debug=True)
