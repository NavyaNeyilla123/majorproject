import React, { useState } from 'react';
import { Database, ExternalLink, Filter, User, Clock } from 'lucide-react';

export default function EvidenceViewer({ evidence }) {
  const [filterSource, setFilterSource] = useState('ALL');

  const sources = ['ALL', 'Jira', 'GitHub', 'Confluence', 'Slack'];

  const filteredEvidence = filterSource === 'ALL'
    ? evidence
    : evidence.filter(e => e.source.toLowerCase() === filterSource.toLowerCase());

  const getSourceBadgeClass = (s) => {
    switch (s) {
      case 'Jira': return 'badge-jira';
      case 'GitHub': return 'badge-github';
      case 'Confluence': return 'badge-confluence';
      case 'Slack': return 'badge-slack';
      default: return 'badge-jira';
    }
  };

  return (
    <div className="glass-card" style={{ padding: '24px', marginBottom: '24px' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '18px', flexWrap: 'wrap', gap: '12px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <Database size={20} color="#60A5FA" />
          <h3 style={{ fontSize: '1.05rem', fontWeight: 700, margin: 0, color: '#F3F4F6' }}>
            Retrieved Cross-Platform Evidence ({filteredEvidence.length})
          </h3>
        </div>

        {/* Source Filter Tabs */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', background: 'var(--bg-input)', padding: '4px', borderRadius: '8px' }}>
          <Filter size={14} color="var(--text-muted)" style={{ margin: '0 4px' }} />
          {sources.map(src => (
            <button
              key={src}
              onClick={() => setFilterSource(src)}
              style={{
                background: filterSource === src ? '#2563EB' : 'transparent',
                color: filterSource === src ? '#FFF' : 'var(--text-muted)',
                border: 'none',
                padding: '4px 10px',
                borderRadius: '6px',
                fontSize: '0.75rem',
                fontWeight: 600,
                cursor: 'pointer',
                transition: 'all 0.15s ease'
              }}
            >
              {src}
            </button>
          ))}
        </div>
      </div>

      {filteredEvidence.length === 0 ? (
        <div style={{ padding: '30px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.9rem' }}>
          No evidence items match the selected source filter.
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', gap: '16px' }}>
          {filteredEvidence.map((item, idx) => (
            <div 
              key={idx} 
              style={{
                background: 'var(--bg-input)',
                border: '1px solid var(--border-color)',
                borderRadius: '10px',
                padding: '16px',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between',
                transition: 'transform 0.15s ease, border-color 0.15s ease'
              }}
            >
              <div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                  <span className={`badge ${getSourceBadgeClass(item.source)}`}>
                    {item.source} • {item.document_id}
                  </span>
                  <span style={{ fontSize: '0.72rem', color: '#60A5FA', fontFamily: 'var(--font-mono)', fontWeight: 600 }}>
                    Score: {(item.score * 100).toFixed(1)}%
                  </span>
                </div>

                <h4 style={{ fontSize: '0.92rem', fontWeight: 700, color: '#F3F4F6', marginBottom: '8px' }}>
                  {item.title}
                </h4>

                <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', lineHeight: '1.5', marginBottom: '12px' }}>
                  "{item.content}"
                </p>
              </div>

              <div style={{
                borderTop: '1px solid var(--border-color)',
                paddingTop: '8px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                fontSize: '0.72rem',
                color: 'var(--text-dim)'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <User size={12} /> {item.author || 'N/A'}
                  </span>
                  {item.timestamp && (
                    <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                      <Clock size={12} /> {new Date(item.timestamp).toLocaleDateString()}
                    </span>
                  )}
                </div>

                <a 
                  href={item.url || '#'} 
                  target="_blank" 
                  rel="noreferrer" 
                  style={{ color: '#60A5FA', display: 'flex', alignItems: 'center', gap: '2px', textDecoration: 'none' }}
                >
                  <span>Open</span>
                  <ExternalLink size={12} />
                </a>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
