import discord
from discord.ext import tasks
import requests
import json
from datetime import datetime
import aiohttp
import asyncio
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import re
import os
from config import UPDATE_INTERVAL, WEBHOOK_URL, SERVER_ID

class ServerStatsBot:
    def __init__(self, webhook_url, server_id):
        self.webhook_url = webhook_url
        self.server_id = server_id
        self.stats_file = 'stats_db.json'
        self.stats_db = self.load_stats()
        self.session = None
        self.driver = None
        self.hourly_update_task = None
        self.update_interval = UPDATE_INTERVAL
        self.setup_driver()

    async def start(self):
        self.session = aiohttp.ClientSession()
        try:
            print("Führe erste Aktualisierung durch...")
            await self.hourly_update()
            
            print(f"Starte Update-Task (Intervall: {self.update_interval} Sekunden)...")
            if not self.hourly_update_task:
                # Erstelle den Task mit dem korrekten Intervall
                self.hourly_update.change_interval(seconds=self.update_interval)
                self.hourly_update_task = self.hourly_update.start()
            
            print("Bot läuft - warte auf Updates...")
            print("Drücke STRG+C zum Beenden")
            
            while True:
                await asyncio.sleep(60)
                
        except asyncio.CancelledError:
            print("Bot-Task wurde abgebrochen")
        except Exception as e:
            print(f"Fehler im Bot: {e}")
        finally:
            print("Räume Bot-Ressourcen auf...")
            if self.session and not self.session.closed:
                await self.session.close()
            if self.driver:
                self.driver.quit()

    def setup_driver(self):
        try:
            if self.driver:
                self.driver.quit()
                
            chrome_options = Options()
            chrome_options.add_argument('--headless=new')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36')
            
            service = ChromeService(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(
                options=chrome_options,
                service=service
            )
            self.driver.implicitly_wait(10)
            print("Chrome-Driver erfolgreich initialisiert")
            
        except Exception as e:
            print(f"Fehler beim Setup des Drivers: {e}")
            if self.driver:
                self.driver.quit()
                self.driver = None

    def get_player_count(self):
        try:
            if not self.driver:
                print("Driver nicht verfügbar, initialisiere neu...")
                self.setup_driver()
                
            if not self.driver:
                print("Driver konnte nicht initialisiert werden")
                return 0
                
            # Seite neu laden und warten bis sie vollständig geladen ist
            self.driver.get('https://servers.redm.gg/servers/detail/bzy79l')
            WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # Warte auf das spezifische Element mit der Spielerzahl
            player_element = WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'div.connect-bar div.right span.material-icons-outlined'))
            )
            
            print("Gefundenes Element:", player_element.text)
            
            # Finde das benachbarte Element mit der tatsächlichen Zahl
            player_count = self.driver.find_element(By.CSS_SELECTOR, 'div.connect-bar div.right').text
            print("Vollständiger Text:", player_count)
            
            # Extrahiere die erste Zahl aus dem Text
            numbers = re.findall(r'\d+', player_count)
            if numbers:
                return int(numbers[0])
            return 0
                
        except Exception as e:
            print(f"Fehler beim Scraping: {e}")
            # Bei Fehlern Driver neu initialisieren
            self.setup_driver()
            return 0

    def load_stats(self):
        if os.path.exists(self.stats_file):
            try:
                with open(self.stats_file, 'r') as f:
                    data = json.load(f)
                    # Konvertiere Timestamp-Strings zurück zu datetime-Objekten
                    for entry in data['hourly']:
                        entry['timestamp'] = datetime.fromisoformat(entry['timestamp'])
                    return data
            except Exception as e:
                print(f"Fehler beim Laden der Statistiken: {e}")
        return {'hourly': []}

    def save_stats(self):
        try:
            # Konvertiere datetime-Objekte zu Strings für JSON
            data = {'hourly': []}
            for entry in self.stats_db['hourly']:
                data['hourly'].append({
                    'timestamp': entry['timestamp'].isoformat(),
                    'players': entry['players']
                })
            with open(self.stats_file, 'w') as f:
                json.dump(data, f)
        except Exception as e:
            print(f"Fehler beim Speichern der Statistiken: {e}")

    @tasks.loop(seconds=UPDATE_INTERVAL)
    async def hourly_update(self):
        try:
            print(f"\nFühre Update aus - {datetime.now().strftime('%H:%M:%S')}")
            players = self.get_player_count()
            timestamp = datetime.now()
            
            # Neue Daten speichern
            self.stats_db['hourly'].append({
                'timestamp': timestamp,
                'players': players
            })
            
            # Statistiken berechnen
            stats = self.calculate_stats()
            
            embed = discord.Embed(
                title="Misty Mountain - Aktuelle Spielerzahl",
                description=f"**{players}** Spieler online",
                color=discord.Color.blue(),
                timestamp=timestamp
            )
            
            # Statistiken hinzufügen
            embed.add_field(
                name="24 Stunden",
                value=f"Durchschnitt: {stats['day_avg']}\nMaximum: {stats['day_max']}\nMinimum: {stats['day_min']}",
                inline=True
            )
            embed.add_field(
                name="7 Tage",
                value=f"Durchschnitt: {stats['week_avg']}\nMaximum: {stats['week_max']}\nMinimum: {stats['week_min']}",
                inline=True
            )
            embed.add_field(
                name="30 Tage",
                value=f"Durchschnitt: {stats['month_avg']}\nMaximum: {stats['month_max']}\nMinimum: {stats['month_min']}",
                inline=True
            )
            
            await self.send_webhook(embed)
            
            # Speichere die Statistiken nach dem Update
            self.save_stats()
            
            # Entferne alte Einträge (älter als 30 Tage)
            now = datetime.now()
            self.stats_db['hourly'] = [
                entry for entry in self.stats_db['hourly']
                if (now - entry['timestamp']).total_seconds() <= 2592000
            ]
            
            print(f"Update abgeschlossen - {players} Spieler online")
            
        except Exception as e:
            print(f"Fehler beim Update: {e}")

    def calculate_stats(self):
        now = datetime.now()
        stats = {}
        
        # Filtere die Daten nach Zeiträumen
        day_data = [entry['players'] for entry in self.stats_db['hourly'] 
                    if (now - entry['timestamp']).total_seconds() <= 86400]  # 24 Stunden
        week_data = [entry['players'] for entry in self.stats_db['hourly']
                     if (now - entry['timestamp']).total_seconds() <= 604800]  # 7 Tage
        month_data = [entry['players'] for entry in self.stats_db['hourly']
                      if (now - entry['timestamp']).total_seconds() <= 2592000]  # 30 Tage
        
        # Berechne Statistiken für jeden Zeitraum
        def calc_stats(data):
            if not data:
                return {'avg': 0, 'max': 0, 'min': 0}
            return {
                'avg': round(sum(data) / len(data), 1),
                'max': max(data),
                'min': min(data)
            }
        
        day_stats = calc_stats(day_data)
        week_stats = calc_stats(week_data)
        month_stats = calc_stats(month_data)
        
        return {
            'day_avg': day_stats['avg'],
            'day_max': day_stats['max'],
            'day_min': day_stats['min'],
            'week_avg': week_stats['avg'],
            'week_max': week_stats['max'],
            'week_min': week_stats['min'],
            'month_avg': month_stats['avg'],
            'month_max': month_stats['max'],
            'month_min': month_stats['min']
        }

    async def send_webhook(self, embed):
        webhook = discord.Webhook.from_url(
            self.webhook_url,
            session=self.session
        )
        await webhook.send(embed=embed)

    def __del__(self):
        if hasattr(self, 'hourly_update_task') and self.hourly_update_task:
            self.hourly_update_task.cancel()
        if hasattr(self, 'driver') and self.driver:
            self.driver.quit()