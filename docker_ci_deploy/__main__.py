#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import print_function

import argparse
import re
import subprocess
import sys
from itertools import chain


# Reference regexes for parsing Docker image tags into separate parts.
# https://github.com/docker/distribution/blob/v2.6.0-rc.2/reference/regexp.go
HOSTNAME_COMPONENT_PATTERN = (
    r'(?:[a-zA-Z0-9]|[a-zA-Z0-9][a-zA-Z0-9-]*[a-zA-Z0-9])')
# hostname = hostcomponent ['.' hostcomponent]* [':' port-number]
HOSTNAME_PATTERN = (
    HOSTNAME_COMPONENT_PATTERN +
    r'(?:(?:\.{})+)?'.format(HOSTNAME_COMPONENT_PATTERN) +
    r'(?::[0-9]+)?')

NAME_COMPONENT_PATTERN = r'[a-z0-9]+(?:(?:(?:[._]|__|[-]*)[a-z0-9]+)+)?'
# name = [hostname '/'] component ['/' component]*
NAME_PATTERN = (
    r'(?:{}/)?'.format(HOSTNAME_PATTERN) +
    NAME_COMPONENT_PATTERN +
    r'(?:(?:/{})+)?'.format(NAME_COMPONENT_PATTERN))

TAG_PATTERN = r'[\w][\w.-]{0,127}'
DIGEST_PATTERN = (
    r'[A-Za-z][A-Za-z0-9]*(?:[-_+.][A-Za-z][A-Za-z0-9]*)*[:][[:xdigit:]]{32,}')

# REFERENCE_REGEX is the full supported format of a reference. The regex is
# anchored and has capturing groups for name, tag, and digest components.
# reference = name [ ":" tag ] [ "@" digest ]
REFERENCE_REGEX = re.compile(
    r'^({})'.format(NAME_PATTERN) +
    r'(?::({}))?'.format(TAG_PATTERN) +
    r'(?:@({}))?$'.format(DIGEST_PATTERN))

# ANCHORED_NAME_REGEX is used to parse a name value, capturing the hostname and
# trailing components.
ANCHORED_NAME_REGEX = re.compile(r'^{}$'.format(
    r'(?:({})/)?'.format(HOSTNAME_PATTERN) +
    r'({})'.format(
        NAME_COMPONENT_PATTERN +
        r'(?:(?:/{})+)?'.format(NAME_COMPONENT_PATTERN))))


def split_image_tag(image_tag):
    """
    Split the given image tag into its name and tag parts (<name>[:<tag>]).
    """
    match = REFERENCE_REGEX.match(image_tag)
    if match is None:
        raise ValueError("Unable to parse image tag '%s'" % (image_tag,))

    return match.group(1), match.group(2)


def join_image_tag(image, tag):
    """ Join an image name and tag. """
    if not tag:
        return image

    return ':'.join((image, tag))


class RegistryTagger(object):
    def __init__(self, registry):
        self._registry = registry

    def generate_tag(self, image):
        # First try just append the registry without stripping the old
        joined_image = _join_image_registry(image, self._registry)
        # Check if that worked and return if so
        if ANCHORED_NAME_REGEX.match(joined_image) is not None:
            return joined_image

        # If the tag was invalid, try strip the existing registry first
        return _join_image_registry(
            _strip_image_registry(image), self._registry)


def _strip_image_registry(image):
    match = ANCHORED_NAME_REGEX.match(image)
    if match is None:
        raise ValueError("Unable to parse image name '%s'" % (image,))

    return match.group(2)


def _join_image_registry(image, registry):
    return '/'.join((registry, image))


class VersionTagger(object):
    def __init__(self, versions, latest=False):
        """
        :param versions:
            The list of version to prepend to the tag.
        :param latest:
            If True, return the tag without the version as well as the
            versioned tag(s). Include the tag 'latest' if the given tag is
            empty or None.
        """
        self._versions = versions
        self._latest = latest

    def generate_tags(self, tag):
        """
        Generate a list of tags based on the given tag and version information.
        Prepends the version to the tag, unless the version is already present.

        :param tag:
            The input tag to generate version tags from. The tag 'latest' is
            considered a special-case and will be treated like an empty tag
            (i.e. the version will be returned as the new tag).
        :rtype: list
        """
        stripped_tag = _strip_tag_version(tag, self._versions)

        if stripped_tag and stripped_tag != 'latest':
            versioned_tags = (
                [_join_tag_version(stripped_tag, v) for v in self._versions])
        else:
            versioned_tags = list(self._versions)

        if self._latest:
            latest_tag = stripped_tag if stripped_tag else 'latest'
            versioned_tags.append(latest_tag)

        return versioned_tags


