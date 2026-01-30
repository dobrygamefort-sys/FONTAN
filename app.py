import os
import uuid
import json
from datetime import datetime, timedelta
# Подключаем Cloudinary
import cloudinary
import cloudinary.uploader
import cloudinary.api

from flask import Flask, render_template, redirect, url_for, request, flash, jsonify, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import or_, and_, func
import jinja2

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
    """Простая AI модерация контента на запрещённые слова"""
    if not text:
        return True, ""
    
    forbidden_words = [
        'спам', 'реклама', 'казино', 'ставки', 'наркотики', 
        'оружие', 'взлом', 'hack', 'porn', 'sex'
    ]
    
    text_lower = text.lower()
    for word in forbidden_words:
        if word in text_lower:
            return False, f"Обнаружено запрещённое слово: {word}"
    
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
    theme = db.Column(db.String(10), default='light')
    
    # Поля админа
    is_admin = db.Column(db.Boolean, default=False)
    is_banned = db.Column(db.Boolean, default=False)
    is_verified = db.Column(db.Boolean, default=False)

    posts = db.relationship('Post', backref='author', lazy=True)
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
    views = db.Column(db.Integer, default=0)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    is_moderated = db.Column(db.Boolean, default=True)
    moderation_reason = db.Column(db.String(200), nullable=True)
    
    comments_rel = db.relationship('Comment', backref='post', cascade="all, delete-orphan", lazy=True)
    likes_rel = db.relationship('Like', backref='post', cascade="all, delete-orphan", lazy=True)
    views_rel = db.relationship('PostView', backref='post', cascade="all, delete-orphan", lazy=True)
    poll = db.relationship('Poll', backref='post', uselist=False, cascade="all, delete-orphan")

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# Проверка на бан
@app.before_request
def check_ban():
    if current_user.is_authenticated and current_user.is_banned:
        logout_user()
        flash("Ваш аккаунт заблокирован администрацией.", "danger")
        return redirect(url_for('login'))

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

