"""Kill isolated active containers and verify recovery through the real app.

Set OPENSPRITE_CORE_FAULT_IMAGE to a built runtime image. This script creates
only uniquely named owned containers/volumes, preserves evidence, and stops
its recovery containers. It never touches an existing application container.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import time
from uuid import uuid4


def docker(*args):
    return subprocess.run(["docker", *args], check=True, text=True, capture_output=True, timeout=60).stdout.strip()


def snapshot(container):
    return json.loads(docker("exec", "-e", "OPENSPRITE_CORE_FAULT_OPERATION=inspect",
                             container, "python", "/proof/core_runtime_fault_fixture.py"))


def wait_ready(container, *, app=False):
    until = time.monotonic() + 45
    while time.monotonic() < until:
        if app:
            result = subprocess.run(["docker", "exec", container, "python", "-c",
                "import json,urllib.request; assert json.load(urllib.request.urlopen('http://127.0.0.1:8765/healthz',timeout=2)) == {'status':'ok'}"],
                capture_output=True, timeout=10)
            if result.returncode == 0:
                return
        else:
            logs = docker("logs", container)
            if '"ready": true' in logs:
                return
        time.sleep(.2)
    raise AssertionError("Isolated fixture did not become ready")


def main():
    image = os.environ["OPENSPRITE_CORE_FAULT_IMAGE"]
    image_id = docker("image", "inspect", "--format", "{{.Id}}", image)
    root = Path(__file__).resolve().parents[1]
    suffix = uuid4().hex[:10]
    output = root / "tmp" / "core-runtime-proof" / ("faults-"+suffix)
    output.mkdir(parents=True, exist_ok=False)
    proofs = []
    for kind in ("answer_stream", "draft_stream", "summary_transaction", "final_transaction"):
        name = "opensprite-core-fault-"+suffix+"-"+kind.replace("_", "-")
        volume, recovery = name+"-data", name+"-recovery"
        assert name.startswith("opensprite-core-fault-") and recovery.startswith(name)
        docker("volume", "create", volume)
        common = ["--mount", f"type=volume,source={volume},target=/home/opensprite/.opensprite",
                  "--mount", f"type=bind,source={root / 'scripts'},target=/proof,readonly",
                  "--env", "OPENSPRITE_CORE_FAULT_FIXTURE=1",
                  "--security-opt", "no-new-privileges:true", "--cap-drop", "ALL"]
        docker("run", "-d", "--name", name, *common, "--env", "OPENSPRITE_CORE_FAULT_OPERATION=actor",
               "--env", "OPENSPRITE_CORE_FAULT_KIND="+kind, "--env", "OPENSPRITE_CORE_FAULT_NONCE="+str(uuid4()),
               "--entrypoint", "python", image_id, "/proof/core_runtime_fault_fixture.py")
        try:
            wait_ready(name)
            before = snapshot(name)
            assert docker("inspect", "--format", "{{.State.Running}}", name) == "true"
            assert docker("exec", name, "id", "-u") == "10001"
            assert before["run"]["status"] == "running"
            assert len(before["steps"]) == 1 and before["steps"][0]["text"] == before["prefix"]
            assert before["summary"] is None
            assert not any(e["type"] in ("run.completed", "run.failed", "run.cancelled") for e in before["events"])
            docker("kill", "--signal", "KILL", name)
            assert docker("inspect", "--format", "{{.State.ExitCode}}", name) == "137"
            docker("run", "-d", "--name", recovery, *common, image_id)
            wait_ready(recovery, app=True)
            after = snapshot(recovery)
            assert after["run"]["status"] == "interrupted"
            assert after["run"]["assistant_message_id"] is None
            assert after["steps"][0]["text"] == before["steps"][0]["text"]
            assert after["steps"][0]["status"] == ("interrupted" if kind.endswith("stream") else "completed")
            assert after["messages"] == before["messages"]
            assert after["summary"] is None
            assert before["events"] == after["events"][:-1]
            assert after["events"][-1]["type"] == "run.interrupted"
            assert after["run"]["partial_text"] == (before["prefix"] if kind in ("answer_stream", "final_transaction") else "")
            if kind in ("draft_stream", "summary_transaction"):
                assert not any(e["type"] == "assistant.delta" for e in after["events"])
            docker("restart", recovery)
            wait_ready(recovery, app=True)
            assert snapshot(recovery) == after  # no automatic resend or duplicate terminal
            proof = {"kind": kind, "imageId": image_id, "container": name, "recoveryContainer": recovery,
                     "volume": volume, "killedWhileRunning": True, "before": before, "after": after,
                     "secondRestartIdentical": True}
            (output / (kind+".json")).write_text(json.dumps(proof, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
            proofs.append({"kind": kind, "runId": after["run"]["id"], "status": "interrupted",
                           "committedTextPreserved": True, "transactionRollback": kind.endswith("transaction"),
                           "secondRestartIdentical": True})
            print(json.dumps(proofs[-1]), flush=True)
        finally:
            # The owned actor may have failed before the kill; never stop another app.
            for container in (name, recovery):
                subprocess.run(["docker", "stop", "--time", "3", container], capture_output=True, timeout=15)
    result = {"imageId": image_id, "cases": proofs, "evidence": str(output),
              "limits": "Committed SQLite data only; unflushed deltas and power-loss durability are not promised."}
    (output / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
