from __future__ import annotations
import discord
from discord import app_commands
from discord.ext import commands
from utils.store import get_config, set_config

# ── Custom Emojis ──────────────────────────────────────────────
E_SUCCESS  = "<:success:1518137986095644703>"
E_CROSS    = "<:wickk:1518137821355966494>"
E_INFO     = "<:Warning:1517892973482868960>"
E_WARN     = "<:warn:1518063335923257386>"
E_TICKET   = "<:ticket:1513730006910500977>"
E_BUG      = "<:TbotBug:1518063885855358996>"
E_CLAIM    = "<:claim:1518064508948447242>"
E_VIEW     = "<:view:1518064705854373969>"
E_REOPEN   = "<:ticket_reopen:1518064251405733898>"
E_QUESTION = "<:question_mark:1518064034862076007>"
E_DELETE   = "<:delete:1518064106723217418>"
E_SETUP    = "<:setup:1518064880769568828>"
E_CUSTOM   = "<:customize:1518065679041957989>"

# ── Colors ─────────────────────────────────────────────────────
# All container accent bars + backgrounds are pure black, regardless of
# message type (success/error/info/warn all look the same now).
EMBED_COLOR   = 0x000000
SUCCESS_COLOR = 0x000000
ERROR_COLOR   = 0x000000
WARN_COLOR    = 0x000000
INFO_COLOR    = 0x000000

BRAND_FULL = "Linuxx Ticketing • Powered by wmikon"

DEFAULT_BANNER = (
    "https://cdn.discordapp.com/attachments/1414256332592254986/"
    "1416490775046389851/standard_2.gif?ex=6a3a2795&is=6a38d615&"
    "hm=316a7f58973c16b80a1790490a4803f968d00a1996fc83e9fb36880e2d9aa07b&"
)

DEFAULT_CATEGORIES = ["General Support", "Giveaway Claim", "Bug Report", "Other"]

COLOR_OPTIONS = ["Blue", "Green", "Red", "Grey", "Yellow"]

BUTTON_COLOR_MAP = {
    "Green":  discord.ButtonStyle.success,
    "Blue":   discord.ButtonStyle.primary,
    "Grey":   discord.ButtonStyle.secondary,
    "Yellow": discord.ButtonStyle.secondary,
    "Red":    discord.ButtonStyle.danger,
}

# Colour options for the optional Panel Text button. Discord only has 5
# real non-link button styles (Blurple, Grey, Green, Red — Yellow has no
# native style). Black/White/Yellow all render as Discord's grey button
# since there's no native style for them; labelled honestly in the picker
# so admins know what they'll actually get.
PANEL_BUTTON_COLOR_OPTIONS = ["Grey", "Yellow", "Blue", "Red", "Black", "White"]

PANEL_BUTTON_COLOR_MAP = {
    "Grey":   discord.ButtonStyle.secondary,
    "Yellow": discord.ButtonStyle.secondary,
    "Blue":   discord.ButtonStyle.primary,
    "Red":    discord.ButtonStyle.danger,
    "Black":  discord.ButtonStyle.secondary,
    "White":  discord.ButtonStyle.secondary,
}

CATEGORY_EMOJIS = {
    "General Support": E_QUESTION,
    "Giveaway Claim":  E_TICKET,
    "Bug Report":      E_BUG,
    "Other":           E_CUSTOM,
}


# ── Shared State ───────────────────────────────────────────────

class SetupState:
    def __init__(self):
        self.support_role: discord.Role | None               = None
        self.panel_channel: discord.TextChannel | None       = None
        self.ticket_category: discord.CategoryChannel | None = None
        self.log_channel: discord.TextChannel | None         = None
        self.ticket_limit: int       = 3
        self.panel_title: str        = "Support Center"
        self.panel_description: str  = "Click a button below to open a ticket."
        # Pre-filled defaults — server name/icon resolved at finish time
        self.author_name: str        = ""          # filled at finish with guild.name
        self.author_icon_url: str    = ""          # filled at finish with guild.icon
        self.footer_text: str        = "Linuxx Ticketing"
        self.footer_icon_url: str    = ""          # bot avatar, resolved at finish
        self.thumbnail_url: str      = ""          # guild icon, resolved at finish
        self.image_url: str          = DEFAULT_BANNER
        self.button_label: str       = "Open a Ticket"
        self.button_emoji: str       = ""
        # Per-button colours: key = category name or "main"
        self.button_colors: dict[str, str] = {
            "main":            "Blue",
            "General Support": "Grey",
            "Giveaway Claim":  "Green",
            "Bug Report":      "Red",
            "Other":           "Grey",
        }
        self.active_categories: list[str] = DEFAULT_CATEGORIES[:]
        # Whether the main "Open a Ticket" button is shown on the button
        # panel. Category buttons remain the only way to open tickets if
        # this is turned off — guarded so it can never be turned off when
        # there are zero categories left (and vice versa).
        self.show_main_button: bool  = True
        # Optional extra button shown under the panel's main text.
        # Empty label = no button at all on the panel.
        self.panel_button_label: str = ""
        self.panel_button_url: str   = ""   # if set -> link button
        self.panel_button_text: str  = ""   # if no url -> shown as popup on click
        self.panel_button_emoji: str = ""
        self.panel_button_color: str = "Grey"
        # Track whether user explicitly edited author/footer/thumbnail
        # so we know not to overwrite at finish if they cleared them
        self._author_edited: bool    = False
        self._footer_edited: bool    = False
        self._thumb_edited: bool     = False

    def resolved_author_name(self, guild: discord.Guild) -> str:
        if self._author_edited:
            return self.author_name
        return self.author_name or guild.name

    def resolved_author_icon(self, guild: discord.Guild) -> str:
        if self._author_edited:
            return self.author_icon_url
        return self.author_icon_url or (guild.icon.url if guild.icon else "")

    def resolved_footer_icon(self, bot: discord.Client) -> str:
        if self._footer_edited:
            return self.footer_icon_url
        return self.footer_icon_url or (bot.user.display_avatar.url if bot.user else "")

    def resolved_thumbnail(self, guild: discord.Guild) -> str:
        if self._thumb_edited:
            return self.thumbnail_url
        return self.thumbnail_url or (guild.icon.url if guild.icon else "")


