import os
import uuid
import json
from datetime import datetime
from flask import Flask, render_template, redirect, url_for, request, flash, send_from_directory, jsonify, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import or_, and_, desc
import jinja2

# --- НАСТРОЙКИ ---
app = Flask(__name__)
app.config['SECRET_KEY'] = 'fontan_ultra_fixed_v8'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///fontan_v8.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'webm', 'mp3', 'wav', 'ogg'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    try:
        os.makedirs(UPLOAD_FOLDER)
    except OSError:
        pass

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Простая AI модерация (проверка на запрещенные слова)
def moderate_content(text):
    if not text:
        return True
    bad_words = ['спам', 'реклама', 'казино', 'азарт']  # Добавь свои слова
    text_lower = text.lower()
    for word in bad_words:
        if word in text_lower:
            return False
    return True

# --- БАЗА ДАННЫХ ---

group_members = db.Table('group_members',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('group_id', db.Integer, db.ForeignKey('group.id'), primary_key=True)
)

# Таблица вайбиков (подписок)
vibes = db.Table('vibes',
    db.Column('follower_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('following_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('timestamp', db.DateTime, default=datetime.utcnow)
)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    bio = db.Column(db.String(300), default="Я тут новенький!")
    avatar = db.Column(db.String(200), default=None)
    theme = db.Column(db.String(10), default='light')  # Тема: light/dark
    
    posts = db.relationship('Post', backref='author', lazy=True)
    likes = db.relationship('Like', backref='user', lazy=True)
    groups = db.relationship('Group', secondary=group_members, backref=db.backref('members', lazy='dynamic'))
    
    # Вайбики (подписки)
    following = db.relationship('User', secondary=vibes,
                                primaryjoin=(vibes.c.follower_id == id),
                                secondaryjoin=(vibes.c.following_id == id),
                                backref=db.backref('followers', lazy='dynamic'),
                                lazy='dynamic')

class Friendship(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status = db.Column(db.String(20), default='pending')

class Group(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    creator_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    avatar = db.Column(db.String(200), default=None)

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=True)
    body = db.Column(db.Text, nullable=True)
    voice_filename = db.Column(db.String(200), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    sender = db.relationship('User', foreign_keys=[sender_id])

class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)

class PostView(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(500), nullable=True)
    voice_filename = db.Column(db.String(200), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    author = db.relationship('User', backref='comments')

# Таблица для опросов
class Poll(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question = db.Column(db.String(300), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)

class PollOption(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(200), nullable=False)
    poll_id = db.Column(db.Integer, db.ForeignKey('poll.id'), nullable=False)
    votes = db.relationship('PollVote', backref='option', cascade="all, delete-orphan")

class PollVote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    option_id = db.Column(db.Integer, db.ForeignKey('poll_option.id'), nullable=False)

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=True)
    image_filename = db.Column(db.String(200), nullable=True)
    video_filename = db.Column(db.String(200), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    views = db.Column(db.Integer, default=0)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    moderated = db.Column(db.Boolean, default=True)  # Прошел ли модерацию
    
    comments_rel = db.relationship('Comment', backref='post', cascade="all, delete-orphan", lazy=True)
    likes_rel = db.relationship('Like', backref='post', cascade="all, delete-orphan", lazy=True)
    views_rel = db.relationship('PostView', backref='post', cascade="all, delete-orphan", lazy=True)
    poll = db.relationship('Poll', backref='post', uselist=False, cascade="all, delete-orphan")

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# --- ШАБЛОНЫ ---
templates = {
    'base.html': """
<!DOCTYPE html>
<html lang="ru" data-bs-theme="{{ 'dark' if current_user.is_authenticated and current_user.theme == 'dark' else 'light' }}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Fontan V8</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.0/font/bootstrap-icons.css">
    <style>
        [data-bs-theme="dark"] {
            --bs-body-bg: #0d1117;
            --bs-body-color: #c9d1d9;
            --bs-card-bg: #161b22;
            --bs-border-color: #30363d;
        }
        
        body { 
            background-color: var(--bs-body-bg, #f0f2f5); 
            font-family: 'Segoe UI', sans-serif;
            transition: background-color 0.3s ease;
        }
        
        .navbar { 
            background: linear-gradient(135deg, #4f46e5, #7c3aed);
            transition: all 0.3s ease;
        }
        
        .card { 
            border: none; 
            border-radius: 16px; 
            box-shadow: 0 2px 5px rgba(0,0,0,0.05); 
            margin-bottom: 20px;
            transition: transform 0.2s ease, box-shadow 0.2s ease;
            background-color: var(--bs-card-bg, white);
        }
        
        .card:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        }
        
        .avatar { 
            width: 40px; 
            height: 40px; 
            border-radius: 50%; 
            object-fit: cover; 
            background: #ddd; 
            display: flex; 
            align-items: center; 
            justify-content: center; 
            font-weight: bold; 
            color: #555; 
            overflow: hidden;
            transition: transform 0.2s ease;
        }
        
        .avatar:hover {
            transform: scale(1.1);
        }
        
        .avatar img { width: 100%; height: 100%; object-fit: cover; }
        
        .msg-bubble { 
            padding: 8px 14px; 
            border-radius: 18px; 
            max-width: 75%; 
            margin-bottom: 4px; 
            position: relative;
            animation: fadeIn 0.3s ease;
        }
        
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        .msg-sent { background-color: #4f46e5; color: white; align-self: flex-end; border-bottom-right-radius: 4px; }
        .msg-received { background-color: #e5e7eb; color: black; align-self: flex-start; border-bottom-left-radius: 4px; }
        
        [data-bs-theme="dark"] .msg-received {
            background-color: #30363d;
            color: #c9d1d9;
        }
        
        .sender-name { font-size: 0.7rem; color: #666; margin-bottom: 2px; margin-left: 10px; }
        .blink { animation: blinker 1s linear infinite; } 
        @keyframes blinker { 50% { opacity: 0; } }
        
        .post-enter {
            animation: slideUp 0.4s ease;
        }
        
        @keyframes slideUp {
            from {
                opacity: 0;
                transform: translateY(20px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
        
        .btn {
            transition: all 0.2s ease;
        }
        
        .btn:hover {
            transform: scale(1.05);
        }
        
        .poll-option {
            transition: all 0.2s ease;
            cursor: pointer;
        }
        
        .poll-option:hover {
            background-color: rgba(79, 70, 229, 0.1);
        }
        
        .vibe-btn {
            transition: all 0.3s ease;
        }
        
        .vibe-btn.vibed {
            animation: pulse 0.5s ease;
        }
        
        @keyframes pulse {
            0%, 100% { transform: scale(1); }
            50% { transform: scale(1.2); }
        }
        
        .theme-toggle {
            cursor: pointer;
            font-size: 1.2rem;
            transition: transform 0.3s ease;
        }
        
        .theme-toggle:hover {
            transform: rotate(20deg);
        }
        
        .loading-spinner {
            text-align: center;
            padding: 20px;
        }
        
        .hover-shadow:hover {
            background-color: rgba(0,0,0,0.02);
        }
        
        [data-bs-theme="dark"] .hover-shadow:hover {
            background-color: rgba(255,255,255,0.05);
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
                        <i class="bi bi-{{ 'moon-fill' if current_user.theme == 'light' else 'sun-fill' }}"></i>
                    </span>
                    <a class="nav-link text-white fs-5" href="{{ url_for('messenger') }}"><i class="bi bi-chat-fill"></i></a>
                    <a class="nav-link text-white fs-5" href="{{ url_for('friends_requests') }}"><i class="bi bi-people-fill"></i></a>
                    <a class="nav-link text-white fs-5" href="{{ url_for('settings') }}"><i class="bi bi-gear-fill"></i></a>
                    <a class="nav-link text-white fs-5" href="{{ url_for('profile', username=current_user.username) }}">
                          <div class="avatar" style="width: 30px; height: 30px;">
                            {% if current_user.avatar %}
                                <img src="{{ url_for('uploaded_file', filename=current_user.avatar) }}">
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
                .then(() => location.reload());
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
                        <img src="{{ url_for('uploaded_file', filename=current_user.avatar) }}" style="width:100px; height:100px; border-radius:50%;">
                    {% else %}
                        <div style="width:100px; height:100px; border-radius:50%; background:#ccc; line-height:100px; font-size:40px; margin:0 auto;">
                        {{ current_user.username[0].upper() }}
                        </div>
                    {% endif %}
                </div>
                <h5>{{ current_user.username }}</h5>
                <div class="text-muted small">
                    <span><i class="bi bi-heart-fill text-danger"></i> {{ current_user.followers.count() }} вайбиков</span>
                </div>
            </div>
            <hr>
            <a href="{{ url_for('users_list') }}" class="btn btn-outline-primary w-100 mb-2 rounded-pill">Найти людей</a>
            <a href="{{ url_for('friends_requests') }}" class="btn btn-outline-success w-100 mb-2 rounded-pill">Запросы в друзья</a>
            <a href="{{ url_for('my_vibes') }}" class="btn btn-outline-danger w-100 mb-2 rounded-pill">Мои вайбики</a>
        </div>
    </div>

    <div class="col-md-6">
        <div class="card p-3">
            <form id="create-post-form" method="POST" action="{{ url_for('create_post') }}" enctype="multipart/form-data">
                <textarea name="content" class="form-control border-0 bg-light rounded-3 p-3" placeholder="Что нового?" rows="3"></textarea>
                
                <div id="poll-section" style="display:none;" class="mt-3 p-3 bg-light rounded">
                    <input type="text" name="poll_question" class="form-control mb-2" placeholder="Вопрос опроса">
                    <input type="text" name="poll_option1" class="form-control mb-2" placeholder="Вариант 1">
                    <input type="text" name="poll_option2" class="form-control mb-2" placeholder="Вариант 2">
                    <input type="text" name="poll_option3" class="form-control mb-2" placeholder="Вариант 3 (опционально)">
                    <input type="text" name="poll_option4" class="form-control mb-2" placeholder="Вариант 4 (опционально)">
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
        
        <div class="mb-3 d-flex gap-2 justify-content-center">
            <button class="btn btn-sm rounded-pill" id="feed-all" onclick="switchFeed('all')">Все посты</button>
            <button class="btn btn-sm btn-primary rounded-pill" id="feed-vibes" onclick="switchFeed('vibes')">Вайбики</button>
        </div>

        <div id="posts-container"></div>
        <div id="loading" class="loading-spinner" style="display:none;">
            <div class="spinner-border text-primary" role="status"></div>
        </div>
    </div>
</div>

<script>
let currentPage = 1;
let loading = false;
let hasMore = true;
let feedType = 'vibes';

function togglePoll() {
    const section = document.getElementById('poll-section');
    section.style.display = section.style.display === 'none' ? 'block' : 'none';
}

function switchFeed(type) {
    feedType = type;
    currentPage = 1;
    hasMore = true;
    document.getElementById('posts-container').innerHTML = '';
    
    document.getElementById('feed-all').className = 'btn btn-sm rounded-pill' + (type === 'all' ? ' btn-primary' : '');
    document.getElementById('feed-vibes').className = 'btn btn-sm rounded-pill' + (type === 'vibes' ? ' btn-primary' : '');
    
    loadPosts();
}

async function loadPosts() {
    if (loading || !hasMore) return;
    
    loading = true;
    document.getElementById('loading').style.display = 'block';
    
    try {
        const response = await fetch(`/api/posts?page=${currentPage}&type=${feedType}`);
        const data = await response.json();
        
        if (data.posts.length === 0) {
            hasMore = false;
            if (currentPage === 1) {
                document.getElementById('posts-container').innerHTML = '<div class="text-center py-5 text-muted"><p>Лента пуста.</p></div>';
            }
        } else {
            data.posts.forEach(post => {
                document.getElementById('posts-container').insertAdjacentHTML('beforeend', createPostHTML(post));
            });
            currentPage++;
        }
    } catch (e) {
        console.error(e);
    }
    
    loading = false;
    document.getElementById('loading').style.display = 'none';
}

function createPostHTML(post) {
    let pollHTML = '';
    if (post.poll) {
        pollHTML = `
            <div class="mt-3 p-3 bg-light rounded">
                <h6 class="mb-3"><i class="bi bi-bar-chart-fill"></i> ${post.poll.question}</h6>
                ${post.poll.options.map(opt => {
                    const total = post.poll.total_votes;
                    const percent = total > 0 ? Math.round((opt.votes / total) * 100) : 0;
                    return `
                        <div class="poll-option mb-2 p-2 rounded border ${post.poll.user_voted ? '' : ''}" 
                             onclick="${post.poll.user_voted ? '' : `vote(${opt.id})`}">
                            <div class="d-flex justify-content-between mb-1">
                                <span>${opt.text}</span>
                                <span class="text-muted">${opt.votes} (${percent}%)</span>
                            </div>
                            <div class="progress" style="height: 5px;">
                                <div class="progress-bar" style="width: ${percent}%"></div>
                            </div>
                        </div>
                    `;
                }).join('')}
                <small class="text-muted">Всего голосов: ${post.poll.total_votes}</small>
            </div>
        `;
    }
    
    return `
        <div class="card p-3 post-enter">
            <div class="d-flex justify-content-between align-items-start">
                <div class="d-flex align-items-center">
                    <a href="/profile/${post.author.username}" class="text-decoration-none">
                        <div class="avatar me-2">
                            ${post.author.avatar ? `<img src="/uploads/${post.author.avatar}">` : post.author.username[0].toUpperCase()}
                        </div>
                    </a>
                    <div>
                        <a href="/profile/${post.author.username}" class="fw-bold text-dark text-decoration-none">${post.author.username}</a>
                        <div class="text-muted small">${post.timestamp}</div>
                    </div>
                </div>
                ${post.is_author ? `<a class="text-danger" href="/delete_post/${post.id}"><i class="bi bi-trash"></i></a>` : ''}
            </div>
            
            <div class="mt-2">
                ${post.content ? `<p class="card-text fs-6">${post.content}</p>` : ''}
                ${post.image_filename ? `<img src="/uploads/${post.image_filename}" class="img-fluid rounded">` : ''}
                ${post.video_filename ? `<video controls class="img-fluid rounded"><source src="/uploads/${post.video_filename}"></video>` : ''}
            </div>
            
            ${pollHTML}

            <div class="d-flex align-items-center justify-content-between mt-3 pt-2 border-top">
                <div class="d-flex gap-4">
                    <form action="/like/${post.id}" method="POST">
                        <button class="btn p-0 text-secondary d-flex align-items-center gap-1">
                            <i class="bi ${post.user_liked ? 'bi-heart-fill text-danger' : 'bi-heart'} fs-5"></i>
                            <span>${post.likes}</span>
                        </button>
                    </form>
                    <div class="text-secondary d-flex align-items-center gap-1">
                        <i class="bi bi-chat fs-5"></i> <span>${post.comments_count}</span>
                    </div>
                </div>
                <div class="text-muted small"><i class="bi bi-eye"></i> ${post.views}</div>
            </div>

            <div class="mt-3 bg-light p-2 rounded-3">
                ${post.comments.map(c => `
                    <div class="mb-2 border-bottom pb-1">
                        <div class="d-flex justify-content-between">
                             <small><b>${c.author}</b>:</small>
                             ${c.can_delete ? `<a href="/delete_comment/${c.id}" class="text-danger small" style="text-decoration:none;">×</a>` : ''}
                        </div>
                        ${c.text ? `<div class="small">${c.text}</div>` : ''}
                        ${c.voice_filename ? `<audio controls style="height: 30px; width: 200px;" class="mt-1"><source src="/uploads/${c.voice_filename}"></audio>` : ''}
                    </div>
                `).join('')}
                <div class="mt-2">
                     <form action="/add_comment/${post.id}" method="POST" class="d-flex gap-1 align-items-center">
                        <input type="text" name="text" class="form-control form-control-sm rounded-pill" placeholder="Комментарий...">
                        <button type="button" class="btn btn-sm btn-danger btn-record-comment rounded-circle" data-post-id="${post.id}"><i class="bi bi-mic-fill"></i></button>
                        <button type="submit" class="btn btn-sm btn-primary rounded-circle"><i class="bi bi-send-fill"></i></button>
                     </form>
                </div>
            </div>
        </div>
    `;
}

async function vote(optionId) {
    await fetch(`/vote_poll/${optionId}`, { method: 'POST' });
    location.reload();
}

window.addEventListener('scroll', () => {
    if (window.innerHeight + window.scrollY >= document.body.offsetHeight - 500) {
        loadPosts();
    }
});

loadPosts();

// Логика записи комментариев
document.addEventListener('click', async (e) => {
    if (e.target.closest('.btn-record-comment')) {
        const btn = e.target.closest('.btn-record-comment');
        const postId = btn.dataset.postId;
        
        if (!btn.mediaRecorder) {
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                btn.mediaRecorder = new MediaRecorder(stream);
                btn.audioChunks = [];
                
                btn.mediaRecorder.addEventListener("dataavailable", event => { btn.audioChunks.push(event.data); });
                btn.mediaRecorder.addEventListener("stop", () => {
                    const audioBlob = new Blob(btn.audioChunks, { type: 'audio/webm' });
                    const formData = new FormData();
                    formData.append("voice", audioBlob, "voice.webm");
                    fetch(`/add_voice_comment/${postId}`, { method: 'POST', body: formData }).then(r => location.reload());
                });
                
                btn.mediaRecorder.start();
                btn.classList.remove('btn-danger');
                btn.classList.add('btn-warning', 'blink');
                btn.isRecording = true;
            } catch (err) { alert("Нет доступа к микрофону!"); }
        } else {
            btn.mediaRecorder.stop();
            btn.classList.add('btn-danger');
            btn.classList.remove('btn-warning', 'blink');
            btn.isRecording = false;
            btn.mediaRecorder = null;
        }
    }
});
</script>
{% endblock %}
    """,

    'my_vibes.html': """
{% extends "base.html" %}
{% block content %}
<div class="row justify-content-center">
    <div class="col-md-8">
        <h3 class="mb-4"><i class="bi bi-heart-fill text-danger"></i> Мои вайбики</h3>
        
        <ul class="nav nav-tabs mb-4">
            <li class="nav-item">
                <a class="nav-link {{ 'active' if tab == 'followers' else '' }}" href="{{ url_for('my_vibes', tab='followers') }}">
                    Подписчики ({{ followers|length }})
                </a>
            </li>
            <li class="nav-item">
                <a class="nav-link {{ 'active' if tab == 'following' else '' }}" href="{{ url_for('my_vibes', tab='following') }}">
                    Подписки ({{ following|length }})
                </a>
            </li>
        </ul>
        
        {% set users_list = followers if tab == 'followers' else following %}
        {% if users_list %}
            {% for user in users_list %}
            <div class="card p-3 mb-2 d-flex flex-row justify-content-between align-items-center">
                <div class="d-flex align-items-center">
                    <a href="{{ url_for('profile', username=user.username) }}" class="text-decoration-none">
                        <div class="avatar me-3">
                            {% if user.avatar %}
                                <img src="{{ url_for('uploaded_file', filename=user.avatar) }}">
                            {% else %}
                                {{ user.username[0].upper() }}
                            {% endif %}
                        </div>
                    </a>
                    <div>
                        <h5 class="mb-0">{{ user.username }}</h5>
                        <small class="text-muted">{{ user.bio }}</small>
                    </div>
                </div>
                <a href="{{ url_for('profile', username=user.username) }}" class="btn btn-primary btn-sm rounded-pill">Профиль</a>
            </div>
            {% endfor %}
        {% else %}
            <div class="alert alert-light text-center">Пока никого нет</div>
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
                            <img src="{{ url_for('uploaded_file', filename=req.user.avatar) }}">
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
        <div class="col-md-4 border-end h-100 d-flex flex-column bg-light">
            <div class="p-3 border-bottom d-flex justify-content-between align-items-center">
                <h5 class="mb-0 fw-bold">Чаты</h5>
                <button class="btn btn-sm btn-outline-primary rounded-pill" data-bs-toggle="modal" data-bs-target="#createGroupModal">+ Группа</button>
            </div>
            <div class="overflow-auto flex-grow-1">
                <div class="p-2 text-uppercase text-muted small fw-bold">Личные</div>
                {% for friend in friends %}
                <a href="{{ url_for('messenger', type='private', chat_id=friend.id) }}" class="d-flex align-items-center p-3 text-decoration-none text-dark border-bottom bg-white hover-shadow">
                    <div class="avatar me-3">
                        {% if friend.avatar %}
                            <img src="{{ url_for('uploaded_file', filename=friend.avatar) }}">
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
                <a href="{{ url_for('messenger', type='group', chat_id=group.id) }}" class="d-flex align-items-center p-3 text-decoration-none text-dark border-bottom bg-white hover-shadow">
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

        <div class="col-md-8 h-100 d-flex flex-column bg-white position-relative">
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
                <div class="p-3 border-top bg-light">
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
            <div class="avatar avatar-xl" style="width: 120px; height: 120px; font-size: 48px;">
                {% if user.avatar %}
                    <img src="{{ url_for('uploaded_file', filename=user.avatar) }}">
                {% else %}
                    {{ user.username[0].upper() }}
                {% endif %}
            </div>
        </div>
        <div class="mt-5 pt-2 ms-2 d-flex justify-content-between align-items-start">
            <div>
                <h2 class="fw-bold mb-0">{{ user.username }}</h2>
                <p class="text-muted mb-2">{{ user.bio }}</p>
                <div class="d-flex gap-3 text-muted small">
                    <span><i class="bi bi-heart-fill text-danger"></i> {{ user.followers.count() }} вайбиков</span>
                    <span><i class="bi bi-heart text-primary"></i> {{ user.following.count() }} подписок</span>
                </div>
            </div>
            <div class="d-flex gap-2 align-items-center">
                {% if current_user.id != user.id %}
                    <button class="btn rounded-pill vibe-btn {{ 'btn-danger vibed' if is_vibing else 'btn-outline-danger' }}" 
                            onclick="toggleVibe({{ user.id }}, this)">
                        <i class="bi bi-heart{{ '-fill' if is_vibing else '' }}"></i>
                        {{ 'Вайбнут' if is_vibing else 'Вайбнуться' }}
                    </button>
                    
                    {% if friendship_status == 'accepted' %}
                        <a href="{{ url_for('messenger', type='private', chat_id=user.id) }}" class="btn btn-primary rounded-pill px-4">Сообщение</a>
                        <a href="{{ url_for('remove_friend', user_id=user.id) }}" class="btn btn-outline-secondary rounded-pill">Удалить из друзей</a>
                    {% elif friendship_status == 'pending_sent' %}
                        <button class="btn btn-secondary rounded-pill px-4" disabled>Запрос отправлен</button>
                    {% elif friendship_status == 'pending_received' %}
                        <a href="{{ url_for('accept_friend', user_id=user.id) }}" class="btn btn-success rounded-pill px-4">Принять</a>
                    {% else %}
                        <a href="{{ url_for('add_friend', user_id=user.id) }}" class="btn btn-primary rounded-pill px-4">Добавить в друзья</a>
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
        <div class="card p-3">
            <div class="d-flex justify-content-between">
                <div class="text-muted small">{{ post.timestamp.strftime('%d.%m.%Y %H:%M:%S') }}</div>
                {% if post.author.id == current_user.id %}
                    <a href="{{ url_for('delete_post', post_id=post.id) }}" class="text-danger small text-decoration-none">Удалить</a>
                {% endif %}
            </div>
            <p class="mt-2">{{ post.content }}</p>
            {% if post.image_filename %}
                <img src="{{ url_for('uploaded_file', filename=post.image_filename) }}" class="img-fluid rounded">
            {% endif %}
            {% if post.video_filename %}
                <video controls class="img-fluid rounded"><source src="{{ url_for('uploaded_file', filename=post.video_filename) }}"></video>
            {% endif %}
        </div>
        {% endfor %}
    </div>
</div>

<script>
async function toggleVibe(userId, btn) {
    const response = await fetch(`/toggle_vibe/${userId}`, { method: 'POST' });
    const data = await response.json();
    
    if (data.vibing) {
        btn.className = 'btn rounded-pill vibe-btn btn-danger vibed';
        btn.innerHTML = '<i class="bi bi-heart-fill"></i> Вайбнут';
    } else {
        btn.className = 'btn rounded-pill vibe-btn btn-outline-danger';
        btn.innerHTML = '<i class="bi bi-heart"></i> Вайбнуться';
    }
}
</script>
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
                        <div class="avatar avatar-xl mx-auto mb-3" style="width: 120px; height: 120px;">
                            <img src="{{ url_for('uploaded_file', filename=current_user.avatar) }}">
                        </div>
                    {% else %}
                        <div class="avatar avatar-xl mx-auto mb-3" style="width: 120px; height: 120px; font-size: 48px;">
                            {{ current_user.username[0].upper() }}
                        </div>
                    {% endif %}
                    <label class="btn btn-sm btn-outline-primary rounded-pill">
                        Изменить фото 
                        <input type="file" name="avatar" hidden accept="image/*">
                    </label>
                </div>
                <div class="mb-3">
                    <label class="form-label text-muted small">Никнейм</label>
                    <input type="text" name="username" class="form-control" value="{{ current_user.username }}">
                </div>
                <div class="mb-4">
                    <label class="form-label text-muted small">Описание</label>
                    <textarea name="bio" class="form-control" rows="3">{{ current_user.bio }}</textarea>
                </div>
                <button type="submit" class="btn btn-primary w-100 py-2 rounded-pill">Сохранить</button>
            </form>
            
            <hr class="my-4">
            
            <a href="{{ url_for('logout') }}" class="btn btn-outline-danger w-100 rounded-pill">Выйти</a>
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
            <h3 class="text-center mb-4">{{ title }}</h3>
            <form method="POST">
                {% if not is_login %}
                    <input type="email" name="email" class="form-control mb-3" placeholder="Email" required>
                {% endif %}
                <input type="text" name="username" class="form-control mb-3" placeholder="Ник" required>
                <input type="password" name="password" class="form-control mb-3" placeholder="Пароль" required>
                <button class="btn btn-primary w-100 rounded-pill">{{ title }}</button>
            </form>
            <div class="text-center mt-3">
                <a href="{{ url_for('login' if not is_login else 'register') }}">
                    {{ 'Войти' if not is_login else 'Регистрация' }}
                </a>
            </div>
        </div>
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
        {% if u.id != current_user.id %}
        <div class="col-md-4 mb-3">
            <div class="card p-3">
                <div class="d-flex align-items-center mb-2">
                    <div class="avatar me-3">
                        {% if u.avatar %}
                            <img src="{{ url_for('uploaded_file', filename=u.avatar) }}">
                        {% else %}
                            {{ u.username[0].upper() }}
                        {% endif %}
                    </div>
                    <div>
                        <h5 class="mb-0">{{ u.username }}</h5>
                        <small class="text-muted">{{ u.followers.count() }} вайбиков</small>
                    </div>
                </div>
                <a href="{{ url_for('profile', username=u.username) }}" class="btn btn-sm btn-outline-primary rounded-pill w-100">
                    Профиль
                </a>
            </div>
        </div>
        {% endif %}
    {% endfor %}
</div>
{% endblock %}
    """
}

app.jinja_loader = jinja2.DictLoader(templates)

# --- ROUTES ---

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/')
@login_required
def index():
    return render_template('index.html')

@app.route('/api/posts')
@login_required
def get_posts_api():
    page = int(request.args.get('page', 1))
    feed_type = request.args.get('type', 'vibes')
    per_page = 5
    
    # Рекомендации: посты от тех, на кого подписан
    if feed_type == 'vibes':
        following_ids = [u.id for u in current_user.following.all()]
        following_ids.append(current_user.id)  # И свои посты
        query = Post.query.filter(Post.user_id.in_(following_ids), Post.moderated == True)
    else:
        query = Post.query.filter_by(moderated=True)
    
    posts = query.order_by(Post.timestamp.desc()).paginate(page=page, per_page=per_page, error_out=False)
    
    result = []
    for p in posts.items:
        # Счетчик просмотров
        view = PostView.query.filter_by(user_id=current_user.id, post_id=p.id).first()
        if not view:
            db.session.add(PostView(user_id=current_user.id, post_id=p.id))
            p.views += 1
    db.session.commit()
    
    for p in posts.items:
        poll_data = None
        if p.poll:
            options = PollOption.query.filter_by(poll_id=p.poll.id).all()
            total_votes = sum(len(opt.votes) for opt in options)
            user_voted = any(PollVote.query.filter_by(user_id=current_user.id, option_id=opt.id).first() for opt in options)
            
            poll_data = {
                'question': p.poll.question,
                'options': [{'id': opt.id, 'text': opt.text, 'votes': len(opt.votes)} for opt in options],
                'total_votes': total_votes,
                'user_voted': user_voted
            }
        
        comments = []
        for c in p.comments_rel[:3]:  # Показываем только 3 последних
            comments.append({
                'id': c.id,
                'author': c.author.username,
                'text': c.text,
                'voice_filename': c.voice_filename,
                'can_delete': c.user_id == current_user.id or p.user_id == current_user.id
            })
        
        result.append({
            'id': p.id,
            'content': p.content,
            'image_filename': p.image_filename,
            'video_filename': p.video_filename,
            'timestamp': p.timestamp.strftime('%d.%m.%Y %H:%M:%S'),
            'views': p.views,
            'likes': len(p.likes_rel),
            'user_liked': current_user.id in [like.user_id for like in p.likes_rel],
            'comments_count': len(p.comments_rel),
            'comments': comments,
            'author': {
                'username': p.author.username,
                'avatar': p.author.avatar
            },
            'is_author': p.author.id == current_user.id,
            'poll': poll_data
        })
    
    return jsonify({'posts': result})

@app.route('/toggle_theme', methods=['POST'])
@login_required
def toggle_theme():
    current_user.theme = 'dark' if current_user.theme == 'light' else 'light'
    db.session.commit()
    return jsonify({'theme': current_user.theme})

@app.route('/toggle_vibe/<int:user_id>', methods=['POST'])
@login_required
def toggle_vibe(user_id):
    user = db.session.get(User, user_id)
    if not user or user.id == current_user.id:
        return jsonify({'error': 'Invalid'}), 400
    
    if user in current_user.following:
        current_user.following.remove(user)
        vibing = False
    else:
        current_user.following.append(user)
        vibing = True
    
    db.session.commit()
    return jsonify({'vibing': vibing})

@app.route('/my_vibes')
@login_required
def my_vibes():
    tab = request.args.get('tab', 'followers')
    followers = list(current_user.followers.all())
    following = list(current_user.following.all())
    return render_template('my_vibes.html', tab=tab, followers=followers, following=following)

@app.route('/vote_poll/<int:option_id>', methods=['POST'])
@login_required
def vote_poll(option_id):
    option = db.session.get(PollOption, option_id)
    if not option:
        return jsonify({'error': 'Not found'}), 404
    
    # Проверяем, не голосовал ли уже
    poll = db.session.get(Poll, option.poll_id)
    all_options = PollOption.query.filter_by(poll_id=poll.id).all()
    for opt in all_options:
        existing = PollVote.query.filter_by(user_id=current_user.id, option_id=opt.id).first()
        if existing:
            return jsonify({'error': 'Already voted'}), 400
    
    vote = PollVote(user_id=current_user.id, option_id=option_id)
    db.session.add(vote)
    db.session.commit()
    return jsonify({'success': True})

@app.route('/profile/<username>')
@login_required
def profile(username):
    user = User.query.filter_by(username=username).first_or_404()
    posts = Post.query.filter_by(user_id=user.id, moderated=True).order_by(Post.timestamp.desc()).all()
    
    status = None
    if current_user.id != user.id:
        friendship = Friendship.query.filter(
            ((Friendship.sender_id == current_user.id) & (Friendship.receiver_id == user.id)) |
            ((Friendship.sender_id == user.id) & (Friendship.receiver_id == current_user.id))
        ).first()
        if friendship:
            if friendship.status == 'accepted':
                status = 'accepted'
            elif friendship.sender_id == current_user.id:
                status = 'pending_sent'
            else:
                status = 'pending_received'
    
    is_vibing = user in current_user.following
    
    return render_template('profile.html', user=user, posts=posts, friendship_status=status, is_vibing=is_vibing)

# --- ДРУЗЬЯ ---
@app.route('/add_friend/<int:user_id>')
@login_required
def add_friend(user_id):
    if user_id == current_user.id:
        return redirect(request.referrer)
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
        friends.append(db.session.get(User, uid))
        
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
            if u:
                group.members.append(u)
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
        voice_url = url_for('uploaded_file', filename=m.voice_filename) if m.voice_filename else None
        result.append({
            'body': m.body,
            'voice_url': voice_url,
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
    
    voice_filename = None
    if voice:
        filename = f"msg_voice_{uuid.uuid4()}.webm"
        voice.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        voice_filename = filename

    if not body and not voice_filename:
        return jsonify({'error': 'Empty'}), 400

    msg = Message(sender_id=current_user.id, body=body, voice_filename=voice_filename)
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
        file = request.files['voice']
        filename = f"comment_voice_{uuid.uuid4()}.webm"
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        db.session.add(Comment(voice_filename=filename, user_id=current_user.id, post_id=post_id))
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
    file = request.files.get('avatar')
    
    if file and file.filename != '' and allowed_file(file.filename):
        try:
            ext = file.filename.rsplit('.', 1)[1].lower()
            filename = f"avatar_{current_user.id}_{uuid.uuid4().hex[:8]}.{ext}"
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            current_user.avatar = filename
        except OSError:
            flash("Ошибка загрузки", "danger")
    
    if bio:
        current_user.bio = bio
    
    if username and username != current_user.username:
        if not User.query.filter_by(username=username).first():
            current_user.username = username
        else:
            flash("Ник занят")
    
    db.session.commit()
    return redirect(url_for('profile', username=current_user.username))

@app.route('/create_post', methods=['POST'])
@login_required
def create_post():
    content = request.form.get('content')
    file = request.files.get('media')
    
    # AI Модерация
    if not moderate_content(content):
        flash("Пост заблокирован модерацией за неприемлемый контент!", "danger")
        return redirect(url_for('index'))
    
    image_filename, video_filename = None, None
    if file and file.filename != '' and allowed_file(file.filename):
        ext = file.filename.rsplit('.', 1)[1].lower()
        filename = str(uuid.uuid4()) + '.' + ext
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        if ext in ['mp4', 'webm', 'mov']:
            video_filename = filename
        else:
            image_filename = filename
    
    if content or image_filename or video_filename:
        post = Post(content=content, image_filename=image_filename, video_filename=video_filename, author=current_user, moderated=True)
        db.session.add(post)
        db.session.flush()
        
        # Добавляем опрос если есть
        poll_question = request.form.get('poll_question')
        if poll_question:
            poll = Poll(question=poll_question, post_id=post.id)
            db.session.add(poll)
            db.session.flush()
            
            for i in range(1, 5):
                option_text = request.form.get(f'poll_option{i}')
                if option_text:
                    option = PollOption(text=option_text, poll_id=poll.id)
                    db.session.add(option)
        
        db.session.commit()
        flash("Пост опубликован!", "success")
    
    return redirect(url_for('index'))

@app.route('/delete_post/<int:post_id>')
@login_required
def delete_post(post_id):
    post = db.session.get(Post, post_id)
    if post and post.author.id == current_user.id:
        db.session.delete(post)
        db.session.commit()
    return redirect(url_for('profile', username=current_user.username))

@app.route('/like/<int:post_id>', methods=['POST'])
@login_required
def like_post(post_id):
    existing = Like.query.filter_by(user_id=current_user.id, post_id=post_id).first()
    if existing:
        db.session.delete(existing)
    else:
        db.session.add(Like(user_id=current_user.id, post_id=post_id))
    db.session.commit()
    return redirect(request.referrer)

@app.route('/add_comment/<int:post_id>', methods=['POST'])
@login_required
def add_comment(post_id):
    text = request.form.get('text')
    if text:
        db.session.add(Comment(text=text, user_id=current_user.id, post_id=post_id))
        db.session.commit()
    return redirect(url_for('index'))

@app.route('/delete_comment/<int:comment_id>')
@login_required
def delete_comment(comment_id):
    comment = db.session.get(Comment, comment_id)
    if comment and (comment.user_id == current_user.id or comment.post.user_id == current_user.id):
        db.session.delete(comment)
        db.session.commit()
    return redirect(url_for('index'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        if User.query.filter_by(email=request.form.get('email')).first():
            flash("Email уже используется", "danger")
            return redirect(url_for('register'))
        
        new_user = User(
            email=request.form.get('email'),
            username=request.form.get('username'),
            password=generate_password_hash(request.form.get('password'))
        )
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
            login_user(user)
            return redirect(url_for('index'))
        flash("Неверные данные", "danger")
    
    return render_template('auth.html', title="Вход", is_login=True)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5000)
