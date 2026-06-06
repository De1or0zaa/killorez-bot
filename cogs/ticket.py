import discord
from discord import app_commands
from discord.ext import commands
from utils.database import fetch_one, fetch_all, execute_query
from utils.embeds import create_embed, create_success_embed, create_error_embed, json_to_list, list_to_json, EMBED_GREEN, EMBED_RED, EMBED_PURPLE
import json

WATERMARK = "KILLOREZ HELPER"


async def ensure_ticket_settings(guild_id):
    """Гарантирует что строка настроек существует для сервера"""
    settings = await fetch_one(
        "SELECT * FROM ticket_settings WHERE guild_id = ?",
        (guild_id,)
    )
    if not settings:
        await execute_query(
            "INSERT INTO ticket_settings (guild_id) VALUES (?)",
            (guild_id,)
        )
        settings = await fetch_one(
            "SELECT * FROM ticket_settings WHERE guild_id = ?",
            (guild_id,)
        )
    return settings


# ==================== ВЬЮХИ ДЛЯ НАСТРОЕК ====================

class TicketSettingsView(discord.ui.View):
    def __init__(self, guild_id):
        super().__init__(timeout=300)
        self.guild_id = guild_id

    @discord.ui.button(label="Роли обзванивающего", style=discord.ButtonStyle.primary, row=0)
    async def set_call_roles(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = CallRolesModal(self.guild_id)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Голосовые каналы", style=discord.ButtonStyle.primary, row=0)
    async def set_call_channels(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = CallChannelsModal(self.guild_id)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Канал логов", style=discord.ButtonStyle.primary, row=1)
    async def set_log_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = LogChannelModal(self.guild_id)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Категория тикетов", style=discord.ButtonStyle.primary, row=1)
    async def set_category(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = CategoryModal(self.guild_id)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Приветствие", style=discord.ButtonStyle.secondary, row=2)
    async def set_welcome(self, interaction: discord.Interaction, button: discord.ui.Button):
        settings = await ensure_ticket_settings(self.guild_id)
        modal = WelcomeMessageModal(self.guild_id)
        modal.message_input.default = settings['welcome_message'] or ""
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Сообщение обзвона", style=discord.ButtonStyle.secondary, row=2)
    async def set_call_msg(self, interaction: discord.Interaction, button: discord.ui.Button):
        settings = await ensure_ticket_settings(self.guild_id)
        modal = CallMessageModal(self.guild_id)
        modal.message_input.default = settings['call_message'] or ""
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Вопросы анкеты", style=discord.ButtonStyle.secondary, row=3)
    async def set_questions(self, interaction: discord.Interaction, button: discord.ui.Button):
        settings = await ensure_ticket_settings(self.guild_id)
        modal = QuestionsModal(self.guild_id)
        existing = json_to_list(settings['questions'])
        modal.questions_input.default = "\n".join(existing)
        await interaction.response.send_modal(modal)


# ==================== МОДАЛЫ ====================

class CallRolesModal(discord.ui.Modal, title="Роли обзванивающего"):
    roles_input = discord.ui.TextInput(
        label="ID ролей через запятую",
        placeholder="123456,789012",
        required=True
    )

    def __init__(self, guild_id):
        super().__init__()
        self.guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction):
        await ensure_ticket_settings(self.guild_id)
        roles = [int(r.strip()) for r in self.roles_input.value.split(",") if r.strip().isdigit()]
        if not roles:
            embed = create_error_embed("Ошибка", "Введите хотя бы один корректный ID роли!")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        await execute_query(
            "UPDATE ticket_settings SET call_roles = ? WHERE guild_id = ?",
            (list_to_json(roles), self.guild_id)
        )
        role_mentions = ", ".join([f"<@&{r}>" for r in roles])
        embed = create_success_embed("Успешно", f"Роли обзванивающего обновлены!\n{role_mentions}")
        await interaction.response.send_message(embed=embed, ephemeral=True)


class CallChannelsModal(discord.ui.Modal, title="Голосовые каналы обзвона"):
    channels_input = discord.ui.TextInput(
        label="ID каналов через запятую",
        placeholder="123456,789012",
        required=True
    )

    def __init__(self, guild_id):
        super().__init__()
        self.guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction):
        await ensure_ticket_settings(self.guild_id)
        channels = [int(c.strip()) for c in self.channels_input.value.split(",") if c.strip().isdigit()]
        if not channels:
            embed = create_error_embed("Ошибка", "Введите хотя бы один корректный ID канала!")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        await execute_query(
            "UPDATE ticket_settings SET call_channels = ? WHERE guild_id = ?",
            (list_to_json(channels), self.guild_id)
        )
        channel_mentions = ", ".join([f"<#{c}>" for c in channels])
        embed = create_success_embed("Успешно", f"Голосовые каналы обзвона обновлены!\n{channel_mentions}")
        await interaction.response.send_message(embed=embed, ephemeral=True)


class LogChannelModal(discord.ui.Modal, title="Канал логов тикетов"):
    channel_input = discord.ui.TextInput(
        label="ID канала логов",
        placeholder="123456789",
        required=True
    )

    def __init__(self, guild_id):
        super().__init__()
        self.guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction):
        await ensure_ticket_settings(self.guild_id)
        if not self.channel_input.value.strip().isdigit():
            embed = create_error_embed("Ошибка", "Введите корректный ID канала!")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        channel_id = int(self.channel_input.value.strip())
        await execute_query(
            "UPDATE ticket_settings SET log_channel_id = ? WHERE guild_id = ?",
            (channel_id, self.guild_id)
        )
        embed = create_success_embed("Успешно", f"Канал логов тикетов обновлен! <#{channel_id}>")
        await interaction.response.send_message(embed=embed, ephemeral=True)


