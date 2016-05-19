# docker-ci-deploy
Python script to help push Docker images to a registry using CI services

## Installation
```
pip install docker-ci-deploy
```

The script is self-contained and has no dependencies. It can be run by simply executing the [main file](docker-ci-deploy/__main__.py).

## Usage
The script can tag an existing image, login to a registry, and push the tags to the registry, depending on what arguments are passed to it.

There is one required argument: the image to push.

#### Pushing an image
```
docker-ci-deploy my-image:latest
```

This will simply push the image `my-image:latest` to the default registry (https://hub.docker.com).

#### Logging in
On a CI service you are unlikely to be logged in to the registry. You can login using the `--login` parameter, which takes an argument of the form `<username>:<password>`.
```
docker-ci-deploy --login 'janedoe:pa$$word' my-image:latest
```
The script will then login before pushing the image.

#### Tagging
```
docker-ci-deploy --login 'janedoe:pa$$word' \
  --tag alpine --tag $(git rev-parse --short HEAD) my-image:latest

```
This will result in the tags `my-image:alpine` and `my-image:eea981f` (for example) being created and pushed (**Note:** the original tag `my-image:latest` is _not_ pushed).

#### Custom registry
```
docker-ci-deploy --login 'janedoe:pa$$word' \
  --tag alpine --tag $(git rev-parse --short HEAD) \
  --registry my-registry.example.com:5000 \
  my-image:latest
```
This will result in the tags `my-registry.example.com:5000/my-image:alpine` and `my-registry.example.com:5000/my-image:eea981f` being created and pushed. A login request will be made to `my-registry.example.com:5000`.

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

deploy:
  provider: script
  script: docker-ci-deploy --tag $(git rev-parse --short HEAD) --tag latest --login "$DOCKER_USER:$DOCKER_PASS" janedoe/my-image
```
