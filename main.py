import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
from utils.database import init_db

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True
intents.reactions = True
intents.dm_messages = True

bot = commands.Bot(command_prefix='!', intents=intents)


@bot.event
async def on_ready():
    await init_db()
    print(f'{bot.user} запущен!')
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="KILLOREZ HELPER"))
    
    # Load cogs
    cogs_to_load = ['afk', 'ticket', 'car', 'warnings', 'points', 'market', 'commands']
    for cog_name in cogs_to_load:
        try:
            await bot.load_extension(f'cogs.{cog_name}')
            print(f'Загружен ког: {cog_name}')
        except Exception as e:
            print(f'Ошибка загрузки кога {cog_name}: {e}')
    
    # Sync commands
    try:
        synced = await bot.tree.sync()
        print(f'Синхронизировано {len(synced)} команд')
    except Exception as e:
        print(f'Ошибка синхронизации команд: {e}')


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        embed = discord.Embed(title="Ошибка", description="У вас нет прав для выполнения этой команды.", color=0xED4245)
        embed.set_footer(text="KILLOREZ HELPER")
        await ctx.send(embed=embed)
    elif isinstance(error, commands.MissingRequiredArgument):
        embed = discord.Embed(title="Ошибка", description="Укажите все необходимые аргументы.", color=0xED4245)
        embed.set_footer(text="KILLOREZ HELPER")
        await ctx.send(embed=embed)


TOKEN = os.getenv('DISCORD_TOKEN')
if not TOKEN:
    print("ОШИБКА: Установите DISCORD_TOKEN в .env файле!")
    exit(1)

bot.run(TOKEN)
