import os
import uuid
import json
import random
import string
from datetime import datetime, timedelta
# Подключаем Cloudinary
import cloudinary
import cloudinary.uploader
import cloudinary.api
from flask import Flask, render_template, redirect, url_for, request, flash, jsonify, abort, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import or_, and_, func, desc, text
import jinja2
import re  # Добавлен глобальный import re

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

# --- ГЕНЕРАЦИЯ КАПЧИ ---
def generate_captcha():
    """Генерирует простую капчу из 6 символов"""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

# --- AI МОДЕРАЦИЯ КОНТЕНТА (УЛУЧШЕННАЯ) ---
def moderate_content(text):
    """Улучшенная AI модерация контента на запрещённые слова"""
    if not text:
        return True, ""
   
    # Расширенный список запрещённых слов
    forbidden_words = [
        'спам', 'реклама', 'казино', 'ставки', 'наркотики',
        'оружие', 'взлом', 'hack', 'porn', 'sex', 'scam',
        'fraud', 'phishing', 'malware', 'virus', 'crack'
    ]
   
    text_lower = text.lower()
    for word in forbidden_words:
        if word in text_lower:
            return False, f"Обнаружено запрещённое слово: {word}"
   
    # Проверка на чрезмерное количество ссылок (спам)
    if text_lower.count('http://') + text_lower.count('https://') > 3:
        return False, "Слишком много ссылок в сообщении"
   
    # Проверка на капс (более 70% заглавных букв)
    letters = [c for c in text if c.isalpha()]
    if len(letters) > 10:
        caps_ratio = sum(1 for c in letters if c.isupper()) / len(letters)
        if caps_ratio > 0.7:
            return False, "Слишком много заглавных букв (капс)"
   
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
    banner = db.Column(db.String(300), default=None) # НОВОЕ: Баннер профиля
    theme = db.Column(db.String(10), default='light')
    color_scheme = db.Column(db.String(20), default='blue') # НОВОЕ: Цветовая схема
   
    # Поля админа
    is_admin = db.Column(db.Boolean, default=False)
    is_banned = db.Column(db.Boolean, default=False)
    is_verified = db.Column(db.Boolean, default=False)
   
    # НОВОЕ: Статус онлайн
    is_online = db.Column(db.Boolean, default=False)
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
   
    # НОВОЕ: Статус "Печатает..."
    is_typing = db.Column(db.Boolean, default=False)
    typing_in_chat = db.Column(db.Integer, nullable=True) # ID чата где печатает
    # --- ИСПРАВЛЕНИЕ: Добавлен foreign_keys для постов ---
    posts = db.relationship('Post', foreign_keys='Post.user_id', backref='author', lazy=True)
   
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

