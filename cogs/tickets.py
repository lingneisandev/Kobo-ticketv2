from __future__ import annotations
import asyncio
import datetime
import discord
from discord import app_commands
from discord.ext import commands

from utils.store import (
    get_config, set_config, get_ticket, get_user_open_count,
    next_ticket_number, create_ticket, update_ticket, delete_ticket,
)
from utils.transcript import generate_transcript

# ── Custom Emojis (all IDs from source) ───────────────────────
E_SUCCESS  = "<:success:1518137986095644703>"   # tick
E_CROSS    = "<:wickk:1518137821355966494>"     # cross
E_INFO     = "<:Warning:1517892973482868960>"   # info
E_WARN     = "<:warn:1518063335923257386>"      # warn
E_TICKET   = "<:ticket:1513730006910500977>"    # ticket
E_BUG      = "<:TbotBug:1518063885855358996>"   # bug
E_CLAIM    = "<:claim:1518064508948447242>"     # claim
E_VIEW     = "<:view:1518064705854373969>"      # view/configure
E_REOPEN   = "<:ticket_reopen:1518064251405733898>"  # reopen
E_QUESTION = "<:question_mark:1518064034862076007>"  # question
E_DELETE   = "<:delete:1518064106723217418>"    # delete/trash
E_SETUP    = "<:setup:1518064880769568828>"     # setup/gear
E_CUSTOM   = "<:customize:1518065679041957989>" # customise/pencil

# ── Colors ─────────────────────────────────────────────────────
# All container accent bars + backgrounds are pure black, regardless of
# message type (success/error/info/warn all look the same now).
EMBED_COLOR   = 0x000000
SUCCESS_COLOR = 0x000000
ERROR_COLOR   = 0x000000
WARN_COLOR    = 0x000000
INFO_COLOR    = 0x000000

BUTTON_COLOR_MAP = {
    "Green":  discord.ButtonStyle.success,
    "Blue":   discord.ButtonStyle.primary,
    "Grey":   discord.ButtonStyle.secondary,
    "Yellow": discord.ButtonStyle.secondary,
    "Red":    discord.ButtonStyle.danger,
}

# Colour options for the optional Panel Text button — mirrors the map in
# cogs/setup.py. Discord has no native Black/White/Yellow button style,
# so those render as the standard grey button.
PANEL_BUTTON_COLOR_MAP = {
    "Grey":   discord.ButtonStyle.secondary,
    "Yellow": discord.ButtonStyle.secondary,
    "Blue":   discord.ButtonStyle.primary,
    "Red":    discord.ButtonStyle.danger,
    "Black":  discord.ButtonStyle.secondary,
    "White":  discord.ButtonStyle.secondary,
}

DEFAULT_CATEGORIES = ["General Support", "Giveaway Claim", "Bug Report", "Other"]

CATEGORY_EMOJIS = {
    "General Support": E_QUESTION,
    "Giveaway Claim":  E_TICKET,
    "Bug Report":      E_BUG,
    "Other":           E_CUSTOM,
}

CATEGORY_DESCRIPTIONS = {
    "General Support": "Get help with general questions",
    "Giveaway Claim":  "Claim your giveaway prize",
    "Bug Report":      "Report a bug or issue",
    "Other":           "Something not listed above",
}

BRAND      = "Linuxx Ticketing"
BRAND_FULL = "Linuxx Ticketing • Powered by wmikon"


# ── Helpers ────────────────────────────────────────────────────

def ticket_num(n: int) -> str:
    return f"#{n:04d}"

def _style(color: str) -> discord.ButtonStyle:
    return BUTTON_COLOR_MAP.get(color, discord.ButtonStyle.primary)


class MessageLayout(discord.ui.LayoutView):
    """Generic single-container layout for simple text replies."""
    def __init__(self, text: str, color: int, *, extra_rows: list[discord.ui.ActionRow] | None = None):
        super().__init__()
        container = discord.ui.Container(accent_color=color)
        container.add_item(discord.ui.TextDisplay(text))
        self.add_item(container)
        for row in (extra_rows or []):
            self.add_item(row)


def _err(msg: str) -> MessageLayout:
    return MessageLayout(f"{E_CROSS} {msg}", ERROR_COLOR)

def _warn_embed(msg: str) -> MessageLayout:
    return MessageLayout(f"{E_WARN} {msg}", WARN_COLOR)

def _ok(msg: str) -> MessageLayout:
    return MessageLayout(f"{E_SUCCESS} {msg}", SUCCESS_COLOR)

def _ok_raw(text: str) -> MessageLayout:
    """Like _ok but takes pre-formatted text (e.g. multi-line, with its own heading)."""
    return MessageLayout(text, SUCCESS_COLOR)


class LogLayout(discord.ui.LayoutView):
    """Replaces the old log embed — a container with a heading, field-style
    lines, and a timestamp footer line (Components V2 has no embed footer)."""
    def __init__(self, title: str, color: int):
        super().__init__()
        self._container = discord.ui.Container(accent_color=color)
        self._lines: list[str] = [f"## {title}"]
        self._thumbnail: discord.ui.Section | None = None
        self._rendered = False

    def add_field(self, name: str, value: str, inline: bool = False):
        self._lines.append(f"**{name}:** {value}")

    def set_footer(self, text: str):
        """Compatibility shim — old code used embed footers for extra detail
        like a channel ID. Components V2 containers have no footer, so we
        fold this onto its own line instead of dropping it."""
        self._lines.append(f"-# {text}")

    def set_thumbnail(self, url: str):
        self._thumb_url = url

    def _render(self):
        if self._rendered:
            return
        body = "\n".join(self._lines)
        ts = datetime.datetime.now(datetime.timezone.utc).strftime("%d %b %Y %H:%M UTC")
        body += f"\n\n*{ts}*"
        thumb_url = getattr(self, "_thumb_url", None)
        if thumb_url:
            section = discord.ui.Section(
                discord.ui.TextDisplay(body),
                accessory=discord.ui.Thumbnail(thumb_url),
            )
            self._container.add_item(section)
        else:
            self._container.add_item(discord.ui.TextDisplay(body))
        self.add_item(self._container)
        self._rendered = True

    def to_send_kwargs(self) -> dict:
        self._render()
        return {"view": self}


