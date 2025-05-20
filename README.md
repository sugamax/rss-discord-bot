# RSS Discord Bot

A Discord bot that monitors RSS feeds and posts new articles to designated Discord channels, automatically categorizing them based on their content. The bot runs twice a week and posts articles from the last 7 days that haven't been posted yet.

## Features

- **Multiple Feed Categories**: Supports three main categories:
  - Engineering (software development, architecture, tech blogs)
  - Data Analytics (data engineering, data science, analytics)
  - Management (engineering management, leadership, CTO blogs)

- **Smart Categorization**: Automatically categorizes articles into subcategories using keyword matching and content analysis

- **Rich Discord Embeds**: Posts articles with:
  - Article title and link
  - Source feed name
  - TL;DR summary
  - Publication date
  - ChatGPT summary link
  - Category-based organization

- **SQLite Database**: Stores seen entries in a local SQLite database to prevent duplicate posts

- **Automated Scheduling**: Runs automatically every Tuesday and Friday at 12:15 PM Denver time

## Prerequisites

- Python 3.8 or higher
- Discord Bot Token
- Discord Server with appropriate channels
- Linux system with systemd (for automated scheduling)

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/rss-bot.git
   cd rss-bot
   ```

2. Create and activate a virtual environment (optional but recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up configuration:
   ```bash
   cp config.example.yaml config.yaml
   ```
   Edit `config.yaml` and add your Discord channel IDs and RSS feeds.

5. Set your Discord token:
   ```bash
   export DISCORD_TOKEN="your_discord_token_here"
   ```

6. Install as a systemd service:
   ```bash
   sudo ./install.sh
   ```

## Configuration

### Discord Channel Setup

1. Create three channels in your Discord server:
   - Engineering channel
   - Data Analytics channel
   - Management channel

2. Get the channel IDs and update them in `config.yaml`:
   ```yaml
   settings:
     channels:
       engineering:
         id: YOUR_ENGINEERING_CHANNEL_ID
       data_analytics:
         id: YOUR_DATA_ANALYTICS_CHANNEL_ID
       management:
         id: YOUR_MANAGEMENT_CHANNEL_ID
   ```

### RSS Feed Configuration

Add your RSS feeds to `config.yaml` under the appropriate category:

```yaml
rss_feeds:
  engineering:
    - name: "Example Engineering Blog"
      url: "https://example.com/feed"
  data_analytics:
    - name: "Example Data Blog"
      url: "https://example.com/data/feed"
  management:
    - name: "Example Management Blog"
      url: "https://example.com/management/feed"
```

## Usage

### Manual Run

To run the bot manually:

```bash
python rss_discord_bot.py
```

### Command Line Options

- `--from-start`: Process all entries from the beginning, ignoring seen entries
- `--check-now`: Run feed check immediately and exit
- `--category`: Run bot for specific category only (engineering, data_analytics, or management)

Example:
```bash
python rss_discord_bot.py --category engineering
```

### Service Management

- Check service status:
  ```bash
  systemctl status rss-bot.service
  ```

- Check timer status:
  ```bash
  systemctl status rss-bot.timer
  ```

- View logs:
  ```bash
  journalctl -u rss-bot.service
  ```

## Categories

### Engineering
- Tutorials & Guides
- Bug Fixes & Issues
- Security & Vulnerabilities
- Releases & Updates
- AI & Machine Learning
- Cloud & Infrastructure
- Databases & Storage
- Mobile Development
- Web Development
- Game Development
- Design & UX
- Architecture & Design Patterns

### Data Analytics
- Data Engineering
- Data Science
- Analytics & BI
- Machine Learning
- Artificial Intelligence
- Big Data
- Data Quality
- Data Governance
- Data Visualization

### Management
- Leadership
- Team Management
- Product Management
- Project Management
- Agile & Scrum
- Strategy
- Innovation
- Culture & Organization
- Career Development

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Thanks to all the RSS feed providers
- Discord.py for the Discord API wrapper
- Feedparser for RSS feed parsing
- NLTK for text processing and summarization 