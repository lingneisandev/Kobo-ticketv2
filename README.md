# KoboTiket

> **Developed by lingneisandevz** - Discord ID: `-`

A fully-featured Discord ticket bot built with **discord.py 2.7+** and **Python 3.10+**.  
All panels, ticket messages, and replies use Discord's **Components V2** (`LayoutView` / `Container`) - no legacy embeds.

---

## Project Structure

```
Linuxx Tickets/
 main.py                  Bot entry point
 requirements.txt         Python dependencies
 .env                     Your bot token (never share this!)
 LICENSE                  Project licence
 cogs/
    setup.py             /setup command & wizard
    tickets.py           Ticket logic, panels, buttons
 utils/
    store.py             JSON config & ticket storage
    transcript.py        HTML transcript generator
 data/                    Auto-created on first run
     configs.json
     tickets.json
```

---

## Hosting Setup Guide

### Prerequisites

| Requirement | Version |
|---|---|
| Python | 3.10 or higher |
| pip | Latest recommended |
| discord.py | 2.7+ |

---

### Option A - VPS / Dedicated Server (Linux)

This is the recommended way to host the bot 24/7.

**1. Connect to your server**
```bash
ssh user@your-server-ip
```

**2. Install Python 3.10+**
```bash
sudo apt update && sudo apt install python3 python3-pip python3-venv -y
```

**3. Upload the bot files**  
Using SCP, SFTP (FileZilla), or git clone your repository:
```bash
git clone https://github.com/youruser/linuxx-tickets.git
cd linuxx-tickets
```

**4. Create a virtual environment**
```bash
python3 -m venv venv
source venv/bin/activate
```

**5. Install dependencies**
```bash
pip install -r requirements.txt
```

**6. Configure your token**  
Open `.env` and paste your bot token:
```env
TOKEN=your_actual_bot_token_here
```
>  **Never share your `.env` file or commit it to GitHub.**

**7. Run the bot**
```bash
python main.py
```

**8. Keep it running with `screen` or `pm2`**

Using `screen` (simple):
```bash
screen -S linuxx
python main.py
# Press Ctrl+A then D to detach
```

Using `pm2` (recommended):
```bash
npm install -g pm2
pm2 start main.py --name linuxx-tickets --interpreter python3
pm2 save
pm2 startup
```

---

### Option B - Windows (Local / Home Server)

**1. Install Python 3.10+**  
Download from https://python.org - tick **"Add Python to PATH"** during install.

**2. Open a terminal in the bot folder**  
Shift + Right-click inside the folder - *Open PowerShell window here*

**3. Install dependencies**
```powershell
pip install -r requirements.txt
```

**4. Configure your token**  
Open `.env` in Notepad and fill in your bot token:
```env
TOKEN=your_actual_bot_token_here
```

**5. Run the bot**
```powershell
python main.py
```

---

### Discord Developer Portal Setup

1. Go to https://discord.com/developers/applications
2. Select your application - **Bot** tab
3. Enable these **Privileged Gateway Intents**:
   -  Server Members Intent
   -  Message Content Intent
4. Under **OAuth2 - URL Generator**, select scopes: `bot` + `applications.commands`
5. Choose permissions: `Administrator` (or configure granularly)
6. Use the generated URL to invite the bot to your server

---

### First-Time Configuration (In Discord)

Once the bot is online:

1. Run `/setup` in a channel (you need **Administrator** permission)
2. Follow the interactive wizard to configure your ticket panel
3. The bot will create a panel with a button or dropdown for users to open tickets

---

## Commands

| Command | Description | Permission |
|---|---|---|
| `/setup` | Configure a button-style ticket panel | Administrator |
| `/setup2` | Configure a dropdown-style ticket panel | Administrator |
| `/close` | Close the current ticket | Support Role |
| `/add @user` | Add a member to the ticket | Support Role |
| `/remove @user` | Remove a member from the ticket | Support Role |
| `/transcript` | Generate an HTML transcript of the ticket | Support Role |
| `/ticketinfo` | View details about the current ticket | Support Role |

---

## Features

- 2-step interactive setup wizard (button panel & dropdown panel)
- Built entirely on **Components V2** - no legacy embeds
- Fully customisable panel (title, description, author + icon, thumbnail, image)
- Custom button label, emoji & colour (Green, Blue, Grey, Yellow, Red)
- Add / remove category buttons or dropdown options from either wizard
- Claim / Close / Reopen / Delete ticket buttons
- Per-user ticket limit enforcement
- HTML transcripts DMed to users on ticket deletion
- Full log channel support (opened, claimed, closed, reopened, deleted)
- Persistent buttons - survive bot restarts
- No database required - lightweight JSON file storage

---

## Troubleshooting

**Bot not responding to `/setup`?**  
-> Make sure slash commands have synced. Restart the bot and wait up to 1 hour for Discord to propagate.

**`TOKEN not found in .env` error?**  
-> Make sure your `.env` file exists in the root folder and contains `TOKEN=your_token_here` with no spaces around `=`.

**Intents error on startup?**  
-> Enable Server Members Intent and Message Content Intent in the Discord Developer Portal.

**Buttons stop working after restart?**  
-> This bot uses persistent views  they should survive restarts. If not, ensure `main.py` is fully restarted.

---

*Linuxx Tickets - Developed by wmikon - Discord ID: `1313132336799420468`*
