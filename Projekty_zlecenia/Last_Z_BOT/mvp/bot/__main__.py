"""
Entry point for bot macro testing.
Spawned by LastZBot-SelfTest orchestrator via: python -m mvp.bot
"""
import sys
import logging
from pathlib import Path

# Ensure project root is in sys.path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

def main():
    print("[BOT_MAIN] Starting", flush=True)
    
    from mvp.logger import setup_dev_logging
    setup_dev_logging()
    logger = logging.getLogger("mvp.bot.main")
    logger.info("Bot macro engine starting (test orchestrator mode)")
    print("[BOT_MAIN] Imports OK", flush=True)
    
    try:
        from mvp.config import MVPConfig
        from mvp.bot.runner import BotRunner
        
        print("[BOT_MAIN] Loading config", flush=True)
        config = MVPConfig.load()
        print("[BOT_MAIN] Config loaded", flush=True)
        
        # In test orchestrator mode, the game window is LastZBot-SelfTest.exe, not the real game
        if not any(arg.startswith("--real-game") for arg in sys.argv):
            logger.info("Test mode: overriding process_name to 'LastZBot-SelfTest.exe'")
            config.process_name = "LastZBot-SelfTest.exe"
            print(f"[BOT_MAIN] Process name set to: {config.process_name}", flush=True)
        
        print("[BOT_MAIN] Initializing BotRunner", flush=True)
        runner = BotRunner(config)
        print("[BOT_MAIN] BotRunner initialized", flush=True)
        
        print("[BOT_MAIN] Starting runner.run()", flush=True)
        runner.run()
        print("[BOT_MAIN] runner.run() completed", flush=True)
        
    except Exception as e:
        logger.error(f"Bot crashed: {e}", exc_info=True)
        print(f"[BOT_MAIN] EXCEPTION: {e}", flush=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