def _log_embed(title: str, color: int) -> LogLayout:
    return LogLayout(title, color)

async def send_log(guild: discord.Guild, config: dict, log: LogLayout, file: discord.File | None = None):
    log_id = config.get("log_channel_id")
    if not log_id:
        return
    ch = guild.get_channel(int(log_id))
    if not ch:
        return
    try:
        # Components V2 LayoutView cannot carry file= in the same send() call.
        # Send the CV2 log layout first, then send the transcript file as a
        # separate CV2 container (black accent) followed by the raw file.
        await ch.send(**log.to_send_kwargs())
        if file:
            transcript_note = LogLayout("Ticket Transcript", 0x000000)
            transcript_note.add_field(
                name="Transcript",
                value="The HTML transcript for this ticket is attached below.",
                inline=False,
            )
            await ch.send(**transcript_note.to_send_kwargs())
            await ch.send(file=file)
    except Exception:
        pass


def _rows_from_view(view: discord.ui.View) -> list[discord.ui.ActionRow]:
    """Folds a legacy discord.ui.View's buttons/select into ActionRows so
    they can be attached to a Components V2 LayoutView."""
    rows: list[discord.ui.ActionRow] = []
    row = discord.ui.ActionRow()
    count = 0
    for item in view.children:
        if isinstance(item, discord.ui.Select) or count >= 5:
            if count:
                rows.append(row)
            row = discord.ui.ActionRow()
            count = 0
        row.add_item(item)
        count += 1
        if isinstance(item, discord.ui.Select):
            rows.append(row)
            row = discord.ui.ActionRow()
            count = 0
    if count:
        rows.append(row)
    return rows


class PanelExtraButton(discord.ui.Button):
    """The optional 'Panel Button' shown under the panel text when it has
    no URL (i.e. it shows a popup instead of linking out). Looks up its
    text from the guild's saved config at click-time rather than capturing
    it in a closure, so it keeps working after a bot restart."""

    def __init__(self, label: str = "", style: discord.ButtonStyle = discord.ButtonStyle.secondary, emoji: str = ""):
        super().__init__(
            label=label or "More Info",
            style=style,
            emoji=emoji or None,
            custom_id="panel:extra_btn",
        )

    async def callback(self, interaction: discord.Interaction):
        config = get_config(interaction.guild.id) or {}
        text = config.get("panel_button_text") or "No additional information set."
        await interaction.response.send_message(
            view=MessageLayout(text, EMBED_COLOR), ephemeral=True
        )


class PanelExtraButtonRegistration(discord.ui.LayoutView):
    """Empty-shell layout used only to re-register PanelExtraButton's
    custom_id for persistence on bot restart — never actually sent."""
    def __init__(self):
        super().__init__(timeout=None)
        row = discord.ui.ActionRow()
        row.add_item(PanelExtraButton())
        self.add_item(row)


def build_panel_layout(
    *,
    title: str,
    description: str,
    color: int,
    author_name: str = "",
    author_icon_url: str = "",
    thumbnail_url: str = "",
    image_url: str = "",
    action_view: discord.ui.View,
    panel_button_label: str = "",
    panel_button_url: str = "",
    panel_button_text: str = "",
    panel_button_style: discord.ButtonStyle = discord.ButtonStyle.secondary,
    panel_button_emoji: str = "",
) -> discord.ui.LayoutView:
    """Builds the main ticket panel (button panel or dropdown panel) as a
    Components V2 layout, replacing the old embed-based panel builder.
    `action_view` supplies the buttons/select (TicketPanelView or
    TicketSelectPanel) which get folded into this layout's action rows.

    `panel_button_*` describes an entirely optional extra button shown
    right under the panel's main text (e.g. a "Rules" link or a "FAQ"
    popup), separate from the ticket-opening controls in `action_view`.
    If `panel_button_label` is empty, no button is added at all.
    - If `panel_button_url` is set, it's a link button to that URL.
    - Otherwise, if `panel_button_text` is set, clicking shows that text
      as an ephemeral popup.
    """

    class PanelLayout(discord.ui.LayoutView):
        def __init__(self):
            super().__init__(timeout=None)
            container = discord.ui.Container(accent_color=color)

            heading = f"## {title}" if title else ""
            body_text = "\n".join(t for t in (heading, description) if t)

            if author_name:
                section = discord.ui.Section(
                    discord.ui.TextDisplay(body_text or "​"),
                    accessory=discord.ui.Thumbnail(author_icon_url) if author_icon_url else discord.ui.Thumbnail("https://cdn.discordapp.com/embed/avatars/0.png"),
                )
                container.add_item(section)
            elif thumbnail_url:
                section = discord.ui.Section(
                    discord.ui.TextDisplay(body_text or "​"),
                    accessory=discord.ui.Thumbnail(thumbnail_url),
                )
                container.add_item(section)
            else:
                container.add_item(discord.ui.TextDisplay(body_text))

            # Entirely optional extra button under the panel text — only
            # appears at all if the admin configured a label for it.
            if panel_button_label:
                btn_row = discord.ui.ActionRow()
                if panel_button_url:
                    btn_row.add_item(discord.ui.Button(
                        label=panel_button_label,
                        style=discord.ButtonStyle.link,
                        url=panel_button_url,
                        emoji=panel_button_emoji or None,
                    ))
                else:
                    btn_row.add_item(PanelExtraButton(
                        label=panel_button_label,
                        style=panel_button_style,
                        emoji=panel_button_emoji,
                    ))
                container.add_item(btn_row)

            if image_url:
                container.add_item(discord.ui.Separator())
                container.add_item(discord.ui.MediaGallery(discord.MediaGalleryItem(image_url)))

            # Fold the action view's buttons/select into rows inside the container
            for row in _rows_from_view(action_view):
                container.add_item(row)

            self.add_item(container)

    return PanelLayout()


# ── Multi-Step Form Engine ─────────────────────────────────────

