# -*- coding: utf-8 -*-
import re
import sys
from subprocess import CalledProcessError

from testtools import ExpectedException
from testtools.assertions import assert_that
from testtools.matchers import Equals, MatchesRegex, MatchesStructure

from docker_ci_deploy.__main__ import (
    cmd, DockerCiDeployRunner, generate_semver_versions, ImageTagGenerator,
    join_image_tag, main, RegistryNameGenerator, ReplacementTagGenerator,
    SequentialTagGenerator, split_image_tag, VersionTagGenerator)


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


class TestRegistryNameGenerator(object):
    def test_image_without_registry(self):
        """
        When an image without a registry is provided, the registry should be
        prepended to the image with a '/' character.
        """
        image = RegistryNameGenerator('registry:5000').generate_name('bar')
        assert_that(image, Equals('registry:5000/bar'))

    def test_image_with_registry(self):
        """
        When an image is provided that already specifies a registry, that
        registry should be replaced with the given registry.
        """
        image = RegistryNameGenerator('registry2:5000').generate_name(
            'registry:5000/bar')
        assert_that(image, Equals('registry2:5000/bar'))

    def test_image_might_have_registry(self):
        """
        When an image is provided that looks like it *may* already specify a
        registry, the registry should just be prepended to the image name and
        returned, provided that the resulting image name is valid.
        """
        image = RegistryNameGenerator('registry:5000').generate_name(
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
            RegistryNameGenerator('registry:5000').generate_name(image)


class TestReplacementTagGenerator(object):
    def test_replaces(self):
        """
        Given any tag, the list of tags that the generator was constructed with
        are returned.
        """
        generator = ReplacementTagGenerator(['foo', 'bar'])
        tags = generator.generate_tags('baz')
        assert_that(tags, Equals(['foo', 'bar']))


class TestGenerateSemverVersionsFunc(object):
    def test_standard_version(self):
        """
        When a standard 3-part semantic version is passed, 3 version strings
        should be returned with decreasing levels of precision.
        """
        versions = generate_semver_versions('5.4.1')
        assert_that(versions, Equals(['5.4.1', '5.4', '5']))

    def test_extended_version(self):
        """
        When a version is passed with extra information separated by '-',
        version strings should be returned with decreasing levels of precision.
        """
        versions = generate_semver_versions('5.5.0-alpha')
        assert_that(versions, Equals(['5.5.0-alpha', '5.5.0', '5.5', '5']))

    def test_one_version_part(self):
        """
        When a version with a single part is passed, that version should be
        returned in a list.
        """
        versions = generate_semver_versions('foo')
        assert_that(versions, Equals(['foo']))

    def test_precision_less_than_version(self):
        """
        When precision is less than the precision of the version, semantic
        versions should be generated up to the specified precision.
        """
        versions = generate_semver_versions('3.5.3', precision=2)
        assert_that(versions, Equals(['3.5.3', '3.5']))

    def test_precision_equal_to_version(self):
        """
        When precision is equal to the precision of the version, the generated
        versions should be just the version itself.
        """
        versions = generate_semver_versions('3.5.3', precision=3)
        assert_that(versions, Equals(['3.5.3']))

    def test_precision_greater_than_version(self):
        """
        When precision is greater than the precision of the version, an error
        should be raised.
        """
        with ExpectedException(
            ValueError,
                r'The minimum precision \(4\) is greater than the precision '
                r"of version '3\.5\.3' \(3\)"):
            generate_semver_versions('3.5.3', precision=4)

    def test_does_not_generate_zero(self):
        """
        When a version is passed with a major version of 0, the version '0'
        should not be returned in the list of versions.
        """
        versions = generate_semver_versions('0.6.11')
        assert_that(versions, Equals(['0.6.11', '0.6']))

    def test_zero_true(self):
        """
        When a version is passed with a major version of 0, and the zero
        parameter is True, the version '0' should be returned in the list of
        versions.
        """
        versions = generate_semver_versions('0.6.11', zero=True)
        assert_that(versions, Equals(['0.6.11', '0.6', '0']))

    def test_does_generate_zero_if_only_zero(self):
        """
        When the version '0' is passed, that version should be returned in a
        list.
        """
        versions = generate_semver_versions('0')
        assert_that(versions, Equals(['0']))


class TestVersionTagGenerator(object):
    def test_tag_without_version(self):
        """
        When a tag does not start with the version, the version should be
        prepended to the tag with a '-' character.
        """
        generator = VersionTagGenerator(['1.2.3'])
        tags = generator.generate_tags('foo')
        assert_that(tags, Equals(['1.2.3-foo']))

    def test_tag_with_version(self):
        """
        When a tag starts with one of the versions, then the version and '-'
        separator should be removed from the tag and the remaining tag
        processed.
        """
        generator = VersionTagGenerator(['1.2.3', '1.2', '1'])
        tags = generator.generate_tags('1.2-foo')
        assert_that(tags, Equals(['1.2.3-foo', '1.2-foo', '1-foo']))

    def test_tag_is_version(self):
        """
        When a tag is equal to one of the versions, the versions should be
        returned.
        """
        generator = VersionTagGenerator(['1.2.3', '1.2', '1'])
        tags = generator.generate_tags('1')
        assert_that(tags, Equals(['1.2.3', '1.2', '1']))

    def test_tag_is_none(self):
        """ When a tag is None, the versions should be returned. """
        generator = VersionTagGenerator(['1.2.3'])
        tags = generator.generate_tags(None)
        assert_that(tags, Equals(['1.2.3']))

    def test_tag_is_latest(self):
        """ When the tag is 'latest', the versions should be returned. """
        generator = VersionTagGenerator(['1.2.3'])
        tags = generator.generate_tags('latest')
        assert_that(tags, Equals(['1.2.3']))

    def test_latest(self):
        """
        When latest is True and a tag is provided, the versioned and
        unversioned tags should be returned.
        """
        generator = VersionTagGenerator(['1.2.3'], latest=True)
        tags = generator.generate_tags('foo')
        assert_that(tags, Equals(['1.2.3-foo', 'foo']))

    def test_latest_tag_with_version(self):
        """
        When latest is True and the tag already has the version prefixed, the
        tag and 'latest' tag should be returned.
        """
        generator = VersionTagGenerator(['1.2.3'], latest=True)
        tags = generator.generate_tags('1.2.3-foo')
        assert_that(tags, Equals(['1.2.3-foo', 'foo']))

    def test_latest_tag_is_version(self):
        """
        When latest is True and the tag is the version, the version and
        'latest' tag should be returned.
        """
        generator = VersionTagGenerator(['1.2.3'], latest=True)
        tags = generator.generate_tags('1.2.3')
        assert_that(tags, Equals(['1.2.3', 'latest']))

    def test_latest_tag_is_none(self):
        """
        When latest is True and the tag is None, the version and 'latest' tag
        should be returned.
        """
        generator = VersionTagGenerator(['1.2.3'], latest=True)
        tags = generator.generate_tags(None)
        assert_that(tags, Equals(['1.2.3', 'latest']))

    def test_latest_tag_is_latest(self):
        """
        When latest is True and the tag is 'latest', the version and 'latest'
        tag should be returned.
        """
        generator = VersionTagGenerator(['1.2.3'], latest=True)
        tags = generator.generate_tags('latest')
        assert_that(tags, Equals(['1.2.3', 'latest']))


class TestSequentialTagGenerator(object):
    def test_no_generators(self):
        """
        When no tag generators are provided, the given tag is returned
        unchanged in a list.
        """
        generator = SequentialTagGenerator([])
        tags = generator.generate_tags('foo')
        assert_that(tags, Equals(['foo']))

    def test_one_generator(self):
        """
        When one tag generator is provided, the generator works the same as if
        it were applied directly.
        """
        generator = SequentialTagGenerator([
            VersionTagGenerator(['1.2.3', '1.2', '1'])
        ])
        tags = generator.generate_tags('foo')
        assert_that(tags, Equals([
            '1.2.3-foo',
            '1.2-foo',
            '1-foo',
        ]))

    def test_multiple_generators(self):
        """
        When multiple tag generators are provided, each tag generator is
        applied sequentially to the result of the previous.
        """
        generator = SequentialTagGenerator([
            ReplacementTagGenerator(['baz']),
            VersionTagGenerator(['4.5.6'], latest=True),
            VersionTagGenerator(['1.2.3', '1.2', '1']),
        ])
        tags = generator.generate_tags('foo')
        assert_that(tags, Equals([
            '1.2.3-4.5.6-baz',
            '1.2-4.5.6-baz',
            '1-4.5.6-baz',
            '1.2.3-baz',
            '1.2-baz',
            '1-baz',
        ]))

    # FIXME?: The following 2 tests describe a weird, unintuitive edge case :-(
    # Passing `--tag latest` with `--version <version>` but *not*
    # `--version-latest` doesn't actually get you the tag 'latest' but rather
    # effectively removes any existing tag.
    def test_version_new_tag_is_latest(self, capfd):
        """
        When a version is provided as well as a new tag, and the new tag is
        'latest', then the image should be tagged with the new version only.
        """
        generator = SequentialTagGenerator([
            ReplacementTagGenerator(['latest']),
            VersionTagGenerator(['1.2.3'])
        ])
        tags = generator.generate_tags('abc')

        assert_that(tags, Equals(['1.2.3']))

    def test_version_new_tag_is_latest_with_version(self, capfd):
        """
        When a version is provided as well as a new tag, and the new tag is
        'latest' plus the version, then the image should be tagged with the
        new version only.
        """
        generator = SequentialTagGenerator([
            ReplacementTagGenerator(['1.2.3-latest']),
            VersionTagGenerator(['1.2.3'])
        ])
        tags = generator.generate_tags('abc')

        assert_that(tags, Equals(['1.2.3']))


class TestImageTagGenerator(object):
    def test_passthrough(self):
        """
        When the tag generator is an empty SequentialTagGenerator and the name
        generator is None, image tags should be returned unchanged in a list.
        """
        tag_generator = SequentialTagGenerator([])
        name_generator = None
        generator = ImageTagGenerator(tag_generator, name_generator)

        tags = generator.generate_image_tags('foo:bar')
        assert_that(tags, Equals(['foo:bar']))

    def test_tag_generator(self):
        """
        When there is a tag generator but the name generator is None, image
        tags should be returned with changed tags, but unchanged names.
        """
        tag_generator = ReplacementTagGenerator(['baz', 'abc'])
        name_generator = None
        generator = ImageTagGenerator(tag_generator, name_generator)

        tags = generator.generate_image_tags('foo:bar')
        assert_that(tags, Equals(['foo:baz', 'foo:abc']))

    def test_name_generator(self):
        """
        When there is a tag generator and a name generator, image tags should
        be returned with changed tags and a changed name.
        """
        tag_generator = SequentialTagGenerator([])
        name_generator = RegistryNameGenerator('localhost:5000')
        generator = ImageTagGenerator(tag_generator, name_generator)

        tags = generator.generate_image_tags('foo:bar')
        assert_that(tags, Equals(['localhost:5000/foo:bar']))


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
        When the --version flag is used, the version is added to the image tag.
        """
        main([
            '--executable', 'echo',
            '--version', '1.2.3',
            'test-image:abc'
        ])

        assert_output_lines(capfd, [
            'tag test-image:abc test-image:1.2.3-abc',
            'push test-image:1.2.3-abc'
        ])

    def test_semver_precision(self, capfd):
        """
        When the --semver-precision option is used, the semver versions are
        generated with the correct precision.
        """
        main([
            '--executable', 'echo',
            '--version', '1.2.3',
            '--version-semver',
            '--semver-precision', '2',
            'test-image:abc'
        ])

        assert_output_lines(capfd, [
            'tag test-image:abc test-image:1.2.3-abc',
            'tag test-image:abc test-image:1.2-abc',
            'push test-image:1.2.3-abc',
            'push test-image:1.2-abc',
        ])

    def test_semver_precision_default(self, capfd):
        """
        When the --version-semver flag is used, but the --semver-precision
        option is not, the semver precision should default to 1.
        """
        main([
            '--executable', 'echo',
            '--version', '1.2.3',
            '--version-semver',
            'test-image:abc'
        ])

        assert_output_lines(capfd, [
            'tag test-image:abc test-image:1.2.3-abc',
            'tag test-image:abc test-image:1.2-abc',
            'tag test-image:abc test-image:1-abc',
            'push test-image:1.2.3-abc',
            'push test-image:1.2-abc',
            'push test-image:1-abc',
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

    def test_version_latest_requires_version(self, capfd):
        """
        When the main function is given the `--version-latest` option but no
        `--version` option, it should exit with a return code of 2 and inform
        the user of the missing option.
        """
        with ExpectedException(SystemExit, MatchesStructure(code=Equals(2))):
            main(['--version-latest', 'test-image:abc'])

        out, err = capfd.readouterr()
        assert_that(out, Equals(''))
        assert_that(err, MatchesRegex(
            r'.*error: the --version-latest option requires --version$',
            re.DOTALL
        ))

    def test_version_latest_requires_non_empty_version(self, capfd):
        """
        When the main function is given the `--version-latest` option and an
        empty `--version` option, it should exit with a return code of 2 and
        inform the user of the missing option.
        """
        with ExpectedException(SystemExit, MatchesStructure(code=Equals(2))):
            main(['--version-latest', '--version', '', 'test-image:abc'])

        out, err = capfd.readouterr()
        assert_that(out, Equals(''))
        assert_that(err, MatchesRegex(
            r'.*error: the --version-latest option requires --version$',
            re.DOTALL
        ))

    def test_version_semver_requires_version(self, capfd):
        """
        When the main function is given the `--version-semver` option but no
        `--version` option, it should exit with a return code of 2 and inform
        the user of the missing option.
        """
        with ExpectedException(SystemExit, MatchesStructure(code=Equals(2))):
            main(['--version-semver', 'test-image:abc'])

        out, err = capfd.readouterr()
        assert_that(out, Equals(''))
        assert_that(err, MatchesRegex(
            r'.*error: the --version-semver option requires --version$',
            re.DOTALL
        ))

    def test_version_semver_requires_non_empty_version(self, capfd):
        """
        When the main function is given the `--version-semver` option and an
        empty `--version` option, it should exit with a return code of 2 and
        inform the user of the missing option.
        """
        with ExpectedException(SystemExit, MatchesStructure(code=Equals(2))):
            main(['--version-semver', '--version', '', 'test-image:abc'])

        out, err = capfd.readouterr()
        assert_that(out, Equals(''))
        assert_that(err, MatchesRegex(
            r'.*error: the --version-semver option requires --version$',
            re.DOTALL
        ))

    def test_semver_precision_requires_version_semver(self, capfd):
        """
        When the main function is given the `--semver-precision` option but no
        `--version-semver` option, it should exit with a return code of 2 and
        inform the user of the missing option.
        """
        with ExpectedException(SystemExit, MatchesStructure(code=Equals(2))):
            main(['--semver-precision', '2', 'test-image:abc'])

        out, err = capfd.readouterr()
        assert_that(out, Equals(''))
        assert_that(err, MatchesRegex(
            r'.*error: the --semver-precision option requires '
            r'--version-semver$',
            re.DOTALL
        ))

    def test_semver_zero_requires_version_semver(self, capfd):
        """
        When the main function is given the `--semver-zero` option but no
        `--version-semver` option, it should exit with a return code of 2 and
        inform the user of the missing option.
        """
        with ExpectedException(SystemExit, MatchesStructure(code=Equals(2))):
            main(['--semver-zero', 'test-image:abc'])

        out, err = capfd.readouterr()
        assert_that(out, Equals(''))
        assert_that(err, MatchesRegex(
            r'.*error: the --semver-zero option requires --version-semver$',
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

    def test_version_semver_requires_argument(self, capfd):
        """
        When the main function is given the `--version-semver` option without
        an argument, an error should be raised.
        """
        with ExpectedException(SystemExit, MatchesStructure(code=Equals(2))):
            main([
                '--version', '1.2.3',
                '--version-semver',
                '--semver-precision',
                '--', 'test-image',
            ])

        out, err = capfd.readouterr()
        assert_that(out, Equals(''))
        assert_that(err, MatchesRegex(
            r'.*error: argument -P/--semver-precision: expected one argument$',
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

    def test_deprecated_tag_version(self, capfd):
        """
        When the main function is given the `--tag-version` option, the option
        should be used as the `--version` option and a deprecation warning
        should be printed.
        """
        main([
            '--executable', 'echo',
            '--tag-version', '1.2.3',
            'test-image',
        ])

        assert_output_lines(capfd, [
            'tag test-image test-image:1.2.3',
            'push test-image:1.2.3',
        ], [
            ('DEPRECATED: the --tag-version option is deprecated and will be '
             'removed in the next release. Please use --version instead')
        ])

    def test_deprecated_tag_latest(self, capfd):
        """
        When the main function is given the `--tag-latest` option, the option
        should be used as the `--version-latest` option and a deprecation
        warning should be printed.
        """
        main([
            '--executable', 'echo',
            '--version', '1.2.3',
            '--tag-latest',
            'test-image',
        ])

        assert_output_lines(capfd, [
            'tag test-image test-image:1.2.3',
            'tag test-image test-image:latest',
            'push test-image:1.2.3',
            'push test-image:latest',
        ], [
            ('DEPRECATED: the --tag-latest option is deprecated and will be '
             'removed in the next release. Please use --version-latest '
             'instead')
        ])

    def test_deprecated_tag_semver(self, capfd):
        """
        When the main function is given the `--tag-semver` option, the option
        should be used as the `--version-semver` option and a deprecation
        warning should be printed.
        """
        main([
            '--executable', 'echo',
            '--version', '1.2.3',
            '--tag-semver',
            'test-image',
        ])

        assert_output_lines(capfd, [
            'tag test-image test-image:1.2.3',
            'tag test-image test-image:1.2',
            'tag test-image test-image:1',
            'push test-image:1.2.3',
            'push test-image:1.2',
            'push test-image:1',
        ], [
            ('DEPRECATED: the --tag-semver option is deprecated and will be '
             'removed in the next release. Please use --version-semver '
             'instead')
        ])

    def test_version_take_precedence_over_deprecated_tag_version(self, capfd):
        """
        When the main function is given the `--version` and `--tag-version`
        options, the `--version` value takes precedence over the
        `--tag-version` value.
        """
        main([
            '--executable', 'echo',
            '--version', '1.2.3',
            '--tag-version', '4.5.6',
            'test-image',
        ])

        assert_output_lines(capfd, [
            'tag test-image test-image:1.2.3',
            'push test-image:1.2.3',
        ], [
            ('DEPRECATED: the --tag-version option is deprecated and will be '
             'removed in the next release. Please use --version instead')
        ])
