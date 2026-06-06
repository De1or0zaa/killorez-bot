import discord
from discord import app_commands
from discord.ext import commands
from utils.database import fetch_one, fetch_all, execute_query
from utils.embeds import create_embed, create_success_embed, create_error_embed, EMBED_GREEN, EMBED_RED, EMBED_PURPLE

WATERMARK = "KILLOREZ HELPER"


# ==================== UI: КНОПКА ОТЧЕТА ====================

class PointsReportView(discord.ui.View):
    def __init__(self, guild_id):
        super().__init__(timeout=None)
        self.guild_id = guild_id

    @discord.ui.button(label="Создать отчет", style=discord.ButtonStyle.green, emoji="📋")
    async def report_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        events = await fetch_all(
            "SELECT * FROM point_events WHERE guild_id = ?",
            (self.guild_id,)
        )
        if not events:
            embed = create_error_embed("Ошибка", "Нет доступных мероприятий!")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        embed = create_embed("Выберите мероприятие",
            "Выберите мероприятие в выпадающем списке ниже, за которое вы хотели бы получить очки!",
            EMBED_PURPLE)
        view = discord.ui.View(timeout=120)
        view.add_item(EventSelect(events))
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class EventSelect(discord.ui.Select):
    def __init__(self, events):
        options = []
        for e in events:
            options.append(discord.SelectOption(
                label=e['name'],
                description=f"Очки: {e['points']}",
                value=str(e['event_id'])
            ))
        super().__init__(placeholder="Выберите мероприятие", options=options)
        self.events = events

    async def callback(self, interaction: discord.Interaction):
        event_id = int(self.values[0])
        event = await fetch_one(
            "SELECT * FROM point_events WHERE event_id = ?",
            (event_id,)
        )
        if not event:
            embed = create_error_embed("Ошибка", "Мероприятие не найдено!")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        modal = EvidenceModal(event, interaction.guild.id)
        await interaction.response.send_modal(modal)


# ==================== UI: МОДАЛ ДОКАЗАТЕЛЬСТВ ====================

class EvidenceModal(discord.ui.Modal, title="Отчет на баллы"):
    description_input = discord.ui.TextInput(
        label="Описание",
        style=discord.TextStyle.paragraph,
        placeholder="Опишите ваше участие в мероприятии",
        required=True,
        max_length=500
    )
    evidence_input = discord.ui.TextInput(
        label="Доказательства (ссылки на скриншоты/видео)",
        style=discord.TextStyle.paragraph,
        placeholder="Вставьте ссылку на скриншот или видео с мероприятия\nНапример: https://cdn.discordapp.com/...",
        required=False,
        max_length=1000
    )

    def __init__(self, event, guild_id):
        super().__init__()
        self.event = event
        self.guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction):
        settings = await fetch_one(
            "SELECT * FROM point_settings WHERE guild_id = ?",
            (self.guild_id,)
        )
        if not settings or not settings['log_channel_id']:
            embed = create_error_embed("Ошибка", "Канал логов для отчетов не настроен! Используйте `/points log_channel`")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        log_channel = interaction.guild.get_channel(settings['log_channel_id'])
        if not log_channel:
            embed = create_error_embed("Ошибка", "Канал логов не найден!")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        desc = f"**От:** {interaction.user.mention}\n"
        desc += f"**Мероприятие:** {self.event['name']}\n"
        desc += f"**Очки:** {self.event['points']}\n"
        desc += f"**Описание:** {self.description_input.value}"

        evidence_text = self.evidence_input.value.strip() if self.evidence_input.value else ""
        if evidence_text:
            desc += f"\n**Доказательства:** {evidence_text}"

        evidence_embed = create_embed("Новый отчет!", desc, EMBED_PURPLE)

        view = ApproveRejectView(
            user_id=interaction.user.id,
            guild_id=self.guild_id,
            event_id=self.event['event_id'],
            event_name=self.event['name'],
            points=self.event['points']
        )

        await log_channel.send(embed=evidence_embed, view=view)

        confirm_embed = create_success_embed("Отчет отправлен",
            f"Ваш отчет за **{self.event['name']}** отправлен на проверку модераторам!")
        await interaction.response.send_message(embed=confirm_embed, ephemeral=True)


