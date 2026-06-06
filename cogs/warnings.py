import discord
from discord import app_commands
from discord.ext import commands
from utils.database import fetch_one, fetch_all, execute_query
from utils.embeds import create_embed, create_success_embed, create_error_embed, json_to_list, list_to_json, EMBED_GREEN, EMBED_RED, EMBED_ORANGE

WATERMARK = "KILLOREZ HELPER"


class WarningsCog(commands.Cog, name="Warnings"):
    def __init__(self, bot):
        self.bot = bot

    warning = app_commands.Group(name="warning", description="Система штрафов")

    @warning.command(name="add", description="Выдать штраф участнику")
    @app_commands.describe(member="Участник", reason="Причина", warn_role="Роль штрафа")
    async def warning_add(self, interaction: discord.Interaction, member: discord.Member, reason: str = "", warn_role: discord.Role = None):
        # Check admin role
        settings = await fetch_one(
            "SELECT * FROM warning_settings WHERE guild_id = ?",
            (interaction.guild.id,)
        )
        if settings and settings['admin_role_id']:
            admin_role = interaction.guild.get_role(settings['admin_role_id'])
            if admin_role and admin_role not in interaction.user.roles:
                embed = create_error_embed("Ошибка", f"У вас нет роли {admin_role.mention} для выдачи штрафов!")
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

        warn_role_id = warn_role.id if warn_role else None
        await execute_query(
            "INSERT INTO warnings (guild_id, user_id, admin_id, reason, warn_role_id) VALUES (?, ?, ?, ?, ?)",
            (interaction.guild.id, member.id, interaction.user.id, reason, warn_role_id)
        )

        if warn_role:
            try:
                await member.add_roles(warn_role)
            except discord.Forbidden:
                pass

        desc = f"**Участник:** {member.mention}\n**Админ:** {interaction.user.mention}\n"
        if reason:
            desc += f"**Причина:** {reason}\n"
        if warn_role:
            desc += f"**Роль штрафа:** {warn_role.mention}\n"

        embed = create_embed("Штраф выдан", desc, EMBED_ORANGE)
        await interaction.response.send_message(embed=embed)

        # Log
        log_settings = await fetch_one(
            "SELECT * FROM guild_settings WHERE guild_id = ?",
            (interaction.guild.id,)
        )
        if log_settings and log_settings['log_channel_id']:
            log_channel = interaction.guild.get_channel(log_settings['log_channel_id'])
            if log_channel:
                log_embed = create_embed("Штраф выдан", desc, EMBED_ORANGE)
                await log_channel.send(embed=log_embed)

        # DM notification
        try:
            dm_embed = create_embed("Штраф", f"Вам был выдан штраф на сервере **{interaction.guild.name}**\n**Причина:** {reason or 'Не указана'}", EMBED_ORANGE)
            await member.send(embed=dm_embed)
        except discord.Forbidden:
            pass

    @warning.command(name="delete", description="Удалить штраф с участника")
    @app_commands.describe(member="Участник", warning_id="ID штрафа")
    async def warning_delete(self, interaction: discord.Interaction, member: discord.Member, warning_id: int = None):
        if warning_id:
            warn = await fetch_one(
                "SELECT * FROM warnings WHERE warning_id = ? AND guild_id = ?",
                (warning_id, interaction.guild.id)
            )
            if not warn:
                embed = create_error_embed("Ошибка", "Штраф с таким ID не найден!")
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            if warn['warn_role_id']:
                role = interaction.guild.get_role(warn['warn_role_id'])
                if role:
                    try:
                        await member.remove_roles(role)
                    except discord.Forbidden:
                        pass

            await execute_query("DELETE FROM warnings WHERE warning_id = ?", (warning_id,))
            embed = create_success_embed("Штраф удален", f"Штраф #{warning_id} удален с участника {member.mention}")
            await interaction.response.send_message(embed=embed)
        else:
            # Remove all warnings for user
            warns = await fetch_all(
                "SELECT * FROM warnings WHERE user_id = ? AND guild_id = ?",
                (member.id, interaction.guild.id)
            )
            for w in warns:
                if w['warn_role_id']:
                    role = interaction.guild.get_role(w['warn_role_id'])
                    if role:
                        try:
                            await member.remove_roles(role)
                        except discord.Forbidden:
                            pass

            await execute_query(
                "DELETE FROM warnings WHERE user_id = ? AND guild_id = ?",
                (member.id, interaction.guild.id)
            )
            embed = create_success_embed("Штрафы удалены", f"Все штрафы удалены с участника {member.mention}")
            await interaction.response.send_message(embed=embed)

    @warning.command(name="set", description="Выбрать роли штрафа")
    @app_commands.describe(roles="ID ролей через запятую")
    async def warning_set_roles(self, interaction: discord.Interaction, roles: str):
        role_ids = [int(r.strip()) for r in roles.split(",") if r.strip().isdigit()]
        settings = await fetch_one(
            "SELECT * FROM warning_settings WHERE guild_id = ?",
            (interaction.guild.id,)
        )
        if settings:
            await execute_query(
                "UPDATE warning_settings SET warn_roles = ? WHERE guild_id = ?",
                (list_to_json(role_ids), interaction.guild.id)
            )
        else:
            await execute_query(
                "INSERT INTO warning_settings (guild_id, warn_roles) VALUES (?, ?)",
                (interaction.guild.id, list_to_json(role_ids))
            )

        role_mentions = ", ".join([f"<@&{r}>" for r in role_ids])
        embed = create_success_embed("Роли штрафа обновлены", f"Роли: {role_mentions}")
        await interaction.response.send_message(embed=embed)

    @warning.command(name="admin", description="Выбрать роль админа для штрафов")
    @app_commands.describe(role="Роль админа")
    async def warning_set_admin(self, interaction: discord.Interaction, role: discord.Role):
        settings = await fetch_one(
            "SELECT * FROM warning_settings WHERE guild_id = ?",
            (interaction.guild.id,)
        )
        if settings:
            await execute_query(
                "UPDATE warning_settings SET admin_role_id = ? WHERE guild_id = ?",
                (role.id, interaction.guild.id)
            )
        else:
            await execute_query(
                "INSERT INTO warning_settings (guild_id, admin_role_id) VALUES (?, ?)",
                (interaction.guild.id, role.id)
            )

        embed = create_success_embed("Роль админа обновлена", f"Роль: {role.mention}")
        await interaction.response.send_message(embed=embed)

    @warning.command(name="list", description="Список всех оштрафованных")
    async def warning_list(self, interaction: discord.Interaction):
        warns = await fetch_all(
            "SELECT * FROM warnings WHERE guild_id = ?",
            (interaction.guild.id,)
        )
        if not warns:
            embed = create_embed("Список штрафов", "Нет оштрафованных участников", discord.Color.blue())
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        desc = ""
        for w in warns:
            user = self.bot.get_user(w['user_id'])
            admin = self.bot.get_user(w['admin_id'])
            name = user.mention if user else f"<@{w['user_id']}>"
            admin_name = admin.mention if admin else f"<@{w['admin_id']}>"
            desc += f"**#{w['warning_id']}** | {name} | Админ: {admin_name}"
            if w['reason']:
                desc += f" | {w['reason']}"
            if w['warn_role_id']:
                desc += f" | <@&{w['warn_role_id']}>"
            desc += "\n"

        embed = create_embed("Список штрафов", desc, EMBED_ORANGE)
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(WarningsCog(bot))
