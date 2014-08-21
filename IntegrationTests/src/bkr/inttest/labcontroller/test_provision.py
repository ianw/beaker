
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.

import sys
import time
import logging
import pkg_resources
from turbogears.database import session
from nose.plugins.skip import SkipTest
from bkr.server.model import LabController, PowerType, CommandStatus
from bkr.labcontroller.config import get_conf
from bkr.inttest import data_setup, Process
from bkr.inttest.assertions import wait_for_condition
from bkr.inttest.labcontroller import LabControllerTestCase, processes, \
        daemons_running_externally
from bkr.server.model import System, User

log = logging.getLogger(__name__)

def wait_for_commands_to_finish(system, timeout):
    def _commands_finished():
        with session.begin():
            session.expire_all()
            return system.command_queue[0].status in \
                    (CommandStatus.completed, CommandStatus.failed)
    wait_for_condition(_commands_finished, timeout=timeout)

def assert_command_is_delayed(command, min_delay, timeout):
    """
    Asserts that the given command is not run for at least *min_delay* seconds, 
    and also completes within *timeout* seconds after the delay has elapsed.
    """
    def _command_completed():
        with session.begin():
            session.refresh(command)
            return command.status == CommandStatus.completed
    assert not _command_completed(), 'Command should not be completed initially'
    log.info('Command %s is not completed initially', command.id)
    time.sleep(min_delay)
    assert not _command_completed(), 'Command should still not be completed after delay'
    log.info('Command %s is still not completed after delay', command.id)
    wait_for_condition(_command_completed, timeout=timeout)
    log.info('Command %s is completed', command.id)

