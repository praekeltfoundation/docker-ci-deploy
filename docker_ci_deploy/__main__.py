#!/usr/bin/env python
from __future__ import print_function

import argparse
import re
import subprocess

from itertools import chain


def _strip_image_tag(image):
    """
    Remove the tag part from a Docker tag and return the rest. Full tags are of
    the form [REGISTRYHOST/][NAME/...]NAME[:TAG] where the REGISTRYHOST may
    contain a ':' but the NAME parts may not.
    """
    match = re.match('^((?:.+\/)?[^:]+)(?::.+)?$', image)
    if match is None:
        raise RuntimeError('Unable to parse tag "%s"' % (image,))

    return match.group(1)


def _strip_image_registry(image):
    # TODO: Not yet sure how to differentiate REGISTRYHOST from a NAME segment.
    return image


def _docker_cmd(*cmds, **kwargs):
    """ Run a Docker command or print it if ``dry_run=True``. """
    if kwargs.get('dry_run', False):
        if 'obfuscated' in kwargs:
            cmds = kwargs['obfuscated']
        print(' '.join(('docker',) + cmds))
    else:
        subprocess.check_output(('docker',) + cmds)


def docker_tag(in_tag, out_tag, **kwargs):
    """ Run ``docker tag`` with the given tags. """
    _docker_cmd('tag', in_tag, out_tag, **kwargs)


def docker_login(username, password, registry, **kwargs):
    """ Run ``docker login`` with the given credentials. """
    cmd = [
        'login',
        '--username', username,
        '--password', password,
        registry,
    ]
    obfuscated = list(cmd)
    obfuscated[4] = '<password>'
    kwargs['obfuscated'] = tuple(obfuscated)
    _docker_cmd(*cmd, **kwargs)


def docker_push(tag, **kwargs):
    """ Run ``docker push`` with the given tag. """
    _docker_cmd('push', tag, **kwargs)


def main():
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
    parser.add_argument('image',
                        help='Tag (full image name) to push')

    args = parser.parse_args()

    # Build list of tags to push with provided tags
    push_tags = []
    if args.tag is not None:
        tags = chain.from_iterable(args.tag)  # Flatten tags array
        stripped_tag = _strip_image_tag(args.image)
        for tag in tags:
            push_tags.append('%s:%s' % (stripped_tag, tag,))
    else:
        push_tags = [args.image]

    # Update tags with registry host information
    if args.registry is not None:
        for i, tag in enumerate(push_tags):
            stripped_tag = _strip_image_registry(tag)
            push_tags[i] = '%s/%s' % (args.registry, stripped_tag,)

    # Actually tag the image if necessary
    if len(push_tags) != 1 or push_tags[0] != args.image:
        for tag in push_tags:
            if args.verbose:
                print('Tagging "%s" as "%s"...' % (args.image, tag,))
            docker_tag(args.image, tag, dry_run=args.dry_run)

    # Login if login details provided
    if args.login is not None:
        username, password = args.login.split(':', 2)
        if args.verbose:
            print('Logging in as "%s"...' % (username,))
        docker_login(username, password, args.registry, dry_run=args.dry_run)

    # Finally, push the tags
    for tag in push_tags:
        if args.verbose:
            print('Pushing tag "%s"...' % (tag,))
        docker_push(tag, dry_run=args.dry_run)

if __name__ == "__main__":
    main()