# ==================== UI: ОДОБРИТЬ / ОТКЛОНИТЬ ====================

class ApproveRejectView(discord.ui.View):
    def __init__(self, user_id, guild_id, event_id, event_name, points):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.guild_id = guild_id
        self.event_id = event_id
        self.event_name = event_name
        self.points = points

    @discord.ui.button(label="Одобрить", style=discord.ButtonStyle.green, emoji="✅")
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        existing = await fetch_one(
            "SELECT * FROM points WHERE user_id = ? AND guild_id = ?",
            (self.user_id, self.guild_id)
        )
        if existing:
            await execute_query(
                "UPDATE points SET amount = amount + ? WHERE user_id = ? AND guild_id = ?",
                (self.points, self.user_id, self.guild_id)
            )
            new_amount = existing['amount'] + self.points
        else:
            new_amount = self.points
            await execute_query(
                "INSERT INTO points (user_id, guild_id, amount) VALUES (?, ?, ?)",
                (self.user_id, self.guild_id, self.points)
            )

        user = interaction.client.get_user(self.user_id)

        embed = create_success_embed("Отчет одобрен",
            f"Отчет **{self.event_name}** от {user.mention if user else f'<@{self.user_id}>'} одобрен! +{self.points} очков\nТекущий баланс: **{new_amount}** очков")
        await interaction.response.edit_message(embed=embed, view=None)

        try:
            dm_embed = create_success_embed("Отчет одобрен!",
                f"Ваш отчет за **{self.event_name}** одобрен! +{self.points} очков\nТекущий баланс: **{new_amount}** очков")
            if user:
                await user.send(embed=dm_embed)
        except discord.Forbidden:
            pass

    @discord.ui.button(label="Отклонить", style=discord.ButtonStyle.red, emoji="❌")
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.client.get_user(self.user_id)

        embed = create_embed("Отчет отклонен",
            f"Отчет от {user.mention if user else f'<@{self.user_id}>'} отклонен.", EMBED_RED)
        await interaction.response.edit_message(embed=embed, view=None)

        try:
            dm_embed = create_embed("Отчет отклонен",
                f"Ваш отчет за **{self.event_name}** был отклонен.", EMBED_RED)
            if user:
                await user.send(embed=dm_embed)
        except discord.Forbidden:
            pass


# ==================== КОГ ====================

