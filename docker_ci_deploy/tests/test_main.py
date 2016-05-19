# -*- coding: utf-8 -*-
import sys

import pytest

from subprocess import CalledProcessError

from docker_ci_deploy.__main__ import (
    cmd, DockerCiDeployRunner, main, strip_image_tag)

""" strip_image_tag() """


def test_strip_image_tag():
    """
    Given an image tag with registry, name and tag components, strip_image_tag
    should strip only the tag component.
    """
    image = 'registry.example.com:5000/user/name:tag'
    stripped_tag = strip_image_tag(image)

    assert stripped_tag == 'registry.example.com:5000/user/name'


def test_strip_image_tag_no_tag():
    """
    Given an image tag with only registry and name components, strip_image_tag
    should return the image name unchanged.
    """
    image = 'registry.example.com:5000/user/name'
    stripped_tag = strip_image_tag(image)

    assert stripped_tag == image


def test_strip_image_tag_no_registry():
    """
    Given an image tag with only name and tag components, strip_image_tag
    should strip the tag component.
    """
    image = 'user/name:tag'
    stripped_tag = strip_image_tag(image)

    assert stripped_tag == 'user/name'


def test_strip_image_tag_no_registry_or_tag():
    """
    Given an image tag with only name components, strip_image_tag should return
    the image name unchanged.
    """
    image = 'user/name'
    stripped_tag = strip_image_tag(image)

    assert stripped_tag == image


def test_strip_image_tag_unparsable():
    """ Given a malformed image tag, strip_image_tag should throw an error. """
    image = 'this:is:invalid/user:test/name:tag/'
    with pytest.raises(RuntimeError) as e_info:
        strip_image_tag(image)

    assert str(e_info.value) == 'Unable to parse tag "%s"' % (image,)


""" cmd() """


def assert_output_lines(capfd, stdout_lines, stderr_lines=[]):
    out, err = capfd.readouterr()

    out_lines = out.split('\n')
    assert out_lines.pop() == ''
    assert out_lines == stdout_lines

    err_lines = err.split('\n')
    assert err_lines.pop() == ''
    assert err_lines == stderr_lines


def test_cmd_stdout(capfd):
    """
    When a command writes to stdout, that output should be captured and written
    to Python's stdout.
    """
    cmd(['echo', 'Hello, World!'])

    assert_output_lines(capfd, stdout_lines=['Hello, World!'], stderr_lines=[])


def test_cmd_stderr(capfd):
    """
    When a command writes to stderr, that output should be captured and written
    to Python's stderr.
    """
    # Have to do something a bit more complicated to echo to stderr w/o shell
    cmd(['awk', 'BEGIN { print "Hello, World!" > "/dev/stderr" }'])

    assert_output_lines(capfd, stdout_lines=[], stderr_lines=['Hello, World!'])


def test_cmd_error(capfd):
    """
    When a command exits with a non-zero return code, an error should be raised
    with the correct information about the result of the command. There should
    be no output to stdout or stderr.
    """
    args = ['awk', 'BEGIN { print "errored"; exit 1 }']
    with pytest.raises(CalledProcessError) as e_info:
        cmd(args)

    e = e_info.value
    assert e.cmd == args
    assert e.returncode == 1
    assert e.output == b'errored\n'

    assert_output_lines(capfd, [], [])


