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

    def test_tag_replacement(self, capfd, echo_script):
        """
        When tags are provided to the runner and the provided image has a tag,
        that tag should be tagged with the new tag, and the the new tag should
        be pushed.
        """
        runner = DockerCiDeployRunner(executable=echo_script)
        runner.run('test-image:abc', tags=['def'])

        assert_output_lines(capfd, [
            'tag test-image:abc test-image:def',
            'push test-image:def'
        ])

    def test_registry(self, capfd, echo_script):
        """
        When a registry is provided to the runner, the image should be tagged
        with the registry and pushed.
        """
        runner = DockerCiDeployRunner(executable=echo_script)
        runner.run('test-image', registry='registry.example.com:5000')

        assert_output_lines(capfd, [
            'tag test-image registry.example.com:5000/test-image',
            'push registry.example.com:5000/test-image'
        ])

    def test_tags_and_registry(self, capfd, echo_script):
        """
        When tags and a registry are provided to the runner, the image should
        be tagged with both the tags and the registry and pushed.
        """
        runner = DockerCiDeployRunner(executable=echo_script)
        runner.run('test-image:ghi', tags=['abc', 'def'],
                   registry='registry.example.com:5000')

        assert_output_lines(capfd, [
            'tag test-image:ghi registry.example.com:5000/test-image:abc',
            'tag test-image:ghi registry.example.com:5000/test-image:def',
            'push registry.example.com:5000/test-image:abc',
            'push registry.example.com:5000/test-image:def'
        ])

    def test_login(self, capfd, echo_script):
        """
        When login details are provided to the runner, a login request should
        be made and the image should be pushed.
        """
        runner = DockerCiDeployRunner(executable=echo_script)
        runner.run('test-image', login='janedoe:pa$$word')

        assert_output_lines(capfd, [
            'login --username janedoe --password pa$$word',
            'push test-image'
        ])

    def test_registry_and_login(self, capfd, echo_script):
        """
        When a registry and login details are provided to the runner, the image
        should be tagged with the registry and a login request should be made
        to the specified registry. The image should be pushed.
        """
        runner = DockerCiDeployRunner(executable=echo_script)
        runner.run('test-image', registry='registry.example.com:5000',
                   login='janedoe:pa$$word')

        assert_output_lines(capfd, [
            'tag test-image registry.example.com:5000/test-image',
            'login --username janedoe --password pa$$word '
            'registry.example.com:5000',
            'push registry.example.com:5000/test-image'
        ])

    def test_all_options(self, capfd, echo_script):
        """
        When tags, a registry, and login details are provided to the runner,
        the image should be tagged with the tags and registry, a login request
        should be made to the specified registry, and the tags should be
        pushed.
        """
        runner = DockerCiDeployRunner(executable=echo_script)
        runner.run('test-image:tag', tags=['latest', 'best'],
                   registry='registry.example.com:5000',
                   login='janedoe:pa$$word')

        assert_output_lines(capfd, [
            'tag test-image:tag registry.example.com:5000/test-image:latest',
            'tag test-image:tag registry.example.com:5000/test-image:best',
            'login --username janedoe --password pa$$word '
            'registry.example.com:5000',
            'push registry.example.com:5000/test-image:latest',
            'push registry.example.com:5000/test-image:best'
        ])

    def test_dry_run(self, capfd, echo_script):
        """
        When running in dry-run mode, the expected commands should be logged
        and no other output should be produced as no subprocesses should be
        run.
        """
        runner = DockerCiDeployRunner(executable=echo_script, dry_run=True)
        logs = []
        runner.logger = lambda *args: logs.append(' '.join(args))
        runner.run('test-image:tag', tags=['latest'])

        expected = [
            'tag test-image:tag test-image:latest',
            'push test-image:latest'
        ]
        expected = ['%s %s' % (echo_script, s,) for s in expected]
        assert logs == expected

        assert_output_lines(capfd, [], [])

    def test_dry_run_obfuscates_password(self, capfd, echo_script):
        """
        When running in dry-run mode and login details are provided, the user's
        password should not be logged.
        """
        runner = DockerCiDeployRunner(executable=echo_script, dry_run=True)
        logs = []
        runner.logger = lambda *args: logs.append(' '.join(args))
        runner.run('test-image', login='janedoe:pa$$word')

        expected = [
            'login --username janedoe --password <password>',
            'push test-image'
        ]
        expected = ['%s %s' % (echo_script, s,) for s in expected]
        assert logs == expected

        assert_output_lines(capfd, [], [])
