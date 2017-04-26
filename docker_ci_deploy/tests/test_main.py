# -*- coding: utf-8 -*-
import re
import sys
from subprocess import CalledProcessError

from testtools import ExpectedException
from testtools.assertions import assert_that
from testtools.matchers import Equals, MatchesRegex, MatchesStructure

from docker_ci_deploy.__main__ import (
    cmd, DockerCiDeployRunner, join_image_tag, main, RegistryTagger,
    generate_tags, VersionTagger, split_image_tag)


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


class TestRegistryTagger(object):
    def test_image_without_registry(self):
        """
        When an image without a registry is provided, the registry should be
        prepended to the image with a '/' character.
        """
        image = RegistryTagger('registry:5000').generate_tag('bar')
        assert_that(image, Equals('registry:5000/bar'))

    def test_image_with_registry(self):
        """
        When an image is provided that already specifies a registry, that
        registry should be replaced with the given registry.
        """
        image = RegistryTagger('registry2:5000').generate_tag(
            'registry:5000/bar')
        assert_that(image, Equals('registry2:5000/bar'))

    def test_image_might_have_registry(self):
        """
        When an image is provided that looks like it *may* already specify a
        registry, the registry should just be prepended to the image name and
        returned, provided that the resulting image name is valid.
        """
        image = RegistryTagger('registry:5000').generate_tag(
            'praekeltorg/alpine-python')
        assert_that(image, Equals('registry:5000/praekeltorg/alpine-python'))

    def test_image_unparsable(self):
        """
        Given a malformed image name, replace_image_registry should throw an
        error.
        """
        image = 'foo:5000:port/name'
        with ExpectedException(
                ValueError, r"Unable to parse image name '%s'" % (image,)):
            RegistryTagger('registry:5000').generate_tag(image)


class TestVersionTagger(object):
    def test_tag_without_version(self):
        """
        When a tag does not start with the version, the version should be
        prepended to the tag with a '-' character.
        """
        tagger = VersionTagger('1.2.3')
        tags = tagger.generate_tags('foo')
        assert_that(tags, Equals(['1.2.3-foo']))

    def test_tag_with_version(self):
        """
        When a tag starts with the version, then the version and '-' separator
        should be removed from the tag and the remaining tag processed.
        """
        tagger = VersionTagger('1.2.3')
        tags = tagger.generate_tags('1.2.3-foo')
        assert_that(tags, Equals(['1.2.3-foo']))

    def test_tag_is_version(self):
        """ When a tag is equal to the version, the tag should be returned. """
        tagger = VersionTagger('1.2.3')
        tags = tagger.generate_tags('1.2.3')
        assert_that(tags, Equals(['1.2.3']))

    def test_tag_is_none(self):
        """ When a tag is None, the version should be returned. """
        tagger = VersionTagger('1.2.3')
        tags = tagger.generate_tags(None)
        assert_that(tags, Equals(['1.2.3']))

    def test_tag_is_latest(self):
        """ When the tag is 'latest', the version should be returned. """
        tagger = VersionTagger('1.2.3')
        tags = tagger.generate_tags('latest')
        assert_that(tags, Equals(['1.2.3']))

    def test_latest(self):
        """
        When latest is True and a tag is provided, the versioned and
        unversioned tags should be returned.
        """
        tagger = VersionTagger('1.2.3', latest=True)
        tags = tagger.generate_tags('foo')
        assert_that(tags, Equals(['1.2.3-foo', 'foo']))

    def test_latest_tag_is_latest(self):
        """
        When latest is True and a tag is provided, and the tag is 'latest', the
        versioned tag and 'latest' tag should be returned.
        """
        tagger = VersionTagger('1.2.3', latest=True)
        tags = tagger.generate_tags('latest')
        assert_that(tags, Equals(['1.2.3', 'latest']))

    def test_semver(self):
        """
        When semver is True and a tag is provided, the tag should be prefixed
        with each part of the version.
        """
        tagger = VersionTagger('1.2.3', semver=True)
        tags = tagger.generate_tags('foo')
        assert_that(tags, Equals(['1.2.3-foo', '1.2-foo', '1-foo']))

    def test_semver_no_tag(self):
        """
        When semver is True and a tag is not provided, tags should be generated
        for each part of the version.
        """
        tagger = VersionTagger('1.2.3', semver=True)
        tags = tagger.generate_tags(None)
        assert_that(tags, Equals(['1.2.3', '1.2', '1']))

    def test_semver_do_not_tag_zero(self):
        """
        When semver is True, and a version with a major version of '0' is
        provided, a tag should not be generated with the version '0'.
        """
        tagger = VersionTagger('0.6.11', semver=True)
        tags = tagger.generate_tags('foo')
        assert_that(tags, Equals(['0.6.11-foo', '0.6-foo']))

    def test_semver_tag_zero_if_only_zero(self):
        """
        When semver is True, and the version '0' is provided, a tag should be
        generated with the version '0'.
        """
        tagger = VersionTagger('0', semver=True)
        tags = tagger.generate_tags('foo')
        assert_that(tags, Equals(['0-foo']))

    def test_semver_tag_zero_true(self):
        """
        When semver and zero are True, and a version with a major version of
        '0' is provided, a tag should be generated with the version '0'.
        """
        tagger = VersionTagger('0.6.11', semver=True, zero=True)
        tags = tagger.generate_tags('foo')
        assert_that(tags, Equals(['0.6.11-foo', '0.6-foo', '0-foo']))

    def test_semver_tag_contains_semver(self):
        """
        When semver is True and a tag is provided that starts with one of the
        parts of the version, that version part should be removed before the
        tag is prefixed with each version part.
        """
        tagger = VersionTagger('1.2.3', semver=True)
        tags = tagger.generate_tags('1.2-foo')
        assert_that(tags, Equals(['1.2.3-foo', '1.2-foo', '1-foo']))

    def test_semver_with_latest(self):
        """
        When semver is True, a tag is provided, and latest is True, each
        version part should be prefixed to the tag and the plain tag should
        also be returned.
        """
        tagger = VersionTagger('1.2.3', latest=True, semver=True)
        tags = tagger.generate_tags('foo')
        assert_that(tags, Equals(['1.2.3-foo', '1.2-foo', '1-foo', 'foo']))

    def test_semver_no_tag_with_latest(self):
        """
        When semver is True, a tag is not provided, and latest is True, each
        version part as well as the 'latest' tag should be returned.
        """
        tagger = VersionTagger('1.2.3', latest=True, semver=True)
        tags = tagger.generate_tags(None)
        assert_that(tags, Equals(['1.2.3', '1.2', '1', 'latest']))


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


