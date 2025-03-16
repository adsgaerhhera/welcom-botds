import discord
import asyncio
import os
import sys
import traceback
from discord.ext import commands
from aiohttp import web
import logging
import threading

# ===== ロギング設定 =====
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("discord_bot")

# ===== Discordボットの初期化 =====
intents = discord.Intents.default()
intents.members = True
intents.presences = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ===== 環境変数から設定を取得 =====
try:
    TOKEN = os.getenv("DISCORD_TOKEN")
    ROLE_ID = int(os.getenv("DISCORD_ROLE_ID", "0") or 0)
    WELCOME_CHANNEL_ID = int(os.getenv("DISCORD_WELCOME_CHANNEL_ID", "0") or 0)
    ERROR_REPORT_USER_IDS = [int(x) for x in os.getenv("ERROR_REPORT_USER_IDS", "").split(",") if x.isdigit()]
    BOT_OWNER_IDS = [int(x) for x in os.getenv("BOT_OWNER_IDS", "").split(",") if x.isdigit()]
except ValueError as e:
    logger.critical(f"環境変数の取得中にエラー: {e}")
    sys.exit(1)

if not TOKEN:
    logger.critical("TOKEN が設定されていません。ボットを起動できません。")
    sys.exit(1)

# ===== ヘルスチェック用HTTPサーバー =====
async def health_check(request):
    """ヘルスチェックエンドポイント"""
    return web.Response(text="OK")

app = web.Application()
app.add_routes([web.get('/health', health_check)])

def run_health_server():
    """バックグラウンドでHTTPサーバーを起動"""
    web.run_app(app, host="0.0.0.0", port=8000)

# ===== Discordボットのイベントとコマンド =====
@bot.event
async def on_ready():
    logger.info(f"ボットが起動しました: {bot.user}")

@bot.event
async def on_member_join(member):
    """新メンバーがサーバーに参加したときに呼び出される"""
    try:
        role = member.guild.get_role(ROLE_ID)
        welcome_channel = bot.get_channel(WELCOME_CHANNEL_ID)

        if role and welcome_channel:
            await welcome_channel.send(
                f"ようこそ {role.mention} の皆さん！\n"
                "「お喋りを始める前に、もういくつかステップがあります。」と出ていると思うので、\n"
                "「了解」を押してルールに同意してください。\n"
                "その後、https://discord.com/channels/1165775639798878288/1165775640918773843 で認証をして、みんなとお喋りをしましょう！"
            )
            await asyncio.sleep(60)  # 必要に応じた待機
    except Exception as e:
        error_message = f"on_member_joinエラー:\n{traceback.format_exc()}"
        logger.error(error_message)
        for user_id in ERROR_REPORT_USER_IDS:
            try:
                user = await bot.fetch_user(user_id)
                await user.send(f"エラー通知:\n{error_message}")
            except Exception as dm_error:
                logger.error(f"DM送信エラー: {dm_error}")

@bot.event
async def on_error(event, *args, **kwargs):
    """イベント処理中のエラーをキャッチ"""
    error_message = f"イベント {event} 中のエラー:\n{traceback.format_exc()}"
    logger.error(error_message)
    for user_id in ERROR_REPORT_USER_IDS:
        try:
            user = await bot.fetch_user(user_id)
            await user.send(f"エラー通知:\n{error_message}")
        except Exception as dm_error:
            logger.error(f"DM送信エラー: {dm_error}")

@bot.event
async def on_disconnect():
    """切断イベントの処理"""
    logger.warning("Discordサーバーから切断されました。再接続を試みます。")

@bot.event
async def on_resumed():
    """再接続成功時の処理"""
    logger.info("Discordサーバーへの接続が再開されました。")

@bot.command(name="restart")
async def restart(ctx):
    """ボット再起動用コマンド"""
    if ctx.author.id not in BOT_OWNER_IDS:
        await ctx.send("このコマンドを実行する権限がありません。")
        logger.warning(f"{ctx.author.name} が無権限で再起動を試みました。")
        return

    await ctx.send("ボットを再起動しています...")
    logger.info("ボットを再起動します。")
    await bot.close()
    os._exit(0)

async def report_status():
    """定期的にエラーがないことを通知"""
    await bot.wait_until_ready()
    while not bot.is_closed():
        try:
            for user_id in ERROR_REPORT_USER_IDS:
                user = await bot.fetch_user(user_id)
                await user.send("過去1時間、エラーは発生しませんでした。")
            await asyncio.sleep(3600)  # 1時間待機
        except Exception as e:
            logger.error(f"report_status中にエラーが発生しました: {e}")

# ===== メイン関数 =====
async def main():
    asyncio.create_task(report_status())  # 定期エラーレポートタスク
    threading.Thread(target=run_health_server, daemon=True).start()  # HTTPサーバー起動
    async with bot:
        await bot.start(TOKEN)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("ボットが手動で停止されました。")
    except Exception as e:
        logger.critical(f"致命的なエラー: {traceback.format_exc()}")