class CategoryModal(discord.ui.Modal, title="Категория тикетов"):
    category_input = discord.ui.TextInput(
        label="ID категории",
        placeholder="123456789",
        required=True
    )

    def __init__(self, guild_id):
        super().__init__()
        self.guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction):
        await ensure_ticket_settings(self.guild_id)
        if not self.category_input.value.strip().isdigit():
            embed = create_error_embed("Ошибка", "Введите корректный ID категории!")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        category_id = int(self.category_input.value.strip())
        await execute_query(
            "UPDATE ticket_settings SET category_id = ? WHERE guild_id = ?",
            (category_id, self.guild_id)
        )
        embed = create_success_embed("Успешно", f"Категория тикетов обновлена! <#{category_id}>")
        await interaction.response.send_message(embed=embed, ephemeral=True)


class WelcomeMessageModal(discord.ui.Modal, title="Приветственное сообщение"):
    message_input = discord.ui.TextInput(
        label="Сообщение",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=1000
    )

    def __init__(self, guild_id):
        super().__init__()
        self.guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction):
        await ensure_ticket_settings(self.guild_id)
        await execute_query(
            "UPDATE ticket_settings SET welcome_message = ? WHERE guild_id = ?",
            (self.message_input.value, self.guild_id)
        )
        embed = create_success_embed("Успешно", "Приветственное сообщение обновлено!")
        await interaction.response.send_message(embed=embed, ephemeral=True)


class CallMessageModal(discord.ui.Modal, title="Сообщение обзвона"):
    message_input = discord.ui.TextInput(
        label="Сообщение обзвона",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=1000
    )

    def __init__(self, guild_id):
        super().__init__()
        self.guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction):
        await ensure_ticket_settings(self.guild_id)
        await execute_query(
            "UPDATE ticket_settings SET call_message = ? WHERE guild_id = ?",
            (self.message_input.value, self.guild_id)
        )
        embed = create_success_embed("Успешно", "Сообщение обзвона обновлено!")
        await interaction.response.send_message(embed=embed, ephemeral=True)


