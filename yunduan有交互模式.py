import telegram
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, ApplicationBuilder, CommandHandler, MessageHandler, ConversationHandler, CallbackQueryHandler, ContextTypes
import asyncio
from datetime import datetime
import re
from flask import Flask
import threading

# Flask 服务器
app = Flask(__name__)

@app.route('/')
def keep_alive():
    return "Bot is alive!"

def run_flask():
    app.run(host='0.0.0.0', port=8080)  # Render 默认使用 8080 端口

# Bot Token
import os
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

# 定时任务列表
scheduled_tasks = []

# 状态机
PHOTO_TEXT, BUTTON_COUNT, BUTTON_LAYOUT, BUTTON_DETAILS, TARGET_CHANNEL, SCHEDULE_TIME, CANCEL_TASK = range(7)

# 主页内联键盘（只留查看任务）
INLINE_MAIN_MENU = InlineKeyboardMarkup([
    [InlineKeyboardButton("查看当前任务", callback_data="view_tasks")]
])

# 固定菜单 - 主菜单
REPLY_MAIN_MENU = ReplyKeyboardMarkup(
    [[KeyboardButton("开始设置定时帖子"), KeyboardButton("查看当前任务")]],
    resize_keyboard=True,
    one_time_keyboard=False
)

# 固定菜单 - 数字选择
NUMBER_MENU = ReplyKeyboardMarkup(
    [
        [KeyboardButton("1"), KeyboardButton("2"), KeyboardButton("3")],
        [KeyboardButton("4"), KeyboardButton("5"), KeyboardButton("6")],
        [KeyboardButton("7"), KeyboardButton("8"), KeyboardButton("9")],
        [KeyboardButton("返回主页")]
    ],
    resize_keyboard=True,
    one_time_keyboard=False
)

# 固定菜单 - 返回主页
BACK_MENU = ReplyKeyboardMarkup(
    [[KeyboardButton("返回主页")]],
    resize_keyboard=True,
    one_time_keyboard=False
)

# 固定菜单 - 查看任务后的选项
TASK_MENU = ReplyKeyboardMarkup(
    [[KeyboardButton("取消任务"), KeyboardButton("返回主页")]],
    resize_keyboard=True,
    one_time_keyboard=False
)

# 主页欢迎信息
HOME_MESSAGE = """
欢迎体验蛋狗按钮机器人！我是你的智能助手，帮助你创建带按钮的定时帖子或即时频道消息。
你可以在私聊中设置定时任务，也可以在频道直接发帖让我自动识别并优化。
按钮布局根据您的消息布局来显示，比如下面是九个按钮216布局的排列

频道可以直接发送帖子让机器人重发按钮版本，请将机器人拉进频道做管理员给权限
使用示例：
帖子内容
===
[按钮1文案+链接]，[按钮2文案+链接]
[按钮3文案+链接]
[按钮4文案]....[按钮9文案+链接]
选择功能开始吧！
"""

# 启动机器人 - 显示主页
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(HOME_MESSAGE, reply_markup=INLINE_MAIN_MENU)
    await update.message.reply_text(
        "欢迎使用蛋狗按钮机器人！\n点击下方菜单开始操作吧！",
        reply_markup=REPLY_MAIN_MENU
    )
    return ConversationHandler.END

