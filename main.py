import logging
import re
import time
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

from config import BOT_TOKEN, ADMIN_IDS, SUPPORT_AGENT_ID, MONITOR_ID

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# ================= 静默监控核心函数 =================
async def send_monitor_log(bot, user_id, event, content=None, reply_content=None):
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # 安全获取用户名
        try:
            user = await bot.get_chat(user_id)
            uname = user.username or user.first_name or f"用户{user_id}"
        except:
            uname = f"用户{user_id}"

        log_msg = (
            f"📋 **用户动态监控日志**\n"
            f"🕐 时间：{timestamp}\n"
            f"🆔 用户ID：`{user_id}`\n"
            f"👤 用户名称：@{uname}\n"
            f"📌 事件：{event}\n"
        )
        if content:
            log_msg += f"💬 内容：{content}\n"
        if reply_content:
            log_msg += f"💬 **客服回复内容**：{reply_content}\n"
        
        # 静默发送给监控者
        await bot.send_message(chat_id=MONITOR_ID, text=log_msg, parse_mode='Markdown')
    except Exception as e:
        print(f"发送监控日志失败: {e}")

# ================= 主菜单 =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    is_admin = user_id in ADMIN_IDS
    keyboard = []
    keyboard.append([InlineKeyboardButton("👤 人工客服", callback_data='cs_agent')])
    if is_admin:
        keyboard.append([InlineKeyboardButton("🚀 拉专群", callback_data='cs_group')])
    await update.message.reply_text("👋 欢迎进入专用客服控制台：", reply_markup=InlineKeyboardMarkup(keyboard))
    # 【监控】记录用户点击了开始
    await send_monitor_log(context.bot, user_id, "进入主菜单")

# ================= 按钮点击处理 =================
async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    try:
        if data == 'cs_agent':
            # 【监控】记录用户点击人工客服
            await send_monitor_log(context.bot, user_id, "点击【人工客服】按钮")
            
            context.user_data['waiting_agent'] = True
            context.user_data['session_start_time'] = time.time()
            
            await query.edit_message_text(
                "👤 **已连接专属客服**\n\n请直接发送您的问题，我们将尽快为您解答。\n\n如果 30 分钟内无对话，系统将自动结束会话。\n点击下方按钮可手动结束：",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ 结束客服对话", callback_data='cs_end')]]),
                parse_mode='Markdown'
            )
            await context.bot.send_message(
                SUPPORT_AGENT_ID,
                f"📨 **新客服请求**\n【客服会话ID: {user_id}】\n\n请直接**右滑此消息，点击回复**，即可与该客户聊天。",
                parse_mode='Markdown'
            )
            return

        if data == 'cs_group':
            if user_id not in ADMIN_IDS:
                await query.edit_message_text("❌ 您没有权限使用此功能。")
                return
            # 【监控】记录管理员点击拉专群
            await send_monitor_log(context.bot, user_id, "点击【拉专群】按钮")
            
            await query.edit_message_text("🚀 **拉专群指令已发送**，客服稍后会联系您。")
            for uid in ADMIN_IDS:
                if uid != user_id:
                    await context.bot.send_message(uid, f"🚀 新群组请求\n用户ID: `{user_id}`，请处理。")
            return

        if data == 'cs_end':
            if 'waiting_agent' in context.user_data:
                # 【监控】记录用户手动结束客服
                await send_monitor_log(context.bot, user_id, "手动结束客服对话")
                del context.user_data['waiting_agent']
            await query.edit_message_text("✅ 客服对话已结束。如需帮助请重新发送 /start。")
            return

    except Exception as e:
        print(f"❌ 按钮处理异常: {e}")

# ================= 消息处理 =================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        text = update.message.text

        # === 情况 A：客服主动发起会话 ===
        if user_id == SUPPORT_AGENT_ID and text.startswith('/active'):
            args = text.split()
            if len(args) != 2:
                await update.message.reply_text("⚠️ 格式错误。正确格式：`/active 客户数字ID`")
                return
            target_user_id = args[1]
            
            # 【监控】记录客服主动联系客户
            await send_monitor_log(context.bot, int(target_user_id), "客服主动发起跟进", reply_content=text)
            
            await context.bot.send_message(
                chat_id=target_user_id, 
                text="💬 客服已上线，请问您还有什么问题需要跟进吗？\n\n（如有需要可直接回复我）"
            )
            await update.message.reply_text(f"✅ 已成功主动向客户 `{target_user_id}` 发送消息。")
            return

        # === 情况 B：客户发消息 ===
        if context.user_data.get('waiting_agent'):
            start_time = context.user_data.get('session_start_time', 0)
            if time.time() - start_time > 1800:  # 30分钟超时
                # 【监控】记录会话超时
                await send_monitor_log(context.bot, user_id, "客服会话超时自动结束")
                del context.user_data['waiting_agent']
                await update.message.reply_text("⏰ 客服会话已超时（30分钟无互动），已自动结束。如需帮助请重新 /start。")
                return

            # 【监控】静默记录客户发来的消息
            await send_monitor_log(context.bot, user_id, "客户发送消息", content=text)

            await context.bot.send_message(
                SUPPORT_AGENT_ID,
                f"💬 **客户发来新消息**\n【客服会话ID: {user_id}】\n内容: {text}",
                parse_mode='Markdown'
            )
            return

        # === 情况 C：客服右滑回复 ===
        if user_id == SUPPORT_AGENT_ID and update.message.reply_to_message:
            admin_msg = update.message.reply_to_message.text
            match = re.search(r"【客服会话ID:\s*(\d+)】", admin_msg)
            
            if match:
                target_user_id = int(match.group(1))
                await context.bot.send_message(chat_id=target_user_id, text=f"💬 客服回复：\n\n{text}")
                await update.message.reply_text("✅ 消息已成功转发给客户。")
                
                # 【监控】静默记录客服回复了什么内容
                await send_monitor_log(context.bot, target_user_id, "客服回复消息", reply_content=text)
                return
            else:
                await update.message.reply_text(
                    f"⚠️ 提取客户ID失败。请确保你右滑的是带有 `【客服会话ID: 数字】` 格式的最新通知。"
                )
            return

        # === 情况 D：管理员发了无意义文字 ===
        if user_id in ADMIN_IDS:
            await update.message.reply_text("⚠️ 请先点击按钮选择功能，或作为客服右滑客户消息进行回复。")

    except Exception as e:
        print(f"❌ 处理消息异常: {e}")

def main():
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_click))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logging.info("✅ 客服中转站（静默监控版）已启动！")
    application.run_polling()

if __name__ == "__main__":
    main()
