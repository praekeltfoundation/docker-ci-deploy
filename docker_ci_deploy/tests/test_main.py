# -*- coding: utf-8 -*-
import re
import stat
import sys
from subprocess import CalledProcessError

import pytest
from testtools import ExpectedException
from testtools.assertions import assert_that
from testtools.matchers import (
    AfterPreprocessing as After, Equals, Is, MatchesRegex, MatchesStructure,
    Not)

from docker_ci_deploy.__main__ import (
    cmd, DockerCiDeployRunner, join_image_tag, main, replace_image_registry,
    replace_tag_version, split_image_tag)


class TestSplitImageTagFunc(object):
    def test_split(self):
        """
        Given an image tag with registry, name and tag components,
        split_image_tag should return the registry and name as the image and
        the tag part as the tag.
        """
        image_and_tag = split_image_tag(
            'registry.example.com:5000/user/name:tag')

        assert_that(image_and_tag, Equals(
            ('registry.example.com:5000/user/name', 'tag')))

    def test_no_tag(self):
        """
        Given an image tag with only registry and name components,
        split_image_tag should return the image name unchanged and None for the
        tag.
        """
        image_and_tag = split_image_tag('registry.example.com:5000/user/name')

        assert_that(image_and_tag, Equals(
            ('registry.example.com:5000/user/name', None)))

    def test_no_registry(self):
        """
        Given an image tag with only name and tag components, split_image_tag
        should return the user and name part for the name and the tag part for
        the tag.
        """
        image_and_tag = split_image_tag('user/name:tag')

        assert_that(image_and_tag, Equals(('user/name', 'tag')))

    def test_no_registry_or_tag(self):
        """
        Given an image tag with only name components, split_image_tag should
        return the image name unchanged and None for the tag.
        """
        image_and_tag = split_image_tag('user/name')

        assert_that(image_and_tag, Equals(('user/name', None)))

    def test_tag_unparsable(self):
        """
        Given a malformed image tag, split_image_tag should throw an error.
        """
        image_tag = 'this:is:invalid/user:test/name:tag/'
        with ExpectedException(
                ValueError, r"Unable to parse image tag '%s'" % (image_tag,)):
            split_image_tag(image_tag)


class TestJoinImageTagFunc(object):
    def test_image_and_tag(self):
        """
        When an image and tag are provided, the two should be joined using a
        ':' character.
        """
        image_tag = join_image_tag('bar', 'foo')
        assert_that(image_tag, Equals('bar:foo'))

    def test_tag_is_none(self):
        """ When the provided tag is None, the image should be returned. """
        image_tag = join_image_tag('bar', None)
        assert_that(image_tag, Equals('bar'))

    def test_tag_is_empty(self):
        """ When the provided tag is empty, the image should be returned. """
        image_tag = join_image_tag('bar', '')
        assert_that(image_tag, Equals('bar'))


class TestReplaceImageRegistryFunc(object):
    def test_image_without_registry(self):
        """
        When an image without a registry is provided, the registry should be
        prepended to the image with a '/' character.
        """
        image = replace_image_registry('bar', 'registry:5000')
        assert_that(image, Equals('registry:5000/bar'))

    @pytest.mark.xfail
    def test_image_with_registry(self):
        """
        When an image is provided that already specifies a registry, that
        registry should be replaced with the given registry.

        This is currently expected to fail as we haven't implemented the logic
        to strip the registry address from the rest of a tag (we just return
        the whole tag).
        """
        image = replace_image_registry('registry:5000/bar', 'registry2:5000')
        assert_that(image, Equals('registry:5000/bar'))

    def test_registry_is_none(self):
        """
        When an image is provided and the provided registry is None, the image
        should be returned.
        """
        image = replace_image_registry('bar', None)
        assert_that(image, Equals('bar'))


