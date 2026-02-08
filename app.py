import os
import uuid
import json
import re
import random
from datetime import datetime, timedelta
# Подключаем Cloudinary
import cloudinary
import cloudinary.uploader
import cloudinary.api

from flask import Flask, render_template, redirect, url_for, request, flash, jsonify, abort, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import or_, and_, func, text
import jinja2
from flask_socketio import SocketIO, emit, join_room, leave_room

# --- НАСТРОЙКИ ПРИЛОЖЕНИЯ ---
app = Flask(__name__)
app.config['SECRET_KEY'] = 'fontan_ultra_admin_edition_v9_reset'

# --- НАСТРОЙКИ CLOUDINARY (ТВОИ ДАННЫЕ ВСТАВЛЕНЫ) ---
cloudinary.config(
    cloud_name = 'daz4839e7', 
    api_key = '371541773313745', 
    api_secret = 'fumEMY1h-nsFKW8B5BCgix9EN-8',
    secure = True
)

# --- НАСТРОЙКА БД (NEON / RENDER) ---
NEON_DB_URL = os.environ.get('DATABASE_URL')
if not NEON_DB_URL:
    # Твоя резервная ссылка
    NEON_DB_URL = 'postgresql://neondb_owner:npg_pIZeE3uY7XLF@ep-shy-field-ahelwpwv-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=require' 

if NEON_DB_URL and NEON_DB_URL.startswith("postgres://"):
    NEON_DB_URL = NEON_DB_URL.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = NEON_DB_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {"pool_pre_ping": True, "pool_recycle": 300}

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
socketio = SocketIO(app, cors_allowed_origins="*")

# --- ФУНКЦИЯ ЗАГРУЗКИ В ОБЛАКО ---
def upload_to_cloud(file_obj, resource_type="auto"):
    if not file_obj: return None
    try:
        # Грузим в Cloudinary, папка fontan_app
        upload_result = cloudinary.uploader.upload(
            file_obj, 
            resource_type=resource_type,
            folder="fontan_app"
        )
        return upload_result['secure_url'] # Возвращаем вечную ссылку
    except Exception as e:
        print(f"Ошибка Cloudinary: {e}")
        return None

def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'webm', 'mp3', 'wav', 'ogg'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- AI МОДЕРАЦИЯ КОНТЕНТА ---
def moderate_content(text):
    """Улучшенная бесплатная AI модерация контента (эвристики + стоп-слова)"""
    if not text:
        return True, ""
    
    forbidden_words = [
        'спам', 'реклама', 'казино', 'ставки', 'наркотики',
        'оружие', 'взлом', 'hack', 'porn', 'sex', 'nsfw', '18+',
        'фишинг', 'обнал', 'крипта', 'профит', 'заработок',
        'мошен', 'scam', 'leak', 'onlyfans'
    ]
    
    text_lower = text.lower()
    for word in forbidden_words:
        if word in text_lower:
            return False, f"Обнаружено запрещённое слово: {word}"

    # Эвристики: слишком много ссылок/капса/повторов
    links = len(re.findall(r'(https?://|www\.)', text_lower))
    if links >= 3:
        return False, "Слишком много ссылок"

    letters = re.findall(r'[a-zа-я]', text_lower)
    if letters:
        upper = sum(1 for c in text if c.isupper())
        if upper / max(1, len(text)) > 0.6 and len(text) > 20:
            return False, "Слишком много капса"

    if len(text) > 4000:
        return False, "Слишком длинный текст"
    
    return True, ""

# --- МОДЕЛИ БАЗЫ ДАННЫХ ---

group_members = db.Table('group_members',
    db.Column('user_id', db.Integer, db.ForeignKey('users.id'), primary_key=True),
    db.Column('group_id', db.Integer, db.ForeignKey('groups.id'), primary_key=True)
)

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    bio = db.Column(db.String(300), default="Я тут новенький!")
    avatar = db.Column(db.String(300), default=None)
    banner = db.Column(db.String(300), default=None)
    theme = db.Column(db.String(10), default='light')
    color_theme = db.Column(db.String(20), default='blue')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Поля админа
    is_admin = db.Column(db.Boolean, default=False)
    is_banned = db.Column(db.Boolean, default=False)
    is_verified = db.Column(db.Boolean, default=False)

    posts = db.relationship('Post', backref='author', lazy=True, foreign_keys='Post.user_id')
    likes = db.relationship('Like', backref='user', lazy=True)
    groups = db.relationship('Group', secondary=group_members, backref=db.backref('members', lazy='dynamic'))
    
    # Подписки (вайбики)
    following = db.relationship(
        'Follow',
        foreign_keys='Follow.follower_id',
        backref='follower',
        lazy='dynamic',
        cascade='all, delete-orphan'
    )
    followers = db.relationship(
        'Follow',
        foreign_keys='Follow.following_id',
        backref='following_user',
        lazy='dynamic',
        cascade='all, delete-orphan'
    )

class Follow(db.Model):
    __tablename__ = 'follows'
    id = db.Column(db.Integer, primary_key=True)
    follower_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    following_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class Friendship(db.Model):
    __tablename__ = 'friendships'
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    status = db.Column(db.String(20), default='pending') 

class Group(db.Model):
    __tablename__ = 'groups'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(300), default="")
    is_private = db.Column(db.Boolean, default=False)
    creator_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

