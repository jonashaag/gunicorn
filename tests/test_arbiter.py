# -*- coding: utf-8 -
#
# This file is part of gunicorn released under the MIT license.
# See the NOTICE for more information.

import os

try:
    import unittest.mock as mock
except ImportError:
    import mock

import gunicorn.app.base
import gunicorn.arbiter


class DummyApplication(gunicorn.app.base.BaseApplication):
    """
    Dummy application that has a default configuration.
    """

    def init(self, parser, opts, args):
        """No-op"""

    def load(self):
        """No-op"""

    def load_config(self):
        """No-op"""


def test_arbiter_shutdown_closes_listeners():
    arbiter = gunicorn.arbiter.Arbiter(DummyApplication())
    listener1 = mock.Mock()
    listener2 = mock.Mock()
    arbiter.LISTENERS = [listener1, listener2]
    arbiter.stop()
    listener1.close.assert_called_with()
    listener2.close.assert_called_with()


@mock.patch('os.fork')
def test_arbiter_calls_worker_exit(mock_os_fork):
    mock_os_fork.return_value = 0

    arbiter = gunicorn.arbiter.Arbiter(DummyApplication())
    arbiter.cfg.settings['worker_exit'] = mock.Mock()
    arbiter.pid = None
    mock_worker = mock.Mock()
    arbiter.worker_class = mock.Mock(return_value=mock_worker)
    try:
        arbiter.spawn_worker()
    except SystemExit:
        pass
    arbiter.cfg.worker_exit.assert_called_with(arbiter, mock_worker)


@mock.patch('os.waitpid')
def test_arbiter_reap_workers(mock_os_waitpid):
    mock_os_waitpid.side_effect = [(42, 0), (0, 0)]
    arbiter = gunicorn.arbiter.Arbiter(DummyApplication())
    arbiter.cfg.settings['child_exit'] = mock.Mock()
    mock_worker = mock.Mock()
    arbiter.WORKERS = {42: mock_worker}
    arbiter.reap_workers()
    mock_worker.tmp.close.assert_called_with()
    arbiter.cfg.child_exit.assert_called_with(arbiter, mock_worker)


class PreloadedAppWithEnvSettings(DummyApplication):
    """
    Simple application that makes use of the 'preload' feature to
    start the application before spawning worker processes and sets
    environmental variable configuration settings.
    """

    def load_config(self):
        """Set the 'preload_app' and 'raw_env' settings in order to verify their
        interaction below.
        """
        self.cfg.set('raw_env', [
            'SOME_PATH=/tmp/something', 'OTHER_PATH=/tmp/something/else'])
        self.cfg.set('preload_app', True)

    def wsgi(self):
        """Assert that the expected environmental variables are set when
        the main entry point of this application is called as part of a
        'preloaded' application.
        """
        verify_env_vars()
        return super(PreloadedAppWithEnvSettings, self).wsgi()


def verify_env_vars():
    assert os.getenv('SOME_PATH') == '/tmp/something'
    assert os.getenv('OTHER_PATH') == '/tmp/something/else'


def test_env_vars_available_during_preload():
    """Ensure that configured environmental variables are set during the
    initial set up of the application (called from the .setup() method of
    the Arbiter) such that they are available during the initial loading
    of the WSGI application.
    """
    # Note that we aren't making any assertions here, they are made in the
    # dummy application object being loaded here instead.
    gunicorn.arbiter.Arbiter(PreloadedAppWithEnvSettings())
