import discord
from discord import app_commands
from discord.ext import commands
from utils.database import fetch_one, fetch_all, execute_query
from utils.embeds import create_embed, create_success_embed, create_error_embed, json_to_list, list_to_json, EMBED_GREEN, EMBED_RED, EMBED_PURPLE
import json

WATERMARK = "KILLOREZ HELPER"


class TicketSettingsView(discord.ui.View):
    def __init__(self, guild_id):
        super().__init__(timeout=300)
        self.guild_id = guild_id

    @discord.ui.button(label="Изменить роль обзванивающего", style=discord.ButtonStyle.primary, row=0)
    async def set_call_roles(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = CallRolesModal(self.guild_id)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Изменить голосовые каналы", style=discord.ButtonStyle.primary, row=0)
    async def set_call_channels(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = CallChannelsModal(self.guild_id)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Изменить канал логов", style=discord.ButtonStyle.primary, row=1)
    async def set_log_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = LogChannelModal(self.guild_id)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Изменить раздел тикетов", style=discord.ButtonStyle.primary, row=1)
    async def set_category(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = CategoryModal(self.guild_id)
        await interaction.response.send_modal(modal)


class CallRolesModal(discord.ui.Modal, title="Изменить роли обзванивающего"):
    roles_input = discord.ui.TextInput(label="ID ролей через запятую", placeholder="123456,789012")

    def __init__(self, guild_id):
        super().__init__()
        self.guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction):
        roles = [int(r.strip()) for r in self.roles_input.value.split(",") if r.strip().isdigit()]
        await execute_query(
            "UPDATE ticket_settings SET call_roles = ? WHERE guild_id = ?",
            (list_to_json(roles), self.guild_id)
        )
        embed = create_success_embed("Успешно", f"Роли обзванивающего обновлены!")
        await interaction.response.send_message(embed=embed, ephemeral=True)


class CallChannelsModal(discord.ui.Modal, title="Изменить голосовые каналы"):
    channels_input = discord.ui.TextInput(label="ID каналов через запятую", placeholder="123456,789012")

    def __init__(self, guild_id):
        super().__init__()
        self.guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction):
        channels = [int(c.strip()) for c in self.channels_input.value.split(",") if c.strip().isdigit()]
        await execute_query(
            "UPDATE ticket_settings SET call_channels = ? WHERE guild_id = ?",
            (list_to_json(channels), self.guild_id)
        )
        embed = create_success_embed("Успешно", "Голосовые каналы обзвона обновлены!")
        await interaction.response.send_message(embed=embed, ephemeral=True)


class LogChannelModal(discord.ui.Modal, title="Изменить канал логов"):
    channel_input = discord.ui.TextInput(label="ID канала логов", placeholder="123456789")

    def __init__(self, guild_id):
        super().__init__()
        self.guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction):
        if not self.channel_input.value.strip().isdigit():
            embed = create_error_embed("Ошибка", "Введите корректный ID канала!")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        await execute_query(
            "UPDATE ticket_settings SET log_channel_id = ? WHERE guild_id = ?",
            (int(self.channel_input.value.strip()), self.guild_id)
        )
        embed = create_success_embed("Успешно", "Канал логов тикетов обновлен!")
        await interaction.response.send_message(embed=embed, ephemeral=True)


class CategoryModal(discord.ui.Modal, title="Изменить раздел тикетов"):
    category_input = discord.ui.TextInput(label="ID категории", placeholder="123456789")

    def __init__(self, guild_id):
        super().__init__()
        self.guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction):
        if not self.category_input.value.strip().isdigit():
            embed = create_error_embed("Ошибка", "Введите корректный ID категории!")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        await execute_query(
            "UPDATE ticket_settings SET category_id = ? WHERE guild_id = ?",
            (int(self.category_input.value.strip()), self.guild_id)
        )
        embed = create_success_embed("Успешно", "Раздел тикетов обновлен!")
        await interaction.response.send_message(embed=embed, ephemeral=True)


class WelcomeMessageModal(discord.ui.Modal, title="Изменить вступительное сообщение"):
    message_input = discord.ui.TextInput(label="Сообщение", style=discord.TextStyle.paragraph)

    def __init__(self, guild_id):
        super().__init__()
        self.guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction):
        await execute_query(
            "UPDATE ticket_settings SET welcome_message = ? WHERE guild_id = ?",
            (self.message_input.value, self.guild_id)
        )
        embed = create_success_embed("Успешно", "Вступительное сообщение обновлено!")
        await interaction.response.send_message(embed=embed, ephemeral=True)


class CallMessageModal(discord.ui.Modal, title="Изменить сообщение обзвона"):
    message_input = discord.ui.TextInput(label="Сообщение обзвона", style=discord.TextStyle.paragraph)

    def __init__(self, guild_id):
        super().__init__()
        self.guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction):
        await execute_query(
            "UPDATE ticket_settings SET call_message = ? WHERE guild_id = ?",
            (self.message_input.value, self.guild_id)
        )
        embed = create_success_embed("Успешно", "Сообщение обзвона обновлено!")
        await interaction.response.send_message(embed=embed, ephemeral=True)


