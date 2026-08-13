/**
 * DocMind AI — app.js v5
 * Features: Chat history, streaming, multi-doc, responsive sidebar
 */
'use strict';

// ── Helpers ──────────────────────────────────────
const $  = id => document.getElementById(id);
const esc = s  => String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
const cid = s  => String(s||'').replace(/[^a-z0-9]/gi,'_');
const now = ()  => new Date().toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'});

// ── State ────────────────────────────────────────
const S = {
  theme    : localStorage.getItem('dm_theme') || 'dark',
  streaming: false,
  polling  : null,
  files    : {},
  sessions : JSON.parse(localStorage.getItem('dm_sessions') || '[]'),
  activeId : null,
  pendingDel: null,
};

// ── DOM ──────────────────────────────────────────
let D = {};
function initDom(){
  D = {
    sidebar   : $('sidebar'),
    sbClose   : $('sbClose'),
    menuBtn   : $('menuBtn'),
    overlay   : null,
    newChatBtn: $('newChatBtn'),
    historyList:$('historyList'),
    historyEmpty:$('historyEmpty'),
    dropZone  : $('dropZone'),
    fileInput : $('fileInput'),
    docList   : $('docList'),
    docEmpty  : $('docEmpty'),
    fileCount : $('fileCount'),
    chunkInfo : $('chunkInfo'),
    totalChunks:$('totalChunks'),
    themeBtn  : $('themeBtn'),
    tbTitle   : $('tbTitle'),
    tbTitleTxt: $('tbTitleTxt'),
    statusPill: $('statusPill'),
    spDot     : $('spDot'),
    statusTxt : $('statusTxt'),
    clearBtn  : $('clearBtn'),
    chat      : $('chat'),
    welcome   : $('welcome'),
    msgsWrap  : $('msgsWrap'),
    msgs      : $('msgs'),
    msgInput  : $('msgInput'),
    sendBtn   : $('sendBtn'),
    charCount : $('charCount'),
    idxPopup  : $('idxPopup'),
    idxList   : $('idxList'),
    delModal  : $('delModal'),
    delDesc   : $('delDesc'),
    delCancel : $('delCancel'),
    delOk     : $('delOk'),
    toasts    : $('toasts'),
  };
  // Create overlay element for mobile
  const ov = document.createElement('div');
  ov.className = 'sb-overlay';
  ov.id = 'sbOverlay';
  document.body.appendChild(ov);
  D.overlay = ov;
}

// ── INIT ─────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  initDom();
  applyTheme(S.theme);
  bindEvents();
  renderHistory();
  loadDocs();
  // Start fresh session
  startNewSession();
});

// ── THEME ────────────────────────────────────────
function applyTheme(t){
  S.theme = t;
  document.documentElement.setAttribute('data-theme', t);
  localStorage.setItem('dm_theme', t);
  if(D.themeBtn) D.themeBtn.textContent = t==='dark' ? '☀️' : '🌙';
}

// ── SIDEBAR ──────────────────────────────────────
function openSidebar(){
  D.sidebar.classList.add('sb-mobile-open');
  D.overlay.classList.add('show');
}
function closeSidebar(){
  D.sidebar.classList.remove('sb-mobile-open');
  D.overlay.classList.remove('show');
}

