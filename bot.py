"""
🔍 ULP Searcher Bot - COMPLETE ENGLISH VERSION
With Large File Upload (NO SIZE LIMITS) - Owner: @ibericowner
"""

import os
import logging
import sqlite3
import threading
import io
import zipfile
import random
import asyncio
import hashlib
import shutil
import time
import tempfile
import glob
import re
import json
from datetime import datetime, time as dt_time, timedelta
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor

from flask import Flask, request, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    ContextTypes, CallbackQueryHandler, filters,
    ConversationHandler, JobQueue
)

# ============================================================================
# CONFIGURATION - NO SIZE LIMITS
# ============================================================================

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
ADMIN_IDS = [int(id.strip()) for id in os.getenv('ADMIN_IDS', '').split(',') if id.strip()]
BOT_OWNER = "@ibericowner"
BOT_NAME = "🔍 ULP Searcher Bot"
BOT_VERSION = "8.0 NO LIMITS"
MAX_FREE_CREDITS = 2
RESET_HOUR = 0

# Referral system
REFERRAL_BONUS = 1

# ⚠️ NO SIZE LIMITS - Telegram will reject if too big
MAX_UPLOAD_SIZE = 100 * 1024 * 1024 * 1024  # 100GB (basically ignore)
CHUNK_SIZE = 100 * 1024 * 1024
ALLOWED_EXTENSIONS = ['.txt', '.zip', '.7z', '.rar', '.gz', '.tar']
COMPRESSED_EXTENSIONS = ['.zip', '.7z', '.rar', '.gz', '.tar']

PORT = int(os.getenv('PORT', 10000))

BASE_DIR = "bot_data"
DATA_DIR = os.path.join(BASE_DIR, "ulp_files")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
UPLOAD_TEMP_DIR = os.path.join(BASE_DIR, "temp_uploads")
PROCESSING_DIR = os.path.join(BASE_DIR, "processing")
CACHE_DIR = os.path.join(BASE_DIR, "cache")
DB_PATH = os.path.join(BASE_DIR, "bot.db")

for directory in [BASE_DIR, DATA_DIR, UPLOAD_DIR, UPLOAD_TEMP_DIR, PROCESSING_DIR, CACHE_DIR]:
    os.makedirs(directory, exist_ok=True)

CHOOSING_FORMAT = 0

thread_executor = ThreadPoolExecutor(max_workers=4)
process_executor = ProcessPoolExecutor(max_workers=2)

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
# DATABASE INITIALIZATION
# ============================================================================

def init_database():
    with sqlite3.connect(DB_PATH) as conn:
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
            CREATE TABLE IF NOT EXISTS uploaded_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT,
                file_hash TEXT UNIQUE,
                file_size INTEGER,
                upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                processed BOOLEAN DEFAULT FALSE,
                lines_count INTEGER DEFAULT 0,
                processing_time INTEGER,
                uploaded_by INTEGER,
                status TEXT DEFAULT 'pending'
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS broadcasts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_id INTEGER,
                message TEXT,
                sent_to INTEGER DEFAULT 0,
                failed_to INTEGER DEFAULT 0,
                sent_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
    
    logger.info("✅ Database initialized")

# ============================================================================
# SEARCH ENGINE WITH DNI DOMAIN SEARCH
# ============================================================================

class SearchEngine:
    def __init__(self, data_dir: str = DATA_DIR):
        self.data_dir = data_dir
        self.data_files = []
        self.load_all_data()
    
    def load_all_data(self):
        self.data_files = glob.glob(os.path.join(self.data_dir, "*.txt"))
        logger.info(f"📂 Loaded {len(self.data_files)} files")
    
    def search_domain(self, domain: str, max_results: int = 10000) -> Tuple[int, List[str]]:
        results = []
        domain_lower = domain.lower()
        
        for file_path in self.data_files:
            if len(results) >= max_results:
                break
            
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        
                        if domain_lower in line.lower():
                            results.append(line)
                        
                        if len(results) >= max_results:
                            break
            
            except Exception as e:
                logger.error(f"Error in {file_path}: {e}")
                continue
        
        return len(results), results
    
    def search_email(self, email: str, max_results: int = 5000) -> Tuple[int, List[str]]:
        results = []
        email_lower = email.lower()
        
        for file_path in self.data_files:
            if len(results) >= max_results:
                break
            
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        
                        if email_lower in line.lower():
                            results.append(line)
                        
                        if len(results) >= max_results:
                            break
            
            except Exception as e:
                logger.error(f"Error in {file_path}: {e}")
                continue
        
        return len(results), results
    
    def search_login(self, login: str, max_results: int = 5000) -> Tuple[int, List[str]]:
        results = []
        login_lower = login.lower()
        
        for file_path in self.data_files:
            if len(results) >= max_results:
                break
            
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
                        
                        if len(results) >= max_results:
                            break
            
            except Exception as e:
                logger.error(f"Error in {file_path}: {e}")
                continue
        
        return len(results), results
    
    def search_password(self, password: str, max_results: int = 5000) -> Tuple[int, List[str]]:
        results = []
        password_lower = password.lower()
        
        for file_path in self.data_files:
            if len(results) >= max_results:
                break
            
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        
                        if password_lower in line.lower():
                            results.append(line)
                        
                        if len(results) >= max_results:
                            break
            
            except Exception as e:
                logger.error(f"Error in {file_path}: {e}")
                continue
        
        return len(results), results
    
    def search_dni_in_domain(self, domain: str, max_results: int = 10000) -> Tuple[int, List[str]]:
        results = []
        domain_lower = domain.lower()
        
        for file_path in self.data_files:
            if len(results) >= max_results:
                break
            
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        
                        if domain_lower in line.lower():
                            dni_pattern = r'\b\d{7,8}[A-Z]?\b'
                            if re.search(dni_pattern, line):
                                if ':' in line:
                                    results.append(line)
                        
                        if len(results) >= max_results:
                            break
            
            except Exception as e:
                logger.error(f"Error in {file_path}: {e}")
                continue
        
        return len(results), results
    
    def get_stats(self) -> Dict:
        total_size = 0
        for file_path in self.data_files:
            try:
                total_size += os.path.getsize(file_path)
            except:
                pass
        
        return {
            "total_files": len(self.data_files),
            "total_size_gb": total_size / (1024**3),
            "recent_files": []
        }
    
    def add_data_file(self, file_path: str) -> Tuple[bool, str]:
        try:
            timestamp = int(time.time())
            filename = os.path.basename(file_path)
            unique_filename = f"{timestamp}_{filename}"
            dest_path = os.path.join(self.data_dir, unique_filename)
            
            shutil.copy2(file_path, dest_path)
            self.load_all_data()
            return True, unique_filename
        except Exception as e:
            return False, str(e)

