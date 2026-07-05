"""
Transcript generator — Linuxx Ticketing
Dev: wmikon
"""
from __future__ import annotations
import discord
import io
import datetime


async def generate_transcript(channel: discord.TextChannel) -> discord.File:
    messages = []
    async for msg in channel.history(limit=None, oldest_first=True):
        messages.append(msg)

    html = _build_html(channel, messages)
    buf  = io.BytesIO(html.encode("utf-8"))
    return discord.File(buf, filename=f"transcript-{channel.name}.html")


def _build_html(channel: discord.TextChannel, messages: list[discord.Message]) -> str:
    rows = ""
    for msg in messages:
        if msg.author.bot and not msg.embeds and not msg.content:
            continue
        ts      = msg.created_at.strftime("%Y-%m-%d %H:%M:%S UTC")
        avatar  = msg.author.display_avatar.url
        content = discord.utils.escape_markdown(msg.content) if msg.content else ""
        attachments = ""
        for a in msg.attachments:
            attachments += f'<a href="{a.url}" target="_blank">[Attachment: {a.filename}]</a> '
        embed_parts = []
        for e in msg.embeds:
            parts = []
            if e.title:
                parts.append(f"<strong>{discord.utils.escape_markdown(e.title)}</strong>")
            if e.description:
                parts.append(discord.utils.escape_markdown(e.description))
            embed_parts.append(
                f'<span class="embed-note">[Embed: {" — ".join(parts) if parts else "no content"}]</span>'
            )
        embed_note = " ".join(embed_parts) + (" " if embed_parts else "") if not msg.content else ""

        rows += f"""
        <div class="message">
          <img class="avatar" src="{avatar}" alt=""/>
          <div class="body">
            <span class="author">{discord.utils.escape_mentions(msg.author.display_name)}</span>
            <span class="ts">{ts}</span>
            <p>{embed_note}{content}{attachments}</p>
          </div>
        </div>"""

    generated = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<title>Transcript • #{channel.name}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #1e1f22; color: #dbdee1; font-family: 'Segoe UI', sans-serif; padding: 32px; }}
  header {{ margin-bottom: 24px; border-bottom: 1px solid #3f4147; padding-bottom: 16px; }}
  header h1 {{ color: #fff; font-size: 1.4rem; }}
  header p {{ color: #888; font-size: 0.85rem; margin-top: 4px; }}
  .brand {{ color: #5865f2; font-weight: 600; }}
  .message {{ display: flex; gap: 14px; margin-bottom: 20px; }}
  .avatar {{ width: 40px; height: 40px; border-radius: 50%; flex-shrink: 0; }}
  .body {{ flex: 1; }}
  .author {{ font-weight: 700; color: #fff; margin-right: 8px; }}
  .ts {{ font-size: 0.72rem; color: #72767d; }}
  p {{ margin-top: 4px; line-height: 1.5; word-break: break-word; }}
  .embed-note {{ color: #5865f2; font-style: italic; }}
  a {{ color: #00b0f4; }}
  footer {{ margin-top: 32px; border-top: 1px solid #3f4147; padding-top: 12px;
            font-size: 0.78rem; color: #555; }}
</style>
</head>
<body>
<header>
  <h1>Transcript — <span style="color:#5865f2">#{channel.name}</span></h1>
  <p>Generated on {generated} &nbsp;•&nbsp; <span class="brand">Linuxx Ticketing</span> &nbsp;•&nbsp; dev: wmikon</p>
</header>
{rows}
<footer>Linuxx Ticketing System • Developed by wmikon • {generated}</footer>
</body>
</html>"""