class TestCmdFunc(object):
    def test_stdout(self, capfd):
        """
        When a command writes to stdout, that output should be captured and
        written to Python's stdout.
        """
        cmd(['echo', 'Hello, World!'])

        assert_output_lines(
            capfd, stdout_lines=['Hello, World!'], stderr_lines=[])

    def test_stderr(self, capfd):
        """
        When a command writes to stderr, that output should be captured and
        written to Python's stderr.
        """
        # Have to do something a bit more complicated to echo to stderr
        cmd(['awk', 'BEGIN { print "Hello, World!" > "/dev/stderr" }'])

        assert_output_lines(
            capfd, stdout_lines=[], stderr_lines=['Hello, World!'])

    def test_stdout_unicode(self, capfd):
        """
        When a command writes Unicode to a standard stream, that output should
        be captured and encoded correctly.
        """
        cmd(['echo', 'á, é, í, ó, ú, ü, ñ, ¿, ¡'])

        assert_output_lines(capfd, ['á, é, í, ó, ú, ü, ñ, ¿, ¡'])

    def test_error(self, capfd):
        """
        When a command exits with a non-zero return code, an error should be
        raised with the correct information about the result of the command.
        The stdout or stderr output should still be captured.
        """
        args = ['awk', 'BEGIN { print "errored"; exit 1 }']
        with ExpectedException(CalledProcessError, MatchesStructure(
                cmd=Equals(args),
                returncode=Equals(1),
                output=Equals(b'errored\n'))):
            cmd(args)

        assert_output_lines(capfd, ['errored'], [])


class TestGenerateTagsFunc(object):
    def test_no_tags(self):
        """
        When no parameters are provided, and an image name without a tag is
        passed, a list should be returned with the given image name unchanged.
        """
        tags = generate_tags('test-image')

        assert_that(tags, Equals(['test-image']))

    def test_no_tags_existing_tag(self):
        """
        When no parameters are provided, and an image tag with a tag is passed,
        a list should be returned with the given image tag unchanged.
        """
        tags = generate_tags('test-image:abc')

        assert_that(tags, Equals(['test-image:abc']))

    def test_tags(self):
        """
        When the tags parameter is provided, and an image name without a tag is
        passed, a list of image tags should be returned with the tags appended.
        """
        tags = generate_tags('test-image', tags=['abc', 'def'])

        assert_that(tags, Equals(['test-image:abc', 'test-image:def']))

    def test_tag_existing_tag(self):
        """
        When the tags parameter is provided, and an image tag with a tag is
        passed, a list of image tags should be returned with the tag replaced
        by the new tags.
        """
        tags = generate_tags('test-image:abc', tags=['def', 'ghi'])

        assert_that(tags, Equals(['test-image:def', 'test-image:ghi']))

    # FIXME?: The following 2 tests describe a weird, unintuitive edge case :-(
    # Passing `--tag latest` with `--tag-version <version>` but *not*
    # `--tag-latest` doesn't actually get you the tag 'latest' but rather
    # effectively removes any existing tag.
    def test_version_new_tag_is_latest(self, capfd):
        """
        When a version is provided as well as a new tag, and the new tag is
        'latest', then the image should be tagged with the new version only.
        """
        version_tagger = VersionTagger('1.2.3')
        tags = generate_tags(
            'test-image:abc', tags=['latest'], version_tagger=version_tagger)

        assert_that(tags, Equals(['test-image:1.2.3']))

    def test_version_new_tag_is_latest_with_version(self, capfd):
        """
        When a version is provided as well as a new tag, and the new tag is
        'latest' plus the version, then the image should be tagged with the
        new version only.
        """
        version_tagger = VersionTagger('1.2.3')
        tags = generate_tags('test-image:abc', tags=['1.2.3-latest'],
                             version_tagger=version_tagger)

        assert_that(tags, Equals(['test-image:1.2.3']))


