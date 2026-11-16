'use strict';
const $ = s => document.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const date = s => s ? new Date(s).toLocaleString('en-US', {month:'short',day:'numeric',year:'numeric',hour:'numeric',minute:'2-digit'}) : 'Not available';
const safeURL = url => {try {const u = new URL(url); return u.protocol === 'https:' && ['www.youtube.com','youtube.com','neoreach.com','developers.google.com'].includes(u.hostname) ? u.href : '#';} catch {return '#';}};
let data, selected='rtx-students', busy=false, current=null, savedExample=false;
const questions = {
 availability:'Which public videos can we verify for this campaign, and what needs a human follow-up?',
 publishers:'Who published the linked videos? Separate the NVIDIA brand channel from other publishers, and explain what the records do and do not prove.',
 sales:'Which creator drove the most sales? Explain whether the available records can answer this and what data is missing.'
};
const remember=(key,value)=>{try{localStorage.setItem(key,value);}catch{}};
const recalled=key=>{try{return localStorage.getItem(key);}catch{return null;}};
function error(message){$('#error').textContent=message;$('#error').hidden=!message;}
function setBusy(value){busy=value;document.querySelectorAll('#agent-form button,#example-button,.campaign').forEach(b=>b.disabled=value);$('#question').disabled=value;$('#run-button').innerHTML=value?'Checking records <span class="loading-dot"></span>':'Run agent <span>↗</span>';}
function campaign(){return data.campaigns.find(c=>c.id===selected);}
function content(rows){
 $('#content-count').textContent=`${rows.length} source-listed videos`;
 const live=rows.some(r=>r.observation_type==='live');
 $('#data-time').textContent=`${live?'Live metadata check':'Research snapshot'} · ${date(rows[0]?.checked_at)}`;
 $('#content-list').innerHTML=rows.map(r=>{
   const ok=r.http_status===200&&r.title;
   return `<article class="content-row">${ok?`<img class="thumb" src="https://i.ytimg.com/vi/${esc(r.video_id)}/mqdefault.jpg" alt="" loading="lazy">`:'<div class="thumb no-thumb" aria-hidden="true">↗</div>'}<div class="content-info"><p class="publisher">${esc(r.author_name||'Publisher not verified')}</p><h3>${esc(r.title||'Source-listed video · '+r.video_id)}</h3><a class="content-link" href="https://www.youtube.com/watch?v=${esc(r.video_id)}" target="_blank" rel="noopener noreferrer">Open original video ↗</a></div><div class="content-status"><span class="tag ${ok?'ok':'warn'}">${ok?'Metadata found':'Needs a look'}</span><small class="stamp">${r.observation_type==='live'?'Live check':'Snapshot'} · ${r.http_status===null?'request failed':'HTTP '+esc(r.http_status)}</small></div></article>`;
 }).join('');
}
async function choose(id){
 if(busy)return;selected=id;current=null;savedExample=false;
 $('#campaigns').innerHTML=data.campaigns.map(c=>`<button class="campaign" type="button" data-campaign="${esc(c.id)}" aria-pressed="${c.id===selected}"><span class="category">${c.id==='rtx-students'?'BACK TO SCHOOL':'PRODUCT LAUNCH'}</span>${c.id===selected?'<span class="check-mark">✓</span>':''}<strong>${esc(c.title)}</strong><small>${esc(c.subtitle)}</small></button>`).join('');
 $('#brief-text').textContent=campaign().ui_summary||campaign().brief;$('#case-link').href=campaign().source_url;
 $('#question').value=campaign().question;content(data.videos.filter(v=>v.campaign_id===id));
 $('#report-section').hidden=true;$('#progress-panel').hidden=true;error('');
 const previous=recalled('desk-report-'+selected);
 if(previous){try{const r=await fetch('/api/runs/'+encodeURIComponent(previous));if(r.ok&&selected===id){current=await r.json();renderReport();}}catch{}}
}
function renderReport(){
 const r=current;if(!r)return;
 const evidence=Object.fromEntries(r.evidence.map(e=>[e.id,e]));
 const labels={verified:'Source-supported',follow_up:'Human follow-up',limitation:'Data limit'};
 const state=savedExample?'Saved real run':r.status==='approved'?'Reviewed · approved':r.status==='follow_up'?'Reviewed · follow-up':'Awaiting your review';
 const section=$('#report-section');section.hidden=false;
 section.innerHTML=`<div class="report-top"><p class="eyebrow">AGENT REPORT</p><span class="tag ${r.status==='approved'?'ok':'blue'}">${esc(state)}</span></div><h2>${esc(r.report.headline)}</h2><p class="report-meta">${savedExample?'Recorded run':'This run'} · ${date(r.created_at)} · ${esc(r.seconds)} seconds · ${r.live_refresh?'Public metadata refreshed during this run':'Research snapshot used'}</p><p class="report-answer">${esc(r.report.answer)}</p><div class="findings">${r.report.findings.map(f=>`<article class="finding"><span class="tag ${f.kind==='follow_up'?'warn':f.kind==='verified'?'ok':''}">${esc(labels[f.kind])}</span><h3>${esc(f.title)}</h3><p>${esc(f.detail)}</p><div class="evidence-links">${f.evidence_ids.map(id=>{const e=evidence[id];return e?`<a href="#evidence-${esc(id.replaceAll(':','-'))}" data-evidence="1">${id==='brief'?'Case study':id==='limits'?'Data limits':id.startsWith('metadata:')?'Video metadata':'Check record'} ↘</a>`:'';}).join('')}</div></article>`).join('')}</div><p class="next-step"><strong>Suggested next step:</strong> ${esc(r.report.next_step)}</p>
 ${!r.checks.passed?`<p class="error">Evidence checks need attention. Approval is disabled. ${esc(r.checks.problems.join(' '))}</p>`:''}
 ${savedExample?'<div class="review-box"><div><h3>This is a saved example</h3><p>It records a real Vertex AI run at the time shown above.</p></div><div><p>Run the agent above to check the sources now and create your own reviewable report.</p></div></div>':r.status==='awaiting_review'?`<div class="review-box"><div><h3>You make the final call.</h3><p>Check the sources, add a note, then approve this report or keep it for follow-up. This review stays in your demo session.</p></div><form id="review-form" class="review-controls"><label for="review-note">Your review note</label><textarea id="review-note" rows="2" maxlength="1200" required placeholder="What did you check, or what still needs a follow-up?"></textarea><div class="review-buttons"><button class="primary" type="submit" value="approved" ${r.checks.passed?'':'disabled'}>Approve report</button><button class="secondary" type="submit" value="follow_up">Keep for follow-up</button></div></form></div>`:`<div class="review-outcome ${r.status==='follow_up'?'follow-up':''}"><strong>${r.status==='approved'?'Report approved':'Marked for follow-up'}</strong><p>${esc(r.review.note)}</p><small>Saved ${date(r.review.reviewed_at)} · Demo visitor</small></div>`}
 <details><summary>See the agent’s tool calls <span>${r.trace.length} calls · ${r.checks.passed?'evidence checks passed':'checks need attention'}</span></summary><ol class="trace">${r.trace.map(t=>`<li><code>${esc(t.tool)}</code> → ${t.evidence_ids.length} evidence records</li>`).join('')}</ol><p class="report-meta">Model: ${esc(r.model)} · LangGraph orchestration · ${r.usage.reduce((n,u)=>n+u.input_tokens,0)} input / ${r.usage.reduce((n,u)=>n+u.output_tokens,0)} output tokens. Model assessment is not a guarantee; your review remains necessary.</p></details>
 <details id="evidence-details"><summary>Inspect source records <span>${r.evidence.length} evidence records</span></summary>${r.evidence.map(e=>`<div class="evidence-record" id="evidence-${esc(e.id.replaceAll(':','-'))}"><strong>${esc(e.id)}</strong><p>${esc(e.text)}</p><a href="${esc(safeURL(e.source_url))}" target="_blank" rel="noopener noreferrer">Open source ↗</a></div>`).join('')}</details>`;
 if(!savedExample&&r.observations)content(r.observations);
}
function progress(event){
 const item=document.createElement('div');item.className='progress-row';
 item.innerHTML='<span>↗</span><p></p>';item.querySelector('p').textContent=event.message;$('#progress').append(item);
 if(event.tool==='refresh_public_metadata'&&event.evidence)content(event.evidence.filter(e=>e.record).map(e=>e.record));
}
async function run(event){
 event.preventDefault();if(busy)return;error('');setBusy(true);current=null;savedExample=false;
 $('#report-section').hidden=true;$('#progress').textContent='';$('#progress-panel').hidden=false;
 try{
  const response=await fetch('/api/runs',{method:'POST',headers:{'Content-Type':'application/json','X-Desk-Request':'1'},body:JSON.stringify({campaign_id:selected,question:$('#question').value.trim()})});
  if(!response.ok){const d=await response.json();throw new Error(typeof d.detail==='string'?d.detail:'Please check your question and try again.');}
  const reader=response.body.getReader(),decoder=new TextDecoder();let buffer='',gotResult=false;
  while(true){const {value,done}=await reader.read();if(done)break;buffer+=decoder.decode(value,{stream:true});let boundary;
   while((boundary=buffer.indexOf('\n\n'))!==-1){const block=buffer.slice(0,boundary);buffer=buffer.slice(boundary+2);if(!block.startsWith('data: '))continue;const event=JSON.parse(block.slice(6));
    if(event.type==='error')throw new Error(event.message);
    if(event.type==='progress')progress(event);
    if(event.type==='result'){gotResult=true;current=event.result;remember('desk-report-'+selected,current.id);renderReport();}
   }
  }
  if(!gotResult)throw new Error('The connection ended before a report was returned. Please try again.');
  $('#progress-panel').hidden=true;$('#report-section').scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth',block:'start'});
 }catch(e){error(e.message);}finally{setBusy(false);}
}
document.addEventListener('click',async event=>{
 const c=event.target.closest('[data-campaign]');if(c)await choose(c.dataset.campaign);
 const p=event.target.closest('[data-preset]');if(p&&!busy)$('#question').value=questions[p.dataset.preset];
 if(event.target.closest('[data-evidence]'))$('#evidence-details').open=true;
});
$('#agent-form').addEventListener('submit',run);
$('#example-button').addEventListener('click',async()=>{if(busy)return;error('');try{const response=await fetch('/api/example/'+selected);if(!response.ok)throw new Error('This saved example is unavailable. Run the agent to check the sources.');current=await response.json();savedExample=true;renderReport();$('#report-section').scrollIntoView({behavior:'smooth',block:'start'});}catch(e){error(e.message);}});
document.addEventListener('submit',async event=>{
 if(event.target.id!=='review-form')return;event.preventDefault();const controls=event.target.querySelectorAll('button');controls.forEach(b=>b.disabled=true);
 try{const response=await fetch('/api/runs/'+current.id+'/review',{method:'POST',headers:{'Content-Type':'application/json','X-Desk-Request':'1'},body:JSON.stringify({decision:event.submitter.value,note:$('#review-note').value.trim()})});const d=await response.json();if(!response.ok)throw new Error(typeof d.detail==='string'?d.detail:'Add a review note before saving.');current=d;renderReport();}catch(e){error(e.message);controls.forEach(b=>b.disabled=false);}
});
(async()=>{try{const response=await fetch('/api/catalog');if(!response.ok)throw new Error('Source records could not be loaded. Reload the page to try again.');data=await response.json();await choose(selected);}catch(e){error(e.message);}})();
