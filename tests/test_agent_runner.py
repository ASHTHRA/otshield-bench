"""Offline automation checks: no cloud providers or laboratory execution."""
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace

import pytest

from scripts import agent_runner as runner
from scripts import soup_context


def task_repo(tmp_path):
    (tmp_path / 'automation/tasks').mkdir(parents=True)
    (tmp_path / 'AGENTS.md').write_text('PERMANENT repository safety')
    (tmp_path / 'automation/AGENT_GUARDRAILS.md').write_text('PERMANENT evidence policy')
    task = tmp_path / 'automation/tasks/03_simulation_adapter.md'
    task.write_text('simulation Docker preflight')
    return task


def test_completed_never_forced(tmp_path, monkeypatch):
    task = task_repo(tmp_path)
    Path(str(task) + '.done').touch()
    Path(str(task) + '.blocked').touch()
    monkeypatch.setenv('FORCE_TASK', '1')
    assert runner.pending(tmp_path, task.name) == []


def test_pending_skips_blocked(tmp_path):
    task = task_repo(tmp_path)
    assert runner.pending(tmp_path) == [task]
    Path(str(task) + '.blocked').touch()
    assert runner.pending(tmp_path) == []


def test_future_numbered_tasks_are_discovered(tmp_path):
    task_repo(tmp_path)
    future = tmp_path / "automation/tasks/07_future.md"
    future.write_text("future")
    assert [item.name for item in runner.pending(tmp_path)] == [
        "03_simulation_adapter.md", "07_future.md"
    ]


@pytest.mark.parametrize('failure', [False, True])
def test_policy_outside_router(tmp_path, monkeypatch, failure):
    task = task_repo(tmp_path)
    def fake_run(*args, **kwargs):
        assert kwargs['input'] == task.read_text()
        assert 'PERMANENT' not in kwargs['input']
        if failure:
            raise subprocess.TimeoutExpired('soup', 1)
        return SimpleNamespace(returncode=0, stdout='optional routed context')
    monkeypatch.setattr(runner, 'run', fake_run)
    text = runner.prompt(tmp_path, task, 'fake-python')
    assert 'PERMANENT repository safety' in text
    assert 'PERMANENT evidence policy' in text
    assert runner.POLICY in text
    assert text.endswith(task.read_text())


def test_credentials_scoped_and_imports_absolute(tmp_path, monkeypatch):
    monkeypatch.setenv('GROQ_API_KEY', 'synthetic-groq')
    monkeypatch.setenv('TYPESAFE_API_KEY', 'synthetic-jev')
    monkeypatch.setenv('OTHER_TOKEN', 'synthetic-other')
    env = runner.environment(tmp_path, credentials=('GROQ_API_KEY',))
    assert env['GROQ_API_KEY'] == 'synthetic-groq'
    assert 'TYPESAFE_API_KEY' not in env
    assert 'OTHER_TOKEN' not in env
    assert env['PYTHONPATH'].split(':') == [str(tmp_path), str(tmp_path / 'src')]


def test_imports_survive_reset_clean(tmp_path):
    # Destructive commands run exclusively in this disposable fixture.
    def git(*args):
        subprocess.run(['git', *args], cwd=tmp_path, check=True, capture_output=True)
    git('init')
    (tmp_path / 'scripts').mkdir()
    (tmp_path / 'src/otshield').mkdir(parents=True)
    for path in ('scripts/__init__.py', 'src/otshield/__init__.py'):
        (tmp_path / path).write_text('')
    shutil.copy(runner.ROOT / 'scripts/soup_context.py', tmp_path / 'scripts/soup_context.py')
    git('add', '.')
    git('-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-m', 'fixture')
    (tmp_path / 'transient').touch()
    git('reset', '--hard', 'HEAD')
    git('clean', '-fd')
    result = runner.run([sys.executable, '-c', 'import scripts.soup_context, otshield'], tmp_path)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize('choice,code,expected', [('retry', 0, 'retry'), ('continue', 0, 'continue'),
    ('finish', 0, 'human_review'), ('retry', 1, 'human_review'), ('invalid', 0, 'human_review')])
def test_jev_fail_closed(tmp_path, monkeypatch, choice, code, expected):
    task = task_repo(tmp_path)
    monkeypatch.setattr(subprocess, 'run', lambda *a, **kw: SimpleNamespace(stdout=choice, returncode=code))
    assert runner.jev(tmp_path, task) == expected


def test_verification_uses_current_interpreter(tmp_path, monkeypatch):
    commands = []
    def fake_run(command, root):
        commands.append(command)
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(runner, 'run', fake_run)
    assert runner.verify(tmp_path)
    assert commands == [[sys.executable, '-m', 'pytest', '-q'], [sys.executable, '-m', 'build']]


def test_real_soup_offline_smoke():
    python = runner.ROOT / '.soup-venv/bin/python'
    if not python.exists():
        pytest.skip('Optional soup-ai environment absent; use runner --smoke after installation')
    result = runner.run([str(python), str(runner.ROOT / 'scripts/soup_context.py')],
                        runner.ROOT, input='simulation Docker Compose preflight adapter')
    assert result.returncode == 0, result.stderr
    assert 'mocked prerequisite' in result.stdout
    assert 'simulation Docker Compose preflight adapter' in result.stdout


def test_soup_contract(monkeypatch):
    class FakeSoup:
        def register(self, **kwargs):
            assert 'PERMANENT' not in kwargs['instructions']
        def prepare(self, task):
            return ['invalid output']
    monkeypatch.setitem(sys.modules, 'soup', SimpleNamespace(Soup=FakeSoup))
    with pytest.raises(ValueError):
        soup_context.route('task')


@pytest.mark.parametrize('decision,passes,expected_attempts,expected_code', [
    ('retry', [False, True], 2, 0),
    ('human_review', [False], 1, 20),
    ('retry', [False, False], 2, 20),
])
def test_bounded_pipeline(tmp_path, monkeypatch, decision, passes, expected_attempts, expected_code):
    task = task_repo(tmp_path)
    monkeypatch.setattr(runner, 'ROOT', tmp_path)
    monkeypatch.setattr(sys, 'argv', ['runner'])
    monkeypatch.setenv('GROQ_API_KEY', 'fake')
    monkeypatch.setenv('TYPESAFE_API_KEY', 'fake')
    monkeypatch.delenv('ONLY_TASK', raising=False)
    monkeypatch.setattr(shutil, 'which', lambda name: '/fake/aider')
    commands = []
    def fake_run(command, root, **kwargs):
        commands.append(command)
        return SimpleNamespace(returncode=0, stdout='')
    monkeypatch.setattr(runner, 'run', fake_run)
    monkeypatch.setattr(runner, 'prompt', lambda *a: 'PERMANENT policy plus task context')
    monkeypatch.setattr(runner, 'verify', lambda root: True)
    monkeypatch.setattr(runner, 'jev', lambda *a: decision)
    attempts = []
    def fake_implement(root, text, model):
        assert root != tmp_path
        assert root.parent == tmp_path / '.otshield-runtime'
        assert 'PERMANENT' in text
        attempts.append(model)
        return passes[len(attempts) - 1]
    monkeypatch.setattr(runner, 'implement', fake_implement)
    assert runner.main() == expected_code
    assert len(attempts) == expected_attempts
    assert task.read_text() == 'simulation Docker preflight'
    assert not Path(str(task) + '.done').exists()
    assert not Path(str(task) + '.blocked').exists()
    assert not any(word in command for command in commands for word in ('push', 'reset', 'clean', 'commit'))
