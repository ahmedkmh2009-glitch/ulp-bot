"""
ULP Searcher Bot - Versión REAL Y FUNCIONAL
Bot completo para búsqueda ULP con motor local
"""

import os
import logging
import sqlite3
import threading
import io
import zipfile
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import glob

from flask import Flask, request, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    ContextTypes, CallbackQueryHandler, filters,
    ConversationHandler
)

# ============================================================================
# CONFIGURACIÓN
# ============================================================================

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
ADMIN_IDS = [int(id.strip()) for id in os.getenv('ADMIN_IDS', '').split(',') if id.strip()]
BOT_OWNER = "@tu_usuario"
BOT_NAME = "🔍 ULP Searcher Bot"
BOT_VERSION = "4.0 REAL"
MAX_FREE_CREDITS = 5

PORT = int(os.getenv('PORT', 10000))

BASE_DIR = "bot_data"
DATA_DIR = os.path.join(BASE_DIR, "ulp_files")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
DB_PATH = os.path.join(BASE_DIR, "bot.db")

for directory in [BASE_DIR, DATA_DIR, UPLOAD_DIR]:
    os.makedirs(directory, exist_ok=True)

CHOOSING_FORMAT, ADMIN_ADD_CREDITS = range(2)

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
    return jsonify({"status": "online", "bot": BOT_NAME})

@app.route('/health')
def health():
    return jsonify({"status": "healthy"})

# ============================================================================
# MOTOR DE BÚSQUEDA
# ============================================================================

class SearchEngine:
    def __init__(self, data_dir: str = DATA_DIR):
        self.data_dir = data_dir
        self.data_files = []
        self.load_all_data()
    
    def load_all_data(self):
        self.data_files = glob.glob(os.path.join(self.data_dir, "*.txt"))
        logger.info(f"📂 Cargados {len(self.data_files)} archivos")
    
    def search_domain(self, domain: str, max_results: int = 5000) -> Tuple[int, List[str]]:
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
                        
                        # Buscar dominio en cualquier parte de la línea
                        if domain_lower in line.lower():
                            results.append(line)
                        
                        if len(results) >= max_results:
                            break
            
            except Exception as e:
                logger.error(f"Error en {file_path}: {e}")
                continue
        
        return len(results), results
    
    def search_email(self, email: str, max_results: int = 1000) -> Tuple[int, List[str]]:
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
                        
                        # Buscar email específico
                        if email_lower in line.lower():
                            results.append(line)
                        
                        if len(results) >= max_results:
                            break
            
            except Exception as e:
                logger.error(f"Error en {file_path}: {e}")
                continue
        
        return len(results), results
    
    def search_dni(self, dni: str, max_results: int = 1000) -> Tuple[int, List[str]]:
        results = []
        dni_lower = dni.lower()
        
        for file_path in self.data_files:
            if len(results) >= max_results:
                break
            
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        
                        # Buscar DNI en cualquier parte
                        if dni_lower in line.lower():
                            results.append(line)
                        
                        if len(results) >= max_results:
                            break
            
            except Exception as e:
                logger.error(f"Error en {file_path}: {e}")
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
# SISTEMA DE CRÉDITOS
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
                    free_credits INTEGER DEFAULT 5,
                    total_searches INTEGER DEFAULT 0,
                    join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
    
    def get_or_create_user(self, user_id: int, username: str = "", first_name: str = ""):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
            user = cursor.fetchone()
            
            if user:
                return dict(user)
            
            cursor.execute('''
                INSERT INTO users (user_id, username, first_name, free_credits)
                VALUES (?, ?, ?, ?)
            ''', (user_id, username, first_name, MAX_FREE_CREDITS))
            
            conn.commit()
            return {
                'user_id': user_id,
                'username': username,
                'first_name': first_name,
                'free_credits': MAX_FREE_CREDITS
            }
    
    def get_user_credits(self, user_id: int) -> int:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT free_credits FROM users WHERE user_id = ?', (user_id,))
            result = cursor.fetchone()
            return result['free_credits'] if result else 0
    
    def has_enough_credits(self, user_id: int) -> bool:
        return self.get_user_credits(user_id) > 0
    
    def use_credits(self, user_id: int, search_type: str, query: str, results_count: int = 0):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute(
                'SELECT free_credits FROM users WHERE user_id = ?',
                (user_id,)
            )
            result = cursor.fetchone()
            
            if not result or result['free_credits'] < 1:
                return False
            
            cursor.execute('''
                UPDATE users 
                SET free_credits = free_credits - 1,
                    total_searches = total_searches + 1
                WHERE user_id = ?
            ''', (user_id,))
            
            cursor.execute('''
                INSERT INTO transactions 
                (user_id, amount, type, description)
                VALUES (?, ?, ?, ?)
            ''', (user_id, -1, 'search_used', f'{search_type}: {query}'))
            
            conn.commit()
            return True
    
    def add_credits_to_user(self, user_id: int, amount: int, admin_id: int) -> Tuple[bool, str]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute(
                'SELECT free_credits FROM users WHERE user_id = ?',
                (user_id,)
            )
            result = cursor.fetchone()
            
            if not result:
                return False, "Usuario no encontrado"
            
            cursor.execute(
                'UPDATE users SET free_credits = free_credits + ? WHERE user_id = ?',
                (amount, user_id)
            )
            
            cursor.execute('''
                INSERT INTO transactions 
                (user_id, amount, type, description)
                VALUES (?, ?, ?, ?)
            ''', (user_id, amount, 'admin_add', f'Créditos añadidos por admin {admin_id}'))
            
            conn.commit()
            return True, f"✅ {amount} créditos añadidos"
    
    def get_user_info(self, user_id: int):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
            result = cursor.fetchone()
            return dict(result) if result else None
    
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
            
            cursor.execute('SELECT SUM(free_credits) as total FROM users')
            stats['total_credits'] = cursor.fetchone()['total'] or 0
            
            return stats

