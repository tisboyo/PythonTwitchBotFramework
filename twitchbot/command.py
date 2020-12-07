import os
import typing
from datetime import datetime
from importlib import import_module
from typing import Dict, Callable, Optional, List, Tuple

from twitchbot.database import CustomCommand
from twitchbot.message import Message
from .config import cfg
from .enums import CommandContext
from .util import get_py_files, get_file_name
from .util import temp_syspath

if typing.TYPE_CHECKING:
    from .modloader import Mod

DEFAULT_COOLDOWN_BYPASS = 'bypass_cooldown'
DEFAULT_COOLDOWN = 0

__all__ = (
    'Command', 'commands', 'command_exist', 'load_commands_from_directory', 'DummyCommand', 'CustomCommandAction',
    'ModCommand', 'SubCommand', 'get_command', 'CUSTOM_COMMAND_PLACEHOLDERS', 'command_last_execute',
    'get_time_since_execute', 'reset_command_last_execute', 'is_command_off_cooldown', 'is_command_on_cooldown',
    'update_command_last_execute', 'set_command_permission')


class Command:
    def __init__(self, name: str, prefix: str = None, func: Callable = None, global_command: bool = True,
                 context: CommandContext = CommandContext.CHANNEL, permission: str = None, syntax: str = None,
                 help: str = None, aliases: List[str] = None, cooldown: int = DEFAULT_COOLDOWN,
                 cooldown_bypass: str = DEFAULT_COOLDOWN_BYPASS, hidden: bool = False):
        """
        :param name: name of the command (without the prefix)
        :param prefix: prefix require before the command name (defaults the the configs prefix if None)
        :param func: the function that the commands executes
        :param global_command: should the command be registered globally?
        :param context: the context through which calling the command is allowed
        :param permission: permission needed to run the command in chat
        :param syntax: help message for how to use the command, <> is required, () is optional
        :param help: help message for the command, used with the `help` command
        :param aliases: aliases for this same command, only works if global_command is True
        :param cooldown: time between when this command when can be run, 0 means the command be run without any delay and is default value
        :param cooldown_bypass: permission that allows those who have it to bypass the commands cooldown
        :param hidden: hides the command from the output of the commands command
        """
        self.hidden = hidden
        self.cooldown_bypass = cooldown_bypass
        self.cooldown: int = cooldown
        self.aliases: List[str] = aliases if aliases is not None else []
        self.help: str = help
        self.syntax: str = syntax
        self.permission: str = permission
        self.context: CommandContext = context
        self.prefix: str = (prefix if prefix is not None else cfg.prefix).lower()
        self.func: Callable = func
        self.name: str = name.lower()
        self.sub_cmds: Dict[str, Command] = {}
        self.parent: Optional[Command] = None

        if global_command:
            commands[self.fullname] = self

            # register all aliases passed to this functions
            if aliases is not None:
                for alias in aliases:
                    commands[self.prefix + alias] = self

    @property
    def fullname(self) -> str:
        return self.prefix + self.name

    def parent_chain(self) -> List['Command']:
        """
        returns a list with the chain of commands leading to this command

        also includes this command

        ex (with subcommands used):
            c subcommands b subcommands a
            parent_chain() returns [a, b, c]

        :return: list of parents leading to this command, plus the current command at the end
        """
        parents = [self]
        parent = self.parent
        while parent:
            parents.append(parent)
            parent = parent.parent
        return parents[::-1]

    def _get_cmd_func(self, args) -> Tuple['Callable', List[str]]:
        """returns a tuple of the final commands command function and the remaining argument"""
        if not self.sub_cmds or not args or args[0].lower() not in self.sub_cmds:
            return self.func, args

        return self.sub_cmds[args[0].lower()]._get_cmd_func(args[1:])

    def get_sub_cmd(self, args) -> Tuple['Command', Tuple[str]]:
        """
        returns the final command in a sub-command chain from the args passed to the this function

        the sub-command chain is based off of the current command this function is called on

        args is a list or tuple of strings
        """
        if not self.sub_cmds or not args or args[0].lower() not in self.sub_cmds:
            return self, args

        return self.sub_cmds[args[0].lower()].get_sub_cmd(args[1:])

    async def execute(self, msg: Message):
        func, args = self._get_cmd_func(msg.parts[1:])
        await func(msg, *args)

    async def has_permission_to_run_from_msg(self, origin_msg: Message):
        from .event_util import forward_event_with_results
        from .enums import Event

        for parent in self.parent_chain():
            if (parent.permission
                    and not all(await forward_event_with_results(Event.on_permission_check, origin_msg, parent, channel=origin_msg.channel_name))):
                return False
        return True

    # decorator support
    def __call__(self, func) -> 'Command':
        self.func = func
        return self

    def __str__(self):
        return f'<{self.__class__.__name__} fullname={repr(self.fullname)} parent={self.parent}>'

    def __getitem__(self, item):
        return self.sub_cmds.get(item.lower()) or self.sub_cmds.get(item.lower()[1:])

    def __repr__(self):
        return f'<{self.__class__.__name__} fullname={self.fullname}>'


class SubCommand(Command):
    def __init__(self, parent: Command, name: str, func: Callable = None, permission: str = None, syntax: str = None,
                 help: str = None, cooldown: int = DEFAULT_COOLDOWN, cooldown_bypass: str = DEFAULT_COOLDOWN_BYPASS, hidden: bool = False):
        super().__init__(name=name, prefix='', func=func, permission=permission, syntax=syntax, help=help,
                         global_command=False, cooldown=cooldown, cooldown_bypass=cooldown_bypass, hidden=hidden)

        self.parent: Command = parent
        self.parent.sub_cmds[self.name] = self