# ── Components V2 Helpers ───────────────────────────────────────

class MessageLayout(discord.ui.LayoutView):
    """Generic single-container layout for simple text replies."""
    def __init__(self, text: str, color: int, *, extra_rows: list[discord.ui.ActionRow] | None = None):
        super().__init__()
        container = discord.ui.Container(accent_color=color)
        container.add_item(discord.ui.TextDisplay(text))
        self.add_item(container)
        for row in (extra_rows or []):
            self.add_item(row)


def _ok(msg: str) -> MessageLayout:
    return MessageLayout(f"{E_SUCCESS}  {msg}", SUCCESS_COLOR)

def _ok_raw(text: str) -> MessageLayout:
    """Like _ok but takes pre-formatted text (e.g. with its own heading)."""
    return MessageLayout(text, SUCCESS_COLOR)

def _err(msg: str) -> MessageLayout:
    return MessageLayout(f"{E_CROSS}  {msg}", ERROR_COLOR)

def _info(msg: str) -> MessageLayout:
    return MessageLayout(f"{E_INFO}  {msg}", INFO_COLOR)


# ── Modals ─────────────────────────────────────────────────────

class PanelTextModal(discord.ui.Modal, title="Panel Text Settings"):
    panel_title = discord.ui.TextInput(
        label="Panel Title",
        placeholder="e.g. Support Center",
        max_length=100,
    )
    panel_description = discord.ui.TextInput(
        label="Panel Description",
        style=discord.TextStyle.paragraph,
        placeholder="Click a button below to open a ticket.",
        max_length=300,
        required=False,
    )
    author_name = discord.ui.TextInput(
        label="Author Name  (blank = server name)",
        placeholder="Defaults to your server name",
        required=False,
        max_length=100,
    )
    author_icon_url = discord.ui.TextInput(
        label="Author Icon URL  (blank = server icon)",
        placeholder="Defaults to your server icon",
        required=False,
        max_length=500,
    )

    def __init__(self, state: SetupState):
        super().__init__()
        self.state = state
        self.panel_title.default       = state.panel_title
        self.panel_description.default = state.panel_description
        self.author_name.default       = state.author_name
        self.author_icon_url.default   = state.author_icon_url

    async def on_submit(self, interaction: discord.Interaction):
        self.state.panel_title       = self.panel_title.value
        self.state.panel_description = self.panel_description.value
        self.state.author_name       = self.author_name.value
        self.state.author_icon_url   = self.author_icon_url.value
        self.state._author_edited    = True
        await interaction.response.send_message(
            view=_ok("Panel text updated."), ephemeral=True
        )


class FooterMediaModal(discord.ui.Modal, title="Footer, Thumbnail & Banner"):
    footer_text = discord.ui.TextInput(
        label="Footer Text  (blank = 'Linuxx Ticketing')",
        placeholder="Linuxx Ticketing",
        required=False,
        max_length=200,
    )
    footer_icon_url = discord.ui.TextInput(
        label="Footer Icon URL  (blank = bot avatar)",
        placeholder="Defaults to bot avatar",
        required=False,
        max_length=500,
    )
    thumbnail_url = discord.ui.TextInput(
        label="Thumbnail URL  (blank = server icon)",
        placeholder="Defaults to your server icon",
        required=False,
        max_length=500,
    )
    image_url = discord.ui.TextInput(
        label="Banner Image URL  (blank = default GIF)",
        placeholder="Leave blank for the animated Linuxx banner",
        required=False,
        max_length=500,
    )

    def __init__(self, state: SetupState):
        super().__init__()
        self.state = state
        self.footer_text.default     = state.footer_text
        self.footer_icon_url.default = state.footer_icon_url
        self.thumbnail_url.default   = state.thumbnail_url
        self.image_url.default       = state.image_url

    async def on_submit(self, interaction: discord.Interaction):
        self.state.footer_text     = self.footer_text.value or "Linuxx Ticketing"
        self.state.footer_icon_url = self.footer_icon_url.value
        self.state.thumbnail_url   = self.thumbnail_url.value
        self.state.image_url       = self.image_url.value or DEFAULT_BANNER
        self.state._footer_edited  = True
        self.state._thumb_edited   = True
        await interaction.response.send_message(
            view=_ok("Footer, thumbnail and banner updated."), ephemeral=True
        )


class ButtonLabelModal(discord.ui.Modal, title="Main Button Settings"):
    button_label = discord.ui.TextInput(
        label="Button Label",
        placeholder="e.g. Open a Ticket",
        default="Open a Ticket",
        max_length=80,
    )
    button_emoji = discord.ui.TextInput(
        label="Button Emoji",
        placeholder="Leave blank for default ticket emoji",
        required=False,
        max_length=100,
    )

    def __init__(self, state: SetupState):
        super().__init__()
        self.state = state
        self.button_label.default = state.button_label
        self.button_emoji.default = state.button_emoji

    async def on_submit(self, interaction: discord.Interaction):
        self.state.button_label = self.button_label.value
        self.state.button_emoji = self.button_emoji.value
        await interaction.response.send_message(
            view=_ok("Button settings updated."), ephemeral=True
        )


