#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import print_function

import argparse
import re
import subprocess
import sys
from itertools import chain


# This is complicated but these are the complete regexes used in Docker to
# match image tags. We only use these 2 regexes as porting all of the machinery
# from golang to Python is too much work.
#
# Source code in Docker:
# https://github.com/docker/distribution/blob/v2.6.0-rc.2/reference/regexp.go
#
# The pattern strings were extracted using The Go Playground:
# https://play.golang.org/p/xYRMnoqMqk
REFERENCE_REGEX = re.compile(
    r'^((?:(?:[a-zA-Z0-9]|[a-zA-Z0-9][a-zA-Z0-9-]*[a-zA-Z0-9])(?:(?:\.(?:[a-zA'
    r'-Z0-9]|[a-zA-Z0-9][a-zA-Z0-9-]*[a-zA-Z0-9]))+)?(?::[0-9]+)?/)?[a-z0-9]+('
    r'?:(?:(?:[._]|__|[-]*)[a-z0-9]+)+)?(?:(?:/[a-z0-9]+(?:(?:(?:[._]|__|[-]*)'
    r'[a-z0-9]+)+)?)+)?)(?::([\w][\w.-]{0,127}))?(?:@([A-Za-z][A-Za-z0-9]*(?:['
    r'-_+.][A-Za-z][A-Za-z0-9]*)*[:][[:xdigit:]]{32,}))?$')

ANCHORED_NAME_REGEX = re.compile(
    r'^(?:((?:[a-zA-Z0-9]|[a-zA-Z0-9][a-zA-Z0-9-]*[a-zA-Z0-9])(?:(?:\.(?:[a-zA'
    r'-Z0-9]|[a-zA-Z0-9][a-zA-Z0-9-]*[a-zA-Z0-9]))+)?(?::[0-9]+)?)/)?([a-z0-9]'
    r'+(?:(?:(?:[._]|__|[-]*)[a-z0-9]+)+)?(?:(?:/[a-z0-9]+(?:(?:(?:[._]|__|[-]'
    r'*)[a-z0-9]+)+)?)+)?)$')


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

    return _join_image_registry(_strip_image_registry(image), registry)


def _strip_image_registry(image):
    match = ANCHORED_NAME_REGEX.match(image)
    if match is None:
        raise ValueError("Unable to parse image name '%s'" % (image,))

    return match.group(2)


def _join_image_registry(image, registry):
    return '/'.join((registry, image))


def replace_tag_version(tag, version):
    """
    Replace the version information in the tag with the given version.

    XXXX: will make more sense with more features...
    """
    if version is None:
        return tag

    return _join_tag_version(_strip_tag_version(tag, version), version)


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

    def run(self, images, tags=None, version=None, login=None, registry=None):
        """
        Run the script - tag, login and push as necessary.

        :param images:
            A list of full source image tags.
        :param tags:
            A list of tags to tag the image with or None if no new tags are
            required.
        :param version:
            The version to prepend tags with.
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
            new_tags = (
                [replace_tag_version(new_tag, version) for new_tag in tags])

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
                   login=args.login, registry=args.registry)
    except BaseException as e:
        if args.debug:
            raise

        print('Exception raised during execution: %s' % (str(e),))
        print('Stacktrace suppressed. Use debug mode to see full stacktrace.')
        sys.exit(1)


if __name__ == "__main__":
    main()  # pragma: no cover
