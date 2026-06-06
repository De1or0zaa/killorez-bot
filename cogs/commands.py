import discord
from discord import app_commands
from discord.ext import commands
from utils.database import fetch_one, fetch_all, execute_query
from utils.embeds import create_embed, create_success_embed, create_error_embed, json_to_list, list_to_json, EMBED_GREEN, EMBED_RED, EMBED_PURPLE
from datetime import datetime
import io

WATERMARK = "KILLOREZ HELPER"


# ==================== POINTS REPORT FLOW ====================

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

        # Сразу открываем модал для ввода доказательств
        modal = EvidenceModal(event, interaction.guild.id)
        await interaction.response.send_modal(modal)


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
            embed = create_error_embed("Ошибка", "Канал логов для отчетов не настроен! Используйте `/set points_logs`")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        log_channel = interaction.guild.get_channel(settings['log_channel_id'])
        if not log_channel:
            embed = create_error_embed("Ошибка", "Канал логов не найден!")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Формируем описание отчета
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

        # ОДНО сообщение в канал логов
        await log_channel.send(embed=evidence_embed, view=view)

        confirm_embed = create_success_embed("Отчет отправлен",
            f"Ваш отчет за **{self.event['name']}** отправлен на проверку модераторам!")
        await interaction.response.send_message(embed=confirm_embed, ephemeral=True)


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


# ==================== MARKET ====================

class MarketSelect(discord.ui.Select):
    def __init__(self, products, guild_id):
        options = []
        for p in products:
            options.append(discord.SelectOption(
                label=p['name'],
                description=f"Цена: {p['price']} очков",
                value=str(p['product_id'])
            ))
        super().__init__(placeholder="Выбрать товар", options=options)
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        product_id = int(self.values[0])
        product = await fetch_one(
            "SELECT * FROM market_products WHERE product_id = ? AND guild_id = ?",
            (product_id, self.guild_id)
        )
        if not product:
            embed = create_error_embed("Ошибка", "Товар не найден!")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        points_row = await fetch_one(
            "SELECT * FROM points WHERE user_id = ? AND guild_id = ?",
            (interaction.user.id, self.guild_id)
        )
        user_points = points_row['amount'] if points_row else 0

        if user_points < product['price']:
            embed = create_error_embed("Недостаточно очков",
                f"У вас **{user_points}** очков, а товар стоит **{product['price']}** очков!")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        new_amount = user_points - product['price']
        if new_amount <= 0:
            await execute_query(
                "DELETE FROM points WHERE user_id = ? AND guild_id = ?",
                (interaction.user.id, self.guild_id)
            )
        else:
            await execute_query(
                "UPDATE points SET amount = ? WHERE user_id = ? AND guild_id = ?",
                (new_amount, interaction.user.id, self.guild_id)
            )

        # Log purchase
        settings = await fetch_one(
            "SELECT * FROM market_settings WHERE guild_id = ?",
            (self.guild_id,)
        )
        if settings and settings['log_channel_id']:
            log_channel = interaction.guild.get_channel(settings['log_channel_id'])
            if log_channel:
                log_embed = create_embed("Заказ выполнен!",
                    f"**Товар:** {product['name']}\n**Заказчик:** {interaction.user.mention}\n**Исполнитель:** будет назначен\n**Цена:** {product['price']} очков",
                    EMBED_PURPLE)
                log_embed.set_footer(text=WATERMARK)
                await log_channel.send(embed=log_embed)

        embed = create_success_embed("Покупка совершена!",
            f"Вы купили **{product['name']}** за **{product['price']}** очков!\nОстаток: **{new_amount}** очков")
        await interaction.response.send_message(embed=embed, ephemeral=True)


class MarketShopView(discord.ui.View):
    def __init__(self, guild_id, products):
        super().__init__(timeout=None)
        self.guild_id = guild_id
        self.add_item(MarketSelect(products, guild_id))

    @discord.ui.button(label="Вернуться", style=discord.ButtonStyle.red)
    async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        settings = await fetch_one(
            "SELECT * FROM market_settings WHERE guild_id = ?",
            (interaction.guild.id,)
        )
        welcome_msg = settings['welcome_message'] if settings else "В данном магазине вы можете обменять свои очки на товары."

        embed = create_embed("Магазин", welcome_msg, EMBED_GREEN)
        view = MarketButtonView(guild_id=interaction.guild.id)
        await interaction.response.edit_message(embed=embed, view=view)


