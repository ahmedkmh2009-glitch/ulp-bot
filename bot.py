"""
ULP Searcher Bot - VERSIÓN FLASK 24/7 COMPLETA
Todos los comandos + Upload funcionando + Webhook
"""

import os
import logging
import sqlite3
import threading
import io
import zipfile
import re
import uuid
import asyncio
from datetime import datetime, time
from typing import Dict, List, Optional, Tuple
import glob

from flask import Flask, request, jsonify
from telegram import Update, Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, 
    ContextTypes, CallbackQueryHandler
)

# ============================================================================
# CONFIGURACIÓN
# ============================================================================

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
ADMIN_IDS = [int(id.strip()) for id in os.getenv('ADMIN_IDS', '').split(',') if id.strip()]
BOT_OWNER = "@iberic_owner"
BOT_SUPPORT = "@iberic_owner"
BOT_NAME = "🔍 ULP Searcher Bot"
BOT_VERSION = "17.0 FLASK-FINAL"
MAX_FREE_CREDITS = 2
REFERRAL_CREDITS = 1
RESET_HOUR = 0

PORT = int(os.getenv('PORT', 10000))

# Obtener URL de Render
RENDER_EXTERNAL_URL = os.getenv('RENDER_EXTERNAL_URL')
if not RENDER_EXTERNAL_URL:
    RENDER_EXTERNAL_URL = f"https://localhost:{PORT}"

WEBHOOK_URL = f"{RENDER_EXTERNAL_URL}/webhook"

# Directorios
BASE_DIR = "bot_data"
DATA_DIR = os.path.join(BASE_DIR, "ulp_files")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
DB_PATH = os.path.join(BASE_DIR, "bot.db")

for directory in [BASE_DIR, DATA_DIR, UPLOAD_DIR]:
    os.makedirs(directory, exist_ok=True)
    print(f"📁 Directorio creado: {directory}")

# ============================================================================
# LOGGING
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(BASE_DIR, 'bot.log'), encoding='utf-8', mode='a')
    ]
)
logger = logging.getLogger(__name__)

print("="*60)
print(f"🚀 Iniciando {BOT_NAME} v{BOT_VERSION}")
print(f"👑 Owner: {BOT_OWNER}")
print(f"🌐 Webhook URL: {WEBHOOK_URL}")
print(f"📁 Directorio datos: {DATA_DIR}")
print(f"📤 Directorio uploads: {UPLOAD_DIR}")
print("="*60)

# ============================================================================
# FLASK APP
# ============================================================================

app = Flask(__name__)

# Variables globales
telegram_app = None
bot_instance = None
search_engine = None
credit_system = None

# ============================================================================
# ENDPOINTS DE FLASK
# ============================================================================

@app.route('/')
def home():
    return jsonify({
        "status": "online",
        "bot": BOT_NAME,
        "version": BOT_VERSION,
        "webhook": WEBHOOK_URL,
        "files": len(search_engine.data_files) if search_engine else 0
    })

@app.route('/health')
def health():
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    })

