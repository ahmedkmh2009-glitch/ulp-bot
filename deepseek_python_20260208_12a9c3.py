"""
ULP Searcher Bot - Con selección de formato y compresión ZIP para archivos grandes
Todo en un solo archivo para Render.com
"""

import os
import json
import logging
import asyncio
import aiohttp
import sqlite3
import hashlib
import threading
import time
import zipfile
import io
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from contextlib import contextmanager

from flask import Flask, request, jsonify
from telegram import (
    Update, InlineKeyboardButton, 
    InlineKeyboardMarkup
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    ContextTypes, CallbackQueryHandler, filters,
    ConversationHandler
)

# ============================================================================
# CONFIGURACIÓN
# ============================================================================

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
ULP_API_TOKEN = os.getenv('ULP_API_TOKEN')
ADMIN_IDS = [int(id.strip()) for id in os.getenv('ADMIN_IDS', '').split(',') if id.strip()]
SECRET_KEY = os.getenv('SECRET_KEY', 'default-secret-change-me')
MAX_FREE_CREDITS = 2

BOT_OWNER = "@iberic_owner"
BOT_NAME = "ULP Searcher Bot"
ULP_ROWS = "2,92 billion"

PORT = int(os.getenv('PORT', 10000))
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

# Estados para ConversationHandler
CHOOSING_FORMAT = 1

# ============================================================================
# LOGGING
# ============================================================================

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# ============================================================================
# FLASK APP
# ============================================================================

app = Flask(__name__)
app.secret_key = SECRET_KEY

@app.route('/')
def home():
    return jsonify({"status": "online", "service": BOT_NAME})

@app.route('/health')
def health():
    return jsonify({"status": "healthy"})

# ============================================================================
# SISTEMA DE CRÉDITOS
# ============================================================================

