const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
let instance, lastRun, customActive=false;
let selectedSolvers = new Set(['sa']);
const MAX_EVS = 8, MAX_STATIONS = 5, MAX_SLOTS = 8;
const QAOA_SIM_LIMIT = 24, EXACT_LIMIT = 20;

const api=async p=>{const r=await fetch(p);if(!r.ok)throw Error('API unavailable');return r.json()};

function toast(message){
  const e=$('#toast');e.textContent=message;e.classList.add('show');
  setTimeout(()=>e.classList.remove('show'),2600);
}

function table(headers,rows){
  return `<table><thead><tr>${headers.map(x=>`<th>${x}</th>`).join('')}</tr></thead><tbody>${rows.map(r=>`<tr>${r.map(x=>`<td>${x}</td>`).join('')}</tr>`).join('')}</tbody></table>`;
}

function getQUBOVariableCount(inst){
  if(!inst) return 22;
  const s = inst.n_st || 2;
  const e = inst.n_ev || 3;
  const windows = inst.window || Array(e).fill([0, 1]);
  let chargingVars = 0;
  for(let i = 0; i < e; i++){
    const w = windows[i] || [];
    chargingVars += w.length * s;
  }
  return s + chargingVars;
}

function updateModelTab(inst){
  const target = inst || instance;
  if(!target) return;
  const count = target.n_qubits || getQUBOVariableCount(target);
  const el = $('#modelVarsCount');
  if(el) el.textContent = count;
  const desc = $('#modelProblemDesc');
  if(desc) desc.textContent = `Actual formulation: ${target.n_ev} EVs × ${target.n_st} stations × ${target.n_t} slots → ${count} binary variables`;
}

function updateSolverAvailability(){
  const target = instance;
  if(!target) return;
  const N = target.n_qubits || getQUBOVariableCount(target);

  // SA: Always supported
  const cardSA = $('#card-sa');
  const chkSA = $('#chk-sa');
  const badgeSA = $('#badge-sa');
  if(badgeSA) badgeSA.textContent = '✓ Supported';
  if(chkSA) chkSA.disabled = false;

  // QAOA: Supported up to QAOA_SIM_LIMIT (24 qubits)
  const cardQAOA = $('#card-qaoa');
  const chkQAOA = $('#chk-qaoa');
  const badgeQAOA = $('#badge-qaoa');
  if(N <= QAOA_SIM_LIMIT){
    cardQAOA?.classList.remove('disabled');
    if(chkQAOA) chkQAOA.disabled = false;
    if(badgeQAOA){
      badgeQAOA.className = 'badge badge-success';
      badgeQAOA.textContent = `✓ Aer Sim (${N} qubits ≤ ${QAOA_SIM_LIMIT})`;
    }
  } else {
    cardQAOA?.classList.add('disabled');
    if(chkQAOA){
      chkQAOA.checked = false;
      chkQAOA.disabled = true;
      selectedSolvers.delete('qaoa');
    }
    if(badgeQAOA){
      badgeQAOA.className = 'badge badge-danger';
      badgeQAOA.textContent = `✕ Too Large (${N} > ${QAOA_SIM_LIMIT} qubits)`;
    }
  }

  // Exact Enumeration: Supported up to EXACT_LIMIT (20 qubits)
  const cardExact = $('#card-exact');
  const chkExact = $('#chk-exact');
  const badgeExact = $('#badge-exact');
  if(N <= EXACT_LIMIT){
    cardExact?.classList.remove('disabled');
    if(chkExact) chkExact.disabled = false;
    if(badgeExact){
      badgeExact.className = 'badge badge-warn';
      badgeExact.textContent = `Validation (${N} ≤ ${EXACT_LIMIT})`;
    }
  } else {
    cardExact?.classList.add('disabled');
    if(chkExact){
      chkExact.checked = false;
      chkExact.disabled = true;
      selectedSolvers.delete('exact');
    }
    if(badgeExact){
      badgeExact.className = 'badge badge-danger';
      badgeExact.textContent = `✕ Too Large (${N} > ${EXACT_LIMIT})`;
    }
  }

  // Ensure at least one solver is selected
  if(selectedSolvers.size === 0){
    selectedSolvers.add('sa');
    if(chkSA) chkSA.checked = true;
    cardSA?.classList.add('selected');
  }

  renderSolverControls();
}

function renderSetup(){
  const varCount = instance.n_qubits || getQUBOVariableCount(instance);
  $('#evCount').textContent=instance.n_ev;
  $('#stationCount').textContent=instance.n_st;
  $('#slotCount').textContent=instance.n_t;
  $('#qubits').textContent=varCount;
  updateModelTab(instance);
  updateSolverAvailability();

  $('#evTable').innerHTML=table(
    ['EV ID','Energy demand','Allowed charging slots','Charging requirement'],
    Array.from({length:instance.n_ev},(_,i)=>[
      `EV${i+1}`,
      instance.demand[i]??1,
      (instance.window[i]??[0,1]).map(t=>`T${t+1}`).join(', '),
      `${instance.demand[i]??1} slot(s)`
    ])
  );

  $('#stationTable').innerHTML=table(
    ['Station ID','Candidate location','Capacity','Chargers','Opening cost'],
    Array.from({length:instance.n_st},(_,i)=>[
      `S${i+1}`,
      `Candidate ${String.fromCharCode(65+i)}`,
      1,1,
      Number(instance.open_cost[i]??1).toFixed(1)
    ])
  );

  const slots=Array.from({length:instance.n_t},(_,i)=>`T${i+1}`);
  $('#gridTable').innerHTML=table(
    ['',''+slots.join(' | ')],
    [
      ['Grid capacity',(instance.grid_cap||[]).join(' | ')],
      ['Electricity price',(instance.price||[]).map(x=>Number(x).toFixed(1)).join(' | ')]
    ]
  );
}

function show(id){
  $$('.panel').forEach(x=>x.classList.toggle('active',x.id===id));
  $$('#tabs button').forEach(x=>x.classList.toggle('active',x.dataset.tab===id));
  window.scrollTo({top:0,behavior:'smooth'});
  if(id==='model'){
    updateModelTab(instance);
  }
  if(id==='solve'){
    updateSolverAvailability();
  }
  if(id==='scaling'){
    loadIbmScalingData();
  }
}

function customDimensions(){
  return {
    e: +$('#customEVs').value,
    s: +$('#customStations').value,
    t: +$('#customSlots').value
  };
}

function makeCustomProblem(){
  const {e,s,t}=customDimensions();
  if(!Number.isInteger(e)||!Number.isInteger(s)||!Number.isInteger(t)||e<1||s<1||t<1){
    $('#customErrors').textContent='Use positive whole numbers for EVs, stations, and time slots.';
    return;
  }

  const exceedsLiveLimits = e > MAX_EVS || s > MAX_STATIONS || t > MAX_SLOTS;
  const handoffBtn = $('#estimateHandoffBtn');
  if(handoffBtn){
    handoffBtn.disabled = !exceedsLiveLimits;
    handoffBtn.title = exceedsLiveLimits
      ? `Estimate quantum resources for ${e} EVs × ${s} stations × ${t} slots`
      : 'Available when the problem exceeds live execution limits.';
  }

  if(exceedsLiveLimits){
    $('#customErrors').innerHTML=`
      <div class="warning-banner" style="margin:10px 0;">
        ⚠ <b>Problem exceeds live execution limits</b> (Max ${MAX_EVS} EVs, ${MAX_STATIONS} stations, ${MAX_SLOTS} time slots).<br>
        Live solver execution is disabled for problems of this scale. Click <b>Estimate Resources</b> to evaluate quantum circuit scaling and hardware requirements.
      </div>
    `;
    $('#buildCustomBtn').disabled = true;
    $('#customForms').innerHTML = '';
    return;
  }

  let html='<div class="custom-grid"><article><h3>EV configuration</h3>'+
    Array.from({length:e},(_,i)=>`
      <fieldset><legend>EV ${i+1}</legend>
      <label>ID <input data-ev-id="${i}" value="EV${i+1}"></label>
      <label>Demand <input class="custom-input" data-demand="${i}" type="number" min="1" step="1" value="1"></label>
      <div class="slot-options"><span>Available slots</span>
      ${Array.from({length:t},(_,j)=>`<label><input class="custom-input" data-window="${i}" data-slot="${j}" type="checkbox" checked> T${j+1}</label>`).join('')}
      </div></fieldset>`).join('')+
    '</article><article><h3>Candidate station configuration</h3>'+
    Array.from({length:s},(_,i)=>`
      <fieldset><legend>Station ${i+1}</legend>
      <label>ID <input data-station-id="${i}" value="S${i+1}"></label>
      <label>Number of chargers <input class="custom-input" data-chargers="${i}" type="number" min="1" value="1"></label>
      <label>Charger capacity <input class="custom-input" data-capacity="${i}" type="number" min="1" value="1"></label>
      <label>Opening cost <input class="custom-input" data-open-cost="${i}" type="number" min="0" step="0.1" value="1.0"></label>
      </fieldset>`).join('')+
    '</article></div>';

  html+=`<article class="custom-section"><h3>Time slot configuration</h3>${table(
    ['Slot','Label','Electricity price','Grid capacity'],
    Array.from({length:t},(_,i)=>[
      `T${i+1}`,
      `<input class="custom-input" data-slot-label="${i}" value="Slot ${i+1}">`,
      `<input class="custom-input" data-price="${i}" type="number" min="0" step="0.1" value="1.0">`,
      `<input class="custom-input" data-grid="${i}" type="number" min="1" step="1" value="2">`
    ])
  )}</article>`;

  html+=`<article class="custom-section"><h3>EV-to-Station Travel Cost</h3>
    <p>Enter the detour / travel cost from each EV to each candidate station.</p>
    ${table(
      ['EV / Station',...Array.from({length:s},(_,j)=>`S${j+1}`)],
      Array.from({length:e},(_,i)=>[
        `EV${i+1}`,
        ...Array.from({length:s},(_,j)=>`<input class="custom-input" data-detour-e="${i}" data-detour-s="${j}" type="number" min="0" step="0.1" value="0.0">`)
      ])
    )}</article>`;

  $('#customForms').innerHTML=html;
  $('#customErrors').textContent='';
  validateCustom();
}

function collectCustom(){
  const {e,s,t}=customDimensions(), errors=[];
  const value=selector=>{const x=$(selector);return x?+x.value:NaN};
  const demand=[],window=[],open_cost=[],price=[],grid_cap=[],detour=[];

  if(e > MAX_EVS) errors.push(`EV count (${e}) exceeds limit of ${MAX_EVS}.`);
  if(s > MAX_STATIONS) errors.push(`Station count (${s}) exceeds limit of ${MAX_STATIONS}.`);
  if(t > MAX_SLOTS) errors.push(`Time slot count (${t}) exceeds limit of ${MAX_SLOTS}.`);

  for(let i=0;i<e;i++){
    const d=value(`[data-demand="${i}"]`);
    if(!(d>0))errors.push(`EV ${i+1}: demand must be greater than 0.`);
    demand.push(d);
    const w=$$(`[data-window="${i}"]:checked`).map(x=>+x.dataset.slot);
    if(!w.length)errors.push(`EV ${i+1}: select at least one available charging slot.`);
    window.push(w);
  }
  for(let j=0;j<s;j++){
    const c=value(`[data-open-cost="${j}"]`);
    if(!(c>=0))errors.push(`Station ${j+1}: opening cost cannot be negative.`);
    open_cost.push(c);
  }
  for(let k=0;k<t;k++){
    const p=value(`[data-price="${k}"]`),g=value(`[data-grid="${k}"]`);
    if(!(p>=0))errors.push(`T${k+1}: electricity price cannot be negative.`);
    if(!(g>0))errors.push(`T${k+1}: grid capacity must be greater than 0.`);
    price.push(p);
    grid_cap.push(g);
  }
  for(let i=0;i<e;i++){
    detour[i]=[];
    for(let j=0;j<s;j++){
      const d=value(`[data-detour-e="${i}"][data-detour-s="${j}"]`);
      if(!(d>=0))errors.push(`EV${i+1}–S${j+1}: enter a non-negative travel cost.`);
      detour[i].push(d);
    }
  }

  // Exact dynamic variable count
  let totalChargingVars = 0;
  for(let i=0;i<e;i++){
    totalChargingVars += (window[i]||[]).length * s;
  }
  const n_qubits = s + totalChargingVars;

  return {
    errors,
    data:{
      id:`custom-${Date.now()}`,
      name:`Custom Problem — ${e} EV × ${s} Stations × ${t} Slots`,
      n_ev:e, n_st:s, n_t:t,
      demand, window, price, grid_cap, open_cost, detour,
      stress_w:+$('#stress').value,
      seed:+$('#seed').value,
      n_qubits:n_qubits
    }
  };
}

