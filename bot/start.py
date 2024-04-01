import logging

from telegram.ext import Application

import bot.payments as payments
from bot import config

logger = logging.getLogger(__name__)
logger.setLevel("INFO")


def main() -> None:
    application = Application.builder().token(config.TELEGRAM_TOKEN).build()
    payments.init_handlers(application)
    application.run_polling()
