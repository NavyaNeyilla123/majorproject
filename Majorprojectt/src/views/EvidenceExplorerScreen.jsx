import React, { useState, useEffect } from 'react';
import { 
  Sparkles, 
  Download, 
  Search, 
  ArrowUpRight, 
  Copy, 
  Info
} from 'lucide-react';
import PageHeader from '../components/PageHeader';
import { GmailIcon, GitHubIcon } from '../components/Icons';
import { evidenceService } from '../services/evidenceService';
import useCacheTick from '../hooks/useCacheTick';

export default function EvidenceExplorerScreen({ navigateTo }) {
  const [selectedRecordId, setSelectedRecordId] = useState(null);
  const [activeFilter, setActiveFilter] = useState('All');
  useCacheTick();

  useEffect(() => {
    evidenceService.sync();
  }, []);

  const loaded = evidenceService.isLoaded();
  const counts = evidenceService.getCounts();
  const priorityRecords = evidenceService.getPriorityRecords();
  const detail = evidenceService.getEvidenceDetail(selectedRecordId);
  const activeRecordId = selectedRecordId ?? (priorityRecords[0] ? priorityRecords[0].id : null);
  const dash = '…';

  return (
    <div>
      <PageHeader 
        breadcrumb={['Workspace', 'Evidence Explorer']}
        title="Evidence Explorer"
        subtitle="Inspect the original records behind every project claim, decision, and risk."
        actions={
          <div style={{ display: 'flex', gap: '10px' }}>
            <button className="btn btn-secondary">
              <Download size={15} />
              <span>Export citations</span>
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

      {/* Search & Filter Controls */}
      <div style={{ marginBottom: '16px' }}>
        <div style={{ display: 'flex', gap: '12px', marginBottom: '12px' }}>
          <div style={{ position: 'relative', flex: 1 }}>
            <Search size={15} color="#94A3B8" style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)' }} />
            <input 
              type="text" 
              className="input" 
              placeholder="Search evidence, citations, or conversations" 
              style={{ paddingLeft: '34px' }}
            />
          </div>
          <select className="select" style={{ width: 'auto' }}><option>All projects</option></select>
          <select className="select" style={{ width: 'auto' }}><option>GitHub + Gmail</option></select>
          <select className="select" style={{ width: 'auto' }}><option>Last 7 days</option></select>
        </div>

        {/* Filter Pills */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', gap: '8px' }}>
            {[
              `All records · ${counts.allRecords ?? dash}`, 
              `Email · ${counts.email ?? dash}`, 
              `Decision · ${counts.decision ?? dash}`, 
              `Risk · ${counts.risk ?? dash}`
            ].map((pill, idx) => {
              const label = pill.split(' ')[0];
              const isActive = (label === 'All' && activeFilter === 'All') || activeFilter === label;
              return (
                <button 
                  key={idx} 
                  onClick={() => setActiveFilter(label)}
                  style={{
                    padding: '4px 12px',
                    borderRadius: '16px',
                    fontSize: '0.75rem',
                    fontWeight: 600,
                    border: `1px solid ${isActive ? '#2563EB' : '#CBD5E1'}`,
                    background: isActive ? '#EFF6FF' : '#FFFFFF',
                    color: isActive ? '#2563EB' : '#475569',
                    cursor: 'pointer'
                  }}
                >
                  {pill}
                </button>
              );
            })}
          </div>
          <span style={{ fontSize: '0.7rem', color: '#94A3B8' }}>Intelligence labels can overlap source records</span>
        </div>
      </div>

      {/* Main 2-Column Split */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 420px', gap: '20px' }}>
        {/* Left Column: Priority Records List */}
        <div>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
            <h3 style={{ fontSize: '0.875rem', fontWeight: 700, color: '#0F172A' }}>
              {loaded ? `${priorityRecords.length} priority records` : 'Loading priority records…'}
            </h3>
            <select className="select" style={{ width: 'auto', fontSize: '0.725rem', padding: '2px 6px' }}>
              <option>Sort: Relevance ↓</option>
            </select>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', marginBottom: '16px' }}>
            {!loaded && priorityRecords.length === 0 && (
              <div style={{ padding: '14px', textAlign: 'center', fontSize: '0.775rem', color: '#64748B', background: '#F8FAFC', border: '1px dashed #E2E8F0', borderRadius: '8px' }}>
                Loading evidence from the backend…
              </div>
            )}
            {priorityRecords.map((rec) => (
              <div 
                key={rec.id}
                onClick={() => setSelectedRecordId(rec.id)}
                style={{
                  padding: '14px',
                  background: activeRecordId === rec.id ? '#EFF6FF' : '#FFFFFF',
                  border: `1px solid ${activeRecordId === rec.id ? '#2563EB' : '#E2E8F0'}`,
                  borderRadius: '8px',
                  cursor: 'pointer'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
                  <div style={{ display: 'flex', gap: '6px' }}>
                    <span className={`badge badge-${rec.typeColor}`} style={{ fontSize: '0.65rem' }}>{rec.type}</span>
                    <span className="badge badge-gray" style={{ fontSize: '0.65rem' }}>{rec.project}</span>
                  </div>
                  <ArrowUpRight size={14} color="#64748B" />
                </div>
                <div style={{ fontWeight: 700, fontSize: '0.875rem', color: '#0F172A', marginBottom: '2px' }}>
                  {rec.title}
                </div>
                <div style={{ fontSize: '0.75rem', color: '#475569', marginBottom: '6px' }}>
                  {rec.subtitle}
                </div>
                <div style={{ fontSize: '0.7rem', color: '#64748B' }}>
                  {rec.source}
                </div>
              </div>
            ))}
          </div>

          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '0.75rem', color: '#64748B' }}>
            <span>Showing {priorityRecords.length} of {counts.allRecords ?? dash} indexed source records</span>
            <button className="btn btn-secondary btn-sm">Load more</button>
          </div>
        </div>

        {/* Right Column: Detailed Evidence Excerpt View */}
        <div className="card">
          {!detail ? (
            <div style={{ padding: '24px', textAlign: 'center', fontSize: '0.775rem', color: '#64748B' }}>
              {loaded ? 'No evidence record selected.' : 'Loading evidence detail from the backend…'}
            </div>
          ) : (
          <>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
            <h3 style={{ fontSize: '0.9rem', fontWeight: 700, color: '#0F172A' }}>Evidence detail</h3>
            <span style={{ fontSize: '0.725rem', color: '#2563EB', fontWeight: 600, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px' }}>
              <Copy size={12} /> Copy citation
            </span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
            {detail.sourceIcon === 'gmail' ? <GmailIcon size={16} /> : <GitHubIcon size={16} />}
            {(detail.badges.length ? detail.badges : [{ label: 'Email', color: 'blue' }]).map((b, idx) => (
              <span key={idx} className={`badge badge-${b.color}`} style={{ fontSize: '0.65rem' }}>{b.label}</span>
            ))}
          </div>

          <h2 style={{ fontSize: '1.05rem', fontWeight: 800, color: '#0F172A', marginBottom: '2px' }}>
            {detail.title}
          </h2>
          <div style={{ fontSize: '0.75rem', color: '#64748B', marginBottom: '16px' }}>
            {detail.thread}
          </div>

          {/* Metadata Block */}
          <div style={{ fontSize: '0.775rem', color: '#475569', display: 'flex', flexDirection: 'column', gap: '6px', marginBottom: '16px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>Author:</span>
              <strong style={{ color: '#0F172A' }}>{detail.author}</strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>Received:</span>
              <strong style={{ color: '#0F172A' }}>{detail.receivedAt}</strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>Project:</span>
              <strong style={{ color: '#0F172A' }}>{detail.project}</strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>Source access:</span>
              <strong style={{ color: '#0F172A' }}>{detail.sourceAccess}</strong>
            </div>
          </div>

          {/* Highlighted Quote Excerpt */}
          <div style={{ padding: '14px', background: '#F8FAFC', borderLeft: '3px solid #2563EB', borderRadius: '4px', marginBottom: '14px' }}>
            <div style={{ fontSize: '0.675rem', fontWeight: 700, color: '#64748B', letterSpacing: '0.5px', marginBottom: '6px' }}>
              {detail.excerptLines}
            </div>
            <p style={{ fontSize: '0.825rem', color: '#0F172A', fontStyle: 'italic', lineHeight: 1.5 }}>
              "{detail.originalExcerpt}"
            </p>
          </div>

          <button className="btn btn-secondary btn-sm" style={{ width: '100%', marginBottom: '16px' }}>
            <span>{detail.openLabel}</span>
          </button>

          {/* Claims Supported */}
          <div style={{ marginBottom: '16px' }}>
            <h4 style={{ fontSize: '0.8rem', fontWeight: 700, color: '#0F172A', marginBottom: '6px' }}>
              Claims supported by this record
            </h4>
            <ul style={{ paddingLeft: '16px', fontSize: '0.75rem', color: '#475569', display: 'flex', flexDirection: 'column', gap: '4px' }}>
              {detail.claimsSupported.map((claim, idx) => (
                <li key={idx}>{claim}</li>
              ))}
            </ul>
          </div>

          {/* Info Box */}
          <div className="alert-box alert-blue" style={{ padding: '10px', fontSize: '0.725rem', marginBottom: '16px' }}>
            <Info size={14} color="#2563EB" style={{ flexShrink: 0 }} />
            <div>
              <strong style={{ display: 'block', color: '#1E40AF' }}>Keep the source timestamp in context</strong>
              {detail.contextNote}
            </div>
          </div>

          {/* Linked Intelligence */}
          <div style={{ marginBottom: '16px' }}>
            <h4 style={{ fontSize: '0.8rem', fontWeight: 700, color: '#0F172A', marginBottom: '6px' }}>
              Linked intelligence
            </h4>
            <div style={{ padding: '10px', background: '#F8FAFC', borderRadius: '6px', border: '1px solid #E2E8F0' }}>
              <div style={{ fontWeight: 700, fontSize: '0.8rem', color: '#0F172A', marginBottom: '2px' }}>
                {detail.linkedIntelligence.title}
              </div>
              <div style={{ fontSize: '0.7rem', color: '#64748B', marginBottom: '4px' }}>
                {detail.linkedIntelligence.sources}
              </div>
              <span 
                onClick={() => navigateTo('answer')}
                style={{ fontSize: '0.725rem', color: '#2563EB', fontWeight: 600, cursor: 'pointer' }}
              >
                View AI answer →
              </span>
              <div style={{ fontSize: '0.675rem', color: '#94A3B8', marginTop: '4px' }}>
                {detail.linkedIntelligence.context}
              </div>
            </div>
          </div>

          {/* Retrieval Metadata */}
          <div style={{ borderTop: '1px solid #F1F5F9', paddingTop: '12px' }}>
            <h4 style={{ fontSize: '0.8rem', fontWeight: 700, color: '#0F172A', marginBottom: '6px' }}>
              Retrieval metadata
            </h4>
            <div style={{ fontSize: '0.7rem', color: '#64748B', display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>Citation ID:</span>
                <strong>{detail.metadata.citationId}</strong>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>Chunk:</span>
                <strong>{detail.metadata.chunk}</strong>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>Snapshot:</span>
                <strong>{detail.metadata.snapshot}</strong>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>Index:</span>
                <strong>{detail.metadata.index}</strong>
              </div>
            </div>
            <div style={{ fontSize: '0.65rem', color: '#94A3B8', marginTop: '6px' }}>
              Source permissions checked. Excerpt preserved; classification is AI-generated.
            </div>
          </div>
          </>
          )}
        </div>
      </div>
    </div>
  );
}
