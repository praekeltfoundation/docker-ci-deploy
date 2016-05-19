from setuptools import setup

setup(
    name='docker-ci-deploy',
    version='0.1.0',
    license='MIT',
    url='https://github.com/praekeltfoundation/docker-ci-deploy',
    description='Python script to help push Docker images to a registry using '
                'CI services',
    author='Jamie Hewland',
    author_email='jamie@praekelt.com',
    classifiers=[
        'Development Status :: 4 - Beta',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
    ],
    entry_points={
        'console_scripts': [
            'docker-ci-deploy = docker_ci_deploy.__main__:main'
        ]
    }
)