# НОВОЕ: Таблица для уведомлений
class Notification(db.Model):
    __tablename__ = 'notifications'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    type = db.Column(db.String(50), nullable=False) # like, comment, follow, mention
    from_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'), nullable=True)
    message = db.Column(db.String(300), nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
   
    # --- ИСПРАВЛЕНИЕ: Явное указание ключей ---
    user = db.relationship('User', foreign_keys=[user_id], backref='notifications')
    from_user = db.relationship('User', foreign_keys=[from_user_id])

# НОВОЕ: Массовые рассылки от админа
class BroadcastMessage(db.Model):
    __tablename__ = 'broadcast_messages'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    admin_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
   
    admin = db.relationship('User', backref='broadcasts')

# НОВОЕ: Жалобы (Репорты)
class Report(db.Model):
    __tablename__ = 'reports'
    id = db.Column(db.Integer, primary_key=True)
    reporter_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    reported_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    reported_post_id = db.Column(db.Integer, db.ForeignKey('posts.id'), nullable=True)
    reason = db.Column(db.String(500), nullable=False)
    status = db.Column(db.String(20), default='pending') # pending, reviewed, resolved
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
   
    # --- ИСПРАВЛЕНИЕ: Добавлены foreign_keys ---
    reporter = db.relationship('User', foreign_keys=[reporter_id], backref='reports_sent')
    reported_user = db.relationship('User', foreign_keys=[reported_user_id], backref='reports_received')

# НОВОЕ: Активность сеансов
class UserSession(db.Model):
    __tablename__ = 'user_sessions'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    session_token = db.Column(db.String(100), unique=True, nullable=False)
    device_info = db.Column(db.String(300), nullable=True)
    ip_address = db.Column(db.String(50), nullable=True)
    location = db.Column(db.String(100), nullable=True) # Город/страна
    login_timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    last_activity = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
   
    user = db.relationship('User', backref='sessions')

# НОВОЕ: История входов
class LoginHistory(db.Model):
    __tablename__ = 'login_history'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    ip_address = db.Column(db.String(50), nullable=True)
    location = db.Column(db.String(100), nullable=True)
    device_info = db.Column(db.String(300), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    success = db.Column(db.Boolean, default=True)
   
    user = db.relationship('User', backref='login_history')

# НОВОЕ: Истории (Stories)
class Story(db.Model):
    __tablename__ = 'stories'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    media_url = db.Column(db.String(300), nullable=False)
    media_type = db.Column(db.String(20), nullable=False) # image или video
    caption = db.Column(db.String(200), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False) # Удаляется через 24 часа
    views_count = db.Column(db.Integer, default=0)
   
    author = db.relationship('User', backref='stories')
    views = db.relationship('StoryView', backref='story', cascade='all, delete-orphan')

# НОВОЕ: Просмотры историй
class StoryView(db.Model):
    __tablename__ = 'story_views'
    id = db.Column(db.Integer, primary_key=True)
    story_id = db.Column(db.Integer, db.ForeignKey('stories.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
   
    viewer = db.relationship('User', backref='story_views')

# НОВОЕ: Хэштеги
class Hashtag(db.Model):
    __tablename__ = 'hashtags'
    id = db.Column(db.Integer, primary_key=True)
    tag = db.Column(db.String(100), unique=True, nullable=False)
    usage_count = db.Column(db.Integer, default=0)
   
    posts = db.relationship('PostHashtag', backref='hashtag', cascade='all, delete-orphan')

# НОВОЕ: Связь постов и хэштегов
class PostHashtag(db.Model):
    __tablename__ = 'post_hashtags'
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'), nullable=False)
    hashtag_id = db.Column(db.Integer, db.ForeignKey('hashtags.id'), nullable=False)

# НОВОЕ: Упоминания пользователей
class Mention(db.Model):
    __tablename__ = 'mentions'
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'), nullable=True)
    comment_id = db.Column(db.Integer, db.ForeignKey('comments.id'), nullable=True)
    mentioned_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    mentioner_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
   
    # --- ИСПРАВЛЕНИЕ: Добавлены foreign_keys ---
    mentioned_user = db.relationship('User', foreign_keys=[mentioned_user_id], backref='mentions_received')
    mentioner = db.relationship('User', foreign_keys=[mentioner_user_id], backref='mentions_made')

# НОВОЕ: Карусель медиа (несколько фото/видео в одном посте)
class PostMedia(db.Model):
    __tablename__ = 'post_media'
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'), nullable=False)
    media_url = db.Column(db.String(300), nullable=False)
    media_type = db.Column(db.String(20), nullable=False) # image или video
    order = db.Column(db.Integer, default=0) # Порядок в карусели

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

# ОБНОВЛЁННАЯ: Группы/Клубы с дополнительными функциями
class Group(db.Model):
    __tablename__ = 'groups'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True) # НОВОЕ
    creator_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    avatar = db.Column(db.String(300), nullable=True) # НОВОЕ
    is_private = db.Column(db.Boolean, default=False) # НОВОЕ: Приватный клуб
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
   
    # НОВОЕ: Роли в группах
    roles = db.relationship('GroupRole', backref='group', cascade='all, delete-orphan')

# НОВОЕ: Роли в группах
class GroupRole(db.Model):
    __tablename__ = 'group_roles'
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('groups.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    role = db.Column(db.String(20), default='member') # admin, moderator, editor, member
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)

# НОВОЕ: Заявки на вступление в приватные группы
class GroupJoinRequest(db.Model):
    __tablename__ = 'group_join_requests'
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('groups.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    message = db.Column(db.String(300), nullable=True)
    status = db.Column(db.String(20), default='pending') # pending, approved, rejected
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

# ОБНОВЛЁННАЯ: Сообщения с поддержкой редактирования и удаления
class Message(db.Model):
    __tablename__ = 'messages'
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    group_id = db.Column(db.Integer, db.ForeignKey('groups.id'), nullable=True)
    body = db.Column(db.Text, nullable=True)
    voice_filename = db.Column(db.String(300), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
   
    # НОВОЕ: Статусы сообщений
    is_read = db.Column(db.Boolean, default=False)
    is_delivered = db.Column(db.Boolean, default=False)
    is_edited = db.Column(db.Boolean, default=False) # Отредактировано
    edited_at = db.Column(db.DateTime, nullable=True)
    is_deleted_for_sender = db.Column(db.Boolean, default=False) # Удалено у меня
    is_deleted_for_all = db.Column(db.Boolean, default=False) # Удалено у всех
   
    # --- ИСПРАВЛЕНИЕ: Добавлены foreign_keys ---
    sender = db.relationship('User', foreign_keys=[sender_id], backref='sent_messages')
    recipient = db.relationship('User', foreign_keys=[recipient_id], backref='received_messages')

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
    options = db.Column(db.Text, nullable=False) # JSON строка с вариантами
    votes = db.Column(db.Text, default='{}') # JSON строка с голосами

class PollVote(db.Model):
    __tablename__ = 'poll_votes'
    id = db.Column(db.Integer, primary_key=True)
    poll_id = db.Column(db.Integer, db.ForeignKey('polls.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    option_index = db.Column(db.Integer, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

# ОБНОВЛЁННАЯ: Посты с дополнительными функциями
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
   
    # НОВОЕ: Дополнительные функции
    is_edited = db.Column(db.Boolean, default=False) # Отредактирован
    edited_at = db.Column(db.DateTime, nullable=True)
    comments_disabled = db.Column(db.Boolean, default=False) # Комментарии отключены
   
    # НОВОЕ: Коллаборации (совместный пост)
    collab_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
   
    # НОВОЕ: Алгоритм умной ленты (engagement score)
    engagement_score = db.Column(db.Float, default=0.0)
   
    comments_rel = db.relationship('Comment', backref='post', cascade="all, delete-orphan", lazy=True)
    likes_rel = db.relationship('Like', backref='post', cascade="all, delete-orphan", lazy=True)
    views_rel = db.relationship('PostView', backref='post', cascade="all, delete-orphan", lazy=True)
    poll = db.relationship('Poll', backref='post', uselist=False, cascade="all, delete-orphan")
   
    # НОВОЕ: Связь с каруселью медиа
    media_items = db.relationship('PostMedia', backref='post', cascade='all, delete-orphan')
   
    # НОВОЕ: Связь с хэштегами
    hashtags_rel = db.relationship('PostHashtag', backref='post', cascade='all, delete-orphan')

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# --- ФУНКЦИЯ ОБНОВЛЕНИЯ СТАТУСА ОНЛАЙН ---
def update_user_online_status():
    """Обновляет статус онлайн для текущего пользователя"""
    if current_user.is_authenticated:
        current_user.is_online = True
        current_user.last_seen = datetime.utcnow()
        db.session.commit()

# --- ФУНКЦИЯ СОЗДАНИЯ УВЕДОМЛЕНИЯ ---
def create_notification(user_id, notification_type, from_user_id=None, post_id=None, message=""):
    """Создаёт уведомление для пользователя"""
    notification = Notification(
        user_id=user_id,
        type=notification_type,
        from_user_id=from_user_id,
        post_id=post_id,
        message=message
    )
    db.session.add(notification)
    db.session.commit()

# --- ФУНКЦИЯ ПАРСИНГА ХЭШТЕГОВ ---
def parse_hashtags(text):
    """Извлекает хэштеги из текста"""
    if not text:
        return []
    # Находим все слова, начинающиеся с #
    hashtags = re.findall(r'#(\w+)', text)
    return [tag.lower() for tag in hashtags]

# --- ФУНКЦИЯ ПАРСИНГА УПОМИНАНИЙ ---
def parse_mentions(text):
    """Извлекает упоминания @username из текста"""
    if not text:
        return []
    # Находим все слова, начинающиеся с @
    mentions = re.findall(r'@(\w+)', text)
    return mentions

# --- ФУНКЦИЯ ПОДСВЕТКИ ХЭШТЕГОВ И УПОМИНАНИЙ ---
def highlight_text(text):
    """Подсвечивает хэштеги и упоминания в тексте"""
    if not text:
        return text
    # Подсветка хэштегов
    text = re.sub(
        r'#(\w+)',
        r'<a href="/hashtag/\1" class="hashtag">#\1</a>',
        text
    )
    # Подсветка упоминаний
    text = re.sub(
        r'@(\w+)',
        r'<a href="/profile/\1" class="mention">@\1</a>',
        text
    )
    return text

# --- ФУНКЦИЯ РАСЧЁТА ENGAGEMENT SCORE ---
def calculate_engagement_score(post):
    """Рассчитывает рейтинг поста для умной ленты"""
    # Формула: (лайки * 2 + комментарии * 3 + просмотры * 0.1) / время_с_публикации
    likes_count = len(post.likes_rel)
    comments_count = len(post.comments_rel)
    views_count = post.views
   
    # Вес по времени (свежие посты получают бонус)
    time_since_post = (datetime.utcnow() - post.timestamp).total_seconds() / 3600 # часы
    time_decay = 1 / (1 + time_since_post / 24) # Уменьшается со временем
   
    score = (likes_count * 2 + comments_count * 3 + views_count * 0.1) * time_decay
    return score

# --- ОЧИСТКА УСТАРЕВШИХ ИСТОРИЙ ---
def cleanup_expired_stories():
    """Удаляет истории старше 24 часов"""
    expired = Story.query.filter(Story.expires_at < datetime.utcnow()).all()
    for story in expired:
        db.session.delete(story)
    if expired:
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

# =============================================================================
# ШАБЛОНЫ (ИЗ СТАРОГО КОДА, ОБНОВЛЕННЫЕ ДЛЯ НОВЫХ ФУНКЦИЙ)
# =============================================================================
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

        /* НОВОЕ: Стили для уведомлений */
        .notification-unread {
            background-color: var(--hover-bg);
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
                    <a class="nav-link text-white fs-5" href="{{ url_for('notifications') }}"><i class="bi bi-bell-fill"></i> <span id="unread-count"></span></a>
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
            // Загрузка количества непрочитанных уведомлений
            fetch('/notifications/unread_count')
                .then(r => r.json())
                .then(data => {
                    const countSpan = document.getElementById('unread-count');
                    if (countSpan && data.count > 0) {
                        countSpan.innerText = data.count;
                    }
                });
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
            <a href="{{ url_for('search') }}" class="btn btn-outline-secondary w-100 mb-2 rounded-pill">Поиск</a>
        </div>
    </div>

    <div class="col-md-6">
        <!-- НОВОЕ: Секция историй -->
        {% if stories %}
        <div class="card mb-4 p-3">
            <h5>Истории</h5>
            <div class="d-flex overflow-auto gap-3">
                {% for story in stories %}
                <a href="{{ url_for('view_story', story_id=story.id) }}" class="text-center">
                    <div class="avatar avatar-xl">
                        <img src="{{ story.author.avatar or 'default_avatar.jpg' }}">
                    </div>
                    <small>{{ story.author.username }}</small>
                </a>
                {% endfor %}
            </div>
        </div>
        {% endif %}

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
                            <input type="file" name="media[]" multiple hidden accept="image/*,video/*">
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
        {% if post.content %}<p class="card-text fs-6">{{ highlight_text(post.content) | safe }}</p>{% endif %}
        
        <!-- НОВОЕ: Карусель медиа -->
        {% if post.media_items %}
            <div id="carousel-{{ post.id }}" class="carousel slide">
                <div class="carousel-inner">
                    {% for media in post.media_items | sort(attribute='order') %}
                    <div class="carousel-item {% if loop.first %}active{% endif %}">
                        {% if media.media_type == 'image' %}
                            <img src="{{ media.media_url }}" class="d-block w-100 rounded post-media" alt="...">
                        {% else %}
                            <video controls class="d-block w-100 rounded post-media">
                                <source src="{{ media.media_url }}" type="video/mp4">
                            </video>
                        {% endif %}
                    </div>
                    {% endfor %}
                </div>
                {% if post.media_items | length > 1 %}
                <button class="carousel-control-prev" type="button" data-bs-target="#carousel-{{ post.id }}" data-bs-slide="prev">
                    <span class="carousel-control-prev-icon" aria-hidden="true"></span>
                    <span class="visually-hidden">Previous</span>
                </button>
                <button class="carousel-control-next" type="button" data-bs-target="#carousel-{{ post.id }}" data-bs-slide="next">
                    <span class="carousel-control-next-icon" aria-hidden="true"></span>
                    <span class="visually-hidden">Next</span>
                </button>
                {% endif %}
            </div>
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
            {% if comment.text %}<div class="small">{{ highlight_text(comment.text) | safe }}</div>{% endif %}
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
                    <div class="mb-3">
                        <label>Описание</label>
                        <textarea name="description" class="form-control"></textarea>
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
<div style="height: 180px; background: url('{{ user.banner or 'default_banner.jpg' }}') no-repeat center; background-size: cover;"></div> 
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
        <i class="bi bi-heart-fill"></i> {{ followers_count }} вайберов
    </span>
    <span class="badge bg-secondary">
        {{ following_count }} подписок
    </span>
</div>
<!-- НОВОЕ: Статус онлайн -->
<small class="text-muted">
    {% if user.is_online %}
        <span class="text-success">Онлайн</span>
    {% else %}
        Был онлайн {{ user.last_seen|time_ago }}
    {% endif %}
</small>
</div> 
<div class="d-flex gap-2 flex-wrap"> 
{% if current_user.id != user.id %} 
    {% if is_following %}
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

    <a href="{{ url_for('report_user', user_id=user.id) }}" class="btn btn-outline-warning rounded-pill px-4">Пожаловаться</a>

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
<img src="{{ current_user.banner }}" style="width: 100%; height: 200px; object-fit: cover; border-radius: 10px;" class="mb-3">
{% endif %}
<label class="btn btn-sm btn-outline-primary rounded-pill">Изменить баннер <input type="file" name="banner" hidden accept="image/*"></label>
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
<select name="color_scheme" class="form-select">
    <option value="blue" {% if current_user.color_scheme == 'blue' %}selected{% endif %}>Синяя</option>
    <option value="purple" {% if current_user.color_scheme == 'purple' %}selected{% endif %}>Фиолетовая</option>
    <option value="orange" {% if current_user.color_scheme == 'orange' %}selected{% endif %}>Оранжевая</option>
    <option value="green" {% if current_user.color_scheme == 'green' %}selected{% endif %}>Зелёная</option>
</select>
</div>
<button type="submit" class="btn btn-primary w-100 py-2 rounded-pill">Сохранить</button>
</form>
</div>
</div>
</div> 
{% endblock %}
""",

    'auth.html': """{% extends "base.html" %} {% block content %} <div class="row justify-content-center"><div class="col-md-4"><div class="card p-4 mt-5"><h3 class="text-center">{{ title }}</h3><form method="POST">{% if not is_login %}<input type="email" name="email" class="form-control mb-3" placeholder="Email" required>{% endif %}<input type="text" name="username" class="form-control mb-3" placeholder="Ник" required><input type="password" name="password" class="form-control mb-3" placeholder="Пароль" required><p>Капча: <strong>{{ captcha }}</strong></p><input type="text" name="captcha" class="form-control mb-3" placeholder="Введите капчу" required><button class="btn btn-primary w-100">{{ title }}</button></form><div class="text-center mt-3"><a href="{{ url_for('login' if not is_login else 'register') }}">{{ 'Войти' if not is_login else 'Регистрация' }}</a></div></div></div></div> {% endblock %}""",

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
    # Заглушки для новых шаблонов (чтобы код не падал)
    'notifications.html': """{% extends "base.html" %} {% block content %} <h3>Уведомления</h3> {% for n in notifications %} <div class="card mb-2 {% if not n.is_read %}notification-unread{% endif %}"> <div class="card-body">{{ n.message }} <small>{{ n.timestamp|time_ago }}</small></div> </div> {% endfor %} {% endblock %}""",
    'story_view.html': """{% extends "base.html" %} {% block content %} <div class="d-flex justify-content-center"> {% if story.media_type == 'image' %} <img src="{{ story.media_url }}" alt="Story"> {% else %} <video controls><source src="{{ story.media_url }}"></video> {% endif %} <p>{{ story.caption }}</p> </div> {% endblock %}""",
    'hashtag_posts.html': """{% extends "base.html" %} {% block content %} <h3>Посты с #{{ tag }}</h3> {% for post in posts %} {% include 'post_card.html' %} {% endfor %} {% endblock %}""",
    'search.html': """{% extends "base.html" %} {% block content %} <h3>Результаты поиска по "{{ query }}"</h3> <h5>Пользователи</h5> {% for u in results.users %} <p>{{ u.username }}</p> {% endfor %} <h5>Посты</h5> {% for p in results.posts %} {% include 'post_card.html' %} {% endfor %} <h5>Хэштеги</h5> {% for h in results.hashtags %} <p>#{{ h.tag }}</p> {% endfor %} <h5>Группы</h5> {% for g in results.groups %} <p>{{ g.name }}</p> {% endfor %} {% endblock %}""",
    'admin_panel.html': """{% extends "base.html" %} {% block content %} <h3>Админ панель</h3> <p>Пользователей: {{ total_users }}</p> <p>Постов: {{ total_posts }}</p> <p>Жалоб: {{ total_reports }}</p> <form action="{{ url_for('admin_broadcast') }}" method="POST"> <input name="title" placeholder="Заголовок"> <textarea name="message" placeholder="Сообщение"></textarea> <button>Рассылка</button> </form> {% endblock %}""",
    'sessions.html': """{% extends "base.html" %} {% block content %} <h3>Активные сеансы</h3> {% for s in sessions %} <p>{{ s.device_info }} - Последняя активность: {{ s.last_activity|time_ago }} <a href="{{ url_for('logout_session', session_id=s.id) }}">Выйти</a></p> {% endfor %} <a href="{{ url_for('logout_all_sessions') }}">Выйти со всех</a> {% endblock %}""",
    'login_history.html': """{% extends "base.html" %} {% block content %} <h3>История входов</h3> {% for h in history %} <p>{{ h.timestamp|time_ago }} - {{ h.device_info }} - Успех: {{ h.success }}</p> {% endfor %} {% endblock %}""",
    'edit_post.html': """{% extends "base.html" %} {% block content %} <h3>Редактировать пост</h3> <form method="POST"> <textarea name="content">{{ post.content }}</textarea> <button>Сохранить</button> </form> {% endblock %}""",
    'groups.html': """{% extends "base.html" %} {% block content %} <h3>Группы</h3> <h5>Мои группы</h5> {% for g in my_groups %} <p>{{ g.name }}</p> {% endfor %} <h5>Все группы</h5> {% for g in groups %} <p>{{ g.name }}</p> {% endfor %} {% endblock %}""",
    'group_detail.html': """{% extends "base.html" %} {% block content %} <h3>{{ group.name }}</h3> {% if is_member %} <div>Сообщения: {% for m in messages %} <p>{{ m.body }}</p> {% endfor %}</div> <form action="{{ url_for('send_group_message', group_id=group.id) }}" method="POST"> <input name="body"> <button>Отправить</button> </form> {% else %} {% if group.is_private %} <a href="{{ url_for('join_group', group_id=group.id) }}">Отправить заявку</a> {% else %} <a href="{{ url_for('join_group', group_id=group.id) }}">Вступить</a> {% endif %} {% endif %} {% endblock %}""",
    # Другие заглушки, если нужно
}

app.jinja_env.filters['time_ago'] = time_ago
app.jinja_env.filters['from_json'] = json.loads
app.jinja_loader = jinja2.DictLoader(templates)

# =============================================================================
# РОУТЫ
# =============================================================================
@app.before_request
def before_request():
    """Выполняется перед каждым запросом"""
    if current_user.is_authenticated and current_user.is_banned:
        logout_user()
        flash("Ваш аккаунт заблокирован администрацией.", "danger")
        return redirect(url_for('login'))
    # Обновляем статус онлайн
    update_user_online_status()
    # Очищаем устаревшие истории
    cleanup_expired_stories()

@app.route('/toggle_theme', methods=['POST'])
@login_required
def toggle_theme():
    current_user.theme = 'dark' if current_user.theme == 'light' else 'light'
    db.session.commit()
    return jsonify({'theme': current_user.theme})

# --- ГЛАВНАЯ СТРАНИЦА (УМНАЯ ЛЕНТА) ---
@app.route('/')
@login_required
def index():
    # Получаем ID пользователей, на которых подписан текущий юзер
    following_ids = [f.following_id for f in current_user.following.all()]
    following_ids.append(current_user.id) # Добавляем свои посты
   
    # Умная лента: сортировка по engagement_score
    posts = Post.query.filter(
        Post.user_id.in_(following_ids),
        Post.is_moderated == True
    ).all()
   
    # Обновляем engagement_score для каждого поста
    for post in posts:
        post.engagement_score = calculate_engagement_score(post)
    db.session.commit()
   
    # Сортируем по рейтингу
    posts = sorted(posts, key=lambda p: p.engagement_score, reverse=True)
   
    # Получаем активные истории от подписок
    stories = Story.query.filter(
        Story.user_id.in_(following_ids),
        Story.expires_at > datetime.utcnow()
    ).order_by(Story.timestamp.desc()).all()
   
    return render_template('index.html', posts=posts, stories=stories, highlight_text=highlight_text)

# --- ЦЕНТР УВЕДОМЛЕНИЙ ---
@app.route('/notifications')
@login_required
def notifications():
    """Показывает все уведомления пользователя"""
    user_notifications = Notification.query.filter_by(
        user_id=current_user.id
    ).order_by(Notification.timestamp.desc()).all()
   
    return render_template('notifications.html', notifications=user_notifications)

@app.route('/notifications/mark_read/<int:notification_id>', methods=['POST'])
@login_required
def mark_notification_read(notification_id):
    """Отмечает уведомление как прочитанное"""
    notification = Notification.query.get(notification_id)
    if notification and notification.user_id == current_user.id:
        notification.is_read = True
        db.session.commit()
    return jsonify({'success': True})

@app.route('/notifications/unread_count')
@login_required
def unread_notifications_count():
    """Возвращает количество непрочитанных уведомлений"""
    count = Notification.query.filter_by(
        user_id=current_user.id,
        is_read=False
    ).count()
    return jsonify({'count': count})

# --- ИСТОРИИ (STORIES) ---
@app.route('/create_story', methods=['POST'])
@login_required
def create_story():
    """Создаёт новую историю"""
    file = request.files.get('media')
    caption = request.form.get('caption')
   
    if file and file.filename:
        ext = file.filename.rsplit('.', 1)[1].lower()
        if ext in ['mp4', 'webm', 'mov']:
            media_type = 'video'
            media_url = upload_to_cloud(file, resource_type="video")
        else:
            media_type = 'image'
            media_url = upload_to_cloud(file, resource_type="image")
       
        if media_url:
            # История истекает через 24 часа
            expires_at = datetime.utcnow() + timedelta(hours=24)
           
            story = Story(
                user_id=current_user.id,
                media_url=media_url,
                media_type=media_type,
                caption=caption,
                expires_at=expires_at
            )
            db.session.add(story)
            db.session.commit()
            flash("История опубликована!", "success")
   
    return redirect(url_for('index'))

@app.route('/story/<int:story_id>')
@login_required
def view_story(story_id):
    """Просмотр истории"""
    story = Story.query.get_or_404(story_id)
   
    # Проверяем, не истекла ли история
    if story.expires_at < datetime.utcnow():
        flash("Эта история уже удалена", "info")
        return redirect(url_for('index'))
   
    # Добавляем просмотр
    existing_view = StoryView.query.filter_by(
        story_id=story_id,
        user_id=current_user.id
    ).first()
   
    if not existing_view:
        story.views_count += 1
        view = StoryView(story_id=story_id, user_id=current_user.id)
        db.session.add(view)
        db.session.commit()
   
    return render_template('story_view.html', story=story)

@app.route('/delete_story/<int:story_id>')
@login_required
def delete_story(story_id):
    """Удаление истории"""
    story = Story.query.get_or_404(story_id)
    if story.user_id == current_user.id:
        db.session.delete(story)
        db.session.commit()
        flash("История удалена", "success")
    return redirect(url_for('index'))

# --- ПОИСК ПО ХЭШТЕГАМ ---
@app.route('/hashtag/<tag>')
@login_required
def hashtag_posts(tag):
    """Показывает все посты с определённым хэштегом"""
    hashtag = Hashtag.query.filter_by(tag=tag.lower()).first()
   
    if not hashtag:
        flash(f"Хэштег #{tag} не найден", "info")
        return redirect(url_for('index'))
   
    # Получаем все посты с этим хэштегом
    post_ids = [ph.post_id for ph in hashtag.posts]
    posts = Post.query.filter(
        Post.id.in_(post_ids),
        Post.is_moderated == True
    ).order_by(Post.timestamp.desc()).all()
   
    return render_template('hashtag_posts.html', tag=tag, posts=posts, highlight_text=highlight_text)

# --- ГЛОБАЛЬНЫЙ ПОИСК ---
@app.route('/search')
@login_required
def global_search():
    """Глобальный поиск по людям, постам, хэштегам и группам"""
    query = request.args.get('q', '').strip()
   
    if not query:
        return render_template('search.html', query='', results={})
   
    results = {
        'users': User.query.filter(
            or_(
                User.username.ilike(f'%{query}%'),
                User.bio.ilike(f'%{query}%')
            )
        ).limit(10).all(),
       
        'posts': Post.query.filter(
            Post.content.ilike(f'%{query}%'),
            Post.is_moderated == True
        ).order_by(Post.timestamp.desc()).limit(10).all(),
       
        'hashtags': Hashtag.query.filter(
            Hashtag.tag.ilike(f'%{query}%')
        ).order_by(Hashtag.usage_count.desc()).limit(10).all(),
       
        'groups': Group.query.filter(
            or_(
                Group.name.ilike(f'%{query}%'),
                Group.description.ilike(f'%{query}%')
            )
        ).limit(10).all()
    }
   
    return render_template('search.html', query=query, results=results)

# --- ЖАЛОБЫ (РЕПОРТЫ) ---
@app.route('/report/post/<int:post_id>', methods=['POST'])
@login_required
def report_post(post_id):
    """Пожаловаться на пост"""
    reason = request.form.get('reason')
   
    if reason:
        report = Report(
            reporter_id=current_user.id,
            reported_post_id=post_id,
            reason=reason
        )
        db.session.add(report)
        db.session.commit()
        flash("Жалоба отправлена администрации", "success")
   
    return redirect(request.referrer or url_for('index'))

@app.route('/report/user/<int:user_id>', methods=['POST'])
@login_required
def report_user(user_id):
    """Пожаловаться на пользователя"""
    reason = request.form.get('reason')
   
    if reason:
        report = Report(
            reporter_id=current_user.id,
            reported_user_id=user_id,
            reason=reason
        )
        db.session.add(report)
        db.session.commit()
        flash("Жалоба отправлена администрации", "success")
   
    return redirect(request.referrer or url_for('index'))

# --- АДМИН ПАНЕЛЬ ---
@app.route('/admin')
@login_required
def admin_panel():
    """Админ-панель с графиками и статистикой"""
    if not current_user.is_admin:
        abort(403)
   
    # Статистика
    total_users = User.query.count()
    total_posts = Post.query.count()
    total_reports = Report.query.filter_by(status='pending').count()
   
    # Графики: новые пользователи за последние 7 дней
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    new_users_data = db.session.query(
        func.date(User.id),
        func.count(User.id)
    ).filter(User.id >= 1).group_by(func.date(User.id)).all()
   
    # Посты за последние 7 дней
    posts_data = db.session.query(
        func.date(Post.timestamp),
        func.count(Post.id)
    ).filter(Post.timestamp >= seven_days_ago).group_by(func.date(Post.timestamp)).all()
   
    # Жалобы
    reports = Report.query.filter_by(status='pending').order_by(Report.timestamp.desc()).all()
   
    return render_template(
        'admin_panel.html',
        total_users=total_users,
        total_posts=total_posts,
        total_reports=total_reports,
        reports=reports,
        new_users_data=new_users_data,
        posts_data=posts_data
    )

@app.route('/admin/broadcast', methods=['POST'])
@login_required
def admin_broadcast():
    """Массовая рассылка уведомлений всем пользователям"""
    if not current_user.is_admin:
        abort(403)
   
    title = request.form.get('title')
    message = request.form.get('message')
   
    if title and message:
        # Создаём запись рассылки
        broadcast = BroadcastMessage(
            title=title,
            message=message,
            admin_id=current_user.id
        )
        db.session.add(broadcast)
       
        # Отправляем уведомление каждому пользователю
        all_users = User.query.all()
        for user in all_users:
            create_notification(
                user_id=user.id,
                notification_type='broadcast',
                from_user_id=current_user.id,
                message=f"{title}: {message}"
            )
       
        db.session.commit()
        flash(f"Рассылка отправлена {len(all_users)} пользователям!", "success")
   
    return redirect(url_for('admin_panel'))

@app.route('/admin/resolve_report/<int:report_id>')
@login_required
def resolve_report(report_id):
    """Отметить жалобу как решённую"""
    if not current_user.is_admin:
        abort(403)
   
    report = Report.query.get_or_404(report_id)
    report.status = 'resolved'
    db.session.commit()
    flash("Жалоба помечена как решённая", "success")
   
    return redirect(url_for('admin_panel'))

@app.route('/admin/ban_user/<int:user_id>')
@login_required
def ban_user(user_id):
    """Забанить пользователя"""
    if not current_user.is_admin:
        abort(403)
   
    user = User.query.get_or_404(user_id)
    user.is_banned = True
    db.session.commit()
    flash(f"Пользователь {user.username} забанен", "success")
   
    return redirect(request.referrer or url_for('admin_panel'))

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

# --- АКТИВНОСТЬ СЕАНСОВ ---
@app.route('/sessions')
@login_required
def user_sessions():
    """Показывает активные сеансы пользователя"""
    sessions = UserSession.query.filter_by(
        user_id=current_user.id,
        is_active=True
    ).order_by(UserSession.last_activity.desc()).all()
   
    return render_template('sessions.html', sessions=sessions)

@app.route('/logout_all_sessions')
@login_required
def logout_all_sessions():
    """Выйти со всех устройств"""
    UserSession.query.filter_by(user_id=current_user.id).update({'is_active': False})
    db.session.commit()
    logout_user()
    flash("Вы вышли со всех устройств", "success")
    return redirect(url_for('login'))

@app.route('/logout_session/<int:session_id>')
@login_required
def logout_session(session_id):
    """Выйти из конкретного сеанса"""
    session_obj = UserSession.query.get_or_404(session_id)
    if session_obj.user_id == current_user.id:
        session_obj.is_active = False
        db.session.commit()
        flash("Сеанс завершён", "success")
    return redirect(url_for('user_sessions'))

# --- ИСТОРИЯ ВХОДОВ ---
@app.route('/login_history')
@login_required
def login_history_page():
    """Показывает историю входов"""
    history = LoginHistory.query.filter_by(
        user_id=current_user.id
    ).order_by(LoginHistory.timestamp.desc()).limit(50).all()
   
    return render_template('login_history.html', history=history)

# --- РЕДАКТИРОВАНИЕ ПОСТОВ ---
@app.route('/edit_post/<int:post_id>', methods=['GET', 'POST'])
@login_required
def edit_post(post_id):
    """Редактирование поста"""
    post = Post.query.get_or_404(post_id)
   
    if post.user_id != current_user.id:
        abort(403)
   
    if request.method == 'POST':
        new_content = request.form.get('content')
       
        # AI модерация
        is_ok, reason = moderate_content(new_content)
       
        if is_ok:
            post.content = new_content
            post.is_edited = True
            post.edited_at = datetime.utcnow()
           
            # Обновляем хэштеги
            # Удаляем старые
            PostHashtag.query.filter_by(post_id=post.id).delete()
           
            # Добавляем новые
            hashtags = parse_hashtags(new_content)
            for tag in hashtags:
                hashtag = Hashtag.query.filter_by(tag=tag).first()
                if not hashtag:
                    hashtag = Hashtag(tag=tag, usage_count=0)
                    db.session.add(hashtag)
                    db.session.flush()
               
                hashtag.usage_count += 1
                db.session.add(PostHashtag(post_id=post.id, hashtag_id=hashtag.id))
           
            db.session.commit()
            flash("Пост обновлён", "success")
            return redirect(url_for('index'))
        else:
            flash(f"Модерация: {reason}", "warning")
   
    return render_template('edit_post.html', post=post)

# --- ОТКЛЮЧЕНИЕ КОММЕНТАРИЕВ ---
@app.route('/toggle_comments/<int:post_id>')
@login_required
def toggle_comments(post_id):
    """Включить/выключить комментарии к посту"""
    post = Post.query.get_or_404(post_id)
   
    if post.user_id != current_user.id:
        abort(403)
   
    post.comments_disabled = not post.comments_disabled
    db.session.commit()
   
    status = "отключены" if post.comments_disabled else "включены"
    flash(f"Комментарии {status}", "success")
   
    return redirect(request.referrer or url_for('index'))

# --- РЕДАКТИРОВАНИЕ СООБЩЕНИЙ В ЧАТЕ ---
@app.route('/edit_message/<int:message_id>', methods=['POST'])
@login_required
def edit_message(message_id):
    """Редактировать сообщение в чате"""
    message = Message.query.get_or_404(message_id)
   
    if message.sender_id != current_user.id:
        abort(403)
   
    new_body = request.form.get('body')
   
    if new_body:
        message.body = new_body
        message.is_edited = True
        message.edited_at = datetime.utcnow()
        db.session.commit()
        return jsonify({'success': True})
   
    return jsonify({'error': 'No content'}), 400

# --- УДАЛЕНИЕ СООБЩЕНИЙ ---
@app.route('/delete_message/<int:message_id>/<delete_type>')
@login_required
def delete_message(message_id, delete_type):
    """Удалить сообщение (для себя или для всех)"""
    message = Message.query.get_or_404(message_id)
   
    if delete_type == 'for_me':
        # Удалить у меня
        if message.sender_id == current_user.id:
            message.is_deleted_for_sender = True
        elif message.recipient_id == current_user.id:
            # Для получателя можно добавить отдельное поле
            pass
        db.session.commit()
        flash("Сообщение удалено у вас", "success")
   
    elif delete_type == 'for_all':
        # Удалить у всех (только отправитель)
        if message.sender_id == current_user.id:
            message.is_deleted_for_all = True
            db.session.commit()
            flash("Сообщение удалено у всех", "success")
        else:
            abort(403)
   
    return redirect(request.referrer or url_for('index'))

# --- СТАТУС "ПЕЧАТАЕТ..." ---
@app.route('/typing_status', methods=['POST'])
@login_required
def typing_status():
    """Обновить статус печати"""
    chat_id = request.json.get('chat_id')
    is_typing = request.json.get('is_typing', False)
   
    current_user.is_typing = is_typing
    current_user.typing_in_chat = chat_id if is_typing else None
    db.session.commit()
   
    return jsonify({'success': True})

@app.route('/check_typing/<int:chat_id>')
@login_required
def check_typing(chat_id):
    """Проверить, печатает ли собеседник"""
    # Находим собеседника
    other_user = User.query.get(chat_id)
   
    if other_user and other_user.is_typing and other_user.typing_in_chat == current_user.id:
        return jsonify({'is_typing': True})
   
    return jsonify({'is_typing': False})

# --- КНОПКА "ПОДЕЛИТЬСЯ" ---
@app.route('/share_post/<int:post_id>')
@login_required
def share_post(post_id):
    """Получить ссылку на пост для шаринга"""
    post = Post.query.get_or_404(post_id)
    share_url = request.host_url + f'post/{post_id}'
   
    return jsonify({
        'url': share_url,
        'telegram': f'https://t.me/share/url?url={share_url}',
        'whatsapp': f'https://wa.me/?text={share_url}'
    })

# --- КОЛЛАБОРАЦИИ ---
@app.route('/add_collab/<int:post_id>/<int:user_id>')
@login_required
def add_collab(post_id, user_id):
    """Добавить соавтора к посту"""
    post = Post.query.get_or_404(post_id)
   
    if post.user_id != current_user.id:
        abort(403)
   
    post.collab_user_id = user_id
    db.session.commit()
   
    # Уведомляем соавтора
    create_notification(
        user_id=user_id,
        notification_type='collab',
        from_user_id=current_user.id,
        post_id=post_id,
        message=f"{current_user.username} добавил вас как соавтора поста"
    )
   
    flash("Соавтор добавлен", "success")
    return redirect(url_for('index'))

# =============================================================================
# СУЩЕСТВУЮЩИЕ РОУТЫ (БЕЗ ИЗМЕНЕНИЙ)
# =============================================================================
@app.route('/profile/<username>')
@login_required
def profile(username):
    user = User.query.filter_by(username=username).first_or_404()
    posts = Post.query.filter_by(user_id=user.id, is_moderated=True).order_by(Post.timestamp.desc()).all()
   
    # Проверяем подписку
    is_following = Follow.query.filter_by(follower_id=current_user.id, following_id=user.id).first() is not None
   
    followers_count = user.followers.count()
    following_count = user.following.count()
   
    # Получаем активные истории пользователя
    user_stories = Story.query.filter_by(
        user_id=user.id
    ).filter(Story.expires_at > datetime.utcnow()).order_by(Story.timestamp.desc()).all()
   
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

    return render_template('profile.html',
                         user=user,
                         posts=posts,
                         is_following=is_following,
                         followers_count=followers_count,
                         following_count=following_count,
                         stories=user_stories,
                         highlight_text=highlight_text,
                         friendship_status=status)

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

# Создание таблиц
with app.app_context():
    db.create_all()
    
    # Временный фикс базы данных
    from sqlalchemy import text
    try:
        with db.engine.connect() as conn:
            conn.execute(text("ALTER TABLE posts ADD COLUMN IF NOT EXISTS is_moderated BOOLEAN DEFAULT TRUE;"))
            conn.execute(text("ALTER TABLE posts ADD COLUMN IF NOT EXISTS moderation_reason VARCHAR(200);"))
            conn.commit()
            print(">>> УСПЕШНО: Колонки добавлены в базу данных! <<<")
    except Exception as e:
        print(f">>> INFO (не ошибка): {e}")

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
    app.run(host='0.0.0.0', port=port, debug=False)