# ============================================================================
# BOT PRINCIPAL
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
        user_info = self.credit_system.get_or_create_user(
            user_id=user.id,
            username=user.username or "",
            first_name=user.first_name or ""
        )
        
        credits = self.credit_system.get_user_credits(user.id)
        stats = self.search_engine.get_stats()
        
        keyboard = [
            [InlineKeyboardButton("🔍 Buscar Dominio", callback_data="menu_search")],
            [InlineKeyboardButton("📧 Buscar Email", callback_data="menu_email")],
            [InlineKeyboardButton("💰 Mis Créditos", callback_data="menu_credits")],
            [InlineKeyboardButton("📋 /help", callback_data="menu_help")],
        ]
        
        if user.id in ADMIN_IDS:
            keyboard.append([InlineKeyboardButton("👑 Admin", callback_data="menu_admin")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message = (
            f"<b>👋 Bienvenido {self.escape_html(user.first_name)}!</b>\n\n"
            f"<b>🚀 {BOT_NAME}</b>\n"
            f"<b>📍 Versión:</b> {BOT_VERSION}\n\n"
            f"<b>💰 Tus créditos:</b> <code>{credits}</code>\n"
            f"<b>📁 Archivos en BD:</b> <code>{stats['total_files']}</code>\n\n"
            f"<i>Usa los botones para comenzar</i>"
        )
        
        await update.message.reply_text(message, parse_mode='HTML', reply_markup=reply_markup)
    
    async def search_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        if not self.credit_system.has_enough_credits(user_id):
            await update.message.reply_text(
                f"<b>❌ NO TIENES CRÉDITOS</b>\n\n"
                f"Usa /mycredits para ver tus créditos.\n"
                f"Contacta a {BOT_OWNER} para más créditos.",
                parse_mode='HTML'
            )
            return ConversationHandler.END
        
        if not context.args:
            await update.message.reply_text(
                "<b>❌ Uso:</b> <code>/search dominio.com</code>\n\n"
                "<b>Ejemplos:</b>\n"
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
            [InlineKeyboardButton("❌ Cancelar", callback_data="format_cancel")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"<b>🔍 BUSCAR DOMINIO</b>\n\n"
            f"<b>Dominio:</b> <code>{self.escape_html(query)}</code>\n"
            f"<b>Créditos:</b> <code>{self.credit_system.get_user_credits(user_id)}</code>\n\n"
            f"<b>Selecciona formato:</b>",
            parse_mode='HTML',
            reply_markup=reply_markup
        )
        
        return CHOOSING_FORMAT
    
    async def format_selected_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        
        if user_id not in self.pending_searches:
            await query.edit_message_text("❌ Búsqueda expirada.")
            return ConversationHandler.END
        
        if query.data == "format_cancel":
            await query.edit_message_text("✅ Cancelada.")
            del self.pending_searches[user_id]
            return ConversationHandler.END
        
        search_data = self.pending_searches[user_id]
        domain = search_data["query"]
        
        await query.edit_message_text(f"🔄 <b>Buscando {self.escape_html(domain)}...</b>", parse_mode='HTML')
        
        # Realizar búsqueda
        total_found, results = self.search_engine.search_domain(domain)
        
        if total_found == 0:
            await query.edit_message_text(
                f"<b>❌ NO ENCONTRADO</b>\n\n"
                f"<b>Dominio:</b> <code>{self.escape_html(domain)}</code>\n"
                f"<b>Archivos escaneados:</b> <code>{self.search_engine.get_stats()['total_files']}</code>\n\n"
                f"💰 <b>Crédito NO consumido</b>",
                parse_mode='HTML'
            )
            del self.pending_searches[user_id]
            return ConversationHandler.END
        
        # Usar crédito
        self.credit_system.use_credits(user_id, "domain", domain, total_found)
        credits_left = self.credit_system.get_user_credits(user_id)
        
        # Enviar resultados
        if total_found > 100:
            await self.send_results_as_txt(query, results, domain, total_found, credits_left)
        else:
            await self.send_results_as_message(query, results, domain, total_found, credits_left)
        
        del self.pending_searches[user_id]
        return ConversationHandler.END
    
    async def send_results_as_txt(self, query_callback, results: list, domain: str, total_found: int, credits_left: int):
        txt_buffer = io.BytesIO()
        content = "\n".join(results)
        txt_buffer.write(content.encode('utf-8'))
        txt_buffer.seek(0)
        
        await query_callback.message.reply_document(
            document=txt_buffer,
            filename=f"ulp_{domain}.txt",
            caption=(
                f"<b>📁 RESULTADOS</b>\n\n"
                f"<b>Dominio:</b> <code>{self.escape_html(domain)}</code>\n"
                f"<b>Resultados:</b> <code>{total_found}</code>\n"
                f"<b>Créditos restantes:</b> <code>{credits_left}</code>"
            ),
            parse_mode='HTML'
        )
        
        await query_callback.edit_message_text(
            f"<b>✅ BÚSQUEDA COMPLETADA</b>\n\n"
            f"<b>Dominio:</b> <code>{self.escape_html(domain)}</code>\n"
            f"<b>Resultados:</b> <code>{total_found}</code>\n"
            f"<b>Créditos restantes:</b> <code>{credits_left}</code>\n\n"
            f"<i>Resultados enviados como archivo</i>",
            parse_mode='HTML'
        )
    
    async def send_results_as_message(self, query_callback, results: list, domain: str, total_found: int, credits_left: int):
        response = (
            f"<b>✅ BÚSQUEDA COMPLETADA</b>\n\n"
            f"<b>Dominio:</b> <code>{self.escape_html(domain)}</code>\n"
            f"<b>Resultados:</b> <code>{total_found}</code>\n"
            f"<b>Créditos restantes:</b> <code>{credits_left}</code>\n\n"
            f"<b>Primeros resultados:</b>\n"
            f"<pre>"
        )
        
        for line in results[:10]:
            if len(line) > 80:
                line = line[:77] + "..."
            response += f"{self.escape_html(line)}\n"
        
        response += "</pre>"
        
        if total_found > 10:
            response += f"\n<b>... y {total_found-10} resultados más</b>"
        
        await query_callback.edit_message_text(response, parse_mode='HTML')
    
    async def email_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        if not self.credit_system.has_enough_credits(user_id):
            await update.message.reply_text("<b>❌ NO TIENES CRÉDITOS</b>", parse_mode='HTML')
            return
        
        if not context.args:
            await update.message.reply_text(
                "<b>❌ Uso:</b> <code>/email usuario@gmail.com</code>",
                parse_mode='HTML'
            )
            return
        
        email = context.args[0].lower()
        msg = await update.message.reply_text(f"📧 <b>Buscando {self.escape_html(email)}...</b>", parse_mode='HTML')
        
        total_found, results = self.search_engine.search_email(email)
        
        if total_found == 0:
            await msg.edit_text(
                f"<b>❌ NO ENCONTRADO</b>\n\n"
                f"<b>Email:</b> <code>{self.escape_html(email)}</code>",
                parse_mode='HTML'
            )
            return
        
        self.credit_system.use_credits(user_id, "email", email, total_found)
        credits_left = self.credit_system.get_user_credits(user_id)
        
        response = (
            f"<b>✅ EMAIL ENCONTRADO</b>\n\n"
            f"<b>Email:</b> <code>{self.escape_html(email)}</code>\n"
            f"<b>Resultados:</b> <code>{total_found}</code>\n"
            f"<b>Créditos restantes:</b> <code>{credits_left}</code>\n\n"
            f"<b>Primeros resultados:</b>\n"
            f"<pre>"
        )
        
        for line in results[:5]:
            response += f"{self.escape_html(line)}\n"
        
        response += "</pre>"
        
        await msg.edit_text(response, parse_mode='HTML')
    
    async def dni_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        if not self.credit_system.has_enough_credits(user_id):
            await update.message.reply_text("<b>❌ NO TIENES CRÉDITOS</b>", parse_mode='HTML')
            return
        
        if not context.args:
            await update.message.reply_text(
                "<b>❌ Uso:</b> <code>/dni 12345678A</code>",
                parse_mode='HTML'
            )
            return
        
        dni = context.args[0].upper()
        msg = await update.message.reply_text(f"🆔 <b>Buscando {self.escape_html(dni)}...</b>", parse_mode='HTML')
        
        total_found, results = self.search_engine.search_dni(dni)
        
        if total_found == 0:
            await msg.edit_text(
                f"<b>❌ NO ENCONTRADO</b>\n\n"
                f"<b>DNI:</b> <code>{self.escape_html(dni)}</code>",
                parse_mode='HTML'
            )
            return
        
        self.credit_system.use_credits(user_id, "dni", dni, total_found)
        credits_left = self.credit_system.get_user_credits(user_id)
        
        response = (
            f"<b>✅ DNI ENCONTRADO</b>\n\n"
            f"<b>DNI:</b> <code>{self.escape_html(dni)}</code>\n"
            f"<b>Resultados:</b> <code>{total_found}</code>\n"
            f"<b>Créditos restantes:</b> <code>{credits_left}</code>\n\n"
            f"<b>Primeros resultados:</b>\n"
            f"<pre>"
        )
        
        for line in results[:5]:
            response += f"{self.escape_html(line)}\n"
        
        response += "</pre>"
        
        await msg.edit_text(response, parse_mode='HTML')
    
    async def mycredits_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        credits = self.credit_system.get_user_credits(user_id)
        user_info = self.credit_system.get_user_info(user_id)
        
        response = (
            f"<b>💰 TUS CRÉDITOS</b>\n\n"
            f"👤 <b>Usuario:</b> @{update.effective_user.username or update.effective_user.first_name}\n"
            f"🆔 <b>ID:</b> <code>{user_id}</code>\n"
            f"💰 <b>Créditos disponibles:</b> <code>{credits}</code>\n"
            f"🔍 <b>Búsquedas totales:</b> <code>{user_info.get('total_searches', 0) if user_info else 0}</code>\n\n"
            f"<b>💡 INFORMACIÓN:</b>\n"
            f"• 1 crédito = 1 búsqueda\n"
            f"• Máximo {MAX_FREE_CREDITS} créditos gratis\n"
            f"• Contacta a {BOT_OWNER} para más créditos"
        )
        
        await update.message.reply_text(response, parse_mode='HTML')
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        help_text = (
            f"<b>📚 {BOT_NAME} - AYUDA</b>\n\n"
            f"<b>🔍 COMANDOS:</b>\n"
            f"<code>/search dominio.com</code> - Buscar por dominio\n"
            f"<code>/email correo@gmail.com</code> - Buscar por email\n"
            f"<code>/dni 12345678A</code> - Buscar DNI\n"
            f"<code>/mycredits</code> - Ver tus créditos\n"
            f"<code>/upload</code> - Subir archivo (admin)\n\n"
            
            f"<b>💰 SISTEMA:</b>\n"
            f"• {MAX_FREE_CREDITS} créditos gratis iniciales\n"
            f"• 1 búsqueda = 1 crédito\n"
            f"• Contacta a {BOT_OWNER} para más créditos\n\n"
            
            f"<b>📁 FORMATOS:</b>\n"
            f"• email:password\n"
            f"• dominio:email:password\n"
            f"• usuario:password\n\n"
            
            f"<i>Bot desarrollado por {BOT_OWNER}</i>"
        )
        
        await update.message.reply_text(help_text, parse_mode='HTML')
    
    # ==================== ADMIN ====================
    
    async def addcredits_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        if user_id not in ADMIN_IDS:
            await update.message.reply_text("❌ Solo para administradores.")
            return
        
        if len(context.args) < 2:
            await update.message.reply_text(
                "<b>❌ Uso:</b> <code>/addcredits user_id cantidad</code>\n\n"
                "<b>Ejemplo:</b> <code>/addcredits 123456789 5</code>",
                parse_mode='HTML'
            )
            return
        
        try:
            target_user = int(context.args[0])
            amount = int(context.args[1])
            
            success, message = self.credit_system.add_credits_to_user(target_user, amount, user_id)
            
            if success:
                await update.message.reply_text(
                    f"<b>✅ CRÉDITOS AÑADIDOS</b>\n\n"
                    f"<b>Usuario:</b> <code>{target_user}</code>\n"
                    f"<b>Cantidad:</b> <code>{amount}</code>\n"
                    f"<b>Admin:</b> @{update.effective_user.username}",
                    parse_mode='HTML'
                )
            else:
                await update.message.reply_text(f"❌ {message}")
                
        except ValueError:
            await update.message.reply_text("❌ Error: ID o cantidad inválida")
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {str(e)}")
    
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        if user_id not in ADMIN_IDS:
            await update.message.reply_text("❌ Solo para administradores.")
            return
        
        bot_stats = self.credit_system.get_bot_stats()
        engine_stats = self.search_engine.get_stats()
        
        response = (
            f"<b>📊 ESTADÍSTICAS DEL BOT</b>\n\n"
            f"👥 <b>Usuarios:</b> <code>{bot_stats['total_users']}</code>\n"
            f"🔍 <b>Búsquedas totales:</b> <code>{bot_stats['total_searches']}</code>\n"
            f"💰 <b>Créditos otorgados:</b> <code>{bot_stats['total_credits']}</code>\n"
            f"📁 <b>Archivos en BD:</b> <code>{engine_stats['total_files']}</code>\n\n"
            f"🤖 <b>Versión:</b> {BOT_VERSION}\n"
            f"👑 <b>Admin:</b> @{update.effective_user.username}"
        )
        
        await update.message.reply_text(response, parse_mode='HTML')
    
    async def userslist_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        if user_id not in ADMIN_IDS:
            await update.message.reply_text("❌ Solo para administradores.")
            return
        
        users = self.credit_system.get_all_users(limit=20)
        
        if not users:
            await update.message.reply_text("📭 No hay usuarios registrados.")
            return
        
        response = "<b>📋 USUARIOS REGISTRADOS</b>\n\n"
        
        for i, user in enumerate(users, 1):
            username = f"@{user['username']}" if user['username'] else user['first_name']
            response += f"{i}. {username} (<code>{user['user_id']}</code>) - 💰{user['free_credits']}\n"
        
        await update.message.reply_text(response, parse_mode='HTML')
    
    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        if user_id not in ADMIN_IDS:
            await update.message.reply_text("❌ Solo administradores pueden subir archivos.")
            return
        
        document = update.message.document
        
        if not document.file_name.endswith('.txt'):
            await update.message.reply_text("❌ Solo archivos .txt")
            return
        
        msg = await update.message.reply_text(f"📤 <b>Procesando {self.escape_html(document.file_name)}...</b>", parse_mode='HTML')
        
        try:
            file = await document.get_file()
            temp_path = os.path.join(UPLOAD_DIR, document.file_name)
            await file.download_to_drive(temp_path)
            
            success, result = self.search_engine.add_data_file(temp_path)
            
            if success:
                stats = self.search_engine.get_stats()
                await msg.edit_text(
                    f"<b>✅ ARCHIVO PROCESADO</b>\n\n"
                    f"<b>Nombre:</b> <code>{self.escape_html(document.file_name)}</code>\n"
                    f"<b>Archivos totales:</b> <code>{stats['total_files']}</code>\n\n"
                    f"✅ <i>Listo para búsquedas</i>",
                    parse_mode='HTML'
                )
            else:
                await msg.edit_text(
                    f"<b>❌ ERROR</b>\n\n"
                    f"<b>Archivo:</b> <code>{self.escape_html(document.file_name)}</code>\n"
                    f"<b>Error:</b> {result}",
                    parse_mode='HTML'
                )
        
        except Exception as e:
            await msg.edit_text(
                f"<b>❌ ERROR CRÍTICO</b>\n\n"
                f"Error: {self.escape_html(str(e)[:200])}",
                parse_mode='HTML'
            )
    
    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        
        if query.data == "menu_search":
            await query.edit_message_text(
                "<b>🔍 BUSCAR DOMINIO</b>\n\n"
                "Envía: <code>/search dominio.com</code>\n\n"
                "<b>Ejemplos:</b>\n"
                "<code>/search gmail.com</code>\n"
                "<code>/search facebook.com</code>",
                parse_mode='HTML'
            )
        
        elif query.data == "menu_email":
            await query.edit_message_text(
                "<b>📧 BUSCAR EMAIL</b>\n\n"
                "Envía: <code>/email usuario@gmail.com</code>",
                parse_mode='HTML'
            )
        
        elif query.data == "menu_credits":
            credits = self.credit_system.get_user_credits(user_id)
            await query.edit_message_text(
                f"<b>💰 TUS CRÉDITOS</b>\n\n"
                f"💰 <b>Disponibles:</b> <code>{credits}</code>\n\n"
                f"<i>Usa /mycredits para detalles</i>",
                parse_mode='HTML'
            )
        
        elif query.data == "menu_help":
            await self.help_command(update, context)
        
        elif query.data == "menu_admin":
            if user_id not in ADMIN_IDS:
                await query.edit_message_text("❌ Solo para administradores.")
                return
            
            keyboard = [
                [InlineKeyboardButton("📊 Estadísticas", callback_data="admin_stats")],
                [InlineKeyboardButton("📋 Listar Usuarios", callback_data="admin_users")],
                [InlineKeyboardButton("📤 Subir Archivo", callback_data="admin_upload")],
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                "<b>👑 PANEL ADMIN</b>\n\n"
                "<i>Selecciona una opción:</i>",
                parse_mode='HTML',
                reply_markup=reply_markup
            )
        
        elif query.data == "admin_stats":
            await self.stats_command(update, context)
        
        elif query.data == "admin_users":
            await self.userslist_command(update, context)
        
        elif query.data == "admin_upload":
            await query.edit_message_text(
                "<b>📤 SUBIR ARCHIVO</b>\n\n"
                "Para subir un archivo:\n"
                "1. Envía un archivo .txt\n"
                "2. Formato: email:pass o url:email:pass\n"
                "3. Máximo 50MB\n\n"
                "El archivo se indexará automáticamente.",
                parse_mode='HTML'
            )

# ============================================================================
# EJECUCIÓN PRINCIPAL
# ============================================================================

def run_flask():
    app.run(host='0.0.0.0', port=PORT, threaded=True)

def main():
    logger.info(f"🚀 Iniciando {BOT_NAME} v{BOT_VERSION}")
    
    search_engine = SearchEngine()
    credit_system = CreditSystem()
    bot = ULPBot(search_engine, credit_system)
    
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Handlers de búsqueda
    search_conv = ConversationHandler(
        entry_points=[CommandHandler('search', bot.search_command)],
        states={
            CHOOSING_FORMAT: [
                CallbackQueryHandler(bot.format_selected_handler, pattern='^format_')
            ]
        },
        fallbacks=[CommandHandler('cancel', lambda u, c: ConversationHandler.END)]
    )
    
    # Comandos básicos
    application.add_handler(CommandHandler("start", bot.start))
    application.add_handler(CommandHandler("help", bot.help_command))
    application.add_handler(CommandHandler("mycredits", bot.mycredits_command))
    application.add_handler(search_conv)
    application.add_handler(CommandHandler("email", bot.email_command))
    application.add_handler(CommandHandler("dni", bot.dni_command))
    
    # Comandos admin
    application.add_handler(CommandHandler("addcredits", bot.addcredits_command))
    application.add_handler(CommandHandler("stats", bot.stats_command))
    application.add_handler(CommandHandler("userslist", bot.userslist_command))
    application.add_handler(MessageHandler(filters.Document.ALL, bot.handle_document))
    
    # Handlers de botones
    application.add_handler(CallbackQueryHandler(bot.button_handler, pattern='^menu_'))
    application.add_handler(CallbackQueryHandler(bot.button_handler, pattern='^admin_'))
    
    # Iniciar Flask
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info(f"🌐 Flask en puerto {PORT}")
    
    # Iniciar bot
    logger.info("🤖 Bot iniciado")
    application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

if __name__ == '__main__':
    main()
