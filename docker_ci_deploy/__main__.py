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


def replace_image_registry(image, registry):
    if registry is None:
        return image

    # First try just append the registry without stripping the old
    joined_image = _join_image_registry(image, registry)
    # Check if that worked and return if so
    if ANCHORED_NAME_REGEX.match(joined_image) is not None:
        return joined_image

    # If the tag was invalid, try strip the existing registry first
    return _join_image_registry(_strip_image_registry(image), registry)


def _strip_image_registry(image):
    match = ANCHORED_NAME_REGEX.match(image)
    if match is None:
        raise ValueError("Unable to parse image name '%s'" % (image,))

    return match.group(2)


def _join_image_registry(image, registry):
    return '/'.join((registry, image))


def generate_versioned_tags(tag, version, latest=False):
    """
    Generate a list of tags based on the given tag and version information.
    Prepends the given version

    :param tag:
        The input tag to generate version tags from. The tag 'latest' is
        considered a special-case and will be treated like an empty tag (i.e.
        the version will be returned as the new tag).
    :param version:
        The version to prepend to the tag. If None, the tag will be returned
        unchanged.
    :param latest:
        If True, return the tag without the version as well as the versioned
        tag(s). Include the tag 'latest' if the given tag is empty or None.
    :rtype: list
    """
    if version is None:
        return ['latest'] if latest and not tag else [tag]

    stripped_tag = _strip_tag_version(tag, version)
    if not stripped_tag or stripped_tag == 'latest':
        return [version, 'latest'] if latest else [version]

    versioned_tag = _join_tag_version(stripped_tag, version)
    return [versioned_tag, stripped_tag] if latest else [versioned_tag]


def _strip_tag_version(tag, version):
    """
    Strip the version from the front of the given tag (not image tag) if the
    version is present.
    """
    if tag is None:
        return None
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
    if not tag:
        return version

    return '-'.join((version, tag))


def cmd(args, sanitised_args=None):
    """
    Execute a command in a subprocess. The process is waited for and the return
    code is checked. If the return code is non-zero, an error is raised. The
    stdout/stderr of the process is written to Python's stdout/stderr.

    :param list args:
        List of program arguments to execute.
    :param list sanitised_args:
        Like ``args`` but with any sensitive data redacted. This will be passed
        to the exception object in the case of a non-zero return code.
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
        e_args = args if sanitised_args is None else sanitised_args
        raise subprocess.CalledProcessError(retcode, e_args, output=out)


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

    def _docker_cmd(self, args, sanitised_args=None):
        args = [self.executable] + args
        if sanitised_args is not None:
            sanitised_args = [self.executable] + sanitised_args

        if self.dry_run:
            log_args = args if sanitised_args is None else sanitised_args
            self._log(*log_args)
            return

        cmd(args, sanitised_args)

    def docker_tag(self, in_tag, out_tag):
        """ Run ``docker tag`` with the given tags. """
        self._docker_cmd(['tag', in_tag, out_tag])

    def docker_login(self, username, password, registry):
        """ Run ``docker login`` with the given credentials. """
        args = [
            'login',
            '--username', username,
            '--password', password,
        ]
        if registry is not None:
            args.append(registry)

        sanitised_args = list(args)
        sanitised_args[4] = '<password>'

        self._docker_cmd(args, sanitised_args)

    def docker_push(self, tag):
        """ Run ``docker push`` with the given tag. """
        self._docker_cmd(['push', tag])

    def run(self, images, tags=None, version=None, latest=False, login=None,
            registry=None):
        """
        Run the script - tag, login and push as necessary.

        :param images:
            A list of full source image tags.
        :param tags:
            A list of tags to tag the image with or None if no new tags are
            required.
        :param version:
            The version to prepend tags with.
        :param latest:
            Whether or not to tag this image with the latest tag.
        :param login:
            Login details for the Docker registry in the form
            <username>:<password>.
        :param registry:
            The address to the Docker registry host.
        """
        # Build map of images to tags to push with provided tags
        tag_map = []
        for image_tag in images:
            image, tag = split_image_tag(image_tag)

            # Replace registry in image name
            new_image = replace_image_registry(image, registry)

            # Add the version to any tags
            tags = tags if tags is not None else [tag]
            new_tags = []
            for new_tag in tags:
                new_tags.extend(
                    generate_versioned_tags(new_tag, version, latest))

            # Finally, rejoin the image name and tag parts
            new_image_tags = (
                [join_image_tag(new_image, new_tag) for new_tag in new_tags])

            tag_map.append((image_tag, new_image_tags))

        # Tag the images
        for image_tag, push_tags in tag_map:
            for push_tag in push_tags:
                if push_tag != image_tag:
                    self._log(
                        'Tagging "%s" as "%s"...' % (image_tag, push_tag),
                        if_verbose=True)
                    self.docker_tag(image_tag, push_tag)

        # Login if login details provided
        if login is not None:
            username, password = login.split(':', 2)
            self._log('Logging in as "%s"...' % (username,), if_verbose=True)
            self.docker_login(username, password, registry)

        # Finally, push the tags
        for _, push_tags in tag_map:
            for push_tag in push_tags:
                self._log('Pushing tag "%s"...' % (push_tag,), if_verbose=True)
                self.docker_push(push_tag)


def main(raw_args=sys.argv[1:]):
    parser = argparse.ArgumentParser(
        description='Tag and push Docker images to a registry.')
    parser.add_argument('-t', '--tag', nargs='*',
                        action='append',
                        help='Tags to tag the image with before pushing')
    parser.add_argument('--tag-version',
                        help='Prepend the given version to all tags')
    parser.add_argument('--tag-latest',
                        help='Combine with --tag-version to also tag the '
                             'image without a version so that it is considered'
                             'the latest version')
    parser.add_argument('-l', '--login', nargs='?',
                        help='Login details in the form <username>:<password> '
                             'to login to the registry')
    parser.add_argument('-r', '--registry', nargs='?',
                        help='Address for the registry to login and push to')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Verbose logging output')
    parser.add_argument('-d', '--debug', action='store_true',
                        help='Run in debug mode with full stacktraces. '
                             'WARNING: do not use this in production as it is '
                             'likely that your credentials will be leaked if '
                             'this script errors.')
    parser.add_argument('--dry-run', action='store_true',
                        help='Print but do not execute any Docker commands')
    parser.add_argument('--executable', nargs='?', default='docker',
                        help='Path to the Docker client executable (default: '
                             '%(default)s)')
    parser.add_argument('image', nargs='+',
                        help='Tags (full image names) to push')

    args = parser.parse_args(raw_args)

    runner = DockerCiDeployRunner(dry_run=args.dry_run, verbose=args.verbose,
                                  executable=args.executable)
    # Flatten list of tags
    tags = chain.from_iterable(args.tag) if args.tag is not None else None

    try:
        runner.run(args.image, tags=tags, version=args.tag_version,
                   latest=args.tag_latest, login=args.login,
                   registry=args.registry)
    except BaseException as e:
        if args.debug:
            raise

        print('Exception raised during execution: %s' % (str(e),))
        print('Stacktrace suppressed. Use debug mode to see full stacktrace.')
        sys.exit(1)


if __name__ == "__main__":
    main()  # pragma: no cover
