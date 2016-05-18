import stat

import pytest

from docker_ci_deploy.__main__ import DockerCiDeployRunner


class TestDockerCiDeployRunner(object):
    @pytest.fixture(scope='session')
    def echo_script(self, tmpdir_factory):
        path = tmpdir_factory.mktemp('tmp').join('echo_script.sh')
        path.write('#!/bin/sh\necho "$@"\n')
        path.chmod(path.stat().mode | stat.S_IEXEC)
        return str(path)

    def test_defaults(self, capsys, echo_script):
        """
        When the runner is run with defaults, the image should be pushed.
        """
        runner = DockerCiDeployRunner(executable=echo_script)
        runner.run('test-image')

        out, err = capsys.readouterr()
        assert out == 'push test-image\n'
        assert err == ''

    def test_tags(self, capsys, echo_script):
        """
        When tags are provided to the runner, the image should be tagged and
        each tag should be pushed.
        """
        runner = DockerCiDeployRunner(executable=echo_script)
        runner.run('test-image', tags=['abc', 'def'])

        out, err = capsys.readouterr()
        out_lines = out.split('\n')

        assert out_lines.pop(0) == 'tag test-image test-image:abc'
        assert out_lines.pop(0) == 'tag test-image test-image:def'
        assert out_lines.pop(0) == 'push test-image:abc'
        assert out_lines.pop(0) == 'push test-image:def'
        assert out_lines.pop(0) == ''
        assert len(out_lines) == 0

        assert err == ''
