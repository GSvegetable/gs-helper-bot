import logging
import re
import time
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

# ================= 按钮点击处理 =================
async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    # 1. 点击人工客服
    if data == 'cs_agent':
        context.user_data['waiting_agent'] = True
        context.user_data['session_start_time'] = time.time()  # 记录开始时间
        
        await query.edit_message_text(
            "👤 **已连接专属客服**\n\n"
            "请直接发送您的问题，我们将尽快为您解答。\n\n"
            "如果 30 分钟内无对话，系统将自动结束会话。\n"
            "点击下方按钮可手动结束：",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ 结束客服对话", callback_data='cs_end')]]),
            parse_mode='Markdown'
        )
        
        # 通知客服（使用加强版提取格式）
        await context.bot.send_message(
            SUPPORT_AGENT_ID,
            f"📨 **新客服请求**\n"
            f"【客服会话ID: {user_id}】\n\n"
            f"请直接**右滑此消息，点击回复**，即可与该客户聊天。",
            parse_mode='Markdown'
        )
        return

    # 2. 点击拉专群
    if data == 'cs_group':
        if user_id not in ADMIN_IDS:
            await query.edit_message_text("❌ 您没有权限使用此功能。")
            return
        await query.edit_message_text("🚀 **拉专群指令已发送**，客服稍后会联系您。")
        for uid in ADMIN_IDS:
            if uid != user_id:
                await context.bot.send_message(uid, f"🚀 新群组请求\n用户ID: `{user_id}`，请处理。")
        return

    # 3. 结束客服对话
    if data == 'cs_end':
        if 'waiting_agent' in context.user_data:
            del context.user_data['waiting_agent']
        await query.edit_message_text("✅ 客服对话已结束。如需帮助请重新发送 /start。")


# ================= 消息处理 =================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    # === 情况 A：客服主动发起会话（新增功能） ===
    if user_id == SUPPORT_AGENT_ID and text.startswith('/active'):
        args = text.split()
        if len(args) != 2:
            await update.message.reply_text("⚠️ 格式错误。正确格式：`/active 客户数字ID`")
            return
        target_user_id = args[1]
        # 主动发送给客户一条消息，开启对话
        await context.bot.send_message(
            chat_id=target_user_id, 
            text="💬 客服已上线，请问您还有什么问题需要跟进吗？\n\n（如有需要可直接回复我）"
        )
        await update.message.reply_text(f"✅ 已成功主动向客户 `{target_user_id}` 发送消息。")
        return

    # === 情况 B：客户发消息（处于客服模式） ===
    if context.user_data.get('waiting_agent'):
        # 超时检查：如果超过 30 分钟无互动，自动退出
        start_time = context.user_data.get('session_start_time', 0)
        if time.time() - start_time > 1800:  # 1800秒 = 30分钟
            del context.user_data['waiting_agent']
            await update.message.reply_text("⏰ 客服会话已超时（30分钟无互动），已自动结束。如需帮助请重新 /start。")
            return

        # 转发消息给客服（带上严格格式的会话ID）
        await context.bot.send_message(
            SUPPORT_AGENT_ID,
            f"💬 **客户发来新消息**\n"
            f"【客服会话ID: {user_id}】\n"
            f"内容: {text}",
            parse_mode='Markdown'
        )
        return

    # === 情况 C：客服右滑回复（提取唯一会话ID） ===
    if user_id == SUPPORT_AGENT_ID and update.message.reply_to_message:
        admin_msg = update.message.reply_to_message.text
        # 使用绝对安全的正则匹配：提取 【客服会话ID: 数字】
        match = re.search(r"【客服会话ID:\s*(\d+)】", admin_msg)
        
        if match:
            target_user_id = int(match.group(1))
            # 把客服的话转发给对应的客户
            await context.bot.send_message(chat_id=target_user_id, text=f"💬 客服回复：\n\n{text}")
            await update.message.reply_text("✅ 消息已成功转发给客户。")
            return
        else:
            # 如果右滑错了，给客服最清晰的提示
            await update.message.reply_text(
                f"⚠️ 无法提取客户ID。\n\n"
                f"你右滑回复的原始消息是：\n`{admin_msg}`\n\n"
                f"👉 请确保你右滑的是带有 `【客服会话ID: 数字】` 格式的最新通知。"
            )
            return

    # === 情况 D：管理员发了无意义文字 ===
    if user_id in ADMIN_IDS:
        await update.message.reply_text("⚠️ 请先点击按钮选择功能，或作为客服右滑客户消息进行回复。")


def main():
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_click))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logging.info("✅ 客服中转站（优化版）已启动！")
    application.run_polling()

if __name__ == "__main__":
    main()
