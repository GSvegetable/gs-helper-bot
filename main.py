import logging
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

from config import BOT_TOKEN, ADMIN_IDS, SUPPORT_AGENT_ID

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# ================= 核心权限校验 =================
async def check_admin(update: Update) -> bool:
    user_id = update.effective_user.id
    # 不是管理员发 /start 或点按钮，机器人直接静默装死
    if user_id not in ADMIN_IDS:
        return False
    return True

# ================= 主菜单 =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_admin(update):
        return
    keyboard = [
        [InlineKeyboardButton("👤 人工客服", callback_data='cs_agent')],
        [InlineKeyboardButton("🚀 拉专群", callback_data='cs_group')]
    ]
    await update.message.reply_text("👋 欢迎进入专用客服控制台，请选择功能：", reply_markup=InlineKeyboardMarkup(keyboard))

# ================= 按钮点击处理 =================
async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if not await check_admin(query):
        return

    if query.data == 'cs_agent':
        await query.edit_message_text(
            "👤 **人工客服模式已开启**\n\n"
            "现在所有发给我的文字，都会被实时转发给指定的专属客服。\n"
            "客服回复你时，你将看到消息来自我（机器人）。\n\n"
            "点击下方按钮可结束对话：",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ 结束客服对话", callback_data='cs_end')]]),
            parse_mode='Markdown'
        )
        context.user_data['waiting_agent'] = True

        # 通知专属客服有客户进来了
        await context.bot.send_message(
            SUPPORT_AGENT_ID,
            f"📨 **新客服请求**\n用户ID: `{user_id}`\n请直接回复此消息与客户聊天。",
            parse_mode='Markdown'
        )

    elif query.data == 'cs_group':
        await query.edit_message_text(
            "🚀 **拉专群指令已发送**\n\n"
            "机器人无法自动建群。\n"
            "我已通知管理员，他会手动拉你进入专属群组，请稍等。",
            parse_mode='Markdown'
        )
        # 通知管理员和客服拉群
        for uid in ADMIN_IDS:
            if uid != user_id:
                await context.bot.send_message(uid, f"🚀 新群组请求\n用户ID: `{user_id}`，请处理。")
        await context.bot.send_message(SUPPORT_AGENT_ID, f"🚀 新群组请求\n用户ID: `{user_id}`，请拉入群组。")

    elif query.data == 'cs_end':
        if 'waiting_agent' in context.user_data:
            del context.user_data['waiting_agent']
        await query.edit_message_text("✅ 客服对话已结束，感谢您的使用。")

# ================= 消息处理（只有管理员能触发客服） =================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    chat_id = update.effective_chat.id

    # 情况1：管理员（你）发给机器人的消息（转发给客服，或者作为客户身份）
    if user_id in ADMIN_IDS:
        if context.user_data.get('waiting_agent'):
            # 把客户的话转发给专属客服
            await context.bot.send_message(
                SUPPORT_AGENT_ID,
                f"💬 客户消息：\n\n{text}"
            )
            return

    # 情况2：专属客服右滑回复了之前的通知（回传给客户）
    if user_id == SUPPORT_AGENT_ID and update.message.reply_to_message:
        admin_msg = update.message.reply_to_message.text
        match = re.search(r"用户ID: `(\d+)`", admin_msg)
        if match:
            target_user_id = int(match.group(1))
            # 把客服的话转发给客户
            await context.bot.send_message(chat_id=target_user_id, text=f"💬 客服回复：\n\n{text}")
            await update.message.reply_text("✅ 消息已成功转发给客户。")
            return

    # 管理员无意义的文字回复
    if user_id in ADMIN_IDS:
        await update.message.reply_text("⚠️ 请先点击按钮选择功能，或作为客服右滑消息进行回复。")

def main():
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_click))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logging.info("✅ 客服中转站已启动！")
    application.run_polling()

if __name__ == "__main__":
    main()