function validateCustom(){
  if(!$('#customForms').children.length)return;
  const {errors,data}=collectCustom();
  $('#customErrors').innerHTML=errors.length
    ? errors.map(x=>`<div>⚠ ${x}</div>`).join('')
    : '<div class="valid">✓ Custom problem is valid and ready to save.</div>';
  const saveBtn = $('#saveCustomBtn');
  if(saveBtn) saveBtn.disabled = !!errors.length;
  const buildBtn = $('#buildCustomBtn');
  if(buildBtn) buildBtn.disabled = !!errors.length;
  $('#evCount').textContent=data.n_ev;
  $('#stationCount').textContent=data.n_st;
  $('#slotCount').textContent=data.n_t;
  $('#qubits').textContent=data.n_qubits;
  $('#modelVarsCount').textContent=data.n_qubits;
}

function renderSolverControls(){
  const container = $('#solverControls');
  if(!container) return;
  const hasSA = selectedSolvers.has('sa');
  const hasQAOA = selectedSolvers.has('qaoa');
  const hasExact = selectedSolvers.has('exact');

  let html = '';

  if(hasSA){
    html += `
      <div class="solver-param-block" id="saParamsBlock">
        <h4>Simulated Annealing (SA) Parameters</h4>
        <div class="controls">
          <label>Iterations <input id="saIterations" type="number" min="500" max="50000" step="500" value="4000"></label>
          <label>Initial Temp (T₀) <input id="saInitTemp" type="number" min="0.1" step="0.5" value="10.0"></label>
          <label>Final Temp (T_f) <input id="saFinalTemp" type="number" min="0.0001" step="0.001" value="0.01"></label>
          <label>Cooling <select id="saSchedule"><option value="geometric">Geometric</option><option value="linear">Linear</option><option value="exponential">Exponential</option></select></label>
          <label>Seed <input id="saSeed" type="number" value="${instance?.seed||42}"></label>
          <label>Restarts <input id="saRestarts" type="number" min="1" max="50" value="8"></label>
          <label>Time Budget (s) <input id="saTimeBudget" type="number" min="1" placeholder="Unlimited"></label>
        </div>
      </div>
    `;
  }

  if(hasQAOA){
    html += `
      <div class="solver-param-block" id="qaoaParamsBlock">
        <h4>Quantum / Hybrid QAOA Parameters (Qiskit Aer)</h4>
        <div class="controls">
          <label>QAOA Depth (p) <input id="qaoaP" type="number" min="1" max="4" value="1"></label>
          <label>Shots <input id="qaoaShots" type="number" min="64" max="4096" step="64" value="512"></label>
          <label>Optimizer <select id="qaoaOpt"><option>COBYLA</option><option>SPSA</option></select></label>
          <label>Max Iterations <input id="qaoaMaxIter" type="number" min="5" max="100" value="25"></label>
          <label>Seed <input id="qaoaSeed" type="number" value="${instance?.seed||42}"></label>
        </div>
        <small class="muted" style="display:block;margin-top:6px;">Evaluates parameterized ansatz circuit on AerSimulator against the identical binary QUBO. Simulation limit: ${QAOA_SIM_LIMIT} qubits.</small>
      </div>
    `;
  }

  if(hasExact){
    html += `
      <div class="solver-param-block" id="exactParamsBlock">
        <h4>Exact Enumeration (Ground Truth Validation)</h4>
        <p class="muted" style="margin:0;">Evaluates all 2<sup>N</sup> states up to N=${EXACT_LIMIT} to determine exact global optimum and compute optimality gaps.</p>
      </div>
    `;
  }

  if(!html){
    html = '<p class="muted">Select at least one solver above.</p>';
  }

  container.innerHTML = html;
}

function collectSolverPayload(){
  const solvers = Array.from(selectedSolvers);
  return {
    solvers: solvers,
    solver: solvers[0] || 'classical',
    params: {
      sa: {
        n_iterations: +$('#saIterations')?.value || 4000,
        initial_temp: +$('#saInitTemp')?.value || 10.0,
        final_temp: +$('#saFinalTemp')?.value || 0.01,
        cooling_schedule: $('#saSchedule')?.value || 'geometric',
        seed: +$('#saSeed')?.value || 42,
        restarts: +$('#saRestarts')?.value || 8,
        runtime_budget_s: $('#saTimeBudget')?.value ? +$('#saTimeBudget').value : null
      },
      qaoa: {
        p: +$('#qaoaP')?.value || 1,
        shots: +$('#qaoaShots')?.value || 512,
        optimizer: $('#qaoaOpt')?.value || 'COBYLA',
        max_iterations: +$('#qaoaMaxIter')?.value || 25,
        seed: +$('#qaoaSeed')?.value || 42,
        max_sim_qubits: QAOA_SIM_LIMIT
      }
    }
  };
}

function getViolatedCells(inst, best){
  const targetInst = inst || instance;
  const s = best || {};
  const violations = s.violations || [];
  const violated = new Set();
  if(!violations.length || s.feasible) return violated;

  violations.forEach(v => {
    // 1. Grid capacity violation: Slot (?:T)?<t> load ...
    const gridMatch = v.match(/Slot\s*(?:T)?(\d+).*exceeds grid limit/i);
    if(gridMatch){
      const t = parseInt(gridMatch[1], 10) - 1;
      (s.assignments || []).forEach(a => {
        if(a.slot === t) violated.add(`${a.ev}-${a.slot}`);
      });
    }
    // 2. Coupling violation: EV <e> assigned to closed station (?:S)?<s> at slot (?:T)?<t>
    const coupMatch = v.match(/EV\s*(\d+).*closed station\s*(?:S)?(\d+).*slot\s*(?:T)?(\d+)/i);
    if(coupMatch){
      const e = parseInt(coupMatch[1], 10) - 1;
      const t = parseInt(coupMatch[3], 10) - 1;
      violated.add(`${e}-${t}`);
    }
    // 3. Simultaneous charging violation: EV <e> scheduled at multiple stations at slot (?:T)?<t>
    const simMatch = v.match(/EV\s*(\d+).*multiple stations.*slot\s*(?:T)?(\d+)/i);
    if(simMatch){
      const e = parseInt(simMatch[1], 10) - 1;
      const t = parseInt(simMatch[2], 10) - 1;
      violated.add(`${e}-${t}`);
    }
    // 4. Station capacity violation: Station (?:S)?<s> serves multiple EVs at slot (?:T)?<t>
    const stMatch = v.match(/Station\s*(?:S)?(\d+).*multiple EVs.*slot\s*(?:T)?(\d+)/i);
    if(stMatch){
      const st = parseInt(stMatch[1], 10) - 1;
      const t = parseInt(stMatch[2], 10) - 1;
      (s.assignments || []).forEach(a => {
        if(a.station === st && a.slot === t) violated.add(`${a.ev}-${a.slot}`);
      });
    }
    // 5. Time window violation: EV <e> scheduled at slot (?:T)?<t> outside allowed window
    const winMatch = v.match(/EV\s*(\d+).*slot\s*(?:T)?(\d+).*outside/i);
    if(winMatch){
      const e = parseInt(winMatch[1], 10) - 1;
      const t = parseInt(winMatch[2], 10) - 1;
      violated.add(`${e}-${t}`);
    }
  });

  return violated;
}

function renderScheduleTable(inst, best, containerId='schedule', title=''){
  const targetInst = inst || instance;
  const s = best || {};
  let schedHtml = '';
  if(title) schedHtml += `<h4 style="margin:8px 0 6px;">${title}</h4>`;

  const rawAssignments = s.assignments || [];
  // Validate assignment bounds against target instance
  const validAssignments = rawAssignments.filter(a =>
    a &&
    a.ev >= 0 && a.ev < targetInst.n_ev &&
    a.station >= 0 && a.station < targetInst.n_st &&
    a.slot >= 0 && a.slot < targetInst.n_t
  );
  const outOfBoundsCount = rawAssignments.length - validAssignments.length;

  if(outOfBoundsCount > 0){
    schedHtml += `
      <div class="warning-banner" style="margin-bottom:8px;font-size:12px;">
        ⚠ <b>Data Isolation Warning</b>: ${outOfBoundsCount} stale assignment(s) outside target instance dimensions (${targetInst.n_ev} EVs × ${targetInst.n_st} stations × ${targetInst.n_t} slots) were detected and omitted.
      </div>
    `;
  }

  const violatedCells = getViolatedCells(targetInst, s);

  schedHtml += '<table class="schedule-table"><thead><tr><th>EV / Slot</th>';
  for (let t = 0; t < targetInst.n_t; t++) {
    schedHtml += `<th>T${t+1}</th>`;
  }
  schedHtml += '</tr></thead><tbody>';

  for (let e = 0; e < targetInst.n_ev; e++) {
    schedHtml += `<tr><td>EV${e+1}</td>`;
    for (let t = 0; t < targetInst.n_t; t++) {
      const a = validAssignments.find(x => x.ev === e && x.slot === t);
      const isCellViolated = violatedCells.has(`${e}-${t}`);
      const tdClass = a ? (isCellViolated ? 'filled cell-violation' : 'filled') : (isCellViolated ? 'cell-violation' : '');
      const tdTitle = isCellViolated ? 'Constraint violation associated with this slot' : '';
      schedHtml += `<td class="${tdClass}" title="${tdTitle}">${a ? `S${a.station + 1}` : '—'}</td>`;
    }
    schedHtml += '</tr>';
  }
  schedHtml += '</tbody></table>';

  // Detailed assignments table: strictly use validAssignments
  if(validAssignments.length > 0){
    schedHtml += '<details style="margin-top:10px;" open><summary style="font-size:12px;cursor:pointer;font-weight:600;">Detailed Charging Assignments Table</summary>';
    schedHtml += table(
      ['EV', 'Station', 'Time Slot', 'Demand', 'Detour Cost', 'Electricity Price', 'Status'],
      validAssignments.map(a => {
        const isViolated = violatedCells.has(`${a.ev}-${a.slot}`);
        return [
          `EV${a.ev + 1}`,
          `S${a.station + 1}`,
          `T${a.slot + 1}`,
          `${a.demand || 1} slot`,
          `$${Number(a.detour_cost ?? 0).toFixed(2)}`,
          `$${Number(a.electricity_price ?? 0).toFixed(2)}`,
          isViolated ? `<span class="badge badge-danger">Violated</span>` : `<span class="badge badge-success">Assigned</span>`
        ];
      })
    );
    schedHtml += '</details>';
  } else {
    schedHtml += '<p class="muted" style="margin-top:8px;font-size:12px;">No active charging assignments for this schedule.</p>';
  }

  // Constraint Violations block (shown if solver is infeasible and has reported violations)
  if(!s.feasible && s.violations && s.violations.length > 0){
    schedHtml += `
      <div class="solver-violations">
        <b>Constraint Violations:</b>
        ${s.violations.map(v => `<div>⚠ ${v}</div>`).join('')}
      </div>
    `;
  }

  const el = $(`#${containerId}`);
  if(el) el.innerHTML = schedHtml;
}

function renderGridMetrics(inst, best, metricsContainerId='gridMetrics'){
  const targetInst = inst || instance;
  const s = best || {};
  const T = targetInst.n_t;
  const loads = s.load || Array(T).fill(0);
  const caps = targetInst.grid_cap || Array(T).fill(1);

  // 1. Peak Load: max(L_t)
  const peakLoad = Math.max(...loads, 0);

  // 2. Peak Utilization: max(L_t / G_t * 100)
  const utils = loads.map((l, t) => ((l / (caps[t] || 1)) * 100));
  const peakUtil = Math.max(...utils, 0);

  // 3. Average Utilization: avg(L_t / G_t * 100)
  const avgUtil = utils.reduce((sum, u) => sum + u, 0) / Math.max(1, T);

  // 4. Near-Capacity Slots: count(L_t / G_t >= 0.80) -> X / T
  const nearCapCount = loads.filter((l, t) => (l / (caps[t] || 1)) >= 0.80).length;
  const nearCapStr = `${nearCapCount} / ${T}`;

  // 5. Capacity Violations: count(L_t > G_t)
  const capViolations = loads.filter((l, t) => l > (caps[t] || 1)).length;

  const metricsEl = $(`#${metricsContainerId}`);
  if(metricsEl){
    metricsEl.innerHTML = `
      <div><b>${peakLoad}</b><span>Peak Load</span></div>
      <div><b>${peakUtil.toFixed(1)}%</b><span>Peak Utilization</span></div>
      <div><b>${avgUtil.toFixed(1)}%</b><span>Average Utilization</span></div>
      <div><b>${nearCapStr}</b><span>Near-Capacity Slots</span></div>
      <div class="${capViolations > 0 ? 'viol' : ''}"><b>${capViolations}</b><span>Capacity Violations</span></div>
    `;
  }
}