class TestDockerCiDeployRunner(object):
    def test_tag(self, capfd):
        """
        When ``tag`` is called, the Docker CLI should be called with the 'tag'
        command and the source and target tags.
        """
        runner = DockerCiDeployRunner(executable='echo')
        runner.docker_tag('foo', 'bar')

        assert_output_lines(capfd, ['tag foo bar'])

    def test_tag_verbose(self, capfd):
        """
        When ``tag`` is called, and verbose is True, a message should be
        logged.
        """
        runner = DockerCiDeployRunner(executable='echo', verbose=True)
        runner.docker_tag('foo', 'bar')

        assert_output_lines(
            capfd, ['Tagging "foo" as "bar"...', 'tag foo bar'])

    def test_tag_dry_run(self, capfd):
        """
        When ``tag`` is called, and dry_run is True, the Docker command should
        be printed but not executed.
        """
        runner = DockerCiDeployRunner(dry_run=True)
        runner.docker_tag('foo', 'bar')

        assert_output_lines(capfd, ['docker tag foo bar'])

    def test_tag_same_tag(self, capfd):
        """
        When ``tag`` is called, and the output tag is the same as the input
        tag, the command should not be executed.
        """
        runner = DockerCiDeployRunner(executable='echo')
        runner.docker_tag('bar', 'bar')

        assert_output_lines(capfd, [], [])

    def test_tag_same_tag_verbose(self, capfd):
        """
        When ``tag`` is called, and the output tag is the same as the input
        tag, and verbose is True, a message should be logged that explains that
        no tagging will be done.
        """
        runner = DockerCiDeployRunner(executable='echo', verbose=True)
        runner.docker_tag('bar', 'bar')

        assert_output_lines(capfd, ['Not tagging "bar" as itself'])

    def test_push(self, capfd):
        """
        When ``push`` is called, the Docker CLI should be called with the
        'push' command and the image tag.
        """
        runner = DockerCiDeployRunner(executable='echo')
        runner.docker_push('foo')

        assert_output_lines(capfd, ['push foo'])

    def test_push_verbose(self, capfd):
        """
        When ``push`` is called, and verbose is True, a message should be
        logged.
        """
        runner = DockerCiDeployRunner(executable='echo', verbose=True)
        runner.docker_push('foo')

        assert_output_lines(capfd, ['Pushing tag "foo"...', 'push foo'])

    def test_push_dry_run(self, capfd):
        """
        When ``push`` is called, and dry_run is True, the Docker command should
        be printed but not executed.
        """
        runner = DockerCiDeployRunner(dry_run=True)
        runner.docker_push('foo')

        assert_output_lines(capfd, ['docker push foo'])


