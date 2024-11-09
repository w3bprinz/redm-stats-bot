const Discord = require("discord.js");
const puppeteer = require("puppeteer");
const fs = require("fs").promises;
const { UPDATE_INTERVAL, WEBHOOK_URL, SERVER_ID } = require("./config");

class ServerStatsBot {
  constructor(webhookUrl, serverId) {
    this.webhookUrl = webhookUrl;
    this.serverId = serverId;
    this.statsFile = "stats_db.json";
    this.statsDb = { hourly: [] };
    this.browser = null;
    this.updateInterval = null;
  }

  async init() {
    try {
      await this.loadStats();
      await this.setupBrowser();
      console.log("Bot initialisiert");
    } catch (error) {
      console.error("Fehler bei der Initialisierung:", error);
    }
  }

  async setupBrowser() {
    try {
      this.browser = await puppeteer.launch({
        headless: "new",
        args: ["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
      });
      console.log("Browser erfolgreich initialisiert");
    } catch (error) {
      console.error("Fehler beim Browser-Setup:", error);
      this.browser = null;
    }
  }

  async getPlayerCount() {
    try {
      if (!this.browser) {
        await this.setupBrowser();
      }

      const page = await this.browser.newPage();
      await page.setUserAgent(
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36"
      );

      await page.goto("https://servers.redm.gg/servers/detail/bzy79l", {
        waitUntil: "networkidle0",
      });

      const playerCount = await page.evaluate(() => {
        const element = document.querySelector("div.connect-bar div.right");
        if (element) {
          const match = element.textContent.match(/\d+/);
          return match ? parseInt(match[0]) : 0;
        }
        return 0;
      });

      await page.close();
      return playerCount;
    } catch (error) {
      console.error("Fehler beim Scraping:", error);
      return 0;
    }
  }

  async loadStats() {
    try {
      const data = await fs.readFile(this.statsFile, "utf8");
      const stats = JSON.parse(data);
      stats.hourly = stats.hourly.map((entry) => ({
        ...entry,
        timestamp: new Date(entry.timestamp),
      }));
      this.statsDb = stats;
    } catch (error) {
      this.statsDb = { hourly: [] };
    }
  }

  async saveStats() {
    try {
      await fs.writeFile(this.statsFile, JSON.stringify(this.statsDb));
    } catch (error) {
      console.error("Fehler beim Speichern der Statistiken:", error);
    }
  }

  calculateStats() {
    const now = new Date();

    const filterData = (hours) => {
      return this.statsDb.hourly
        .filter((entry) => now - new Date(entry.timestamp) <= hours * 3600000)
        .map((entry) => entry.players);
    };

    const calcStats = (data) => {
      if (!data.length) return { avg: 0, max: 0, min: 0 };
      return {
        avg: Math.round((data.reduce((a, b) => a + b, 0) / data.length) * 10) / 10,
        max: Math.max(...data),
        min: Math.min(...data),
      };
    };

    const dayData = filterData(24);
    const weekData = filterData(168);
    const monthData = filterData(720);

    const dayStats = calcStats(dayData);
    const weekStats = calcStats(weekData);
    const monthStats = calcStats(monthData);

    return {
      day_avg: dayStats.avg,
      day_max: dayStats.max,
      day_min: dayStats.min,
      week_avg: weekStats.avg,
      week_max: weekStats.max,
      week_min: weekStats.min,
      month_avg: monthStats.avg,
      month_max: monthStats.max,
      month_min: monthStats.min,
    };
  }

  async sendWebhook(players, stats) {
    const webhook = new Discord.WebhookClient({ url: this.webhookUrl });

    const embed = new Discord.EmbedBuilder()
      .setTitle("Misty Mountain - Aktuelle Spielerzahl")
      .setDescription(`**${players}** Spieler online`)
      .setColor(0x0099ff)
      .setTimestamp()
      .addFields(
        {
          name: "24 Stunden",
          value: `Durchschnitt: ${stats.day_avg}\nMaximum: ${stats.day_max}\nMinimum: ${stats.day_min}`,
          inline: true,
        },
        {
          name: "7 Tage",
          value: `Durchschnitt: ${stats.week_avg}\nMaximum: ${stats.week_max}\nMinimum: ${stats.week_min}`,
          inline: true,
        },
        {
          name: "30 Tage",
          value: `Durchschnitt: ${stats.month_avg}\nMaximum: ${stats.month_max}\nMinimum: ${stats.month_min}`,
          inline: true,
        }
      );

    await webhook.send({ embeds: [embed] });
  }

  async update() {
    try {
      console.log(`\nFühre Update aus - ${new Date().toLocaleTimeString()}`);
      const players = await this.getPlayerCount();

      this.statsDb.hourly.push({
        timestamp: new Date(),
        players,
      });

      const stats = this.calculateStats();
      await this.sendWebhook(players, stats);
      await this.saveStats();

      // Alte Einträge entfernen (älter als 30 Tage)
      const now = new Date();
      this.statsDb.hourly = this.statsDb.hourly.filter((entry) => now - new Date(entry.timestamp) <= 2592000000);

      console.log(`Update abgeschlossen - ${players} Spieler online`);
    } catch (error) {
      console.error("Fehler beim Update:", error);
    }
  }

  async start() {
    await this.init();
    await this.update();
    this.updateInterval = setInterval(() => this.update(), UPDATE_INTERVAL * 1000);
    console.log(`Bot läuft - Update-Intervall: ${UPDATE_INTERVAL} Sekunden`);
  }

  async stop() {
    if (this.updateInterval) {
      clearInterval(this.updateInterval);
    }
    if (this.browser) {
      await this.browser.close();
    }
    console.log("Bot wurde beendet");
  }
}

module.exports = ServerStatsBot;
