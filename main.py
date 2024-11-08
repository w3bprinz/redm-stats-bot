import asyncio
import signal
from bot import ServerStatsBot
from config import WEBHOOK_URL, SERVER_ID

async def shutdown(signal, loop, bot):
    print(f"\nSignal {signal.name} empfangen. Beende Bot...")
    
    # Tasks aufräumen
    if bot.hourly_update_task:
        bot.hourly_update_task.cancel()
    
    # Session schließen
    if bot.session and not bot.session.closed:
        await bot.session.close()
    
    # Selenium Driver beenden
    if bot.driver:
        bot.driver.quit()
    
    # Event Loop beenden
    loop.stop()

async def main():
    bot = ServerStatsBot(
        webhook_url=WEBHOOK_URL,
        server_id=SERVER_ID
    )
    
    # Signal Handler einrichten
    loop = asyncio.get_event_loop()
    signals = (signal.SIGTERM, signal.SIGINT)
    for s in signals:
        loop.add_signal_handler(
            s, 
            lambda s=s: asyncio.create_task(shutdown(s, loop, bot))
        )
    
    try:
        print("Bot wird gestartet...")
        await bot.start()
    except Exception as e:
        print(f"Unerwarteter Fehler: {e}")
    finally:
        # Cleanup
        if bot.driver:
            bot.driver.quit()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBot wurde beendet.")