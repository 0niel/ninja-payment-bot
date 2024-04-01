import datetime
import html
import json
import logging
import traceback
from datetime import timedelta

from pydiscourse import DiscourseClient
from pydiscourse.exceptions import DiscourseClientError
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    PreCheckoutQueryHandler,
    filters,
)

from bot import config
from bot.config import DISCOURSE_API_KEY, PAYMENT_PROVIDER_TOKEN
from bot.models.subscription import Subscription

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

CURRENCY = "RUB"
DISCOURSE_URL = "https://mirea.ninja"
DISCOURSE_GROUP_ID = 107
CUSTOM_PAYLOAD = "MIREA_NINJA_SUBSCRIPTION"
SUBSCRIPTION_DURATION_DAYS = 30
SUBSCRIPTION_PRICE = 499
DEVELOPER_CHAT_ID = config.DEVELOPER_CHAT_ID

discourse_client = DiscourseClient(DISCOURSE_URL, api_key=DISCOURSE_API_KEY, api_username="system")

USERNAME_WAITING, START_SHIPPING = range(2)
KEYBOARD_FEEDBACK_CONTACT = [
    [
        InlineKeyboardButton("Написать администратору", url="https://t.me/i_am_oniel"),
    ]
]


async def start_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info(f"User {update.message.from_user.id} ({update.message.from_user.username}) started the bot")
    msg = (
        "👋 Чтобы купить подписку, введите своё имя пользователя на форуме mirea.ninja\n\n"
        "Если у вас нет аккаунта, то создайте учётную запись на сайте https://mirea.ninja"
    )
    await update.message.reply_text(msg)
    return USERNAME_WAITING


async def on_username_received_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    username = update.message.text.strip()

    try:
        subscription = await Subscription.get_by_username(username)
        if subscription:
            await update.message.reply_text("❌ У вас уже есть активная подписка!")
            return

        user = discourse_client.user(username)
        if not user:
            await update.message.reply_text(
                "❌ Пользователь не найден! Пожалуйста, введите корректное имя пользователя."
            )
            return

        if DISCOURSE_GROUP_ID in user["groups"]:
            await update.message.reply_text("❌ У вас уже есть активная подписка!")
            return

        context.user_data["username"] = username

    except DiscourseClientError as e:
        logger.error("Failed to get user: %s", e)
        response = e.response
        if response.status_code == 404:
            await update.message.reply_text(
                "❌ Пользователь не найден! Пожалуйста, введите корректное имя пользователя."
            )
        else:
            await update.message.reply_text(
                "❌ Произошла ошибка при получении данных. Повторите попытку позже или обратитесь к администратору",
                reply_markup=InlineKeyboardMarkup(KEYBOARD_FEEDBACK_CONTACT),
            )
        return
    except Exception as e:
        logger.error("Failed to get user: %s", e)
        await update.message.reply_text(
            "❌ Произошла ошибка при получении данных. Обратитесь к администратору",
            reply_markup=InlineKeyboardMarkup(KEYBOARD_FEEDBACK_CONTACT),
        )
        return

    avatar = user["avatar_template"].replace("{size}", "100")
    avatar = f"{DISCOURSE_URL}{avatar}"
    msg = (
        f"🔑 Пожалуйста, подтвердите, что вы хотите купить подписку на {SUBSCRIPTION_DURATION_DAYS} дней.\n\n"
        f"Ваше имя пользователя: {username}"
    )

    keyboard = [
        [
            InlineKeyboardButton("✅ Да", callback_data="confirm"),
            InlineKeyboardButton("❌ Нет", callback_data="cancel"),
        ]
    ]

    await update.message.reply_photo(avatar, caption=msg, reply_markup=InlineKeyboardMarkup(keyboard))

    return START_SHIPPING


async def start_with_shipping_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query

    if query.data == "cancel":
        await query.answer("Операция отменена")
        await query.message.delete()
        return USERNAME_WAITING

    await query.answer()

    chat_id = query.message.chat_id
    title = "Оплата подписки"
    description = f"Вы оплачиваете подписку к AI инфраструктуре на форуме на {SUBSCRIPTION_DURATION_DAYS} дней!"
    prices = [LabeledPrice("Подписка", SUBSCRIPTION_PRICE * 100)]

    logger.info(f"Sending invoice to user {chat_id} for subscription")

    await context.bot.send_invoice(
        chat_id,
        title,
        description,
        CUSTOM_PAYLOAD,
        PAYMENT_PROVIDER_TOKEN,
        CURRENCY,
        prices,
    )


