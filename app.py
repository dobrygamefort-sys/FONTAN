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
    banner = db.Column(db.String(300), default=None)  # НОВОЕ: Баннер профиля
    theme = db.Column(db.String(10), default='light')
    color_scheme = db.Column(db.String(20), default='blue')  # НОВОЕ: Цветовая схема
    
    # Поля админа
    is_admin = db.Column(db.Boolean, default=False)
    is_banned = db.Column(db.Boolean, default=False)
    is_verified = db.Column(db.Boolean, default=False)
    
    # НОВОЕ: Статус онлайн
    is_online = db.Column(db.Boolean, default=False)
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    
    # НОВОЕ: Статус "Печатает..."
    is_typing = db.Column(db.Boolean, default=False)
    typing_in_chat = db.Column(db.Integer, nullable=True)  # ID чата где печатает

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
    type = db.Column(db.String(50), nullable=False)  # like, comment, follow, mention
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
    status = db.Column(db.String(20), default='pending')  # pending, reviewed, resolved
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
    location = db.Column(db.String(100), nullable=True)  # Город/страна
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
    media_type = db.Column(db.String(20), nullable=False)  # image или video
    caption = db.Column(db.String(200), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)  # Удаляется через 24 часа
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
    media_type = db.Column(db.String(20), nullable=False)  # image или video
    order = db.Column(db.Integer, default=0)  # Порядок в карусели

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
    description = db.Column(db.Text, nullable=True)  # НОВОЕ
    creator_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    avatar = db.Column(db.String(300), nullable=True)  # НОВОЕ
    is_private = db.Column(db.Boolean, default=False)  # НОВОЕ: Приватный клуб
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # НОВОЕ: Роли в группах
    roles = db.relationship('GroupRole', backref='group', cascade='all, delete-orphan')

# НОВОЕ: Роли в группах
class GroupRole(db.Model):
    __tablename__ = 'group_roles'
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('groups.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    role = db.Column(db.String(20), default='member')  # admin, moderator, editor, member
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)

