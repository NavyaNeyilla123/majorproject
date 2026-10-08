import React, { useState, useEffect } from 'react';
import {
  Sparkles,
  ExternalLink,
  Search
} from 'lucide-react';
import PageHeader from '../components/PageHeader';
import { gmailService } from '../services/gmailService';
import useCacheTick from '../hooks/useCacheTick';

const MONTHS = ['January','February','March','April','May','June','July',
  'August','September','October','November','December'];

function longDate(iso) {
  if (!iso) return '';
  const [y, m, d] = iso.slice(0, 10).split('-').map(Number);
  if (!y || !m || !d) return iso;
  return `${MONTHS[m - 1]} ${d}, ${y}`;
}

function shortDate(iso) {
  if (!iso) return '';
  const [, m, d] = iso.slice(0, 10).split('-').map(Number);
  if (!m || !d) return iso;
  return `${MONTHS[m - 1].slice(0, 3)} ${d}`;
}

function msgTime(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  let h = d.getUTCHours() % 12;
  if (h === 0) h = 12;
  const mm = String(d.getUTCMinutes()).padStart(2, '0');
  return `${months[d.getUTCMonth()]} ${d.getUTCDate()} · ${h}:${mm} ${d.getUTCHours() < 12 ? 'AM' : 'PM'}`;
}

