import os
import sys
import threading
import logging
import toml
import argparse

LOG = logging.getLogger(__name__)

import autobot
import autobot.config
from . import brain
from . import scheduler

# TODO: Help parsing
# TODO: HipChat Plugin
# TODO: Core Admin Plugin
# TODO: Plugin folder scaffolding script
# TODO: Live plugin reloads using inotify
# TODO: Event system for state change in service providers
# TODO: Testing using Behave
# TODO: Documentation using Sphinx
# TODO: Format {} shorthands in plugins
# TODO: Redis Plugin
# TODO: ACL..?
# TODO: Nicer CLI than logger?


def parse_args():
    parser = argparse.ArgumentParser(
        description='The primary foreground script for the chatbot library'
        'Autobot')
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
        LOG.debug('Reading configuration file from {}!'.format(f))
        with open(f) as conf:
            config.update(toml.loads(conf.read()))

    LOG.debug('Importing plugins!')
    factory = autobot.Factory(config)

    brain_thread = threading.Thread(
        name='brain',
        target=brain.boot,
        args=(factory,)
    )

    timer_thread = threading.Thread(
        name='timer',
        target=scheduler.timer_thread,
        args=(factory, config.get('scheduler_resolution'))
    )

    LOG.debug('Booting brain!')
    try:
        brain_thread.start()

        LOG.debug('Revving up the scheduler!')
        timer_thread.start()

        LOG.debug('Starting service listener!')
        service = factory.get_service()
        service.start()

        # TODO: Evaluate placement of this... thing
        [m.compile(mention_name=service.mention_name) for m in brain.matchers]

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