function clearResultsDisplay(){
  const notice = $('#resultNotice');
  if(notice) notice.innerHTML = '';
  const meta = $('#resultMeta');
  if(meta) meta.textContent = 'Awaiting optimization run';
  const sumTiles = $('#summaryTiles');
  if(sumTiles) sumTiles.style.display = 'flex';
  const mStCard = $('#multiStationPlacementCard');
  if(mStCard) mStCard.style.display = 'none';
  const pills = $('#multiFeasibilityPills');
  if(pills) pills.innerHTML = '';
  const mStTable = $('#multiStationPlacementTable');
  if(mStTable) mStTable.innerHTML = '';
  const sched = $('#schedule');
  if(sched) sched.innerHTML = '<p class="muted">No solution available. Run optimization on the Solve tab.</p>';
  const multiCont = $('#multiSchedulesContainer');
  if(multiCont) multiCont.innerHTML = '';
  const multiCard = $('#multiSchedulesCard');
  if(multiCard) multiCard.style.display = 'none';
  const singleGrid = $('#singleSolutionGrid');
  if(singleGrid) singleGrid.style.display = 'grid';
  const stationsList = $('#stationsList');
  if(stationsList) stationsList.innerHTML = '<p class="muted">Awaiting run</p>';
  const valBox = $('#validationBox');
  if(valBox){ valBox.innerHTML = 'Awaiting run'; valBox.className = 'checks'; }
  const loadChart = $('#loadChart');
  if(loadChart) loadChart.innerHTML = '';
  const loadLegend = $('#loadLegend');
  if(loadLegend) loadLegend.innerHTML = '<i class="actual"></i> Actual load <i class="capacity"></i> Grid capacity';
  const gridMetrics = $('#gridMetrics');
  if(gridMetrics) gridMetrics.innerHTML = '';
  const gridProfileTable = $('#gridProfileTable');
  if(gridProfileTable) gridProfileTable.innerHTML = '';
  const costChart = $('#costChart');
  if(costChart) costChart.innerHTML = '';
  const costSummary = $('#costSummary');
  if(costSummary){ costSummary.style.display = 'block'; costSummary.innerHTML = '<b>Awaiting run</b>'; }
  const qCard = $('#quantumResourcesCard');
  if(qCard) qCard.style.display = 'none';
  const cmpCard = $('#resultComparison');
  if(cmpCard) cmpCard.style.display = 'none';
  const sName = $('#resSolverName');
  if(sName) sName.textContent = '—';
  const rTime = $('#resRuntime');
  if(rTime) rTime.textContent = '—';
  $('#resFeasible').textContent = '—';
  $('#resFeasible').className = 'val';
  $('#resObjective').textContent = '—';
  if($('#resTotalCost')) $('#resTotalCost').textContent = '—';
  $('#resStationsOpen').textContent = '—';
  $('#resGridStress').textContent = '—';
  $('#resGap').textContent = '—';
}

