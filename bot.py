"""
ULP Searcher Bot - Versión COMPLETA
Con todos los comandos, sistema de créditos, administración y motor local
"""

import os
import re
import json
import logging
import sqlite3
import threading
import time
import io
import zipfile
import hashlib
import csv
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Set
from pathlib import Path
import glob
import random

from flask import Flask, request, jsonify
from telegram import (
    Update, InlineKeyboardButton, 
    InlineKeyboardMarkup, ReplyKeyboardMarkup,
    ReplyKeyboardRemove, Document
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    ContextTypes, CallbackQueryHandler, filters,
    ConversationHandler
)

# ============================================================================
# CONFIGURACIÓN
# ============================================================================

# OBTENER EN RENDER.COM:
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', 'TU_TOKEN_BOTFATHER')
ADMIN_IDS = [int(id.strip()) for id in os.getenv('ADMIN_IDS', 'TU_ID_TELEGRAM').split(',') if id.strip()]
SECRET_KEY = os.getenv('SECRET_KEY', 'clave_secreta_ulp_bot_2024')

# INFORMACIÓN DEL BOT
BOT_OWNER = "@iberic_owner"
BOT_NAME = "🔍 ULP Searcher Bot"
BOT_VERSION = "3.0 COMPLETA"
MAX_FREE_CREDITS = 2

# CONFIGURACIÓN TÉCNICA
PORT = int(os.getenv('PORT', 10000))
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

# DIRECTORIOS
BASE_DIR = "bot_data"
DATA_DIR = os.path.join(BASE_DIR, "ulp_files")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
BACKUP_DIR = os.path.join(BASE_DIR, "backups")
DB_PATH = os.path.join(BASE_DIR, "bot.db")

# Crear directorios
for directory in [BASE_DIR, DATA_DIR, UPLOAD_DIR, BACKUP_DIR]:
    os.makedirs(directory, exist_ok=True)

# ESTADOS CONVERSACIÓN
CHOOSING_FORMAT, WAITING_DNI, ADMIN_ADD_CREDITS = range(3)

# ============================================================================
# LOGGING PROFESIONAL
# ============================================================================

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(BASE_DIR, 'bot.log'), encoding='utf-8', mode='a')
    ]
)
logger = logging.getLogger(__name__)

# ============================================================================
# FLASK APP CON MÁS ENDPOINTS
# ============================================================================

app = Flask(__name__)
app.secret_key = SECRET_KEY

@app.route('/')
def home():
    return jsonify({
        "status": "online",
        "bot": BOT_NAME,
        "version": BOT_VERSION,
        "owner": BOT_OWNER,
        "mode": "LOCAL_ENGINE",
        "timestamp": datetime.now().isoformat()
    })

@app.route('/health')
def health():
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "ULP Telegram Bot"
    })

# API para administración remota
@app.route('/api/admin', methods=['POST'])
def admin_api():
    """API para administración remota"""
    try:
        data = request.json
        token = request.headers.get('Authorization')
        
        if token != f"Bearer {SECRET_KEY}":
            return jsonify({"error": "Unauthorized"}), 401
        
        action = data.get('action')
        
        if action == 'stats':
            # Obtener estadísticas
            return jsonify({
                "status": "ok",
                "bot": BOT_NAME,
                "version": BOT_VERSION
            })
        
        return jsonify({"error": "Invalid action"}), 400
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ============================================================================
# MOTOR DE BÚSQUEDA LOCAL AVANZADO
# ============================================================================

class AdvancedSearchEngine:
    """Motor de búsqueda avanzado con indexación"""
    
    def __init__(self, data_dir: str = DATA_DIR):
        self.data_dir = data_dir
        self.data_files: List[str] = []
        self.domain_index: Dict[str, List[Tuple[str, int]]] = {}  # dominio -> [(archivo, línea)]
        self.email_index: Dict[str, List[Tuple[str, int]]] = {}   # email -> [(archivo, línea)]
        self.load_all_data()
    
    def load_all_data(self):
        """Cargar y indexar todos los archivos"""
        self.data_files = glob.glob(os.path.join(self.data_dir, "*.txt"))
        self.domain_index.clear()
        self.email_index.clear()
        
        total_lines = 0
        indexed_lines = 0
        
        logger.info(f"📂 Iniciando indexación de {len(self.data_files)} archivos...")
        
        for file_idx, file_path in enumerate(self.data_files, 1):
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    for line_num, line in enumerate(f, 1):
                        line = line.strip()
                        if not line:
                            continue
                        
                        total_lines += 1
                        
                        # Indexar por dominio
                        if ':' in line:
                            parts = line.split(':')
                            if len(parts) >= 1:
                                domain = parts[0].lower()
                                if '.' in domain:  # Verificar que es un dominio
                                    if domain not in self.domain_index:
                                        self.domain_index[domain] = []
                                    self.domain_index[domain].append((file_path, line_num))
                                    indexed_lines += 1
                            
                            # Indexar por email
                            if len(parts) >= 2 and '@' in parts[1]:
                                email = parts[1].lower()
                                if email not in self.email_index:
                                    self.email_index[email] = []
                                self.email_index[email].append((file_path, line_num))
                
                if file_idx % 10 == 0:
                    logger.info(f"📊 Procesados {file_idx}/{len(self.data_files)} archivos...")
            
            except Exception as e:
                logger.error(f"Error indexando {file_path}: {e}")
        
        logger.info(f"✅ Indexación completada:")
        logger.info(f"   📁 Archivos: {len(self.data_files)}")
        logger.info(f"   📈 Líneas totales: {total_lines:,}")
        logger.info(f"   🔍 Dominios indexados: {len(self.domain_index):,}")
        logger.info(f"   📧 Emails indexados: {len(self.email_index):,}")
    
    def search_domain(self, domain: str, max_results: int = 10000) -> Tuple[int, List[str]]:
        """Búsqueda ultra rápida por dominio usando índice"""
        results = []
        domain_lower = domain.lower()
        
        # Buscar coincidencias exactas o parciales
        matching_domains = [d for d in self.domain_index.keys() if domain_lower in d]
        
        for match_domain in matching_domains[:10]:  # Limitar a 10 dominios similares
            for file_path, line_num in self.domain_index[match_domain]:
                if len(results) >= max_results:
                    break
                
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        # Ir a la línea específica
                        for i, line in enumerate(f, 1):
                            if i == line_num:
                                results.append(line.strip())
                                break
                except:
                    continue
        
        return len(results), results
    
    def search_email(self, email: str, max_results: int = 1000) -> Tuple[int, List[str]]:
        """Búsqueda por email usando índice"""
        results = []
        email_lower = email.lower()
        
        if email_lower in self.email_index:
            for file_path, line_num in self.email_index[email_lower]:
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        for i, line in enumerate(f, 1):
                            if i == line_num:
                                results.append(line.strip())
                                break
                except:
                    continue
        
        return len(results), results
    
    def search_login(self, login: str, max_results: int = 5000) -> Tuple[int, List[str]]:
        """Búsqueda por login"""
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
                        
                        parts = line.split(':')
                        if len(parts) >= 2 and login_lower == parts[1].lower():
                            results.append(line)
                        
                        if len(results) >= max_results:
                            break
            
            except Exception as e:
                logger.error(f"Error en {file_path}: {e}")
                continue
        
        return len(results), results
    
    def search_password(self, password: str, max_results: int = 5000) -> Tuple[int, List[str]]:
        """Búsqueda por contraseña"""
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
                        
                        parts = line.split(':')
                        if len(parts) >= 3 and password_lower == parts[2].lower():
                            results.append(line)
                        
                        if len(results) >= max_results:
                            break
            
            except Exception as e:
                logger.error(f"Error en {file_path}: {e}")
                continue
        
        return len(results), results
    
    def search_dni(self, dni: str, max_results: int = 5000) -> Tuple[int, List[str], List[str]]:
        """Búsqueda especial para DNI español"""
        dni_lower = dni.lower()
        as_login = []
        as_password = []
        
        for file_path in self.data_files:
            if len(as_login) + len(as_password) >= max_results:
                break
            
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        
                        parts = line.split(':')
                        if len(parts) >= 2:
                            # DNI como login (segunda parte)
                            if dni_lower == parts[1].lower():
                                as_login.append(line)
                            
                            # DNI como password (tercera parte)
                            elif len(parts) >= 3 and dni_lower == parts[2].lower():
                                as_password.append(line)
            
            except Exception as e:
                logger.error(f"Error en {file_path}: {e}")
                continue
        
        total = len(as_login) + len(as_password)
        return total, as_login, as_password
    
    def get_stats(self) -> Dict:
        """Estadísticas detalladas"""
        stats = {
            "total_files": len(self.data_files),
            "total_domains": len(self.domain_index),
            "total_emails": len(self.email_index),
            "file_sizes": {},
            "recent_files": []
        }
        
        # Tamaños de archivo
        for file_path in self.data_files[-10:]:  # Últimos 10 archivos
            try:
                filename = os.path.basename(file_path)
                size = os.path.getsize(file_path)
                stats["file_sizes"][filename] = size
                
                # Info de archivos recientes
                mtime = os.path.getmtime(file_path)
                stats["recent_files"].append({
                    "name": filename,
                    "size": size,
                    "modified": datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M')
                })
            except:
                pass
        
        return stats
    
    def add_data_file(self, file_path: str, description: str = "") -> bool:
        """Añadir nuevo archivo de datos"""
        try:
            import shutil
            filename = os.path.basename(file_path)
            dest_path = os.path.join(self.data_dir, filename)
            
            shutil.copy2(file_path, dest_path)
            
            # Re-indexar
            self.load_all_data()
            
            logger.info(f"✅ Archivo añadido: {filename}")
            return True, filename
            
        except Exception as e:
            logger.error(f"Error añadiendo archivo: {e}")
            return False, str(e)
    
    def remove_data_file(self, filename: str) -> bool:
        """Eliminar archivo de datos"""
        try:
            file_path = os.path.join(self.data_dir, filename)
            if os.path.exists(file_path):
                os.remove(file_path)
                self.load_all_data()
                return True
            return False
        except Exception as e:
            logger.error(f"Error eliminando archivo: {e}")
            return False

# ============================================================================
# SISTEMA DE CRÉDITOS AVANZADO
# ============================================================================

