# docker-ci-deploy

[![PyPI](https://img.shields.io/pypi/v/docker-ci-deploy.svg)](https://pypi.python.org/pypi/docker-ci-deploy)
[![Build Status](https://travis-ci.org/praekeltfoundation/docker-ci-deploy.svg?branch=develop)](https://travis-ci.org/praekeltfoundation/docker-ci-deploy)
[![codecov](https://codecov.io/gh/praekeltfoundation/docker-ci-deploy/branch/develop/graph/badge.svg)](https://codecov.io/gh/praekeltfoundation/docker-ci-deploy)

> NOTE: The `-l`/`--login` parameter (and associated `-d`/`--debug` parameter) has been removed in version 0.3.0. Use a manual `docker login` command in the `before_deploy` section of your Travis file (or equivalent) to log in.

A command-line tool to help generate tags and push Docker images to a registry. Simplifies deployment of Docker images from CI services such as Travis CI.

In a single command, `docker-ci-deploy` can:
* Change the tags on images
* Add version information to image tags
* Add registry addresses to image tags
* Push tags to a registry

The best way to try out `docker-ci-deploy` is to give it a spin with the `--dry-run` flag and observe all the `docker` commands that it *would* invoke:
```
> $ docker-ci-deploy --version 2.7.13 --version-semver --version-latest \
      --registry registry:5000 --dry-run \
      praekeltorg/alpine-python \
      praekeltorg/alpine-python:onbuild

docker tag praekeltorg/alpine-python registry:5000/praekeltorg/alpine-python:2.7.13
docker tag praekeltorg/alpine-python registry:5000/praekeltorg/alpine-python:2.7
docker tag praekeltorg/alpine-python registry:5000/praekeltorg/alpine-python:2
docker tag praekeltorg/alpine-python registry:5000/praekeltorg/alpine-python:latest
docker tag praekeltorg/alpine-python:onbuild registry:5000/praekeltorg/alpine-python:2.7.13-onbuild
docker tag praekeltorg/alpine-python:onbuild registry:5000/praekeltorg/alpine-python:2.7-onbuild
docker tag praekeltorg/alpine-python:onbuild registry:5000/praekeltorg/alpine-python:2-onbuild
docker tag praekeltorg/alpine-python:onbuild registry:5000/praekeltorg/alpine-python:onbuild
docker push registry:5000/praekeltorg/alpine-python:2.7.13
docker push registry:5000/praekeltorg/alpine-python:2.7
docker push registry:5000/praekeltorg/alpine-python:2
docker push registry:5000/praekeltorg/alpine-python:latest
docker push registry:5000/praekeltorg/alpine-python:2.7.13-onbuild
docker push registry:5000/praekeltorg/alpine-python:2.7-onbuild
docker push registry:5000/praekeltorg/alpine-python:2-onbuild
docker push registry:5000/praekeltorg/alpine-python:onbuild
```

If you want to make your commands even shorter, the `docker-ci-deploy` command is also available as just `dcd`, and most options have a short form:
```
> $ dcd -V 3.6.0 -S -L -r registry:5000 --dry-run alpine-python

docker tag alpine-python registry:5000/alpine-python:3.6.0
docker tag alpine-python registry:5000/alpine-python:3.6
docker tag alpine-python registry:5000/alpine-python:3
docker tag alpine-python registry:5000/alpine-python:latest
docker push registry:5000/alpine-python:3.6.0
docker push registry:5000/alpine-python:3.6
docker push registry:5000/alpine-python:3
docker push registry:5000/alpine-python:latest
```

Use the `-h`/`--help` option to see all available options.

## Installation
```
pip install docker-ci-deploy==0.2.0
```

The script is self-contained and has no dependencies. It can be run by simply executing the [main file](docker-ci-deploy/__main__.py).

## Usage
The script can tag an existing image and push the new tags to a registry.

There is one required argument: the image to push.

#### Pushing an image
```
docker-ci-deploy my-image:latest
```

This will simply push the image `my-image:latest` to the default registry (https://hub.docker.com).

#### Tagging
```
docker-ci-deploy --tag alpine --tag $(git rev-parse --short HEAD) my-image:latest

```
This will result in the tags `my-image:alpine` and `my-image:eea981f` (for example) being created and pushed (**Note:** the original tag `my-image:latest` is _not_ pushed).

#### Version tags
```
docker-ci-deploy --tag alpine --version 1.2.3 my-image
```
This will result in the tag `my-image:1.2.3-alpine` being created and pushed. If a version is already present in the start of a tag, it will not be added. For example, in the above example if `--tag 1.2.3-alpine` were provided, the image would still be tagged with `1.2.3-alpine`, not `1.2.3-1.2.3-alpine`.

You can also push the tags without the version information so that they are considered the "latest" tag:
```
docker-ci-deploy --version 1.2.3 --version-latest my-image
```
This will result in the tags `my-image:1.2.3` and `my-image:latest` being pushed.

> NOTE: The `--version` and `--version-latest` options used to be known as `--tag-version` and `--tag-latest`, respectively. These old option names will continue working for the current release but will be removed soon.

#### Semantic version tags
```
docker-ci-deploy --tag alpine --version 1.2.3 --version-semver my-image
```
This will result in the tags `my-image:1.2.3-alpine`, `my-image:1.2-alpine`, and `my-image:1-alpine` being created and pushed. If part of the version is already present in the start of a tag, it will not be added. For example, in the above example if `--tag 1.2-alpine` were provided, the image would still be tagged with `1.2.3-alpine`, not `1.2.3-1.2-alpine`.

This works by stripping pieces from the front of the version string using the regex `[.-]?\w+$`. This means that version strings with some text in them are also supported. For example, a tag such as `8.7.1-jessie` will produce the tags/tag prefixes `8.7.1-jessie`, `8.7.1`, `8.7`, and `8`.

An optional "precision" value can be set using the `--semver-precision` option. This sets the minimum precision of the generated versions. For example, by passing `--version 1.2.3 --version-semver --semver-precision 2`, the versions `1.2.3` and `1.2` are generated but *not* `1`.

Note that this will **not** tag a version `0` unless the `--semver-zero` option is also used.

This can be used in combination with `--version-latest`.

> NOTE: The `--version-semver` option used to be known as `--tag-version`. This old option name will continue working for the current release but will be removed soon.

#### Custom registry
```
docker-ci-deploy \
  --tag alpine --tag $(git rev-parse --short HEAD) \
  --registry my-registry.example.com:5000 \
  my-image:latest
```
This will result in the tags `my-registry.example.com:5000/my-image:alpine` and `my-registry.example.com:5000/my-image:eea981f` being created and pushed.

**NOTE:** The reference grammar for Docker image tags (as of Docker 1.13.0) is not strict enough to distinguish between a registry address and an image name component in all cases. For example, the tag `praekeltorg/alpine-python` could refer to the image with name `alpine-python` stored in the registry with hostname `praekeltorg` *or* it could be an image called `praekeltorg/alpine-python` stored in the default registry. `docker-ci-deploy` will first just prepend the registry address to the tag and only attempt to remove an existing registry address from the tag if the new tag is invalid.

#### Multiple images
You can provide multiple images to `docker-ci-deploy` and it will tag and push all of them:
```
docker-ci-deploy --tag $(git rev-parse --short HEAD) my-image my-other-image
```
This will result in the tags `my-image:eea981f` and `my-other-image:eea981f` being created and pushed.

#### Debugging
Use the `--dry-run` and `--verbose` parameters to see what the script will do before you use it. For more help try `docker-ci-deploy --help`.

## Travis CI
The script could be used in any CI service that provides access to the standard Docker CLI but was developed with Travis in mind.

For Travis CI this config should get you started pushing images to Docker Hub:
```yaml
sudo: required
services:
  - docker
language: python
env:
  global:
    - DOCKER_USER=janedoe
    - secret: <encrypted> # DOCKER_PASS=pa$$word

before_install:
  - sudo apt-get update
  - sudo apt-get install -o Dpkg::Options::="--force-confold" -y docker-engine
  - pip install docker-ci-deploy

script:
  - docker build -t janedoe/my-image .

before_deploy:
  - docker login -u "$DOCKER_USER" -p "$DOCKER_PASS"
deploy:
  provider: script
  script: docker-ci-deploy --tag $(git rev-parse --short HEAD) --tag latest janedoe/my-image
```
