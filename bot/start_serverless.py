import json
import logging

from telegram import Update
from telegram.ext import Application

from bot import config

logging.basicConfig(
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def process_update(event, application):
    await application.update_queue.put(Update.de_json(data=json.loads(event["body"]), bot=application.bot))


async def handler(event, context):
    """Yandex.Cloud functions handler."""
    logger.info("Process event: " + str(event["httpMethod"]))

    """Start the bot."""
    from bot import handlers

    logger.info("Starting bot")

    # Here we set updater to None because we want our custom webhook server to handle the updates
    # and hence we don't need an Updater instance
    application = Application.builder().token(config.TELEGRAM_TOKEN).updater(None).build()

    # Setup command and message handlers
    handlers.setup(application)
    logger.info("Setup handlers")

    # Run application and webserver together
    async with application:
        await application.start()
        await process_update(event, application)
        await application.stop()

    return {"statusCode": 200, "body": "ok"}