// ── EVENTS ───────────────────────────────────────
function bindEvents(){
  D.themeBtn?.addEventListener('click', () => applyTheme(S.theme==='dark'?'light':'dark'));
  D.sbClose?.addEventListener('click', closeSidebar);
  D.menuBtn?.addEventListener('click', openSidebar);
  D.overlay?.addEventListener('click', closeSidebar);
  D.newChatBtn?.addEventListener('click', startNewSession);
  D.clearBtn?.addEventListener('click', clearCurrentChat);

  // Upload
  D.dropZone?.addEventListener('click', () => D.fileInput?.click());
  D.fileInput?.addEventListener('change', e => handleUpload(e.target.files));
  D.dropZone?.addEventListener('dragover', e => { e.preventDefault(); D.dropZone.classList.add('dz-over'); });
  D.dropZone?.addEventListener('dragleave', () => D.dropZone.classList.remove('dz-over'));
  D.dropZone?.addEventListener('drop', e => { e.preventDefault(); D.dropZone.classList.remove('dz-over'); handleUpload(e.dataTransfer.files); });
  document.addEventListener('dragover', e => e.preventDefault());
  document.addEventListener('drop', e => { e.preventDefault(); if(e.dataTransfer?.files?.length) handleUpload(e.dataTransfer.files); });

  // Input
  D.msgInput?.addEventListener('input', onInputChange);
  D.msgInput?.addEventListener('keydown', e => { if(e.key==='Enter'&&!e.shiftKey){ e.preventDefault(); sendMessage(); } });
  D.sendBtn?.addEventListener('click', sendMessage);

  // Modal
  D.delCancel?.addEventListener('click', () => D.delModal.style.display='none');
  D.delOk?.addEventListener('click', () => { if(S.pendingDel) doDelete(S.pendingDel); D.delModal.style.display='none'; });
  D.delModal?.addEventListener('click', e => { if(e.target===D.delModal) D.delModal.style.display='none'; });
}

// ── INPUT ────────────────────────────────────────
function onInputChange(){
  const v = D.msgInput.value;
  D.charCount.textContent = `${v.length} / 4000`;
  D.sendBtn.disabled = !v.trim() || S.streaming;
  D.msgInput.style.height = 'auto';
  D.msgInput.style.height = Math.min(D.msgInput.scrollHeight, 180) + 'px';
}

// ── STATUS ───────────────────────────────────────
function setStatus(state, txt){
  D.statusPill.className = 'status-pill';
  if(state==='thinking') D.statusPill.classList.add('sp-thinking');
  if(state==='error')    D.statusPill.classList.add('sp-error');
  D.statusTxt.textContent = txt;
  D.spDot.style.background = state==='thinking' ? 'var(--yel)' : state==='error' ? 'var(--red)' : 'var(--green)';
}

// ══════════════════════════════════════════════════
// CHAT HISTORY — localStorage based
// ══════════════════════════════════════════════════
function startNewSession(){
  // Save current if has messages
  saveCurrentSession();

  const id = 'sess_' + Date.now();
  S.activeId = id;
  S.sessions.unshift({ id, title: 'New Chat', time: Date.now(), msgs: [] });
  if(S.sessions.length > 30) S.sessions = S.sessions.slice(0,30);
  saveSessionsToStorage();

  // Clear UI
  D.msgs.innerHTML = '';
  D.msgsWrap.style.display = 'none';
  D.welcome.style.display = '';
  D.tbTitleTxt.textContent = 'New Chat';

  // Clear server session
  fetch('/api/chat/clear', {method:'POST'}).catch(()=>{});

  renderHistory();
}

function saveCurrentSession(){
  if(!S.activeId) return;
  const sess = S.sessions.find(s => s.id === S.activeId);
  if(!sess) return;
  // Collect messages from DOM
  const msgEls = D.msgs.querySelectorAll('.msg');
  if(msgEls.length === 0) return;
  const msgs = [];
  msgEls.forEach(el => {
    const role    = el.classList.contains('msg-user') ? 'user' : 'assistant';
    const bubble  = el.querySelector('.bubble');
    const sources = [...el.querySelectorAll('.src-chip')].map(c => c.textContent.trim());
    if(bubble) msgs.push({ role, html: bubble.innerHTML, sources });
  });
  sess.msgs  = msgs;
  sess.title = getSessionTitle(msgs);
  sess.time  = Date.now();
  saveSessionsToStorage();
}

function getSessionTitle(msgs){
  const first = msgs.find(m => m.role==='user');
  if(!first) return 'New Chat';
  const txt = first.html.replace(/<[^>]*>/g,'').trim();
  return txt.length > 38 ? txt.slice(0,38)+'…' : txt;
}

function saveSessionsToStorage(){
  try { localStorage.setItem('dm_sessions', JSON.stringify(S.sessions)); } catch{}
}

