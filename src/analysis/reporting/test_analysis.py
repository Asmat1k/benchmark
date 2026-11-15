import copy
import csv
import itertools
import json
import math
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
from jsonschema import ValidationError

from reporting.analyze import AUDIT_FIELDS, analyze, compute, json_numbers, validate_series
from reporting.inference import bootstrap, decisions, holm4, nearest_rank, rank_interval, sign_test
from measurement.metrics import run_metrics
from measurement.raw import digest, read, rows, validate_raw, write
from reporting.synthetic import make_fixture, rehash
from execution.replace import replace
from execution.violation import diagnose
from execution.schedule import make_schedule

REFERENCE = read(Path(__file__).resolve().parents[1]/"tests/fixtures/references.json")
THRESHOLDS = read(Path("configs/thresholds.json"))


class StatisticalTests(unittest.TestCase):
    def test_all_prespecified_references(self):
        for case in REFERENCE["sign"]:
            result = sign_test(case["values"])
            self.assertEqual(result["n"],len(case["values"]))
            self.assertEqual(result["Nzero"],case["values"].count(0))
            self.assertAlmostEqual(result["p_raw"],case["p"],delta=1e-10)
        np.testing.assert_allclose(holm4(REFERENCE["holm_input"]),REFERENCE["holm_output"],atol=1e-10,rtol=0)
        self.assertEqual(holm4([.01,.01,.01,.01]),[.04]*4)
        self.assertEqual(rank_interval([0]*20)["bounds"],[0,0])
        self.assertEqual(rank_interval(list(range(1,21)))["ranks"],[6,15])
        self.assertEqual(rank_interval(list(range(1,21)),.0125)["ranks"],[5,16])
        self.assertEqual(rank_interval([1,2,3,4,5])["bounds"],[-math.inf,math.inf])
        self.assertEqual(nearest_rank([1,2,3,4],.5),2)
        self.assertEqual(nearest_rank([1,2,3,4],.95),4)

    def test_exact_sign_enumeration_and_rank_coverage(self):
        for n in range(1,11):
            p_values = []
            for signs in itertools.product((-1,1),repeat=n):
                positive = signs.count(1)
                exact = min(1,2*min(sum(math.comb(n,k) for k in range(positive,n+1)),
                                    sum(math.comb(n,k) for k in range(n-positive,n+1)))/2**n)
                actual = sign_test(signs)["p_raw"]
                self.assertEqual(actual,exact)
                p_values.append(actual)
            for alpha in (.05,.0125):
                self.assertLessEqual(sum(p < alpha for p in p_values)/2**n,alpha)
                ci = rank_interval(list(range(n)),alpha)
                k = ci["ranks"][0]
                exact_coverage = sum(math.comb(n,j) for j in range(k,n-k+1))/2**n
                self.assertEqual(ci["binomial_coverage"],exact_coverage)
                self.assertGreaterEqual(exact_coverage,1-alpha)
        for n in range(1,7):
            for signs in itertools.product((-1,0,1),repeat=n):
                result = sign_test(signs)
                exact = min(1,2*min(sum(math.comb(n,k) for k in range(signs.count(1),n+1)),
                                    sum(math.comb(n,k) for k in range(signs.count(-1),n+1)))/2**n)
                self.assertEqual(result["p_raw"],exact)

    def test_bootstrap_preserves_blocks_and_replay(self):
        rng = np.random.Generator(np.random.PCG64(20261108))
        indices = rng.integers(0,20,size=(10000,20))
        result = bootstrap([-.5]*20,indices)
        self.assertEqual(result["estimate"],-.5)
        self.assertEqual(result["bounds"],[-.5,-.5])
        varying = np.linspace(-2,3,20)
        expected = np.quantile(np.mean(varying[indices],axis=1),[.00625,.99375],method="linear")
        np.testing.assert_allclose(bootstrap(varying,indices)["bounds"],expected,atol=1e-10,rtol=0)
        fixture = REFERENCE["block_bootstrap"]
        blocks = fixture["block_delta_S_pp"]
        indices = np.array(list(itertools.product(range(4),repeat=4)))
        correct = bootstrap(blocks,indices,.95)
        self.assertEqual(correct["estimate"],50)
        self.assertEqual(correct["bounds"],[0,100])
        messages = np.repeat(blocks,fixture["wrong_message_repeats"])
        wrong = np.mean(rng.choice(messages,size=(1000,len(messages))),axis=1)
        low,high = np.quantile(wrong,[.025,.975])
        self.assertLess(high-low,10)
        self.assertGreater(correct["bounds"][1]-correct["bounds"][0],high-low)
        with self.assertRaises(ValueError): bootstrap(blocks,np.array([[0,1,2,4]]))

    def test_decision_thresholds_and_barriers(self):
        decide = lambda ci,fullness,complete=True,p=.01: decisions(ci,fullness,p,True,complete,THRESHOLDS)
        self.assertEqual(decide([-10,-6],[-1,0])["useful_gain"],"WT-S")
        self.assertEqual(decide([6,10],[0,1])["useful_gain"],"WS")
        for ci in ([-6,-5],[5,6],[-math.inf,math.inf]):
            self.assertEqual(decide(ci,[-1,1])["practical_decision"],"uncertain")
        self.assertEqual(decide([-5,5],[-1,1])["practical_decision"],"small_difference")
        self.assertIsNone(decide([-10,-6],[-1.01,0])["useful_gain"])
        self.assertEqual(decide([-10,-6],[-1,0],False)["conclusion_status"],"limited")
        self.assertIsNone(decide([-10,-6],[-1,0],p=.05)["useful_gain"])

    def test_metrics_deadlines_penalty_and_diagnostics(self):
        def slot(i,offset):
            return dict(t_plan_ms=i*50,t_send_ms=i*50+1,first_correct_echo_ms=None if offset is None else i*50+offset,
                        send_state="sent",send_lag_ms=1,queue_before_bytes=0)
        slots = [slot(0,100),slot(1,5000),slot(2,5000.1),slot(3,None)]
        events = [dict(type=t,id=dict(phase=1)) for t in ("duplicate","invalid_frame","unknown_ID","framing_error")]
        m,rtts = run_metrics(slots,events,[],100,5000)
        self.assertEqual((m["completed"],m["timely"],m["late_within"],m["uncompleted"]),(2,1,1,2))
        self.assertEqual(rtts,[99,4999])
        self.assertEqual((m["duplicates"],m["invalid"],m["framing_errors"]),(1,2,1))
        for finite in (1139,1140):
            m,_ = run_metrics([slot(i,2 if i < finite else None) for i in range(1200)],[],[],100,5000)
            self.assertEqual(m["penalized_p95_ms"],math.inf if finite == 1139 else 1)
        m,_ = run_metrics([slot(i,None) for i in range(1200)],[],[],100,5000)
        self.assertIsNone(m["Q_ms"])
        self.assertEqual((m["S_pct"],m["U_pct"]),(0,100))
        self.assertEqual(json_numbers([-math.inf,math.inf,None]),["-inf","+inf",None])


class SeriesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.directory = make_fixture(Path(cls.temp.name)/"synthetic")

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def cli(self,directory):
        return subprocess.run([sys.executable,"-B",'-m',"reporting.analyze",str(directory)],capture_output=True,text=True)

    def assert_cli_rejected(self,directory,reason):
        before = {str(p.relative_to(directory)):digest(p) for p in (directory/"derived").rglob("*") if p.is_file()}
        process = self.cli(directory)
        self.assertNotEqual(process.returncode,0,process.stdout)
        self.assertIn(reason,process.stderr)
        self.assertEqual(before,{str(p.relative_to(directory)):digest(p) for p in (directory/"derived").rglob("*") if p.is_file()})

    def test_r1_swapped_and_duplicated_directory_contents_cli(self):
        schedule = read(self.directory/"schedule.json")
        first = next(r for r in schedule["runs"] if r["mode"] == "WS")
        second = next(r for r in schedule["runs"] if r["attempt_id"] == first["attempt_id"] and r["mode"] == "WT-S")
        for operation in ("swap","duplicate"):
            with self.subTest(operation=operation), tempfile.TemporaryDirectory() as tmp:
                directory = Path(tmp)/"series"; shutil.copytree(self.directory,directory)
                a,b = (directory/"raw"/r["run_id"] for r in (first,second))
                if operation == "swap":
                    a.rename(directory/"hold"); b.rename(a); (directory/"hold").rename(b)
                else:
                    shutil.rmtree(b); shutil.copytree(a,b)
                self.assert_cli_rejected(directory,"raw directory/run attribution mismatch")

    def test_r2_scheduler_miss_with_null_queue_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)/"series"; shutil.copytree(self.directory,directory)
            ws = [r for r in read(directory/"schedule.json")["runs"] if r["mode"] == "WS"]
            for run,count in zip(ws,(1,1200)):
                folder = directory/"raw"/run["run_id"]
                slots = rows(folder/"slots.jsonl")
                for slot in slots[:count]:
                    slot.update(t_send_ms=None,send_lag_ms=None,api_return_ms=None,write_fulfilled_ms=None,
                        first_correct_echo_ms=None,echo_bytes=None,queue_before_bytes=None,
                        send_state="scheduler_miss",terminal_reason="scheduler_miss",ontime=False,completed_by_horizon=False)
                events = [e for e in rows(folder/"events.jsonl") if e["id"] is None or e["id"]["phase"] == 0 or
                          int(e["id"]["seq"]) >= count or e["type"] == "phase_transition"]
                for i,e in enumerate(events): e["event_index"]=i
                for name,records in (("slots",slots),("events",events)):
                    (folder/f"{name}.jsonl").write_text("".join(json.dumps(r)+"\n" for r in records))
                server = read(folder/"server.json")
                server["measurement"] = dict(received=1200-count,invalid=0,write_attempted=1200-count,echoed=1200-count,errors=0)
                write(folder/"server.json",server)
                write(folder/"counters.json",dict(active=0,**{k:server[k] for k in ("warmup","measurement")}))
                rehash(folder)
            process = self.cli(directory)
            self.assertEqual(process.returncode,0,process.stderr)
            with (directory/"derived/runs.csv").open() as handle:
                result = {r["run_id"]:r for r in csv.DictReader(handle)}
            mixed,missed = (result[r["run_id"]] for r in ws[:2])
            self.assertEqual((mixed["scheduler_miss"],mixed["completed"],mixed["queue_observations"],mixed["max_queue_bytes"]),("1","1199","1199","0"))
            self.assertAlmostEqual(float(mixed["S_pct"]),100*1199/1200,delta=1e-10)
            self.assertAlmostEqual(float(mixed["U_pct"]),100/1200,delta=1e-10)
            self.assertEqual((missed["scheduler_miss"],missed["completed"],missed["queue_observations"],missed["max_queue_bytes"]),("1200","0","0","NA"))
            self.assertEqual((missed["Q_ms"],missed["S_pct"],missed["U_pct"],missed["penalized_p95_ms"]),("NA","0.0","100.0","inf"))

    def test_r3_truncated_series_against_signed_plan_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)/"series"; shutil.copytree(self.directory,directory)
            schedule,ledger = read(directory/"schedule.json"),read(directory/"ledger.json")
            schedule["blocks"] = schedule["blocks"][:1]
            schedule["runs"] = [r for r in schedule["runs"] if r["attempt_id"] == schedule["blocks"][0]["attempt_id"]]
            ledger["attempts"] = ledger["attempts"][:1]
            write(directory/"schedule.json",schedule); write(directory/"ledger.json",ledger)
            kept = {r["run_id"] for r in schedule["runs"]}
            for folder in (directory/"raw").iterdir():
                if folder.name not in kept: shutil.rmtree(folder)
            self.assert_cli_rejected(directory,"original schedule membership changed")

    def test_r6_smoke_cannot_enter_comparison_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            schedule = make_schedule("smoke","synthetic-smoke",1,1)
            directory = make_fixture(Path(tmp)/"smoke",schedule=schedule)
            for folder in (directory/"raw").iterdir(): validate_raw(folder,directory/"schedule.json")
            self.assert_cli_rejected(directory,"smoke is diagnostic only")

    def test_integrity_refuses_series_and_pair_mutations(self):
        directory = self.directory
        schedule = read(directory/"schedule.json")
        ledger = read(directory/"ledger.json")
        variants = []
        duplicate = copy.deepcopy(schedule); duplicate["runs"].append(duplicate["runs"][0]); variants.append(("schedule.json",duplicate))
        mismatch = copy.deepcopy(schedule); mismatch["runs"][0]["session_id"]="wrong"; variants.append(("schedule.json",mismatch))
        wrong_seed = copy.deepcopy(schedule); wrong_seed["runs"][0]["forward_seed"]+=1; variants.append(("schedule.json",wrong_seed))
        missing = copy.deepcopy(schedule); missing["runs"].pop(); variants.append(("schedule.json",missing))
        incomplete = copy.deepcopy(ledger); incomplete["attempts"][0]["status"]="planned"; variants.append(("ledger.json",incomplete))
        for filename,changed in variants:
            with self.subTest(filename=filename):
                write(directory/filename,changed)
                try:
                    with self.assertRaises((ValueError,ValidationError)): validate_series(directory)
                finally:
                    write(directory/"schedule.json",schedule); write(directory/"ledger.json",ledger)

    def test_real_raw_validation(self):
        folder = self.directory/"raw"/read(self.directory/"schedule.json")["runs"][0]["run_id"]
        path = folder/"slots.jsonl"
        original = path.read_bytes()
        try:
            path.write_bytes(original+b"\n")
            with self.assertRaisesRegex(ValueError,"hash mismatch"): validate_series(self.directory)
            path.write_bytes(original)
            events = (folder/"events.jsonl").read_bytes()
            (folder/"events.jsonl").write_text("")
            rehash(folder)
            with self.assertRaisesRegex(ValueError,"incomplete echo events"): validate_series(self.directory)
        finally:
            path.write_bytes(original)
            (folder/"events.jsonl").write_bytes(events)
            rehash(folder)

    def test_null_profiles_and_mixed_release_are_not_silently_removed(self):
        schedule = read(self.directory/"schedule.json")
        targets = [next(r for r in schedule["runs"] if r["mode"] == mode) for mode in ("WT-S","WT-D")]
        originals = {}
        try:
            for run in targets:
                folder = self.directory/"raw"/run["run_id"]
                for filename in ("slots.jsonl","events.jsonl","manifest.json"):
                    originals[folder/filename] = (folder/filename).read_bytes()
                slots = rows(folder/"slots.jsonl")
                for slot in slots:
                    slot.update(first_correct_echo_ms=None,echo_bytes=None,completed_by_horizon=False,ontime=False,terminal_reason="horizon")
                events = [e for e in rows(folder/"events.jsonl") if e["id"] is None or e["id"]["phase"] == 0 or e["type"] == "phase_transition"]
                for index,e in enumerate(events): e["event_index"] = index
                for name,records in (("slots",slots),("events",events)):
                    (folder/f"{name}.jsonl").write_text("".join(json.dumps(r)+"\n" for r in records))
                rehash(folder)
            with tempfile.TemporaryDirectory() as tmp, patch("reporting.plots.figures"):
                compute(self.directory,Path(tmp))
                report = read(Path(tmp)/"analysis.json")
                self.assertEqual(len(report["profiles"]),4)
                null_profile = next(p for p in report["profiles"] if p["profile"] == targets[0]["profile"])
                self.assertEqual(null_profile["sign"]["p_raw"],1)
                self.assertTrue(null_profile["sign"]["placeholder"])
                self.assertEqual(null_profile["statistical_decision"],"unavailable")
                self.assertEqual(null_profile["completeness_gate"],"failed")
                self.assertEqual(null_profile["n"],1)
                wt_d = next(p["WT_D"] for p in report["profiles"] if p["profile"] == targets[1]["profile"])
                self.assertIsNone(wt_d["Q"])
                self.assertEqual(wt_d["S"]["bounds"],[0,0])
            manifest = read(self.directory/"raw"/targets[0]["run_id"]/"manifest.json")
            manifest["commit"] = "a"*40
            write(self.directory/"raw"/targets[0]["run_id"]/"manifest.json",manifest)
            rehash(self.directory/"raw"/targets[0]["run_id"])
            with self.assertRaisesRegex(ValueError,"mixed release"): validate_series(self.directory)
        finally:
            for path,data in originals.items(): path.write_bytes(data)
            for run in targets: rehash(self.directory/"raw"/run["run_id"])

    def test_normal_cli_and_offline_reproduction(self):
        directory = self.directory
        raw_before = {str(p):digest(p) for p in (directory/"raw").rglob("*") if p.is_file()}
        process = subprocess.run([sys.executable,"-B",'-m',"reporting.analyze",str(directory)],capture_output=True,text=True)
        self.assertEqual(process.returncode,0,process.stderr)
        report = read(directory/"derived/analysis.json")
        audit = pd.read_csv(directory/"derived/audit.csv")
        self.assertEqual(tuple(audit.columns),AUDIT_FIELDS)
        self.assertEqual(len(audit),0)
        self.assertTrue(report["synthetic"])
        self.assertEqual(len(report["profiles"]),4)
        first_indices = {}
        for profile in report["profiles"]:
            self.assertEqual(profile["fullness"]["bounds"],[-.5,-.5])
            self.assertTrue(profile["WT_D"]["descriptive_only"])
            self.assertEqual(profile["CI95"]["bounds"],["-inf","+inf"])
            artifact = report["provenance"]["bootstrap"][profile["profile"]]
            indices = np.load(directory/"derived"/artifact["path"])["indices"]
            first_indices[profile["profile"]] = indices
            self.assertEqual(indices.shape,(10000,1))
            np.testing.assert_array_equal(indices,0)
            rng = np.random.Generator(np.random.PCG64())
            rng.bit_generator.state = artifact["state_before"]
            np.testing.assert_array_equal(indices,rng.integers(0,profile["n"],size=indices.shape))
        analyze(directory)
        replay = read(directory/"derived/analysis.json")
        self.assertEqual(report,replay)
        for profile,indices in first_indices.items():
            np.testing.assert_array_equal(indices,np.load(directory/"derived"/f"bootstrap-{profile}.npz")["indices"])
        self.assertEqual(raw_before,{str(p):digest(p) for p in (directory/"raw").rglob("*") if p.is_file()})
        for extension in ("png","svg","pdf"):
            files = list((directory/"derived/figures").glob(f"*.{extension}"))
            self.assertEqual(len(files),8)
            self.assertTrue(all(p.stat().st_size > 100 for p in files))
        from PIL import Image
        with Image.open(directory/"derived/figures/Q_ms.png") as image:
            self.assertAlmostEqual(image.info["dpi"][0],300,delta=.1)

    def test_whole_block_audit_and_replacement(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = make_fixture(Path(tmp)/"before")
            run = read(directory/"schedule.json")["runs"][0]
            folder = directory/"raw"/run["run_id"]
            snapshot = read(folder/"network_after.json"); snapshot["forwarding"]=0
            write(folder/"network_after.json",snapshot); rehash(folder)
            evidence = directory/"proof.json"
            self.assertTrue(diagnose(folder,directory/"schedule.json",evidence))
            replacement = replace(directory,run["attempt_id"],"path",evidence)
            ready = make_fixture(Path(tmp)/"after",schedule=read(directory/"schedule.json"))
            shutil.copytree(directory/"audit",ready/"audit")
            schedule,selected,audit = validate_series(ready)
            self.assertEqual(len(audit),1)
            self.assertNotIn(run["attempt_id"],{r["attempt_id"] for r in selected})
            self.assertIn(replacement["attempt_id"],{r["attempt_id"] for r in selected})
            self.assertEqual(len([r for r in selected if r["block_id"] == run["block_id"]]),3)
            process = self.cli(ready)
            self.assertEqual(process.returncode,0,process.stderr)
            audit_csv = pd.read_csv(ready/"derived/audit.csv")
            self.assertEqual(tuple(audit_csv.columns),AUDIT_FIELDS)
            self.assertEqual(len(audit_csv),1)
            self.assertEqual(audit_csv.iloc[0]["attempt_id"],run["attempt_id"])
            sibling = next(p for p in (ready/"audit"/run["attempt_id"]).iterdir() if p.is_dir() and p.name != run["run_id"])
            sibling.rename(ready/"removed-member")
            self.assert_cli_rejected(ready,"audit member inventory mismatch")
            (ready/"removed-member").rename(sibling)
            path = sibling/"slots.jsonl"; original = path.read_bytes()
            corrupted = rows(path)
            next(s for s in corrupted if s["first_correct_echo_ms"] is not None)["terminal_reason"]="local_api_error"
            path.write_text("".join(json.dumps(r)+"\n" for r in corrupted)); rehash(sibling)
            self.assert_cli_rejected(ready,"schema/terminal outcome")
            path.write_bytes(original); rehash(sibling)
            proof = ready/"audit"/run["attempt_id"]/"evidence.json"
            proof.write_text("{}")
            with self.assertRaisesRegex(ValueError,"audit evidence mismatch"): validate_series(ready)

    def test_r4_partial_old_block_can_be_archived_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = make_fixture(Path(tmp)/"before",datagrams=False)
            schedule = read(directory/"schedule.json"); run = schedule["runs"][0]
            other = next(r for r in schedule["runs"] if r["attempt_id"] == run["attempt_id"] and r != run)
            shutil.rmtree(directory/"raw"/other["run_id"])
            ledger = read(directory/"ledger.json"); ledger["attempts"][0]["status"]="planned"
            write(directory/"ledger.json",ledger); write(directory/"queue.json",[run["attempt_id"]])
            folder = directory/"raw"/run["run_id"]
            network = read(folder/"network_after.json"); network["forwarding"]=0
            write(folder/"network_after.json",network); rehash(folder)
            evidence=directory/"proof.json"; self.assertTrue(diagnose(folder,directory/"schedule.json",evidence))
            replace(directory,run["attempt_id"],"path",evidence)
            ready=make_fixture(Path(tmp)/"after",schedule=read(directory/"schedule.json"))
            shutil.copytree(directory/"audit",ready/"audit")
            self.assertEqual(len(read(ready/"audit"/run["attempt_id"]/"transaction.json")["moves"]),1)
            process=self.cli(ready); self.assertEqual(process.returncode,0,process.stderr)

    def test_r5_replacement_execution_order_and_old_snapshots_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = make_fixture(Path(tmp)/"before",blocks=2)
            original = read(directory/"schedule.json"); run = original["runs"][0]
            ledger = read(directory/"ledger.json")
            for attempt in ledger["attempts"]: attempt["status"]="planned"
            write(directory/"ledger.json",ledger); write(directory/"queue.json",[a["attempt_id"] for a in ledger["attempts"]])
            folder = directory/"raw"/run["run_id"]
            network = read(folder/"network_after.json"); network["forwarding"]=0
            write(folder/"network_after.json",network); rehash(folder)
            evidence=directory/"proof.json"; self.assertTrue(diagnose(folder,directory/"schedule.json",evidence))
            replacement=replace(directory,run["attempt_id"],"path",evidence)
            schedule=read(directory/"schedule.json"); queue=read(directory/"queue.json")
            self.assertGreater(queue.index(replacement["attempt_id"]),0)
            self.assertLess(queue.index(replacement["attempt_id"]),len(queue)-1)
            order = [r["run_id"] for attempt in queue for r in schedule["runs"] if r["attempt_id"] == attempt]
            ready=make_fixture(Path(tmp)/"after",schedule=schedule,execution_order=order)
            shutil.copytree(directory/"audit",ready/"audit")
            early=ready/"raw"/order[0]
            write(early/"schedule.json",original)
            manifest=read(early/"manifest.json"); manifest["schedule_sha256"]=digest(early/"schedule.json")
            write(early/"manifest.json",manifest); rehash(early)
            process=self.cli(ready); self.assertEqual(process.returncode,0,process.stderr)
            for path in (ready/"derived/runs.csv",ready/"derived/figures/runs-plot.csv"):
                frame=pd.read_csv(path)
                self.assertEqual(frame.run_id.tolist(),order)
                self.assertEqual(frame.run_order.tolist(),list(range(len(order))))

    def test_r4a_hash_corrupted_schedule_diagnose_replace_analyze_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory=make_fixture(Path(tmp)/"before",datagrams=False)
            run=read(directory/"schedule.json")["runs"][0]
            source=directory/"raw"/run["run_id"]
            corrupted=read(source/"schedule.json"); corrupted["master_seed"]+=1
            write(source/"schedule.json",corrupted)
            proof=directory/"proof.json"
            process=subprocess.run([sys.executable,"-B",'-m',"execution.violation",str(source),str(directory/"schedule.json"),str(proof)],capture_output=True,text=True)
            self.assertEqual(process.returncode,0,process.stderr)
            self.assertEqual((read(proof)["reason"],read(proof)["error"]),("hash","hash mismatch"))
            process=subprocess.run([sys.executable,"-B",'-m',"execution.replace",str(directory),run["attempt_id"],"hash",str(proof)],capture_output=True,text=True)
            self.assertEqual(process.returncode,0,process.stderr)
            ready=make_fixture(Path(tmp)/"after",schedule=read(directory/"schedule.json"))
            shutil.copytree(directory/"audit",ready/"audit")
            process=self.cli(ready)
            self.assertEqual(process.returncode,0,process.stderr)
            audit=pd.read_csv(ready/"derived/audit.csv")
            self.assertEqual((len(audit),audit.iloc[0]["reason"]),(1,"hash"))
            archived=ready/"audit"/run["attempt_id"]
            source=archived/run["run_id"]
            self.assertEqual(read(archived/"schedule.json")["master_seed"],20261108)
            self.assertEqual(read(source/"schedule.json")["master_seed"],20261109)

            def reject_edit(path,value,reason):
                original=path.read_bytes()
                try:
                    write(path,value)
                    self.assert_cli_rejected(ready,reason)
                finally:
                    path.write_bytes(original)

            changed=read(source/"schedule.json"); changed["master_seed"]+=1
            reject_edit(source/"schedule.json",changed,"audit source changed")
            changed=read(archived/"evidence.json"); changed["error"]="tampered"
            reject_edit(archived/"evidence.json",changed,"audit evidence mismatch")
            changed=read(source/"manifest.json"); changed["mode"]="WT-D"
            reject_edit(source/"manifest.json",changed,"raw directory/run attribution mismatch")
            changed=read(archived/"schedule.json"); changed["master_seed"]+=1
            reject_edit(archived/"schedule.json",changed,"schedule snapshot identity")
            changed=read(archived/"transaction.json"); changed["schedule"]["master_seed"]+=1
            reject_edit(archived/"transaction.json",changed,"schedule snapshot identity")
            sibling=next(p for p in archived.iterdir() if p.is_dir() and p.name != run["run_id"])
            changed=read(sibling/"schedule.json"); changed["master_seed"]+=1
            reject_edit(sibling/"schedule.json",changed,"schedule snapshot identity")
            active=next((ready/"raw").iterdir())
            originals={active/name:(active/name).read_bytes() for name in ("schedule.json","manifest.json","checks.json","SHA256SUMS")}
            try:
                changed=read(active/"schedule.json"); changed["master_seed"]+=1
                write(active/"schedule.json",changed)
                manifest=read(active/"manifest.json"); manifest["schedule_sha256"]=digest(active/"schedule.json")
                write(active/"manifest.json",manifest); rehash(active)
                self.assert_cli_rejected(ready,"schedule snapshot identity")
            finally:
                for path,data in originals.items(): path.write_bytes(data)
            print("R4a normal CLI: diagnose hash/hash mismatch -> replace -> analyze accepted; post-proof source/evidence, identity, independent archive, transaction, sibling and rehashed active snapshot mutations rejected without changing derived.")


if __name__ == "__main__":
    unittest.main()