class QuestionsModal(discord.ui.Modal, title="Вопросы анкеты"):
    questions_input = discord.ui.TextInput(
        label="Вопросы (каждый с новой строки, макс. 5)",
        style=discord.TextStyle.paragraph,
        placeholder="Ваш вопрос 1\nВаш вопрос 2\nВаш вопрос 3",
        required=True,
        max_length=500
    )

    def __init__(self, guild_id):
        super().__init__()
        self.guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction):
        await ensure_ticket_settings(self.guild_id)
        questions = [q.strip() for q in self.questions_input.value.split("\n") if q.strip()]
        if not questions:
            embed = create_error_embed("Ошибка", "Введите хотя бы один вопрос!")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        questions = questions[:5]  # Максимум 5 вопросов
        await execute_query(
            "UPDATE ticket_settings SET questions = ? WHERE guild_id = ?",
            (list_to_json(questions), self.guild_id)
        )
        questions_text = "\n".join([f"{i+1}. {q}" for i, q in enumerate(questions)])
        embed = create_success_embed("Успешно", f"Вопросы обновлены!\n{questions_text}")
        await interaction.response.send_message(embed=embed, ephemeral=True)


# ==================== ТИКЕТ — СОЗДАНИЕ КАНАЛА ====================

class TicketButtonView(discord.ui.View):
    def __init__(self, bot, guild_id):
        super().__init__(timeout=None)
        self.bot = bot
        self.guild_id = guild_id

    @discord.ui.button(label="Подать тикет", style=discord.ButtonStyle.green, emoji="📩")
    async def create_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        settings = await ensure_ticket_settings(self.guild_id)

        questions = json_to_list(settings['questions'])
        category_id = settings['category_id']

        guild = interaction.guild
        category = guild.get_channel(category_id) if category_id else None

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True, read_message_history=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True, read_message_history=True)
        }

        call_roles = json_to_list(settings['call_roles'])
        for role_id in call_roles:
            role = guild.get_role(role_id)
            if role:
                overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)

        # Счётчик тикетов для уникального имени
        existing_tickets = await fetch_all(
            "SELECT * FROM tickets WHERE guild_id = ?",
            (guild.id,)
        )
        ticket_num = len(existing_tickets) + 1

        channel = await guild.create_text_channel(
            name=f"тикет-{ticket_num}",
            category=category,
            overwrites=overwrites
        )

        await execute_query(
            "INSERT INTO tickets (channel_id, guild_id, user_id) VALUES (?, ?, ?)",
            (channel.id, guild.id, interaction.user.id)
        )

        welcome_msg = settings['welcome_message'] or "Добро пожаловать в тикет! Опишите вашу проблему, и мы поможем вам в ближайшее время."
        embed = create_embed("Тикет создан", welcome_msg, EMBED_GREEN)
        embed.add_field(name="Участник", value=interaction.user.mention, inline=True)

        view = TicketActionView(self.bot, guild.id, interaction.user.id, questions)
        await channel.send(embed=embed, view=view)

        confirm_embed = create_success_embed("Тикет создан", f"Ваш тикет: {channel.mention}")
        await interaction.response.send_message(embed=confirm_embed, ephemeral=True)


# ==================== ДЕЙСТВИЯ В ТИКЕТЕ ====================

