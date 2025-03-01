import telegram
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from flask import Flask, request
import logging
import os
import asyncio
from aiohttp import web

# 设置日志
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Flask 应用（仅用于 Render 的根路径）
app = Flask(__name__)
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")
application = Application.builder().token(TOKEN).build()

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

# 处理私聊消息
async def handle_private(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(HOME_MESSAGE)

# 处理机器人被加入频道
async def handle_new_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    if message and message.new_chat_members:
        for member in message.new_chat_members:
            if member.id == context.bot.id:
                inviter = message.from_user.username or message.from_user.full_name or f"ID:{message.from_user.id}"
                chat_title = message.chat.title or "未命名频道"
                chat_id = message.chat_id
                logger.info(f"机器人被加入频道: {chat_title} (ID: {chat_id}), 邀请者: {inviter}")

# 频道帖子识别与重发
async def handle_channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.channel_post
    text = message.text or message.caption or ""
    if "===" in text:
        parts = text.split("===", 1)
        if len(parts) == 2:
            content = parts[0].strip()
            button_text = parts[1].strip()
            lines = button_text.split("\n")
            keyboard = []
            buttons = []
            
            for line in lines:
                items = line.split(",")
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
                
                if message.photo:
                    await context.bot.send_photo(
                        chat_id=message.chat_id,
                        photo=message.photo[-1].file_id,
                        caption=content,
                        reply_markup=reply_markup
                    )
                elif message.video:
                    await context.bot.send_video(
                        chat_id=message.chat_id,
                        video=message.video.file_id,
                        caption=content,
                        reply_markup=reply_markup
                    )
                else:
                    await context.bot.send_message(
                        chat_id=message.chat_id,
                        text=content,
                        reply_markup=reply_markup
                    )

# Webhook 处理（异步）
async def webhook(request):
    try:
        json_data = await request.json()
        logger.info(f"Received JSON: {json_data}")
        if not json_data or "update_id" not in json_data:
            logger.error("Invalid JSON: missing update_id")
            return web.Response(text="Error: Invalid update", status=400)
        if "message" in json_data:
            if "date" not in json_data["message"]:
                logger.error("Invalid JSON: missing date in message")
                return web.Response(text="Error: Missing date", status=400)
            if "message_id" not in json_data["message"]:
                logger.error("Invalid JSON: missing message_id in message")
                return web.Response(text="Error: Missing message_id", status=400)
        update = Update.de_json(json_data, application.bot)
        if update is None:
            logger.error("Failed to parse update")
            return web.Response(text="Error: Invalid update", status=400)
        await application.process_update(update)
        logger.info("Update processed successfully")
        return web.Response(text="OK", status=200)
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return web.Response(text="Error", status=500)

# 根路径（给 UptimeRobot）
@app.route('/')
def keep_alive():
    logger.info("Root path accessed")
    return "Bot is alive!"

# 设置处理器
def setup_handlers():
    application.add_handler(CommandHandler("start", handle_private))
    application.add_handler(MessageHandler(filters.ChatType.PRIVATE, handle_private))
    application.add_handler(MessageHandler(filters.ChatType.CHANNEL, handle_channel_post))
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, handle_new_chat_member))

# 设置 Webhook
async def set_webhook():
    await application.initialize()  # 初始化 Application
    await application.bot.set_webhook(url=f"{WEBHOOK_URL}/{TOKEN}")
    logger.info(f"Webhook set to {WEBHOOK_URL}/{TOKEN}")

# 启动 aiohttp 服务器
async def start_aiohttp():
    aio_app = web.Application()
    aio_app.router.add_post(f"/{TOKEN}", webhook)
    runner = web.AppRunner(aio_app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 10000)
    await site.start()
    logger.info("aiohttp server started on port 10000")

# 主函数
async def main():
    setup_handlers()
    await set_webhook()
    await start_aiohttp()

if __name__ == "__main__":
    if 'RENDER' not in os.environ:
        # 本地运行 Flask
        loop = asyncio.get_event_loop()
        loop.run_until_complete(set_webhook())
        port = int(os.environ.get("PORT", 10000))
        app.run(host="0.0.0.0", port=port)
    else:
        # Render 上运行 aiohttp
        asyncio.run(main())