class Message(db.Model):
    __tablename__ = 'messages'
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    group_id = db.Column(db.Integer, db.ForeignKey('groups.id'), nullable=True)
    body = db.Column(db.Text, nullable=True) 
    voice_filename = db.Column(db.String(300), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    edited_at = db.Column(db.DateTime, nullable=True)
    delivered_at = db.Column(db.DateTime, nullable=True)
    read_at = db.Column(db.DateTime, nullable=True)
    deleted_for_all = db.Column(db.Boolean, default=False)
    deleted_for = db.Column(db.Text, default='[]')  # JSON list of user ids
    sender = db.relationship('User', foreign_keys=[sender_id])

class Like(db.Model):
    __tablename__ = 'likes'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'), nullable=False)

class PostView(db.Model):
    __tablename__ = 'post_views'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'), nullable=False)

class Comment(db.Model):
    __tablename__ = 'comments'
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(500), nullable=True)
    voice_filename = db.Column(db.String(300), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'), nullable=False)
    author = db.relationship('User', backref='comments')

class Poll(db.Model):
    __tablename__ = 'polls'
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'), nullable=False)
    question = db.Column(db.String(300), nullable=False)
    options = db.Column(db.Text, nullable=False)  # JSON строка с вариантами
    votes = db.Column(db.Text, default='{}')  # JSON строка с голосами

class PollVote(db.Model):
    __tablename__ = 'poll_votes'
    id = db.Column(db.Integer, primary_key=True)
    poll_id = db.Column(db.Integer, db.ForeignKey('polls.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    option_index = db.Column(db.Integer, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class Post(db.Model):
    __tablename__ = 'posts'
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=True)
    image_filename = db.Column(db.String(300), nullable=True)
    video_filename = db.Column(db.String(300), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    edited_at = db.Column(db.DateTime, nullable=True)
    views = db.Column(db.Integer, default=0)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    co_author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    is_moderated = db.Column(db.Boolean, default=True)
    moderation_reason = db.Column(db.String(200), nullable=True)
    comments_enabled = db.Column(db.Boolean, default=True)
    
    comments_rel = db.relationship('Comment', backref='post', cascade="all, delete-orphan", lazy=True)
    likes_rel = db.relationship('Like', backref='post', cascade="all, delete-orphan", lazy=True)
    views_rel = db.relationship('PostView', backref='post', cascade="all, delete-orphan", lazy=True)
    poll = db.relationship('Poll', backref='post', uselist=False, cascade="all, delete-orphan")
    media = db.relationship('PostMedia', backref='post', cascade="all, delete-orphan", lazy=True)
    co_author = db.relationship('User', foreign_keys=[co_author_id])

class PostMedia(db.Model):
    __tablename__ = 'post_media'
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'), nullable=False)
    media_url = db.Column(db.String(300), nullable=False)
    media_type = db.Column(db.String(20), nullable=False)  # image | video

class Notification(db.Model):
    __tablename__ = 'notifications'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    from_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    ntype = db.Column(db.String(50), nullable=False)  # like, comment, follow, mention, system
    message = db.Column(db.String(300), nullable=True)
    link = db.Column(db.String(200), nullable=True)
    is_read = db.Column(db.Boolean, default=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class Report(db.Model):
    __tablename__ = 'reports'
    id = db.Column(db.Integer, primary_key=True)
    reporter_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'), nullable=True)
    target_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    reason = db.Column(db.String(300), nullable=True)
    status = db.Column(db.String(30), default='open')
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class Story(db.Model):
    __tablename__ = 'stories'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    media_url = db.Column(db.String(300), nullable=False)
    media_type = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)
    author = db.relationship('User', foreign_keys=[user_id])

class StoryView(db.Model):
    __tablename__ = 'story_views'
    id = db.Column(db.Integer, primary_key=True)
    story_id = db.Column(db.Integer, db.ForeignKey('stories.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class UserSession(db.Model):
    __tablename__ = 'user_sessions'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    session_token = db.Column(db.String(64), nullable=False, unique=True)
    ip = db.Column(db.String(64), nullable=True)
    city = db.Column(db.String(100), nullable=True)
    user_agent = db.Column(db.String(300), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)

def ensure_user_sessions_schema():
    try:
        with app.app_context():
            db.session.execute(text("ALTER TABLE user_sessions ADD COLUMN IF NOT EXISTS ip VARCHAR(64)"))
            db.session.execute(text("ALTER TABLE user_sessions ADD COLUMN IF NOT EXISTS city VARCHAR(100)"))
            db.session.execute(text("ALTER TABLE user_sessions ADD COLUMN IF NOT EXISTS user_agent VARCHAR(300)"))
            db.session.execute(text("ALTER TABLE user_sessions ADD COLUMN IF NOT EXISTS created_at TIMESTAMP"))
            db.session.execute(text("ALTER TABLE user_sessions ADD COLUMN IF NOT EXISTS last_seen TIMESTAMP"))
            db.session.execute(text("ALTER TABLE user_sessions ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE"))
            db.session.commit()
    except Exception as e:
        print(f"Schema check failed: {e}")
        db.session.rollback()

class GroupRole(db.Model):
    __tablename__ = 'group_roles'
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('groups.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    role = db.Column(db.String(30), default='member')  # admin, moderator, editor, member

class GroupJoinRequest(db.Model):
    __tablename__ = 'group_join_requests'
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('groups.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    status = db.Column(db.String(30), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

ensure_user_sessions_schema()

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

@app.context_processor
def inject_counts():
    if current_user.is_authenticated:
        unread = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
    else:
        unread = 0
    return dict(unread_notifications=unread)

# Проверка на бан
@app.before_request
def check_ban():
    if current_user.is_authenticated and current_user.is_banned:
        logout_user()
        flash("Ваш аккаунт заблокирован администрацией.", "danger")
        return redirect(url_for('login'))

@app.before_request
def update_last_seen():
    if current_user.is_authenticated:
        current_user.last_seen = datetime.utcnow()
        token = session.get('session_token')
        if token:
            sess = UserSession.query.filter_by(session_token=token, user_id=current_user.id, is_active=True).first()
            if sess:
                sess.last_seen = datetime.utcnow()
        db.session.commit()

# --- ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ ДЛЯ ВРЕМЕНИ ---
def time_ago(dt):
    """Красивое отображение времени"""
    now = datetime.utcnow()
    diff = now - dt
    
    seconds = diff.total_seconds()
    
    if seconds < 60:
        return "только что"
    elif seconds < 3600:
        minutes = int(seconds / 60)
        return f"{minutes} мин назад"
    elif seconds < 86400:
        hours = int(seconds / 3600)
        return f"{hours} ч назад"
    elif seconds < 604800:
        days = int(seconds / 86400)
        return f"{days} д назад"
    else:
        return dt.strftime('%d.%m.%Y в %H:%M')

app.jinja_env.filters['time_ago'] = time_ago

# --- КАПЧА ---
def generate_captcha():
    a = random.randint(1, 9)
    b = random.randint(1, 9)
    op = random.choice(['+', '-'])
    question = f"{a} {op} {b}"
    answer = str(a + b) if op == '+' else str(a - b)
    session['captcha_q'] = question
    session['captcha_a'] = answer
    return question

def validate_captcha(user_answer):
    return user_answer and session.get('captcha_a') == str(user_answer).strip()

# --- УПОМИНАНИЯ И ХЭШТЕГИ ---
def linkify_text(text):
    if not text:
        return text
    def repl_mention(match):
        uname = match.group(1)
        return f'<a href="/profile/{uname}" class="text-primary">@{uname}</a>'
    def repl_tag(match):
        tag = match.group(1)
        return f'<a href="/search?q=%23{tag}" class="text-success">#{tag}</a>'
    text = re.sub(r'@([A-Za-z0-9_\\.]+)', repl_mention, text)
    text = re.sub(r'#([A-Za-z0-9_\\.]+)', repl_tag, text)
    return text

app.jinja_env.filters['linkify'] = linkify_text

def create_notification(user_id, ntype, message=None, link=None, from_user_id=None):
    try:
        n = Notification(user_id=user_id, from_user_id=from_user_id, ntype=ntype, message=message, link=link)
        db.session.add(n)
        db.session.commit()
    except Exception as e:
        print(f"notify error: {e}")

def get_client_ip():
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    if ip and ',' in ip:
        ip = ip.split(',')[0].strip()
    return ip

def guess_city(ip):
    if not ip:
        return None
    if ip.startswith('127.') or ip.startswith('10.') or ip.startswith('192.168'):
        return 'Local'
    return None

def get_room(chat_type, chat_id, user_id):
    if chat_type == 'private':
        a, b = sorted([int(user_id), int(chat_id)])
        return f"private_{a}_{b}"
    return f"group_{chat_id}"

# --- ШАБЛОНЫ ---
templates = {
    'base.html': """
<!DOCTYPE html>
<html lang="ru" data-theme="{{ current_user.theme if current_user.is_authenticated else 'light' }}" data-color="{{ current_user.color_theme if current_user.is_authenticated else 'blue' }}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Fontan V5</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.0/font/bootstrap-icons.css">
    <style>
        :root[data-theme="light"] {
            --bg-color: #f0f2f5;
            --card-bg: #ffffff;
            --text-color: #000000;
            --text-muted: #65676b;
            --border-color: #e4e6eb;
            --navbar-bg: linear-gradient(135deg, #4f46e5, #7c3aed);
            --hover-bg: #f0f2f5;
            --accent: #4f46e5;
        }
        
        :root[data-theme="dark"] {
            --bg-color: #18191a;
            --card-bg: #242526;
            --text-color: #e4e6eb;
            --text-muted: #b0b3b8;
            --border-color: #3a3b3c;
            --navbar-bg: linear-gradient(135deg, #3730a3, #5b21b6);
            --hover-bg: #3a3b3c;
            --accent: #4f46e5;
        }

        :root[data-color="blue"] { --accent: #2563eb; }
        :root[data-color="purple"] { --accent: #7c3aed; }
        :root[data-color="orange"] { --accent: #f97316; }
        
        body { 
            background-color: var(--bg-color); 
            color: var(--text-color);
            font-family: 'Segoe UI', sans-serif;
            transition: background-color 0.3s, color 0.3s;
        }
        
        .navbar { 
            background: var(--navbar-bg);
            transition: background 0.3s;
        }
        
        .card { 
            background-color: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 16px; 
            box-shadow: 0 2px 5px rgba(0,0,0,0.1); 
            margin-bottom: 20px;
            transition: all 0.3s;
            animation: fadeIn 0.5s ease-in;
        }
        
        .card:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }
        
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(20px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        @keyframes slideIn {
            from { transform: translateX(-100%); }
            to { transform: translateX(0); }
        }
        
        @keyframes pulse {
            0%, 100% { transform: scale(1); }
            50% { transform: scale(1.05); }
        }
        
        .avatar { 
            width: 40px; 
            height: 40px; 
            border-radius: 50%; 
            object-fit: cover; 
            background: var(--hover-bg); 
            display: flex; 
            align-items: center; 
            justify-content: center; 
            font-weight: bold; 
            color: var(--text-muted); 
            overflow: hidden;
            transition: transform 0.3s;
        }
        
        .avatar:hover {
            transform: scale(1.1);
        }
        
        .avatar img { 
            width: 100%; 
            height: 100%; 
            object-fit: cover; 
        }
        
        .msg-bubble { 
            padding: 8px 14px; 
            border-radius: 18px; 
            max-width: 75%; 
            margin-bottom: 4px;
            animation: slideIn 0.3s ease-out;
        }
        
        .msg-sent { 
            background-color: #4f46e5; 
            color: white; 
            align-self: flex-end; 
        }
        
        .msg-received { 
            background-color: var(--hover-bg); 
            color: var(--text-color); 
            align-self: flex-start; 
        }
        
        .verified-icon { 
            color: #1DA1F2; 
            margin-left: 4px; 
        }
        
        .blink { 
            animation: blinker 1s linear infinite; 
        } 
        
        @keyframes blinker { 
            50% { opacity: 0; } 
        }
        
        .text-muted {
            color: var(--text-muted) !important;
        }
        
        .border-top, .border-bottom {
            border-color: var(--border-color) !important;
        }
        
        .bg-light {
            background-color: var(--hover-bg) !important;
        }
        
        .form-control, .form-select {
            background-color: var(--card-bg);
            color: var(--text-color);
            border-color: var(--border-color);
        }
        
        .form-control:focus, .form-select:focus {
            background-color: var(--card-bg);
            color: var(--text-color);
            border-color: #4f46e5;
        }
        
        .btn-outline-primary:hover,
        .btn-outline-success:hover,
        .btn-outline-secondary:hover {
            color: white;
        }
        
        a {
            color: inherit;
        }
        
        .post-media {
            max-width: 100%;
            border-radius: 12px;
            transition: transform 0.3s;
        }
        
        .post-media:hover {
            transform: scale(1.02);
        }
        
        .poll-option {
            transition: all 0.3s;
            cursor: pointer;
        }
        
        .poll-option:hover {
            background-color: var(--hover-bg);
            transform: translateX(5px);
        }
        
        .poll-bar {
            height: 100%;
            background: linear-gradient(90deg, #4f46e5, #7c3aed);
            border-radius: 8px;
            transition: width 0.5s ease-out;
        }
        
        .theme-toggle {
            cursor: pointer;
            font-size: 1.3rem;
            transition: transform 0.3s;
        }
        
        .theme-toggle:hover {
            transform: rotate(20deg);
        }
        
        .loading-spinner {
            text-align: center;
            padding: 20px;
            display: none;
        }
        
        .spinner-border {
            border-color: #4f46e5;
            border-right-color: transparent;
        }
        
        .badge-vibers {
            background: linear-gradient(135deg, #4f46e5, #7c3aed);
            color: white;
            padding: 0.25rem 0.75rem;
            border-radius: 12px;
            font-size: 0.85rem;
            animation: pulse 2s infinite;
        }
        
        .follow-btn {
            transition: all 0.3s;
        }
        
        .follow-btn:hover {
            transform: scale(1.05);
        }

        .online-dot {
            width: 10px;
            height: 10px;
            background: #22c55e;
            border-radius: 50%;
            border: 2px solid var(--card-bg);
            position: absolute;
            bottom: -1px;
            right: -1px;
        }

        .story-item {
            width: 80px;
            text-align: center;
        }

        .story-avatar {
            width: 64px;
            height: 64px;
            border-radius: 50%;
            border: 2px solid #7c3aed;
            overflow: hidden;
            margin: 0 auto 6px;
        }

        .lightbox {
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(0,0,0,0.85);
            display: none;
            align-items: center;
            justify-content: center;
            z-index: 9999;
        }

        .lightbox img, .lightbox video {
            max-width: 90vw;
            max-height: 90vh;
            border-radius: 12px;
        }

        .like-pop {
            position: absolute;
            color: #ef4444;
            font-size: 48px;
            animation: pop 0.7s ease-out forwards;
        }

        @keyframes pop {
            0% { transform: scale(0.4); opacity: 0; }
            50% { transform: scale(1.1); opacity: 1; }
            100% { transform: scale(1.4); opacity: 0; }
        }
    </style>
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark sticky-top mb-4 shadow-sm">
        <div class="container">
            <a class="navbar-brand fw-bold" href="{{ url_for('index') }}"><i class="bi bi-droplet-fill"></i> Fontan</a>
            {% if current_user.is_authenticated %}
            <form class="d-none d-md-flex ms-3" action="{{ url_for('search') }}" method="GET" style="max-width:380px; width:100%;">
                <input name="q" class="form-control form-control-sm rounded-pill" placeholder="Поиск: люди, посты, хэштеги, группы">
            </form>
            {% endif %}
            <div class="d-flex gap-3 align-items-center">
                {% if current_user.is_authenticated %}
                    <span class="theme-toggle text-white" onclick="toggleTheme()">
                        <i class="bi bi-moon-stars-fill" id="theme-icon"></i>
                    </span>
                    <a class="nav-link text-white fs-5 position-relative" href="{{ url_for('notifications') }}">
                        <i class="bi bi-bell-fill"></i>
                        {% if unread_notifications > 0 %}
                            <span class="position-absolute top-0 start-100 translate-middle badge rounded-pill bg-danger">{{ unread_notifications }}</span>
                        {% endif %}
                    </a>
                    <a class="nav-link text-white fs-5" href="{{ url_for('messenger') }}"><i class="bi bi-chat-fill"></i></a>
                    <a class="nav-link text-white fs-5" href="{{ url_for('friends_requests') }}"><i class="bi bi-people-fill"></i></a>
                    <a class="nav-link text-white fs-5" href="{{ url_for('my_vibers') }}">
                        <i class="bi bi-heart-fill"></i>
                    </a>
                    <a class="nav-link text-white fs-5" href="{{ url_for('settings') }}"><i class="bi bi-gear-fill"></i></a>
                    <a class="nav-link text-white fs-5" href="{{ url_for('profile', username=current_user.username) }}">
                          <div class="avatar" style="width: 30px; height: 30px;">
                            {% if current_user.avatar %}
                                <img src="{{ current_user.avatar }}">
                            {% else %}
                                {{ current_user.username[0].upper() }}
                            {% endif %}
                          </div>
                    </a>
                    <a class="nav-link text-white fs-5" href="{{ url_for('logout') }}"><i class="bi bi-box-arrow-right"></i></a>
                {% endif %}
            </div>
        </div>
    </nav>
    <div class="container">
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="alert alert-{{ category }} text-center shadow-sm rounded-4">{{ message }}</div>
                {% endfor %}
            {% endif %}
        {% endwith %}
        {% block content %}{% endblock %}
    </div>
    <div class="lightbox" id="lightbox" onclick="closeLightbox()">
        <div id="lightbox-content"></div>
    </div>
    
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        function toggleTheme() {
            fetch('/toggle_theme', { method: 'POST' })
                .then(r => r.json())
                .then(data => {
                    document.documentElement.setAttribute('data-theme', data.theme);
                    updateThemeIcon(data.theme);
                });
        }
        
        function updateThemeIcon(theme) {
            const icon = document.getElementById('theme-icon');
            if (theme === 'dark') {
                icon.className = 'bi bi-sun-fill';
            } else {
                icon.className = 'bi bi-moon-stars-fill';
            }
        }
        
        // Инициализация иконки при загрузке
        document.addEventListener('DOMContentLoaded', function() {
            const theme = document.documentElement.getAttribute('data-theme');
            updateThemeIcon(theme);
        });

        function openLightbox(url, type) {
            const lb = document.getElementById('lightbox');
            const content = document.getElementById('lightbox-content');
            content.innerHTML = '';
            if (type === 'video') {
                content.innerHTML = `<video controls autoplay><source src="${url}"></video>`;
            } else {
                content.innerHTML = `<img src="${url}">`;
            }
            lb.style.display = 'flex';
        }

        function closeLightbox() {
            const lb = document.getElementById('lightbox');
            const content = document.getElementById('lightbox-content');
            content.innerHTML = '';
            lb.style.display = 'none';
        }

        function likePop(e, postId) {
            const pop = document.createElement('div');
            pop.className = 'like-pop';
            pop.innerHTML = '❤';
            pop.style.left = (e.clientX - 24) + 'px';
            pop.style.top = (e.clientY - 24) + 'px';
            document.body.appendChild(pop);
            setTimeout(() => pop.remove(), 700);
            fetch(`/like/${postId}`, { method: 'POST' }).then(() => {});
        }

        function sharePost(url) {
            const full = window.location.origin + url;
            if (navigator.share) {
                navigator.share({ url: full });
            } else {
                navigator.clipboard.writeText(full).then(() => alert('Ссылка скопирована'));
            }
        }

        function editPost(postId) {
            const text = prompt('Новый текст поста');
            if (text === null) return;
            const formData = new FormData();
            formData.append('content', text);
            fetch(`/edit_post/${postId}`, { method: 'POST', body: formData }).then(() => location.reload());
        }
    </script>
</body>
</html>
    """,

    'index.html': """
{% extends "base.html" %}
{% block content %}
<div class="row">
    <div class="col-md-3 d-none d-md-block">
        <div class="card p-3 sidebar">
            <div class="text-center mb-3">
                <div class="avatar avatar-xl mx-auto mb-2">
                    {% if current_user.avatar %}
                        <img src="{{ current_user.avatar }}" style="width:100px; height:100px; border-radius:50%;">
                    {% else %}
                        <div style="width:100px; height:100px; border-radius:50%; background:var(--hover-bg); line-height:100px; font-size:40px; margin:0 auto;">
                        {{ current_user.username[0].upper() }}
                        </div>
                    {% endif %}
                </div>
                <h5>
                    {{ current_user.username }}
                    {% if current_user.is_verified %}<i class="bi bi-patch-check-fill verified-icon"></i>{% endif %}
                </h5>
                {% if current_user.is_admin %}<span class="badge bg-danger">ADMIN</span>{% endif %}
                <div class="mt-2">
                    <span class="badge-vibers">
                        <i class="bi bi-heart-fill"></i> {{ current_user.followers.count() }} вайберов
                    </span>
                </div>
            </div>
            <hr>
            <a href="{{ url_for('users_list') }}" class="btn btn-outline-primary w-100 mb-2 rounded-pill">Найти людей</a>
            <a href="{{ url_for('friends_requests') }}" class="btn btn-outline-success w-100 mb-2 rounded-pill">Запросы в друзья</a>
            <a href="{{ url_for('my_vibers') }}" class="btn btn-outline-info w-100 mb-2 rounded-pill">
                <i class="bi bi-heart-fill"></i> Мои вайберы
            </a>
            {% if current_user.is_admin %}
            <a href="{{ url_for('admin_dashboard') }}" class="btn btn-outline-danger w-100 mb-2 rounded-pill">Админ</a>
            {% endif %}
        </div>
    </div>

    <div class="col-md-6">
        <div class="card p-3 mb-3">
            <div class="d-flex align-items-center gap-3 overflow-auto">
                <form method="POST" action="{{ url_for('create_story') }}" enctype="multipart/form-data" class="story-item">
                    <div class="story-avatar">
                        {% if current_user.avatar %}
                            <img src="{{ current_user.avatar }}" style="width:100%; height:100%; object-fit:cover;">
                        {% else %}
                            <div style="width:100%; height:100%; background:var(--hover-bg); display:flex; align-items:center; justify-content:center;">+</div>
                        {% endif %}
                    </div>
                    <label class="btn btn-sm btn-outline-primary rounded-pill">
                        История
                        <input type="file" name="story_media" hidden accept="image/*,video/*">
                    </label>
                </form>
                {% for story in stories %}
                <a class="story-item text-decoration-none" href="{{ url_for('view_story', story_id=story.id) }}">
                    <div class="story-avatar">
                        <img src="{{ story.media_url }}" style="width:100%; height:100%; object-fit:cover;">
                    </div>
                    <small class="text-muted">{{ story.author.username }}</small>
                </a>
                {% endfor %}
            </div>
        </div>

        <div class="card p-3">
            <form method="POST" action="{{ url_for('create_post') }}" enctype="multipart/form-data" id="create-post-form">
                <textarea name="content" class="form-control border-0 bg-light rounded-3 p-3" placeholder="Что нового?" rows="3"></textarea>
                
                <div id="poll-section" style="display: none;" class="mt-3 p-3 bg-light rounded-3">
                    <input type="text" name="poll_question" class="form-control mb-2" placeholder="Вопрос опроса" id="poll-question">
                    <div id="poll-options">
                        <input type="text" name="poll_option_1" class="form-control mb-2" placeholder="Вариант 1">
                        <input type="text" name="poll_option_2" class="form-control mb-2" placeholder="Вариант 2">
                    </div>
                    <button type="button" class="btn btn-sm btn-outline-secondary" onclick="addPollOption()">+ Добавить вариант</button>
                </div>
                
                <div class="mt-3 d-flex justify-content-between align-items-center">
                    <div class="d-flex gap-2">
                        <label class="btn btn-light text-primary rounded-pill">
                            <i class="bi bi-camera-fill"></i> Медиа
                            <input type="file" name="media" hidden accept="image/*,video/*" multiple>
                        </label>
                        <button type="button" class="btn btn-light text-success rounded-pill" onclick="togglePoll()">
                            <i class="bi bi-bar-chart-fill"></i> Опрос
                        </button>
                    </div>
                    <button type="submit" class="btn btn-primary rounded-pill px-4">Пост</button>
                </div>
                <div class="mt-2 d-flex gap-3 align-items-center">
                    <div class="form-check">
                        <input class="form-check-input" type="checkbox" name="disable_comments" id="disable_comments">
                        <label class="form-check-label" for="disable_comments">Отключить комментарии</label>
                    </div>
                    <input type="text" name="co_author" class="form-control form-control-sm" placeholder="Со‑автор (@username)">
                </div>
            </form>
        </div>

        <div id="posts-container">
            {% for post in posts %}
            {% include 'post_card.html' %}
            {% endfor %}
        </div>
        
        <div class="loading-spinner" id="loading-spinner">
            <div class="spinner-border" role="status">
                <span class="visually-hidden">Загрузка...</span>
            </div>
        </div>
        
        {% if not posts %}
        <div class="text-center py-5 text-muted"><p>Лента пуста. Подпишитесь на кого-нибудь!</p></div>
        {% endif %}
    </div>
</div>

<script>
let pollOptionCount = 2;
let isLoading = false;
let currentPage = 1;
let hasMore = true;

function togglePoll() {
    const pollSection = document.getElementById('poll-section');
    pollSection.style.display = pollSection.style.display === 'none' ? 'block' : 'none';
}

function addPollOption() {
    pollOptionCount++;
    if (pollOptionCount <= 6) {
        const optionsDiv = document.getElementById('poll-options');
        const input = document.createElement('input');
        input.type = 'text';
        input.name = `poll_option_${pollOptionCount}`;
        input.className = 'form-control mb-2';
        input.placeholder = `Вариант ${pollOptionCount}`;
        optionsDiv.appendChild(input);
    }
}

// Ленивая подгрузка постов
window.addEventListener('scroll', function() {
    if (isLoading || !hasMore) return;
    
    const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
    const scrollHeight = document.documentElement.scrollHeight;
    const clientHeight = document.documentElement.clientHeight;
    
    if (scrollTop + clientHeight >= scrollHeight - 500) {
        loadMorePosts();
    }
});

function loadMorePosts() {
    isLoading = true;
    document.getElementById('loading-spinner').style.display = 'block';
    currentPage++;
    
    fetch(`/api/load_posts?page=${currentPage}`)
        .then(r => r.json())
        .then(data => {
            document.getElementById('loading-spinner').style.display = 'none';
            
            if (data.posts && data.posts.length > 0) {
                const container = document.getElementById('posts-container');
                data.posts.forEach(postHtml => {
                    const div = document.createElement('div');
                    div.innerHTML = postHtml;
                    container.appendChild(div.firstElementChild);
                });
                isLoading = false;
            } else {
                hasMore = false;
            }
        })
        .catch(err => {
            console.error(err);
            isLoading = false;
            document.getElementById('loading-spinner').style.display = 'none';
        });
}

document.querySelectorAll('.btn-record-comment').forEach(btn => {
    let mediaRecorder;
    let audioChunks = [];
    let isRecording = false;

    btn.addEventListener('click', async () => {
        const postId = btn.dataset.postId;
        if (!isRecording) {
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                mediaRecorder = new MediaRecorder(stream);
                mediaRecorder.start();
                btn.classList.remove('btn-danger');
                btn.classList.add('btn-warning', 'blink');
                isRecording = true;
                mediaRecorder.addEventListener("dataavailable", event => { audioChunks.push(event.data); });
                mediaRecorder.addEventListener("stop", () => {
                    const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
                    const formData = new FormData();
                    formData.append("voice", audioBlob, "voice.webm");
                    fetch(`/add_voice_comment/${postId}`, { method: 'POST', body: formData }).then(r => location.reload());
                    audioChunks = [];
                });
            } catch (err) { alert("Нет доступа к микрофону!"); }
        } else {
            mediaRecorder.stop();
            btn.classList.add('btn-danger');
            btn.classList.remove('btn-warning', 'blink');
            isRecording = false;
        }
    });
});

function votePoll(pollId, optionIndex) {
    fetch(`/vote_poll/${pollId}/${optionIndex}`, { method: 'POST' })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                location.reload();
            } else {
                alert(data.error || 'Ошибка голосования');
            }
        });
}
</script>
{% endblock %}
    """,

    'post_card.html': """
<div class="card p-3">
    <div class="d-flex justify-content-between align-items-start">
        <div class="d-flex align-items-center">
            <a href="{{ url_for('profile', username=post.author.username) }}" class="text-decoration-none">
                <div class="avatar me-2">
                    {% if post.author.avatar %}
                        <img src="{{ post.author.avatar }}">
                    {% else %}
                        {{ post.author.username[0].upper() }}
                    {% endif %}
                </div>
            </a>
            <div>
                <a href="{{ url_for('profile', username=post.author.username) }}" class="fw-bold text-decoration-none" style="color: var(--text-color);">
                    {{ post.author.username }}
                    {% if post.author.is_verified %}<i class="bi bi-patch-check-fill verified-icon"></i>{% endif %}
                </a>
                {% if post.co_author_id %}
                    <span class="text-muted small">· cо‑автор</span>
                    <a href="{{ url_for('profile', username=post.co_author.username) }}" class="text-decoration-none text-muted small">
                        {{ post.co_author.username }}
                    </a>
                {% endif %}
                <div class="text-muted small" style="font-size: 0.75rem;">{{ post.timestamp|time_ago }}{% if post.edited_at %} · изменено{% endif %}</div>
            </div>
        </div>
        {% if post.author.id == current_user.id or current_user.is_admin %}
        <div class="d-flex gap-2">
            <a class="text-secondary" href="#" onclick="editPost({{ post.id }});return false;"><i class="bi bi-pencil"></i></a>
            <a class="text-danger" href="{{ url_for('delete_post', post_id=post.id) }}"><i class="bi bi-trash"></i></a>
        </div>
        {% endif %}
    </div>
    
    {% if not post.is_moderated %}
    <div class="alert alert-warning mt-2 mb-2">
        <i class="bi bi-exclamation-triangle-fill"></i> Пост заблокирован модерацией: {{ post.moderation_reason }}
    </div>
    {% endif %}
    
    <div class="mt-2 position-relative" ondblclick="likePop(event, {{ post.id }})">
        {% if post.content %}<p class="card-text fs-6">{{ post.content|linkify|safe }}</p>{% endif %}
        {% if post.media and post.media|length > 0 %}
            <div id="carousel-{{ post.id }}" class="carousel slide" data-bs-ride="carousel">
                <div class="carousel-inner">
                    {% for m in post.media %}
                    <div class="carousel-item {% if loop.index0 == 0 %}active{% endif %}">
                        {% if m.media_type == 'video' %}
                            <video controls class="post-media img-fluid rounded" onclick="openLightbox('{{ m.media_url }}','video')"><source src="{{ m.media_url }}"></video>
                        {% else %}
                            <img src="{{ m.media_url }}" class="post-media img-fluid rounded" onclick="openLightbox('{{ m.media_url }}','image')">
                        {% endif %}
                    </div>
                    {% endfor %}
                </div>
                {% if post.media|length > 1 %}
                <button class="carousel-control-prev" type="button" data-bs-target="#carousel-{{ post.id }}" data-bs-slide="prev">
                    <span class="carousel-control-prev-icon"></span>
                </button>
                <button class="carousel-control-next" type="button" data-bs-target="#carousel-{{ post.id }}" data-bs-slide="next">
                    <span class="carousel-control-next-icon"></span>
                </button>
                {% endif %}
            </div>
        {% else %}
            {% if post.image_filename %}
                <img src="{{ post.image_filename }}" class="post-media img-fluid rounded" onclick="openLightbox('{{ post.image_filename }}','image')">
            {% endif %}
            {% if post.video_filename %}
                <video controls class="post-media img-fluid rounded" onclick="openLightbox('{{ post.video_filename }}','video')"><source src="{{ post.video_filename }}"></video>
            {% endif %}
        {% endif %}
        
        {% if post.poll %}
        <div class="mt-3 p-3 bg-light rounded-3">
            <h6 class="mb-3"><i class="bi bi-bar-chart-fill"></i> {{ post.poll.question }}</h6>
            {% set poll_data = post.poll.votes|from_json %}
            {% set total_votes = poll_data.values()|sum %}
            {% set user_voted = current_user.id|string in poll_data.keys() %}
            
            {% for option in post.poll.options|from_json %}
            {% set option_votes = poll_data.get(loop.index0|string, 0) %}
            {% set percentage = (option_votes / total_votes * 100) if total_votes > 0 else 0 %}
            
            <div class="poll-option mb-2 p-2 border rounded position-relative" 
                 {% if not user_voted %}onclick="votePoll({{ post.poll.id }}, {{ loop.index0 }})"{% endif %}>
                <div class="poll-bar position-absolute top-0 start-0 h-100" style="width: {{ percentage }}%; opacity: 0.2;"></div>
                <div class="position-relative d-flex justify-content-between align-items-center">
                    <span>{{ option }}</span>
                    <span class="badge bg-primary">{{ percentage|round(1) }}% ({{ option_votes }})</span>
                </div>
            </div>
            {% endfor %}
            
            <small class="text-muted">Всего голосов: {{ total_votes }}</small>
        </div>
        {% endif %}
    </div>

    <div class="d-flex align-items-center justify-content-between mt-3 pt-2 border-top">
        <div class="d-flex gap-4">
            <form action="{{ url_for('like_post', post_id=post.id) }}" method="POST">
                <button class="btn p-0 text-secondary d-flex align-items-center gap-1">
                    <i class="bi {% if current_user.id in post.likes_rel|map(attribute='user_id')|list %}bi-heart-fill text-danger{% else %}bi-heart{% endif %} fs-5"></i>
                    <span>{{ post.likes_rel|length }}</span>
                </button>
            </form>
            <div class="text-secondary d-flex align-items-center gap-1">
                <i class="bi bi-chat fs-5"></i> <span>{{ post.comments_rel|length }}</span>
            </div>
            <button class="btn p-0 text-secondary d-flex align-items-center gap-1" onclick="sharePost('{{ url_for('post_view', post_id=post.id) }}')">
                <i class="bi bi-share fs-5"></i> <span>Поделиться</span>
            </button>
        </div>
        <div class="text-muted small d-flex gap-3 align-items-center">
            <a class="text-danger text-decoration-none" href="{{ url_for('report', post_id=post.id) }}"><i class="bi bi-flag-fill"></i></a>
            <span><i class="bi bi-eye"></i> {{ post.views }}</span>
        </div>
    </div>

    <div class="mt-3 bg-light p-2 rounded-3">
        {% for comment in post.comments_rel %}
        <div class="mb-2 border-bottom pb-1">
            <div class="d-flex justify-content-between">
                 <small>
                     <b>{{ comment.author.username }}</b>
                     {% if comment.author.is_verified %}<i class="bi bi-patch-check-fill verified-icon" style="font-size: 10px;"></i>{% endif %}
                     :
                 </small>
                 {% if comment.user_id == current_user.id or post.user_id == current_user.id or current_user.is_admin %}
                    <a href="{{ url_for('delete_comment', comment_id=comment.id) }}" class="text-danger small" style="text-decoration:none;">×</a>
                 {% endif %}
            </div>
            {% if comment.text %}<div class="small">{{ comment.text }}</div>{% endif %}
            {% if comment.voice_filename %}
                <audio controls style="height: 30px; width: 200px;" class="mt-1">
                    <source src="{{ comment.voice_filename }}">
                </audio>
            {% endif %}
        </div>
        {% endfor %}
        {% if post.comments_enabled %}
        <div class="mt-2">
              <form action="{{ url_for('add_comment', post_id=post.id) }}" method="POST" class="d-flex gap-1 align-items-center">
                <input type="text" name="text" class="form-control form-control-sm rounded-pill" placeholder="Комментарий...">
                <button type="button" class="btn btn-sm btn-danger btn-record-comment rounded-circle" data-post-id="{{ post.id }}"><i class="bi bi-mic-fill"></i></button>
                <button type="submit" class="btn btn-sm btn-primary rounded-circle"><i class="bi bi-send-fill"></i></button>
              </form>
        </div>
        {% else %}
            <div class="text-muted small">Комментарии отключены</div>
        {% endif %}
    </div>
</div>
    """,

    'my_vibers.html': """
{% extends "base.html" %}
{% block content %}
<div class="row justify-content-center">
    <div class="col-md-8">
        <h3 class="mb-4">
            <i class="bi bi-heart-fill text-danger"></i> Мои вайберы
            <span class="badge-vibers ms-2">{{ followers|length }}</span>
        </h3>
        
        {% if followers %}
            {% for follower in followers %}
            <div class="card p-3 mb-2 d-flex flex-row justify-content-between align-items-center">
                <div class="d-flex align-items-center">
                    <div class="avatar me-3">
                        {% if follower.avatar %}
                            <img src="{{ follower.avatar }}">
                        {% else %}
                            {{ follower.username[0].upper() }}
                        {% endif %}
                    </div>
                    <div>
                        <h5 class="mb-0">
                            {{ follower.username }}
                            {% if follower.is_verified %}<i class="bi bi-patch-check-fill verified-icon"></i>{% endif %}
                        </h5>
                        <small class="text-muted">{{ follower.bio }}</small>
                    </div>
                </div>
                <div>
                    <a href="{{ url_for('profile', username=follower.username) }}" class="btn btn-primary btn-sm rounded-pill">Профиль</a>
                </div>
            </div>
            {% endfor %}
        {% else %}
            <div class="alert alert-light text-center">
                <i class="bi bi-emoji-frown"></i> У вас пока нет вайберов
            </div>
        {% endif %}
    </div>
</div>
{% endblock %}
    """,

    'friends.html': """
{% extends "base.html" %}
{% block content %}
<div class="row justify-content-center">
    <div class="col-md-8">
        <h3 class="mb-4">Входящие запросы</h3>
        {% if requests %}
            {% for req in requests %}
            <div class="card p-3 mb-2 d-flex flex-row justify-content-between align-items-center">
                <div class="d-flex align-items-center">
                    <div class="avatar me-3">
                        {% if req.user.avatar %}
                            <img src="{{ req.user.avatar }}">
                        {% else %}
                            {{ req.user.username[0].upper() }}
                        {% endif %}
                    </div>
                    <h5>{{ req.user.username }}</h5>
                </div>
                <div>
                    <a href="{{ url_for('accept_friend', user_id=req.user.id) }}" class="btn btn-success btn-sm rounded-pill">Принять</a>
                    <a href="{{ url_for('remove_friend', user_id=req.user.id) }}" class="btn btn-outline-danger btn-sm rounded-pill">Отклонить</a>
                </div>
            </div>
            {% endfor %}
        {% else %}
            <div class="alert alert-light text-center">Нет новых запросов</div>
        {% endif %}
    </div>
</div>
{% endblock %}
    """,

    'messenger.html': """
{% extends "base.html" %}
{% block content %}
<div class="card" style="height: 85vh; overflow: hidden;">
    <div class="row g-0 h-100">
        <div class="col-md-4 border-end h-100 d-flex flex-column" style="background-color: var(--hover-bg);">
            <div class="p-3 border-bottom d-flex justify-content-between align-items-center">
                <h5 class="mb-0 fw-bold">Чаты</h5>
                <button class="btn btn-sm btn-outline-primary rounded-pill" data-bs-toggle="modal" data-bs-target="#createGroupModal">+ Группа</button>
            </div>
            <div class="overflow-auto flex-grow-1">
                <div class="p-2 text-uppercase text-muted small fw-bold">Личные</div>
                {% for friend in friends %}
                <a href="{{ url_for('messenger', type='private', chat_id=friend.id) }}" class="d-flex align-items-center p-3 text-decoration-none border-bottom hover-shadow" style="color: var(--text-color); background-color: var(--card-bg);">
                    <div class="avatar me-3 position-relative">
                        {% if friend.avatar %}
                            <img src="{{ friend.avatar }}">
                        {% else %}
                            {{ friend.username[0].upper() }}
                        {% endif %}
                        {% if friend.id in online_ids %}<span class="online-dot"></span>{% endif %}
                    </div>
                    <div>
                        <div class="fw-bold">{{ friend.username }}</div>
                    </div>
                </a>
                {% endfor %}
                <div class="p-2 text-uppercase text-muted small fw-bold mt-2">Группы</div>
                {% for group in groups %}
                <a href="{{ url_for('messenger', type='group', chat_id=group.id) }}" class="d-flex align-items-center p-3 text-decoration-none border-bottom hover-shadow" style="color: var(--text-color); background-color: var(--card-bg);">
                    <div class="avatar me-3 bg-info text-white">
                        <i class="bi bi-people-fill"></i>
                    </div>
                    <div>
                        <div class="fw-bold">{{ group.name }}</div>
                    </div>
                </a>
                {% endfor %}
            </div>
        </div>

        <div class="col-md-8 h-100 d-flex flex-column position-relative" style="background-color: var(--card-bg);">
            {% if active_chat %}
                <div class="p-3 border-bottom d-flex align-items-center justify-content-between shadow-sm" style="z-index: 10;">
                    <div class="d-flex align-items-center">
                        <div class="fw-bold fs-5">
                            {% if chat_type == 'private' %}
                                {{ active_chat.username }}
                            {% else %}
                                {{ active_chat.name }} (Группа)
                            {% endif %}
                        </div>
                    </div>
                </div>
                <div class="flex-grow-1 p-4 overflow-auto d-flex flex-column" id="chat-box"></div>
                <div id="typing-indicator" class="text-muted small px-4" style="display:none;">Печатает...</div>
                <div class="p-3 border-top" style="background-color: var(--hover-bg);">
                    <div class="d-flex gap-2 align-items-center">
                        <input type="hidden" id="chat_type" value="{{ chat_type }}">
                        <input type="hidden" id="chat_id" value="{{ active_chat.id }}">
                        <button id="emoji-btn" class="btn btn-outline-secondary rounded-circle">😊</button>
                        <input type="text" id="msg-input" class="form-control rounded-pill border-0 shadow-sm" placeholder="Написать..." autocomplete="off">
                        <button id="btn-record-msg" class="btn btn-danger rounded-circle shadow-sm"><i class="bi bi-mic-fill"></i></button>
                        <button id="btn-send-msg" class="btn btn-primary rounded-circle shadow-sm"><i class="bi bi-send-fill"></i></button>
                    </div>
                </div>
            {% else %}
                <div class="d-flex align-items-center justify-content-center h-100 text-muted">
                    <h4>Выберите чат</h4>
                </div>
            {% endif %}
        </div>
    </div>
</div>

<div class="modal fade" id="createGroupModal" tabindex="-1">
    <div class="modal-dialog">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title">Создать группу</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <form action="{{ url_for('create_group') }}" method="POST">
                <div class="modal-body">
                    <div class="mb-3">
                        <label>Название группы</label>
                        <input type="text" name="name" class="form-control" required>
                    </div>
                    <div class="mb-3">
                        <label>Описание</label>
                        <input type="text" name="description" class="form-control">
                    </div>
                    <div class="form-check mb-3">
                        <input class="form-check-input" type="checkbox" name="is_private" id="is_private">
                        <label class="form-check-label" for="is_private">Приватная группа</label>
                    </div>
                    <label>Выберите участников</label>
                    <div class="border rounded p-2" style="max-height: 200px; overflow-y: auto;">
                        {% for friend in friends %}
                        <div class="form-check">
                            <input class="form-check-input" type="checkbox" name="members" value="{{ friend.id }}" id="f{{ friend.id }}">
                            <label class="form-check-label" for="f{{ friend.id }}">
                                {{ friend.username }}
                            </label>
                        </div>
                        {% endfor %}
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="submit" class="btn btn-primary">Создать</button>
                </div>
            </form>
        </div>
    </div>
</div>

{% if active_chat %}
<script src="https://cdn.socket.io/4.7.2/socket.io.min.js"></script>
<script>
    const chatBox = document.getElementById('chat-box');
    const chatType = document.getElementById('chat_type').value;
    const chatId = parseInt(document.getElementById('chat_id').value);
    const msgInput = document.getElementById('msg-input');
    const sendBtn = document.getElementById('btn-send-msg');
    const recordBtn = document.getElementById('btn-record-msg');
    const emojiBtn = document.getElementById('emoji-btn');

    const roomId = chatType === 'private' ? `private_${Math.min({{ current_user.id }}, chatId)}_${Math.max({{ current_user.id }}, chatId)}` : `group_${chatId}`;

    async function sendMessage(text, voiceBlob = null) {
        const formData = new FormData();
        formData.append('type', chatType);
        formData.append('target_id', chatId);
        if (text) formData.append('body', text);
        if (voiceBlob) formData.append('voice', voiceBlob, 'voice.webm');

        await fetch(`/api/send_message`, { method: 'POST', body: formData });
        msgInput.value = '';
        loadMessages();
    }

    sendBtn.addEventListener('click', () => {
        if (msgInput.value) sendMessage(msgInput.value);
    });

    emojiBtn.addEventListener('click', () => {
        const emoji = prompt('Эмодзи (например 😄🔥❤️)');
        if (emoji) msgInput.value += emoji;
        msgInput.focus();
    });

    let mediaRecorder;
    let audioChunks = [];
    let isRecording = false;

    recordBtn.addEventListener('click', async () => {
        if (!isRecording) {
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                mediaRecorder = new MediaRecorder(stream);
                mediaRecorder.start();
                recordBtn.classList.remove('btn-danger');
                recordBtn.classList.add('btn-warning', 'blink');
                isRecording = true;
                mediaRecorder.addEventListener("dataavailable", event => { audioChunks.push(event.data); });
                mediaRecorder.addEventListener("stop", () => {
                    const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
                    sendMessage(null, audioBlob);
                    audioChunks = [];
                });
            } catch (err) { alert("Нужен микрофон!"); }
        } else {
            mediaRecorder.stop();
            recordBtn.classList.add('btn-danger');
            recordBtn.classList.remove('btn-warning', 'blink');
            isRecording = false;
        }
    });

    async function loadMessages() {
        try {
            const response = await fetch(`/api/messages?type=${chatType}&id=${chatId}`);
            const messages = await response.json();
            
            if (chatBox.childElementCount !== messages.length) {
                chatBox.innerHTML = ''; 
                messages.forEach(msg => {
                    const isMe = msg.sender_id == {{ current_user.id }};
                    const div = document.createElement('div');
                    
                    let senderHtml = '';
                    if (chatType === 'group' && !isMe) senderHtml = `<div class="sender-name">${msg.sender_name}</div>`;
                    
                    let contentHtml = '';
                    if (msg.body) contentHtml += `<div>${msg.body}</div>`;
                    if (msg.voice_url) contentHtml += `<audio controls src="${msg.voice_url}" style="height:30px; width:200px; margin-top:5px;"></audio>`;
                    let actionsHtml = '';
                    if (isMe && !msg.deleted_for_all) {
                        actionsHtml = `<div class="text-muted small mt-1">
                            <a href="#" onclick="editMessage(${msg.id});return false;">Редактировать</a> ·
                            <a href="#" onclick="deleteMessage(${msg.id}, 'all');return false;">Удалить у всех</a> ·
                            <a href="#" onclick="deleteMessage(${msg.id}, 'me');return false;">Удалить у меня</a>
                        </div>`;
                    }
                    let status = '';
                    if (isMe) {
                        if (msg.read_at) status = '✓✓';
                        else if (msg.delivered_at) status = '✓';
                    }

                    div.className = `d-flex flex-column ${isMe ? 'align-items-end' : 'align-items-start'} mb-2`;
                    div.innerHTML = `${senderHtml}<div class="msg-bubble ${isMe ? 'msg-sent' : 'msg-received'}">${contentHtml}<div class="text-muted small text-end">${msg.edited_at ? 'изменено' : ''} ${status}</div></div>${actionsHtml}`;
                    chatBox.appendChild(div);
                });
                chatBox.scrollTop = chatBox.scrollHeight;
            }
        } catch (e) { console.error(e); }
    }
    
    async function editMessage(id) {
        const text = prompt('Новый текст');
        if (!text) return;
        await fetch('/api/edit_message', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ id, text }) });
        loadMessages();
    }
    async function deleteMessage(id, mode) {
        await fetch('/api/delete_message', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ id, mode }) });
        loadMessages();
    }
    
    const socket = io();
    let typingTimeout = null;

    socket.on('connect', () => {
        socket.emit('join', { room: roomId });
        loadMessages();
        socket.emit('presence', { online: true });
    });

    socket.on('message', (data) => {
        if (data.room_id === roomId) {
            loadMessages();
        }
    });

    socket.on('typing', (data) => {
        if (data.room_id === roomId && data.user_id !== {{ current_user.id }}) {
            const t = document.getElementById('typing-indicator');
            if (t) { t.style.display = 'block'; }
            clearTimeout(typingTimeout);
            typingTimeout = setTimeout(() => { if (t) t.style.display = 'none'; }, 1500);
        }
    });

    document.getElementById('msg-input')?.addEventListener('input', () => {
        socket.emit('typing', { room_id: roomId, user_id: {{ current_user.id }} });
    });
</script>
{% endif %}
{% endblock %}
    """,
    'profile.html': """
{% extends "base.html" %} 
{% block content %} 
<div class="card overflow-hidden"> 
{% if user.banner %}
<div style="height: 180px; background-image: url('{{ user.banner }}'); background-size: cover; background-position: center;"></div>
{% else %}
<div style="height: 180px; background: linear-gradient(45deg, #4f46e5, #ec4899);"></div> 
{% endif %}
<div class="card-body position-relative pt-0 pb-4"> 
<div class="position-absolute start-0 ms-4" style="top: -60px;"> 
<div class="avatar avatar-xl"> 
{% if user.avatar %} <img src="{{ user.avatar }}" style="width: 120px; height: 120px; border-radius: 50%;"> {% else %} 
<div style="width: 120px; height: 120px; border-radius: 50%; background: var(--hover-bg); line-height: 120px; font-size: 50px;">
{{ user.username[0].upper() }}
</div>
{% endif %} 
{% if is_online %}<span class="online-dot"></span>{% endif %}
</div> 
</div> 
<div class="mt-5 pt-2 ms-2 d-flex justify-content-between align-items-start"> 
<div> 
<h2 class="fw-bold mb-0">
    {{ user.username }}
    {% if user.is_verified %}<i class="bi bi-patch-check-fill verified-icon"></i>{% endif %}
</h2> 
<p class="text-muted mb-2">{{ user.bio }}</p>
<div class="d-flex gap-3 mb-2">
    <span class="badge-vibers">
        <i class="bi bi-heart-fill"></i> {{ user.followers.count() }} вайберов
    </span>
    <span class="badge bg-secondary">
        {{ user.following.count() }} подписок
    </span>
</div>
</div> 
<div class="d-flex gap-2 flex-wrap"> 
{% if current_user.id != user.id %} 
    {% set is_following = namespace(value=False) %}
    {% for follow in user.followers.all() %}
        {% if follow.follower_id == current_user.id %}
            {% set is_following.value = True %}
        {% endif %}
    {% endfor %}
    
    {% if is_following.value %}
        <a href="{{ url_for('unfollow_user', user_id=user.id) }}" class="btn btn-outline-danger rounded-pill follow-btn px-4">
            <i class="bi bi-heart-fill"></i> Отписаться
        </a>
    {% else %}
        <a href="{{ url_for('follow_user', user_id=user.id) }}" class="btn btn-primary rounded-pill follow-btn px-4">
            <i class="bi bi-heart"></i> Вайбнуться
        </a>
    {% endif %}

    {% if friendship_status == 'accepted' %} 
    <a href="{{ url_for('messenger', type='private', chat_id=user.id) }}" class="btn btn-success rounded-pill px-4">Сообщение</a> 
    <a href="{{ url_for('remove_friend', user_id=user.id) }}" class="btn btn-outline-danger rounded-pill">Удалить из друзей</a> 
    {% elif friendship_status == 'pending_sent' %} 
    <button class="btn btn-secondary rounded-pill px-4" disabled>Запрос отправлен</button> 
    {% elif friendship_status == 'pending_received' %} 
    <a href="{{ url_for('accept_friend', user_id=user.id) }}" class="btn btn-success rounded-pill px-4">Принять</a> 
    {% else %} 
    <a href="{{ url_for('add_friend', user_id=user.id) }}" class="btn btn-outline-primary rounded-pill px-4">Добавить в друзья</a> 
    {% endif %} 

    {% if current_user.is_admin %}
        <a href="{{ url_for('admin_ban_user', user_id=user.id) }}" class="btn btn-danger rounded-pill">
            {% if user.is_banned %}Разбанить{% else %}ЗАБАНИТЬ{% endif %}
        </a>
        <a href="{{ url_for('admin_verify_user', user_id=user.id) }}" class="btn btn-info text-white rounded-pill">
            {% if user.is_verified %}Снять галку{% else %}Дать галку{% endif %}
        </a>
    {% endif %}
    <a href="{{ url_for('report', user_id=user.id) }}" class="btn btn-outline-danger rounded-pill">Пожаловаться</a>

{% else %} 
<a href="{{ url_for('settings') }}" class="btn btn-outline-secondary rounded-pill">Настройки</a> 
{% endif %} 
</div> 
</div> 
</div> 
</div> 
<div class="row"> 
<div class="col-md-8 mx-auto"> 
<h5 class="mb-3 ps-2">Публикации</h5> 
{% for post in posts %} 
{% include 'post_card.html' %}
{% endfor %} 
</div> 
</div> 
{% endblock %}
""",
    'settings.html': """
{% extends "base.html" %} 
{% block content %} 
<div class="row justify-content-center">
<div class="col-md-6">
<div class="card p-4">
<h3 class="mb-4">Настройки</h3>
<form action="{{ url_for('update_settings') }}" method="POST" enctype="multipart/form-data">
<div class="mb-4 text-center">
{% if current_user.avatar %}
<div class="avatar avatar-xl mx-auto mb-3">
    <img src="{{ current_user.avatar }}" style="width: 120px; height: 120px; border-radius: 50%;">
</div>
{% else %}
<div class="avatar avatar-xl mx-auto mb-3" style="width: 120px; height: 120px; line-height: 120px; font-size: 50px;">
    {{ current_user.username[0].upper() }}
</div>
{% endif %}
<label class="btn btn-sm btn-outline-primary rounded-pill">Изменить фото <input type="file" name="avatar" hidden accept="image/*"></label>
</div>
<div class="mb-4 text-center">
{% if current_user.banner %}
<img src="{{ current_user.banner }}" style="width:100%; border-radius:12px; max-height:160px; object-fit:cover;">
{% endif %}
<label class="btn btn-sm btn-outline-secondary rounded-pill mt-2">Баннер профиля <input type="file" name="banner" hidden accept="image/*"></label>
</div>
<div class="mb-3">
<label class="form-label text-muted small">Никнейм</label>
<input type="text" name="username" class="form-control" value="{{ current_user.username }}">
</div>
<div class="mb-4">
<label class="form-label text-muted small">Описание</label>
<textarea name="bio" class="form-control" rows="3">{{ current_user.bio }}</textarea>
</div>
<div class="mb-4">
<label class="form-label text-muted small">Тема оформления</label>
<select name="theme" class="form-select">
    <option value="light" {% if current_user.theme == 'light' %}selected{% endif %}>☀️ Светлая</option>
    <option value="dark" {% if current_user.theme == 'dark' %}selected{% endif %}>🌙 Тёмная</option>
</select>
</div>
<div class="mb-4">
<label class="form-label text-muted small">Цветовая схема</label>
<select name="color_theme" class="form-select">
    <option value="blue" {% if current_user.color_theme == 'blue' %}selected{% endif %}>Синяя</option>
    <option value="purple" {% if current_user.color_theme == 'purple' %}selected{% endif %}>Фиолетовая</option>
    <option value="orange" {% if current_user.color_theme == 'orange' %}selected{% endif %}>Оранжевая</option>
</select>
</div>
<button type="submit" class="btn btn-primary w-100 py-2 rounded-pill">Сохранить</button>
</form>
<div class="mt-3 text-center">
  <a href="{{ url_for('sessions') }}" class="text-decoration-none">История входов и устройства</a>
</div>
</div>
</div>
</div> 
{% endblock %}
""",
    'auth.html': """
{% extends "base.html" %}
{% block content %}
<div class="row justify-content-center">
  <div class="col-md-4">
    <div class="card p-4 mt-5">
      <h3 class="text-center">{{ title }}</h3>
      <form method="POST">
        {% if not is_login %}
        <input type="email" name="email" class="form-control mb-3" placeholder="Email" required>
        {% endif %}
        <input type="text" name="username" class="form-control mb-3" placeholder="Ник" required>
        <input type="password" name="password" class="form-control mb-3" placeholder="Пароль" required>
        <div class="mb-3">
          <label class="form-label text-muted small">Капча: {{ captcha_q }}</label>
          <input type="text" name="captcha" class="form-control" placeholder="Ответ" required>
        </div>
        <button class="btn btn-primary w-100">{{ title }}</button>
      </form>
      <div class="text-center mt-3">
        <a href="{{ url_for('login' if not is_login else 'register') }}">{{ 'Войти' if not is_login else 'Регистрация' }}</a>
      </div>
    </div>
  </div>
</div>
{% endblock %}
""",
    'notifications.html': """
{% extends "base.html" %}
{% block content %}
<div class="row justify-content-center">
  <div class="col-md-8">
    <h3 class="mb-3">Уведомления</h3>
    {% if notifications %}
      {% for n in notifications %}
      <div class="card p-3 mb-2 {% if not n.is_read %}border-primary{% endif %}">
        <div class="d-flex justify-content-between align-items-center">
          <div>
            <strong>{{ n.ntype }}</strong> — {{ n.message or '' }}
            {% if n.link %}<a href="{{ n.link }}" class="ms-2">Открыть</a>{% endif %}
          </div>
          <small class="text-muted">{{ n.timestamp|time_ago }}</small>
        </div>
      </div>
      {% endfor %}
    {% else %}
      <div class="alert alert-light text-center">Нет уведомлений</div>
    {% endif %}
  </div>
</div>
{% endblock %}
""",
    'admin_dashboard.html': """
{% extends "base.html" %}
{% block content %}
<div class="row">
  <div class="col-md-8">
    <h3 class="mb-3">Админ-дашборд</h3>
    <canvas id="usersChart" height="120"></canvas>
    <canvas id="postsChart" height="120" class="mt-4"></canvas>
  </div>
  <div class="col-md-4">
    <div class="card p-3 mb-3">
      <h5>Массовая рассылка</h5>
      <form method="POST" action="{{ url_for('admin_broadcast') }}">
        <textarea name="message" class="form-control mb-2" rows="3" placeholder="Сообщение всем"></textarea>
        <button class="btn btn-primary w-100">Отправить</button>
      </form>
    </div>
    <div class="card p-3">
      <a href="{{ url_for('admin_reports') }}" class="btn btn-outline-danger w-100">Жалобы</a>
    </div>
  </div>
</div>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<script>
const labels = {{ chart_labels|tojson }};
new Chart(document.getElementById('usersChart'), {
  type: 'line',
  data: { labels, datasets: [{ label: 'Новые пользователи', data: {{ users_data|tojson }}, borderColor:'#2563eb' }] }
});
new Chart(document.getElementById('postsChart'), {
  type: 'line',
  data: { labels, datasets: [{ label: 'Посты', data: {{ posts_data|tojson }}, borderColor:'#f97316' }] }
});
</script>
{% endblock %}
""",
    'reports.html': """
{% extends "base.html" %}
{% block content %}
<div class="row justify-content-center">
  <div class="col-md-8">
    <h3 class="mb-3">Жалобы</h3>
    {% for r in reports %}
    <div class="card p-3 mb-2">
      <div><strong>ID:</strong> {{ r.id }} · {{ r.reason }} · {{ r.status }}</div>
      <div class="text-muted small">{{ r.timestamp|time_ago }}</div>
    </div>
    {% endfor %}
  </div>
</div>
{% endblock %}
""",
    'sessions.html': """
{% extends "base.html" %}
{% block content %}
<div class="row justify-content-center">
  <div class="col-md-8">
    <h3 class="mb-3">Активные сеансы</h3>
    <a href="{{ url_for('logout_all') }}" class="btn btn-danger mb-3">Выйти со всех устройств</a>
    {% for s in sessions %}
    <div class="card p-3 mb-2">
      <div><strong>IP:</strong> {{ s.ip }} · <strong>Город:</strong> {{ s.city or '—' }}</div>
      <div class="text-muted small">{{ s.user_agent }}</div>
      <div class="text-muted small">Последняя активность: {{ s.last_seen|time_ago }}</div>
    </div>
    {% endfor %}
  </div>
</div>
{% endblock %}
""",
    'search.html': """
{% extends "base.html" %}
{% block content %}
<h3 class="mb-3">Результаты поиска: "{{ q }}"</h3>
<div class="row">
  <div class="col-md-4">
    <h5>Пользователи</h5>
    {% for u in users %}
    <div class="card p-2 mb-2">
      <a href="{{ url_for('profile', username=u.username) }}">{{ u.username }}</a>
    </div>
    {% endfor %}
    <h5 class="mt-4">Группы</h5>
    {% for g in groups %}
    <div class="card p-2 mb-2">
      {{ g.name }}
    </div>
    {% endfor %}
  </div>
  <div class="col-md-8">
    <h5>Посты и хэштеги</h5>
    {% for p in posts %}
      {% include 'post_card.html' %}
    {% endfor %}
  </div>
</div>
{% endblock %}
""",
    'story_view.html': """
{% extends "base.html" %}
{% block content %}
<div class="card p-3 text-center">
  {% if story.media_type == 'video' %}
    <video controls autoplay style="max-width:100%"><source src="{{ story.media_url }}"></video>
  {% else %}
    <img src="{{ story.media_url }}" style="max-width:100%; border-radius:12px;">
  {% endif %}
  <div class="text-muted mt-2">История исчезнет: {{ story.expires_at|time_ago }}</div>
</div>
{% endblock %}
""",
    'post_view.html': """
{% extends "base.html" %}
{% block content %}
<div class="row justify-content-center">
  <div class="col-md-8">
    {% include 'post_card.html' %}
  </div>
</div>
{% endblock %}
""",
    'users.html': """
{% extends "base.html" %} 
{% block content %} 
<h3 class="mb-4">Поиск людей</h3> 
<div class="row"> 
{% for u in users %} 
{% if u.id != current_user.id and u.username != 'admin' %} 
<div class="col-md-4 mb-3">
    <div class="card p-3">
        <div class="d-flex align-items-center mb-2">
            <div class="avatar me-3">
                {% if u.avatar %}
                    <img src="{{ u.avatar }}">
                {% else %}
                    {{ u.username[0].upper() }}
                {% endif %}
            </div>
            <div>
                <h5 class="mb-0">
                    {{ u.username }} 
                    {% if u.is_verified %}<i class="bi bi-patch-check-fill verified-icon"></i>{% endif %}
                </h5>
                <small class="text-muted">{{ u.followers.count() }} вайберов</small>
            </div>
        </div>
        <a href="{{ url_for('profile', username=u.username) }}" class="btn btn-sm btn-outline-primary rounded-pill w-100">Профиль</a>
    </div>
</div> 
{% endif %} 
{% endfor %} 
</div> 
{% endblock %}
"""
}

app.jinja_env.filters['from_json'] = json.loads
app.jinja_loader = jinja2.DictLoader(templates)

# --- ROUTES ---

@app.route('/')
@login_required
def index():
    # Умная лента: ранжирование по интересу, а не только по новизне
    following_ids = [f.following_id for f in current_user.following.all()]
    base_posts = Post.query.filter_by(is_moderated=True).order_by(Post.timestamp.desc()).limit(200).all()
    now = datetime.utcnow()
    ranked = []
    for p in base_posts:
        age_hours = max(1, (now - p.timestamp).total_seconds() / 3600)
        likes = len(p.likes_rel)
        comments = len(p.comments_rel)
        views = p.views or 0
        score = (likes * 3 + comments * 2 + views * 0.2) / age_hours
        if p.user_id in following_ids:
            score *= 1.5
        ranked.append((score, p))
    ranked.sort(key=lambda x: x[0], reverse=True)
    posts = [p for _, p in ranked][:10]
    
    for p in posts:
        view = PostView.query.filter_by(user_id=current_user.id, post_id=p.id).first()
        if not view:
            db.session.add(PostView(user_id=current_user.id, post_id=p.id))
            p.views += 1
    db.session.commit()
    stories = Story.query.filter(Story.expires_at > now).order_by(Story.created_at.desc()).limit(20).all()
    return render_template('index.html', posts=posts, stories=stories)

@app.route('/api/load_posts')
@login_required
def load_posts_api():
    """API для ленивой подгрузки постов"""
    page = request.args.get('page', 1, type=int)
    per_page = 10
    
    following_ids = [f.following_id for f in current_user.following.all()]
    base_posts = Post.query.filter_by(is_moderated=True).order_by(Post.timestamp.desc()).limit(400).all()
    now = datetime.utcnow()
    ranked = []
    for p in base_posts:
        age_hours = max(1, (now - p.timestamp).total_seconds() / 3600)
        likes = len(p.likes_rel)
        comments = len(p.comments_rel)
        views = p.views or 0
        score = (likes * 3 + comments * 2 + views * 0.2) / age_hours
        if p.user_id in following_ids:
            score *= 1.5
        ranked.append((score, p))
    ranked.sort(key=lambda x: x[0], reverse=True)
    items = [p for _, p in ranked][(page-1)*per_page:page*per_page]
    
    posts_html = []
    for post in items:
        # Отмечаем просмотр
        view = PostView.query.filter_by(user_id=current_user.id, post_id=post.id).first()
        if not view:
            db.session.add(PostView(user_id=current_user.id, post_id=post.id))
            post.views += 1
        
        posts_html.append(render_template('post_card.html', post=post))
    
    db.session.commit()
    return jsonify({'posts': posts_html})

@app.route('/profile/<username>')
@login_required
def profile(username):
    user = User.query.filter_by(username=username).first_or_404()
    posts = Post.query.filter_by(user_id=user.id).order_by(Post.timestamp.desc()).all()
    is_online = (datetime.utcnow() - (user.last_seen or datetime.utcnow())) < timedelta(minutes=5)
    status = None
    if current_user.id != user.id:
        friendship = Friendship.query.filter(
            ((Friendship.sender_id == current_user.id) & (Friendship.receiver_id == user.id)) |
            ((Friendship.sender_id == user.id) & (Friendship.receiver_id == current_user.id))
        ).first()
        if friendship:
            if friendship.status == 'accepted': status = 'accepted'
            elif friendship.sender_id == current_user.id: status = 'pending_sent'
            else: status = 'pending_received'
    return render_template('profile.html', user=user, posts=posts, friendship_status=status, is_online=is_online)

# --- ВАЙБЕРЫ (ПОДПИСКИ) ---
@app.route('/follow/<int:user_id>')
@login_required
def follow_user(user_id):
    if user_id == current_user.id:
        return redirect(request.referrer)
    
    existing = Follow.query.filter_by(follower_id=current_user.id, following_id=user_id).first()
    if not existing:
        db.session.add(Follow(follower_id=current_user.id, following_id=user_id))
        db.session.commit()
        create_notification(user_id, 'follow', f'{current_user.username} подписался на вас', link=url_for('profile', username=current_user.username), from_user_id=current_user.id)
        flash("Вы вайбнулись! 💜", "success")
    
    return redirect(request.referrer or url_for('index'))

@app.route('/unfollow/<int:user_id>')
@login_required
def unfollow_user(user_id):
    follow = Follow.query.filter_by(follower_id=current_user.id, following_id=user_id).first()
    if follow:
        db.session.delete(follow)
        db.session.commit()
        flash("Вы отписались", "info")
    
    return redirect(request.referrer or url_for('index'))

@app.route('/my_vibers')
@login_required
def my_vibers():
    """Страница с моими подписчиками (вайберами)"""
    follower_ids = [f.follower_id for f in current_user.followers.all()]
    followers = User.query.filter(User.id.in_(follower_ids)).all()
    return render_template('my_vibers.html', followers=followers)

# --- ПЕРЕКЛЮЧЕНИЕ ТЕМЫ ---
@app.route('/toggle_theme', methods=['POST'])
@login_required
def toggle_theme():
    current_user.theme = 'dark' if current_user.theme == 'light' else 'light'
    db.session.commit()
    return jsonify({'theme': current_user.theme})

# --- ГОЛОСОВАНИЕ В ОПРОСАХ ---
@app.route('/vote_poll/<int:poll_id>/<int:option_index>', methods=['POST'])
@login_required
def vote_poll(poll_id, option_index):
    poll = db.session.get(Poll, poll_id)
    if not poll:
        return jsonify({'error': 'Опрос не найден'}), 404
    
    # Проверяем, голосовал ли уже
    existing_vote = PollVote.query.filter_by(poll_id=poll_id, user_id=current_user.id).first()
    if existing_vote:
        return jsonify({'error': 'Вы уже голосовали'}), 400
    
    # Добавляем голос
    db.session.add(PollVote(poll_id=poll_id, user_id=current_user.id, option_index=option_index))
    
    # Обновляем счётчик
    votes = json.loads(poll.votes) if poll.votes else {}
    votes[str(option_index)] = votes.get(str(option_index), 0) + 1
    poll.votes = json.dumps(votes)
    
    db.session.commit()
    return jsonify({'success': True})

# --- АДМИНСКИЕ ФУНКЦИИ ---
@app.route('/admin/ban/<int:user_id>')
@login_required
def admin_ban_user(user_id):
    if not current_user.is_admin: abort(403)
    user = db.session.get(User, user_id)
    if user and user.username != 'admin':
        user.is_banned = not user.is_banned
        db.session.commit()
        flash(f"Пользователь {'забанен' if user.is_banned else 'разбанен'}", "warning")
    return redirect(url_for('profile', username=user.username))

@app.route('/admin/verify/<int:user_id>')
@login_required
def admin_verify_user(user_id):
    if not current_user.is_admin: abort(403)
    user = db.session.get(User, user_id)
    if user:
        user.is_verified = not user.is_verified
        db.session.commit()
        flash("Статус верификации изменен", "success")
    return redirect(url_for('profile', username=user.username))

# --- ДРУЗЬЯ ---
@app.route('/add_friend/<int:user_id>')
@login_required
def add_friend(user_id):
    if user_id == current_user.id: return redirect(request.referrer)
    existing = Friendship.query.filter(
        ((Friendship.sender_id == current_user.id) & (Friendship.receiver_id == user_id)) |
        ((Friendship.sender_id == user_id) & (Friendship.receiver_id == current_user.id))
    ).first()
    if not existing:
        db.session.add(Friendship(sender_id=current_user.id, receiver_id=user_id, status='pending'))
        db.session.commit()
        flash("Запрос отправлен", "success")
    return redirect(request.referrer)

@app.route('/accept_friend/<int:user_id>')
@login_required
def accept_friend(user_id):
    friendship = Friendship.query.filter_by(sender_id=user_id, receiver_id=current_user.id, status='pending').first()
    if friendship:
        friendship.status = 'accepted'
        db.session.commit()
        flash("Теперь вы друзья!", "success")
    return redirect(request.referrer)

@app.route('/remove_friend/<int:user_id>')
@login_required
def remove_friend(user_id):
    friendship = Friendship.query.filter(
        ((Friendship.sender_id == current_user.id) & (Friendship.receiver_id == user_id)) |
        ((Friendship.sender_id == user_id) & (Friendship.receiver_id == current_user.id))
    ).first()
    if friendship:
        db.session.delete(friendship)
        db.session.commit()
        flash("Удалено", "info")
    return redirect(request.referrer)

@app.route('/friends/requests')
@login_required
def friends_requests():
    pending = Friendship.query.filter_by(receiver_id=current_user.id, status='pending').all()
    reqs = []
    for p in pending:
        sender = db.session.get(User, p.sender_id)
        reqs.append({'user': sender})
    return render_template('friends.html', requests=reqs)

# --- МЕССЕНДЖЕР ---
@app.route('/messenger')
@login_required
def messenger():
    chat_type = request.args.get('type')
    chat_id = request.args.get('chat_id')
    
    friends_relations = Friendship.query.filter(
        (Friendship.status == 'accepted') & 
        ((Friendship.sender_id == current_user.id) | (Friendship.receiver_id == current_user.id))
    ).all()
    friends = []
    for f in friends_relations:
        uid = f.receiver_id if f.sender_id == current_user.id else f.sender_id
        u = db.session.get(User, uid)
        if u.username != 'admin':
            friends.append(u)
        
    groups = current_user.groups
    active_chat = None
    if chat_type == 'private' and chat_id:
        active_chat = db.session.get(User, int(chat_id))
    elif chat_type == 'group' and chat_id:
        active_chat = db.session.get(Group, int(chat_id))
        if active_chat and current_user not in active_chat.members:
             active_chat = None

    now = datetime.utcnow()
    online_ids = [u.id for u in friends if u.last_seen and (now - u.last_seen) < timedelta(minutes=5)]
    return render_template('messenger.html', friends=friends, groups=groups, active_chat=active_chat, chat_type=chat_type, online_ids=online_ids)

@app.route('/create_group', methods=['POST'])
@login_required
def create_group():
    name = request.form.get('name')
    description = request.form.get('description', '')
    is_private = True if request.form.get('is_private') else False
    member_ids = request.form.getlist('members')
    if name:
        group = Group(name=name, creator_id=current_user.id, description=description, is_private=is_private)
        group.members.append(current_user)
        for mid in member_ids:
            u = db.session.get(User, int(mid))
            if u: group.members.append(u)
        db.session.add(group)
        db.session.commit()
        db.session.add(GroupRole(group_id=group.id, user_id=current_user.id, role='admin'))
        db.session.commit()
        return redirect(url_for('messenger', type='group', chat_id=group.id))
    return redirect(url_for('messenger'))

@app.route('/api/messages')
@login_required
def get_messages():
    type_ = request.args.get('type')
    id_ = request.args.get('id')
    messages = []
    
    if type_ == 'private':
        messages = Message.query.filter(
            ((Message.sender_id == current_user.id) & (Message.recipient_id == id_)) |
            ((Message.sender_id == id_) & (Message.recipient_id == current_user.id))
        ).order_by(Message.timestamp.asc()).all()
    elif type_ == 'group':
        group = db.session.get(Group, id_)
        if group and current_user in group.members:
            messages = Message.query.filter_by(group_id=id_).order_by(Message.timestamp.asc()).all()

    result = []
    for m in messages:
        if m.deleted_for_all:
            continue
        deleted_for = json.loads(m.deleted_for) if m.deleted_for else []
        if current_user.id in deleted_for:
            continue
        if m.recipient_id == current_user.id and not m.delivered_at:
            m.delivered_at = datetime.utcnow()
        if m.recipient_id == current_user.id and not m.read_at:
            m.read_at = datetime.utcnow()
        result.append({
            'id': m.id,
            'body': m.body,
            'voice_url': m.voice_filename,
            'sender_id': m.sender_id,
            'sender_name': m.sender.username,
            'edited_at': m.edited_at,
            'delivered_at': m.delivered_at,
            'read_at': m.read_at,
            'deleted_for_all': m.deleted_for_all
        })
    db.session.commit()
    return jsonify(result)

@app.route('/api/send_message', methods=['POST'])
@login_required
def send_api_message():
    type_ = request.form.get('type')
    target_id = request.form.get('target_id')
    body = request.form.get('body')
    voice = request.files.get('voice')
    
    voice_url = None
    if voice:
        voice_url = upload_to_cloud(voice, resource_type="video")

    if not body and not voice_url:
        return jsonify({'error': 'Empty'}), 400

    msg = Message(sender_id=current_user.id, body=body, voice_filename=voice_url)
    if type_ == 'private':
        msg.recipient_id = target_id
    elif type_ == 'group':
        msg.group_id = target_id
        
    db.session.add(msg)
    db.session.commit()
    room = get_room(type_, target_id, current_user.id)
    socketio.emit('message', {'room_id': room}, to=room)
    return jsonify({'status': 'ok'})

@app.route('/api/edit_message', methods=['POST'])
@login_required
def edit_message_api():
    data = request.get_json(force=True)
    mid = data.get('id')
    text = data.get('text')
    msg = db.session.get(Message, mid)
    if msg and msg.sender_id == current_user.id and not msg.deleted_for_all:
        msg.body = text
        msg.edited_at = datetime.utcnow()
        db.session.commit()
        room = get_room('group' if msg.group_id else 'private', msg.group_id or msg.recipient_id, current_user.id)
        socketio.emit('message', {'room_id': room}, to=room)
        return jsonify({'ok': True})
    return jsonify({'ok': False}), 400

@app.route('/api/delete_message', methods=['POST'])
@login_required
def delete_message_api():
    data = request.get_json(force=True)
    mid = data.get('id')
    mode = data.get('mode')
    msg = db.session.get(Message, mid)
    if not msg: return jsonify({'ok': False}), 404
    if mode == 'all' and msg.sender_id == current_user.id:
        msg.deleted_for_all = True
    else:
        deleted_for = json.loads(msg.deleted_for) if msg.deleted_for else []
        if current_user.id not in deleted_for:
            deleted_for.append(current_user.id)
        msg.deleted_for = json.dumps(deleted_for)
    db.session.commit()
    room = get_room('group' if msg.group_id else 'private', msg.group_id or msg.recipient_id, msg.sender_id)
    socketio.emit('message', {'room_id': room}, to=room)
    return jsonify({'ok': True})

# --- ПОСТЫ И КОММЕНТАРИИ ---
@app.route('/add_voice_comment/<int:post_id>', methods=['POST'])
@login_required
def add_voice_comment(post_id):
    post = db.session.get(Post, post_id)
    if post and not post.comments_enabled:
        return jsonify({'error': 'Comments disabled'}), 400
    if 'voice' in request.files:
        url = upload_to_cloud(request.files['voice'], resource_type="video")
        if url:
            db.session.add(Comment(voice_filename=url, user_id=current_user.id, post_id=post_id))
            db.session.commit()
            return jsonify({'success': True})
    return jsonify({'error': 'No file'}), 400

@app.route('/users')
@login_required
def users_list():
    users = User.query.all()
    return render_template('users.html', users=users)

@app.route('/settings')
@login_required
def settings():
    return render_template('settings.html')

@app.route('/update_settings', methods=['POST'])
@login_required
def update_settings():
    username = request.form.get('username')
    bio = request.form.get('bio')
    theme = request.form.get('theme')
    color_theme = request.form.get('color_theme')
    file = request.files.get('avatar')
    banner = request.files.get('banner')
    
    if file and file.filename != '':
        url = upload_to_cloud(file, resource_type="image")
        if url: current_user.avatar = url
    if banner and banner.filename != '':
        url = upload_to_cloud(banner, resource_type="image")
        if url: current_user.banner = url
            
    if bio: current_user.bio = bio
    if theme and theme in ['light', 'dark']: 
        current_user.theme = theme
    if color_theme and color_theme in ['blue', 'purple', 'orange']:
        current_user.color_theme = color_theme
    if username and username != current_user.username:
        if not User.query.filter_by(username=username).first(): current_user.username = username
        else: flash("Ник занят")
    db.session.commit()
    return redirect(url_for('profile', username=current_user.username))

@app.route('/notifications')
@login_required
def notifications():
    notes = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.timestamp.desc()).all()
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({Notification.is_read: True})
    db.session.commit()
    return render_template('notifications.html', notifications=notes)

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if not current_user.is_admin: abort(403)
    # последние 14 дней
    labels = []
    users_data = []
    posts_data = []
    for i in range(13, -1, -1):
        day = (datetime.utcnow() - timedelta(days=i)).date()
        labels.append(day.strftime('%d.%m'))
        users_count = User.query.filter(func.date(User.created_at) == day).count()
        posts_count = Post.query.filter(func.date(Post.timestamp) == day).count()
        users_data.append(users_count)
        posts_data.append(posts_count)
    return render_template('admin_dashboard.html', chart_labels=labels, users_data=users_data, posts_data=posts_data)

@app.route('/admin/broadcast', methods=['POST'])
@login_required
def admin_broadcast():
    if not current_user.is_admin: abort(403)
    msg = request.form.get('message', '').strip()
    if msg:
        for u in User.query.all():
            create_notification(u.id, 'system', msg, link=url_for('index'), from_user_id=current_user.id)
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/reports')
@login_required
def admin_reports():
    if not current_user.is_admin: abort(403)
    reports = Report.query.order_by(Report.timestamp.desc()).all()
    return render_template('reports.html', reports=reports)

@app.route('/report')
@login_required
def report():
    post_id = request.args.get('post_id')
    user_id = request.args.get('user_id')
    reason = request.args.get('reason', 'Жалоба')
    r = Report(reporter_id=current_user.id, post_id=post_id, target_user_id=user_id, reason=reason)
    db.session.add(r)
    db.session.commit()
    flash("Жалоба отправлена", "info")
    return redirect(request.referrer or url_for('index'))

@app.route('/sessions')
@login_required
def sessions():
    sessions = UserSession.query.filter_by(user_id=current_user.id, is_active=True).order_by(UserSession.last_seen.desc()).all()
    return render_template('sessions.html', sessions=sessions)

@app.route('/search')
@login_required
def search():
    q = request.args.get('q', '').strip()
    users = []
    posts = []
    groups = []
    if q:
        if q.startswith('#'):
            tag = q[1:]
            posts = Post.query.filter(Post.content.ilike(f'%#{tag}%')).order_by(Post.timestamp.desc()).limit(20).all()
        else:
            users = User.query.filter(User.username.ilike(f'%{q}%')).limit(20).all()
            posts = Post.query.filter(Post.content.ilike(f'%{q}%')).order_by(Post.timestamp.desc()).limit(20).all()
            groups = Group.query.filter(Group.name.ilike(f'%{q}%')).limit(20).all()
    return render_template('search.html', q=q, users=users, posts=posts, groups=groups)

@app.route('/post/<int:post_id>')
@login_required
def post_view(post_id):
    post = db.session.get(Post, post_id)
    if not post: abort(404)
    return render_template('post_view.html', post=post)

@app.route('/edit_post/<int:post_id>', methods=['POST'])
@login_required
def edit_post(post_id):
    post = db.session.get(Post, post_id)
    if post and post.user_id == current_user.id:
        content = request.form.get('content')
        post.content = content
        post.edited_at = datetime.utcnow()
        db.session.commit()
    return redirect(url_for('post_view', post_id=post_id))

@app.route('/create_story', methods=['POST'])
@login_required
def create_story():
    file = request.files.get('story_media')
    if file and file.filename != '':
        ext = file.filename.rsplit('.', 1)[1].lower()
        media_type = 'video' if ext in ['mp4', 'webm', 'mov'] else 'image'
        url = upload_to_cloud(file, resource_type="video" if media_type == 'video' else "image")
        if url:
            s = Story(user_id=current_user.id, media_url=url, media_type=media_type, expires_at=datetime.utcnow()+timedelta(hours=24))
            db.session.add(s)
            db.session.commit()
    return redirect(url_for('index'))

@app.route('/story/<int:story_id>')
@login_required
def view_story(story_id):
    story = db.session.get(Story, story_id)
    if not story or story.expires_at < datetime.utcnow(): abort(404)
    view = StoryView.query.filter_by(story_id=story_id, user_id=current_user.id).first()
    if not view:
        db.session.add(StoryView(story_id=story_id, user_id=current_user.id))
        db.session.commit()
    return render_template('story_view.html', story=story)

@app.route('/create_post', methods=['POST'])
@login_required
def create_post():
    content = request.form.get('content')
    files = request.files.getlist('media')
    image_url, video_url = None, None
    media_items = []
    
    # AI модерация контента
    is_ok, reason = moderate_content(content)
    
    if files:
        for file in files:
            if file and file.filename != '':
                ext = file.filename.rsplit('.', 1)[1].lower()
                if ext in ['mp4', 'webm', 'mov']:
                    url = upload_to_cloud(file, resource_type="video")
                    if url: media_items.append(('video', url))
                else:
                    url = upload_to_cloud(file, resource_type="image")
                    if url: media_items.append(('image', url))
        if media_items:
            # Для обратной совместимости (первый файл)
            if media_items[0][0] == 'video':
                video_url = media_items[0][1]
            else:
                image_url = media_items[0][1]
    
    # Создание опроса
    poll_question = request.form.get('poll_question')
    poll_data = None
    
    if poll_question:
        options = []
        for i in range(1, 7):
            opt = request.form.get(f'poll_option_{i}')
            if opt:
                options.append(opt)
        
        if len(options) >= 2:
            poll_data = {
                'question': poll_question,
                'options': options
            }
            
    # Со-автор
    co_author = request.form.get('co_author', '').replace('@','').strip()
    co_author_user = User.query.filter_by(username=co_author).first() if co_author else None
    comments_enabled = not bool(request.form.get('disable_comments'))

    if content or image_url or video_url or poll_data or media_items:
        post = Post(
            content=content, 
            image_filename=image_url, 
            video_filename=video_url, 
            author=current_user,
            co_author_id=co_author_user.id if co_author_user else None,
            comments_enabled=comments_enabled,
            is_moderated=is_ok,
            moderation_reason=reason if not is_ok else None
        )
        db.session.add(post)
        db.session.flush()

        for mtype, url in media_items:
            db.session.add(PostMedia(post_id=post.id, media_url=url, media_type=mtype))
        
        if poll_data:
            poll = Poll(
                post_id=post.id,
                question=poll_data['question'],
                options=json.dumps(poll_data['options']),
                votes=json.dumps({})
            )
            db.session.add(poll)
        
        db.session.commit()
        
        if not is_ok:
            flash(f"⚠️ Ваш пост заблокирован модерацией: {reason}", "warning")

        # Упоминания
        if content:
            mentions = set(re.findall(r'@([A-Za-z0-9_\\.]+)', content))
            for uname in mentions:
                u = User.query.filter_by(username=uname).first()
                if u:
                    create_notification(u.id, 'mention', f'Вас упомянули в посте {current_user.username}', link=url_for('post_view', post_id=post.id), from_user_id=current_user.id)
        if co_author_user:
            create_notification(co_author_user.id, 'collab', f'Вас добавили со‑автором поста', link=url_for('post_view', post_id=post.id), from_user_id=current_user.id)
    
    return redirect(url_for('index'))

@app.route('/delete_post/<int:post_id>')
@login_required
def delete_post(post_id):
    post = db.session.get(Post, post_id)
    if post and (post.author.id == current_user.id or current_user.is_admin):
        db.session.delete(post)
        db.session.commit()
    return redirect(url_for('index'))

@app.route('/like/<int:post_id>', methods=['POST'])
@login_required
def like_post(post_id):
    existing = Like.query.filter_by(user_id=current_user.id, post_id=post_id).first()
    if existing: db.session.delete(existing)
    else:
        db.session.add(Like(user_id=current_user.id, post_id=post_id))
        post = db.session.get(Post, post_id)
        if post and post.user_id != current_user.id:
            create_notification(post.user_id, 'like', f'{current_user.username} лайкнул ваш пост', link=url_for('post_view', post_id=post.id), from_user_id=current_user.id)
    db.session.commit()
    return redirect(request.referrer)

@app.route('/add_comment/<int:post_id>', methods=['POST'])
@login_required
def add_comment(post_id):
    text = request.form.get('text')
    post = db.session.get(Post, post_id)
    if post and not post.comments_enabled:
        return redirect(url_for('index'))
    
    # AI модерация комментариев
    is_ok, reason = moderate_content(text)
    
    if text and is_ok:
        db.session.add(Comment(text=text, user_id=current_user.id, post_id=post_id))
        db.session.commit()
        if post and post.user_id != current_user.id:
            create_notification(post.user_id, 'comment', f'{current_user.username} прокомментировал ваш пост', link=url_for('post_view', post_id=post.id), from_user_id=current_user.id)
        if text:
            mentions = set(re.findall(r'@([A-Za-z0-9_\\.]+)', text))
            for uname in mentions:
                u = User.query.filter_by(username=uname).first()
                if u:
                    create_notification(u.id, 'mention', f'Вас упомянули в комментарии', link=url_for('post_view', post_id=post_id), from_user_id=current_user.id)
    elif not is_ok:
        flash(f"⚠️ Комментарий заблокирован: {reason}", "warning")
    
    return redirect(url_for('index'))

@app.route('/delete_comment/<int:comment_id>')
@login_required
def delete_comment(comment_id):
    comment = db.session.get(Comment, comment_id)
    if comment and (comment.user_id == current_user.id or comment.post.user_id == current_user.id or current_user.is_admin):
        db.session.delete(comment)
        db.session.commit()
    return redirect(url_for('index'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        if not validate_captcha(request.form.get('captcha')):
            flash("Неверная капча", "danger")
            return redirect(url_for('register'))
        if User.query.filter_by(email=request.form.get('email')).first(): return redirect(url_for('register'))
        new_user = User(email=request.form.get('email'), username=request.form.get('username'), password=generate_password_hash(request.form.get('password')))
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)
        token = uuid.uuid4().hex
        session['session_token'] = token
        ip = get_client_ip()
        db.session.add(UserSession(user_id=new_user.id, session_token=token, ip=ip, city=guess_city(ip), user_agent=request.headers.get('User-Agent')))
        db.session.commit()
        return redirect(url_for('index'))
    captcha_q = generate_captcha()
    return render_template('auth.html', title="Регистрация", is_login=False, captcha_q=captcha_q)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if not validate_captcha(request.form.get('captcha')):
            flash("Неверная капча", "danger")
            return redirect(url_for('login'))
        user = User.query.filter_by(username=request.form.get('username')).first()
        if user and check_password_hash(user.password, request.form.get('password')):
            if user.is_banned:
                flash("Вы забанены.", "danger")
            else:
                login_user(user)
                token = uuid.uuid4().hex
                session['session_token'] = token
                ip = get_client_ip()
                db.session.add(UserSession(user_id=user.id, session_token=token, ip=ip, city=guess_city(ip), user_agent=request.headers.get('User-Agent')))
                db.session.commit()
                return redirect(url_for('index'))
    captcha_q = generate_captcha()
    return render_template('auth.html', title="Вход", is_login=True, captcha_q=captcha_q)

@app.route('/logout')
@login_required
def logout():
    token = session.get('session_token')
    if token:
        sess = UserSession.query.filter_by(session_token=token, user_id=current_user.id).first()
        if sess:
            sess.is_active = False
            db.session.commit()
    session.pop('session_token', None)
    logout_user()
    return redirect(url_for('login'))

@app.route('/logout_all')
@login_required
def logout_all():
    UserSession.query.filter_by(user_id=current_user.id, is_active=True).update({UserSession.is_active: False})
    db.session.commit()
    session.pop('session_token', None)
    logout_user()
    return redirect(url_for('login'))

# --- SOCKET.IO ---
@socketio.on('join')
def on_join(data):
    room = data.get('room')
    join_room(room)

@socketio.on('typing')
def on_typing(data):
    room = data.get('room_id')
    emit('typing', data, to=room)

@socketio.on('presence')
def on_presence(data):
    emit('presence', {'user_id': current_user.id, 'online': data.get('online', True)}, broadcast=True)

# --- СОЗДАНИЕ ТАБЛИЦ И АДМИНА ---
with app.app_context():
    db.create_all()
    
    # --- ВРЕМЕННЫЙ ФИКС БАЗЫ ДАННЫХ (ЛЕЧЕНИЕ ОШИБКИ) ---
    # Этот блок добавит недостающие колонки в существующую базу на Render
    from sqlalchemy import text
    try:
        with db.engine.connect() as conn:
            conn.execute(text("ALTER TABLE posts ADD COLUMN IF NOT EXISTS is_moderated BOOLEAN DEFAULT TRUE;"))
            conn.execute(text("ALTER TABLE posts ADD COLUMN IF NOT EXISTS moderation_reason VARCHAR(200);"))
            conn.execute(text("ALTER TABLE posts ADD COLUMN IF NOT EXISTS edited_at TIMESTAMP;"))
            conn.execute(text("ALTER TABLE posts ADD COLUMN IF NOT EXISTS co_author_id INTEGER;"))
            conn.execute(text("ALTER TABLE posts ADD COLUMN IF NOT EXISTS comments_enabled BOOLEAN DEFAULT TRUE;"))

            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS banner VARCHAR(300);"))
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS color_theme VARCHAR(20) DEFAULT 'blue';"))
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT NOW();"))
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS last_seen TIMESTAMP DEFAULT NOW();"))

            conn.execute(text("ALTER TABLE messages ADD COLUMN IF NOT EXISTS edited_at TIMESTAMP;"))
            conn.execute(text("ALTER TABLE messages ADD COLUMN IF NOT EXISTS delivered_at TIMESTAMP;"))
            conn.execute(text("ALTER TABLE messages ADD COLUMN IF NOT EXISTS read_at TIMESTAMP;"))
            conn.execute(text("ALTER TABLE messages ADD COLUMN IF NOT EXISTS deleted_for_all BOOLEAN DEFAULT FALSE;"))
            conn.execute(text("ALTER TABLE messages ADD COLUMN IF NOT EXISTS deleted_for TEXT DEFAULT '[]';"))

            conn.execute(text("ALTER TABLE groups ADD COLUMN IF NOT EXISTS description VARCHAR(300);"))
            conn.execute(text("ALTER TABLE groups ADD COLUMN IF NOT EXISTS is_private BOOLEAN DEFAULT FALSE;"))
            conn.commit()
            print(">>> УСПЕШНО: Колонки добавлены в базу данных! <<<")
    except Exception as e:
        print(f">>> INFO (не ошибка): {e}")
    # ---------------------------------------------------

    # Создание админа
    admin = User.query.filter_by(username='admin').first()
    if not admin:
        print("Создаю админа...")
        admin = User(
            username='admin',
            email='admin@fontan.local',
            password=generate_password_hash('12we1qtr11'),
            is_admin=True,
            is_verified=True,
            bio="Главный Администратор",
            theme='dark'
        )
        db.session.add(admin)
        db.session.commit()
        print("Админ создан: admin / 12we1qtr11")

if __name__ == '__main__':
    # Для Render важно использовать host='0.0.0.0' и порт из окружения
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host='0.0.0.0', port=port, debug=False)