# --- ШАБЛОНЫ ---
templates = {
    'base.html': """
<!DOCTYPE html>
<html lang="ru" data-theme="{{ current_user.theme if current_user.is_authenticated else 'light' }}">
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
        }
        
        :root[data-theme="dark"] {
            --bg-color: #18191a;
            --card-bg: #242526;
            --text-color: #e4e6eb;
            --text-muted: #b0b3b8;
            --border-color: #3a3b3c;
            --navbar-bg: linear-gradient(135deg, #3730a3, #5b21b6);
            --hover-bg: #3a3b3c;
        }
        
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
    </style>
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark sticky-top mb-4 shadow-sm">
        <div class="container">
            <a class="navbar-brand fw-bold" href="{{ url_for('index') }}"><i class="bi bi-droplet-fill"></i> Fontan</a>
            <div class="d-flex gap-3 align-items-center">
                {% if current_user.is_authenticated %}
                    <span class="theme-toggle text-white" onclick="toggleTheme()">
                        <i class="bi bi-moon-stars-fill" id="theme-icon"></i>
                    </span>
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
        </div>
    </div>

    <div class="col-md-6">
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
                            <input type="file" name="media" hidden accept="image/*,video/*">
                        </label>
                        <button type="button" class="btn btn-light text-success rounded-pill" onclick="togglePoll()">
                            <i class="bi bi-bar-chart-fill"></i> Опрос
                        </button>
                    </div>
                    <button type="submit" class="btn btn-primary rounded-pill px-4">Пост</button>
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
                <div class="text-muted small" style="font-size: 0.75rem;">{{ post.timestamp|time_ago }}</div>
            </div>
        </div>
        {% if post.author.id == current_user.id or current_user.is_admin %}
        <a class="text-danger" href="{{ url_for('delete_post', post_id=post.id) }}"><i class="bi bi-trash"></i></a>
        {% endif %}
    </div>
    
    {% if not post.is_moderated %}
    <div class="alert alert-warning mt-2 mb-2">
        <i class="bi bi-exclamation-triangle-fill"></i> Пост заблокирован модерацией: {{ post.moderation_reason }}
    </div>
    {% endif %}
    
    <div class="mt-2">
        {% if post.content %}<p class="card-text fs-6">{{ post.content }}</p>{% endif %}
        {% if post.image_filename %}
            <img src="{{ post.image_filename }}" class="post-media img-fluid rounded">
        {% endif %}
        {% if post.video_filename %}
            <video controls class="post-media img-fluid rounded"><source src="{{ post.video_filename }}"></video>
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
        </div>
        <div class="text-muted small"><i class="bi bi-eye"></i> {{ post.views }}</div>
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
        <div class="mt-2">
              <form action="{{ url_for('add_comment', post_id=post.id) }}" method="POST" class="d-flex gap-1 align-items-center">
                <input type="text" name="text" class="form-control form-control-sm rounded-pill" placeholder="Комментарий...">
                <button type="button" class="btn btn-sm btn-danger btn-record-comment rounded-circle" data-post-id="{{ post.id }}"><i class="bi bi-mic-fill"></i></button>
                <button type="submit" class="btn btn-sm btn-primary rounded-circle"><i class="bi bi-send-fill"></i></button>
              </form>
        </div>
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
                    <div class="avatar me-3">
                        {% if friend.avatar %}
                            <img src="{{ friend.avatar }}">
                        {% else %}
                            {{ friend.username[0].upper() }}
                        {% endif %}
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
                <div class="p-3 border-top" style="background-color: var(--hover-bg);">
                    <div class="d-flex gap-2 align-items-center">
                        <input type="hidden" id="chat_type" value="{{ chat_type }}">
                        <input type="hidden" id="chat_id" value="{{ active_chat.id }}">
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
<script>
    const chatBox = document.getElementById('chat-box');
    const chatType = document.getElementById('chat_type').value;
    const chatId = document.getElementById('chat_id').value;
    const msgInput = document.getElementById('msg-input');
    const sendBtn = document.getElementById('btn-send-msg');
    const recordBtn = document.getElementById('btn-record-msg');

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

                    div.className = `d-flex flex-column ${isMe ? 'align-items-end' : 'align-items-start'} mb-2`;
                    div.innerHTML = `${senderHtml}<div class="msg-bubble ${isMe ? 'msg-sent' : 'msg-received'}">${contentHtml}</div>`;
                    chatBox.appendChild(div);
                });
                chatBox.scrollTop = chatBox.scrollHeight;
            }
        } catch (e) { console.error(e); }
    }
    
    setInterval(loadMessages, 2000);
    loadMessages();
</script>
{% endif %}
{% endblock %}
    """,
    'profile.html': """
{% extends "base.html" %} 
{% block content %} 
<div class="card overflow-hidden"> 
<div style="height: 180px; background: linear-gradient(45deg, #4f46e5, #ec4899);"></div> 
<div class="card-body position-relative pt-0 pb-4"> 
<div class="position-absolute start-0 ms-4" style="top: -60px;"> 
<div class="avatar avatar-xl"> 
{% if user.avatar %} <img src="{{ user.avatar }}" style="width: 120px; height: 120px; border-radius: 50%;"> {% else %} 
<div style="width: 120px; height: 120px; border-radius: 50%; background: var(--hover-bg); line-height: 120px; font-size: 50px;">
{{ user.username[0].upper() }}
</div>
{% endif %} 
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
<button type="submit" class="btn btn-primary w-100 py-2 rounded-pill">Сохранить</button>
</form>
</div>
</div>
</div> 
{% endblock %}
""",
    'auth.html': """{% extends "base.html" %} {% block content %} <div class="row justify-content-center"><div class="col-md-4"><div class="card p-4 mt-5"><h3 class="text-center">{{ title }}</h3><form method="POST">{% if not is_login %}<input type="email" name="email" class="form-control mb-3" placeholder="Email" required>{% endif %}<input type="text" name="username" class="form-control mb-3" placeholder="Ник" required><input type="password" name="password" class="form-control mb-3" placeholder="Пароль" required><button class="btn btn-primary w-100">{{ title }}</button></form><div class="text-center mt-3"><a href="{{ url_for('login' if not is_login else 'register') }}">{{ 'Войти' if not is_login else 'Регистрация' }}</a></div></div></div></div> {% endblock %}""",
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
    # Рекомендательная лента: показываем посты от тех, на кого подписан пользователь
    following_ids = [f.following_id for f in current_user.following.all()]
    
    if following_ids:
        posts = Post.query.filter(
            Post.user_id.in_(following_ids),
            Post.is_moderated == True
        ).order_by(Post.timestamp.desc()).limit(10).all()
    else:
        # Если не на кого не подписан, показываем все посты
        posts = Post.query.filter_by(is_moderated=True).order_by(Post.timestamp.desc()).limit(10).all()
    
    for p in posts:
        view = PostView.query.filter_by(user_id=current_user.id, post_id=p.id).first()
        if not view:
            db.session.add(PostView(user_id=current_user.id, post_id=p.id))
            p.views += 1
    db.session.commit()
    return render_template('index.html', posts=posts)

@app.route('/api/load_posts')
@login_required
def load_posts_api():
    """API для ленивой подгрузки постов"""
    page = request.args.get('page', 1, type=int)
    per_page = 10
    
    following_ids = [f.following_id for f in current_user.following.all()]
    
    if following_ids:
        posts = Post.query.filter(
            Post.user_id.in_(following_ids),
            Post.is_moderated == True
        ).order_by(Post.timestamp.desc()).paginate(page=page, per_page=per_page, error_out=False)
    else:
        posts = Post.query.filter_by(is_moderated=True).order_by(Post.timestamp.desc()).paginate(page=page, per_page=per_page, error_out=False)
    
    posts_html = []
    for post in posts.items:
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
    return render_template('profile.html', user=user, posts=posts, friendship_status=status)

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

    return render_template('messenger.html', friends=friends, groups=groups, active_chat=active_chat, chat_type=chat_type)

@app.route('/create_group', methods=['POST'])
@login_required
def create_group():
    name = request.form.get('name')
    member_ids = request.form.getlist('members')
    if name:
        group = Group(name=name, creator_id=current_user.id)
        group.members.append(current_user)
        for mid in member_ids:
            u = db.session.get(User, int(mid))
            if u: group.members.append(u)
        db.session.add(group)
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
        result.append({
            'body': m.body,
            'voice_url': m.voice_filename,
            'sender_id': m.sender_id,
            'sender_name': m.sender.username
        })
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
    return jsonify({'status': 'ok'})

# --- ПОСТЫ И КОММЕНТАРИИ ---
@app.route('/add_voice_comment/<int:post_id>', methods=['POST'])
@login_required
def add_voice_comment(post_id):
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
    file = request.files.get('avatar')
    
    if file and file.filename != '':
        url = upload_to_cloud(file, resource_type="image")
        if url: current_user.avatar = url
            
    if bio: current_user.bio = bio
    if theme and theme in ['light', 'dark']: 
        current_user.theme = theme
    if username and username != current_user.username:
        if not User.query.filter_by(username=username).first(): current_user.username = username
        else: flash("Ник занят")
    db.session.commit()
    return redirect(url_for('profile', username=current_user.username))

@app.route('/create_post', methods=['POST'])
@login_required
def create_post():
    content = request.form.get('content')
    file = request.files.get('media')
    image_url, video_url = None, None
    
    # AI модерация контента
    is_ok, reason = moderate_content(content)
    
    if file and file.filename != '':
        ext = file.filename.rsplit('.', 1)[1].lower()
        if ext in ['mp4', 'webm', 'mov']:
            video_url = upload_to_cloud(file, resource_type="video")
        else:
            image_url = upload_to_cloud(file, resource_type="image")
    
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
            
    if content or image_url or video_url or poll_data:
        post = Post(
            content=content, 
            image_filename=image_url, 
            video_filename=video_url, 
            author=current_user,
            is_moderated=is_ok,
            moderation_reason=reason if not is_ok else None
        )
        db.session.add(post)
        db.session.flush()
        
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
    else: db.session.add(Like(user_id=current_user.id, post_id=post_id))
    db.session.commit()
    return redirect(request.referrer)

@app.route('/add_comment/<int:post_id>', methods=['POST'])
@login_required
def add_comment(post_id):
    text = request.form.get('text')
    
    # AI модерация комментариев
    is_ok, reason = moderate_content(text)
    
    if text and is_ok:
        db.session.add(Comment(text=text, user_id=current_user.id, post_id=post_id))
        db.session.commit()
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
        if User.query.filter_by(email=request.form.get('email')).first(): return redirect(url_for('register'))
        new_user = User(email=request.form.get('email'), username=request.form.get('username'), password=generate_password_hash(request.form.get('password')))
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)
        return redirect(url_for('index'))
    return render_template('auth.html', title="Регистрация", is_login=False)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form.get('username')).first()
        if user and check_password_hash(user.password, request.form.get('password')):
            if user.is_banned:
                flash("Вы забанены.", "danger")
            else:
                login_user(user)
                return redirect(url_for('index'))
    return render_template('auth.html', title="Вход", is_login=True)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# --- СОЗДАНИЕ ТАБЛИЦ И АДМИНА ---
with app.app_context():
    db.create_all()
    
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
    app.run(debug=True, port=5000)