class AddCategoryModal(discord.ui.Modal, title="Add New Category"):
    cat_name = discord.ui.TextInput(
        label="Category Name",
        placeholder="e.g. Partnership Request",
        max_length=80,
    )

    def __init__(self, state: SetupState, *, dropdown: bool = False):
        super().__init__()
        self.state    = state
        self.dropdown = dropdown

    async def on_submit(self, interaction: discord.Interaction):
        name = self.cat_name.value.strip()
        if not name:
            return await interaction.response.send_message(
                view=_err("Category name cannot be empty."), ephemeral=True
            )
        if name in self.state.active_categories:
            return await interaction.response.send_message(
                view=_err(f"**{name}** already exists."), ephemeral=True
            )
        if len(self.state.active_categories) >= 10:
            return await interaction.response.send_message(
                view=_err("Maximum 10 categories allowed."), ephemeral=True
            )
        self.state.active_categories.append(name)
        # Default colour for new button
        self.state.button_colors[name] = "Grey"

        # Rebuild whichever step-2 flow this modal was opened from
        # (button panel vs dropdown panel) — previously this always
        # rebuilt the button-panel view even when launched from /setup2.
        if self.dropdown:
            await interaction.response.edit_message(
                view=SetupStep2Layout(self.state, dropdown=True)
            )
        else:
            await interaction.response.edit_message(
                view=SetupStep2Layout(self.state)
            )


# ── Panel Text Button (optional extra button under panel text) ─

class PanelButtonModal(discord.ui.Modal, title="Panel Button"):
    button_label = discord.ui.TextInput(
        label="Button Label  (blank = no button at all)",
        placeholder="e.g. Rules, FAQ, Chat Here",
        required=False,
        max_length=80,
    )
    button_url = discord.ui.TextInput(
        label="Button URL  (optional)",
        placeholder="https://… — leave blank to show popup text instead",
        required=False,
        max_length=500,
    )
    button_text = discord.ui.TextInput(
        label="Popup Text  (shown if no URL is set)",
        style=discord.TextStyle.paragraph,
        placeholder="Text shown to the user when they click the button",
        required=False,
        max_length=1000,
    )
    button_emoji = discord.ui.TextInput(
        label="Button Emoji  (optional)",
        required=False,
        max_length=100,
    )

    def __init__(self, state: SetupState):
        super().__init__()
        self.state = state
        self.button_label.default = state.panel_button_label
        self.button_url.default   = state.panel_button_url
        self.button_text.default  = state.panel_button_text
        self.button_emoji.default = state.panel_button_emoji

    async def on_submit(self, interaction: discord.Interaction):
        label = self.button_label.value.strip()
        url   = self.button_url.value.strip()

        if url and not (url.startswith("http://") or url.startswith("https://")):
            return await interaction.response.send_message(
                view=_err("Button URL must start with `http://` or `https://`."), ephemeral=True
            )
        if label and not url and not self.button_text.value.strip():
            return await interaction.response.send_message(
                view=_err("Set either a **URL** or some **Popup Text** for the button to do something when clicked."),
                ephemeral=True,
            )

        self.state.panel_button_label = label
        self.state.panel_button_url   = url
        self.state.panel_button_text  = self.button_text.value.strip()
        self.state.panel_button_emoji = self.button_emoji.value.strip()

        msg = "Panel button removed." if not label else "Panel button updated."
        await interaction.response.send_message(view=_ok(msg), ephemeral=True)


class PanelButtonColorSelect(discord.ui.Select):
    _STYLE_DISPLAY_NAMES = {
        discord.ButtonStyle.primary:   "Blurple",
        discord.ButtonStyle.secondary: "Grey",
        discord.ButtonStyle.success:   "Green",
        discord.ButtonStyle.danger:    "Red",
    }

    def __init__(self, state: SetupState):
        self.state = state
        current = state.panel_button_color
        super().__init__(
            placeholder="Colour for the panel button…",
            options=[
                discord.SelectOption(
                    label=c,
                    value=c,
                    description=f"Renders as Discord's {self._STYLE_DISPLAY_NAMES[PANEL_BUTTON_COLOR_MAP[c]]} button",
                    default=(c == current),
                )
                for c in PANEL_BUTTON_COLOR_OPTIONS
            ],
        )

    async def callback(self, interaction: discord.Interaction):
        self.state.panel_button_color = self.values[0]
        await interaction.response.send_message(
            view=_ok(f"Panel button colour set to **{self.values[0]}**."), ephemeral=True
        )


class PanelButtonColorView(discord.ui.LayoutView):
    def __init__(self, state: SetupState):
        super().__init__(timeout=60)
        container = discord.ui.Container(accent_color=EMBED_COLOR)
        container.add_item(discord.ui.TextDisplay(
            f"{E_INFO}  Pick a colour for the panel button.\n"
            f"-# Discord has no native Black/White/Yellow button — these render as the standard grey button."
        ))
        row = discord.ui.ActionRow()
        row.add_item(PanelButtonColorSelect(state))
        container.add_item(row)
        self.add_item(container)


# ── Button Colour Select (targets a specific button key) ───────

class SingleButtonColorSelect(discord.ui.Select):
    def __init__(self, state: SetupState, target: str, label: str):
        self.state  = state
        self.target = target
        current = state.button_colors.get(target, "Blue")
        super().__init__(
            placeholder=f"Colour for: {label}",
            options=[
                discord.SelectOption(
                    label=c,
                    value=c,
                    description=f"Set {label} to {c}",
                    default=(c == current),
                )
                for c in COLOR_OPTIONS
            ],
        )

    async def callback(self, interaction: discord.Interaction):
        self.state.button_colors[self.target] = self.values[0]
        await interaction.response.send_message(
            view=_ok(f"Colour set to **{self.values[0]}**."), ephemeral=True
        )