class TestDockerCiDeployRunner(object):
    def test_defaults(self, capfd):
        """
        When the runner is run with defaults, the image should be pushed.
        """
        runner = DockerCiDeployRunner(executable='echo')
        runner.run('test-image')

        assert_output_lines(capfd, ['push test-image'])

    def test_tags(self, capfd):
        """
        When tags are provided to the runner, the image should be tagged and
        each tag should be pushed.
        """
        runner = DockerCiDeployRunner(executable='echo')
        runner.run('test-image', tags=['abc', 'def'])

        assert_output_lines(capfd, [
            'tag test-image test-image:abc',
            'tag test-image test-image:def',
            'push test-image:abc',
            'push test-image:def'
        ])

    def test_tag_replacement(self, capfd):
        """
        When tags are provided to the runner and the provided image has a tag,
        that tag should be tagged with the new tag, and the the new tag should
        be pushed.
        """
        runner = DockerCiDeployRunner(executable='echo')
        runner.run('test-image:abc', tags=['def'])

        assert_output_lines(capfd, [
            'tag test-image:abc test-image:def',
            'push test-image:def'
        ])

    def test_registry(self, capfd):
        """
        When a registry is provided to the runner, the image should be tagged
        with the registry and pushed.
        """
        runner = DockerCiDeployRunner(executable='echo')
        runner.run('test-image', registry='registry.example.com:5000')

        assert_output_lines(capfd, [
            'tag test-image registry.example.com:5000/test-image',
            'push registry.example.com:5000/test-image'
        ])

    def test_tags_and_registry(self, capfd):
        """
        When tags and a registry are provided to the runner, the image should
        be tagged with both the tags and the registry and pushed.
        """
        runner = DockerCiDeployRunner(executable='echo')
        runner.run('test-image:ghi', tags=['abc', 'def'],
                   registry='registry.example.com:5000')

        assert_output_lines(capfd, [
            'tag test-image:ghi registry.example.com:5000/test-image:abc',
            'tag test-image:ghi registry.example.com:5000/test-image:def',
            'push registry.example.com:5000/test-image:abc',
            'push registry.example.com:5000/test-image:def'
        ])

    def test_login(self, capfd):
        """
        When login details are provided to the runner, a login request should
        be made and the image should be pushed.
        """
        runner = DockerCiDeployRunner(executable='echo')
        runner.run('test-image', login='janedoe:pa$$word')

        assert_output_lines(capfd, [
            'login --username janedoe --password pa$$word',
            'push test-image'
        ])

    def test_registry_and_login(self, capfd):
        """
        When a registry and login details are provided to the runner, the image
        should be tagged with the registry and a login request should be made
        to the specified registry. The image should be pushed.
        """
        runner = DockerCiDeployRunner(executable='echo')
        runner.run('test-image', registry='registry.example.com:5000',
                   login='janedoe:pa$$word')

        assert_output_lines(capfd, [
            'tag test-image registry.example.com:5000/test-image',
            'login --username janedoe --password pa$$word '
            'registry.example.com:5000',
            'push registry.example.com:5000/test-image'
        ])

    def test_all_options(self, capfd):
        """
        When tags, a registry, and login details are provided to the runner,
        the image should be tagged with the tags and registry, a login request
        should be made to the specified registry, and the tags should be
        pushed.
        """
        runner = DockerCiDeployRunner(executable='echo')
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

    def test_dry_run(self, capfd):
        """
        When running in dry-run mode, the expected commands should be logged
        and no other output should be produced as no subprocesses should be
        run.
        """
        runner = DockerCiDeployRunner(dry_run=True)
        logs = []
        runner.logger = lambda *args: logs.append(' '.join(args))
        runner.run('test-image:tag', tags=['latest'])

        expected = [
            'docker tag test-image:tag test-image:latest',
            'docker push test-image:latest'
        ]
        assert logs == expected

        assert_output_lines(capfd, [], [])

    def test_dry_run_obfuscates_password(self, capfd):
        """
        When running in dry-run mode and login details are provided, the user's
        password should not be logged.
        """
        runner = DockerCiDeployRunner(dry_run=True)
        logs = []
        runner.logger = lambda *args: logs.append(' '.join(args))
        runner.run('test-image', login='janedoe:pa$$word')

        expected = [
            'docker login --username janedoe --password <password>',
            'docker push test-image'
        ]
        assert logs == expected

        assert_output_lines(capfd, [], [])


""" main() """


def test_main_args(capfd):
    """
    When the main function is given a set of common arguments, the script
    should be run as expected.
    """
    main([
        '--login', 'janedoe:pa$$word',
        '--registry', 'registry.example.com:5000',
        '--executable', 'echo',
        'test-image:abc'
    ])

    assert_output_lines(capfd, [
        'tag test-image:abc registry.example.com:5000/test-image:abc',
        'login --username janedoe --password pa$$word '
        'registry.example.com:5000',
        'push registry.example.com:5000/test-image:abc'
    ])


def test_main_image_required(capfd):
    """
    When the main function is given no image argument, it should exit with a
    return code of 2 and inform the user of the missing argument.
    """
    with pytest.raises(SystemExit) as e_info:
        main(['--tag', 'abc'])

    assert e_info.value.args == (2,)

    out, err = capfd.readouterr()
    assert out == ''

    # More useful error message added to argparse in Python 3
    if sys.version_info >= (3,):
        assert 'error: the following arguments are required: image' in err
    else:
        assert 'error: too few arguments' in err


def test_main_many_tags(capfd):
    """
    When the main function is given multiple tag arguments in different ways,
    the tags should be correctly passed through to the runner.
    """
    main([
        '--tag', 'abc', 'def',
        '-t', 'ghi',
        '--executable', 'echo',
        'test-image:xyz'
    ])

    assert_output_lines(capfd, [
        'tag test-image:xyz test-image:abc',
        'tag test-image:xyz test-image:def',
        'tag test-image:xyz test-image:ghi',
        'push test-image:abc',
        'push test-image:def',
        'push test-image:ghi'
    ])
