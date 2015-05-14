import functools
import collections
import datetime
import logging
import regex
import autobot
from .helpers import DictObj

LOG = logging.getLogger(__name__)


class Message(object):
    def __init__(self, message, author, reply_path=None, mention_parse=None):
        assert issubclass(type(reply_path), ChatObject)
        self._message = message
        self._author = author
        self._reply_path = reply_path
        self._mentions = []
        mention_name = ''
        if mention_parse:
            mention_name, self._mentions = mention_parse(message)
            message = self._strip_mention(message, mention_name)

    def mentions(self, username):
        return username in self._mentions

    def mentions_self(self):
        return autobot.SELF_MENTION in self._mentions

    def direct_message(self):
        return issubclass(type(self._reply_path), User)

    def reply(self, message):
        LOG.debug('Sending message {} to appropriate places..'.format(message))
        self._reply_path.say(message)

    def __str__(self):
        return self._message

    @property
    def author(self):
        return self._author

    def _strip_mention(self, message, mention_name):
        if message.startswith(mention_name):
            message = message[len(mention_name):].strip()
        return message


class ChatObject(object):
    def __init__(self, name, reply_handler):
        self.name = name
        self._internal = DictObj()
        self._reply_handler = reply_handler

    def say(self, message):
        if not self._reply_handler:
            raise NotImplementedError()
        self._reply_handler(self, message)


class Room(ChatObject):
    def __init__(self, name, topic=None, roster=None, reply_handler=None):
        super().__init__(name, reply_handler)
        self.roster = roster
        self.topic = topic

    def __str__(self):
        return self.name

    def join(self):
        pass

    def leave(self):
        pass


class User(ChatObject):
    def __init__(self, name, real_name, reply_handler=None):
        super().__init__(name, reply_handler)
        self.real_name = real_name

    def __str__(self):
        return self.name


class MetaPlugin(type):
    def __new__(cls, name, bases, namespace, **kwargs):
        for method in namespace.values():
            if hasattr(method, '_attach_class'):
                setattr(method, '_class_name', name)
        return type.__new__(cls, name, bases, namespace, **kwargs)


class Plugin(metaclass=MetaPlugin):
    def __init__(self, factory):
        self._factory = factory
        self._storage = None

    @property
    def default_room(self):
        return self._factory.get_service().default_room

    @property
    def service(self):
        return self._factory.get_service()

    @property
    def storage(self):
        if not self._storage:
            storage = self._factory.get_storage()
            # Let's namespace the plugin's storage
            name = type(self).__name__
            if name not in storage:
                storage[name] = {}
            self._storage = storage[name]

        return self._storage



class Storage(collections.UserDict):
    def sync(self):
        raise NotImplementedError()

    def close(self):
        raise NotImplementedError()


class Service(object):
    config_defaults = {'mention_name': 'autobot'}

    def __init__(self, config=None):
        self._config = config
        self._default_room = None

    def start(self):
        if 'rooms' not in self._config:
            raise Exception('No rooms to join defined!')

    def shutdown(self):
        raise NotImplementedError()

    def join_room(self, room):
        raise NotImplementedError()

    def get_room(self, name):
        raise NotImplementedError()

    def send_message(self, message):
        raise NotImplementedError()

    @property
    def default_room(self):
        if not self._default_room:
            room_name = None
            if 'default_room' in self._config:
                room_name = self._config['default_room']
            else:
                room_name = self._config['rooms'][0]
            self._default_room = self.get_room(room_name)
        return self._default_room

    @property
    def mention_name(self):
        if 'mention_name' in self._config:
            return self._config['mention_name']
        else:
            return None


class Callback(object):
    def __init__(self, func, priority=100):
        self._callback = None
        self._func = func
        self.priority = priority
        if hasattr(func, '_priority'):
            self.priority = func._priority
        self.lock = ''

    @property
    def __name__(self):
        return self._func.__name__

    def get_callback(self, factory):
        if not self._callback:
            self._callback = factory.get_callback(self._func)
        return self._callback


class Matcher(Callback):
    def __init__(self, func, pattern, priority=50, condition=lambda x: True):
        super().__init__(func, priority)
        self.pattern = pattern
        self.condition = condition
        self.regex = None

    def compile(self, **format_args):
        self.regex = regex.compile(self.pattern.format(**format_args))


@functools.total_ordering
class ScheduledCallback(Callback):
    def __init__(self, func, cron):
        self._cron = cron
        self.get_next()
        super().__init__(func, self.timestamp)

    def get_next(self):
        self.timestamp = self._cron.get_next(datetime.datetime).timestamp()
        return self.timestamp

    def _is_comparable(self, other):
        if not hasattr(other, 'timestamp'):
            raise NotImplemented('Cannot compare %s and %s',
                                 type(self), type(other))

    def __eq__(self, other):
        self._is_comparable(other)
        return self.timestamp == other.timestamp

    def __lt__(self, other):
        self._is_comparable(other)
        return self.timestamp < other.timestamp