# ============================================================================
# CREDIT SYSTEM WITH AUTO-CREATE USERS
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
        pass
    
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
                last_reset_str = result['last_reset']
                today = datetime.now().date()
                
                try:
                    last_reset = datetime.strptime(last_reset_str, '%Y-%m-%d').date()
                except:
                    last_reset = today
                
                if last_reset != today:
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
            
            # AUTO-CREATE USER IF NOT EXISTS
            cursor.execute('SELECT user_id FROM users WHERE user_id = ?', (user_id,))
            result = cursor.fetchone()
            
            if not result:
                # Create user automatically
                referral_code = self.generate_referral_code(user_id)
                cursor.execute('''
                    INSERT INTO users 
                    (user_id, daily_credits, referral_code, last_reset)
                    VALUES (?, 2, ?, DATE('now'))
                ''', (user_id, referral_code))
                
                cursor.execute('''
                    INSERT INTO transactions (user_id, amount, type, description)
                    VALUES (?, ?, ?, ?)
                ''', (user_id, 2, 'daily_reset', 'Auto-created by admin'))
                
                conn.commit()
            
            # Now add credits
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
            
            cursor.execute('SELECT SUM(referrals_count) as total FROM users')
            stats['total_referrals'] = cursor.fetchone()['total'] or 0
            
            return stats

# ============================================================================
# LARGE FILE PROCESSOR
# ============================================================================

class LargeFileProcessor:
    def __init__(self):
        self.processing_tasks = {}
    
    def calculate_file_hash(self, file_path: str) -> str:
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    
    def process_large_txt_file(self, file_path: str, output_dir: str) -> dict:
        stats = {
            'lines_processed': 0,
            'valid_lines': 0,
            'errors': 0,
            'output_file': None
        }
        
        try:
            file_size = os.path.getsize(file_path)
            output_file = os.path.join(output_dir, "processed.txt")
            
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as infile, \
                 open(output_file, 'w', encoding='utf-8') as outfile:
                
                chunk_size = 100000
                chunk = []
                
                for line in infile:
                    line = line.strip()
                    if not line:
                        continue
                    
                    chunk.append(line)
                    stats['lines_processed'] += 1
                    
                    if len(chunk) >= chunk_size:
                        for chunk_line in chunk:
                            if ':' in chunk_line and len(chunk_line) > 3:
                                outfile.write(chunk_line + '\n')
                                stats['valid_lines'] += 1
                        chunk = []
                
                for chunk_line in chunk:
                    if ':' in chunk_line and len(chunk_line) > 3:
                        outfile.write(chunk_line + '\n')
                        stats['valid_lines'] += 1
            
            stats['output_file'] = output_file
            logger.info(f"Processed file: {stats['lines_processed']} lines, {stats['valid_lines']} valid")
            
            return stats
        
        except Exception as e:
            logger.error(f"Error processing large file: {e}")
            stats['errors'] += 1
            return stats
    
    def process_compressed_file(self, file_path: str, output_dir: str) -> str:
        import zipfile
        import tarfile
        import gzip
        
        file_ext = os.path.splitext(file_path)[1].lower()
        extracted_dir = os.path.join(output_dir, "extracted")
        os.makedirs(extracted_dir, exist_ok=True)
        
        try:
            if file_ext == '.zip':
                with zipfile.ZipFile(file_path, 'r') as zip_ref:
                    zip_ref.extractall(extracted_dir)
            elif file_ext == '.tar':
                with tarfile.open(file_path, 'r') as tar_ref:
                    tar_ref.extractall(extracted_dir)
            elif file_ext == '.gz':
                with gzip.open(file_path, 'rb') as gz_ref:
                    with open(os.path.join(extracted_dir, "extracted.txt"), 'wb') as out_ref:
                        out_ref.write(gz_ref.read())
            else:
                logger.error(f"Unsupported compressed format: {file_ext}")
                return None
            
            txt_files = []
            for root, dirs, files in os.walk(extracted_dir):
                for file in files:
                    if file.endswith('.txt'):
                        txt_files.append(os.path.join(root, file))
            
            if txt_files:
                combined_file = os.path.join(output_dir, "combined.txt")
                with open(combined_file, 'w', encoding='utf-8') as outfile:
                    for txt_file in txt_files:
                        try:
                            with open(txt_file, 'r', encoding='utf-8', errors='ignore') as infile:
                                for line in infile:
                                    outfile.write(line)
                        except Exception as e:
                            logger.error(f"Error reading {txt_file}: {e}")
                            continue
                
                return combined_file
            
            return None
        
        except Exception as e:
            logger.error(f"Error processing compressed file: {e}")
            return None

# ============================================================================
# MAIN BOT CLASS
# ============================================================================