def _strip_tag_version(tag, semver_versions):
    """
    Strip the version from the front of the given tag (not image tag) if the
    version is present.

    :param semver_versions:
        A list of versions from longest to shortest.
    """
    if tag is None:
        return None
    for version in semver_versions:
        if tag == version:
            return ''
        if tag.startswith(version + '-'):
            return tag[len(version) + 1:]

    return tag


def _join_tag_version(tag, version):
    """
    Join a tag (not image tag) and version by prepending the version to the tag
    with a '-' character.
    """
    return '-'.join((version, tag))


def generate_semver_versions(version, precision=1, zero=False):
    """
    Generate strings of the given version to different degrees of precision.
    Won't generate a version 0 unless ``zero`` is True.
    e.g. '5.4.1' => ['5.4.1', '5.4', '5']
         '5.5.0-alpha' => ['5.5.0-alpha', '5.5.0', '5.5', '5']

    :param version: The version string to generate versions from.
    :param precision:
        The minimum number of version parts in the generated versions.
    :param zero:
        If True, also return the major version '0' when generating versions.
    """
    sub_versions = []
    remaining_version = version
    while remaining_version:
        sub_versions.append(remaining_version)
        remaining_version = re.sub(r'[.-]?\w+$', r'', remaining_version)

    if precision > len(sub_versions):
        raise ValueError(
            'The minimum precision (%d) is greater than the precision of '
            "version '%s' (%d)" % (precision, version, len(sub_versions)))

    if precision > 1:
        sub_versions = sub_versions[:-(precision - 1)]

    if not zero and len(sub_versions) > 1 and sub_versions[-1] == '0':
        sub_versions = sub_versions[:-1]

    return sub_versions


def generate_tags(image_tag, tags=None, version_tagger=None,
                  registry_tagger=None):
    """
    Generate tags for the given image tag.

    :param image:
        A full source image tag.
    :param tags:
        A list of tags to tag the image with or None if no new tags are
        required.
    :param version_tagger:
        The VersionTagger instance to tag with.
    :param registry_tagger:
        The RegistryTagger instance to tag with.
    :return:
        The list of tags for this image.
    """
    image, tag = split_image_tag(image_tag)

    # Replace registry in image name
    if registry_tagger is not None:
        registry_image = registry_tagger.generate_tag(image)
    else:
        registry_image = image

    # Add the version to any tags
    new_tags = tags if tags is not None else [tag]
    if version_tagger is not None:
        version_tags = []
        for new_tag in new_tags:
            version_tags.extend(version_tagger.generate_tags(new_tag))
    else:
        version_tags = new_tags

    # Finally, rejoin the image name and tag parts
    return [join_image_tag(registry_image, v_t) for v_t in version_tags]