function loadSession(id){
  saveCurrentSession();
  const sess = S.sessions.find(s => s.id===id);
  if(!sess) return;
  S.activeId = id;

  D.msgs.innerHTML = '';
  D.welcome.style.display = 'none';
  D.msgsWrap.style.display = '';
  D.tbTitleTxt.textContent = sess.title;

  sess.msgs.forEach(m => {
    if(m.role==='user'){
      const d = document.createElement('div');
      d.className = 'msg msg-user';
      d.innerHTML = `
        <div class="msg-av av-u">U</div>
        <div class="msg-body">
          <div class="msg-top"><span class="msg-role">You</span></div>
          <div class="bubble bubble-u">${m.html}</div>
        </div>`;
      D.msgs.appendChild(d);
    } else {
      const d = document.createElement('div');
      d.className = 'msg msg-ai';
      const srcHtml = m.sources?.length ? `<div class="msg-sources"><span class="src-lbl">Sources</span>${m.sources.map(s=>`<span class="src-chip">📄 ${esc(s)}</span>`).join('')}</div>` : '';
      d.innerHTML = `
        <div class="msg-av av-ai">⬡</div>
        <div class="msg-body">
          <div class="msg-top"><span class="msg-role">DocMind AI</span></div>
          <div class="bubble bubble-ai">${m.html}</div>
          ${srcHtml}
          <div class="msg-acts"><button class="ma" onclick="copyBubble(this)">📋 Copy</button></div>
        </div>`;
      D.msgs.appendChild(d);
    }
  });

  scrollBottom();
  renderHistory();
  closeSidebar();

  // Restore server session history for continued conversation
  fetch('/api/chat/clear',{method:'POST'}).catch(()=>{});
}

function deleteSession(id, e){
  e?.stopPropagation();
  S.sessions = S.sessions.filter(s => s.id!==id);
  saveSessionsToStorage();
  if(S.activeId===id) startNewSession();
  else renderHistory();
}

function renderHistory(){
  if(!D.historyList) return;
  // Remove existing h-items
  D.historyList.querySelectorAll('.h-item').forEach(e => e.remove());

  const validSessions = S.sessions.filter(s => s.msgs && s.msgs.length > 0);

  if(D.historyEmpty) D.historyEmpty.style.display = validSessions.length ? 'none' : '';

  validSessions.forEach(sess => {
    const d = document.createElement('div');
    d.className = 'h-item' + (sess.id===S.activeId?' active':'');
    d.onclick = () => loadSession(sess.id);
    const t = new Date(sess.time);
    const timeStr = t.toLocaleDateString([], {month:'short', day:'numeric'}) + ' ' + t.toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'});
    d.innerHTML = `
      <span class="h-icon">💬</span>
      <div class="h-text">
        <div class="h-title">${esc(sess.title)}</div>
        <div class="h-time">${timeStr}</div>
      </div>
      <button class="h-del" title="Delete" onclick="deleteSession('${sess.id}',event)">🗑</button>`;
    D.historyList.appendChild(d);
  });
}

async function clearCurrentChat(){
  if(!D.msgs.children.length) return;
  saveCurrentSession();
  D.msgs.innerHTML = '';
  D.msgsWrap.style.display = 'none';
  D.welcome.style.display = '';
  // Reset current session messages
  const sess = S.sessions.find(s => s.id===S.activeId);
  if(sess) { sess.msgs=[]; sess.title='New Chat'; saveSessionsToStorage(); }
  renderHistory();
  await fetch('/api/chat/clear',{method:'POST'}).catch(()=>{});
}

// ══════════════════════════════════════════════════
// UPLOAD
// ══════════════════════════════════════════════════
async function handleUpload(fileList){
  if(!fileList?.length) return;
  const files = Array.from(fileList);
  const fd = new FormData();
  files.forEach(f => fd.append('files', f));
  showIdxPopup(files.map(f=>f.name));
  try {
    const res  = await fetch('/api/documents/upload',{method:'POST',body:fd});
    const data = await res.json();
    (data.results||[]).forEach(r => {
      if(r.status==='error'){ toast('Upload Error', r.error, 'err'); updateIr(r.filename,'error'); }
      else { S.files[r.filename]={status:'processing',chunks:0}; updateIr(r.filename,'processing'); }
    });
    startPolling();
  } catch(err){ toast('Upload Failed', err.message, 'err'); hideIdxPopup(); }
  if(D.fileInput) D.fileInput.value='';
}

