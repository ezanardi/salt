# -*- coding: utf-8 -*-
'''
Beacon to monitor active channels and calls on an Asterisk PBX.
'''

# Import Python libs
from __future__ import absolute_import
import logging
import re
import os

# Salt libs
import salt.utils

log = logging.getLogger(__name__)

ACTIVE_CHANNELS_KWD = 'channels'
ACTIVE_CALLS_KWD = 'calls'
PROBES = [ACTIVE_CHANNELS_KWD, ACTIVE_CALLS_KWD]
CHANNELS_PATTERN = re.compile(r'(\d+) active channels?$')
CALLS_PATTERN = re.compile(r'(\d+) active calls?$')
CALLS_WITH_MAXCALLS_PATTERN = re.compile(r'(\d+) of (\d+) max active calls?')


def __virtual__():
    return bool(salt.utils.which('asterisk')) \
        or (False, 'The asterisk_calls '
                   'beacon cannot be loaded. Asterisk is not installed.')


def __validate__(config):
    '''
    Validate the beacon configuration
    '''
    # Temporary fix for https://github.com/saltstack/salt/issues/38121
    if isinstance(config, list):
        tmpconfig = {}
        map(tmpconfig.update, config)
        config = tmpconfig

    if not isinstance(config, dict):
        return False, ('Configuration for asterisk_calls beacon '
                       'must be a dictionary.')
    for key, value in config.items():
        if key not in PROBES:
            return False, ('Invalid name "{0}" for asterisk_calls probe. '
                           'Must be one of {1}'.format(key, PROBES))
        if not isinstance(value, list):
            return False, ('Invalid value "{0}" for asterisk_calls probe {1}. '
                           'Must be a [min, max] list.'.format(value, key))
        if len(value) != 2:
            return False, ('Invalid value "{0}" for asterisk_calls probe {1}. '
                           'Must be a [min, max] list.'.format(value, key))
    return True, 'Valid beacon configuration'


def beacon(config):
    '''
    Monitor active channels and calls on an Asterisk PBX running on the minion.

    Define a range for each probe and emit a beacon when the value is
    out of range.

    .. code-block:: yaml

        asterisk_calls:
          channels: [0, 50]
          calls: [0, 25]

    For Nitrogen, beacon configuration must be a list.

    .. code-block:: yaml

        asterisk_calls:
        - channels: [0, 50]
        - calls: [0, 25]

    '''
    log.trace('asterisk_calls beacon starting')
    ret = []

    # Temporary fix for https://github.com/saltstack/salt/issues/38121
    if isinstance(config, list):
        tmpconfig = {}
        map(tmpconfig.update, config)
        config = tmpconfig

    if not config:    # Nothing to probe
        return ret

    # Read values from asterisk
    result = __salt__['cmd.run_all']('asterisk -x "core show channels"')
    if result['retcode'] != 0:
        # cmd.run_all logs errors unless we have told it not to do so
        return ret
    out = result['stdout']

    for line in out.split(os.linesep):
        # Is an "active channels" line?
        match = CHANNELS_PATTERN.match(line)
        if match:
            channels = int(match.group(1))
            if ACTIVE_CHANNELS_KWD in config:  # probe active channels
                channels_min, channels_max = config[ACTIVE_CHANNELS_KWD]
                if not channels_min <= channels <= channels_max:
                    ret.append({
                        'tag': 'active_channels',
                        'channels': channels
                    })
            continue    # Process next line of output
        # Is an "active calls" line? (2 patterns, without and with maxcalls)
        match = CALLS_PATTERN.match(line) or \
            CALLS_WITH_MAXCALLS_PATTERN.match(line)
        if match:
            calls = int(match.group(1))
            if ACTIVE_CALLS_KWD in config:  # probe active calls
                calls_min, calls_max = config[ACTIVE_CALLS_KWD]
                if not calls_min <= calls <= calls_max:
                    ret.append({
                        'tag': 'active_calls',
                        'calls': calls
                    })

    return ret
