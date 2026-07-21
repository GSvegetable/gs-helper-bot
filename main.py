import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

from config import BOT_TOKEN, ADMIN_IDS

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# 存储当前的客服对话状态
active_agent_sessions = {}  # 格式: {客户ID: 客服ID}
active_client_sessions = {} # 格式: {客服ID: 客户ID}

# ================= 核心权限拦截 =================
async def check_permission(update: Update) -> bool:
    user = update.effective_user
    if user.id not in ADMIN_IDS:
        # 非管理员给你发消息，机器人直接静默装死，没有任何回复
        return False
    return True

# ================= 主菜单（只有管理员能用） =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_permission(update):
        return

    keyboard = [
        [InlineKeyboardButton("👤 人工客服", callback_data='cs_agent')],
        [InlineKeyboardButton("🚀 拉专群", callback_data='cs_group')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("👋 欢迎进入专用客服控制台，请选择功能：", reply_markup=reply_markup)

# ================= 按钮点击处理 =================
async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if not await check_permission(query):
        return

    # 1. 点击了“人工客服”
    if query.data == 'cs_agent':
        await query.edit_message_text(
            "👤 **人工客服模式已开启**\n\n"
            "现在所有发给你的消息，都会被实时转发给管理员。\n"
            "管理员回复你时，你看到的消息将显示为机器人的回复。\n\n"
            "点击下方按钮可结束对话：",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ 结束客服对话", callback_data='cs_end')]]),
            parse_mode='Markdown'
        )
        # 记录当前用户正在等待客服
        context.user_data['waiting_agent'] = True
        # 通知管理员有人请求客服
        for admin_id in ADMIN_IDS:
            if admin_id != user_id:
                await context.bot.send_message(
                    admin_id,
                    f"📨 **新客服请求**\n用户ID: `{user_id}`\n请回复此消息来与该用户聊天。",
                    parse_mode='Markdown'
                )

    # 2. 点击了“拉专群”
    elif query.data == 'cs_group':
        await query.edit_message_text(
            "🚀 **拉专群指令已发送给管理员**\n\n"
            "机器人无法自动创建群组。\n"
            "管理员收到你的指令后，会手动拉你进入专属群组。\n\n"
            "*(请等待管理员操作)*",
            parse_mode='Markdown'
        )
        # 通知管理员有人请求拉群
        for admin_id in ADMIN_IDS:
            if admin_id != user_id:
                await context.bot.send_message(
                    admin_id,
                    f"🚀 **新群组请求**\n用户ID: `{user_id}`\n请为该用户创建一个专属群组，并把机器人设为管理员拉入。",
                    parse_mode='Markdown'
                )

    # 3. 结束对话
    elif query.data == 'cs_end':
        if 'waiting_agent' in context.user_data:
            del context.user_data['waiting_agent']
        await query.edit_message_text("✅ 客服对话已结束，感谢您的使用。如需帮助请重新发送 /start。")

# ================= 消息处理（只有管理员能触发转发） =================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_permission(update):
        return

    user_id = update.effective_user.id
    text = update.message.text
    chat_id = update.effective_chat.id

    # 如果当前用户是“客户”，且设置了等待客服
    if context.user_data.get('waiting_agent'):
        # 转发给另一个管理员
        for admin_id in ADMIN_IDS:
            if admin_id != user_id:
                await context.bot.send_message(
                    admin_id,
                    f"💬 收到客户新消息：\n\n{text}"
                )
        return

    # 如果当前用户是“管理员”，且正在给某客户回消息（他右滑了客服转发的通知）
    if update.message.reply_to_message:
        admin_msg = update.message.reply_to_message.text
        # 尝试提取用户ID
        import re
        match = re.search(r"用户ID: `(\d+)`", admin_msg)
        if match:
            target_user_id = int(match.group(1))
            # 把管理员的话转发给用户
            await context.bot.send_message(chat_id=target_user_id, text=f"💬 客服回复：\n\n{text}")
            await update.message.reply_text("✅ 消息已成功转发给客户。")
            return

    # 管理员无意义的文字回复
    await update.message.reply_text("⚠️ 请先点击按钮选择功能，或右滑回复之前的通知消息来回复客户。")

def main():
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_click))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logging.info("✅ 专群客服中转站已启动！")
    application.run_polling()

if __name__ == "__main__":
    main()