class PointsCog(commands.Cog, name="Points"):
    def __init__(self, bot):
        self.bot = bot

    points = app_commands.Group(name="points", description="Система баллов и отчетов")

    # --- Посмотреть очки ---
    @points.command(name="balance", description="Посмотреть свои очки")
    @app_commands.describe(member="Участник (необязательно)")
    async def points_balance(self, interaction: discord.Interaction, member: discord.Member = None):
        target = member or interaction.user
        existing = await fetch_one(
            "SELECT * FROM points WHERE user_id = ? AND guild_id = ?",
            (target.id, interaction.guild.id)
        )
        amount = existing['amount'] if existing else 0

        embed = create_embed("Баланс", f"У {target.mention} **{amount}** очков", EMBED_GREEN)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # --- Изменить очки (админ) ---
    @points.command(name="set", description="Изменить кол-во баллов у участника")
    @app_commands.describe(member="Участник", amount="Кол-во очков (+xx или -xx)")
    async def points_set(self, interaction: discord.Interaction, member: discord.Member, amount: str):
        try:
            if amount.startswith("+"):
                points = int(amount[1:])
            elif amount.startswith("-"):
                points = -int(amount[1:])
            else:
                points = int(amount)
        except ValueError:
            embed = create_error_embed("Ошибка", "Введите корректное число! Пример: +10 или -5")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        existing = await fetch_one(
            "SELECT * FROM points WHERE user_id = ? AND guild_id = ?",
            (member.id, interaction.guild.id)
        )
        if existing:
            new_amount = max(0, existing['amount'] + points)
            await execute_query(
                "UPDATE points SET amount = ? WHERE user_id = ? AND guild_id = ?",
                (new_amount, member.id, interaction.guild.id)
            )
        else:
            new_amount = max(0, points)
            await execute_query(
                "INSERT INTO points (user_id, guild_id, amount) VALUES (?, ?, ?)",
                (member.id, interaction.guild.id, new_amount)
            )

        embed = create_success_embed("Очки обновлены",
            f"У {member.mention} теперь **{new_amount}** очков (изменение: {'+' if points >= 0 else ''}{points})")
        await interaction.response.send_message(embed=embed)

    # --- Добавить мероприятие ---
    @points.command(name="add_event", description="Добавить мероприятие и очки за него")
    @app_commands.describe(name="Название мероприятия", points="Кол-во очков за мероприятие")
    async def points_add_event(self, interaction: discord.Interaction, name: str, points: int):
        await execute_query(
            "INSERT INTO point_events (guild_id, name, points) VALUES (?, ?, ?)",
            (interaction.guild.id, name, points)
        )
        embed = create_success_embed("Мероприятие добавлено", f"**{name}** — **{points}** очков")
        await interaction.response.send_message(embed=embed)

    # --- Удалить мероприятие ---
    @points.command(name="remove_event", description="Удалить мероприятие")
    @app_commands.describe(name="Название мероприятия")
    async def points_remove_event(self, interaction: discord.Interaction, name: str):
        result = await fetch_one(
            "SELECT * FROM point_events WHERE guild_id = ? AND name = ?",
            (interaction.guild.id, name)
        )
        if not result:
            embed = create_error_embed("Ошибка", f"Мероприятие **{name}** не найдено!")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await execute_query(
            "DELETE FROM point_events WHERE guild_id = ? AND name = ?",
            (interaction.guild.id, name)
        )
        embed = create_success_embed("Мероприятие удалено", f"**{name}** удалено из списка мероприятий")
        await interaction.response.send_message(embed=embed)

    # --- Список мероприятий ---
    @points.command(name="events", description="Список всех мероприятий")
    async def points_events(self, interaction: discord.Interaction):
        events = await fetch_all(
            "SELECT * FROM point_events WHERE guild_id = ?",
            (interaction.guild.id,)
        )
        if not events:
            embed = create_embed("Мероприятия", "Нет добавленных мероприятий.", EMBED_PURPLE)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        desc = ""
        for i, e in enumerate(events, 1):
            desc += f"{i}. **{e['name']}** — {e['points']} очков\n"

        embed = create_embed("Мероприятия", desc, EMBED_PURPLE)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # --- Кнопка для отчетов ---
    @points.command(name="button", description="Создать кнопку для подачи отчетов")
    async def points_button(self, interaction: discord.Interaction):
        events = await fetch_all(
            "SELECT * FROM point_events WHERE guild_id = ?",
            (interaction.guild.id,)
        )

        desc = "Нажмите кнопку ниже, чтобы создать отчет на баллы за мероприятие."
        if events:
            desc += "\n\n**Доступные мероприятия:**\n"
            for e in events:
                desc += f"• {e['name']} — {e['points']} очков\n"

        embed = create_embed("Отчеты на баллы", desc, EMBED_GREEN)
        view = PointsReportView(interaction.guild.id)
        await interaction.response.send_message(embed=embed, view=view)

    # --- Канал логов отчетов ---
    @points.command(name="log_channel", description="Изменить канал логов для отчетов")
    @app_commands.describe(channel="Канал логов")
    async def points_log_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        settings = await fetch_one(
            "SELECT * FROM point_settings WHERE guild_id = ?",
            (interaction.guild.id,)
        )
        if settings:
            await execute_query(
                "UPDATE point_settings SET log_channel_id = ? WHERE guild_id = ?",
                (channel.id, interaction.guild.id)
            )
        else:
            await execute_query(
                "INSERT INTO point_settings (guild_id, log_channel_id) VALUES (?, ?)",
                (interaction.guild.id, channel.id)
            )

        embed = create_success_embed("Канал логов обновлен", f"Отчеты будут отправляться в {channel.mention}")
        await interaction.response.send_message(embed=embed)

    # --- Сбросить всем очки ---
    @points.command(name="reset_all", description="Сбросить всем очки")
    async def points_reset_all(self, interaction: discord.Interaction):
        await execute_query(
            "DELETE FROM points WHERE guild_id = ?",
            (interaction.guild.id,)
        )
        embed = create_success_embed("Очки сброшены", "Все очки участников были сброшены!")
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(PointsCog(bot))
