# -*- coding: utf-8 -*-
import stat

import pytest

from docker_ci_deploy.__main__ import DockerCiDeployRunner


def assert_output_lines(capfd, stdout_lines, stderr_lines=[]):
    out, err = capfd.readouterr()

    out_lines = out.split('\n')
    assert out_lines.pop() == ''
    assert out_lines == stdout_lines

    err_lines = err.split('\n')
    assert err_lines.pop() == ''
    assert err_lines == stderr_lines


class TestDockerCiDeployRunner(object):
    @pytest.fixture(scope='session')
    def echo_script(self, tmpdir_factory):
        path = tmpdir_factory.mktemp('tmp').join('echo_script.sh')
        path.write('#!/bin/sh\necho "$@"\n')
        path.chmod(path.stat().mode | stat.S_IEXEC)
        return str(path)

    def test_defaults(self, capfd, echo_script):
        """
        When the runner is run with defaults, the image should be pushed.
        """
        runner = DockerCiDeployRunner(executable=echo_script)
        runner.run('test-image')

        assert_output_lines(capfd, ['push test-image'])

    def test_tags(self, capfd, echo_script):
        """
        When tags are provided to the runner, the image should be tagged and
        each tag should be pushed.
        """
        runner = DockerCiDeployRunner(executable=echo_script)
        runner.run('test-image', tags=['abc', 'def'])

        assert_output_lines(capfd, [
            'tag test-image test-image:abc',
            'tag test-image test-image:def',
            'push test-image:abc',
            'push test-image:def'
        ])
