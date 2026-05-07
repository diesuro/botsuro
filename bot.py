import os
import requests
import discord
from discord import app_commands
from discord.ext import commands
from aiohttp import web

API_BASE_URL = os.environ.get("API_BASE_URL", "https://bloxsuro-server.onrender.com").rstrip("/")
ADMIN_SECRET = os.environ.get("ADMIN_SECRET", "")
DISCORD_BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "")
PORT = int(os.environ.get("PORT", "10000"))

ALLOWED_USERS = {
    964974537156472884,
    398692582063996929,
}

BRAND_NAME = "BLOXSURO"
BRAND_COLOR = 0xFF2434
DARK_COLOR = 0x111116


def allowed(interaction: discord.Interaction) -> bool:
    return interaction.user.id in ALLOWED_USERS


def api_post(path: str, payload: dict):
    if not ADMIN_SECRET:
        return {"ok": False, "error": "ADMIN_SECRET is not configured."}

    data = dict(payload or {})
    data["secret"] = ADMIN_SECRET

    try:
        response = requests.post(f"{API_BASE_URL}{path}", json=data, timeout=18)
        try:
            body = response.json()
        except Exception:
            return {"ok": False, "error": f"Invalid API response. HTTP {response.status_code}"}

        if response.status_code >= 400 and not body.get("error"):
            body["error"] = f"HTTP {response.status_code}"

        return body
    except requests.RequestException as exc:
        return {"ok": False, "error": f"API unavailable: {exc}"}


def base_embed(title: str, description: str = "", color: int = BRAND_COLOR) -> discord.Embed:
    embed = discord.Embed(title=title, description=description, color=color)
    embed.set_footer(text="BLOXSURO License Control")
    return embed


def error_embed(message: str) -> discord.Embed:
    embed = base_embed("BLOXSURO ERROR", color=0xEF4444)
    embed.add_field(name="Reason", value=message or "Unknown error", inline=False)
    return embed


def access_embed() -> discord.Embed:
    embed = base_embed("BLOXSURO ACCESS", color=0xEF4444)
    embed.add_field(name="Status", value="You are not authorized to use this command.", inline=False)
    return embed