function renderResults(run){
  if(!run) return;
  lastRun = run;

  // Single Source of Truth verification: check instance matching
  const runInstId = run.instance_id || run.best?.instance_id;
  const isInstanceMatch = !runInstId || !instance?.id || (runInstId === instance.id);
  const noticeEl = $('#resultNotice');

  if(!isInstanceMatch){
    if(noticeEl){
      noticeEl.innerHTML = `
        <div class="warning-banner" style="margin-bottom:12px;">
          <b>Instance Mismatch Warning</b>: The displayed run result (Instance: <code>${runInstId}</code>) does not match the active problem instance (Instance: <code>${instance.id}</code>). Please run optimization on the Solve tab to obtain valid results for this instance.
        </div>
      `;
    }
    clearResultsDisplay();
    return;
  }
  const results = run.results || {};
  const completedSolvers = Object.entries(results).filter(([k, r]) => r.status === 'completed' && r.best);
  const isMulti = run.is_multi === true && completedSolvers.length > 1;
  const solversRequested = run.solvers_requested || [run.solver_key || 'sa'];

  // Handle simulation guard warning if QAOA was unsupported
  const qaoaRun = results.qaoa;
  const qaoaUnsupported = qaoaRun && qaoaRun.status === 'unsupported_size';
  if(noticeEl){
    if(qaoaUnsupported){
      noticeEl.innerHTML = `
        <div class="warning-banner">
          <b>Simulation Guard Notice</b>:
          ${qaoaRun.error || `QAOA simulation unavailable for this instance (${qaoaRun.actual_qubits} logical qubits exceeds the Aer simulation limit of ${qaoaRun.maximum_simulation_qubits || QAOA_SIM_LIMIT}).`}
        </div>
      `;
    } else {
      noticeEl.innerHTML = '';
    }
  }

  // Determine primary display run
  let primaryRun = run;
  if(results.sa && results.sa.status === 'completed'){
    primaryRun = results.sa;
  } else if(results.qaoa && results.qaoa.status === 'completed'){
    primaryRun = results.qaoa;
  } else if(results.exact && results.exact.status === 'completed'){
    primaryRun = results.exact;
  } else if(completedSolvers.length > 0){
    primaryRun = completedSolvers[0][1];
  }

  const s = primaryRun.best || {};
  const isDemo = primaryRun.provenance?.is_demo === true;

  // 1. Header meta
  if(isMulti){
    $('#resultMeta').textContent = `Multi-Solver Evaluation · ${completedSolvers.map(([k, r]) => r.solver).join(' + ')} · Same QUBO Formulation (${run.qubo_vars || instance.n_qubits} qubits)`;
  } else {
    $('#resultMeta').textContent = isDemo
      ? 'Precomputed baseline reference · Demo data'
      : `${primaryRun.solver} · ${primaryRun.backend || 'Local'} · ${new Date().toLocaleTimeString()}`;
  }

  // 2. Top Summary Card / Station Placement Conditional Logic
  const summaryTiles = $('#summaryTiles');
  const multiStationCard = $('#multiStationPlacementCard');
  const singleGrid = $('#singleSolutionGrid');
  const multiSchedCard = $('#multiSchedulesCard');

  if(isMulti){
    // CASE B: MULTIPLE SOLVERS SELECTED
    if(summaryTiles) summaryTiles.style.display = 'none';
    if(multiStationCard) multiStationCard.style.display = 'block';

    // Multi-solver feasibility summary pills
    const pillsHtml = completedSolvers.map(([k, r]) => {
      const isFeas = r.best?.feasible;
      const badgeCls = isFeas ? 'badge-success' : 'badge-danger';
      const statusText = isFeas ? '✓ Feasible' : '✕ Infeasible';
      return `<span class="badge ${badgeCls}" style="font-size:13px;padding:5px 12px;"><b>${r.solver}</b>: ${statusText}</span>`;
    }).join('');
    const pillsEl = $('#multiFeasibilityPills');
    if(pillsEl) pillsEl.innerHTML = pillsHtml;

    // Station Placement Comparison Table across solvers
    const stTableHeaders = ['Station', ...completedSolvers.map(([k, r]) => r.solver), 'Base Opening Cost'];
    const stTableRows = [];
    for(let i = 0; i < instance.n_st; i++){
      const row = [`<b>Station ${i+1}</b>`];
      completedSolvers.forEach(([k, r]) => {
        const isOpen = r.best?.stations_open?.[i];
        row.push(isOpen ? '<span class="green" style="font-weight:600;">Open</span>' : '<span class="muted">Closed</span>');
      });
      row.push(`$${Number(instance.open_cost?.[i] ?? 1.0).toFixed(1)}`);
      stTableRows.push(row);
    }
    // Summary row: Total stations opened
    const totalRow = ['<b>Total Stations Opened</b>'];
    completedSolvers.forEach(([k, r]) => {
      const cnt = (r.best?.stations_open || []).filter(Boolean).length;
      totalRow.push(`<b>${cnt} / ${instance.n_st}</b>`);
    });
    totalRow.push('—');
    stTableRows.push(totalRow);

    // Summary row: Infrastructure Cost
    const infraRow = ['<b>Infrastructure Cost</b>'];
    completedSolvers.forEach(([k, r]) => {
      const cost = r.best?.cost_breakdown?.infrastructure ?? 0;
      infraRow.push(`<b>$${Number(cost).toFixed(2)}</b>`);
    });
    infraRow.push('—');
    stTableRows.push(infraRow);

    const stTableEl = $('#multiStationPlacementTable');
    if(stTableEl) stTableEl.innerHTML = table(stTableHeaders, stTableRows);

  } else {
    // CASE A: ONLY ONE SOLVER SELECTED
    if(summaryTiles) summaryTiles.style.display = 'flex';
    if(multiStationCard) multiStationCard.style.display = 'none';

    // Single solver horizontal card summary fields
    const solverNameEl = $('#resSolverName');
    if(solverNameEl){
      let sLabel = primaryRun.solver || 'SA';
      if(sLabel.toLowerCase().includes('simulated')) sLabel = 'SA';
      else if(sLabel.toLowerCase().includes('qaoa')) sLabel = 'QAOA';
      else if(sLabel.toLowerCase().includes('exact')) sLabel = 'Exact';
      solverNameEl.textContent = sLabel;
    }
    const runtimeEl = $('#resRuntime');
    if(runtimeEl){
      if(isDemo){
        runtimeEl.textContent = 'Demo';
      } else if(primaryRun.runtime_s !== undefined && primaryRun.runtime_s !== null){
        runtimeEl.textContent = `${Number(primaryRun.runtime_s).toFixed(3)}s`;
      } else if(primaryRun.runtime !== undefined && primaryRun.runtime !== null){
        runtimeEl.textContent = `${Number(primaryRun.runtime).toFixed(3)}s`;
      } else {
        runtimeEl.textContent = '—';
      }
    }

    const isFeas = s.feasible;
    $('#resFeasible').textContent = isFeas ? '✓ FEASIBLE' : (primaryRun.status === 'unsupported_size' ? 'N/A' : '✕ INFEASIBLE');
    $('#resFeasible').className = isFeas ? 'val green' : 'val red';
    $('#resObjective').textContent = s.objective !== undefined ? Number(s.objective).toFixed(2) : 'N/A';
    if($('#resTotalCost')) $('#resTotalCost').textContent = s.objective !== undefined ? Number(s.objective).toFixed(2) : 'N/A';
    const openCount = (s.stations_open || []).filter(Boolean).length;
    $('#resStationsOpen').textContent = s.stations_open ? `${openCount} / ${instance.n_st}` : 'N/A';
    $('#resGridStress').textContent = s.cost_breakdown?.grid_stress !== undefined ? Number(s.cost_breakdown.grid_stress).toFixed(2) : 'N/A';
    $('#resGap').textContent = primaryRun.metrics?.optimality_gap || '0.0%';

    // Selected stations list
    let stHtml = '';
    (s.stations_open || []).forEach((isOpen, idx)=>{
      const cost = instance.open_cost?.[idx] ?? 1.0;
      stHtml += `<p><b>Station ${idx+1} — <span class="${isOpen?'green':'muted'}">${isOpen?'OPEN':'CLOSED'}</span></b> <span class="right">Cost: ${isOpen?Number(cost).toFixed(1):'0.0'}</span></p>`;
    });
    $('#stationsList').innerHTML = stHtml || '<p class="muted">No station data available.</p>';

    // Validation checklist
    if(s.feasible){
      $('#validationBox').innerHTML = `
        ✓ Charging demand satisfied (${instance.n_ev} EVs)<br>
        ✓ Time windows satisfied<br>
        ✓ Station capacity satisfied (≤ 1 EV/charger)<br>
        ✓ Grid capacity satisfied<br>
        ✓ Station-opening coupling satisfied
      `;
      $('#validationBox').className = 'checks';
    } else if(s.violations && s.violations.length){
      $('#validationBox').innerHTML = s.violations.map(v=>`⚠ ${v}`).join('<br>');
      $('#validationBox').className = 'checks validation';
    } else {
      $('#validationBox').innerHTML = '<span class="muted">No validation violations recorded.</span>';
      $('#validationBox').className = 'checks';
    }
  }

  // 3. Decoded Scheduling Solutions
  if(isMulti){
    if(singleGrid) singleGrid.style.display = 'none';
    if(multiSchedCard) multiSchedCard.style.display = 'block';

    const multiContainer = $('#multiSchedulesContainer');
    let mHtml = '';
    for(const [k, r] of completedSolvers){
      mHtml += `<div class="card" style="margin-bottom:12px;">
        <div class="section-title">
          <div>
            <h4 style="margin:0;">${r.solver}</h4>
            <p class="muted" style="margin:2px 0;">Objective: <b>${Number(r.best.objective).toFixed(2)}</b> · Runtime: <b>${r.runtime_s} s</b></p>
          </div>
          <span class="badge ${r.best.feasible ? 'badge-success' : 'badge-danger'}">${r.best.feasible ? 'FEASIBLE' : 'INFEASIBLE'}</span>
        </div>
        <div id="sched-${k}"></div>
      </div>`;
    }
    if(multiContainer) multiContainer.innerHTML = mHtml;
    for(const [k, r] of completedSolvers){
      renderScheduleTable(instance, r.best, `sched-${k}`);
    }
  } else {
    if(singleGrid) singleGrid.style.display = 'grid';
    if(multiSchedCard) multiSchedCard.style.display = 'none';
    renderScheduleTable(instance, s, 'schedule');
  }

  // 4. Grid Performance Section
  const T = instance.n_t;
  const caps = instance.grid_cap || Array(T).fill(1);

  if(isMulti){
    // Calculate global maximum for scaling across all completed solvers + grid limits
    const allLoads = completedSolvers.flatMap(([k, r]) => r.best?.load || []);
    const maxVal = Math.max(...caps, ...allLoads, 1);
    const scale = 140 / maxVal;

    // Multi-solver load legend
    const legendHtml = completedSolvers.map(([k, r]) => `<i class="actual bar-${k}"></i> ${r.solver} Load`).join(' ') + ` <i class="capacity"></i> Grid Capacity`;
    $('#loadLegend').innerHTML = legendHtml;

    // Multi-solver load chart bars
    $('#loadChart').innerHTML = Array.from({length: T}, (_, t) => `
      <div class="barpair">
        ${completedSolvers.map(([k, r]) => {
          const l = r.best?.load?.[t] ?? 0;
          return `<div class="bar bar-${k}" style="height:${Math.max(4, l * scale)}px" title="${r.solver} Load: ${l}"></div>`;
        }).join('')}
        <div class="cap" style="height:${Math.max(4, (caps[t] || 1) * scale)}px" title="Capacity: ${caps[t]}"></div>
        <label>T${t+1}</label>
      </div>
    `).join('');

    // Comparative load table
    const gridHeaders = ['Time Slot', ...completedSolvers.map(([k, r]) => `${r.solver} Load`), 'Grid Limit', 'Status'];
    const gridRows = Array.from({length: T}, (_, t) => {
      const isAnyOver = completedSolvers.some(([k, r]) => (r.best?.load?.[t] ?? 0) > (caps[t] || 1));
      return [
        `T${t+1}`,
        ...completedSolvers.map(([k, r]) => r.best?.load?.[t] ?? 0),
        caps[t],
        isAnyOver ? '<span class="badge badge-danger">Exceeded</span>' : '<span class="badge badge-success">OK</span>'
      ];
    });
    $('#gridProfileTable').innerHTML = table(gridHeaders, gridRows);

    // Grid performance metrics for primary run (or SA if present)
    renderGridMetrics(instance, (results.sa?.best || s));
  } else {
    // Single solver load chart
    const activeLoad = s.load || Array(T).fill(0);
    const maxVal = Math.max(...caps, ...activeLoad, 1);
    const scale = 140 / maxVal;
    const barCls = primaryRun.solver_key === 'qaoa' ? 'bar-qaoa' : (primaryRun.solver_key === 'exact' ? 'bar-exact' : 'bar-sa');

    $('#loadLegend').innerHTML = `<i class="actual ${barCls}"></i> Actual Load <i class="capacity"></i> Grid Capacity`;
    $('#loadChart').innerHTML = activeLoad.map((v, i) => `
      <div class="barpair">
        <div class="bar ${barCls}" style="height:${Math.max(4, v * scale)}px" title="Load: ${v}"></div>
        <div class="cap" style="height:${Math.max(4, (caps[i] || 1) * scale)}px" title="Capacity: ${caps[i]}"></div>
        <label>T${i+1}</label>
      </div>
    `).join('');
    $('#gridProfileTable').innerHTML = '';
    renderGridMetrics(instance, s);
  }

  // 5. Cost Breakdown Section
  if(isMulti){
    // Find maximum cost across all solvers and cost components for uniform bar scaling
    const allCostVals = [];
    completedSolvers.forEach(([k, r]) => {
      if(r.best?.cost_breakdown){
        allCostVals.push(...Object.values(r.best.cost_breakdown));
      }
    });
    const maxCost = Math.max(...allCostVals, 1.0);

    let costHtml = '';
    completedSolvers.forEach(([k, r], idx) => {
      const c = r.best?.cost_breakdown || {};
      const isFirst = idx === 0;
      costHtml += `
        <div style="margin:${isFirst?'0 0 8px':'18px 0 8px'};padding-top:${isFirst?'0':'12px'};border-top:${isFirst?'none':'1px solid #d8e5ee'};display:flex;justify-content:space-between;align-items:center;">
          <h4 style="margin:0;font-size:14px;">${r.solver}</h4>
          <span class="badge ${r.best?.feasible ? 'badge-success' : 'badge-danger'}">${r.best?.feasible ? 'FEASIBLE' : 'INFEASIBLE'}</span>
        </div>
      `;
      for(const [cKey, cVal] of Object.entries(c)){
        const label = cKey.replace(/_/g, ' ');
        const barWidth = Math.max(2, (cVal / maxCost) * 70);
        costHtml += `
          <div><span>${label}</span><i class="bar-${k}" style="width:${barWidth}%"></i><b>${Number(cVal).toFixed(2)}</b></div>
        `;
      }
      costHtml += `
        <p style="margin:6px 0 10px;text-align:right;font-size:13px;"><b>Total / Objective: ${r.best?.objective !== undefined ? Number(r.best.objective).toFixed(2) : 'N/A'}</b></p>
      `;
    });
    $('#costChart').innerHTML = costHtml;
    const costSum = $('#costSummary');
    if(costSum) costSum.style.display = 'none';
  } else {
    // Single Solver Cost Breakdown
    const costSum = $('#costSummary');
    if(costSum) costSum.style.display = 'block';
    const c = s.cost_breakdown || {};
    const maxCost = Math.max(...Object.values(c), 1.0);
    const barCls = primaryRun.solver_key === 'qaoa' ? 'bar-qaoa' : (primaryRun.solver_key === 'exact' ? 'bar-exact' : 'bar-sa');
    $('#costChart').innerHTML = Object.entries(c).map(([k, v]) => `
      <div><span>${k.replace(/_/g, ' ')}</span><i class="${barCls}" style="width:${Math.max(2, (v / maxCost) * 70)}%"></i><b>${Number(v).toFixed(2)}</b></div>
    `).join('');
    if(costSum) costSum.innerHTML = `<b>Total: ${s.objective !== undefined ? Number(s.objective).toFixed(2) : 'N/A'}</b> <span class="muted">${isDemo ? 'Precomputed demo reference' : `Live solver result (${primaryRun.solver})`}</span>`;
  }

  // 6. Quantum Resource Analysis Section (Show ONLY if QAOA was evaluated or attempted)
  const qResCard = $('#quantumResourcesCard');
  if(qResCard){
    const qData = results.qaoa || (primaryRun.solver_key === 'qaoa' ? primaryRun : null);
    if(qData && (qData.status === 'completed' || qData.status === 'unsupported_size' || qData.resources)){
      qResCard.style.display = 'block';
      const qRes = qData.resources || {};
      const qMet = qData.metrics || {};
      const isEst = qRes.is_estimated === true || qData.status === 'unsupported_size';

      $('#quantumTag').textContent = isEst ? 'Quantum Resource Estimation (Static)' : 'Measured Qiskit Aer Execution';
      $('#quantumTag').className = isEst ? 'tag' : 'tag live';
      $('#quantumResourceSubtitle').textContent = isEst
        ? 'Calculated Hamiltonian and circuit scaling requirements (simulation bypassed due to size)'
        : 'Exact quantum circuit metrics measured from Qiskit Aer circuit simulation';

      let qHtml = `
        <div class="quantum-resource-grid">
          <div><b>${qRes.qubits ?? instance.n_qubits}</b><span>Logical Qubits</span></div>
          <div><b>${qMet.p ?? 1}</b><span>QAOA Depth (p)</span></div>
          <div><b>${qRes.depth ?? 'N/A'}</b><span>Circuit Depth</span></div>
          <div><b>${qRes.transpiled_depth ?? 'N/A'}</b><span>Transpiled Depth</span></div>
          <div><b>${qRes.total_gates ?? 'N/A'}</b><span>Total Gates</span></div>
          <div><b>${qRes.two_qubit_gates ?? 'N/A'}</b><span>2-Qubit Gates</span></div>
          <div><b>${qRes.transpiled_cx_gates ?? 'N/A'}</b><span>Transpiled CX</span></div>
          <div><b>${qMet.shots ?? 512}</b><span>Shots</span></div>
          <div><b>${qMet.evaluations ?? 0}</b><span>Optimizer Evaluations</span></div>
          <div><b>${qRes.hamiltonian_terms ?? 'N/A'}</b><span>Hamiltonian Terms</span></div>
        </div>
      `;

      if(qMet.optimal_parameters){
        const g = qMet.optimal_parameters.gamma?.join(', ') || 'N/A';
        const b = qMet.optimal_parameters.beta?.join(', ') || 'N/A';
        qHtml += `<p class="muted" style="margin-top:8px;">Optimal parameters: γ = [${g}], β = [${b}] · Optimizer: <b>${qMet.optimizer || 'COBYLA'}</b></p>`;
      }
      $('#quantumResourceContent').innerHTML = qHtml;
    } else {
      qResCard.style.display = 'none';
    }
  }

  // 7. Multi-Solver Comparison Section (Show only in multi-solver mode when 2+ rows exist)
  const cmpCard = $('#resultComparison');
  if(cmpCard){
    const cmpData = run.comparison;
    if(isMulti && cmpData && cmpData.has_comparison && cmpData.rows && cmpData.rows.length >= 2){
      cmpCard.style.display = 'block';
      $('#resultCompareTable').innerHTML = table(
        ['Solver', 'Objective', 'Feasible', 'Stations Open', 'Electricity', 'Detour', 'Infra', 'Grid Stress', 'Runtime', 'Evaluations', 'Optimality Gap'],
        cmpData.rows.map(r => {
          const sOpen = results[r.solver_key]?.best?.stations_open;
          const openStr = sOpen ? `${sOpen.filter(Boolean).length} / ${instance.n_st}` : 'N/A';
          return [
            `<b>${r.solver}</b>`,
            `<b>${Number(r.objective).toFixed(2)}</b>`,
            r.feasible ? '<span class="badge badge-success">Yes</span>' : '<span class="badge badge-danger">No</span>',
            openStr,
            `$${Number(r.electricity_cost).toFixed(2)}`,
            `$${Number(r.detour_cost).toFixed(2)}`,
            `$${Number(r.infrastructure_cost).toFixed(2)}`,
            Number(r.grid_stress).toFixed(2),
            `${r.runtime_s} s`,
            r.evaluations,
            r.optimality_gap || '0.0%'
          ];
        })
      );

      // Comparative bars
      const maxObj = Math.max(...cmpData.rows.map(r=>r.objective || 1), 1.0);
      $('#resCompareObjBars').innerHTML = cmpData.rows.map(r=>`
        <div><span>${r.solver}</span><i class="bar-${r.solver_key}" style="width:${Math.max(12, (r.objective/maxObj)*80)}%">${Number(r.objective).toFixed(2)}</i></div>
      `).join('');

      const maxTime = Math.max(...cmpData.rows.map(r=>r.runtime_s || 0.01), 0.01);
      $('#resCompareTimeBars').innerHTML = cmpData.rows.map(r=>`
        <div><span>${r.solver}</span><i class="bar-${r.solver_key}" style="width:${Math.max(12, (r.runtime_s/maxTime)*80)}%">${Number(r.runtime_s).toFixed(3)} s</i></div>
      `).join('');
    } else {
      cmpCard.style.display = 'none';
    }
  }
}

function resultView(data){
  renderResults(data);
}

let allInstancesMap = {};
let builtInPresets = [];
let customInstances = [];

