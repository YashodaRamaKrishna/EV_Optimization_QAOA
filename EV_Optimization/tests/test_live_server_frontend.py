"""Checks live running server HTML and endpoints with refined Estimate Resources requirements."""

import urllib.request
import json

def test_live():
    html = urllib.request.urlopen("http://localhost:5000/").read().decode()

    # 1. HTML elements that MUST be present
    checks_present = [
        "Problem Setup",
        "Model",
        "Solve",
        "Results",
        "Scaling &amp; IBM Hardware",
        "Estimate Resources",
        'id="scaling"',
        'id="estimate"',
        # Section A: 2x2 Grid Line Graphs
        'id="graphScalingSize"',
        'id="graphScalingDepth"',
        'id="graphScalingGates"',
        'id="graphScaling2Q"',
        # Section B: IBM Hardware Demonstration
        'id="ibmProblemSelect"',
        'id="runIbmHardwareBtn"',
        'id="ibmSourceTag"',
        'id="ibmProblemMetaCard"',
        'id="ibmStationsList"',
        'id="ibmValidationBox"',
        'id="ibmSchedule"',
        'id="ibmLoadChart"',
        'id="ibmGridMetrics"',
        'id="ibmGridProfileTable"',
        # Section B6: 4 Bar Graphs
        'id="resBarQubits"',
        'id="resBarGates"',
        'id="resBar2Q"',
        'id="resBarDepth"',
        # Estimate Resources
        'id="estimatePreset"',
        'id="runEstimateBtn"',
        'id="estimateHandoffBtn"',
        "Target IBM Quantum Device",
        'id="estSummaryCard"',
        'id="estSummaryGrid"',
        'id="estAerGrid"',
        'id="estAerMemGrid"',
        "Aer Statevector Computer Requirement",
        'id="estIbmGrid"',
        'id="estIbmDeviceGrid"',
        "Device Capacity &amp; Topology Mapping",
        # Problem Setup & Model Workflow Buttons
        'id="addProblemBtn"',
        'id="deleteProblemBtn"',
        'id="toModel"',
        'id="saveCustomBtn"',
        'id="cancelCustomBtn"',
        'id="modelToSolveBtn"',
    ]

    for c in checks_present:
        assert c in html, f"Missing in served HTML: {c}"
    print("[OK] All expected HTML structure checks passed!")

    # 2. HTML elements that MUST be absent (removed 6-row table, old analytics table, Section C)
    assert 'id="ibmScalingTable"' not in html, "Old 6-row instance table id='ibmScalingTable' still present in HTML!"
    assert 'id="ibmAnalyticsTable"' not in html, "Old analytics table id='ibmAnalyticsTable' still present in HTML!"
    assert 'id="ibmLastCompletedCard"' not in html, "Old last completed card still present in HTML!"
    assert "Section C" not in html and "C." not in html[:html.find('id="estimate"')], "Section C or leftover C header still present in Scaling tab!"

    # 2. HTML elements that MUST be absent (removed methodology card)
    assert "Resource Classification &amp; Validity" not in html, "Old Resource Classification & Validity card still present in HTML!"
    assert "Resource Classification & Validity" not in html, "Old Resource Classification & Validity card still present in HTML!"
    print("[OK] Verified 'Resource Classification & Validity' card is cleanly removed from HTML!")

    # 3. Check Scaling API
    r_scale = urllib.request.urlopen("http://localhost:5000/api/scaling/ibm-demo")
    d_scale = json.loads(r_scale.read())
    assert d_scale["status"] == "ok"
    assert len(d_scale["instances"]) == 6
    print("[OK] Scaling API returned 6 instances!")

    # 4. Check Estimate API with Baseline (26 qubits default)
    req_b = urllib.request.Request(
        "http://localhost:5000/api/estimate-resources",
        data=json.dumps({"instance": {"n_ev": 3, "n_st": 2, "n_t": 4}, "p": 1, "backend": "ibm_brisbane"}).encode(),
        headers={"Content-Type": "application/json"}
    )
    r_b = urllib.request.urlopen(req_b)
    d_b = json.loads(r_b.read())
    assert d_b["status"] == "derived_from_circuit"
    assert d_b["instance_summary"]["logical_qubits"] == 26
    assert "statevector_memory_str" in d_b["aer"]
    assert "physical_qubits_required" in d_b["ibm"]
    assert d_b["ibm"]["device_capacity"] == 127
    print("[OK] Estimate API baseline returned valid circuit derivation with memory and physical qubits!")

    # 5. Check Estimate API with 62-Qubit Example (10 EVs x 2 Stations x 3 Slots)
    req_62 = urllib.request.Request(
        "http://localhost:5000/api/estimate-resources",
        data=json.dumps({"instance": {"n_ev": 10, "n_st": 2, "n_t": 3}, "p": 3, "backend": "ibm_torino"}).encode(),
        headers={"Content-Type": "application/json"}
    )
    r_62 = urllib.request.urlopen(req_62)
    d_62 = json.loads(r_62.read())
    assert d_62["instance_summary"]["logical_qubits"] == 62
    assert d_62["aer"]["statevector_memory_str"] == "73.8 EB"
    assert d_62["aer"]["statevector_amplitudes"] == "2^62"
    assert d_62["aer"]["simulation_status_code"] == "not_practical"
    assert d_62["ibm"]["device_capacity"] == 133
    assert d_62["ibm"]["physical_qubits_required"] <= 133
    assert d_62["ibm"]["physical_qubits_required"] >= 62
    assert d_62["ibm"]["physical_qubits_required"] != d_62["ibm"]["device_capacity"]
    print("[OK] Estimate API 62-qubit example correctly computed 73.8 EB memory and distinguished physical qubits from capacity!")

    # 6. Check Estimate API with Large Instance (20x10x8)
    req_l = urllib.request.Request(
        "http://localhost:5000/api/estimate-resources",
        data=json.dumps({"instance": {"n_ev": 20, "n_st": 10, "n_t": 8}, "p": 2, "backend": "ibm_torino"}).encode(),
        headers={"Content-Type": "application/json"}
    )
    r_l = urllib.request.urlopen(req_l)
    d_l = json.loads(r_l.read())
    assert d_l["status"] == "analytical_estimation"
    assert d_l["instance_summary"]["logical_qubits"] == 1610
    print("[OK] Estimate API large problem returned valid analytical estimation!")

    # 7. Check IBM Execute API
    req_ibm = urllib.request.Request(
        "http://localhost:5000/api/ibm/execute",
        data=json.dumps({"instance_id": "demo-inst-3"}).encode(),
        headers={"Content-Type": "application/json"}
    )
    r_ibm = urllib.request.urlopen(req_ibm)
    d_ibm = json.loads(r_ibm.read())
    assert d_ibm["status"] == "ok"
    assert d_ibm["instance_id"] == "demo-inst-3"
    assert d_ibm["result"]["feasible"] is True
    assert len(d_ibm["result"]["assignments"]) > 0
    assert "aer_resources" in d_ibm
    assert "ibm_resources" in d_ibm
    print("[OK] IBM Execute API returned precomputed hardware solution for baseline!")

if __name__ == "__main__":
    test_live()
