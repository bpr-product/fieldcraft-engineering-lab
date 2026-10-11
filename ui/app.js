'use strict';
const $ = (id) => document.getElementById(id);
const workspace = 'north-demo';
let currentMeasurementId = null;
let currentCatalog = [];
let lastSupplierBranch = 'branch-a';

async function api(path, init={}) {
  const response = await fetch(path, {headers:{'Content-Type':'application/json'}, ...init});
  let body;
  try { body = await response.json(); } catch { body = {detail:`HTTP ${response.status}`}; }
  if (!response.ok) throw new Error(body.detail || `HTTP ${response.status}`);
  return body;
}
function jsonResult(id, data) { $(id).textContent = JSON.stringify(data, null, 2); }
async function run(buttonId, outputId, fn) {
  const button = $(buttonId);
  button.disabled = true;
  if (outputId) $(outputId).textContent = 'Running...';
  try { const result = await fn(); if(outputId) jsonResult(outputId, result); return result; }
  catch (error) { if(outputId) $(outputId).textContent = `Error: ${error.message}`; return null; }
  finally { button.disabled = false; }
}
function post(path, payload) {return api(path, {method:'POST',body:JSON.stringify(payload)});}
function money(cents) {return cents == null ? 'price unavailable' : '$'+(cents/100).toFixed(2);}

async function refreshOverview() {
  const data = await api(`/api/overview?tenant_id=${encodeURIComponent(workspace)}`);
  $('metricProjects').textContent=data.metrics.projects;
  $('metricFinance').textContent=data.metrics.financial_records;
  $('metricDocuments').textContent=data.metrics.documents;
  $('metricMaterials').textContent=data.metrics.materials;
  $('llmMode').textContent = data.model_mode === 'configured_llm' ? 'LLM CONFIGURED' : 'OFFLINE EVIDENCE MODE';
}

$('syncBtn').addEventListener('click', () => run('syncBtn', 'accountingResult', async () => {
  const result=await post('/api/accounting/sync', {tenant_id:workspace}); await refreshOverview(); return result;
}));

$('pullBtn').addEventListener('click', () => run('pullBtn', 'accountingResult', async () => {
  const result=await post('/api/accounting/pull',{tenant_id:workspace,remote_id:'inbound-sample-01'});
  await refreshOverview(); return result;
}));
$('conflictBtn').addEventListener('click', () => run('conflictBtn', 'accountingResult', async () => {
  return await post('/api/accounting/mock-external-change',
     {tenant_id:workspace,record_id:'fin-1',amount_cents:61000});
}));

async function searchSupplier() {
  const q=$('supplierQuery').value.trim();
  const data=await api(`/api/supplier/search?tenant_id=${workspace}&branch_id=${lastSupplierBranch}&q=${encodeURIComponent(q)}`);
  currentCatalog=data.items;
  const list=$('supplierList'); list.replaceChildren();
  if (!currentCatalog.length) {list.textContent='No items found.';return;}
  currentCatalog.forEach(item => {
    const row=document.createElement('label');row.className='supplier-row';
    const cb=document.createElement('input');cb.type='checkbox';cb.className='catalog-check';cb.value=item.sku;
    cb.checked=!!(item.price_cents && item.available_to_order);
    const body=document.createElement('span');const title=document.createElement('strong');title.textContent=item.name;
    const caption=document.createElement('small');caption.textContent=`${item.sku} · ${item.supplier_uom} · ${money(item.price_cents)} · ${item.available_to_order ? 'available to order' : 'not available'}`;
    body.append(title, caption);row.append(cb,body);list.appendChild(row);
  });
}
$('searchSupplierBtn').addEventListener('click', () => run('searchSupplierBtn', 'supplierResult', async()=>{
  await searchSupplier();return {matches: currentCatalog.length, provider_mode:'synthetic', note:'Availability is not physical stock quantity.'};
}));
$('importSupplierBtn').addEventListener('click',()=>run('importSupplierBtn','supplierResult',async()=>{
  const skus=[...document.querySelectorAll('.catalog-check:checked')].map(el=>el.value);
  if (!skus.length) throw new Error('Select at least one item.');
  const result=await post('/api/supplier/import',{tenant_id:workspace,vendor_id:'vendor-main',branch_id:lastSupplierBranch,skus});
  await refreshOverview();return result;
}));

$('requestMeasureBtn').addEventListener('click',()=>run('requestMeasureBtn','measurementResult',async()=>{
  const result=await post('/api/measurements/orders',{tenant_id:workspace,project_id:$('measureProject').value});
  currentMeasurementId=result.id;$('completeMeasureBtn').disabled=false;
  await refreshOverview();return result;
}));
$('completeMeasureBtn').addEventListener('click',()=>run('completeMeasureBtn','measurementResult',async()=>{
  if(!currentMeasurementId) throw new Error('Request a measurement first.');
  const id=currentMeasurementId;
  const result=await post(`/api/measurements/orders/${id}/ingest`,{tenant_id:workspace,roof_area_sqft:2720,roof_pitch_ratio:0.33,facet_count:8});
  currentMeasurementId=null; await refreshOverview();return result;
}));

$('refreshPipelineBtn').addEventListener('click',()=>run('refreshPipelineBtn','pipelineResult',async()=>{
  const result=await post('/api/documents/refresh',{tenant_id:workspace});await refreshOverview();return result;
}));

for (const button of document.querySelectorAll('[data-question]')) {
  button.addEventListener('click',()=>{ $('question').value=button.dataset.question; $('question').focus(); });
}
$('askForm').addEventListener('submit', async event=>{
  event.preventDefault();
  const btn=$('askForm').querySelector('button');btn.disabled=true;
  $('assistantAnswer').textContent='Retrieving project context...';$('traceList').replaceChildren();
  try{
    const active=$('activeProject').value || null;
    const result=await post('/api/assistant/ask',{tenant_id:workspace,user_id:'demo-user',session_id:'web-demo-001',question:$('question').value,active_project_id:active});
    $('assistantAnswer').textContent=result.answer;
    for(const step of result.trace){const li=document.createElement('li');li.textContent=`${step.step}: ${step.detail}`;$('traceList').append(li);}
    if(result.evidence.length){
      const li=document.createElement('li');li.textContent=`Sources: ${result.evidence.map(s=>s.document_id+' (v'+s.version+')').join(', ')}`;$('traceList').append(li);
    }
  }catch(err){$('assistantAnswer').textContent=`Request failed: ${err.message}`;}
  finally{btn.disabled=false;}
});

$('writeMemoryBtn').addEventListener('click',()=>run('writeMemoryBtn','memoryResult',()=>post('/api/memory/write',{
  tenant_id:workspace,user_id:'demo-user',topic:$('memoryTopic').value,value:$('memoryValue').value,source_id:`demo-explicit-${Date.now()}`,source_type:'user_explicit'
})));
$('recallMemoryBtn').addEventListener('click',()=>run('recallMemoryBtn','memoryResult',()=>api(`/api/memory/recall?tenant_id=${workspace}&user_id=demo-user&topic=${encodeURIComponent($('memoryTopic').value)}`)));
$('forgetMemoryBtn').addEventListener('click',()=>run('forgetMemoryBtn','memoryResult',()=>post('/api/memory/forget',{
  tenant_id:workspace,user_id:'demo-user',topic:$('memoryTopic').value
})));

(async()=>{
  try{await refreshOverview();await searchSupplier();}
  catch(err){$('assistantAnswer').textContent=`The local API is not available: ${err.message}`;}
})();