async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info(f"Precheckout query: {update.pre_checkout_query}")
    username = context.user_data.get("username")
    query = update.pre_checkout_query
    if query.invoice_payload != CUSTOM_PAYLOAD or not username:
        logger.error("Invalid payload")
        await query.answer(ok=False, error_message="Что-то пошло не так.. Попробуйте ещё раз.")
    else:
        logger.info("Precheckout query is valid")
        await query.answer(ok=True)


async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        user_id = update.message.from_user.id
        username = context.user_data.get("username")
        if not username:
            await update.message.reply_text(
                "❌ Произошла ошибка! Пользователь не найден!",
                reply_markup=InlineKeyboardMarkup(KEYBOARD_FEEDBACK_CONTACT),
            )
            return

        start_date = datetime.datetime.now()
        end_date = start_date + timedelta(days=SUBSCRIPTION_DURATION_DAYS)

        subscription = await Subscription.create(user_id, username, start_date, end_date)
        context.job_queue.run_once(add_user_to_group_task, 0, data={"username": subscription.username})

        await update.message.reply_text(
            f"✅ Подписка успешно оформлена!\n\n"
            f"📅 Срок действия подписки: {start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}\n\n"
        )
        await update.message.reply_text(
            "👋 Для получения доступа к AI инфраструктуре, перейдите на форум https://mirea.ninja\n\n"
            "Читайте инструкцию по использованию AI инфраструктуры в разделе https://mirea.ninja/c/ai/111",
        )
        await update.message.reply_text(
            "Если у вас возникли вопросы, обращайтесь к администратору",
            reply_markup=InlineKeyboardMarkup(KEYBOARD_FEEDBACK_CONTACT),
        )
    except Exception as e:
        logger.error("Failed to create subscription: %s", e)
        await update.message.reply_text(
            "❌ Произошла ошибка при оформлении подписки!",
            reply_markup=InlineKeyboardMarkup(KEYBOARD_FEEDBACK_CONTACT),
        )
        return


async def check_subscriptions(context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        users_to_remove = await Subscription.get_expired_subscriptions()
        if users_to_remove:
            usernames = ",".join(users_to_remove)
            discourse_client.delete_group_member(DISCOURSE_GROUP_ID, usernames)
            await Subscription.remove_subscriptions(users_to_remove)
    except Exception as e:
        logger.error("Failed to remove users from the group: %s", e)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Exception while handling an update:", exc_info=context.error)

    # traceback.format_exception returns the usual python message about an exception, but as a
    # list of strings rather than a single string, so we have to join them together.
    tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
    tb_string = "".join(tb_list)

    # Build the message with some markup and additional information about what happened.
    # You might need to add some logic to deal with messages longer than the 4096 character limit.
    update_str = update.to_dict() if isinstance(update, Update) else str(update)
    message = (
        "An exception was raised while handling an update\n"
        f"<pre>update = {html.escape(json.dumps(update_str, indent=2, ensure_ascii=False))}"
        "</pre>\n\n"
        f"<pre>context.chat_data = {html.escape(str(context.chat_data))}</pre>\n\n"
        f"<pre>context.user_data = {html.escape(str(context.user_data))}</pre>\n\n"
        f"<pre>{html.escape(tb_string)}</pre>"
    )

    await context.bot.send_message(chat_id=DEVELOPER_CHAT_ID, text=message, parse_mode=ParseMode.HTML)


async def add_user_to_group_task(context: ContextTypes.DEFAULT_TYPE) -> None:
    job = context.job
    username = job.data["username"]

    try:
        discourse_client.add_group_member(DISCOURSE_GROUP_ID, username=username)
        logger.info(f"User {username} added to the group successfully")
    except DiscourseClientError as e:
        logger.warning(f"Failed to add user {username} to the group: {e}")
        # Reschedule the task to run again after a certain interval (e.g., 1 hour)
        context.job_queue.run_once(add_user_to_group_task, 3600, data={"username": username})
    except Exception as e:
        logger.error(f"Unexpected error while adding user {username} to the group: {e}")


def init_handlers(app: Application) -> None:
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start_callback)],
        states={
            USERNAME_WAITING: [MessageHandler(filters.TEXT & ~filters.COMMAND, on_username_received_callback)],
            START_SHIPPING: [CallbackQueryHandler(start_with_shipping_callback)],
        },
        fallbacks=[CommandHandler("start", start_callback)],
    )

    app.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))
    app.add_handler(conv_handler)

    app.add_error_handler(error_handler)

    job_queue = app.job_queue
    job_queue.run_repeating(check_subscriptions, interval=timedelta(days=1))
