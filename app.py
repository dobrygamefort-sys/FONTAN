import os
import uuid
import json
from datetime import datetime
from flask import Flask, render_template, redirect, url_for, request, flash, send_from_directory, jsonify, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import or_, and_
import jinja2

# --- НАСТРОЙКИ ---
app = Flask(__name__)
app.config['SECRET_KEY'] = 'fontan_ultra_fixed_v7'

# --- НАСТРОЙКА NEON TECH (POSTGRESQL) ---
# 1. Сначала пытаемся взять URL из переменных окружения (для продакшена)
# 2. Если нет, используем заглушку (СЮДА ВСТАВЬ СВОЮ СТРОКУ ИЗ NEON ДЛЯ ЛОКАЛЬНОГО ТЕСТА)
NEON_DB_URL = os.environ.get('DATABASE_URL')

if not NEON_DB_URL:
    # ВСТАВЬ СЮДА СВОЮ СТРОКУ, например: "postgres://user:pass@ep-xyz.neon.tech/neondb?sslmode=require"
    NEON_DB_URL = 'postgresql://neondb_owner:npg_pIZeE3uY7XLF@ep-shy-field-ahelwpwv-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require' 

# Исправление для SQLAlchemy (Neon выдает postgres://, а библиотека требует postgresql://)
if NEON_DB_URL and NEON_DB_URL.startswith("postgres://"):
    NEON_DB_URL = NEON_DB_URL.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = NEON_DB_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024  # Увеличили до 32 МБ

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

# --- БАЗА ДАННЫХ ---

group_members = db.Table('group_members',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('group_id', db.Integer, db.ForeignKey('group.id'), primary_key=True)
)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    bio = db.Column(db.String(300), default="Я тут новенький!")
    avatar = db.Column(db.String(200), default=None)
    
    posts = db.relationship('Post', backref='author', lazy=True)
    likes = db.relationship('Like', backref='user', lazy=True)
    groups = db.relationship('Group', secondary=group_members, backref=db.backref('members', lazy='dynamic'))

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
    body = db.Column(db.Text, nullable=True) # Может быть пустым, если только голос
    voice_filename = db.Column(db.String(200), nullable=True) # Для голосовых
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    sender = db.relationship('User', foreign_keys=[sender_id])

class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)