class ULPBot:
    def __init__(self, search_engine: SearchEngine, credit_system: CreditSystem):
        self.search_engine = search_engine
        self.credit_system = credit_system
        self.file_processor = LargeFileProcessor()
        self.pending_searches = {}
        self.active_uploads = {}
    
    async def upload_large_system(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Sistema de upload para archivos grandes (por partes)"""
        user_id = update.effective_user.id
        
        if user_id not in ADMIN_IDS:
            await update.message.reply_text("❌ Admins only.")
            return
        
        # Crear sesión de upload única
        upload_id = f"upload_{user_id}_{int(time.time())}"
        self.active_uploads[upload_id] = {
            'parts': [],
            'total_parts': 0,
            'original_filename': '',
            'start_time': time.time(),
            'user_id': user_id
        }
        
        await update.message.reply_text(
            f"📦 <b>LARGE FILE UPLOAD SYSTEM</b>\n\n"
            f"<b>Upload ID:</b> <code>{upload_id}</code>\n\n"
            f"<b>📝 INSTRUCCIONES:</b>\n"
            f"1. <b>Divide tu archivo</b> en partes de 20MB\n"
            f"2. <b>Nombra las partes:</b> archivo.part001, archivo.part002, etc.\n"
            f"3. <b>Envía las partes</b> una por una al bot\n"
            f"4. <b>Cuando termines</b>, envía: <code>/finishupload {upload_id}</code>\n\n"
            f"<b>🔧 HERRAMIENTAS:</b>\n"
            f"• 7zip: <code>7z a -v20m archivo.7z tu_archivo.txt</code>\n"
            f"• WinRAR: Dividir en volúmenes\n"
            f"• HJSplit (Windows)\n\n"
            f"<i>El bot combinará las partes automáticamente</i>",
            parse_mode='HTML'
        )
    
    async def handle_file_part(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Manejar partes de archivos grandes"""
        user_id = update.effective_user.id
        
        if user_id not in ADMIN_IDS:
            await update.message.reply_text("❌ Admins only.")
            return
        
        if not update.message.document:
            return
        
        document = update.message.document
        filename = document.file_name
        
        # Verificar si es parte de archivo
        if '.part' in filename.lower() or filename.lower().endswith(('.001', '.002', '.003')):
            await self._process_file_part(update, document, filename, user_id)
        else:
            # Archivo normal - usar sistema antiguo
            await self.handle_large_file_upload(update, context)
    
    async def _process_file_part(self, update, document, filename, user_id):
        """Procesar una parte de archivo"""
        msg = await update.message.reply_text(f"📥 <b>Processing part: {filename}</b>", parse_mode='HTML')
        
        try:
            # Extraer nombre base y número de parte
            base_name = None
            part_num = None
            
            # Patrones: archivo.part001, archivo.001, archivo.r00, etc.
            patterns = [
                r'(.+)\.part(\d+)',  # archivo.part001
                r'(.+)\.(\d{3})$',   # archivo.001
                r'(.+)\.r(\d{2})$',  # archivo.r00 (rar)
                r'(.+)\.z(\d{2})$',  # archivo.z01 (zip)
            ]
            
            for pattern in patterns:
                match = re.search(pattern, filename.lower())
                if match:
                    base_name = match.group(1)
                    part_num = int(match.group(2))
                    break
            
            if not base_name or part_num is None:
                await msg.edit_text(f"❌ <b>Invalid part filename: {filename}</b>", parse_mode='HTML')
                return
            
            # Descargar parte
            file = await document.get_file()
            
            # Directorio para este upload
            upload_dir = os.path.join(UPLOAD_TEMP_DIR, f"multipart_{base_name}_{user_id}")
            os.makedirs(upload_dir, exist_ok=True)
            
            part_path = os.path.join(upload_dir, f"part_{part_num:03d}")
            await file.download_to_drive(part_path)
            
            # Actualizar registro de partes
            parts_file = os.path.join(upload_dir, "parts.json")
            parts_data = {}
            
            if os.path.exists(parts_file):
                with open(parts_file, 'r') as f:
                    parts_data = json.load(f)
            
            parts_data[str(part_num)] = {
                'filename': filename,
                'size': document.file_size,
                'downloaded': True,
                'path': part_path
            }
            
            with open(parts_file, 'w') as f:
                json.dump(parts_data, f)
            
            total_parts = len(parts_data)
            
            await msg.edit_text(
                f"✅ <b>PART RECEIVED</b>\n\n"
                f"<b>File:</b> {base_name}\n"
                f"<b>Part:</b> {filename} (#{part_num})\n"
                f"<b>Size:</b> {document.file_size/(1024*1024):.1f} MB\n"
                f"<b>Total parts received:</b> {total_parts}\n\n"
                f"<i>Send next part or finish with:</i>\n"
                f"<code>/finishupload {base_name}</code>",
                parse_mode='HTML'
            )
            
        except Exception as e:
            await msg.edit_text(f"❌ <b>Error:</b> {str(e)[:200]}", parse_mode='HTML')
    
    async def finish_upload_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Finalizar upload de partes y combinarlas"""
        user_id = update.effective_user.id
        
        if user_id not in ADMIN_IDS:
            await update.message.reply_text("❌ Admins only.")
            return
        
        if not context.args:
            await update.message.reply_text(
                "❌ <b>Usage:</b> <code>/finishupload base_name</code>\n\n"
                "<b>Example:</b> <code>/finishupload mydatabase</code>",
                parse_mode='HTML'
            )
            return
        
        base_name = context.args[0]
        upload_dir = os.path.join(UPLOAD_TEMP_DIR, f"multipart_{base_name}_{user_id}")
        
        if not os.path.exists(upload_dir):
            await update.message.reply_text(f"❌ No upload found for: {base_name}")
            return
        
        msg = await update.message.reply_text(f"🔄 <b>Combining parts for {base_name}...</b>", parse_mode='HTML')
        
        try:
            # Leer información de partes
            parts_file = os.path.join(upload_dir, "parts.json")
            if not os.path.exists(parts_file):
                await msg.edit_text("❌ No parts information found")
                return
            
            with open(parts_file, 'r') as f:
                parts_data = json.load(f)
            
            # Combinar partes en orden
            combined_file = os.path.join(upload_dir, f"{base_name}_combined.txt")
            
            with open(combined_file, 'wb') as outfile:
                for part_num in sorted([int(k) for k in parts_data.keys()]):
                    part_info = parts_data[str(part_num)]
                    part_path = part_info['path']
                    
                    if os.path.exists(part_path):
                        with open(part_path, 'rb') as infile:
                            shutil.copyfileobj(infile, outfile)
                        
                        await msg.edit_text(
                            f"🔄 <b>Combining part {part_num}/{len(parts_data)}...</b>\n"
                            f"<i>Processing {base_name}</i>",
                            parse_mode='HTML'
                        )
            
            # Procesar archivo combinado
            file_size = os.path.getsize(combined_file)
            
            await msg.edit_text(
                f"✅ <b>FILE COMBINED SUCCESSFULLY!</b>\n\n"
                f"<b>File:</b> {base_name}\n"
                f"<b>Total parts:</b> {len(parts_data)}\n"
                f"<b>Final size:</b> {file_size/(1024*1024):.2f} MB\n"
                f"<b>Status:</b> Processing combined file...",
                parse_mode='HTML'
            )
            
            # Procesar archivo combinado
            await self._process_upload_background(combined_file, f"{base_name}_combined.txt", user_id, msg)
            
            # Limpiar partes temporales
            try:
                shutil.rmtree(upload_dir)
            except:
                pass
            
        except Exception as e:
            await msg.edit_text(f"❌ <b>Error combining parts:</b> {str(e)[:200]}", parse_mode='HTML')
    
    async def split_help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Mostrar ayuda para dividir archivos"""
        user_id = update.effective_user.id
        
        if user_id not in ADMIN_IDS:
            await update.message.reply_text("❌ Admins only.")
            return
        
        help_text = """
📦 <b>HOW TO UPLOAD LARGE FILES (>20MB)</b>

🔧 <b>METHOD 1: Using 7zip (RECOMMENDED)</b>
<code>7z a -v20m database.7z your_file.txt</code>
• Creates: database.7z.001, database.7z.002, etc.
• Send each .00X file to bot

🔧 <b>METHOD 2: Using HJSplit (Windows)</b>
1. Download HJSplit: http://www.hjsplit.org/
2. Split file into 20MB parts
3. Send .001, .002, etc. to bot

🔧 <b>METHOD 3: Using split command (Linux/Mac)</b>
<code>split -b 20m large_file.txt large_file.part</code>
• Creates: large_file.partaa, large_file.partab, etc.

📝 <b>STEPS:</b>
1. Split your file into 20MB parts
2. Send parts one by one to bot
3. When finished: <code>/finishupload filename</code>

⚡ <b>BOT WILL:</b>
• Auto-detect part numbers
• Combine all parts
• Process as normal file
• Add to search database

💡 <b>TIP:</b> For 38MB file → 2 parts (20MB + 18MB)
"""
        
        await update.message.reply_text(help_text, parse_mode='HTML')
    
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
            f"<b>📁 Database Size:</b> <code>{stats['total_size_gb']:.2f}</code> GB\n"
            f"<b>📂 Files in DB:</b> <code>{stats['total_files']}</code>\n\n"
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
                InlineKeyboardButton("🔐 email:pass", callback_data="format_emailpass"),
                InlineKeyboardButton("🔗 url:email:pass", callback_data="format_urlemailpass")
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
        
        await query.edit_message_text(f"🔄 <b>Searching {self.escape_html(domain)}...</b>", parse_mode='HTML')
        
        total_found, results = self.search_engine.search_domain(domain)
        
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
        
        if not self.credit_system.use_credits(user_id, "domain", domain, total_found):
            await query.edit_message_text("<b>❌ Error using credits</b>", parse_mode='HTML')
            del self.pending_searches[user_id]
            return ConversationHandler.END
        
        total_credits = self.credit_system.get_user_credits(user_id)
        daily_credits = self.credit_system.get_daily_credits_left(user_id)
        
        if total_found > 100:
            await self.send_results_as_txt(query, results, domain, total_found, daily_credits, total_credits)
        else:
            await self.send_results_as_message(query, results, domain, total_found, daily_credits, total_credits)
        
        del self.pending_searches[user_id]
        return ConversationHandler.END
    
    async def send_results_as_txt(self, query_callback, results: list, domain: str, total_found: int, daily_credits: int, total_credits: int):
        txt_buffer = io.BytesIO()
        content = "\n".join(results)
        txt_buffer.write(content.encode('utf-8'))
        txt_buffer.seek(0)
        
        await query_callback.message.reply_document(
            document=txt_buffer,
            filename=f"ulp_{domain}.txt",
            caption=(
                f"<b>📁 RESULTS</b>\n\n"
                f"<b>Domain:</b> <code>{self.escape_html(domain)}</code>\n"
                f"<b>Results:</b> <code>{total_found}</code>\n"
                f"<b>Daily credits left:</b> <code>{daily_credits}</code>\n"
                f"<b>Total credits:</b> <code>{total_credits}</code>"
            ),
            parse_mode='HTML'
        )
        
        await query_callback.edit_message_text(
            f"<b>✅ SEARCH COMPLETED</b>\n\n"
            f"<b>Domain:</b> <code>{self.escape_html(domain)}</code>\n"
            f"<b>Results:</b> <code>{total_found}</code>\n"
            f"<b>Daily credits left:</b> <code>{daily_credits}</code>\n"
            f"<b>Total credits:</b> <code>{total_credits}</code>\n\n"
            f"<i>Results sent as file</i>",
            parse_mode='HTML'
        )
    
    async def send_results_as_message(self, query_callback, results: list, domain: str, total_found: int, daily_credits: int, total_credits: int):
        response = (
            f"<b>✅ SEARCH COMPLETED</b>\n\n"
            f"<b>Domain:</b> <code>{self.escape_html(domain)}</code>\n"
            f"<b>Results:</b> <code>{total_found}</code>\n"
            f"<b>Daily credits left:</b> <code>{daily_credits}</code>\n"
            f"<b>Total credits:</b> <code>{total_credits}</code>\n\n"
            f"<b>First results:</b>\n"
            f"<pre>"
        )
        
        for line in results[:10]:
            if len(line) > 80:
                line = line[:77] + "..."
            response += f"{self.escape_html(line)}\n"
        
        response += "</pre>"
        
        if total_found > 10:
            response += f"\n<b>... and {total_found-10} more results</b>"
        
        await query_callback.edit_message_text(response, parse_mode='HTML')
    
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
        
        total_found, results = self.search_engine.search_email(email)
        
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
        
        response = (
            f"<b>✅ EMAIL FOUND</b>\n\n"
            f"<b>Email:</b> <code>{self.escape_html(email)}</code>\n"
            f"<b>Results:</b> <code>{total_found}</code>\n"
            f"<b>Daily credits left:</b> <code>{daily_credits}</code>\n"
            f"<b>Total credits:</b> <code>{total_credits}</code>\n\n"
            f"<b>First results:</b>\n"
            f"<pre>"
        )
        
        for line in results[:5]:
            response += f"{self.escape_html(line)}\n"
        
        response += "</pre>"
        
        await msg.edit_text(response, parse_mode='HTML')
    
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
        
        total_found, results = self.search_engine.search_login(login)
        
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
        
        response = (
            f"<b>✅ LOGIN FOUND</b>\n\n"
            f"<b>Login:</b> <code>{self.escape_html(login)}</code>\n"
            f"<b>Results:</b> <code>{total_found}</code>\n"
            f"<b>Daily credits left:</b> <code>{daily_credits}</code>\n"
            f"<b>Total credits:</b> <code>{total_credits}</code>\n\n"
            f"<b>First results:</b>\n"
            f"<pre>"
        )
        
        for line in results[:5]:
            response += f"{self.escape_html(line)}\n"
        
        response += "</pre>"
        
        await msg.edit_text(response, parse_mode='HTML')
    
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
        
        total_found, results = self.search_engine.search_password(password)
        
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
        
        response = (
            f"<b>✅ PASSWORD FOUND</b>\n\n"
            f"<b>Password search:</b> <code>********</code>\n"
            f"<b>Results:</b> <code>{total_found}</code>\n"
            f"<b>Daily credits left:</b> <code>{daily_credits}</code>\n"
            f"<b>Total credits:</b> <code>{total_credits}</code>\n\n"
            f"<b>First results:</b>\n"
            f"<pre>"
        )
        
        for line in results[:5]:
            line = line.replace(password, "***" + password[-3:] if len(password) > 3 else "***")
            response += f"{self.escape_html(line)}\n"
        
        response += "</pre>"
        
        await msg.edit_text(response, parse_mode='HTML')
    
    async def dni_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
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
                "<b>❌ Usage:</b> <code>/dni domain.com</code>\n\n"
                "<b>Examples:</b>\n"
                "<code>/dni gmail.com</code> - Find Spanish DNI combos from gmail.com\n"
                "<code>/dni hotmail.com</code> - Find Spanish DNI combos from hotmail.com\n\n"
                "<b>⚠️ Note:</b> Searches for Spanish DNI format (8 digits + optional letter)",
                parse_mode='HTML'
            )
            return
        
        domain = context.args[0].lower().strip()
        msg = await update.message.reply_text(
            f"🔍 <b>Searching DNI combos in {self.escape_html(domain)}...</b>\n"
            f"<i>This may take a moment...</i>",
            parse_mode='HTML'
        )
        
        total_found, results = self.search_engine.search_dni_in_domain(domain)
        
        if total_found == 0:
            await msg.edit_text(
                f"<b>❌ NO DNI COMBOS FOUND</b>\n\n"
                f"<b>Domain:</b> <code>{self.escape_html(domain)}</code>\n"
                f"<b>Files scanned:</b> <code>{self.search_engine.get_stats()['total_files']}</code>\n\n"
                f"<i>No Spanish DNI combos found for this domain.</i>",
                parse_mode='HTML'
            )
            return
        
        if not self.credit_system.use_credits(user_id, "dni_domain", domain, total_found):
            await msg.edit_text("<b>❌ Error using credits</b>", parse_mode='HTML')
            return
        
        total_credits = self.credit_system.get_user_credits(user_id)
        daily_credits = self.credit_system.get_daily_credits_left(user_id)
        
        if total_found > 100:
            txt_buffer = io.BytesIO()
            content = "\n".join(results)
            txt_buffer.write(content.encode('utf-8'))
            txt_buffer.seek(0)
            
            filename = f"dni_combos_{domain.replace('.', '_')}.txt"
            
            await update.message.reply_document(
                document=txt_buffer,
                filename=filename,
                caption=(
                    f"<b>📁 DNI COMBOS FOUND</b>\n\n"
                    f"<b>Domain:</b> <code>{self.escape_html(domain)}</code>\n"
                    f"<b>Total DNI combos:</b> <code>{total_found}</code>\n"
                    f"<b>Daily credits left:</b> <code>{daily_credits}</code>\n"
                    f"<b>Total credits:</b> <code>{total_credits}</code>"
                ),
                parse_mode='HTML'
            )
            
            await msg.edit_text(
                f"<b>✅ DNI COMBOS FOUND</b>\n\n"
                f"<b>Domain:</b> <code>{self.escape_html(domain)}</code>\n"
                f"<b>Total DNI combos:</b> <code>{total_found}</code>\n"
                f"<b>Daily credits left:</b> <code>{daily_credits}</code>\n"
                f"<b>Total credits:</b> <code>{total_credits}</code>\n\n"
                f"<i>Results sent as file 📁</i>",
                parse_mode='HTML'
            )
        else:
            response = (
                f"<b>✅ DNI COMBOS FOUND</b>\n\n"
                f"<b>Domain:</b> <code>{self.escape_html(domain)}</code>\n"
                f"<b>Total DNI combos:</b> <code>{total_found}</code>\n"
                f"<b>Daily credits left:</b> <code>{daily_credits}</code>\n"
                f"<b>Total credits:</b> <code>{total_credits}</code>\n\n"
                f"<b>First {min(10, total_found)} combos:</b>\n"
                f"<pre>"
            )
            
            for line in results[:10]:
                if len(line) > 80:
                    line = line[:77] + "..."
                response += f"{self.escape_html(line)}\n"
            
            response += "</pre>"
            
            if total_found > 10:
                response += f"\n<b>... and {total_found-10} more DNI combos</b>"
            
            await msg.edit_text(response, parse_mode='HTML')
    
    async def mycredits_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        total_credits = self.credit_system.get_user_credits(user_id)
        daily_credits = self.credit_system.get_daily_credits_left(user_id)
        extra_credits = total_credits - daily_credits
        user_info = self.credit_system.get_user_info(user_id)
        
        now = datetime.now()
        reset_time = dt_time(hour=RESET_HOUR, minute=0, second=0)
        
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
            f"  • <100 results → In message\n"
            f"  • 100-10,000 → .txt file\n"
            f"  • >10,000 → .zip file\n\n"
            
            f"<b>🎁 SPECIAL OFFERS:</b>\n"
            f"• First-time users: {MAX_FREE_CREDITS} credits\n"
            f"• Active users: Bonus credits\n"
            f"• Bulk purchases: Discounts\n\n"
            
            f"<i>Contact {BOT_OWNER} for custom packages!</i>"
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
            f"<b>👑 OWNER:</b> {BOT_OWNER}\n"
            f"<b>📅 LAUNCHED:</b> 2024\n\n"
            
            f"<b>🔍 WHAT WE DO:</b>\n"
            f"• Search credentials by domain\n"
            f"• Search by email, login, password\n"
            f"• Search Spanish DNI combos by domain\n"
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
            f"• email only\n\n"
            
            f"<b>⚙️ TECHNOLOGY:</b>\n"
            f"• Local search engine\n"
            f"• Fast indexing\n"
            f"• Secure database\n"
            f"• 24/7 availability\n\n"
            
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
            f"<code>/email user@gmail.com</code> - Search by email\n"
            f"<code>/login username</code> - Search by login\n"
            f"<code>/pass password123</code> - Search by password\n"
            f"<code>/dni domain.com</code> - Search Spanish DNI combos from domain\n\n"
            
            f"<b>📋 FORMATS FOR /search:</b>\n"
            f"• email:password\n"
            f"• url:email:password\n"
            f"• login:password\n"
            f"• email only\n\n"
            
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
            f"<code>/broadcast</code> - Send to all users\n"
            f"<code>/upload</code> - Upload ULP file\n"
            f"<code>/uploadlarge</code> - Upload large files (part by part)\n"
            f"<code>/splithelp</code> - Help for splitting files\n\n"
            
            f"<b>📁 RESULTS DELIVERY:</b>\n"
            f"• <100 results → Message\n"
            f"• 100-10,000 → .txt file\n"
            f"• >10,000 → .zip file\n\n"
            
            f"<b>💡 TIPS:</b>\n"
            f"• Use specific terms for better results\n"
            f"• Invite friends to earn free credits\n"
            f"• Contact {BOT_OWNER} for more credits\n\n"
            
            f"<i>Bot developed by {BOT_OWNER}</i>"
        )
        
        await update.message.reply_text(help_text, parse_mode='HTML')
    
    # ==================== ADMIN COMMANDS ====================
    
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
        
        total_lines = 0
        for file_path in glob.glob(os.path.join(DATA_DIR, "*.txt")):
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    total_lines += sum(1 for _ in f)
            except:
                pass
        
        response = (
            f"<b>📊 BOT STATISTICS</b>\n\n"
            f"👥 <b>Users:</b> <code>{bot_stats['total_users']}</code>\n"
            f"🔍 <b>Total searches:</b> <code>{bot_stats['total_searches']}</code>\n"
            f"💰 <b>Total credits:</b> <code>{bot_stats['total_credits']}</code>\n"
            f"👥 <b>Total referrals:</b> <code>{bot_stats.get('total_referrals', 0)}</code>\n"
            f"📁 <b>Files in DB:</b> <code>{engine_stats['total_files']}</code>\n"
            f"📊 <b>Total lines:</b> <code>{total_lines:,}</code>\n"
            f"💾 <b>Database size:</b> <code>{engine_stats['total_size_gb']:.2f} GB</code>\n"
            f"🔄 <b>Daily reset:</b> {RESET_HOUR}:00\n\n"
            f"🤖 <b>Version:</b> {BOT_VERSION}\n"
            f"👑 <b>Owner:</b> {BOT_OWNER}"
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
        
        if not context.args:
            await update.message.reply_text(
                "<b>❌ Usage:</b> <code>/broadcast your message here</code>\n\n"
                "<b>Example:</b>\n"
                "<code>/broadcast New update available! Check /help</code>",
                parse_mode='HTML'
            )
            return
        
        message = " ".join(context.args)
        msg = await update.message.reply_text("📢 <b>Starting broadcast...</b>", parse_mode='HTML')
        
        users = self.credit_system.get_all_users(limit=1000)
        total_users = len(users)
        successful = 0
        failed = 0
        
        await msg.edit_text(f"📢 <b>Broadcasting to {total_users} users...</b>", parse_mode='HTML')
        
        for user in users:
            try:
                await context.bot.send_message(
                    chat_id=user['user_id'],
                    text=f"📢 <b>ANNOUNCEMENT FROM {BOT_OWNER}</b>\n\n{message}\n\n<i>Bot: {BOT_NAME}</i>",
                    parse_mode='HTML'
                )
                successful += 1
            except Exception as e:
                failed += 1
                logger.error(f"Failed to send to {user['user_id']}: {e}")
            
            if (successful + failed) % 10 == 0:
                await msg.edit_text(
                    f"📢 <b>Broadcast Progress:</b>\n"
                    f"✅ Sent: <code>{successful}</code>\n"
                    f"❌ Failed: <code>{failed}</code>\n"
                    f"📊 Total: <code>{successful + failed}/{total_users}</code>",
                    parse_mode='HTML'
                )
        
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO broadcasts (admin_id, message, sent_to, failed_to)
                VALUES (?, ?, ?, ?)
            ''', (user_id, message, successful, failed))
            conn.commit()
        
        await msg.edit_text(
            f"✅ <b>BROADCAST COMPLETED</b>\n\n"
            f"📊 <b>Statistics:</b>\n"
            f"✅ <b>Successful:</b> <code>{successful}</code>\n"
            f"❌ <b>Failed:</b> <code>{failed}</code>\n"
            f"👥 <b>Total users:</b> <code>{total_users}</code>\n\n"
            f"<i>Message saved to database.</i>",
            parse_mode='HTML'
        )
    
    async def handle_large_file_upload(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle file uploads - NO SIZE CHECK VERSION"""
        user_id = update.effective_user.id
        
        if user_id not in ADMIN_IDS:
            await update.message.reply_text("❌ Admins only.")
            return
        
        if not update.message.document:
            await update.message.reply_text(
                "<b>📤 UPLOAD FILES (NO SIZE LIMIT)</b>\n\n"
                "<b>⚠️ WARNING:</b> Telegram may reject very large files\n\n"
                "<b>Supported formats:</b>\n"
                "• .txt (text files)\n"
                "• .zip, .7z, .rar (compressed)\n\n"
                "<i>Send file directly to upload...</i>",
                parse_mode='HTML'
            )
            return
        
        document = update.message.document
        file_ext = os.path.splitext(document.file_name)[1].lower()
        
        if file_ext not in ALLOWED_EXTENSIONS:
            await update.message.reply_text(
                f"❌ Unsupported format: {file_ext}\n"
                f"✅ Supported: .txt, .zip, .7z, .rar, .gz, .tar"
            )
            return
        
        # NO SIZE CHECK - Telegram will fail if too big
        status_msg = await update.message.reply_text(
            f"📥 <b>ATTEMPTING UPLOAD...</b>\n\n"
            f"<b>File:</b> <code>{self.escape_html(document.file_name)}</code>\n"
            f"<b>Type:</b> {file_ext}\n"
            f"<i>Trying to download from Telegram...</i>",
            parse_mode='HTML'
        )
        
        try:
            # Try to download - Telegram will fail if file is too big
            file = await document.get_file()
            
            # Create temp directory
            upload_id = f"{user_id}_{int(time.time())}"
            temp_dir = os.path.join(UPLOAD_TEMP_DIR, upload_id)
            os.makedirs(temp_dir, exist_ok=True)
            
            temp_path = os.path.join(temp_dir, document.file_name)
            
            # Download file
            await file.download_to_drive(temp_path)
            
            actual_size = os.path.getsize(temp_path)
            
            await status_msg.edit_text(
                f"✅ <b>DOWNLOAD SUCCESSFUL!</b>\n\n"
                f"<b>File:</b> <code>{self.escape_html(document.file_name)}</code>\n"
                f"<b>Size:</b> {actual_size/(1024**2):.2f} MB\n"
                f"<b>Status:</b> Processing file...",
                parse_mode='HTML'
            )
            
            # Process file
            await self._process_upload_background(temp_path, document.file_name, user_id, status_msg)
            
        except Exception as e:
            error_msg = str(e)
            
            # Check if it's a size error from Telegram
            if "too big" in error_msg.lower() or "400" in error_msg or "413" in error_msg:
                await status_msg.edit_text(
                    f"❌ <b>TELEGRAM REJECTED FILE</b>\n\n"
                    f"<b>File:</b> <code>{self.escape_html(document.file_name)}</code>\n"
                    f"<b>Reason:</b> File too large for Telegram API\n\n"
                    f"<b>🔧 SOLUTIONS:</b>\n"
                    f"1. <b>Compress with 7zip</b> (38MB → ~4MB)\n"
                    f"2. <b>Split file</b> into smaller parts\n"
                    f"3. <b>Use .7z format</b> for better compression\n\n"
                    f"<i>Even if we ignore size check, Telegram API has limits!</i>",
                    parse_mode='HTML'
                )
            else:
                await status_msg.edit_text(
                    f"❌ <b>UPLOAD FAILED</b>\n\n"
                    f"<b>Error:</b> {error_msg[:200]}",
                    parse_mode='HTML'
                )
    
    async def _process_upload_background(self, file_path: str, filename: str, user_id: int, status_msg):
        """Process uploaded file in background"""
        
        def process_file():
            try:
                process_id = f"proc_{int(time.time())}"
                process_dir = os.path.join(PROCESSING_DIR, process_id)
                os.makedirs(process_dir, exist_ok=True)
                
                result = {
                    'filename': filename,
                    'original_size_mb': os.path.getsize(file_path) / (1024**2),
                    'processed_lines': 0,
                    'unique_lines': 0,
                    'processing_time': 0,
                    'output_file': None
                }
                
                start_time = time.time()
                file_ext = os.path.splitext(file_path)[1].lower()
                
                if file_ext in COMPRESSED_EXTENSIONS:
                    extracted_file = self.file_processor.process_compressed_file(file_path, process_dir)
                    if extracted_file:
                        stats = self.file_processor.process_large_txt_file(extracted_file, process_dir)
                        result.update(stats)
                        result['output_file'] = stats['output_file']
                    else:
                        raise Exception("Failed to extract compressed file")
                else:
                    stats = self.file_processor.process_large_txt_file(file_path, process_dir)
                    result.update(stats)
                    result['output_file'] = stats['output_file']
                
                if result['output_file'] and os.path.exists(result['output_file']):
                    final_filename = f"db_{int(time.time())}_{filename}"
                    final_path = os.path.join(DATA_DIR, final_filename)
                    shutil.move(result['output_file'], final_path)
                    
                    success, message = self.search_engine.add_data_file(final_path)
                    if not success:
                        raise Exception(f"Failed to add to search engine: {message}")
                    
                    result['final_path'] = final_path
                    result['processing_time'] = time.time() - start_time
                
                return result
            
            except Exception as e:
                logger.error(f"Background processing error: {e}")
                return {'error': str(e)}
            finally:
                try:
                    temp_dir = os.path.dirname(file_path)
                    if os.path.exists(temp_dir):
                        shutil.rmtree(temp_dir)
                except:
                    pass
        
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(thread_executor, process_file)
        
        if 'error' in result:
            await status_msg.edit_text(
                f"❌ <b>PROCESSING FAILED</b>\n\n"
                f"<b>File:</b> <code>{self.escape_html(filename)}</code>\n"
                f"<b>Error:</b> {result['error'][:200]}",
                parse_mode='HTML'
            )
        else:
            stats = self.search_engine.get_stats()
            await status_msg.edit_text(
                f"✅ <b>FILE PROCESSED SUCCESSFULLY</b>\n\n"
                f"<b>File:</b> <code>{self.escape_html(filename)}</code>\n"
                f"<b>Original size:</b> {result['original_size_mb']:.2f} MB\n"
                f"<b>Processing time:</b> {result['processing_time']:.1f} seconds\n"
                f"<b>Lines processed:</b> {result.get('lines_processed', 0):,}\n"
                f"<b>Valid lines added:</b> {result.get('valid_lines', 0):,}\n"
                f"<b>Total files in DB:</b> {stats['total_files']}\n"
                f"<b>Database size:</b> {stats['total_size_gb']:.2f} GB\n\n"
                f"<b>✅ Ready for searches!</b>",
                parse_mode='HTML'
            )
    
    async def upload_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show upload information"""
        user_id = update.effective_user.id
        
        if user_id not in ADMIN_IDS:
            await update.message.reply_text("❌ Admins only.")
            return
        
        stats = self.search_engine.get_stats()
        
        response = (
            f"<b>📤 FILE UPLOAD SYSTEM (NO SIZE LIMITS)</b>\n\n"
            f"<b>📁 Current Database:</b>\n"
            f"• Files: <code>{stats['total_files']}</code>\n"
            f"• Size: <code>{stats['total_size_gb']:.2f}</code> GB\n\n"
            
            f"<b>📦 Supported Formats:</b>\n"
            f"• .txt (plain text)\n"
            f"• .zip, .rar, .7z (compressed)\n\n"
            
            f"<b>⚠️ IMPORTANT:</b>\n"
            f"• Telegram API may reject files > 20MB\n"
            f"• Compress large files with 7zip\n"
            f"• Use .7z format for best compression\n\n"
            
            f"<b>📊 System Status:</b>\n"
        )
        
        try:
            total, used, free = shutil.disk_usage("/")
            response += f"• Free space: <code>{free/(1024**3):.1f}</code> GB\n"
        except:
            response += "• Disk space: Unknown\n"
        
        response += f"• Processing threads: <code>{thread_executor._max_workers}</code>\n\n"
        
        response += (
            f"<b>🚀 How to Upload:</b>\n"
            f"1. Send file directly to bot\n"
            f"2. Bot will try to download it\n"
            f"3. If Telegram rejects it, compress first\n\n"
            
            f"<i>Note: Only admins can upload files</i>"
        )
        
        await update.message.reply_text(response, parse_mode='HTML')
    
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
                [InlineKeyboardButton("📤 Upload File", callback_data="admin_upload")],
                [InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")],
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
        
        elif query.data == "admin_upload":
            await self.upload_command(update, context)
        
        elif query.data == "admin_broadcast":
            await query.edit_message_text(
                "<b>📢 BROADCAST MESSAGE</b>\n\n"
                "To send a message to all users:\n"
                "<code>/broadcast your message here</code>\n\n"
                "<b>Example:</b>\n"
                "<code>/broadcast New update available! Check /help for new features.</code>",
                parse_mode='HTML'
            )

# ============================================================================
# MAIN EXECUTION
# ============================================================================

def run_flask():
    app.run(host='0.0.0.0', port=PORT, threaded=True)

def main():
    logger.info(f"🚀 Starting {BOT_NAME} v{BOT_VERSION}")
    logger.info(f"👑 Owner: {BOT_OWNER}")
    logger.info(f"💰 Free credits: {MAX_FREE_CREDITS} (resets at {RESET_HOUR}:00)")
    logger.info(f"📁 NO SIZE LIMITS - Telegram API may reject large files")
    
    init_database()
    
    search_engine = SearchEngine()
    credit_system = CreditSystem()
    bot = ULPBot(search_engine, credit_system)
    
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    search_conv = ConversationHandler(
        entry_points=[CommandHandler('search', bot.search_command)],
        states={
            CHOOSING_FORMAT: [
                CallbackQueryHandler(bot.format_selected_handler, pattern='^format_')
            ]
        },
        fallbacks=[CommandHandler('cancel', lambda u, c: ConversationHandler.END)]
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
    application.add_handler(CommandHandler("uploadlarge", bot.upload_large_system))
    application.add_handler(CommandHandler("finishupload", bot.finish_upload_command))
    application.add_handler(CommandHandler("splithelp", bot.split_help_command))
    application.add_handler(MessageHandler(filters.Document.ALL, bot.handle_file_part))
    
    # Admin commands
    application.add_handler(CommandHandler("addcredits", bot.addcredits_command))
    application.add_handler(CommandHandler("userinfo", bot.userinfo_command))
    application.add_handler(CommandHandler("stats", bot.stats_command))
    application.add_handler(CommandHandler("userslist", bot.userslist_command))
    application.add_handler(CommandHandler("broadcast", bot.broadcast_command))
    application.add_handler(CommandHandler("upload", bot.upload_command))
    
    # File upload handler
    application.add_handler(MessageHandler(filters.Document.ALL, bot.handle_large_file_upload))
    
    # Button handlers
    application.add_handler(CallbackQueryHandler(bot.button_handler, pattern='^menu_'))
    application.add_handler(CallbackQueryHandler(bot.button_handler, pattern='^admin_'))
    application.add_handler(CallbackQueryHandler(bot.button_handler, pattern='^copy_'))
    application.add_handler(CallbackQueryHandler(bot.button_handler, pattern='^format_'))
    
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info(f"🌐 Flask server running on port {PORT}")
    
    logger.info("🤖 Bot started and ready")
    application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

if __name__ == '__main__':
    main()