class TicketActionView(discord.ui.View):
    def __init__(self, bot, guild_id, owner_id, questions):
        super().__init__(timeout=None)
        self.bot = bot
        self.guild_id = guild_id
        self.owner_id = owner_id
        self.questions = questions

    @discord.ui.button(label="Закрыть тикет", style=discord.ButtonStyle.red, emoji="🔒")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Подтверждение закрытия
        embed = create_embed("Закрытие тикета",
            f"Вы уверены что хотите закрыть тикет? Нажмите кнопку ниже для подтверждения.",
            EMBED_RED)
        view = ConfirmCloseView(self.guild_id)
        await interaction.response.send_message(embed=embed, view=view)

    @discord.ui.button(label="Обзвон", style=discord.ButtonStyle.primary, emoji="📞")
    async def call_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        settings = await ensure_ticket_settings(self.guild_id)

        call_channels = json_to_list(settings['call_channels'])
        call_msg = settings['call_message'] or "Обзвон начат!"

        if not call_channels:
            embed = create_error_embed("Ошибка", "Голосовые каналы не настроены! Используйте `/ticket call_channels`")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        channel_mentions = " ".join([f"<#{c}>" for c in call_channels])
        embed = create_embed("Обзвон", f"{call_msg}\n\nГолосовые каналы: {channel_mentions}", EMBED_PURPLE)

        # Упомянуть владельца тикета
        ticket = await fetch_one("SELECT * FROM tickets WHERE channel_id = ?", (interaction.channel.id,))
        if ticket:
            user = interaction.guild.get_member(ticket['user_id'])
            if user:
                embed.add_field(name="Участник", value=user.mention, inline=True)

        await interaction.response.send_message(content=f"<@{ticket['user_id']}>" if ticket else None, embed=embed)

    @discord.ui.button(label="Анкета", style=discord.ButtonStyle.secondary, emoji="📝")
    async def fill_form(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.questions:
            embed = create_error_embed("Ошибка", "Вопросы не настроены! Используйте `/ticket questions`")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        modal = TicketFormModal(self.questions)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Добавить участника", style=discord.ButtonStyle.success, emoji="➕")
    async def add_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = AddUserModal(self.guild_id)
        await interaction.response.send_modal(modal)


class ConfirmCloseView(discord.ui.View):
    def __init__(self, guild_id):
        super().__init__(timeout=60)
        self.guild_id = guild_id

    @discord.ui.button(label="Подтвердить закрытие", style=discord.ButtonStyle.danger, emoji="✅")
    async def confirm_close(self, interaction: discord.Interaction, button: discord.ui.Button):
        settings = await ensure_ticket_settings(self.guild_id)

        # Собрать логи сообщений из канала
        messages = []
        async for msg in interaction.channel.history(limit=100, oldest_first=True):
            if msg.author.bot:
                continue
            messages.append(f"[{msg.created_at.strftime('%H:%M')}] {msg.author.name}: {msg.content}")

        log_text = "\n".join(messages[-50:]) if messages else "Нет сообщений"

        if settings and settings['log_channel_id']:
            log_channel = interaction.guild.get_channel(settings['log_channel_id'])
            if log_channel:
                ticket = await fetch_one("SELECT * FROM tickets WHERE channel_id = ?", (interaction.channel.id,))
                owner_mention = f"<@{ticket['user_id']}>" if ticket else "Неизвестен"

                log_embed = create_embed("Тикет закрыт",
                    f"**Канал:** {interaction.channel.name}\n**Закрыл:** {interaction.user.mention}\n**Владелец:** {owner_mention}",
                    EMBED_RED)

                # Отправить лог как файл если длинный
                if len(log_text) > 1024:
                    log_embed.add_field(name="Сообщения", value="См. прикрепленный файл", inline=False)
                    import io
                    file = discord.File(io.BytesIO(log_text.encode('utf-8')), filename=f"ticket-{interaction.channel.name}.txt")
                    await log_channel.send(embed=log_embed, file=file)
                else:
                    log_embed.add_field(name="Сообщения", value=log_text[:1024] or "Нет", inline=False)
                    await log_channel.send(embed=log_embed)

        await execute_query("DELETE FROM tickets WHERE channel_id = ?", (interaction.channel.id,))

        closing_embed = create_embed("Тикет закрывается...",
            f"Тикет закрыт пользователем {interaction.user.mention}. Канал будет удален через 5 секунд.",
            EMBED_RED)
        await interaction.response.edit_message(embed=closing_embed, view=None)

        import asyncio
        await asyncio.sleep(5)
        await interaction.channel.delete()


class AddUserModal(discord.ui.Modal, title="Добавить участника в тикет"):
    user_input = discord.ui.TextInput(
        label="ID участника",
        placeholder="123456789",
        required=True
    )

    def __init__(self, guild_id):
        super().__init__()
        self.guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction):
        if not self.user_input.value.strip().isdigit():
            embed = create_error_embed("Ошибка", "Введите корректный ID участника!")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        user_id = int(self.user_input.value.strip())
        member = interaction.guild.get_member(user_id)
        if not member:
            embed = create_error_embed("Ошибка", "Участник не найден на сервере!")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await interaction.channel.set_permissions(member, view_channel=True, send_messages=True, read_message_history=True)

        embed = create_success_embed("Участник добавлен", f"{member.mention} добавлен в тикет!")
        await interaction.response.send_message(embed=embed)