class TestMainFunc(object):
    def test_args(self, capfd):
        """
        When the main function is given a set of common arguments, the script
        should be run as expected.
        """
        main([
            '--registry', 'registry.example.com:5000',
            '--executable', 'echo',
            'test-image:abc'
        ])

        assert_output_lines(capfd, [
            'tag test-image:abc registry.example.com:5000/test-image:abc',
            'push registry.example.com:5000/test-image:abc'
        ])

    def test_version(self, capfd):
        """
        When the --tag-version flag is used, the version is added to the image
        tag.
        """
        main([
            '--executable', 'echo',
            '--tag-version', '1.2.3',
            'test-image:abc'
        ])

        assert_output_lines(capfd, [
            'tag test-image:abc test-image:1.2.3-abc',
            'push test-image:1.2.3-abc'
        ])

    def test_image_required(self, capfd):
        """
        When the main function is given no image argument, it should exit with
        a return code of 2 and inform the user of the missing argument.
        """
        with ExpectedException(SystemExit, MatchesStructure(code=Equals(2))):
            main(['--tag', 'abc'])

        out, err = capfd.readouterr()
        assert_that(out, Equals(''))

        # More useful error message added to argparse in Python 3
        if sys.version_info >= (3,):
            # Use re.DOTALL so that '.*' also matches newlines
            assert_that(err, MatchesRegex(
                r'.*error: the following arguments are required: image$',
                re.DOTALL
            ))
        else:
            assert_that(
                err, MatchesRegex(r'.*error: too few arguments$', re.DOTALL))

    def test_tag_latest_requires_tag_version(self, capfd):
        """
        When the main function is given the `--tag-latest` option but no
        `--tag-version` option, it should exit with a return code of 2 and
        inform the user of the missing option.
        """
        with ExpectedException(SystemExit, MatchesStructure(code=Equals(2))):
            main(['--tag-latest', 'test-image:abc'])

        out, err = capfd.readouterr()
        assert_that(out, Equals(''))
        assert_that(err, MatchesRegex(
            r'.*error: the --tag-latest option requires --tag-version$',
            re.DOTALL
        ))

    def test_tag_latest_requires_non_empty_tag_version(self, capfd):
        """
        When the main function is given the `--tag-latest` option and an empty
        `--tag-version` option, it should exit with a return code of 2 and
        inform the user of the missing option.
        """
        with ExpectedException(SystemExit, MatchesStructure(code=Equals(2))):
            main(['--tag-latest', '--tag-version', '', 'test-image:abc'])

        out, err = capfd.readouterr()
        assert_that(out, Equals(''))
        assert_that(err, MatchesRegex(
            r'.*error: the --tag-latest option requires --tag-version$',
            re.DOTALL
        ))

    def test_tag_semver_requires_tag_version(self, capfd):
        """
        When the main function is given the `--tag-semver` option but no
        `--tag-version` option, it should exit with a return code of 2 and
        inform the user of the missing option.
        """
        with ExpectedException(SystemExit, MatchesStructure(code=Equals(2))):
            main(['--tag-semver', 'test-image:abc'])

        out, err = capfd.readouterr()
        assert_that(out, Equals(''))
        assert_that(err, MatchesRegex(
            r'.*error: the --tag-semver option requires --tag-version$',
            re.DOTALL
        ))

    def test_tag_semver_requires_non_empty_tag_version(self, capfd):
        """
        When the main function is given the `--tag-semver` option and an empty
        `--tag-version` option, it should exit with a return code of 2 and
        inform the user of the missing option.
        """
        with ExpectedException(SystemExit, MatchesStructure(code=Equals(2))):
            main(['--tag-semver', '--tag-version', '', 'test-image:abc'])

        out, err = capfd.readouterr()
        assert_that(out, Equals(''))
        assert_that(err, MatchesRegex(
            r'.*error: the --tag-semver option requires --tag-version$',
            re.DOTALL
        ))

    def test_tag_zero_requires_tag_semver(self, capfd):
        """
        When the main function is given the `--tag-zero` option but no
        `--tag-semver` option, it should exit with a return code of 2 and
        inform the user of the missing option.
        """
        with ExpectedException(SystemExit, MatchesStructure(code=Equals(2))):
            main(['--tag-zero', 'test-image:abc'])

        out, err = capfd.readouterr()
        assert_that(out, Equals(''))
        assert_that(err, MatchesRegex(
            r'.*error: the --tag-zero option requires --tag-semver$',
            re.DOTALL
        ))

    def test_many_tags(self, capfd):
        """
        When the main function is given multiple tag arguments in different
        ways, the tags should be correctly passed through to the runner.
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

    def test_tag_requires_arguments(self, capfd):
        """
        When the main function is given the `--tag` option without any
        arguments, an error should be raised.
        """
        with ExpectedException(SystemExit, MatchesStructure(code=Equals(2))):
            main(['--tag', '--', 'test-image'])

        out, err = capfd.readouterr()
        assert_that(out, Equals(''))
        assert_that(err, MatchesRegex(
            r'.*error: argument -t/--tag: expected at least one argument$',
            re.DOTALL
        ))

    def test_registry_requires_argument(self, capfd):
        """
        When the main function is given the `--registry` option without an
        argument, an error should be raised.
        """
        with ExpectedException(SystemExit, MatchesStructure(code=Equals(2))):
            main(['--registry', '--', 'test-image'])

        out, err = capfd.readouterr()
        assert_that(out, Equals(''))
        assert_that(err, MatchesRegex(
            r'.*error: argument -r/--registry: expected one argument$',
            re.DOTALL
        ))

    def test_executable_requires_argument(self, capfd):
        """
        When the main function is given the `--executable` option without an
        argument, an error should be raised.
        """
        with ExpectedException(SystemExit, MatchesStructure(code=Equals(2))):
            main(['--executable', '--', 'test-image'])

        out, err = capfd.readouterr()
        assert_that(out, Equals(''))
        assert_that(err, MatchesRegex(
            r'.*error: argument --executable: expected one argument$',
            re.DOTALL
        ))