class TestReplaceTagVersionFunc(object):
    def test_tag_without_version(self):
        """
        When a tag does not start with the version, the version should be
        prepended to the tag with a '-' character.
        """
        tag = replace_tag_version('foo', '1.2.3')
        assert_that(tag, Equals('1.2.3-foo'))

    def test_tag_with_version(self):
        """
        When a tag starts with the version, then the version and '-' separator
        should be removed from the tag and the remaining tag returned.
        """
        tag = replace_tag_version('1.2.3-foo', '1.2.3')
        assert_that(tag, Equals('1.2.3-foo'))

    def test_tag_is_version(self):
        """ When a tag is equal to the version, the tag should be returned. """
        tag = replace_tag_version('1.2.3', '1.2.3')
        assert_that(tag, Equals('1.2.3'))

    def test_tag_is_none(self):
        """ When a tag is None, the version should be returned. """
        tag = replace_tag_version(None, '1.2.3')
        assert_that(tag, Equals('1.2.3'))

    def test_version_is_none(self):
        """ When the version is None, the tag should be returned. """
        tag = replace_tag_version('foo', None)
        assert_that(tag, Equals('foo'))


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

    def test_version_no_tag(self, capfd):
        """
        When a version is provided and there is no tag, the image should be
        tagged with the version.
        """
        runner = DockerCiDeployRunner(executable='echo')
        runner.run(['test-image'], version='1.2.3')

        assert_output_lines(capfd, [
            'tag test-image test-image:1.2.3',
            'push test-image:1.2.3',
        ])

    def test_version_existing_tag(self, capfd):
        """
        When a version is provided and there is an existing tag in the image
        tag, then the version should be prepende to the tag.
        """
        runner = DockerCiDeployRunner(executable='echo')
        runner.run(['test-image:abc'], version='1.2.3')

        assert_output_lines(capfd, [
            'tag test-image:abc test-image:1.2.3-abc',
            'push test-image:1.2.3-abc',
        ])

    def test_version_existing_tag_with_version(self, capfd):
        """
        When a version is provided and there is an existing tag in the image
        tag that already starts with the version then the image should not be
        retagged.
        """
        runner = DockerCiDeployRunner(executable='echo')
        runner.run(['test-image:1.2.3-abc'], version='1.2.3')

        assert_output_lines(capfd, [
            'push test-image:1.2.3-abc',
        ])

    def test_version_existing_tag_is_version(self, capfd):
        """
        When a version is provided and there is an existing tag in the image
        tag that is equal to the version then the image should not be retagged.
        """
        runner = DockerCiDeployRunner(executable='echo')
        runner.run(['test-image:1.2.3'], version='1.2.3')

        assert_output_lines(capfd, [
            'push test-image:1.2.3',
        ])

    def test_version_new_tag(self, capfd):
        """
        When a version is provided as well as a new tag, the version should be
        prepended to the new tag and the image tagged with the new tag.
        """
        runner = DockerCiDeployRunner(executable='echo')
        runner.run(['test-image:abc'], tags=['def'], version='1.2.3')

        assert_output_lines(capfd, [
            'tag test-image:abc test-image:1.2.3-def',
            'push test-image:1.2.3-def',
        ])

    def test_version_new_tag_with_version(self, capfd):
        """
        When a version is provided as well as a new tag, and the new tag starts
        with the version, then the image should be tagged with the new version.
        """
        runner = DockerCiDeployRunner(executable='echo')
        runner.run(['test-image:abc'], tags=['1.2.3-def'], version='1.2.3')

        assert_output_lines(capfd, [
            'tag test-image:abc test-image:1.2.3-def',
            'push test-image:1.2.3-def',
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
        When tags, a version, a registry, and login details are provided to the
        runner, the image should be tagged with the tags, version and registry,
        a login request should be made to the specified registry, and the tags
        should be pushed.
        """
        runner = DockerCiDeployRunner(executable='echo')
        runner.run(['test-image:tag'], tags=['latest', 'best'],
                   version='1.2.3',
                   registry='registry.example.com:5000',
                   login='janedoe:pa55word')

        assert_output_lines(capfd, [
            ('tag test-image:tag '
                'registry.example.com:5000/test-image:1.2.3-latest'),
            ('tag test-image:tag '
                'registry.example.com:5000/test-image:1.2.3-best'),
            'login --username janedoe --password pa55word '
            'registry.example.com:5000',
            'push registry.example.com:5000/test-image:1.2.3-latest',
            'push registry.example.com:5000/test-image:1.2.3-best'
        ])

    def test_all_options_multiple_images(self, capfd):
        """
        When multiple images, tags, a version, a registry, and login details
        are provided to the runner, all the image should be tagged with the
        tags, a version and registry, a login request should be made to the
        specified registry, and the tags should be pushed.
        """
        runner = DockerCiDeployRunner(executable='echo')
        runner.run(['test-image:tag', 'test-image2:tag2'],
                   tags=['latest', 'best'],
                   version='1.2.3',
                   registry='registry.example.com:5000',
                   login='janedoe:pa55word')

        assert_output_lines(capfd, [
            ('tag test-image:tag '
                'registry.example.com:5000/test-image:1.2.3-latest'),
            ('tag test-image:tag '
                'registry.example.com:5000/test-image:1.2.3-best'),
            ('tag test-image2:tag2 '
                'registry.example.com:5000/test-image2:1.2.3-latest'),
            ('tag test-image2:tag2 '
                'registry.example.com:5000/test-image2:1.2.3-best'),
            'login --username janedoe --password pa55word '
            'registry.example.com:5000',
            'push registry.example.com:5000/test-image:1.2.3-latest',
            'push registry.example.com:5000/test-image:1.2.3-best',
            'push registry.example.com:5000/test-image2:1.2.3-latest',
            'push registry.example.com:5000/test-image2:1.2.3-best',
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