function getStoredProblemId(){
  try{ return localStorage.getItem('selectedProblemId'); }catch(e){ return null; }
}

function setStoredProblemId(id){
  try{
    if(id) localStorage.setItem('selectedProblemId', id);
    else localStorage.removeItem('selectedProblemId');
  }catch(e){}
}

function updateProblemActionsState(){
  if(!instance) return;
  const isBuiltin = builtInPresets.some(p => p.id === instance.id);
  const delBtn = $('#deleteProblemBtn');
  if(delBtn){
    delBtn.disabled = isBuiltin;
    delBtn.title = isBuiltin ? "Built-in presets cannot be deleted" : `Delete "${instance.name}"`;
  }
}

async function loadInstances(targetId = null){
  const res = await api('/api/presets');
  builtInPresets = res.presets || [];
  customInstances = res.custom || [];
  allInstancesMap = {};

  builtInPresets.forEach(p => { allInstancesMap[p.id] = p; });
  customInstances.forEach(c => { allInstancesMap[c.id] = c; });

  let html = '<optgroup label="Built-in Presets">';
  builtInPresets.forEach(p => {
    html += `<option value="${p.id}">${p.name}</option>`;
  });
  html += '</optgroup>';

  if(customInstances.length > 0){
    html += '<optgroup label="Custom Problems">';
    customInstances.forEach(c => {
      html += `<option value="${c.id}">${c.name}</option>`;
    });
    html += '</optgroup>';
  }

  $('#preset').innerHTML = html;

  const storedId = getStoredProblemId();
  const desiredId = targetId || (storedId && allInstancesMap[storedId] ? storedId : (instance && allInstancesMap[instance.id] ? instance.id : builtInPresets[0]?.id));
  if(desiredId && allInstancesMap[desiredId]){
    instance = allInstancesMap[desiredId];
    $('#preset').value = desiredId;
    setStoredProblemId(desiredId);
  } else if(builtInPresets.length > 0){
    instance = builtInPresets[0];
    $('#preset').value = instance.id;
    setStoredProblemId(instance.id);
  }

  updateProblemActionsState();
  renderSetup();
}

async function initialize(){
  try{
    await loadInstances();

    $('#preset').onchange = () => {
      const v = $('#preset').value;
      if(allInstancesMap[v]){
        instance = allInstancesMap[v];
        setStoredProblemId(v);
        updateProblemActionsState();
        renderSetup();
        toast(`Loaded problem: ${instance.name}`);
      }
      lastRun = null;
      clearResultsDisplay();
      const resTab = $('#tabs [data-tab=result]');
      if(resTab) resTab.disabled = true;
      const job = $('#job');
      if(job){
        job.className = 'job';
        job.innerHTML = `Status: <b>Ready</b><span> Problem instance changed. Click "Run Optimization" on the Solve tab.</span>`;
      }
    };

    // Solver Card Checkbox interactions
    ['sa', 'qaoa', 'exact'].forEach(sKey => {
      const card = $(`#card-${sKey}`);
      const chk = $(`#chk-${sKey}`);
      if(chk){
        chk.onchange = (e) => {
          e.stopPropagation();
          if(chk.disabled) return;
          if(chk.checked){
            selectedSolvers.add(sKey);
            card?.classList.add('selected');
          } else {
            selectedSolvers.delete(sKey);
            card?.classList.remove('selected');
          }
          // Ensure at least one solver is selected
          if(selectedSolvers.size === 0){
            selectedSolvers.add(sKey);
            chk.checked = true;
            card?.classList.add('selected');
            toast('At least one solver must remain selected.');
          }
          renderSolverControls();
        };
      }
      if(card){
        card.onclick = (e) => {
          if(e.target.tagName === 'INPUT') return;
          if(chk && !chk.disabled){
            chk.checked = !chk.checked;
            chk.dispatchEvent(new Event('change'));
          }
        };
      }
    });

    renderSolverControls();

    const baselineData = await api('/api/results/baseline');
    renderResults(baselineData);

    await loadIbmScalingData();

  }catch(e){
    toast('Local backend server offline. Please run "python -m server"');
  }
}

// Attach event listeners
$('#customEVs').oninput = makeCustomProblem;
$('#customStations').oninput = makeCustomProblem;
$('#customSlots').oninput = makeCustomProblem;
$('#createProblemBtn').onclick = makeCustomProblem;
$('#customForms').oninput = validateCustom;

// Add Problem button handler
const addProblemBtn = $('#addProblemBtn');
if(addProblemBtn){
  addProblemBtn.onclick = () => {
    $('#customBuilder').hidden = false;
    makeCustomProblem();
    $('#customBuilder').scrollIntoView({ behavior: 'smooth' });
    toast('Define custom problem parameters and click "Save Problem".');
  };
}

// Delete Problem button handler
const deleteProblemBtn = $('#deleteProblemBtn');
if(deleteProblemBtn){
  deleteProblemBtn.onclick = async () => {
    if(!instance) return;
    const isBuiltin = builtInPresets.some(p => p.id === instance.id);
    if(isBuiltin){
      toast('Built-in presets cannot be deleted.');
      return;
    }
    const confirmed = window.confirm(`Are you sure you want to delete problem "${instance.name}"?\nThis cannot be undone.`);
    if(!confirmed) return;

    try{
      const r = await fetch(`/api/instances/${instance.id}`, { method: 'DELETE' });
      if(!r.ok){
        const err = await r.json();
        throw Error(err.error || 'Failed to delete problem');
      }
      toast(`Problem "${instance.name}" deleted.`);
      setStoredProblemId('baseline-3x2x4');
      await loadInstances('baseline-3x2x4');
    }catch(e){
      toast('Error deleting problem: ' + e.message);
    }
  };
}

// Save Custom Problem handler
const saveCustomBtn = $('#saveCustomBtn');
if(saveCustomBtn){
  saveCustomBtn.onclick = async () => {
    const { errors, data } = collectCustom();
    if(errors.length){
      $('#customErrors').innerHTML = errors.map(x => `<div>⚠ ${x}</div>`).join('');
      return;
    }
    try{
      const r = await fetch('/api/instances', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
      });
      if(!r.ok){
        const err = await r.json();
        throw Error(err.error || 'Failed to save custom problem');
      }
      const savedInstance = await r.json();
      $('#customBuilder').hidden = true;
      setStoredProblemId(savedInstance.id);
      await loadInstances(savedInstance.id);
      lastRun = null;
      clearResultsDisplay();
      $('#tabs [data-tab=result]').disabled = true;
      toast(`Problem saved! Ready to Build Model (${savedInstance.n_qubits} QUBO variables).`);
    }catch(e){
      $('#customErrors').textContent = e.message;
      toast('Error saving problem: ' + e.message);
    }
  };
}

// Cancel Custom Problem handler
const cancelCustomBtn = $('#cancelCustomBtn');
if(cancelCustomBtn){
  cancelCustomBtn.onclick = () => {
    $('#customBuilder').hidden = true;
    $('#customErrors').textContent = '';
  };
}

// Build Model handler
$('#buildCustomBtn').onclick = async () => {
  if($('#saveCustomBtn') && !$('#saveCustomBtn').disabled){
    await $('#saveCustomBtn').click();
    show('model');
  }
};

$('#baselineBtn').onclick = () => {
  if(allInstancesMap['baseline-3x2x4']){
    setStoredProblemId('baseline-3x2x4');
    $('#preset').value = 'baseline-3x2x4';
    $('#preset').dispatchEvent(new Event('change'));
  }
};

$('#resetBtn').onclick = () => { location.reload(); };

const generateBtn = $('#generateBtn');
if(generateBtn){
  generateBtn.onclick = () => {
    $('#addProblemBtn')?.click();
  };
}

$('#toModel').onclick = () => {
  if(!instance){
    toast('Please select or create a problem instance first.');
    return;
  }
  updateModelTab(instance);
  toast(`Model formulation built for ${instance.name} (${instance.n_qubits || getQUBOVariableCount(instance)} variables).`);
  show('model');
};

// Model Tab Continue to Solve Button
const modelToSolveBtn = $('#modelToSolveBtn');
if(modelToSolveBtn){
  modelToSolveBtn.onclick = () => {
    if(!instance){
      toast('Model formulation not ready. Please select or build a problem first.');
      return;
    }
    show('solve');
    toast('Navigated to Solve tab.');
  };
}

$$('#tabs button').forEach(b => b.onclick = () => {
  if(b.disabled) return;
  const tab = b.dataset.tab;
  if(tab === 'result' && !lastRun){
    toast('No optimization results available for the active instance. Run optimization first.');
    return;
  }
  show(tab);
});