class KeyCopyView(discord.ui.View):
    def __init__(self, key: str):
        super().__init__(timeout=180)
        self.key = key

    @discord.ui.button(label="Copy Key", style=discord.ButtonStyle.danger)
    async def copy_key(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            f"Copy this key:\n```txt\n{self.key}\n```",
            ephemeral=True,
        )

    @discord.ui.button(label="Key Details", style=discord.ButtonStyle.secondary)
    async def key_details(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = api_post("/admin/key-info", {"key": self.key})
        if not data.get("ok"):
            await interaction.response.send_message(embed=error_embed(data.get("error", "Unknown error")), ephemeral=True)
            return
        await interaction.response.send_message(embed=key_info_embed(data), view=KeyCopyView(self.key), ephemeral=True)


def key_info_embed(data: dict) -> discord.Embed:
    key = data.get("key", "N/A")
    embed = base_embed("BLOXSURO LICENSE")
    embed.add_field(name="Key", value=f"```txt\n{key}\n```", inline=False)
    embed.add_field(name="Owner", value=data.get("owner") or "Not linked", inline=True)
    embed.add_field(name="Status", value=data.get("status", "Unknown"), inline=True)
    embed.add_field(name="Remaining", value=data.get("remaining", "Unknown"), inline=True)
    embed.add_field(name="HWID", value=f"```txt\n{data.get('hwid') or 'Not bound'}\n```", inline=False)
    embed.add_field(name="Expires", value=data.get("expires", "Unknown"), inline=False)
    return embed


def generated_embed(data: dict) -> discord.Embed:
    key = data.get("key", "N/A")
    embed = base_embed("BLOXSURO KEY GENERATED")
    embed.add_field(name="Key", value=f"```txt\n{key}\n```", inline=False)
    embed.add_field(name="Duration", value=data.get("duration", "Unknown"), inline=True)
    embed.add_field(name="Owner", value=data.get("owner") or "Not linked", inline=True)
    embed.add_field(name="Expires", value=data.get("expires", "Unknown"), inline=False)
    return embed


def action_embed(title: str, key: str, result: str) -> discord.Embed:
    embed = base_embed(title)
    embed.add_field(name="Key", value=f"```txt\n{key}\n```", inline=False)
    embed.add_field(name="Result", value=result, inline=False)
    return embed


async def no_access(interaction: discord.Interaction):
    await interaction.response.send_message(embed=access_embed(), ephemeral=True)


intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        print(f"BLOXSURO bot online as {bot.user}. Synced {len(synced)} commands.", flush=True)
    except Exception as exc:
        print(f"Command sync failed: {exc}", flush=True)


@bot.tree.command(name="keygen", description="Generate a BLOXSURO license key.")
@app_commands.describe(duration="Duration: 1m, 1h, 1d, 7d, 30d", user="Optional user/name to link to this key")
async def keygen(interaction: discord.Interaction, duration: str = "30d", user: str = ""):
    if not allowed(interaction):
        await no_access(interaction)
        return

    await interaction.response.defer(ephemeral=True)

    data = api_post("/admin/create", {"duration": duration, "owner": user})
    if not data.get("ok"):
        await interaction.followup.send(embed=error_embed(data.get("error", "Unknown error")), ephemeral=True)
        return

    key = data.get("key", "")
    await interaction.followup.send(embed=generated_embed(data), view=KeyCopyView(key), ephemeral=True)


@bot.tree.command(name="link", description="Link an existing key to a user/name.")
@app_commands.describe(key="License key", user="User/name to link")
async def link(interaction: discord.Interaction, key: str, user: str):
    if not allowed(interaction):
        await no_access(interaction)
        return

    await interaction.response.defer(ephemeral=True)

    data = api_post("/admin/link-owner", {"key": key, "owner": user})
    if not data.get("ok"):
        await interaction.followup.send(embed=error_embed(data.get("error", "Unknown error")), ephemeral=True)
        return

    embed = action_embed("BLOXSURO KEY LINKED", key, f"Linked to: {user}")
    await interaction.followup.send(embed=embed, view=KeyCopyView(key), ephemeral=True)


@bot.tree.command(name="search", description="Search keys linked to a user/name.")
@app_commands.describe(user="User/name to search, example: bloxkey281381283")
async def search(interaction: discord.Interaction, user: str):
    if not allowed(interaction):
        await no_access(interaction)
        return

    await interaction.response.defer(ephemeral=True)

    data = api_post("/admin/search-owner", {"owner": user})
    if not data.get("ok"):
        await interaction.followup.send(embed=error_embed(data.get("error", "Unknown error")), ephemeral=True)
        return

    keys = data.get("keys", [])
    if not keys:
        embed = base_embed("BLOXSURO SEARCH")
        embed.add_field(name="User", value=user, inline=False)
        embed.add_field(name="Result", value="No keys found.", inline=False)
        await interaction.followup.send(embed=embed, ephemeral=True)
        return

    embed = base_embed("BLOXSURO SEARCH RESULTS")
    embed.add_field(name="User", value=user, inline=False)

    for index, item in enumerate(keys[:10], start=1):
        embed.add_field(
            name=f"Result {index}",
            value=(
                f"Key: `{item.get('key')}`\n"
                f"Status: `{item.get('status', 'Unknown')}`\n"
                f"Remaining: `{item.get('remaining', 'Unknown')}`\n"
                f"HWID: `{item.get('hwid') or 'Not bound'}`"
            ),
            inline=False,
        )

    first_key = keys[0].get("key", "")
    view = KeyCopyView(first_key) if first_key else None
    await interaction.followup.send(embed=embed, view=view, ephemeral=True)


@bot.tree.command(name="keyinfo", description="Show key status, remaining time, owner and HWID.")
@app_commands.describe(key="License key")
async def keyinfo(interaction: discord.Interaction, key: str):
    if not allowed(interaction):
        await no_access(interaction)
        return

    await interaction.response.defer(ephemeral=True)

    data = api_post("/admin/key-info", {"key": key})
    if not data.get("ok"):
        await interaction.followup.send(embed=error_embed(data.get("error", "Unknown error")), ephemeral=True)
        return

    await interaction.followup.send(embed=key_info_embed(data), view=KeyCopyView(key), ephemeral=True)


@bot.tree.command(name="timeleft", description="Check remaining time for a key.")
@app_commands.describe(key="License key")
async def timeleft(interaction: discord.Interaction, key: str):
    if not allowed(interaction):
        await no_access(interaction)
        return

    await interaction.response.defer(ephemeral=True)

    data = api_post("/admin/key-info", {"key": key})
    if not data.get("ok"):
        await interaction.followup.send(embed=error_embed(data.get("error", "Unknown error")), ephemeral=True)
        return

    embed = base_embed("BLOXSURO TIME LEFT")
    embed.add_field(name="Key", value=f"```txt\n{data.get('key')}\n```", inline=False)
    embed.add_field(name="Remaining", value=data.get("remaining", "Unknown"), inline=True)
    embed.add_field(name="Status", value=data.get("status", "Unknown"), inline=True)
    embed.add_field(name="Owner", value=data.get("owner") or "Not linked", inline=False)

    await interaction.followup.send(embed=embed, view=KeyCopyView(key), ephemeral=True)


@bot.tree.command(name="reset_hwid", description="Reset HWID from a key.")
@app_commands.describe(key="License key")
async def reset_hwid(interaction: discord.Interaction, key: str):
    if not allowed(interaction):
        await no_access(interaction)
        return

    await interaction.response.defer(ephemeral=True)

    data = api_post("/admin/action", {"action": "reset_hwid", "keys": [key]})
    if not data.get("ok"):
        await interaction.followup.send(embed=error_embed(data.get("error", "Unknown error")), ephemeral=True)
        return

    await interaction.followup.send(embed=action_embed("BLOXSURO HWID RESET", key, "HWID reset completed."), view=KeyCopyView(key), ephemeral=True)


@bot.tree.command(name="disable", description="Disable a key.")
@app_commands.describe(key="License key")
async def disable(interaction: discord.Interaction, key: str):
    if not allowed(interaction):
        await no_access(interaction)
        return

    await interaction.response.defer(ephemeral=True)

    data = api_post("/admin/action", {"action": "disable", "keys": [key]})
    if not data.get("ok"):
        await interaction.followup.send(embed=error_embed(data.get("error", "Unknown error")), ephemeral=True)
        return

    await interaction.followup.send(embed=action_embed("BLOXSURO KEY DISABLED", key, "Key disabled."), view=KeyCopyView(key), ephemeral=True)


@bot.tree.command(name="enable", description="Re-enable a disabled key.")
@app_commands.describe(key="License key")
async def enable(interaction: discord.Interaction, key: str):
    if not allowed(interaction):
        await no_access(interaction)
        return

    await interaction.response.defer(ephemeral=True)

    data = api_post("/admin/action", {"action": "enable", "keys": [key]})
    if not data.get("ok"):
        await interaction.followup.send(embed=error_embed(data.get("error", "Unknown error")), ephemeral=True)
        return

    await interaction.followup.send(embed=action_embed("BLOXSURO KEY ENABLED", key, "Key enabled."), view=KeyCopyView(key), ephemeral=True)


@bot.tree.command(name="delete", description="Delete a key permanently.")
@app_commands.describe(key="License key")
async def delete(interaction: discord.Interaction, key: str):
    if not allowed(interaction):
        await no_access(interaction)
        return

    await interaction.response.defer(ephemeral=True)

    data = api_post("/admin/action", {"action": "delete", "keys": [key]})
    if not data.get("ok"):
        await interaction.followup.send(embed=error_embed(data.get("error", "Unknown error")), ephemeral=True)
        return

    await interaction.followup.send(embed=action_embed("BLOXSURO KEY DELETED", key, "Key permanently deleted."), ephemeral=True)


async def health(request):
    return web.json_response({"online": True, "service": "BLOXSURO Discord Bot"})


async def start_health_server():
    app = web.Application()
    app.router.add_get("/", health)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    print(f"Health server running on port {PORT}", flush=True)


async def main():
    if not DISCORD_BOT_TOKEN:
        raise RuntimeError("DISCORD_BOT_TOKEN is not configured.")
    await start_health_server()
    await bot.start(DISCORD_BOT_TOKEN)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
