from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-very-secret-key-123'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///blog.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Модели
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    posts = db.relationship('Post', backref='author', lazy=True)
    comments = db.relationship('Comment', backref='author', lazy=True)
    following = db.relationship('Follow', foreign_keys='Follow.follower_id', backref='follower', lazy=True)
    followers = db.relationship('Follow', foreign_keys='Follow.followed_id', backref='followed', lazy=True)

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    date_posted = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    is_public = db.Column(db.Boolean, default=True)
    tags = db.Column(db.String(200))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    comments = db.relationship('Comment', backref='post', lazy=True)

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    date_posted = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)

class Follow(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    follower_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    followed_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date_followed = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('follower_id', 'followed_id', name='unique_follow'),
    )

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Создаем таблицы
with app.app_context():
    db.create_all()

# Маршруты
@app.route('/')
def home():
    posts = Post.query.filter_by(is_public=True).order_by(Post.date_posted.desc()).all()
    return render_template('index.html', posts=posts)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = generate_password_hash(request.form['password'])

        if User.query.filter_by(username=username).first():
            flash('Имя пользователя уже занято', 'error')
            return redirect(url_for('register'))

        new_user = User(username=username, password=password)
        db.session.add(new_user)
        db.session.commit()

        flash('Регистрация прошла успешно! Теперь вы можете войти.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()

        if user and check_password_hash(user.password, request.form['password']):
            login_user(user)
            return redirect(url_for('home'))

        flash('Неверное имя пользователя или пароль', 'error')

    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

@app.route('/post/new', methods=['GET', 'POST'])
@login_required
def new_post():
    if request.method == 'POST':
        post = Post(
            title=request.form['title'],
            content=request.form['content'],
            is_public='is_public' in request.form,
            tags=request.form.get('tags', ''),
            author=current_user
        )
        db.session.add(post)
        db.session.commit()
        flash('Пост успешно создан!', 'success')
        return redirect(url_for('home'))

    return render_template('create_post.html')

@app.route('/post/<int:post_id>')
def view_post(post_id):
    post = Post.query.get_or_404(post_id)

    if not post.is_public and (not current_user.is_authenticated or post.author != current_user):
        flash('Этот пост приватный', 'error')
        return redirect(url_for('home'))

    return render_template('post.html', post=post)

@app.route('/post/<int:post_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_post(post_id):
    post = Post.query.get_or_404(post_id)

    if post.author != current_user:
        flash('Вы можете редактировать только свои посты', 'error')
        return redirect(url_for('home'))

    if request.method == 'POST':
        post.title = request.form['title']
        post.content = request.form['content']
        post.is_public = 'is_public' in request.form
        post.tags = request.form.get('tags', '')
        db.session.commit()
        flash('Пост успешно обновлен!', 'success')
        return redirect(url_for('view_post', post_id=post.id))

    return render_template('edit_post.html', post=post)

@app.route('/post/<int:post_id>/delete', methods=['POST'])
@login_required
def delete_post(post_id):
    post = Post.query.get_or_404(post_id)

    if post.author != current_user:
        flash('Вы можете удалять только свои посты', 'error')
        return redirect(url_for('home'))

    db.session.delete(post)
    db.session.commit()
    flash('Пост успешно удален!', 'success')
    return redirect(url_for('home'))

@app.route('/post/<int:post_id>/comment', methods=['POST'])
@login_required
def add_comment(post_id):
    post = Post.query.get_or_404(post_id)
    comment = Comment(
        content=request.form['content'],
        author=current_user,
        post=post
    )
    db.session.add(comment)
    db.session.commit()
    flash('Комментарий добавлен!', 'success')
    return redirect(url_for('view_post', post_id=post.id))

@app.route('/follow/<int:user_id>', methods=['POST'])
@login_required
def follow(user_id):
    user_to_follow = User.query.get_or_404(user_id)

    if current_user.id == user_id:
        flash('Вы не можете подписаться на себя', 'error')
        return redirect(url_for('home'))

    if Follow.query.filter_by(follower_id=current_user.id, followed_id=user_id).first():
        flash(f'Вы уже подписаны на {user_to_follow.username}', 'error')
        return redirect(url_for('home'))

    follow = Follow(follower_id=current_user.id, followed_id=user_id)
    db.session.add(follow)
    db.session.commit()
    flash(f'Вы подписались на {user_to_follow.username}!', 'success')
    return redirect(url_for('home'))

@app.route('/unfollow/<int:user_id>', methods=['POST'])
@login_required
def unfollow(user_id):
    user_to_unfollow = User.query.get_or_404(user_id)
    follow = Follow.query.filter_by(follower_id=current_user.id, followed_id=user_id).first()

    if not follow:
        flash(f'Вы не подписаны на {user_to_unfollow.username}', 'error')
        return redirect(url_for('home'))

    db.session.delete(follow)
    db.session.commit()
    flash(f'Вы отписались от {user_to_unfollow.username}', 'success')
    return redirect(url_for('home'))

@app.route('/feed')
@login_required
def feed():
    following = Follow.query.filter_by(follower_id=current_user.id).all()
    following_ids = [f.followed_id for f in following]
    posts = Post.query.filter(Post.user_id.in_(following_ids)).order_by(Post.date_posted.desc()).all()
    return render_template('feed.html', posts=posts)

@app.route('/tags/<tag>')
def posts_by_tag(tag):
    posts = Post.query.filter(Post.tags.contains(tag)).order_by(Post.date_posted.desc()).all()
    return render_template('tags.html', posts=posts, tag=tag)

if __name__ == '__main__':
    app.run(debug=True)