// Export JSON button handler
const exportBtn = $('#exportBtn');
if(exportBtn){
  exportBtn.onclick = () => {
    if(!lastRun){
      toast('No run result available to export.');
      return;
    }
    const blob = new Blob([JSON.stringify(lastRun, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `ev-optimization-${lastRun.run_id || 'result'}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    toast('Exported run result to JSON');
  };
}

$('#runBtn').onclick=async()=>{
  const job=$('#job');
  job.className='job running';
  const solverNames = Array.from(selectedSolvers).map(s=>s.toUpperCase()).join(' + ');
  job.innerHTML=`Status: <b>Optimizing</b><span> Evaluating binary QUBO formulation with ${solverNames}…</span>`;
  $('#runBtn').disabled=true;

  try{
    const payload = collectSolverPayload();
    const r=await fetch(`/api/instances/${instance.id}/runs`,{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify(payload)
    });
    if(!r.ok){
      const err = await r.json();
      throw Error(err.error||'Optimization run failed');
    }
    const runResult = await r.json();
    renderResults(runResult);
    $('#tabs [data-tab=result]').disabled=false;
    job.className='job done';
    job.innerHTML=`Status: <b>Completed</b><span> Optimization completed for ${solverNames}.</span>`;
    toast('Optimization complete — viewing decoded solution');
    show('result');
  }catch(e){
    job.className='job';
    job.innerHTML=`Status: <b>Error</b><span> ${e.message}</span>`;
    toast('Error during optimization: '+e.message);
  }finally{
    $('#runBtn').disabled=false;
  }
};

// ==========================================
// ==========================================
// Scaling & IBM Hardware Tab Logic
// ==========================================
let ibmScalingDataLoaded = false;
let ibmAllInstances = [];

function renderScalingSvgLineGraph(containerId, xVals, seriesList, xLabel, yLabel, isInt=true){
  const el = $(`#${containerId}`);
  if(!el) return;
  
  const w = 380;
  const h = 210;
  const padL = 45;
  const padR = 20;
  const padT = 20;
  const padB = 40;
  const plotW = w - padL - padR;
  const plotH = h - padT - padB;

  const minX = Math.min(...xVals);
  const maxX = Math.max(...xVals);
  const spanX = Math.max(1, maxX - minX);

  let maxY = 0;
  seriesList.forEach(s => {
    const sMax = Math.max(...s.values);
    if(sMax > maxY) maxY = sMax;
  });
  maxY = Math.max(maxY * 1.1, 10);

  const getX = (val) => padL + ((val - minX) / spanX) * plotW;
  const getY = (val) => padT + plotH - (val / maxY) * plotH;

  // Horizontal grid lines (4 ticks)
  let gridSvg = '';
  const yTicks = 4;
  for(let i = 0; i <= yTicks; i++){
    const yVal = (maxY / yTicks) * i;
    const yPos = getY(yVal);
    const labelVal = isInt ? (yVal >= 1000 ? (yVal/1000).toFixed(1) + 'k' : Math.round(yVal)) : yVal.toFixed(1);
    gridSvg += `
      <line x1="${padL}" y1="${yPos}" x2="${w - padR}" y2="${yPos}" stroke="#e2e8f0" stroke-width="1" stroke-dasharray="3,3" />
      <text x="${padL - 6}" y="${yPos + 3}" fill="#64748b" font-size="10" text-anchor="end">${labelVal}</text>
    `;
  }

  // X ticks at data points
  let xTicksSvg = '';
  xVals.forEach((x, idx) => {
    const xPos = getX(x);
    xTicksSvg += `
      <line x1="${xPos}" y1="${padT + plotH}" x2="${xPos}" y2="${padT + plotH + 4}" stroke="#94a3b8" stroke-width="1" />
      <text x="${xPos}" y="${padT + plotH + 15}" fill="#64748b" font-size="10" text-anchor="middle">${x}</text>
    `;
  });

  // Series paths and points
  let seriesSvg = '';
  seriesList.forEach(s => {
    const points = xVals.map((x, idx) => `${getX(x).toFixed(1)},${getY(s.values[idx]).toFixed(1)}`).join(' ');
    seriesSvg += `
      <polyline fill="none" stroke="${s.color}" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round" points="${points}" />
    `;
    xVals.forEach((x, idx) => {
      const px = getX(x).toFixed(1);
      const py = getY(s.values[idx]).toFixed(1);
      const v = s.values[idx];
      seriesSvg += `
        <circle cx="${px}" cy="${py}" r="4" fill="#ffffff" stroke="${s.color}" stroke-width="2.5">
          <title>${s.name}: ${v} (X = ${x})</title>
        </circle>
      `;
    });
  });

  // Axis lines and titles
  const axesSvg = `
    <line x1="${padL}" y1="${padT}" x2="${padL}" y2="${padT + plotH}" stroke="#94a3b8" stroke-width="1.5" />
    <line x1="${padL}" y1="${padT + plotH}" x2="${w - padR}" y2="${padT + plotH}" stroke="#94a3b8" stroke-width="1.5" />
    <text x="${padL + plotW / 2}" y="${h - 6}" fill="#475569" font-size="11" font-weight="600" text-anchor="middle">${xLabel}</text>
    <text transform="rotate(-90)" x="${-(padT + plotH / 2)}" y="12" fill="#475569" font-size="10.5" font-weight="600" text-anchor="middle">${yLabel}</text>
  `;

  el.innerHTML = `
    <svg viewBox="0 0 ${w} ${h}" style="width:100%;height:auto;display:block;overflow:visible;">
      ${gridSvg}
      ${xTicksSvg}
      ${seriesSvg}
      ${axesSvg}
    </svg>
  `;
}

function renderResCompareBar(containerId, label1, val1, label2, val2, class1='bar-aer', class2='bar-ibm'){
  const maxV = Math.max(val1, val2, 1);
  const w1 = Math.max(12, Math.round((val1 / maxV) * 80));
  const w2 = Math.max(12, Math.round((val2 / maxV) * 80));
  const el = $(`#${containerId}`);
  if(el){
    el.innerHTML = `
      <div><span>${label1}</span><i class="${class1}" style="width:${w1}%;border-radius:3px;">${val1}</i></div>
      <div><span>${label2}</span><i class="${class2}" style="width:${w2}%;border-radius:3px;">${val2}</i></div>
    `;
  }
}

function updateIbmProblemMetadata(instData){
  if(!instData) return;
  const dimsEl = $('#ibmMetaDims');
  if(dimsEl) dimsEl.textContent = `${instData.evs || 2} EV × ${instData.stations || 2} St × ${instData.time_slots || 2} T`;
  const qEl = $('#ibmMetaQubits');
  if(qEl) qEl.textContent = instData.logical_qubits || '—';
  const bkEl = $('#ibmMetaBackend');
  if(bkEl) bkEl.textContent = instData.backend || instData.ibm?.backend_label || 'ibm_fez';
  const shEl = $('#ibmMetaShots');
  if(shEl) shEl.textContent = `${instData.shots || 2048} (p=${instData.qaoa_p || instData.p || 2})`;
  const depthEl = $('#ibmMetaDepth');
  if(depthEl) depthEl.textContent = instData.transpiled_depth ?? instData.ibm?.transpiled_depth ?? '—';
  const g2El = $('#ibmMeta2QGates');
  if(g2El) g2El.textContent = instData.two_qubit_gates ?? instData.ibm?.two_qubit_gates ?? '—';
  const bfEl = $('#ibmMetaBestFeasible');
  if(bfEl){
    const v = instData.best_feasible_obj;
    bfEl.textContent = (typeof v === 'number') ? `$${v.toFixed(2)}` : (v ?? '—');
  }
  const fpEl = $('#ibmMetaFeasibleProb');
  if(fpEl){
    const p = instData.feasible_prob;
    fpEl.textContent = (typeof p === 'number') ? `${(p * 100).toFixed(2)}%` : (p ?? '—');
  }
}

function renderIbmStationPlacement(prob, sol, stListId, valBoxId, violBoxId){
  const stList = $(`#${stListId}`);
  if(stList){
    let stHtml = '';
    (sol?.stations_open || []).forEach((isOpen, idx) => {
      const cost = prob?.open_cost?.[idx] ?? 1.0;
      stHtml += `<p><b>Station ${idx+1} — <span class="${isOpen?'green':'muted'}">${isOpen?'OPEN':'CLOSED'}</span></b> <span class="right">Cost: $${isOpen?Number(cost).toFixed(1):'0.0'}</span></p>`;
    });
    stList.innerHTML = stHtml || '<p class="muted">No station data available.</p>';
  }

  const vBox = $(`#${valBoxId}`);
  const violBox = $(`#${violBoxId}`);
  if(vBox){
    if(sol?.feasible){
      vBox.innerHTML = `
        ✓ Charging demand satisfied (${prob?.n_ev || 2} EVs)<br>
        ✓ Time windows satisfied<br>
        ✓ Station capacity satisfied (≤ 1 EV/charger)<br>
        ✓ Grid capacity satisfied<br>
        ✓ Station-opening coupling satisfied
      `;
      vBox.className = 'checks';
      if(violBox) violBox.style.display = 'none';
    } else {
      vBox.innerHTML = '<span class="muted">Validation detected constraint violations:</span>';
      vBox.className = 'checks';
      if(violBox){
        violBox.style.display = 'block';
        const viols = (sol?.violations && sol.violations.length) ? sol.violations : ['Constraint violations / infeasible assignments'];
        violBox.innerHTML = `<b>Constraint Violations:</b>${viols.map(v => `<div>⚠ ${v}</div>`).join('')}`;
      }
    }
  }
}

function renderIbmGridPerformance(prob, sol, chartId, tableId, barClass){
  const T = prob?.n_t || 2;
  const caps = prob?.grid_cap || Array(T).fill(1);
  const activeLoad = sol?.load || Array(T).fill(0);
  const maxVal = Math.max(...caps, ...activeLoad, 1);
  const scale = 110 / maxVal;

  const chartEl = $(`#${chartId}`);
  if(chartEl){
    chartEl.innerHTML = activeLoad.map((v, i) => `
      <div class="barpair">
        <div class="bar ${barClass}" style="height:${Math.max(4, v * scale)}px" title="Load: ${v}"></div>
        <div class="cap" style="height:${Math.max(4, (caps[i] || 1) * scale)}px" title="Capacity: ${caps[i]}"></div>
        <label>T${i+1}</label>
      </div>
    `).join('');
  }

  const profileEl = $(`#${tableId}`);
  if(profileEl){
    const gridHeaders = ['Time Slot', 'Actual Load', 'Grid Limit', 'Utilization', 'Electricity Price', 'Status'];
    const gridRows = Array.from({length: T}, (_, t) => {
      const l = activeLoad[t] ?? 0;
      const cap = caps[t] || 1;
      const isOver = l > cap;
      const util = ((l / cap) * 100).toFixed(1) + '%';
      const price = '$' + Number(prob?.price?.[t] ?? 1.0).toFixed(2);
      return [
        `T${t+1}`,
        l,
        cap,
        util,
        price,
        isOver ? '<span class="badge badge-danger">Exceeded</span>' : '<span class="badge badge-success">OK</span>'
      ];
    });
    profileEl.innerHTML = table(gridHeaders, gridRows);
  }
}

function renderIbmCostBreakdown(sol, chartId, summaryId, barClass, titlePrefix){
  const chartEl = $(`#${chartId}`);
  const sumEl = $(`#${summaryId}`);
  const c = sol?.cost_breakdown || {};
  const maxCost = Math.max(...Object.values(c), 1.0);

  if(chartEl){
    chartEl.innerHTML = Object.entries(c).map(([k, v]) => `
      <div><span>${k.replace(/_/g, ' ')}</span><i class="${barClass}" style="width:${Math.max(2, (v / maxCost) * 70)}%"></i><b>$${Number(v).toFixed(2)}</b></div>
    `).join('');
  }

  if(sumEl){
    const objVal = (sol?.objective !== undefined && sol?.objective !== null) ? `$${Number(sol.objective).toFixed(2)}` : 'N/A';
    sumEl.innerHTML = `<b>Total Objective: ${objVal}</b> <span class="muted">(${titlePrefix})</span>`;
  }
}

function renderIbmHardwareExecution(payload){
  if(!payload) return;
  const prob = payload.problem;
  const meta = payload.metadata || {};
  const isLive = payload.source === 'live';

  // 1. Source Tag
  const tagEl = $('#ibmSourceTag');
  if(tagEl){
    tagEl.className = isLive ? 'tag live' : 'tag tag-warn';
    tagEl.textContent = payload.source_label || (isLive ? 'LIVE IBM HARDWARE RESULT' : 'PRECOMPUTED IBM HARDWARE RESULT');
  }

  // 2. Metadata Summary Card
  updateIbmProblemMetadata({
    evs: meta.evs || prob?.n_ev,
    stations: meta.stations || prob?.n_st,
    time_slots: meta.time_slots || prob?.n_t,
    logical_qubits: meta.logical_qubits || prob?.n_qubits,
    shots: meta.shots,
    qaoa_p: meta.qaoa_p,
    backend: meta.backend,
    transpiled_depth: meta.transpiled_depth,
    two_qubit_gates: meta.two_qubit_gates,
    best_feasible_obj: meta.best_feasible_obj,
    feasible_prob: meta.feasible_prob,
    ibm: payload.ibm_resources,
    aer: payload.aer_resources
  });

  // 3. Left Column: Qiskit Aer Simulator
  const aerNoticeEl = $('#aerUnsupportedNotice');
  const aerContentEl = $('#aerResultsContent');
  const aerBadgeEl = $('#aerFeasibilityBadge');
  const aerSol = payload.aer_solution;
  const isAerUnsupported = (!aerSol && ((prob?.n_qubits || meta.logical_qubits) > 24)) || (aerSol && aerSol.status === 'unsupported_size') || ((prob?.n_qubits || meta.logical_qubits) > 24);

  if(isAerUnsupported){
    if(aerNoticeEl) aerNoticeEl.style.display = 'block';
    const qCountEl = $('#aerUnsupportedQubits');
    if(qCountEl) qCountEl.textContent = prob?.n_qubits || meta.logical_qubits || 30;
    if(aerContentEl) aerContentEl.style.display = 'none';
    if(aerBadgeEl){
      aerBadgeEl.className = 'badge badge-warn';
      aerBadgeEl.textContent = 'Out of Resources (N > 24)';
    }
  } else if(aerSol) {
    if(aerNoticeEl) aerNoticeEl.style.display = 'none';
    if(aerContentEl) aerContentEl.style.display = 'block';
    if(aerBadgeEl){
      aerBadgeEl.className = aerSol.feasible ? 'badge badge-success' : 'badge badge-danger';
      aerBadgeEl.textContent = aerSol.feasible ? '✓ Feasible' : '✕ Infeasible';
    }
    renderIbmStationPlacement(prob, aerSol, 'aerStationsList', 'aerValidationBox', 'aerViolationsBox');
    renderScheduleTable(prob, aerSol, 'aerSchedule');
    renderIbmGridPerformance(prob, aerSol, 'aerLoadChart', 'aerGridProfileTable', 'bar-aer');
    renderGridMetrics(prob, aerSol, 'aerGridMetrics');
    renderIbmCostBreakdown(aerSol, 'aerCostChart', 'aerCostSummary', 'bar-aer', 'Aer Simulation');
  }

  // 4. Right Column: IBM Quantum Hardware
  const ibmBadgeEl = $('#ibmFeasibilityBadge');
  const ibmSubLabelEl = $('#ibmHardwareSubLabel');
  const ibmSol = payload.result || payload.best_observed || {};

  if(ibmSubLabelEl){
    ibmSubLabelEl.textContent = isLive ? `Real Hardware Execution (${meta.backend || 'ibm_fez'})` : `Hardware Architecture (${meta.backend || 'ibm_fez'})`;
  }
  if(ibmBadgeEl){
    ibmBadgeEl.className = ibmSol.feasible ? 'badge badge-success' : 'badge badge-danger';
    ibmBadgeEl.textContent = ibmSol.feasible ? '✓ Feasible' : '✕ Infeasible';
  }
  renderIbmStationPlacement(prob, ibmSol, 'ibmStationsList', 'ibmValidationBox', 'ibmViolationsBox');
  renderScheduleTable(prob, ibmSol, 'ibmSchedule');
  renderIbmGridPerformance(prob, ibmSol, 'ibmLoadChart', 'ibmGridProfileTable', 'bar-ibm');
  renderGridMetrics(prob, ibmSol, 'ibmGridMetrics');
  renderIbmCostBreakdown(ibmSol, 'ibmCostChart', 'ibmCostSummary', 'bar-ibm', 'IBM Hardware');

  // 5. Quantum Resource Comparison (Selected Problem)
  const aer = payload.aer_resources || {};
  const ibm = payload.ibm_resources || {};
  const logQ = aer.logical_qubits || prob?.n_qubits || meta.logical_qubits || 10;
  const physReq = ibm.physical_qubits_required || logQ;

  renderResCompareBar('resBarQubits', 'Logical Qubits', logQ, 'Physical Required', physReq, 'bar-aer', 'bar-ibm');
  renderResCompareBar('resBarGates', 'Aer Total Gates', aer.total_gates || 0, 'IBM Transpiled', ibm.total_gates || 0, 'bar-aer', 'bar-ibm');
  renderResCompareBar('resBar2Q', 'Aer 2Q (Rzz)', aer.two_qubit_gates || 0, 'IBM CX Gates', ibm.two_qubit_gates || 0, 'bar-aer', 'bar-ibm');
  renderResCompareBar('resBarDepth', 'Aer Depth', aer.circuit_depth || 0, 'IBM Transpiled', ibm.transpiled_depth || 0, 'bar-aer', 'bar-ibm');

  const capBadge = $('#ibmDeviceCapacityBadge');
  if(capBadge && ibm.device_capacity){
    capBadge.textContent = `Target Device: ${ibm.device_capacity} Physical Qubits (${ibm.backend_label || ibm.backend || meta.backend || 'ibm_fez'})`;
  }
}

const LIVE_IBM_INSTANCES = new Set([
  'instance-a-2x2x2',
  'small-2x2x2',
  'custom-1791428968536',
  'demo-inst-1'
]);

function normalizeLiveIbmId(id){
  if(id === 'small-2x2x2' || id === 'demo-inst-1') return 'instance-a-2x2x2';
  return id;
}

async function displayIbmHardwareProblem(instId){
  const canonId = normalizeLiveIbmId(instId);
  const isSupported = LIVE_IBM_INSTANCES.has(instId) || LIVE_IBM_INSTANCES.has(canonId);

  const demoNoticeEl = $('#ibmDemoNotice');
  const errorEl = $('#ibmHardwareError');
  const errorMsgEl = $('#ibmHardwareErrorMsg');
  const tagEl = $('#ibmSourceTag');
  const runBtn = $('#runIbmHardwareBtn');

  if(errorEl) errorEl.style.display = 'none';

  const pSelect = $('#ibmPSelect');
  const shotsSelect = $('#ibmShotsSelect');
  const pVal = pSelect ? parseInt(pSelect.value, 10) : 2;
  const shotsVal = shotsSelect ? parseInt(shotsSelect.value, 10) : 2048;

  if(!isSupported){
    // DEMO mode for curated problems 2-6
    if(demoNoticeEl) demoNoticeEl.style.display = 'block';
    if(tagEl){
      tagEl.className = 'tag tag-warn';
      tagEl.textContent = 'DEMO';
    }
    if(runBtn){
      runBtn.disabled = true;
      runBtn.title = 'Live hardware execution is supported only for Problem A and Problem B';
    }
    // Fetch demo execution payload
    try {
      const res = await fetch('/api/ibm/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ instance_id: instId })
      });
      const data = await res.json();
      renderIbmHardwareExecution(data);
    } catch(e){
      console.warn('Demo fetch failed:', e);
    }
    return;
  }

  // Supported Live Instance mode (Problem A or Problem B)
  if(demoNoticeEl) demoNoticeEl.style.display = 'none';
  if(runBtn){
    runBtn.disabled = false;
    runBtn.title = 'Execute this problem on real IBM Quantum hardware';
  }

  // Fetch stored hardware result for this instance
  try {
    const res = await fetch(`/api/ibm/stored-result/${canonId}?p=${pVal}&shots=${shotsVal}`);
    const data = await res.json();

    if(data.status === 'completed'){
      if(tagEl){
        tagEl.className = data.live_hardware ? 'tag live' : 'tag tag-warn';
        tagEl.textContent = data.live_hardware ? 'LIVE IBM HARDWARE RESULT' : 'PRECOMPUTED IBM HARDWARE RESULT';
      }
      const probDef = (canonId === 'instance-a-2x2x2') ? {
        id: 'instance-a-2x2x2', name: 'Problem A — 2 EV × 2 Stations × 2 Slots',
        n_ev: 2, n_st: 2, n_t: 2, n_qubits: 10,
        demand: [1, 1], window: [[0, 1], [0, 1]], price: [1.0, 2.0],
        grid_cap: [2, 2], open_cost: [1.0, 1.5], detour: [[0.0, 0.3], [0.2, 0.0]], stress_w: 0.25
      } : {
        id: 'custom-1791428968536', name: 'Problem B — 3 EV × 2 Stations × 4 Slots',
        n_ev: 3, n_st: 2, n_t: 4, n_qubits: 20,
        demand: [2, 2, 1], window: [[1, 2, 3], [0, 1, 2], [1, 2, 3]],
        price: [1.2, 1.3, 1.1, 1.1], grid_cap: [2, 2, 2, 2], open_cost: [1.7, 1.0],
        detour: [[0.2, 0.2], [0.2, 0.3], [0.2, 0.1]], stress_w: 0.45
      };

      const bestObs = data.best_observed || data.best_solution || {};
      const bestFeas = data.best_feasible || (data.feasibility?.has_feasible_solution ? { objective: data.feasibility?.best_feasible_objective } : null);

      renderIbmHardwareExecution({
        status: 'ok',
        instance_id: canonId,
        source: data.live_hardware ? 'live' : 'stored',
        source_label: data.live_hardware ? 'LIVE IBM HARDWARE RESULT' : 'STORED HARDWARE RESULT',
        problem: probDef,
        metadata: {
          name: canonId === 'instance-a-2x2x2' ? 'Problem A — 2 EV × 2 Stations × 2 Slots' : 'Problem B — 3 EV × 2 Stations × 4 Slots',
          evs: data.instance_summary?.n_ev || probDef.n_ev,
          stations: data.instance_summary?.n_st || probDef.n_st,
          time_slots: data.instance_summary?.n_t || probDef.n_t,
          logical_qubits: data.logical_qubits || probDef.n_qubits,
          shots: data.shots || shotsVal,
          qaoa_p: data.p || pVal,
          backend: data.backend || 'ibm_fez',
          job_id: data.job_id,
          transpiled_depth: data.transpiled_depth,
          two_qubit_gates: data.two_qubit_gates,
          best_feasible_obj: bestFeas ? (bestFeas.objective ?? '—') : 'None (Infeasible)',
          feasible_prob: data.feasible_sample_probability ?? 0.0,
        },
        result: bestObs,
        aer_solution: data.aer_solution,
        aer_resources: data.comparison_with_aer?.aer_qaoa,
        ibm_resources: data.resources,
      });

    } else if(data.status === 'hardware_failed'){
      if(tagEl){
        tagEl.className = 'tag tag-danger';
        tagEl.textContent = 'HARDWARE EXECUTION FAILED';
      }
      if(errorEl){
        errorEl.style.display = 'block';
        if(errorMsgEl) errorMsgEl.textContent = data.message || data.error || 'Live hardware execution failed.';
      }
    } else {
      if(tagEl){
        tagEl.className = 'tag tag-info';
        tagEl.textContent = 'SUPPORTED LIVE PROBLEM (READY TO RUN)';
      }
      updateIbmProblemMetadata({
        evs: canonId === 'instance-a-2x2x2' ? 2 : 3,
        stations: 2,
        time_slots: canonId === 'instance-a-2x2x2' ? 2 : 4,
        logical_qubits: canonId === 'instance-a-2x2x2' ? 10 : 20,
        backend: 'ibm_fez (Heron r2)',
        job_id: '—',
        shots: shotsVal,
        qaoa_p: pVal,
      });
    }
  } catch(e){
    console.warn('Stored result fetch failed:', e);
  }
}

async function runIbmHardwareProblem(instId){
  const canonId = normalizeLiveIbmId(instId);
  const isSupported = LIVE_IBM_INSTANCES.has(instId) || LIVE_IBM_INSTANCES.has(canonId);

  if(!isSupported){
    toast('Live execution is strictly supported only for Problem A and Problem B');
    return;
  }

  const btn = $('#runIbmHardwareBtn');
  const tagEl = $('#ibmSourceTag');
  const errorEl = $('#ibmHardwareError');
  const errorMsgEl = $('#ibmHardwareErrorMsg');

  const pSelect = $('#ibmPSelect');
  const shotsSelect = $('#ibmShotsSelect');
  const pVal = pSelect ? parseInt(pSelect.value, 10) : 2;
  const shotsVal = shotsSelect ? parseInt(shotsSelect.value, 10) : 2048;

  if(errorEl) errorEl.style.display = 'none';
  if(btn) btn.disabled = true;
  if(tagEl){
    tagEl.className = 'tag';
    tagEl.textContent = `Submitting to IBM Quantum Hardware (p=${pVal}, ${shotsVal} shots)...`;
  }

  try {
    const res = await fetch('/api/ibm/hardware-run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ instance_id: canonId, p: pVal, shots: shotsVal })
    });
    const data = await res.json();
    if(data.status === 'completed'){
      toast(`Hardware execution completed on ${data.backend}!`);
      await displayIbmHardwareProblem(canonId);
    } else {
      if(tagEl){
        tagEl.className = 'tag tag-danger';
        tagEl.textContent = 'HARDWARE EXECUTION FAILED';
      }
      if(errorEl){
        errorEl.style.display = 'block';
        if(errorMsgEl) errorMsgEl.textContent = data.message || data.error || 'Execution failed';
      }
      toast('Hardware execution failed: ' + (data.message || data.error || 'Error'));
    }
  } catch(err){
    if(tagEl){
      tagEl.className = 'tag tag-danger';
      tagEl.textContent = 'HARDWARE EXECUTION FAILED';
    }
    if(errorEl){
      errorEl.style.display = 'block';
      if(errorMsgEl) errorMsgEl.textContent = err.message;
    }
    toast('Error: ' + err.message);
  } finally {
    if(btn) btn.disabled = false;
  }
}

async function loadIbmScalingData(){
  try{
    const data = await api('/api/scaling/ibm-demo');
    if(!data || !data.instances) return;
    ibmAllInstances = data.instances;

    // 1. Render Section A: 2 × 2 SVG Line Graphs
    const instances = data.instances;
    const xBinaryVars = instances.map(inst => inst.qubo_variables ?? inst.logical_qubits ?? inst.problem_definition?.n_qubits);
    const yLogicalQubits = instances.map(inst => inst.logical_qubits ?? inst.qubo_variables ?? inst.problem_definition?.n_qubits);

    const yAerDepth = instances.map(inst => inst.aer?.circuit_depth ?? 0);
    const yIbmDepth = instances.map(inst => inst.ibm?.transpiled_depth ?? 0);

    const yAerGates = instances.map(inst => inst.aer?.total_gates ?? 0);
    const yIbmGates = instances.map(inst => inst.ibm?.total_gates ?? 0);

    const yAer2Q = instances.map(inst => inst.aer?.two_qubit_gates ?? 0);
    const yIbm2Q = instances.map(inst => inst.ibm?.two_qubit_gates ?? 0);

    const AER_COLOR = '#1192e8'; // Blue for Aer / Ideal / Algorithmic
    const IBM_COLOR = '#7b1fa2'; // Purple for IBM / Heavy-Hex Transpiled

    renderScalingSvgLineGraph(
      'graphScalingSize',
      xBinaryVars,
      [{ name: 'Logical Qubits', values: yLogicalQubits, color: AER_COLOR }],
      'Binary Variables',
      'Logical Qubits'
    );

    renderScalingSvgLineGraph(
      'graphScalingDepth',
      xBinaryVars,
      [
        { name: 'Aer Algorithmic', values: yAerDepth, color: AER_COLOR },
        { name: 'IBM Transpiled', values: yIbmDepth, color: IBM_COLOR }
      ],
      'Binary Variables',
      'Circuit Depth'
    );

    renderScalingSvgLineGraph(
      'graphScalingGates',
      xBinaryVars,
      [
        { name: 'Aer Total Gates', values: yAerGates, color: AER_COLOR },
        { name: 'IBM Transpiled Gates', values: yIbmGates, color: IBM_COLOR }
      ],
      'Binary Variables',
      'Total Gates'
    );

    renderScalingSvgLineGraph(
      'graphScaling2Q',
      xBinaryVars,
      [
        { name: 'Aer 2Q (Rzz)', values: yAer2Q, color: AER_COLOR },
        { name: 'IBM Transpiled CX', values: yIbm2Q, color: IBM_COLOR }
      ],
      'Binary Variables',
      '2-Qubit Gates'
    );

    // 2. Setup Section B: Problem Selector & Initial Display
    const selectEl = $('#ibmProblemSelect');
    const runBtn = $('#runIbmHardwareBtn');

    // Build curated options with explicit Supported Live vs Demo badges
    const optionsHtml = [
      '<option value="instance-a-2x2x2">Problem A — 2 EV × 2 Stations × 2 Slots (10 Qubits) [Supported Live]</option>',
      '<option value="custom-1791428968536">Problem B — 3 EV × 2 Stations × 4 Slots (20 Qubits) [Supported Live]</option>',
      ...ibmAllInstances.filter(i => !['demo-inst-1', 'small-2x2x2', 'instance-a-2x2x2'].includes(i.instance_id)).map(inst => `
        <option value="${inst.instance_id}">
          ${inst.name} (${inst.logical_qubits} Qubits) [Demo]
        </option>
      `)
    ].join('');

    if(selectEl){
      selectEl.innerHTML = optionsHtml;

      selectEl.onchange = () => {
        const selectedId = selectEl.value;
        displayIbmHardwareProblem(selectedId);
      };
    }

    const pSelect = $('#ibmPSelect');
    if(pSelect){
      pSelect.onchange = () => {
        const selectedId = selectEl?.value || 'instance-a-2x2x2';
        displayIbmHardwareProblem(selectedId);
      };
    }

    const shotsSelect = $('#ibmShotsSelect');
    if(shotsSelect){
      shotsSelect.onchange = () => {
        const selectedId = selectEl?.value || 'instance-a-2x2x2';
        displayIbmHardwareProblem(selectedId);
      };
    }

    if(runBtn){
      runBtn.onclick = () => {
        const selectedId = $('#ibmProblemSelect')?.value || 'instance-a-2x2x2';
        runIbmHardwareProblem(selectedId);
      };
    }

    // Determine initial selection based on Problem Setup active instance
    const activeProblemId = instance?.id || getStoredProblemId() || 'instance-a-2x2x2';
    const canonActiveId = normalizeLiveIbmId(activeProblemId);

    if(selectEl){
      if(LIVE_IBM_INSTANCES.has(activeProblemId)){
        selectEl.value = canonActiveId;
      } else if(Array.from(selectEl.options).some(o => o.value === activeProblemId)){
        selectEl.value = activeProblemId;
      } else {
        selectEl.value = 'instance-a-2x2x2';
      }
    }

    // Display stored result or demo without executing hardware
    const initialId = selectEl?.value || 'instance-a-2x2x2';
    await displayIbmHardwareProblem(initialId);

    ibmScalingDataLoaded = true;
  }catch(err){
    console.warn('Failed to load IBM scaling data:', err);
  }
}

// ==========================================
// Estimate Resources Tab Logic
// ==========================================
async function runEstimation(){
  const e = parseInt($('#estEVs').value) || 3;
  const s = parseInt($('#estStations').value) || 2;
  const t = parseInt($('#estSlots').value) || 4;
  const p = parseInt($('#estP').value) || 1;
  const backend = $('#estBackend').value || 'ibm_brisbane';

  const notice = $('#estStatusNotice');
  const btn = $('#runEstimateBtn');
  if(btn) btn.disabled = true;
  if(notice) notice.innerHTML = '<span class="badge badge-info">Synthesizing QUBO & generating QAOA circuit transpilation...</span>';

  try {
    const payloadInst = (instance && instance.n_ev === e && instance.n_st === s && instance.n_t === t)
      ? instance
      : { n_ev: e, n_st: s, n_t: t };

    const r = await fetch('/api/estimate-resources', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        instance: payloadInst,
        p: p,
        backend: backend
      })
    });

    if(!r.ok){
      const err = await r.json();
      throw Error(err.error || 'Failed to estimate resources');
    }

    const res = await r.json();
    renderEstimationResults(res);
    if(notice) notice.innerHTML = `<span class="badge badge-success">✓ Resource estimation complete for ${res.instance_summary.n_ev} EVs × ${res.instance_summary.n_st} St × ${res.instance_summary.n_t} Slots (${res.instance_summary.logical_qubits} Qubits)</span>`;
  } catch(err){
    if(notice) notice.innerHTML = `<span class="badge badge-danger">✕ Estimation error: ${err.message}</span>`;
    toast('Estimation failed: ' + err.message);
  } finally {
    if(btn) btn.disabled = false;
  }
}

