import logging
import re
import traceback
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

from config import BOT_TOKEN, ADMIN_IDS, SUPPORT_AGENT_ID

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# ================= 主菜单 =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    is_admin = user_id in ADMIN_IDS
    keyboard = []
    keyboard.append([InlineKeyboardButton("👤 人工客服", callback_data='cs_agent')])
    if is_admin:
        keyboard.append([InlineKeyboardButton("🚀 拉专群", callback_data='cs_group')])
    await update.message.reply_text("👋 欢迎进入专用客服控制台：", reply_markup=InlineKeyboardMarkup(keyboard))
    print(f"✅ 用户 {user_id} 已进入主菜单")

# ================= 按钮点击处理 =================
async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    print(f"🟢 收到按钮点击事件！用户ID: {user_id}, 动作: {data}")

    try:
        # 1. 点击人工客服
        if data == 'cs_agent':
            context.user_data['waiting_agent'] = True
            await query.edit_message_text(
                "👤 **已连接专属客服**\n\n请直接发送您的问题，我们将尽快为您解答。\n\n点击下方按钮可结束对话：",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ 结束客服对话", callback_data='cs_end')]]),
                parse_mode='Markdown'
            )
            print("📤 正在尝试通知客服...")

            # 尝试发送通知给客服
            try:
                await context.bot.send_message(
                    SUPPORT_AGENT_ID,
                    f"📨 **新客服请求**\n用户ID: `{user_id}`\n请直接**右滑此消息，点击回复**，即可与该客户聊天。",
                    parse_mode='Markdown'
                )
                print(f"✅ 通知成功发送给客服 {SUPPORT_AGENT_ID}")
            except Exception as e:
                print(f"❌ 发送客服通知失败！错误信息: {e}")
                await query.message.reply_text("⚠️ 客服似乎无法接收消息，请检查是否已经把机器人拉黑了。")
            return

        # 2. 拉专群
        if data == 'cs_group':
            if user_id not in ADMIN_IDS:
                await query.edit_message_text("❌ 您没有权限使用此功能。")
                return
            await query.edit_message_text("🚀 **拉专群指令已发送**，客服稍后会联系您。")
            for uid in ADMIN_IDS:
                if uid != user_id:
                    await context.bot.send_message(uid, f"🚀 新群组请求\n用户ID: `{user_id}`，请处理。")
            await context.bot.send_message(SUPPORT_AGENT_ID, f"🚀 新群组请求\n用户ID: `{user_id}`，请拉入群组。")
            return

        # 3. 结束对话
        if data == 'cs_end':
            if 'waiting_agent' in context.user_data:
                del context.user_data['waiting_agent']
            await query.edit_message_text("✅ 客服对话已结束。如需帮助请重新发送 /start。")
            return

    except Exception as e:
        print(f"❌ 按钮处理出现严重异常: {e}")
        print(traceback.format_exc())

# ================= 消息处理 =================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        text = update.message.text

        # 客户发消息
        if context.user_data.get('waiting_agent'):
            print(f"📩 收到客户 {user_id} 的消息: {text}")
            await context.bot.send_message(
                SUPPORT_AGENT_ID,
                f"💬 **客户发来新消息**\n用户ID: `{user_id}`\n内容: {text}",
                parse_mode='Markdown'
            )
            return

        # 客服右滑回复
        if user_id == SUPPORT_AGENT_ID and update.message.reply_to_message:
            admin_msg = update.message.reply_to_message.text
            match = re.search(r"用户ID: `(\d+)`", admin_msg)
            if match:
                target_user_id = int(match.group(1))
                await context.bot.send_message(chat_id=target_user_id, text=f"💬 客服回复：\n\n{text}")
                await update.message.reply_text("✅ 消息已成功转发给客户。")
                return
            else:
                await update.message.reply_text("⚠️ 请右滑带有用户ID的客服通知消息。")
            return

        if user_id in ADMIN_IDS:
            await update.message.reply_text("⚠️ 请先点击按钮选择功能。")
    except Exception as e:
        print(f"❌ 处理消息时出现错误: {e}")

def main():
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_click))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logging.info("✅ 客服中转站已启动！")
    application.run_polling()

if __name__ == "__main__":
    main()
