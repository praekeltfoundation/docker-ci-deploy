#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import print_function

import argparse
import re
import subprocess
import sys

from itertools import chain


def strip_image_tag(image):
    """
    Remove the tag part from a Docker tag and return the rest. Full tags are of
    the form [REGISTRYHOST/][NAME/...]NAME[:TAG] where the REGISTRYHOST may
    contain a ':' but no '/', the NAME parts may contain '/' but no ':', and
    the TAG part may contain neither ':' nor '/'.
    """
    match = re.match('^((?:[^\/]+\/)?[^:]+)(?::[^:\/]+)?$', image)
    if match is None:
        raise RuntimeError('Unable to parse tag "%s"' % (image,))

    return match.group(1)


def strip_image_registry(image):
    # TODO: Not yet sure how to differentiate REGISTRYHOST from a NAME segment.
    return image


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
    retcode = process.poll()
    if retcode:
        raise subprocess.CalledProcessError(retcode, args, output=out)

    if sys.version_info >= (3,):
        sys.stdout.buffer.write(out)
        sys.stderr.buffer.write(err)
    else:
        # Python 2 doesn't have a .buffer on stdout/stderr for writing binary
        # data. The below will only work for unicode in Python 2.7.1+ due to
        # https://bugs.python.org/issue4947.
        sys.stdout.write(out)
        sys.stderr.write(err)


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

    def _docker_cmd(self, *args):
        args = [self.executable] + list(args)
        if self.dry_run:
            self._log(*args)
            return

        cmd(args)

    def docker_tag(self, in_tag, out_tag):
        """ Run ``docker tag`` with the given tags. """
        self._docker_cmd('tag', in_tag, out_tag)

    def docker_login(self, username, password, registry):
        """ Run ``docker login`` with the given credentials. """
        cmd = [
            'login',
            '--username', username,
            '--password', password if not self.dry_run else '<password>',
        ]
        if registry is not None:
            cmd.append(registry)
        self._docker_cmd(*cmd)

    def docker_push(self, tag):
        """ Run ``docker push`` with the given tag. """
        self._docker_cmd('push', tag)

    def run(self, image, tags=None, login=None, registry=None):
        """
        Run the script - tag, login and push as necessary.

        :param image:
            The full source image tag.
        :param tags:
            A list of tags to tag the image with or None if no new tags are
            required.
        :param login:
            Login details for the Docker registry in the form
            <username>:<password>.
        :param registry:
            The address to the Docker registry host.
        """
        # Build list of tags to push with provided tags
        push_tags = []
        if tags is not None:
            stripped_tag = strip_image_tag(image)
            for tag in tags:
                push_tags.append('%s:%s' % (stripped_tag, tag,))
        else:
            push_tags = [image]

        # Update tags with registry host information
        if registry is not None:
            for i, tag in enumerate(push_tags):
                stripped_tag = strip_image_registry(tag)
                push_tags[i] = '%s/%s' % (registry, stripped_tag,)

        # Actually tag the image
        for tag in push_tags:
            if tag != image:
                self._log('Tagging "%s" as "%s"...' % (image, tag,),
                          if_verbose=True)
                self.docker_tag(image, tag)

        # Login if login details provided
        if login is not None:
            username, password = login.split(':', 2)
            self._log('Logging in as "%s"...' % (username,), if_verbose=True)
            self.docker_login(username, password, registry)

        # Finally, push the tags
        for tag in push_tags:
            self._log('Pushing tag "%s"...' % (tag,), if_verbose=True)
            self.docker_push(tag)


def main(raw_args=sys.argv[1:]):
    parser = argparse.ArgumentParser(
        description='Tag and push Docker images to a registry.')
    parser.add_argument('-t', '--tag', nargs='*',
                        action='append',
                        help='Tags to tag the image with before pushing')
    parser.add_argument('-l', '--login', nargs='?',
                        help='Login details in the form <username>:<password> '
                             'to login to the registry')
    parser.add_argument('-r', '--registry', nargs='?',
                        help='Address for the registry to login and push to')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Verbose logging output')
    parser.add_argument('--dry-run', action='store_true',
                        help='Print but do not execute any Docker commands')
    parser.add_argument('--executable', nargs='?', default='docker',
                        help='Path to the Docker client executable (default: '
                             '%(default)s)')
    parser.add_argument('image', help='Tag (full image name) to push')

    args = parser.parse_args(raw_args)

    runner = DockerCiDeployRunner(dry_run=args.dry_run, verbose=args.verbose,
                                  executable=args.executable)
    # Flatten list of tags
    tags = chain.from_iterable(args.tag) if args.tag is not None else None
    runner.run(args.image, tags=tags, login=args.login, registry=args.registry)


if __name__ == "__main__":
    main()  # pragma: no cover
