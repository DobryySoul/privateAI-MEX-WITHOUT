from sqlalchemy import ForeignKey, String, BigInteger, DateTime, func, Text, LargeBinary, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import List
from enum import Enum as PyEnum
from database.engine import Base
metadata = Base.metadata


class PaymentMethod(PyEnum):
    """Enum для методов оплаты"""
    CASH = "cash"          
    BANK = "bank"         


# User table
class User(Base):
    __tablename__ = 'user'
    __table_args__ = {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4', 'mysql_collate': 'utf8mb4_unicode_ci', 'extend_existing': True}

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram: Mapped[BigInteger] = mapped_column(BigInteger)
    message_counter: Mapped[int] = mapped_column(default=0)
    global_message_counter: Mapped[int] = mapped_column(default=0)
    payment_method: Mapped[PaymentMethod | None] = mapped_column(Enum(PaymentMethod), nullable=True)
    # status_list: Mapped[str] = mapped_column(Text, default=json.dumps([False] * length))
    stop: Mapped[bool] = mapped_column(default=False)
    data_name: Mapped[str | None] = mapped_column(String(720), nullable=True)
    data_one: Mapped[str | None] = mapped_column(String(720), nullable=True)
    data_two: Mapped[str | None] = mapped_column(String(720), nullable=True)
    data_three: Mapped[str | None] = mapped_column(String(720), nullable=True)
    data_photo: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime, default=func.now())

    message_rel: Mapped[List["Message"]] = relationship(back_populates="user_rel", cascade='all, delete')


# Модель сообщения
class Message(Base):
    __tablename__ = 'message'
    __table_args__ = {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4', 'mysql_collate': 'utf8mb4_unicode_ci'}

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('user.id'))
    text: Mapped[str] = mapped_column(Text(collation='utf8mb4_unicode_ci'))
    from_me: Mapped[bool] = mapped_column(default=False)  #Если true - сообщение от бота, если false - от пользователя
    created_at: Mapped[DateTime] = mapped_column(DateTime, default=func.now())
    push_id: Mapped[int | None] = mapped_column(ForeignKey('push_notification.id'), nullable=True)
    attachment_path: Mapped[str | None] = mapped_column(String(720), nullable=True)

    user_rel: Mapped["User"] = relationship(back_populates="message_rel")
    push_rel: Mapped["PushNotification"] = relationship("PushNotification", back_populates="message_rel", uselist=False)


class PushNotification(Base):
    __tablename__ = 'push_notification'
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('user.id'))
    period: Mapped[str] = mapped_column(String(16))  # '15m', '1d', '7d'
    sent_at: Mapped[DateTime] = mapped_column(DateTime, default=func.now())

    user_rel: Mapped["User"] = relationship()
    message_rel: Mapped["Message"] = relationship("Message", back_populates="push_rel", uselist=False)

# Модель платежа
class Payment(Base):
    __tablename__ = 'payment'
    __table_args__ = {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4', 'mysql_collate': 'utf8mb4_unicode_ci'}

    id: Mapped[int] = mapped_column(primary_key=True)
    stop: Mapped[bool] = mapped_column(default=False)
    use_count: Mapped[int] = mapped_column(default=0)
    type: Mapped[PaymentMethod | None] = mapped_column(Enum(PaymentMethod), nullable=True)
    data_name: Mapped[str | None] = mapped_column(String(720), nullable=True)
    data_one: Mapped[str | None] = mapped_column(String(720), nullable=True)
    data_two: Mapped[str | None] = mapped_column(String(720), nullable=True)
    data_three: Mapped[str | None] = mapped_column(String(720), nullable=True)
    data_photo: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime, default=func.now())