class StepModal(discord.ui.Modal):
    def __init__(self, title: str, fields: list[dict], category: str,
                 step_num: int, total: int, collected: dict, on_done):
        super().__init__(title=f"{category} — Step {step_num}/{total}" if total > 1 else title)
        self.category  = category
        self.step_num  = step_num
        self.total     = total
        self.collected = collected
        self.on_done   = on_done
        self._inputs   = []

        for f in fields:
            inp = discord.ui.TextInput(
                label=f["label"][:45],
                placeholder=f.get("placeholder", "")[:100],
                required=f.get("required", True),
                style=discord.TextStyle.paragraph if f.get("long") else discord.TextStyle.short,
                max_length=f.get("max_length", 500),
            )
            self.add_item(inp)
            self._inputs.append(inp)

    async def on_submit(self, interaction: discord.Interaction):
        for inp in self._inputs:
            self.collected[inp.label] = inp.value
        await self.on_done(interaction, self.collected)


def _get_form_steps(config: dict, category: str) -> list[dict]:
    forms = config.get("form_steps", {})
    cat_steps = forms.get(category)
    if not cat_steps:
        return [{"title": "Ticket Details", "fields": [
            {"label": "Reason", "placeholder": "Describe your issue or request…",
             "required": False, "long": True, "max_length": 1000}
        ]}]
    return cat_steps


async def start_form(interaction: discord.Interaction, category: str):
    config = get_config(interaction.guild.id)
    if not config:
        return await interaction.response.send_message(
            view=_err("Ticket system not configured. Ask an admin to run `/setup`."),
            ephemeral=True,
        )

    steps     = _get_form_steps(config, category)
    collected: dict = {}

    async def after_step(inter: discord.Interaction, answers: dict, step_index: int):
        if step_index + 1 < len(steps):
            nxt = steps[step_index + 1]
            modal = StepModal(
                nxt["title"], nxt["fields"], category,
                step_index + 2, len(steps), answers,
                lambda i, a: after_step(i, a, step_index + 1),
            )
            await inter.response.send_modal(modal)
        else:
            reason = "\n".join(f"**{k}:** {v}" for k, v in answers.items() if v)
            await open_ticket(inter, category, reason or "No reason provided.", answers)

    first = steps[0]
    modal = StepModal(
        first["title"], first["fields"], category,
        1, len(steps), collected,
        lambda i, a: after_step(i, a, 0),
    )
    await interaction.response.send_modal(modal)


# ── Ticket Control Buttons ─────────────────────────────────────

class TicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Claim", style=discord.ButtonStyle.primary,
                       custom_id="ticket:claim", emoji=E_CLAIM)
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        ticket = get_ticket(interaction.channel.id)
        if not ticket:
            return await interaction.response.send_message(view=_err("Ticket data not found."), ephemeral=True)

        config       = get_config(interaction.guild.id)
        support_role = interaction.guild.get_role(config["support_role_id"]) if config else None

        if support_role and support_role not in interaction.user.roles:
            return await interaction.response.send_message(
                view=_err("Only support staff can claim tickets."), ephemeral=True
            )

        if ticket.get("claimed_by"):
            claimer = interaction.guild.get_member(int(ticket["claimed_by"]))
            name    = claimer.display_name if claimer else "Unknown"
            return await interaction.response.send_message(
                view=_warn_embed(f"Already claimed by **{name}**."), ephemeral=True
            )

        update_ticket(interaction.channel.id, {"claimed_by": str(interaction.user.id)})

        await interaction.response.send_message(
            view=_ok(f"{E_CLAIM} **{interaction.user.display_name}** has claimed this ticket.")
        )

        try:
            if not interaction.channel.name.startswith("claimed-"):
                await interaction.channel.edit(name=f"claimed-{interaction.channel.name}")
        except Exception:
            pass

        if config:
            log = _log_embed(f"{E_CLAIM} Ticket Claimed", INFO_COLOR)
            log.add_field(name="Claimed By", value=f"{interaction.user.mention} (`{interaction.user.id}`)", inline=False)
            log.add_field(name="Channel",    value=interaction.channel.mention, inline=True)
            log.add_field(name="Ticket",     value=ticket_num(ticket.get("number", 0)), inline=True)
            await send_log(interaction.guild, config, log)

    @discord.ui.button(label="Close", style=discord.ButtonStyle.danger,
                       custom_id="ticket:close", emoji=E_DELETE)
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await close_ticket(interaction)


# ── Closed Ticket Buttons ──────────────────────────────────────

class ClosedTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Delete", style=discord.ButtonStyle.danger,
                       custom_id="ticket:delete", emoji=E_DELETE)
    async def delete_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        config       = get_config(interaction.guild.id)
        support_role = interaction.guild.get_role(config["support_role_id"]) if config else None

        if support_role and support_role not in interaction.user.roles:
            return await interaction.response.send_message(
                view=_err("Only support staff can delete tickets."), ephemeral=True
            )

        ticket = get_ticket(interaction.channel.id)
        await interaction.response.send_message(view=_warn_embed("Deleting ticket in **3 seconds…**"))
        transcript_file = await generate_transcript(interaction.channel)

        if config and ticket:
            number    = ticket.get("number", 0)
            author_id = ticket.get("author_id")
            author    = interaction.guild.get_member(int(author_id)) if author_id else None
            category  = ticket.get("category", "General Support")

            log = _log_embed(f"{E_DELETE} Ticket Deleted", ERROR_COLOR)
            log.add_field(name="Author",     value=f"{author.mention if author else 'Unknown'} (`{author_id}`)", inline=False)
            log.add_field(name="Deleted By", value=f"{interaction.user.mention} (`{interaction.user.id}`)", inline=False)
            log.add_field(name="Category",   value=category, inline=True)
            log.add_field(name="Ticket",     value=ticket_num(number), inline=True)
            log.set_footer(f"ID: {interaction.channel.id}")
            await send_log(interaction.guild, config, log, transcript_file)

            if author:
                try:
                    t2 = await generate_transcript(interaction.channel)
                    # Send a CV2 layout message first (black accent), then the
                    # transcript file as a separate message — attaching both in
                    # one call causes a glitch with Components V2.
                    dm_msg = LogLayout(f"Ticket Transcript — {ticket_num(number)}", 0x000000)
                    dm_msg.add_field(
                        name="Server",
                        value=interaction.guild.name,
                        inline=True,
                    )
                    dm_msg.add_field(
                        name="Category",
                        value=category,
                        inline=True,
                    )
                    dm_msg.add_field(
                        name="Status",
                        value=(
                            f"Your **{category}** ticket {ticket_num(number)} has been closed. "
                            f"The transcript is attached below."
                        ),
                        inline=False,
                    )
                    dm_msg.set_footer("Linuxx Ticketing • Powered by wmikon")
                    await author.send(**dm_msg.to_send_kwargs())
                    await author.send(file=t2)
                except Exception:
                    pass

        delete_ticket(interaction.channel.id)
        await asyncio.sleep(3)
        try:
            await interaction.channel.delete(reason=f"Ticket deleted by {interaction.user}")
        except Exception:
            pass

    @discord.ui.button(label="Reopen", style=discord.ButtonStyle.success,
                       custom_id="ticket:reopen", emoji=E_REOPEN)
    async def reopen_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        config       = get_config(interaction.guild.id)
        support_role = interaction.guild.get_role(config["support_role_id"]) if config else None

        if support_role and support_role not in interaction.user.roles:
            return await interaction.response.send_message(
                view=_err("Only support staff can reopen tickets."), ephemeral=True
            )

        ticket = get_ticket(interaction.channel.id)
        if not ticket:
            return await interaction.response.send_message(view=_err("Ticket data not found."), ephemeral=True)

        author = interaction.guild.get_member(int(ticket["author_id"]))
        if author:
            await interaction.channel.set_permissions(author, read_messages=True, send_messages=True)

        try:
            name = interaction.channel.name.removeprefix("claimed-")
            await interaction.channel.edit(name=name)
        except Exception:
            pass

        update_ticket(interaction.channel.id, {"status": "open", "claimed_by": None})

        await interaction.response.send_message(
            view=_ok(f"{E_REOPEN} Ticket reopened by {interaction.user.mention}.")
        )
        await interaction.message.edit(view=TicketControlView())

        if config:
            log = _log_embed(f"{E_REOPEN} Ticket Reopened", SUCCESS_COLOR)
            log.add_field(name="Reopened By", value=f"{interaction.user.mention} (`{interaction.user.id}`)", inline=False)
            log.add_field(name="Channel",     value=interaction.channel.mention, inline=True)
            log.add_field(name="Ticket",      value=ticket_num(ticket.get("number", 0)), inline=True)
            await send_log(interaction.guild, config, log)


# ── Close Logic ────────────────────────────────────────────────

async def close_ticket(interaction: discord.Interaction):
    ticket = get_ticket(interaction.channel.id)
    if not ticket:
        return await interaction.response.send_message(
            view=_err("This is not a ticket channel."), ephemeral=True
        )

    config = get_config(interaction.guild.id)
    author = interaction.guild.get_member(int(ticket["author_id"]))
    if author:
        await interaction.channel.set_permissions(author, read_messages=False)

    update_ticket(interaction.channel.id, {"status": "closed"})

    close_text = (
        f"## {E_DELETE} Ticket Closed\n"
        f"Closed by {interaction.user.mention}.\n\n"
        f"> {E_DELETE} **Delete** — removes this channel & DMs transcript to user\n"
        f"> {E_REOPEN} **Reopen** — restores access and reopens the ticket"
    )
    await interaction.response.send_message(
        view=MessageLayout(close_text, ERROR_COLOR, extra_rows=_rows_from_view(ClosedTicketView()))
    )

    if config:
        number = ticket.get("number", 0)
        log = _log_embed(f"{E_DELETE} Ticket Closed", WARN_COLOR)
        log.add_field(name="Author",    value=f"{author.mention if author else 'Unknown'} (`{ticket['author_id']}`)", inline=False)
        log.add_field(name="Closed By", value=f"{interaction.user.mention} (`{interaction.user.id}`)", inline=False)
        log.add_field(name="Ticket",    value=ticket_num(number), inline=True)
        log.add_field(name="Channel",   value=interaction.channel.mention, inline=True)
        log.set_footer(f"ID: {interaction.channel.id}")
        await send_log(interaction.guild, config, log)


# ── Open Ticket ────────────────────────────────────────────────