function showIdxPopup(names){
  D.idxList.innerHTML = names.map(n=>`
    <div class="ir" id="ir-${cid(n)}">
      <span class="ir-name" title="${esc(n)}">${esc(n)}</span>
      <div class="ir-bar"><div class="ir-fill" id="if-${cid(n)}" style="width:8%"></div></div>
      <span class="ir-st" id="is-${cid(n)}">...</span>
    </div>`).join('');
  D.idxPopup.style.display='block';
}
function hideIdxPopup(){ D.idxPopup.style.display='none'; }
function updateIr(name, status, chunks){
  const fill=$('if-'+cid(name)), stat=$('is-'+cid(name));
  if(!fill||!stat) return;
  if(status==='done'){ fill.style.width='100%'; stat.textContent=chunks>0?`${chunks}ch`:'✓'; stat.style.color='var(--green)'; }
  else if(status==='error'){ fill.style.width='100%'; fill.style.background='var(--red)'; stat.textContent='✗'; stat.style.color='var(--red)'; }
  else { fill.style.width='55%'; }
}

// ── Polling ──────────────────────────────────────
function startPolling(){ if(S.polling) return; S.polling=setInterval(pollStatus,1800); }
function stopPolling(){ clearInterval(S.polling); S.polling=null; }

async function pollStatus(){
  try {
    const data = await fetch('/api/documents/status').then(r=>r.json());
    let any=false;
    for(const [name,info] of Object.entries(data)){
      S.files[name]=info;
      updateIr(name, info.status, info.chunks);
      if(info.status==='processing'||info.status==='pending') any=true;
    }
    renderDocs();
    if(!any){ stopPolling(); setTimeout(hideIdxPopup,1200); await loadDocs(); }
  } catch{}
}

async function loadDocs(){
  try {
    const data = await fetch('/api/documents/list').then(r=>r.json());
    data.files.forEach(f=>{ if(!S.files[f]) S.files[f]={status:'done',chunks:0}; });
    if(D.totalChunks) D.totalChunks.textContent=(data.total_chunks||0).toLocaleString();
    if(D.chunkInfo) D.chunkInfo.style.display=data.total_chunks>0?'':'none';
    renderDocs();
  } catch{}
}

function renderDocs(){
  if(!D.docList) return;
  const entries = Object.entries(S.files);
  const done    = entries.filter(([,v])=>v?.status==='done').length;
  D.fileCount.textContent = done;
  D.docEmpty.style.display = entries.length ? 'none' : '';
  D.docList.querySelectorAll('.dc').forEach(e=>e.remove());

  const EXT_COLOR = {
    pdf:'#f87171,#2a0f0f', docx:'#60a5fa,#0f1a2a', doc:'#60a5fa,#0f1a2a',
    xlsx:'#34d399,#0a2018', xls:'#34d399,#0a2018', csv:'#34d399,#0a2018',
    pptx:'#fbbf24,#2a1f0a', ppt:'#fbbf24,#2a1f0a',
    json:'#a78bfa,#1a0f2a', xml:'#a78bfa,#1a0f2a',
    html:'#fb923c,#2a1508', htm:'#fb923c,#2a1508',
  };

  entries.forEach(([name,info])=>{
    if(!info) return;
    const ext   = name.split('.').pop().toLowerCase();
    const cols  = (EXT_COLOR[ext]||'#6080ff,#0a0f2a').split(',');
    const dotC  = info.status==='done'?'std':info.status==='error'?'ste':'stp';
    const stTxt = info.status==='done'?(info.chunks>0?`${info.chunks} chunks`:info.chunks===-1?'cached':'indexed'):
                  info.status==='error'?(info.error?.slice(0,20)||'error'):'indexing…';
    const d = document.createElement('div');
    d.className='dc';
    d.innerHTML=`
      <div class="dc-ext" style="color:${cols[0]};background:${cols[1]}22">${ext.toUpperCase().slice(0,4)}</div>
      <div class="dc-info">
        <div class="dc-name" title="${esc(name)}">${esc(name)}</div>
        <div class="dc-st"><span class="st-dot ${dotC}"></span>${esc(stTxt)}</div>
      </div>
      <div class="dc-acts">
        <button class="da da-reload" title="Re-index" onclick="reindexDoc('${esc(name)}')">↺</button>
        <button class="da da-del" title="Delete" onclick="confirmDel('${esc(name)}')">🗑</button>
      </div>`;
    D.docList.appendChild(d);
  });
}