# НОВОЕ: Заявки на вступление в приватные группы
class GroupJoinRequest(db.Model):
    __tablename__ = 'group_join_requests'
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('groups.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    message = db.Column(db.String(300), nullable=True)
    status = db.Column(db.String(20), default='pending')  # pending, approved, rejected
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
    is_edited = db.Column(db.Boolean, default=False)  # Отредактировано
    edited_at = db.Column(db.DateTime, nullable=True)
    is_deleted_for_sender = db.Column(db.Boolean, default=False)  # Удалено у меня
    is_deleted_for_all = db.Column(db.Boolean, default=False)  # Удалено у всех
    
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
    options = db.Column(db.Text, nullable=False)  # JSON строка с вариантами
    votes = db.Column(db.Text, default='{}')  # JSON строка с голосами

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
    is_edited = db.Column(db.Boolean, default=False)  # Отредактирован
    edited_at = db.Column(db.DateTime, nullable=True)
    comments_disabled = db.Column(db.Boolean, default=False)  # Комментарии отключены
    
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
    import re
    # Находим все слова, начинающиеся с #
    hashtags = re.findall(r'#(\w+)', text)
    return [tag.lower() for tag in hashtags]

# --- ФУНКЦИЯ ПАРСИНГА УПОМИНАНИЙ ---
def parse_mentions(text):
    """Извлекает упоминания @username из текста"""
    if not text:
        return []
    import re
    # Находим все слова, начинающиеся с @
    mentions = re.findall(r'@(\w+)', text)
    return mentions

# --- ФУНКЦИЯ ПОДСВЕТКИ ХЭШТЕГОВ И УПОМИНАНИЙ ---
def highlight_text(text):
    """Подсвечивает хэштеги и упоминания в тексте"""
    if not text:
        return text
    import re
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
    time_since_post = (datetime.utcnow() - post.timestamp).total_seconds() / 3600  # часы
    time_decay = 1 / (1 + time_since_post / 24)  # Уменьшается со временем
    
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

# =============================================================================
# РОУТЫ
# =============================================================================

@app.before_request
def before_request():
    """Выполняется перед каждым запросом"""
    # Обновляем статус онлайн
    if current_user.is_authenticated:
        update_user_online_status()
    
    # Очищаем устаревшие истории
    cleanup_expired_stories()

# --- ГЛАВНАЯ СТРАНИЦА (УМНАЯ ЛЕНТА) ---
@app.route('/')
@login_required
def index():
    # Получаем ID пользователей, на которых подписан текущий юзер
    following_ids = [f.following_id for f in current_user.following.all()]
    following_ids.append(current_user.id)  # Добавляем свои посты
    
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
    
    return render_template('profile.html', 
                         user=user, 
                         posts=posts, 
                         is_following=is_following,
                         followers_count=followers_count,
                         following_count=following_count,
                         stories=user_stories,
                         highlight_text=highlight_text)

@app.route('/follow/<int:user_id>')
@login_required
def follow(user_id):
    if user_id == current_user.id:
        return redirect(request.referrer)
    
    existing = Follow.query.filter_by(follower_id=current_user.id, following_id=user_id).first()
    if existing:
        db.session.delete(existing)
    else:
        db.session.add(Follow(follower_id=current_user.id, following_id=user_id))
        # Создаём уведомление
        create_notification(
            user_id=user_id,
            notification_type='follow',
            from_user_id=current_user.id,
            message=f"{current_user.username} подписался на вас"
        )
    
    db.session.commit()
    return redirect(request.referrer)

@app.route('/add_friend/<int:user_id>')
@login_required
def add_friend(user_id):
    existing = Friendship.query.filter(
        or_(
            and_(Friendship.sender_id == current_user.id, Friendship.receiver_id == user_id),
            and_(Friendship.sender_id == user_id, Friendship.receiver_id == current_user.id)
        )
    ).first()
    if not existing:
        db.session.add(Friendship(sender_id=current_user.id, receiver_id=user_id))
        db.session.commit()
    return redirect(request.referrer)

@app.route('/accept_friend/<int:friendship_id>')
@login_required
def accept_friend(friendship_id):
    friendship = db.session.get(Friendship, friendship_id)
    if friendship and friendship.receiver_id == current_user.id:
        friendship.status = 'accepted'
        db.session.commit()
    return redirect(url_for('index'))

@app.route('/friends')
@login_required
def friends():
    my_friends = Friendship.query.filter(
        or_(
            and_(Friendship.sender_id == current_user.id, Friendship.status == 'accepted'),
            and_(Friendship.receiver_id == current_user.id, Friendship.status == 'accepted')
        )
    ).all()
    
    pending_requests = Friendship.query.filter_by(receiver_id=current_user.id, status='pending').all()
    
    return render_template('friends.html', friends=my_friends, requests=pending_requests)

@app.route('/create_group', methods=['POST'])
@login_required
def create_group():
    name = request.form.get('name')
    description = request.form.get('description')
    is_private = request.form.get('is_private') == 'on'
    file = request.files.get('avatar')
    
    avatar_url = None
    if file and file.filename:
        avatar_url = upload_to_cloud(file, resource_type="image")
    
    if name:
        group = Group(
            name=name,
            description=description,
            creator_id=current_user.id,
            avatar=avatar_url,
            is_private=is_private
        )
        db.session.add(group)
        db.session.flush()
        
        # Создатель автоматически становится админом группы
        role = GroupRole(
            group_id=group.id,
            user_id=current_user.id,
            role='admin'
        )
        db.session.add(role)
        
        # Добавляем в members
        group.members.append(current_user)
        db.session.commit()
    
    return redirect(url_for('groups'))

@app.route('/groups')
@login_required
def groups():
    all_groups = Group.query.all()
    my_groups = current_user.groups
    return render_template('groups.html', groups=all_groups, my_groups=my_groups)

@app.route('/group/<int:group_id>')
@login_required
def group_detail(group_id):
    group = db.session.get(Group, group_id)
    if not group:
        abort(404)
    
    # Проверяем, является ли пользователь членом группы
    is_member = current_user in group.members
    
    # Если группа приватная и пользователь не член - показываем запрос на вступление
    if group.is_private and not is_member:
        join_request = GroupJoinRequest.query.filter_by(
            group_id=group_id,
            user_id=current_user.id,
            status='pending'
        ).first()
        return render_template('group_detail.html', group=group, is_member=False, join_request=join_request)
    
    messages = Message.query.filter_by(group_id=group_id).order_by(Message.timestamp).all()
    
    # Получаем роль пользователя
    user_role = GroupRole.query.filter_by(group_id=group_id, user_id=current_user.id).first()
    
    return render_template('group_detail.html', group=group, messages=messages, is_member=is_member, user_role=user_role)

@app.route('/join_group/<int:group_id>')
@login_required
def join_group(group_id):
    group = db.session.get(Group, group_id)
    
    if group:
        if group.is_private:
            # Отправляем заявку
            existing = GroupJoinRequest.query.filter_by(
                group_id=group_id,
                user_id=current_user.id
            ).first()
            
            if not existing:
                join_request = GroupJoinRequest(
                    group_id=group_id,
                    user_id=current_user.id,
                    message=request.args.get('message', '')
                )
                db.session.add(join_request)
                db.session.commit()
                flash("Заявка на вступление отправлена", "success")
        else:
            # Открытая группа - вступаем сразу
            if current_user not in group.members:
                group.members.append(current_user)
                
                # Добавляем роль member
                role = GroupRole(
                    group_id=group_id,
                    user_id=current_user.id,
                    role='member'
                )
                db.session.add(role)
                db.session.commit()
    
    return redirect(url_for('group_detail', group_id=group_id))

@app.route('/leave_group/<int:group_id>')
@login_required
def leave_group(group_id):
    group = db.session.get(Group, group_id)
    if group and current_user in group.members:
        group.members.remove(current_user)
        # Удаляем роль
        GroupRole.query.filter_by(group_id=group_id, user_id=current_user.id).delete()
        db.session.commit()
    return redirect(url_for('groups'))

@app.route('/send_group_message/<int:group_id>', methods=['POST'])
@login_required
def send_group_message(group_id):
    group = db.session.get(Group, group_id)
    if not group or current_user not in group.members:
        abort(403)
    
    body = request.form.get('body')
    
    # AI модерация
    is_ok, reason = moderate_content(body)
    
    if body and is_ok:
        msg = Message(sender_id=current_user.id, group_id=group_id, body=body, is_delivered=True)
        db.session.add(msg)
        db.session.commit()
    elif not is_ok:
        flash(f"Сообщение заблокировано: {reason}", "warning")
    
    return redirect(url_for('group_detail', group_id=group_id))

@app.route('/chat/<int:user_id>')
@login_required
def chat(user_id):
    other_user = db.session.get(User, user_id)
    if not other_user:
        abort(404)
    
    messages = Message.query.filter(
        or_(
            and_(Message.sender_id == current_user.id, Message.recipient_id == user_id),
            and_(Message.sender_id == user_id, Message.recipient_id == current_user.id)
        ),
        Message.is_deleted_for_all == False
    ).order_by(Message.timestamp).all()
    
    # Отмечаем сообщения как прочитанные
    for msg in messages:
        if msg.recipient_id == current_user.id and not msg.is_read:
            msg.is_read = True
    db.session.commit()
    
    return render_template('chat.html', other_user=other_user, messages=messages)

@app.route('/send_message/<int:user_id>', methods=['POST'])
@login_required
def send_message(user_id):
    body = request.form.get('body')
    
    # AI модерация
    is_ok, reason = moderate_content(body)
    
    if body and is_ok:
        msg = Message(sender_id=current_user.id, recipient_id=user_id, body=body, is_delivered=True)
        db.session.add(msg)
        db.session.commit()
    elif not is_ok:
        flash(f"Сообщение заблокировано: {reason}", "warning")
    
    return redirect(url_for('chat', user_id=user_id))

@app.route('/upload_voice/<int:recipient_id>', methods=['POST'])
@login_required
def upload_voice(recipient_id):
    file = request.files.get('voice')
    if file and file.filename != '':
        url = upload_to_cloud(file, resource_type="video")
        if url:
            db.session.add(Message(voice_filename=url, sender_id=current_user.id, recipient_id=recipient_id, is_delivered=True))
            db.session.commit()
            return jsonify({'success': True})
    return jsonify({'error': 'No file'}), 400

@app.route('/upload_voice_comment/<int:post_id>', methods=['POST'])
@login_required
def upload_voice_comment(post_id):
    file = request.files.get('voice')
    if file and file.filename != '':
        url = upload_to_cloud(file, resource_type="video")
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
    color_scheme = request.form.get('color_scheme')
    
    avatar_file = request.files.get('avatar')
    banner_file = request.files.get('banner')
    
    if avatar_file and avatar_file.filename != '':
        url = upload_to_cloud(avatar_file, resource_type="image")
        if url: 
            current_user.avatar = url
    
    if banner_file and banner_file.filename != '':
        url = upload_to_cloud(banner_file, resource_type="image")
        if url:
            current_user.banner = url
            
    if bio: 
        current_user.bio = bio
    
    if theme and theme in ['light', 'dark']: 
        current_user.theme = theme
    
    if color_scheme and color_scheme in ['blue', 'purple', 'orange', 'green']:
        current_user.color_scheme = color_scheme
    
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
    files = request.files.getlist('media[]')  # НОВОЕ: Поддержка множественных файлов
    
    # AI модерация контента
    is_ok, reason = moderate_content(content)
    
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
    
    # Создаём пост
    if content or files or poll_data:
        post = Post(
            content=content,
            author=current_user,
            is_moderated=is_ok,
            moderation_reason=reason if not is_ok else None
        )
        db.session.add(post)
        db.session.flush()
        
        # НОВОЕ: Обрабатываем множественные файлы для карусели
        if files:
            for idx, file in enumerate(files):
                if file and file.filename != '':
                    ext = file.filename.rsplit('.', 1)[1].lower()
                    if ext in ['mp4', 'webm', 'mov']:
                        media_url = upload_to_cloud(file, resource_type="video")
                        media_type = 'video'
                    else:
                        media_url = upload_to_cloud(file, resource_type="image")
                        media_type = 'image'
                    
                    if media_url:
                        media_item = PostMedia(
                            post_id=post.id,
                            media_url=media_url,
                            media_type=media_type,
                            order=idx
                        )
                        db.session.add(media_item)
        
        # Создаём опрос если есть
        if poll_data:
            poll = Poll(
                post_id=post.id,
                question=poll_data['question'],
                options=json.dumps(poll_data['options']),
                votes=json.dumps({})
            )
            db.session.add(poll)
        
        # НОВОЕ: Парсим хэштеги
        if content:
            hashtags = parse_hashtags(content)
            for tag in hashtags:
                hashtag = Hashtag.query.filter_by(tag=tag).first()
                if not hashtag:
                    hashtag = Hashtag(tag=tag, usage_count=0)
                    db.session.add(hashtag)
                    db.session.flush()
                
                hashtag.usage_count += 1
                db.session.add(PostHashtag(post_id=post.id, hashtag_id=hashtag.id))
            
            # НОВОЕ: Парсим упоминания
            mentions = parse_mentions(content)
            for username in mentions:
                mentioned_user = User.query.filter_by(username=username).first()
                if mentioned_user:
                    mention = Mention(
                        post_id=post.id,
                        mentioned_user_id=mentioned_user.id,
                        mentioner_user_id=current_user.id
                    )
                    db.session.add(mention)
                    
                    # Создаём уведомление
                    create_notification(
                        user_id=mentioned_user.id,
                        notification_type='mention',
                        from_user_id=current_user.id,
                        post_id=post.id,
                        message=f"{current_user.username} упомянул вас в посте"
                    )
        
        db.session.commit()
        
        if not is_ok:
            flash(f"⚠️ Ваш пост заблокирован модерацией: {reason}", "warning")
        else:
            flash("Пост создан!", "success")
    
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
    
    if existing:
        db.session.delete(existing)
    else:
        db.session.add(Like(user_id=current_user.id, post_id=post_id))
        
        # Создаём уведомление автору поста
        post = Post.query.get(post_id)
        if post and post.user_id != current_user.id:
            create_notification(
                user_id=post.user_id,
                notification_type='like',
                from_user_id=current_user.id,
                post_id=post_id,
                message=f"{current_user.username} лайкнул ваш пост"
            )
    
    db.session.commit()
    return redirect(request.referrer)

@app.route('/add_comment/<int:post_id>', methods=['POST'])
@login_required
def add_comment(post_id):
    post = Post.query.get(post_id)
    
    # Проверяем, отключены ли комментарии
    if post and post.comments_disabled:
        flash("Комментарии к этому посту отключены", "warning")
        return redirect(url_for('index'))
    
    text = request.form.get('text')
    
    # AI модерация комментариев
    is_ok, reason = moderate_content(text)
    
    if text and is_ok:
        db.session.add(Comment(text=text, user_id=current_user.id, post_id=post_id))
        
        # Создаём уведомление автору поста
        if post and post.user_id != current_user.id:
            create_notification(
                user_id=post.user_id,
                notification_type='comment',
                from_user_id=current_user.id,
                post_id=post_id,
                message=f"{current_user.username} прокомментировал ваш пост"
            )
        
        # НОВОЕ: Парсим упоминания в комментариях
        mentions = parse_mentions(text)
        for username in mentions:
            mentioned_user = User.query.filter_by(username=username).first()
            if mentioned_user:
                comment = Comment(text=text, user_id=current_user.id, post_id=post_id)
                db.session.add(comment)
                db.session.flush()
                
                mention = Mention(
                    comment_id=comment.id,
                    mentioned_user_id=mentioned_user.id,
                    mentioner_user_id=current_user.id
                )
                db.session.add(mention)
                
                # Уведомление
                create_notification(
                    user_id=mentioned_user.id,
                    notification_type='mention',
                    from_user_id=current_user.id,
                    post_id=post_id,
                    message=f"{current_user.username} упомянул вас в комментарии"
                )
        
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

@app.route('/vote_poll/<int:poll_id>/<int:option_index>', methods=['POST'])
@login_required
def vote_poll(poll_id, option_index):
    poll = Poll.query.get_or_404(poll_id)
    
    # Проверяем, голосовал ли уже
    existing_vote = PollVote.query.filter_by(poll_id=poll_id, user_id=current_user.id).first()
    
    if existing_vote:
        flash("Вы уже голосовали в этом опросе", "warning")
    else:
        # Добавляем голос
        vote = PollVote(poll_id=poll_id, user_id=current_user.id, option_index=option_index)
        db.session.add(vote)
        
        # Обновляем счётчик голосов
        votes = json.loads(poll.votes) if poll.votes else {}
        votes[str(option_index)] = votes.get(str(option_index), 0) + 1
        poll.votes = json.dumps(votes)
        
        db.session.commit()
        flash("Ваш голос учтён!", "success")
    
    return redirect(request.referrer or url_for('index'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        # НОВОЕ: Проверка капчи
        captcha_input = request.form.get('captcha')
        captcha_answer = session.get('captcha')
        
        if captcha_input != captcha_answer:
            flash("Неверная капча", "danger")
            return redirect(url_for('register'))
        
        email = request.form.get('email')
        username = request.form.get('username')
        password = request.form.get('password')
        
        if User.query.filter_by(email=email).first():
            flash("Email уже зарегистрирован", "danger")
            return redirect(url_for('register'))
        
        if User.query.filter_by(username=username).first():
            flash("Имя пользователя занято", "danger")
            return redirect(url_for('register'))
        
        new_user = User(
            email=email,
            username=username,
            password=generate_password_hash(password)
        )
        db.session.add(new_user)
        db.session.commit()
        
        login_user(new_user)
        
        # Создаём сеанс
        session_token = str(uuid.uuid4())
        user_session = UserSession(
            user_id=new_user.id,
            session_token=session_token,
            device_info=request.user_agent.string,
            ip_address=request.remote_addr
        )
        db.session.add(user_session)
        
        # Добавляем в историю входов
        login_history = LoginHistory(
            user_id=new_user.id,
            ip_address=request.remote_addr,
            device_info=request.user_agent.string,
            success=True
        )
        db.session.add(login_history)
        db.session.commit()
        
        return redirect(url_for('index'))
    
    # Генерируем капчу
    captcha = generate_captcha()
    session['captcha'] = captcha
    
    return render_template('auth.html', title="Регистрация", is_login=False, captcha=captcha)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # НОВОЕ: Проверка капчи
        captcha_input = request.form.get('captcha')
        captcha_answer = session.get('captcha')
        
        if captcha_input != captcha_answer:
            flash("Неверная капча", "danger")
            return redirect(url_for('login'))
        
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password, password):
            if user.is_banned:
                flash("Вы забанены.", "danger")
                
                # Добавляем неудачный вход в историю
                login_history = LoginHistory(
                    user_id=user.id,
                    ip_address=request.remote_addr,
                    device_info=request.user_agent.string,
                    success=False
                )
                db.session.add(login_history)
                db.session.commit()
            else:
                login_user(user)
                
                # Создаём новый сеанс
                session_token = str(uuid.uuid4())
                user_session = UserSession(
                    user_id=user.id,
                    session_token=session_token,
                    device_info=request.user_agent.string,
                    ip_address=request.remote_addr
                )
                db.session.add(user_session)
                
                # Добавляем успешный вход в историю
                login_history = LoginHistory(
                    user_id=user.id,
                    ip_address=request.remote_addr,
                    device_info=request.user_agent.string,
                    success=True
                )
                db.session.add(login_history)
                db.session.commit()
                
                return redirect(url_for('index'))
        else:
            flash("Неверное имя пользователя или пароль", "danger")
    
    # Генерируем капчу
    captcha = generate_captcha()
    session['captcha'] = captcha
    
    return render_template('auth.html', title="Вход", is_login=True, captcha=captcha)

@app.route('/logout')
@login_required
def logout():
    # Деактивируем текущий сеанс
    current_session = UserSession.query.filter_by(
        user_id=current_user.id,
        is_active=True
    ).order_by(UserSession.last_activity.desc()).first()
    
    if current_session:
        current_session.is_active = False
        db.session.commit()
    
    # Обновляем статус онлайн
    current_user.is_online = False
    db.session.commit()
    
    logout_user()
    return redirect(url_for('login'))

# --- СОЗДАНИЕ ТАБЛИЦ И АВТОМАТИЧЕСКОЕ ДОБАВЛЕНИЕ КОЛОНОК ---
with app.app_context():
    db.create_all()
    
    # --- АВТОМАТИЧЕСКОЕ ДОБАВЛЕНИЕ НОВЫХ КОЛОНОК БЕЗ УДАЛЕНИЯ БАЗЫ ---
    try:
        with db.engine.connect() as conn:
            # Добавляем колонки в таблицу users
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS banner VARCHAR(300);"))
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS color_scheme VARCHAR(20) DEFAULT 'blue';"))
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_online BOOLEAN DEFAULT FALSE;"))
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP;"))
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_typing BOOLEAN DEFAULT FALSE;"))
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS typing_in_chat INTEGER;"))
            
            # Добавляем колонки в таблицу posts
            conn.execute(text("ALTER TABLE posts ADD COLUMN IF NOT EXISTS is_moderated BOOLEAN DEFAULT TRUE;"))
            conn.execute(text("ALTER TABLE posts ADD COLUMN IF NOT EXISTS moderation_reason VARCHAR(200);"))
            conn.execute(text("ALTER TABLE posts ADD COLUMN IF NOT EXISTS is_edited BOOLEAN DEFAULT FALSE;"))
            conn.execute(text("ALTER TABLE posts ADD COLUMN IF NOT EXISTS edited_at TIMESTAMP;"))
            conn.execute(text("ALTER TABLE posts ADD COLUMN IF NOT EXISTS comments_disabled BOOLEAN DEFAULT FALSE;"))
            conn.execute(text("ALTER TABLE posts ADD COLUMN IF NOT EXISTS collab_user_id INTEGER;"))
            conn.execute(text("ALTER TABLE posts ADD COLUMN IF NOT EXISTS engagement_score FLOAT DEFAULT 0.0;"))
            
            # Добавляем колонки в таблицу messages
            conn.execute(text("ALTER TABLE messages ADD COLUMN IF NOT EXISTS is_read BOOLEAN DEFAULT FALSE;"))
            conn.execute(text("ALTER TABLE messages ADD COLUMN IF NOT EXISTS is_delivered BOOLEAN DEFAULT FALSE;"))
            conn.execute(text("ALTER TABLE messages ADD COLUMN IF NOT EXISTS is_edited BOOLEAN DEFAULT FALSE;"))
            conn.execute(text("ALTER TABLE messages ADD COLUMN IF NOT EXISTS edited_at TIMESTAMP;"))
            conn.execute(text("ALTER TABLE messages ADD COLUMN IF NOT EXISTS is_deleted_for_sender BOOLEAN DEFAULT FALSE;"))
            conn.execute(text("ALTER TABLE messages ADD COLUMN IF NOT EXISTS is_deleted_for_all BOOLEAN DEFAULT FALSE;"))
            
            # Добавляем колонки в таблицу groups
            conn.execute(text("ALTER TABLE groups ADD COLUMN IF NOT EXISTS description TEXT;"))
            conn.execute(text("ALTER TABLE groups ADD COLUMN IF NOT EXISTS avatar VARCHAR(300);"))
            conn.execute(text("ALTER TABLE groups ADD COLUMN IF NOT EXISTS is_private BOOLEAN DEFAULT FALSE;"))
            conn.execute(text("ALTER TABLE groups ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;"))
            
            conn.commit()
            print(">>> УСПЕШНО: Все новые колонки добавлены в базу данных! <<<")
    except Exception as e:
        print(f">>> INFO (это нормально если таблицы уже существуют): {e}")
    
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
            theme='dark',
            color_scheme='blue'
        )
        db.session.add(admin)
        db.session.commit()
        print("Админ создан: admin / 12we1qtr11")

if __name__ == '__main__':
    # Для Render важно использовать host='0.0.0.0' и порт из окружения
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
