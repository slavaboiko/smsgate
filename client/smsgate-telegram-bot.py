#!/usr/bin/env python3
import os
import logging
import asyncio
import ssl
import base64
from datetime import datetime
from typing import Optional, Dict, Any
from pathlib import Path

import telegram
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)
from dotenv import load_dotenv

from smsgate_rpcclient import SMSGateRPCClient

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Conversation states
PHONE_NUMBER, USSD_CODE, SMS_RECIPIENT, SMS_TEXT, SMS_FLASH = range(5)

def load_config():
    """Load configuration from environment variables and .env file"""
    # Try to load .env file from the same directory as the script
    script_dir = Path(__file__).parent
    env_path = script_dir / '.env'
    
    if env_path.exists():
        load_dotenv(env_path)
        logger.info(f"Loaded configuration from {env_path}")
    else:
        logger.warning(f"No .env file found at {env_path}. Using environment variables only.")
    
    # Required environment variables
    required_vars = {
        'TELEGRAM_BOT_TOKEN': 'Telegram Bot Token',
        'SMSGATE_ALLOWED_USERS': 'Allowed Users List',
        'SMSGATE_API_TOKEN': 'SMSGate API Token',
    }
    
    # Check for required variables
    missing_vars = []
    for var, description in required_vars.items():
        if not os.getenv(var):
            missing_vars.append(f"{var} ({description})")
    
    if missing_vars:
        raise ValueError(
            f"Missing required environment variables:\n" +
            "\n".join(f"- {var}" for var in missing_vars) +
            "\n\nPlease set these variables in your environment or create a .env file."
        )
    
    # Parse allowed users
    allowed_users = os.getenv('SMSGATE_ALLOWED_USERS', '')
    allowed_users = set(int(uid) for uid in allowed_users.split(',') if uid)
    
    if not allowed_users:
        logger.warning("No allowed users specified. Bot will be inaccessible.")
    
    return {
        'telegram_token': os.getenv('TELEGRAM_BOT_TOKEN'),
        'allowed_users': allowed_users,
        'host': os.getenv('SMSGATE_HOST', 'localhost'),
        'port': int(os.getenv('SMSGATE_PORT', '7000')),
        'ca_file': os.getenv('SMSGATE_CA_FILE'),
        'api_token': os.getenv('SMSGATE_API_TOKEN'),
    }

