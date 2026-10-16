#!/usr/bin/env python3
"""Resumable single-account PR controller; cooperative foreground containment, NOT a sandbox.

All mutable data lives in a dedicated LOCAL repository's private control directory.
Cloud-synced roots are refused before writes; the user's project mirror is not used.
An explicit private runtime-config.json beside this installed program selects the
local control repository. Source checkouts are inert until installed/configured.
The user's main worktree is never checked out, pulled, staged, or committed. No force push,
reset, stash, clean, automatic conflict resolution, admin bypass, or fake approval.
Receipts retain guard outcomes/truncation and real exit codes, with credential
redaction. Arbitrary programs must cooperate: never detach or access another tree.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import shutil
import stat
import subprocess
import sys
import tempfile

ORIGIN = 'https://github.com/ChromiteCr/Skills.git'
REPOSITORY = 'ChromiteCr/Skills'
GH = shutil.which('gh') or 'gh'
GH_CONFIG = str(Path.home() / '.config/gh-personal')
NAME = 'ChromiteCr'
EMAIL = '152609776+ChromiteCr@users.noreply.github.com'
GATE_NAME = 'Skills gate'
GATE_APP_ID = 15368  # Verified public https://api.github.com/apps/github-actions identity.
HELPER = '!GH_CONFIG_DIR=' + GH_CONFIG + ' ' + GH + ' auth git-credential'
IDENT = re.compile(r'[a-z0-9]+(?:-[a-z0-9]+)*\Z')
SHA = re.compile(r'[0-9a-f]{40,64}\Z')
FORBIDDEN = {'sh', 'bash', 'zsh', 'dash', 'fish', 'csh', 'tcsh', 'ksh', 'nohup',
             'setsid', 'daemonize', 'at', 'batch', 'crontab', 'launchctl',
             'systemd-run', 'screen', 'tmux', 'disown', 'env', 'sudo', 'xargs', 'parallel'}
OPERATORS = {'&', '&&', '||', ';', '|', '>', '>>', '<', '2>', '2>&1'}
LIMITED = ['SKILL_INDEX.md', 'CHANGELOG.md', '.claude-plugin/plugin.json',
           '.claude-plugin/marketplace.json']


class Refused(Exception):
    def __init__(self, reason, code=73):
        self.reason, self.code = reason, code
        super().__init__(reason)


def require(condition, reason):
    if not condition:
        raise Refused(reason)


def label(value):
    require(isinstance(value, str) and len(value) <= 64 and IDENT.fullmatch(value), 'unsafe_id')
    return value


def redact(value):
    if isinstance(value, dict):
        return {k: '[REDACTED]' if re.search(r'token|password|passwd|authorization|secret|api[_-]?key|access[_-]?key', k, re.I)
                else redact(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(x) for x in value]
    if isinstance(value, str):
        value = re.sub(r'\b(?:gh[pousr]_[A-Za-z0-9_]+|github_pat_[A-Za-z0-9_]+)\b', '[REDACTED]', value)
        value = re.sub(r'(?i)(authorization\s*[:=]\s*(?:bearer|basic)?\s*)\S+', r'\1[REDACTED]', value)
        value = re.sub(r'(?i)(\b\w*(?:token|password|passwd|secret|api_key|access_key)\w*\s*=\s*)\S+', r'\1[REDACTED]', value)
        return re.sub(r'https://[^/\s@]+@', 'https://[REDACTED]@', value)
    return value


def local_path(path):
    """Reject known cloud roots and symlink routing; not a filesystem-provider detector.

    Installation must additionally verify the selected volume is local and not
    configured for third-party sync. Checking only a lexical path is insufficient.
    """
    path = Path(path)
    require(path.is_absolute() and '..' not in path.parts, 'absolute_local_path_required')
    for candidate in (path, path.resolve(strict=False)):
        parts = [part.casefold() for part in candidate.parts]
        require(not any(part in {'cloudstorage', 'mobile documents', 'dropbox',
                                 'google drive', 'googledrive', 'icloud drive'}
                        or part.startswith('onedrive') for part in parts),
                'cloud_synced_path_forbidden')
    require(not any(p.is_symlink() for p in [path, *path.parents]), 'symlink_local_path')
    return path


def runtime_root():
    config = Path(__file__).resolve().with_name('runtime-config.json')
    require(config.is_file() and not config.is_symlink(), 'local_runtime_not_installed')
    data = load(config)
    require(isinstance(data, dict) and data.get('schema') == 1 and
            isinstance(data.get('root'), str), 'invalid_runtime_config')
    return local_path(data['root'])


def private_dir(path):
    path = local_path(path)
    if not path.exists():
        path.mkdir(mode=0o700)
    info = path.lstat()
    require(stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid()
            and not info.st_mode & 0o077, 'unsafe_private_directory')
    return path


def atomic(path, data):
    path = Path(path)
    require(not path.is_symlink(), 'symlink_state')
    fd, tmp = tempfile.mkstemp(prefix='.pending-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as out:
            json.dump(data, out, sort_keys=True, ensure_ascii=False)
            out.write('\n')
            out.flush()
            os.fsync(out.fileno())
        os.replace(tmp, path)
        dfd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def load(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd) as src:
        info = os.fstat(src.fileno())
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_uid == os.getuid()
                and not info.st_mode & 0o077, 'unsafe_private_file')
        return json.load(src)


def environment():
    env = dict(os.environ)
    for key in list(env):
        if key.startswith(('GIT_', 'GH_', 'GITHUB_')) or re.search(
                r'TOKEN|SECRET|PASSWORD|PASSWD|AUTHORIZATION|API_KEY|ACCESS_KEY|PRIVATE_KEY', key, re.I):
            env.pop(key)
    env.update(GH_CONFIG_DIR=GH_CONFIG, GIT_TERMINAL_PROMPT='0', GIT_OPTIONAL_LOCKS='0',
               PYTHONDONTWRITEBYTECODE='1')
    if 'SKILLS_GUARD_FD' in env:
        scoped = [('gc.auto', '0'), ('gc.autoDetach', 'false'), ('maintenance.auto', 'false'),
                  ('maintenance.autoDetach', 'false'), ('core.fsmonitor', 'false')]
        env['GIT_CONFIG_COUNT'] = str(len(scoped))
        for i, (key, value) in enumerate(scoped):
            env['GIT_CONFIG_KEY_' + str(i)] = key
            env['GIT_CONFIG_VALUE_' + str(i)] = value
    return env


def inherited_fd():
    raw = os.environ.get('SKILLS_GUARD_FD')
    return (int(raw),) if raw is not None else ()


def command_allowed(argv):
    require(bool(argv), 'missing_command')
    resolved = shutil.which(argv[0]) or argv[0]
    require(Path(argv[0]).name not in FORBIDDEN and Path(resolved).resolve().name not in FORBIDDEN,
            'shell_or_detachment_launcher_forbidden')
    require(not any(arg in OPERATORS for arg in argv), 'shell_control_operator_forbidden')
    if Path(resolved).name == 'git':
        require(len(argv) > 1 and argv[1] in {'status', 'diff', 'show', 'log', 'ls-files', 'rev-parse'},
                'git_mutation_requires_controller')


class Controller:
    # Constructor injection is for synthetic tests, not a production CLI override.
    def __init__(self, root=None, origin=ORIGIN):
        self.root, self.origin = local_path(root) if root is not None else runtime_root(), origin
        self.control = self.root / '.git/skills-dev-control'
        require(not any(p.is_symlink() for p in [self.root, *self.root.parents]), 'symlink_root')
        require(not (self.root / '.git').is_symlink() and (self.root / '.git').is_dir(), 'not_local_gitdir')
        private_dir(self.control)
        self.data = private_dir(self.control / 'pr')
        self.receipts = private_dir(self.data / 'receipts')
        for folder in ('runs', 'items', 'snapshots'):
            private_dir(self.data / folder)
        self.state_path = self.data / 'state.json'
        self.state = load(self.state_path) if self.state_path.exists() else {'schema': 1, 'active': None, 'items': {}}

    def save(self):
        atomic(self.state_path, self.state)

    def receipt(self, kind, result):
        path = self.receipts / (kind + '-' + secrets.token_hex(12) + '.json')
        atomic(path, {'kind': kind, 'credential_redaction': True, **redact(result)})
        return str(path)

    def invoke(self, argv, cwd=None, check=True, timeout=180, kind='command', input=None):
        # File-backed capture cannot deadlock on inherited stdout pipes. Raw files
        # are private/unlinked; only redacted bounded output is durably recorded.
        # A guard JSON has two <=1MiB streams which JSON escaping can expand 6x.
        limit = 20 * 1024 * 1024 if kind == 'devctl-transport' else 1024 * 1024
        result = {}
        with tempfile.TemporaryFile(dir=self.receipts) as stdout, tempfile.TemporaryFile(dir=self.receipts) as stderr:
            try:
                proc = subprocess.run(argv, cwd=cwd or self.data, env=environment(), input=input,
                                      stdout=stdout, stderr=stderr, timeout=timeout, pass_fds=inherited_fd())
                code = proc.returncode
            except subprocess.TimeoutExpired:
                code = 124
            except OSError:
                code = 127
                stderr.write(b'cannot execute foreground command')
                stderr.flush()
            for name, stream in (('stdout', stdout), ('stderr', stderr)):
                size = os.fstat(stream.fileno()).st_size
                stream.seek(0)
                raw = stream.read(limit)
                result.update({name: raw.decode('utf-8', 'replace'), name + '_bytes': size,
                               name + '_truncated': size > len(raw)})
        result.update(returncode=code, exit_code=code if code >= 0 else 128 - code, timed_out=code == 124)
        result['receipt'] = self.receipt(kind, result)
        if check and code:
            raise Refused('command_failed; receipt=' + result['receipt'], result['exit_code'])
        if check and (result['stdout_truncated'] or result['stderr_truncated']):
            raise Refused('output_truncated; receipt=' + result['receipt'])
        return result

    def git(self, repo, *args, check=True, input=None):
        args = ['git', '-c', 'credential.helper=', '-c', 'credential.helper=' + HELPER,
                '-c', 'gc.auto=0', '-c', 'gc.autoDetach=false', '-c', 'maintenance.auto=false',
                '-c', 'maintenance.autoDetach=false', '-c', 'core.fsmonitor=false', *args]
        return self.invoke(args, repo, check, input=input, kind='git')

    def text(self, repo, *args):
        return self.git(repo, *args)['stdout'].strip()

    def gh(self, *args, check=True):
        return self.invoke([GH, *args], check=check, kind='github')

    def identity(self):
        require(self.gh('api', 'user', '--jq', '.login')['stdout'].strip() == NAME, 'personal_identity_mismatch')

    def inspect(self, repo, branch=None, intermediate=True):
        repo = Path(repo)
        require(not repo.is_symlink() and not (repo / '.git').is_symlink()
                and (repo / '.git').is_dir(), 'unsafe_clone_gitdir')
        require(Path(self.text(repo, 'rev-parse', '--show-toplevel')) == repo, 'clone_root_mismatch')
        require(Path(self.text(repo, 'rev-parse', '--absolute-git-dir')) == repo / '.git', 'clone_gitdir_mismatch')
        require(self.text(repo, 'remote', 'get-url', '--all', 'origin') == self.origin, 'origin_mismatch')
        require(self.text(repo, 'remote', 'get-url', '--push', '--all', 'origin') == self.origin, 'push_origin_mismatch')
        aux = self.git(repo, 'config', '--get-regexp',
                       r'^(core\.(hookspath|sshcommand)|filter\..*\.(clean|smudge|process)|merge\..*\.driver|diff\..*\.(command|textconv)|credential\..*\.helper|remote\..*\.pushurl|url\..*\.(insteadof|pushinsteadof))$', check=False)
        require(aux['returncode'] == 1, 'hooks_filters_or_redirects_require_review')
        hooks = repo / '.git/hooks'
        require(not hooks.is_symlink(), 'symlink_hooks')
        if hooks.exists():
            require(not any(p.is_symlink() or (p.is_file() and not p.name.endswith('.sample')
                        and os.access(p, os.X_OK)) for p in hooks.iterdir()), 'active_hooks_require_review')
        require(not (repo / '.git/objects/info/alternates').exists(), 'shared_objects_forbidden')
        if intermediate:
            for name in ('MERGE_HEAD', 'CHERRY_PICK_HEAD', 'REVERT_HEAD', 'rebase-merge',
                         'rebase-apply', 'sequencer', 'index.lock'):
                require(not (repo / '.git' / name).exists(), 'git_intermediate_state:' + name)
        if branch is not None:
            require(self.text(repo, 'branch', '--show-current') == branch, 'owned_branch_mismatch')
        for key in ('GIT_AUTHOR_IDENT', 'GIT_COMMITTER_IDENT'):
            require(self.text(repo, 'var', key).startswith(NAME + ' <' + EMAIL + '> '), 'git_identity_mismatch')

    def provision(self, folder, source):
        folder = local_path(folder)
        # A pre-existing path, even empty, is NEVER adopted. Failed clones stay for review.
        require(not folder.exists() and not folder.is_symlink(), 'unknown_or_incomplete_clone_preserved')
        self.git(folder.parent, 'clone', '--no-hardlinks', '--no-checkout', '--', str(source), str(folder))
        if str(source) != self.origin:
            require(self.text(folder, 'remote', 'get-url', '--all', 'origin') == str(source), 'new_clone_origin_unexpected')
            self.git(folder, 'remote', 'set-url', 'origin', self.origin)
        self.inspect(folder)

    def item(self):
        key = self.state.get('active')
        require(key in self.state['items'], 'no_active_item')
        item = self.state['items'][key]
        require(label(item['id']) == key and item['branch'] == 'auto/' + key, 'corrupt_item')
        require(item['plan_hash'] == self.plan_hash(item), 'plan_hash_changed')
        folder = self.data / 'items' / key
        private_dir(folder)
        require(load(folder / 'owner.json') == {'id': key, 'nonce': item['nonce']}, 'item_ownership_mismatch')
        return item, folder / 'repo'

    @staticmethod
    def plan_hash(item):
        plan = {k: item[k] for k in ('id', 'title', 'skill', 'acceptance', 'allowed_paths', 'base')}
        return hashlib.sha256(json.dumps(plan, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

    def bump(self, item, key):
        item['counters'][key] = item['counters'].get(key, 0) + 1
        self.save()

    def prepare(self):
        self.identity()
        if self.state['active']:
            item, repo = self.item()
            self.inspect(repo, item['branch'])
            return self.summary(item, repo, 'resumable')
        seed = self.data / 'seed'
        if not self.state.get('seed_ready'):
            self.provision(seed, self.origin)
            self.state['seed_ready'] = True
            self.save()
        self.inspect(seed)
        self.git(seed, 'fetch', '--no-tags', 'origin', 'refs/heads/main:refs/remotes/origin/main')
        base = self.text(seed, 'rev-parse', 'refs/remotes/origin/main')
        require(SHA.fullmatch(base), 'invalid_base')
        audit = self.git(seed, 'show', base + ':AUDIT-AND-IDEAS.md')['stdout']
        path = self.data / ('audit-' + base + '.json')
        atomic(path, {'base': base, 'path': 'AUDIT-AND-IDEAS.md', 'text': audit})
        self.state.update(prepared_base=base, audit_receipt=str(path))
        self.save()
        return {'status': 'prepared', 'base': base, 'audit_snapshot': str(path)}

    def create(self, args):
        key, skill = label(args.id), label(args.skill)
        require(args.title.strip() and args.acceptance.strip() and len(args.title) < 240, 'missing_plan')
        if self.state['active']:
            item, repo = self.item()
            require(all(item[k] == getattr(args, k) for k in ('id', 'title', 'skill', 'acceptance')), 'another_plan_active')
            self.inspect(repo, item['branch'])
            return self.summary(item, repo, 'resumable')
        require(key not in self.state['items'], 'completed_id_must_not_be_reused')
        self.prepare()
        base, seed = self.state['prepared_base'], self.data / 'seed'
        names = self.text(seed, 'ls-tree', '-r', '--name-only', base).splitlines()
        matches = [p for p in names if re.fullmatch(r'skills/[^/]+/' + re.escape(skill) + r'/SKILL\.md', p)]
        require(len(matches) == 1, 'select_exact_existing_skill; new_skills_require_review')
        prefix = matches[0].removesuffix('SKILL.md')
        allowed = [prefix, 'tests/cases/' + skill + '.md', 'tests/' + skill + '/',
                   'tests/fixtures/' + skill + '/', 'tests/test_' + skill.replace('-', '_') + '.py', *LIMITED]
        require(not self.remote_sha(seed, 'auto/' + key), 'remote_branch_already_exists')
        folder = self.data / 'items' / key
        require(not folder.exists() and not folder.is_symlink(), 'unknown_item_directory')
        private_dir(folder)
        item = dict(id=key, title=args.title, skill=skill, acceptance=args.acceptance,
                    allowed_paths=allowed, base=base, integration_base=base, branch='auto/' + key,
                    nonce=secrets.token_hex(16), counters={}, phase='creating')
        item['plan_hash'] = self.plan_hash(item)
        atomic(folder / 'owner.json', {'id': key, 'nonce': item['nonce']})
        self.state['items'][key] = item
        self.state['active'] = key
        self.save()
        self.provision(folder / 'repo', seed)
        self.git(folder / 'repo', 'checkout', '-b', item['branch'], base)
        item['phase'] = 'editing'
        self.save()
        return self.summary(item, folder / 'repo', 'created')

    def summary(self, item, repo, status):
        return {'status': status, 'id': item['id'], 'clone': str(repo), 'branch': item['branch'],
                'base': item['base'], 'plan_hash': item['plan_hash'], 'allowed_paths': item['allowed_paths'],
                'dirty': bool(self.text(repo, 'status', '--porcelain=v1', '--untracked-files=all')),
                'counters': item['counters'], 'pr': item.get('pr')}

    def run(self, args):
        item, repo = self.item()
        self.inspect(repo, item['branch'])
        command = args.command[1:] if args.command[:1] == ['--'] else args.command
        require(args.foreground, 'foreground_attestation_required')
        command_allowed(command)
        self.bump(item, 'runs')
        result = self.invoke(command, repo, check=False, timeout=None, kind='work')
        # The unchanged outer guard supplies the finite timeout and process-group supervision.
        item['last_run_exit'] = result['exit_code']
        self.save()
        return {'status': 'command_finished', 'exit_code': result['exit_code'], 'receipt': result['receipt']}

    def paths(self, repo, *args):
        return [x for x in self.git(repo, *args)['stdout'].split('\0') if x]

    def allowed(self, item, repo, path):
        parts = PurePosixPath(path).parts
        require(path and not path.startswith('/') and '\\' not in path and
                not any(ord(c) < 32 for c in path) and str(PurePosixPath(path)) == path
                and not any(p in ('.', '..', '.git', '.github') for p in parts), 'unsafe_path')
        require(not any(p.lower().startswith(('.env', '.git', '.ssh')) or
                p.lower() in {'agents.md', 'claude.md', 'audit-and-ideas.md', 'control', 'skills-dev-control',
                              '.aws', '.openclaw', '.claude', '.config', 'policy.md', 'pr_automation'} or
                re.search(r'(?i)(secret|credential|(?:^|[-_])tokens?(?:$|[-_.])|private[-_]?key|\.pem$|\.key$|\.p12$|\.pfx$)', p)
                for p in parts), 'private_or_control_path')
        require(any(path.startswith(p) if p.endswith('/') else path == p for p in item['allowed_paths']),
                'out_of_scope_path:' + path)
        cursor = repo
        for part in parts:
            cursor = cursor / part
            require(not cursor.is_symlink(), 'symlink_path')
            if cursor.exists():
                require(cursor.is_dir() or cursor.is_file(), 'special_file_path')

    def scope(self, item, repo):
        changes = set(self.paths(repo, 'diff', '--name-only', '-z', '--no-renames', item['integration_base']))
        changes.update(self.paths(repo, 'diff', '--cached', '--name-only', '-z', '--no-renames', item['integration_base']))
        changes.update(self.paths(repo, 'ls-files', '--others', '--exclude-standard', '-z'))
        for path in sorted(changes):
            self.allowed(item, repo, path)
        for row in self.paths(repo, 'ls-files', '--stage', '-z'):
            mode, rest = row.split(' ', 1)
            path = rest.split('\t', 1)[1]
            if path in changes:
                require(mode in ('100644', '100755'), 'symlink_or_submodule_index')
        return changes

    def remote_sha(self, repo, branch):
        rows = self.text(repo, 'ls-remote', '--heads', 'origin', 'refs/heads/' + branch).splitlines()
        require(len(rows) <= 1, 'ambiguous_remote_branch')
        if not rows:
            return None
        sha, ref = rows[0].split()
        require(SHA.fullmatch(sha) and ref == 'refs/heads/' + branch, 'invalid_remote_branch')
        return sha

    def query_pr(self, item):
        fields = 'number,state,isDraft,body,headRefName,headRefOid,baseRefName,mergeCommit,mergeStateStatus,statusCheckRollup,autoMergeRequest,url'
        rows = json.loads(self.gh('pr', 'list', '--repo', REPOSITORY, '--head', item['branch'],
                                 '--state', 'all', '--json', fields)['stdout'])
        require(isinstance(rows, list) and len(rows) <= 1, 'ambiguous_prs')
        if not rows:
            require(not item.get('pr'), 'previous_pr_missing')
            return None
        pr = rows[0]
        require(pr['headRefName'] == item['branch'] and pr['baseRefName'] == 'main'
                and self.marker(item) in pr['body'], 'foreign_pr_preserved')
        item['pr'] = pr['number']
        item['pr_state'] = pr['state']
        self.save()
        return pr

    @staticmethod
    def marker(item):
        return '<!-- skills-pr:' + item['id'] + ':' + item['plan_hash'] + ' -->'

    @staticmethod
    def failing(pr):
        bad = {'FAILURE', 'ERROR', 'CANCELLED', 'TIMED_OUT', 'ACTION_REQUIRED', 'STARTUP_FAILURE'}
        return any(str(c.get('conclusion') or c.get('state', '')).upper() in bad
                   for c in pr.get('statusCheckRollup') or [])

    def terminal(self, item, pr, repo):
        if pr and pr['state'] == 'MERGED':
            merge = pr.get('mergeCommit')
            oid = merge.get('oid') if isinstance(merge, dict) else None
            require(isinstance(oid, str) and SHA.fullmatch(oid), 'merged_commit_missing_preserved')
            self.git(repo, 'fetch', '--no-tags', 'origin', 'refs/heads/main:refs/remotes/origin/main')
            require(self.git(repo, 'merge-base', '--is-ancestor', oid, 'refs/remotes/origin/main',
                             check=False)['returncode'] == 0, 'merged_commit_not_on_main_preserved')
            item['phase'] = 'merged'
            self.state['active'] = None
            self.save()
            return {'status': 'merged', 'id': item['id'], 'pr': pr['number'], 'workspace_preserved': True}
        require(not pr or pr['state'] == 'OPEN', 'closed_unmerged_pr_preserved')
        require(not pr or pr.get('mergeStateStatus') not in ('DIRTY', 'CONFLICTING'), 'merge_conflict_preserved')
        return None

    def integrate(self, item, repo):
        self.git(repo, 'fetch', '--no-tags', 'origin', 'refs/heads/main:refs/remotes/origin/main')
        main = self.text(repo, 'rev-parse', 'refs/remotes/origin/main')
        if main == item['integration_base']:
            return None
        require(self.git(repo, 'merge-base', '--is-ancestor', item['integration_base'], main, check=False)['returncode'] == 0,
                'main_history_rewritten_preserved')
        if self.text(repo, 'status', '--porcelain=v1', '--untracked-files=all'):
            return {'status': 'needs_update', 'id': item['id'], 'dirty': True,
                    'reason': 'base_advanced; preserve edits; use checkpoint for validated local commit, then reconcile/finish'}
        dry = self.git(repo, 'merge-tree', '--write-tree', 'HEAD', main, check=False)
        require(dry['returncode'] == 0, 'merge_conflict_preserved')
        self.bump(item, 'base_updates')
        self.git(repo, 'merge', '--no-edit', '--no-stat', main)
        item['integration_base'] = main
        item['validated_tree'] = None
        self.save()
        return None

    @staticmethod
    def verify_export(snapshot, entries):
        for row in entries:
            header, path = row.split('\t', 1)
            mode, kind, oid = header.split()
            require(mode in ('100644', '100755') and kind == 'blob', 'nonregular_export_entry')
            require(path and not path.startswith('/') and '..' not in PurePosixPath(path).parts, 'unsafe_export_path')
            target = snapshot
            for part in PurePosixPath(path).parts:
                target = target / part
                require(not target.is_symlink(), 'export_symlink')
            info = target.stat()
            require(stat.S_ISREG(info.st_mode) and bool(info.st_mode & 0o111) == (mode == '100755'), 'export_mode_changed')
            digest = hashlib.new('sha1' if len(oid) == 40 else 'sha256')
            digest.update(('blob ' + str(info.st_size) + '\0').encode())
            with target.open('rb') as source:
                for chunk in iter(lambda: source.read(1024 * 1024), b''):
                    digest.update(chunk)
            require(digest.hexdigest() == oid, 'export_content_changed')

    def snapshot_check(self, item, repo, tree):
        self.bump(item, 'validations')
        folder = Path(tempfile.mkdtemp(prefix=item['id'] + '-', dir=self.data / 'snapshots'))
        # Kept on failure/success for diagnosis, never delete user work or unknown paths.
        snapshot = private_dir(folder / 'export')
        entries = self.paths(repo, 'ls-tree', '-r', '-z', tree)
        self.git(repo, 'checkout-index', '--all', '--prefix=' + str(snapshot) + '/')
        self.verify_export(snapshot, entries)
        changes = self.paths(repo, 'diff', '--cached', '--name-status', '-z', '--no-renames', item['integration_base'])
        manifest = folder / 'changes.json'
        atomic(manifest, [{'status': s, 'path': p} for s, p in zip(changes[::2], changes[1::2])])
        atomic(folder / 'snapshot.json', {'base': item['base'], 'integration_base': item['integration_base'],
                                         'tree': tree, 'manifest': str(manifest)})
        ci = Path(__file__).resolve().with_name('ci.py')
        require(ci.is_file() and not ci.is_symlink(), 'trusted_ci_missing')
        result = self.invoke([sys.executable, str(ci), '--root', str(snapshot), '--files-json', str(manifest),
                              '--mode', 'local', '--branch', item['branch']],
                             snapshot, check=False, timeout=None, kind='validation')
        if result['exit_code']:
            raise Refused('local_checks_failed; receipt=' + result['receipt'], result['exit_code'])
        # CI always runs automation tests, but selected new business unittest
        # files must also actually run, rather than merely appear in the commit.
        additional = []
        named = 'test_' + item['skill'].replace('-', '_') + '.py'
        targets = [('tests', named)] if (snapshot / 'tests' / named).is_file() else []
        own_tests = snapshot / 'tests' / item['skill']
        if own_tests.is_dir() and any(own_tests.rglob('test*.py')):
            targets.append(('tests/' + item['skill'], 'test*.py'))
        for directory, pattern in targets:
            tested = self.invoke([sys.executable, '-B', '-m', 'unittest', 'discover', '-s', directory,
                                  '-p', pattern, '-v'], snapshot, check=False, timeout=None, kind='targeted-test')
            additional.append(tested['receipt'])
            incomplete = re.search(r'Ran 0 tests|skipped=[1-9]|expected failures=[1-9]',
                                   tested['stdout'] + tested['stderr'])
            if tested['exit_code'] or incomplete or tested['stdout_truncated'] or tested['stderr_truncated']:
                raise Refused('targeted_tests_failed_or_incomplete; receipt=' + tested['receipt'], tested['exit_code'] or 73)
        self.verify_export(snapshot, entries)
        item.update(validated_tree=tree, validated_ci=hashlib.sha256(ci.read_bytes()).hexdigest(),
                    validated_integration_base=item['integration_base'],
                    validation_receipt=result['receipt'], additional_test_receipts=additional)
        self.save()

    def reconcile(self):
        self.identity()
        if not self.state['active']:
            return {'status': 'idle'}
        item, repo = self.item()
        self.bump(item, 'reconciliations')
        self.inspect(repo, item['branch'])
        pr = self.query_pr(item)
        done = self.terminal(item, pr, repo)
        if done:
            return done
        update = self.integrate(item, repo)
        if update:
            return update
        result = self.summary(item, repo, 'checks_failed' if pr and self.failing(pr) else
                              ('draft' if pr and pr['isDraft'] else 'resumable'))
        return result

    def verify_server_gate(self):
        """Read-only, fail-closed proof of an app-bound gate with no admin/actor bypass.

        Classic protection OR active repository rulesets must enforce PRs, strict
        exact-app checks, no force-push and no deletion. Legacy any-app contexts,
        inaccessible policies, missing fields and bypass actors are insufficient.
        """
        prefix = 'repos/' + REPOSITORY
        result = self.gh('api', prefix + '/branches/main/protection', check=False)
        if result['exit_code'] == 0:
            data = json.loads(result['stdout'])
            checks = data.get('required_status_checks') or {}
            reviews = data.get('required_pull_request_reviews')
            bypass = (reviews or {}).get('bypass_pull_request_allowances') or {}
            exact = any(c.get('context') == GATE_NAME and c.get('app_id') == GATE_APP_ID
                        for c in checks.get('checks', []))
            if (exact and checks.get('strict') is True and isinstance(reviews, dict) and
                    type(reviews.get('required_approving_review_count')) is int and not any(bypass.values()) and data.get('enforce_admins', {}).get('enabled') is True and
                    data.get('allow_force_pushes', {}).get('enabled') is False and
                    data.get('allow_deletions', {}).get('enabled') is False):
                return
        result = self.gh('api', prefix + '/rules/branches/main', check=False)
        require(result['exit_code'] == 0, 'server_gate_policy_unreadable')
        rules = json.loads(result['stdout'])
        require(isinstance(rules, list), 'invalid_effective_rules')
        accepted, seen, exact = set(), {}, False
        for rule in rules:
            rid = rule.get('ruleset_id')
            require(type(rid) is int and rid > 0, 'unidentified_effective_ruleset')
            if rid not in seen:
                detail = json.loads(self.gh('api', prefix + '/rulesets/' + str(rid))['stdout'])
                seen[rid] = (detail.get('enforcement') == 'active' and detail.get('target') == 'branch'
                             and detail.get('bypass_actors') == [])
            if not seen[rid]:
                continue
            accepted.add(rule['type'])
            parameters = rule.get('parameters') or {}
            if rule['type'] == 'required_status_checks' and parameters.get('strict_required_status_checks_policy') is True:
                exact = exact or any(c.get('context') == GATE_NAME and c.get('integration_id') == GATE_APP_ID
                                    for c in parameters.get('required_status_checks', []))
        require(exact and {'pull_request', 'non_fast_forward', 'deletion'} <= accepted,
                'server_gate_not_enforced; require exact Skills gate/GitHub Actions, strict PR policy, no bypass')

    def review_required(self, item, repo):
        # Mechanical scope is not semantic review. Changes to existing test evidence
        # remain Draft; ordinary new tests and skill changes may use server gates.
        rows = self.paths(repo, 'diff', '--name-status', '-z', '--no-renames', item['integration_base'], 'HEAD')
        for status_code, path in zip(rows[::2], rows[1::2]):
            name = PurePosixPath(path).name
            if status_code == 'T' or (status_code != 'A' and
                    (path.startswith('tests/') or name.startswith(('test_', 'test-')))):
                return 'existing_test_evidence_or_type_change_requires_human_review'
        return None

    def checkpoint(self):
        return self.finish(checkpoint=True)

    def finish(self, checkpoint=False):
        self.identity()
        item, repo = self.item()
        self.bump(item, 'finish_attempts')
        self.inspect(repo, item['branch'])
        pr = self.query_pr(item)  # Read BEFORE any retry/mutation.
        done = self.terminal(item, pr, repo)
        if done:
            return done
        self.scope(item, repo)
        update = None if checkpoint else self.integrate(item, repo)
        if update:
            return update
        changed = self.scope(item, repo)
        require(changed, 'no_scoped_change')
        # Includes legitimate new tests. No blanket add, even inside an owned clone.
        # Already-staged deletions have no index path left for `git add` to match.
        pending = set(self.paths(repo, 'diff', '--name-only', '-z', '--no-renames'))
        pending.update(self.paths(repo, 'ls-files', '--others', '--exclude-standard', '-z'))
        if pending:
            self.git(repo, '--literal-pathspecs', 'add', '--', *sorted(pending))
        tree = self.text(repo, 'write-tree')
        require(item['plan_hash'] == self.plan_hash(item), 'plan_hash_changed')
        ci_hash = hashlib.sha256(Path(__file__).resolve().with_name('ci.py').read_bytes()).hexdigest()
        if (item.get('validated_tree') != tree or item.get('validated_ci') != ci_hash
                or item.get('validated_integration_base') != item['integration_base']):
            self.snapshot_check(item, repo, tree)
        require(self.text(repo, 'write-tree') == tree, 'index_changed_during_validation')
        require(not self.text(repo, 'diff', '--name-only') and
                not self.text(repo, 'ls-files', '--others', '--exclude-standard'), 'worktree_changed_during_validation')
        if tree != self.text(repo, 'rev-parse', 'HEAD^{tree}'):
            self.bump(item, 'commit_attempts')
            self.git(repo, 'commit', '-m', item['title'], '-m', self.marker(item))
        head = self.text(repo, 'rev-parse', 'HEAD')
        item['head'] = head
        item['counters']['commits'] = int(self.text(repo, 'rev-list', '--count', item['integration_base'] + '..HEAD'))
        self.save()
        if checkpoint:
            return self.summary(item, repo, 'checkpointed_locally')
        remote = self.remote_sha(repo, item['branch'])
        if remote and remote != head:
            self.git(repo, 'fetch', '--no-tags', 'origin', 'refs/heads/' + item['branch'])
            require(self.git(repo, 'merge-base', '--is-ancestor', remote, head, check=False)['returncode'] == 0,
                    'remote_divergence_preserved')
        if remote != head:
            pr = self.query_pr(item)
            done = self.terminal(item, pr, repo)
            if done:
                return done
            # Never publish an appended, not-yet-reviewed snapshot into a ready
            # auto-merging PR. Both ambiguous demotions must be confirmed first.
            if pr and pr.get('autoMergeRequest'):
                self.bump(item, 'disable_auto_attempts')
                self.gh('pr', 'merge', str(pr['number']), '--repo', REPOSITORY, '--disable-auto', check=False)
                pr = self.query_pr(item)
                require(pr and pr['state'] == 'OPEN' and not pr.get('autoMergeRequest'), 'disable_auto_unconfirmed')
            if pr and not pr['isDraft']:
                self.bump(item, 'draft_attempts')
                self.gh('pr', 'ready', str(pr['number']), '--repo', REPOSITORY, '--undo', check=False)
                pr = self.query_pr(item)
                require(pr and pr['state'] == 'OPEN' and pr['isDraft'], 'draft_unconfirmed')
            self.bump(item, 'push_attempts')
            pushed = self.git(repo, 'push', 'origin', 'HEAD:refs/heads/' + item['branch'], check=False)
            require(self.remote_sha(repo, item['branch']) == head,
                    'push_unconfirmed; receipt=' + pushed['receipt'])
        pr = self.query_pr(item)
        if not pr:
            self.bump(item, 'pr_create_attempts')
            body = self.marker(item) + '\n\n' + item['acceptance'] + '\n\nLocal exact-snapshot checks passed. Server checks/reviews remain required.'
            result = self.gh('pr', 'create', '--repo', REPOSITORY, '--head', item['branch'], '--base', 'main',
                             '--draft', '--title', item['title'], '--body', body, check=False)
            pr = self.query_pr(item)  # Ambiguous write: query, never blind retry in this turn.
            require(pr is not None, 'pr_creation_unconfirmed; receipt=' + result['receipt'])
        done = self.terminal(item, pr, repo)
        if done:
            return done
        require(pr['headRefOid'] == head, 'pr_head_not_confirmed')
        review = self.review_required(item, repo)
        if review:
            item['phase'] = 'review_required'
            self.save()
            return {**self.summary(item, repo, 'review_required'), 'reason': review}
        if self.failing(pr):
            item['phase'] = 'checks_failed'
            self.save()
            return self.summary(item, repo, 'checks_failed')
        self.bump(item, 'server_gate_checks')
        try:
            self.verify_server_gate()
        except Refused:
            item['phase'] = 'server_gate_unverified'
            self.save()
            if pr.get('autoMergeRequest'):
                self.bump(item, 'disable_auto_attempts')
                self.gh('pr', 'merge', str(pr['number']), '--repo', REPOSITORY, '--disable-auto', check=False)
                pr = self.query_pr(item)
                require(pr and pr['state'] == 'OPEN' and not pr.get('autoMergeRequest'), 'disable_auto_unconfirmed')
            if not pr['isDraft']:
                self.gh('pr', 'ready', str(pr['number']), '--repo', REPOSITORY, '--undo', check=False)
                pr = self.query_pr(item)
                require(pr and pr['state'] == 'OPEN' and pr['isDraft'], 'draft_unconfirmed')
            raise
        if pr['isDraft']:
            self.bump(item, 'ready_attempts')
            self.gh('pr', 'ready', str(pr['number']), '--repo', REPOSITORY, check=False)
            pr = self.query_pr(item)
            require(pr and not pr['isDraft'], 'ready_unconfirmed')
        if not pr.get('autoMergeRequest'):
            self.verify_server_gate()  # Re-read immediately before requesting native auto-merge.
            self.bump(item, 'auto_merge_attempts')
            self.gh('pr', 'merge', str(pr['number']), '--repo', REPOSITORY, '--auto', '--squash',
                    '--match-head-commit', head, check=False)
            pr = self.query_pr(item)
            require(pr and (pr.get('autoMergeRequest') or pr['state'] == 'MERGED'), 'native_auto_merge_unconfirmed')
        done = self.terminal(item, pr, repo)
        if done:
            return done
        item['phase'] = 'auto_merge_enabled'
        self.save()
        return self.summary(item, repo, item['phase'])

    def status(self):
        if self.state['active']:
            item, repo = self.item()
            self.inspect(repo, item['branch'])
            return self.summary(item, repo, item['phase'])
        return {'status': 'idle', 'completed': {k: v['phase'] for k, v in self.state['items'].items()}}

    def guard(self, args):
        argv = [sys.executable, str(self.control / 'devctl.py'), '--git-dir', str(self.root / '.git'), *args]
        result = self.invoke(argv, timeout=None, check=False, kind='devctl-transport')
        try:
            payload = json.loads(result['stdout'])
            require(isinstance(payload, dict), 'invalid_guard_receipt')
        except (ValueError, Refused):
            raise Refused('invalid_guard_receipt; transport=' + result['receipt'])
        path = self.receipt('devctl-result', payload)  # Full structured receipt BEFORE any short output/state.
        require(type(payload.get('exit_code')) is int, 'invalid_guard_receipt; receipt=' + path)
        code = result['exit_code'] or payload['exit_code']
        if result.get('stdout_truncated') or result.get('stderr_truncated'):
            code = code or 73
        if args[:1] == ['run'] and (payload.get('writer_finished') is not True
                or payload.get('outputs_complete') is not True
                or payload.get('stdout_truncated') is not False
                or payload.get('stderr_truncated') is not False):
            code = code or 73
        return payload, path, code

    @staticmethod
    def worker_result(payload, receipt, code):
        # A guard exit alone is not evidence of a complete controller response.
        try:
            require(not payload.get('stdout_truncated'), 'invalid_worker_receipt')
            inner = json.loads(payload.get('stdout', ''))
            require(isinstance(inner, dict) and type(inner.get('exit_code')) is int,
                    'invalid_worker_receipt')
        except (ValueError, TypeError, Refused):
            return {'status': 'refused', 'reason': payload.get('reason') or 'invalid_worker_receipt',
                    'receipt': receipt, 'exit_code': code or 73}
        summary = {**inner, 'receipt': receipt, 'exit_code': code or inner['exit_code']}
        if code:
            summary.update(status='refused', reason=payload.get('reason') or 'guard_operation_failed')
        return summary

    def dispatch(self, args, argv):
        label(args.run_id)
        runpath = self.data / 'runs' / (args.run_id + '.json')
        if args.action == 'start' and not runpath.exists():
            # Recover the narrow crash window after durable begin receipt but
            # before its run index. Ownership is revalidated, never inferred.
            acquired = []
            for path in self.receipts.glob('devctl-result-*.json'):
                old = load(path)
                if old.get('run') == args.run_id and old.get('status') == 'acquired' and old.get('owner_file'):
                    acquired.append((old, str(path)))
            require(len(acquired) <= 1, 'ambiguous_begin_receipts')
            if acquired:
                old, begin_receipt = acquired[0]
                payload, receipt, code = self.guard(['run', '--owner', old['owner_file'], '--timeout', str(args.timeout),
                    '--', sys.executable, str(Path(__file__).resolve()), '_worker', *argv])
                result = self.worker_result(payload, receipt, code)
                code = result['exit_code']
                if not code:
                    atomic(runpath, {'owner': old['owner_file'], 'begin_receipt': begin_receipt, 'ended': False})
                return {'status': 'recovered_start' if not code else 'ownership_not_valid',
                        'run_id': args.run_id, 'receipt': receipt, 'exit_code': code}
            payload, receipt, code = self.guard(['begin', '--job', 'skills-pr', '--run', args.run_id])
            if code:
                return {'status': payload.get('status'), 'receipt': receipt, 'exit_code': code}
            atomic(runpath, {'owner': payload['owner_file'], 'begin_receipt': receipt, 'ended': False})
            return {'status': 'started', 'run_id': args.run_id, 'receipt': receipt}
        require(runpath.exists(), 'run_not_started')
        run = load(runpath)
        require(not run['ended'], 'run_already_ended; use_new_run_id')
        if args.action == 'end':
            payload, receipt, code = self.guard(['end', '--owner', run['owner']])
            if not code:
                run['ended'] = True
                atomic(runpath, run)
            return {'status': payload.get('status'), 'receipt': receipt, 'exit_code': code}
        payload, receipt, code = self.guard(['run', '--owner', run['owner'], '--timeout', str(args.timeout),
                                            '--', sys.executable, str(Path(__file__).resolve()), '_worker', *argv])
        return self.worker_result(payload, receipt, code)


def parser():
    p = argparse.ArgumentParser(description=__doc__, epilog='No credentials or owner tokens in arguments/output. '
        'Run IDs identify one guard lease, not an item. After end/expiry use a NEW run ID; prepare resumes the active item. '
        'A dirty advanced-base clone returns needs_update; use checkpoint then reconcile for a non-rewriting merge. '
        'Readiness/auto-merge require a verified strict Skills gate from GitHub Actions (app 15368), enforced without bypass. '
        'Existing test-evidence edits stay Draft for human review; new-skill/policy maintenance is not automatic. '
        'Failed/unknown clone directories are preserved, never adopted or deleted.')
    sub = p.add_subparsers(dest='action', required=True)
    helptexts = {'start': 'Acquire unchanged devctl lease; same valid run is idempotent.',
                 'prepare': 'Resume active item first; otherwise fetch isolated seed and snapshot latest audit.',
                 'create': 'Select one existing skill; persist immutable explicit plan and create isolated auto/<id> clone.',
                 'run': 'Execute a cooperative foreground argv in the owned clone; no shell/background front door.',
                 'finish': 'Scope/stage exact paths, validate exact snapshot, commit, push, Draft PR, native auto-merge.',
                 'checkpoint': 'Validate and commit scoped edits locally only; makes dirty advanced-base work resumable.',
                 'reconcile': 'Reconcile remote PR/checks; clean owned branches may merge advancing main without rewriting.',
                 'status': 'Read active owned item and persistent counters (still requires valid lease).',
                 'end': 'Release this run only; keep item clone/state/receipts for the next run.'}
    for action, text in helptexts.items():
        q = sub.add_parser(action, help=text, description=text)
        q.add_argument('--run-id', required=True, help='lowercase kebab label, at most 64 characters')
        q.add_argument('--timeout', type=int, default=600, help='outer guard timeout, 1..600 seconds (default 600)')
        if action == 'create':
            for key, helptext in {
                    'id': 'unique stable kebab item ID; becomes auto/<id>; never reuse a completed ID',
                    'title': 'immutable commit and PR title',
                    'skill': 'exact existing skill directory basename; determines the explicit path allowlist',
                    'acceptance': 'immutable, testable acceptance criteria recorded in the plan and PR'}.items():
                q.add_argument('--' + key, required=True, help=helptext)
        if action == 'run':
            q.add_argument('--foreground', action='store_true', help='attest command/descendants never detach or leave owned scope')
            q.add_argument('command', nargs=argparse.REMAINDER, help='-- executable args; stdin remains available')
    return p


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    worker = argv[:1] == ['_worker']
    if worker:
        argv.pop(0)
    args = parser().parse_args(argv)
    try:
        require(1 <= args.timeout <= 600, 'timeout_out_of_range')
        c = Controller()
        if worker:
            fds = inherited_fd()
            require(bool(fds), 'guard_required')
            actual = os.fstat(fds[0])
            expected = (c.control / 'lease-guard/mutex.lock').stat()
            require((actual.st_dev, actual.st_ino) == (expected.st_dev, expected.st_ino), 'wrong_guard_fd')
            if args.action == 'start':
                result = {'status': 'already_started', 'run_id': args.run_id}
            elif args.action in ('create', 'run'):
                result = getattr(c, args.action)(args)
            else:
                require(args.action != 'end', 'invalid_worker_action')
                result = getattr(c, args.action)()
        else:
            fd = os.open(c.data / 'dispatch.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, 'r+'):
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    raise Refused('another_controller_dispatch_active')
                result = c.dispatch(args, argv)
        code = result.get('exit_code', 0)
    except Refused as exc:
        result, code = {'status': 'refused', 'reason': exc.reason, 'exit_code': exc.code}, exc.code
    except (OSError, ValueError, KeyError, TypeError):
        result, code = {'status': 'refused', 'reason': 'io_or_metadata_error_preserved', 'exit_code': 73}, 73
    result['exit_code'] = code  # Worker JSON always carries its actual application exit.
    print(json.dumps(redact(result), ensure_ascii=False, sort_keys=True), flush=True)
    return code


if __name__ == '__main__':
    sys.exit(main())