export default function GmailIntelligenceScreen({ navigateTo }) {
  const [selectedThreadId, setSelectedThreadId] = useState(null);
  const [expanded, setExpanded] = useState(false);
  const [showAll, setShowAll] = useState(false);
  useCacheTick();
  useEffect(() => {
    gmailService.sync();
  }, []);

  const priorityThreads = gmailService.getPriorityThreads();
  const allThreads = gmailService.getThreads();
  const threads = showAll ? allThreads : priorityThreads;
  const stats = gmailService.getStats();
  const summary = gmailService.getExtractedSummary();
  const synced = gmailService.getSyncedLabel();
  const activeId = selectedThreadId || (threads[0] && threads[0].id) || null;
  const threadDetail = gmailService.getThreadById(activeId);
  const extractedIntel = activeId ? gmailService.getExtractedIntelligence(activeId) : [];

  if (!gmailService.isLoaded()) {
    return (
      <div>
        <PageHeader
          breadcrumb={['Workspace', 'Gmail Intelligence']}
          title="Gmail Intelligence"
          subtitle="Turn project conversations into traceable decisions, risks, and actions."
        />
        <div className="card" style={{ padding: '24px', color: '#64748B', fontSize: '0.875rem' }}>
          Loading live Gmail data from the KnowledgeOps API…
        </div>
      </div>
    );
  }

  const visibleMessages = threadDetail
    ? (expanded ? threadDetail.messages : threadDetail.messages.slice(0, 2))
    : [];
  const hiddenMessages = threadDetail ? threadDetail.messages.slice(2) : [];
  const hiddenSenders = [...new Set(hiddenMessages.map(m => m.sender))].join(' and ');

  return (
    <div>
      <PageHeader 
        breadcrumb={['Workspace', 'Gmail Intelligence']}
        title="Gmail Intelligence"
        subtitle="Turn project conversations into traceable decisions, risks, and actions."
        actions={
          <div style={{ display: 'flex', gap: '10px' }}>
            <button className="btn btn-secondary">
              <ExternalLink size={15} />
              <span>Open Gmail</span>
            </button>
            <button 
              onClick={() => navigateTo('ask')}
              className="btn btn-primary"
            >
              <Sparkles size={15} />
              <span>Ask KnowledgeOps</span>
            </button>
          </div>
        }
      />

      {/* 4 Metric Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '16px', marginBottom: '20px' }}>
        <div className="card card-sm">
          <div style={{ color: '#64748B', fontSize: '0.75rem', marginBottom: '4px' }}>Relevant Emails</div>
          <div style={{ fontSize: '1.6rem', fontWeight: 800, color: '#0F172A' }}>{gmailService.getRelevantEmailCount()}</div>
          <div style={{ fontSize: '0.7rem', color: '#64748B', marginTop: '2px' }}>Project inbox · All projects</div>
        </div>

        <div className="card card-sm">
          <div style={{ color: '#64748B', fontSize: '0.75rem', marginBottom: '4px' }}>Received this week</div>
          <div style={{ fontSize: '1.6rem', fontWeight: 800, color: '#0F172A' }}>{gmailService.getReceivedThisWeekCount()}</div>
          <div style={{ fontSize: '0.7rem', color: '#64748B', marginTop: '2px' }}>Last 7 days</div>
        </div>

        <div className="card card-sm">
          <div style={{ color: '#64748B', fontSize: '0.75rem', marginBottom: '4px' }}>Project Risks</div>
          <div style={{ fontSize: '1.6rem', fontWeight: 800, color: '#0F172A' }}>{stats.project_risks_count}</div>
          <div style={{ fontSize: '0.7rem', color: '#D97706', fontWeight: 600, marginTop: '2px' }}>
            Cross-source · {summary.risksHigh} need attention
          </div>
        </div>

        <div className="card card-sm">
          <div style={{ color: '#64748B', fontSize: '0.75rem', marginBottom: '4px' }}>Pending Actions</div>
          <div style={{ fontSize: '1.6rem', fontWeight: 800, color: '#0F172A' }}>{summary.actions}</div>
          <div style={{ fontSize: '0.7rem', color: '#2563EB', fontWeight: 600, marginTop: '2px' }}>
            Cross-source · {summary.actionsToday} due today
          </div>
        </div>
      </div>

      {/* Search & Filter Bar */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '16px', marginBottom: '20px' }}>
        <div style={{ position: 'relative', flex: 1, maxWidth: '440px' }}>
          <Search size={15} color="#94A3B8" style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)' }} />
          <input 
            type="text" 
            className="input" 
            placeholder="Search conversations or extracted insights" 
            style={{ paddingLeft: '34px' }}
          />
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <select className="select" style={{ width: 'auto', fontSize: '0.775rem', padding: '6px 12px' }}>
            <option>All projects</option>
            <option>Platform API</option>
            <option>Customer Portal</option>
          </select>

          <select className="select" style={{ width: 'auto', fontSize: '0.775rem', padding: '6px 12px' }}>
            <option>All categories</option>
            <option>Risks</option>
            <option>Decisions</option>
            <option>Actions</option>
          </select>

          <span style={{ fontSize: '0.75rem', color: '#059669', fontWeight: 600, marginLeft: '8px' }}>
            Synced {synced}
          </span>
        </div>
      </div>

      {/* Main 2-Column Split */}
      <div style={{ display: 'grid', gridTemplateColumns: '400px 1fr', gap: '20px' }}>
        {/* Left Column: Relevant Conversations List */}
        <div>
          <div style={{ marginBottom: '8px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h3 style={{ fontSize: '0.875rem', fontWeight: 700, color: '#0F172A' }}>Relevant conversations</h3>
            <span style={{ fontSize: '0.725rem', color: '#64748B' }}>
              Showing {threads.length} of {allThreads.length} threads
            </span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {threads.map((t) => (
              <div 
                key={t.id}
                onClick={() => { setSelectedThreadId(t.id); setExpanded(false); }}
                style={{
                  padding: '14px',
                  background: activeId === t.id ? '#EFF6FF' : '#FFFFFF',
                  border: `1px solid ${activeId === t.id ? '#2563EB' : '#E2E8F0'}`,
                  borderRadius: '8px',
                  cursor: 'pointer'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
                  <span className={`badge badge-${t.category === 'Risk' ? 'amber' : t.category === 'Decision' ? 'purple' : t.category === 'Action' ? 'blue' : 'gray'}`} style={{ fontSize: '0.65rem' }}>
                    {t.category}
                  </span>
                  <span style={{ fontSize: '0.7rem', color: '#94A3B8' }}>{shortDate(t.last_message_at)}</span>
                </div>
                <div style={{ fontWeight: 700, fontSize: '0.85rem', color: '#0F172A', marginBottom: '2px' }}>
                  {t.subject}
                </div>
                <div style={{ fontSize: '0.725rem', color: '#64748B', marginBottom: '4px' }}>
                  {t.participants.join(', ')}
                </div>
                <p style={{ fontSize: '0.75rem', color: '#334155', marginBottom: '8px', lineHeight: 1.4 }}>
                  {t.snippet}
                </p>
                <div style={{ fontSize: '0.675rem', color: '#64748B' }}>
                  {t.project_name} · {t.message_count} messages
                </div>
              </div>
            ))}
          </div>

          {allThreads.length > priorityThreads.length && (
            <div
              onClick={() => setShowAll(!showAll)}
              style={{ textAlign: 'center', fontSize: '0.75rem', color: '#2563EB', fontWeight: 600, marginTop: '12px', cursor: 'pointer' }}
            >
              {showAll
                ? '↑ Show priority threads only'
                : `Load ${allThreads.length - priorityThreads.length} more conversations →`}
            </div>
          )}
        </div>

        {/* Right Column: Selected Thread Details & Extracted Intelligence */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {/* Upper Box: Email Thread View */}
          <div className="card">
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <h3 style={{ fontSize: '1.05rem', fontWeight: 800, color: '#0F172A' }}>
                  {threadDetail.subject}
                </h3>
                <span className="badge badge-purple">Email</span>
                {threadDetail.is_release_blocker && <span className="badge badge-amber">Release blocker</span>}
              </div>
              <span style={{ fontSize: '0.75rem', color: '#64748B' }}>{threadDetail.message_count || threadDetail.messages.length} messages</span>
            </div>

            <div style={{ fontSize: '0.75rem', color: '#64748B', marginBottom: '16px' }}>
              {threadDetail.project_name} · Thread {threadDetail.id} · {longDate(threadDetail.last_message_at || threadDetail.created_at)}
            </div>

            {/* Render Thread Messages */}
            {visibleMessages.map((msg, mIdx) => (
              <div key={msg.id || mIdx} style={{ padding: '14px', background: '#F8FAFC', borderRadius: '8px', border: '1px solid #E2E8F0', marginBottom: '12px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                  <strong style={{ fontSize: '0.85rem', color: '#0F172A' }}>{msg.sender}</strong>
                  <span style={{ fontSize: '0.7rem', color: '#94A3B8' }}>{msgTime(msg.received_at)}</span>
                </div>
                {msg.recipients && (
                  <div style={{ fontSize: '0.725rem', color: '#64748B', marginBottom: '8px' }}>
                    {Array.isArray(msg.recipients) ? msg.recipients.join(', ') : msg.recipients}
                  </div>
                )}
                <p style={{ fontSize: '0.8rem', color: '#334155', lineHeight: 1.5 }}>
                  {msg.body}
                </p>
              </div>
            ))}

            {/* Expand control */}
            {hiddenMessages.length > 0 && (
              <div
                onClick={() => setExpanded(!expanded)}
                style={{ padding: '8px 12px', background: '#F1F5F9', borderRadius: '6px', fontSize: '0.75rem', color: '#475569', cursor: 'pointer', textAlign: 'center', marginBottom: '16px' }}
              >
                {expanded
                  ? '[-] Hide expanded messages'
                  : `[+] ${hiddenMessages.length} more message${hiddenMessages.length > 1 ? 's' : ''} · ${hiddenSenders} Expand`}
              </div>
            )}
            {hiddenMessages.length === 0 && <div style={{ marginBottom: '16px' }}></div>}

            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '0.725rem', color: '#64748B' }}>
              <span>Original source retained · Read-only</span>
              <span style={{ color: '#2563EB', fontWeight: 600, cursor: 'pointer' }}>Open thread in Gmail ↗</span>
            </div>
          </div>

          {/* Lower Box: Extracted Intelligence */}
          <div className="card">
            <div style={{ marginBottom: '14px' }}>
              <h3 style={{ fontSize: '0.95rem', fontWeight: 700, color: '#0F172A' }}>Extracted intelligence</h3>
              <div style={{ fontSize: '0.725rem', color: '#64748B' }}>
                Cross-checked against GitHub · derived from {activeId} records
              </div>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {extractedIntel.length === 0 && (
                <div style={{ padding: '14px', borderRadius: '6px', background: '#F8FAFC', border: '1px solid #E2E8F0', fontSize: '0.775rem', color: '#64748B' }}>
                  No extracted decisions, risks or actions recorded for thread {activeId}.
                </div>
              )}
              {extractedIntel.map((item, idx) => (
                <div 
                  key={idx} 
                  style={{ 
                    padding: '12px', 
                    background: item.type === 'Action' ? '#EFF6FF' : '#F8FAFC', 
                    borderRadius: '6px', 
                    border: `1px solid ${item.type === 'Action' ? '#BFDBFE' : '#E2E8F0'}` 
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px' }}>
                    <span className={`badge badge-${item.typeColor}`} style={{ fontSize: '0.65rem' }}>{item.type}</span>
                    <strong style={{ fontSize: '0.825rem', color: item.type === 'Action' ? '#1E40AF' : '#0F172A' }}>{item.title}</strong>
                  </div>
                  {item.description && (
                    <p style={{ fontSize: '0.775rem', color: '#475569', marginBottom: '6px' }}>
                      {item.description}
                    </p>
                  )}
                  {item.suggestedOwners && (
                    <div style={{ fontSize: '0.75rem', color: '#1E3A8A', marginBottom: '8px' }}>
                      Suggested owners: <strong>{item.suggestedOwners}</strong> | Due: <strong>{item.due}</strong>
                    </div>
                  )}
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '0.675rem', color: '#64748B' }}>
                    <span>{item.source || item.status}</span>
                    {item.type === 'Action' && (
                      <button 
                        onClick={() => navigateTo('workflows')}
                        className="btn btn-primary btn-sm"
                      >
                        <span>→ Review action</span>
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
