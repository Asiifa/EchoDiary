"""
EchoDiary - Voice Diary and Mood Summariser
Application Entry Point
"""
import sys
import logging
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from app.config import Config
from app.database import init_db
from app.ui.main_window import MainWindow


def setup_logging():
    """Configure local application logging."""
    Config.ensure_directories()
    log_file = Config.LOGS_DIR / "echodiary.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(str(log_file), encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    logging.info(f"Starting {Config.APP_NAME} v{Config.APP_VERSION}")
    logging.info(f"Data directory: {Config.BASE_DATA_DIR}")


def main():
    """Main application lifecycle runner."""
    # Ensure all directories exist
    Config.ensure_directories()

    # Configure logging
    setup_logging()

    # Initialize local SQLite database tables
    try:
        init_db()
        logging.info("SQLite database tables verified.")
    except Exception as e:
        logging.error(f"Failed to initialize database: {e}", exc_info=True)
        sys.exit(1)

    # Initialize PySide6 application
    app = QApplication(sys.argv)
    app.setApplicationName(Config.APP_NAME)
    app.setApplicationVersion(Config.APP_VERSION)
    app.setOrganizationName("EchoDiaryLocal")

    # Instantiate and display the main window
    window = MainWindow()
    window.show()

    # Enter Qt main event loop
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