class TicketFormModal(discord.ui.Modal, title="Анкета"):
    def __init__(self, questions):
        super().__init__()
        self.answers = []
        for i, q in enumerate(questions[:5]):
            item = discord.ui.TextInput(label=q[:45], style=discord.TextStyle.paragraph, required=True)
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


# ==================== КОГ ====================

class TicketCog(commands.Cog, name="Ticket"):
    def __init__(self, bot):
        self.bot = bot

    ticket = app_commands.Group(name="ticket", description="Система тикетов")

    @ticket.command(name="setup", description="Начальная настройка тикетов")
    @app_commands.describe(
        category="Категория для тикетов",
        log_channel="Канал логов тикетов"
    )
    async def ticket_setup(self, interaction: discord.Interaction,
                           category: discord.CategoryChannel = None,
                           log_channel: discord.TextChannel = None):
        settings = await ensure_ticket_settings(interaction.guild.id)

        updates = []
        if category:
            await execute_query(
                "UPDATE ticket_settings SET category_id = ? WHERE guild_id = ?",
                (category.id, interaction.guild.id)
            )
            updates.append(f"**Категория:** {category.mention}")

        if log_channel:
            await execute_query(
                "UPDATE ticket_settings SET log_channel_id = ? WHERE guild_id = ?",
                (log_channel.id, interaction.guild.id)
            )
            updates.append(f"**Канал логов:** {log_channel.mention}")

        if not updates:
            embed = create_error_embed("Ошибка", "Укажите хотя бы один параметр!")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        embed = create_success_embed("Тикеты настроены", "\n".join(updates))
        await interaction.response.send_message(embed=embed)

    @ticket.command(name="category", description="Изменить категорию тикетов")
    @app_commands.describe(category="Категория для тикетов")
    async def ticket_category(self, interaction: discord.Interaction, category: discord.CategoryChannel):
        await ensure_ticket_settings(interaction.guild.id)
        await execute_query(
            "UPDATE ticket_settings SET category_id = ? WHERE guild_id = ?",
            (category.id, interaction.guild.id)
        )
        embed = create_success_embed("Успешно", f"Категория тикетов: {category.mention}")
        await interaction.response.send_message(embed=embed)

    @ticket.command(name="log_channel", description="Изменить канал логов тикетов")
    @app_commands.describe(channel="Канал логов")
    async def ticket_log_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await ensure_ticket_settings(interaction.guild.id)
        await execute_query(
            "UPDATE ticket_settings SET log_channel_id = ? WHERE guild_id = ?",
            (channel.id, interaction.guild.id)
        )
        embed = create_success_embed("Успешно", f"Канал логов тикетов: {channel.mention}")
        await interaction.response.send_message(embed=embed)

    @ticket.command(name="call_roles", description="Изменить роли обзванивающего")
    @app_commands.describe(role1="Роль 1", role2="Роль 2", role3="Роль 3", role4="Роль 4", role5="Роль 5")
    async def ticket_call_roles(self, interaction: discord.Interaction,
                                 role1: discord.Role = None, role2: discord.Role = None,
                                 role3: discord.Role = None, role4: discord.Role = None,
                                 role5: discord.Role = None):
        await ensure_ticket_settings(interaction.guild.id)
        roles = [r for r in [role1, role2, role3, role4, role5] if r is not None]
        if not roles:
            embed = create_error_embed("Ошибка", "Укажите хотя бы одну роль!")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        role_ids = [r.id for r in roles]
        await execute_query(
            "UPDATE ticket_settings SET call_roles = ? WHERE guild_id = ?",
            (list_to_json(role_ids), interaction.guild.id)
        )
        role_mentions = ", ".join([r.mention for r in roles])
        embed = create_success_embed("Успешно", f"Роли обзванивающего: {role_mentions}")
        await interaction.response.send_message(embed=embed)

    @ticket.command(name="call_channels", description="Изменить голосовые каналы обзвона")
    @app_commands.describe(channel1="Канал 1", channel2="Канал 2", channel3="Канал 3", channel4="Канал 4", channel5="Канал 5")
    async def ticket_call_channels(self, interaction: discord.Interaction,
                                    channel1: discord.VoiceChannel = None, channel2: discord.VoiceChannel = None,
                                    channel3: discord.VoiceChannel = None, channel4: discord.VoiceChannel = None,
                                    channel5: discord.VoiceChannel = None):
        await ensure_ticket_settings(interaction.guild.id)
        channels = [c for c in [channel1, channel2, channel3, channel4, channel5] if c is not None]
        if not channels:
            embed = create_error_embed("Ошибка", "Укажите хотя бы один канал!")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        channel_ids = [c.id for c in channels]
        await execute_query(
            "UPDATE ticket_settings SET call_channels = ? WHERE guild_id = ?",
            (list_to_json(channel_ids), interaction.guild.id)
        )
        channel_mentions = ", ".join([c.mention for c in channels])
        embed = create_success_embed("Успешно", f"Голосовые каналы обзвона: {channel_mentions}")
        await interaction.response.send_message(embed=embed)

    @ticket.command(name="welcome", description="Изменить приветственное сообщение")
    @app_commands.describe(message="Приветственное сообщение")
    async def ticket_welcome(self, interaction: discord.Interaction, message: str):
        await ensure_ticket_settings(interaction.guild.id)
        await execute_query(
            "UPDATE ticket_settings SET welcome_message = ? WHERE guild_id = ?",
            (message, interaction.guild.id)
        )
        embed = create_success_embed("Успешно", f"Приветственное сообщение обновлено!")
        await interaction.response.send_message(embed=embed)

    @ticket.command(name="call_message", description="Изменить сообщение обзвона")
    @app_commands.describe(message="Сообщение обзвона")
    async def ticket_call_message(self, interaction: discord.Interaction, message: str):
        await ensure_ticket_settings(interaction.guild.id)
        await execute_query(
            "UPDATE ticket_settings SET call_message = ? WHERE guild_id = ?",
            (message, interaction.guild.id)
        )
        embed = create_success_embed("Успешно", "Сообщение обзвона обновлено!")
        await interaction.response.send_message(embed=embed)

    @ticket.command(name="questions", description="Изменить вопросы анкеты")
    @app_commands.describe(
        question1="Вопрос 1", question2="Вопрос 2", question3="Вопрос 3",
        question4="Вопрос 4", question5="Вопрос 5"
    )
    async def ticket_questions(self, interaction: discord.Interaction,
                                question1: str = None, question2: str = None,
                                question3: str = None, question4: str = None,
                                question5: str = None):
        await ensure_ticket_settings(interaction.guild.id)
        questions = [q for q in [question1, question2, question3, question4, question5] if q is not None]
        if not questions:
            embed = create_error_embed("Ошибка", "Укажите хотя бы один вопрос!")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await execute_query(
            "UPDATE ticket_settings SET questions = ? WHERE guild_id = ?",
            (list_to_json(questions), interaction.guild.id)
        )
        questions_text = "\n".join([f"{i+1}. {q}" for i, q in enumerate(questions)])
        embed = create_success_embed("Успешно", f"Вопросы обновлены!\n{questions_text}")
        await interaction.response.send_message(embed=embed)

    @ticket.command(name="settings", description="Панель настроек тикетов")
    async def ticket_settings(self, interaction: discord.Interaction):
        settings = await ensure_ticket_settings(interaction.guild.id)

        call_roles = json_to_list(settings['call_roles'])
        call_channels = json_to_list(settings['call_channels'])
        questions = json_to_list(settings['questions'])

        roles_str = ', '.join([f'<@&{r}>' for r in call_roles]) or 'Не установлены'
        channels_str = ', '.join([f'<#{c}>' for c in call_channels]) or 'Не установлены'
        log_str = f'<#{settings["log_channel_id"]}>' if settings['log_channel_id'] else 'Не установлен'
        cat_str = f'<#{settings["category_id"]}>' if settings['category_id'] else 'Не установлена'
        questions_str = '\n'.join([f'{i+1}. {q}' for i, q in enumerate(questions)]) if questions else 'Не установлены'

        desc = f"**Категория:** {cat_str}\n"
        desc += f"**Канал логов:** {log_str}\n"
        desc += f"**Роли обзванивающего:** {roles_str}\n"
        desc += f"**Голосовые каналы:** {channels_str}\n"
        desc += f"**Вопросы:**\n{questions_str}\n"
        desc += f"\n**Приветствие:** {settings['welcome_message'] or 'По умолчанию'}\n"
        desc += f"**Сообщение обзвона:** {settings['call_message'] or 'По умолчанию'}"

        embed = create_embed("Настройки тикетов", desc, EMBED_PURPLE)
        view = TicketSettingsView(interaction.guild.id)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @ticket.command(name="create", description="Создать кнопку для подачи тикета")
    async def ticket_create(self, interaction: discord.Interaction):
        settings = await ensure_ticket_settings(interaction.guild.id)

        if not settings['category_id']:
            embed = create_error_embed("Ошибка", "Сначала настройте категорию тикетов! Используйте `/ticket category`")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        embed = create_embed(
            "Подать тикет",
            "Нажмите кнопку ниже, чтобы подать тикет. Вам будет создан личный канал, где вы сможете задать свой вопрос.",
            EMBED_GREEN
        )
        view = TicketButtonView(self.bot, interaction.guild.id)
        await interaction.response.send_message(embed=embed, view=view)

    @ticket.command(name="close", description="Закрыть текущий тикет")
    async def ticket_close(self, interaction: discord.Interaction):
        ticket = await fetch_one("SELECT * FROM tickets WHERE channel_id = ?", (interaction.channel.id,))
        if not ticket:
            embed = create_error_embed("Ошибка", "Это не канал тикета!")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        settings = await ensure_ticket_settings(interaction.guild.id)

        # Собрать логи
        messages = []
        async for msg in interaction.channel.history(limit=100, oldest_first=True):
            if msg.author.bot:
                continue
            messages.append(f"[{msg.created_at.strftime('%H:%M')}] {msg.author.name}: {msg.content}")

        log_text = "\n".join(messages[-50:]) if messages else "Нет сообщений"

        if settings and settings['log_channel_id']:
            log_channel = interaction.guild.get_channel(settings['log_channel_id'])
            if log_channel:
                owner_mention = f"<@{ticket['user_id']}>"
                log_embed = create_embed("Тикет закрыт",
                    f"**Канал:** {interaction.channel.name}\n**Закрыл:** {interaction.user.mention}\n**Владелец:** {owner_mention}",
                    EMBED_RED)

                if len(log_text) > 1024:
                    log_embed.add_field(name="Сообщения", value="См. прикрепленный файл", inline=False)
                    import io
                    file = discord.File(io.BytesIO(log_text.encode('utf-8')), filename=f"ticket-{interaction.channel.name}.txt")
                    await log_channel.send(embed=log_embed, file=file)
                else:
                    log_embed.add_field(name="Сообщения", value=log_text[:1024] or "Нет", inline=False)
                    await log_channel.send(embed=log_embed)

        await execute_query("DELETE FROM tickets WHERE channel_id = ?", (interaction.channel.id,))

        closing_embed = create_embed("Тикет закрывается...",
            f"Тикет закрыт {interaction.user.mention}. Канал будет удален через 5 секунд.", EMBED_RED)
        await interaction.response.send_message(embed=closing_embed)

        import asyncio
        await asyncio.sleep(5)
        await interaction.channel.delete()


async def setup(bot):
    await bot.add_cog(TicketCog(bot))