function renderEstimationResults(res){
  const container = $('#estimateResultsContainer');
  if(container) container.style.display = 'block';

  const isum = res.instance_summary || {};
  const aer = res.aer || {};
  const ibm = res.ibm || {};

  // 1. Top Concise Summary
  const descEl = $('#estSummaryDesc');
  if(descEl) descEl.textContent = `Problem Formulation: ${isum.n_ev} EVs × ${isum.n_st} Stations × ${isum.n_t} Slots`;
  const sqv = $('#sumQuboVars'); if(sqv) sqv.textContent = isum.qubo_variables ?? '-';
  const slq = $('#sumLogicalQubits'); if(slq) slq.textContent = isum.logical_qubits ?? '-';
  const sqd = $('#sumQaoaDepth'); if(sqd) sqd.textContent = `p = ${aer.p || 1}`;
  const sht = $('#sumHamTerms'); if(sht) sht.textContent = isum.hamiltonian_terms ?? '-';
  const std = $('#sumTargetDevice'); if(std) std.textContent = ibm.label || ibm.backend || '-';

  // 2. Aer Common Core Circuit Metrics Grid
  const aerGrid = $('#estAerGrid');
  if(aerGrid){
    aerGrid.innerHTML = `
      <div><b>${aer.logical_qubits}</b><span>Logical Qubits</span></div>
      <div><b>p = ${aer.p}</b><span>QAOA Depth</span></div>
      <div><b>${aer.circuit_depth}</b><span>Circuit Depth</span></div>
      <div><b>${aer.total_gates}</b><span>Total Gates</span></div>
      <div><b>${aer.two_qubit_gates}</b><span>2-Qubit Gates (Rzz)</span></div>
      <div><b>${aer.transpiled_depth}</b><span>Transpiled Depth</span></div>
      <div><b>${aer.transpiled_cx}</b><span>Transpiled CX</span></div>
    `;
  }

  // 3. Aer Statevector Computer Requirement Sub-block
  let aerBadgeClass = 'badge-success';
  if(aer.simulation_status_code === 'high_memory'){
    aerBadgeClass = 'badge-warn';
  } else if(aer.simulation_status_code === 'not_practical'){
    aerBadgeClass = 'badge-danger';
  }
  const aerBadge = $('#aerSimStatusBadge');
  if(aerBadge){
    aerBadge.className = `badge ${aerBadgeClass}`;
    aerBadge.textContent = aer.simulation_status_label || (aer.simulation_feasible ? '✓ Practical' : '✕ Not practical');
  }

  const aerMemGrid = $('#estAerMemGrid');
  if(aerMemGrid){
    aerMemGrid.innerHTML = `
      <div><b>${aer.logical_qubits}</b><span>Logical Qubits</span></div>
      <div><b>${aer.statevector_amplitudes || '-'}</b><span>Statevector Amplitudes</span></div>
      <div><b>${aer.statevector_memory_str || '-'}</b><span>Estimated Raw Statevector Memory</span></div>
      <div><b><span class="badge ${aerBadgeClass}">${aer.simulation_status_label || (aer.simulation_feasible ? '✓ Practical' : '✕ Not practical')}</span></b><span>Simulation Status</span></div>
    `;
  }

  const aerNote = $('#estAerNote');
  if(aerNote){
    const msg = aer.simulation_status_message || aer.status_message || '';
    const noteClass = aer.simulation_feasible ? 'muted' : 'tag-warn';
    aerNote.innerHTML = `
      <p class="${noteClass}" style="margin:2px 0;"><b>Status:</b> ${msg}</p>
      <p class="muted" style="margin:2px 0;"><b>Runtime Expectation:</b> ${aer.estimated_runtime || '-'}</p>
    `;
  }

  // 4. IBM Common Core Circuit Metrics Grid
  const ibmSub = $('#estIbmSubhead');
  if(ibmSub) ibmSub.textContent = `Transpilation for ${ibm.label || ibm.backend} (${ibm.architecture}).`;

  const ibmGrid = $('#estIbmGrid');
  if(ibmGrid){
    ibmGrid.innerHTML = `
      <div><b>${ibm.logical_qubits}</b><span>Logical Qubits</span></div>
      <div><b>p = ${ibm.p}</b><span>QAOA Depth</span></div>
      <div><b>${ibm.transpiled_depth}</b><span>Transpiled Circuit Depth</span></div>
      <div><b>${ibm.total_gates}</b><span>Total Gates</span></div>
      <div><b>${ibm.two_qubit_gates}</b><span>2-Qubit Gates (CX)</span></div>
    `;
  }

  // 5. IBM Device Capacity & Topology Mapping Sub-block
  const ibmCompatBadge = $('#ibmCompatBadge');
  if(ibmCompatBadge){
    ibmCompatBadge.className = ibm.fits_backend ? 'badge badge-success' : 'badge badge-danger';
    ibmCompatBadge.textContent = ibm.fits_backend ? '✓ Fits' : '✕ Exceeds Device Capacity';
  }

  const ibmDeviceGrid = $('#estIbmDeviceGrid');
  if(ibmDeviceGrid){
    const compatBadgeClass = ibm.fits_backend ? 'badge-success' : 'badge-danger';
    const compatText = ibm.fits_backend ? '✓ Fits' : '✕ Exceeds';
    ibmDeviceGrid.innerHTML = `
      <div><b>${ibm.physical_qubits_required}</b><span>Physical Qubits Required</span></div>
      <div><b>${ibm.device_capacity}</b><span>Device Physical Capacity</span></div>
      <div><b>${ibm.routing_overhead}</b><span>Routing Overhead</span></div>
      <div><b><span class="badge ${compatBadgeClass}">${compatText}</span></b><span>Device Compatibility</span></div>
    `;
  }

  const ibmNote = $('#estIbmNote');
  if(ibmNote){
    const compatClass = ibm.fits_backend ? 'muted' : 'tag-warn';
    ibmNote.innerHTML = `
      <p class="${compatClass}" style="margin:2px 0;"><b>Compatibility:</b> ${ibm.compatibility_status}</p>
      <p class="muted" style="margin:2px 0;"><b>Device Architecture:</b> ${ibm.label || ibm.backend} (${ibm.architecture})</p>
    `;
  }

  window.scrollTo({
    top: container.offsetTop - 40,
    behavior: 'smooth'
  });
}