async def open_ticket(interaction: discord.Interaction, category: str,
                      reason: str, form_data: dict | None = None):
    config = get_config(interaction.guild.id)
    if not config:
        return await interaction.response.send_message(
            view=_err("Ticket system not configured."), ephemeral=True
        )

    limit      = config.get("ticket_limit", 3)
    open_count = get_user_open_count(interaction.guild.id, interaction.user.id)
    if open_count >= limit:
        return await interaction.response.send_message(
            view=_warn_embed(
                f"You have **{open_count}/{limit}** open tickets. "
                f"Please close one before opening another."
            ),
            ephemeral=True,
        )

    cat_ch       = interaction.guild.get_channel(int(config["ticket_category_id"]))
    support_role = interaction.guild.get_role(int(config["support_role_id"]))
    number       = next_ticket_number(interaction.guild.id)
    safe_name    = "".join(c for c in interaction.user.name.lower() if c.isalnum())[:12]
    channel_name = f"ticket-{number:04d}-{safe_name}"

    overwrites = {
        interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
        interaction.user:               discord.PermissionOverwrite(
                                            read_messages=True, send_messages=True, attach_files=True),
        interaction.guild.me:           discord.PermissionOverwrite(
                                            read_messages=True, send_messages=True, manage_channels=True),
    }
    if support_role:
        overwrites[support_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

    channel = await interaction.guild.create_text_channel(
        name=channel_name,
        category=cat_ch,
        overwrites=overwrites,
        topic=f"{category} • {interaction.user} • Ticket {ticket_num(number)}",
    )

    create_ticket(channel.id, {
        "guild_id":   str(interaction.guild.id),
        "author_id":  str(interaction.user.id),
        "category":   category,
        "reason":     reason,
        "number":     number,
        "channel_id": str(channel.id),
        "claimed_by": None,
    })

    mention = support_role.mention if support_role else ""

    # Components V2 messages can't carry separate `content` alongside the
    # new components, so the ping mentions are folded into the TextDisplay
    # itself — mentions in text displays still notify users/roles.
    body = (
        f"{interaction.user.mention} {mention}\n\n"
        f"## {category} • Ticket {ticket_num(number)}\n"
        f"Welcome {interaction.user.mention}!\n"
        f"A support team member will be with you shortly.\n\n"
        f"**{E_VIEW} Ticket Info**\n"
        f"> **Category:** {category}\n"
        f"> **Status:** Open\n"
        f"> **Ticket:** {ticket_num(number)}"
    )

    if form_data and len(form_data) > 1:
        answers = "\n".join(
            f"> **{k}:** {v}" for k, v in form_data.items() if v
        )
        body += f"\n\n**{E_CUSTOM} Your Answers**\n{answers}"
    elif reason and reason != "No reason provided.":
        body += f"\n\n**{E_CUSTOM} Reason**\n> {reason}"

    container = discord.ui.Container(accent_color=EMBED_COLOR)
    section = discord.ui.Section(
        discord.ui.TextDisplay(body),
        accessory=discord.ui.Thumbnail(interaction.user.display_avatar.url),
    )
    container.add_item(section)

    class _TicketOpenLayout(discord.ui.LayoutView):
        def __init__(self):
            super().__init__(timeout=None)
            for row in _rows_from_view(TicketControlView()):
                container.add_item(row)
            self.add_item(container)

    await channel.send(view=_TicketOpenLayout())

    await interaction.response.send_message(
        view=_ok(f"Your ticket has been created: {channel.mention}"),
        ephemeral=True,
    )

    if config.get("log_channel_id"):
        log = _log_embed(f"{E_TICKET} Ticket Opened", INFO_COLOR)
        log.add_field(name="Author",   value=f"{interaction.user.mention} (`{interaction.user.id}`)", inline=False)
        log.add_field(name="Category", value=category, inline=True)
        log.add_field(name="Channel",  value=channel.mention, inline=True)
        log.add_field(name="Ticket",   value=ticket_num(number), inline=True)
        if reason and reason != "No reason provided.":
            log.add_field(name="Reason", value=reason[:500], inline=False)
        log.set_thumbnail(interaction.user.display_avatar.url)
        log.set_footer(f"ID: {channel.id}")
        await send_log(interaction.guild, config, log)


# ── Panel Type 1: Button Panel ─────────────────────────────────

class TicketPanelView(discord.ui.View):
    def __init__(
        self,
        button_label: str = "Open a Ticket",
        button_emoji: str | None = None,
        # Legacy single-colour param kept for backwards-compat
        button_color: str = "Blue",
        # New per-button colours dict: {"main": "Blue", "Bug Report": "Red", ...}
        button_colors: dict | None = None,
        active_categories: list[str] | None = None,
        show_main_button: bool = True,
    ):
        super().__init__(timeout=None)
        if active_categories is None:
            active_categories = DEFAULT_CATEGORIES[:]

        # Resolve colour for a given key
        def _color(key: str, fallback: str) -> discord.ButtonStyle:
            if button_colors:
                return _style(button_colors.get(key, fallback))
            return _style(button_color if key == "main" else fallback)

        # Main button always opens first active category (or General
        # Support) — entirely skipped if show_main_button is False, so the
        # category buttons become the only way to open a ticket.
        if show_main_button:
            first_cat = active_categories[0] if active_categories else "General Support"
            main_btn = discord.ui.Button(
                label=button_label,
                style=_color("main", "Blue"),
                custom_id="panel:open",
                emoji=button_emoji or E_TICKET,
                row=0,
            )
            main_btn.callback = self._cb(first_cat)
            self.add_item(main_btn)

        # Default colour fallbacks per built-in category
        _default_colors = {
            "General Support": "Grey",
            "Giveaway Claim":  "Green",
            "Bug Report":      "Red",
            "Other":           "Grey",
        }

        # Up to 4 category buttons on row 1 (Discord limit: 5 per row)
        for cat in active_categories[:4]:
            fallback = _default_colors.get(cat, "Grey")
            btn = discord.ui.Button(
                label=cat,
                style=_color(cat, fallback),
                custom_id=f"panel:{cat.lower().replace(' ', '_')[:80]}",
                emoji=CATEGORY_EMOJIS.get(cat, E_QUESTION),
                row=1,
            )
            btn.callback = self._cb(cat)
            self.add_item(btn)

        # Safety net: if both the main button and every category were
        # somehow removed, fall back to a single generic open button so
        # the panel is never left with nothing clickable on it.
        if not self.children:
            fallback_btn = discord.ui.Button(
                label=button_label,
                style=_color("main", "Blue"),
                custom_id="panel:open",
                emoji=button_emoji or E_TICKET,
                row=0,
            )
            fallback_btn.callback = self._cb("General Support")
            self.add_item(fallback_btn)

    def _cb(self, category: str):
        async def callback(interaction: discord.Interaction):
            await start_form(interaction, category)
        return callback


# ── Panel Type 2: Dropdown Select Panel ───────────────────────

class TicketSelectPanel(discord.ui.View):
    def __init__(self, active_categories: list[str] | None = None):
        super().__init__(timeout=None)
        cats = active_categories or DEFAULT_CATEGORIES[:]
        options = [
            discord.SelectOption(
                label=cat,
                description=CATEGORY_DESCRIPTIONS.get(cat, "Open a ticket"),
                emoji=CATEGORY_EMOJIS.get(cat, E_QUESTION),
                value=cat,
            )
            for cat in cats[:10]
        ]
        select = discord.ui.Select(
            placeholder="Select a ticket category…",
            options=options,
            custom_id="panel2:select",
            min_values=1,
            max_values=1,
        )
        select.callback = self._on_select
        self.add_item(select)

    async def _on_select(self, interaction: discord.Interaction):
        category = interaction.data["values"][0]
        await start_form(interaction, category)


# ── Help Menu ──────────────────────────────────────────────────

HELP_PAGES = {
    "root": {
        "title": f"{E_INFO} Linuxx Ticketing — Help",
        "body": (
            f"Welcome to **Linuxx Ticketing**!\n"
            f"Select a topic from the menu below.\n\n"
            f"> {E_TICKET} **Getting Started** — how to open tickets\n"
            f"> {E_CLAIM} **Staff Commands** — manage tickets\n"
            f"> {E_SETUP} **Admin Commands** — configure the system\n"
            f"> {E_CUSTOM} **Multi-Step Forms** — custom ticket forms\n"
            f"> {E_VIEW} **Panel Types** — buttons vs dropdown\n"
            f"> {E_INFO} **About** — features and credits"
        ),
    },
    "start": {
        "title": f"{E_TICKET} Getting Started",
        "body": (
            f"**Opening a Ticket**\n"
            f"> Go to the ticket panel channel.\n"
            f"> Click a category button **or** choose from the dropdown panel.\n"
            f"> Fill in the form that appears and submit.\n"
            f"> A private channel will be created just for you.\n\n"
            f"**Inside Your Ticket**\n"
            f"> {E_CLAIM} **Claim** — a staff member takes ownership\n"
            f"> {E_DELETE} **Close** — closes and locks the channel\n\n"
            f"**Ticket Limit**\n"
            f"> You can have up to 3 open tickets at once (set by admins)."
        ),
    },
    "staff": {
        "title": f"{E_CLAIM} Staff Commands",
        "body": (
            f"`/close` — Close the current ticket\n"
            f"`/add @user` — Add a member to this ticket\n"
            f"`/remove @user` — Remove a member from this ticket\n"
            f"`/transcript` — Generate an HTML transcript\n"
            f"`/ticketinfo` — View ticket details\n\n"
            f"**Closed Ticket Buttons**\n"
            f"> {E_DELETE} **Delete** — deletes channel & DMs transcript\n"
            f"> {E_REOPEN} **Reopen** — restores access and reopens"
        ),
    },
    "admin": {
        "title": f"{E_SETUP} Admin Commands",
        "body": (
            f"`/setup` — Full setup wizard *(Administrator only)*\n"
            f"`/panel2` — Send the dropdown-style panel\n"
            f"`/setform` — Configure multi-step forms per category\n\n"
            f"**What You Can Configure**\n"
            f"> Support role, panel channel, ticket category, log channel\n"
            f"> Panel title, description, author name & icon\n"
            f"> Footer text & icon, thumbnail, banner image\n"
            f"> Button label, emoji & colour\n"
            f"> Remove unused category buttons from the panel"
        ),
    },
    "forms": {
        "title": f"{E_CUSTOM} Multi-Step Forms",
        "body": (
            f"Each category supports **1–4 custom form steps**.\n\n"
            f"**Default** — 1 step, asks for a reason.\n\n"
            f"**Custom via `/setform`**\n"
            f"> Set a title for each step\n"
            f"> Add up to 4 fields per step\n"
            f"> Answers appear formatted in the ticket channel\n\n"
            f"**Example — Bug Report:**\n"
            f"> Step 1: Bug title + description\n"
            f"> Step 2: Steps to reproduce\n"
            f"> Step 3: Expected vs actual behaviour"
        ),
    },
    "panels": {
        "title": f"{E_VIEW} Panel Types",
        "body": (
            f"**Panel 1 — Button Panel** *(sent by `/setup`)*\n"
            f"> Main open button + category buttons\n"
            f"> Fast, one click to open a ticket\n\n"
            f"**Panel 2 — Dropdown Panel** *(sent by `/panel2`)*\n"
            f"> Users select from a dropdown menu\n"
            f"> Shows category name, description & emoji\n"
            f"> Supports up to 10 categories\n"
            f"> Displays the animated ticket banner GIF\n\n"
            f"Both panels support multi-step forms."
        ),
    },
    "about": {
        "title": f"{E_INFO} About Linuxx Ticketing",
        "body": (
            f"**Linuxx Ticketing** is a fully-featured Discord ticket system.\n\n"
            f"**Features**\n"
            f"> Two panel styles — buttons & dropdown\n"
            f"> Multi-step customisable ticket forms\n"
            f"> Claim, close, reopen & delete workflow\n"
            f"> HTML transcripts DMed to user on delete\n"
            f"> Full log channel with detailed embeds\n"
            f"> Per-user ticket limits\n"
            f"> Persistent buttons across bot restarts\n"
            f"> No database required\n\n"
            f"**Powered by wmikon**"
        ),
    },
}


class HelpSelect(discord.ui.Select):
    def __init__(self):
        super().__init__(
            placeholder="Select a help topic…",
            custom_id="help:select",
            options=[
                discord.SelectOption(label="Getting Started",  value="start",  emoji=E_TICKET,   description="How to open and use tickets"),
                discord.SelectOption(label="Staff Commands",   value="staff",  emoji=E_CLAIM,    description="Manage tickets as staff"),
                discord.SelectOption(label="Admin Commands",   value="admin",  emoji=E_SETUP,    description="Setup and configuration"),
                discord.SelectOption(label="Multi-Step Forms", value="forms",  emoji=E_CUSTOM,   description="Custom ticket forms"),
                discord.SelectOption(label="Panel Types",      value="panels", emoji=E_VIEW,     description="Buttons vs dropdown panel"),
                discord.SelectOption(label="About",            value="about",  emoji=E_INFO,     description="Features and credits"),
            ],
        )

    async def callback(self, interaction: discord.Interaction):
        page = HELP_PAGES.get(self.values[0], HELP_PAGES["root"])
        await interaction.response.edit_message(view=HelpView(page_key=self.values[0]))


class HelpView(discord.ui.LayoutView):
    def __init__(self, page_key: str = "root"):
        super().__init__(timeout=180)
        page = HELP_PAGES.get(page_key, HELP_PAGES["root"])
        container = discord.ui.Container(accent_color=EMBED_COLOR)
        container.add_item(discord.ui.TextDisplay(f"## {page['title']}\n{page['body']}"))
        self.add_item(container)
        row = discord.ui.ActionRow()
        row.add_item(HelpSelect())
        self.add_item(row)


# ── Form Builder ───────────────────────────────────────────────

class AddStepModal(discord.ui.Modal, title="Add Form Step"):
    step_title = discord.ui.TextInput(label="Step Title", placeholder="e.g. Bug Details", max_length=80)
    field1     = discord.ui.TextInput(label="Field 1 Label", placeholder="e.g. Describe the bug", max_length=80)
    field2     = discord.ui.TextInput(label="Field 2 Label (optional)", placeholder="e.g. Steps to reproduce", required=False, max_length=80)
    field3     = discord.ui.TextInput(label="Field 3 Label (optional)", placeholder="e.g. Expected behaviour", required=False, max_length=80)
    field4     = discord.ui.TextInput(label="Field 4 Label (optional)", placeholder="e.g. Screenshot URL", required=False, max_length=80)

    def __init__(self, category: str, steps: list, view: "FormBuilderView"):
        super().__init__()
        self.category = category
        self.steps    = steps
        self.fbview   = view

    async def on_submit(self, interaction: discord.Interaction):
        fields = [
            {"label": f.value, "placeholder": "", "required": f == self.field1, "long": True, "max_length": 1000}
            for f in [self.field1, self.field2, self.field3, self.field4] if f.value
        ]
        self.steps.append({"title": self.step_title.value, "fields": fields})
        self.fbview.steps = self.steps

        config = get_config(interaction.guild.id) or {}
        forms  = config.get("form_steps", {})
        forms[self.category] = self.steps
        config["form_steps"] = forms
        set_config(interaction.guild.id, config)

        await interaction.response.edit_message(
            view=FormBuilderView(self.category, steps=self.steps, status=f"{E_SUCCESS} Step **{len(self.steps)}** added!")
        )


def _form_builder_text(category: str, steps: list, status: str = "", hint: str = "") -> str:
    summary = "\n".join(
        f"> **Step {i+1}:** {s['title']} — {len(s['fields'])} field(s)"
        for i, s in enumerate(steps)
    ) if steps else "> Default single-step form (reason only)"
    lines = [f"## {E_CUSTOM} Form Builder — {category}"]
    if status:
        lines.append(status)
    lines.append(f"**Current form:**\n{summary}")
    if hint:
        lines.append(hint)
    lines.append("\nAdd more steps or click **Done**.")
    return "\n".join(lines)


class FormBuilderView(discord.ui.LayoutView):
    def __init__(self, category: str, steps: list | None = None, status: str = "", hint: str = ""):
        super().__init__(timeout=300)
        self.category = category
        self.steps: list = steps if steps is not None else []

        container = discord.ui.Container(accent_color=EMBED_COLOR)
        container.add_item(discord.ui.TextDisplay(_form_builder_text(category, self.steps, status, hint)))
        self.add_item(container)

        row = discord.ui.ActionRow()

        add_btn = discord.ui.Button(label="Add Step", style=discord.ButtonStyle.primary, emoji=E_CUSTOM)
        add_btn.callback = self._add_step_cb
        row.add_item(add_btn)

        reset_btn = discord.ui.Button(label="Reset to Default", style=discord.ButtonStyle.danger, emoji=E_DELETE)
        reset_btn.callback = self._reset_cb
        row.add_item(reset_btn)

        done_btn = discord.ui.Button(label="Done", style=discord.ButtonStyle.success, emoji=E_SUCCESS)
        done_btn.callback = self._done_cb
        row.add_item(done_btn)

        self.add_item(row)

    async def _add_step_cb(self, interaction: discord.Interaction):
        if len(self.steps) >= 4:
            return await interaction.response.send_message(
                view=_err("Maximum 4 steps per form."), ephemeral=True
            )
        await interaction.response.send_modal(AddStepModal(self.category, self.steps, self))

    async def _reset_cb(self, interaction: discord.Interaction):
        config = get_config(interaction.guild.id) or {}
        forms  = config.get("form_steps", {})
        forms.pop(self.category, None)
        config["form_steps"] = forms
        set_config(interaction.guild.id, config)
        await interaction.response.edit_message(
            view=FormBuilderView(self.category, steps=[], status=f"{E_SUCCESS} Form reset to the default single-step form.")
        )

    async def _done_cb(self, interaction: discord.Interaction):
        summary = "\n".join(
            f"> **Step {i+1}:** {s['title']} — {len(s['fields'])} field(s)"
            for i, s in enumerate(self.steps)
        ) if self.steps else "> Default single-step form (reason only)"
        await interaction.response.edit_message(
            view=_ok_raw(f"## {E_SUCCESS} Form Saved — {self.category}\n{summary}")
        )


# ── Setform Autocomplete ───────────────────────────────────────

async def _setform_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    config = get_config(interaction.guild.id) or {}
    cats   = config.get("active_categories", DEFAULT_CATEGORIES[:])
    # Also include any categories that already have form steps configured
    #  but were removed from active list — so admins can still edit them
    extra  = [c for c in config.get("form_steps", {}) if c not in cats]
    all_cats = cats + extra
    return [
        app_commands.Choice(name=c, value=c)
        for c in all_cats
        if current.lower() in c.lower()
    ][:25]


# ── Cog ───────────────────────────────────────────────────────

class TicketsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        # Restore persistent views — must match the custom_ids used when panels were sent
        self.bot.add_view(TicketPanelView())
        self.bot.add_view(TicketSelectPanel())
        self.bot.add_view(TicketControlView())
        self.bot.add_view(ClosedTicketView())
        self.bot.add_view(HelpView())
        self.bot.add_view(PanelExtraButtonRegistration())

    @app_commands.command(name="help", description="View Linuxx Ticketing help and commands")
    async def help_cmd(self, interaction: discord.Interaction):
        await interaction.response.send_message(view=HelpView(page_key="root"), ephemeral=True)

    @app_commands.command(name="panel2", description="Send the dropdown-style ticket panel")
    @app_commands.default_permissions(administrator=True)
    async def panel2_cmd(self, interaction: discord.Interaction):
        config = get_config(interaction.guild.id)
        if not config:
            return await interaction.response.send_message(
                view=_err("Run `/setup` or `/setup2` first."), ephemeral=True
            )

        DEFAULT_BANNER = (
            "https://cdn.discordapp.com/attachments/1414256332592254986/"
            "1416490775046389851/standard_2.gif?ex=6a3a2795&is=6a38d615&"
            "hm=316a7f58973c16b80a1790490a4803f968d00a1996fc83e9fb36880e2d9aa07b&"
        )

        cats = config.get("active_categories", DEFAULT_CATEGORIES[:])
        cat_list = "\n".join(
            f"> {CATEGORY_EMOJIS.get(c, E_QUESTION)} **{c}**"
            for c in cats
        )
        description = (
            f"{config.get('panel_description', 'Select a ticket type from the menu below.')}"
            f"\n\n{cat_list}"
        )

        author_name = config.get("author_name") or interaction.guild.name
        author_icon = config.get("author_icon_url") or (
            interaction.guild.icon.url if interaction.guild.icon else None
        )
        thumb = config.get("thumbnail_url") or (
            interaction.guild.icon.url if interaction.guild.icon else None
        )
        image_url = config.get("image_url") or DEFAULT_BANNER

        panel_view = build_panel_layout(
            title=config.get("panel_title", "Support Center"),
            description=description,
            color=EMBED_COLOR,
            author_name=author_name,
            author_icon_url=author_icon or "",
            thumbnail_url=thumb or "",
            image_url=image_url,
            action_view=TicketSelectPanel(cats),
            panel_button_label=config.get("panel_button_label", ""),
            panel_button_url=config.get("panel_button_url", ""),
            panel_button_text=config.get("panel_button_text", ""),
            panel_button_style=PANEL_BUTTON_COLOR_MAP.get(config.get("panel_button_color", "Grey"), discord.ButtonStyle.secondary),
            panel_button_emoji=config.get("panel_button_emoji", ""),
        )

        panel_ch = interaction.guild.get_channel(int(config["panel_channel_id"]))
        if not panel_ch:
            panel_ch = await interaction.guild.fetch_channel(int(config["panel_channel_id"]))

        await panel_ch.send(view=panel_view)
        await interaction.response.send_message(
            view=_ok(f"Dropdown panel sent to {panel_ch.mention}!"), ephemeral=True
        )

    @app_commands.command(name="setform", description="Configure a multi-step form for a ticket category")
    @app_commands.describe(category="The ticket category to configure")
    @app_commands.autocomplete(category=_setform_autocomplete)
    @app_commands.default_permissions(administrator=True)
    async def setform_cmd(self, interaction: discord.Interaction, category: str):
        config   = get_config(interaction.guild.id) or {}
        existing = config.get("form_steps", {}).get(category, [])
        hint = (
            "> Each step = one modal shown to the user\n"
            "> Up to 4 steps, up to 4 fields each\n"
            "> Click **Add Step** to build your form\n"
            "> Click **Reset** to go back to the default"
        )
        view = FormBuilderView(category, steps=existing[:], hint=hint)
        await interaction.response.send_message(view=view, ephemeral=True)

    @app_commands.command(name="close", description="Close the current ticket")
    async def close_cmd(self, interaction: discord.Interaction):
        await close_ticket(interaction)

    @app_commands.command(name="add", description="Add a member to this ticket")
    @app_commands.describe(member="Member to add")
    async def add_member(self, interaction: discord.Interaction, member: discord.Member):
        if not get_ticket(interaction.channel.id):
            return await interaction.response.send_message(view=_err("This is not a ticket channel."), ephemeral=True)
        await interaction.channel.set_permissions(member, read_messages=True, send_messages=True)
        await interaction.response.send_message(
            view=_ok(f"Added {member.mention} to the ticket.")
        )

    @app_commands.command(name="remove", description="Remove a member from this ticket")
    @app_commands.describe(member="Member to remove")
    async def remove_member(self, interaction: discord.Interaction, member: discord.Member):
        if not get_ticket(interaction.channel.id):
            return await interaction.response.send_message(view=_err("This is not a ticket channel."), ephemeral=True)
        await interaction.channel.set_permissions(member, overwrite=None)
        await interaction.response.send_message(
            view=_ok(f"Removed {member.mention} from the ticket.")
        )

    @app_commands.command(name="transcript", description="Generate an HTML transcript of this ticket")
    async def transcript_cmd(self, interaction: discord.Interaction):
        if not get_ticket(interaction.channel.id):
            return await interaction.response.send_message(view=_err("This is not a ticket channel."), ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        f = await generate_transcript(interaction.channel)
        await interaction.followup.send(view=_ok("Transcript ready!"), file=f, ephemeral=True)

    @app_commands.command(name="ticketinfo", description="View details about the current ticket")
    async def ticket_info(self, interaction: discord.Interaction):
        ticket = get_ticket(interaction.channel.id)
        if not ticket:
            return await interaction.response.send_message(view=_err("This is not a ticket channel."), ephemeral=True)

        author     = interaction.guild.get_member(int(ticket["author_id"]))
        claimer_id = ticket.get("claimed_by")
        claimer    = interaction.guild.get_member(int(claimer_id)) if claimer_id else None
        number     = ticket.get("number", 0)
        status     = ticket.get("status", "open")
        color      = SUCCESS_COLOR if status == "open" else ERROR_COLOR

        author_display = author.mention if author else f"`{ticket['author_id']}`"
        body_lines = [
            f"## {E_VIEW} Ticket {ticket_num(number)}",
            f"**Author:** {author_display}",
            f"**Category:** {ticket.get('category', 'Unknown')}",
            f"**Status:** {'Open' if status == 'open' else 'Closed'}",
            f"**Claimed:** {claimer.mention if claimer else 'Unclaimed'}",
        ]
        if ticket.get("reason") and ticket["reason"] != "No reason provided.":
            body_lines.append(f"**Reason:** {ticket['reason'][:500]}")
        body = "\n".join(body_lines)

        container = discord.ui.Container(accent_color=color)
        if author:
            container.add_item(discord.ui.Section(
                discord.ui.TextDisplay(body),
                accessory=discord.ui.Thumbnail(author.display_avatar.url),
            ))
        else:
            container.add_item(discord.ui.TextDisplay(body))

        class _InfoLayout(discord.ui.LayoutView):
            def __init__(self):
                super().__init__()
                self.add_item(container)

        await interaction.response.send_message(view=_InfoLayout(), ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(TicketsCog(bot))
