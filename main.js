const ServerStatsBot = require("./bot");
const { WEBHOOK_URL, SERVER_ID } = require("./config");

const bot = new ServerStatsBot(WEBHOOK_URL, SERVER_ID);

async function main() {
  try {
    await bot.start();

    // Graceful Shutdown
    process.on("SIGINT", async () => {
      console.log("\nBeende Bot...");
      await bot.stop();
      process.exit(0);
    });

    process.on("SIGTERM", async () => {
      console.log("\nBeende Bot...");
      await bot.stop();
      process.exit(0);
    });
  } catch (error) {
    console.error("Unerwarteter Fehler:", error);
    await bot.stop();
    process.exit(1);
  }
}

main();