class SingleButtonColorView(discord.ui.LayoutView):
    def __init__(self, state: SetupState, target: str, label: str):
        super().__init__(timeout=60)
        container = discord.ui.Container(accent_color=INFO_COLOR)
        container.add_item(discord.ui.TextDisplay(f"{E_INFO}  Choose a colour for **{label}**."))
        row = discord.ui.ActionRow()
        row.add_item(SingleButtonColorSelect(state, target, label))
        container.add_item(row)
        self.add_item(container)


# ── All-buttons colour picker ───────────────────────────────────

class AllButtonsColorSelect(discord.ui.Select):
    """Shows a dropdown to pick which button to recolour."""
    def __init__(self, state: SetupState):
        self.state = state
        options = [
            discord.SelectOption(
                label=f"Main Button ({state.button_label})",
                value="main",
                description=f"Currently: {state.button_colors.get('main', 'Blue')}",
                emoji=E_TICKET,
            )
        ] + [
            discord.SelectOption(
                label=cat,
                value=cat,
                description=f"Currently: {state.button_colors.get(cat, 'Grey')}",
                emoji=CATEGORY_EMOJIS.get(cat, E_QUESTION),
            )
            for cat in state.active_categories
        ]
        super().__init__(
            placeholder="Which button to recolour?",
            options=options[:25],
        )

    async def callback(self, interaction: discord.Interaction):
        target = self.values[0]
        label  = "Main Button" if target == "main" else target
        await interaction.response.send_message(
            view=SingleButtonColorView(self.state, target, label),
            ephemeral=True,
        )


class AllButtonsColorView(discord.ui.LayoutView):
    def __init__(self, state: SetupState):
        super().__init__(timeout=60)
        container = discord.ui.Container(accent_color=INFO_COLOR)
        container.add_item(discord.ui.TextDisplay(f"{E_INFO}  Pick a button to change its colour."))
        row = discord.ui.ActionRow()
        row.add_item(AllButtonsColorSelect(state))
        container.add_item(row)
        self.add_item(container)


# ── Delete Categories Select ───────────────────────────────────

class DeleteCatsSelect(discord.ui.Select):
    """Lets the admin remove category buttons/options — and, on the button
    panel only, the main 'Open a Ticket' button itself. Guarded so the
    panel can never end up with nothing left to click: removing the main
    button is blocked while zero categories remain, and removing the last
    category is blocked while the main button is already hidden."""

    MAIN_VALUE = "__main_button__"

    def __init__(self, state: SetupState, *, dropdown: bool, parent_message: discord.Message | None):
        self.state          = state
        self.dropdown        = dropdown
        self.parent_message  = parent_message

        options = [
            discord.SelectOption(label=c, value=c, emoji=CATEGORY_EMOJIS.get(c, E_QUESTION))
            for c in state.active_categories
        ]
        # The main button is only ever a removable option on the button
        # panel — the dropdown panel has no separate main button.
        if not dropdown and state.show_main_button:
            options.append(discord.SelectOption(
                label=f"Open a Ticket — Main Button ({state.button_label})",
                value=self.MAIN_VALUE,
                emoji=E_TICKET,
                description="The main button shown above the category buttons",
            ))

        super().__init__(
            placeholder="Select what to remove…",
            min_values=1,
            max_values=max(1, len(options)),
            options=options or [discord.SelectOption(label="Nothing left to remove", value="__none__")],
            disabled=not options,
        )

    async def callback(self, interaction: discord.Interaction):
        wants_main = self.MAIN_VALUE in self.values
        cats_to_remove = [v for v in self.values if v != self.MAIN_VALUE]

        # Work out what would remain after this removal, then block the
        # whole action if it would leave the panel with nothing clickable.
        remaining_cats = [c for c in self.state.active_categories if c not in cats_to_remove]
        remaining_main = self.state.show_main_button and not wants_main

        if not self.dropdown and not remaining_cats and not remaining_main:
            return await interaction.response.send_message(
                view=_err(
                    "Can't remove that — the panel needs **at least one** "
                    "category button or the main button to stay clickable."
                ),
                ephemeral=True,
            )
        if self.dropdown and not remaining_cats:
            return await interaction.response.send_message(
                view=_err("Can't remove the last category — the dropdown needs at least one option."),
                ephemeral=True,
            )

        for cat in cats_to_remove:
            if cat in self.state.active_categories:
                self.state.active_categories.remove(cat)
                self.state.button_colors.pop(cat, None)
        if wants_main:
            self.state.show_main_button = False

        removed_bits = []
        if cats_to_remove:
            removed_bits.append(", ".join(cats_to_remove))
        if wants_main:
            removed_bits.append("the main button")
        removed_summary = " and ".join(removed_bits)

        remaining = ", ".join(self.state.active_categories) or "None"
        if not self.dropdown:
            remaining += f"  •  Main button: {'shown' if self.state.show_main_button else 'hidden'}"

        # Refresh this ephemeral picker in place so it reflects what's left
        await interaction.response.edit_message(
            view=DeleteCatsView(self.state, dropdown=self.dropdown, parent_message=self.parent_message)
        )

        # Also push the change back to the underlying step-2 panel message,
        # which previously went stale after removing a category from /setup2
        # or /setup.
        if self.parent_message is not None:
            try:
                if self.dropdown:
                    await self.parent_message.edit(view=SetupStep2Layout(self.state, dropdown=True))
                else:
                    await self.parent_message.edit(view=SetupStep2Layout(self.state))
            except discord.HTTPException:
                pass

        await interaction.followup.send(
            view=_ok(f"Removed {removed_summary}. **Remaining:** {remaining}"), ephemeral=True
        )