function confirmDel(name){
  S.pendingDel = name;
  D.delDesc.textContent = `"${name}" and all its indexed chunks will be permanently removed.`;
  D.delModal.style.display = 'flex';
}
async function doDelete(name){
  try {
    await fetch(`/api/documents/delete/${encodeURIComponent(name)}`,{method:'DELETE'});
    delete S.files[name];
    renderDocs();
    await loadDocs();
    toast('Deleted', `${name} removed`, 'ok');
  } catch(err){ toast('Error', err.message, 'err'); }
}
async function reindexDoc(name){
  try {
    await fetch(`/api/documents/reindex/${encodeURIComponent(name)}`,{method:'POST'});
    S.files[name]={status:'processing',chunks:0};
    showIdxPopup([name]);
    startPolling();
    toast('Re-indexing', name, 'inf');
  } catch(err){ toast('Error', err.message, 'err'); }
}

// ══════════════════════════════════════════════════
// CHAT
// ══════════════════════════════════════════════════
async function sendMessage(){
  const q = D.msgInput?.value.trim();
  if(!q||S.streaming) return;

  D.welcome.style.display = 'none';
  D.msgsWrap.style.display = '';
  addUserMsg(q);

  D.msgInput.value = ''; D.msgInput.style.height='auto';
  D.charCount.textContent = '0 / 4000';
  D.sendBtn.disabled = true;
  D.sendBtn.classList.add('streaming');
  setStatus('thinking','Thinking…');
  S.streaming = true;

  const aiId = addAiMsg();

  try {
    const res = await fetch('/api/chat/message',{
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({message:q})
    });
    if(!res.ok) throw new Error((await res.json()).error||'Server error');

    const reader=res.body.getReader(), dec=new TextDecoder();
    let buf='', full='', sources=[];

    while(true){
      const {value,done}=await reader.read();
      if(done) break;
      buf+=dec.decode(value,{stream:true});
      const lines=buf.split('\n'); buf=lines.pop();
      for(const line of lines){
        if(!line.startsWith('data: ')) continue;
        try {
          const ev=JSON.parse(line.slice(6));
          if(ev.type==='sources')    sources=ev.sources||[];
          else if(ev.type==='token'){ full+=ev.content; streamAi(aiId,full,sources); }
          else if(ev.type==='done') { sources=ev.sources||sources; finalizeAi(aiId,full,sources); }
          else if(ev.type==='error') finalizeAi(aiId,`❌ **Error:** ${ev.message}`,[]);
        } catch{}
      }
    }
    finalizeAi(aiId, full, sources);
    setStatus('ready','Ready');
    // Update title from first user msg
    const sess=S.sessions.find(s=>s.id===S.activeId);
    if(sess && sess.title==='New Chat'){
      sess.title=q.length>38?q.slice(0,38)+'…':q;
      D.tbTitleTxt.textContent=sess.title;
      saveSessionsToStorage();
      renderHistory();
    }
  } catch(err){
    finalizeAi(aiId,`❌ **Error:** ${err.message}`,[]);
    setStatus('error','Error');
    setTimeout(()=>setStatus('ready','Ready'),3000);
  } finally {
    S.streaming=false;
    D.sendBtn.classList.remove('streaming');
    D.sendBtn.disabled=!D.msgInput?.value.trim();
    scrollBottom();
    saveCurrentSession();
  }
}

function addUserMsg(text){
  const d=document.createElement('div');
  d.className='msg msg-user';
  d.innerHTML=`
    <div class="msg-av av-u">U</div>
    <div class="msg-body">
      <div class="msg-top"><span class="msg-role">You</span><span class="msg-time">${now()}</span></div>
      <div class="bubble bubble-u">${esc(text)}</div>
    </div>`;
  D.msgs.appendChild(d); scrollBottom();
}