def cmd(args):
    """
    Execute a command in a subprocess. The process is waited for and the return
    code is checked. If the return code is non-zero, an error is raised. The
    stdout/stderr of the process is written to Python's stdout/stderr.

    :param list args:
        List of program arguments to execute.
    """
    process = subprocess.Popen(
        args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    out, err = process.communicate()

    if sys.version_info >= (3,):
        sys.stdout.buffer.write(out)
        sys.stderr.buffer.write(err)
    else:
        # Python 2 doesn't have a .buffer on stdout/stderr for writing binary
        # data. The below will only work for unicode in Python 2.7.1+ due to
        # https://bugs.python.org/issue4947.
        sys.stdout.write(out)
        sys.stderr.write(err)

    retcode = process.poll()
    if retcode:
        raise subprocess.CalledProcessError(retcode, args, output=out)


class DockerCiDeployRunner(object):

    logger = print

    def __init__(self, executable='docker', dry_run=False, verbose=False):
        self.executable = executable
        self.dry_run = dry_run
        self.verbose = verbose

    def _log(self, *args, **kwargs):
        if kwargs.get('if_verbose', False) and not self.verbose:
            return
        self.logger(*args)

    def _docker_cmd(self, args):
        args = [self.executable] + args

        if self.dry_run:
            self._log(*args)
            return

        cmd(args)

    def docker_tag(self, in_tag, out_tag):
        """ Run ``docker tag`` with the given tags. """
        if in_tag == out_tag:
            self._log('Not tagging "%s" as itself' % (in_tag,),
                      if_verbose=True)
            return

        self._log('Tagging "%s" as "%s"...' % (in_tag, out_tag),
                  if_verbose=True)
        self._docker_cmd(['tag', in_tag, out_tag])

    def docker_push(self, tag):
        """ Run ``docker push`` with the given tag. """
        self._log('Pushing tag "%s"...' % (tag,), if_verbose=True)
        self._docker_cmd(['push', tag])


def main(raw_args=sys.argv[1:]):
    parser = argparse.ArgumentParser(
        description='Tag and push Docker images to a registry.')
    parser.add_argument('-t', '--tag', nargs='+', action='append',
                        help='Tags to tag the image with before pushing')
    parser.add_argument('-V', '--version',
                        help='Prepend the given version to all tags')
    parser.add_argument('-L', '--version-latest', action='store_true',
                        help='Combine with --version to also tag the image '
                             'without a version so that it is considered the '
                             'latest version')
    parser.add_argument('-S', '--version-semver', action='store_true',
                        help='Combine with --version to also tag the image '
                             'with each major and minor version')
    parser.add_argument('-P', '--semver-precision', type=int,
                        metavar='PRECISION',
                        help='Combine with --version-semver to specify the '
                             'minimum number of parts in the generated '
                             'versions (default: 1)')
    parser.add_argument('-Z', '--semver-zero', action='store_true',
                        help='Combine with --version-semver to tag the image '
                             "with the major version '0' when that is part of "
                             'the version. This is not done by default.')
    parser.add_argument('-r', '--registry',
                        help='Address for the registry to push to')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Verbose logging output')
    parser.add_argument('--dry-run', action='store_true',
                        help='Print but do not execute any Docker commands')
    parser.add_argument('--executable', default='docker',
                        help='Path to the Docker client executable (default: '
                             '%(default)s)')
    parser.add_argument('image', nargs='+',
                        help='Tags (full image names) to push')

    _add_deprecated_arguments(parser)

    args = parser.parse_args(raw_args)
    _resolve_deprecated_arguments(args)

    if args.version_latest and not args.version:
        parser.error('the --version-latest option requires --version')
    if args.version_semver and not args.version:
        parser.error('the --version-semver option requires --version')

    if args.semver_precision and not args.version_semver:
        parser.error('the --semver-precision option requires --version-semver')
    if args.semver_zero and not args.version_semver:
        parser.error('the --semver-zero option requires --version-semver')

    runner = DockerCiDeployRunner(dry_run=args.dry_run, verbose=args.verbose,
                                  executable=args.executable)
    # Flatten list of tags
    tags = chain.from_iterable(args.tag) if args.tag is not None else None

    if args.version:
        if args.version_semver:
            versions = generate_semver_versions(
                args.version, args.semver_precision or 1, args.semver_zero)
        else:
            versions = [args.version]
        version_tagger = VersionTagger(versions, args.version_latest)
    else:
        version_tagger = None

    if args.registry:
        registry_tagger = RegistryTagger(args.registry)
    else:
        registry_tagger = None

    # Generate tags
    def tagger(image):
        return generate_tags(image, tags, version_tagger, registry_tagger)
    tag_map = [(image, tagger(image)) for image in args.image]

    # Tag images
    for image, push_tags in tag_map:
        for push_tag in push_tags:
            runner.docker_tag(image, push_tag)

    # Push tags
    for _, push_tags in tag_map:
        for push_tag in push_tags:
            runner.docker_push(push_tag)


def _add_deprecated_arguments(parser):
    parser.add_argument('--tag-version', help=argparse.SUPPRESS,
                        default=argparse.SUPPRESS)
    parser.add_argument('--tag-latest', action='store_true',
                        help=argparse.SUPPRESS, default=argparse.SUPPRESS)
    parser.add_argument('--tag-semver', action='store_true',
                        help=argparse.SUPPRESS, default=argparse.SUPPRESS)


def _resolve_deprecated_arguments(args):
    deprecated_mapping = {
        'tag_version': 'version',
        'tag_latest': 'version_latest',
        'tag_semver': 'version_semver',
    }
    for deprecated, new in deprecated_mapping.items():
        if deprecated in args:
            print('DEPRECATED: the --{} option is deprecated and will be '
                  'removed in the next release. Please use --{} instead'
                  .format(
                    deprecated.replace('_', '-'),
                    new.replace('_', '-')),
                  file=sys.stderr)
            if not getattr(args, new):
                setattr(args, new, getattr(args, deprecated))


if __name__ == "__main__":
    main()  # pragma: no cover
