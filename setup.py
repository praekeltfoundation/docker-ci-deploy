from setuptools import setup, find_packages


with open('README.md') as f:
    README = f.read()

setup(
    name='docker-ci-deploy',
    version='0.2.0.dev0',
    license='MIT',
    url='https://github.com/praekeltfoundation/docker-ci-deploy',
    description='Python script to help push Docker images to a registry using '
                'CI services',
    long_description=README,
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
            'docker-ci-deploy = docker_ci_deploy.__main__:main'
        ]
    }
)