class MarketButtonView(discord.ui.View):
    def __init__(self, guild_id):
        super().__init__(timeout=None)
        self.guild_id = guild_id

    @discord.ui.button(label="Магазин", style=discord.ButtonStyle.green, emoji="🛒")
    async def shop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        settings = await fetch_one(
            "SELECT * FROM market_settings WHERE guild_id = ?",
            (self.guild_id,)
        )
        if not settings:
            embed = create_error_embed("Ошибка", "Магазин не настроен!")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        if settings['roles']:
            market_role_ids = json_to_list(settings['roles'])
            has_role = any(interaction.guild.get_role(rid) in interaction.user.roles for rid in market_role_ids)
            if not has_role:
                role_mentions = ", ".join([f"<@&{rid}>" for rid in market_role_ids])
                embed = create_error_embed("Ошибка", f"У вас нет нужной роли для доступа к магазину!\nТребуются: {role_mentions}")
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

        products = await fetch_all(
            "SELECT * FROM market_products WHERE guild_id = ?",
            (self.guild_id,)
        )
        if not products:
            embed = create_error_embed("Магазин пуст", "Нет товаров в магазине!")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        desc = ""
        if settings['exchange_enabled']:
            desc += f"**Внутренняя валюта:**\n🟢 Курс: {settings['exchange_rate']}$/банк\n\n"

        desc += "**Вещественные товары:**\n"
        for i, p in enumerate(products, 1):
            desc += f"{i}) {p['name']} | Цена: {p['price']}\n"

        embed = create_embed("Выберите товар", desc, EMBED_PURPLE)
        view = MarketShopView(self.guild_id, products)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


# ==================== COG ====================

