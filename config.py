import os

# 从 Railway 环境变量读取
BOT_TOKEN = os.getenv("BOT_TOKEN")

# 你的管理员权限（你本人的 ID + 客服的 ID）
ADMIN_IDS = [7857605443, 8538513211]

# 专属客服账号（只有这个账号会收到客户消息）
SUPPORT_AGENT_ID = 8538513211