class PowerTest(LabControllerTestCase):

    # BEWARE IF USING 'dummy' POWER TYPE:
    # The 'dummy' power script sleeps for $power_id seconds, therefore tests 
    # must ensure they set power_id to a sensible value ('0' or '' unless the 
    # test demands a longer delay).

    def test_power_quiescent_period(self):
        # Test that we do in fact wait for the quiescent period to pass
        # before running a command.
        # This time is needed to guarantee that we are actually waiting for
        # the quiescent period and not waiting for another poll loop:
        quiescent_period = get_conf().get('SLEEP_TIME') * 3
        with session.begin():
            system = data_setup.create_system(lab_controller=self.get_lc())
            system.power.power_type = PowerType.lazy_create(name=u'dummy')
            system.power.power_quiescent_period = quiescent_period
            system.power.power_id = u'' # make power script not sleep
            system.power.delay_until = None
            system.action_power(action=u'off', service=u'testdata')
            command = system.command_queue[0]
        assert_command_is_delayed(command, quiescent_period - 0.5, 10)

    # https://bugzilla.redhat.com/show_bug.cgi?id=1079816
    def test_quiescent_period_is_obeyed_for_consecutive_commands(self):
        quiescent_period = 3
        with session.begin():
            system = data_setup.create_system(lab_controller=self.get_lc())
            system.power.power_type = PowerType.lazy_create(name=u'dummy')
            system.power.power_quiescent_period = quiescent_period
            system.power.power_id = u'' # make power script not sleep
            system.power.delay_until = None
            system.action_power(action=u'on', service=u'testdata')
            system.action_power(action=u'on', service=u'testdata')
            system.action_power(action=u'on', service=u'testdata')
            commands = system.command_queue[:3]
        assert_command_is_delayed(commands[2], quiescent_period - 0.5, 10)
        assert_command_is_delayed(commands[1], quiescent_period - 0.5, 10)
        assert_command_is_delayed(commands[0], quiescent_period - 0.5, 10)

    def test_power_quiescent_period_statefulness_not_elapsed(self):
        if daemons_running_externally():
            raise SkipTest('cannot examine logs of remote beaker-provision')
        provision_process, = [p for p in processes if p.name == \
            'beaker-provision']
        # Initial lookup of this system will reveal no state, so will delay
        # for the whole quiescent period
        try:
            provision_process.start_output_capture()
            with session.begin():
                system = data_setup.create_system(lab_controller=self.get_lc())
                system.power.power_type = PowerType.lazy_create(name=u'dummy')
                system.power.power_quiescent_period = 1
                system.power.power_id = u'' # make power script not sleep
                system.power.delay_until = None
                system.action_power(action=u'off', service=u'testdata')
            wait_for_commands_to_finish(system, timeout=10)
        finally:
            provision_output = provision_process.finish_output_capture()
        self.assertIn('Entering quiescent period, delaying 1 seconds for '
            'command %s'  % system.command_queue[0].id, provision_output)
        # Increase the quiescent period, to ensure we enter it
        try:
            provision_process.start_output_capture()
            with session.begin():
                system = System.by_id(system.id, User.by_user_name('admin'))
                system.power.power_quiescent_period = 10
                system.action_power(action=u'on', service=u'testdata')
            wait_for_commands_to_finish(system, timeout=15)
        finally:
            provision_output = provision_process.finish_output_capture()
        self.assertIn('Entering quiescent period', provision_output)

    def test_power_quiescent_period_statefulness_elapsed(self):
        if daemons_running_externally():
            raise SkipTest('cannot examine logs of remote beaker-provision')
        provision_process, = [p for p in processes if p.name == \
            'beaker-provision']
        # Initial lookup of this system will reveal no state, so will delay
        # for the whole quiescent period
        try:
            provision_process.start_output_capture()
            with session.begin():
                system = data_setup.create_system(lab_controller=self.get_lc())
                system.power.power_type = PowerType.lazy_create(name=u'dummy')
                system.power.power_quiescent_period = 1
                system.power.power_id = u'' # make power script not sleep
                system.power.delay_until = None
                system.action_power(action=u'off', service=u'testdata')
            wait_for_commands_to_finish(system, timeout=10)
        finally:
            provision_output = provision_process.finish_output_capture()
        self.assertIn('Entering quiescent period, delaying 1 seconds for '
            'command %s'  % system.command_queue[0].id, provision_output)
        # This guarantees our quiescent period has elapsed and be ignored
        time.sleep(1)
        try:
            provision_process.start_output_capture()
            with session.begin():
                system = System.by_id(system.id, User.by_user_name('admin'))
                system.action_power(action=u'off', service=u'testdata')
            wait_for_commands_to_finish(system, timeout=10)
        finally:
            provision_output = provision_process.finish_output_capture()
        self.assertNotIn('Entering queiscent period', provision_output)

    # https://bugzilla.redhat.com/show_bug.cgi?id=951309
    def test_power_commands_are_not_run_twice(self):
        # We will make the dummy power script sleep for this long:
        power_sleep = 4
        # To reproduce this bug, we need to queue up three commands for the 
        # same system (so they are run in sequence by beaker-provision), where 
        # the commands take enough time that the second one will still be 
        # running on the next iteration of the polling loop. The third command 
        # will be run twice.
        assert power_sleep < get_conf().get('SLEEP_TIME')
        assert 2 * power_sleep > get_conf().get('SLEEP_TIME')
        with session.begin():
            system = data_setup.create_system(lab_controller=self.get_lc())
            system.power.power_type = PowerType.lazy_create(name=u'dummy')
            system.power.power_id = power_sleep # make power script sleep
            system.action_power(action=u'off', service=u'testdata')
            system.action_power(action=u'off', service=u'testdata')
            system.action_power(action=u'off', service=u'testdata')
        wait_for_commands_to_finish(system, timeout=5 * power_sleep)
        with session.begin():
            session.expire_all()
            self.assertEquals(system.command_queue[0].status, CommandStatus.completed)
            self.assertEquals(system.command_queue[1].status, CommandStatus.completed)
            self.assertEquals(system.command_queue[2].status, CommandStatus.completed)
            # The bug manifests as two "Completed" records for the power 
            # command which ran twice
            self.assertEquals(system.dyn_activity
                    .filter_by(field_name=u'Power', new_value=u'Completed')
                    .count(), 3)

    def test_blank_power_passwords(self):
        if daemons_running_externally():
            raise SkipTest('cannot examine logs of remote beaker-provision')
        provision_process, = [p for p in processes if p.name == 'beaker-provision']
        try:
            provision_process.start_output_capture()
            with session.begin():
                system = data_setup.create_system(lab_controller=self.get_lc())
                system.power.address = None
                system.power.power_type = PowerType.lazy_create(name=u'dummy')
                system.power.power_id = u'' # make power script not sleep
                system.power.power_passwd = None
                system.action_power(action=u'off', service=u'testdata')
            wait_for_commands_to_finish(system, timeout=2 * get_conf().get('SLEEP_TIME'))
        finally:
            provision_output = provision_process.finish_output_capture()
        # The None type is passed in from the db. Later in the code it is converted
        # to the empty string, as it should be.
        self.assertIn("'passwd': None", provision_output, provision_output)

    # https://bugzilla.redhat.com/show_bug.cgi?id=986108
    def test_power_passwords_are_not_logged(self):
        if daemons_running_externally():
            raise SkipTest('cannot examine logs of remote beaker-provision')
        provision_process, = [p for p in processes if p.name == 'beaker-provision']
        try:
            provision_process.start_output_capture()
            with session.begin():
                system = data_setup.create_system(lab_controller=self.get_lc())
                system.power.power_type = PowerType.lazy_create(name=u'dummy')
                system.power.power_id = u'' # make power script not sleep
                system.power.power_passwd = u'dontleakmebro'
                system.action_power(action=u'off', service=u'testdata')
            wait_for_commands_to_finish(system, timeout=2 * get_conf().get('SLEEP_TIME'))
        finally:
            provision_output = provision_process.finish_output_capture()
        self.assert_('Handling command' in provision_output, provision_output)
        self.assert_('Launching power script' in provision_output, provision_output)
        self.assert_(system.power.power_passwd not in provision_output, provision_output)

class ConfigureNetbootTest(LabControllerTestCase):

    @classmethod
    def setUpClass(cls):
        cls.distro_server = Process('http_server.py', args=[sys.executable,
                    pkg_resources.resource_filename('bkr.inttest', 'http_server.py'),
                    '--base', '/notexist'],
                listen_port=19998)
        cls.distro_server.start()

    @classmethod
    def tearDownClass(cls):
        cls.distro_server.stop()

    # https://bugzilla.redhat.com/show_bug.cgi?id=1094553
    def test_timeout_is_enforced_for_fetching_images(self):
        with session.begin():
            lc = self.get_lc()
            system = data_setup.create_system(arch=u'x86_64', lab_controller=lc)
            distro_tree = data_setup.create_distro_tree(arch=u'x86_64',
                    lab_controllers=[lc],
                    # /slow/600 means the response will be delayed 10 minutes
                    urls=['http://localhost:19998/slow/600/'])
            system.configure_netboot(distro_tree=distro_tree,
                    kernel_options=u'', service=u'testdata')
        wait_for_commands_to_finish(system, timeout=(2 * get_conf().get('SLEEP_TIME')
                + get_conf().get('IMAGE_FETCH_TIMEOUT')))
        self.assertEquals(system.command_queue[0].action, u'configure_netboot')
        self.assertEquals(system.command_queue[0].status, CommandStatus.failed)
        self.assertEquals(system.command_queue[0].new_value,
                u'URLError: <urlopen error timed out>')