class PostView(db.Model): # Новая таблица для уникальных просмотров
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

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=True)
    image_filename = db.Column(db.String(200), nullable=True)
    video_filename = db.Column(db.String(200), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    views = db.Column(db.Integer, default=0)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    comments_rel = db.relationship('Comment', backref='post', cascade="all, delete-orphan", lazy=True)
    likes_rel = db.relationship('Like', backref='post', cascade="all, delete-orphan", lazy=True)
    views_rel = db.relationship('PostView', backref='post', cascade="all, delete-orphan", lazy=True)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# --- ШАБЛОНЫ ---
templates = {
    'base.html': """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Fontan V3</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.0/font/bootstrap-icons.css">
    <style>
        body { background-color: #f0f2f5; font-family: 'Segoe UI', sans-serif; }
        .navbar { background: linear-gradient(135deg, #4f46e5, #7c3aed); }
        .card { border: none; border-radius: 16px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); margin-bottom: 20px; }
        .avatar { width: 40px; height: 40px; border-radius: 50%; object-fit: cover; background: #ddd; display: flex; align-items: center; justify-content: center; font-weight: bold; color: #555; overflow: hidden; }
        .avatar img { width: 100%; height: 100%; object-fit: cover; }
        .msg-bubble { padding: 8px 14px; border-radius: 18px; max-width: 75%; margin-bottom: 4px; position: relative; }
        .msg-sent { background-color: #4f46e5; color: white; align-self: flex-end; border-bottom-right-radius: 4px; }
        .msg-received { background-color: #e5e7eb; color: black; align-self: flex-start; border-bottom-left-radius: 4px; }
        .sender-name { font-size: 0.7rem; color: #666; margin-bottom: 2px; margin-left: 10px; }
        .blink { animation: blinker 1s linear infinite; } @keyframes blinker { 50% { opacity: 0; } }
    </style>
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark sticky-top mb-4 shadow-sm">
        <div class="container">
            <a class="navbar-brand fw-bold" href="{{ url_for('index') }}"><i class="bi bi-droplet-fill"></i> Fontan</a>
            <div class="d-flex gap-3 align-items-center">
                {% if current_user.is_authenticated %}
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
            </div>
            <hr>
            <a href="{{ url_for('users_list') }}" class="btn btn-outline-primary w-100 mb-2 rounded-pill">Найти людей</a>
            <a href="{{ url_for('friends_requests') }}" class="btn btn-outline-success w-100 mb-2 rounded-pill">Запросы в друзья</a>
        </div>
    </div>

    <div class="col-md-6">
        <div class="card p-3">
            <form method="POST" action="{{ url_for('create_post') }}" enctype="multipart/form-data">
                <textarea name="content" class="form-control border-0 bg-light rounded-3 p-3" placeholder="Что нового?" rows="3"></textarea>
                <div class="mt-3 d-flex justify-content-between align-items-center">
                    <label class="btn btn-light text-primary rounded-pill">
                        <i class="bi bi-camera-fill"></i> Медиа
                        <input type="file" name="media" hidden accept="image/*,video/*">
                    </label>
                    <button type="submit" class="btn btn-primary rounded-pill px-4">Пост</button>
                </div>
            </form>
        </div>

        {% for post in posts %}
        <div class="card p-3">
            <div class="d-flex justify-content-between align-items-start">
                <div class="d-flex align-items-center">
                    <a href="{{ url_for('profile', username=post.author.username) }}" class="text-decoration-none">
                        <div class="avatar me-2">
                            {% if post.author.avatar %}
                                <img src="{{ url_for('uploaded_file', filename=post.author.avatar) }}">
                            {% else %}
                                {{ post.author.username[0].upper() }}
                            {% endif %}
                        </div>
                    </a>
                    <div>
                        <a href="{{ url_for('profile', username=post.author.username) }}" class="fw-bold text-dark text-decoration-none">{{ post.author.username }}</a>
                        <div class="text-muted small" style="font-size: 0.75rem;">{{ post.timestamp.strftime('%d.%m %H:%M') }}</div>
                    </div>
                </div>
                {% if post.author.id == current_user.id %}
                <a class="text-danger" href="{{ url_for('delete_post', post_id=post.id) }}"><i class="bi bi-trash"></i></a>
                {% endif %}
            </div>
            
            <div class="mt-2">
                {% if post.content %}<p class="card-text fs-6">{{ post.content }}</p>{% endif %}
                {% if post.image_filename %}
                    <img src="{{ url_for('uploaded_file', filename=post.image_filename) }}" class="img-fluid rounded">
                {% endif %}
                {% if post.video_filename %}
                    <video controls class="img-fluid rounded"><source src="{{ url_for('uploaded_file', filename=post.video_filename) }}"></video>
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
                         <small><b>{{ comment.author.username }}</b>:</small>
                         {% if comment.user_id == current_user.id or post.user_id == current_user.id %}
                            <a href="{{ url_for('delete_comment', comment_id=comment.id) }}" class="text-danger small" style="text-decoration:none;">×</a>
                         {% endif %}
                    </div>
                    {% if comment.text %}<div class="small">{{ comment.text }}</div>{% endif %}
                    {% if comment.voice_filename %}
                        <audio controls style="height: 30px; width: 200px;" class="mt-1">
                            <source src="{{ url_for('uploaded_file', filename=comment.voice_filename) }}">
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
        {% else %}
        <div class="text-center py-5 text-muted"><p>Лента пуста.</p></div>
        {% endfor %}
    </div>
</div>

<script>
// Логика записи комментариев
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
</script>
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

    // Отправка текста
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

    // Запись голоса
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
    'profile.html': """{% extends "base.html" %} {% block content %} <div class="card overflow-hidden"> <div style="height: 180px; background: linear-gradient(45deg, #4f46e5, #ec4899);"></div> <div class="card-body position-relative pt-0 pb-4"> <div class="position-absolute start-0 ms-4" style="top: -60px;"> <div class="avatar avatar-xl"> {% if user.avatar %} <img src="{{ url_for('uploaded_file', filename=user.avatar) }}"> {% else %} {{ user.username[0].upper() }} {% endif %} </div> </div> <div class="mt-5 pt-2 ms-2 d-flex justify-content-between align-items-start"> <div> <h2 class="fw-bold mb-0">{{ user.username }}</h2> <p class="text-muted mb-2">{{ user.bio }}</p> </div> <div class="d-flex gap-2"> {% if current_user.id != user.id %} {% if friendship_status == 'accepted' %} <a href="{{ url_for('messenger', type='private', chat_id=user.id) }}" class="btn btn-primary rounded-pill px-4">Сообщение</a> <a href="{{ url_for('remove_friend', user_id=user.id) }}" class="btn btn-outline-danger rounded-pill">Удалить</a> {% elif friendship_status == 'pending_sent' %} <button class="btn btn-secondary rounded-pill px-4" disabled>Запрос отправлен</button> {% elif friendship_status == 'pending_received' %} <a href="{{ url_for('accept_friend', user_id=user.id) }}" class="btn btn-success rounded-pill px-4">Принять</a> {% else %} <a href="{{ url_for('add_friend', user_id=user.id) }}" class="btn btn-primary rounded-pill px-4">Добавить в друзья</a> {% endif %} {% else %} <a href="{{ url_for('settings') }}" class="btn btn-outline-secondary rounded-pill">Настройки</a> {% endif %} </div> </div> </div> </div> <div class="row"> <div class="col-md-8 mx-auto"> <h5 class="mb-3 ps-2">Публикации</h5> {% for post in posts %} <div class="card p-3"> <div class="d-flex justify-content-between"> <div class="text-muted small">{{ post.timestamp.strftime('%d.%m %H:%M') }}</div> {% if post.author.id == current_user.id %} <a href="{{ url_for('delete_post', post_id=post.id) }}" class="text-danger small text-decoration-none">Удалить</a> {% endif %} </div> <p class="mt-2">{{ post.content }}</p> {% if post.image_filename %} <img src="{{ url_for('uploaded_file', filename=post.image_filename) }}" class="post-media"> {% endif %} </div> {% endfor %} </div> </div> {% endblock %}""",
    'settings.html': """{% extends "base.html" %} {% block content %} <div class="row justify-content-center"><div class="col-md-6"><div class="card p-4"><h3 class="mb-4">Настройки</h3><form action="{{ url_for('update_settings') }}" method="POST" enctype="multipart/form-data"><div class="mb-4 text-center">{% if current_user.avatar %}<div class="avatar avatar-xl mx-auto mb-3"><img src="{{ url_for('uploaded_file', filename=current_user.avatar) }}"></div>{% else %}<div class="avatar avatar-xl mx-auto mb-3">{{ current_user.username[0].upper() }}</div>{% endif %}<label class="btn btn-sm btn-outline-primary rounded-pill">Изменить фото <input type="file" name="avatar" hidden accept="image/*"></label></div><div class="mb-3"><label class="form-label text-muted small">Никнейм</label><input type="text" name="username" class="form-control" value="{{ current_user.username }}"></div><div class="mb-4"><label class="form-label text-muted small">Описание</label><textarea name="bio" class="form-control" rows="3">{{ current_user.bio }}</textarea></div><button type="submit" class="btn btn-primary w-100 py-2 rounded-pill">Сохранить</button></form></div></div></div> {% endblock %}""",
    'auth.html': """{% extends "base.html" %} {% block content %} <div class="row justify-content-center"><div class="col-md-4"><div class="card p-4 mt-5"><h3 class="text-center">{{ title }}</h3><form method="POST">{% if not is_login %}<input type="email" name="email" class="form-control mb-3" placeholder="Email" required>{% endif %}<input type="text" name="username" class="form-control mb-3" placeholder="Ник" required><input type="password" name="password" class="form-control mb-3" placeholder="Пароль" required><button class="btn btn-primary w-100">{{ title }}</button></form><div class="text-center mt-3"><a href="{{ url_for('login' if not is_login else 'register') }}">{{ 'Войти' if not is_login else 'Регистрация' }}</a></div></div></div></div> {% endblock %}""",
    'users.html': """{% extends "base.html" %} {% block content %} <h3>Поиск людей</h3> <div class="row"> {% for u in users %} {% if u.id != current_user.id %} <div class="col-md-4 mb-3"><div class="card p-3 d-flex flex-row align-items-center"><div class="avatar me-3">{% if u.avatar %}<img src="{{ url_for('uploaded_file', filename=u.avatar) }}">{% else %}{{ u.username[0].upper() }}{% endif %}</div><div><h5>{{ u.username }}</h5><a href="{{ url_for('profile', username=u.username) }}" class="btn btn-sm btn-outline-primary rounded-pill">Профиль</a></div></div></div> {% endif %} {% endfor %} </div> {% endblock %}"""
}
app.jinja_loader = jinja2.DictLoader(templates)

# --- ROUTES ---

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/')
@login_required
def index():
    posts = Post.query.order_by(Post.timestamp.desc()).all()
    # Умный счетчик просмотров (1 юзер = 1 просмотр)
    for p in posts:
        # Проверяем, видел ли уже этот пользователь этот пост
        view = PostView.query.filter_by(user_id=current_user.id, post_id=p.id).first()
        if not view:
            # Если не видел, создаем запись и увеличиваем счетчик
            db.session.add(PostView(user_id=current_user.id, post_id=p.id))
            p.views += 1
    db.session.commit()
    return render_template('index.html', posts=posts)

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

# Вот здесь была ошибка в шаблоне. Теперь endpoint 'remove_friend' совпадает с вызовом url_for
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
        except OSError: flash("Ошибка загрузки", "danger")
    if bio: current_user.bio = bio
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
    image_filename, video_filename = None, None
    if file and file.filename != '' and allowed_file(file.filename):
        ext = file.filename.rsplit('.', 1)[1].lower()
        filename = str(uuid.uuid4()) + '.' + ext
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        if ext in ['mp4', 'webm', 'mov']: video_filename = filename
        else: image_filename = filename
    if content or image_filename or video_filename:
        db.session.add(Post(content=content, image_filename=image_filename, video_filename=video_filename, author=current_user))
        db.session.commit()
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
    if existing: db.session.delete(existing)
    else: db.session.add(Like(user_id=current_user.id, post_id=post_id))
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
            login_user(user)
            return redirect(url_for('index'))
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