@app.route('/webhook', methods=['POST'])
async def webhook():
    """Endpoint para recibir updates de Telegram"""
    global telegram_app
    
    if telegram_app is None:
        logger.error("❌ Telegram app no inicializada")
        return jsonify({"error": "Bot not initialized"}), 503
    
    try:
        update = Update.de_json(request.get_json(force=True), telegram_app.bot)
        await telegram_app.process_update(update)
        return jsonify({"status": "ok"})
    except Exception as e:
        logger.error(f"❌ Webhook error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/setup-webhook', methods=['GET', 'POST'])
def setup_webhook():
    """Configurar webhook manualmente"""
    try:
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        
        # Eliminar webhook anterior
        bot.delete_webhook(drop_pending_updates=True)
        logger.info("✅ Webhook anterior eliminado")
        
        # Configurar nuevo webhook
        bot.set_webhook(
            url=WEBHOOK_URL,
            allowed_updates=["message", "callback_query"],
            drop_pending_updates=True,
            max_connections=1
        )
        
        webhook_info = bot.get_webhook_info()
        logger.info(f"✅ Webhook configurado: {webhook_info.url}")
        
        return jsonify({
            "status": "success",
            "webhook_url": webhook_info.url,
            "pending_updates": webhook_info.pending_update_count
        })
    except Exception as e:
        logger.error(f"❌ Setup webhook error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/stats')
def stats():
    """Endpoint para ver estadísticas"""
    if search_engine:
        stats = search_engine.get_stats()
        return jsonify(stats)
    return jsonify({"error": "No data"})

# ============================================================================
# SEARCH ENGINE - COMPLETO
# ============================================================================

class SearchEngine:
    def __init__(self, data_dir: str = DATA_DIR):
        self.data_dir = data_dir
        self.data_files = []
        self.load_all_data()
    
    def load_all_data(self):
        """Cargar todos los archivos .txt"""
        self.data_files = glob.glob(os.path.join(self.data_dir, "*.txt"))
        logger.info(f"📂 Cargados {len(self.data_files)} archivos")
        return len(self.data_files)
    
    def search_all_formats(self, query: str) -> Tuple[int, List[str]]:
        """Buscar query - devuelve TODAS las líneas (SIN LÍMITE)"""
        results = []
        query_lower = query.lower()
        
        for file_path in self.data_files:
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        
                        if query_lower in line.lower():
                            results.append(line)
            except Exception as e:
                logger.error(f"Error en {file_path}: {e}")
                continue
        
        logger.info(f"🔍 Encontrados {len(results):,} resultados para '{query}'")
        return len(results), results
    
    def search_clean_email_pass_no_url(self, query: str) -> Tuple[int, List[str]]:
        """Buscar y devolver SOLO email:pass (SIN URLs)"""
        results = []
        search_term = query.lower().strip()
        
        if search_term.startswith('@'):
            search_term = search_term[1:]
        
        for file_path in self.data_files:
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        
                        line_lower = line.lower()
                        
                        if search_term in line_lower:
                            clean_pairs = self.extract_clean_email_pass_no_url(line)
                            
                            for email, password in clean_pairs:
                                email_lower = email.lower()
                                if (search_term in email_lower or 
                                    f"@{search_term}" in email_lower):
                                    if email and password:
                                        results.append(f"{email}:{password}")
            except Exception as e:
                logger.error(f"Error en {file_path}: {e}")
                continue
        
        # Eliminar duplicados
        unique_results = []
        seen = set()
        for result in results:
            if result not in seen:
                seen.add(result)
                unique_results.append(result)
        
        logger.info(f"📧 Encontrados {len(unique_results):,} email:pass para '{query}'")
        return len(unique_results), unique_results
    
    def extract_clean_email_pass_no_url(self, line: str) -> List[Tuple[str, str]]:
        """Extraer pares email:password LIMPIOS (SIN URLs)"""
        pairs = []
        
        # Eliminar URLs
        line_clean = re.sub(r'https?://[^\s]+', '', line, flags=re.IGNORECASE)
        line_clean = re.sub(r'ftp://[^\s]+', '', line_clean, flags=re.IGNORECASE)
        line_clean = re.sub(r'www\.[^\s]+', '', line_clean, flags=re.IGNORECASE)
        
        # Buscar emails
        email_pattern = r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'
        emails = re.findall(email_pattern, line_clean, re.IGNORECASE)
        
        for email in emails:
            email_start = line.find(email)
            if email_start == -1:
                continue
                
            after_email = line[email_start + len(email):]
            password_match = re.search(r'^[^:|\s]*[:|\s]+([^\s]+)', after_email)
            
            if password_match:
                password = password_match.group(1)
                if not password.startswith('http'):
                    pairs.append((email, password))
            else:
                parts = re.split(r'[:|;\s]', after_email, 1)
                if len(parts) > 1 and parts[1].strip():
                    password = parts[1].strip()
                    if not password.startswith('http'):
                        pairs.append((email, password))
        
        return pairs
    
    def search_email_only(self, email: str) -> Tuple[int, List[str]]:
        """Buscar SOLO direcciones de email"""
        results = []
        email_lower = email.lower().strip()
        
        for file_path in self.data_files:
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        
                        emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', line, re.IGNORECASE)
                        
                        for found_email in emails:
                            if email_lower in found_email.lower():
                                results.append(found_email)
            except Exception as e:
                logger.error(f"Error en {file_path}: {e}")
                continue
        
        unique_results = list(set(results))
        return len(unique_results), unique_results
    
    def search_login(self, login: str) -> Tuple[int, List[str]]:
        """Buscar por login/username"""
        results = []
        login_lower = login.lower().strip()
        
        for file_path in self.data_files:
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        
                        parts = re.split(r'[:|;]', line)
                        if len(parts) >= 2:
                            username = parts[0].strip()
                            password = parts[1].strip()
                            
                            if (login_lower in username.lower() and 
                                '@' not in username and 
                                '://' not in username and
                                password):
                                results.append(f"{username}:{password}")
            except Exception as e:
                logger.error(f"Error en {file_path}: {e}")
                continue
        
        return len(results), results
    
    def search_password(self, password: str) -> Tuple[int, List[str]]:
        """Buscar por contraseña"""
        results = []
        pass_lower = password.lower().strip()
        
        for file_path in self.data_files:
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        
                        parts = re.split(r'[:|;]', line)
                        if len(parts) >= 2:
                            username = parts[0].strip()
                            found_password = parts[1].strip()
                            
                            if pass_lower in found_password.lower():
                                results.append(f"{username}:{found_password}")
            except Exception as e:
                logger.error(f"Error en {file_path}: {e}")
                continue
        
        return len(results), results
    
    def search_dni_domain_only_dni_pass(self, domain: str) -> Tuple[int, List[str]]:
        """Buscar SOLO DNI:password para un dominio"""
        results = []
        domain_lower = domain.lower().strip()
        
        if domain_lower.startswith('@'):
            domain_lower = domain_lower[1:]
        
        dni_pass_pattern = r'(\b\d{7,8}[A-Za-z]?\b)\s*[:|;]\s*([^\s]+)'
        
        for file_path in self.data_files:
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        
                        line_lower = line.lower()
                        
                        if domain_lower in line_lower:
                            matches = re.findall(dni_pass_pattern, line, re.IGNORECASE)
                            for dni, password in matches:
                                if '@' not in dni and '@' not in password:
                                    results.append(f"{dni.upper()}:{password}")
            except Exception as e:
                logger.error(f"Error en {file_path}: {e}")
                continue
        
        unique_results = list(set(results))
        return len(unique_results), unique_results
    
    def get_stats(self) -> Dict:
        """Obtener estadísticas de la base de datos"""
        total_lines = 0
        total_size = 0
        
        for file_path in self.data_files:
            try:
                size = os.path.getsize(file_path)
                total_size += size
                
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    total_lines += sum(1 for _ in f)
            except:
                pass
        
        return {
            "total_files": len(self.data_files),
            "total_lines": total_lines,
            "total_size_mb": total_size / (1024 * 1024)
        }
    
    def add_data_file(self, file_path: str) -> Tuple[bool, str]:
        """Añadir archivo a la base de datos - CORREGIDO"""
        try:
            import shutil
            
            # Verificar que el archivo existe
            if not os.path.exists(file_path):
                logger.error(f"❌ Archivo no encontrado: {file_path}")
                return False, "File not found"
            
            filename = os.path.basename(file_path)
            dest_path = os.path.join(self.data_dir, filename)
            
            # Si ya existe, agregar timestamp
            if os.path.exists(dest_path):
                name, ext = os.path.splitext(filename)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                dest_path = os.path.join(self.data_dir, f"{name}_{timestamp}{ext}")
            
            # Copiar archivo
            shutil.copy2(file_path, dest_path)
            logger.info(f"✅ Archivo copiado a: {dest_path}")
            
            # Verificar que se copió correctamente
            if not os.path.exists(dest_path):
                return False, "File copy failed"
            
            # Recargar datos
            self.load_all_data()
            
            return True, os.path.basename(dest_path)
            
        except Exception as e:
            logger.error(f"❌ Error añadiendo archivo: {e}")
            return False, str(e)

# ============================================================================
# CREDIT SYSTEM - COMPLETO
# ============================================================================

class CreditSystem:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.init_database()
        logger.info("✅ Base de datos inicializada")
    
    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_database(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    daily_credits INTEGER DEFAULT 2,
                    extra_credits INTEGER DEFAULT 0,
                    total_searches INTEGER DEFAULT 0,
                    referrals INTEGER DEFAULT 0,
                    referral_code TEXT UNIQUE,
                    referred_by INTEGER,
                    join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_reset DATE DEFAULT CURRENT_DATE
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    amount INTEGER,
                    type TEXT,
                    description TEXT,
                    date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()
    
    def get_or_create_user(self, user_id: int, username: str = "", first_name: str = "", referred_by: int = None):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
            user = cursor.fetchone()
            
            if user:
                return dict(user)
            
            referral_code = str(uuid.uuid4())[:8].upper()
            
            cursor.execute('''
                INSERT INTO users (user_id, username, first_name, daily_credits, referral_code, referred_by)
                VALUES (?, ?, ?, 2, ?, ?)
            ''', (user_id, username, first_name, referral_code, referred_by))
            
            cursor.execute('''
                INSERT INTO transactions (user_id, amount, type, description)
                VALUES (?, ?, ?, ?)
            ''', (user_id, 2, 'welcome', '2 free welcome credits'))
            
            if referred_by:
                cursor.execute('''
                    UPDATE users 
                    SET referrals = referrals + 1,
                        extra_credits = extra_credits + 1
                    WHERE user_id = ?
                ''', (referred_by,))
                
                cursor.execute('''
                    INSERT INTO transactions (user_id, amount, type, description)
                    VALUES (?, ?, ?, ?)
                ''', (referred_by, 1, 'referral', f'Referral credit for user {user_id}'))
            
            conn.commit()
            
            return {
                'user_id': user_id,
                'username': username,
                'first_name': first_name,
                'daily_credits': 2,
                'extra_credits': 0,
                'referral_code': referral_code,
                'referred_by': referred_by
            }
    
    def get_user_credits(self, user_id: int) -> int:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT daily_credits, extra_credits FROM users WHERE user_id = ?', (user_id,))
            result = cursor.fetchone()
            
            if result:
                return result['daily_credits'] + result['extra_credits']
            return 0
    
    def get_daily_credits_left(self, user_id: int) -> int:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT daily_credits FROM users WHERE user_id = ?', (user_id,))
            result = cursor.fetchone()
            return result['daily_credits'] if result else 0
    
    def has_enough_credits(self, user_id: int) -> bool:
        return self.get_user_credits(user_id) > 0
    
    def use_credits(self, user_id: int, search_type: str, query: str, results_count: int = 0):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('SELECT daily_credits, extra_credits FROM users WHERE user_id = ?', (user_id,))
            result = cursor.fetchone()
            
            if not result:
                return False
            
            daily_credits = result['daily_credits']
            extra_credits = result['extra_credits']
            
            if daily_credits > 0:
                new_daily = daily_credits - 1
                new_extra = extra_credits
                credit_type = "daily"
            elif extra_credits > 0:
                new_daily = 0
                new_extra = extra_credits - 1
                credit_type = "extra"
            else:
                return False
            
            cursor.execute('''
                UPDATE users 
                SET daily_credits = ?,
                    extra_credits = ?,
                    total_searches = total_searches + 1
                WHERE user_id = ?
            ''', (new_daily, new_extra, user_id))
            
            cursor.execute('''
                INSERT INTO transactions 
                (user_id, amount, type, description)
                VALUES (?, ?, ?, ?)
            ''', (user_id, -1, 'search_used', f'{search_type}: {query} ({credit_type})'))
            
            conn.commit()
            return True
    
    def get_user_info(self, user_id: int):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
            result = cursor.fetchone()
            return dict(result) if result else None
    
    def get_referral_info(self, user_id: int):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('SELECT referral_code FROM users WHERE user_id = ?', (user_id,))
            result = cursor.fetchone()
            
            if not result:
                return None
            
            referral_code = result['referral_code']
            
            cursor.execute('SELECT COUNT(*) as count FROM users WHERE referred_by = ?', (user_id,))
            referrals_count = cursor.fetchone()['count']
            
            return {
                'referral_code': referral_code,
                'referrals_count': referrals_count,
                'referral_link': f"https://t.me/{(BOT_NAME.replace('🔍', '').replace(' ', ''))}?start={referral_code}"
            }
    
    def add_credits_to_user(self, user_id: int, amount: int, admin_id: int, credit_type: str = 'extra') -> Tuple[bool, str]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('SELECT user_id FROM users WHERE user_id = ?', (user_id,))
            result = cursor.fetchone()
            
            if not result:
                return False, "User not found"
            
            if credit_type == 'extra':
                cursor.execute('UPDATE users SET extra_credits = extra_credits + ? WHERE user_id = ?', (amount, user_id))
            else:
                cursor.execute('UPDATE users SET daily_credits = daily_credits + ? WHERE user_id = ?', (amount, user_id))
            
            cursor.execute('''
                INSERT INTO transactions 
                (user_id, amount, type, description)
                VALUES (?, ?, ?, ?)
            ''', (user_id, amount, f'admin_add_{credit_type}', f'{credit_type} credits added by admin {admin_id}'))
            
            conn.commit()
            return True, f"✅ {amount} {credit_type} credits added"
    
    def get_all_users(self, limit: int = 50):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users ORDER BY join_date DESC LIMIT ?', (limit,))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_bot_stats(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            stats = {}
            cursor.execute('SELECT COUNT(*) as count FROM users')
            stats['total_users'] = cursor.fetchone()['count']
            
            cursor.execute('SELECT COUNT(*) as count FROM transactions WHERE type = "search_used"')
            stats['total_searches'] = cursor.fetchone()['count']
            
            cursor.execute('SELECT SUM(daily_credits + extra_credits) as total FROM users')
            stats['total_credits'] = cursor.fetchone()['total'] or 0
            
            return stats
    
    def get_user_by_username(self, username: str):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
            result = cursor.fetchone()
            return dict(result) if result else None

# ============================================================================
# BOT PRINCIPAL - TODOS LOS COMANDOS
# ============================================================================

class ULPBot:
    def __init__(self, search_engine: SearchEngine, credit_system: CreditSystem):
        self.search_engine = search_engine
        self.credit_system = credit_system
    
    def escape_html(self, text: str) -> str:
        if not text:
            return ""
        text = str(text)
        text = text.replace('&', '&amp;')
        text = text.replace('<', '&lt;')
        text = text.replace('>', '&gt;')
        return text
    
    # ============================================================================
    # START COMMAND
    # ============================================================================
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        args = context.args
        
        referred_by = None
        if args and len(args) > 0:
            referral_code = args[0]
            with self.credit_system.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT user_id FROM users WHERE referral_code = ?', (referral_code,))
                result = cursor.fetchone()
                if result:
                    referred_by = result['user_id']
        
        user_info = self.credit_system.get_or_create_user(
            user_id=user.id,
            username=user.username or "",
            first_name=user.first_name or "",
            referred_by=referred_by
        )
        
        total_credits = self.credit_system.get_user_credits(user.id)
        daily_credits = self.credit_system.get_daily_credits_left(user.id)
        extra_credits = total_credits - daily_credits
        stats = self.search_engine.get_stats()
        
        welcome_msg = ""
        if referred_by:
            welcome_msg = "\n🎉 You joined using a referral link! +1 credit for your friend!"
        
        keyboard = [
            [InlineKeyboardButton("🔍 /search - Search Domain", callback_data="start_search")],
            [InlineKeyboardButton("💰 My Credits", callback_data="menu_credits")],
            [InlineKeyboardButton("📋 Help", callback_data="menu_help")],
        ]
        
        if user.id in ADMIN_IDS:
            keyboard.append([InlineKeyboardButton("👑 Admin", callback_data="menu_admin")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message = (
            f"<b>🔍 {BOT_NAME}</b>\n"
            f"<i>Version: {BOT_VERSION}</i>\n\n"
            f"Welcome <b>{self.escape_html(user.first_name)}</b>!{welcome_msg}\n\n"
            f"<b>Your Credits:</b>\n"
            f"• Daily: {daily_credits}/2 (reset at midnight UTC)\n"
            f"• Extra: {extra_credits}\n"
            f"• Total: {total_credits}\n\n"
            f"<b>Database Stats:</b>\n"
            f"• Files: {stats['total_files']:,}\n"
            f"• Lines: {stats['total_lines']:,}\n"
            f"• Size: {stats['total_size_mb']:,.1f} MB\n\n"
            f"<b>⚠️ IMPORTANT:</b>\n"
            f"• <b>ALL</b> results in ONE file\n"
            f"• <b>NO LIMIT</b> on results\n"
            f"• Email:Pass format = <b>NO URLs</b>\n\n"
            f"Use <b>/search</b> to start!"
        )
        
        await update.message.reply_html(message, reply_markup=reply_markup)
    
    # ============================================================================
    # SEARCH COMMANDS
    # ============================================================================
    
    async def search_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        
        if not context.args:
            await update.message.reply_html(
                "🔍 <b>Search Command</b>\n\n"
                "Usage: <code>/search [query]</code>\n\n"
                "<i>Examples:</i>\n"
                "<code>/search google.com</code>\n"
                "<code>/search user@gmail.com</code>\n"
                "<code>/search @hotmail.com</code>\n\n"
                "Then choose format!\n\n"
                "<b>📁 ALL RESULTS IN ONE FILE - NO LIMITS</b>"
            )
            return
        
        query = ' '.join(context.args)
        
        keyboard = [
            [
                InlineKeyboardButton("📧 Email:Pass Only", callback_data=f"format_clean:{query}"),
                InlineKeyboardButton("🌐 Full Lines", callback_data=f"format_full:{query}")
            ],
            [InlineKeyboardButton("❌ Cancel", callback_data="cancel_search")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_html(
            f"🔍 <b>Search Query:</b> <code>{self.escape_html(query)}</code>\n\n"
            f"<b>Choose format:</b>\n"
            f"1. <b>Email:Pass Only</b> - Clean format (NO URLs)\n"
            f"2. <b>Full Lines</b> - Complete lines with URLs\n\n"
            f"<i>Your credits: {self.credit_system.get_user_credits(user.id)}</i>\n\n"
            f"<b>📁 Results delivered in ONE file - ALL results included</b>",
            reply_markup=reply_markup
        )
    
    async def email_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        
        if not context.args:
            await update.message.reply_html(
                "📧 <b>Email Search</b>\n\n"
                "Usage: <code>/email [email]</code>\n\n"
                "<i>Examples:</i>\n"
                "<code>/email user@gmail.com</code>\n"
                "<code>/email @hotmail.com</code>\n"
                "<code>/email admin@example.com</code>"
            )
            return
        
        query = ' '.join(context.args)
        await self.perform_specific_search(update, user.id, 'email', query)
    
    async def login_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        
        if not context.args:
            await update.message.reply_html(
                "👤 <b>Login Search</b>\n\n"
                "Usage: <code>/login [username]</code>\n\n"
                "<i>Examples:</i>\n"
                "<code>/login admin</code>\n"
                "<code>/login user123</code>\n"
                "<code>/login john_doe</code>"
            )
            return
        
        query = ' '.join(context.args)
        await self.perform_specific_search(update, user.id, 'login', query)
    
    async def pass_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        
        if not context.args:
            await update.message.reply_html(
                "🔐 <b>Password Search</b>\n\n"
                "Usage: <code>/pass [password]</code>\n\n"
                "<i>Examples:</i>\n"
                "<code>/pass 123456</code>\n"
                "<code>/pass password123</code>\n"
                "<code>/pass qwerty</code>"
            )
            return
        
        query = ' '.join(context.args)
        await self.perform_specific_search(update, user.id, 'password', query)
    
    async def dni_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        
        if not context.args:
            await update.message.reply_html(
                "🇪🇸 <b>DNI Search - ONLY DNI:password</b>\n\n"
                "Usage: <code>/dni [domain]</code>\n\n"
                "<i>Examples:</i>\n"
                "<code>/dni google.com</code> - Find ONLY DNI:password patterns\n"
                "<code>/dni gmail.com</code> - Find DNI:password from Gmail\n\n"
                "<b>⚠️ Returns ONLY DNI:password (no emails)</b>"
            )
            return
        
        domain = ' '.join(context.args)
        await self.perform_dni_search(update, user.id, domain)
    
    # ============================================================================
    # USER COMMANDS
    # ============================================================================
    
    async def mycredits_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        total_credits = self.credit_system.get_user_credits(user.id)
        daily_credits = self.credit_system.get_daily_credits_left(user.id)
        extra_credits = total_credits - daily_credits
        user_info = self.credit_system.get_user_info(user.id)
        
        message = (
            f"💰 <b>Your Credits</b>\n\n"
            f"<b>Daily Credits:</b> {daily_credits}/2\n"
            f"<b>Extra Credits:</b> {extra_credits}\n"
            f"<b>Total Credits:</b> {total_credits}\n\n"
            f"<b>Statistics:</b>\n"
            f"• Total searches: {user_info.get('total_searches', 0) if user_info else 0}\n"
            f"• Referrals: {user_info.get('referrals', 0) if user_info else 0}\n"
            f"• Member since: {user_info.get('join_date', 'N/A')[:10] if user_info else 'N/A'}\n\n"
            f"<i>Daily credits reset at midnight UTC</i>\n"
            f"Use /referral to invite friends and get +1 credit each!"
        )
        
        await update.message.reply_html(message)
    
    async def mystats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        user_info = self.credit_system.get_user_info(user.id)
        
        if not user_info:
            await update.message.reply_html("❌ User not found in database")
            return
        
        message = (
            f"📊 <b>Your Statistics</b>\n\n"
            f"<b>Account Info:</b>\n"
            f"• User ID: {user_info['user_id']}\n"
            f"• Username: @{user_info['username'] or 'N/A'}\n"
            f"• Name: {user_info['first_name']}\n"
            f"• Joined: {user_info['join_date'][:10]}\n\n"
            f"<b>Activity:</b>\n"
            f"• Total searches: {user_info['total_searches']}\n"
            f"• Successful referrals: {user_info['referrals']}\n\n"
            f"<b>Current Credits:</b>\n"
            f"• Daily: {user_info['daily_credits']}/2\n"
            f"• Extra: {user_info['extra_credits']}\n"
            f"• Total: {user_info['daily_credits'] + user_info['extra_credits']}"
        )
        
        await update.message.reply_html(message)
    
    async def referral_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        referral_info = self.credit_system.get_referral_info(user.id)
        
        if not referral_info:
            await update.message.reply_html("❌ Could not generate referral info")
            return
        
        message = (
            f"🎯 <b>Referral System</b>\n\n"
            f"<b>How it works:</b>\n"
            f"1. Share your referral link\n"
            f"2. When someone joins using your link\n"
            f"3. You get <b>+1 credit</b>!\n"
            f"4. They get 2 free credits\n\n"
            f"<b>Your Referral Stats:</b>\n"
            f"• Referrals: {referral_info['referrals_count']}\n"
            f"• Your Code: <code>{referral_info['referral_code']}</code>\n\n"
            f"<b>Your Referral Link:</b>\n"
            f"<code>{referral_info['referral_link']}</code>\n\n"
            f"<i>Share this link with friends to earn free credits!</i>"
        )
        
        await update.message.reply_html(message)
    
    async def price_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        message = (
            f"💰 <b>Pricing Information</b>\n\n"
            f"<b>FREE PLAN:</b>\n"
            f"• 2 free credits per day\n"
            f"• +1 credit per referral\n"
            f"• All search features\n\n"
            f"<b>PREMIUM PLANS:</b>\n"
            f"Contact {BOT_OWNER} for premium plans:\n"
            f"• Unlimited searches\n"
            f"• Priority support\n"
            f"• Bulk search options\n\n"
            f"<b>SUPPORT:</b>\n"
            f"Contact {BOT_SUPPORT} for any questions or to purchase credits."
        )
        
        await update.message.reply_html(message)
    
    # ============================================================================
    # INFO COMMANDS
    # ============================================================================
    
    async def info_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        stats = self.credit_system.get_bot_stats()
        engine_stats = self.search_engine.get_stats()
        
        message = (
            f"📚 <b>{BOT_NAME} - Information</b>\n\n"
            f"<b>Version:</b> {BOT_VERSION}\n"
            f"<b>Owner:</b> {BOT_OWNER}\n"
            f"<b>Support:</b> {BOT_SUPPORT}\n\n"
            f"<b>Database Statistics:</b>\n"
            f"• Total files: {engine_stats['total_files']:,}\n"
            f"• Total lines: {engine_stats['total_lines']:,}\n"
            f"• Database size: {engine_stats['total_size_mb']:,.1f} MB\n\n"
            f"<b>User Statistics:</b>\n"
            f"• Total users: {stats['total_users']:,}\n"
            f"• Total searches: {stats['total_searches']:,}\n"
            f"• Total referrals: {stats['total_referrals']:,}\n\n"
            f"<b>Free Credits System:</b>\n"
            f"• 2 free credits daily\n"
            f"• +1 credit per referral\n"
            f"• Resets at midnight UTC\n\n"
            f"Use /help for all available commands."
        )
        
        await update.message.reply_html(message)
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        help_text = (
            f"📚 <b>{BOT_NAME} - COMPLETE HELP</b>\n\n"
            
            "<b>🎯 FREE SYSTEM:</b>\n"
            "• Maximum 2 free credits\n"
            "• 1 credit = 1 search\n"
            "• Invite friends: +1 credit per referral\n\n"
            
            "<b>🔍 SEARCH COMMANDS:</b>\n"
            "/search <domain> - Search by domain (choose format)\n"
            "/email <email> - Search by email\n"
            "/login <username> - Search by login\n"
            "/pass <password> - Search by password\n"
            "/dni <domain> - Find DNI:password ONLY (no emails)\n\n"
            
            "<b>📋 FORMATS FOR /search:</b>\n"
            "• Email:Pass Only - Clean format (NO URLs)\n"
            "• Full Lines - Complete lines with URLs\n\n"
            
            "<b>💰 PERSONAL COMMANDS:</b>\n"
            "/mycredits - Check your credits\n"
            "/mystats - Your statistics\n"
            "/referral - Your referral link\n"
            "/price - Pricing information\n\n"
            
            "<b>📊 INFORMATION:</b>\n"
            "/info - Bot information\n"
            "/help - This help message\n\n"
            
            "<b>👑 ADMIN COMMANDS:</b>\n"
            "/stats - Bot statistics\n"
            "/userslist - List all users\n"
            "/addcredits - Add credits to user\n"
            "/userinfo - User information\n"
            "/broadcast - Send to all users\n"
            "/upload - Upload ULP file\n\n"
            
            "<b>📁 RESULT DELIVERY:</b>\n"
            "• <b>ALL</b> results in ONE file\n"
            "• <b>NO LIMIT</b> on results\n"
            "• Small files → .txt\n"
            "• Large files → .zip\n\n"
            
            "<b>💡 TIPS:</b>\n"
            "• Use specific terms for better results\n"
            "• Invite friends to earn free credits\n"
            f"• Contact {BOT_OWNER} for more credits\n\n"
            
            f"<b>Bot developed by {BOT_OWNER}</b>"
        )
        
        await update.message.reply_html(help_text)
    
    # ============================================================================
    # ADMIN COMMANDS
    # ============================================================================
    
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        
        if user.id not in ADMIN_IDS:
            await update.message.reply_html("❌ This command is for admins only")
            return
        
        stats = self.credit_system.get_bot_stats()
        engine_stats = self.search_engine.get_stats()
        
        message = (
            f"📊 <b>Admin Statistics</b>\n\n"
            f"<b>Users:</b> {stats['total_users']:,}\n"
            f"<b>Total Searches:</b> {stats['total_searches']:,}\n"
            f"<b>Total Credits:</b> {stats['total_credits']:,}\n\n"
            f"<b>Database:</b>\n"
            f"• Files: {engine_stats['total_files']:,}\n"
            f"• Lines: {engine_stats['total_lines']:,}\n"
            f"• Size: {engine_stats['total_size_mb']:,.1f} MB\n"
        )
        
        await update.message.reply_html(message)
    
    async def userslist_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        
        if user.id not in ADMIN_IDS:
            await update.message.reply_html("❌ This command is for admins only")
            return
        
        users = self.credit_system.get_all_users(limit=20)
        
        if not users:
            await update.message.reply_html("📭 No users found in database")
            return
        
        message = "<b>👥 Users List (Last 20)</b>\n\n"
        
        for i, user_data in enumerate(users, 1):
            user_id = user_data['user_id']
            username = user_data['username'] or "No username"
            first_name = user_data['first_name']
            searches = user_data['total_searches']
            credits = user_data['daily_credits'] + user_data['extra_credits']
            join_date = user_data['join_date'][:10]
            
            message += (
                f"{i}. <b>{first_name}</b> (@{username})\n"
                f"   ID: {user_id} | Searches: {searches}\n"
                f"   Credits: {credits} | Joined: {join_date}\n\n"
            )
        
        await update.message.reply_html(message[:4000])  # Telegram limit
    
    async def userinfo_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        
        if user.id not in ADMIN_IDS:
            await update.message.reply_html("❌ This command is for admins only")
            return
        
        if not context.args:
            await update.message.reply_html(
                "👤 <b>User Info</b>\n\n"
                "Usage: <code>/userinfo [user_id or username]</code>\n\n"
                "<i>Examples:</i>\n"
                "<code>/userinfo 123456789</code>\n"
                "<code>/userinfo @username</code>"
            )
            return
        
        identifier = context.args[0].strip()
        
        if identifier.startswith('@'):
            identifier = identifier[1:]
            user_data = self.credit_system.get_user_by_username(identifier)
        else:
            try:
                user_id = int(identifier)
                user_data = self.credit_system.get_user_info(user_id)
            except ValueError:
                await update.message.reply_html("❌ Invalid user ID")
                return
        
        if not user_data:
            await update.message.reply_html("❌ User not found")
            return
        
        total_credits = user_data['daily_credits'] + user_data['extra_credits']
        
        message = (
            f"👤 <b>User Information</b>\n\n"
            f"<b>User ID:</b> {user_data['user_id']}\n"
            f"<b>Username:</b> @{user_data['username'] or 'N/A'}\n"
            f"<b>First Name:</b> {user_data['first_name']}\n"
            f"<b>Join Date:</b> {user_data['join_date']}\n\n"
            f"<b>Credits:</b>\n"
            f"• Daily: {user_data['daily_credits']}/2\n"
            f"• Extra: {user_data['extra_credits']}\n"
            f"• Total: {total_credits}\n\n"
            f"<b>Statistics:</b>\n"
            f"• Total searches: {user_data['total_searches']}\n"
            f"• Referrals: {user_data['referrals']}\n"
            f"• Referral Code: {user_data['referral_code']}\n"
        )
        
        await update.message.reply_html(message)
    
    async def addcredits_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        
        if user.id not in ADMIN_IDS:
            await update.message.reply_html("❌ This command is for admins only")
            return
        
        if len(context.args) < 2:
            await update.message.reply_html(
                "➕ <b>Add Credits</b>\n\n"
                "Usage: <code>/addcredits [user_id] [amount] [type]</code>\n\n"
                "<i>Examples:</i>\n"
                "<code>/addcredits 123456789 10 extra</code>\n"
                "<code>/addcredits 123456789 5 daily</code>\n\n"
                "<i>Type: 'extra' or 'daily' (default: extra)</i>"
            )
            return
        
        try:
            user_id = int(context.args[0])
            amount = int(context.args[1])
            credit_type = context.args[2] if len(context.args) > 2 else 'extra'
            
            if credit_type not in ['extra', 'daily']:
                credit_type = 'extra'
            
            success, message = self.credit_system.add_credits_to_user(user_id, amount, user.id, credit_type)
            
            await update.message.reply_html(message)
        except ValueError:
            await update.message.reply_html("❌ Invalid user ID or amount")
        except Exception as e:
            await update.message.reply_html(f"❌ Error: {str(e)}")
    
    async def broadcast_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        
        if user.id not in ADMIN_IDS:
            await update.message.reply_html("❌ This command is for admins only")
            return
        
        if not context.args:
            await update.message.reply_html(
                "📢 <b>Broadcast Message</b>\n\n"
                "Usage: <code>/broadcast [message]</code>\n\n"
                "<i>Example:</i>\n"
                "<code>/broadcast Hello everyone! New features added!</code>"
            )
            return
        
        message = ' '.join(context.args)
        users = self.credit_system.get_all_users()
        
        if not users:
            await update.message.reply_html("📭 No users to broadcast to")
            return
        
        sent_count = 0
        failed_count = 0
        
        await update.message.reply_html(f"📢 Starting broadcast to {len(users)} users...")
        
        for user_data in users:
            try:
                await context.bot.send_message(
                    chat_id=user_data['user_id'],
                    text=f"📢 <b>Broadcast from {BOT_NAME}</b>\n\n{message}\n\n<i>Bot Owner: {BOT_OWNER}</i>",
                    parse_mode='HTML'
                )
                sent_count += 1
            except Exception as e:
                failed_count += 1
            
            await asyncio.sleep(0.05)  # Rate limit
        
        await update.message.reply_html(
            f"✅ <b>Broadcast Complete</b>\n\n"
            f"• Total users: {len(users)}\n"
            f"• Successfully sent: {sent_count}\n"
            f"• Failed: {failed_count}"
        )
    
    # ============================================================================
    # UPLOAD COMMAND - CORREGIDO Y FUNCIONANDO
    # ============================================================================
    
    async def upload_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Upload ULP file (admin only) - VERSIÓN CORREGIDA Y FUNCIONANDO"""
        user = update.effective_user
        
        # Verificar si es admin
        if user.id not in ADMIN_IDS:
            await update.message.reply_text("❌ This command is for admins only")
            return
        
        # Verificar que hay un archivo
        if not update.message.document:
            await update.message.reply_text(
                "📁 Upload ULP File\n\n"
                "Send a .txt file with ULP data.\n"
                "The file will be added to the search database."
            )
            return
        
        document = update.message.document
        
        # Verificar extensión
        if not document.file_name.endswith('.txt'):
            await update.message.reply_text("❌ Only .txt files are accepted")
            return
        
        msg = await update.message.reply_text("📥 Downloading file...")
        
        try:
            # 1. Crear directorios si no existen
            os.makedirs(UPLOAD_DIR, exist_ok=True)
            os.makedirs(DATA_DIR, exist_ok=True)
            
            # 2. Descargar archivo
            file = await context.bot.get_file(document.file_id)
            temp_path = os.path.join(UPLOAD_DIR, f"temp_{document.file_name}")
            await file.download_to_drive(temp_path)
            
            # 3. Verificar que se descargó
            if not os.path.exists(temp_path):
                await msg.edit_text("❌ File download failed")
                return
            
            file_size = os.path.getsize(temp_path)
            await msg.edit_text(f"✅ Downloaded: {document.file_name} ({file_size:,} bytes)\n📦 Adding to database...")
            
            # 4. Añadir a la base de datos
            success, result = self.search_engine.add_data_file(temp_path)
            
            # 5. Eliminar archivo temporal
            try:
                os.remove(temp_path)
            except:
                pass
            
            # 6. Respuesta
            if success:
                stats = self.search_engine.get_stats()
                await msg.edit_text(
                    f"✅ <b>File Uploaded Successfully!</b>\n\n"
                    f"📄 <b>File:</b> {result}\n"
                    f"📊 <b>Total files:</b> {stats['total_files']}\n"
                    f"📈 <b>Total lines:</b> {stats['total_lines']:,}\n\n"
                    f"Database reloaded and ready for searches.",
                    parse_mode='HTML'
                )
            else:
                await msg.edit_text(f"❌ Upload failed: {result}")
            
        except Exception as e:
            logger.error(f"Upload error: {e}")
            await msg.edit_text(f"❌ Upload error: {str(e)}")
    
    # ============================================================================
    # SEARCH FUNCTIONALITY
    # ============================================================================
    
    async def perform_search_with_format(self, update: Update, user_id: int, query: str, format_type: str):
        if not self.credit_system.has_enough_credits(user_id):
            await self.send_no_credits_message(update, user_id)
            return
        
        query_msg = await update.callback_query.edit_message_text(
            f"🔍 Searching: <code>{self.escape_html(query)}</code>\n"
            f"📋 Format: {format_type.replace('_', ' ').title()}\n"
            f"⏳ Collecting ALL results...",
            parse_mode='HTML'
        )
        
        try:
            if format_type == 'clean':
                count, results = self.search_engine.search_clean_email_pass_no_url(query)
                description = "Email:Pass Only (NO URLs)"
            else:
                count, results = self.search_engine.search_all_formats(query)
                description = "Complete database entries (with URLs)"
            
            success = self.credit_system.use_credits(user_id, format_type, query, count)
            
            if not success:
                await query_msg.edit_text("❌ Error using credits")
                return
            
            daily_credits = self.credit_system.get_daily_credits_left(user_id)
            
            if count == 0:
                await query_msg.edit_text(
                    f"🔍 <b>Search Results</b>\n\n"
                    f"<b>Query:</b> <code>{self.escape_html(query)}</code>\n"
                    f"<b>Results:</b> 0\n\n"
                    f"No results found.\n\n"
                    f"<i>Daily credits remaining: {daily_credits}/2</i>",
                    parse_mode='HTML'
                )
                return
            
            await query_msg.edit_text(
                f"✅ Found: {count:,} results\n"
                f"📁 Creating file with ALL results...\n"
                f"⏳ Please wait..."
            )
            
            results_text = "\n".join(results)
            file_content = f"""SEARCH RESULTS - {BOT_NAME}
Query: {query}
Format: {description}
Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Total Results: {count:,}

{results_text}"""
            
            file_size_mb = len(file_content.encode('utf-8')) / (1024 * 1024)
            
            if file_size_mb <= 45:
                file_obj = io.BytesIO(file_content.encode('utf-8'))
                filename = f"{query.replace('@', '_at_').replace('.', '_dot_')}_{format_type}_{count}_results.txt"
                file_obj.name = filename
                
                await update.callback_query.message.reply_document(
                    document=file_obj,
                    caption=(
                        f"✅ <b>SEARCH COMPLETED</b>\n\n"
                        f"<b>Query:</b> {query}\n"
                        f"<b>Results:</b> {count:,}\n"
                        f"<b>Daily credits left:</b> {daily_credits}/2\n"
                        f"<b>Total credits:</b> {self.credit_system.get_user_credits(user_id)}\n\n"
                        f"<i>ALL results in one file</i>"
                    ),
                    parse_mode='HTML'
                )
                await query_msg.delete()
            else:
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                    zip_file.writestr(f"{query}_ALL_RESULTS.txt", file_content)
                
                zip_buffer.seek(0)
                zip_filename = f"{query}_ALL_RESULTS_{count}.zip"
                zip_buffer.name = zip_filename
                
                await update.callback_query.message.reply_document(
                    document=zip_buffer,
                    caption=(
                        f"✅ <b>SEARCH COMPLETED</b>\n\n"
                        f"<b>Query:</b> {query}\n"
                        f"<b>Results:</b> {count:,}\n"
                        f"<b>File size:</b> {file_size_mb:.1f} MB\n"
                        f"<b>Daily credits left:</b> {daily_credits}/2\n\n"
                        f"<i>ALL results in ZIP file</i>"
                    ),
                    parse_mode='HTML'
                )
                await query_msg.delete()
                
        except Exception as e:
            logger.error(f"Search error: {e}")
            await query_msg.edit_text(f"❌ Error: {str(e)}")
    
    async def perform_specific_search(self, update: Update, user_id: int, search_type: str, query: str):
        if not self.credit_system.has_enough_credits(user_id):
            await self.send_no_credits_message(update, user_id)
            return
        
        msg = await update.message.reply_html(
            f"🔍 Searching for: <code>{self.escape_html(query)}</code>\n"
            f"Type: {search_type.capitalize()}\n"
            f"⏳ Collecting ALL results..."
        )
        
        try:
            if search_type == 'email':
                count, results = self.search_engine.search_email_only(query)
            elif search_type == 'login':
                count, results = self.search_engine.search_login(query)
            elif search_type == 'password':
                count, results = self.search_engine.search_password(query)
            else:
                await msg.edit_text("❌ Invalid search type")
                return
            
            success = self.credit_system.use_credits(user_id, search_type, query, count)
            
            if not success:
                await msg.edit_text("❌ Error using credits")
                return
            
            daily_credits = self.credit_system.get_daily_credits_left(user_id)
            
            if count == 0:
                await msg.edit_text(
                    f"🔍 <b>Search Results</b>\n\n"
                    f"<b>Query:</b> <code>{self.escape_html(query)}</code>\n"
                    f"<b>Type:</b> {search_type.capitalize()}\n"
                    f"<b>Results:</b> 0\n\n"
                    f"No results found.\n\n"
                    f"<i>Daily credits remaining: {daily_credits}/2</i>",
                    parse_mode='HTML'
                )
                return
            
            await msg.edit_text(
                f"✅ Found: {count:,} results\n"
                f"📁 Creating file with ALL results...\n"
                f"⏳ Please wait..."
            )
            
            results_text = "\n".join(results)
            file_content = f"""SEARCH RESULTS - {BOT_NAME}
Type: {search_type.capitalize()}
Query: {query}
Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Total Results: {count:,}

{results_text}"""
            
            file_size_mb = len(file_content.encode('utf-8')) / (1024 * 1024)
            
            if file_size_mb <= 45:
                file_obj = io.BytesIO(file_content.encode('utf-8'))
                filename = f"{search_type}_{query.replace('@', '_at_').replace('.', '_dot_')}_{count}_results.txt"
                file_obj.name = filename
                
                await update.message.reply_document(
                    document=file_obj,
                    caption=(
                        f"✅ <b>SEARCH COMPLETED</b>\n\n"
                        f"<b>Type:</b> {search_type.capitalize()}\n"
                        f"<b>Query:</b> {query}\n"
                        f"<b>Results:</b> {count:,}\n"
                        f"<b>Daily credits left:</b> {daily_credits}/2\n"
                        f"<b>Total credits:</b> {self.credit_system.get_user_credits(user_id)}\n\n"
                        f"<i>ALL results in one file</i>"
                    ),
                    parse_mode='HTML'
                )
                await msg.delete()
            else:
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                    zip_file.writestr(f"{search_type}_{query}_ALL_RESULTS.txt", file_content)
                
                zip_buffer.seek(0)
                zip_filename = f"{search_type}_{query}_{count}_results.zip"
                zip_buffer.name = zip_filename
                
                await update.message.reply_document(
                    document=zip_buffer,
                    caption=(
                        f"✅ <b>SEARCH COMPLETED</b>\n\n"
                        f"<b>Type:</b> {search_type.capitalize()}\n"
                        f"<b>Query:</b> {query}\n"
                        f"<b>Results:</b> {count:,}\n"
                        f"<b>File size:</b> {file_size_mb:.1f} MB\n"
                        f"<b>Daily credits left:</b> {daily_credits}/2\n\n"
                        f"<i>ALL results in ZIP file</i>"
                    ),
                    parse_mode='HTML'
                )
                await msg.delete()
                
        except Exception as e:
            logger.error(f"Search error: {e}")
            await msg.edit_text(f"❌ Error: {str(e)}")
    
    async def perform_dni_search(self, update: Update, user_id: int, domain: str):
        if not self.credit_system.has_enough_credits(user_id):
            await self.send_no_credits_message(update, user_id)
            return
        
        msg = await update.message.reply_html(
            f"🔍 Searching DNI:password from: <code>{self.escape_html(domain)}</code>\n"
            f"⏳ Collecting ALL results (NO emails)..."
        )
        
        try:
            count, results = self.search_engine.search_dni_domain_only_dni_pass(domain)
            
            success = self.credit_system.use_credits(user_id, 'dni', domain, count)
            
            if not success:
                await msg.edit_text("❌ Error using credits")
                return
            
            daily_credits = self.credit_system.get_daily_credits_left(user_id)
            
            if count == 0:
                await msg.edit_text(
                    f"🔍 <b>DNI Search Results</b>\n\n"
                    f"<b>Domain:</b> <code>{self.escape_html(domain)}</code>\n"
                    f"<b>Results:</b> 0 DNI:password combos\n\n"
                    f"No Spanish ID (DNI) combos found for {domain}.\n\n"
                    f"<i>Daily credits remaining: {daily_credits}/2</i>",
                    parse_mode='HTML'
                )
                return
            
            await msg.edit_text(
                f"✅ Found: {count:,} DNI:password combos\n"
                f"📁 Creating file with ALL results...\n"
                f"⏳ Please wait..."
            )
            
            results_text = "\n".join(results)
            file_content = f"""DNI SEARCH RESULTS - {BOT_NAME}
Domain: {domain}
Type: DNI:password combos ONLY (NO emails)
Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Total Results: {count:,}

{results_text}"""
            
            file_size_mb = len(file_content.encode('utf-8')) / (1024 * 1024)
            
            if file_size_mb <= 45:
                file_obj = io.BytesIO(file_content.encode('utf-8'))
                filename = f"dni_{domain.replace('.', '_dot_')}_{count}_results.txt"
                file_obj.name = filename
                
                await update.message.reply_document(
                    document=file_obj,
                    caption=(
                        f"✅ <b>DNI SEARCH COMPLETED</b>\n\n"
                        f"<b>Domain:</b> {domain}\n"
                        f"<b>Results:</b> {count:,} DNI:password combos\n"
                        f"<b>Note:</b> NO emails included\n"
                        f"<b>Daily credits left:</b> {daily_credits}/2\n"
                        f"<b>Total credits:</b> {self.credit_system.get_user_credits(user_id)}\n\n"
                        f"<i>ALL results in one file</i>"
                    ),
                    parse_mode='HTML'
                )
                await msg.delete()
            else:
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                    zip_file.writestr(f"dni_{domain}_ALL_RESULTS.txt", file_content)
                
                zip_buffer.seek(0)
                zip_filename = f"dni_{domain}_{count}_results.zip"
                zip_buffer.name = zip_filename
                
                await update.message.reply_document(
                    document=zip_buffer,
                    caption=(
                        f"✅ <b>DNI SEARCH COMPLETED</b>\n\n"
                        f"<b>Domain:</b> {domain}\n"
                        f"<b>Results:</b> {count:,} DNI:password combos\n"
                        f"<b>Note:</b> NO emails included\n"
                        f"<b>File size:</b> {file_size_mb:.1f} MB\n"
                        f"<b>Daily credits left:</b> {daily_credits}/2\n\n"
                        f"<i>ALL results in ZIP file</i>"
                    ),
                    parse_mode='HTML'
                )
                await msg.delete()
                
        except Exception as e:
            logger.error(f"DNI search error: {e}")
            await msg.edit_text(f"❌ Error: {str(e)}")
    
    async def send_no_credits_message(self, update: Update, user_id: int):
        daily_credits = self.credit_system.get_daily_credits_left(user_id)
        
        message = (
            f"❌ <b>No Credits Available</b>\n\n"
            f"You have used all your credits.\n\n"
            f"<b>Daily Credits:</b> {daily_credits}/2\n\n"
            f"Credits reset at midnight UTC.\n"
            f"Contact {BOT_OWNER} for more credits."
        )
        
        if update.callback_query:
            await update.callback_query.edit_message_text(message, parse_mode='HTML')
        else:
            await update.message.reply_html(message)
    
    # ============================================================================
    # BUTTON HANDLER
    # ============================================================================
    
    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        user = update.effective_user
        data = query.data
        
        if data == "start_search":
            await query.edit_message_text(
                "🔍 <b>Search Command</b>\n\n"
                "Usage: <code>/search [query]</code>\n\n"
                "<i>Examples:</i>\n"
                "<code>/search google.com</code>\n"
                "<code>/search user@gmail.com</code>\n"
                "<code>/search @hotmail.com</code>\n\n"
                "Then choose format!\n\n"
                "<b>📁 ALL RESULTS IN ONE FILE - NO LIMITS</b>",
                parse_mode='HTML'
            )
            
        elif data.startswith("format_"):
            parts = data.split(":", 1)
            if len(parts) == 2:
                format_type = parts[0].replace("format_", "")
                search_query = parts[1]
                await self.perform_search_with_format(update, user.id, search_query, format_type)
        
        elif data == "cancel_search":
            await query.edit_message_text(
                "❌ <b>Search Cancelled</b>\n\n"
                "Use /search to start a new search.",
                parse_mode='HTML'
            )
            
        elif data == "menu_credits":
            await self.mycredits_command(update, context)
            
        elif data == "menu_help":
            await self.help_command(update, context)
            
        elif data == "menu_admin" and user.id in ADMIN_IDS:
            keyboard = [
                [InlineKeyboardButton("📊 /stats - Statistics", callback_data="admin_stats")],
                [InlineKeyboardButton("👥 /userslist - Users List", callback_data="admin_users")],
                [InlineKeyboardButton("👤 /userinfo - User Info", callback_data="admin_userinfo")],
                [InlineKeyboardButton("➕ /addcredits - Add Credits", callback_data="admin_add")],
                [InlineKeyboardButton("📢 /broadcast - Broadcast", callback_data="admin_broadcast")],
                [InlineKeyboardButton("📁 /upload - Upload File", callback_data="admin_upload")],
                [InlineKeyboardButton("⬅️ Back", callback_data="menu_back")],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                "👑 <b>Admin Panel</b>\n\n"
                "Select an option:",
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
            
        elif data == "admin_stats" and user.id in ADMIN_IDS:
            await self.stats_command(update, context)
            
        elif data == "admin_users" and user.id in ADMIN_IDS:
            await self.userslist_command(update, context)
            
        elif data == "admin_userinfo" and user.id in ADMIN_IDS:
            await self.userinfo_command(update, context)
            
        elif data == "admin_add" and user.id in ADMIN_IDS:
            await query.edit_message_text(
                "➕ <b>Add Credits Command</b>\n\n"
                "Usage: <code>/addcredits [user_id] [amount] [type]</code>\n\n"
                "<i>Examples:</i>\n"
                "<code>/addcredits 123456789 10 extra</code>\n"
                "<code>/addcredits 123456789 5 daily</code>",
                parse_mode='HTML'
            )
            
        elif data == "admin_broadcast" and user.id in ADMIN_IDS:
            await query.edit_message_text(
                "📢 <b>Broadcast Command</b>\n\n"
                "Usage: <code>/broadcast [message]</code>\n\n"
                "<i>Example:</i>\n"
                "<code>/broadcast Hello everyone! New features added!</code>",
                parse_mode='HTML'
            )
            
        elif data == "admin_upload" and user.id in ADMIN_IDS:
            await self.upload_command(update, context)
            
        elif data == "menu_back":
            await self.start(update, context)

# ============================================================================
# INICIALIZACIÓN DE LA APLICACIÓN
# ============================================================================

async def initialize():
    """Inicializar todos los componentes"""
    global search_engine, credit_system, bot_instance, telegram_app
    
    logger.info("🚀 Inicializando componentes...")
    
    # Crear componentes
    search_engine = SearchEngine()
    credit_system = CreditSystem()
    bot_instance = ULPBot(search_engine, credit_system)
    
    # Crear aplicación de Telegram
    telegram_app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Registrar todos los handlers
    telegram_app.add_handler(CommandHandler("start", bot_instance.start))
    telegram_app.add_handler(CommandHandler("search", bot_instance.search_command))
    telegram_app.add_handler(CommandHandler("email", bot_instance.email_command))
    telegram_app.add_handler(CommandHandler("login", bot_instance.login_command))
    telegram_app.add_handler(CommandHandler("pass", bot_instance.pass_command))
    telegram_app.add_handler(CommandHandler("dni", bot_instance.dni_command))
    
    telegram_app.add_handler(CommandHandler("mycredits", bot_instance.mycredits_command))
    telegram_app.add_handler(CommandHandler("mystats", bot_instance.mystats_command))
    telegram_app.add_handler(CommandHandler("referral", bot_instance.referral_command))
    telegram_app.add_handler(CommandHandler("price", bot_instance.price_command))
    
    telegram_app.add_handler(CommandHandler("info", bot_instance.info_command))
    telegram_app.add_handler(CommandHandler("help", bot_instance.help_command))
    
    telegram_app.add_handler(CommandHandler("stats", bot_instance.stats_command))
    telegram_app.add_handler(CommandHandler("userslist", bot_instance.userslist_command))
    telegram_app.add_handler(CommandHandler("userinfo", bot_instance.userinfo_command))
    telegram_app.add_handler(CommandHandler("addcredits", bot_instance.addcredits_command))
    telegram_app.add_handler(CommandHandler("broadcast", bot_instance.broadcast_command))
    telegram_app.add_handler(CommandHandler("upload", bot_instance.upload_command))
    
    telegram_app.add_handler(CallbackQueryHandler(bot_instance.button_handler))
    
    # Inicializar aplicación
    await telegram_app.initialize()
    await telegram_app.start()
    
    # Configurar webhook
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    
    # Eliminar webhook existente
    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("✅ Webhook anterior eliminado")
    
    # Configurar nuevo webhook
    await bot.set_webhook(
        url=WEBHOOK_URL,
        allowed_updates=["message", "callback_query"],
        drop_pending_updates=True,
        max_connections=1
    )
    
    webhook_info = await bot.get_webhook_info()
    logger.info(f"✅ Webhook configurado: {webhook_info.url}")
    logger.info(f"📊 Updates pendientes: {webhook_info.pending_update_count}")
    
    logger.info("✅ Bot inicializado correctamente")
    
    return telegram_app

# ============================================================================
# MAIN
# ============================================================================

@app.before_request
async def before_request():
    """Ejecutar antes de la primera petición"""
    global telegram_app
    
    if telegram_app is None:
        await initialize()

def run():
    """Punto de entrada principal"""
    print("="*60)
    print(f"🚀 Iniciando {BOT_NAME} v{BOT_VERSION}")
    print(f"👑 Owner: {BOT_OWNER}")
    print(f"🌐 Webhook URL: {WEBHOOK_URL}")
    print(f"🔌 Puerto: {PORT}")
    print(f"📁 Directorio datos: {DATA_DIR}")
    print("="*60)
    
    # Iniciar Flask
    app.run(host='0.0.0.0', port=PORT, debug=False, use_reloader=False)

if __name__ == "__main__":
    run()
