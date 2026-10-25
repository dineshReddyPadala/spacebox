'use strict';
const $ = (selector) => document.querySelector(selector);
const byId = (id) => document.getElementById(id);
const journey = [
  {title:'First, we listen.',desc:'We understand how you live or work, your priorities, budget, timelines, Vastu and wellness preferences.',items:['Lifestyle and requirements brief','Initial budget and project scope','Site visit or virtual consultation']},
  {title:'We understand the space.',desc:'A measured technical survey comes before a committed layout or a construction-ready quotation.',items:['Site measurements and constraints','Electrical, plumbing and services review','Orientation and practical feasibility']},
  {title:'Your vision, made visible.',desc:'Review layouts, mood boards and finish palettes with buildability in mind.',items:['Space plans and design directions','Material and finish selection','Visual concepts and design approvals']},
  {title:'Clarity before commitment.',desc:'An itemised BOQ explains the agreed scope, specifications, exclusions, price and changes.',items:['Itemised BOQ and material specifications','Inclusions, exclusions and approvals','Milestones and change controls']},
  {title:'Crafted with discipline.',desc:'We coordinate sourcing, fabrication, installation and quality checkpoints against the approved plan.',items:['Procurement and specialist coordination','Site progress and quality checks','Documented updates and approvals']},
  {title:'A space ready for life.',desc:'We inspect the space, close snag items, complete handover and explain product care.',items:['Final inspection and snag closure','Warranty and product documentation','Care guidance and aftercare coordination']}
];
function showProcess(i){
  const box=byId('processDetail');if(!box||!journey[i])return;
  document.querySelectorAll('.process-step').forEach((b,j)=>{b.classList.toggle('active',j===i);b.setAttribute('aria-pressed',j===i?'true':'false')});
  const p=journey[i];
  const deliverables=p.items.map(item=>`<li>${item}</li>`).join('');
  box.innerHTML=`<div><span class="pilltag">PHASE 0${i+1} / 06</span><h3 style="margin:12px 0">${p.title}</h3><p class="muted">${p.desc}</p><a href="/contact" class="link">Discuss your project ↗</a></div><ul class="deliverables" style="list-style:none;padding:0;margin:0">${deliverables}</ul>`;
}
function updateEstimate(){
  const home=byId('estHome'),result=byId('estimateResult');if(!home||!result)return;
  const v=home.value,base={"2bhk":12,"3bhk":18,"4bhk":29,"villa":60}[v];
  const fin=Number(byId('estFinish')?.value||1),scope=Number(byId('estScope')?.value||1),wel=Number(byId('estWellness')?.value||0);
  const mid=base*fin*scope+(wel?1.5:0),lo=(mid*.82).toFixed(1),hi=(mid*1.22).toFixed(1);
  const labels={"2bhk":"2 BHK apartment","3bhk":"3 BHK apartment","4bhk":"4 BHK / premium apartment","villa":"Villa interiors"};
  const row=(k,p)=>`<div class="estRow"><span>${k}</span><span class="barTrack"><span class="barFill" style="display:block;width:${p}%"></span></span><b>${p}%</b></div>`;
  result.innerHTML=`<span class="eyebrow">INDICATIVE INVESTMENT RANGE</span><div class="number" style="margin:20px 0 12px">₹${lo}L – ₹${hi}L</div><p>Planning illustration for ${labels[v]}; a detailed site survey and itemised BOQ are required.</p><div class="detail"><span>Working midpoint</span><strong>₹${mid.toFixed(1)} lakh</strong></div><div class="detail"><span>Finish level</span><strong>${byId('estFinish').selectedOptions[0].textContent}</strong></div><div class="detail"><span>Project scope</span><strong>${byId('estScope').selectedOptions[0].textContent}</strong></div><div class="detail"><span>Wellness option</span><strong>${wel?'Wellness+ allowance':'Standard principles'}</strong></div><div class="estBars"><span class="pilltag">Illustrative cost allocation · not a BOQ</span>${[['Cabinetry & storage',36],['Finishes & fixtures',24],['Site works & labour',22],['Lighting & details',12],['Contingency',6]].map(x=>row(x[0],x[1])).join('')}</div><p style="font-size:.75rem;margin-top:20px">Planning assumptions, not a binding SpaceBox quote. Actual cost depends on specifications, measured scope, approvals, project location and taxes.</p>`;
}
function renderManduva(){
  const brief=byId('mBrief');if(!brief)return;
  const beds=byId('beds').value,floors=byId('floors').value,plot=byId('plot').value,facing=byId('facing').value,purpose=byId('purpose').value,style=byId('style').value;
  const safePurpose={family:'Family residence',dual:'Personal home with optional hosted-stay potential',events:'Gatherings / hospitality-led concept'}[purpose]||'Family residence';
  byId('mTitle').textContent=`${beds}-bedroom · ${floors==='1'?'single-storey':'two-storey'} Manduva home`;
  brief.innerHTML=`<p><b>Site:</b> ${plot} sq yd · ${facing}-facing road<br><b>Aesthetic:</b> ${style}<br><b>Intent:</b> ${safePurpose}</p><p><b>Initial spatial brief:</b> A central courtyard, shaded verandahs, ${beds} bedrooms, pooja consideration, modern kitchen and bathrooms, natural ventilation and timeless materials.</p><p><b>Design lens:</b> Vastu-conscious planning, everyday wellness, family comfort and potential hosted use.</p><p><b>Next step:</b> Survey, local regulations, site north orientation, structural concept and detailed brief.</p>`;
}
function saveManduva(){
  const inputs=['beds','floors','plot','facing','purpose','style'];
  const values=inputs.map(id=>`${id}: ${byId(id)?.value||''}`).join('; ');
  // Navigation only; do not treat planning data as a submitted enquiry.
  window.location.href='/contact?type=Manduva%20Homes&brief='+encodeURIComponent(values);
}
function mobileMenu(){
  const toggle=byId('menuToggle'),links=byId('navlinks');if(!toggle||!links)return;
  toggle.addEventListener('click',()=>{const open=links.classList.toggle('open');toggle.setAttribute('aria-expanded',open?'true':'false');toggle.textContent=open?'✕ Close':'☰ Menu'});
  links.querySelectorAll('a').forEach(a=>a.addEventListener('click',()=>{links.classList.remove('open');toggle.setAttribute('aria-expanded','false')}));
  document.addEventListener('keydown',e=>{if(e.key==='Escape'){links.classList.remove('open');toggle.setAttribute('aria-expanded','false')}});
}
function init(){
 mobileMenu();
 const page=location.pathname;
 document.querySelectorAll('.navlinks a').forEach(a=>{if(a.getAttribute('href')===page)a.classList.add('active')});
 document.querySelectorAll('[data-process-step]').forEach(el=>el.addEventListener('click',()=>showProcess(Number(el.dataset.processStep))));
 if(byId('processDetail'))showProcess(0);
 document.querySelectorAll('[data-manduva-change]').forEach(el=>el.addEventListener('change',renderManduva));
 if(byId('mBrief'))renderManduva();
 document.querySelectorAll('[data-save-manduva]').forEach(el=>el.addEventListener('click',saveManduva));
 document.querySelectorAll('[data-estimate-change]').forEach(el=>el.addEventListener('change',updateEstimate));
 if(byId('estimateResult'))updateEstimate();
 document.querySelectorAll('[data-confirm]').forEach(el=>el.addEventListener('click',e=>{if(!confirm(el.dataset.confirm))e.preventDefault()}));
 if(page==='/contact'){
   const p=new URLSearchParams(location.search);
   const type=p.get('type'),brief=p.get('brief');
   const typeInput=document.querySelector('[name="project_type"]');if(type&&typeInput&&Array.from(typeInput.options).some(o=>o.value===type))typeInput.value=type;
   const msg=document.querySelector('[name="message"]');if(brief&&msg)msg.value='Manduva concept brief: '+brief.slice(0,350);
 }
}
document.addEventListener('DOMContentLoaded',init);