class DeleteCatsView(discord.ui.LayoutView):
    def __init__(self, state: SetupState, *, dropdown: bool = False, parent_message: discord.Message | None = None):
        super().__init__(timeout=60)
        container = discord.ui.Container(accent_color=INFO_COLOR)
        has_options = bool(state.active_categories) or (not dropdown and state.show_main_button)
        text = (
            f"{E_INFO}  Select what to remove."
            if has_options
            else f"{E_WARN}  Nothing left to remove."
        )
        container.add_item(discord.ui.TextDisplay(text))
        row = discord.ui.ActionRow()
        row.add_item(DeleteCatsSelect(state, dropdown=dropdown, parent_message=parent_message))
        container.add_item(row)
        self.add_item(container)


# ── Setup Step 1: Channels & Roles ─────────────────────────────

class _SupportRoleSelect(discord.ui.RoleSelect):
    def __init__(self, state: SetupState):
        self.state = state
        super().__init__(placeholder="① Support Role  (required)", min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        self.state.support_role = self.values[0]
        await interaction.response.send_message(
            view=_ok(f"Support role → {self.state.support_role.mention}"), ephemeral=True
        )


class _PanelChannelSelect(discord.ui.ChannelSelect):
    def __init__(self, state: SetupState):
        self.state = state
        super().__init__(
            placeholder="② Panel Channel  (required)",
            channel_types=[discord.ChannelType.text],
            min_values=1, max_values=1,
        )

    async def callback(self, interaction: discord.Interaction):
        self.state.panel_channel = self.values[0]
        await interaction.response.send_message(
            view=_ok(f"Panel channel → {self.state.panel_channel.mention}"), ephemeral=True
        )


class _TicketCategorySelect(discord.ui.ChannelSelect):
    def __init__(self, state: SetupState):
        self.state = state
        super().__init__(
            placeholder="③ Ticket Category  (required)",
            channel_types=[discord.ChannelType.category],
            min_values=1, max_values=1,
        )

    async def callback(self, interaction: discord.Interaction):
        self.state.ticket_category = self.values[0]
        await interaction.response.send_message(
            view=_ok(f"Ticket category → **{self.state.ticket_category.name}**"), ephemeral=True
        )


class _LogChannelSelect(discord.ui.ChannelSelect):
    def __init__(self, state: SetupState):
        self.state = state
        super().__init__(
            placeholder="④ Log Channel  (optional)",
            channel_types=[discord.ChannelType.text],
            min_values=0, max_values=1,
        )

    async def callback(self, interaction: discord.Interaction):
        self.state.log_channel = self.values[0] if self.values else None
        msg = (
            f"Log channel → {self.state.log_channel.mention}"
            if self.state.log_channel
            else "Log channel skipped."
        )
        await interaction.response.send_message(view=_ok(msg), ephemeral=True)


class SetupStep1Layout(discord.ui.LayoutView):
    def __init__(self, state: SetupState, *, dropdown: bool = False):
        super().__init__(timeout=300)
        self.state    = state
        self.dropdown = dropdown

        container = discord.ui.Container(accent_color=EMBED_COLOR)
        container.add_item(discord.ui.TextDisplay(_step1_text(dropdown=dropdown)))

        for select_cls in (_SupportRoleSelect, _PanelChannelSelect, _TicketCategorySelect, _LogChannelSelect):
            row = discord.ui.ActionRow()
            row.add_item(select_cls(state))
            container.add_item(row)

        btn_row = discord.ui.ActionRow()
        label = "Next — Customise Dropdown Panel" if dropdown else "Next — Customise Panel"
        next_btn = discord.ui.Button(label=label, style=discord.ButtonStyle.primary, emoji=E_SETUP)
        next_btn.callback = self._next_cb
        btn_row.add_item(next_btn)
        container.add_item(btn_row)

        self.add_item(container)

    async def _next_cb(self, interaction: discord.Interaction):
        if not self.state.support_role or not self.state.panel_channel or not self.state.ticket_category:
            return await interaction.response.send_message(
                view=_err("Please select a **Support Role**, **Panel Channel** and **Ticket Category** first."),
                ephemeral=True,
            )
        if self.dropdown:
            await interaction.response.edit_message(view=SetupStep2Layout(self.state, dropdown=True))
        else:
            await interaction.response.edit_message(view=SetupStep2Layout(self.state))


# ── Setup Step 2: Customisation ────────────────────────────────

class SetupStep2Layout(discord.ui.LayoutView):
    """Customisation step shared by /setup (button panel) and /setup2 (dropdown panel)."""
    def __init__(self, state: SetupState, *, dropdown: bool = False):
        super().__init__(timeout=300)
        self.state    = state
        self.dropdown = dropdown

        container = discord.ui.Container(accent_color=EMBED_COLOR)
        container.add_item(discord.ui.TextDisplay(_step2_text(state, dropdown=dropdown)))

        # Row 0 — inside container
        row0 = discord.ui.ActionRow()
        panel_text_btn = discord.ui.Button(label="Panel Text", style=discord.ButtonStyle.primary, emoji=E_CUSTOM)
        panel_text_btn.callback = self._panel_text_cb
        row0.add_item(panel_text_btn)

        footer_media_btn = discord.ui.Button(label="Footer & Media", style=discord.ButtonStyle.primary, emoji=E_VIEW)
        footer_media_btn.callback = self._footer_media_cb
        row0.add_item(footer_media_btn)

        if not dropdown:
            button_label_btn = discord.ui.Button(label="Button Label", style=discord.ButtonStyle.secondary, emoji=E_TICKET)
            button_label_btn.callback = self._button_label_cb
            row0.add_item(button_label_btn)
        container.add_item(row0)

        # Row 0.5 — optional extra panel button (e.g. Rules/FAQ), inside container
        row_extra = discord.ui.ActionRow()
        panel_btn_btn = discord.ui.Button(label="Panel Button", style=discord.ButtonStyle.secondary, emoji=E_VIEW)
        panel_btn_btn.callback = self._panel_button_cb
        row_extra.add_item(panel_btn_btn)

        panel_btn_color_btn = discord.ui.Button(label="Panel Button Colour", style=discord.ButtonStyle.secondary, emoji=E_INFO)
        panel_btn_color_btn.callback = self._panel_button_color_cb
        row_extra.add_item(panel_btn_color_btn)
        container.add_item(row_extra)

        # Row 1 — inside container
        row1 = discord.ui.ActionRow()
        if not dropdown:
            colour_btn = discord.ui.Button(label="Button Colours", style=discord.ButtonStyle.secondary, emoji=E_INFO)
            colour_btn.callback = self._colour_cb
            row1.add_item(colour_btn)

        add_btn = discord.ui.Button(label="Add Category", style=discord.ButtonStyle.success, emoji=E_SUCCESS)
        add_btn.callback = self._add_category_cb
        row1.add_item(add_btn)

        remove_label = "Remove Category / Main Btn" if not dropdown else "Remove Category"
        remove_btn = discord.ui.Button(label=remove_label, style=discord.ButtonStyle.danger, emoji=E_DELETE)
        remove_btn.callback = self._remove_category_cb
        row1.add_item(remove_btn)
        container.add_item(row1)

        # Row 2 — inside container
        row2 = discord.ui.ActionRow()
        back_btn = discord.ui.Button(label="◀ Back", style=discord.ButtonStyle.secondary, emoji=E_REOPEN)
        back_btn.callback = self._back_cb
        row2.add_item(back_btn)

        preview_label = "Preview & Send" if dropdown else "Preview & Finish"
        preview_btn = discord.ui.Button(label=preview_label, style=discord.ButtonStyle.success, emoji=E_SUCCESS)
        preview_btn.callback = self._preview_cb
        row2.add_item(preview_btn)
        container.add_item(row2)

        self.add_item(container)

    async def _panel_text_cb(self, interaction: discord.Interaction):
        await interaction.response.send_modal(PanelTextModal(self.state))

    async def _footer_media_cb(self, interaction: discord.Interaction):
        await interaction.response.send_modal(FooterMediaModal(self.state))

    async def _button_label_cb(self, interaction: discord.Interaction):
        await interaction.response.send_modal(ButtonLabelModal(self.state))

    async def _panel_button_cb(self, interaction: discord.Interaction):
        await interaction.response.send_modal(PanelButtonModal(self.state))

    async def _panel_button_color_cb(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            view=PanelButtonColorView(self.state),
            ephemeral=True,
        )

    async def _colour_cb(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            view=AllButtonsColorView(self.state),
            ephemeral=True,
        )

    async def _add_category_cb(self, interaction: discord.Interaction):
        await interaction.response.send_modal(AddCategoryModal(self.state, dropdown=self.dropdown))

    async def _remove_category_cb(self, interaction: discord.Interaction):
        has_anything_to_remove = bool(self.state.active_categories) or (
            not self.dropdown and self.state.show_main_button
        )
        if not has_anything_to_remove:
            return await interaction.response.send_message(
                view=_err("Nothing left to remove."), ephemeral=True
            )
        # Pass the parent (step-2) message through so the select's callback
        # can refresh it after removing categories — previously the panel
        # underneath went stale and Add Category afterwards could even
        # rebuild the wrong panel type from /setup2.
        await interaction.response.send_message(
            view=DeleteCatsView(self.state, dropdown=self.dropdown, parent_message=interaction.message),
            ephemeral=True,
        )

    async def _back_cb(self, interaction: discord.Interaction):
        await interaction.response.edit_message(view=SetupStep1Layout(self.state, dropdown=self.dropdown))

    async def _preview_cb(self, interaction: discord.Interaction):
        await interaction.response.edit_message(
            view=PreviewLayout(self.state, dropdown=self.dropdown)
        )


# ── Confirm View ───────────────────────────────────────────────

class PreviewLayout(discord.ui.LayoutView):
    def __init__(self, state: SetupState, *, dropdown: bool = False):
        super().__init__(timeout=120)
        self.state    = state
        self.dropdown = dropdown

        container = discord.ui.Container(accent_color=EMBED_COLOR)
        container.add_item(discord.ui.TextDisplay(_preview_text(state, dropdown=dropdown)))

        row = discord.ui.ActionRow()
        back_btn = discord.ui.Button(label="◀ Back", style=discord.ButtonStyle.secondary, emoji=E_REOPEN)
        back_btn.callback = self._back_cb
        row.add_item(back_btn)

        finish_label = "Send Dropdown Panel" if dropdown else "Finish Setup"
        finish_btn = discord.ui.Button(label=finish_label, style=discord.ButtonStyle.success, emoji=E_SUCCESS)
        finish_btn.callback = self._finish_cb
        row.add_item(finish_btn)
        container.add_item(row)

        self.add_item(container)

    async def _back_cb(self, interaction: discord.Interaction):
        await interaction.response.edit_message(view=SetupStep2Layout(self.state, dropdown=self.dropdown))

    async def _finish_cb(self, interaction: discord.Interaction):
        s = self.state
        bot = interaction.client

        # Resolve defaults
        author_name     = s.resolved_author_name(interaction.guild)
        author_icon_url = s.resolved_author_icon(interaction.guild)
        footer_icon_url = s.resolved_footer_icon(bot)
        thumbnail_url   = s.resolved_thumbnail(interaction.guild)

        existing = get_config(interaction.guild.id) or {}
        config = {
            "support_role_id":    s.support_role.id,
            "panel_channel_id":   s.panel_channel.id,
            "ticket_category_id": s.ticket_category.id,
            "log_channel_id":     s.log_channel.id if s.log_channel else None,
            "ticket_limit":       existing.get("ticket_limit", s.ticket_limit) if self.dropdown else s.ticket_limit,
            "panel_title":        s.panel_title,
            "panel_description":  s.panel_description,
            "author_name":        author_name,
            "author_icon_url":    author_icon_url,
            "footer_text":        s.footer_text,
            "footer_icon_url":    footer_icon_url,
            "thumbnail_url":      thumbnail_url,
            "image_url":          s.image_url,
            "button_label":       existing.get("button_label", s.button_label) if self.dropdown else s.button_label,
            "button_emoji":       existing.get("button_emoji", s.button_emoji) if self.dropdown else s.button_emoji,
            "button_colors":      existing.get("button_colors", s.button_colors) if self.dropdown else s.button_colors,
            "show_main_button":   existing.get("show_main_button", s.show_main_button) if self.dropdown else s.show_main_button,
            "active_categories":  s.active_categories,
            "panel_button_label": s.panel_button_label,
            "panel_button_url":   s.panel_button_url,
            "panel_button_text":  s.panel_button_text,
            "panel_button_emoji": s.panel_button_emoji,
            "panel_button_color": s.panel_button_color,
            "form_steps":         existing.get("form_steps", {}),
        }
        set_config(interaction.guild.id, config)

        try:
            if self.dropdown:
                from cogs.tickets import TicketSelectPanel, build_panel_layout

                cats = s.active_categories
                cat_list = "\n".join(
                    f"> {CATEGORY_EMOJIS.get(c, E_QUESTION)} **{c}**"
                    for c in cats
                )
                description = f"{s.panel_description}\n\n{cat_list}"
                panel_view = build_panel_layout(
                    title=s.panel_title,
                    description=description,
                    color=EMBED_COLOR,
                    author_name=author_name,
                    author_icon_url=author_icon_url,
                    thumbnail_url=thumbnail_url,
                    image_url=s.image_url,
                    action_view=TicketSelectPanel(cats),
                    panel_button_label=s.panel_button_label,
                    panel_button_url=s.panel_button_url,
                    panel_button_text=s.panel_button_text,
                    panel_button_style=PANEL_BUTTON_COLOR_MAP.get(s.panel_button_color, discord.ButtonStyle.secondary),
                    panel_button_emoji=s.panel_button_emoji,
                )
            else:
                from cogs.tickets import TicketPanelView, build_panel_layout

                panel_view = build_panel_layout(
                    title=s.panel_title,
                    description=s.panel_description,
                    color=EMBED_COLOR,
                    author_name=author_name,
                    author_icon_url=author_icon_url,
                    thumbnail_url=thumbnail_url,
                    image_url=s.image_url,
                    action_view=TicketPanelView(
                        button_label=s.button_label,
                        button_emoji=s.button_emoji or None,
                        button_color=s.button_colors.get("main", "Blue"),
                        button_colors=s.button_colors,
                        active_categories=s.active_categories,
                        show_main_button=s.show_main_button,
                    ),
                    panel_button_label=s.panel_button_label,
                    panel_button_url=s.panel_button_url,
                    panel_button_text=s.panel_button_text,
                    panel_button_style=PANEL_BUTTON_COLOR_MAP.get(s.panel_button_color, discord.ButtonStyle.secondary),
                    panel_button_emoji=s.panel_button_emoji,
                )

            panel_ch = interaction.guild.get_channel(s.panel_channel.id)
            if panel_ch is None:
                panel_ch = await interaction.guild.fetch_channel(s.panel_channel.id)

            await panel_ch.send(view=panel_view)

            if self.dropdown:
                done_text = (
                    f"{E_SUCCESS}  **Dropdown Panel Sent**\n\n"
                    f"Your dropdown panel is live in {panel_ch.mention}.\n\n"
                    f"> {E_VIEW}  Users select a ticket type from a dropdown\n"
                    f"> {E_CUSTOM}  Use `/setform` to configure per-category forms\n"
                    f"> {E_INFO}  Use `/help` for the full command reference"
                )
            else:
                done_text = (
                    f"{E_SUCCESS}  **Setup Complete**\n\n"
                    f"Your ticket system is live in {panel_ch.mention}.\n\n"
                    f"> {E_TICKET}  Button panel sent to the panel channel\n"
                    f"> {E_VIEW}  Use `/setup2` to configure the dropdown panel\n"
                    f"> {E_CUSTOM}  Use `/setform` to configure ticket forms\n"
                    f"> {E_INFO}  Use `/help` for the full command reference"
                )
            await interaction.response.edit_message(view=_ok_raw(done_text))

        except Exception as e:
            await interaction.response.edit_message(view=_err(f"Config saved but failed to send panel: `{e}`"))



# ── Text Builders (Components V2) ──────────────────────────────

def _step1_text(*, dropdown: bool = False) -> str:
    kind = "Dropdown Panel" if dropdown else "Ticket"
    posted_as = "dropdown panel" if dropdown else "button panel"
    return (
        f"## {E_SETUP}  {kind} Setup — Step 1 of 2\n"
        f"Configure your channels and roles below.\n\n"
        f"**{E_CLAIM}  Required**\n"
        f"> **①** Support Role — who can manage tickets\n"
        f"> **②** Panel Channel — where the {posted_as} is posted\n"
        f"> **③** Ticket Category — where ticket channels open\n\n"
        f"**{E_INFO}  Optional**\n"
        f"> **④** Log Channel — where ticket events are logged\n\n"
        f"Fill in the required fields then click **Next**."
    )


def _step2_text(state: SetupState, *, dropdown: bool = False) -> str:
    cats = ", ".join(state.active_categories) or "None"
    kind = "Dropdown Panel" if dropdown else "Ticket"
    lines = [
        f"## {E_CUSTOM}  {kind} Setup — Step 2 of 2",
        "Customise your panel below.\n",
        f"> {E_CUSTOM}  **Panel Text** — title, description, author name & icon",
        f"> {E_VIEW}  **Footer & Media** — footer, thumbnail, banner",
        f"> {E_VIEW}  **Panel Button** — optional extra button (link or popup) under the panel text",
        f"> {E_INFO}  **Panel Button Colour** — colour for that extra button",
    ]
    if not dropdown:
        lines.append(f"> {E_TICKET}  **Button Label** — main button label & emoji")
        lines.append(f"> {E_INFO}  **Button Colours** — colour for every button on the panel")
    lines.append(f"> {E_SUCCESS}  **Add Category** — add a new ticket category option")
    remove_line = (
        "remove an existing category, or remove the main button" if not dropdown else "remove an existing category option"
    )
    lines.append(f"> {E_DELETE}  **Remove Category / Main Btn** — {remove_line}")
    lines.append(f"\n**Active Categories:** {cats}")
    if not dropdown:
        lines.append(f"**Main Button:** {'Shown' if state.show_main_button else 'Hidden'}")
    if state.panel_button_label:
        lines.append(f"**Panel Button:** {state.panel_button_label} ({state.panel_button_color})")
    if not dropdown:
        colors_preview = "  ".join(
            f"`{k}: {v}`" for k, v in state.button_colors.items()
            if k == "main" or k in state.active_categories
        )
        lines.append(f"**Colours:** {colors_preview or 'defaults'}")
    finish_label = "Preview & Send" if dropdown else "Preview & Finish"
    lines.append(f"\nClick **{finish_label}** when ready.")
    return "\n".join(lines)


def _preview_text(s: SetupState, *, dropdown: bool = False) -> str:
    kind = "Dropdown Panel" if dropdown else "Button Panel"
    finish_label = "Send Dropdown Panel" if dropdown else "Finish Setup"

    lines = [
        f"## {E_VIEW}  {kind} — Preview",
        f"Review your settings then click **{finish_label}**.\n",
        f"> **Panel Channel:** {s.panel_channel.mention}",
        f"> **Support Role:** {s.support_role.mention}",
        f"> **Ticket Category:** {s.ticket_category.name}",
        f"> **Log Channel:** {s.log_channel.mention if s.log_channel else 'None'}",
        f"> **Panel Title:** {s.panel_title}",
        f"> **Author Name:** {s.author_name or '(server name)'}",
        f"> **Footer Text:** {s.footer_text}",
        f"> **Thumbnail:** {f'{E_SUCCESS} Set' if s.thumbnail_url else '(server icon)'}",
        f"> **Banner Image:** {f'{E_SUCCESS} Set' if s.image_url else 'None'}",
        f"> **Active Categories:** {', '.join(s.active_categories) or 'None'}",
        f"> **Panel Button:** {f'{s.panel_button_label} ({s.panel_button_color})' if s.panel_button_label else 'None'}",
    ]
    if not dropdown:
        lines.append(f"> **Main Button:** {'Shown' if s.show_main_button else 'Hidden'}")
    if not dropdown:
        colors_text = "  ".join(
            f"`{k}: {v}`" for k, v in s.button_colors.items()
            if k == "main" or k in s.active_categories
        ) or "defaults"
        lines.append(f"> **Button Colours:** {colors_text}")
    return "\n".join(lines)


# ── Cog ───────────────────────────────────────────────────────

class SetupCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="setup", description="Configure the Linuxx Ticketing button panel")
    @app_commands.default_permissions(administrator=True)
    async def setup(self, interaction: discord.Interaction):
        existing = get_config(interaction.guild.id) or {}
        state = SetupState()
        state.show_main_button   = existing.get("show_main_button", True)
        state.panel_button_label = existing.get("panel_button_label", "")
        state.panel_button_url   = existing.get("panel_button_url", "")
        state.panel_button_text  = existing.get("panel_button_text", "")
        state.panel_button_emoji = existing.get("panel_button_emoji", "")
        state.panel_button_color = existing.get("panel_button_color", "Grey")
        await interaction.response.send_message(
            view=SetupStep1Layout(state, dropdown=False), ephemeral=True
        )

    @app_commands.command(name="setup2", description="Configure and send the dropdown ticket panel")
    @app_commands.default_permissions(administrator=True)
    async def setup2(self, interaction: discord.Interaction):
        # Pre-load existing config if available
        existing = get_config(interaction.guild.id) or {}
        state = SetupState()
        state.panel_title       = existing.get("panel_title", "Support Center")
        state.panel_description = existing.get("panel_description", "Select a ticket type from the menu below.")
        state.author_name       = existing.get("author_name", "")
        state.author_icon_url   = existing.get("author_icon_url", "")
        state.footer_text       = existing.get("footer_text", "Linuxx Ticketing")
        state.footer_icon_url   = existing.get("footer_icon_url", "")
        state.thumbnail_url     = existing.get("thumbnail_url", "")
        state.image_url         = existing.get("image_url", DEFAULT_BANNER)
        state.active_categories = existing.get("active_categories", DEFAULT_CATEGORIES[:])
        state.panel_button_label = existing.get("panel_button_label", "")
        state.panel_button_url   = existing.get("panel_button_url", "")
        state.panel_button_text  = existing.get("panel_button_text", "")
        state.panel_button_emoji = existing.get("panel_button_emoji", "")
        state.panel_button_color = existing.get("panel_button_color", "Grey")
        await interaction.response.send_message(
            view=SetupStep1Layout(state, dropdown=True), ephemeral=True
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(SetupCog(bot))
