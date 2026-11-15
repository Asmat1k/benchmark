import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


@unittest.skipUnless(shutil.which('git'),'host Git test')
class ReleaseGuardTests(unittest.TestCase):
    def test_actual_host_guard_before_stub_network(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            base=root/'base';base.mkdir()
            (base/'docker/lib').mkdir(parents=True);shutil.copyfile('docker/lib/check-release.sh',base/'docker/lib/check-release.sh')
            (base/'src').mkdir();(base/'src/app.py').write_text('original\n')
            (base/'README.md').write_text('original docs\n')
            def git(directory,*args):
                return subprocess.check_output(['git',*args],cwd=directory,text=True,stderr=subprocess.DEVNULL).strip()
            git(base,'init');git(base,'add','docker','src','README.md')
            git(base,'-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-m','Create fixture release')
            expected=git(base,'rev-parse','HEAD')
            for case in ('unchanged','docs-commit','dirty-source','untracked-source'):
                directory=root/case;shutil.copytree(base,directory)
                (directory/'results/main/generated').mkdir(parents=True)
                (directory/'.agents/plan').mkdir(parents=True)
                if case=='docs-commit':
                    (directory/'README.md').write_text('new docs\n');git(directory,'add','README.md')
                    git(directory,'-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-m','Update fixture documentation')
                elif case=='dirty-source':(directory/'src/app.py').write_text('modified\n')
                elif case=='untracked-source':(directory/'src/new.py').write_text('new executable\n')
                script='set -e\nsh docker/lib/check-release.sh "$EXPECTED_COMMIT"\nprintf network > "$NETWORK_MARKER"\n'
                marker=directory/'network-started'
                result=subprocess.run(['/bin/sh','-c',script],cwd=directory,env=dict(os.environ,EXPECTED_COMMIT=expected,NETWORK_MARKER=str(marker)),capture_output=True,text=True)
                self.assertEqual(result.returncode==0,case=='unchanged',case+result.stderr)
                self.assertEqual(marker.exists(),case=='unchanged',case)
                print(case,result.returncode,'network',marker.exists())

    def test_actual_measure_shell_stops_before_network_on_release_change(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);base=root/'base';base.mkdir()
            for name in ('commands/measure.sh','lib/measurement-cleanup.sh','lib/check-release.sh'):
                target=base/'docker'/name
                target.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(Path('docker')/name,target)
            (base/'docker/lib/controller-client.sh').write_text("controller_request() { printf 'baseline 1 2 b0-a0-m0 90\\n'; }\n")
            (base/'src').mkdir();(base/'src/app.py').write_text('original\n')
            (base/'README.md').write_text('docs\n')
            binaries=root/'bin';binaries.mkdir()
            docker=binaries/'docker'
            docker.write_text('#!/bin/sh\ncase "$*" in\n*"execution.series hold"*) echo locked; cat >/dev/null ;;\n*" up -d "*) case "$BENCH_TLS_DIR" in /*) touch "$NETWORK_MARKER"; exit 99 ;; *) exit 88 ;; esac ;;\n*"info --format"*) echo "{}" ;;\n*) exit 0 ;;\nesac\n')
            docker.chmod(0o755)
            tls=root/'tls/server/good';tls.mkdir(parents=True);(tls/'cert.pem').write_text('offline fixture')
            def git(directory,*args):
                return subprocess.check_output(['git',*args],cwd=directory,text=True,stderr=subprocess.DEVNULL).strip()
            git(base,'init');git(base,'add','docker','src','README.md')
            git(base,'-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-m','Create fixture release')
            expected=git(base,'rev-parse','HEAD')
            for case in ('unchanged','docs-commit','dirty-source','untracked-source'):
                directory=root/case;shutil.copytree(base,directory)
                shutil.copytree(root/'tls',directory/'tls')
                series=directory/'results/verify/raw/fixture';series.mkdir(parents=True);(series/'schedule.json').write_text('{}')
                (directory/'.agents/plan').mkdir(parents=True)
                if case=='docs-commit':
                    (directory/'README.md').write_text('new docs\n');git(directory,'add','README.md')
                    git(directory,'-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-m','Update fixture documentation')
                elif case=='dirty-source':(directory/'src/app.py').write_text('modified\n')
                elif case=='untracked-source':(directory/'src/new.py').write_text('new\n')
                marker=directory/'network-started'
                result=subprocess.run(['/bin/sh','docker/commands/measure.sh','results/verify/raw/fixture','0'],cwd=directory,
                    env=dict(os.environ,PATH=str(binaries)+':'+os.environ['PATH'],NETWORK_MARKER=str(marker),SERIES_TLS_DIR='tls',BENCH_CONTROLLER_RESPONSE='offline-stub',BENCH_CONTROLLER_COMMIT=expected),capture_output=True,text=True,timeout=30)
                self.assertEqual(result.returncode,99 if case=='unchanged' else 2,case+result.stdout+result.stderr)
                self.assertEqual(marker.exists(),case=='unchanged',case)
                print('measure',case,result.returncode,'network',marker.exists())