function addAiMsg(){
  const id='ai'+Date.now();
  const d=document.createElement('div');
  d.className='msg msg-ai'; d.id=id;
  d.innerHTML=`
    <div class="msg-av av-ai">⬡</div>
    <div class="msg-body">
      <div class="msg-top"><span class="msg-role">DocMind AI</span><span class="msg-time">${now()}</span></div>
      <div class="bubble bubble-ai" id="${id}b"><div class="typing"><span></span><span></span><span></span></div></div>
    </div>`;
  D.msgs.appendChild(d); scrollBottom(); return id;
}

function streamAi(id, text, sources){
  const b=$(id+'b'); if(!b) return;
  b.innerHTML=renderMd(text); scrollBottom();
}

function finalizeAi(id, text, sources){
  const el=$(id); if(!el) return;
  const b=$(id+'b'); if(b) b.innerHTML=renderMd(text);
  const body=el.querySelector('.msg-body'); if(!body) return;
  body.querySelectorAll('.msg-sources,.msg-acts').forEach(e=>e.remove());
  if(sources?.length){
    const chips=sources.map(s=>`<span class="src-chip">📄 ${esc(s)}</span>`).join('');
    body.insertAdjacentHTML('beforeend',`<div class="msg-sources"><span class="src-lbl">Sources</span>${chips}</div>`);
  }
  body.insertAdjacentHTML('beforeend',`<div class="msg-acts"><button class="ma" onclick="copyBubble(this)">📋 Copy</button></div>`);
  scrollBottom();
}

function scrollBottom(){ requestAnimationFrame(()=>{ if(D.msgsWrap) D.msgsWrap.scrollTop=D.msgsWrap.scrollHeight; }); }

// ── Markdown renderer ─────────────────────────────
function renderMd(src){
  if(!src) return '';
  if(typeof marked!=='undefined'&&marked.parse){ try{return marked.parse(src);}catch{} }
  let h=src
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    .replace(/```[\w]*\n?([\s\S]*?)```/g,(_,c)=>`<pre><code>${c.trim()}</code></pre>`)
    .replace(/`([^`]+)`/g,'<code>$1</code>')
    .replace(/^#### (.+)$/gm,'<h4>$1</h4>').replace(/^### (.+)$/gm,'<h3>$1</h3>')
    .replace(/^## (.+)$/gm,'<h2>$1</h2>').replace(/^# (.+)$/gm,'<h1>$1</h1>')
    .replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>').replace(/\*(.+?)\*/g,'<em>$1</em>')
    .replace(/^[-*] (.+)$/gm,'<li>$1</li>').replace(/^\d+\. (.+)$/gm,'<li>$1</li>');
  h=h.replace(/(<li>[\s\S]*?<\/li>\n?)+/g,m=>`<ul>${m}</ul>`);
  h=h.split(/\n\n+/).map(b=>{
    b=b.trim(); if(!b) return '';
    if(/^<(h[1-6]|ul|ol|pre|blockquote|hr)/.test(b)) return b;
    return `<p>${b.replace(/\n/g,'<br>')}</p>`;
  }).join('');
  return h;
}

// ── Copy ─────────────────────────────────────────
function copyBubble(btn){
  const b=btn.closest('.msg-body')?.querySelector('.bubble'); if(!b) return;
  navigator.clipboard.writeText(b.innerText).then(()=>toast('Copied!','','ok',1500));
}

// ── Toast ─────────────────────────────────────────
function toast(title, sub, type='inf', dur=3500){
  if(!D.toasts) return;
  const icons={ok:'✅',err:'❌',inf:'ℹ️',warn:'⚠️'};
  const t=document.createElement('div');
  t.className=`toast ${type}`;
  t.innerHTML=`<span class="toast-icon">${icons[type]||'ℹ️'}</span><div class="toast-body"><div class="tt">${esc(title)}</div>${sub?`<div class="ts">${esc(sub)}</div>`:''}</div>`;
  D.toasts.appendChild(t);
  setTimeout(()=>{ t.classList.add('out'); setTimeout(()=>t.remove(),300); }, dur);
}