class CreditSystem:
    """Sistema de créditos gratis"""
    
    def __init__(self, db_path: str = "ulp_bot.db"):
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
                    last_name TEXT,
                    join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    free_credits INTEGER DEFAULT 2,
                    total_searches INTEGER DEFAULT 0
                )
            ''')
            
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
            
            conn.commit()
    
    def get_or_create_user(self, user_id: int, username: str = "", first_name: str = "", last_name: str = ""):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
            user = cursor.fetchone()
            
            if user:
                return dict(user)
            
            cursor.execute('''
                INSERT INTO users (user_id, username, first_name, last_name, free_credits)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, username, first_name, last_name, MAX_FREE_CREDITS))
            
            conn.commit()
            
            return {
                'user_id': user_id,
                'username': username,
                'first_name': first_name,
                'last_name': last_name,
                'free_credits': MAX_FREE_CREDITS,
                'total_searches': 0
            }
    
    def get_user_credits(self, user_id: int):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT free_credits FROM users WHERE user_id = ?', (user_id,))
            result = cursor.fetchone()
            return result['free_credits'] if result else 0
    
    def has_credits(self, user_id: int):
        return self.get_user_credits(user_id) > 0
    
    def use_credits(self, user_id: int, search_type: str, query: str, format_used: str, results_count: int):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE users 
                SET free_credits = free_credits - 1,
                    total_searches = total_searches + 1
                WHERE user_id = ?
            ''', (user_id,))
            
            cursor.execute('''
                INSERT INTO searches (user_id, search_type, query, format_used, results_count)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, search_type, query, format_used, results_count))
            
            conn.commit()
            return True
    
    def add_credits(self, user_id: int, amount: int, admin_id: int):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('SELECT free_credits FROM users WHERE user_id = ?', (user_id,))
            result = cursor.fetchone()
            
            if not result:
                return False, 0
            
            current = result['free_credits']
            new_total = min(current + amount, MAX_FREE_CREDITS)
            added = new_total - current
            
            cursor.execute('UPDATE users SET free_credits = ? WHERE user_id = ?', (new_total, user_id))
            
            conn.commit()
            return True, added
    
    def get_user_stats(self, user_id: int):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT u.*, COUNT(s.id) as searches_done
                FROM users u
                LEFT JOIN searches s ON u.user_id = s.user_id
                WHERE u.user_id = ?
                GROUP BY u.user_id
            ''', (user_id,))
            result = cursor.fetchone()
            return dict(result) if result else None

# ============================================================================
# CLIENTE API ULP CON FORMATOS
# ============================================================================

class ULPAPIClient:
    """Cliente para API con selección de formatos"""
    
    def __init__(self, credit_system: CreditSystem):
        self.base_url = "https://enginesearch.top"
        self.token = ULP_API_TOKEN
        self.credit_system = credit_system
        self.session = None
    
    async def init_session(self):
        if not self.session:
            self.session = aiohttp.ClientSession()
    
    async def make_request(self, endpoint: str, params: Dict):
        try:
            await self.init_session()
            async with self.session.get(
                f"{self.base_url}{endpoint}", 
                params=params, 
                timeout=60
            ) as response:
                
                if response.status == 200:
                    text = await response.text()
                    return True, text.strip()
                elif response.status == 401:
                    return False, "❌ Token inválido"
                elif response.status == 403:
                    return False, "❌ Límite alcanzado"
                elif response.status == 404:
                    return False, "❌ No se encontraron resultados"
                else:
                    return False, f"❌ Error {response.status}"
                    
        except Exception as e:
            logger.error(f"API Error: {e}")
            return False, f"❌ Error de conexión"
    
    async def search_with_format(self, search_type: str, query: str, format_choice: str, offset: int = 0):
        """Búsqueda con formato específico"""
        endpoints = {
            "domain": "/search",
            "email": "/mail",
            "login": "/login",
            "password": "/password",
            "mailpass": "/mailpassword"
        }
        
        if search_type not in endpoints:
            return False, "❌ Tipo inválido"
        
        endpoint = endpoints[search_type]
        params = {"token": self.token}
        
        # Parámetros según tipo
        if search_type == "domain":
            params["query"] = query
            params["format"] = format_choice
            if offset > 0:
                params["offset"] = offset
        elif search_type == "email":
            params["email"] = query
        elif search_type == "login":
            params["login"] = query
        elif search_type == "password":
            params["password"] = query
        elif search_type == "mailpass":
            params["password"] = query
        
        return await self.make_request(endpoint, params)

# ============================================================================
# MANEJADORES CON SELECCIÓN DE FORMATO
# ============================================================================

class TelegramBotHandlers:
    def __init__(self, api_client: ULPAPIClient, credit_system: CreditSystem):
        self.api = api_client
        self.credit_system = credit_system
        self.pending_searches: Dict[int, Dict] = {}  # user_id -> {query, type}
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        
        self.credit_system.get_or_create_user(
            user_id=user.id,
            username=user.username or "",
            first_name=user.first_name or "",
            last_name=user.last_name or ""
        )
        
        keyboard = [
            [InlineKeyboardButton("🔍 Buscar Dominio", callback_data="search_domain")],
            [InlineKeyboardButton("📧 Buscar Email", callback_data="search_email")],
            [InlineKeyboardButton("💰 Mis Créditos", callback_data="my_credits")],
            [InlineKeyboardButton("📊 /info", callback_data="bot_info")],
        ]
        
        if user.id in ADMIN_IDS:
            keyboard.append([InlineKeyboardButton("👑 Admin", callback_data="admin_panel")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        credits = self.credit_system.get_user_credits(user.id)
        
        welcome = (
            f"👋 *Hola {user.first_name}!*\n\n"
            f"🚀 *ULP Searcher Bot*\n\n"
            f"🎯 *Tu estado:*\n"
            f"• 🆓 Créditos: `{credits}`/{MAX_FREE_CREDITS}\n"
            f"• 🔍 Búsquedas: `{credits}` disponibles\n\n"
            f"*Nueva función:*\n"
            f"• 🔘 Selecciona formato de resultados\n"
            f"• 📁 Archivos ZIP para resultados grandes\n\n"
            f"Usa /help para ver comandos"
        )
        
        await update.message.reply_text(welcome, parse_mode='Markdown', reply_markup=reply_markup)
    
    async def search_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Inicia búsqueda de dominio con selección de formato"""
        user_id = update.effective_user.id
        
        # Verificar créditos
        if not self.credit_system.has_credits(user_id):
            await update.message.reply_text(
                f"❌ *NO TIENES CRÉDITOS*\n\n"
                f"Usa /mycredits para ver tus créditos.\n"
                f"Contacta a {BOT_OWNER} para más créditos.",
                parse_mode='Markdown'
            )
            return ConversationHandler.END
        
        if not context.args:
            await update.message.reply_text(
                "❌ *Uso:* `/search <dominio>`\n"
                "Ejemplo: `/search vk.com`\n"
                "Ejemplo: `/search facebook.com`",
                parse_mode='Markdown'
            )
            return ConversationHandler.END
        
        query = context.args[0]
        
        # Guardar búsqueda pendiente
        self.pending_searches[user_id] = {
            "type": "domain",
            "query": query,
            "offset": 0
        }
        
        # Mostrar teclado para seleccionar formato
        keyboard = [
            [
                InlineKeyboardButton("🔐 email:pass", callback_data="format_emailpass"),
                InlineKeyboardButton("🔗 url:email:pass", callback_data="format_urlemailpass")
            ],
            [
                InlineKeyboardButton("👤 login:pass", callback_data="format_loginpass"),
                InlineKeyboardButton("📧 email only", callback_data="format_emailonly")
            ],
            [
                InlineKeyboardButton("❌ Cancelar", callback_data="format_cancel")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"🔍 *BÚSQUEDA CONFIGURADA*\n\n"
            f"*Dominio:* `{query}`\n"
            f"*Créditos disponibles:* `{self.credit_system.get_user_credits(user_id)}`\n\n"
            f"📋 *Elige formato de resultados:*\n\n"
            f"• 🔐 *email:pass* - Correo y contraseña\n"
            f"• 🔗 *url:email:pass* - URL completo\n"
            f"• 👤 *login:pass* - Usuario y contraseña\n"
            f"• 📧 *email only* - Solo correos\n",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        
        return CHOOSING_FORMAT
    
    async def email_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Búsqueda por email (sin selección de formato)"""
        user_id = update.effective_user.id
        
        if not self.credit_system.has_credits(user_id):
            await update.message.reply_text(
                f"❌ *NO TIENES CRÉDITOS*\n\n"
                f"Usa /mycredits para ver tus créditos.",
                parse_mode='Markdown'
            )
            return
        
        if not context.args:
            await update.message.reply_text(
                "❌ *Uso:* `/email <correo>`\n"
                "Ejemplo: `/email ejemplo@gmail.com`",
                parse_mode='Markdown'
            )
            return
        
        email = context.args[0]
        
        if '@' not in email or '.' not in email:
            await update.message.reply_text("❌ Formato de email inválido")
            return
        
        await self.perform_search(update, context, "email", email, "password_only")
    
    async def format_selected(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Usuario selecciona formato"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        
        if user_id not in self.pending_searches:
            await query.edit_message_text("❌ Búsqueda expirada. Comienza de nuevo.")
            return ConversationHandler.END
        
        if query.data == "format_cancel":
            await query.edit_message_text("❌ Búsqueda cancelada.")
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
        
        # Obtener datos de búsqueda
        search_data = self.pending_searches[user_id]
        search_type = search_data["type"]
        query_text = search_data["query"]
        
        # Mostrar confirmación
        format_display = {
            "login:pass": "🔐 email:pass",
            "url:login:pass": "🔗 url:email:pass", 
            "url": "📧 email only"
        }
        
        await query.edit_message_text(
            f"✅ *FORMATO SELECCIONADO*\n\n"
            f"*Dominio:* `{query_text}`\n"
            f"*Formato:* {format_display.get(selected_format, selected_format)}\n\n"
            f"🔄 *Iniciando búsqueda...*",
            parse_mode='Markdown'
        )
        
        # Realizar búsqueda
        await self.perform_search_with_format(
            update=update,
            context=context,
            search_type=search_type,
            query=query_text,
            format_choice=selected_format,
            user_id=user_id
        )
        
        # Limpiar búsqueda pendiente
        del self.pending_searches[user_id]
        
        return ConversationHandler.END
    
    async def perform_search_with_format(self, update: Update, context: ContextTypes.DEFAULT_TYPE, 
                                         search_type: str, query: str, format_choice: str, user_id: int):
        """Ejecutar búsqueda con formato específico"""
        
        # Usar crédito
        self.credit_system.use_credits(user_id, search_type, query, format_choice, 0)
        
        # Realizar búsqueda
        success, raw_result = await self.api.search_with_format(search_type, query, format_choice)
        
        if not success:
            # Reembolsar crédito
            self.credit_system.add_credits(user_id, 1, 0)
            await update.callback_query.edit_message_text(
                f"❌ *ERROR EN BÚSQUEDA*\n\n{raw_result}\n\n💰 Crédito reembolsado"
            )
            return
        
        # Procesar resultados
        lines = raw_result.strip().split('\n')
        total_results = len(lines) if lines and lines[0] else 0
        
        if total_results == 0:
            self.credit_system.add_credits(user_id, 1, 0)
            await update.callback_query.edit_message_text(
                f"❌ *SIN RESULTADOS*\n\n"
                f"*Dominio:* `{query}`\n"
                f"*Formato:* `{format_choice}`\n\n"
                f"💰 Crédito reembolsado"
            )
            return
        
        # Actualizar contador de resultados
        with self.credit_system.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'UPDATE searches SET results_count = ? WHERE user_id = ? AND query = ? ORDER BY id DESC LIMIT 1',
                (total_results, user_id, query)
            )
            conn.commit()
        
        # Verificar si es grande (> 10,000 líneas)
        if total_results > 10000:
            await self.send_as_zip(
                update=update,
                context=context,
                lines=lines,
                query=query,
                search_type=search_type,
                format_choice=format_choice,
                total_results=total_results,
                user_id=user_id
            )
        elif total_results > 100:
            await self.send_as_txt_file(
                update=update,
                context=context,
                lines=lines,
                query=query,
                search_type=search_type,
                format_choice=format_choice,
                total_results=total_results,
                user_id=user_id
            )
        else:
            await self.send_as_message(
                update=update,
                context=context,
                lines=lines,
                query=query,
                search_type=search_type,
                format_choice=format_choice,
                total_results=total_results,
                user_id=user_id
            )
    
    async def send_as_zip(self, update: Update, context: ContextTypes.DEFAULT_TYPE, lines: list, 
                          query: str, search_type: str, format_choice: str, total_results: int, user_id: int):
        """Enviar resultados comprimidos en ZIP"""
        
        # Crear archivo en memoria
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # Crear archivo de texto dentro del ZIP
            txt_content = '\n'.join(lines)
            zip_file.writestr(f"{query}_{format_choice}.txt", txt_content)
            
            # Añadir información del archivo
            info_content = f"""Resultados de búsqueda ULP
Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Dominio: {query}
Formato: {format_choice}
Resultados: {total_results:,}
Líneas: {len(lines):,}
Generado por: @{update.callback_query.from_user.username or update.callback_query.from_user.first_name}
"""
            zip_file.writestr("INFO.txt", info_content)
        
        zip_buffer.seek(0)
        
        # Créditos restantes
        remaining = self.credit_system.get_user_credits(user_id)
        
        # Enviar archivo ZIP
        await update.callback_query.message.reply_document(
            document=zip_buffer,
            filename=f"{query}_{format_choice}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
            caption=(
                f"📦 *ARCHIVO ZIP COMPRIMIDO*\n\n"
                f"🔍 *Búsqueda:* {search_type}\n"
                f"📝 *Query:* `{query}`\n"
                f"📋 *Formato:* `{format_choice}`\n"
                f"📊 *Resultados:* `{total_results:,}`\n"
                f"💰 *Créditos restantes:* `{remaining}`\n\n"
                f"*Contenido:*\n"
                f"• `{query}_{format_choice}.txt` - Resultados\n"
                f"• `INFO.txt` - Información\n\n"
                f"_Archivo comprimido para mejor envío_"
            ),
            parse_mode='Markdown'
        )
        
        await update.callback_query.edit_message_text(
            f"✅ *BÚSQUEDA COMPLETADA*\n\n"
            f"*Dominio:* `{query}`\n"
            f"*Formato:* `{format_choice}`\n"
            f"*Resultados:* `{total_results:,}`\n\n"
            f"📦 *Archivo enviado como ZIP*\n"
            f"💰 *Créditos restantes:* `{remaining}`"
        )
    
    async def send_as_txt_file(self, update: Update, context: ContextTypes.DEFAULT_TYPE, lines: list,
                               query: str, search_type: str, format_choice: str, total_results: int, user_id: int):
        """Enviar como archivo .txt"""
        
        # Crear archivo en memoria
        txt_buffer = io.BytesIO()
        txt_content = '\n'.join(lines)
        txt_buffer.write(txt_content.encode('utf-8'))
        txt_buffer.seek(0)
        
        # Créditos restantes
        remaining = self.credit_system.get_user_credits(user_id)
        
        # Enviar archivo
        await update.callback_query.message.reply_document(
            document=txt_buffer,
            filename=f"{query}_{format_choice}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            caption=(
                f"📁 *ARCHIVO DE RESULTADOS*\n\n"
                f"🔍 *Búsqueda:* {search_type}\n"
                f"📝 *Query:* `{query}`\n"
                f"📋 *Formato:* `{format_choice}`\n"
                f"📊 *Resultados:* `{total_results:,}`\n"
                f"💰 *Créditos restantes:* `{remaining}`\n\n"
                f"_Archivo TXT con resultados_"
            ),
            parse_mode='Markdown'
        )
        
        await update.callback_query.edit_message_text(
            f"✅ *BÚSQUEDA COMPLETADA*\n\n"
            f"*Dominio:* `{query}`\n"
            f"*Formato:* `{format_choice}`\n"
            f"*Resultados:* `{total_results:,}`\n\n"
            f"📁 *Archivo TXT enviado*\n"
            f"💰 *Créditos restantes:* `{remaining}`"
        )
    
    async def send_as_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE, lines: list,
                              query: str, search_type: str, format_choice: str, total_results: int, user_id: int):
        """Enviar como mensaje (pocos resultados)"""
        
        remaining = self.credit_system.get_user_credits(user_id)
        
        # Formato display
        format_display = {
            "login:pass": "🔐 email:pass",
            "url:login:pass": "🔗 url:email:pass",
            "url": "📧 email only"
        }
        
        response = (
            f"✅ *BÚSQUEDA COMPLETADA*\n\n"
            f"*Dominio:* `{query}`\n"
            f"*Formato:* {format_display.get(format_choice, format_choice)}\n"
            f"*Resultados:* `{total_results:,}`\n"
            f"*Créditos restantes:* `{remaining}`\n\n"
            f"*Primeros resultados:*\n"
            f"```\n"
        )
        
        # Añadir primeros 15 resultados
        for line in lines[:15]:
            response += f"{line}\n"
        
        response += "```\n"
        
        if total_results > 15:
            response += f"\n*... y {total_results-15:,} resultados más*"
        
        await update.callback_query.edit_message_text(response, parse_mode='Markdown')
    
    async def perform_search(self, update: Update, context: ContextTypes.DEFAULT_TYPE, 
                             search_type: str, query: str, format_choice: str = ""):
        """Búsqueda simple (para email, login, pass)"""
        user_id = update.effective_user.id
        
        # Mensaje de procesando
        processing_msg = await update.message.reply_text(
            f"🔍 *Buscando:* `{query}`...",
            parse_mode='Markdown'
        )
        
        # Usar crédito
        self.credit_system.use_credits(user_id, search_type, query, format_choice, 0)
        
        # Realizar búsqueda
        success, raw_result = await self.api.search_with_format(search_type, query, format_choice)
        
        if not success:
            self.credit_system.add_credits(user_id, 1, 0)
            await processing_msg.edit_text(f"❌ *ERROR:* {raw_result}\n\n💰 Crédito reembolsado")
            return
        
        # Procesar resultados
        lines = raw_result.strip().split('\n')
        total_results = len(lines) if lines and lines[0] else 0
        
        if total_results == 0:
            self.credit_system.add_credits(user_id, 1, 0)
            await processing_msg.edit_text(
                f"❌ *SIN RESULTADOS*\n\n"
                f"*Query:* `{query}`\n\n"
                f"💰 Crédito reembolsado"
            )
            return
        
        # Actualizar contador
        with self.credit_system.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'UPDATE searches SET results_count = ? WHERE user_id = ? AND query = ? ORDER BY id DESC LIMIT 1',
                (total_results, user_id, query)
            )
            conn.commit()
        
        remaining = self.credit_system.get_user_credits(user_id)
        
        # Enviar resultados
        if total_results > 100:
            await self.send_as_txt_file_simple(
                update=update,
                processing_msg=processing_msg,
                lines=lines,
                query=query,
                search_type=search_type,
                total_results=total_results,
                user_id=user_id,
                remaining=remaining
            )
        else:
            await self.send_as_message_simple(
                processing_msg=processing_msg,
                lines=lines,
                query=query,
                search_type=search_type,
                total_results=total_results,
                remaining=remaining
            )
    
    async def send_as_txt_file_simple(self, update: Update, processing_msg, lines: list, query: str,
                                      search_type: str, total_results: int, user_id: int, remaining: int):
        """Enviar archivo .txt simple"""
        
        txt_buffer = io.BytesIO()
        txt_content = '\n'.join(lines)
        txt_buffer.write(txt_content.encode('utf-8'))
        txt_buffer.seek(0)
        
        emoji = "📧" if search_type == "email" else "🔍"
        
        await processing_msg.edit_text(
            f"{emoji} *BÚSQUEDA COMPLETADA*\n\n"
            f"*Query:* `{query}`\n"
            f"*Resultados:* `{total_results:,}`\n\n"
            f"📁 *Enviando archivo...*"
        )
        
        await update.message.reply_document(
            document=txt_buffer,
            filename=f"{search_type}_{query}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            caption=(
                f"{emoji} *ARCHIVO DE RESULTADOS*\n\n"
                f"*Tipo:* {search_type}\n"
                f"*Query:* `{query}`\n"
                f"*Resultados:* `{total_results:,}`\n"
                f"*Créditos restantes:* `{remaining}`"
            ),
            parse_mode='Markdown'
        )
    
    async def send_as_message_simple(self, processing_msg, lines: list, query: str,
                                     search_type: str, total_results: int, remaining: int):
        """Enviar como mensaje simple"""
        
        emoji = "📧" if search_type == "email" else "🔍"
        
        response = (
            f"{emoji} *BÚSQUEDA COMPLETADA*\n\n"
            f"*Tipo:* {search_type}\n"
            f"*Query:* `{query}`\n"
            f"*Resultados:* `{total_results:,}`\n"
            f"*Créditos restantes:* `{remaining}`\n\n"
            f"*Primeros resultados:*\n"
            f"```\n"
        )
        
        for line in lines[:15]:
            response += f"{line}\n"
        
        response += "```\n"
        
        if total_results > 15:
            response += f"\n*... y {total_results-15:,} resultados más*"
        
        await processing_msg.edit_text(response, parse_mode='Markdown')
    
    async def info_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /info"""
        
        # Obtener estadísticas
        with self.credit_system.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) as users FROM users')
            total_users = cursor.fetchone()['users']
            
            cursor.execute('SELECT COUNT(*) as searches FROM searches')
            total_searches = cursor.fetchone()['searches']
        
        info_text = (
            f"🤖 *{BOT_NAME}*\n"
            f"*Propietario:* {BOT_OWNER}\n\n"
            
            f"📊 *ESTADÍSTICAS:*\n"
            f"👥 *Usuarios:* `{total_users}`\n"
            f"🔍 *Búsquedas:* `{total_searches}`\n"
            f"💾 *Filas ULP:* `{ULP_ROWS}`\n\n"
            
            f"🎯 *FUNCIONES:*\n"
            f"• 🔘 Selección de formatos\n"
            f"• 📁 Archivos TXT/ZIP\n"
            f"• 🆓 {MAX_FREE_CREDITS} créditos gratis\n\n"
            
            f"📋 *FORMATOS DISPONIBLES:*\n"
            f"• 🔐 email:pass\n"
            f"• 🔗 url:email:pass\n"
            f"• 👤 login:pass\n"
            f"• 📧 email only\n\n"
            
            f"_Última actualización: {datetime.now().strftime('%d/%m/%Y %H:%M')}_"
        )
        
        await update.message.reply_text(info_text, parse_mode='Markdown')
    
    async def mycredits_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /mycredits"""
        user_id = update.effective_user.id
        credits = self.credit_system.get_user_credits(user_id)
        
        user_stats = self.credit_system.get_user_stats(user_id)
        searches = user_stats.get('searches_done', 0) if user_stats else 0
        
        credits_msg = (
            f"💰 *TUS CRÉDITOS*\n\n"
            f"👤 *Usuario:* @{update.effective_user.username or update.effective_user.first_name}\n"
            f"🆓 *Créditos:* `{credits}`/{MAX_FREE_CREDITS}\n"
            f"🔍 *Búsquedas realizadas:* `{searches}`\n\n"
            f"*💡 INFORMACIÓN:*\n"
            f"• 1 crédito = 1 búsqueda\n"
            f"• Máximo {MAX_FREE_CREDITS} créditos gratis\n"
            f"• Contacta a {BOT_OWNER} para más\n\n"
            f"_Usa /search para buscar_"
        )
        
        await update.message.reply_text(credits_msg, parse_mode='Markdown')
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        help_text = (
            "📚 *COMANDOS DISPONIBLES*\n\n"
            
            "*🔍 BÚSQUEDAS (con selección de formato):*\n"
            "`/search dominio` - Buscar por dominio\n"
            "`/email correo` - Buscar por email\n"
            "`/login usuario` - Buscar por login\n"
            "`/pass contraseña` - Buscar por password\n\n"
            
            "*📋 FORMATOS DISPONIBLES:*\n"
            "• 🔐 email:pass\n"
            "• 🔗 url:email:pass\n"
            "• 👤 login:pass\n"
            "• 📧 email only\n\n"
            
            "*💰 CRÉDITOS:*\n"
            "`/mycredits` - Ver tus créditos\n"
            "`/info` - Información del bot\n\n"
            
            f"*🎯 SISTEMA GRATIS:*\n"
            f"Máximo `{MAX_FREE_CREDITS}` créditos gratis/usuario\n"
            f"1 crédito = 1 búsqueda\n\n"
            
            "*📁 ARCHIVOS:*\n"
            "• <100 resultados → Mensaje\n"
            "• >100 resultados → Archivo .txt\n"
            "• >10,000 resultados → Archivo .zip"
        )
        
        await update.message.reply_text(help_text, parse_mode='Markdown')
    
    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Manejador de botones general"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "search_domain":
            await query.edit_message_text(
                "🔍 *BUSCAR DOMINIO*\n\n"
                "Envía: `/search dominio`\n\n"
                "Ejemplos:\n"
                "`/search vk.com`\n"
                "`/search facebook.com`\n"
                "`/search instagram.com`\n\n"
                "_Podrás seleccionar el formato de resultados_",
                parse_mode='Markdown'
            )
        
        elif query.data == "search_email":
            await query.edit_message_text(
                "📧 *BUSCAR EMAIL*\n\n"
                "Envía: `/email correo@gmail.com`\n\n"
                "_Devuelve contraseñas asociadas al email_",
                parse_mode='Markdown'
            )
        
        elif query.data == "my_credits":
            user_id = query.from_user.id
            credits = self.credit_system.get_user_credits(user_id)
            
            await query.edit_message_text(
                f"💰 *TUS CRÉDITOS*\n\n"
                f"🆓 *Disponibles:* `{credits}`/{MAX_FREE_CREDITS}\n"
                f"🔍 *Búsquas posibles:* `{credits}`\n\n"
                f"_Usa /search para comenzar_",
                parse_mode='Markdown'
            )
        
        elif query.data == "bot_info":
            await self.info_command(update, context)
        
        elif query.data == "admin_panel":
            user_id = query.from_user.id
            
            if user_id not in ADMIN_IDS:
                await query.edit_message_text("❌ Solo para administradores")
                return
            
            await query.edit_message_text(
                "👑 *PANEL DE ADMINISTRACIÓN*\n\n"
                "*Comandos disponibles:*\n"
                "• `/addcredits <id> <cant>` - Añadir créditos\n"
                "• `/userinfo <id>` - Info usuario\n"
                "• `/stats` - Estadísticas\n"
                "• `/userslist` - Listar usuarios\n\n"
                f"_Máximo {MAX_FREE_CREDITS} créditos gratis por usuario_",
                parse_mode='Markdown'
            )

# ============================================================================
# EJECUCIÓN PRINCIPAL
# ============================================================================

def run_flask_app():
    app.run(host='0.0.0.0', port=PORT, threaded=True)

def main():
    logger.info(f"🚀 Iniciando {BOT_NAME}")
    logger.info(f"👑 Owner: {BOT_OWNER}")
    logger.info(f"💾 ULP Rows: {ULP_ROWS}")
    logger.info(f"🎯 Free credits: {MAX_FREE_CREDITS}")
    
    # Inicializar sistemas
    credit_system = CreditSystem()
    api_client = ULPAPIClient(credit_system)
    handlers = TelegramBotHandlers(api_client, credit_system)
    
    # Crear aplicación de Telegram
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # ConversationHandler para búsqueda con formato
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('search', handlers.search_command)],
        states={
            CHOOSING_FORMAT: [
                CallbackQueryHandler(handlers.format_selected, pattern='^format_')
            ]
        },
        fallbacks=[CommandHandler('cancel', lambda u, c: ConversationHandler.END)]
    )
    
    # Comandos normales
    application.add_handler(CommandHandler("start", handlers.start))
    application.add_handler(CommandHandler("info", handlers.info_command))
    application.add_handler(CommandHandler("help", handlers.help_command))
    application.add_handler(CommandHandler("mycredits", handlers.mycredits_command))
    application.add_handler(conv_handler)  # Búsqueda con formato
    application.add_handler(CommandHandler("email", handlers.email_command))
    application.add_handler(CommandHandler("login", handlers.email_command))  # Mismo handler
    application.add_handler(CommandHandler("pass", handlers.email_command))   # Mismo handler
    
    # Handlers de botones
    application.add_handler(CallbackQueryHandler(handlers.button_handler))
    
    # Iniciar Flask
    flask_thread = threading.Thread(target=run_flask_app, daemon=True)
    flask_thread.start()
    
    logger.info(f"🌐 Flask en puerto {PORT}")
    logger.info("🤖 Iniciando bot de Telegram...")
    
    application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

if __name__ == '__main__':
    main()