// Attach Estimate Tab Event Listeners
const runEstBtn = $('#runEstimateBtn');
if(runEstBtn){
  runEstBtn.onclick = runEstimation;
}

const estPreset = $('#estimatePreset');
if(estPreset){
  estPreset.onchange = () => {
    const val = estPreset.value;
    if(val === 'baseline'){
      $('#estEVs').value = 3;
      $('#estStations').value = 2;
      $('#estSlots').value = 4;
    } else if(val === 'small'){
      $('#estEVs').value = 2;
      $('#estStations').value = 2;
      $('#estSlots').value = 2;
    } else if(val === 'medium'){
      $('#estEVs').value = 4;
      $('#estStations').value = 2;
      $('#estSlots').value = 4;
    } else if(val === 'large'){
      $('#estEVs').value = 20;
      $('#estStations').value = 10;
      $('#estSlots').value = 8;
    }
    if(val !== 'custom'){
      runEstimation();
    }
  };
}

['#estEVs', '#estStations', '#estSlots'].forEach(sel => {
  const el = $(sel);
  if(el){
    el.oninput = () => {
      if(estPreset) estPreset.value = 'custom';
    };
  }
});

// Problem Setup handoff button to Estimate tab
const estHandoffBtn = $('#estimateHandoffBtn');
if(estHandoffBtn){
  estHandoffBtn.onclick = () => {
    const { e, s, t } = customDimensions();
    $('#estEVs').value = e;
    $('#estStations').value = s;
    $('#estSlots').value = t;
    if(estPreset) estPreset.value = 'custom';
    show('estimate');
    toast(`Transferred ${e} EVs × ${s} Stations × ${t} Slots to Resource Estimator`);
    runEstimation();
  };
}

initialize();
