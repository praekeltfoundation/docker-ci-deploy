# -*- coding: utf-8 -*-
import re
import stat
import sys
from subprocess import CalledProcessError

from testtools import ExpectedException
from testtools.assertions import assert_that
from testtools.matchers import (
    AfterPreprocessing as After, Equals, MatchesRegex, MatchesStructure, Not)

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

    assert_that(stripped_tag, Equals('registry.example.com:5000/user/name'))


def test_strip_image_tag_no_tag():
    """
    Given an image tag with only registry and name components, strip_image_tag
    should return the image name unchanged.
    """
    image = 'registry.example.com:5000/user/name'
    stripped_tag = strip_image_tag(image)

    assert_that(stripped_tag, Equals(image))


def test_strip_image_tag_no_registry():
    """
    Given an image tag with only name and tag components, strip_image_tag
    should strip the tag component.
    """
    image = 'user/name:tag'
    stripped_tag = strip_image_tag(image)

    assert_that(stripped_tag, Equals('user/name'))


def test_strip_image_tag_no_registry_or_tag():
    """
    Given an image tag with only name components, strip_image_tag should return
    the image name unchanged.
    """
    image = 'user/name'
    stripped_tag = strip_image_tag(image)

    assert_that(stripped_tag, Equals(image))


def test_strip_image_tag_unparsable():
    """ Given a malformed image tag, strip_image_tag should throw an error. """
    image = 'this:is:invalid/user:test/name:tag/'
    with ExpectedException(RuntimeError,
                           r'Unable to parse tag "%s"' % (image,)):
        strip_image_tag(image)


""" cmd() """


def assert_output_lines(capfd, stdout_lines, stderr_lines=[]):
    out, err = capfd.readouterr()
    if sys.version_info < (3,):
        # FIXME: I'm not entirely sure how to determine the correct encoding
        # here and not sure whether the right answer comes from Python itself
        # or pytest. For now, UTF-8 seems like a safe bet.
        out = out.encode('utf-8')
        err = err.encode('utf-8')

    out_lines = out.split('\n')
    assert_that(out_lines.pop(), Equals(''))
    assert_that(out_lines, Equals(stdout_lines))

    err_lines = err.split('\n')
    assert_that(err_lines.pop(), Equals(''))
    assert_that(err_lines, Equals(stderr_lines))


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


def test_cmd_stdout_unicode(capfd):
    """
    When a command writes Unicode to a standard stream, that output should be
    captured and encoded correctly.
    """
    cmd(['echo', 'á, é, í, ó, ú, ü, ñ, ¿, ¡'])

    assert_output_lines(capfd, ['á, é, í, ó, ú, ü, ñ, ¿, ¡'])


def test_cmd_error(capfd):
    """
    When a command exits with a non-zero return code, an error should be raised
    with the correct information about the result of the command. The stdout or
    stderr output should still be captured.
    """
    args = ['awk', 'BEGIN { print "errored"; exit 1 }']
    with ExpectedException(CalledProcessError, MatchesStructure(
            cmd=Equals(args),
            returncode=Equals(1),
            output=Equals(b'errored\n'))):
        cmd(args)

    assert_output_lines(capfd, ['errored'], [])


