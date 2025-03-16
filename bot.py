import discord
import asyncio
import os
import sys
import traceback
from discord.ext import commands

# インテント設定とボットの初期化
intents = discord.Intents.default()
intents.members = True  # Server Members Intent を有効化
intents.presences = True  # Presence Intent を有効化
intents.message_content = True  # Message Content Intent を有効化

bot = commands.Bot(command_prefix="!", intents=intents)

# 環境変数から設定値を取得
TOKEN = os.getenv("DISCORD_TOKEN")  # Botトークン
ROLE_ID = int(os.getenv("DISCORD_ROLE_ID", "0"))  # ロールID (デフォルト値を0)
WELCOME_CHANNEL_ID = int(os.getenv("DISCORD_WELCOME_CHANNEL_ID", "0"))  # チャンネルID (デフォルト値を0)
ERROR_REPORT_USER_IDS = list(map(int, filter(None, os.getenv("ERROR_REPORT_USER_IDS", "").split(","))))
BOT_OWNER_IDS = list(map(int, filter(None, os.getenv("BOT_OWNER_IDS", "").split(","))))

# トークンの存在確認
if not TOKEN:
    print("環境変数 DISCORD_TOKEN が設定されていません。ボットを起動できません。")
    sys.exit(1)

# ロギング設定
import logging
logging.basicConfig(level=logging.INFO)  # 必要に応じてDEBUGに変更可能
logger = logging.getLogger("discord_bot")

# メッセージ送信管理変数
can_send_message = True

async def report_status():
    """
    1時間ごとにエラーがなかったことを指定されたユーザーにDMで送信
    """
    await bot.wait_until_ready()
    try:
        while not bot.is_closed():
            for user_id in ERROR_REPORT_USER_IDS:
                try:
                    user = await bot.fetch_user(user_id)
                    await user.send("過去1時間、エラーは発生しませんでした。")
                    logger.info(f"エラーレポートを {user.name} に送信しました。")
                except Exception as e:
                    logger.error(f"エラーレポート送信中のエラー: {e}")
            await asyncio.sleep(3600)  # 1時間待機
    except asyncio.CancelledError:
        logger.warning("report_statusタスクがキャンセルされました。")
    except Exception as e:
        logger.error(f"report_statusタスク中に予期しないエラー: {traceback.format_exc()}")

@bot.event
async def on_member_join(member):
    """
    新メンバーがサーバーに参加したときに呼び出される
    """
    global can_send_message

    try:
        role = member.guild.get_role(ROLE_ID)
        welcome_channel = bot.get_channel(WELCOME_CHANNEL_ID)

        if role and welcome_channel and can_send_message:
            await welcome_channel.send(
                f"ようこそ {role.mention} の皆さん！\n"
                "「お喋りを始める前に、もういくつかステップがあります。」と出ていると思うので、\n"
                "「了解」を押してルールに同意してください。\n"
                "その後、https://discord.com/channels/1165775639798878288/1165775640918773843 で認証をして、みんなとお喋りをしましょう！"
            )
            can_send_message = False
            await asyncio.sleep(60)  # 60秒間待機
            can_send_message = True
            logger.info(f"歓迎メッセージを {member.name} に送信しました。")
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
    """
    イベント処理中にエラーが発生した場合に呼び出される
    """
    error_message = f"イベント {event} 中のエラー:\n{traceback.format_exc()}"
    logger.error(error_message)
    for user_id in ERROR_REPORT_USER_IDS:
        try:
            user = await bot.fetch_user(user_id)
            await user.send(f"エラー通知:\n{error_message}")
        except Exception as dm_error:
            logger.error(f"DM送信エラー: {dm_error}")

@bot.event
async def on_ready():
    """
    ボットが起動し、準備が整ったときに呼び出される
    """
    logger.info(f"ボットが起動しました: {bot.user}")

@bot.event
async def on_disconnect():
    """
    Discordサーバーから切断されたときに呼び出される
    """
    logger.warning("Discordサーバーから切断されました。再接続を試みます。")

@bot.event
async def on_resumed():
    """
    Discordサーバーへの接続が再開されたときに呼び出される
    """
    logger.info("Discordサーバーへの接続が再開されました。")

@bot.command(name="restart")
async def restart(ctx):
    """
    !restart コマンドでボットを再起動
    """
    if ctx.author.id not in BOT_OWNER_IDS:
        await ctx.send("このコマンドを実行する権限がありません。")
        logger.warning(f"再起動コマンドが権限のないユーザー {ctx.author.name} によって試されました。")
        return

    await ctx.send("ボットを再起動しています...")
    logger.info(f"再起動コマンドが {ctx.author.name} によって実行されました。")
    await bot.close()
    os._exit(0)

async def main():
    """
    メイン関数で非同期にボットを起動
    """
    asyncio.create_task(report_status())
    async with bot:
        await bot.start(TOKEN)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("ボットが手動で停止されました。")
    except Exception as e:
        logger.critical(f"致命的なエラーでボットが停止しました: {traceback.format_exc()}")
