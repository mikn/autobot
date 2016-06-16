import os
import sys
import threading
import logging
import toml
import argparse

LOG = logging.getLogger(__name__)

import autobot
import autobot.config
from . import scheduler

# TODO: Get rid of all globals, let main own all instantiation
# TODO: Output formatter system
# TODO: Make dev help and normal help output different things
# TODO: HipChat Plugin
# TODO: Core Admin Plugin
# TODO: Generic worker thread pool
# TODO: Plugin folder scaffolding script
# TODO: Live plugin reloads using inotify
# TODO: Testing using Behave
# TODO: Create fake factory that satisfies the needs of the brain thread
# TODO: Make the brain and scheduler into classes rather than module methods
# TODO: Documentation using Sphinx
# TODO: Redis Plugin
# TODO: ACL..?
# TODO: Nicer CLI than logger?


def parse_args():
    parser = argparse.ArgumentParser(
        description='The primary foreground script for the chatbot library '
        'autobot')
    parser.add_argument('--debug', action='store_true',
                        help='Enable debug output')
    parser.add_argument('--config-file', help='The configuration file')
    parser.add_argument('--custom-plugins', help='The folder in which '
                        'to look for custom plugins to execute with.',
                        default=os.curdir)
    return parser.parse_args()


def main():
    args = parse_args()
    if args.debug:
        logging.getLogger('autobot').setLevel(logging.DEBUG)

    f = args.config_file

    config = autobot.config.defaults
    if f and os.path.exists(f):
        LOG.debug('Reading configuration file from %s!', f)
        with open(f) as conf:
            config.update(toml.loads(conf.read()))

    factory = autobot.Factory(config)
    LOG.debug('Importing plugins!')
    factory.start()

    brain = autobot.brain.Brain(factory, autobot.brain.matchers)
    brain_thread = threading.Thread(name='brain', target=brain.boot)

    timer_thread = threading.Thread(
        name='timer',
        target=scheduler.timer_thread,
        args=(factory, config.get('scheduler_resolution'))
    )

    try:
        brain_thread.start()
        timer_thread.start()
        LOG.debug('Starting service listener!')
        service = factory.get_service()
        service.start()

        # Make sure the main thread is blocking so we can catch the interrupt
        brain_thread.join()
        timer_thread.join()

    except (KeyboardInterrupt, SystemExit):
        LOG.info('\nI have been asked to quit nicely, and so I will!')
        scheduler.shutdown()
        service.shutdown()
        brain.shutdown()
        sys.exit()


if __name__ == '__main__':
    main()