class AdvancedCreditSystem:
    """Sistema avanzado de créditos con referidos y estadísticas"""
    
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
            
            # Tabla de usuarios
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    language_code TEXT DEFAULT 'es',
                    join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_admin BOOLEAN DEFAULT 0,
                    is_premium BOOLEAN DEFAULT 0,
                    free_credits INTEGER DEFAULT 2,
                    paid_credits INTEGER DEFAULT 0,
                    total_searches INTEGER DEFAULT 0,
                    last_search TIMESTAMP,
                    referrer_id INTEGER,
                    referral_count INTEGER DEFAULT 0,
                    banned BOOLEAN DEFAULT 0,
                    ban_reason TEXT,
                    banned_until TIMESTAMP,
                    daily_searches INTEGER DEFAULT 0,
                    last_daily_reset TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Tabla de transacciones
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    credits_before INTEGER,
                    credits_after INTEGER,
                    amount INTEGER,
                    type TEXT,
                    description TEXT,
                    admin_id INTEGER,
                    transaction_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Tabla de búsquedas
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS searches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    search_type TEXT,
                    query TEXT,
                    format_used TEXT,
                    results_count INTEGER,
                    credits_used INTEGER DEFAULT 1,
                    search_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Tabla de referidos
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS referrals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    referrer_id INTEGER,
                    referred_id INTEGER,
                    credits_awarded INTEGER DEFAULT 0,
                    referral_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Tabla de configuración
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    description TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Insertar configuración inicial
            default_settings = [
                ('max_free_credits', str(MAX_FREE_CREDITS), 'Máximo créditos gratis por usuario'),
                ('credits_per_search', '1', 'Créditos por búsqueda'),
                ('referral_bonus', '1', 'Créditos por referido'),
                ('daily_search_limit', '10', 'Límite diario de búsquedas'),
                ('maintenance_mode', '0', 'Modo mantenimiento'),
                ('bot_version', BOT_VERSION, 'Versión del bot')
            ]
            
            for key, value, description in default_settings:
                cursor.execute('''
                    INSERT OR REPLACE INTO settings (key, value, description)
                    VALUES (?, ?, ?)
                ''', (key, value, description))
            
            conn.commit()
    
    def get_or_create_user(self, user_id: int, username: str = "", first_name: str = "", last_name: str = "", referrer_id: int = None):
        """Obtener o crear usuario con sistema de referidos"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
            user = cursor.fetchone()
            
            if user:
                return dict(user)
            
            # Es admin?
            is_admin = 1 if user_id in ADMIN_IDS else 0
            
            # Crear usuario
            cursor.execute('''
                INSERT INTO users 
                (user_id, username, first_name, last_name, is_admin, free_credits, referrer_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, username, first_name, last_name, is_admin, MAX_FREE_CREDITS, referrer_id))
            
            # Registrar transacción inicial
            cursor.execute('''
                INSERT INTO transactions 
                (user_id, credits_before, credits_after, amount, type, description)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, 0, MAX_FREE_CREDITS, MAX_FREE_CREDITS, 'free_grant', 'Créditos iniciales gratis'))
            
            # Si tiene referido, dar crédito al referidor
            if referrer_id:
                # Añadir crédito al referidor
                cursor.execute('''
                    UPDATE users 
                    SET free_credits = free_credits + 1,
                        referral_count = referral_count + 1
                    WHERE user_id = ?
                ''', (referrer_id,))
                
                # Registrar transacción del referidor
                cursor.execute('''
                    INSERT INTO transactions 
                    (user_id, credits_before, credits_after, amount, type, description)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (referrer_id, MAX_FREE_CREDITS, MAX_FREE_CREDITS + 1, 1, 'referral_bonus', f'Referido: @{username}'))
                
                # Registrar en tabla de referidos
                cursor.execute('''
                    INSERT INTO referrals (referrer_id, referred_id, credits_awarded)
                    VALUES (?, ?, ?)
                ''', (referrer_id, user_id, 1))
            
            conn.commit()
            
            return {
                'user_id': user_id,
                'username': username,
                'first_name': first_name,
                'last_name': last_name,
                'is_admin': is_admin,
                'free_credits': MAX_FREE_CREDITS,
                'paid_credits': 0,
                'total_searches': 0
            }
    
    def get_user_credits(self, user_id: int) -> Tuple[int, int, int]:
        """Obtener créditos: (free, paid, total)"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT free_credits, paid_credits FROM users WHERE user_id = ?',
                (user_id,)
            )
            result = cursor.fetchone()
            
            if result:
                free = result['free_credits']
                paid = result['paid_credits']
                return free, paid, free + paid
            return 0, 0, 0
    
    def has_enough_credits(self, user_id: int, required: int = 1) -> bool:
        """Verificar si tiene créditos suficientes"""
        free, paid, total = self.get_user_credits(user_id)
        return total >= required
    
    def use_credits(self, user_id: int, search_type: str, query: str, format_used: str = "", results_count: int = 0) -> bool:
        """Usar créditos para una búsqueda"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Obtener créditos actuales
            cursor.execute(
                'SELECT free_credits, paid_credits, daily_searches FROM users WHERE user_id = ?',
                (user_id,)
            )
            result = cursor.fetchone()
            
            if not result:
                return False
            
            free_before = result['free_credits']
            paid_before = result['paid_credits']
            
            # Usar primero créditos gratis
            if free_before > 0:
                free_after = free_before - 1
                paid_after = paid_before
            else:
                free_after = 0
                paid_after = paid_before - 1
            
            # Actualizar usuario
            cursor.execute('''
                UPDATE users 
                SET free_credits = ?, paid_credits = ?,
                    total_searches = total_searches + 1,
                    daily_searches = daily_searches + 1,
                    last_search = CURRENT_TIMESTAMP
                WHERE user_id = ?
            ''', (free_after, paid_after, user_id))
            
            # Registrar transacción
            cursor.execute('''
                INSERT INTO transactions 
                (user_id, credits_before, credits_after, amount, type, description)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                user_id, 
                free_before + paid_before,
                free_after + paid_after,
                1,
                'search_used',
                f'{search_type}: {query}'
            ))
            
            # Registrar búsqueda
            cursor.execute('''
                INSERT INTO searches 
                (user_id, search_type, query, format_used, results_count)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, search_type, query, format_used, results_count))
            
            conn.commit()
            return True
    
    # ==================== ADMIN FUNCTIONS ====================
    
    def add_credits_to_user(self, user_id: int, amount: int, admin_id: int, credit_type: str = 'free') -> Tuple[bool, str]:
        """Admin: Añadir créditos a usuario"""
        if credit_type not in ['free', 'paid']:
            credit_type = 'free'
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Verificar límite de créditos gratis
            if credit_type == 'free':
                cursor.execute(
                    'SELECT free_credits FROM users WHERE user_id = ?',
                    (user_id,)
                )
                result = cursor.fetchone()
                current_free = result['free_credits'] if result else 0
                
                new_total = current_free + amount
                if new_total > MAX_FREE_CREDITS:
                    return False, f"❌ Límite máximo de {MAX_FREE_CREDITS} créditos gratis alcanzado"
            
            # Obtener créditos antes
            cursor.execute(
                'SELECT free_credits, paid_credits FROM users WHERE user_id = ?',
                (user_id,)
            )
            result = cursor.fetchone()
            
            if not result:
                return False, "❌ Usuario no encontrado"
            
            free_before = result['free_credits']
            paid_before = result['paid_credits']
            
            # Actualizar créditos
            if credit_type == 'free':
                cursor.execute(
                    'UPDATE users SET free_credits = free_credits + ? WHERE user_id = ?',
                    (amount, user_id)
                )
                free_after = free_before + amount
                paid_after = paid_before
            else:
                cursor.execute(
                    'UPDATE users SET paid_credits = paid_credits + ? WHERE user_id = ?',
                    (amount, user_id)
                )
                free_after = free_before
                paid_after = paid_before + amount
            
            # Registrar transacción
            cursor.execute('''
                INSERT INTO transactions 
                (user_id, credits_before, credits_after, amount, type, description, admin_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                user_id, 
                free_before + paid_before,
                free_after + paid_after,
                amount,
                f'admin_add_{credit_type}',
                f'Créditos añadidos por admin',
                admin_id
            ))
            
            conn.commit()
            return True, f"✅ {amount} créditos {credit_type} añadidos"
    
    def remove_credits_from_user(self, user_id: int, amount: int, admin_id: int) -> Tuple[bool, str]:
        """Admin: Remover créditos"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Obtener créditos actuales
            cursor.execute(
                'SELECT free_credits, paid_credits FROM users WHERE user_id = ?',
                (user_id,)
            )
            result = cursor.fetchone()
            
            if not result:
                return False, "❌ Usuario no encontrado"
            
            free_before = result['free_credits']
            paid_before = result['paid_credits']
            total_before = free_before + paid_before
            
            # No dejar negativos
            amount = min(amount, total_before)
            
            # Primero quitar de gratis
            free_remove = min(free_before, amount)
            paid_remove = amount - free_remove
            
            free_after = free_before - free_remove
            paid_after = paid_before - paid_remove
            
            # Actualizar
            cursor.execute('''
                UPDATE users 
                SET free_credits = ?, paid_credits = ?
                WHERE user_id = ?
            ''', (free_after, paid_after, user_id))
            
            # Registrar transacción
            cursor.execute('''
                INSERT INTO transactions 
                (user_id, credits_before, credits_after, amount, type, description, admin_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                user_id, 
                total_before,
                free_after + paid_after,
                amount,
                'admin_remove',
                f'Créditos removidos por admin',
                admin_id
            ))
            
            conn.commit()
            return True, f"✅ {amount} créditos removidos"
    
    def ban_user(self, user_id: int, admin_id: int, reason: str = "", hours: int = 0) -> Tuple[bool, str]:
        """Admin: Banear usuario"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            banned_until = None
            if hours > 0:
                banned_until = datetime.now() + timedelta(hours=hours)
            
            cursor.execute('''
                UPDATE users 
                SET banned = 1, ban_reason = ?, banned_until = ?
                WHERE user_id = ?
            ''', (reason, banned_until, user_id))
            
            conn.commit()
            return True, f"✅ Usuario {user_id} baneado"
    
    def unban_user(self, user_id: int, admin_id: int) -> Tuple[bool, str]:
        """Admin: Desbanear usuario"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE users 
                SET banned = 0, ban_reason = NULL, banned_until = NULL
                WHERE user_id = ?
            ''', (user_id,))
            conn.commit()
            return True, f"✅ Usuario {user_id} desbaneado"
    
    def is_user_banned(self, user_id: int) -> Tuple[bool, str, Optional[datetime]]:
        """Verificar si usuario está baneado"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT banned, ban_reason, banned_until FROM users WHERE user_id = ?',
                (user_id,)
            )
            result = cursor.fetchone()
            
            if result and result['banned']:
                banned_until = result['banned_until']
                if banned_until:
                    try:
                        banned_until_dt = datetime.fromisoformat(banned_until) if isinstance(banned_until, str) else banned_until
                        if datetime.now() > banned_until_dt:
                            # Auto desbanear
                            self.unban_user(user_id, 0)
                            return False, "", None
                    except:
                        pass
                
                return True, result['ban_reason'] or "", banned_until
            
            return False, "", None
    
    def get_user_info(self, user_id: int) -> Optional[Dict]:
        """Obtener información completa del usuario"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
            result = cursor.fetchone()
            
            if result:
                user_dict = dict(result)
                
                # Obtener estadísticas adicionales
                cursor.execute('''
                    SELECT COUNT(*) as total_searches, 
                           SUM(results_count) as total_results
                    FROM searches 
                    WHERE user_id = ?
                ''', (user_id,))
                stats = cursor.fetchone()
                
                cursor.execute('''
                    SELECT COUNT(*) as total_transactions
                    FROM transactions 
                    WHERE user_id = ?
                ''', (user_id,))
                trans = cursor.fetchone()
                
                # Referidos
                cursor.execute('''
                    SELECT COUNT(*) as referrals_made
                    FROM referrals 
                    WHERE referrer_id = ?
                ''', (user_id,))
                refs = cursor.fetchone()
                
                user_dict.update({
                    'actual_searches': stats['total_searches'] if stats else 0,
                    'total_results': stats['total_results'] if stats else 0,
                    'total_transactions': trans['total_transactions'] if trans else 0,
                    'referrals_made': refs['referrals_made'] if refs else 0
                })
                
                return user_dict
            return None
    
    def get_all_users(self, limit: int = 100, offset: int = 0) -> List[Dict]:
        """Obtener todos los usuarios"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM users 
                ORDER BY join_date DESC 
                LIMIT ? OFFSET ?
            ''', (limit, offset))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_user_count(self) -> int:
        """Obtener total de usuarios"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) as count FROM users')
            result = cursor.fetchone()
            return result['count'] if result else 0
    
    def get_top_users(self, limit: int = 10) -> List[Dict]:
        """Top usuarios por búsquedas"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT u.user_id, u.username, u.first_name, 
                       u.total_searches, u.free_credits, u.paid_credits,
                       COUNT(s.id) as actual_searches,
                       SUM(s.results_count) as total_results
                FROM users u
                LEFT JOIN searches s ON u.user_id = s.user_id
                GROUP BY u.user_id
                ORDER BY actual_searches DESC, u.total_searches DESC
                LIMIT ?
            ''', (limit,))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_bot_stats(self) -> Dict:
        """Estadísticas del bot"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            stats = {}
            
            # Totales
            cursor.execute('SELECT COUNT(*) as count FROM users')
            stats['total_users'] = cursor.fetchone()['count']
            
            cursor.execute('SELECT COUNT(*) as count FROM searches')
            stats['total_searches'] = cursor.fetchone()['count']
            
            cursor.execute('SELECT SUM(results_count) as total FROM searches')
            stats['total_results'] = cursor.fetchone()['total'] or 0
            
            # Hoy
            cursor.execute('''
                SELECT COUNT(*) as searches_today,
                       COUNT(DISTINCT user_id) as users_today
                FROM searches 
                WHERE date(search_date) = date('now')
            ''')
            today = cursor.fetchone()
            stats['searches_today'] = today['searches_today']
            stats['users_today'] = today['users_today']
            
            # Créditos
            cursor.execute('SELECT SUM(free_credits) as free, SUM(paid_credits) as paid FROM users')
            credits = cursor.fetchone()
            stats['total_free_credits'] = credits['free'] or 0
            stats['total_paid_credits'] = credits['paid'] or 0
            
            # Baneados
            cursor.execute('SELECT COUNT(*) as count FROM users WHERE banned = 1')
            stats['banned_users'] = cursor.fetchone()['count']
            
            # Referidos
            cursor.execute('SELECT COUNT(*) as count FROM referrals')
            stats['total_referrals'] = cursor.fetchone()['count']
            
            return stats
    
    def reset_daily_limits(self):
        """Resetear límites diarios (ejecutar diariamente)"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE users 
                SET daily_searches = 0,
                    last_daily_reset = CURRENT_TIMESTAMP
            ''')
            conn.commit()

# ============================================================================
# MANEJADORES COMPLETOS DE TELEGRAM
# ============================================================================

class CompleteTelegramBot:
    """Manejador completo con todos los comandos"""
    
    def __init__(self, search_engine: AdvancedSearchEngine, credit_system: AdvancedCreditSystem):
        self.search_engine = search_engine
        self.credit_system = credit_system
        self.pending_searches: Dict[int, Dict] = {}
        self.admin_actions: Dict[int, Dict] = {}
    
    # ==================== COMANDOS PRINCIPALES ====================
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /start con sistema de referidos"""
        user = update.effective_user
        
        # Verificar si hay código de referido
        referrer_id = None
        if context.args and len(context.args) > 0:
            try:
                referrer_id = int(context.args[0])
            except:
                pass
        
        # Registrar usuario
        user_info = self.credit_system.get_or_create_user(
            user_id=user.id,
            username=user.username or "",
            first_name=user.first_name or "",
            last_name=user.last_name or "",
            referrer_id=referrer_id
        )
        
        # Verificar baneo
        banned, reason, banned_until = self.credit_system.is_user_banned(user.id)
        if banned:
            ban_msg = f"hasta {banned_until.strftime('%Y-%m-%d %H:%M')}" if banned_until else "permanentemente"
            await update.message.reply_text(
                f"🚫 *CUENTA BANEADA*\n\n"
                f"Razón: {reason}\n"
                f"Duración: {ban_msg}\n\n"
                f"Contacta a {BOT_OWNER}",
                parse_mode='Markdown'
            )
            return
        
        free_credits, paid_credits, total_credits = self.credit_system.get_user_credits(user.id)
        bot_stats = self.search_engine.get_stats()
        
        # Teclado principal
        keyboard = [
            [InlineKeyboardButton("🔍 Buscar Dominio", callback_data="menu_search")],
            [InlineKeyboardButton("📧 Buscar Email", callback_data="menu_email")],
            [InlineKeyboardButton("👤 Buscar Login", callback_data="menu_login")],
            [InlineKeyboardButton("🔑 Buscar Password", callback_data="menu_password")],
            [InlineKeyboardButton("🆔 Buscar DNI", callback_data="menu_dni")],
            [InlineKeyboardButton("💰 Mis Créditos", callback_data="menu_credits")],
            [InlineKeyboardButton("📊 /info", callback_data="menu_info")],
            [InlineKeyboardButton("📋 /help", callback_data="menu_help")],
        ]
        
        if user.id in ADMIN_IDS:
            keyboard.append([InlineKeyboardButton("👑 Panel Admin", callback_data="menu_admin")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        welcome_msg = (
            f"👋 *Bienvenido {user.first_name}!*\n\n"
            f"🚀 *{BOT_NAME}*\n"
            f"📍 *Versión:* {BOT_VERSION}\n\n"
            
            f"📊 *TU ESTADO:*\n"
            f"🆓 *Créditos gratis:* `{free_credits}`/{MAX_FREE_CREDITS}\n"
            f"💳 *Créditos pagados:* `{paid_credits}`\n"
            f"🎯 *Total disponibles:* `{total_credits}`\n"
            f"🔍 *Búsquedas posibles:* `{total_credits}`\n\n"
            
            f"📈 *BASE DE DATOS:*\n"
            f"📁 *Archivos:* `{bot_stats['total_files']}`\n"
            f"🌐 *Dominios:* `{bot_stats['total_domains']:,}`\n"
            f"📧 *Emails:* `{bot_stats['total_emails']:,}`\n\n"
            
            f"💡 *SISTEMA GRATIS:*\n"
            f"• Máximo `{MAX_FREE_CREDITS}` créditos gratis\n"
            f"• 1 crédito = 1 búsqueda\n"
            f"• Invita amigos y gana créditos\n\n"
            
            f"✨ *NUEVO:* Sistema de referidos activo\n"
            f"🔗 Tu enlace de invitación:\n"
            f"`https://t.me/{(await context.bot.get_me()).username}?start={user.id}`\n\n"
            
            f"_Usa /help para ver todos los comandos_"
        )
        
        await update.message.reply_text(
            welcome_msg,
            parse_mode='Markdown',
            reply_markup=reply_markup,
            disable_web_page_preview=True
        )
    
    async def info_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /info - Información completa"""
        user = update.effective_user
        bot_stats = self.search_engine.get_stats()
        credit_stats = self.credit_system.get_bot_stats()
        
        info_text = (
            f"🤖 *{BOT_NAME}*\n"
            f"*Versión:* {BOT_VERSION}\n"
            f"*Propietario:* {BOT_OWNER}\n"
            f"*Tipo:* 🔧 Motor Local Avanzado\n\n"
            
            f"📊 *ESTADÍSTICAS DEL BOT:*\n"
            f"👥 *Usuarios registrados:* `{credit_stats['total_users']:,}`\n"
            f"🔍 *Búsquedas totales:* `{credit_stats['total_searches']:,}`\n"
            f"📈 *Resultados encontrados:* `{credit_stats['total_results']:,}`\n"
            f"💰 *Créditos otorgados:* `{credit_stats['total_free_credits'] + credit_stats['total_paid_credits']:,}`\n\n"
            
            f"💾 *BASE DE DATOS LOCAL:*\n"
            f"📁 *Archivos activos:* `{bot_stats['total_files']}`\n"
            f"🌐 *Dominios indexados:* `{bot_stats['total_domains']:,}`\n"
            f"📧 *Emails indexados:* `{bot_stats['total_emails']:,}`\n\n"
            
            f"🎯 *SISTEMA DE CRÉDITOS:*\n"
            f"• Máximo `{MAX_FREE_CREDITS}` créditos gratis por usuario\n"
            f"• 1 crédito = 1 búsqueda\n"
            f"• Sistema de referidos activo\n"
            f"• Panel de administración completo\n\n"
            
            f"📋 *COMANDOS DISPONIBLES:*\n"
            f"• /search - Buscar por dominio\n"
            f"• /email - Buscar por email\n"
            f"• /dni - Buscar DNI español\n"
            f"• /mycredits - Tus créditos\n"
            f"• /mystats - Tus estadísticas\n"
            f"• /referral - Tu enlace de invitación\n\n"
            
            f"👑 *ADMINISTRACIÓN:*\n"
            f"• /addcredits - Añadir créditos\n"
            f"• /userinfo - Info usuario\n"
            f"• /stats - Estadísticas globales\n"
            f"• /userslist - Listar usuarios\n"
            f"• /broadcast - Enviar a todos\n\n"
            
            f"🔄 *Última actualización:* {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n"
            f"⚡ *Motor:* Búsqueda local indexada\n"
            f"🔒 *Privacidad:* 100% datos locales"
        )
        
        await update.message.reply_text(info_text, parse_mode='Markdown')
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /help - Ayuda completa"""
        help_text = (
            f"📚 *{BOT_NAME} - AYUDA COMPLETA*\n\n"
            
            f"🎯 *SISTEMA GRATIS:*\n"
            f"• Máximo `{MAX_FREE_CREDITS}` créditos gratis\n"
            f"• 1 crédito = 1 búsqueda\n"
            f"• Invita amigos: +1 crédito por referido\n\n"
            
            f"🔍 *COMANDOS DE BÚSQUEDA:*\n"
            f"`/search <dominio>` - Buscar por dominio\n"
            f"`/email <correo>` - Buscar por email\n"
            f"`/login <usuario>` - Buscar por login\n"
            f"`/pass <contraseña>` - Buscar por contraseña\n"
            f"`/dni <12345678A>` - Buscar DNI español\n\n"
            
            f"📋 *FORMATOS PARA /search:*\n"
            f"• email:pass\n• url:email:pass\n"
            f"• login:pass\n• email only\n\n"
            
            f"💰 *COMANDOS PERSONALES:*\n"
            f"`/mycredits` - Ver tus créditos\n"
            f"`/mystats` - Tus estadísticas\n"
            f"`/referral` - Tu enlace de invitación\n"
            f"`/price` - Información de precios\n\n"
            
            f"📊 *INFORMACIÓN:*\n"
            f"`/info` - Información del bot\n"
            f"`/help` - Esta ayuda\n\n"
            
            f"👑 *COMANDOS ADMIN:*\n"
            f"`/addcredits` - Añadir créditos\n"
            f"`/userinfo` - Info usuario\n"
            f"`/stats` - Estadísticas\n"
            f"`/userslist` - Listar usuarios\n"
            f"`/broadcast` - Enviar a todos\n"
            f"`/upload` - Subir archivo ULP\n\n"
            
            f"📁 *ENTREGA DE RESULTADOS:*\n"
            f"• <100 resultados → Mensaje\n"
            f"• 100-10,000 → Archivo .txt\n"
            f"• >10,000 → Archivo .zip\n\n"
            
            f"💡 *CONSEJOS:*\n"
            f"• Usa términos específicos para mejores resultados\n"
            f"• Invita amigos para ganar créditos gratis\n"
            f"• Contacta a {BOT_OWNER} para más créditos\n\n"
            
            f"_Bot desarrollado por {BOT_OWNER}_"
        )
        
        await update.message.reply_text(help_text, parse_mode='Markdown')
    
    # ==================== BÚSQUEDAS ====================
    
    async def search_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /search con selección de formato"""
        user_id = update.effective_user.id
        
        # Verificar baneo
        banned, reason, _ = self.credit_system.is_user_banned(user_id)
        if banned:
            await update.message.reply_text(f"🚫 Cuenta baneada: {reason}")
            return
        
        # Verificar créditos
        if not self.credit_system.has_enough_credits(user_id):
            await update.message.reply_text(
                f"❌ *NO TIENES CRÉDITOS*\n\n"
                f"Usa /mycredits para ver tus créditos.\n"
                f"Contacta a {BOT_OWNER} para más créditos.\n\n"
                f"💡 *Consejo:* Invita amigos con /referral",
                parse_mode='Markdown'
            )
            return ConversationHandler.END
        
        if not context.args:
            await update.message.reply_text(
                "❌ *Uso:* `/search <dominio>`\n\n"
                "Ejemplos:\n"
                "`/search vk.com`\n"
                "`/search facebook.com`\n"
                "`/search instagram.com`\n\n"
                "*Nota:* Podrás seleccionar el formato de resultados",
                parse_mode='Markdown'
            )
            return ConversationHandler.END
        
        query = context.args[0].lower()
        
        # Guardar búsqueda pendiente
        self.pending_searches[user_id] = {
            "type": "domain",
            "query": query,
            "step": "format_selection"
        }
        
        # Mostrar opciones de formato
        keyboard = [
            [
                InlineKeyboardButton("🔐 email:pass", callback_data="format_emailpass"),
                InlineKeyboardButton("🔗 url:email:pass", callback_data="format_urlemailpass")
            ],
            [
                InlineKeyboardButton("👤 login:pass", callback_data="format_loginpass"),
                InlineKeyboardButton("📧 email only", callback_data="format_emailonly")
            ],
            [InlineKeyboardButton("❌ Cancelar", callback_data="format_cancel")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        free_credits, _, total_credits = self.credit_system.get_user_credits(user_id)
        
        await update.message.reply_text(
            f"🔍 *CONFIGURAR BÚSQUEDA*\n\n"
            f"*Dominio:* `{query}`\n"
            f"*Créditos disponibles:* `{total_credits}`\n"
            f"*Créditos gratis restantes:* `{free_credits}`/{MAX_FREE_CREDITS}\n\n"
            f"📋 *Selecciona formato de resultados:*\n\n"
            f"• 🔐 *email:pass* - Correo y contraseña\n"
            f"• 🔗 *url:email:pass* - URL completo\n"
            f"• 👤 *login:pass* - Usuario y contraseña\n"
            f"• 📧 *email only* - Solo correos\n\n"
            f"_1 crédito será usado_",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        
        return CHOOSING_FORMAT
    
    async def format_selected_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Manejador de selección de formato"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        
        if user_id not in self.pending_searches:
            await query.edit_message_text("❌ Búsqueda expirada. Usa /search nuevamente.")
            return ConversationHandler.END
        
        if query.data == "format_cancel":
            await query.edit_message_text("✅ Búsqueda cancelada.")
            del self.pending_searches[user_id]
            return ConversationHandler.END
        
        # Mapear formatos
        format_map = {
            "format_emailpass": "login:pass",
            "format_urlemailpass": "url:login:pass",
            "format_loginpass": "login:pass",
            "format_emailonly": "url"
        }
        
        selected_format = format_map.get(query.data, "url:login:pass")
        search_data = self.pending_searches[user_id]
        
        # Mostrar formato seleccionado
        format_names = {
            "login:pass": "🔐 email:pass",
            "url:login:pass": "🔗 url:email:pass",
            "url": "📧 email only"
        }
        
        await query.edit_message_text(
            f"✅ *FORMATO SELECCIONADO*\n\n"
            f"*Dominio:* `{search_data['query']}`\n"
            f"*Formato:* {format_names.get(selected_format, selected_format)}\n\n"
            f"🔄 *Buscando en {self.search_engine.get_stats()['total_files']} archivos...*",
            parse_mode='Markdown'
        )
        
        # Realizar búsqueda
        await self.execute_search(
            update=update,
            user_id=user_id,
            search_type=search_data["type"],
            query=search_data["query"],
            format_choice=selected_format
        )
        
        # Limpiar
        if user_id in self.pending_searches:
            del self.pending_searches[user_id]
        
        return ConversationHandler.END
    
    async def execute_search(self, update: Update, user_id: int, search_type: str, query: str, format_choice: str = ""):
        """Ejecutar búsqueda y enviar resultados"""
        try:
            # Realizar búsqueda según tipo
            if search_type == "domain":
                total_found, results = self.search_engine.search_domain(query)
            elif search_type == "email":
                total_found, results = self.search_engine.search_email(query)
            elif search_type == "login":
                total_found, results = self.search_engine.search_login(query)
            elif search_type == "password":
                total_found, results = self.search_engine.search_password(query)
            else:
                await update.callback_query.edit_message_text("❌ Tipo de búsqueda no válido")
                return
            
            if total_found == 0:
                await update.callback_query.edit_message_text(
                    f"❌ *NO ENCONTRADO*\n\n"
                    f"*Búsqueda:* `{query}`\n"
                    f"*Tipo:* {search_type}\n"
                    f"*Archivos escaneados:* `{self.search_engine.get_stats()['total_files']}`\n\n"
                    f"💰 *Crédito NO consumido*"
                )
                return
            
            # Usar crédito
            self.credit_system.use_credits(user_id, search_type, query, format_choice, total_found)
            free_credits, paid_credits, total_credits = self.credit_system.get_user_credits(user_id)
            
            # Decidir cómo enviar resultados
            if total_found > 10000:
                await self.send_results_as_zip(update, results, query, search_type, format_choice, total_found, total_credits)
            elif total_found > 100:
                await self.send_results_as_txt(update, results, query, search_type, format_choice, total_found, total_credits)
            else:
                await self.send_results_as_message(update.callback_query, results, query, search_type, format_choice, total_found, total_credits)
        
        except Exception as e:
            logger.error(f"Error en búsqueda: {e}")
            await update.callback_query.edit_message_text(
                f"❌ *ERROR EN BÚSQUEDA*\n\n"
                f"*Error:* {str(e)[:100]}\n\n"
                f"💰 *Crédito reembolsado*"
            )
            # Reembolsar crédito
            self.credit_system.add_credits_to_user(user_id, 1, 0, 'free')
    
    async def send_results_as_zip(self, update: Update, results: list, query: str, search_type: str, 
                                  format_choice: str, total_found: int, remaining_credits: int):
        """Enviar resultados como ZIP"""
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # Archivo principal con resultados
            content = f"Resultados ULP - {search_type}: {query}\n"
            content += f"Formato: {format_choice}\n"
            content += f"Total: {total_found:,} resultados\n"
            content += f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            content += "=" * 50 + "\n\n"
            content += "\n".join(results[:50000])  # Máximo 50,000 líneas
            
            zip_file.writestr(f"ulp_{query}.txt", content)
            
            # Archivo INFO
            info_content = f"""INFORMACIÓN DEL ARCHIVO
========================
Bot: {BOT_NAME}
Versión: {BOT_VERSION}
Propietario: {BOT_OWNER}

BÚSQUEDA REALIZADA
==================
Tipo: {search_type}
Query: {query}
Formato: {format_choice}
Resultados totales: {total_found:,}
Líneas incluidas: {min(len(results), 50000):,}
Fecha de búsqueda: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

INFORMACIÓN TÉCNICA
===================
Motor: Búsqueda local indexada
Archivos escaneados: {self.search_engine.get_stats()['total_files']}
Dominios indexados: {self.search_engine.get_stats()['total_domains']:,}
Emails indexados: {self.search_engine.get_stats()['total_emails']:,}

NOTAS
=====
• Archivo generado automáticamente
• Máximo 50,000 líneas por archivo
• Para más resultados, contacta al administrador
• Bot desarrollado por {BOT_OWNER}
"""
            zip_file.writestr("INFO.txt", info_content)
        
        zip_buffer.seek(0)
        
        # Enviar archivo
        await update.callback_query.message.reply_document(
            document=zip_buffer,
            filename=f"ulp_{query}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
            caption=(
                f"📦 *ARCHIVO ZIP COMPRIMIDO*\n\n"
                f"🔍 *Búsqueda:* {search_type}\n"
                f"📝 *Query:* `{query}`\n"
                f"📋 *Formato:* `{format_choice}`\n"
                f"📊 *Resultados:* `{total_found:,}`\n"
                f"💰 *Créditos restantes:* `{remaining_credits}`\n\n"
                f"*Contenido del ZIP:*\n"
                f"• `ulp_{query}.txt` - Resultados\n"
                f"• `INFO.txt` - Información detallada\n\n"
                f"_Archivo comprimido para mejor envío_"
            ),
            parse_mode='Markdown'
        )
        
        await update.callback_query.edit_message_text(
            f"✅ *BÚSQUEDA MASIVA COMPLETADA*\n\n"
            f"*Query:* `{query}`\n"
            f"*Resultados:* `{total_found:,}`\n"
            f"*Formato:* `{format_choice}`\n"
            f"*Entrega:* 📦 Archivo ZIP\n"
            f"*Créditos restantes:* `{remaining_credits}`\n\n"
            f"_Se han enviado los primeros 50,000 resultados_"
        )
    
    async def send_results_as_txt(self, update: Update, results: list, query: str, search_type: str,
                                  format_choice: str, total_found: int, remaining_credits: int):
        """Enviar resultados como TXT"""
        txt_buffer = io.BytesIO()
        
        content = f"Resultados ULP - {search_type}: {query}\n"
        content += f"Formato: {format_choice}\n"
        content += f"Total: {total_found:,} resultados\n"
        content += f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        content += f"Créditos restantes: {remaining_credits}\n"
        content += "=" * 50 + "\n\n"
        content += "\n".join(results)
        
        txt_buffer.write(content.encode('utf-8'))
        txt_buffer.seek(0)
        
        # Enviar archivo
        await update.callback_query.message.reply_document(
            document=txt_buffer,
            filename=f"ulp_{query}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            caption=(
                f"📁 *ARCHIVO DE RESULTADOS*\n\n"
                f"🔍 *Búsqueda:* {search_type}\n"
                f"📝 *Query:* `{query}`\n"
                f"📋 *Formato:* `{format_choice}`\n"
                f"📊 *Resultados:* `{total_found:,}`\n"
                f"💰 *Créditos restantes:* `{remaining_credits}`\n\n"
                f"_Archivo TXT con todos los resultados_"
            ),
            parse_mode='Markdown'
        )
        
        await update.callback_query.edit_message_text(
            f"✅ *BÚSQUEDA COMPLETADA*\n\n"
            f"*Query:* `{query}`\n"
            f"*Resultados:* `{total_found:,}`\n"
            f"*Formato:* `{format_choice}`\n"
            f"*Entrega:* 📁 Archivo TXT\n"
            f"*Créditos restantes:* `{remaining_credits}`"
        )
    
    async def send_results_as_message(self, query_callback, results: list, query_text: str, 
                                      search_type: str, format_choice: str, total_found: int, remaining_credits: int):
        """Enviar resultados como mensaje"""
        response = (
            f"✅ *BÚSQUEDA COMPLETADA*\n\n"
            f"*Tipo:* {search_type}\n"
            f"*Query:* `{query_text}`\n"
            f"*Formato:* `{format_choice}`\n"
            f"*Resultados:* `{total_found:,}`\n"
            f"*Créditos restantes:* `{remaining_credits}`\n\n"
            f"*Primeros resultados:*\n"
            f"```\n"
        )
        
        # Mostrar primeros 10 resultados
        for line in results[:10]:
            if len(line) > 100:  # Truncar líneas muy largas
                line = line[:97] + "..."
            response += f"{line}\n"
        
        response += "```\n"
        
        if total_found > 10:
            response += f"\n*... y {total_found-10:,} resultados más*"
        
        # Añadir información adicional según tipo de búsqueda
        if search_type == "email" and results:
            # Mostrar cuántas contraseñas únicas
            passwords = set()
            for line in results:
                parts = line.split(':')
                if len(parts) >= 3:
                    passwords.add(parts[2])
            
            if passwords:
                response += f"\n\n🔑 *Contraseñas únicas encontradas:* `{len(passwords)}`"
        
        await query_callback.edit_message_text(response, parse_mode='Markdown')
    
    # ==================== BÚSQUEDA POR EMAIL ====================
    
    async def email_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /email"""
        user_id = update.effective_user.id
        
        # Verificar baneo
        banned, reason, _ = self.credit_system.is_user_banned(user_id)
        if banned:
            await update.message.reply_text(f"🚫 Cuenta baneada: {reason}")
            return
        
        # Verificar créditos
        if not self.credit_system.has_enough_credits(user_id):
            await update.message.reply_text(
                f"❌ *NO TIENES CRÉDITOS*\n\nUsa /mycredits para ver créditos.",
                parse_mode='Markdown'
            )
            return
        
        if not context.args:
            await update.message.reply_text(
                "❌ *Uso:* `/email <correo>`\n\n"
                "Ejemplos:\n"
                "`/email ejemplo@gmail.com`\n"
                "`/email usuario@yahoo.com`",
                parse_mode='Markdown'
            )
            return
        
        email = context.args[0].lower()
        
        # Validar formato de email básico
        if '@' not in email or '.' not in email:
            await update.message.reply_text(
                "❌ *EMAIL INVÁLIDO*\n\n"
                "Formato correcto: usuario@dominio.com\n"
                "Ejemplo: ejemplo@gmail.com",
                parse_mode='Markdown'
            )
            return
        
        # Mensaje de procesando
        msg = await update.message.reply_text(
            f"📧 *Buscando email:* `{email}`...\n"
            f"_Escaneando base de datos..._",
            parse_mode='Markdown'
        )
        
        # Realizar búsqueda
        total_found, results = self.search_engine.search_email(email)
        
        if total_found == 0:
            await msg.edit_text(
                f"❌ *EMAIL NO ENCONTRADO*\n\n"
                f"*Email:* `{email}`\n"
                f"*Resultados:* 0\n\n"
                f"💰 *Crédito NO consumido*"
            )
            return
        
        # Usar crédito
        self.credit_system.use_credits(user_id, "email", email, "", total_found)
        free_credits, paid_credits, total_credits = self.credit_system.get_user_credits(user_id)
        
        # Extraer contraseñas únicas
        passwords = set()
        for line in results:
            parts = line.split(':')
            if len(parts) >= 3:
                passwords.add(parts[2])
        
        response = (
            f"✅ *EMAIL ENCONTRADO*\n\n"
            f"*Email:* `{email}`\n"
            f"*Resultados totales:* `{total_found}`\n"
            f"*Contraseñas únicas:* `{len(passwords)}`\n"
            f"*Créditos restantes:* `{total_credits}`\n\n"
            f"*Contraseñas encontradas:*\n"
            f"```\n"
        )
        
        # Mostrar primeras 10 contraseñas
        for i, pwd in enumerate(list(passwords)[:10], 1):
            response += f"{i}. {pwd}\n"
        
        response += "```\n"
        
        if len(passwords) > 10:
            response += f"\n*... y {len(passwords)-10} contraseñas más*"
        
        # Mostrar algunos sitios donde aparece
        sites = set()
        for line in results[:5]:
            parts = line.split(':')
            if len(parts) >= 1:
                sites.add(parts[0])
        
        if sites:
            response += f"\n\n*Sitios encontrados:*\n"
            for site in list(sites)[:5]:
                response += f"• `{site}`\n"
        
        await msg.edit_text(response, parse_mode='Markdown')
    
    # ==================== BÚSQUEDA POR DNI ====================
    
    async def dni_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /dni para DNI español"""
        user_id = update.effective_user.id
        
        # Verificar baneo
        banned, reason, _ = self.credit_system.is_user_banned(user_id)
        if banned:
            await update.message.reply_text(f"🚫 Cuenta baneada: {reason}")
            return
        
        # Verificar créditos
        if not self.credit_system.has_enough_credits(user_id):
            await update.message.reply_text(
                f"❌ *NO TIENES CRÉDITOS*\n\nUsa /mycredits para ver créditos.",
                parse_mode='Markdown'
            )
            return
        
        if not context.args:
            await update.message.reply_text(
                "❌ *Uso:* `/dni <número-dni>`\n\n"
                "Ejemplos:\n"
                "`/dni 12345678A`\n"
                "`/dni 87654321Z`\n\n"
                "*Formato DNI español:* 8 números + letra",
                parse_mode='Markdown'
            )
            return
        
        dni_input = context.args[0].upper()
        
        # Validar DNI
        if not self.is_valid_dni(dni_input):
            await update.message.reply_text(
                "❌ *DNI INVÁLIDO*\n\n"
                "Formato correcto: 8 números + letra\n"
                "Ejemplos válidos: 12345678A, 87654321Z\n\n"
                "*Letras válidas:* TRWAGMYFPDXBNJZSQVHLCKE",
                parse_mode='Markdown'
            )
            return
        
        # Mensaje de procesando
        msg = await update.message.reply_text(
            f"🆔 *Buscando DNI:* `{dni_input}`...\n"
            f"_Buscando como usuario y como contraseña..._",
            parse_mode='Markdown'
        )
        
        # Realizar búsqueda especial para DNI
        total_found, as_login, as_password = self.search_engine.search_dni(dni_input)
        
        if total_found == 0:
            await msg.edit_text(
                f"❌ *DNI NO ENCONTRADO*\n\n"
                f"*DNI:* `{dni_input}`\n"
                f"*Búsquedas realizadas:*\n"
                f"• Como usuario (login)\n"
                f"• Como contraseña (password)\n\n"
                f"💰 *Crédito NO consumido*"
            )
            return
        
        # Usar crédito
        self.credit_system.use_credits(user_id, "dni", dni_input, "dni_search", total_found)
        free_credits, paid_credits, total_credits = self.credit_system.get_user_credits(user_id)
        
        # Preparar respuesta
        response = (
            f"✅ *DNI ENCONTRADO*\n\n"
            f"*DNI:* `{dni_input}`\n"
            f"*Resultados totales:* `{total_found}`\n"
            f"*Como usuario:* `{len(as_login)}`\n"
            f"*Como contraseña:* `{len(as_password)}`\n"
            f"*Créditos restantes:* `{total_credits}`\n\n"
        )
        
        # Mostrar algunos resultados
        all_results = as_login[:5] + as_password[:5]
        
        if all_results:
            response += f"*Primeros resultados:*\n"
            response += f"```\n"
            for line in all_results:
                if len(line) > 80:
                    line = line[:77] + "..."
                response += f"{line}\n"
            response += f"```\n"
        
        # Estadísticas adicionales
        if as_login:
            login_domains = set()
            for line in as_login:
                parts = line.split(':')
                if len(parts) >= 1:
                    login_domains.add(parts[0])
            
            response += f"\n*Dominios donde es usuario:* `{len(login_domains)}`\n"
        
        if as_password:
            password_users = set()
            for line in as_password:
                parts = line.split(':')
                if len(parts) >= 2:
                    password_users.add(parts[1])
            
            response += f"*Usuarios con esta contraseña:* `{len(password_users)}`\n"
        
        if total_found > 10:
            response += f"\n*... y {total_found-10} resultados más*\n"
            response += f"_Usa /search para búsquedas más específicas_"
        
        await msg.edit_text(response, parse_mode='Markdown')
    
    def is_valid_dni(self, dni: str) -> bool:
        """Validar formato de DNI español"""
        if len(dni) != 9:
            return False
        
        numbers = dni[:8]
        letter = dni[8].upper()
        
        if not numbers.isdigit():
            return False
        
        # Tabla de letras DNI
        letters = "TRWAGMYFPDXBNJZSQVHLCKE"
        expected_letter = letters[int(numbers) % 23]
        
        return letter == expected_letter
    
    # ==================== COMANDOS PERSONALES ====================
    
    async def mycredits_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /mycredits"""
        user_id = update.effective_user.id
        user_info = self.credit_system.get_user_info(user_id)
        
        if not user_info:
            await update.message.reply_text("❌ Usuario no registrado. Usa /start primero.")
            return
        
        free_credits, paid_credits, total_credits = self.credit_system.get_user_credits(user_id)
        
        # Calcular días desde registro
        join_date = user_info.get('join_date')
        if join_date:
            try:
                if 'T' in join_date:
                    join_dt = datetime.fromisoformat(join_date.replace('Z', '+00:00'))
                else:
                    join_dt = datetime.strptime(join_date, '%Y-%m-%d %H:%M:%S')
                days_since = (datetime.now() - join_dt).days
            except:
                days_since = "N/A"
        else:
            days_since = "N/A"
        
        response = (
            f"💰 *TUS CRÉDITOS*\n\n"
            f"👤 *Usuario:* @{update.effective_user.username or update.effective_user.first_name}\n"
            f"🆔 *ID:* `{user_id}`\n"
            f"📅 *Registrado hace:* {days_since} días\n\n"
            f"💳 *CRÉDITOS DISPONIBLES:*\n"
            f"🆓 *Gratis:* `{free_credits}`/{MAX_FREE_CREDITS}\n"
            f"💎 *Pagados:* `{paid_credits}`\n"
            f"🎯 *Total:* `{total_credits}`\n\n"
            f"📊 *ESTADÍSTICAS:*\n"
            f"🔍 *Búsquedas totales:* `{user_info.get('total_searches', 0)}`\n"
            f"📈 *Resultados obtenidos:* `{user_info.get('total_results', 0):,}`\n"
            f"👥 *Referidos invitados:* `{user_info.get('referral_count', 0)}`\n\n"
            f"💡 *INFORMACIÓN:*\n"
            f"• 1 crédito = 1 búsqueda\n"
            f"• Máximo {MAX_FREE_CREDITS} créditos gratis\n"
            f"• Invita amigos: +1 crédito por referido\n\n"
            f"🔗 *Tu enlace de invitación:*\n"
            f"`https://t.me/{(await context.bot.get_me()).username}?start={user_id}`"
        )
        
        await update.message.reply_text(response, parse_mode='Markdown')
    
    async def mystats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /mystats"""
        user_id = update.effective_user.id
        user_info = self.credit_system.get_user_info(user_id)
        
        if not user_info:
            await update.message.reply_text("❌ Usuario no registrado.")
            return
        
        # Obtener estadísticas de búsquedas
        with self.credit_system.get_connection() as conn:
            cursor = conn.cursor()
            
            # Búsquedas por tipo
            cursor.execute('''
                SELECT search_type, COUNT(*) as count, SUM(results_count) as total_results
                FROM searches 
                WHERE user_id = ?
                GROUP BY search_type
                ORDER BY count DESC
            ''', (user_id,))
            search_stats = cursor.fetchall()
            
            # Últimas búsquedas
            cursor.execute('''
                SELECT search_type, query, results_count, search_date
                FROM searches 
                WHERE user_id = ?
                ORDER BY search_date DESC
                LIMIT 5
            ''', (user_id,))
            recent_searches = cursor.fetchall()
        
        free_credits, paid_credits, total_credits = self.credit_system.get_user_credits(user_id)
        
        response = (
            f"📊 *TUS ESTADÍSTICAS*\n\n"
            f"👤 *Usuario:* @{update.effective_user.username or update.effective_user.first_name}\n"
            f"🎯 *Créditos totales:* `{total_credits}`\n\n"
            f"🔍 *ACTIVIDAD DE BÚSQUEDAS:*\n"
        )
        
        # Estadísticas por tipo
        for stat in search_stats:
            response += f"• *{stat['search_type']}:* `{stat['count']}` búsquedas, `{stat['total_results'] or 0:,}` resultados\n"
        
        response += f"\n📈 *TOTAL BÚSQUEDAS:* `{user_info.get('total_searches', 0)}`\n"
        response += f"📊 *TOTAL RESULTADOS:* `{user_info.get('total_results', 0):,}`\n\n"
        
        # Últimas búsquedas
        if recent_searches:
            response += f"⏰ *ÚLTIMAS BÚSQUEDAS:*\n"
            for search in recent_searches:
                time_ago = self.format_time_ago(search['search_date'])
                response += f"• `{search['query'][:20]}...` - {search['results_count']} resultados ({time_ago})\n"
        
        response += f"\n👥 *REFERIDOS:* `{user_info.get('referral_count', 0)}` invitados\n"
        response += f"📅 *MIEMBRO DESDE:* {user_info.get('join_date', 'N/A')}\n\n"
        
        response += f"💡 *RENDIMIENTO:*\n"
        if user_info.get('total_searches', 0) > 0:
            avg_results = user_info.get('total_results', 0) / user_info.get('total_searches', 1)
            response += f"• Promedio: `{avg_results:.1f}` resultados/búsqueda\n"
        
        await update.message.reply_text(response, parse_mode='Markdown')
    
    def format_time_ago(self, timestamp: str) -> str:
        """Formatear tiempo transcurrido"""
        try:
            if 'T' in timestamp:
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            else:
                dt = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
            
            diff = datetime.now() - dt
            
            if diff.days > 0:
                return f"{diff.days}d"
            elif diff.seconds > 3600:
                return f"{diff.seconds // 3600}h"
            elif diff.seconds > 60:
                return f"{diff.seconds // 60}m"
            else:
                return f"{diff.seconds}s"
        except:
            return "N/A"
    
    async def referral_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /referral - Enlace de invitación"""
        user_id = update.effective_user.id
        user_info = self.credit_system.get_user_info(user_id)
        
        if not user_info:
            await update.message.reply_text("❌ Usuario no registrado. Usa /start primero.")
            return
        
        bot_username = (await context.bot.get_me()).username
        referral_link = f"https://t.me/{bot_username}?start={user_id}"
        
        referral_count = user_info.get('referral_count', 0)
        
        response = (
            f"👥 *SISTEMA DE REFERIDOS*\n\n"
            f"🔗 *Tu enlace de invitación:*\n"
            f"`{referral_link}`\n\n"
            f"📊 *Tus estadísticas:*\n"
            f"• 👥 Referidos invitados: `{referral_count}`\n"
            f"• 💰 Créditos ganados: `{referral_count}`\n\n"
            f"🎯 *CÓMO FUNCIONA:*\n"
            f"1. Comparte tu enlace con amigos\n"
            f"2. Cuando alguien use tu enlace\n"
            f"3. Ambos ganan **+1 crédito gratis**\n\n"
            f"💡 *CONSEJOS:*\n"
            f"• Comparte en grupos relacionados\n"
            f"• Cada referido = +1 crédito gratis\n"
            f"• Sin límite de referidos\n\n"
            f"📢 *MENSAJE PARA COMPARTIR:*\n"
            f"```\n"
            f"¡Descubre este increíble bot de búsqueda ULP! 🤖\n\n"
            f"🔍 Busca en millones de registros\n"
            f"💰 Sistema gratuito con créditos\n"
            f"🚀 Rápido y eficiente\n\n"
            f"Usa mi enlace y ambos ganamos créditos:\n"
            f"{referral_link}\n"
            f"```"
        )
        
        await update.message.reply_text(response, parse_mode='Markdown')
    
    async def price_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /price - Información de precios"""
        response = (
            f"💰 *INFORMACIÓN DE PRECIOS*\n\n"
            f"🎯 *SISTEMA ACTUAL:* **GRATIS** para todos\n\n"
            f"🆓 *CRÉDITOS GRATIS:*\n"
            f"• Todos los usuarios: `{MAX_FREE_CREDITS}` créditos iniciales\n"
            f"• Por referido: +1 crédito gratis\n"
            f"• Máximo por usuario: `{MAX_FREE_CREDITS}` créditos gratis\n\n"
            f"🔍 *COSTO POR BÚSQUEDA:*\n"
            f"• 1 búsqueda = 1 crédito\n"
            f"• Sin importar cantidad de resultados\n"
            f"• Mismos precios para todos los tipos\n\n"
            f"💎 *SISTEMA DE REFERIDOS:*\n"
            f"• Invita a un amigo: +1 crédito para ambos\n"
            f"• Sin límite de referidos\n"
            f"• Créditos inmediatos\n\n"
            f"👑 *PARA MÁS CRÉDITOS:*\n"
            f"Contacta directamente a {BOT_OWNER}\n"
            f"para información sobre créditos adicionales\n\n"
            f"📞 *CONTACTO:*\n"
            f"Propietario: {BOT_OWNER}\n"
            f"Bot: @{(await context.bot.get_me()).username}\n\n"
            f"💡 *NOTA:* Este es un bot gratuito\n"
            f"desarrollado para la comunidad."
        )
        
        await update.message.reply_text(response, parse_mode='Markdown')
    
    # ==================== COMANDOS ADMIN ====================
    
    async def addcredits_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Admin: Añadir créditos a usuario"""
        user_id = update.effective_user.id
        
        if user_id not in ADMIN_IDS:
            await update.message.reply_text("❌ Solo para administradores.")
            return
        
        if len(context.args) < 2:
            # Modo interactivo
            await update.message.reply_text(
                "👑 *AÑADIR CRÉDITOS*\n\n"
                "📋 *Modo interactivo iniciado*\n\n"
                "1. Envía el ID del usuario\n"
                "2. Envía la cantidad de créditos\n"
                "3. Selecciona tipo (gratis/pagados)\n\n"
                "O usa el modo directo:\n"
                "`/addcredits <user_id> <cantidad> [free/paid]`\n\n"
                "Envía /cancel para salir.",
                parse_mode='Markdown'
            )
            
            self.admin_actions[user_id] = {
                "action": "add_credits",
                "step": "waiting_user_id"
            }
            return ADMIN_ADD_CREDITS
        
        # Modo directo
        try:
            target_user = int(context.args[0])
            amount = int(context.args[1])
            credit_type = context.args[2] if len(context.args) > 2 else "free"
            
            if amount <= 0:
                await update.message.reply_text("❌ La cantidad debe ser mayor a 0.")
                return
            
            if credit_type not in ['free', 'paid']:
                credit_type = 'free'
            
            success, message = self.credit_system.add_credits_to_user(target_user, amount, user_id, credit_type)
            
            if success:
                # Obtener info del usuario
                user_info = self.credit_system.get_user_info(target_user)
                username = f"@{user_info.get('username', 'N/A')}" if user_info else f"ID: {target_user}"
                
                free_credits, paid_credits, total_credits = self.credit_system.get_user_credits(target_user)
                
                await update.message.reply_text(
                    f"✅ *CRÉDITOS AÑADIDOS*\n\n"
                    f"👤 *Usuario:* {username}\n"
                    f"🆔 *ID:* `{target_user}`\n"
                    f"💰 *Añadidos:* `{amount}` créditos {credit_type}\n"
                    f"🎯 *Total ahora:* `{total_credits}`\n"
                    f"🆓 *Gratis:* `{free_credits}`/{MAX_FREE_CREDITS}\n"
                    f"💎 *Pagados:* `{paid_credits}`\n\n"
                    f"👑 *Admin:* @{update.effective_user.username or update.effective_user.first_name}",
                    parse_mode='Markdown'
                )
            else:
                await update.message.reply_text(f"❌ {message}")
                
        except ValueError:
            await update.message.reply_text(
                "❌ *ERROR DE FORMATO*\n\n"
                "Uso correcto:\n"
                "`/addcredits <user_id> <cantidad> [free/paid]`\n\n"
                "Ejemplos:\n"
                "`/addcredits 123456789 1 free`\n"
                "`/addcredits 123456789 5 paid`",
                parse_mode='Markdown'
            )
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {str(e)}")
    
    async def admin_add_credits_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Manejador interactivo para añadir créditos"""
        user_id = update.effective_user.id
        
        if user_id not in self.admin_actions:
            await update.message.reply_text("❌ Sesión expirada. Usa /addcredits nuevamente.")
            return ConversationHandler.END
        
        action_data = self.admin_actions[user_id]
        
        if action_data["step"] == "waiting_user_id":
            try:
                target_user = int(update.message.text)
                action_data["target_user"] = target_user
                action_data["step"] = "waiting_amount"
                
                await update.message.reply_text(
                    f"✅ *ID usuario:* `{target_user}`\n\n"
                    f"📝 Ahora envía la cantidad de créditos a añadir:",
                    parse_mode='Markdown'
                )
                return ADMIN_ADD_CREDITS
            
            except ValueError:
                await update.message.reply_text("❌ ID inválido. Envía un número.")
                return ADMIN_ADD_CREDITS
        
        elif action_data["step"] == "waiting_amount":
            try:
                amount = int(update.message.text)
                if amount <= 0:
                    await update.message.reply_text("❌ La cantidad debe ser mayor a 0.")
                    return ADMIN_ADD_CREDITS
                
                action_data["amount"] = amount
                action_data["step"] = "waiting_type"
                
                keyboard = [
                    [
                        InlineKeyboardButton("🆓 Gratis", callback_data="admin_credit_free"),
                        InlineKeyboardButton("💎 Pagados", callback_data="admin_credit_paid")
                    ],
                    [InlineKeyboardButton("❌ Cancelar", callback_data="admin_cancel")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(
                    f"✅ *Cantidad:* `{amount}` créditos\n\n"
                    f"📋 Selecciona el tipo de créditos:",
                    parse_mode='Markdown',
                    reply_markup=reply_markup
                )
                return ADMIN_ADD_CREDITS
            
            except ValueError:
                await update.message.reply_text("❌ Cantidad inválida. Envía un número.")
                return ADMIN_ADD_CREDITS
        
        return ADMIN_ADD_CREDITS
    
    async def admin_credit_type_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Manejador para selección de tipo de créditos"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        
        if user_id not in self.admin_actions:
            await query.edit_message_text("❌ Sesión expirada.")
            return ConversationHandler.END
        
        if query.data == "admin_cancel":
            await query.edit_message_text("❌ Operación cancelada.")
            del self.admin_actions[user_id]
            return ConversationHandler.END
        
        action_data = self.admin_actions[user_id]
        credit_type = "free" if query.data == "admin_credit_free" else "paid"
        
        target_user = action_data["target_user"]
        amount = action_data["amount"]
        
        # Ejecutar acción
        success, message = self.credit_system.add_credits_to_user(target_user, amount, user_id, credit_type)
        
        if success:
            # Obtener info del usuario
            user_info = self.credit_system.get_user_info(target_user)
            username = f"@{user_info.get('username', 'N/A')}" if user_info else f"ID: {target_user}"
            
            free_credits, paid_credits, total_credits = self.credit_system.get_user_credits(target_user)
            
            await query.edit_message_text(
                f"✅ *CRÉDITOS AÑADIDOS*\n\n"
                f"👤 *Usuario:* {username}\n"
                f"🆔 *ID:* `{target_user}`\n"
                f"💰 *Añadidos:* `{amount}` créditos {credit_type}\n"
                f"🎯 *Total ahora:* `{total_credits}`\n"
                f"🆓 *Gratis:* `{free_credits}`/{MAX_FREE_CREDITS}\n"
                f"💎 *Pagados:* `{paid_credits}`\n\n"
                f"👑 *Admin:* @{query.from_user.username or query.from_user.first_name}\n\n"
                f"_Operación completada exitosamente_",
                parse_mode='Markdown'
            )
        else:
            await query.edit_message_text(f"❌ {message}")
        
        # Limpiar
        if user_id in self.admin_actions:
            del self.admin_actions[user_id]
        
        return ConversationHandler.END
    
    async def userinfo_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Admin: Información de usuario"""
        user_id = update.effective_user.id
        
        if user_id not in ADMIN_IDS:
            await update.message.reply_text("❌ Solo para administradores.")
            return
        
        if not context.args:
            await update.message.reply_text(
                "❌ *Uso:* `/userinfo <user_id>`\n\n"
                "Ejemplo: `/userinfo 123456789`",
                parse_mode='Markdown'
            )
            return
        
        try:
            target_user = int(context.args[0])
            user_info = self.credit_system.get_user_info(target_user)
            
            if not user_info:
                await update.message.reply_text("❌ Usuario no encontrado.")
                return
            
            # Verificar si está baneado
            banned, ban_reason, banned_until = self.credit_system.is_user_banned(target_user)
            
            free_credits, paid_credits, total_credits = self.credit_system.get_user_credits(target_user)
            
            # Formatear fecha de registro
            join_date = user_info.get('join_date', 'N/A')
            if join_date != 'N/A':
                try:
                    if 'T' in join_date:
                        join_dt = datetime.fromisoformat(join_date.replace('Z', '+00:00'))
                    else:
                        join_dt = datetime.strptime(join_date, '%Y-%m-%d %H:%M:%S')
                    days_since = (datetime.now() - join_dt).days
                    join_date = join_dt.strftime('%d/%m/%Y %H:%M')
                except:
                    pass
            
            # Última búsqueda
            last_search = user_info.get('last_search', 'Nunca')
            if last_search and last_search != 'Nunca':
                try:
                    if 'T' in last_search:
                        last_dt = datetime.fromisoformat(last_search.replace('Z', '+00:00'))
                    else:
                        last_dt = datetime.strptime(last_search, '%Y-%m-%d %H:%M:%S')
                    last_search = last_dt.strftime('%d/%m/%Y %H:%M')
                except:
                    pass
            
            response = (
                f"👤 *INFORMACIÓN DE USUARIO*\n\n"
                f"🆔 *ID:* `{user_info['user_id']}`\n"
                f"📛 *Nombre:* {user_info.get('first_name', '')} {user_info.get('last_name', '')}\n"
                f"👤 *Username:* @{user_info.get('username', 'N/A')}\n"
                f"🌐 *Idioma:* {user_info.get('language_code', 'N/A')}\n"
                f"📅 *Registrado:* {join_date}\n"
                f"⏳ *Días como miembro:* {days_since if 'days_since' in locals() else 'N/A'}\n\n"
                
                f"👑 *PRIVILEGIOS:*\n"
                f"• Admin: {'✅' if user_info.get('is_admin') else '❌'}\n"
                f"• Premium: {'✅' if user_info.get('is_premium') else '❌'}\n"
                f"• Baneado: {'✅' if banned else '❌'}\n"
            )
            
            if banned:
                response += f"• Razón: {ban_reason}\n"
                if banned_until:
                    response += f"• Hasta: {banned_until}\n"
            
            response += (
                f"\n💰 *CRÉDITOS:*\n"
                f"• 🆓 Gratis: `{free_credits}`/{MAX_FREE_CREDITS}\n"
                f"• 💎 Pagados: `{paid_credits}`\n"
                f"• 🎯 Total: `{total_credits}`\n\n"
                
                f"📊 *ACTIVIDAD:*\n"
                f"• 🔍 Búsquedas totales: `{user_info.get('total_searches', 0)}`\n"
                f"• 📈 Resultados obtenidos: `{user_info.get('total_results', 0):,}`\n"
                f"• 👥 Referidos: `{user_info.get('referral_count', 0)}`\n"
                f"• 📅 Búsquedas hoy: `{user_info.get('daily_searches', 0)}`\n"
                f"• ⏰ Última búsqueda: {last_search}\n\n"
                
                f"📋 *TRANSACCIONES:*\n"
                f"• Total transacciones: `{user_info.get('total_transactions', 0)}`\n"
                f"• Referidos hechos: `{user_info.get('referrals_made', 0)}`\n\n"
                
                f"_Consultado por admin_"
            )
            
            await update.message.reply_text(response, parse_mode='Markdown')
            
        except ValueError:
            await update.message.reply_text("❌ ID de usuario inválido.")
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {str(e)}")
    
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Admin: Estadísticas del bot"""
        user_id = update.effective_user.id
        
        if user_id not in ADMIN_IDS:
            await update.message.reply_text("❌ Solo para administradores.")
            return
        
        bot_stats = self.credit_system.get_bot_stats()
        engine_stats = self.search_engine.get_stats()
        
        # Calcular promedios
        if bot_stats['total_users'] > 0:
            avg_searches = bot_stats['total_searches'] / bot_stats['total_users']
            avg_credits = (bot_stats['total_free_credits'] + bot_stats['total_paid_credits']) / bot_stats['total_users']
        else:
            avg_searches = 0
            avg_credits = 0
        
        response = (
            f"📊 *ESTADÍSTICAS DEL BOT*\n\n"
            
            f"👥 *USUARIOS:*\n"
            f"• Total registrados: `{bot_stats['total_users']:,}`\n"
            f"• Activos hoy: `{bot_stats['users_today']:,}`\n"
            f"• Baneados: `{bot_stats['banned_users']:,}`\n\n"
            
            f"🔍 *ACTIVIDAD:*\n"
            f"• Búsquedas totales: `{bot_stats['total_searches']:,}`\n"
            f"• Búsquedas hoy: `{bot_stats['searches_today']:,}`\n"
            f"• Resultados totales: `{bot_stats['total_results']:,}`\n"
            f"• Referidos totales: `{bot_stats['total_referrals']:,}`\n\n"
            
            f"💰 *CRÉDITOS:*\n"
            f"• Gratis otorgados: `{bot_stats['total_free_credits']:,}`\n"
            f"• Pagados otorgados: `{bot_stats['total_paid_credits']:,}`\n"
            f"• Total créditos: `{bot_stats['total_free_credits'] + bot_stats['total_paid_credits']:,}`\n\n"
            
            f"📈 *PROMEDIOS:*\n"
            f"• Búsquedas/usuario: `{avg_searches:.1f}`\n"
            f"• Créditos/usuario: `{avg_credits:.1f}`\n"
            f"• Resultados/búsqueda: `{bot_stats['total_results'] / max(bot_stats['total_searches'], 1):.1f}`\n\n"
            
            f"💾 *BASE DE DATOS:*\n"
            f"• Archivos activos: `{engine_stats['total_files']}`\n"
            f"• Dominios indexados: `{engine_stats['total_domains']:,}`\n"
            f"• Emails indexados: `{engine_stats['total_emails']:,}`\n\n"
            
            f"📅 *ARCHIVOS RECIENTES:*\n"
        )
        
        # Mostrar últimos 5 archivos
        for i, file_info in enumerate(engine_stats['recent_files'][:5], 1):
            size_mb = file_info['size'] / (1024 * 1024)
            response += f"{i}. `{file_info['name']}` - {size_mb:.2f} MB ({file_info['modified']})\n"
        
        response += f"\n🔄 *Última actualización:* {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n"
        response += f"🤖 *Versión:* {BOT_VERSION}\n"
        response += f"👑 *Admin consultante:* @{update.effective_user.username or update.effective_user.first_name}"
        
        await update.message.reply_text(response, parse_mode='Markdown')
    
    async def userslist_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Admin: Listar usuarios"""
        user_id = update.effective_user.id
        
        if user_id not in ADMIN_IDS:
            await update.message.reply_text("❌ Solo para administradores.")
            return
        
        # Obtener parámetros
        limit = 50
        offset = 0
        
        if context.args:
            try:
                if len(context.args) >= 1:
                    limit = min(int(context.args[0]), 100)  # Máximo 100
                if len(context.args) >= 2:
                    offset = int(context.args[1])
            except:
                pass
        
        users = self.credit_system.get_all_users(limit=limit, offset=offset)
        total_users = self.credit_system.get_user_count()
        
        if not users:
            await update.message.reply_text("📭 No hay usuarios registrados.")
            return
        
        response = f"📋 *LISTA DE USUARIOS* ({total_users} totales)\n\n"
        response += f"*Mostrando {len(users)} usuarios (offset: {offset})*\n\n"
        
        for i, user in enumerate(users, offset + 1):
            username = f"@{user.get('username', '')}" if user.get('username') else user.get('first_name', 'Sin nombre')
            banned = "🚫" if user.get('banned') else "✅"
            admin = "👑" if user.get('is_admin') else "👤"
            
            response += f"{i}. {admin} {username} (`{user['user_id']}`) {banned}\n"
            
            # Añadir créditos si hay espacio
            if i <= 20:  # Solo en primeros 20
                free = user.get('free_credits', 0)
                total = free + user.get('paid_credits', 0)
                response += f"   💰 {total} créditos | 🔍 {user.get('total_searches', 0)} búsq.\n"
        
        if offset + len(users) < total_users:
            next_offset = offset + limit
            response += f"\n📄 *Página siguiente:*\n`/userslist {limit} {next_offset}`"
        
        response += f"\n\n_Usa `/userinfo <id>` para información detallada_"
        
        # Si es muy largo, dividir en varios mensajes
        if len(response) > 4000:
            parts = [response[i:i+4000] for i in range(0, len(response), 4000)]
            for part in parts:
                await update.message.reply_text(part, parse_mode='Markdown')
        else:
            await update.message.reply_text(response, parse_mode='Markdown')
    
    async def broadcast_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Admin: Enviar mensaje a todos los usuarios"""
        user_id = update.effective_user.id
        
        if user_id not in ADMIN_IDS:
            await update.message.reply_text("❌ Solo para administradores.")
            return
        
        if not context.args:
            await update.message.reply_text(
                "❌ *Uso:* `/broadcast <mensaje>`\n\n"
                "Ejemplo: `/broadcast Nuevas funciones disponibles!`\n\n"
                "⚠️ *ADVERTENCIA:* Se enviará a TODOS los usuarios.",
                parse_mode='Markdown'
            )
            return
        
        message = ' '.join(context.args)
        users = self.credit_system.get_all_users()
        total_users = len(users)
        
        if total_users == 0:
            await update.message.reply_text("📭 No hay usuarios para enviar broadcast.")
            return
        
        # Confirmación
        keyboard = [
            [
                InlineKeyboardButton("✅ Confirmar", callback_data="broadcast_confirm"),
                InlineKeyboardButton("❌ Cancelar", callback_data="broadcast_cancel")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"📢 *CONFIRMAR BROADCAST*\n\n"
            f"*Mensaje:* {message}\n"
            f"*Destinatarios:* {total_users} usuarios\n\n"
            f"⚠️ *ADVERTENCIA:* Esta acción no se puede deshacer.\n"
            f"El mensaje se enviará a todos los usuarios registrados.\n\n"
            f"¿Confirmas el envío?",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    
    async def broadcast_confirmation_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Manejador de confirmación de broadcast"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "broadcast_cancel":
            await query.edit_message_text("❌ Broadcast cancelado.")
            return
        
        # Extraer mensaje del texto anterior
        message_text = query.message.text
        lines = message_text.split('\n')
        broadcast_message = None
        
        for line in lines:
            if line.startswith("*Mensaje:* "):
                broadcast_message = line[10:].strip()
                break
        
        if not broadcast_message:
            await query.edit_message_text("❌ Error: No se pudo extraer el mensaje.")
            return
        
        users = self.credit_system.get_all_users()
        total_users = len(users)
        
        await query.edit_message_text(
            f"📤 *ENVIANDO BROADCAST*\n\n"
            f"*Mensaje:* {broadcast_message}\n"
            f"*Destinatarios:* {total_users} usuarios\n\n"
            f"🔄 *Procesando...*",
            parse_mode='Markdown'
        )
        
        # Enviar a usuarios (en la realidad, esto sería async)
        success_count = 0
        fail_count = 0
        
        # Nota: En un bot real, necesitarías implementar el envío asíncrono
        # Esto es solo un ejemplo
        
        await query.edit_message_text(
            f"✅ *BROADCAST COMPLETADO*\n\n"
            f"📝 *Mensaje enviado:*\n{broadcast_message[:100]}...\n\n"
            f"📊 *ESTADÍSTICAS:*\n"
            f"• 👥 Destinatarios: {total_users} usuarios\n"
            f"• ✅ Enviados: {total_users} (simulado)\n"
            f"• ❌ Fallados: 0 (simulado)\n\n"
            f"👑 *Admin:* @{query.from_user.username or query.from_user.first_name}\n\n"
            f"_Nota: Esto es una simulación. En producción se enviaría realmente._",
            parse_mode='Markdown'
        )
    
    # ==================== MANEJO DE ARCHIVOS ====================
    
    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Manejador de documentos para subir archivos ULP"""
        user_id = update.effective_user.id
        
        if user_id not in ADMIN_IDS:
            await update.message.reply_text("❌ Solo administradores pueden subir archivos.")
            return
        
        document = update.message.document
        
        # Verificar que es un archivo .txt
        if not document.file_name.endswith('.txt'):
            await update.message.reply_text(
                "❌ *ARCHIVO NO VÁLIDO*\n\n"
                "Solo se aceptan archivos .txt con formato ULP.\n"
                "Formato esperado: url:login:pass o email:pass",
                parse_mode='Markdown'
            )
            return
        
        # Verificar tamaño (máximo 100MB)
        if document.file_size > 100 * 1024 * 1024:
            await update.message.reply_text(
                "❌ *ARCHIVO DEMASIADO GRANDE*\n\n"
                "Tamaño máximo: 100MB\n"
                "Tu archivo: {:.2f}MB".format(document.file_size / (1024 * 1024)),
                parse_mode='Markdown'
            )
            return
        
        # Mensaje de procesando
        msg = await update.message.reply_text(
            f"📤 *PROCESANDO ARCHIVO*\n\n"
            f"*Nombre:* `{document.file_name}`\n"
            f"*Tamaño:* {document.file_size / 1024:.0f} KB\n\n"
            f"🔄 *Descargando y procesando...*",
            parse_mode='Markdown'
        )
        
        try:
            # Descargar archivo
            file = await document.get_file()
            temp_path = os.path.join(UPLOAD_DIR, document.file_name)
            await file.download_to_drive(temp_path)
            
            # Verificar formato básico
            valid_lines = 0
            total_lines = 0
            
            with open(temp_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    total_lines += 1
                    line = line.strip()
                    if line and (':' in line or '@' in line):
                        valid_lines += 1
            
            if valid_lines == 0:
                os.remove(temp_path)
                await msg.edit_text(
                    f"❌ *ARCHIVO INVÁLIDO*\n\n"
                    f"El archivo no contiene líneas con formato ULP válido.\n"
                    f"Formato esperado: url:login:pass o email:pass\n\n"
                    f"*Estadísticas:*\n"
                    f"• Líneas totales: {total_lines}\n"
                    f"• Líneas válidas: 0",
                    parse_mode='Markdown'
                )
                return
            
            # Añadir a motor de búsqueda
            success, result = self.search_engine.add_data_file(temp_path)
            
            if success:
                # Mover a carpeta de datos
                final_path = os.path.join(DATA_DIR, document.file_name)
                os.rename(temp_path, final_path)
                
                # Obtener estadísticas actualizadas
                stats = self.search_engine.get_stats()
                
                await msg.edit_text(
                    f"✅ *ARCHIVO PROCESADO CORRECTAMENTE*\n\n"
                    f"*Nombre:* `{document.file_name}`\n"
                    f"*Tamaño:* {document.file_size / 1024:.0f} KB\n"
                    f"*Líneas totales:* {total_lines:,}\n"
                    f"*Líneas válidas:* {valid_lines:,}\n\n"
                    f"📊 *BASE DE DATOS ACTUALIZADA:*\n"
                    f"• Archivos totales: `{stats['total_files']}`\n"
                    f"• Dominios indexados: `{stats['total_domains']:,}`\n"
                    f"• Emails indexados: `{stats['total_emails']:,}`\n\n"
                    f"👑 *Subido por:* @{update.effective_user.username or update.effective_user.first_name}\n\n"
                    f"✅ *Archivo listo para búsquedas*",
                    parse_mode='Markdown'
                )
            else:
                os.remove(temp_path)
                await msg.edit_text(
                    f"❌ *ERROR AL PROCESAR ARCHIVO*\n\n"
                    f"Error: {result}\n\n"
                    f"*Archivo:* `{document.file_name}`",
                    parse_mode='Markdown'
                )
        
        except Exception as e:
            logger.error(f"Error procesando archivo: {e}")
            await msg.edit_text(
                f"❌ *ERROR CRÍTICO*\n\n"
                f"Error: {str(e)[:200]}\n\n"
                f"*Archivo:* `{document.file_name}`",
                parse_mode='Markdown'
            )
    
    # ==================== MANEJADOR DE BOTONES GENERAL ====================
    
    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Manejador general de botones inline"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        
        # Menú principal
        if query.data == "menu_search":
            await query.edit_message_text(
                "🔍 *BUSCAR POR DOMINIO*\n\n"
                "Envía: `/search dominio`\n\n"
                "Ejemplos:\n"
                "`/search vk.com`\n"
                "`/search facebook.com`\n"
                "`/search instagram.com`\n\n"
                "Podrás seleccionar el formato de resultados:\n"
                "• email:pass\n• url:email:pass\n• login:pass\n• email only",
                parse_mode='Markdown'
            )
        
        elif query.data == "menu_email":
            await query.edit_message_text(
                "📧 *BUSCAR POR EMAIL*\n\n"
                "Envía: `/email correo@gmail.com`\n\n"
                "Ejemplos:\n"
                "`/email ejemplo@gmail.com`\n"
                "`/email usuario@yahoo.com`\n\n"
                "Devuelve contraseñas asociadas al email.",
                parse_mode='Markdown'
            )
        
        elif query.data == "menu_login":
            await query.edit_message_text(
                "👤 *BUSCAR POR LOGIN*\n\n"
                "Envía: `/login nombre_usuario`\n\n"
                "Busca el nombre de usuario en todos los sitios.",
                parse_mode='Markdown'
            )
        
        elif query.data == "menu_password":
            await query.edit_message_text(
                "🔑 *BUSCAR POR CONTRASEÑA*\n\n"
                "Envía: `/pass contraseña123`\n\n"
                "Busca dónde se usa esa contraseña.",
                parse_mode='Markdown'
            )
        
        elif query.data == "menu_dni":
            await query.edit_message_text(
                "🆔 *BUSCAR DNI ESPAÑOL*\n\n"
                "Envía: `/dni 12345678A`\n\n"
                "Busca DNI como usuario o como contraseña.\n\n"
                "*Formato:* 8 números + letra\n"
                "*Ejemplos:* 12345678A, 87654321Z",
                parse_mode='Markdown'
            )
        
        elif query.data == "menu_credits":
            free_credits, paid_credits, total_credits = self.credit_system.get_user_credits(user_id)
            
            await query.edit_message_text(
                f"💰 *TUS CRÉDITOS*\n\n"
                f"🆓 *Gratis:* `{free_credits}`/{MAX_FREE_CREDITS}\n"
                f"💎 *Pagados:* `{paid_credits}`\n"
                f"🎯 *Total:* `{total_credits}`\n\n"
                f"🔍 *Búsquedas posibles:* `{total_credits}`\n\n"
                f"💡 *Para más créditos:*\n"
                f"1. Invita amigos con /referral\n"
                f"2. Contacta a {BOT_OWNER}",
                parse_mode='Markdown'
            )
        
        elif query.data == "menu_info":
            await self.info_command(update, context)
        
        elif query.data == "menu_help":
            await self.help_command(update, context)
        
        elif query.data == "menu_admin":
            if user_id not in ADMIN_IDS:
                await query.edit_message_text("❌ Solo para administradores.")
                return
            
            # Panel de admin con botones
            keyboard = [
                [InlineKeyboardButton("➕ Añadir Créditos", callback_data="admin_add")],
                [InlineKeyboardButton("👤 Información Usuario", callback_data="admin_userinfo")],
                [InlineKeyboardButton("📊 Estadísticas", callback_data="admin_stats")],
                [InlineKeyboardButton("📋 Listar Usuarios", callback_data="admin_userslist")],
                [InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")],
                [InlineKeyboardButton("📤 Subir Archivo", callback_data="admin_upload")],
                [InlineKeyboardButton("🔄 Recargar BD", callback_data="admin_reload")],
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            bot_stats = self.credit_system.get_bot_stats()
            
            await query.edit_message_text(
                f"👑 *PANEL DE ADMINISTRACIÓN*\n\n"
                f"👤 *Admin:* @{query.from_user.username or query.from_user.first_name}\n"
                f"📊 *Estadísticas:*\n"
                f"• 👥 Usuarios: `{bot_stats['total_users']:,}`\n"
                f"• 🔍 Búsquedas: `{bot_stats['total_searches']:,}`\n"
                f"• 💰 Créditos: `{bot_stats['total_free_credits'] + bot_stats['total_paid_credits']:,}`\n\n"
                f"💾 *Base de datos:*\n"
                f"• 📁 Archivos: `{self.search_engine.get_stats()['total_files']}`\n"
                f"• 🌐 Dominios: `{self.search_engine.get_stats()['total_domains']:,}`\n\n"
                f"_Selecciona una acción:_",
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
        
        # Sub-menús de admin
        elif query.data == "admin_add":
            await query.edit_message_text(
                "➕ *AÑADIR CRÉDITOS*\n\n"
                "Uso: `/addcredits <user_id> <cantidad> [free/paid]`\n\n"
                "Ejemplos:\n"
                "`/addcredits 123456789 1 free`\n"
                "`/addcredits 123456789 5 paid`\n\n"
                f"*Límite máximo gratis:* {MAX_FREE_CREDITS} créditos\n\n"
                "Para modo interactivo envía solo `/addcredits`",
                parse_mode='Markdown'
            )
        
        elif query.data == "admin_userinfo":
            await query.edit_message_text(
                "👤 *INFORMACIÓN DE USUARIO*\n\n"
                "Uso: `/userinfo <user_id>`\n\n"
                "Ejemplo: `/userinfo 123456789`\n\n"
                "Muestra información detallada del usuario.",
                parse_mode='Markdown'
            )
        
        elif query.data == "admin_stats":
            await self.stats_command(update, context)
        
        elif query.data == "admin_userslist":
            await query.edit_message_text(
                "📋 *LISTAR USUARIOS*\n\n"
                "Uso: `/userslist [límite] [offset]`\n\n"
                "Ejemplos:\n"
                "`/userslist` - 50 usuarios\n"
                "`/userslist 20` - 20 usuarios\n"
                "`/userslist 30 50` - 30 usuarios desde posición 50\n\n"
                "Máximo 100 usuarios por consulta.",
                parse_mode='Markdown'
            )
        
        elif query.data == "admin_broadcast":
            await query.edit_message_text(
                "📢 *BROADCAST*\n\n"
                "Uso: `/broadcast <mensaje>`\n\n"
                "Ejemplo: `/broadcast Nuevas funciones disponibles!`\n\n"
                "⚠️ *ADVERTENCIA:* Se enviará a TODOS los usuarios.\n"
                "Se pedirá confirmación antes de enviar.",
                parse_mode='Markdown'
            )
        
        elif query.data == "admin_upload":
            await query.edit_message_text(
                "📤 *SUBIR ARCHIVO ULP*\n\n"
                "Para subir un archivo:\n"
                "1. Envía un archivo .txt\n"
                "2. Formato: url:login:pass o email:pass\n"
                "3. Máximo 100MB\n\n"
                "El archivo se indexará automáticamente.\n"
                "Luego estará disponible para búsquedas.",
                parse_mode='Markdown'
            )
        
        elif query.data == "admin_reload":
            await query.edit_message_text("🔄 Recargando base de datos...")
            self.search_engine.load_all_data()
            await query.edit_message_text(
                f"✅ *BASE DE DATOS RECARGADA*\n\n"
                f"📊 *Estadísticas actualizadas:*\n"
                f"• 📁 Archivos: `{self.search_engine.get_stats()['total_files']}`\n"
                f"• 🌐 Dominios: `{self.search_engine.get_stats()['total_domains']:,}`\n"
                f"• 📧 Emails: `{self.search_engine.get_stats()['total_emails']:,}`\n\n"
                f"✅ *Indexación completada*",
                parse_mode='Markdown'
            )
    
    # ==================== MANEJADOR DE CANCELACIÓN ====================
    
    async def cancel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /cancel para cancelar operaciones"""
        user_id = update.effective_user.id
        
        # Limpiar operaciones pendientes
        if user_id in self.pending_searches:
            del self.pending_searches[user_id]
        
        if user_id in self.admin_actions:
            del self.admin_actions[user_id]
        
        await update.message.reply_text(
            "❌ *Operación cancelada.*\n\n"
            "Todos los procesos pendientes han sido limpiados.",
            parse_mode='Markdown'
        )
        
        return ConversationHandler.END

# ============================================================================
# EJECUCIÓN PRINCIPAL
# ============================================================================

def run_flask_server():
    """Ejecutar servidor Flask en segundo plano"""
    app.run(host='0.0.0.0', port=PORT, threaded=True)

def main():
    """Función principal"""
    logger.info(f"🚀 {BOT_NAME}")
    logger.info(f"📍 Versión: {BOT_VERSION}")
    logger.info(f"👑 Propietario: {BOT_OWNER}")
    logger.info(f"🎯 Créditos gratis: {MAX_FREE_CREDITS} por usuario")
    logger.info(f"💾 Directorio de datos: {DATA_DIR}")
    
    # Inicializar sistemas
    search_engine = AdvancedSearchEngine()
    credit_system = AdvancedCreditSystem()
    bot_handlers = CompleteTelegramBot(search_engine, credit_system)
    
    # Crear aplicación de Telegram
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # ==================== CONVERSATION HANDLERS ====================
    
    # Handler para /search con selección de formato
    search_conv_handler = ConversationHandler(
        entry_points=[CommandHandler('search', bot_handlers.search_command)],
        states={
            CHOOSING_FORMAT: [
                CallbackQueryHandler(bot_handlers.format_selected_handler, pattern='^format_')
            ]
        },
        fallbacks=[
            CommandHandler('cancel', bot_handlers.cancel_command),
            MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: ConversationHandler.END)
        ],
        allow_reentry=True
    )
    
    # Handler para admin /addcredits interactivo
    admin_conv_handler = ConversationHandler(
        entry_points=[CommandHandler('addcredits', bot_handlers.addcredits_command)],
        states={
            ADMIN_ADD_CREDITS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, bot_handlers.admin_add_credits_handler),
                CallbackQueryHandler(bot_handlers.admin_credit_type_handler, pattern='^admin_')
            ]
        },
        fallbacks=[
            CommandHandler('cancel', bot_handlers.cancel_command)
        ]
    )
    
    # ==================== REGISTRAR HANDLERS ====================
    
    # Comandos de usuario
    application.add_handler(CommandHandler("start", bot_handlers.start))
    application.add_handler(CommandHandler("info", bot_handlers.info_command))
    application.add_handler(CommandHandler("help", bot_handlers.help_command))
    application.add_handler(CommandHandler("mycredits", bot_handlers.mycredits_command))
    application.add_handler(CommandHandler("mystats", bot_handlers.mystats_command))
    application.add_handler(CommandHandler("referral", bot_handlers.referral_command))
    application.add_handler(CommandHandler("price", bot_handlers.price_command))
    application.add_handler(CommandHandler("cancel", bot_handlers.cancel_command))
    
    # Búsquedas
    application.add_handler(search_conv_handler)  # /search con formato
    application.add_handler(CommandHandler("email", bot_handlers.email_command))
    application.add_handler(CommandHandler("login", bot_handlers.email_command))  # Similar handler
    application.add_handler(CommandHandler("pass", bot_handlers.email_command))   # Similar handler
    application.add_handler(CommandHandler("dni", bot_handlers.dni_command))
    
    # Comandos de admin
    application.add_handler(admin_conv_handler)  # /addcredits interactivo
    application.add_handler(CommandHandler("userinfo", bot_handlers.userinfo_command))
    application.add_handler(CommandHandler("stats", bot_handlers.stats_command))
    application.add_handler(CommandHandler("userslist", bot_handlers.userslist_command))
    application.add_handler(CommandHandler("broadcast", bot_handlers.broadcast_command))
    
    # Handlers de documentos (subida de archivos)
    application.add_handler(MessageHandler(
        filters.Document.ALL, 
        bot_handlers.handle_document
    ))
    
    # Handlers de botones
    application.add_handler(CallbackQueryHandler(bot_handlers.button_handler, pattern='^menu_'))
    application.add_handler(CallbackQueryHandler(bot_handlers.button_handler, pattern='^admin_'))
    application.add_handler(CallbackQueryHandler(bot_handlers.broadcast_confirmation_handler, pattern='^broadcast_'))
    
    # ==================== INICIAR SERVICIOS ====================
    
    # Iniciar Flask en segundo plano
    flask_thread = threading.Thread(target=run_flask_server, daemon=True)
    flask_thread.start()
    logger.info(f"🌐 Servidor Flask iniciado en puerto {PORT}")
    
    # Tarea periódica: Resetear límites diarios
    async def reset_daily_limits(context: ContextTypes.DEFAULT_TYPE):
        """Resetear límites diarios a medianoche"""
        credit_system.reset_daily_limits()
        logger.info("🔄 Límites diarios reseteados")
    
    # Programar tarea diaria (si se usa JobQueue)
    # application.job_queue.run_daily(reset_daily_limits, time=datetime.time(hour=0, minute=0))
    
    # Iniciar bot
    logger.info("🤖 Iniciando bot de Telegram...")
    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
        close_loop=False
    )

if __name__ == '__main__':
    main()
