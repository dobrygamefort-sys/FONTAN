# 1. ПОДГОТОВКА СРЕДЫ

from gevent import monkey

monkey.patch_all()

# 2. РЎРўРђРќР”РђР РўРќР«Р• Р‘РР‘Р›РРћРўР•РљР

import os

import uuid

import json

import re

import random

import requests  # Для связи с Cloudflare

from pathlib import Path

from urllib.parse import quote_plus

from datetime import datetime, timedelta

# 3. ОБЛАКО

import cloudinary

import cloudinary.uploader

import cloudinary.api

# 4. FLASK Р Р РђРЎРЁРР Р•РќРРЇ

from flask import Flask, render_template, redirect, url_for, request, flash, jsonify, abort, session, send_from_directory

from flask_sqlalchemy import SQLAlchemy

from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user

from flask_socketio import SocketIO, emit, join_room, leave_room

# 5. РРќРЎРўР РЈРњР•РќРўР« Р”РђРќРќР«РҐ

from werkzeug.security import generate_password_hash, check_password_hash

from sqlalchemy import or_, and_, func, text

import jinja2

# --- РРќРР¦РРђР›РР—РђР¦РРЇ РћР‘РЄР•РљРўРћР’ ---

db = SQLAlchemy()

login_manager = LoginManager()

# 1. Получаем путь к папке, где лежит этот app.py

current_dir = os.path.dirname(os.path.abspath(__file__))

# 2. Собираем путь к папке templates

template_path = os.path.join(current_dir, 'templates')

# Печатаем в логи для отладки (ты увидишь это в панели Render)

print(f">>> DEBUG: Текущая директория: {current_dir}")

print(f">>> DEBUG: РС‰Сѓ С€Р°Р±Р»РѕРЅС‹ РІ: {template_path}")

print(f">>> DEBUG: Список файлов в templates: {os.listdir(template_path) if os.path.exists(template_path) else 'ПАПКА НЕ НАЙДЕНА'}")

app = Flask(__name__, template_folder=template_path)

app.config['SECRET_KEY'] = 'fontan_ultra_admin_edition_v9_reset'

# --- РќРђРЎРўР РћР™РљР РњРћРЎРўРђ (CLOUDFLARE + TELEGRAM) ---

CF_WORKER_URL = "https://fontan.arthur-kgame1.workers.dev"

# Р’РЎРўРђР’Р¬ РЎР’РћР™ ID РР— @userinfobot РќРР–Р•:

ADMIN_TG_ID = "1373304655"

# --- GROQ AI CONFIG ---

GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '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')

GROQ_MODEL = "llama-3.3-70b-versatile"
AI_DAILY_CREDITS = 40
AI_MODEL_OPTIONS = {
    'fast': {
        'key': 'fast',
        'label': 'Быстрая',
        'api_model': os.environ.get('GROQ_FAST_MODEL', 'llama-3.1-8b-instant'),
        'cost': 1,
        'hint': 'Быстрый ответ, экономит кредиты'
    },
    'smart': {
        'key': 'smart',
        'label': 'Думающая',
        'api_model': os.environ.get('GROQ_SMART_MODEL', GROQ_MODEL),
        'cost': 3,
        'hint': 'Думает дольше, пишет надёжнее и умнее'
    }
}

GROQ_COOLDOWN_SECONDS = 5   # минимум секунд между запросами от одного юзера

GROQ_TIMEOUT_SECONDS = 30   # если нет ответа за 15с — "попробуй позже"

AI_ADMIN_MODE = {}  # {chat_id: True} — в каком чате админ отвечает сам

# --- WEBRTC ICE СЕРВЕРЫ (STUN/TURN) ---

WEBRTC_ICE_SERVERS = [

    {"urls": "stun:stun.l.google.com:19302"},

    {"urls": "stun:stun1.l.google.com:19302"},

]

# --- НАСТРОЙКА БАЗЫ ДАННЫХ (Supabase IPv4 Pooler) ---
# ВАЖНО: Удали переменную DATABASE_URL на Render или замени её на Supabase pooler URL!
# Supabase IPv4 Transaction Pooler (работает на Render free tier, нет IPv6):
# postgresql://postgres.apbtrkzzvnpogpttgbpg:PASSWORD@aws-0-us-east-1.pooler.supabase.com:6543/postgres
# Найти свой URL: Supabase → Project Settings → Database → Transaction pooler

from sqlalchemy.pool import NullPool

# Supabase Transaction Pooler URL (IPv4, работает на Render)
import os
from sqlalchemy.pool import NullPool
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_socketio import SocketIO
import cloudinary


import os
import cloudinary
from sqlalchemy.pool import NullPool
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_socketio import SocketIO

# --- 1. НАСТРОЙКА БАЗЫ ДАННЫХ ---
# Прямой URL (порт 5432) — самый надежный путь без пулера
import os
import cloudinary
from sqlalchemy.pool import NullPool
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_socketio import SocketIO

# --- 1. НАСТРОЙКА БАЗЫ ДАННЫХ (БЕЗ NEON) ---
# Прямой URL Supabase (порт 5432) — самый стабильный
import os
import cloudinary
from sqlalchemy.pool import NullPool
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user
from flask_socketio import SocketIO
from flask import session

# 1. СТРОГИЙ URL (IPv4 совместимый)
import os
import cloudinary
from sqlalchemy.pool import NullPool
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user
from flask_socketio import SocketIO
from flask import session

# --- 1. ЖЕСТКАЯ НАСТРОЙКА URL (ПРЯМОЕ ПОДКЛЮЧЕНИЕ) ---
# ВАЖНО: Используем прямой хост проекта db.apbtrk... и стандартный порт 5432
# Это обходит капризные пулеры и ошибки "Tenant not found"
import os
import cloudinary
from sqlalchemy.pool import NullPool
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user
from flask_socketio import SocketIO
from flask import session

# --- 1. ЖЕСТКАЯ НАСТРОЙКА URL (IPv4 FIX) ---
# Мы используем адрес пулера, но на ПРЯМОМ порту 5432, чтобы обойти проблемы с IPv6
import os
import cloudinary
from sqlalchemy.pool import NullPool
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user
from flask_socketio import SocketIO
from flask import session

# --- 1. ПРИНУДИТЕЛЬНЫЙ КОНФИГ SUPABASE (Игнорируем переменные Render) ---
# Используем порт 6543 и специальный логин для стабильной работы пулера
DB_USER = "postgres.apbtrkzzvnpogpttgbpg" 
DB_PASS = "FontanAdmin2026"
DB_HOST = "aws-0-us-east-1.pooler.supabase.com"
DB_PORT = "6543"
DB_NAME = "postgres"

# Собираем URL с фиксом для SQLAlchemy (prepare_threshold=0 необходим для пулеров)
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}?prepare_threshold=0"

# --- 2. КОНФИГУРАЦИЯ FLASK ---
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    "poolclass": NullPool,
    "connect_args": {
        "sslmode": "require",
        "connect_timeout": 30
    }
}

# --- 3. ИНИЦИАЛИЗАЦИЯ РАСШИРЕНИЙ ---
db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
socketio = SocketIO(app, async_mode='gevent', cors_allowed_origins="*")

# --- 4. CLOUDINARY CONFIG ---
cloudinary.config(
    cloud_name = 'daz4839e7', 
    api_key = '371541773313745', 
    api_secret = 'fumEMY1h-nsFKW8B5BCgix9EN-8',
    secure = True
)

# --- 5. БЕЗОПАСНЫЙ ЗАПУСК (Внутри контекста) ---
with app.app_context():
    try:
        from sqlalchemy import text
        # Простая проверка связи
        db.session.execute(text('SELECT 1'))
        db.create_all()
        print(">>> [FONTAN] SUCCESS: База данных Supabase подключена!")
    except Exception as e:
        # Если здесь ошибка, приложение не упадет при старте, а выдаст инфо в лог
        print(f">>> [FONTAN] DATABASE STARTUP WARNING: {e}")

# --- 6. ФИКС ФУНКЦИИ track_visitor ---
@app.before_request
def track_visitor():
    try:
        if not session.get('tracked_visitor'):
            stats = SiteStats.query.first()
            if stats:
                stats.total_visitors = (stats.total_visitors or 0) + 1
                db.session.commit()
                session['tracked_visitor'] = True
            else:
                try:
                    new_stats = SiteStats(total_visitors=1)
                    db.session.add(new_stats)
                    db.session.commit()
                    session['tracked_visitor'] = True
                except:
                    db.session.rollback()

        if current_user.is_authenticated:
            if not session.get('user_visit_counted'):
                current_user.total_visits = (current_user.total_visits or 0) + 1
                current_user.last_seen = db.func.now()
                db.session.commit()
                session['user_visit_counted'] = True
    except Exception as e:
        db.session.rollback()
        print(f">>> [FONTAN] Visitor tracking paused: {e}")
# --- Р’РЎРџРћРњРћР“РђРўР•Р›Р¬РќР«Р• Р¤РЈРќРљР¦РР ---

def send_verification_code(email):

    code = str(random.randint(100000, 999999))

    session['temp_code'] = code

    session['temp_email'] = email

    # РС‰РµРј РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ РІ Р±Р°Р·Рµ

    user = User.query.filter_by(email=email).first()

    # Если у юзера нет ТГ, шлем админу

    target_id = user.telegram_id if (user and hasattr(user, 'telegram_id') and user.telegram_id) else ADMIN_TG_ID

    payload = {

        "chat_id": target_id,

        "text": f"<b>🔑 Код Fontan</b>\nДля: {email}\nКод: <code>{code}</code>"

    }

    try:

        requests.post(CF_WORKER_URL, json=payload, timeout=5)

    except Exception as e:

        print(f"!!! [РћРЁРР‘РљРђ]: {e}")

        print(f"\n[DEBUG LOG] КОД: {code}\n")

    return True

# --- РРќРР¦РРђР›РР—РђР¦РРЇ Р‘Р” ---

with app.app_context():

    try:

        db.create_all()

    except:

        pass

# --- РњРћР”Р•Р›Р Р”РђРќРќР«РҐ ---

# --- РћРЎРўРђР›Р¬РќР«Р• РљРћРќРЎРўРђРќРўР« Р Р¤РЈРќРљР¦РР ---

MEDIA_EXTENSIONS = ('.mp3', '.wav', '.ogg', '.webm', '.m4a')

def upload_to_cloud(file_obj, resource_type="auto"):

    if not file_obj: return None

    try:

        res = cloudinary.uploader.upload(file_obj, resource_type=resource_type, folder="fontan_app")

        return res['secure_url']

    except: return None

def allowed_file(filename):

    ALLOWED = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'webm', 'mp3', 'wav', 'ogg'}

    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED

def normalize_text(value):

    return re.sub(r'\s+', ' ', (value or '').strip())

def get_ai_model_config(model_key):

    normalized_key = (model_key or 'fast').strip().lower()

    return AI_MODEL_OPTIONS.get(normalized_key, AI_MODEL_OPTIONS['fast'])

def reset_daily_ai_credits(user):

    now = datetime.utcnow()

    if user.ai_credits is None:

        user.ai_credits = AI_DAILY_CREDITS

        user.ai_credits_reset_at = now

        return True

    if not user.ai_credits_reset_at or user.ai_credits_reset_at.date() != now.date():

        user.ai_credits = AI_DAILY_CREDITS

        user.ai_credits_reset_at = now

        return True

    return False

def get_ai_credit_state(user, commit=False):

    changed = reset_daily_ai_credits(user)

    if commit and changed:

        db.session.commit()

    return {
        'balance': max(0, int(user.ai_credits or 0)),
        'limit': AI_DAILY_CREDITS,
    }

def spend_ai_credits(user, amount):

    reset_daily_ai_credits(user)

    current_balance = int(user.ai_credits or 0)

    if amount > current_balance:

        return False

    user.ai_credits = current_balance - amount

    if not user.ai_credits_reset_at:

        user.ai_credits_reset_at = datetime.utcnow()

    return True

def consume_idempotency_token(scope, token, ttl_seconds=1800):

    token = (token or '').strip()

    if not token:

        return True

    now_ts = int(datetime.utcnow().timestamp())

    idempotency = session.get('_idempotency', {})

    scope_items = [

        item for item in idempotency.get(scope, [])

        if now_ts - int(item.get('ts', 0)) < ttl_seconds

    ]

    if any(item.get('token') == token for item in scope_items):

        return False

    scope_items.append({'token': token, 'ts': now_ts})

    idempotency[scope] = scope_items[-30:]

    session['_idempotency'] = idempotency

    session.modified = True

    return True

def recent_duplicate_signature(scope, signature, ttl_seconds=12):

    signature = (signature or '').strip()

    if not signature:

        return False

    now_ts = int(datetime.utcnow().timestamp())

    recent = session.get('_recent_signatures', {})

    scope_items = [

        item for item in recent.get(scope, [])

        if now_ts - int(item.get('ts', 0)) < ttl_seconds

    ]

    if any(item.get('sig') == signature for item in scope_items):

        recent[scope] = scope_items

        session['_recent_signatures'] = recent

        session.modified = True

        return True

    scope_items.append({'sig': signature, 'ts': now_ts})

    recent[scope] = scope_items[-20:]

    session['_recent_signatures'] = recent

    session.modified = True

    return False

def find_media_asset(asset_name):

    candidates = [asset_name]

    if not Path(asset_name).suffix:

        candidates.extend([f'{asset_name}{ext}' for ext in MEDIA_EXTENSIONS])

    search_roots = [

        Path(app.root_path),

        Path(app.root_path) / 'static',

        Path(app.root_path) / 'static' / 'audio',

    ]

    for candidate in candidates:

        for root in search_roots:

            file_path = root / candidate

            if file_path.exists() and file_path.is_file():

                return file_path

    return None

# --- AI РњРћР”Р•Р РђР¦РРЇ РљРћРќРўР•РќРўРђ ---

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

# --- РњРћР”Р•Р›Р Р‘РђР—Р« Р”РђРќРќР«РҐ ---

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

    email_confirmed = db.Column(db.Boolean, default=False)

    email_confirmation_token = db.Column(db.String(100), unique=True, nullable=True)

    is_online = db.Column(db.Boolean, default=False)

    total_visits = db.Column(db.Integer, default=0)

    telegram_id = db.Column(db.String(100), nullable=True)
    ai_credits = db.Column(db.Integer, default=AI_DAILY_CREDITS)
    ai_credits_reset_at = db.Column(db.DateTime, default=datetime.utcnow)

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

    client_token = db.Column(db.String(80), nullable=True)

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

    client_token = db.Column(db.String(80), nullable=True)

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

    client_token = db.Column(db.String(80), nullable=True)

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

class FluxVideo(db.Model):

    __tablename__ = 'flux_videos'

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    video_url = db.Column(db.String(300), nullable=False)

    description = db.Column(db.Text, nullable=True)

    likes = db.Column(db.Integer, default=0)

    views = db.Column(db.Integer, default=0)

    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    author = db.relationship('User', backref='flux_videos')

class FluxLike(db.Model):

    __tablename__ = 'flux_likes'

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    video_id = db.Column(db.Integer, db.ForeignKey('flux_videos.id'), nullable=False)

class FluxComment(db.Model):

    __tablename__ = 'flux_comments'

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    video_id = db.Column(db.Integer, db.ForeignKey('flux_videos.id'), nullable=False)

    text = db.Column(db.Text, nullable=False)

    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    author = db.relationship('User', backref='flux_comments')

class SiteStats(db.Model):

    __tablename__ = 'site_stats'

    id = db.Column(db.Integer, primary_key=True)

    total_visitors = db.Column(db.Integer, default=0)

    peak_online = db.Column(db.Integer, default=0)

class AiChat(db.Model):

    __tablename__ = 'ai_chats'

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    title = db.Column(db.String(200), default='Новый чат')

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

    is_admin_mode = db.Column(db.Boolean, default=False)

    user = db.relationship('User', foreign_keys=[user_id])

    messages = db.relationship('AiMessage', backref='chat', cascade='all, delete-orphan', order_by='AiMessage.timestamp')

class AiMessage(db.Model):

    __tablename__ = 'ai_messages'

    id = db.Column(db.Integer, primary_key=True)

    chat_id = db.Column(db.Integer, db.ForeignKey('ai_chats.id'), nullable=False)

    role = db.Column(db.String(20), nullable=False)  # user | assistant | admin

    content = db.Column(db.Text, nullable=True)

    file_url = db.Column(db.String(300), nullable=True)

    file_type = db.Column(db.String(20), nullable=True)

    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

