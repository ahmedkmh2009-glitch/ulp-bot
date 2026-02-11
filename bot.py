"""
🔍 ULP Searcher Bot - COMPLETE ENGLISH VERSION - CORREGIDO FINAL
With ALL Commands + Broadcast + Referral System
Owner: @iberic_owner
"""

import os
import logging
import sqlite3
import threading
import io
import zipfile
import random
from datetime import datetime, time, timedelta
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import glob
import asyncio
import re

from flask import Flask, request, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    ContextTypes, CallbackQueryHandler, filters,
    ConversationHandler, JobQueue
)

# ============================================================================
# CONFIGURATION
# ============================================================================

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
ADMIN_IDS = [int(id.strip()) for id in os.getenv('ADMIN_IDS', '').split(',') if id.strip()]
BOT_OWNER = "@iberic_owner"
BOT_NAME = "🔍 ULP Searcher Bot"
BOT_VERSION = "7.2 COMPLETE EN - DNI FIXED"
MAX_FREE_CREDITS = 2
RESET_HOUR = 0

# Referral system
REFERRAL_BONUS = 1

PORT = int(os.getenv('PORT', 10000))

BASE_DIR = "bot_data"
DATA_DIR = os.path.join(BASE_DIR, "ulp_files")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
DB_PATH = os.path.join(BASE_DIR, "bot.db")

for directory in [BASE_DIR, DATA_DIR, UPLOAD_DIR]:
    os.makedirs(directory, exist_ok=True)

CHOOSING_FORMAT, BROADCAST_MESSAGE = range(2)

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

# ============================================================================
# FLASK APP
# ============================================================================

app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({"status": "online", "bot": BOT_NAME, "owner": BOT_OWNER})

@app.route('/health')
def health():
    return jsonify({"status": "healthy"})

# ============================================================================
# SEARCH ENGINE - SIN LÍMITES
# ============================================================================

class SearchEngine:
    def __init__(self, data_dir: str = DATA_DIR):
        self.data_dir = data_dir
        self.data_files = []
        self.load_all_data()
    
    def load_all_data(self):
        self.data_files = glob.glob(os.path.join(self.data_dir, "*.txt"))
        logger.info(f"📂 Loaded {len(self.data_files)} files")
    
    def search_domain(self, domain: str, max_results: int = None) -> Tuple[int, List[str]]:
        """Busca dominio SIN LÍMITE"""
        results = []
        domain_lower = domain.lower()
        
        for file_path in self.data_files:
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        
                        if domain_lower in line.lower():
                            results.append(line)
                        
                        if max_results and len(results) >= max_results:
                            break
            
            except Exception as e:
                logger.error(f"Error in {file_path}: {e}")
                continue
        
        return len(results), results
    
    def search_email(self, email: str, max_results: int = None) -> Tuple[int, List[str]]:
        results = []
        email_lower = email.lower()
        
        for file_path in self.data_files:
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        
                        if email_lower in line.lower():
                            results.append(line)
                        
                        if max_results and len(results) >= max_results:
                            break
            
            except Exception as e:
                logger.error(f"Error in {file_path}: {e}")
                continue
        
        return len(results), results
    
    def search_login(self, login: str, max_results: int = None) -> Tuple[int, List[str]]:
        results = []
        login_lower = login.lower()
        
        for file_path in self.data_files:
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        
                        if ':' in line:
                            parts = line.split(':')
                            if len(parts) >= 2:
                                if login_lower in parts[0].lower():
                                    results.append(line)
                        
                        if max_results and len(results) >= max_results:
                            break
            
            except Exception as e:
                logger.error(f"Error in {file_path}: {e}")
                continue
        
        return len(results), results
    
    def search_password(self, password: str, max_results: int = None) -> Tuple[int, List[str]]:
        results = []
        password_lower = password.lower()
        
        for file_path in self.data_files:
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        
                        if password_lower in line.lower():
                            results.append(line)
                        
                        if max_results and len(results) >= max_results:
                            break
            
            except Exception as e:
                logger.error(f"Error in {file_path}: {e}")
                continue
        
        return len(results), results
    
    def search_dni(self, dni: str, max_results: int = None) -> Tuple[int, List[str]]:
        """Busca DNI español en formato DNI:password"""
        results = []
        dni_clean = dni.upper().replace(' ', '').replace('-', '')
        
        # Patrón para DNI español: 8 números + letra
        dni_pattern = r'\b[0-9]{8}[A-Z]\b'
        
        for file_path in self.data_files:
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        
                        # Buscar líneas que contengan el DNI
                        if dni_clean in line.upper():
                            # Verificar que sea un formato DNI:pass
                            parts = line.split(':')
                            if len(parts) >= 2:
                                # El primer campo debe ser un DNI válido
                                first_part = parts[0].upper().strip()
                                if re.match(dni_pattern, first_part):
                                    results.append(line)
                        
                        if max_results and len(results) >= max_results:
                            break
            
            except Exception as e:
                logger.error(f"Error in {file_path}: {e}")
                continue
        
        return len(results), results
    
    def search_dni_by_domain(self, domain: str, max_results: int = None) -> Tuple[int, List[str]]:
        """Busca combos DNI:password que contengan un dominio específico"""
        results = []
        domain_lower = domain.lower()
        
        # Patrón para DNI español
        dni_pattern = r'\b[0-9]{8}[A-Z]\b'
        
        for file_path in self.data_files:
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        
                        # Verificar que sea DNI:password
                        parts = line.split(':')
                        if len(parts) >= 2:
                            first_part = parts[0].upper().strip()
                            if re.match(dni_pattern, first_part):
                                # Buscar el dominio en toda la línea
                                if domain_lower in line.lower():
                                    results.append(line)
                        
                        if max_results and len(results) >= max_results:
                            break
            
            except Exception as e:
                logger.error(f"Error in {file_path}: {e}")
                continue
        
        return len(results), results
    
    def get_stats(self) -> Dict:
        return {
            "total_files": len(self.data_files),
            "recent_files": []
        }
    
    def add_data_file(self, file_path: str) -> Tuple[bool, str]:
        try:
            import shutil
            filename = os.path.basename(file_path)
            dest_path = os.path.join(self.data_dir, filename)
            shutil.copy2(file_path, dest_path)
            self.load_all_data()
            return True, filename
        except Exception as e:
            return False, str(e)

# ============================================================================
# CREDIT SYSTEM WITH REFERRALS
# ============================================================================

