import telegram
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes
import asyncio
import re
from flask import Flask
import threading
import logging
from datetime import datetime
import os

# 设置日志
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Flask 服务器
app = Flask(__name__)

@app.route('/')
def keep_alive():
    return "Bot is alive!"

def run_flask():
    app.run(host='0.0.0.0', port=8080)

# Bot Token
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

# 主页信息
HOME_MESSAGE = """
欢迎体验蛋狗按钮机器人！我是你的智能助手，帮助你在频道创建带按钮的帖子。
请将机器人拉进频道并设为管理员，然后直接在频道发送帖子，我会自动识别并优化为按钮版本。
使用方法：
1. 在频道发送帖子，格式如下：
帖子内容
===
[按钮1文案+链接]，[按钮2文案+链接]
[按钮3文案+链接]
[按钮4文案]....[按钮9文案+链接]
2. 按钮用中英文逗号分隔，换行决定按钮布局
3. 支持最多9个按钮
示例：
欢迎体验机器人
===
[百度+http://baidu.com]，[谷歌+https://google.com]
[推特+https://twitter.com]
开始在频道发帖试试吧！
"""

# 启动机器人 - 显示主页
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(HOME_MESSAGE)

# 处理私聊中任何消息 - 只显示主页
async def handle_private_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(HOME_MESSAGE)

# 处理机器人被加入频道
async def handle_new_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    if message.new_chat_members:
        for member in message.new_chat_members:
            if member.id == context.bot.id:
                inviter = message.from_user.username or message.from_user.full_name or f"ID:{message.from_user.id}"
                chat_title = message.chat.title or "未命名频道"
                chat_id = message.chat_id
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                logger.info(f"机器人被加入频道: {chat_title} (ID: {chat_id}), 邀请者: {inviter}, 时间: {timestamp}")

# 频道帖子识别与重发
async def handle_channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.channel_post
    if message.text and "===" in message.text:
        parts = message.text.split("===", 1)
        if len(parts) == 2:
            content = parts[0].strip()
            button_text = parts[1].strip()
            lines = button_text.split("\n")
            keyboard = []
            buttons = []
            
            for line in lines:
                items = re.split(r"[,，]", line)
                row = []
                for item in items:
                    item = item.strip()
                    if item.startswith("[") and item.endswith("]") and "+" in item:
                        btn_info = item[1:-1].split("+", 1)
                        if len(btn_info) == 2 and len(buttons) < 9:
                            btn = InlineKeyboardButton(btn_info[0].strip(), url=btn_info[1].strip())
                            row.append(btn)
                            buttons.append(btn)
                if row:
                    keyboard.append(row)
            
            if buttons:
                reply_markup = InlineKeyboardMarkup(keyboard)
                await context.bot.delete_message(chat_id=message.chat_id, message_id=message.message_id)
                new_message = await context.bot.send_message(chat_id=message.chat_id, text=content, reply_markup=reply_markup)
                
                # 记录日志
                chat_title = message.chat.title or "未命名频道"
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                message_link = f"https://t.me/c/{str(message.chat_id)[4:]}/{new_message.message_id}"
                sender = message.from_user.username or message.from_user.full_name or f"ID:{message.from_user.id}"
                logger.info(f"频道帖子处理: {chat_title} (ID: {message.chat_id}), 发送者: {sender}, 时间: {timestamp}, 消息链接: {message_link}")

def main():
    # 启动 Flask 服务器线程
    threading.Thread(target=run_flask, daemon=True).start()

    application = ApplicationBuilder().token(TOKEN).build()

    # 处理私聊
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(
        telegram.ext.filters.ChatType.PRIVATE, 
        handle_private_message
    ))
    
    # 处理频道帖子
    application.add_handler(MessageHandler(
        telegram.ext.filters.ChatType.CHANNEL, 
        handle_channel_post
    ))
    
    # 处理机器人被加入频道
    application.add_handler(MessageHandler(
        telegram.ext.filters.StatusUpdate.NEW_CHAT_MEMBERS,
        handle_new_chat_member
    ))

    application.run_polling()

if __name__ == "__main__":
    main()