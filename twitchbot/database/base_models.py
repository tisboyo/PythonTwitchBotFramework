from sqlalchemy import Column, Integer, String, Float, Boolean
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class Quote(Base):
    __tablename__ = "quotes"

    id = Column(Integer, primary_key=True, nullable=False)
    user = Column(String(255))
    channel = Column(String(255), nullable=False)
    alias = Column(String(255))
    value = Column(String(255), nullable=False)


class CustomCommand(Base):
    __tablename__ = "commands"

    id = Column(Integer, primary_key=True, nullable=False)
    name = Column(String(255), nullable=False)
    channel = Column(String(255), nullable=False)
    response = Column(String(255), nullable=False)


class Balance(Base):
    __tablename__ = "balance"

    id = Column(Integer, nullable=False, primary_key=True)
    channel = Column(String(255), nullable=False)
    user = Column(String(255), nullable=False)
    balance = Column(Integer, nullable=False)


class CurrencyName(Base):
    __tablename__ = "currency_names"

    id = Column(Integer, nullable=False, primary_key=True)
    channel = Column(String(255), nullable=False)
    name = Column(String(255), nullable=False)


class MessageTimer(Base):
    __tablename__ = "message_timers"

    id = Column(Integer, nullable=False, primary_key=True)
    name = Column(String(255), nullable=False)
    channel = Column(String(255), nullable=False)
    message = Column(String(255), nullable=False)
    interval = Column(Float, nullable=False)
    active = Column(Boolean, nullable=False, default=False)