class SMSGateTelegramBot:
    def __init__(self, config: Dict[str, Any], rpc_client: SMSGateRPCClient):
        self.application = Application.builder().token(config['telegram_token']).build()
        self.rpc_client = rpc_client
        self.allowed_users = config['allowed_users']
        
        # Set up handlers
        self.setup_handlers()
        
        # Start SMS checker
        self.sms_checker_task = None

    def setup_handlers(self):
        """Set up all command and conversation handlers"""
        
        # Command handlers
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("help", self.help))
        self.application.add_handler(CommandHandler("status", self.status))
        self.application.add_handler(CommandHandler("get_sms", self.get_sms))
        self.application.add_handler(CommandHandler("get_all_sms", self.get_all_sms))
        self.application.add_handler(CommandHandler("read_stored_sms", self.read_stored_sms))
        self.application.add_handler(CommandHandler("me", self.me))
        
        # USSD conversation handler
        ussd_handler = ConversationHandler(
            entry_points=[CommandHandler("ussd", self.ussd)],
            states={
                PHONE_NUMBER: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.phone_number)
                ],
                USSD_CODE: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.ussd_code)
                ],
            },
            fallbacks=[CommandHandler("cancel", self.cancel)]
        )
        self.application.add_handler(ussd_handler)
        
        # SMS conversation handler
        sms_handler = ConversationHandler(
            entry_points=[CommandHandler("sms", self.sms)],
            states={
                PHONE_NUMBER: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.phone_number)
                ],
                SMS_RECIPIENT: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.sms_recipient)
                ],
                SMS_TEXT: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.sms_text)
                ],
                SMS_FLASH: [
                    CallbackQueryHandler(self.sms_flash)
                ],
            },
            fallbacks=[CommandHandler("cancel", self.cancel)]
        )
        self.application.add_handler(sms_handler)

    async def check_auth(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
        """Check if user is authorized"""
        if update.effective_user.id not in self.allowed_users:
            await update.message.reply_text("Sorry, you are not authorized to use this bot.")
            return False
        return True

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Send a message when the command /start is issued."""
        if not await self.check_auth(update, context):
            return
            
        await update.message.reply_text(
            "Welcome to SMSGate Bot! Use /help to see available commands."
        )

    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Send a message when the command /help is issued."""
        if not await self.check_auth(update, context):
            return
            
        help_text = """
Available commands:
/status - Show modem status
/get_all_sms - Get all received SMS messages from all modems
/read_stored_sms - Read all stored SMS messages from all modems
/ussd - Send USSD code
/sms - Send SMS
/cancel - Cancel current operation
        """
        await update.message.reply_text(help_text)

    async def status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show modem status"""
        if not await self.check_auth(update, context):
            return
            
        try:
            stats = self.rpc_client.get_stats()
            status_text = "Modem Status:\n\n"
            for identifier, info in stats.items():
                status_text += f"Modem {identifier}:\n"
                status_text += f"Phone: {info['phone_number']}\n"
                status_text += f"Network: {info['current_network']}\n"
                status_text += f"Signal: {info['current_signal']} dB\n"
                status_text += f"Status: {info['status']}\n"
                status_text += f"Health: {info['health_state_short']}\n"
                if info['health_state_message']:
                    status_text += f"Health Message: {info['health_state_message']}\n"
                status_text += "\n"
            await update.message.reply_text(status_text, disable_web_page_preview=True)
        except Exception as e:
            await update.message.reply_text(f"Error getting status: {str(e)}")

    async def get_sms(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Get received SMS messages"""
        if not await self.check_auth(update, context):
            return
            
        try:
            sms_list = self.rpc_client.get_sms()
            if not sms_list:
                await update.message.reply_text("No SMS messages found.")
                return
                
            for sms in sms_list:
                message = (
                    f"From: {sms['sender']}\n"
                    f"To: {sms['recipient']}\n"
                    f"Time: {sms['timestamp']}\n"
                    f"ID: {sms['id']}\n"
                    f"Text:\n\n{sms['text']}\n"
                )
                await update.message.reply_text(message, disable_web_page_preview=True)
        except Exception as e:
            await update.message.reply_text(f"Error getting SMS: {str(e)}")

    async def get_all_sms(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Get all received SMS messages from all modems"""
        if not await self.check_auth(update, context):
            return
            
        try:
            sms_list = self.rpc_client.get_all_sms()
            if not sms_list:
                await update.message.reply_text("No SMS messages found.")
                return
                
            # Group messages by modem
            messages_by_modem = {}
            for sms in sms_list:
                modem = sms.get('modem', 'Unknown')
                if modem not in messages_by_modem:
                    messages_by_modem[modem] = []
                messages_by_modem[modem].append(sms)
            
            # Send messages grouped by modem
            for modem, messages in messages_by_modem.items():
                await update.message.reply_text(f"Messages from modem {modem}:")
                for sms in messages:
                    message = (
                        f"From: {sms['sender']}\n"
                        f"To: {sms['recipient']}\n"
                        f"Time: {sms['timestamp']}\n"
                        f"ID: {sms['id']}\n"
                        f"Text:\n\n{sms['text']}\n"
                    )
                    await update.message.reply_text(message, disable_web_page_preview=True)
                await update.message.reply_text("---")
        except Exception as e:
            await update.message.reply_text(f"Error getting SMS: {str(e)}")

    async def read_stored_sms(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Read all stored SMS messages from all modems"""
        if not await self.check_auth(update, context):
            return
            
        try:
            await update.message.reply_text("Reading stored SMS messages...")
            messages = self.rpc_client.read_stored_sms()
            
            if not messages:
                await update.message.reply_text("No stored SMS messages found.")
                return
                
            # Format messages for display
            response = "Stored SMS Messages:\n\n"
            for msg in messages:
                response += f"From: {msg.get('sender', 'Unknown')}\n"
                response += f"To: {msg.get('recipient', 'Unknown')}\n"
                response += f"Time: {msg.get('timestamp', 'Unknown')}\n"
                response += f"Text: {msg.get('text', '')}\n"
                if msg.get('flash', False):
                    response += "Flash message\n"
                response += "-" * 40 + "\n"
                
            # Split long messages if needed
            if len(response) > 4000:
                chunks = [response[i:i+4000] for i in range(0, len(response), 4000)]
                for chunk in chunks:
                    await update.message.reply_text(chunk, disable_web_page_preview=True)
            else:
                await update.message.reply_text(response, disable_web_page_preview=True)
                
        except Exception as e:
            await update.message.reply_text(f"Error reading stored SMS: {str(e)}")

    async def ussd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start USSD conversation"""
        if not await self.check_auth(update, context):
            return
            
        await update.message.reply_text("Please enter the phone number to use:")
        return PHONE_NUMBER

    async def phone_number(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle phone number input"""
        context.user_data['phone_number'] = update.message.text
        if context.user_data.get('ussd_code'):
            await update.message.reply_text("Please enter the USSD code:")
            return USSD_CODE
        else:
            await update.message.reply_text("Please enter the recipient's phone number:")
            return SMS_RECIPIENT

    async def ussd_code(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle USSD code input"""
        try:
            status, response = self.rpc_client.send_ussd(
                context.user_data['phone_number'],
                update.message.text
            )
            await update.message.reply_text(f"USSD Response: {response}")
        except Exception as e:
            await update.message.reply_text(f"Error sending USSD: {str(e)}")
        return ConversationHandler.END

    async def sms(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start SMS conversation"""
        if not await self.check_auth(update, context):
            return
            
        await update.message.reply_text("Please enter the phone number to use:")
        return PHONE_NUMBER

    async def sms_recipient(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle SMS recipient input"""
        context.user_data['sms_recipient'] = update.message.text
        await update.message.reply_text("Please enter the message text:")
        return SMS_TEXT

    async def sms_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle SMS text input"""
        context.user_data['sms_text'] = update.message.text
        keyboard = [
            [
                InlineKeyboardButton("Yes", callback_data="flash_yes"),
                InlineKeyboardButton("No", callback_data="flash_no")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Send as flash message?", reply_markup=reply_markup)
        return SMS_FLASH

    async def sms_flash(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle flash message choice"""
        query = update.callback_query
        await query.answer()
        
        flash = query.data == "flash_yes"
        try:
            self.rpc_client.send_sms(
                context.user_data['phone_number'],
                context.user_data['sms_recipient'],
                context.user_data['sms_text'],
                flash
            )
            await query.edit_message_text("SMS sent successfully!")
        except Exception as e:
            await query.edit_message_text(f"Error sending SMS: {str(e)}")
        return ConversationHandler.END

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Cancel the current operation"""
        if not await self.check_auth(update, context):
            return
            
        await update.message.reply_text("Operation cancelled.")
        return ConversationHandler.END

    async def me(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show user information and authorization status"""
        user = update.effective_user
        is_authorized = user.id in self.allowed_users
        
        message = (
            f"Your Telegram Information:\n"
            f"ID: {user.id}\n"
            f"Username: @{user.username if user.username else 'None'}\n"
            f"First Name: {user.first_name}\n"
            f"Last Name: {user.last_name if user.last_name else 'None'}\n"
            f"Language Code: {user.language_code if user.language_code else 'None'}\n\n"
            f"Authorization Status: {'✅ Authorized' if is_authorized else '❌ Not Authorized'}\n\n"
        )
        await update.message.reply_text(message)

    async def check_new_sms(self):
        """Check for new SMS messages every 30 seconds"""
        while True:
            try:
                sms_list = self.rpc_client.get_all_sms()
                if sms_list:
                    # Group messages by modem
                    messages_by_modem = {}
                    for sms in sms_list:
                        modem = sms.get('modem', 'Unknown')
                        if modem not in messages_by_modem:
                            messages_by_modem[modem] = []
                        messages_by_modem[modem].append(sms)
                    
                    # Send notifications grouped by modem
                    for modem, messages in messages_by_modem.items():
                        for sms in messages:
                            message = (
                                f"New SMS received on modem {modem}!\n"
                                f"From: {sms['sender']}\n"
                                f"To: {sms['recipient']}\n"
                                f"Time: {sms['timestamp']}\n"
                                f"Text:\n\n{sms['text']}\n"
                            )
                            # Notify all allowed users
                            for user_id in self.allowed_users:
                                try:
                                    await self.application.bot.send_message(chat_id=user_id, text=message, disable_web_page_preview=True)
                                except Exception as e:
                                    logger.error(f"Error sending notification to user {user_id}: {e}")
            except Exception as e:
                logger.error(f"Error checking for new SMS: {e}")
            
            await asyncio.sleep(30)  # Wait 30 seconds before next check

    async def start_sms_checker(self):
        """Start the SMS checker task"""
        self.sms_checker_task = asyncio.create_task(self.check_new_sms())

    async def run(self):
        """Start the bot"""
        try:
            # Start SMS checker
            await self.start_sms_checker()
            
            # Start the bot
            await self.application.initialize()
            await self.application.start()
            await self.application.updater.start_polling(allowed_updates=Update.ALL_TYPES)
            
            # Keep the bot running until stopped
            while True:
                await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"Error in run(): {e}")
            await self.stop()

    async def stop(self):
        """Stop the bot gracefully"""
        try:
            # Cancel SMS checker task
            if self.sms_checker_task:
                self.sms_checker_task.cancel()
                try:
                    await self.sms_checker_task
                except asyncio.CancelledError:
                    pass
                self.sms_checker_task = None

            # Stop application
            if self.application:
                await self.application.updater.stop()
                await self.application.stop()
                await self.application.shutdown()
        except Exception as e:
            logger.error(f"Error in stop(): {e}")

async def main_async():
    try:
        # Load configuration
        config = load_config()
        
        # Initialize RPC client
        rpc_client = SMSGateRPCClient(
            host=config['host'],
            port=config['port'],
            ca_file=config['ca_file'],
            api_token=config['api_token']
        )

        # Create and run the bot
        bot = SMSGateTelegramBot(config, rpc_client)
        
        await bot.run()
    except ValueError as e:
        logger.error(str(e))
        return 1
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
        await bot.stop()
    except Exception as e:
        logger.error(f"Error running bot: {e}")
        await bot.stop()
        return 1
    return 0

def main():
    """Main entry point"""
    try:
        exit_code = asyncio.run(main_async())
        return exit_code
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
        return 0
    except Exception as e:
        logger.error(f"Error in main: {e}")
        return 1

if __name__ == '__main__':
    exit(main())