def ensure_user_sessions_schema():

    from sqlalchemy import text

    try:

        with app.app_context():

            # 1. Таблица user_sessions

            db.session.execute(text("ALTER TABLE user_sessions ADD COLUMN IF NOT EXISTS ip VARCHAR(64)"))

            db.session.execute(text("ALTER TABLE user_sessions ADD COLUMN IF NOT EXISTS city VARCHAR(100)"))

            db.session.execute(text("ALTER TABLE user_sessions ADD COLUMN IF NOT EXISTS user_agent VARCHAR(300)"))

            db.session.execute(text("ALTER TABLE user_sessions ADD COLUMN IF NOT EXISTS created_at TIMESTAMP"))

            db.session.execute(text("ALTER TABLE user_sessions ADD COLUMN IF NOT EXISTS last_seen TIMESTAMP"))

            db.session.execute(text("ALTER TABLE user_sessions ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE"))

            # 2. Таблица notifications

            db.session.execute(text("ALTER TABLE notifications ADD COLUMN IF NOT EXISTS ntype VARCHAR(50) DEFAULT 'system'"))

            db.session.execute(text("ALTER TABLE notifications ADD COLUMN IF NOT EXISTS link VARCHAR(500)"))

            db.session.execute(text("ALTER TABLE notifications ADD COLUMN IF NOT EXISTS from_user_id INTEGER"))

            # Фикс: старая колонка "type" (NOT NULL без дефолта) вызывала краш при вставке через ntype

            db.session.execute(text("ALTER TABLE notifications ALTER COLUMN type DROP NOT NULL"))

            db.session.execute(text("ALTER TABLE notifications ALTER COLUMN type SET DEFAULT 'system'"))

            # 3. Таблица stories

            db.session.execute(text("ALTER TABLE stories ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"))

            db.session.execute(text("ALTER TABLE stories ADD COLUMN IF NOT EXISTS media_type VARCHAR(50) DEFAULT 'image'"))

            # 4. РўРђР‘Р›РР¦Рђ REPORTS (РСЃРїСЂР°РІР»СЏРµРј РІР°С€Сѓ РЅРѕРІСѓСЋ РѕС€РёР±РєСѓ)

            db.session.execute(text("ALTER TABLE reports ADD COLUMN IF NOT EXISTS post_id INTEGER"))

            db.session.execute(text("ALTER TABLE reports ADD COLUMN IF NOT EXISTS target_user_id INTEGER"))

            db.session.execute(text("ALTER TABLE reports ADD COLUMN IF NOT EXISTS reason TEXT"))

            db.session.execute(text("ALTER TABLE reports ADD COLUMN IF NOT EXISTS status VARCHAR(50) DEFAULT 'open'"))

            db.session.execute(text("ALTER TABLE reports ADD COLUMN IF NOT EXISTS timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP"))

            # 6. Flux

            db.session.execute(text("CREATE TABLE IF NOT EXISTS flux_videos (id SERIAL PRIMARY KEY, user_id INTEGER, video_url VARCHAR(300), description TEXT, likes INTEGER DEFAULT 0, views INTEGER DEFAULT 0, timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY(user_id) REFERENCES users(id))"))

            db.session.execute(text("ALTER TABLE flux_videos ADD COLUMN IF NOT EXISTS likes INTEGER DEFAULT 0"))

            db.session.execute(text("CREATE TABLE IF NOT EXISTS flux_likes (id SERIAL PRIMARY KEY, user_id INTEGER, video_id INTEGER, FOREIGN KEY(user_id) REFERENCES users(id), FOREIGN KEY(video_id) REFERENCES flux_videos(id))"))

            db.session.execute(text("CREATE TABLE IF NOT EXISTS flux_comments (id SERIAL PRIMARY KEY, user_id INTEGER, video_id INTEGER, text TEXT, timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY(user_id) REFERENCES users(id), FOREIGN KEY(video_id) REFERENCES flux_videos(id))"))

            # 7. Analytics

            db.session.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_online BOOLEAN DEFAULT FALSE"))

            db.session.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS total_visits INTEGER DEFAULT 0"))

            db.session.execute(text("CREATE TABLE IF NOT EXISTS site_stats (id SERIAL PRIMARY KEY, total_visitors INTEGER DEFAULT 0, peak_online INTEGER DEFAULT 0)"))

            db.session.execute(text("ALTER TABLE site_stats ADD COLUMN IF NOT EXISTS peak_online INTEGER DEFAULT 0"))

            # Initialize stats if not exist

            res = db.session.execute(text("SELECT count(*) FROM site_stats")).scalar()

            if res == 0:

                db.session.execute(text("INSERT INTO site_stats (total_visitors, peak_online) VALUES (0, 0)"))

            # 5. Сообщения

            db.session.execute(text("ALTER TABLE messages ADD COLUMN IF NOT EXISTS read_at TIMESTAMP"))

            db.session.execute(text("ALTER TABLE messages ADD COLUMN IF NOT EXISTS deleted_for_all BOOLEAN DEFAULT FALSE"))

            db.session.execute(text("ALTER TABLE messages ADD COLUMN IF NOT EXISTS client_token VARCHAR(80)"))

            db.session.execute(text("ALTER TABLE comments ADD COLUMN IF NOT EXISTS client_token VARCHAR(80)"))

            db.session.execute(text("ALTER TABLE posts ADD COLUMN IF NOT EXISTS client_token VARCHAR(80)"))

            db.session.commit()

            print(">>> БАЗА ДАННЫХ ПОЛНОСТЬЮ ОБНОВЛЕНА: Жалобы, уведомления и сессии в порядке! <<<")

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

@app.before_request
def track_visitor():
    try:
        # 1. Счётчик общих визитов сайта (SiteStats)
        if not session.get('tracked_visitor'):
            stats = SiteStats.query.first()
            if stats:
                stats.total_visitors = (stats.total_visitors or 0) + 1
                db.session.commit()
                session['tracked_visitor'] = True
            else:
                # Если записи еще нет, создаем её
                try:
                    new_stats = SiteStats(total_visitors=1)
                    db.session.add(new_stats)
                    db.session.commit()
                    session['tracked_visitor'] = True
                except:
                    db.session.rollback()

        # 2. Счётчик визитов конкретного пользователя
        if current_user.is_authenticated:
            if not session.get('user_visit_counted'):
                # Используем (val or 0), чтобы не упасть если в базе NULL
                current_user.total_visits = (current_user.total_visits or 0) + 1
                current_user.last_seen = db.func.now()
                db.session.commit()
                session['user_visit_counted'] = True

    except Exception as e:
        db.session.rollback()
        # Если база недоступна, просто пишем в лог, но сайт НЕ падает
        print(f">>> [APP LOG] track_visitor non-critical error: {e}")

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

        try:

            now = datetime.utcnow()

            last_sync = session.get('last_seen_sync')

            if last_sync:

                try:

                    if now - datetime.fromisoformat(last_sync) < timedelta(seconds=30):

                        return None

                except ValueError:

                    pass

            current_user.last_seen = now

            token = session.get('session_token')

            if token:

                sess = UserSession.query.filter_by(session_token=token, user_id=current_user.id, is_active=True).first()

                if sess:

                    sess.last_seen = now

            session['last_seen_sync'] = now.isoformat()

            db.session.commit()

        except Exception as e:

            db.session.rollback()

            print(f">>> update_last_seen error (non-critical): {e}")

# --- Р’РЎРџРћРњРћР“РђРўР•Р›Р¬РќРђРЇ Р¤РЈРќРљР¦РРЇ Р”Р›РЇ Р’Р Р•РњР•РќР ---

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

# --- РЈРџРћРњРРќРђРќРРЇ Р РҐР­РЁРўР•Р“Р ---

def linkify_text(text):

    if not text:

        return text

    def repl_mention(match):

        uname = match.group(1)

        return f'<a href="/profile/{uname}" class="text-primary">@{uname}</a>'

    def repl_tag(match):

        tag = match.group(1)

        return f'<a href="/search?q={quote_plus(f"#{tag}")}" class="text-success fw-semibold">#{tag}</a>'

    text = re.sub(r'@([A-Za-z0-9_\\.]+)', repl_mention, text)

    text = re.sub(r'#([A-Za-z0-9_\\.]+)', repl_tag, text)

    return text

app.jinja_env.filters['linkify'] = linkify_text

def safe_from_json(value):

    if value in (None, ''):

        return {}

    try:

        return json.loads(value)

    except (TypeError, ValueError, json.JSONDecodeError):

        raw = str(value).strip()

        return [] if raw.startswith('[') else {}

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

@app.route('/media_asset/<asset_name>')