class QuestionsModal(discord.ui.Modal, title="Изменить вопросы"):
    questions_input = discord.ui.TextInput(
        label="Вопросы (каждый с новой строки)",
        style=discord.TextStyle.paragraph,
        placeholder="Ваш вопрос 1\nВаш вопрос 2\nВаш вопрос 3"
    )

    def __init__(self, guild_id):
        super().__init__()
        self.guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction):
        questions = [q.strip() for q in self.questions_input.value.split("\n") if q.strip()]
        await execute_query(
            "UPDATE ticket_settings SET questions = ? WHERE guild_id = ?",
            (list_to_json(questions), self.guild_id)
        )
        embed = create_success_embed("Успешно", f"Вопросы обновлены! ({len(questions)} вопросов)")
        await interaction.response.send_message(embed=embed, ephemeral=True)


class TicketButtonView(discord.ui.View):
    def __init__(self, bot, guild_id):
        super().__init__(timeout=None)
        self.bot = bot
        self.guild_id = guild_id

    @discord.ui.button(label="Подать тикет", style=discord.ButtonStyle.green, emoji="📩")
    async def create_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        settings = await fetch_one(
            "SELECT * FROM ticket_settings WHERE guild_id = ?",
            (self.guild_id,)
        )
        if not settings:
            embed = create_error_embed("Ошибка", "Тикет система не настроена!")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        questions = json_to_list(settings['questions'])
        category_id = settings['category_id']
        
        guild = interaction.guild
        category = guild.get_channel(category_id) if category_id else None
        
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True)
        }
        
        call_roles = json_to_list(settings['call_roles'])
        for role_id in call_roles:
            role = guild.get_role(role_id)
            if role:
                overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)

        channel = await guild.create_text_channel(
            name=f"тикет-{interaction.user.name}",
            category=category,
            overwrites=overwrites
        )

        await execute_query(
            "INSERT INTO tickets (channel_id, guild_id, user_id) VALUES (?, ?, ?)",
            (channel.id, guild.id, interaction.user.id)
        )

        welcome_msg = settings['welcome_message'] or "Добро пожаловать в тикет!"
        embed = create_embed("Тикет создан", welcome_msg, EMBED_GREEN)
        embed.add_field(name="Участник", value=interaction.user.mention, inline=True)
        
        view = TicketActionView(self.bot, guild.id, interaction.user.id, questions)
        await channel.send(embed=embed, view=view)

        confirm_embed = create_success_embed("Тикет создан", f"Ваш тикет: {channel.mention}")
        await interaction.response.send_message(embed=confirm_embed, ephemeral=True)


