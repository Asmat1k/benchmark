import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from raw import digest, read, rows, validate_raw, write
from record import complete
from test_measurement import fixture, rehash, pending_publication
from violation import diagnose


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        Path("build").mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir="build")
        self.directory = Path(self.temp.name).resolve()
        fixture(self.directory)
        self.folder = self.directory / "raw/b0-a0-m0"

    def tearDown(self):
        self.temp.cleanup()

    def tree(self):
        return {str(p.relative_to(self.directory)):digest(p) for p in self.directory.rglob("*") if p.is_file()}

    def defect(self):
        snapshot = read(self.folder / "network_after.json")
        snapshot["forwarding"] = 0
        write(self.folder / "network_after.json", snapshot)
        rehash(self.folder)
        evidence = self.directory / "proof.json"
        self.assertTrue(diagnose(self.folder,self.directory/"schedule.json",evidence))
        return evidence

    def cli(self, directory, evidence, attempt="b0-a0", reason="path"):
        return subprocess.run([sys.executable,"-B","src/analysis/replace.py",str(directory),attempt,reason,str(evidence)],capture_output=True,text=True)

    def cleanup(self, partial, code):
        script = '''set -eu
series_dir=$1; run_dir=$2; project=collector; index=0; stage=publication; prepared=1; lock_pid=""
work="$series_dir/work"; mkdir "$work"
compose() { return 0; }
analyze() { "$3" -B "$@"; }
'''
        script = script.replace('analyze() { "$3" -B "$@"; }', 'analyze() { '+__import__('shlex').quote(sys.executable)+' -B "$@"; }')
        script += '. docker/lib/measurement-cleanup.sh\ntrap cleanup EXIT\nexit "$3"\n'
        return subprocess.run(["sh","-c",script,"cleanup",str(self.directory),str(partial),str(code)],capture_output=True,text=True)

    def test_actual_cleanup_exit3_then_relative_cli(self):
        partial=self.directory/"collector.partial"
        self.folder.rename(partial)
        (partial/"SHA256SUMS").unlink()
        pending_publication(self.directory, partial)
        write(partial/"page.json",dict(slots=rows(partial/"warmup.jsonl")+rows(partial/"slots.jsonl"),events=rows(partial/"events.jsonl")))
        for when in ("before","after"):
            snapshot=read(partial/f"network_{when}.json")
            for role in ("browser","server"):
                (partial/f"{role}-route-{when}.txt").write_text(snapshot[role])
                (partial/f"{role}-settings-{when}.txt").write_text(snapshot["endpoints"][role])
            (partial/f"router-links-{when}.txt").write_text(snapshot["links"])
        (partial/"forward-after").write_text("0")
        with self.assertRaises(SystemExit) as failure: complete(self.directory,0,partial)
        self.assertEqual(failure.exception.code,3)
        before={p.name:digest(p) for p in partial.iterdir()}
        result=self.cleanup(partial,3)
        self.assertEqual(result.returncode,3,result.stderr)
        quarantine=self.directory/"quarantine/collector"
        self.assertEqual(before,{p.name:digest(p) for p in quarantine.iterdir()})
        evidence=self.directory/"violations/b0-a0-m0.json"
        result=self.cli(Path(os.path.relpath(self.directory)),Path(os.path.relpath(evidence)))
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertFalse((self.directory/"STOP").exists())
        self.assertFalse((self.directory/"PENDING_REPLACEMENT").exists())
        self.assertEqual(len(list((self.directory/"audit/b0-a0").glob("*-m*"))),2)

    def test_complete_clock_violation_keeps_replacement_route(self):
        slots=rows(self.folder/"slots.jsonl")
        slots[0]["t_send_ms"]=slots[0]["t_plan_ms"]-1
        (self.folder/"slots.jsonl").write_text("".join(json.dumps(s)+"\n" for s in slots))
        rehash(self.folder)
        evidence=self.directory/"clock.json"
        self.assertTrue(diagnose(self.folder,self.directory/"schedule.json",evidence))
        self.assertEqual(read(evidence)["reason"],"clock")
        self.assertFalse((self.directory/"STOP").exists())
        result=self.cli(os.path.relpath(self.directory),evidence,reason="clock")
        self.assertEqual(result.returncode,0,result.stderr)

    def test_foreign_identity_refused_before_mutation(self):
        evidence=self.defect()
        proof=read(evidence)
        proof.update(run_id="b1-a0-m0",attempt_id="b1-a0")
        proof["identity"].update(run_id="b1-a0-m0",attempt_id="b1-a0",block_id="b1")
        write(evidence,proof)
        before=self.tree()
        result=self.cli(os.path.relpath(self.directory),evidence,"b1-a0")
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(before,self.tree())
        self.assertFalse((self.directory/"audit").exists())

    def test_missing_journal_and_expiry_take_actual_stop_cleanup(self):
        for name in ("checks.json","network_before.json","context.json"):
            path=self.folder/name; saved=path.read_bytes(); path.unlink()
            self.assertFalse(diagnose(self.folder,self.directory/"schedule.json",self.directory/"bad.json"))
            self.assertTrue((self.directory/"STOP").exists())
            (self.directory/"STOP").unlink()
            path.write_bytes(saved)
        manifest=read(self.folder/"manifest.json"); manifest["ended_utc"]="2040-01-01T00:00:00Z"
        write(self.folder/"manifest.json",manifest); rehash(self.folder)
        self.assertFalse(diagnose(self.folder,self.directory/"schedule.json",self.directory/"expired.json"))
        self.assertTrue((self.directory/"STOP").exists())
        partial=self.directory/"collector.partial"; self.folder.rename(partial)
        result=self.cleanup(partial,1)
        self.assertEqual(result.returncode,1,result.stderr)
        self.assertTrue((self.directory/"STOP").exists())
        self.assertEqual(read(self.directory/"ledger.json")["attempts"][0]["status"],"stopped")

    def test_published_environment_provenance_conflicts(self):
        for filename, mutate in (
            ("environment.json",lambda v:v["vm"].update(cpus=123)),
            ("environment.json",lambda v:v["limits"][0].update(cpu=1)),
            ("provenance.json",lambda v:v["images"][0].update(id="foreign-image")),
            ("provenance.json",lambda v:v["lock_hashes"].clear())):
            original=(self.folder/filename).read_bytes()
            value=read(self.folder/filename); mutate(value); write(self.folder/filename,value); rehash(self.folder)
            with self.assertRaisesRegex(ValueError,"publication mismatch"):
                validate_raw(self.folder,self.directory/"schedule.json")
            (self.folder/filename).write_bytes(original); rehash(self.folder)

    def test_hard_exit_releases_lock_and_symlink_cli_recovers(self):
        evidence=self.defect()
        code='''import os,sys
sys.path.insert(0,"src/analysis")
from pathlib import Path
from replace import replace
def crash(stage):
    if stage=="move-0": os._exit(91)
replace(Path(sys.argv[1]),"b0-a0","path",Path(sys.argv[2]),crash)
'''
        process=subprocess.run([sys.executable,"-B","-c",code,str(self.directory),str(evidence)],capture_output=True,text=True)
        self.assertEqual(process.returncode,91,process.stderr)
        self.assertTrue((self.directory/"replacement.json").exists())
        alias=self.directory.parent/(self.directory.name+"-alias")
        alias.symlink_to(self.directory,target_is_directory=True)
        try:
            result=self.cli(os.path.relpath(alias),os.path.relpath(alias/"proof.json"))
            self.assertEqual(result.returncode,0,result.stderr)
        finally:
            alias.unlink()
        self.assertEqual(sum(a["replacement_of"]=="b0-a0" for a in read(self.directory/"ledger.json")["attempts"]),1)
        self.assertEqual(len(list((self.directory/"audit/b0-a0").glob("*-m*"))),2)

    def test_live_owner_blocks_actual_cli(self):
        evidence=self.defect()
        code='''import sys
sys.path.insert(0,"src/analysis")
from series import measurement_lock
with measurement_lock():
 print("held",flush=True)
 sys.stdin.read()
'''
        process=subprocess.Popen([sys.executable,"-B","-c",code],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
        try:
            self.assertEqual(process.stdout.readline().strip(),"held")
            result=self.cli(os.path.relpath(self.directory),evidence)
            self.assertNotEqual(result.returncode,0)
            self.assertFalse((self.directory/"audit").exists())
        finally:
            process.kill(); process.wait(); process.stdin.close(); process.stdout.close()
        result=self.cli(os.path.relpath(self.directory),evidence)
        self.assertEqual(result.returncode,0,result.stderr)


if __name__ == "__main__": unittest.main()
