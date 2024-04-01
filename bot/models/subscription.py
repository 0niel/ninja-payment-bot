import datetime

import sqlalchemy as db

from bot.db import db_session
from bot.models.base import BaseModel


class Subscription(BaseModel):
    __tablename__ = "subscriptions"

    id = db.Column(db.Integer, primary_key=True)
    telegram_user_id = db.Column(db.Integer)
    username = db.Column(db.String)
    start_date = db.Column(db.DateTime)
    end_date = db.Column(db.DateTime)

    @staticmethod
    async def create(telegram_user_id: int, username: str, start_date: datetime, end_date: datetime) -> "Subscription":
        with db_session() as session:
            subscription = Subscription(
                telegram_user_id=telegram_user_id,
                username=username,
                start_date=start_date,
                end_date=end_date,
            )
            session.add(subscription)
            session.commit()
            return subscription

    @staticmethod
    async def get_by_username(username: str) -> "Subscription":
        with db_session() as session:
            return session.query(Subscription).filter(Subscription.username == username).first()

    @staticmethod
    async def get_expired_subscriptions() -> list[str]:
        subscibers_to_remove = []

        with db_session() as session:
            now = datetime.datetime.now()
            expired_subscriptions = session.query(Subscription).filter(Subscription.end_date <= now).all()

            for subscription in expired_subscriptions:
                subscibers_to_remove.append(subscription.username)

        return subscibers_to_remove

    @staticmethod
    async def remove_subscriptions(usernames: list[str]) -> None:
        with db_session() as session:
            session.query(Subscription).filter(Subscription.username.in_(usernames)).delete(synchronize_session=False)
            session.commit()


Subscription.__table__.create(checkfirst=True)