class TicketActionView(discord.ui.View):
    def __init__(self, bot, guild_id, owner_id, questions):
        super().__init__(timeout=None)
        self.bot = bot
        self.guild_id = guild_id
        self.owner_id = owner_id
        self.questions = questions

    @discord.ui.button(label="Закрыть тикет", style=discord.ButtonStyle.red, emoji="🔒")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = create_embed("Тикет закрыт", f"Тикет закрыт пользователем {interaction.user.mention}", EMBED_RED)
        await interaction.response.send_message(embed=embed)
        
        settings = await fetch_one(
            "SELECT * FROM ticket_settings WHERE guild_id = ?",
            (self.guild_id,)
        )
        if settings and settings['log_channel_id']:
            log_channel = interaction.guild.get_channel(settings['log_channel_id'])
            if log_channel:
                log_embed = create_embed("Тикет закрыт", f"Тикет {interaction.channel.name} закрыт", EMBED_RED)
                log_embed.add_field(name="Закрыл", value=interaction.user.mention, inline=True)
                await log_channel.send(embed=log_embed)
        
        await execute_query("DELETE FROM tickets WHERE channel_id = ?", (interaction.channel.id,))
        await interaction.channel.delete()

    @discord.ui.button(label="Обзвон", style=discord.ButtonStyle.primary, emoji="📞")
    async def call_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        settings = await fetch_one(
            "SELECT * FROM ticket_settings WHERE guild_id = ?",
            (self.guild_id,)
        )
        if not settings:
            embed = create_error_embed("Ошибка", "Настройки не найдены!")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        call_channels = json_to_list(settings['call_channels'])
        call_msg = settings['call_message'] or "Обзвон начат!"
        
        if not call_channels:
            embed = create_error_embed("Ошибка", "Голосовые каналы не настроены!")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        channel_mentions = " ".join([f"<#{c}>" for c in call_channels])
        embed = create_embed("Обзвон", f"{call_msg}\n\nГолосовые каналы: {channel_mentions}", EMBED_PURPLE)
        
        # Mention ticket owner
        ticket = await fetch_one("SELECT * FROM tickets WHERE channel_id = ?", (interaction.channel.id,))
        if ticket:
            user = interaction.guild.get_member(ticket['user_id'])
            if user:
                embed.add_field(name="Участник", value=user.mention, inline=True)
        
        await interaction.response.send_message(embed=embed)

    @discord.ui.button(label="Анкета", style=discord.ButtonStyle.secondary, emoji="📝")
    async def fill_form(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.questions:
            embed = create_error_embed("Ошибка", "Вопросы не настроены!")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        modal = TicketFormModal(self.questions)
        await interaction.response.send_modal(modal)


class TicketFormModal(discord.ui.Modal, title="Анкета"):
    def __init__(self, questions):
        super().__init__()
        self.answers = []
        for i, q in enumerate(questions[:5]):  # Max 5 fields
            item = discord.ui.TextInput(label=q[:45], style=discord.TextStyle.paragraph)
            self.add_item(item)
        self.questions = questions

    async def on_submit(self, interaction: discord.Interaction):
        answers = []
        for child in self.children:
            if isinstance(child, discord.ui.TextInput):
                answers.append(f"**{child.label}:** {child.value}")
        
        desc = "\n".join(answers)
        embed = create_embed("Ответы на анкету", desc, EMBED_PURPLE)
        embed.add_field(name="Участник", value=interaction.user.mention, inline=True)
        await interaction.response.send_message(embed=embed)


class TicketCog(commands.Cog, name="Ticket"):
    def __init__(self, bot):
        self.bot = bot

    ticket = app_commands.Group(name="ticket", description="Система тикетов")

    @ticket.command(name="set", description="Настройки тикетов")
    @app_commands.describe(setting="Что изменить", message="Текст сообщения")
    async def ticket_set(self, interaction: discord.Interaction, setting: str, message: str = ""):
        settings = await fetch_one(
            "SELECT * FROM ticket_settings WHERE guild_id = ?",
            (interaction.guild.id,)
        )
        if not settings:
            await execute_query(
                "INSERT INTO ticket_settings (guild_id) VALUES (?)",
                (interaction.guild.id,)
            )

        if setting == "message":
            modal = WelcomeMessageModal(interaction.guild.id)
            modal.message_input.default = settings['welcome_message'] if settings else ""
            await interaction.response.send_modal(modal)
        elif setting == "call":
            modal = CallMessageModal(interaction.guild.id)
            modal.message_input.default = settings['call_message'] if settings else ""
            await interaction.response.send_modal(modal)
        elif setting == "questions":
            modal = QuestionsModal(interaction.guild.id)
            if settings:
                existing = json_to_list(settings['questions'])
                modal.questions_input.default = "\n".join(existing)
            await interaction.response.send_modal(modal)
        else:
            embed = create_error_embed("Ошибка", "Используйте: message, call, questions")
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @ticket.command(name="settings", description="Настройки тикетов с кнопками")
    async def ticket_settings(self, interaction: discord.Interaction):
        settings = await fetch_one(
            "SELECT * FROM ticket_settings WHERE guild_id = ?",
            (interaction.guild.id,)
        )
        if not settings:
            await execute_query(
                "INSERT INTO ticket_settings (guild_id) VALUES (?)",
                (interaction.guild.id,)
            )
            settings = await fetch_one(
                "SELECT * FROM ticket_settings WHERE guild_id = ?",
                (interaction.guild.id,)
            )

        call_roles = json_to_list(settings['call_roles'])
        call_channels = json_to_list(settings['call_channels'])
        
        roles_str = ', '.join([f'<@&{r}>' for r in call_roles]) or 'Не установлены'
        channels_str = ', '.join([f'<#{c}>' for c in call_channels]) or 'Не установлены'
        log_str = f'<#{settings["log_channel_id"]}>' if settings['log_channel_id'] else 'Не установлен'
        cat_str = f'<#{settings["category_id"]}>' if settings['category_id'] else 'Не установлен'

        desc = f"**Роли обзванивающего:** {roles_str}\n"
        desc += f"**Голосовые каналы:** {channels_str}\n"
        desc += f"**Канал логов:** {log_str}\n"
        desc += f"**Раздел тикетов:** {cat_str}\n"

        embed = create_embed("Настройки тикетов", desc, EMBED_PURPLE)
        view = TicketSettingsView(interaction.guild.id)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @ticket.command(name="create", description="Создать кнопку для подачи тикета")
    async def ticket_create(self, interaction: discord.Interaction):
        settings = await fetch_one(
            "SELECT * FROM ticket_settings WHERE guild_id = ?",
            (interaction.guild.id,)
        )
        if not settings:
            embed = create_error_embed("Ошибка", "Сначала настройте тикет систему!")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        embed = create_embed(
            "Подать тикет",
            "Нажмите кнопку ниже, чтобы подать тикет. Вам будет создан личный канал, где вы сможете задать свой вопрос.",
            EMBED_GREEN
        )
        view = TicketButtonView(self.bot, interaction.guild.id)
        await interaction.response.send_message(embed=embed, view=view)


async def setup(bot):
    await bot.add_cog(TicketCog(bot))