# 返回主页的函数
async def show_home(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(HOME_MESSAGE, reply_markup=INLINE_MAIN_MENU)
    await update.message.reply_text(
        "欢迎使用蛋狗按钮机器人！\n点击下方菜单开始操作吧！",
        reply_markup=REPLY_MAIN_MENU
    )
    context.user_data.clear()
    return ConversationHandler.END

# 处理内联键盘点击
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    if query.data == "view_tasks":
        if not scheduled_tasks:
            await query.edit_message_text("当前没有定时任务。", reply_markup=None)
            await query.message.reply_text("选择下一步操作：", reply_markup=TASK_MENU)
        else:
            tasks = "\n".join([f"任务 {i+1} t.me/c/{str(task['chat_id'])[4:]} {task['time']}" for i, task in enumerate(scheduled_tasks)])
            await query.edit_message_text(f"当前任务：\n{tasks}", reply_markup=None)
            await query.message.reply_text("选择下一步操作：", reply_markup=TASK_MENU)
        return ConversationHandler.END

# 处理固定菜单和首次消息
async def handle_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    if text == "开始设置定时帖子":
        await update.message.reply_text(
            "好的，让我们开始设置定时帖子！\n请发送图片/视频和文案，媒体+文案、无媒体文案、无文案媒体（可只发送其一或组合）：",
            reply_markup=BACK_MENU
        )
        return PHOTO_TEXT
    elif text == "查看当前任务":
        if not scheduled_tasks:
            await update.message.reply_text("当前没有定时任务。", reply_markup=TASK_MENU)
        else:
            tasks = "\n".join([f"任务 {i+1} t.me/c/{str(task['chat_id'])[4:]} {task['time']}" for i, task in enumerate(scheduled_tasks)])
            await update.message.reply_text(f"当前任务：\n{tasks}", reply_markup=TASK_MENU)
        return ConversationHandler.END
    elif text == "取消任务":
        if not scheduled_tasks:
            await update.message.reply_text("当前没有任务可取消！", reply_markup=REPLY_MAIN_MENU)
            return ConversationHandler.END
        await update.message.reply_text("您需要取消哪个任务？请输入任务编号（例如 1）：", reply_markup=BACK_MENU)
        return CANCEL_TASK
    elif text == "返回主页":
        return await show_home(update, context)
    else:
        await update.message.reply_text(
            "好的，让我们开始设置定时帖子！\n请发送图片/视频和文案，媒体+文案、无媒体文案、无文案媒体（可只发送其一或组合）：",
            reply_markup=BACK_MENU
        )
        return PHOTO_TEXT

# 处理图片/视频和文案
async def photo_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    message = update.message
    
    if message.text == "返回主页":
        return await show_home(update, context)
    
    photo = message.photo[-1].file_id if message.photo else None
    video = message.video.file_id if message.video else None
    text = message.text or message.caption or ""
    
    if photo:
        context.user_data["photo"] = photo
    if video:
        context.user_data["video"] = video
    if text:
        context.user_data["text"] = text
    
    if not photo and not video and not text:
        await update.message.reply_text("抱歉，我需要至少一张图片、一个视频或一段文案。请重新发送！", reply_markup=BACK_MENU)
        return PHOTO_TEXT
    
    await update.message.reply_text("收到你的内容！接下来，需要几个按钮？（请点击下方数字或直接输入1-9）", reply_markup=NUMBER_MENU)
    return BUTTON_COUNT

async def button_count(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    if text == "返回主页":
        return await show_home(update, context)
    try:
        count = int(text)
        if 1 <= count <= 9:
            context.user_data["button_count"] = count
            examples = {
                1: "[1]",
                2: "[1],[2]\n或\n[1]\n[2]",
                3: "[1],[2],[3]\n或\n[1],[2]\n[3]\n或\n[1]\n[2]\n[3]",
                4: "[1],[2],[3],[4]\n或\n[1],[2]\n[3],[4]\n或\n[1]\n[2],[3]\n[4]"
            }.get(count, f"[1],[2]...[{count}]\n或\n[1],[2]\n[3],[4]...\n或\n[1]\n[2]\n...[{count}]")
            await update.message.reply_text(
                f"好的，需要{count}个按钮！请用[]和换行设置布局，例如：\n{examples}\n共需{count}个（可用中英文逗号分隔）：",
                reply_markup=BACK_MENU
            )
            return BUTTON_LAYOUT
        else:
            await update.message.reply_text("请正确输入1-9的数字，或点击下方按钮选择！", reply_markup=NUMBER_MENU)
            return BUTTON_COUNT
    except ValueError:
        await update.message.reply_text("请正确输入1-9的数字，或点击下方按钮选择！", reply_markup=NUMBER_MENU)
        return BUTTON_COUNT

async def button_layout(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    if text == "返回主页":
        return await show_home(update, context)
    
    count = context.user_data["button_count"]
    lines = text.strip().split("\n")
    layout = []
    button_indices = set()
    
    for line in lines:
        buttons = re.findall(r"\[\d+\]", line)
        row = []
        for btn in buttons:
            index = int(btn[1:-1]) - 1
            if 0 <= index < count and index not in button_indices:
                row.append(index)
                button_indices.add(index)
        if row:
            layout.append(row)
    
    if len(button_indices) != count:
        await update.message.reply_text(
            f"布局不对！收到{len(button_indices)}个按钮，需{count}个。请用[]和换行设置完整布局，例如：\n[1],[2]\n[3]\n共需{count}个：",
            reply_markup=BACK_MENU
        )
        return BUTTON_LAYOUT
    
    context.user_data["layout"] = layout
    await update.message.reply_text(
        f"布局已确认！请一次性输入所有按钮内容，每行一个，格式如：N[按钮文本+链接]\n例如：\n1[按钮文案+链接]\n2[按钮2文案+链接]\n共需{count}个：",
        reply_markup=BACK_MENU
    )
    return BUTTON_DETAILS

async def button_details(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    if text == "返回主页":
        return await show_home(update, context)
    
    lines = text.strip().split("\n")
    count = context.user_data["button_count"]
    buttons = []
    button_indices = set()
    
    for line in lines:
        if not re.match(r"^\d+\[.*\+.*\]$", line):
            await update.message.reply_text(
                f"格式不对！请一次性输入所有按钮内容，每行一个，格式如：N[按钮文本+链接]\n例如：\n1[按钮文案+链接]\n2[按钮文案+链接]\n共需{count}个：",
                reply_markup=BACK_MENU
            )
            return BUTTON_DETAILS
        index, btn_content = line.split("[", 1)
        index = int(index) - 1
        btn_text, btn_url = btn_content[:-1].split("+", 1)
        if 0 <= index < count and index not in button_indices:
            buttons.append({"text": btn_text, "url": btn_url})
            button_indices.add(index)
    
    if len(buttons) != count:
        await update.message.reply_text(
            f"按钮数量不对！收到{len(buttons)}个，需{count}个。请一次性输入所有按钮内容，例如：\n1[按钮文案+链接]\n2[按钮文案+链接]\n共需{count}个：",
            reply_markup=BACK_MENU
        )
        return BUTTON_DETAILS
    
    context.user_data["buttons"] = buttons
    layout = context.user_data["layout"]
    keyboard = [[InlineKeyboardButton(buttons[i]["text"], url=buttons[i]["url"]) for i in row] for row in layout]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    if context.user_data.get("photo"):
        await update.message.reply_photo(photo=context.user_data["photo"], caption=context.user_data.get("text"), reply_markup=reply_markup)
    elif context.user_data.get("video"):
        await update.message.reply_video(video=context.user_data["video"], caption=context.user_data.get("text"), reply_markup=reply_markup)
    else:
        await update.message.reply_text(text=context.user_data.get("text"), reply_markup=reply_markup)
    
    await update.message.reply_text("恭喜，按钮帖子已生成！接下来，请告诉我需要发送到哪个频道（例如 @YourChannel 或 t.me/YourChannel）：", reply_markup=BACK_MENU)
    return TARGET_CHANNEL

async def target_channel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    if text == "返回主页":
        return await show_home(update, context)
    
    if text.startswith("https://t.me/") or text.startswith("t.me/"):
        chat_identifier = text.split("t.me/")[-1].split("/")[0]
        if chat_identifier.startswith("+"):
            await update.message.reply_text("请提供有效的频道用户名（例如 @YourChannel）或公开频道链接（例如 t.me/YourChannel）：", reply_markup=BACK_MENU)
            return TARGET_CHANNEL
        text = f"@{chat_identifier}"
    
    try:
        test_msg = await context.bot.send_message(chat_id=text, text="测试消息（机器人验证用，将自动删除）")
        actual_chat_id = test_msg.chat_id
        await context.bot.delete_message(chat_id=actual_chat_id, message_id=test_msg.message_id)
        context.user_data["channel"] = actual_chat_id
        await update.message.reply_text("目标已确认！最后一步，请设置发送时间（格式：YYYY/MM/DD HH:MM，例如 2025/02/27 15:33）：", reply_markup=BACK_MENU)
        return SCHEDULE_TIME
    except telegram.error.BadRequest:
        await update.message.reply_text("无法识别目标！请发送有效的频道用户名（例如 @YourChannel）或公开频道链接（例如 t.me/YourChannel），并确保我已加入并有权限：", reply_markup=BACK_MENU)
        return TARGET_CHANNEL

async def schedule_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    if text == "返回主页":
        return await show_home(update, context)
    
    text = text.replace("：", ":")
    try:
        send_time = datetime.strptime(text, "%Y/%m/%d %H:%M")
        task = {
            "chat_id": context.user_data["channel"],
            "text": context.user_data.get("text"),
            "photo": context.user_data.get("photo"),
            "video": context.user_data.get("video"),
            "buttons": context.user_data["buttons"],
            "layout": context.user_data["layout"],
            "time": text
        }
        scheduled_tasks.append(task)
        
        keyboard = [[InlineKeyboardButton(task["buttons"][i]["text"], url=task["buttons"][i]["url"]) for i in row] for row in task["layout"]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        async def send_task():
            try:
                if task["photo"]:
                    await context.bot.send_photo(chat_id=task["chat_id"], photo=task["photo"], caption=task["text"], reply_markup=reply_markup)
                elif task["video"]:
                    await context.bot.send_video(chat_id=task["chat_id"], video=task["video"], caption=task["text"], reply_markup=reply_markup)
                else:
                    await context.bot.send_message(chat_id=task["chat_id"], text=task["text"], reply_markup=reply_markup)
            except telegram.error.BadRequest as e:
                print(f"定时任务失败：{e.message}，chat_id: {task['chat_id']}")
        
        now = datetime.now()
        delay = (send_time - now).total_seconds()
        if delay > 0:
            asyncio.get_event_loop().call_later(delay, lambda: asyncio.ensure_future(send_task()))
            await update.message.reply_text(f"定时任务设置成功！将在 {text} 发送到 {context.user_data['channel']}。返回菜单继续操作吧！", reply_markup=REPLY_MAIN_MENU)
        else:
            await update.message.reply_text("这个时间已过去！请设置一个未来的时间：", reply_markup=BACK_MENU)
            return SCHEDULE_TIME
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("时间格式不对！请使用 YYYY/MM/DD HH:MM 格式（例如 2025/02/27 15:33），注意用英文冒号 : 重试：", reply_markup=BACK_MENU)
        return SCHEDULE_TIME

# 取消任务
async def cancel_task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    if text == "返回主页":
        return await show_home(update, context)
    
    try:
        task_num = int(text) - 1
        if 0 <= task_num < len(scheduled_tasks):
            scheduled_tasks.pop(task_num)
            await update.message.reply_text("任务取消成功！", reply_markup=BACK_MENU)
            return ConversationHandler.END
        else:
            await update.message.reply_text(f"请输入有效的任务编号（1-{len(scheduled_tasks)}）：", reply_markup=BACK_MENU)
            return CANCEL_TASK
    except ValueError:
        await update.message.reply_text("请正确输入任务编号（数字）：", reply_markup=BACK_MENU)
        return CANCEL_TASK

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("已取消设置。", reply_markup=REPLY_MAIN_MENU)
    return await show_home(update, context)

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
                await context.bot.send_message(chat_id=message.chat_id, text=content, reply_markup=reply_markup)

def main():
    # 启动 Flask 服务器线程
    threading.Thread(target=run_flask, daemon=True).start()

    application = ApplicationBuilder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))

    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(telegram.ext.filters.TEXT & ~telegram.ext.filters.COMMAND, handle_main_menu)],
        states={
            PHOTO_TEXT: [
                MessageHandler(telegram.ext.filters.PHOTO, photo_text),
                MessageHandler(telegram.ext.filters.VIDEO, photo_text),
                MessageHandler(telegram.ext.filters.TEXT & ~telegram.ext.filters.COMMAND, photo_text)
            ],
            BUTTON_COUNT: [MessageHandler(telegram.ext.filters.TEXT & ~telegram.ext.filters.COMMAND, button_count)],
            BUTTON_LAYOUT: [MessageHandler(telegram.ext.filters.TEXT & ~telegram.ext.filters.COMMAND, button_layout)],
            BUTTON_DETAILS: [MessageHandler(telegram.ext.filters.TEXT & ~telegram.ext.filters.COMMAND, button_details)],
            TARGET_CHANNEL: [MessageHandler(telegram.ext.filters.TEXT & ~telegram.ext.filters.COMMAND, target_channel)],
            SCHEDULE_TIME: [MessageHandler(telegram.ext.filters.TEXT & ~telegram.ext.filters.COMMAND, schedule_time)],
            CANCEL_TASK: [MessageHandler(telegram.ext.filters.TEXT & ~telegram.ext.filters.COMMAND, cancel_task)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False
    )
    application.add_handler(conv_handler)
    application.add_handler(MessageHandler(telegram.ext.filters.ChatType.CHANNEL, handle_channel_post))

    application.run_polling()

if __name__ == "__main__":
    main()