class DummyCommand(Command):
    def __init__(self, name: str, prefix: str = None, global_command: bool = True,
                 context: CommandContext = CommandContext.CHANNEL, permission: str = None, syntax: str = None,
                 help: str = None, aliases: List[str] = None, hidden: bool = False):
        super().__init__(name=name, prefix=prefix, func=self.exec, global_command=global_command,
                         context=context, permission=permission, syntax=syntax, help=help, aliases=aliases, hidden=hidden)

    async def exec(self, msg: Message, *args):
        """the function called when the dummy command is executed"""
        if self.sub_cmds:
            await msg.reply(f'command options: {", ".join(name for name, cmd in self.sub_cmds.items() if not cmd.hidden)}')
        else:
            await msg.reply('no sub-commands were found for this command')

    def add_sub_cmd(self, name: str) -> 'DummyCommand':
        """adds a new DummyCommand to the current DummyCommand as a sub-command, then returns the new DummyCommand"""
        cmd = DummyCommand(name, prefix='', global_command=False)
        self.sub_cmds[cmd.fullname] = cmd
        return cmd


def _calc_channel_live_time(msg) -> str:
    if msg.channel.live:
        return format((msg.channel.stats.started_at - datetime.now()).total_seconds() / 3600, '.1f')

    return '[NOT LIVE]'


CUSTOM_COMMAND_PLACEHOLDERS = (
    (
        '%user',
        lambda msg: f'@{msg.author}'
    ),
    (
        '%uptime',
        _calc_channel_live_time
    ),
    (
        '%channel',
        lambda msg: msg.channel_name
    ),
)


class CustomCommandAction(Command):
    def __init__(self, cmd):
        super().__init__(cmd.name, prefix='', func=self.execute, global_command=False, hidden=True)
        self.cmd: CustomCommand = cmd
        self.cooldown = 0

    async def execute(self, msg: Message):
        resp = self.cmd.response

        for placeholder, func in CUSTOM_COMMAND_PLACEHOLDERS:
            if placeholder in resp:
                resp = resp.replace(placeholder, func(msg))

        await msg.channel.send_message(resp)


class ModCommand(Command):
    def __init__(self, mod_name: str, name: str, prefix: str = None, func: Callable = None, global_command: bool = True,
                 context: CommandContext = CommandContext.CHANNEL, permission: str = None, syntax: str = None,
                 help: str = None, cooldown: int = DEFAULT_COOLDOWN, cooldown_bypass: str = DEFAULT_COOLDOWN_BYPASS, hidden: bool = False):
        super().__init__(name=name, prefix=prefix, func=func, global_command=global_command, context=context,
                         permission=permission, syntax=syntax, help=help, cooldown=cooldown,
                         cooldown_bypass=cooldown_bypass, hidden=hidden)
        self.mod_name = mod_name

    @property
    def mod(self):
        from .modloader import mods
        return mods[self.mod_name]

    async def execute(self, msg: Message):
        func, args = self._get_cmd_func(msg.parts[1:])
        if 'self' in func.__code__.co_varnames:
            await func(self.mod, msg, *args)
        else:
            await func(msg, *args)


commands: Dict[str, Command] = {}
command_last_execute: Dict[Tuple[str, str], datetime] = {}


def _create_cooldown_key(channel: str, cmd: str) -> Tuple[str, str]:
    return channel.lower(), cmd.lower()


def is_command_off_cooldown(channel: str, cmd: str, cooldown: int = None) -> bool:
    if not command_exist(cmd):
        return True
    return get_time_since_execute(channel, cmd) >= (cooldown or get_command(cmd).cooldown)


def is_command_on_cooldown(channel: str, cmd: str, cooldown: int = None) -> bool:
    return not is_command_off_cooldown(channel, cmd, cooldown)


def get_time_since_execute(channel: str, cmd: str) -> int:
    last_execute = command_last_execute.get(_create_cooldown_key(channel, cmd), datetime.min)
    return int(abs((last_execute - datetime.now()).total_seconds()))


def update_command_last_execute(channel: str, cmd: str):
    command_last_execute[_create_cooldown_key(channel, cmd)] = datetime.now()


def reset_command_last_execute(channel: str, cmd: str):
    command_last_execute[_create_cooldown_key(channel, cmd)] = datetime.min


def load_commands_from_directory(path):
    print(f'loading commands from {path}')

    path = os.path.abspath(path)

    if not os.path.exists(path):
        return

    with temp_syspath(path):
        for file in get_py_files(path):
            fname = get_file_name(file)
            mod = import_module(fname)


def command_exist(name: str) -> bool:
    """
    returns a bool indicating if a command exists,
    tries added a configs prefix to the name if not found initially,
    does not check for custom commands
    """
    return any(cmd in commands for cmd in (name, cfg.prefix + name))


def get_command(name: str) -> Optional[Command]:
    """
    gets a commands,
    tries added a configs prefix to the name if not found initally,
    returns None if not exist, does not get custom commands
    """
    return commands.get(name) or commands.get(cfg.prefix + name)


def set_command_permission(cmd: str, new_permission: Optional[str]) -> bool:
    """
    overrides a command's previous permission and sets to the new one from `new_permission`
    :param cmd: command to override permission for
    :param new_permission: new permission to set for `cmd`
    :return:
    """
    command = get_command(cmd)
    if not command:
        return False

    command.permission = new_permission
    return True