def media_asset(asset_name):

    if asset_name not in {'rigton', 'rigton2'}:

        abort(404)

    file_path = find_media_asset(asset_name)

    if not file_path:

        abort(404)

    return send_from_directory(str(file_path.parent), file_path.name, conditional=True)

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

                    <a class="nav-link text-white fs-5" href="{{ url_for('flux_feed') }}" title="Flux (Shorts)"><i class="bi bi-play-btn-fill"></i></a>

                    <a class="nav-link text-white fs-5" href="{{ url_for('fontan_ai') }}" title="FontanAI"><i class="bi bi-robot"></i></a>

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

    {% if current_user.is_authenticated %}

    <script src="https://cdn.socket.io/4.7.2/socket.io.min.js"></script>

    {% endif %}

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

        

        function generateActionToken() {

            if (window.crypto && typeof window.crypto.randomUUID === 'function') {

                return window.crypto.randomUUID();

            }

            return `tok_${Date.now()}_${Math.random().toString(16).slice(2)}`;

        }

        function initIdempotentForms(root = document) {

            root.querySelectorAll('form.js-idempotent-form').forEach(form => {

                if (form.dataset.idempotentBound === '1') return;

                form.dataset.idempotentBound = '1';

                form.addEventListener('submit', () => {

                    let tokenInput = form.querySelector('input[name=\"client_token\"]');

                    if (!tokenInput) {

                        tokenInput = document.createElement('input');

                        tokenInput.type = 'hidden';

                        tokenInput.name = 'client_token';

                        form.appendChild(tokenInput);

                    }

                    if (!tokenInput.value) {

                        tokenInput.value = generateActionToken();

                    }

                    form.querySelectorAll('button[type=\"submit\"], input[type=\"submit\"]').forEach(btn => {

                        btn.disabled = true;

                        if (btn.tagName === 'BUTTON') {

                            btn.dataset.originalHtml = btn.dataset.originalHtml || btn.innerHTML;

                            btn.innerHTML = '<span class=\"spinner-border spinner-border-sm me-1\"></span>Отправка';

                        } else {

                            btn.dataset.originalValue = btn.dataset.originalValue || btn.value;

                            btn.value = 'Отправка...';

                        }

                    });

                });

            });

        }

        

        // РРЅРёС†РёР°Р»РёР·Р°С†РёСЏ РёРєРѕРЅРєРё РїСЂРё Р·Р°РіСЂСѓР·РєРµ

        document.addEventListener('DOMContentLoaded', function() {

            const theme = document.documentElement.getAttribute('data-theme');

            updateThemeIcon(theme);

            initIdempotentForms(document);

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

        {% if current_user.is_authenticated %}

        window.fontanBaseSocket = window.fontanBaseSocket || io();

        if (!window.__fontanBaseCallInit) {

            window.__fontanBaseCallInit = true;

            window.fontanBaseSocket.on('connect', () => {

                window.fontanBaseSocket.emit('join_user_room', { user_id: {{ current_user.id }} });

            });

            window.fontanBaseSocket.on('call_invite', (data) => {

                if (window.__fontanMessengerHandlesCalls) return;

                try {

                    sessionStorage.setItem('pendingIncomingCall', JSON.stringify(data));

                } catch (error) {

                    console.error(error);

                }

                const shouldOpen = window.confirm(`Звонит ${data.from_username}. Открыть чат?`);

                if (shouldOpen) {

                    window.location.href = `/messenger?type=private&chat_id=${data.from_id}`;

                } else {

                    window.fontanBaseSocket.emit('call_decline', { to_user_id: data.from_id, reason: 'Отклонено' });

                }

            });

        }

        {% endif %}

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

            <form method="POST" action="{{ url_for('create_post') }}" enctype="multipart/form-data" id="create-post-form" class="js-idempotent-form">

                <input type="hidden" name="client_token">

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

                if (window.initIdempotentForms) {

                    window.initIdempotentForms(container);

                }

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

    {% set post_author = post.author %}

    {% set post_co_author = post.co_author %}

    <div class="d-flex justify-content-between align-items-start">

        <div class="d-flex align-items-center">

            <a href="{{ url_for('profile', username=(post_author.username if post_author else current_user.username)) }}" class="text-decoration-none">

                <div class="avatar me-2">

                    {% if post_author and post_author.avatar %}

                        <img src="{{ post_author.avatar }}">

                    {% else %}

                        {{ post_author.username[0].upper() if post_author else '?' }}

                    {% endif %}

                </div>

            </a>

            <div>

                <a href="{{ url_for('profile', username=(post_author.username if post_author else current_user.username)) }}" class="fw-bold text-decoration-none" style="color: var(--text-color);">

                    {{ post_author.username if post_author else 'Удалённый пользователь' }}

                    {% if post_author and post_author.is_verified %}<i class="bi bi-patch-check-fill verified-icon"></i>{% endif %}

                </a>

                {% if post.co_author_id and post_co_author %}

                    <span class="text-muted small">· cо‑автор</span>

                    <a href="{{ url_for('profile', username=post_co_author.username) }}" class="text-decoration-none text-muted small">

                        {{ post_co_author.username }}

                    </a>

                {% endif %}

                <div class="text-muted small" style="font-size: 0.75rem;">{{ post.timestamp|time_ago }}{% if post.edited_at %} · изменено{% endif %}</div>

            </div>

        </div>

        {% if (post_author and post_author.id == current_user.id) or current_user.is_admin %}

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

                     <b>{{ comment.author.username if comment.author else 'Удалённый пользователь' }}</b>

                     {% if comment.author and comment.author.is_verified %}<i class="bi bi-patch-check-fill verified-icon" style="font-size: 10px;"></i>{% endif %}

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

              <form action="{{ url_for('add_comment', post_id=post.id) }}" method="POST" class="d-flex gap-1 align-items-center js-idempotent-form">

                <input type="hidden" name="client_token">

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

                <div class="p-3 border-bottom d-flex align-items-center justify-content-between shadow-sm" style="z-index: 10; backdrop-filter: blur(14px); background: linear-gradient(180deg, rgba(79,70,229,0.06), transparent), var(--card-bg);">

                    <div class="d-flex align-items-center gap-3">

                        {% if chat_type == 'private' %}

                        <div class="avatar" style="width:46px; height:46px;">

                            {% if active_chat.avatar %}

                                <img src="{{ active_chat.avatar }}">

                            {% else %}

                                {{ active_chat.username[0].upper() }}

                            {% endif %}

                        </div>

                        {% endif %}

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

                        {% if chat_type == 'private' %}

                        <button id="btn-start-call" class="btn btn-outline-success rounded-circle" title="Позвонить"><i class="bi bi-telephone-fill"></i></button>

                        <button id="btn-start-video" class="btn btn-outline-primary rounded-circle" title="Видео"><i class="bi bi-camera-video-fill"></i></button>

                        {% endif %}

                        <button id="emoji-btn" class="btn btn-outline-secondary rounded-circle">😊</button>

                        <input type="text" id="msg-input" class="form-control rounded-pill border-0 shadow-sm" placeholder="Написать..." autocomplete="off">

                        <button id="btn-record-msg" class="btn btn-danger rounded-circle shadow-sm"><i class="bi bi-mic-fill"></i></button>

                        <button id="btn-send-msg" class="btn btn-primary rounded-circle shadow-sm"><i class="bi bi-send-fill"></i></button>

                    </div>

                </div>

                <div id="call-overlay" style="display:none; position:absolute; inset:16px; z-index:30; border-radius:26px; background:rgba(9,15,30,.74); backdrop-filter:blur(18px);">

                    <div style="height:100%; display:flex; align-items:center; justify-content:center; padding:24px;">

                        <div style="width:min(440px,100%); text-align:center; color:#fff; padding:28px; border-radius:28px; background:linear-gradient(135deg, rgba(79,70,229,.96), rgba(17,24,39,.96)); box-shadow:0 30px 80px rgba(15,23,42,.45);">

                            <video id="remote-media" autoplay playsinline style="display:none; width:min(100%,420px); max-height:280px; object-fit:cover; border-radius:22px; margin:0 auto 16px; background:#050816;"></video>

                            <div id="call-avatar-wrap" style="width:120px; height:120px; margin:0 auto 18px; border-radius:50%; padding:6px; background:linear-gradient(135deg, rgba(255,255,255,.95), rgba(125,211,252,.45)); animation:pulse 1.8s infinite;">

                                <div id="call-avatar" style="width:100%; height:100%; border-radius:50%; overflow:hidden; display:flex; align-items:center; justify-content:center; font-size:2rem; font-weight:700; background:rgba(255,255,255,.16);"></div>

                            </div>

                            <div id="call-username" class="fs-4 fw-bold">Call</div>

                            <div id="call-status" style="opacity:.88; min-height:24px;">Готовимся к звонку...</div>

                            <div id="call-timer" style="font-size:1.5rem; font-weight:700; letter-spacing:.08em; margin:8px 0 18px;">00:00</div>

                            <div class="d-flex justify-content-center gap-2 flex-wrap">

                                <button class="btn btn-light rounded-circle" id="call-mic-btn" title="Микрофон"><i class="bi bi-mic-fill"></i></button>

                                <button class="btn btn-light rounded-circle" id="call-speaker-btn" title="Звук"><i class="bi bi-volume-up-fill"></i></button>

                                <button class="btn btn-light rounded-circle" id="call-camera-btn" title="Вебка"><i class="bi bi-camera-video-fill"></i></button>

                                <button class="btn btn-light rounded-circle" id="call-screen-btn" title="Экран"><i class="bi bi-display-fill"></i></button>

                                <button class="btn btn-success rounded-circle" id="call-accept-btn" title="Ответить" style="display:none;"><i class="bi bi-telephone-inbound-fill"></i></button>

                                <button class="btn btn-danger rounded-circle" id="call-decline-btn" title="Отклонить" style="display:none;"><i class="bi bi-telephone-x-fill"></i></button>

                                <button class="btn btn-danger rounded-circle" id="call-end-btn" title="Завершить"><i class="bi bi-telephone-x-fill"></i></button>

                            </div>

                        </div>

                        <video id="local-preview" autoplay muted playsinline style="display:none; position:absolute; right:18px; bottom:18px; width:148px; height:112px; object-fit:cover; border-radius:18px; border:2px solid rgba(255,255,255,.2); background:#050816;"></video>

                    </div>

                </div>

                <audio id="ringtone-outgoing" preload="auto" loop src="{{ url_for('media_asset', asset_name='rigton') }}"></audio>

                <audio id="ringtone-incoming" preload="auto" loop src="{{ url_for('media_asset', asset_name='rigton2') }}"></audio>

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

    window.__fontanMessengerHandlesCalls = true;

    const chatBox = document.getElementById('chat-box');

    const chatType = document.getElementById('chat_type').value;

    const chatId = parseInt(document.getElementById('chat_id').value);

    const msgInput = document.getElementById('msg-input');

    const sendBtn = document.getElementById('btn-send-msg');

    const recordBtn = document.getElementById('btn-record-msg');

    const emojiBtn = document.getElementById('emoji-btn');

    const currentUserId = {{ current_user.id }};

    const currentUsername = {{ current_user.username|tojson }};

    const currentUserAvatar = {{ current_user.avatar|default('', true)|tojson }};

    const peerMeta = {

        id: {{ active_chat.id|tojson }},

        username: {% if chat_type == 'private' %}{{ active_chat.username|tojson }}{% else %}{{ active_chat.name|tojson }}{% endif %},

        avatar: {% if chat_type == 'private' %}{{ active_chat.avatar|default('', true)|tojson }}{% else %}''{% endif %}

    };

    const callOverlay = document.getElementById('call-overlay');

    const callStatus = document.getElementById('call-status');

    const callTimer = document.getElementById('call-timer');

    const callUsername = document.getElementById('call-username');

    const callAvatar = document.getElementById('call-avatar');

    const callAcceptBtn = document.getElementById('call-accept-btn');

    const callDeclineBtn = document.getElementById('call-decline-btn');

    const callMicBtn = document.getElementById('call-mic-btn');

    const callSpeakerBtn = document.getElementById('call-speaker-btn');

    const callCameraBtn = document.getElementById('call-camera-btn');

    const callScreenBtn = document.getElementById('call-screen-btn');

    const callEndBtn = document.getElementById('call-end-btn');

    const localPreview = document.getElementById('local-preview');

    const remoteMedia = document.getElementById('remote-media');

    const outgoingRingtone = document.getElementById('ringtone-outgoing');

    const incomingRingtone = document.getElementById('ringtone-incoming');

    const startCallBtn = Array.from(document.querySelectorAll('#btn-start-call')).pop() || null;

    const startVideoBtn = Array.from(document.querySelectorAll('#btn-start-video')).pop() || null;

    const rtcConfig = { iceServers: {{ webrtc_ice_servers|tojson }} };

    let isSendingMessage = false;

    let lastRenderedSignature = '';

    let activeCall = null;

    let peerConnection = null;

    let localStream = null;

    let remoteStream = null;

    let screenStream = null;

    let callTimerInterval = null;

    let callStartedAt = null;

    let callConnectTimeout = null;

    let callDisconnectTimeout = null;

    let isRemoteAudioEnabled = true;

    const CALL_STORAGE_KEY = `fontan_call_state_${currentUserId}`;

    const CALL_CONNECT_TIMEOUT_MS = 25000;

    try {

        const pendingIncomingCall = JSON.parse(sessionStorage.getItem('pendingIncomingCall') || 'null');

        if (pendingIncomingCall && pendingIncomingCall.from_id === chatId) {

            activeCall = {

                peerId: pendingIncomingCall.from_id,

                chatId: pendingIncomingCall.chat_id,

                username: pendingIncomingCall.from_username,

                avatar: pendingIncomingCall.from_avatar,

                kind: pendingIncomingCall.kind || 'audio',

                mode: 'incoming'

            };

            sessionStorage.removeItem('pendingIncomingCall');

        }

        if (!activeCall) {

            const savedCall = JSON.parse(sessionStorage.getItem(CALL_STORAGE_KEY) || 'null');

            if (savedCall && Number(savedCall.peerId) === Number(chatId)) {

                activeCall = {

                    peerId: savedCall.peerId,

                    chatId: savedCall.chatId || chatId,

                    username: savedCall.username,

                    avatar: savedCall.avatar,

                    kind: savedCall.kind || 'audio',

                    mode: savedCall.mode || 'reconnecting',

                    restored: true

                };

                if (savedCall.startedAt) {

                    callStartedAt = savedCall.startedAt;

                }

            }

        }

    } catch (error) {

        console.error(error);

    }

    function persistCallState() {

        if (!activeCall) return;

        try {

            sessionStorage.setItem(CALL_STORAGE_KEY, JSON.stringify({

                peerId: activeCall.peerId,

                chatId: activeCall.chatId || chatId,

                username: activeCall.username,

                avatar: activeCall.avatar,

                kind: activeCall.kind || 'audio',

                mode: activeCall.mode || 'incoming',

                startedAt: callStartedAt,

                restored: !!activeCall.restored

            }));

        } catch (error) {

            console.error(error);

        }

    }

    function clearCallState() {

        try {

            sessionStorage.removeItem(CALL_STORAGE_KEY);

            sessionStorage.removeItem('pendingIncomingCall');

        } catch (error) {

            console.error(error);

        }

    }

    function clearConnectTimeout() {

        if (callConnectTimeout) {

            clearTimeout(callConnectTimeout);

            callConnectTimeout = null;

        }

    }

    function clearDisconnectTimeout() {

        if (callDisconnectTimeout) {

            clearTimeout(callDisconnectTimeout);

            callDisconnectTimeout = null;

        }

    }

    function startConnectTimeout() {

        clearConnectTimeout();

        callConnectTimeout = setTimeout(() => {

            if (!activeCall) return;

            alert('Не удалось подключить звонок. Попробуйте позвонить ещё раз.');

            finishCall(false);

        }, CALL_CONNECT_TIMEOUT_MS);

    }

    function scheduleDisconnectRecovery() {

        clearDisconnectTimeout();

        callDisconnectTimeout = setTimeout(() => {

            if (!peerConnection) return;

            if (['disconnected', 'failed', 'closed'].includes(peerConnection.connectionState)) {

                finishCall(false);

            }

        }, 8000);

    }

    function escapeHtml(value) {

        return (value || '').replace(/[&<>\"']/g, char => ({

            '&': '&amp;',

            '<': '&lt;',

            '>': '&gt;',

            '"': '&quot;',

            "'": '&#39;'

        }[char]));

    }

    function generateToken() {

        return window.generateActionToken ? window.generateActionToken() : `msg_${Date.now()}_${Math.random().toString(16).slice(2)}`;

    }

    const roomId = chatType === 'private' ? `private_${Math.min({{ current_user.id }}, chatId)}_${Math.max({{ current_user.id }}, chatId)}` : `group_${chatId}`;

    async function sendMessage(text, voiceBlob = null) {

        const trimmedText = (text || '').trim();

        if ((!trimmedText && !voiceBlob) || isSendingMessage) return;

        const formData = new FormData();

        formData.append('type', chatType);

        formData.append('target_id', chatId);

        formData.append('client_token', generateToken());

        if (trimmedText) formData.append('body', trimmedText);

        if (voiceBlob) formData.append('voice', voiceBlob, 'voice.webm');

        try {

            isSendingMessage = true;

            sendBtn.disabled = true;

            const response = await fetch(`/api/send_message`, { method: 'POST', body: formData });

            const data = await response.json();

            if (!response.ok) {

                alert(data.error || 'Не удалось отправить сообщение');

                return;

            }

            msgInput.value = '';

            loadMessages();

        } finally {

            isSendingMessage = false;

            sendBtn.disabled = false;

        }

    }

    sendBtn.addEventListener('click', () => {

        if (msgInput.value) sendMessage(msgInput.value);

    });

    msgInput.addEventListener('keydown', (event) => {

        if (event.key === 'Enter' && !event.shiftKey) {

            event.preventDefault();

            sendMessage(msgInput.value);

        }

    });

    emojiBtn.addEventListener('click', () => {

        const emoji = prompt('Р­РјРѕРґР·Рё (РЅР°РїСЂРёРјРµСЂ рџ„рџ”Ґвќ¤пёЏ)');

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

            const signature = JSON.stringify(messages.map(msg => [msg.id, msg.body, msg.edited_at, msg.read_at, msg.deleted_for_all]));

            

            if (lastRenderedSignature !== signature) {

                lastRenderedSignature = signature;

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

    

    const socket = window.fontanBaseSocket || io();

    window.fontanBaseSocket = socket;

    let typingTimeout = null;

    socket.on('connect', () => {

        socket.emit('join', { room: roomId });

        socket.emit('join_user_room', { user_id: currentUserId });

        loadMessages();

        socket.emit('presence', { online: true });

        if (chatType === 'private' && activeCall?.restored && activeCall.peerId === peerMeta.id && activeCall.mode !== 'incoming') {

            showCallOverlay('reconnecting', 'Восстанавливаем звонок...', activeCall);

            startConnectTimeout();

            socket.emit('call_invite', {

                to_user_id: activeCall.peerId,

                chat_id: chatId,

                kind: activeCall.kind || 'audio',

                from_id: currentUserId,

                from_username: currentUsername,

                from_avatar: currentUserAvatar,

                restored: true

            });

        }

    });

    socket.on('message', (data) => {

        if (data.room_id === roomId) {

            loadMessages();

        }

    });

    socket.on('typing', (data) => {

        if (data.room_id === roomId && data.user_id !== currentUserId) {

            const t = document.getElementById('typing-indicator');

            if (t) { t.style.display = 'block'; }

            clearTimeout(typingTimeout);

            typingTimeout = setTimeout(() => { if (t) t.style.display = 'none'; }, 1500);

        }

    });

    document.getElementById('msg-input')?.addEventListener('input', () => {

        socket.emit('typing', { room_id: roomId, user_id: currentUserId });

    });

    function stopRingtones() {

        [incomingRingtone, outgoingRingtone].forEach(audio => {

            if (!audio) return;

            audio.pause();

            audio.currentTime = 0;

        });

    }

    function setCallIdentity(user) {

        if (!callUsername || !callAvatar) return;

        callUsername.textContent = user?.username || 'Звонок';

        if (user?.avatar) {

            callAvatar.innerHTML = `<img src="${user.avatar}" style="width:100%; height:100%; object-fit:cover;">`;

        } else {

            callAvatar.textContent = (user?.username || '?').charAt(0).toUpperCase();

        }

    }

    function showCallOverlay(mode, statusText, user) {

        if (!callOverlay) return;

        if (activeCall) {

            activeCall.mode = mode;

            persistCallState();

        }

        setCallIdentity(user || activeCall || peerMeta);

        callOverlay.style.display = 'block';

        callStatus.textContent = statusText || 'Соединение...';

        callAcceptBtn.style.display = mode === 'incoming' ? 'inline-flex' : 'none';

        callDeclineBtn.style.display = mode === 'incoming' ? 'inline-flex' : 'none';

        callEndBtn.style.display = mode === 'incoming' ? 'none' : 'inline-flex';

    }

    function hideCallOverlay() {

        if (!callOverlay) return;

        callOverlay.style.display = 'none';

        callAcceptBtn.style.display = 'none';

        callDeclineBtn.style.display = 'none';

        callEndBtn.style.display = 'inline-flex';

        callTimer.textContent = '00:00';

        callStatus.textContent = 'Готовимся к звонку...';

        remoteMedia.style.display = 'none';

        remoteMedia.srcObject = null;

        localPreview.style.display = 'none';

        localPreview.srcObject = null;

    }

    if (activeCall) {

        if (activeCall.mode !== 'incoming') {

            showCallOverlay('reconnecting', 'Восстанавливаем звонок...', activeCall);

            startConnectTimeout();

        } else {

        showCallOverlay(

            'incoming',

            activeCall.kind === 'video' ? 'Входящий видео звонок' : 'Входящий звонок',

            activeCall

        );

        incomingRingtone?.play().catch(() => {});

        }

    }

    function startCallClock() {

        clearConnectTimeout();

        clearInterval(callTimerInterval);

        callStartedAt = Date.now();

        persistCallState();

        callTimerInterval = setInterval(() => {

            const total = Math.floor((Date.now() - callStartedAt) / 1000);

            const mins = String(Math.floor(total / 60)).padStart(2, '0');

            const secs = String(total % 60).padStart(2, '0');

            callTimer.textContent = `${mins}:${secs}`;

        }, 1000);

    }

    function stopCallClock() {

        clearInterval(callTimerInterval);

        callTimerInterval = null;

        callStartedAt = null;

    }

    async function ensureLocalStream(options = { audio: true, video: false }) {

        const needAudio = options.audio && !(localStream && localStream.getAudioTracks().length);

        const needVideo = options.video && !(localStream && localStream.getVideoTracks().length);

        if (!localStream) localStream = new MediaStream();

        if (needAudio || needVideo) {

            const stream = await navigator.mediaDevices.getUserMedia({ audio: needAudio, video: needVideo });

            stream.getTracks().forEach(track => localStream.addTrack(track));

        }

        if (localStream.getTracks().length) {

            localPreview.srcObject = localStream;

            localPreview.style.display = 'block';

        }

        return localStream;

    }

    async function ensurePeerConnection() {

        if (peerConnection) return peerConnection;

        peerConnection = new RTCPeerConnection(rtcConfig);

        remoteStream = new MediaStream();

        remoteMedia.srcObject = remoteStream;

        peerConnection.onicecandidate = (event) => {

            if (event.candidate && activeCall?.peerId) {

                socket.emit('call_signal', { to_user_id: activeCall.peerId, signal: { type: 'ice', candidate: event.candidate } });

            }

        };

        peerConnection.ontrack = (event) => {

            event.streams[0].getTracks().forEach(track => {

                if (!remoteStream.getTracks().some(existing => existing.id === track.id)) {

                    remoteStream.addTrack(track);

                }

            });

            remoteMedia.style.display = 'block';

            remoteMedia.play().catch(() => {});

        };

        peerConnection.onconnectionstatechange = () => {

            if (peerConnection.connectionState === 'connected') {

                clearDisconnectTimeout();

                if (activeCall) {

                    activeCall.mode = 'active';

                    persistCallState();

                }

                callStatus.textContent = 'В эфире';

                startCallClock();

            }

            if (peerConnection.connectionState === 'disconnected') {

                callStatus.textContent = 'Связь пропала, пытаемся восстановить...';

                scheduleDisconnectRecovery();

            }

            if (['failed', 'closed'].includes(peerConnection.connectionState)) {

                finishCall(false);

            }

        };

        if (localStream) {

            localStream.getTracks().forEach(track => peerConnection.addTrack(track, localStream));

        }

        return peerConnection;

    }

    async function sendOffer() {

        await ensurePeerConnection();

        const offer = await peerConnection.createOffer();

        await peerConnection.setLocalDescription(offer);

        socket.emit('call_signal', { to_user_id: activeCall.peerId, signal: { type: 'offer', sdp: peerConnection.localDescription } });

    }

    async function syncVideoSender(track, streamForTrack = null) {

        if (!peerConnection || !track) return;

        const sender = peerConnection.getSenders().find(item => item.track && item.track.kind === 'video');

        if (sender) {

            await sender.replaceTrack(track);

            return;

        }

        peerConnection.addTrack(track, streamForTrack || localStream);

        await sendOffer();

    }

    async function finishCall(notifyPeer = true) {

        clearConnectTimeout();

        clearDisconnectTimeout();

        stopCallClock();

        stopRingtones();

        if (notifyPeer && activeCall?.peerId) {

            socket.emit('call_end', { to_user_id: activeCall.peerId, reason: 'Звонок завершён' });

        }

        if (peerConnection) {

            peerConnection.close();

            peerConnection = null;

        }

        if (screenStream) {

            screenStream.getTracks().forEach(track => track.stop());

            screenStream = null;

        }

        if (localStream) {

            localStream.getTracks().forEach(track => track.stop());

            localStream = null;

        }

        activeCall = null;

        clearCallState();

        hideCallOverlay();

    }

    async function startOutgoingCall(kind = 'audio') {

        if (chatType !== 'private' || activeCall) return;

        activeCall = { peerId: peerMeta.id, username: peerMeta.username, avatar: peerMeta.avatar, kind, mode: 'outgoing' };

        showCallOverlay('outgoing', kind === 'video' ? 'Видео звонок...' : 'Звоним...', activeCall);

        stopRingtones();

        outgoingRingtone?.play().catch(() => {});

        startConnectTimeout();

        await ensureLocalStream({ audio: true, video: kind === 'video' });

        socket.emit('call_invite', {

            to_user_id: peerMeta.id,

            chat_id: chatId,

            kind,

            from_id: currentUserId,

            from_username: currentUsername,

            from_avatar: currentUserAvatar

        });

    }

    async function handleSignal(signal, fromUserId) {

        if (signal.type === 'offer') {

            // Если звонок уже активен — это рenegotiation (напр. screen share),

            // не сбрасываем UI и таймер

            const isRenegotiation = activeCall && activeCall.mode === 'active';

            await ensureLocalStream({ audio: true, video: activeCall?.kind === 'video' });

            await ensurePeerConnection();

            await peerConnection.setRemoteDescription(new RTCSessionDescription(signal.sdp));

            const answer = await peerConnection.createAnswer();

            await peerConnection.setLocalDescription(answer);

            socket.emit('call_signal', { to_user_id: fromUserId, signal: { type: 'answer', sdp: peerConnection.localDescription } });

            if (!isRenegotiation) {

                activeCall.mode = 'connecting';

                startConnectTimeout();

                showCallOverlay('active', 'Соединяем...', activeCall);

            }

        } else if (signal.type === 'answer' && peerConnection) {

            const isRenegotiation = activeCall && activeCall.mode === 'active';

            await peerConnection.setRemoteDescription(new RTCSessionDescription(signal.sdp));

            if (!isRenegotiation) {

                activeCall.mode = 'connecting';

                startConnectTimeout();

                showCallOverlay('active', 'Соединяем...', activeCall);

            }

        } else if (signal.type === 'ice' && peerConnection && signal.candidate) {

            try { await peerConnection.addIceCandidate(new RTCIceCandidate(signal.candidate)); } catch (error) { console.error(error); }

        }

    }

    startCallBtn?.addEventListener('click', () => startOutgoingCall('audio'));

    startVideoBtn?.addEventListener('click', () => startOutgoingCall('video'));

    callAcceptBtn?.addEventListener('click', async () => {

        if (!activeCall) return;

        stopRingtones();

        activeCall.mode = 'connecting';

        startConnectTimeout();

        showCallOverlay('active', 'Подключаемся...', activeCall);

        await ensureLocalStream({ audio: true, video: activeCall.kind === 'video' });

        socket.emit('call_accept', { to_user_id: activeCall.peerId, chat_id: activeCall.chatId, kind: activeCall.kind });

    });

    callDeclineBtn?.addEventListener('click', () => {

        if (!activeCall) return;

        socket.emit('call_decline', { to_user_id: activeCall.peerId, reason: 'Отклонено' });

        finishCall(false);

    });

    callEndBtn?.addEventListener('click', () => finishCall(true));

    callMicBtn?.addEventListener('click', async () => {

        await ensureLocalStream({ audio: true });

        const track = localStream.getAudioTracks()[0];

        if (track) track.enabled = !track.enabled;

        callMicBtn.classList.toggle('btn-danger', track && !track.enabled);

    });

    callSpeakerBtn?.addEventListener('click', () => {

        isRemoteAudioEnabled = !isRemoteAudioEnabled;

        remoteMedia.muted = !isRemoteAudioEnabled;

        callSpeakerBtn.classList.toggle('btn-danger', !isRemoteAudioEnabled);

    });

    callCameraBtn?.addEventListener('click', async () => {

        await ensureLocalStream({ audio: true, video: true });

        const track = localStream.getVideoTracks()[0];

        if (track) track.enabled = !track.enabled;

        if (peerConnection && track) {

            await syncVideoSender(track, localStream);

        }

        callCameraBtn.classList.toggle('btn-danger', track && !track.enabled);

    });

    callScreenBtn?.addEventListener('click', async () => {

        if (!activeCall) return;

        if (screenStream) {

            screenStream.getTracks().forEach(track => track.stop());

            screenStream = null;

            callScreenBtn.classList.remove('btn-danger');

            return;

        }

        try {

            // Fix screen sharing: Use a new offer/answer cycle to stabilize the connection

            screenStream = await navigator.mediaDevices.getDisplayMedia({ 

                video: { cursor: "always" },

                audio: false 

            });

            const screenTrack = screenStream.getVideoTracks()[0];

            

            if (peerConnection && screenTrack) {

                // Ensure the track is active before replacing

                if (screenTrack.readyState === 'live') {

                    await syncVideoSender(screenTrack, screenStream);

                }

            }

            

            localPreview.srcObject = screenStream;

            localPreview.style.display = 'block';

            callScreenBtn.classList.add('btn-danger');

            

            screenTrack.onended = async () => {

                screenStream = null;

                localPreview.srcObject = localStream;

                if (peerConnection && localStream?.getVideoTracks()[0]) {

                    const cameraTrack = localStream.getVideoTracks()[0];

                    await syncVideoSender(cameraTrack, localStream);

                }

                callScreenBtn.classList.remove('btn-danger');

            };

        } catch (error) {

            console.error("Screen share error:", error);

            alert("Ошибка при включении демонстрации экрана");

        }

    });

    socket.on('call_invite', (data) => {

        if (data.from_id === currentUserId || activeCall) return;

        activeCall = { peerId: data.from_id, chatId: data.chat_id, username: data.from_username, avatar: data.from_avatar, kind: data.kind || 'audio', mode: 'incoming' };

        showCallOverlay('incoming', data.kind === 'video' ? 'Входящий видео звонок' : 'Входящий звонок', activeCall);

        stopRingtones();

        incomingRingtone?.play().catch(() => {});

    });

    socket.on('call_accepted', async (data) => {

        if (!activeCall || data.from_id !== activeCall.peerId) return;

        activeCall.mode = 'connecting';

        startConnectTimeout();

        stopRingtones();

        showCallOverlay('active', 'Соединяем...', activeCall);

        await ensurePeerConnection();

        await sendOffer();

    });

    socket.on('call_declined', (data) => {

        if (activeCall && data.from_id === activeCall.peerId) {

            alert(data.reason || 'Звонок отклонён');

            finishCall(false);

        }

    });

    socket.on('call_ended', (data) => {

        if (activeCall && data.from_id === activeCall.peerId) finishCall(false);

    });

    socket.on('call_signal', async (data) => {

        try {

            if (!activeCall) activeCall = { peerId: data.from_id, username: peerMeta.username, avatar: peerMeta.avatar, kind: 'audio' };

            await handleSignal(data.signal, data.from_id);

        } catch (error) {

            console.error(error);

            finishCall(false);

        }

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

            {% if user.is_banned %}Р Р°Р·Р±Р°РЅРёС‚СЊ{% else %}Р—РђР‘РђРќРРўР¬{% endif %}

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

  <a href="{{ url_for('sessions') }}" class="text-decoration-none">История РІС…РѕРґРѕРІ Рё СѓСЃС‚СЂРѕР№СЃС‚РІР°</a>

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

    <div class="card p-4 mt-5 shadow-lg border-0" style="border-radius: 20px;">

      <h3 class="text-center mb-4 fw-bold">{{ title }}</h3>

      

      {% if show_verify %}

      <div class="alert alert-info small">📲 Код отправлен в ваш Telegram!</div>

      <form method="POST">

        <input type="hidden" name="action" value="verify_code">

        <input type="text" name="verify_code" class="form-control mb-3 rounded-pill text-center" placeholder="6-значный код" required maxlength="6" style="font-size: 1.5rem; letter-spacing: 5px;">

        <button class="btn btn-primary w-100 rounded-pill py-2 fw-bold">Подтвердить</button>

      </form>

      {% else %}

      <form method="POST">

        <input type="hidden" name="action" value="send_code">

        {% if not is_login %}

        <input type="email" name="email" class="form-control mb-3 rounded-pill" placeholder="Email" required>

        {% endif %}

        <input type="text" name="username" class="form-control mb-3 rounded-pill" placeholder="Ник" required>

        <input type="password" name="password" class="form-control mb-3 rounded-pill" placeholder="Пароль" required>

        <div class="mb-3">

          <label class="form-label text-muted small ms-2">Капча: {{ captcha_q }}</label>

          <input type="text" name="captcha" class="form-control rounded-pill" placeholder="Ответ" required>

        </div>

        <button class="btn btn-primary w-100 rounded-pill py-2 fw-bold">{{ 'Войти' if is_login else 'Зарегистрироваться' }}</button>

      </form>

      {% endif %}

      

      <div class="text-center mt-4">

        <a href="{{ url_for('login' if not is_login else 'register') }}" class="text-decoration-none text-primary">{{ 'Уже есть аккаунт? Войти' if not is_login else 'Нет аккаунта? Регистрация' }}</a>

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

<style>

    .admin-stat {

        background: linear-gradient(135deg, var(--grad-a), var(--grad-b));

        color: #fff; border-radius: 20px; padding: 22px 20px; text-align: center; border: none;

        box-shadow: 0 4px 20px rgba(0,0,0,.15);

    }

    .admin-stat h2 { font-size: 2.2rem; font-weight: 800; margin: 0; }

    .admin-stat p { margin: 4px 0 0; opacity: .85; font-size: .9rem; }

    .online-user-row { display:flex; align-items:center; gap:10px; padding:8px 0; border-bottom:1px solid var(--border-color); }

    .online-dot { width:9px; height:9px; background:#22c55e; border-radius:50%; flex-shrink:0; }

</style>

<div class="d-flex justify-content-between align-items-center mb-4">

    <h3 class="fw-bold mb-0"><i class="bi bi-shield-fill-check me-2 text-danger"></i>Панель Администратора</h3>

    <span class="badge bg-danger fs-6 rounded-pill px-3">ADMIN</span>

</div>

<!-- Stats Row -->

<div class="row g-3 mb-4">

    <div class="col-6 col-md-3">

        <div class="admin-stat" style="--grad-a:#2563eb; --grad-b:#1d4ed8;">

            <h2>{{ online_count }}</h2>

            <p><i class="bi bi-circle-fill" style="color:#86efac;"></i> Онлайн сейчас</p>

        </div>

    </div>

    <div class="col-6 col-md-3">

        <div class="admin-stat" style="--grad-a:#7c3aed; --grad-b:#5b21b6;">

            <h2>{{ peak_online }}</h2>

            <p><i class="bi bi-graph-up-arrow"></i> Пик онлайн</p>

        </div>

    </div>

    <div class="col-6 col-md-3">

        <div class="admin-stat" style="--grad-a:#f97316; --grad-b:#ea580c;">

            <h2>{{ total_visitors }}</h2>

            <p><i class="bi bi-people-fill"></i> Всего посещений</p>

        </div>

    </div>

    <div class="col-6 col-md-3">

        <div class="admin-stat" style="--grad-a:#059669; --grad-b:#047857;">

            <h2>{{ total_users }}</h2>

            <p><i class="bi bi-person-check-fill"></i> Пользователей</p>

        </div>

    </div>

    <div class="col-6 col-md-3">

        <div class="admin-stat" style="--grad-a:#db2777; --grad-b:#be185d;">

            <h2>{{ total_posts }}</h2>

            <p><i class="bi bi-file-post-fill"></i> Всего постов</p>

        </div>

    </div>

    <div class="col-6 col-md-3">

        <div class="admin-stat" style="--grad-a:#0891b2; --grad-b:#0e7490;">

            <h2>{{ total_flux }}</h2>

            <p><i class="bi bi-play-btn-fill"></i> Flux видео</p>

        </div>

    </div>

    <div class="col-12 col-md-6">

        <div class="card p-3 h-100">

            <h6 class="fw-bold mb-3">Быстрые действия</h6>

            <div class="d-flex flex-wrap gap-2">

                <a href="{{ url_for('admin_reports') }}" class="btn btn-outline-danger rounded-pill"><i class="bi bi-flag-fill me-1"></i>Жалобы</a>

                <a href="{{ url_for('users_list') }}" class="btn btn-outline-primary rounded-pill"><i class="bi bi-people-fill me-1"></i>Все пользователи</a>

                <a href="{{ url_for('admin_flux_list') }}" class="btn btn-outline-secondary rounded-pill"><i class="bi bi-play-btn-fill me-1"></i>Flux видео</a>

                <a href="{{ url_for('admin_ai_chats') }}" class="btn btn-outline-primary rounded-pill"><i class="bi bi-robot me-1"></i>FontanAI чаты</a>

            </div>

            <hr>

            <h6 class="fw-bold mb-2">Рассылка всем</h6>

            <form method="POST" action="{{ url_for('admin_broadcast') }}" class="d-flex gap-2">

                <input type="text" name="message" class="form-control rounded-pill" placeholder="Введите сообщение..." required>

                <button class="btn btn-primary rounded-pill px-4">Отправить</button>

            </form>

        </div>

    </div>

</div>

<!-- Charts -->

<div class="row g-3 mb-4">

    <div class="col-md-6">

        <div class="card p-3">

            <h6 class="fw-bold mb-3">Новые пользователи (14 дней)</h6>

            <canvas id="usersChart" height="160"></canvas>

        </div>

    </div>

    <div class="col-md-6">

        <div class="card p-3">

            <h6 class="fw-bold mb-3">Новые посты (14 дней)</h6>

            <canvas id="postsChart" height="160"></canvas>

        </div>

    </div>

</div>

<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>

<script>

const labels = {{ chart_labels|tojson }};

const chartDefaults = {

    fill: true,

    tension: 0.4,

    pointRadius: 3,

    borderWidth: 2,

};

new Chart(document.getElementById('usersChart'), {

    type: 'line',

    data: { labels, datasets: [{ ...chartDefaults, label: 'Пользователи', data: {{ users_data|tojson }}, borderColor:'#2563eb', backgroundColor:'rgba(37,99,235,.12)' }] },

    options: { plugins:{ legend:{display:false} }, scales:{ y:{ beginAtZero:true, ticks:{stepSize:1} } } }

});

new Chart(document.getElementById('postsChart'), {

    type: 'line',

    data: { labels, datasets: [{ ...chartDefaults, label: 'Посты', data: {{ posts_data|tojson }}, borderColor:'#f97316', backgroundColor:'rgba(249,115,22,.12)' }] },

    options: { plugins:{ legend:{display:false} }, scales:{ y:{ beginAtZero:true, ticks:{stepSize:1} } } }

});

</script>

{% endblock %}

""",

    'admin_flux.html': """

{% extends "base.html" %}

{% block content %}

<div class="d-flex justify-content-between align-items-center mb-4">

    <h3 class="fw-bold mb-0"><i class="bi bi-play-btn-fill me-2 text-primary"></i>Управление Flux видео</h3>

    <a href="{{ url_for('admin_dashboard') }}" class="btn btn-outline-secondary rounded-pill"><i class="bi bi-arrow-left me-1"></i>Назад</a>

</div>

<div class="row g-3 mb-4">

    <div class="col-6 col-md-3">

        <div class="card p-3 text-center border-0" style="background:linear-gradient(135deg,#2563eb,#1d4ed8);color:#fff;border-radius:16px;">

            <h3 class="fw-bold mb-0">{{ total }}</h3>

            <small>Всего видео</small>

        </div>

    </div>

    <div class="col-6 col-md-3">

        <div class="card p-3 text-center border-0" style="background:linear-gradient(135deg,#f97316,#ea580c);color:#fff;border-radius:16px;">

            <h3 class="fw-bold mb-0">{{ total_views }}</h3>

            <small>Всего просмотров</small>

        </div>

    </div>

</div>

<div class="card p-0 overflow-hidden">

<table class="table table-hover mb-0" style="color:var(--text-color);">

    <thead style="background:var(--hover-bg);">

        <tr>

            <th class="ps-3">ID</th>

            <th>Автор</th>

            <th>Описание</th>

            <th>Просмотры</th>

            <th>Лайки</th>

            <th>Дата</th>

            <th>Действие</th>

        </tr>

    </thead>

    <tbody>

    {% for v in videos %}

    <tr>

        <td class="ps-3 text-muted small">{{ v.id }}</td>

        <td>

            <a href="{{ url_for('profile', username=v.author.username) }}" class="text-decoration-none fw-semibold">

                {{ v.author.username }}

            </a>

        </td>

        <td class="text-muted small" style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">

            {{ v.description or '—' }}

        </td>

        <td><i class="bi bi-eye me-1"></i>{{ v.views }}</td>

        <td><i class="bi bi-heart me-1 text-danger"></i>{{ v.likes }}</td>

        <td class="text-muted small">{{ v.timestamp|time_ago }}</td>

        <td>

            <form method="POST" action="{{ url_for('admin_delete_flux', video_id=v.id) }}"

                  onsubmit="return confirm('Удалить это видео?');" style="display:inline;">

                <button type="submit" class="btn btn-sm btn-outline-danger rounded-pill">

                    <i class="bi bi-trash-fill"></i> Удалить

                </button>

            </form>

        </td>

    </tr>

    {% else %}

    <tr><td colspan="7" class="text-center text-muted py-4">Нет видео</td></tr>

    {% endfor %}

    </tbody>

</table>

</div>

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

    {% for post in posts %}

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

  <div class="text-muted mt-2">История РёСЃС‡РµР·РЅРµС‚: {{ story.expires_at|time_ago }}</div>

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

    'flux.html': """

{% extends "base.html" %}

{% block content %}

<style>

    body { background-color: #000 !important; color: #fff !important; }

    .flux-page-wrap { max-width: 480px; margin: 0 auto; position: relative; }

    .flux-container {

        height: calc(100dvh - 70px);

        overflow-y: scroll;

        scroll-snap-type: y mandatory;

        scroll-behavior: smooth;

        -webkit-overflow-scrolling: touch;

    }

    .flux-container::-webkit-scrollbar { display: none; }

    .flux-item {

        height: calc(100dvh - 70px);

        scroll-snap-align: start;

        position: relative;

        background: #000;

    }

    .flux-item video {

        width: 100%; height: 100%; object-fit: cover;

        display: block;

    }

    .flux-overlay {

        position: absolute; bottom: 0; left: 0; right: 0;

        background: linear-gradient(transparent 30%, rgba(0,0,0,0.75) 100%);

        padding: 20px 16px 24px;

        display: flex; justify-content: space-between; align-items: flex-end;

    }

    .flux-info { flex: 1; padding-right: 12px; }

    .flux-info .username { font-weight: 700; font-size: 1rem; }

    .flux-info .desc { font-size: 0.88rem; opacity: 0.9; margin-top: 4px; max-height: 60px; overflow: hidden; }

    .flux-info .views-badge { font-size: 0.78rem; opacity: 0.65; margin-top: 6px; }

    .flux-actions {

        display: flex; flex-direction: column; gap: 18px; align-items: center; min-width: 56px;

    }

    .flux-btn {

        background: rgba(255,255,255,0.12);

        border: none; border-radius: 50%;

        width: 52px; height: 52px; color: #fff; font-size: 22px;

        display: flex; align-items: center; justify-content: center;

        backdrop-filter: blur(8px);

        cursor: pointer; transition: transform .15s, background .2s;

    }

    .flux-btn:hover { transform: scale(1.12); background: rgba(255,255,255,0.22); }

    .flux-btn.liked { color: #ff4d4d; background: rgba(255,77,77,0.2); }

    .flux-btn-label { font-size: 0.75rem; text-align: center; margin-top: -10px; opacity: 0.8; }

    .flux-upload-fab {

        position: fixed; bottom: 30px; right: 24px; z-index: 200;

        background: linear-gradient(135deg, #4f46e5, #7c3aed);

        border: none; border-radius: 50%; width: 56px; height: 56px;

        color: #fff; font-size: 28px; display: flex; align-items: center; justify-content: center;

        box-shadow: 0 6px 24px rgba(79,70,229,.5); cursor: pointer;

    }

    .flux-my-btn {

        position: fixed; bottom: 96px; right: 24px; z-index: 200;

        background: rgba(255,255,255,0.15);

        border: none; border-radius: 50%; width: 46px; height: 46px;

        color: #fff; font-size: 20px; display: flex; align-items: center; justify-content: center;

        backdrop-filter: blur(10px); cursor: pointer;

    }

    /* Comment drawer */

    .flux-comments-drawer {

        position: fixed; bottom: 0; left: 50%; transform: translateX(-50%);

        width: min(480px, 100vw); max-height: 60vh;

        background: #1a1a2e; border-radius: 24px 24px 0 0;

        z-index: 500; display: none; flex-direction: column;

        box-shadow: 0 -4px 40px rgba(0,0,0,.6);

    }

    .flux-comments-drawer.open { display: flex; }

    .drawer-header {

        padding: 14px 20px 10px; display: flex; justify-content: space-between; align-items: center;

        border-bottom: 1px solid rgba(255,255,255,0.08);

    }

    .drawer-comments-list { flex: 1; overflow-y: auto; padding: 12px 16px; }

    .drawer-comment {

        display: flex; gap: 10px; margin-bottom: 14px;

    }

    .drawer-comment-avatar {

        width: 34px; height: 34px; border-radius: 50%; background: #4f46e5;

        display: flex; align-items: center; justify-content: center; font-weight: 700; flex-shrink: 0;

        overflow: hidden;

    }

    .drawer-comment-avatar img { width: 100%; height: 100%; object-fit: cover; }

    .drawer-comment-body { flex: 1; }

    .drawer-comment-name { font-size: 0.82rem; font-weight: 600; opacity: 0.8; }

    .drawer-comment-text { font-size: 0.93rem; }

    .drawer-input-row {

        display: flex; gap: 10px; padding: 12px 16px;

        border-top: 1px solid rgba(255,255,255,0.08);

        background: #1a1a2e;

    }

    .drawer-input-row input {

        flex: 1; background: rgba(255,255,255,0.08); border: none; border-radius: 20px;

        padding: 10px 16px; color: #fff; font-size: 0.93rem;

    }

    .drawer-input-row input::placeholder { color: rgba(255,255,255,0.4); }

    .drawer-input-row button {

        background: #4f46e5; border: none; border-radius: 50%; width: 40px; height: 40px;

        color: #fff; display: flex; align-items: center; justify-content: center;

    }

    .drawer-backdrop {

        display: none; position: fixed; inset: 0; background: rgba(0,0,0,.5); z-index: 499;

    }

    .drawer-backdrop.open { display: block; }

</style>

<div class="flux-page-wrap">

    <div class="flux-container" id="flux-container">

        {% for video in videos %}

        <div class="flux-item" id="video-{{ video.id }}" data-vid-id="{{ video.id }}">

            <video src="{{ video.video_url }}" loop playsinline preload="metadata"

                   onclick="togglePlay(this)"></video>

            <div class="flux-overlay">

                <div class="flux-info">

                    <div class="username">@{{ video.author.username }}</div>

                    {% if video.description %}

                    <div class="desc">{{ video.description }}</div>

                    {% endif %}

                    <div class="views-badge">

                        <i class="bi bi-eye-fill"></i> {{ video.views }}

                    </div>

                </div>

                <div class="flux-actions">

                    <div>

                        <button class="flux-btn {% if current_user.id in video_likes[video.id] %}liked{% endif %}"

                                onclick="likeFlux({{ video.id }}, this)" id="like-btn-{{ video.id }}">

                            <i class="bi bi-heart-fill"></i>

                        </button>

                        <div class="flux-btn-label" id="like-count-{{ video.id }}">{{ video_likes[video.id]|length }}</div>

                    </div>

                    <div>

                        <button class="flux-btn" onclick="openComments({{ video.id }})">

                            <i class="bi bi-chat-dots-fill"></i>

                        </button>

                        <div class="flux-btn-label">{{ video_comments[video.id]|length }}</div>

                    </div>

                    <div>

                        <button class="flux-btn" onclick="shareFlux({{ video.id }})">

                            <i class="bi bi-share-fill"></i>

                        </button>

                    </div>

                </div>

            </div>

        </div>

        {% else %}

        <div class="d-flex align-items-center justify-content-center" style="height:100%; color:#fff;">

            <div class="text-center opacity-50">

                <i class="bi bi-play-btn" style="font-size:4rem;"></i>

                <h5 class="mt-3">Пока нет видео. Будь первым!</h5>

            </div>

        </div>

        {% endfor %}

    </div>

</div>

<!-- FABs -->

<button class="flux-upload-fab" data-bs-toggle="modal" data-bs-target="#uploadFluxModal" title="Загрузить">

    <i class="bi bi-plus-lg"></i>

</button>

<a href="{{ url_for('flux_my_videos') }}" class="flux-my-btn" title="Мои видео">

    <i class="bi bi-person-video3"></i>

</a>

<!-- Comment Drawer -->

<div class="drawer-backdrop" id="drawer-backdrop" onclick="closeComments()"></div>

<div class="flux-comments-drawer" id="comments-drawer">

    <div class="drawer-header">

        <span class="fw-bold">Комментарии</span>

        <button class="btn btn-sm text-white opacity-60" onclick="closeComments()" style="background:none; border:none;">

            <i class="bi bi-x-lg fs-5"></i>

        </button>

    </div>

    <div class="drawer-comments-list" id="drawer-comments-list">

        <div class="text-center opacity-40 py-3 small">Загрузка...</div>

    </div>

    <div class="drawer-input-row">

        <input type="text" id="comment-input" placeholder="Написать комментарий..." maxlength="300">

        <button onclick="submitComment()"><i class="bi bi-send-fill"></i></button>

    </div>

</div>

<!-- Upload Modal -->

<div class="modal fade" id="uploadFluxModal" tabindex="-1">

    <div class="modal-dialog modal-dialog-centered">

        <div class="modal-content" style="background:#1a1a2e; color:#fff; border-radius:20px; border:1px solid rgba(255,255,255,.1);">

            <div class="modal-header border-0 pb-0">

                <h5 class="modal-title fw-bold"><i class="bi bi-play-btn-fill me-2" style="color:#7c3aed;"></i>Выложить Flux</h5>

                <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>

            </div>

            <form action="{{ url_for('upload_flux') }}" method="POST" enctype="multipart/form-data">

                <div class="modal-body">

                    <div class="mb-3">

                        <label class="form-label small opacity-60">Видео (вертикальный формат)</label>

                        <input type="file" name="video" class="form-control"

                               style="background:rgba(255,255,255,0.07); color:#fff; border-color:rgba(255,255,255,0.15);"

                               accept="video/*" required>

                    </div>

                    <div class="mb-3">

                        <textarea name="description" class="form-control"

                                  style="background:rgba(255,255,255,0.07); color:#fff; border-color:rgba(255,255,255,0.15);"

                                  rows="3" placeholder="Описание..."></textarea>

                    </div>

                </div>

                <div class="modal-footer border-0 pt-0">

                    <button type="submit" class="btn w-100 rounded-pill fw-bold"

                            style="background:linear-gradient(135deg,#4f46e5,#7c3aed); color:#fff;">

                        Опубликовать <i class="bi bi-send-fill ms-1"></i>

                    </button>

                </div>

            </form>

        </div>

    </div>

</div>

<script>

    let currentCommentVideoId = null;

    const allComments = {{ video_comments_data|tojson }};

    // Auto-play on scroll

    const container = document.getElementById('flux-container');

    let currentVideo = null;

    const viewedSet = new Set(); // Дедупликация просмотров в рамках сессии браузера

    const observer = new IntersectionObserver((entries) => {

        entries.forEach(entry => {

            const video = entry.target.querySelector('video');

            const vidId = entry.target.dataset.vidId;

            if (!video) return;

            if (entry.isIntersecting) {

                if (currentVideo && currentVideo !== video) {

                    currentVideo.pause();

                    currentVideo.currentTime = 0;

                }

                video.play().catch(() => {});

                currentVideo = video;

                // Считаем просмотр только один раз за сессию страницы

                if (vidId && !viewedSet.has(vidId)) {

                    viewedSet.add(vidId);

                    fetch(`/flux/view/${vidId}`, { method: 'POST' });

                }

            } else {

                video.pause();

            }

        });

    }, { threshold: 0.7 });

    document.querySelectorAll('.flux-item').forEach(item => observer.observe(item));

    // Авто-скролл к видео по якорю в URL (например /flux#video-42)

    if (window.location.hash) {

        const target = document.querySelector(window.location.hash);

        if (target) {

            setTimeout(() => target.scrollIntoView({ behavior: 'smooth', block: 'center' }), 300);

        }

    }

    function togglePlay(video) {

        if (video.paused) video.play();

        else video.pause();

    }

    function likeFlux(id, btn) {

        fetch(`/flux/like/${id}`, { method: 'POST' })

            .then(r => r.json())

            .then(data => {

                if (data.liked) btn.classList.add('liked');

                else btn.classList.remove('liked');

                const countEl = document.getElementById(`like-count-${id}`);

                if (countEl) countEl.textContent = data.likes_count;

            });

    }

    function shareFlux(videoId) {

        const full = window.location.origin + '/flux#video-' + videoId;

        if (navigator.share) {

            navigator.share({ url: full });

        } else {

            navigator.clipboard.writeText(full).then(() => {

                const toast = document.createElement('div');

                toast.className = 'position-fixed bottom-0 start-50 translate-middle-x mb-5';

                toast.innerHTML = '<div class="alert alert-dark text-white px-4 py-2 rounded-pill shadow">Ссылка скопирована!</div>';

                document.body.appendChild(toast);

                setTimeout(() => toast.remove(), 2000);

            });

        }

    }

    function openComments(videoId) {

        currentCommentVideoId = videoId;

        const list = document.getElementById('drawer-comments-list');

        const comments = allComments[videoId] || [];

        if (comments.length === 0) {

            list.innerHTML = '<div class="text-center opacity-40 py-4 small">Комментариев пока нет. Будь первым!</div>';

        } else {

            list.innerHTML = comments.map(c => `

                <div class="drawer-comment">

                    <div class="drawer-comment-avatar">

                        ${c.avatar ? `<img src="${c.avatar}">` : c.username[0].toUpperCase()}

                    </div>

                    <div class="drawer-comment-body">

                        <div class="drawer-comment-name">@${c.username}</div>

                        <div class="drawer-comment-text">${c.text}</div>

                    </div>

                </div>

            `).join('');

        }

        document.getElementById('comments-drawer').classList.add('open');

        document.getElementById('drawer-backdrop').classList.add('open');

    }

    function closeComments() {

        document.getElementById('comments-drawer').classList.remove('open');

        document.getElementById('drawer-backdrop').classList.remove('open');

        currentCommentVideoId = null;

    }

    async function submitComment() {

        if (!currentCommentVideoId) return;

        const input = document.getElementById('comment-input');

        const text = input.value.trim();

        if (!text) return;

        const fd = new FormData();

        fd.append('text', text);

        const resp = await fetch(`/flux/comment/ajax/${currentCommentVideoId}`, { method: 'POST', body: fd });

        const data = await resp.json();

        if (data.ok) {

            input.value = '';

            // Add to local list

            if (!allComments[currentCommentVideoId]) allComments[currentCommentVideoId] = [];

            allComments[currentCommentVideoId].push({ username: data.username, avatar: data.avatar, text: data.text });

            openComments(currentCommentVideoId);

        }

    }

    document.getElementById('comment-input').addEventListener('keydown', (e) => {

        if (e.key === 'Enter') submitComment();

    });

</script>

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

""",

    'flux_my_videos.html': """

{% extends "base.html" %}

{% block content %}

<style>

    .flux-stat-card {

        background: linear-gradient(135deg, #1a1a2e, #16213e);

        color: #fff;

        border-radius: 20px;

        padding: 24px;

        text-align: center;

        border: 1px solid rgba(255,255,255,0.08);

    }

    .flux-stat-card h2 { font-size: 2.4rem; font-weight: 800; margin: 0; }

    .flux-stat-card p { opacity: 0.7; margin: 0; font-size: 0.9rem; }

    .flux-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 16px; }

    .flux-thumb {

        position: relative; border-radius: 16px; overflow: hidden; aspect-ratio: 9/16;

        background: #000; cursor: pointer;

    }

    .flux-thumb video { width: 100%; height: 100%; object-fit: cover; }

    .flux-thumb-overlay {

        position: absolute; bottom: 0; left: 0; right: 0;

        background: linear-gradient(transparent, rgba(0,0,0,0.85));

        padding: 12px; color: #fff;

    }

    .flux-delete-btn {

        position: absolute; top: 10px; right: 10px;

        background: rgba(220,38,38,0.8); border: none; border-radius: 50%;

        width: 34px; height: 34px; color: #fff; display: flex; align-items: center; justify-content: center;

        backdrop-filter: blur(6px); cursor: pointer;

    }

</style>

<div class="d-flex justify-content-between align-items-center mb-4">

    <h3 class="fw-bold mb-0"><i class="bi bi-play-btn-fill me-2"></i>Мои Flux</h3>

    <a href="{{ url_for('flux_feed') }}" class="btn btn-primary rounded-pill px-4">

        <i class="bi bi-play-circle me-1"></i> Смотреть ленту

    </a>

</div>

<!-- Аналитика -->

<div class="row g-3 mb-4">

    <div class="col-4">

        <div class="flux-stat-card">

            <h2>{{ stats.total_videos }}</h2>

            <p><i class="bi bi-play-fill"></i> Видео</p>

        </div>

    </div>

    <div class="col-4">

        <div class="flux-stat-card">

            <h2>{{ stats.total_views }}</h2>

            <p><i class="bi bi-eye-fill"></i> Просмотров</p>

        </div>

    </div>

    <div class="col-4">

        <div class="flux-stat-card">

            <h2>{{ stats.total_likes }}</h2>

            <p><i class="bi bi-heart-fill"></i> Лайков</p>

        </div>

    </div>

</div>

{% if my_videos %}

<div class="flux-grid">

    {% for video in my_videos %}

    <div class="flux-thumb">

        <video src="{{ video.video_url }}" muted loop playsinline

               onmouseover="this.play()" onmouseout="this.pause()"></video>

        <div class="flux-thumb-overlay">

            <div class="d-flex gap-3 mb-1">

                <span><i class="bi bi-eye-fill"></i> {{ video.views }}</span>

                <span><i class="bi bi-heart-fill" style="color:#ff4d4d"></i> {{ video.likes }}</span>

                <span><i class="bi bi-chat-fill"></i> {{ video_comments[video.id] }}</span>

            </div>

            {% if video.description %}

            <div class="small text-truncate opacity-75">{{ video.description }}</div>

            {% endif %}

            <div class="small opacity-50">{{ video.timestamp|time_ago }}</div>

        </div>

        <form method="POST" action="{{ url_for('delete_flux', video_id=video.id) }}"

              onsubmit="return confirm('Удалить видео?')">

            <button type="submit" class="flux-delete-btn" title="Удалить">

                <i class="bi bi-trash-fill"></i>

            </button>

        </form>

    </div>

    {% endfor %}

</div>

{% else %}

<div class="text-center py-5">

    <i class="bi bi-camera-video" style="font-size:4rem; opacity:0.3;"></i>

    <h5 class="mt-3 opacity-50">Ты ещё не выкладывал видео</h5>

    <a href="{{ url_for('flux_feed') }}" class="btn btn-primary rounded-pill mt-3 px-5">

        Выложить первое <i class="bi bi-plus-lg"></i>

    </a>

</div>

{% endif %}

{% endblock %}

""",

    'fontan_ai.html': """{% extends "base.html" %}
{% block content %}

<style>
.ai-layout { display:flex; gap:0; height:calc(100vh - 120px); max-height:800px; border-radius:20px; overflow:hidden; border:1px solid var(--border-color); background:var(--card-bg); }
.ai-sidebar { width:260px; min-width:220px; border-right:1px solid var(--border-color); display:flex; flex-direction:column; background:var(--card-bg); }
.ai-sidebar-header { padding:16px; border-bottom:1px solid var(--border-color); }
.ai-chat-list { flex:1; overflow-y:auto; padding:8px; }
.ai-chat-item { padding:10px 14px; border-radius:12px; cursor:pointer; margin-bottom:4px; transition:background .2s; display:flex; align-items:center; gap:8px; }
.ai-chat-item:hover, .ai-chat-item.active { background:var(--hover-bg); }
.ai-chat-item .chat-title { font-size:.88rem; flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.ai-chat-item .chat-time { font-size:.72rem; color:var(--text-muted); flex-shrink:0; }
.ai-main { flex:1; display:flex; flex-direction:column; min-width:0; }
.ai-chat-header { padding:14px 20px; border-bottom:1px solid var(--border-color); display:flex; align-items:center; gap:12px; }
.ai-messages { flex:1; overflow-y:auto; padding:20px; display:flex; flex-direction:column; gap:12px; }
.ai-msg { display:flex; gap:10px; max-width:85%; animation:fadeIn .3s ease-out; }
.ai-msg.user { align-self:flex-end; flex-direction:row-reverse; }
.ai-msg.assistant { align-self:flex-start; }
.ai-bubble { padding:10px 16px; border-radius:18px; font-size:.93rem; line-height:1.5; word-break:break-word; }
.ai-msg.user .ai-bubble { background:linear-gradient(135deg,#4f46e5,#7c3aed); color:#fff; border-radius:18px 18px 4px 18px; }
.ai-msg.assistant .ai-bubble { background:var(--hover-bg); color:var(--text-color); border-radius:18px 18px 18px 4px; }
.ai-avatar { width:34px; height:34px; border-radius:50%; display:flex; align-items:center; justify-content:center; font-size:1.1rem; flex-shrink:0; }
.ai-avatar.bot { background:linear-gradient(135deg,#4f46e5,#7c3aed); color:#fff; }
.ai-avatar.user { background:var(--hover-bg); }
.ai-input-area { padding:14px 20px; border-top:1px solid var(--border-color); }
.ai-input-row { display:flex; gap:8px; align-items:flex-end; background:var(--hover-bg); border-radius:16px; padding:8px 12px; }
.ai-input-row textarea { flex:1; background:transparent; border:none; resize:none; color:var(--text-color); font-size:.93rem; max-height:120px; outline:none; padding:4px 0; }
.ai-send-btn { width:38px; height:38px; border-radius:50%; background:linear-gradient(135deg,#4f46e5,#7c3aed); border:none; color:#fff; display:flex; align-items:center; justify-content:center; cursor:pointer; flex-shrink:0; transition:transform .15s; }
.ai-send-btn:hover:not(:disabled) { transform:scale(1.1); }
.ai-send-btn:disabled { opacity:.4; cursor:not-allowed; }
.ai-typing { display:flex; gap:4px; align-items:center; padding:10px 16px; background:var(--hover-bg); border-radius:18px 18px 18px 4px; width:fit-content; }
.ai-typing span { width:8px; height:8px; border-radius:50%; background:var(--text-muted); animation:typingBounce 1.2s infinite; }
.ai-typing span:nth-child(2) { animation-delay:.2s; }
.ai-typing span:nth-child(3) { animation-delay:.4s; }
@keyframes typingBounce { 0%,60%,100%{transform:translateY(0);} 30%{transform:translateY(-6px);} }
.ai-file-preview { display:flex; align-items:center; gap:8px; background:var(--card-bg); border-radius:10px; padding:6px 10px; margin-bottom:6px; font-size:.82rem; border:1px solid var(--border-color); }
.ai-file-label { cursor:pointer; color:var(--text-muted); }
.ai-file-label:hover { color:var(--accent); }
.ai-empty { flex:1; display:flex; flex-direction:column; align-items:center; justify-content:center; color:var(--text-muted); gap:12px; }
@keyframes fadeIn { from{opacity:0;transform:translateY(10px);} to{opacity:1;transform:translateY(0);} }
@media(max-width:600px){.ai-sidebar{display:none;} .ai-sidebar.show{display:flex;position:fixed;inset:0;z-index:999;width:100%;}}
.ai-msg-file img { max-width:220px; border-radius:12px; margin-top:6px; cursor:pointer; }
.ai-msg-file a { color:inherit; text-decoration:underline; font-size:.82rem; }
.ai-model-bar { display:flex; gap:6px; align-items:center; margin-bottom:8px; }
.ai-model-btn { display:flex; align-items:center; gap:5px; padding:5px 12px; border-radius:20px; border:1.5px solid var(--border-color); background:transparent; color:var(--text-muted); font-size:.82rem; cursor:pointer; transition:all .2s; }
.ai-model-btn.active { border-color:#7c3aed; background:rgba(124,58,237,.12); color:#7c3aed; font-weight:600; }
.ai-model-btn:hover:not(.active) { border-color:var(--text-muted); }
.ai-model-cost { font-size:.72rem; background:rgba(124,58,237,.18); color:#7c3aed; border-radius:8px; padding:1px 5px; }
.ai-credits-bar { display:flex; align-items:center; gap:8px; font-size:.8rem; color:var(--text-muted); margin-bottom:8px; }
.ai-credits-pill { background:rgba(124,58,237,.13); color:#7c3aed; border-radius:12px; padding:3px 10px; font-weight:700; font-size:.82rem; }
.ai-credits-low { background:rgba(239,68,68,.13); color:#ef4444; }
.ai-code-block { position:relative; margin:8px 0; border-radius:10px; overflow:hidden; }
.ai-code-block pre { margin:0; padding:12px 14px 12px 14px; background:#1e1e2e; color:#cdd6f4; font-size:.85rem; overflow-x:auto; }
.ai-code-block code { font-family:'Fira Code',monospace,sans-serif; }
.ai-copy-btn { position:absolute; top:6px; right:6px; background:rgba(255,255,255,.12); border:none; border-radius:7px; color:#fff; padding:3px 9px; font-size:.75rem; cursor:pointer; display:flex; align-items:center; gap:4px; transition:background .2s; }
.ai-copy-btn:hover { background:rgba(255,255,255,.25); }
.ai-copy-btn.copied { background:rgba(34,197,94,.3); color:#86efac; }
.ai-code-lang { position:absolute; top:7px; left:10px; font-size:.7rem; color:#888; font-family:monospace; }
.ai-model-badge { font-size:.68rem; padding:1px 6px; border-radius:6px; margin-left:4px; }
.ai-model-badge.fast { background:rgba(59,130,246,.15); color:#3b82f6; }
.ai-model-badge.smart { background:rgba(124,58,237,.15); color:#7c3aed; }
</style>

<div class="ai-layout">
  <div class="ai-sidebar" id="aiSidebar">
    <div class="ai-sidebar-header">
      <div class="d-flex align-items-center justify-content-between mb-2">
        <span class="fw-bold"><i class="bi bi-robot me-1" style="color:#7c3aed"></i>FontanAI</span>
      </div>
      <button class="btn btn-primary btn-sm w-100 rounded-pill" onclick="newChat()">
        <i class="bi bi-plus-lg me-1"></i>Новый чат
      </button>
    </div>
    <div class="ai-chat-list" id="chatList">
      {% for c in chats %}
      <div class="ai-chat-item {% if loop.first %}active{% endif %}" data-chat-id="{{ c.id }}" onclick="loadChat({{ c.id }}, this)">
        <i class="bi bi-chat-dots text-muted" style="font-size:.9rem;flex-shrink:0;"></i>
        <span class="chat-title">{{ c.title }}</span>
        <span class="chat-time">{{ c.updated_at|time_ago }}</span>
      </div>
      {% endfor %}
    </div>
  </div>

  <div class="ai-main">
    <div class="ai-chat-header">
      <button class="btn btn-sm btn-outline-secondary d-md-none" onclick="document.getElementById('aiSidebar').classList.toggle('show')">
        <i class="bi bi-list"></i>
      </button>
      <div class="ai-avatar bot"><i class="bi bi-robot"></i></div>
      <div class="flex-1">
        <span class="fw-semibold" id="chatTitle">{% if chats %}{{ chats[0].title }}{% else %}FontanAI{% endif %}</span>
        <div class="text-muted small" style="font-size:.75rem;" id="modelHint">Powered by Groq &middot; выбери модель ниже</div>
      </div>
      <div class="ms-auto d-flex gap-2">
        <button class="btn btn-sm btn-outline-danger rounded-pill" id="deleteChatBtn" onclick="deleteCurrentChat()" style="display:none;">
          <i class="bi bi-trash"></i>
        </button>
      </div>
    </div>

    <div class="ai-messages" id="aiMessages">
      <div class="ai-empty" id="aiEmpty">
        <i class="bi bi-robot" style="font-size:3.5rem;opacity:.3;"></i>
        <div class="text-center">
          <div class="fw-semibold">FontanAI готов к работе</div>
          <div class="small opacity-75">Задай вопрос или создай новый чат</div>
        </div>
      </div>
    </div>

    <div class="ai-input-area">
      <div class="ai-credits-bar" id="creditsBar">
        <i class="bi bi-lightning-charge-fill" style="color:#7c3aed"></i>
        <span>Кредиты:</span>
        <span class="ai-credits-pill" id="creditsVal">{{ ai_credit_state.balance }}</span>
        <span class="text-muted" style="font-size:.75rem">/ {{ ai_credit_state.limit }} в день</span>
      </div>
      <div class="ai-model-bar">
        {% for m in ai_model_options %}
        <button class="ai-model-btn {% if loop.first %}active{% endif %}"
                data-model-key="{{ m.key }}"
                data-model-cost="{{ m.cost }}"
                data-model-hint="{{ m.hint }}"
                onclick="selectModel(this)"
                title="{{ m.hint }}">
          {% if m.key == 'fast' %}<i class="bi bi-lightning-fill" style="font-size:.85rem"></i>
          {% else %}<i class="bi bi-stars" style="font-size:.85rem"></i>{% endif %}
          {{ m.label }}
          <span class="ai-model-cost">{{ m.cost }} кр.</span>
        </button>
        {% endfor %}
      </div>
      <div id="filePreview" style="display:none;" class="ai-file-preview">
        <i class="bi bi-paperclip"></i>
        <span id="filePreviewName" class="flex-1 text-truncate"></span>
        <button class="btn btn-sm btn-link text-danger p-0" onclick="clearFile()"><i class="bi bi-x"></i></button>
      </div>
      <div class="ai-input-row">
        <label class="ai-file-label" for="aiFileInput" title="Прикрепить файл">
          <i class="bi bi-paperclip fs-5"></i>
        </label>
        <input type="file" id="aiFileInput" style="display:none;" accept="image/*,.pdf,.txt,.doc,.docx" onchange="handleFileSelect(this)">
        <textarea id="aiInput" placeholder="Напиши сообщение…" rows="1"
                  onkeydown="if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();aiSendMessage();}"
                  oninput="this.style.height='auto';this.style.height=this.scrollHeight+'px'"></textarea>
        <button class="ai-send-btn" id="aiSendBtn" onclick="aiSendMessage()">
          <i class="bi bi-send-fill"></i>
        </button>
      </div>
    </div>
  </div>
</div>

<script>
let currentChatId = {% if chats %}{{ chats[0].id }}{% else %}null{% endif %};
let isWaiting = false;
let aiNextSendAt = 0;
let selectedModelKey = '{{ ai_model_options[0].key if ai_model_options else "fast" }}';
const AI_COOLDOWN_SECONDS = 5;

function selectModel(btn) {
  document.querySelectorAll('.ai-model-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  selectedModelKey = btn.dataset.modelKey;
  document.getElementById('modelHint').textContent = btn.dataset.modelHint;
}

function startAiCooldown(seconds) {
  const secs = Math.max(0, parseInt(seconds || 0, 10));
  if (!secs) return;
  aiNextSendAt = Date.now() + (secs * 1000);
}

function updateCredits(creditObj) {
  if (!creditObj) return;
  const el = document.getElementById('creditsVal');
  if (!el) return;
  el.textContent = creditObj.balance;
  el.classList.toggle('ai-credits-low', creditObj.balance <= 5);
}

{% if chats %}loadChat({{ chats[0].id }}, document.querySelector('.ai-chat-item'));{% endif %}

async function newChat() {
  const res = await fetch('/api/ai/new_chat', {method:'POST'});
  const data = await res.json();
  currentChatId = data.chat_id;
  const list = document.getElementById('chatList');
  const item = document.createElement('div');
  item.className = 'ai-chat-item active';
  item.dataset.chatId = data.chat_id;
  item.onclick = function(){ loadChat(data.chat_id, this); };
  item.innerHTML = `<i class="bi bi-chat-dots text-muted" style="font-size:.9rem;flex-shrink:0;"></i><span class="chat-title">${data.title}</span><span class="chat-time">только что</span>`;
  list.querySelectorAll('.ai-chat-item').forEach(el => el.classList.remove('active'));
  list.prepend(item);
  document.getElementById('aiMessages').innerHTML = '<div class="ai-empty" id="aiEmpty"><i class="bi bi-robot" style="font-size:3.5rem;opacity:.3;"></i><div class="text-center"><div class="fw-semibold">Новый чат</div><div class="small opacity-75">Задай вопрос FontanAI</div></div></div>';
  document.getElementById('chatTitle').textContent = 'Новый чат';
  document.getElementById('deleteChatBtn').style.display = 'inline-block';
}

async function loadChat(chatId, el) {
  currentChatId = chatId;
  document.querySelectorAll('.ai-chat-item').forEach(i => i.classList.remove('active'));
  if (el) el.classList.add('active');
  document.getElementById('deleteChatBtn').style.display = 'inline-block';
  const box = document.getElementById('aiMessages');
  box.innerHTML = '<div class="text-center py-4 text-muted small">Загрузка…</div>';
  const res = await fetch(`/api/ai/chat/${chatId}`);
  const data = await res.json();
  document.getElementById('chatTitle').textContent = data.title || 'Чат';
  updateCredits(data.credits);
  box.innerHTML = '';
  if (!data.messages || data.messages.length === 0) {
    box.innerHTML = '<div class="ai-empty" id="aiEmpty"><i class="bi bi-robot" style="font-size:3.5rem;opacity:.3;"></i><div class="text-center"><div class="fw-semibold">FontanAI готов к работе</div><div class="small opacity-75">Задай вопрос или создай новый чат</div></div></div>';
  } else {
    data.messages.forEach(m => appendMessage(m));
  }
}

function copyCode(blockId, btn) {
  const el = document.getElementById(blockId);
  if (!el) return;
  navigator.clipboard.writeText(el.textContent).then(() => {
    btn.innerHTML = '<i class="bi bi-check2"></i> Скопировано';
    btn.classList.add('copied');
    setTimeout(() => { btn.innerHTML = '<i class="bi bi-clipboard"></i> Копировать'; btn.classList.remove('copied'); }, 2000);
  });
}

function renderMarkdown(text) {
  if (!text) return '';
  let html = '';
  const parts = text.split(/(```[\\s\\S]*?```)/g);
  parts.forEach(part => {
    if (part.startsWith('```')) {
      const lines = part.slice(3).split('\n');
      const lang = lines[0].trim() || 'code';
      const code = lines.slice(1).join('\n').replace(/```$/, '').trimEnd();
      const escaped = code.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
      const bid = 'cb_' + Math.random().toString(36).slice(2,8);
      html += `<div class="ai-code-block"><span class="ai-code-lang">${lang}</span><pre><code id="${bid}">${escaped}</code></pre><button class="ai-copy-btn" onclick="copyCode('${bid}',this)"><i class="bi bi-clipboard"></i> Копировать</button></div>`;
    } else {
      let t = part.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
        .replace(/[*][*](.+?)[*][*]/g,'<strong>$1</strong>')
        .replace(/[*](.+?)[*]/g,'<em>$1</em>')
        .replace(/`(.+?)`/g,'<code style="background:rgba(124,58,237,.12);padding:1px 5px;border-radius:4px;font-size:.87em">$1</code>')
        .replace(/\n/g,'<br>');
      html += t;
    }
  });
  return html;
}

function appendMessage(m) {
  const box = document.getElementById('aiMessages');
  const empty = document.getElementById('aiEmpty');
  if (empty) empty.remove();
  const wrap = document.createElement('div');
  wrap.className = `ai-msg ${m.role}`;
  const avatar = document.createElement('div');
  avatar.className = `ai-avatar ${m.role === 'user' ? 'user' : 'bot'}`;
  avatar.innerHTML = m.role === 'user' ? '<i class="bi bi-person-fill"></i>' : '<i class="bi bi-robot"></i>';
  const bubble = document.createElement('div');
  bubble.className = 'ai-bubble';
  let html = '';
  if (m.role === 'assistant') {
    html += renderMarkdown(m.content || '');
    if (m.model) html += `<span class="ai-model-badge ${m.model}">${m.model === 'smart' ? '🧠 Думающая' : '⚡ Быстрая'}</span>`;
  } else {
    html += (m.content || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/\n/g,'<br>');
  }
  if (m.file_url) {
    if (m.file_type === 'image') html += `<div class="ai-msg-file"><img src="${m.file_url}" onclick="window.open('${m.file_url}','_blank')"></div>`;
    else html += `<div class="ai-msg-file"><a href="${m.file_url}" target="_blank"><i class="bi bi-paperclip me-1"></i>Файл</a></div>`;
  }
  html += `<div style="font-size:.7rem;opacity:.5;margin-top:4px;text-align:${m.role==='user'?'right':'left'}">${m.timestamp}</div>`;
  bubble.innerHTML = html;
  if (m.role === 'user') { wrap.appendChild(bubble); wrap.appendChild(avatar); }
  else { wrap.appendChild(avatar); wrap.appendChild(bubble); }
  box.appendChild(wrap);
  box.scrollTop = box.scrollHeight;
}

function showTyping() {
  const box = document.getElementById('aiMessages');
  const empty = document.getElementById('aiEmpty');
  if (empty) empty.remove();
  const wrap = document.createElement('div');
  wrap.className = 'ai-msg assistant';
  wrap.id = 'typingIndicator';
  wrap.innerHTML = `<div class="ai-avatar bot"><i class="bi bi-robot"></i></div><div class="ai-typing"><span></span><span></span><span></span></div>`;
  box.appendChild(wrap);
  box.scrollTop = box.scrollHeight;
}

function removeTyping() {
  const t = document.getElementById('typingIndicator');
  if (t) t.remove();
}

let selectedFile = null;
function handleFileSelect(input) {
  selectedFile = input.files[0];
  if (selectedFile) {
    document.getElementById('filePreview').style.display = 'flex';
    document.getElementById('filePreviewName').textContent = selectedFile.name;
  }
}
function clearFile() {
  selectedFile = null;
  document.getElementById('aiFileInput').value = '';
  document.getElementById('filePreview').style.display = 'none';
}

async function aiSendMessage() {
  if (isWaiting) return;
  if (Date.now() < aiNextSendAt) {
    alert(`Подожди ${Math.ceil((aiNextSendAt - Date.now()) / 1000)} сек`);
    return;
  }
  const input = document.getElementById('aiInput');
  const text = input.value.trim();
  if (!text && !selectedFile) return;
  if (!currentChatId) {
    try { await newChat(); } catch(e) { alert('Не удалось создать чат'); return; }
  }
  isWaiting = true;
  document.getElementById('aiSendBtn').disabled = true;
  const formData = new FormData();
  formData.append('chat_id', currentChatId);
  formData.append('model', selectedModelKey);
  if (text) formData.append('content', text);
  if (selectedFile) formData.append('file', selectedFile);
  input.value = '';
  input.style.height = 'auto';
  clearFile();
  showTyping();
  try {
    const res = await fetch('/api/ai/send', {method:'POST', body:formData});
    removeTyping();
    if (res.status === 429) {
      const data = await res.json();
      startAiCooldown(data.retry_after || AI_COOLDOWN_SECONDS);
      alert(data.error || 'Подожди немного!');
      isWaiting = false;
      document.getElementById('aiSendBtn').disabled = false;
      return;
    }
    if (res.status === 402) {
      const data = await res.json();
      alert(data.error || 'Недостаточно кредитов!');
      updateCredits(data.credits);
      isWaiting = false;
      document.getElementById('aiSendBtn').disabled = false;
      return;
    }
    const data = await res.json();
    if (data.error) { alert(data.error); isWaiting = false; document.getElementById('aiSendBtn').disabled = false; return; }
    appendMessage(data.user_msg);
    startAiCooldown(AI_COOLDOWN_SECONDS);
    if (data.ai_msg) appendMessage(data.ai_msg);
    else if (data.admin_mode) {
      const box = document.getElementById('aiMessages');
      const notice = document.createElement('div');
      notice.className = 'text-center text-muted small my-2';
      notice.textContent = '⏳ Ожидаем ответа оператора…';
      box.appendChild(notice);
      box.scrollTop = box.scrollHeight;
    }
    if (data.credits) updateCredits(data.credits);
    const item = document.querySelector(`.ai-chat-item[data-chat-id="${currentChatId}"] .chat-title`);
    if (item) item.textContent = document.getElementById('chatTitle').textContent;
  } catch(e) {
    removeTyping();
    appendMessage({role:'assistant', content:'⏳ Попробуйте позже — нейросеть не отвечает.', timestamp:new Date().toLocaleTimeString('ru',{hour:'2-digit',minute:'2-digit'})});
  }
  isWaiting = false;
  document.getElementById('aiSendBtn').disabled = false;
  input.focus();
}

async function deleteCurrentChat() {
  if (!currentChatId) return;
  if (!confirm('Удалить этот чат?')) return;
  await fetch(`/api/ai/delete_chat/${currentChatId}`, {method:'POST'});
  const item = document.querySelector(`.ai-chat-item[data-chat-id="${currentChatId}"]`);
  if (item) item.remove();
  currentChatId = null;
  document.getElementById('aiMessages').innerHTML = '<div class="ai-empty"><i class="bi bi-robot" style="font-size:3.5rem;opacity:.3;"></i><div class="text-center"><div class="fw-semibold">Чат удалён</div></div></div>';
  document.getElementById('deleteChatBtn').style.display = 'none';
}

if (typeof io !== 'undefined') {
  const sock = io();
  sock.on('connect', () => { if(currentChatId) sock.emit('join_ai_chat', {chat_id: currentChatId}); });
  sock.on('ai_message', (data) => {
    if (data.chat_id == currentChatId) {
      removeTyping();
      appendMessage({role:'assistant', content:data.content, timestamp:data.timestamp});
      isWaiting = false;
      document.getElementById('aiSendBtn').disabled = false;
    }
  });
}
</script>

{% endblock %}
""",

    'admin_ai_chats.html': """

{% extends "base.html" %}

{% block content %}

<style>

.ai-admin-chat-list { display: flex; flex-direction: column; gap: 12px; }

.ai-admin-chat-card { border-radius: 16px; padding: 16px; border: 1px solid var(--border-color); background: var(--card-bg); }

.ai-chat-msgs { max-height: 300px; overflow-y: auto; background: var(--hover-bg); border-radius: 12px; padding: 12px; margin: 10px 0; display: flex; flex-direction: column; gap: 8px; }

.ai-admin-msg { padding: 8px 12px; border-radius: 12px; font-size: 0.88rem; max-width: 80%; }

.ai-admin-msg.user { background: #4f46e5; color: #fff; align-self: flex-end; }

.ai-admin-msg.assistant { background: var(--border-color); align-self: flex-start; }

.ai-reply-form { display: flex; gap: 8px; }

.ai-reply-form input { flex: 1; border-radius: 20px; border: 1px solid var(--border-color); background: var(--card-bg); color: var(--text-color); padding: 8px 16px; }

.mode-badge { font-size: 0.72rem; padding: 3px 8px; border-radius: 8px; }

.mode-ai { background: #22c55e; color: #fff; }

.mode-admin { background: #f97316; color: #fff; }

</style>

<div class="d-flex align-items-center justify-content-between mb-4">

  <h3 class="fw-bold mb-0"><i class="bi bi-robot me-2" style="color:#7c3aed"></i>FontanAI — Все чаты</h3>

  <a href="{{ url_for('admin_dashboard') }}" class="btn btn-outline-secondary rounded-pill"><i class="bi bi-arrow-left me-1"></i>Назад</a>

</div>

<div class="ai-admin-chat-list">

{% for chat in chats %}

<div class="ai-admin-chat-card" id="chatCard{{ chat.id }}">

  <div class="d-flex align-items-center gap-3 mb-2">

    <div>

      <span class="fw-semibold">{{ chat.user.username }}</span>

      <span class="text-muted small ms-2">{{ chat.title }}</span>

    </div>

    <div class="ms-auto d-flex gap-2 align-items-center">

      <span class="mode-badge {% if chat.is_admin_mode %}mode-admin{% else %}mode-ai{% endif %}" id="modeBadge{{ chat.id }}">

        {% if chat.is_admin_mode %}👤 Ручной{% else %}🤖 ИИ{% endif %}

      </span>

      <button class="btn btn-sm btn-outline-secondary rounded-pill" onclick="toggleMode({{ chat.id }})">

        Переключить режим

      </button>

    </div>

  </div>

  <div class="ai-chat-msgs" id="msgs{{ chat.id }}">

    {% for m in chat.messages %}

    <div class="ai-admin-msg {{ m.role }}">

      <div style="font-size:.7rem;opacity:.6;margin-bottom:2px;">{{ 'Пользователь' if m.role == 'user' else 'ИИ / Админ' }} В· {{ m.timestamp|time_ago }}</div>

      {% if m.content %}{{ m.content }}{% endif %}

      {% if m.file_url and m.file_type == 'image' %}<br><img src="{{ m.file_url }}" style="max-width:140px;border-radius:8px;margin-top:4px;">{% endif %}

    </div>

    {% endfor %}

  </div>

  {% if chat.is_admin_mode %}

  <div class="ai-reply-form" id="replyForm{{ chat.id }}">

    <input type="text" placeholder="РћС‚РІРµС‚РёС‚СЊ РѕС‚ РёРјРµРЅРё РРвЂ¦" id="replyInput{{ chat.id }}" onkeydown="if(event.key==='Enter') adminReply({{ chat.id }})">

    <button class="btn btn-primary rounded-pill px-3" onclick="adminReply({{ chat.id }})"><i class="bi bi-send-fill"></i></button>

  </div>

  {% else %}

  <div class="ai-reply-form" id="replyForm{{ chat.id }}" style="display:none;">

    <input type="text" placeholder="РћС‚РІРµС‚РёС‚СЊ РѕС‚ РёРјРµРЅРё РРвЂ¦" id="replyInput{{ chat.id }}" onkeydown="if(event.key==='Enter') adminReply({{ chat.id }})">

    <button class="btn btn-primary rounded-pill px-3" onclick="adminReply({{ chat.id }})"><i class="bi bi-send-fill"></i></button>

  </div>

  {% endif %}

</div>

{% else %}

<div class="text-center text-muted py-5">

  <i class="bi bi-robot" style="font-size:3rem;opacity:.3;"></i>

  <div class="mt-3">Чатов ещё нет</div>

</div>

{% endfor %}

</div>

<script>

async function toggleMode(chatId) {

  const res = await fetch(`/admin/ai_mode/${chatId}`, {method:'POST'});

  const data = await res.json();

  const badge = document.getElementById('modeBadge' + chatId);

  const form = document.getElementById('replyForm' + chatId);

  if(data.is_admin_mode) {

    badge.textContent = '👤 Ручной';

    badge.className = 'mode-badge mode-admin';

    form.style.display = 'flex';

  } else {

    badge.textContent = '🤖 ИИ';

    badge.className = 'mode-badge mode-ai';

    form.style.display = 'none';

  }

}

async function adminReply(chatId) {

  const input = document.getElementById('replyInput' + chatId);

  const text = input.value.trim();

  if(!text) return;

  const fd = new FormData();

  fd.append('content', text);

  const res = await fetch(`/admin/ai_reply/${chatId}`, {method:'POST', body:fd});

  if(res.ok) {

    input.value = '';

    const msgs = document.getElementById('msgs' + chatId);

    const div = document.createElement('div');

    div.className = 'ai-admin-msg assistant';

    div.innerHTML = `<div style="font-size:.7rem;opacity:.6;margin-bottom:2px;">ИИ / Админ В· С‚РѕР»СЊРєРѕ С‡С‚Рѕ</div>${text}`;

    msgs.appendChild(div);

    msgs.scrollTop = msgs.scrollHeight;

  }

}

// Прокрутить все чаты вниз

document.querySelectorAll('.ai-chat-msgs').forEach(el => el.scrollTop = el.scrollHeight);

</script>

{% endblock %}

"""

}

app.jinja_env.filters['from_json'] = safe_from_json

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

# --- Р’РђР™Р‘Р•Р Р« (РџРћР”РџРРЎРљР) ---

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

# --- РџР•Р Р•РљР›Р®Р§Р•РќРР• РўР•РњР« ---

@app.route('/toggle_theme', methods=['POST'])

@login_required

def toggle_theme():

    current_user.theme = 'dark' if current_user.theme == 'light' else 'light'

    db.session.commit()

    return jsonify({'theme': current_user.theme})

# --- Р“РћР›РћРЎРћР’РђРќРР• Р’ РћРџР РћРЎРђРҐ ---

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

# --- РђР”РњРРќРЎРљРР• Р¤РЈРќРљР¦РР ---

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

    return render_template(

        'messenger.html',

        friends=friends,

        groups=groups,

        active_chat=active_chat,

        chat_type=chat_type,

        online_ids=online_ids,

        webrtc_ice_servers=WEBRTC_ICE_SERVERS

    )

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

    try:

        id_ = int(request.args.get('id', 0))

    except (TypeError, ValueError):

        return jsonify([])

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

    try:

        target_id = int(request.form.get('target_id', 0))

    except (TypeError, ValueError):

        return jsonify({'error': 'Bad target'}), 400

    body = normalize_text(request.form.get('body'))

    voice = request.files.get('voice')

    client_token = request.form.get('client_token', '').strip()

    voice_url = None

    if voice:

        voice_url = upload_to_cloud(voice, resource_type="video")

    if not body and not voice_url:

        return jsonify({'error': 'Empty'}), 400

    if not consume_idempotency_token(f'message:{type_}:{target_id}', client_token):

        return jsonify({'status': 'duplicate'}), 200

    signature = f'{type_}:{target_id}:{body}:{bool(voice_url)}'

    if recent_duplicate_signature(f'message-sig:{target_id}', signature):

        return jsonify({'status': 'duplicate'}), 200

    if type_ == 'private':

        recipient = db.session.get(User, target_id)

        if not recipient or recipient.username == 'admin' and not current_user.is_admin:

            return jsonify({'error': 'Chat unavailable'}), 404

    elif type_ == 'group':

        group = db.session.get(Group, target_id)

        if not group or current_user not in group.members:

            return jsonify({'error': 'Access denied'}), 403

    else:

        return jsonify({'error': 'Bad type'}), 400

    msg = Message(sender_id=current_user.id, body=body, voice_filename=voice_url, client_token=client_token or None)

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

    text = normalize_text(data.get('text'))

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

# --- РџРћРЎРўР« Р РљРћРњРњР•РќРўРђР РР ---

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

    # Online now: active in last 5 min

    online_count = User.query.filter(User.last_seen > datetime.utcnow() - timedelta(minutes=5)).count()

    stats = SiteStats.query.first()

    total_visitors = stats.total_visitors if stats else 0

    peak_online = stats.peak_online if stats else 0

    total_users = User.query.count()

    total_posts = Post.query.count()

    total_flux = FluxVideo.query.count()

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

    return render_template('admin_dashboard.html',

                           chart_labels=labels, users_data=users_data, posts_data=posts_data,

                           online_count=online_count, total_visitors=total_visitors,

                           peak_online=peak_online, total_users=total_users,

                           total_posts=total_posts, total_flux=total_flux)

@app.route('/admin/broadcast', methods=['POST'])

@login_required

def admin_broadcast():

    if not current_user.is_admin: abort(403)

    msg = request.form.get('message', '').strip()

    if msg:

        try:

            users = User.query.all()

            for u in users:

                create_notification(u.id, 'system', msg, link=url_for('index'), from_user_id=current_user.id)

            db.session.commit()

            flash(f"Рассылка отправлена {len(users)} пользователям!", "success")

        except Exception as e:

            db.session.rollback()

            print(f"[broadcast ERROR] {e}")

            flash("Ошибка рассылки", "danger")

    else:

        flash("Сообщение не может быть пустым", "warning")

    return redirect(url_for('admin_dashboard'))

@app.route('/admin/flux')

@login_required

def admin_flux_list():

    if not current_user.is_admin: abort(403)

    videos = FluxVideo.query.order_by(FluxVideo.timestamp.desc()).all()

    total_views = sum(v.views for v in videos)

    return render_template('admin_flux.html', videos=videos,

                           total=len(videos), total_views=total_views)

@app.route('/admin/flux/delete/<int:video_id>', methods=['POST'])

@login_required

def admin_delete_flux(video_id):

    if not current_user.is_admin: abort(403)

    video = FluxVideo.query.get_or_404(video_id)

    FluxLike.query.filter_by(video_id=video_id).delete()

    FluxComment.query.filter_by(video_id=video_id).delete()

    db.session.delete(video)

    db.session.commit()

    flash("Видео удалено администратором.", "success")

    return redirect(url_for('admin_flux_list'))

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

            tag = re.sub(r'[^A-Za-z0-9_\.]+', '', q[1:])[:80]

            if tag:

                posts = Post.query.filter(

                    Post.content.isnot(None),

                    Post.content.ilike(f'%#{tag}%')

                ).order_by(Post.timestamp.desc()).limit(20).all()

        else:

            users = User.query.filter(User.username.ilike(f'%{q}%')).limit(20).all()

            posts = Post.query.filter(Post.content.isnot(None), Post.content.ilike(f'%{q}%')).order_by(Post.timestamp.desc()).limit(20).all()

            groups = Group.query.filter(Group.name.ilike(f'%{q}%')).limit(20).all()

    posts = [post for post in posts if getattr(post, 'author', None)]

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

    content = normalize_text(request.form.get('content'))

    client_token = request.form.get('client_token', '').strip()

    if not consume_idempotency_token('create_post', client_token):

        flash("Пост уже был отправлен. Дубликат остановлен.", "warning")

        return redirect(url_for('index'))

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

    duplicate_signature = f'{content}|{len(media_items)}|{bool(poll_data)}|{co_author_user.id if co_author_user else 0}|{comments_enabled}'

    if recent_duplicate_signature('create_post_sig', duplicate_signature):

        flash("Похоже, это повторный клик по посту. Второй пост не создан.", "warning")

        return redirect(url_for('index'))

    if content or image_url or video_url or poll_data or media_items:

        post = Post(

            content=content, 

            image_filename=image_url, 

            video_filename=video_url, 

            author=current_user,

            co_author_id=co_author_user.id if co_author_user else None,

            comments_enabled=comments_enabled,

            is_moderated=is_ok,

            moderation_reason=reason if not is_ok else None,

            client_token=client_token or None

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

@app.route('/delete_post/<int:post_id>', methods=['GET', 'POST'])

@login_required

def delete_post(post_id):

    try:

        post = db.session.get(Post, post_id)

        if post and (post.user_id == current_user.id or current_user.is_admin):

            # Сначала убираем FK на посты в жалобах (nullable поле)

            Report.query.filter_by(post_id=post_id).update({'post_id': None})

            db.session.flush()

            db.session.delete(post)

            db.session.commit()

            flash("Пост удалён", "success")

        else:

            flash("Нет доступа", "danger")

    except Exception as e:

        db.session.rollback()

        print(f"[delete_post ERROR] {e}")

        flash("Ошибка при удалении поста. Попробуй ещё раз.", "danger")

    return redirect(request.referrer or url_for('index'))

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

    text = normalize_text(request.form.get('text'))

    client_token = request.form.get('client_token', '').strip()

    post = db.session.get(Post, post_id)

    if post and not post.comments_enabled:

        return redirect(url_for('index'))

    # AI модерация комментариев

    is_ok, reason = moderate_content(text)

    if not consume_idempotency_token(f'comment:{post_id}', client_token):

        flash("Комментарий уже был отправлен. Дубликат остановлен.", "warning")

        return redirect(url_for('index'))

    if text and is_ok:

        if recent_duplicate_signature(f'comment-sig:{post_id}', text):

            flash("Похожий комментарий уже появился. Дубликат остановлен.", "warning")

            return redirect(url_for('index'))

        db.session.add(Comment(text=text, user_id=current_user.id, post_id=post_id, client_token=client_token or None))

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

@app.route('/flux')

@login_required

def flux_feed():

    videos = FluxVideo.query.order_by(func.random()).limit(20).all()

    video_likes = {}

    video_comments = {}

    video_comments_data = {}

    for vid in videos:

        video_likes[vid.id] = [l.user_id for l in FluxLike.query.filter_by(video_id=vid.id).all()]

        comments = FluxComment.query.filter_by(video_id=vid.id).order_by(FluxComment.timestamp.desc()).limit(50).all()

        video_comments[vid.id] = comments

        video_comments_data[vid.id] = [

            {

                'username': c.author.username,

                'avatar': c.author.avatar or '',

                'text': c.text

            } for c in comments

        ]

    return render_template('flux.html', videos=videos, video_likes=video_likes,

                           video_comments=video_comments, video_comments_data=video_comments_data)

@app.route('/flux/view/<int:id>', methods=['POST'])

@login_required

def track_flux_view(id):

    """Счётчик просмотров: вызывается из JS один раз при реальном показе видео."""

    viewed = session.get('flux_viewed_ids', [])

    if id not in viewed:

        v = FluxVideo.query.get(id)

        if v:

            v.views += 1

            db.session.commit()

        viewed.append(id)

        session['flux_viewed_ids'] = viewed[-200:]

        session.modified = True

    return jsonify({'ok': True})

@app.route('/flux/upload', methods=['POST'])

@login_required

def upload_flux():

    video = request.files.get('video')

    desc = request.form.get('description')

    if video:

        # Handle video uploads to Cloudinary (resource_type="video").

        url = upload_to_cloud(video, resource_type="video")

        if url:

            new_flux = FluxVideo(user_id=current_user.id, video_url=url, description=desc)

            db.session.add(new_flux)

            db.session.commit()

            flash("Flux опубликован!", "success")

    return redirect(url_for('flux_feed'))

@app.route('/flux/like/<int:id>', methods=['POST'])

@login_required

def like_flux(id):

    v = FluxVideo.query.get_or_404(id)

    existing = FluxLike.query.filter_by(user_id=current_user.id, video_id=id).first()

    if existing:

        db.session.delete(existing)

        v.likes = max(0, v.likes - 1)

        db.session.commit()

        return jsonify({'liked': False, 'likes_count': v.likes})

    else:

        db.session.add(FluxLike(user_id=current_user.id, video_id=id))

        v.likes += 1

        db.session.commit()

        return jsonify({'liked': True, 'likes_count': v.likes})

@app.route('/flux/comment/ajax/<int:id>', methods=['POST'])

@login_required

def comment_flux_ajax(id):

    text = request.form.get('text', '').strip()

    if not text:

        return jsonify({'ok': False, 'error': 'Пустой комментарий'}), 400

    if len(text) > 300:

        return jsonify({'ok': False, 'error': 'Слишком длинный'}), 400

    FluxVideo.query.get_or_404(id)

    db.session.add(FluxComment(user_id=current_user.id, video_id=id, text=text))

    db.session.commit()

    return jsonify({

        'ok': True,

        'username': current_user.username,

        'avatar': current_user.avatar or '',

        'text': text

    })

@app.route('/flux/comment/<int:id>', methods=['POST'])

@login_required

def comment_flux(id):

    text = request.form.get('text')

    if text:

        db.session.add(FluxComment(user_id=current_user.id, video_id=id, text=text))

        db.session.commit()

    return redirect(url_for('flux_feed'))

@app.route('/delete_comment/<int:comment_id>')

@login_required

def delete_comment(comment_id):

    comment = db.session.get(Comment, comment_id)

    if comment and (comment.user_id == current_user.id or comment.post.user_id == current_user.id or current_user.is_admin):

        db.session.delete(comment)

        db.session.commit()

    return redirect(url_for('index'))

# Страница моих Flux-видео

@app.route('/flux/my_videos')

@login_required

def flux_my_videos():

    my_videos = FluxVideo.query.filter_by(user_id=current_user.id).order_by(FluxVideo.timestamp.desc()).all()

    stats = {

        'total_views': sum(v.views for v in my_videos),

        'total_likes': sum(v.likes for v in my_videos),

        'total_videos': len(my_videos),

    }

    video_comments = {v.id: FluxComment.query.filter_by(video_id=v.id).count() for v in my_videos}

    return render_template('flux_my_videos.html', my_videos=my_videos, stats=stats, video_comments=video_comments)

# Удалить своё Flux-видео

@app.route('/flux/delete/<int:video_id>', methods=['POST'])

@login_required

def delete_flux(video_id):

    video = FluxVideo.query.get_or_404(video_id)

    if video.user_id != current_user.id and not current_user.is_admin:

        abort(403)

    FluxLike.query.filter_by(video_id=video_id).delete()

    FluxComment.query.filter_by(video_id=video_id).delete()

    db.session.delete(video)

    db.session.commit()

    flash("Видео удалено", "success")

    return redirect(url_for('flux_my_videos'))

@app.route('/register', methods=['GET', 'POST'])

def register():

    if request.method == 'POST':

        if not validate_captcha(request.form.get('captcha')):

            flash("Неверная капча", "danger")

            return redirect(url_for('register'))

        email = request.form.get('email')

        username = request.form.get('username')

        password = request.form.get('password')

        if User.query.filter_by(email=email).first():

            flash("Этот email уже зарегистрирован.", "danger")

            return redirect(url_for('register'))

        if User.query.filter_by(username=username).first():

            flash("Этот никнейм уже занят.", "danger")

            return redirect(url_for('register'))

        new_user = User(

            email=email,

            username=username,

            password=generate_password_hash(password),

            email_confirmed=False

        )

        db.session.add(new_user)

        db.session.commit()

        session['temp_user_id'] = new_user.id

        # Новый пользователь — TG ID нет, идём настраивать

        return redirect(url_for('setup_telegram'))

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

                return redirect(url_for('login'))

            session['temp_user_id'] = user.id

            # Если TG ID не привязан — сначала настроить

            if not user.telegram_id:

                return redirect(url_for('setup_telegram'))

            if send_verification_code(user.email):

                return redirect(url_for('verify_email'))

            else:

                flash("Ошибка отправки кода", "danger")

        else:

            flash("Неверный логин или пароль", "danger")

    captcha_q = generate_captcha()

    return render_template('auth.html', title="Вход", is_login=True, captcha_q=captcha_q)

@app.route('/setup_telegram', methods=['GET', 'POST'])

def setup_telegram():

    """Страница привязки Telegram ID перед отправкой кода подтверждения."""

    user_id = session.get('temp_user_id')

    if not user_id:

        return redirect(url_for('login'))

    if request.method == 'POST':

        tg_id = request.form.get('telegram_id', '').strip()

        if not tg_id or not tg_id.isdigit():

            flash("Введи корректный Telegram ID (только цифры)", "danger")

            return redirect(url_for('setup_telegram'))

        user = db.session.get(User, user_id)

        if not user:

            flash("Пользователь не найден", "danger")

            return redirect(url_for('login'))

        user.telegram_id = tg_id

        db.session.commit()

        if send_verification_code(user.email):

            flash("Код отправлен в Telegram!", "success")

            return redirect(url_for('verify_email'))

        else:

            flash("Ошибка отправки кода", "danger")

            return redirect(url_for('setup_telegram'))

    # --- РџР РђР’РР›Р¬РќРђРЇ Р—РђР“Р РЈР—РљРђ РЁРђР‘Р›РћРќРђ (Р‘Р•Р— РћРЁРР‘РћРљ Р Р›РРЁРќР•Р“Рћ РљРћР”Рђ РќРђ Р­РљР РђРќР•) ---

    try:

        # Пытаемся отрендерить стандартно

        return render_template('setup_telegram.html')

    except Exception:

        # Если Flask опять "потерял" папку templates, читаем файл принудительно

        import os

        from flask import render_template_string

        # Определяем путь к файлу шаблона

        template_path = os.path.join(app.root_path, 'templates', 'setup_telegram.html')

        if os.path.exists(template_path):

            with open(template_path, 'r', encoding='utf-8') as f:

                template_content = f.read()

                # РСЃРїРѕР»СЊР·СѓРµРј render_template_string, С‡С‚РѕР±С‹ СѓР±СЂР°С‚СЊ "РєСЂР°РєРѕР·СЏР±СЂС‹" СЃРѕ СЃРєСЂРёРЅР°

                return render_template_string(template_content)

        return f"Критическая ошибка: файл не найден даже по пути {template_path}"

@app.route('/verify_email', methods=['GET', 'POST'])

def verify_email():

    if request.method == 'POST':

        user_code = request.form.get('verify_code')

        if user_code == session.get('temp_code'):

            user_id = session.get('temp_user_id')

            user = db.session.get(User, user_id)

            if user:

                user.email_confirmed = True

                db.session.commit()

                login_user(user)

                # Cleanup

                session.pop('temp_user_id', None)

                session.pop('temp_code', None)

                session.pop('temp_email', None)

                token = uuid.uuid4().hex

                session['session_token'] = token

                ip = get_client_ip()

                db.session.add(UserSession(user_id=user.id, session_token=token, ip=ip, city=guess_city(ip), user_agent=request.headers.get('User-Agent')))

                db.session.commit()

                flash("Успешный вход!", "success")

                return redirect(url_for('index'))

        else:

            flash("Неверный код", "danger")

    return render_template('auth.html', title="Подтверждение", is_login=True, show_verify=True, captcha_q=generate_captcha())

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

@app.route('/confirm_email/<token>')

def confirm_email(token):

    user = User.query.filter_by(email_confirmation_token=token).first()

    if user:

        user.email_confirmed = True

        user.email_confirmation_token = None

        db.session.commit()

        flash("Email подтвержден! Теперь вы можете войти.", "success")

    else:

        flash("Недействительная ссылка для подтверждения.", "danger")

    return redirect(url_for('login'))

# --- FONTAN AI ---

def call_groq_api(messages_history, model_name=None):

    """Вызов Groq API с таймаутом"""

    headers = {

        "Authorization": f"Bearer {GROQ_API_KEY}",

        "Content-Type": "application/json"

    }

    payload = {

        "model": model_name or GROQ_MODEL,

        "messages": [{"role": "system", "content": "You are Fontan AI, an artificial model assistant of Fontan platform. If asked who you are or how you were created, answer: I am an artificial model Fontan AI. Reply in Russian, briefly and helpfully."}] + messages_history,

        "max_tokens": 1024,

        "temperature": 0.7

    }

    try:

        resp = requests.post(

            "https://api.groq.com/openai/v1/chat/completions",

            headers=headers, json=payload,

            timeout=GROQ_TIMEOUT_SECONDS

        )

        if resp.status_code == 200:

            data = resp.json()

            return data['choices'][0]['message']['content'], None

        elif resp.status_code == 429:

            return None, "rate_limit"

        else:

            return None, f"api_error_{resp.status_code}"

    except requests.Timeout:

        return None, "timeout"

    except Exception as e:

        return None, str(e)

def get_fontan_identity_reply(user_text):

    text = (user_text or "").strip().lower()

    if not text:

        return None

    identity_patterns = [

        r"\bкто\s+ты\b",

        r"\bты\s+кто\b",

        r"\bкто\s+тебя\s+создал\b",

        r"\bна\s+ч[её]м\s+ты\s+создан",

        r"\bкак\s+тебя\s+создали\b",

        r"\bwhat\s+are\s+you\b",

        r"\bwho\s+are\s+you\b",

        r"\bhow\s+were\s+you\s+made\b",

    ]

    if any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in identity_patterns):

        return (

            "Я искусственная модель Fontan AI. "

            "Меня создали для помощи пользователям платформы Fontan: "

            "отвечаю на вопросы, помогаю с текстами и идеями."

        )

    return None

@app.route('/fontan_ai')

@login_required

def fontan_ai():

    chats = AiChat.query.filter_by(user_id=current_user.id).order_by(AiChat.updated_at.desc()).all()

    credit_state = get_ai_credit_state(current_user, commit=True)
    model_options = [
        {
            'key': model['key'],
            'label': model['label'],
            'cost': model['cost'],
            'hint': model['hint'],
        }
        for model in AI_MODEL_OPTIONS.values()
    ]

    return render_template(
        'fontan_ai.html',
        chats=chats,
        ai_credit_state=credit_state,
        ai_model_options=model_options
    )

@app.route('/api/ai/new_chat', methods=['POST'])

@login_required

def ai_new_chat():

    chat = AiChat(user_id=current_user.id, title='Новый чат')

    db.session.add(chat)

    db.session.commit()

    return jsonify({'chat_id': chat.id, 'title': chat.title})

@app.route('/api/ai/chats')

@login_required

def ai_get_chats():

    chats = AiChat.query.filter_by(user_id=current_user.id).order_by(AiChat.updated_at.desc()).all()

    return jsonify([{

        'id': c.id, 'title': c.title,

        'updated_at': c.updated_at.strftime('%d.%m %H:%M'),

        'is_admin_mode': c.is_admin_mode

    } for c in chats])

@app.route('/api/ai/chat/<int:chat_id>')

@login_required

def ai_get_messages(chat_id):

    chat = db.session.get(AiChat, chat_id)

    if not chat or (chat.user_id != current_user.id and not current_user.is_admin):

        abort(403)

    msgs = []

    for m in chat.messages:

        msgs.append({

            'id': m.id, 'role': m.role,

            'content': m.content,

            'file_url': m.file_url,

            'file_type': m.file_type,

            'timestamp': m.timestamp.strftime('%H:%M')

        })

    return jsonify({
        'messages': msgs,
        'title': chat.title,
        'is_admin_mode': chat.is_admin_mode,
        'credits': get_ai_credit_state(current_user, commit=True)
    })

@app.route('/api/ai/send', methods=['POST'])

@login_required

def ai_send_message():

    chat_id = request.form.get('chat_id', type=int)
    content = request.form.get('content', '').strip()
    file = request.files.get('file')
    selected_model_key = request.form.get('model', 'fast')
    model_config = get_ai_model_config(selected_model_key)

    if not chat_id:

        return jsonify({'error': 'Нет chat_id'}), 400

    chat = db.session.get(AiChat, chat_id)

    if not chat or chat.user_id != current_user.id:

        return jsonify({'error': 'Доступ запрещён'}), 403

    credit_state = get_ai_credit_state(current_user, commit=True)

    if not chat.is_admin_mode and credit_state['balance'] < model_config['cost']:

        return jsonify({
            'error': f"Недостаточно кредитов. Для модели «{model_config['label']}» нужно {model_config['cost']} кр.",
            'credits': credit_state,
            'required_credits': model_config['cost']
        }), 402

    last_msg = AiMessage.query.filter_by(chat_id=chat_id).filter(
        AiMessage.role == 'user'
    ).order_by(AiMessage.timestamp.desc()).first()

    if last_msg:

        diff = (datetime.utcnow() - last_msg.timestamp).total_seconds()

        if diff < GROQ_COOLDOWN_SECONDS:

            wait_seconds = int(GROQ_COOLDOWN_SECONDS - diff) + 1

            return jsonify({
                'error': f'Подожди {wait_seconds} сек',
                'retry_after': wait_seconds
            }), 429

    file_url, file_type_val = None, None

    if file and file.filename:

        ext = file.filename.rsplit('.', 1)[-1].lower()

        if ext in ['png', 'jpg', 'jpeg', 'gif', 'webp']:

            file_url = upload_to_cloud(file, resource_type="image")
            file_type_val = 'image'

        else:

            file_url = upload_to_cloud(file, resource_type="raw")
            file_type_val = 'file'

    if not content and not file_url:

        return jsonify({'error': 'Пустое сообщение'}), 400

    user_msg = AiMessage(
        chat_id=chat_id,
        role='user',
        content=content,
        file_url=file_url,
        file_type=file_type_val
    )
    db.session.add(user_msg)

    if chat.title == 'Новый чат' and content:

        chat.title = content[:50] + ('…' if len(content) > 50 else '')

    chat.updated_at = datetime.utcnow()
    db.session.commit()

    user_msg_payload = {
        'id': user_msg.id,
        'role': 'user',
        'content': content,
        'file_url': file_url,
        'file_type': file_type_val,
        'timestamp': user_msg.timestamp.strftime('%H:%M')
    }

    if chat.is_admin_mode:

        return jsonify({
            'user_msg': user_msg_payload,
            'ai_msg': None,
            'admin_mode': True,
            'credits': credit_state,
            'selected_model': model_config['key']
        })

    history = []

    for m in chat.messages:

        if m.role in ('user', 'assistant'):

            history.append({"role": m.role, "content": m.content or '[файл]'})

    identity_reply = get_fontan_identity_reply(content)

    if identity_reply:

        ai_text, error = identity_reply, None

    else:

        ai_text, error = call_groq_api(history, model_config['api_model'])

    should_charge = error is None and bool(ai_text)
    credits_spent = 0

    if error in ('timeout', 'rate_limit'):

        ai_text = "⏳ Попробуйте позже — нейросеть сейчас не отвечает. Повтори запрос через минуту."

    elif error and not ai_text:

        ai_text = "❌ Произошла ошибка. Попробуй позже."

    if should_charge and spend_ai_credits(current_user, model_config['cost']):

        credits_spent = model_config['cost']

    ai_msg = AiMessage(chat_id=chat_id, role='assistant', content=ai_text)
    db.session.add(ai_msg)
    db.session.commit()

    return jsonify({
        'user_msg': user_msg_payload,
        'ai_msg': {
            'id': ai_msg.id,
            'role': 'assistant',
            'content': ai_text,
            'timestamp': ai_msg.timestamp.strftime('%H:%M'),
            'model': model_config['key']
        },
        'credits': get_ai_credit_state(current_user),
        'credits_spent': credits_spent,
        'selected_model': model_config['key']
    })

@app.route('/api/ai/delete_chat/<int:chat_id>', methods=['POST'])

@login_required

def ai_delete_chat(chat_id):

    chat = db.session.get(AiChat, chat_id)

    if chat and (chat.user_id == current_user.id or current_user.is_admin):

        db.session.delete(chat)

        db.session.commit()

    return jsonify({'ok': True})

# --- ADMIN AI FUNCTIONS ---

@app.route('/admin/ai_chats')

@login_required

def admin_ai_chats():

    if not current_user.is_admin: abort(403)

    chats = AiChat.query.order_by(AiChat.updated_at.desc()).all()

    return render_template('admin_ai_chats.html', chats=chats)

@app.route('/admin/ai_mode/<int:chat_id>', methods=['POST'])

@login_required

def admin_ai_toggle_mode(chat_id):

    if not current_user.is_admin: abort(403)

    chat = db.session.get(AiChat, chat_id)

    if chat:

        chat.is_admin_mode = not chat.is_admin_mode

        db.session.commit()

        return jsonify({'is_admin_mode': chat.is_admin_mode})

    return jsonify({'error': 'Not found'}), 404

@app.route('/admin/ai_reply/<int:chat_id>', methods=['POST'])

@login_required

def admin_ai_reply(chat_id):

    if not current_user.is_admin: abort(403)

    content = request.form.get('content', '').strip()

    chat = db.session.get(AiChat, chat_id)

    if not chat or not content:

        return jsonify({'error': 'Bad request'}), 400

    # РЎРѕС…СЂР°РЅСЏРµРј РєР°Рє 'assistant' С‡С‚РѕР±С‹ СЋР·РµСЂ РІРёРґРµР» РєР°Рє РѕС‚РІРµС‚ РР

    msg = AiMessage(chat_id=chat_id, role='assistant', content=content)

    db.session.add(msg)

    chat.updated_at = datetime.utcnow()

    db.session.commit()

    # Уведомить через socketio

    socketio.emit('ai_message', {

        'chat_id': chat_id,

        'role': 'assistant',

        'content': content,

        'timestamp': msg.timestamp.strftime('%H:%M')

    }, to=f"ai_chat_{chat_id}")

    return jsonify({'ok': True})

@socketio.on('join_ai_chat')

def on_join_ai_chat(data):

    chat_id = data.get('chat_id')

    join_room(f"ai_chat_{chat_id}")

# --- SOCKET.IO ---

@socketio.on('connect')

def on_connect():

    if current_user.is_authenticated:

        current_user.is_online = True

        db.session.commit()

        # Track peak online

        online_count = User.query.filter_by(is_online=True).count()

        stats = SiteStats.query.first()

        if stats and online_count > (stats.peak_online or 0):

            stats.peak_online = online_count

            db.session.commit()

        emit('user_status', {'user_id': current_user.id, 'status': 'online'}, broadcast=True)

@socketio.on('disconnect')

def on_disconnect():

    if current_user.is_authenticated:

        current_user.is_online = False

        db.session.commit()

        emit('user_status', {'user_id': current_user.id, 'status': 'offline'}, broadcast=True)

@socketio.on('join')

def on_join(data):

    room = data.get('room')

    join_room(room)

@socketio.on('join_user_room')

def on_join_user_room(data):

    user_id = data.get('user_id') or current_user.id

    join_room(f"user_{int(user_id)}")

@socketio.on('typing')

def on_typing(data):

    room = data.get('room_id')

    emit('typing', data, to=room)

@socketio.on('presence')

def on_presence(data):

    emit('presence', {'user_id': current_user.id, 'online': data.get('online', True)}, broadcast=True)

@socketio.on('call_invite')

def on_call_invite(data):

    to_user_id = data.get('to_user_id')

    if not to_user_id:

        return

    emit('call_invite', {

        'from_id': current_user.id,

        'from_username': data.get('from_username'),

        'from_avatar': data.get('from_avatar'),

        'chat_id': data.get('chat_id'),

        'kind': data.get('kind', 'audio')

    }, to=f"user_{int(to_user_id)}")

@socketio.on('call_accept')

def on_call_accept(data):

    to_user_id = data.get('to_user_id')

    if not to_user_id:

        return

    emit('call_accepted', {

        'from_id': current_user.id,

        'chat_id': data.get('chat_id'),

        'kind': data.get('kind', 'audio')

    }, to=f"user_{int(to_user_id)}")

@socketio.on('call_decline')

def on_call_decline(data):

    to_user_id = data.get('to_user_id')

    if not to_user_id:

        return

    emit('call_declined', {

        'from_id': current_user.id,

        'reason': data.get('reason', 'Отклонено')

    }, to=f"user_{int(to_user_id)}")

@socketio.on('call_end')

def on_call_end(data):

    to_user_id = data.get('to_user_id')

    if not to_user_id:

        return

    emit('call_ended', {

        'from_id': current_user.id,

        'reason': data.get('reason', 'Звонок завершён')

    }, to=f"user_{int(to_user_id)}")

@socketio.on('call_signal')

def on_call_signal(data):

    to_user_id = data.get('to_user_id')

    signal = data.get('signal')

    if not to_user_id or not signal:

        return

    emit('call_signal', {

        'from_id': current_user.id,

        'signal': signal

    }, to=f"user_{int(to_user_id)}")

# --- РЎРћР—Р”РђРќРР• РўРђР‘Р›РР¦ Р РђР”РњРРќРђ ---

with app.app_context():

    db.create_all()

    # --- Р’Р Р•РњР•РќРќР«Р™ Р¤РРљРЎ Р‘РђР—Р« Р”РђРќРќР«РҐ (Р›Р•Р§Р•РќРР• РћРЁРР‘РљР) ---

    # Этот блок добавит недостающие колонки в существующую базу на Render

    from sqlalchemy import text

    try:

        with db.engine.connect() as conn:

            conn.execute(text("ALTER TABLE posts ADD COLUMN IF NOT EXISTS is_moderated BOOLEAN DEFAULT TRUE;"))

            conn.execute(text("ALTER TABLE posts ADD COLUMN IF NOT EXISTS moderation_reason VARCHAR(200);"))

            conn.execute(text("ALTER TABLE posts ADD COLUMN IF NOT EXISTS edited_at TIMESTAMP;"))

            conn.execute(text("ALTER TABLE posts ADD COLUMN IF NOT EXISTS co_author_id INTEGER;"))

            conn.execute(text("ALTER TABLE posts ADD COLUMN IF NOT EXISTS comments_enabled BOOLEAN DEFAULT TRUE;"))

            conn.execute(text("ALTER TABLE posts ADD COLUMN IF NOT EXISTS client_token VARCHAR(80);"))

            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS banner VARCHAR(300);"))

            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS color_theme VARCHAR(20) DEFAULT 'blue';"))

            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT NOW();"))

            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS last_seen TIMESTAMP DEFAULT NOW();"))

            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS email_confirmed BOOLEAN DEFAULT FALSE;"))

            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS email_confirmation_token VARCHAR(100);"))

            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_online BOOLEAN DEFAULT FALSE;"))

            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS total_visits INTEGER DEFAULT 0;"))

            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS telegram_id VARCHAR(100);"))
            conn.execute(text(f"ALTER TABLE users ADD COLUMN IF NOT EXISTS ai_credits INTEGER DEFAULT {AI_DAILY_CREDITS};"))
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS ai_credits_reset_at TIMESTAMP DEFAULT NOW();"))
            conn.execute(text(f"UPDATE users SET ai_credits = {AI_DAILY_CREDITS} WHERE ai_credits IS NULL;"))
            conn.execute(text("UPDATE users SET ai_credits_reset_at = NOW() WHERE ai_credits_reset_at IS NULL;"))

            conn.execute(text("ALTER TABLE messages ADD COLUMN IF NOT EXISTS edited_at TIMESTAMP;"))

            conn.execute(text("ALTER TABLE messages ADD COLUMN IF NOT EXISTS delivered_at TIMESTAMP;"))

            conn.execute(text("ALTER TABLE messages ADD COLUMN IF NOT EXISTS read_at TIMESTAMP;"))

            conn.execute(text("ALTER TABLE messages ADD COLUMN IF NOT EXISTS deleted_for_all BOOLEAN DEFAULT FALSE;"))

            conn.execute(text("ALTER TABLE messages ADD COLUMN IF NOT EXISTS deleted_for TEXT DEFAULT '[]';"))

            conn.execute(text("ALTER TABLE messages ADD COLUMN IF NOT EXISTS client_token VARCHAR(80);"))

            conn.execute(text("ALTER TABLE comments ADD COLUMN IF NOT EXISTS client_token VARCHAR(80);"))

            conn.execute(text("ALTER TABLE groups ADD COLUMN IF NOT EXISTS description VARCHAR(300);"))

            conn.execute(text("ALTER TABLE groups ADD COLUMN IF NOT EXISTS is_private BOOLEAN DEFAULT FALSE;"))

            # FontanAI tables

            conn.execute(text("""

                CREATE TABLE IF NOT EXISTS ai_chats (

                    id SERIAL PRIMARY KEY,

                    user_id INTEGER REFERENCES users(id),

                    title VARCHAR(200) DEFAULT 'Новый чат',

                    created_at TIMESTAMP DEFAULT NOW(),

                    updated_at TIMESTAMP DEFAULT NOW(),

                    is_admin_mode BOOLEAN DEFAULT FALSE

                )

            """))

            conn.execute(text("""

                CREATE TABLE IF NOT EXISTS ai_messages (

                    id SERIAL PRIMARY KEY,

                    chat_id INTEGER REFERENCES ai_chats(id) ON DELETE CASCADE,

                    role VARCHAR(20) NOT NULL,

                    content TEXT,

                    file_url VARCHAR(300),

                    file_type VARCHAR(20),

                    timestamp TIMESTAMP DEFAULT NOW()

                )

            """))

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