class TestDockerCiDeployRunner(object):
    def test_defaults(self, capfd):
        """
        When the runner is run with defaults, the image should be pushed.
        """
        runner = DockerCiDeployRunner(executable='echo')
        runner.run(['test-image'])

        assert_output_lines(capfd, ['push test-image'])

    def test_defaults_multiple_images(self, capfd):
        """
        When the runner is run with defaults, and multiple images are provided,
        all the images should be pushed.
        """
        runner = DockerCiDeployRunner(executable='echo')
        runner.run(['test-image', 'test-image2'])

        assert_output_lines(capfd, ['push test-image', 'push test-image2'])

    def test_tags(self, capfd):
        """
        When tags are provided to the runner, the image should be tagged and
        each tag should be pushed.
        """
        runner = DockerCiDeployRunner(executable='echo')
        runner.run(['test-image'], tags=['abc', 'def'])

        assert_output_lines(capfd, [
            'tag test-image test-image:abc',
            'tag test-image test-image:def',
            'push test-image:abc',
            'push test-image:def'
        ])

    def test_tags_multiple_images(self, capfd):
        """
        When tags are provided to the runner, and multiple images are provided,
        all the images should be tagged and each tag should be pushed.
        """
        runner = DockerCiDeployRunner(executable='echo')
        runner.run(['test-image', 'test-image2'], tags=['abc', 'def'])

        assert_output_lines(capfd, [
            'tag test-image test-image:abc',
            'tag test-image test-image:def',
            'tag test-image2 test-image2:abc',
            'tag test-image2 test-image2:def',
            'push test-image:abc',
            'push test-image:def',
            'push test-image2:abc',
            'push test-image2:def',
        ])

    def test_tag_replacement(self, capfd):
        """
        When tags are provided to the runner and the provided image has a tag,
        that tag should be tagged with the new tag, and the the new tag should
        be pushed.
        """
        runner = DockerCiDeployRunner(executable='echo')
        runner.run(['test-image:abc'], tags=['def'])

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
        runner.run(['test-image'], registry='registry.example.com:5000')

        assert_output_lines(capfd, [
            'tag test-image registry.example.com:5000/test-image',
            'push registry.example.com:5000/test-image'
        ])

    def test_registry_multiple_images(self, capfd):
        """
        When a registry is provided to the runner, the image should be tagged
        with the registry and pushed.
        """
        runner = DockerCiDeployRunner(executable='echo')
        runner.run(['test-image', 'test-image2'],
                   registry='registry.example.com:5000')

        assert_output_lines(capfd, [
            'tag test-image registry.example.com:5000/test-image',
            'tag test-image2 registry.example.com:5000/test-image2',
            'push registry.example.com:5000/test-image',
            'push registry.example.com:5000/test-image2',
        ])

    def test_tags_and_registry(self, capfd):
        """
        When tags and a registry are provided to the runner, the image should
        be tagged with both the tags and the registry and pushed.
        """
        runner = DockerCiDeployRunner(executable='echo')
        runner.run(['test-image:ghi'], tags=['abc', 'def'],
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
        runner.run(['test-image'], login='janedoe:pa55word')

        assert_output_lines(capfd, [
            'login --username janedoe --password pa55word',
            'push test-image'
        ])

    def test_registry_and_login(self, capfd):
        """
        When a registry and login details are provided to the runner, the image
        should be tagged with the registry and a login request should be made
        to the specified registry. The image should be pushed.
        """
        runner = DockerCiDeployRunner(executable='echo')
        runner.run(['test-image'], registry='registry.example.com:5000',
                   login='janedoe:pa55word')

        assert_output_lines(capfd, [
            'tag test-image registry.example.com:5000/test-image',
            'login --username janedoe --password pa55word '
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
        runner.run(['test-image:tag'], tags=['latest', 'best'],
                   registry='registry.example.com:5000',
                   login='janedoe:pa55word')

        assert_output_lines(capfd, [
            'tag test-image:tag registry.example.com:5000/test-image:latest',
            'tag test-image:tag registry.example.com:5000/test-image:best',
            'login --username janedoe --password pa55word '
            'registry.example.com:5000',
            'push registry.example.com:5000/test-image:latest',
            'push registry.example.com:5000/test-image:best'
        ])

    def test_all_options_multiple_images(self, capfd):
        """
        When multiple images, tags, a registry, and login details are provided
        to the runner, all the image should be tagged with the tags and
        registry, a login request should be made to the specified registry, and
        the tags should be pushed.
        """
        runner = DockerCiDeployRunner(executable='echo')
        runner.run(['test-image:tag', 'test-image2:tag2'],
                   tags=['latest', 'best'],
                   registry='registry.example.com:5000',
                   login='janedoe:pa55word')

        assert_output_lines(capfd, [
            'tag test-image:tag registry.example.com:5000/test-image:latest',
            'tag test-image:tag registry.example.com:5000/test-image:best',
            ('tag test-image2:tag2 '
                'registry.example.com:5000/test-image2:latest'),
            'tag test-image2:tag2 registry.example.com:5000/test-image2:best',
            'login --username janedoe --password pa55word '
            'registry.example.com:5000',
            'push registry.example.com:5000/test-image:latest',
            'push registry.example.com:5000/test-image:best',
            'push registry.example.com:5000/test-image2:latest',
            'push registry.example.com:5000/test-image2:best',
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
        runner.run(['test-image:tag'], tags=['latest'])

        expected = [
            'docker tag test-image:tag test-image:latest',
            'docker push test-image:latest'
        ]
        assert_that(logs, Equals(expected))

        assert_output_lines(capfd, [], [])

    def test_dry_run_obfuscates_password(self, capfd):
        """
        When running in dry-run mode and login details are provided, the user's
        password should not be logged.
        """
        runner = DockerCiDeployRunner(dry_run=True)
        logs = []
        runner.logger = lambda *args: logs.append(' '.join(args))
        runner.run(['test-image'], login='janedoe:pa55word')

        expected = [
            'docker login --username janedoe --password <password>',
            'docker push test-image'
        ]
        assert_that(logs, Equals(expected))

        assert_output_lines(capfd, [], [])

    def test_failed_run_obfuscates_password(self, tmpdir):
        """
        When running in dry-run mode and login details are provided, the user's
        password should not be logged.
        """
        exit_1 = tmpdir.join('exit_1.sh')
        exit_1.write('#!/bin/sh\nexit 1\n')
        exit_1.chmod(exit_1.stat().mode | stat.S_IEXEC)

        runner = DockerCiDeployRunner(executable=str(exit_1))
        with ExpectedException(CalledProcessError,
                               After(str, Not(MatchesRegex(r'pa55word')))):
            runner.run(['test-image'], login='janedoe:pa55word')


""" main() """


def test_main_args(capfd):
    """
    When the main function is given a set of common arguments, the script
    should be run as expected.
    """
    main([
        '--login', 'janedoe:pa55word',
        '--registry', 'registry.example.com:5000',
        '--executable', 'echo',
        'test-image:abc'
    ])

    assert_output_lines(capfd, [
        'tag test-image:abc registry.example.com:5000/test-image:abc',
        'login --username janedoe --password pa55word '
        'registry.example.com:5000',
        'push registry.example.com:5000/test-image:abc'
    ])


def test_main_image_required(capfd):
    """
    When the main function is given no image argument, it should exit with a
    return code of 2 and inform the user of the missing argument.
    """
    with ExpectedException(SystemExit, MatchesStructure(code=Equals(2))):
        main(['--tag', 'abc'])

    out, err = capfd.readouterr()
    assert_that(out, Equals(''))

    # More useful error message added to argparse in Python 3
    if sys.version_info >= (3,):
        # Use re.DOTALL so that '.*' also matches newlines
        assert_that(err, MatchesRegex(
            r'.*error: the following arguments are required: image$', re.DOTALL
        ))
    else:
        assert_that(
            err, MatchesRegex(r'.*error: too few arguments$', re.DOTALL))


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


def test_main_hides_stacktrace(capfd):
    """
    When an error is thrown - for example if the Docker executable cannot be
    found - then the stacktrace is suppressed and information about the
    runtime arguments is not exposed.
    """
    with ExpectedException(SystemExit, MatchesStructure(code=Equals(1))):
        main([
            '--login', 'janedoe:pa55word',
            '--executable', 'does-not-exist1234',
            'test-image'
        ])

    # FIXME: actually assert that traceback is not printed

    if sys.version_info >= (3,):
        error_msg = "[Errno 2] No such file or directory: 'does-not-exist1234'"
    else:
        error_msg = '[Errno 2] No such file or directory'
    assert_output_lines(capfd, [
        'Exception raised during execution: %s' % (error_msg,),
        'Stacktrace suppressed. Use debug mode to see full stacktrace.',
    ])


def test_main_debug_shows_stacktrace(capfd):
    """
    When an error is thrown - for example if the Docker executable cannot be
    found - then the stacktrace is suppressed and information about the
    runtime arguments is not exposed.
    """
    if sys.version_info >= (3,):
        err_type = FileNotFoundError  # noqa: F821
    else:
        err_type = OSError
    with ExpectedException(err_type, r'\[Errno 2\] No such file or directory'):
        main([
            '--debug',
            '--login', 'janedoe:pa55word',
            '--executable', 'does-not-exist1234',
            'test-image'
        ])

    # FIXME: actually assert that traceback is printed

    # pytest suppresses the stack trace itself so it doesn't show up in
    # stdout/stderr
    assert_output_lines(capfd, [], [])
