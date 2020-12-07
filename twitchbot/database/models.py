from asyncio import Task


from .session import init_tables
from ..config import cfg
from ..enums import CommandContext

from .base_models import Quote as BaseQuote
from .base_models import CustomCommand as BaseCustomCommand
from .base_models import Balance as BaseBalance
from .base_models import CurrencyName as BaseCurrencyName
from .base_models import MessageTimer as BaseMessageTimer

__all__ = ("Quote", "CustomCommand", "Balance", "CurrencyName", "MessageTimer")


class Quote(BaseQuote):
    @classmethod
    def create(cls, channel: str, value: str, user: str = None, alias: str = None):
        return Quote(channel=channel.lower(), user=user, value=value, alias=alias)


class CustomCommand(BaseCustomCommand):

    context = CommandContext.CHANNEL
    permission = None

    @classmethod
    def create(cls, channel: str, name: str, response: str):
        return CustomCommand(
            channel=channel.lower(), name=name.lower(), response=response
        )

    @property
    def fullname(self):
        return self.name

    def __str__(self):
        return f"<CustomCommand channel={self.channel!r} name={self.name!r} response={self.response!r}>"


class Balance(BaseBalance):
    @classmethod
    def create(cls, channel: str, user: str, balance: int = cfg.default_balance):
        return Balance(channel=channel.lower(), user=user, balance=balance)


class CurrencyName(BaseCurrencyName):
    @classmethod
    def create(cls, channel: str, name: str):
        return CurrencyName(channel=channel.lower(), name=name)


class MessageTimer(BaseMessageTimer):

    task: Task = None

    @property
    def running(self):
        return self.task is not None and not self.task.done()

    @classmethod
    def create(
        cls, channel: str, name: str, message: str, interval: float, active=False
    ):
        return MessageTimer(
            name=name,
            channel=channel,
            message=message,
            interval=interval,
            active=active,
        )


init_tables()
