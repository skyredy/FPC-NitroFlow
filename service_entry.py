import logging
import time
from app.settings import Settings
from app.runtime import run

def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    reported = None
    while True:
        settings = Settings.load()
        state = "ready" if settings.configured else "waiting_for_configuration"
        if state != reported:
            logging.info("Service status: %s", state)
            reported = state
        if state == "ready":
            run(settings)
            return
        time.sleep(15)

if __name__ == "__main__":
    main()
