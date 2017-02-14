import codecs
import os

from setuptools import setup, find_packages

HERE = os.path.abspath(os.path.dirname(__file__))


def read(*parts):  # Stolen from txacme
    with codecs.open(os.path.join(HERE, *parts), 'rb', 'utf-8') as f:
        return f.read()


def readme():
    # Prefer the ReStructuredText README, but fallback to Markdown if it hasn't
    # been generated
    if os.path.exists('README.rst'):
        return read('README.rst')
    else:
        return read('README.md')


setup(
    name='docker-ci-deploy',
    version='0.2.0',
    license='MIT',
    url='https://github.com/praekeltfoundation/docker-ci-deploy',
    description='Python script to help push Docker images to a registry using '
                'CI services',
    long_description=readme(),
    author='Jamie Hewland',
    author_email='jamie@praekelt.org',
    maintainer='Praekelt.org SRE team',
    maintainer_email='sre@praekelt.org',
    classifiers=[
        'Development Status :: 4 - Beta',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
    ],
    packages=find_packages(),
    entry_points={
        'console_scripts': [
            'docker-ci-deploy = docker_ci_deploy.__main__:main',
            'dcd = docker_ci_deploy.__main__:main',
        ]
    }
)