class CreditSystem:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.init_database()
    
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
                    referrals_count INTEGER DEFAULT 0,
                    referral_code TEXT UNIQUE,
                    referred_by INTEGER,
                    join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_reset DATE DEFAULT CURRENT_DATE,
                    active BOOLEAN DEFAULT TRUE
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
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS referrals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    referrer_id INTEGER,
                    referred_id INTEGER,
                    bonus_credited BOOLEAN DEFAULT FALSE,
                    date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS daily_resets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    reset_date DATE UNIQUE,
                    users_reset INTEGER DEFAULT 0,
                    reset_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS broadcasts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    admin_id INTEGER,
                    message TEXT,
                    sent_to INTEGER DEFAULT 0,
                    failed_to INTEGER DEFAULT 0,
                    date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()
    
    def generate_referral_code(self, user_id: int) -> str:
        code = f"REF{user_id}{random.randint(1000, 9999)}"
        return code
    
    def get_or_create_user(self, user_id: int, username: str = "", first_name: str = "", referred_by: Optional[int] = None):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
            user = cursor.fetchone()
            
            if user:
                self.check_daily_reset(user_id)
                return dict(user)
            
            referral_code = self.generate_referral_code(user_id)
            
            cursor.execute('''
                INSERT INTO users 
                (user_id, username, first_name, daily_credits, referral_code, referred_by, last_reset)
                VALUES (?, ?, ?, 2, ?, ?, DATE('now'))
            ''', (user_id, username, first_name, referral_code, referred_by))
            
            cursor.execute('''
                INSERT INTO transactions (user_id, amount, type, description)
                VALUES (?, ?, ?, ?)
            ''', (user_id, 2, 'daily_reset', '2 daily initial credits'))
            
            if referred_by:
                cursor.execute('''
                    INSERT INTO referrals (referrer_id, referred_id)
                    VALUES (?, ?)
                ''', (referred_by, user_id))
                
                cursor.execute('''
                    UPDATE users 
                    SET extra_credits = extra_credits + ?,
                        referrals_count = referrals_count + 1
                    WHERE user_id = ?
                ''', (REFERRAL_BONUS, referred_by))
                
                cursor.execute('''
                    INSERT INTO transactions 
                    (user_id, amount, type, description)
                    VALUES (?, ?, ?, ?)
                ''', (referred_by, REFERRAL_BONUS, 'referral_bonus', f'Referral bonus for user {user_id}'))
                
                cursor.execute('''
                    UPDATE referrals 
                    SET bonus_credited = TRUE
                    WHERE referrer_id = ? AND referred_id = ?
                ''', (referred_by, user_id))
            
            conn.commit()
            
            return {
                'user_id': user_id,
                'username': username,
                'first_name': first_name,
                'daily_credits': 2,
                'extra_credits': 0,
                'referral_code': referral_code,
                'referred_by': referred_by,
                'referrals_count': 0
            }
    
    def check_daily_reset(self, user_id: int):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute(
                'SELECT last_reset, daily_credits FROM users WHERE user_id = ?',
                (user_id,)
            )
            result = cursor.fetchone()
            
            if result:
                last_reset = result['last_reset']
                today = datetime.now().date()
                
                if last_reset != str(today):
                    cursor.execute('''
                        UPDATE users 
                        SET daily_credits = 2,
                            last_reset = DATE('now')
                        WHERE user_id = ?
                    ''', (user_id,))
                    
                    cursor.execute('''
                        INSERT INTO transactions (user_id, amount, type, description)
                        VALUES (?, ?, ?, ?)
                    ''', (user_id, 2, 'daily_reset', 'Daily reset to 2 credits'))
                    
                    conn.commit()
    
    def get_user_credits(self, user_id: int) -> int:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT daily_credits, extra_credits FROM users WHERE user_id = ?',
                (user_id,)
            )
            result = cursor.fetchone()
            
            if result:
                self.check_daily_reset(user_id)
                cursor.execute(
                    'SELECT daily_credits, extra_credits FROM users WHERE user_id = ?',
                    (user_id,)
                )
                result = cursor.fetchone()
                return result['daily_credits'] + result['extra_credits']
            
            return 0
    
    def get_daily_credits_left(self, user_id: int) -> int:
        self.check_daily_reset(user_id)
        
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
            
            self.check_daily_reset(user_id)
            
            cursor.execute(
                'SELECT daily_credits, extra_credits FROM users WHERE user_id = ?',
                (user_id,)
            )
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
    
    def add_credits_to_user(self, user_id: int, amount: int, admin_id: int, credit_type: str = 'extra') -> Tuple[bool, str]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute(
                'SELECT extra_credits FROM users WHERE user_id = ?',
                (user_id,)
            )
            result = cursor.fetchone()
            
            if not result:
                return False, "User not found"
            
            if credit_type == 'extra':
                cursor.execute(
                    'UPDATE users SET extra_credits = extra_credits + ? WHERE user_id = ?',
                    (amount, user_id)
                )
            else:
                cursor.execute(
                    'UPDATE users SET daily_credits = daily_credits + ? WHERE user_id = ?',
                    (amount, user_id)
                )
            
            cursor.execute('''
                INSERT INTO transactions 
                (user_id, amount, type, description)
                VALUES (?, ?, ?, ?)
            ''', (user_id, amount, f'admin_add_{credit_type}', f'{credit_type} credits added by admin {admin_id}'))
            
            conn.commit()
            return True, f"✅ {amount} {credit_type} credits added"
    
    def get_user_info(self, user_id: int):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
            result = cursor.fetchone()
            return dict(result) if result else None
    
    def get_referral_stats(self, user_id: int):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT 
                    referrals_count,
                    referral_code,
                    (SELECT COUNT(*) FROM referrals WHERE referrer_id = ?) as total_referred
                FROM users 
                WHERE user_id = ?
            ''', (user_id, user_id))
            
            result = cursor.fetchone()
            return dict(result) if result else None
    
    def get_referral_link(self, user_id: int) -> str:
        user_info = self.get_user_info(user_id)
        if user_info and user_info.get('referral_code'):
            bot_name_clean = BOT_NAME.split()[0].replace('🔍', '').strip()
            return f"https://t.me/{bot_name_clean}?start=ref_{user_info['referral_code']}"
        return ""
    
    def validate_referral_code(self, code: str) -> Tuple[bool, Optional[int]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT user_id FROM users WHERE referral_code = ?', (code,))
            result = cursor.fetchone()
            if result:
                return True, result['user_id']
            return False, None
    
    def get_all_users(self, limit: int = 50):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users WHERE active = TRUE ORDER BY join_date DESC LIMIT ?', (limit,))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_all_users_for_broadcast(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT user_id FROM users WHERE active = TRUE')
            return [row['user_id'] for row in cursor.fetchall()]
    
    def save_broadcast(self, admin_id: int, message: str, sent_to: int, failed_to: int):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO broadcasts (admin_id, message, sent_to, failed_to)
                VALUES (?, ?, ?, ?)
            ''', (admin_id, message, sent_to, failed_to))
            conn.commit()
    
    def get_bot_stats(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            stats = {}
            cursor.execute('SELECT COUNT(*) as count FROM users WHERE active = TRUE')
            stats['total_users'] = cursor.fetchone()['count']
            
            cursor.execute('SELECT COUNT(*) as count FROM transactions WHERE type = "search_used"')
            stats['total_searches'] = cursor.fetchone()['count']
            
            cursor.execute('SELECT SUM(daily_credits + extra_credits) as total FROM users')
            stats['total_credits'] = cursor.fetchone()['total'] or 0
            
            cursor.execute('SELECT SUM(referrals_count) as total FROM users')
            stats['total_referrals'] = cursor.fetchone()['total'] or 0
            
            cursor.execute('SELECT COUNT(*) as count FROM broadcasts')
            stats['total_broadcasts'] = cursor.fetchone()['count']
            
            return stats

# ============================================================================
# MAIN BOT - CORREGIDO: DNI CON DOMINIO Y FILTROS EXACTOS
# ============================================================================

class ULPBot:
    def __init__(self, search_engine: SearchEngine, credit_system: CreditSystem):
        self.search_engine = search_engine
        self.credit_system = credit_system
        self.pending_searches = {}
    
    def escape_html(self, text: str) -> str:
        if not text:
            return ""
        text = str(text)
        text = text.replace('&', '&amp;')
        text = text.replace('<', '&lt;')
        text = text.replace('>', '&gt;')
        return text
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        referred_by = None
        
        if context.args and len(context.args) > 0:
            if context.args[0].startswith('ref_'):
                ref_code = context.args[0][4:]
                valid, referrer_id = self.credit_system.validate_referral_code(ref_code)
                if valid and referrer_id != user.id:
                    referred_by = referrer_id
        
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
        
        keyboard = [
            [InlineKeyboardButton("🔍 Search Domain", callback_data="menu_search")],
            [InlineKeyboardButton("📧 Search Email", callback_data="menu_email")],
            [InlineKeyboardButton("💰 My Credits", callback_data="menu_credits")],
            [InlineKeyboardButton("👥 Referral System", callback_data="menu_referral")],
            [InlineKeyboardButton("📋 /help", callback_data="menu_help")],
        ]
        
        if user.id in ADMIN_IDS:
            keyboard.append([InlineKeyboardButton("👑 Admin", callback_data="menu_admin")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        welcome_msg = f"<b>👋 Welcome {self.escape_html(user.first_name)}!</b>\n\n"
        
        if referred_by:
            welcome_msg += f"<b>🎉 REFERRAL BONUS!</b>\n"
            welcome_msg += f"You joined using a referral link!\n\n"
        
        welcome_msg += (
            f"<b>🚀 {BOT_NAME}</b>\n"
            f"<b>📍 Version:</b> {BOT_VERSION}\n\n"
            f"<b>💰 YOUR CREDITS:</b>\n"
            f"🆓 <b>Daily:</b> <code>{daily_credits}</code>/{MAX_FREE_CREDITS} (resets at {RESET_HOUR}:00)\n"
            f"💎 <b>Extra:</b> <code>{extra_credits}</code> (permanent)\n"
            f"🎯 <b>Total:</b> <code>{total_credits}</code>\n\n"
            f"<b>📁 Files in DB:</b> <code>{stats['total_files']}</code>\n\n"
            f"<i>Use buttons to start</i>"
        )
        
        await update.message.reply_text(welcome_msg, parse_mode='HTML', reply_markup=reply_markup)
    
    async def search_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        if not self.credit_system.has_enough_credits(user_id):
            await update.message.reply_text(
                f"<b>❌ NO CREDITS</b>\n\n"
                f"Your daily credits reset at {RESET_HOUR}:00\n"
                f"Contact {BOT_OWNER} for extra credits.",
                parse_mode='HTML'
            )
            return ConversationHandler.END
        
        if not context.args:
            await update.message.reply_text(
                "<b>❌ Usage:</b> <code>/search domain.com</code>\n\n"
                "<b>Examples:</b>\n"
                "<code>/search gmail.com</code>\n"
                "<code>/search facebook.com</code>",
                parse_mode='HTML'
            )
            return ConversationHandler.END
        
        query = context.args[0].lower()
        self.pending_searches[user_id] = {"query": query}
        
        keyboard = [
            [
                InlineKeyboardButton("🔐 email:pass (extracted)", callback_data="format_emailpass"),
                InlineKeyboardButton("🔗 url:email:pass (full)", callback_data="format_urlemailpass")
            ],
            [InlineKeyboardButton("❌ Cancel", callback_data="format_cancel")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        daily_credits = self.credit_system.get_daily_credits_left(user_id)
        total_credits = self.credit_system.get_user_credits(user_id)
        
        await update.message.reply_text(
            f"<b>🔍 SEARCH DOMAIN</b>\n\n"
            f"<b>Domain:</b> <code>{self.escape_html(query)}</code>\n"
            f"<b>Daily credits:</b> <code>{daily_credits}</code>/{MAX_FREE_CREDITS}\n"
            f"<b>Total credits:</b> <code>{total_credits}</code>\n\n"
            f"<b>Select format:</b>",
            parse_mode='HTML',
            reply_markup=reply_markup
        )
        
        return CHOOSING_FORMAT
    
    async def format_selected_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        
        if user_id not in self.pending_searches:
            await query.edit_message_text("❌ Search expired.")
            return ConversationHandler.END
        
        if query.data == "format_cancel":
            await query.edit_message_text("✅ Canceled.")
            del self.pending_searches[user_id]
            return ConversationHandler.END
        
        search_data = self.pending_searches[user_id]
        domain = search_data["query"]
        selected_format = query.data
        
        await query.edit_message_text(f"🔄 <b>Searching {self.escape_html(domain)}...</b>", parse_mode='HTML')
        
        # Buscar TODOS los resultados SIN LÍMITE
        total_found, all_results = self.search_engine.search_domain(domain, max_results=None)
        
        if total_found == 0:
            await query.edit_message_text(
                f"<b>❌ NOT FOUND</b>\n\n"
                f"<b>Domain:</b> <code>{self.escape_html(domain)}</code>\n"
                f"<b>Files scanned:</b> <code>{self.search_engine.get_stats()['total_files']}</code>\n\n"
                f"💰 <b>Credit NOT consumed</b>",
                parse_mode='HTML'
            )
            del self.pending_searches[user_id]
            return ConversationHandler.END
        
        # FILTRAR según el formato seleccionado
        filtered_results = []
        
        for line in all_results:
            line = line.strip()
            if not line:
                continue
                
            if selected_format == "format_emailpass":
                # 🔥 EXTRACTO SOLO email:password de CUALQUIER formato
                parts = line.split(':')
                
                # Buscar el email (que contiene @) y la contraseña
                email = None
                password = None
                
                for i, part in enumerate(parts):
                    if '@' in part and '.' in part:  # Es un email
                        email = part
                        # La contraseña suele ser el siguiente campo
                        if i + 1 < len(parts):
                            password = parts[i + 1]
                        break
                
                # Si encontramos email y password, creamos línea email:pass
                if email and password:
                    filtered_results.append(f"{email}:{password}")
                    
            elif selected_format == "format_urlemailpass":
                # 🔥 LÍNEA COMPLETA ORIGINAL (url:email:pass o cualquier formato)
                # Solo verificamos que tenga al menos 2 ':' y que contenga @
                if line.count(':') >= 2 and '@' in line:
                    filtered_results.append(line)
        
        # Si no hay resultados después del filtro
        if not filtered_results:
            await query.edit_message_text(
                f"<b>❌ NO RESULTS IN SELECTED FORMAT</b>\n\n"
                f"<b>Domain:</b> <code>{self.escape_html(domain)}</code>\n"
                f"<b>Total found (all formats):</b> <code>{total_found}</code>\n"
                f"<b>Format selected:</b> {'email:pass (extracted)' if selected_format == 'format_emailpass' else 'url:email:pass (full line)'}\n"
                f"<b>Results in this format:</b> <code>0</code>\n\n"
                f"💰 <b>Credit NOT consumed</b>",
                parse_mode='HTML'
            )
            del self.pending_searches[user_id]
            return ConversationHandler.END
        
        # CONSUMIR CRÉDITO SOLO AHORA
        if not self.credit_system.use_credits(user_id, "domain", domain, len(filtered_results)):
            await query.edit_message_text("<b>❌ Error using credits</b>", parse_mode='HTML')
            del self.pending_searches[user_id]
            return ConversationHandler.END
        
        total_credits = self.credit_system.get_user_credits(user_id)
        daily_credits = self.credit_system.get_daily_credits_left(user_id)
        
        # SIEMPRE ARCHIVO
        if len(filtered_results) < 5000:
            await self.send_results_as_txt(
                query, 
                filtered_results, 
                domain, 
                len(filtered_results), 
                daily_credits, 
                total_credits,
                selected_format
            )
        else:
            await self.send_results_as_zip(
                query, 
                filtered_results, 
                domain, 
                len(filtered_results), 
                daily_credits, 
                total_credits,
                selected_format
            )
        
        del self.pending_searches[user_id]
        return ConversationHandler.END
    
    async def send_results_as_txt(self, query_callback, results: list, domain: str, total_found: int, 
                                  daily_credits: int, total_credits: int, selected_format: str):
        """Siempre envía como archivo .txt"""
        txt_buffer = io.BytesIO()
        content = "\n".join(results)
        txt_buffer.write(content.encode('utf-8'))
        txt_buffer.seek(0)
        
        if selected_format == "format_emailpass":
            format_name = "email_pass_extracted"
            format_display = "email:password (extracted)"
        else:
            format_name = "url_email_pass_full"
            format_display = "url:email:password (full line)"
        
        await query_callback.message.reply_document(
            document=txt_buffer,
            filename=f"ulp_{domain}_{format_name}_{total_found}.txt",
            caption=(
                f"<b>📁 RESULTS (TXT FILE)</b>\n\n"
                f"<b>Domain:</b> <code>{self.escape_html(domain)}</code>\n"
                f"<b>Format:</b> <code>{format_display}</code>\n"
                f"<b>Results:</b> <code>{total_found}</code>\n"
                f"<b>Daily credits left:</b> <code>{daily_credits}</code>\n"
                f"<b>Total credits:</b> <code>{total_credits}</code>\n\n"
                f"<i>✓ Results delivered as .txt file</i>"
            ),
            parse_mode='HTML'
        )
        
        await query_callback.edit_message_text(
            f"<b>✅ SEARCH COMPLETED</b>\n\n"
            f"<b>Domain:</b> <code>{self.escape_html(domain)}</code>\n"
            f"<b>Format:</b> <code>{format_display}</code>\n"
            f"<b>Results:</b> <code>{total_found}</code>\n"
            f"<b>Daily credits left:</b> <code>{daily_credits}</code>\n"
            f"<b>Total credits:</b> <code>{total_credits}</code>\n\n"
            f"<i>📎 Results sent as .txt file</i>",
            parse_mode='HTML'
        )
    
    async def send_results_as_zip(self, query_callback, results: list, domain: str, total_found: int,
                                  daily_credits: int, total_credits: int, selected_format: str):
        """Divide en partes de 5000 líneas y comprime"""
        zip_buffer = io.BytesIO()
        
        if selected_format == "format_emailpass":
            format_name = "email_pass_extracted"
            format_display = "email:password (extracted)"
        else:
            format_name = "url_email_pass_full"
            format_display = "url:email:password (full line)"
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            chunk_size = 5000
            total_parts = (len(results) + chunk_size - 1) // chunk_size
            
            for i in range(0, len(results), chunk_size):
                chunk = results[i:i + chunk_size]
                content = "\n".join(chunk)
                part_num = i // chunk_size + 1
                filename = f"ulp_{domain}_{format_name}_part{part_num}_of_{total_parts}.txt"
                zip_file.writestr(filename, content)
        
        zip_buffer.seek(0)
        
        await query_callback.message.reply_document(
            document=zip_buffer,
            filename=f"ulp_{domain}_{format_name}_{total_found}.zip",
            caption=(
                f"<b>📦 RESULTS (ZIP FILE)</b>\n\n"
                f"<b>Domain:</b> <code>{self.escape_html(domain)}</code>\n"
                f"<b>Format:</b> <code>{format_display}</code>\n"
                f"<b>Results:</b> <code>{total_found}</code>\n"
                f"<b>Parts:</b> <code>{total_parts}</code> files\n"
                f"<b>Daily credits left:</b> <code>{daily_credits}</code>\n"
                f"<b>Total credits:</b> <code>{total_credits}</code>\n\n"
                f"<i>📎 Results sent as .zip file ({total_found} lines)</i>"
            ),
            parse_mode='HTML'
        )
        
        await query_callback.edit_message_text(
            f"<b>✅ SEARCH COMPLETED</b>\n\n"
            f"<b>Domain:</b> <code>{self.escape_html(domain)}</code>\n"
            f"<b>Format:</b> <code>{format_display}</code>\n"
            f"<b>Results:</b> <code>{total_found}</code>\n"
            f"<b>Daily credits left:</b> <code>{daily_credits}</code>\n"
            f"<b>Total credits:</b> <code>{total_credits}</code>\n\n"
            f"<i>📦 Results sent as .zip file (split into {total_parts} parts)</i>",
            parse_mode='HTML'
        )
    
    async def email_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        if not self.credit_system.has_enough_credits(user_id):
            await update.message.reply_text(
                f"<b>❌ NO CREDITS</b>\n\n"
                f"Your daily credits reset at {RESET_HOUR}:00",
                parse_mode='HTML'
            )
            return
        
        if not context.args:
            await update.message.reply_text(
                "<b>❌ Usage:</b> <code>/email user@gmail.com</code>",
                parse_mode='HTML'
            )
            return
        
        email = context.args[0].lower()
        msg = await update.message.reply_text(f"📧 <b>Searching {self.escape_html(email)}...</b>", parse_mode='HTML')
        
        total_found, results = self.search_engine.search_email(email, max_results=None)
        
        if total_found == 0:
            await msg.edit_text(
                f"<b>❌ NOT FOUND</b>\n\n"
                f"<b>Email:</b> <code>{self.escape_html(email)}</code>",
                parse_mode='HTML'
            )
            return
        
        if not self.credit_system.use_credits(user_id, "email", email, total_found):
            await msg.edit_text("<b>❌ Error using credits</b>", parse_mode='HTML')
            return
        
        total_credits = self.credit_system.get_user_credits(user_id)
        daily_credits = self.credit_system.get_daily_credits_left(user_id)
        
        # Siempre archivo
        txt_buffer = io.BytesIO()
        txt_buffer.write("\n".join(results).encode('utf-8'))
        txt_buffer.seek(0)
        
        await msg.reply_document(
            document=txt_buffer,
            filename=f"ulp_email_{email}_{total_found}.txt",
            caption=(
                f"<b>📁 EMAIL RESULTS</b>\n\n"
                f"<b>Email:</b> <code>{self.escape_html(email)}</code>\n"
                f"<b>Results:</b> <code>{total_found}</code>\n"
                f"<b>Daily credits left:</b> <code>{daily_credits}</code>\n"
                f"<b>Total credits:</b> <code>{total_credits}</code>"
            ),
            parse_mode='HTML'
        )
        
        await msg.edit_text(f"<b>✅ Email search completed</b>", parse_mode='HTML')
    
    async def login_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        if not self.credit_system.has_enough_credits(user_id):
            await update.message.reply_text(
                f"<b>❌ NO CREDITS</b>\n\n"
                f"Your daily credits reset at {RESET_HOUR}:00",
                parse_mode='HTML'
            )
            return
        
        if not context.args:
            await update.message.reply_text(
                "<b>❌ Usage:</b> <code>/login username</code>",
                parse_mode='HTML'
            )
            return
        
        login = context.args[0].lower()
        msg = await update.message.reply_text(f"👤 <b>Searching {self.escape_html(login)}...</b>", parse_mode='HTML')
        
        total_found, results = self.search_engine.search_login(login, max_results=None)
        
        if total_found == 0:
            await msg.edit_text(
                f"<b>❌ NOT FOUND</b>\n\n"
                f"<b>Login:</b> <code>{self.escape_html(login)}</code>",
                parse_mode='HTML'
            )
            return
        
        if not self.credit_system.use_credits(user_id, "login", login, total_found):
            await msg.edit_text("<b>❌ Error using credits</b>", parse_mode='HTML')
            return
        
        total_credits = self.credit_system.get_user_credits(user_id)
        daily_credits = self.credit_system.get_daily_credits_left(user_id)
        
        txt_buffer = io.BytesIO()
        txt_buffer.write("\n".join(results).encode('utf-8'))
        txt_buffer.seek(0)
        
        await msg.reply_document(
            document=txt_buffer,
            filename=f"ulp_login_{login}_{total_found}.txt",
            caption=(
                f"<b>📁 LOGIN RESULTS</b>\n\n"
                f"<b>Login:</b> <code>{self.escape_html(login)}</code>\n"
                f"<b>Results:</b> <code>{total_found}</code>\n"
                f"<b>Daily credits left:</b> <code>{daily_credits}</code>\n"
                f"<b>Total credits:</b> <code>{total_credits}</code>"
            ),
            parse_mode='HTML'
        )
        
        await msg.edit_text(f"<b>✅ Login search completed</b>", parse_mode='HTML')
    
    async def pass_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        if not self.credit_system.has_enough_credits(user_id):
            await update.message.reply_text(
                f"<b>❌ NO CREDITS</b>\n\n"
                f"Your daily credits reset at {RESET_HOUR}:00",
                parse_mode='HTML'
            )
            return
        
        if not context.args:
            await update.message.reply_text(
                "<b>❌ Usage:</b> <code>/pass password123</code>",
                parse_mode='HTML'
            )
            return
        
        password = context.args[0].lower()
        msg = await update.message.reply_text(f"🔑 <b>Searching password...</b>", parse_mode='HTML')
        
        total_found, results = self.search_engine.search_password(password, max_results=None)
        
        if total_found == 0:
            await msg.edit_text(
                f"<b>❌ NOT FOUND</b>\n\n"
                f"<b>Password:</b> <code>********</code>",
                parse_mode='HTML'
            )
            return
        
        if not self.credit_system.use_credits(user_id, "password", password, total_found):
            await msg.edit_text("<b>❌ Error using credits</b>", parse_mode='HTML')
            return
        
        total_credits = self.credit_system.get_user_credits(user_id)
        daily_credits = self.credit_system.get_daily_credits_left(user_id)
        
        txt_buffer = io.BytesIO()
        txt_buffer.write("\n".join(results).encode('utf-8'))
        txt_buffer.seek(0)
        
        await msg.reply_document(
            document=txt_buffer,
            filename=f"ulp_password_search_{total_found}.txt",
            caption=(
                f"<b>📁 PASSWORD RESULTS</b>\n\n"
                f"<b>Password searched:</b> <code>********</code>\n"
                f"<b>Results:</b> <code>{total_found}</code>\n"
                f"<b>Daily credits left:</b> <code>{daily_credits}</code>\n"
                f"<b>Total credits:</b> <code>{total_credits}</code>"
            ),
            parse_mode='HTML'
        )
        
        await msg.edit_text(f"<b>✅ Password search completed</b>", parse_mode='HTML')
    
    async def dni_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Busca DNI:password por número de DNI o por dominio"""
        user_id = update.effective_user.id
        
        if not self.credit_system.has_enough_credits(user_id):
            await update.message.reply_text(
                f"<b>❌ NO CREDITS</b>\n\n"
                f"Your daily credits reset at {RESET_HOUR}:00",
                parse_mode='HTML'
            )
            return
        
        if not context.args:
            await update.message.reply_text(
                "<b>❌ Usage:</b>\n"
                "<code>/dni 12345678A</code> - Search by DNI number\n"
                "<code>/dni dominio.com</code> - Search DNI:pass by domain\n\n"
                "<b>Examples:</b>\n"
                "<code>/dni 12345678A</code>\n"
                "<code>/dni gmail.com</code>",
                parse_mode='HTML'
            )
            return
        
        query = context.args[0].upper()
        msg = await update.message.reply_text(f"🆔 <b>Searching DNI combos: {self.escape_html(query)}...</b>", parse_mode='HTML')
        
        # Detectar si es un DNI (8 números + letra) o un dominio
        dni_pattern = r'^[0-9]{8}[A-Z]$'
        
        if re.match(dni_pattern, query):
            # Búsqueda por número de DNI
            total_found, results = self.search_engine.search_dni(query, max_results=None)
            search_type = "dni_number"
            search_display = f"DNI: {query}"
        else:
            # Búsqueda por dominio
            total_found, results = self.search_engine.search_dni_by_domain(query.lower(), max_results=None)
            search_type = "dni_domain"
            search_display = f"Domain: {query.lower()}"
        
        if total_found == 0:
            await msg.edit_text(
                f"<b>❌ NOT FOUND</b>\n\n"
                f"<b>{search_display}</b>\n"
                f"<b>No DNI:password combos found</b>",
                parse_mode='HTML'
            )
            return
        
        if not self.credit_system.use_credits(user_id, "dni", query, total_found):
            await msg.edit_text("<b>❌ Error using credits</b>", parse_mode='HTML')
            return
        
        total_credits = self.credit_system.get_user_credits(user_id)
        daily_credits = self.credit_system.get_daily_credits_left(user_id)
        
        # Siempre archivo
        if total_found < 5000:
            txt_buffer = io.BytesIO()
            content = "\n".join(results)
            txt_buffer.write(content.encode('utf-8'))
            txt_buffer.seek(0)
            
            filename = f"ulp_dni_{query}_{total_found}.txt" if search_type == "dni_number" else f"ulp_dni_domain_{query}_{total_found}.txt"
            
            await msg.reply_document(
                document=txt_buffer,
                filename=filename,
                caption=(
                    f"<b>📁 DNI:PASSWORD RESULTS</b>\n\n"
                    f"<b>{search_display}</b>\n"
                    f"<b>Results:</b> <code>{total_found}</code>\n"
                    f"<b>Format:</b> <code>DNI:password</code>\n"
                    f"<b>Daily credits left:</b> <code>{daily_credits}</code>\n"
                    f"<b>Total credits:</b> <code>{total_credits}</code>"
                ),
                parse_mode='HTML'
            )
        else:
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                chunk_size = 5000
                total_parts = (len(results) + chunk_size - 1) // chunk_size
                
                for i in range(0, len(results), chunk_size):
                    chunk = results[i:i + chunk_size]
                    content = "\n".join(chunk)
                    part_num = i // chunk_size + 1
                    
                    if search_type == "dni_number":
                        filename = f"ulp_dni_{query}_part{part_num}_of_{total_parts}.txt"
                    else:
                        filename = f"ulp_dni_domain_{query}_part{part_num}_of_{total_parts}.txt"
                    
                    zip_file.writestr(filename, content)
            
            zip_buffer.seek(0)
            
            zip_filename = f"ulp_dni_{query}_{total_found}.zip" if search_type == "dni_number" else f"ulp_dni_domain_{query}_{total_found}.zip"
            
            await msg.reply_document(
                document=zip_buffer,
                filename=zip_filename,
                caption=(
                    f"<b>📦 DNI:PASSWORD RESULTS (ZIP)</b>\n\n"
                    f"<b>{search_display}</b>\n"
                    f"<b>Results:</b> <code>{total_found}</code>\n"
                    f"<b>Parts:</b> <code>{total_parts}</code> files\n"
                    f"<b>Format:</b> <code>DNI:password</code>\n"
                    f"<b>Daily credits left:</b> <code>{daily_credits}</code>\n"
                    f"<b>Total credits:</b> <code>{total_credits}</code>"
                ),
                parse_mode='HTML'
            )
        
        await msg.edit_text(f"<b>✅ DNI search completed</b>", parse_mode='HTML')
    
    async def mycredits_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        total_credits = self.credit_system.get_user_credits(user_id)
        daily_credits = self.credit_system.get_daily_credits_left(user_id)
        extra_credits = total_credits - daily_credits
        user_info = self.credit_system.get_user_info(user_id)
        
        now = datetime.now()
        reset_time = time(hour=RESET_HOUR, minute=0, second=0)
        
        if now.time() < reset_time:
            next_reset = datetime.combine(now.date(), reset_time)
        else:
            next_reset = datetime.combine(now.date() + timedelta(days=1), reset_time)
        
        hours_to_reset = (next_reset - now).seconds // 3600
        minutes_to_reset = ((next_reset - now).seconds % 3600) // 60
        
        response = (
            f"<b>💰 YOUR CREDITS</b>\n\n"
            f"👤 <b>User:</b> @{update.effective_user.username or update.effective_user.first_name}\n"
            f"🆔 <b>ID:</b> <code>{user_id}</code>\n\n"
            f"<b>💳 AVAILABLE CREDITS:</b>\n"
            f"🆓 <b>Daily:</b> <code>{daily_credits}</code>/{MAX_FREE_CREDITS}\n"
            f"💎 <b>Extra:</b> <code>{extra_credits}</code>\n"
            f"🎯 <b>Total:</b> <code>{total_credits}</code>\n\n"
            f"<b>⏰ NEXT RESET:</b>\n"
            f"🔄 <b>Time:</b> {RESET_HOUR}:00\n"
            f"⏳ <b>Time left:</b> {hours_to_reset}h {minutes_to_reset}m\n\n"
            f"<b>📊 STATISTICS:</b>\n"
            f"🔍 <b>Total searches:</b> <code>{user_info.get('total_searches', 0) if user_info else 0}</code>\n\n"
            f"<b>💡 INFORMATION:</b>\n"
            f"• Daily credits reset at {RESET_HOUR}:00\n"
            f"• Extra credits are permanent\n"
            f"• Contact {BOT_OWNER} for extra credits"
        )
        
        await update.message.reply_text(response, parse_mode='HTML')
    
    async def mystats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        user_info = self.credit_system.get_user_info(user_id)
        referral_stats = self.credit_system.get_referral_stats(user_id)
        
        if not user_info:
            await update.message.reply_text("❌ User not found")
            return
        
        total_credits = self.credit_system.get_user_credits(user_id)
        daily_credits = self.credit_system.get_daily_credits_left(user_id)
        extra_credits = total_credits - daily_credits
        
        referrals_count = referral_stats.get('referrals_count', 0) if referral_stats else 0
        total_referred = referral_stats.get('total_referred', 0) if referral_stats else 0
        
        response = (
            f"<b>📊 YOUR STATISTICS</b>\n\n"
            f"👤 <b>User:</b> @{update.effective_user.username or update.effective_user.first_name}\n"
            f"🆔 <b>ID:</b> <code>{user_id}</code>\n"
            f"📅 <b>Join date:</b> {user_info.get('join_date', 'N/A')}\n\n"
            
            f"<b>💰 CREDITS:</b>\n"
            f"🆓 <b>Daily:</b> <code>{daily_credits}</code>/{MAX_FREE_CREDITS}\n"
            f"💎 <b>Extra:</b> <code>{extra_credits}</code>\n"
            f"🎯 <b>Total:</b> <code>{total_credits}</code>\n\n"
            
            f"<b>🔍 SEARCHES:</b>\n"
            f"📈 <b>Total searches:</b> <code>{user_info.get('total_searches', 0)}</code>\n\n"
            
            f"<b>👥 REFERRALS:</b>\n"
            f"🤝 <b>Referrals made:</b> <code>{referrals_count}</code>\n"
            f"👥 <b>Total referred:</b> <code>{total_referred}</code>\n"
            f"🎁 <b>Bonus per referral:</b> <code>+{REFERRAL_BONUS}</code> credits\n\n"
            
            f"<i>Use /referral to get your referral link!</i>"
        )
        
        await update.message.reply_text(response, parse_mode='HTML')
    
    async def referral_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        referral_stats = self.credit_system.get_referral_stats(user_id)
        referral_link = self.credit_system.get_referral_link(user_id)
        
        if not referral_stats:
            await update.message.reply_text("❌ Error getting referral information")
            return
        
        referrals_count = referral_stats.get('referrals_count', 0)
        referral_code = referral_stats.get('referral_code', 'N/A')
        
        response = (
            f"<b>🤝 REFERRAL SYSTEM</b>\n\n"
            f"<b>🎁 HOW IT WORKS:</b>\n"
            f"• Share your referral link with friends\n"
            f"• When they join using your link:\n"
            f"  → You get: <b>+{REFERRAL_BONUS} credits</b>\n"
            f"  → They get: <b>{MAX_FREE_CREDITS} daily credits</b>\n\n"
            
            f"<b>📊 YOUR STATS:</b>\n"
            f"👥 <b>Referrals made:</b> <code>{referrals_count}</code>\n"
            f"💰 <b>Total earned:</b> <code>{referrals_count * REFERRAL_BONUS}</code> credits\n"
            f"🔑 <b>Your code:</b> <code>{referral_code}</code>\n\n"
            
            f"<b>🔗 YOUR REFERRAL LINK:</b>\n"
            f"<code>{referral_link}</code>\n\n"
            
            f"<b>📝 HOW TO SHARE:</b>\n"
            f"1. Copy the link above\n"
            f"2. Share it with friends\n"
            f"3. Earn credits when they join!\n\n"
            
            f"<i>Credits are added automatically when they use /start</i>"
        )
        
        keyboard = [
            [InlineKeyboardButton("📋 Copy Link", callback_data="copy_referral")],
            [InlineKeyboardButton("💰 My Credits", callback_data="menu_credits")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(response, parse_mode='HTML', reply_markup=reply_markup)
    
    async def price_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        response = (
            f"<b>💰 PRICE INFORMATION</b>\n\n"
            f"<b>🎯 FREE SYSTEM:</b>\n"
            f"🆓 <b>{MAX_FREE_CREDITS} free daily credits</b>\n"
            f"🔄 <b>Resets at:</b> {RESET_HOUR}:00\n"
            f"👥 <b>Referral bonus:</b> +{REFERRAL_BONUS} credits per friend\n\n"
            
            f"<b>💎 EXTRA CREDITS:</b>\n"
            f"• Contact {BOT_OWNER} for extra credits\n"
            f"• Extra credits are permanent\n"
            f"• They don't reset daily\n\n"
            
            f"<b>📊 CREDIT VALUES:</b>\n"
            f"🔍 <b>1 credit</b> = <b>1 search</b>\n"
            f"📁 <b>Results delivery:</b>\n"
            f"  • <5000 results → .txt file\n"
            f"  • ≥5000 results → .zip file (split into parts)\n\n"
            
            f"<b>💡 TIPS:</b>\n"
            f"• Use specific terms for better results\n"
            f"• Invite friends to earn free credits\n"
            f"• Contact {BOT_OWNER} for more credits\n\n"
            
            f"<i>Bot developed by {BOT_OWNER}</i>"
        )
        
        keyboard = [
            [InlineKeyboardButton("👥 Referral System", callback_data="menu_referral")],
            [InlineKeyboardButton("💰 My Credits", callback_data="menu_credits")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(response, parse_mode='HTML', reply_markup=reply_markup)
    
    async def info_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        response = (
            f"<b>📚 {BOT_NAME} - INFORMATION</b>\n\n"
            f"<b>🚀 VERSION:</b> {BOT_VERSION}\n"
            f"<b>👑 OWNER:</b> {BOT_OWNER}\n\n"
            
            f"<b>🔍 WHAT WE DO:</b>\n"
            f"• Search credentials by domain\n"
            f"• Search by email, login, password\n"
            f"• Search DNI:password combos (by DNI number or domain)\n"
            f"• Local database with millions of records\n\n"
            
            f"<b>💰 CREDIT SYSTEM:</b>\n"
            f"• {MAX_FREE_CREDITS} free daily credits\n"
            f"• Referral system: +{REFERRAL_BONUS} credits\n"
            f"• Extra credits available\n"
            f"• 1 credit = 1 search\n\n"
            
            f"<b>📁 DATA FORMATS:</b>\n"
            f"• email:password\n"
            f"• url:email:password\n"
            f"• login:password\n"
            f"• DNI:password\n\n"
            
            f"<b>📁 RESULTS DELIVERY:</b>\n"
            f"• ALL results are delivered as files\n"
            f"• <5000 results → .txt file\n"
            f"• ≥5000 results → .zip file (split)\n\n"
            
            f"<i>For support contact {BOT_OWNER}</i>"
        )
        
        await update.message.reply_text(response, parse_mode='HTML')
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        help_text = (
            f"<b>📚 {BOT_NAME} - COMPLETE HELP</b>\n\n"
            
            f"<b>🎯 FREE SYSTEM:</b>\n"
            f"• Max {MAX_FREE_CREDITS} free credits\n"
            f"• 1 credit = 1 search\n"
            f"• Invite friends: +{REFERRAL_BONUS} credit per referral\n\n"
            
            f"<b>🔍 SEARCH COMMANDS:</b>\n"
            f"<code>/search domain.com</code> - Search by domain\n"
            f"  • email:pass (extracted) - SOLO email:password\n"
            f"  • url:email:pass (full) - Línea completa\n"
            f"<code>/email user@gmail.com</code> - Search by email\n"
            f"<code>/login username</code> - Search by login\n"
            f"<code>/pass password123</code> - Search by password\n"
            f"<code>/dni 12345678A</code> - Search DNI:password by DNI number\n"
            f"<code>/dni dominio.com</code> - Search DNI:password by domain\n\n"
            
            f"<b>💰 PERSONAL COMMANDS:</b>\n"
            f"<code>/mycredits</code> - View your credits\n"
            f"<code>/mystats</code> - Your statistics\n"
            f"<code>/referral</code> - Your referral link\n"
            f"<code>/price</code> - Price information\n\n"
            
            f"<b>📊 INFORMATION:</b>\n"
            f"<code>/info</code> - Bot information\n"
            f"<code>/help</code> - This help\n\n"
            
            f"<b>👑 ADMIN COMMANDS:</b>\n"
            f"<code>/addcredits</code> - Add credits\n"
            f"<code>/userinfo</code> - User information\n"
            f"<code>/stats</code> - Statistics\n"
            f"<code>/userslist</code> - List users\n"
            f"<code>/broadcast</code> - Send to all\n"
            f"<code>/upload</code> - Upload ULP file\n\n"
            
            f"<b>📁 RESULTS DELIVERY:</b>\n"
            f"• <5000 results → .txt file\n"
            f"• ≥5000 results → .zip file (split into parts)\n"
            f"• NO results shown in message\n\n"
            
            f"<b>💡 TIPS:</b>\n"
            f"• Use specific terms for better results\n"
            f"• Invite friends to earn free credits\n"
            f"• Contact {BOT_OWNER} for more credits\n\n"
            
            f"<i>Bot developed by {BOT_OWNER}</i>"
        )
        
        await update.message.reply_text(help_text, parse_mode='HTML')
    
    # ==================== ADMIN ====================
    
    async def addcredits_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        if user_id not in ADMIN_IDS:
            await update.message.reply_text("❌ Admins only.")
            return
        
        if len(context.args) < 2:
            await update.message.reply_text(
                "<b>❌ Usage:</b> <code>/addcredits user_id amount [daily/extra]</code>\n\n"
                "<b>Examples:</b>\n"
                "<code>/addcredits 123456789 5 daily</code>\n"
                "<code>/addcredits 123456789 10 extra</code>\n\n"
                "<b>Note:</b> 'daily' credits reset at midnight, 'extra' are permanent (default).",
                parse_mode='HTML'
            )
            return
        
        try:
            target_user = int(context.args[0])
            amount = int(context.args[1])
            credit_type = context.args[2] if len(context.args) > 2 else "extra"
            
            if credit_type not in ['daily', 'extra']:
                credit_type = 'extra'
            
            success, message = self.credit_system.add_credits_to_user(target_user, amount, user_id, credit_type)
            
            if success:
                await update.message.reply_text(
                    f"<b>✅ CREDITS ADDED</b>\n\n"
                    f"<b>User:</b> <code>{target_user}</code>\n"
                    f"<b>Amount:</b> <code>{amount}</code> {credit_type} credits\n"
                    f"<b>Type:</b> {'🆓 Daily (will reset)' if credit_type == 'daily' else '💎 Extra (permanent)'}\n"
                    f"<b>Admin:</b> @{update.effective_user.username}",
                    parse_mode='HTML'
                )
            else:
                await update.message.reply_text(f"❌ {message}")
                
        except ValueError:
            await update.message.reply_text("❌ Error: Invalid ID or amount")
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {str(e)}")
    
    async def userinfo_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        if user_id not in ADMIN_IDS:
            await update.message.reply_text("❌ Admins only.")
            return
        
        if not context.args:
            await update.message.reply_text(
                "<b>❌ Usage:</b> <code>/userinfo user_id</code>\n"
                "<b>Example:</b> <code>/userinfo 123456789</code>",
                parse_mode='HTML'
            )
            return
        
        try:
            target_user = int(context.args[0])
            user_info = self.credit_system.get_user_info(target_user)
            
            if not user_info:
                await update.message.reply_text("❌ User not found")
                return
            
            total_credits = user_info['daily_credits'] + user_info['extra_credits']
            referral_stats = self.credit_system.get_referral_stats(target_user)
            referrals_count = referral_stats.get('referrals_count', 0) if referral_stats else 0
            
            response = (
                f"<b>👤 USER INFORMATION</b>\n\n"
                f"<b>Basic Info:</b>\n"
                f"🆔 <b>ID:</b> <code>{user_info['user_id']}</code>\n"
                f"👤 <b>Username:</b> @{user_info['username'] or 'N/A'}\n"
                f"📛 <b>Name:</b> {user_info['first_name'] or 'N/A'}\n"
                f"📅 <b>Join date:</b> {user_info['join_date']}\n"
                f"🔄 <b>Last reset:</b> {user_info.get('last_reset', 'N/A')}\n\n"
                
                f"<b>💰 Credits:</b>\n"
                f"🆓 <b>Daily:</b> <code>{user_info['daily_credits']}</code>\n"
                f"💎 <b>Extra:</b> <code>{user_info['extra_credits']}</code>\n"
                f"🎯 <b>Total:</b> <code>{total_credits}</code>\n\n"
                
                f"<b>🔍 Activity:</b>\n"
                f"📈 <b>Searches:</b> <code>{user_info['total_searches']}</code>\n"
                f"👥 <b>Referrals:</b> <code>{referrals_count}</code>\n"
                f"🔑 <b>Referral code:</b> <code>{user_info.get('referral_code', 'N/A')}</code>\n"
                f"🤝 <b>Referred by:</b> <code>{user_info.get('referred_by', 'No one')}</code>\n\n"
                
                f"<b>💡 Admin Actions:</b>\n"
                f"Add credits: <code>/addcredits {target_user} 10</code>"
            )
            
            await update.message.reply_text(response, parse_mode='HTML')
            
        except ValueError:
            await update.message.reply_text("❌ Error: Invalid user ID")
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {str(e)}")
    
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        if user_id not in ADMIN_IDS:
            await update.message.reply_text("❌ Admins only.")
            return
        
        bot_stats = self.credit_system.get_bot_stats()
        engine_stats = self.search_engine.get_stats()
        
        response = (
            f"<b>📊 BOT STATISTICS</b>\n\n"
            f"👥 <b>Users:</b> <code>{bot_stats['total_users']}</code>\n"
            f"🔍 <b>Total searches:</b> <code>{bot_stats['total_searches']}</code>\n"
            f"💰 <b>Total credits:</b> <code>{bot_stats['total_credits']}</code>\n"
            f"👥 <b>Total referrals:</b> <code>{bot_stats.get('total_referrals', 0)}</code>\n"
            f"📢 <b>Total broadcasts:</b> <code>{bot_stats.get('total_broadcasts', 0)}</code>\n"
            f"📁 <b>Files in DB:</b> <code>{engine_stats['total_files']}</code>\n"
            f"🔄 <b>Daily reset:</b> {RESET_HOUR}:00\n\n"
            f"🤖 <b>Version:</b> {BOT_VERSION}\n"
            f"👑 <b>Admin:</b> @{update.effective_user.username}"
        )
        
        await update.message.reply_text(response, parse_mode='HTML')
    
    async def userslist_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        if user_id not in ADMIN_IDS:
            await update.message.reply_text("❌ Admins only.")
            return
        
        users = self.credit_system.get_all_users(limit=20)
        
        if not users:
            await update.message.reply_text("📭 No registered users.")
            return
        
        response = "<b>📋 REGISTERED USERS</b>\n\n"
        
        for i, user in enumerate(users, 1):
            username = f"@{user['username']}" if user['username'] else user['first_name']
            daily = user['daily_credits']
            extra = user['extra_credits']
            searches = user['total_searches']
            response += f"{i}. {self.escape_html(username)} (<code>{user['user_id']}</code>) - 🆓{daily} 💎{extra} 🔍{searches}\n"
        
        await update.message.reply_text(response, parse_mode='HTML')
    
    async def broadcast_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        if user_id not in ADMIN_IDS:
            await update.message.reply_text("❌ Admins only.")
            return
        
        await update.message.reply_text(
            "📢 <b>BROADCAST MESSAGE</b>\n\n"
            "Send the message you want to broadcast to all users.\n"
            "You can use HTML formatting.\n\n"
            "Type /cancel to cancel.",
            parse_mode='HTML'
        )
        
        return BROADCAST_MESSAGE
    
    async def broadcast_message_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        if user_id not in ADMIN_IDS:
            await update.message.reply_text("❌ Admins only.")
            return ConversationHandler.END
        
        message_text = update.message.text
        users = self.credit_system.get_all_users_for_broadcast()
        total_users = len(users)
        
        if total_users == 0:
            await update.message.reply_text("❌ No users to broadcast to.")
            return ConversationHandler.END
        
        msg = await update.message.reply_text(
            f"📢 <b>STARTING BROADCAST</b>\n\n"
            f"<b>Message:</b> {message_text[:100]}...\n"
            f"<b>To users:</b> <code>{total_users}</code>\n\n"
            f"🔄 <i>Sending...</i>",
            parse_mode='HTML'
        )
        
        sent_count = 0
        failed_count = 0
        
        for user in users:
            try:
                await context.bot.send_message(
                    chat_id=user,
                    text=message_text,
                    parse_mode='HTML'
                )
                sent_count += 1
                
                if sent_count % 10 == 0:
                    await msg.edit_text(
                        f"📢 <b>BROADCAST IN PROGRESS</b>\n\n"
                        f"✅ <b>Sent:</b> <code>{sent_count}</code>\n"
                        f"❌ <b>Failed:</b> <code>{failed_count}</code>\n"
                        f"📊 <b>Total:</b> <code>{total_users}</code>\n\n"
                        f"🔄 <i>Sending...</i>",
                        parse_mode='HTML'
                    )
                    await asyncio.sleep(0.5)
                    
            except Exception as e:
                failed_count += 1
                logger.error(f"Failed to send to {user}: {e}")
        
        self.credit_system.save_broadcast(user_id, message_text, sent_count, failed_count)
        
        await msg.edit_text(
            f"📢 <b>BROADCAST COMPLETED</b>\n\n"
            f"<b>Message sent:</b> {message_text[:100]}...\n\n"
            f"✅ <b>Successfully sent:</b> <code>{sent_count}</code>\n"
            f"❌ <b>Failed:</b> <code>{failed_count}</code>\n"
            f"📊 <b>Total users:</b> <code>{total_users}</code>\n\n"
            f"📈 <b>Success rate:</b> <code>{round((sent_count/total_users)*100, 2)}%</code>\n\n"
            f"✅ <i>Broadcast saved to database</i>",
            parse_mode='HTML'
        )
        
        return ConversationHandler.END
    
    async def cancel_broadcast(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("❌ Broadcast cancelled.")
        return ConversationHandler.END
    
    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        if user_id not in ADMIN_IDS:
            await update.message.reply_text("❌ Admins only can upload files.")
            return
        
        document = update.message.document
        
        if not document.file_name.endswith('.txt'):
            await update.message.reply_text("❌ Only .txt files")
            return
        
        msg = await update.message.reply_text(f"📤 <b>Processing {self.escape_html(document.file_name)}...</b>", parse_mode='HTML')
        
        try:
            file = await document.get_file()
            temp_path = os.path.join(UPLOAD_DIR, document.file_name)
            await file.download_to_drive(temp_path)
            
            success, result = self.search_engine.add_data_file(temp_path)
            
            if success:
                stats = self.search_engine.get_stats()
                await msg.edit_text(
                    f"<b>✅ FILE PROCESSED</b>\n\n"
                    f"<b>Name:</b> <code>{self.escape_html(document.file_name)}</code>\n"
                    f"<b>Total files:</b> <code>{stats['total_files']}</code>\n\n"
                    f"✅ <i>Ready for searches</i>",
                    parse_mode='HTML'
                )
            else:
                await msg.edit_text(
                    f"<b>❌ ERROR</b>\n\n"
                    f"<b>File:</b> <code>{self.escape_html(document.file_name)}</code>\n"
                    f"<b>Error:</b> {result}",
                    parse_mode='HTML'
                )
        
        except Exception as e:
            await msg.edit_text(
                f"<b>❌ CRITICAL ERROR</b>\n\n"
                f"Error: {self.escape_html(str(e)[:200])}",
                parse_mode='HTML'
            )
    
    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        
        if query.data == "menu_search":
            await query.edit_message_text(
                "<b>🔍 SEARCH DOMAIN</b>\n\n"
                "Send: <code>/search domain.com</code>\n\n"
                "<b>Examples:</b>\n"
                "<code>/search gmail.com</code>\n"
                "<code>/search facebook.com</code>",
                parse_mode='HTML'
            )
        
        elif query.data == "menu_email":
            await query.edit_message_text(
                "<b>📧 SEARCH EMAIL</b>\n\n"
                "Send: <code>/email user@gmail.com</code>",
                parse_mode='HTML'
            )
        
        elif query.data == "menu_credits":
            total_credits = self.credit_system.get_user_credits(user_id)
            daily_credits = self.credit_system.get_daily_credits_left(user_id)
            await query.edit_message_text(
                f"<b>💰 YOUR CREDITS</b>\n\n"
                f"🆓 <b>Daily:</b> <code>{daily_credits}</code>/{MAX_FREE_CREDITS}\n"
                f"🎯 <b>Total:</b> <code>{total_credits}</code>\n\n"
                f"<i>Use /mycredits for details</i>",
                parse_mode='HTML'
            )
        
        elif query.data == "menu_referral":
            await self.referral_command(update, context)
        
        elif query.data == "menu_help":
            await self.help_command(update, context)
        
        elif query.data == "copy_referral":
            referral_link = self.credit_system.get_referral_link(user_id)
            await query.answer(f"Link copied: {referral_link}", show_alert=False)
        
        elif query.data == "menu_admin":
            if user_id not in ADMIN_IDS:
                await query.edit_message_text("❌ Admins only.")
                return
            
            keyboard = [
                [InlineKeyboardButton("📊 Statistics", callback_data="admin_stats")],
                [InlineKeyboardButton("📋 List Users", callback_data="admin_users")],
                [InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")],
                [InlineKeyboardButton("📤 Upload File", callback_data="admin_upload")],
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                "<b>👑 ADMIN PANEL</b>\n\n"
                "<i>Select an option:</i>",
                parse_mode='HTML',
                reply_markup=reply_markup
            )
        
        elif query.data == "admin_stats":
            await self.stats_command(update, context)
        
        elif query.data == "admin_users":
            await self.userslist_command(update, context)
        
        elif query.data == "admin_broadcast":
            await update.callback_query.message.reply_text(
                "📢 <b>BROADCAST</b>\n\n"
                "Use the command: <code>/broadcast</code>\n\n"
                "Then type the message you want to send to all users.",
                parse_mode='HTML'
            )
        
        elif query.data == "admin_upload":
            await query.edit_message_text(
                "<b>📤 UPLOAD FILE</b>\n\n"
                "To upload a file:\n"
                "1. Send a .txt file\n"
                "2. Format: email:pass, url:email:pass, login:pass, DNI:pass\n"
                "3. Max 50MB\n\n"
                "File will be indexed automatically.",
                parse_mode='HTML'
            )

# ============================================================================
# MAIN EXECUTION
# ============================================================================

def run_flask():
    app.run(host='0.0.0.0', port=PORT, threaded=True)

def main():
    logger.info(f"🚀 Starting {BOT_NAME} v{BOT_VERSION}")
    
    search_engine = SearchEngine()
    credit_system = CreditSystem()
    bot = ULPBot(search_engine, credit_system)
    
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Search handlers
    search_conv = ConversationHandler(
        entry_points=[CommandHandler('search', bot.search_command)],
        states={
            CHOOSING_FORMAT: [
                CallbackQueryHandler(bot.format_selected_handler, pattern='^format_')
            ]
        },
        fallbacks=[CommandHandler('cancel', lambda u, c: ConversationHandler.END)],
        per_message=False
    )
    
    # Broadcast handlers
    broadcast_conv = ConversationHandler(
        entry_points=[CommandHandler('broadcast', bot.broadcast_command)],
        states={
            BROADCAST_MESSAGE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, bot.broadcast_message_handler)
            ]
        },
        fallbacks=[CommandHandler('cancel', bot.cancel_broadcast)]
    )
    
    # Basic commands
    application.add_handler(CommandHandler("start", bot.start))
    application.add_handler(CommandHandler("help", bot.help_command))
    application.add_handler(CommandHandler("info", bot.info_command))
    application.add_handler(CommandHandler("mycredits", bot.mycredits_command))
    application.add_handler(CommandHandler("mystats", bot.mystats_command))
    application.add_handler(CommandHandler("referral", bot.referral_command))
    application.add_handler(CommandHandler("price", bot.price_command))
    application.add_handler(search_conv)
    application.add_handler(CommandHandler("email", bot.email_command))
    application.add_handler(CommandHandler("login", bot.login_command))
    application.add_handler(CommandHandler("pass", bot.pass_command))
    application.add_handler(CommandHandler("dni", bot.dni_command))
    
    # Admin commands
    application.add_handler(CommandHandler("addcredits", bot.addcredits_command))
    application.add_handler(CommandHandler("userinfo", bot.userinfo_command))
    application.add_handler(CommandHandler("stats", bot.stats_command))
    application.add_handler(CommandHandler("userslist", bot.userslist_command))
    application.add_handler(broadcast_conv)
    application.add_handler(MessageHandler(filters.Document.ALL, bot.handle_document))
    
    # Button handlers
    application.add_handler(CallbackQueryHandler(bot.button_handler, pattern='^menu_'))
    application.add_handler(CallbackQueryHandler(bot.button_handler, pattern='^admin_'))
    application.add_handler(CallbackQueryHandler(bot.button_handler, pattern='^copy_'))
    
    # Start Flask
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info(f"🌐 Flask on port {PORT}")
    
    # Start bot
    logger.info("🤖 Bot started")
    application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

if __name__ == '__main__':
    main()
