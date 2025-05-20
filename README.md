# RSS Discord Bot

A Discord bot that monitors RSS feeds and posts new articles to specified Discord channels, organized by categories.

## Features

- Monitors multiple RSS feeds across different categories (Engineering, Data Analytics, Management)
- Automatically categorizes articles based on content and tags
- Posts articles to appropriate Discord channels with:
  - Article title and link
  - Source feed information
  - TL;DR summary
  - Publication date
  - ChatGPT summary link
- Uses SQLite database to track seen entries
- Scheduled runs via systemd (twice weekly)
- Configurable feed categories and channels

## Installation

1. Clone the repository:
```bash
git clone https://github.com/sugamax/rss-discord-bot.git
cd rss-discord-bot
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create a `.env` file with your Discord token:
```
DISCORD_TOKEN=your_discord_token_here
```

5. Copy `config.example.yaml` to `config.yaml` and update with your settings:
```bash
cp config.example.yaml config.yaml
```

6. Install the systemd service and timer:
```bash
sudo cp rss-bot.service rss-bot.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable rss-bot.timer
sudo systemctl start rss-bot.timer
```

## Configuration

### Discord Token
Set your Discord bot token in the `.env` file:
```
DISCORD_TOKEN=your_discord_token_here
```

### RSS Feeds
Configure your RSS feeds in `config.yaml`:
```yaml
rss_feeds:
  engineering:
    - name: "Feed Name"
      url: "https://feed-url.com/rss"
  data_analytics:
    - name: "Data Feed"
      url: "https://data-feed.com/rss"
  management:
    - name: "Management Feed"
      url: "https://management-feed.com/rss"
```

### Discord Channels
Configure your Discord channels in `config.yaml`:
```yaml
settings:
  channels:
    engineering:
      id: "your_channel_id"
    data_analytics:
      id: "your_channel_id"
    management:
      id: "your_channel_id"
```

## Usage

### Manual Run
To run the bot manually:
```bash
python rss_discord_bot.py
```

To process all entries from the start (ignoring seen entries):
```bash
python rss_discord_bot.py --from-start
```

To run for a specific category:
```bash
python rss_discord_bot.py --category engineering
```

### Systemd Service
The bot runs automatically twice a week (Tuesday and Friday at 12:15 PM Denver time) via systemd.

Check service status:
```bash
sudo systemctl status rss-bot.service
```

Check timer status:
```bash
sudo systemctl status rss-bot.timer
```

View logs:
```bash
sudo journalctl -u rss-bot.service
```

## Database

The bot uses SQLite to track seen entries. The database file is stored at the path specified in `config.yaml`:
```yaml
settings:
  db_path: "/path/to/rss_bot.db"
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Thanks to all the RSS feed providers
- Discord.py for the Discord API wrapper
- Feedparser for RSS feed parsing
- NLTK for text processing and summarization 