class AllCommandsCog(commands.Cog, name="AllCommands"):
    """Centralized command cog to avoid group conflicts"""

    def __init__(self, bot):
        self.bot = bot

    # ==================== SET GROUP ====================
    set_group = app_commands.Group(name="set", description="Настройки бота")

    # --- Main Roles ---
    @set_group.command(name="mainroles", description="Выбрать основные роли")
    @app_commands.describe(roles="ID ролей через запятую")
    async def set_mainroles(self, interaction: discord.Interaction, roles: str):
        role_ids = [int(r.strip()) for r in roles.split(",") if r.strip().isdigit()]
        settings = await fetch_one(
            "SELECT * FROM guild_settings WHERE guild_id = ?",
            (interaction.guild.id,)
        )
        if settings:
            await execute_query(
                "UPDATE guild_settings SET main_roles = ? WHERE guild_id = ?",
                (list_to_json(role_ids), interaction.guild.id)
            )
        else:
            await execute_query(
                "INSERT INTO guild_settings (guild_id, main_roles) VALUES (?, ?)",
                (interaction.guild.id, list_to_json(role_ids))
            )

        role_mentions = ", ".join([f"<@&{r}>" for r in role_ids])
        embed = create_success_embed("Основные роли обновлены", f"Роли: {role_mentions}")
        await interaction.response.send_message(embed=embed)

    # --- Points ---
    @set_group.command(name="points", description="Изменить кол-во баллов у участника")
    @app_commands.describe(member="Участник", amount="Кол-во очков (+xx или -xx)")
    async def set_points(self, interaction: discord.Interaction, member: discord.Member, amount: str):
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

    # --- Points Market ---
    @set_group.command(name="points_market", description="Добавить мероприятие и очки за него")
    @app_commands.describe(name="Название мероприятия", points="Кол-во очков")
    async def add_points_market(self, interaction: discord.Interaction, name: str, points: int):
        await execute_query(
            "INSERT INTO point_events (guild_id, name, points) VALUES (?, ?, ?)",
            (interaction.guild.id, name, points)
        )
        embed = create_success_embed("Мероприятие добавлено", f"**{name}** — **{points}** очков")
        await interaction.response.send_message(embed=embed)

    # --- Points Button ---
    @set_group.command(name="points_button", description="Добавить кнопку для отчетов на баллы")
    async def set_points_button(self, interaction: discord.Interaction):
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

    # --- Points Logs ---
    @set_group.command(name="points_logs", description="Изменить канал логов для отчетов")
    @app_commands.describe(channel="Канал логов")
    async def set_points_logs(self, interaction: discord.Interaction, channel: discord.TextChannel):
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

        embed = create_success_embed("Канал логов обновлен", f"Канал: {channel.mention}")
        await interaction.response.send_message(embed=embed)

    # --- Market Product ---
    @set_group.command(name="market_product", description="Добавить продукт в магазин")
    @app_commands.describe(name="Название товара", price="Цена в очках", description="Описание товара")
    async def set_market_product(self, interaction: discord.Interaction, name: str, price: int, description: str = ""):
        await execute_query(
            "INSERT INTO market_products (guild_id, name, price, description) VALUES (?, ?, ?, ?)",
            (interaction.guild.id, name, price, description)
        )
        embed = create_success_embed("Товар добавлен", f"**{name}** добавлен в магазин за **{price}** очков!")
        await interaction.response.send_message(embed=embed)

    # --- Market Roles ---
    @set_group.command(name="role_market", description="Изменить роли для доступа к магазину")
    @app_commands.describe(roles="ID ролей через запятую")
    async def set_role_market(self, interaction: discord.Interaction, roles: str):
        role_ids = [int(r.strip()) for r in roles.split(",") if r.strip().isdigit()]
        settings = await fetch_one(
            "SELECT * FROM market_settings WHERE guild_id = ?",
            (interaction.guild.id,)
        )
        if settings:
            await execute_query(
                "UPDATE market_settings SET roles = ? WHERE guild_id = ?",
                (list_to_json(role_ids), interaction.guild.id)
            )
        else:
            await execute_query(
                "INSERT INTO market_settings (guild_id, roles) VALUES (?, ?)",
                (interaction.guild.id, list_to_json(role_ids))
            )
        role_mentions = ", ".join([f"<@&{r}>" for r in role_ids])
        embed = create_success_embed("Роли магазина обновлены", f"Роли: {role_mentions}")
        await interaction.response.send_message(embed=embed)

    @set_group.command(name="role_market_admin", description="Изменить админ роли магазина")
    @app_commands.describe(roles="ID ролей через запятую")
    async def set_role_market_admin(self, interaction: discord.Interaction, roles: str):
        role_ids = [int(r.strip()) for r in roles.split(",") if r.strip().isdigit()]
        settings = await fetch_one(
            "SELECT * FROM market_settings WHERE guild_id = ?",
            (interaction.guild.id,)
        )
        if settings:
            await execute_query(
                "UPDATE market_settings SET admin_roles = ? WHERE guild_id = ?",
                (list_to_json(role_ids), interaction.guild.id)
            )
        else:
            await execute_query(
                "INSERT INTO market_settings (guild_id, admin_roles) VALUES (?, ?)",
                (interaction.guild.id, list_to_json(role_ids))
            )
        role_mentions = ", ".join([f"<@&{r}>" for r in role_ids])
        embed = create_success_embed("Роли админов магазина обновлены", f"Роли: {role_mentions}")
        await interaction.response.send_message(embed=embed)

    # ==================== CREATE GROUP ====================
    create_group = app_commands.Group(name="create", description="Создание элементов")

    @create_group.command(name="market_button", description="Добавить кнопки магазина")
    async def create_market_button(self, interaction: discord.Interaction):
        settings = await fetch_one(
            "SELECT * FROM market_settings WHERE guild_id = ?",
            (interaction.guild.id,)
        )
        welcome_msg = settings['welcome_message'] if settings else "В данном магазине вы можете обменять свои очки либо на другую валюту, либо на товары, устанавливаемые вручную администрацией. Для того, чтобы воспользоваться магазином, нажмите кнопку ниже."

        embed = create_embed("Магазин", welcome_msg, EMBED_GREEN)
        view = MarketButtonView(guild_id=interaction.guild.id)
        await interaction.response.send_message(embed=embed, view=view)

    @create_group.command(name="market_logs", description="Добавить канал логов магазина")
    @app_commands.describe(channel="Канал логов")
    async def create_market_logs(self, interaction: discord.Interaction, channel: discord.TextChannel):
        settings = await fetch_one(
            "SELECT * FROM market_settings WHERE guild_id = ?",
            (interaction.guild.id,)
        )
        if settings:
            await execute_query(
                "UPDATE market_settings SET log_channel_id = ? WHERE guild_id = ?",
                (channel.id, interaction.guild.id)
            )
        else:
            await execute_query(
                "INSERT INTO market_settings (guild_id, log_channel_id) VALUES (?, ?)",
                (interaction.guild.id, channel.id)
            )
        embed = create_success_embed("Канал логов магазина обновлен", f"Канал: {channel.mention}")
        await interaction.response.send_message(embed=embed)

    # ==================== LOGS GROUP ====================
    logs_group = app_commands.Group(name="logs", description="Система логов")

    @logs_group.command(name="channel", description="Выбрать канал для логов")
    @app_commands.describe(channel="Канал для логов")
    async def logs_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        settings = await fetch_one(
            "SELECT * FROM guild_settings WHERE guild_id = ?",
            (interaction.guild.id,)
        )
        if settings:
            await execute_query(
                "UPDATE guild_settings SET log_channel_id = ? WHERE guild_id = ?",
                (channel.id, interaction.guild.id)
            )
        else:
            await execute_query(
                "INSERT INTO guild_settings (guild_id, log_channel_id) VALUES (?, ?)",
                (interaction.guild.id, channel.id)
            )

        embed = create_success_embed("Канал логов обновлен", f"Логи будут отправляться в {channel.mention}")
        await interaction.response.send_message(embed=embed)

    # ==================== POINTS COMMANDS ====================
    @app_commands.command(name="points_reset_all", description="Сбросить всем очки")
    async def points_reset_all(self, interaction: discord.Interaction):
        await execute_query(
            "DELETE FROM points WHERE guild_id = ?",
            (interaction.guild.id,)
        )
        embed = create_success_embed("Очки сброшены", "Все очки участников были сброшены!")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="points", description="Посмотреть свои очки")
    @app_commands.describe(member="Участник (необязательно)")
    async def check_points(self, interaction: discord.Interaction, member: discord.Member = None):
        target = member or interaction.user
        existing = await fetch_one(
            "SELECT * FROM points WHERE user_id = ? AND guild_id = ?",
            (target.id, interaction.guild.id)
        )
        amount = existing['amount'] if existing else 0

        embed = create_embed("Очки", f"У {target.mention} **{amount}** очков", EMBED_GREEN)
        await interaction.response.send_message(embed=embed)

    # ==================== MESSAGE GROUP ====================
    message_group = app_commands.Group(name="message", description="Система рассылки")

    @message_group.command(name="send", description="Отправить сообщение в ЛС людям с ролью")
    @app_commands.describe(role="Роль получателей", text="Текст сообщения")
    async def message_send(self, interaction: discord.Interaction, role: discord.Role, text: str):
        await interaction.response.defer(thinking=True)

        members_with_role = [m for m in role.members if not m.bot]
        delivered = 0
        not_delivered = 0

        embed_to_send = create_embed(
            f"Сообщение от {interaction.guild.name}",
            text,
            discord.Color.blue()
        )
        embed_to_send.add_field(name="Отправлено", value=interaction.user.mention, inline=True)
        embed_to_send.set_footer(text=WATERMARK)

        for member in members_with_role:
            try:
                await member.send(embed=embed_to_send)
                delivered += 1
            except (discord.Forbidden, discord.HTTPException):
                not_delivered += 1

        result_embed = create_embed("Рассылка завершена",
            f"**Роль:** {role.mention}\n"
            f"**Доставлено:** {delivered}\n"
            f"**Не доставлено (ЛС закрыт):** {not_delivered}\n"
            f"**Всего участников:** {len(members_with_role)}",
            EMBED_GREEN
        )
        await interaction.followup.send(embed=result_embed)


async def setup(bot):
    await bot.add_cog(AllCommandsCog(bot))
