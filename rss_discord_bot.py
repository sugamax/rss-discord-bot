import feedparser
import time
import json
import yaml
import discord
from datetime import datetime, timedelta, timezone
import logging
from pathlib import Path
import asyncio
import os
from dotenv import load_dotenv
import argparse
import re
from bs4 import BeautifulSoup
import html
import requests
from urllib.parse import urlparse
import socket
import ssl
import nltk
from nltk.tokenize import sent_tokenize, word_tokenize
from nltk.corpus import stopwords
from nltk.probability import FreqDist
from collections import defaultdict
import string
from urllib.parse import quote
import aiohttp
import sqlite3
from contextlib import contextmanager
import traceback

# Download required NLTK data
try:
    nltk.data.find('tokenizers/punkt')
except LookupError as e:
    logging.error(f"NLTK resource 'punkt' not found: {e}. Downloading...")
    nltk.download('punkt')
try:
    nltk.data.find('corpora/stopwords')
except LookupError as e:
    logging.error(f"NLTK resource 'stopwords' not found: {e}. Downloading...")
    nltk.download('stopwords')

load_dotenv()
config = yaml.safe_load(open('config.yaml'))
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s',
                   handlers=[logging.FileHandler(config['settings']['log_file']), logging.StreamHandler()])

class RSSMonitor(discord.Client):
    def __init__(self, from_start=False, target_category=None):
        intents = discord.Intents.default()
        intents.guild_messages = True
        super().__init__(intents=intents)
        self.config = yaml.safe_load(open('config.yaml'))
        logging.info(f"Loaded config: {self.config}")
        self.target_category = target_category
        self.feeds = self.config['rss_feeds']
        self.start_date = datetime.now() - timedelta(days=7)
        self.from_start = from_start
        self.channels = self.config['settings']['channels']
        logging.info(f"Channel config: {self.channels}")
        self._session = None
        self._closed = False
        
        # Initialize database first
        self._init_db()
        
        # Then load seen entries
        self.seen_entries = self.load_seen_entries()
        
        self.icons = {
            'google': '🔍',
            'microsoft': '🪟',
            'apple': '🍎',
            'amazon': '📦',
            'meta': '👥',
            'netflix': '🎬',
            'spotify': '🎵',
            'github': '💻',
            'stack': '📚',
            'medium': '📝',
            'dev.to': '👨‍💻',
            'hackernews': '📰',
            'reddit': '🔴',
            'twitter': '🐦',
            'linkedin': '💼',
            'default': '📢'
        }
        
        # Define categories based on channel type
        self.categories = {
            'engineering': {
                'tutorial': {
                    'icon': '📖',
                    'name': 'Tutorials & Guides',
                    'primary': ['tutorial', 'guide', 'how to', 'learn', 'step by step', 'hands-on'],
                    'secondary': ['example', 'demo', 'walkthrough']
                },
                'bug': {
                    'icon': '🐛',
                    'name': 'Bug Fixes & Issues',
                    'primary': ['bug fix', 'issue fix', 'problem fix', 'error fix', 'debug'],
                    'secondary': ['bug', 'issue', 'problem', 'error', 'debug']
                },
                'security': {
                    'icon': '🔒',
                    'name': 'Security & Vulnerabilities',
                    'primary': ['security', 'vulnerability', 'exploit', 'hack', 'breach', 'cyber'],
                    'secondary': ['secure', 'protect', 'defense']
                },
                'release': {
                    'icon': '🔄',
                    'name': 'Releases & Updates',
                    'primary': ['release', 'update', 'version', 'new feature', 'announcement'],
                    'secondary': ['launch', 'deploy']
                },
                'ai': {
                    'icon': '🤖',
                    'name': 'AI & Machine Learning',
                    'primary': ['artificial intelligence', 'machine learning', 'neural network', 'deep learning', 'ai model', 'ml model'],
                    'secondary': ['neural', 'deep learning', 'tensorflow', 'pytorch', 'scikit-learn']
                },
                'cloud': {
                    'icon': '☁️',
                    'name': 'Cloud & Infrastructure',
                    'primary': ['cloud', 'aws', 'azure', 'gcp', 'infrastructure', 'kubernetes', 'docker'],
                    'secondary': ['serverless', 'kubernetes', 'docker', 'container', 'microservices']
                },
                'database': {
                    'icon': '🗄️',
                    'name': 'Databases & Storage',
                    'primary': ['database', 'sql', 'nosql', 'storage', 'query', 'elasticsearch'],
                    'secondary': ['db', 'data store', 'cache', 'postgresql', 'mysql', 'mongodb']
                },
                'mobile': {
                    'icon': '📱',
                    'name': 'Mobile Development',
                    'primary': ['mobile', 'ios', 'android', 'app', 'smartphone'],
                    'secondary': ['flutter', 'react native', 'swift', 'kotlin']
                },
                'web': {
                    'icon': '🌐',
                    'name': 'Web Development',
                    'primary': ['web', 'frontend', 'backend', 'javascript', 'react', 'angular', 'application', 'development', 'engineering', 'software'],
                    'secondary': ['api', 'server', 'client', 'browser', 'programming', 'code']
                },
                'game': {
                    'icon': '🎮',
                    'name': 'Game Development',
                    'primary': ['game', 'gaming', 'unity', 'unreal', '3d'],
                    'secondary': ['game engine', 'graphics', 'physics']
                },
                'design': {
                    'icon': '🎨',
                    'name': 'Design & UX',
                    'primary': ['design', 'ui', 'ux', 'interface', 'user experience'],
                    'secondary': ['layout', 'wireframe', 'prototype']
                },
                'architecture': {
                    'icon': '🏗️',
                    'name': 'Architecture & Design Patterns',
                    'primary': ['architecture', 'architect', 'design pattern', 'system design', 'microservices', 'distributed systems', 'scalability', 'clean architecture', 'domain driven design', 'ddd'],
                    'secondary': ['pattern', 'design principles', 'best practices', 'performance', 'scaling', 'high availability', 'fault tolerance', 'resilience']
                },
                'default': {
                    'icon': '📢',
                    'name': 'Other Articles',
                    'primary': [],
                    'secondary': []
                }
            },
            'data_analytics': {
                'data_engineering': {
                    'icon': '⚙️',
                    'name': 'Data Engineering',
                    'primary': ['data engineering', 'etl', 'data pipeline', 'data warehouse', 'data modeling'],
                    'secondary': ['data ops', 'data mesh', 'data fabric']
                },
                'data_science': {
                    'icon': '🔬',
                    'name': 'Data Science',
                    'primary': ['data science', 'data mining', 'data analysis', 'statistical analysis'],
                    'secondary': ['predictive modeling', 'data scientist']
                },
                'analytics': {
                    'icon': '📊',
                    'name': 'Analytics & BI',
                    'primary': ['analytics', 'business intelligence', 'bi', 'data analytics'],
                    'secondary': ['reporting', 'metrics', 'kpis', 'insights']
                },
                'ml': {
                    'icon': '🤖',
                    'name': 'Machine Learning',
                    'primary': ['machine learning', 'ml', 'predictive analytics'],
                    'secondary': ['model training', 'model deployment']
                },
                'ai': {
                    'icon': '🧠',
                    'name': 'Artificial Intelligence',
                    'primary': ['artificial intelligence', 'ai', 'deep learning'],
                    'secondary': ['neural networks', 'cognitive computing']
                },
                'big_data': {
                    'icon': '💾',
                    'name': 'Big Data',
                    'primary': ['big data', 'data lake', 'hadoop', 'spark'],
                    'secondary': ['distributed computing', 'data processing']
                },
                'data_quality': {
                    'icon': '✅',
                    'name': 'Data Quality',
                    'primary': ['data quality', 'data testing', 'data validation'],
                    'secondary': ['data profiling', 'data monitoring']
                },
                'data_governance': {
                    'icon': '📋',
                    'name': 'Data Governance',
                    'primary': ['data governance', 'data strategy', 'data security'],
                    'secondary': ['data privacy', 'data ethics']
                },
                'data_visualization': {
                    'icon': '📈',
                    'name': 'Data Visualization',
                    'primary': ['data visualization', 'data storytelling', 'dashboard'],
                    'secondary': ['charts', 'graphs', 'reports']
                },
                'default': {
                    'icon': '📢',
                    'name': 'Other Articles',
                    'primary': [],
                    'secondary': []
                }
            },
            'management': {
                'leadership': {
                    'icon': '👑',
                    'name': 'Leadership',
                    'primary': ['leadership', 'leadership development', 'leadership skills', 'leadership style', 'leadership qualities'],
                    'secondary': ['executive', 'management style', 'leadership role', 'leadership position']
                },
                'team_management': {
                    'icon': '👥',
                    'name': 'Team Management',
                    'primary': ['team management', 'team building', 'team collaboration'],
                    'secondary': ['team leadership', 'team development']
                },
                'product_management': {
                    'icon': '📦',
                    'name': 'Product Management',
                    'primary': ['product management', 'product development', 'product strategy'],
                    'secondary': ['product innovation', 'product planning']
                },
                'project_management': {
                    'icon': '📋',
                    'name': 'Project Management',
                    'primary': ['project management', 'project planning', 'project execution'],
                    'secondary': ['project delivery', 'project methodology']
                },
                'agile': {
                    'icon': '🔄',
                    'name': 'Agile & Scrum',
                    'primary': ['agile', 'scrum', 'agile development', 'agile transformation'],
                    'secondary': ['sprint', 'kanban', 'agile methodology']
                },
                'strategy': {
                    'icon': '🎯',
                    'name': 'Strategy',
                    'primary': ['strategy', 'strategic planning', 'business strategy'],
                    'secondary': ['strategic thinking', 'strategic management']
                },
                'innovation': {
                    'icon': '💡',
                    'name': 'Innovation',
                    'primary': ['innovation', 'business innovation', 'innovation management'],
                    'secondary': ['innovative thinking', 'innovation strategy']
                },
                'culture': {
                    'icon': '🏢',
                    'name': 'Culture & Organization',
                    'primary': ['culture', 'company culture', 'organizational culture'],
                    'secondary': ['workplace culture', 'cultural transformation']
                },
                'career': {
                    'icon': '💼',
                    'name': 'Career Development',
                    'primary': ['career', 'career development', 'career growth'],
                    'secondary': ['professional development', 'career planning']
                },
                'default': {
                    'icon': '📢',
                    'name': 'Other Articles',
                    'primary': [],
                    'secondary': []
                }
            }
        }
        self._last_category = None
        self.stop_words = set(stopwords.words('english'))

    async def setup_hook(self):
        # This is called when the bot is starting up
        logging.info("Bot is starting up...")
        self._session = aiohttp.ClientSession()

    async def close(self):
        if not self._closed:
            self._closed = True
            if self._session:
                await self._session.close()
            await super().close()

    async def on_ready(self):
        logging.info(f'Bot is ready! Logged in as {self.user}')
        try:
            await self.check_all_feeds()
            await self.close()
        except Exception as e:
            logging.error(f"Error in on_ready: {str(e)}")
            await self.close()

    def get_icon(self, feed_name, title):
        # First try to match feed name
        feed_name_lower = feed_name.lower()
        for key, icon in self.icons.items():
            if key in feed_name_lower:
                return icon

        # Then try to match title keywords
        title_lower = title.lower()
        if any(word in title_lower for word in ['tutorial', 'guide', 'how to']):
            return '📖'
        elif any(word in title_lower for word in ['bug', 'fix', 'issue']):
            return '🐛'
        elif any(word in title_lower for word in ['security', 'vulnerability']):
            return '🔒'
        elif any(word in title_lower for word in ['release', 'update', 'version']):
            return '🔄'
        elif any(word in title_lower for word in ['interview', 'career']):
            return '💼'
        elif any(word in title_lower for word in ['ai', 'machine learning', 'ml']):
            return '🤖'
        elif any(word in title_lower for word in ['cloud', 'aws', 'azure', 'gcp']):
            return '☁️'
        elif any(word in title_lower for word in ['database', 'sql', 'nosql']):
            return '🗄️'
        elif any(word in title_lower for word in ['mobile', 'ios', 'android']):
            return '📱'
        elif any(word in title_lower for word in ['web', 'frontend', 'backend']):
            return '🌐'
        elif any(word in title_lower for word in ['game', 'gaming']):
            return '🎮'
        elif any(word in title_lower for word in ['design', 'ui', 'ux']):
            return '🎨'
        elif any(word in title_lower for word in ['data', 'analytics']):
            return '📊'
        elif any(word in title_lower for word in ['blockchain', 'crypto']):
            return '⛓️'
        elif any(word in title_lower for word in ['startup', 'business']):
            return '🚀'
        
        return self.icons['default']

    def get_tldr(self, entry):
        try:
            # Try to get content from different possible fields
            content = None
            if hasattr(entry, 'content'):
                content = entry.content[0].value
            elif hasattr(entry, 'summary'):
                content = entry.summary
            elif hasattr(entry, 'description'):
                content = entry.description

            if not content:
                return None

            # Clean HTML and get text
            soup = BeautifulSoup(content, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style", "meta", "link"]):
                script.decompose()
                
            # Get the main content
            text = soup.get_text()
            
            # Clean up the text
            text = ' '.join(text.split())
            
            # Remove common unwanted phrases
            unwanted_phrases = [
                "undefined", "The post", "appeared first on", "Read more",
                "Continue reading", "Click here", "Read the full article",
                "View original", "Source:", "via", "Posted by", "Published by",
                "Written by", "Share this", "Subscribe to", "Follow us",
                "Join our", "Sign up"
            ]
            
            for phrase in unwanted_phrases:
                text = text.replace(phrase, "")
                
            # Clean up any double spaces and trim
            text = ' '.join(text.split())
            
            # If text is too short, return it as is
            if len(text.split()) < 50:
                return text[:500] + "..." if len(text) > 500 else text

            try:
                # Try using NLTK's sentence tokenizer
                sentences = sent_tokenize(text)
            except LookupError:
                # Fallback to simple sentence splitting if NLTK tokenizer is not available
                sentences = [s.strip() for s in text.split('.') if s.strip()]
            
            # Calculate word frequencies
            word_frequencies = defaultdict(int)
            for sentence in sentences:
                # Simple word tokenization without NLTK
                words = sentence.lower().split()
                for word in words:
                    if word not in self.stop_words and word not in string.punctuation:
                        word_frequencies[word] += 1
            
            # Normalize word frequencies
            max_frequency = max(word_frequencies.values()) if word_frequencies else 1
            for word in word_frequencies:
                word_frequencies[word] = word_frequencies[word] / max_frequency
            
            # Score sentences based on word frequencies
            sentence_scores = defaultdict(float)
            for sentence in sentences:
                words = sentence.lower().split()
                for word in words:
                    if word in word_frequencies:
                        sentence_scores[sentence] += word_frequencies[word]
                # Normalize by sentence length
                sentence_scores[sentence] /= len(words) if words else 1
            
            # Get top 3 sentences
            top_sentences = sorted(sentence_scores.items(), key=lambda x: x[1], reverse=True)[:3]
            summary = ' '.join(sentence for sentence, score in sorted(top_sentences, key=lambda x: sentences.index(x[0])))
            
            # Limit to 30 words
            words = summary.split()
            if len(words) > 30:
                return ' '.join(words[:30]) + '...'
            return summary
                
        except Exception as e:
            logging.error(f"Error in get_tldr: {str(e)}")
            # Fallback to simple extraction
            try:
                words = text.split()
                return ' '.join(words[:30]) + '...'
            except:
                return None

    @contextmanager
    def _get_db(self):
        """Context manager for database connections."""
        db_path = self.config['settings'].get('db_path', 'rss_bot.db')
        conn = None
        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            yield conn, conn.cursor()
        except Exception as e:
            logging.error(f"Database connection error: {str(e)}")
            raise
        finally:
            if conn:
                conn.close()

    def _init_db(self):
        """Initialize the SQLite database."""
        db_path = self.config['settings'].get('db_path', 'rss_bot.db')
        logging.info(f"Initializing database at: {db_path}")
        
        # Ensure the parent directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        logging.info(f"Ensured directory exists for database")
        
        # Create a direct connection for initialization
        conn = None
        try:
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            
            # Create the table if it doesn't exist
            cur.execute('''
                CREATE TABLE IF NOT EXISTS seen_entries (
                    feed_name TEXT,
                    entry_id TEXT,
                    seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (feed_name, entry_id)
                )
            ''')
            conn.commit()
            
            # Verify table exists
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='seen_entries'")
            if not cur.fetchone():
                raise Exception("Failed to create seen_entries table")
                
            logging.info("Database initialized successfully")
            
        except Exception as e:
            logging.error(f"Error initializing database: {str(e)}")
            raise
        finally:
            if conn:
                conn.close()

    def load_seen_entries(self):
        """Load seen entries from SQLite database."""
        seen_entries = defaultdict(list)
        try:
            with self._get_db() as (conn, cur):
                cur.execute('SELECT feed_name, entry_id FROM seen_entries')
                rows = cur.fetchall()
                logging.info(f"Loaded {len(rows)} seen entries from database")
                for feed_name, entry_id in rows:
                    seen_entries[feed_name].append(entry_id)
            return seen_entries
        except Exception as e:
            logging.error(f"Error loading seen entries: {str(e)}")
            return defaultdict(list)

    def save_seen_entries(self):
        """Save seen entries to SQLite database."""
        try:
            with self._get_db() as (conn, cur):
                # Get all current entries
                cur.execute('SELECT feed_name, entry_id FROM seen_entries')
                existing_entries = {(feed_name, entry_id) for feed_name, entry_id in cur.fetchall()}
                
                # Prepare new entries to insert
                new_entries = []
                for feed_name, entries in self.seen_entries.items():
                    for entry_id in entries:
                        if (feed_name, entry_id) not in existing_entries:
                            new_entries.append((feed_name, entry_id))
                
                # Insert new entries
                if new_entries:
                    cur.executemany(
                        'INSERT OR IGNORE INTO seen_entries (feed_name, entry_id) VALUES (?, ?)',
                        new_entries
                    )
                    conn.commit()
                    logging.info(f"Saved {len(new_entries)} new entries to database")
                    
                    # Verify the entries were saved
                    cur.execute('SELECT COUNT(*) FROM seen_entries')
                    total_entries = cur.fetchone()[0]
                    logging.info(f"Total entries in database: {total_entries}")
        except Exception as e:
            logging.error(f"Error saving seen entries: {str(e)}")

    def is_entry_new(self, feed_name, entry):
        """Check if an entry is new by querying the database."""
        entry_id = entry.get('id', entry.get('link', ''))
        
        if not entry_id:
            logging.warning(f"No entry ID found for entry from {feed_name}")
            return True
            
        if self.from_start:
            return True
            
        try:
            with self._get_db() as (conn, cur):
                # Check if entry exists in database
                cur.execute('SELECT 1 FROM seen_entries WHERE feed_name = ? AND entry_id = ?', (feed_name, entry_id))
                return cur.fetchone() is None
        except Exception as e:
            logging.error(f"Error checking if entry is new: {str(e)}")
            return True  # If there's an error, treat it as new

    def is_entry_recent(self, entry):
        try:
            # Get feed name for better error reporting
            feed_name = getattr(entry, 'feed', {}).get('title', 'Unknown')
            entry_title = entry.get('title', 'Unknown')

            # List of possible date fields to check
            date_fields = [
                'published_parsed',
                'updated_parsed',
                'created_parsed',
                'modified_parsed',
                'date_parsed',
                'pubDate_parsed',
                'dc:date_parsed',
                'dc:created_parsed',
                'dc:modified_parsed'
            ]
            
            # Try parsed date fields first
            for field in date_fields:
                if hasattr(entry, field):
                    try:
                        date_tuple = getattr(entry, field)
                        if date_tuple:
                            published = datetime(*date_tuple[:6])
                            # Check if the date is within 7 days before current date
                            now = datetime.now()
                            time_diff = (now - published).total_seconds()
                            return time_diff <= (7 * 24 * 60 * 60)  # 7 days in seconds
                    except (TypeError, ValueError) as e:
                        logging.debug(f"Could not parse {field} for entry '{entry_title}' from feed '{feed_name}': {str(e)}")
                        continue

            # If no parsed date found, try string date fields
            date_string_fields = [
                'published',
                'updated',
                'created',
                'modified',
                'date',
                'pubDate',
                'dc:date',
                'dc:created',
                'dc:modified'
            ]
            
            # Common date formats to try
            date_formats = [
                '%Y-%m-%dT%H:%M:%S%z',  # ISO 8601 with timezone
                '%Y-%m-%dT%H:%M:%S',    # ISO 8601 without timezone
                '%a, %d %b %Y %H:%M:%S %z',  # RFC 822 with timezone
                '%a, %d %b %Y %H:%M:%S',     # RFC 822 without timezone
                '%Y-%m-%d %H:%M:%S%z',       # Custom with timezone
                '%Y-%m-%d %H:%M:%S',         # Custom without timezone
                '%d %b %Y %H:%M:%S %z',      # Alternative format with timezone
                '%d %b %Y %H:%M:%S',         # Alternative format without timezone
                '%Y-%m-%d'                   # Just date
            ]

            for field in date_string_fields:
                date_str = getattr(entry, field, None)
                if date_str:
                    for date_format in date_formats:
                        try:
                            published = datetime.strptime(date_str, date_format)
                            # If timezone info is missing, assume UTC
                            if published.tzinfo is None:
                                published = published.replace(tzinfo=timezone.utc)
                            # Check if the date is within 7 days before current date
                            now = datetime.now(published.tzinfo)
                            time_diff = (now - published).total_seconds()
                            return time_diff <= (7 * 24 * 60 * 60)  # 7 days in seconds
                        except ValueError:
                            continue

            # If still no date found, try to extract date from entry ID or link
            if hasattr(entry, 'id'):
                # Some feeds include date in their IDs
                id_date_match = re.search(r'(\d{4}[-/]\d{2}[-/]\d{2})', entry.id)
                if id_date_match:
                    try:
                        date_str = id_date_match.group(1)
                        published = datetime.strptime(date_str, '%Y-%m-%d')
                        # Check if the date is within 7 days before current date
                        now = datetime.now()
                        time_diff = (now - published).total_seconds()
                        return time_diff <= (7 * 24 * 60 * 60)  # 7 days in seconds
                    except ValueError:
                        pass

            # If no date found at all, dump the full entry data as JSON
            entry_data = {}
            for key in dir(entry):
                if not key.startswith('_'):  # Skip internal attributes
                    try:
                        value = getattr(entry, key)
                        # Convert to string if it's not JSON serializable
                        if not isinstance(value, (str, int, float, bool, list, dict, type(None))):
                            value = str(value)
                        entry_data[key] = value
                    except Exception as e:
                        entry_data[key] = f"<Error getting value: {str(e)}>"
            
            logging.warning(f"No date found for entry '{entry_title}' from feed '{feed_name}'")
            logging.warning("Full entry data:")
            logging.warning(json.dumps(entry_data, indent=2))
            return False

        except Exception as e:
            logging.error(f"Error parsing date for entry '{entry.get('title', 'Unknown')}' from feed '{getattr(entry, 'feed', {}).get('title', 'Unknown')}': {str(e)}")
            return False

    def get_category(self, feed_name, title, content, entry):
        # If the target category is management, always return 'default'
        if self.target_category == 'management':
            return 'default'
        
        # First try to get category from feed tags
        if hasattr(entry, 'tags'):
            # Map common tag names to our categories based on channel type
            tag_mapping = {
                'engineering': {
                    'go': 'web',
                    'golang': 'web',
                    'python': 'web',
                    'javascript': 'web',
                    'java': 'web',
                    'ruby': 'web',
                    'php': 'web',
                    'rust': 'web',
                    'c++': 'web',
                    'c#': 'web',
                    'dotnet': 'web',
                    'node': 'web',
                    'react': 'web',
                    'angular': 'web',
                    'vue': 'web',
                    'django': 'web',
                    'flask': 'web',
                    'spring': 'web',
                    'rails': 'web',
                    'laravel': 'web',
                    'express': 'web',
                    'nextjs': 'web',
                    'nuxt': 'web',
                    'svelte': 'web',
                    'typescript': 'web',
                    'swift': 'mobile',
                    'kotlin': 'mobile',
                    'android': 'mobile',
                    'ios': 'mobile',
                    'flutter': 'mobile',
                    'reactnative': 'mobile',
                    'xamarin': 'mobile',
                    'unity': 'game',
                    'unreal': 'game',
                    'godot': 'game',
                    'gamedev': 'game',
                    'gaming': 'game',
                    'ai': 'ai',
                    'machine-learning': 'ai',
                    'ml': 'ai',
                    'artificial-intelligence': 'ai',
                    'deep-learning': 'ai',
                    'neural-networks': 'ai',
                    'tensorflow': 'ai',
                    'pytorch': 'ai',
                    'cloud': 'cloud',
                    'aws': 'cloud',
                    'azure': 'cloud',
                    'gcp': 'cloud',
                    'kubernetes': 'cloud',
                    'docker': 'cloud',
                    'devops': 'cloud',
                    'database': 'database',
                    'sql': 'database',
                    'nosql': 'database',
                    'mongodb': 'database',
                    'postgresql': 'database',
                    'mysql': 'database',
                    'redis': 'database',
                    'security': 'security',
                    'cybersecurity': 'security',
                    'hacking': 'security',
                    'privacy': 'security',
                    'design': 'design',
                    'ui': 'design',
                    'ux': 'design',
                    'frontend': 'design',
                    'css': 'design',
                    'html': 'design',
                    'tutorial': 'tutorial',
                    'how-to': 'tutorial',
                    'guide': 'tutorial',
                    'learning': 'tutorial',
                    'application': 'web',
                    'app': 'web',
                    'development': 'web',
                    'developer': 'web',
                    'engineering': 'web',
                    'software': 'web',
                    'programming': 'web',
                    'code': 'web',
                    'architecture': 'architecture',
                    'architect': 'architecture',
                    'design-pattern': 'architecture',
                    'design-patterns': 'architecture',
                    'system-design': 'architecture',
                    'microservices': 'architecture',
                    'distributed-systems': 'architecture',
                    'scalability': 'architecture',
                    'performance': 'architecture',
                    'clean-code': 'architecture',
                    'clean-architecture': 'architecture',
                    'ddd': 'architecture',
                    'domain-driven-design': 'architecture'
                },
                'data_analytics': {
                    'data-engineering': 'data_engineering',
                    'data-science': 'data_science',
                    'analytics': 'analytics',
                    'bi': 'analytics',
                    'business-intelligence': 'analytics',
                    'machine-learning': 'ml',
                    'ml': 'ml',
                    'artificial-intelligence': 'ai',
                    'ai': 'ai',
                    'big-data': 'big_data',
                    'data-quality': 'data_quality',
                    'data-governance': 'data_governance',
                    'data-visualization': 'data_visualization',
                    'etl': 'data_engineering',
                    'data-pipeline': 'data_engineering',
                    'data-warehouse': 'data_engineering',
                    'data-lake': 'big_data',
                    'data-modeling': 'data_engineering',
                    'data-architecture': 'data_engineering',
                    'data-strategy': 'data_governance',
                    'data-security': 'data_governance',
                    'data-privacy': 'data_governance',
                    'data-ethics': 'data_governance',
                    'data-ops': 'data_engineering',
                    'data-mesh': 'data_architecture',
                    'data-fabric': 'data_architecture',
                    'data-catalog': 'data_governance',
                    'data-lineage': 'data_governance',
                    'data-observability': 'data_quality',
                    'data-testing': 'data_quality',
                    'data-validation': 'data_quality',
                    'data-profiling': 'data_quality',
                    'data-monitoring': 'data_quality',
                    'data-analytics': 'analytics',
                    'data-visualization': 'data_visualization',
                    'data-storytelling': 'data_visualization',
                    'data-dashboard': 'data_visualization',
                    'data-reporting': 'analytics',
                    'data-metrics': 'analytics',
                    'data-kpis': 'analytics',
                    'data-insights': 'analytics',
                    'data-discovery': 'analytics',
                    'data-exploration': 'analytics',
                    'data-mining': 'data_science',
                    'data-analysis': 'data_science',
                    'data-science': 'data_science',
                    'data-scientist': 'data_science',
                    'data-engineer': 'data_engineering',
                    'data-analyst': 'analytics',
                    'data-architect': 'data_architecture',
                    'data-governance': 'data_governance',
                    'data-quality': 'data_quality',
                    'data-visualization': 'data_visualization'
                },
                'management': {
                    'leadership': {
                        'primary': ['leadership', 'leadership development', 'leadership skills', 'leadership style', 'leadership qualities'],
                        'secondary': ['executive', 'management style', 'leadership role', 'leadership position'],
                        'exclude': ['engineering', 'technical', 'software', 'development', 'kubernetes', 'container', 'cloud', 'infrastructure']
                    },
                    'team_management': {
                        'primary': ['team management', 'team building', 'team collaboration'],
                        'secondary': ['team leadership', 'team development']
                    },
                    'product_management': {
                        'primary': ['product management', 'product development', 'product strategy'],
                        'secondary': ['product innovation', 'product planning']
                    },
                    'project_management': {
                        'primary': ['project management', 'project planning', 'project execution'],
                        'secondary': ['project delivery', 'project methodology']
                    },
                    'agile': {
                        'primary': ['agile', 'scrum', 'agile development', 'agile transformation'],
                        'secondary': ['sprint', 'kanban', 'agile methodology']
                    },
                    'strategy': {
                        'primary': ['strategy', 'strategic planning', 'business strategy'],
                        'secondary': ['strategic thinking', 'strategic management']
                    },
                    'innovation': {
                        'primary': ['innovation', 'business innovation', 'innovation management'],
                        'secondary': ['innovative thinking', 'innovation strategy']
                    },
                    'culture': {
                        'primary': ['culture', 'company culture', 'organizational culture'],
                        'secondary': ['workplace culture', 'cultural transformation']
                    },
                    'career': {
                        'primary': ['career', 'career development', 'career growth'],
                        'secondary': ['professional development', 'career planning']
                    }
                }
            }
            
            # Get the appropriate tag mapping based on the target category
            channel_type = self.target_category or 'engineering'
            current_tag_mapping = tag_mapping.get(channel_type, tag_mapping['engineering'])
            
            # Check each tag
            for tag in entry.tags:
                # Handle both regular tags and CDATA tags
                tag_term = tag.get('term', '').lower()
                if not tag_term and hasattr(tag, 'text'):
                    tag_term = tag.text.lower()
                
                # Clean up the tag term
                tag_term = tag_term.strip()
                if tag_term.startswith('cdata[') and tag_term.endswith(']'):
                    tag_term = tag_term[6:-1].strip()
                
                if tag_term in current_tag_mapping:
                    return current_tag_mapping[tag_term]
                
                # Try splitting compound tags (e.g., "Web Development" -> ["web", "development"])
                for word in tag_term.split():
                    if word in current_tag_mapping:
                        return current_tag_mapping[word]
        
        # If no tags found or no matching tags, fall back to keyword-based categorization
        text = f"{feed_name} {title} {content}".lower()
        
        # Define keywords for each category based on channel type
        keywords = {
            'engineering': {
                'tutorial': {
                    'primary': ['tutorial', 'guide', 'how to', 'learn', 'step by step', 'hands-on'],
                    'secondary': ['example', 'demo', 'walkthrough']
                },
                'bug': {
                    'primary': ['bug fix', 'issue fix', 'problem fix', 'error fix', 'debug'],
                    'secondary': ['bug', 'issue', 'problem', 'error', 'debug']
                },
                'security': {
                    'primary': ['security', 'vulnerability', 'exploit', 'hack', 'breach', 'cyber'],
                    'secondary': ['secure', 'protect', 'defense']
                },
                'release': {
                    'primary': ['release', 'update', 'version', 'new feature', 'announcement'],
                    'secondary': ['launch', 'deploy']
                },
                'ai': {
                    'primary': ['artificial intelligence', 'machine learning', 'neural network', 'deep learning'],
                    'secondary': ['ai model', 'ml model', 'neural', 'deep learning']
                },
                'cloud': {
                    'primary': ['cloud', 'aws', 'azure', 'gcp', 'infrastructure'],
                    'secondary': ['serverless', 'kubernetes', 'docker']
                },
                'database': {
                    'primary': ['database', 'sql', 'nosql', 'storage', 'query', 'elasticsearch'],
                    'secondary': ['db', 'data store', 'cache'],
                    'exclude': ['search', 'application', 'development', 'engineering', 'software']
                },
                'mobile': {
                    'primary': ['mobile', 'ios', 'android', 'app', 'smartphone'],
                    'secondary': ['flutter', 'react native', 'swift', 'kotlin']
                },
                'web': {
                    'primary': ['web', 'frontend', 'backend', 'javascript', 'react', 'angular', 'application', 'development', 'engineering', 'software'],
                    'secondary': ['api', 'server', 'client', 'browser', 'programming', 'code']
                },
                'game': {
                    'primary': ['game', 'gaming', 'unity', 'unreal', '3d'],
                    'secondary': ['game engine', 'graphics', 'physics']
                },
                'design': {
                    'primary': ['design', 'ui', 'ux', 'interface', 'user experience'],
                    'secondary': ['layout', 'wireframe', 'prototype']
                },
                'architecture': {
                    'primary': ['architecture', 'architect', 'design pattern', 'system design', 'microservices', 'distributed systems', 'scalability', 'clean architecture', 'domain driven design', 'ddd'],
                    'secondary': ['pattern', 'design principles', 'best practices', 'performance', 'scaling', 'high availability', 'fault tolerance', 'resilience']
                }
            },
            'data_analytics': {
                'data_engineering': {
                    'primary': ['data engineering', 'etl', 'data pipeline', 'data warehouse', 'data modeling'],
                    'secondary': ['data ops', 'data mesh', 'data fabric']
                },
                'data_science': {
                    'primary': ['data science', 'data mining', 'data analysis', 'statistical analysis'],
                    'secondary': ['predictive modeling', 'data scientist']
                },
                'analytics': {
                    'primary': ['analytics', 'business intelligence', 'bi', 'data analytics'],
                    'secondary': ['reporting', 'metrics', 'kpis', 'insights']
                },
                'ml': {
                    'primary': ['machine learning', 'ml', 'predictive analytics'],
                    'secondary': ['model training', 'model deployment']
                },
                'ai': {
                    'primary': ['artificial intelligence', 'ai', 'deep learning'],
                    'secondary': ['neural networks', 'cognitive computing']
                },
                'big_data': {
                    'primary': ['big data', 'data lake', 'hadoop', 'spark'],
                    'secondary': ['distributed computing', 'data processing']
                },
                'data_quality': {
                    'primary': ['data quality', 'data testing', 'data validation'],
                    'secondary': ['data profiling', 'data monitoring']
                },
                'data_governance': {
                    'primary': ['data governance', 'data strategy', 'data security'],
                    'secondary': ['data privacy', 'data ethics']
                },
                'data_visualization': {
                    'primary': ['data visualization', 'data storytelling', 'dashboard'],
                    'secondary': ['charts', 'graphs', 'reports']
                }
            },
            'management': {
                'leadership': {
                    'primary': ['leadership', 'leadership development', 'leadership skills', 'leadership style', 'leadership qualities'],
                    'secondary': ['executive', 'management style', 'leadership role', 'leadership position'],
                    'exclude': ['engineering', 'technical', 'software', 'development', 'kubernetes', 'container', 'cloud', 'infrastructure']
                },
                'team_management': {
                    'primary': ['team management', 'team building', 'team collaboration'],
                    'secondary': ['team leadership', 'team development']
                },
                'product_management': {
                    'primary': ['product management', 'product development', 'product strategy'],
                    'secondary': ['product innovation', 'product planning']
                },
                'project_management': {
                    'primary': ['project management', 'project planning', 'project execution'],
                    'secondary': ['project delivery', 'project methodology']
                },
                'agile': {
                    'primary': ['agile', 'scrum', 'agile development', 'agile transformation'],
                    'secondary': ['sprint', 'kanban', 'agile methodology']
                },
                'strategy': {
                    'primary': ['strategy', 'strategic planning', 'business strategy'],
                    'secondary': ['strategic thinking', 'strategic management']
                },
                'innovation': {
                    'primary': ['innovation', 'business innovation', 'innovation management'],
                    'secondary': ['innovative thinking', 'innovation strategy']
                },
                'culture': {
                    'primary': ['culture', 'company culture', 'organizational culture'],
                    'secondary': ['workplace culture', 'cultural transformation']
                },
                'career': {
                    'primary': ['career', 'career development', 'career growth'],
                    'secondary': ['professional development', 'career planning']
                }
            }
        }
        
        # Get the appropriate keywords based on the target category
        channel_type = self.target_category or 'engineering'
        current_keywords = keywords.get(channel_type, keywords['engineering'])
        
        # Score each category
        category_scores = {}
        for category, keyword_sets in current_keywords.items():
            if category == 'default':
                continue
                
            score = 0
            # Check primary keywords (higher weight)
            for keyword in keyword_sets['primary']:
                if keyword in text:
                    score += 2
            # Check secondary keywords (lower weight)
            for keyword in keyword_sets['secondary']:
                if keyword in text:
                    score += 1
                    
            # Apply exclusion rules
            if 'exclude' in keyword_sets:
                for keyword in keyword_sets['exclude']:
                    if keyword in text:
                        score = 0
                        break
                    
            category_scores[category] = score
        
        # Get the category with the highest score
        if category_scores:
            max_score = max(category_scores.values())
            if max_score > 0:
                # Get all categories with the max score
                top_categories = [cat for cat, score in category_scores.items() if score == max_score]
                # If there's a tie, prefer certain categories based on channel type
                if channel_type == 'engineering':
                    priority_order = ['tutorial', 'web', 'cloud', 'database', 'ai', 'security', 'release', 'bug', 
                                    'mobile', 'game', 'design', 'architecture']
                elif channel_type == 'data_analytics':
                    priority_order = ['data_engineering', 'data_science', 'analytics', 'ml', 'ai', 'big_data',
                                    'data_quality', 'data_governance', 'data_visualization']
                else:  # management
                    priority_order = ['leadership', 'team_management', 'product_management', 'project_management',
                                    'agile', 'strategy', 'innovation', 'culture', 'career']
                
                for category in priority_order:
                    if category in top_categories:
                        return category
                
        return 'default'

    async def send_category_header(self, channel, category):
        if not hasattr(self, '_last_category') or self._last_category != category:
            # Create a more prominent header
            header_text = f"# {self.categories[category]['icon']} {self.categories[category]['name']}"
            embed = discord.Embed(
                title=header_text,
                color=discord.Color.blue()
            )
            
            await channel.send(embed=embed)
            self._last_category = category
            await asyncio.sleep(1)  # Small delay after header

    async def send_category_section(self, channel, category, entries, include_date=None):
        if not entries:
            return

        # Ensure the category exists in the current channel type
        channel_type = self.target_category or 'engineering'
        if category not in self.categories[channel_type]:
            logging.warning(f"Category '{category}' not found in {channel_type} channel type, using 'default'")
            category = 'default'

        # Create the category header
        header_text = f"# {self.categories[channel_type][category]['icon']} {self.categories[channel_type][category]['name']}"
        if include_date:
            header_text = f"📅 {include_date}\n\n{header_text}"
            
        embed = discord.Embed(
            title=header_text,
            color=discord.Color.blue()
        )
        embed.description = "\n\n"

        # Add all entries for this category
        for feed_name, entry in entries:
            icon = self.get_icon(feed_name, entry.title)
            tldr = self.get_tldr(entry)
            
            # Format the entry
            entry_text = f"**{icon} [{entry.title}]({entry.link})**\n"
            entry_text += f"*From: {feed_name}*\n"
            
            if tldr:
                entry_text += f"\n{tldr}\n"
            
            try:
                published = datetime(*entry.published_parsed[:6])
                entry_text += f"\n*Published: {published.strftime('%Y-%m-%d %H:%M:%S')}*\n"
            except (AttributeError, TypeError):
                pass
            
            # Add ChatGPT link
            prompt = f"Please summarize this article in approximately 100 words and add key learning points: {entry.title} - {entry.link}"
            encoded_prompt = quote(prompt)
            chatgpt_url = f"https://chat.openai.com?prompt={encoded_prompt}"
            entry_text += f"\n[🤖 Ask ChatGPT to summarize this article]({chatgpt_url})\n"
            
            # Add divider between entries
            entry_text += "\n" + "•" * 3 + "\n\n"
            
            # Add to embed if it fits, otherwise send current embed and start a new one
            if len(embed.description) + len(entry_text) > 4000:  # Discord's limit
                try:
                    await asyncio.wait_for(channel.send(embed=embed), timeout=1.0)
                except asyncio.TimeoutError:
                    logging.error(f"Timeout while sending message to channel {channel.id}")
                except Exception as e:
                    logging.error(f"Error sending message to channel {channel.id}: {str(e)}")
                    
                embed = discord.Embed(
                    title=header_text,
                    color=discord.Color.blue()
                )
                embed.description = "\n\n"  # Just add some spacing
            
            embed.description += entry_text

        # Send the final embed for this category
        try:
            await asyncio.wait_for(channel.send(embed=embed), timeout=1.0)
        except asyncio.TimeoutError:
            logging.error(f"Timeout while sending final message to channel {channel.id}")
        except Exception as e:
            logging.error(f"Error sending final message to channel {channel.id}: {str(e)}")

    async def fetch_feed(self, feed_url):
        try:
            headers = {
                'User-Agent': 'curl/8.5.0',
                'Accept': '*/*'
            }
            
            # Use aiohttp session if available
            if self._session and not self._closed:
                try:
                    async with self._session.get(feed_url, headers=headers, timeout=20, allow_redirects=True) as response:
                        response.raise_for_status()
                        content = await response.read()
                        content_type = response.headers.get('content-type', '').lower()
                        if not any(xml_type in content_type for xml_type in ['xml', 'rss', 'atom']):
                            logging.warning(f"Response from {feed_url} doesn't appear to be an RSS feed (content-type: {content_type})")
                            return None
                        logging.info(f"Feed response from {feed_url}:\n{content[:500]}...")  # Show first 500 chars
                        return feedparser.parse(content)
                except Exception as e:
                    logging.warning(f"Failed to fetch {feed_url} with aiohttp: {str(e)}")
                    # Fall through to requests

            # Fallback to requests
            response = requests.get(feed_url, timeout=20, headers=headers, verify=True, allow_redirects=True)
            response.raise_for_status()
            
            content_type = response.headers.get('content-type', '').lower()
            if not any(xml_type in content_type for xml_type in ['xml', 'rss', 'atom']):
                logging.warning(f"Response from {feed_url} doesn't appear to be an RSS feed (content-type: {content_type})")
                return None
                
            return feedparser.parse(response.content)
        except (requests.RequestException, socket.gaierror) as e:
            logging.warning(f"Failed to fetch {feed_url} with requests: {str(e)}")
            try:
                # Fallback to feedparser's direct parsing with a timeout
                return feedparser.parse(feed_url, agent=headers['User-Agent'])
            except Exception as e:
                logging.error(f"Failed to parse feed {feed_url}: {str(e)}")
                return None
        except Exception as e:
            logging.error(f"Unexpected error fetching feed {feed_url}: {str(e)}")
            return None

    def get_category_order(self, channel_type):
        """Get the ordered list of categories for a channel type."""
        if channel_type == 'engineering':
            return [
                'tutorial', 'web', 'cloud', 'database', 'ai', 'security', 'release', 'bug',
                'mobile', 'game', 'design', 'architecture', 'data', 'default'
            ]
        elif channel_type == 'data_analytics':
            return [
                'data_engineering', 'data_science', 'analytics', 'ml', 'ai', 'big_data',
                'data_quality', 'data_governance', 'data_visualization', 'default'
            ]
        else:  # management
            return [
                'leadership', 'team_management', 'product_management', 'project_management',
                'agile', 'strategy', 'innovation', 'culture', 'career', 'default'
            ]

    async def check_all_feeds(self):
        """Check all feeds for new entries"""
        try:
            await self._init_session()
            
            # Get the categories to process
            categories_to_process = [self.target_category] if self.target_category else self.feeds.keys()
            logging.info(f"Processing categories: {categories_to_process}")
            
            for channel_type in categories_to_process:
                if channel_type not in self.feeds:
                    logging.error(f"Category '{channel_type}' not found in feeds configuration")
                    continue
                    
                # Get channel for this category
                if channel_type not in self.channels:
                    logging.error(f"No channel configuration found for {channel_type}")
                    continue
                    
                channel_id = self.channels[channel_type]['id']
                channel = self.get_channel(int(channel_id))
                if not channel:
                    logging.error(f"Could not find channel with ID {channel_id}")
                    continue
                
                logging.info(f"Processing channel: {channel_type} (ID: {channel_id})")
                
                # Dictionary to store entries by feed source
                feed_entries = defaultdict(list)
                
                # Process each feed in this category
                for feed in self.feeds[channel_type]:
                    if isinstance(feed, dict) and 'name' in feed and 'url' in feed:
                        logging.info(f"Fetching feed: {feed['name']} ({feed['url']})")
                        try:
                            headers = {
                                'User-Agent': 'curl/8.5.0',
                                'Accept': '*/*'
                            }
                            async with self._session.get(feed['url'], headers=headers, timeout=10) as response:
                                logging.info(f"Response status for {feed['name']}: {response.status}")
                                logging.info(f"Response headers for {feed['name']}: {dict(response.headers)}")
                                if response.status == 200:
                                    content = await response.text()
                                    logging.info(f"Feed response from {feed['name']}:\n{content[:500]}...")  # Show first 500 chars
                                    feed_data = feedparser.parse(content)
                                    
                                    if not feed_data.entries:
                                        logging.warning(f"No entries found in feed: {feed['name']}")
                                        continue
                                        
                                    logging.info(f"Processing {len(feed_data.entries)} entries from {feed['name']}")
                                    
                                    for entry in feed_data.entries:
                                        if self.is_entry_new(feed['name'], entry) and self.is_entry_recent(entry):
                                            logging.info(f"New entry found in {feed['name']}: {entry.get('title', 'No title')}")
                                            feed_entries[feed['name']].append(entry)
                                            # Save to seen entries
                                            self.seen_entries[feed['name']].append(entry.get('id', entry.get('link', '')))
                                            self.save_seen_entries()
                                else:
                                    logging.error(f"Failed to fetch {feed['name']}: HTTP {response.status}")
                                            
                        except asyncio.TimeoutError:
                            logging.error(f"Timeout while fetching feed {feed['name']}")
                        except Exception as e:
                            logging.error(f"Error checking feed {feed['name']}: {str(e)}")
                            import traceback
                            logging.error(f"Stack trace:\n{traceback.format_exc()}")
                
                # Only send header and process entries if there are new entries
                if feed_entries:
                    logging.info(f"Found new entries for {channel_type}: {sum(len(entries) for entries in feed_entries.values())} total entries")
                    # Send date header for this channel
                    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    header_embed = discord.Embed(
                        title="📅 New tech blog posts are here!",
                        description=f"*Posted on {current_time}*",
                        color=discord.Color.blue()
                    )
                    try:
                        await asyncio.wait_for(channel.send(embed=header_embed), timeout=1.0)
                        await asyncio.sleep(1)  # Small delay after header
                    except asyncio.TimeoutError:
                        logging.error(f"Timeout while sending header to channel {channel.id}")
                    except Exception as e:
                        logging.error(f"Error sending header to channel {channel.id}: {str(e)}")
                    
                    # Send entries grouped by feed source in batches of 4
                    for feed_name, entries in feed_entries.items():
                        if entries:
                            logging.info(f"Sending {len(entries)} entries from {feed_name}")
                            # Process entries in batches of 4
                            for i in range(0, len(entries), 4):
                                batch = entries[i:i+4]
                                logging.info(f"Sending batch {i//4 + 1} of {(len(entries) + 3)//4} for {feed_name}")
                                
                                # Create feed header and batch message
                                embed = discord.Embed(
                                    title=f"📰 {feed_name}",
                                    color=discord.Color.blue()
                                )
                                
                                # Add entries to the embed
                                for entry in batch:
                                    icon = self.get_icon(feed_name, entry.title)
                                    tldr = self.get_tldr(entry)
                                    
                                    # Format the entry
                                    entry_text = f"**{icon} [{entry.title}]({entry.link})**\n"
                                    
                                    if tldr:
                                        entry_text += f"{tldr}\n"
                                    
                                    try:
                                        published = datetime(*entry.published_parsed[:6])
                                        entry_text += f"*Published: {published.strftime('%Y-%m-%d %H:%M:%S')}*\n"
                                    except (AttributeError, TypeError):
                                        pass

                                    # Add ChatGPT link
                                    prompt = f"Please summarize this article in approximately 100 words and add key learning points: {entry.title} - {entry.link}"
                                    encoded_prompt = quote(prompt)
                                    chatgpt_url = f"https://chat.openai.com?prompt={encoded_prompt}"
                                    entry_text += f"[🤖 Ask ChatGPT to summarize]({chatgpt_url})\n"
                                    
                                    # Add divider between entries
                                    entry_text += "\n" + "•" * 3 + "\n\n"
                                    
                                    # Add to embed description
                                    if len(embed.description or "") + len(entry_text) > 4000:  # Discord's limit
                                        # Send current embed and start a new one
                                        try:
                                            await asyncio.wait_for(channel.send(embed=embed), timeout=1.0)
                                            await asyncio.sleep(1.5)  # Sleep between messages
                                        except asyncio.TimeoutError:
                                            logging.error(f"Timeout while sending message to channel {channel.id}")
                                        except Exception as e:
                                            logging.error(f"Error sending message to channel {channel.id}: {str(e)}")
                                        
                                        # Create new embed with feed header
                                        embed = discord.Embed(
                                            title=f"📰 {feed_name} (continued)",
                                            color=discord.Color.blue()
                                        )
                                    
                                    # Add entry to embed description
                                    if embed.description is None:
                                        embed.description = entry_text
                                    else:
                                        embed.description += entry_text
                                
                                # Send the final embed for this batch
                                try:
                                    await asyncio.wait_for(channel.send(embed=embed), timeout=1.0)
                                    await asyncio.sleep(1.5)  # Sleep between messages
                                except asyncio.TimeoutError:
                                    logging.error(f"Timeout while sending message to channel {channel.id}")
                                except Exception as e:
                                    logging.error(f"Error sending message to channel {channel.id}: {str(e)}")
                else:
                    logging.info(f"No new entries found for {channel_type}")
                
        except Exception as e:
            logging.error(f"Error in check_all_feeds: {str(e)}")
            import traceback
            logging.error(f"Stack trace:\n{traceback.format_exc()}")
        finally:
            if self._session and not self._closed:
                await self._session.close()

    async def _init_session(self):
        """Initialize aiohttp session if not already initialized"""
        if self._session is None:
            self._session = aiohttp.ClientSession()
            
    async def _close_session(self):
        """Close aiohttp session if it exists"""
        if self._session is not None:
            await self._session.close()
            self._session = None

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--from-start', action='store_true', help='Process all entries from May 2025, ignoring seen entries')
    parser.add_argument('--category', choices=['engineering', 'data_analytics', 'management'], 
                      help='Run bot for specific category only')
    args = parser.parse_args()

    # Log the arguments for debugging
    logging.info(f"Starting bot with arguments: from_start={args.from_start}, category={args.category}")

    monitor = RSSMonitor(from_start=args.from_start, target_category=args.category)
    
    try:
        await monitor.start(os.getenv('DISCORD_TOKEN'))
    except Exception as e:
        logging.error(f"Error in main: {str(e)}")
    finally:
        if not monitor._closed:
            await monitor.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Bot stopped by user")
    except Exception as e:
        logging.error(f"Fatal error: {str(e)}") 